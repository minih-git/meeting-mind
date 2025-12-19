import os
import time
import threading
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from modelscope import snapshot_download
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
from meeting_mind.app.core.config import settings
from meeting_mind.app.core.logger import logger


class LLMEngine:
    _instance = None
    _engine: Optional[Any] = None
    _tokenizer: Optional[Any] = None
    _mode: str = "cuda"  # "cuda" (vLLM) or "cpu" (Transformers)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMEngine, cls).__new__(cls)
        return cls._instance

    def load_model(self):
        """
        初始化 LLM 引擎。
        """
        if self._engine is not None:
            return

        self._mode = settings.LLM_DEVICE.lower()
        self._provider = getattr(settings, "LLM_PROVIDER", "local")

        if self._provider == "cloud":
            logger.info(f"使用云端 LLM Provider: {settings.CLOUD_LLM_MODEL}")
            import openai

            openai.api_key = settings.CLOUD_LLM_API_KEY
            openai.base_url = settings.CLOUD_LLM_API_BASE
            return

        logger.info(
            f"正在准备加载 LLM 模型: {settings.LLM_MODEL_ID}, 模式: {self._mode}"
        )

        try:
            # 优先检查本地模型路径，避免非必要的联网检查
            local_model_path = os.path.join(settings.MODELS_DIR, settings.LLM_MODEL_ID)
            if os.path.exists(local_model_path):
                logger.info(f"发现本地模型，直接加载: {local_model_path}")
                model_path = local_model_path
            else:
                logger.info(
                    f"本地模型未找到 ({local_model_path})，尝试从 ModelScope 下载/加载..."
                )
                # 确保模型已下载并获取本地路径
                model_path = snapshot_download(
                    settings.LLM_MODEL_ID, cache_dir=settings.MODELS_DIR
                )
            logger.info(f"模型路径: {model_path}")

            # 初始化 Tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_path, trust_remote_code=True
            )

            if self._mode == "cuda":
                self._load_vllm(model_path)
            else:
                self._load_cpu(model_path)

            logger.info(f"LLM 引擎 ({self._mode}) 加载完成")

        except Exception as e:
            logger.error(f"LLM 引擎加载失败: {e}")
            raise e

    def _load_vllm(self, model_path):
        from vllm.engine.async_llm_engine import AsyncLLMEngine
        from vllm.engine.arg_utils import AsyncEngineArgs

        engine_args = AsyncEngineArgs(
            model=model_path,
            trust_remote_code=True,
            gpu_memory_utilization=settings.VLLM_GPU_MEMORY_UTILIZATION,
            max_model_len=settings.VLLM_MAX_MODEL_LEN,
        )
        self._engine = AsyncLLMEngine.from_engine_args(engine_args)

    def _load_cpu(self, model_path):
        import torch

        # CPU 模式下加载模型
        self._engine = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="cpu",
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )
        self._engine.eval()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        stream: bool = False,
        force_cloud: bool = False,
    ) -> AsyncGenerator[str, None] | Dict[str, Any]:

        if self._provider == "cloud" or force_cloud:
            return await self._chat_cloud(messages, temperature, max_tokens, stream)

        if self._engine is None:
            return await self._chat_cloud(messages, temperature, max_tokens, stream)

        if self._mode == "cuda":
            return await self._chat_vllm(messages, temperature, max_tokens, stream)
        else:
            if stream:
                return self._chat_cpu_stream(messages, temperature, max_tokens)
            else:
                return await asyncio.to_thread(
                    self._chat_cpu_sync, messages, temperature, max_tokens
                )

    async def _chat_cloud(self, messages, temperature, max_tokens, stream):
        import openai
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.CLOUD_LLM_API_KEY,
            base_url=settings.CLOUD_LLM_API_BASE,
        )

        try:
            response = await client.chat.completions.create(
                model=settings.CLOUD_LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )

            if stream:

                async def stream_gen():
                    async for chunk in response:
                        content = chunk.choices[0].delta.content
                        if content:
                            yield content

                return stream_gen()
            else:
                content = response.choices[0].message.content
                usage = response.usage
                return {
                    "content": content,
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    },
                }
        except Exception as e:
            logger.error(f"Cloud LLM request failed: {e}")
            raise e

    async def _chat_vllm(self, messages, temperature, max_tokens, stream):
        from vllm.sampling_params import SamplingParams

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            stop_token_ids=[self._tokenizer.eos_token_id, self._tokenizer.pad_token_id],
        )

        request_id = f"req_{os.urandom(4).hex()}"
        results_generator = self._engine.generate(prompt, sampling_params, request_id)

        if stream:

            async def stream_gen():
                previous_text = ""
                async for request_output in results_generator:
                    current_text = request_output.outputs[0].text
                    new_text = current_text[len(previous_text) :]
                    previous_text = current_text
                    if new_text:
                        yield new_text

            return stream_gen()
        else:
            start_time = time.time()
            final_output = ""
            usage = {}
            async for request_output in results_generator:
                final_output = request_output.outputs[0].text
                # 手动计算 token
                prompt_tokens = len(request_output.prompt_token_ids)
                completion_tokens = len(request_output.outputs[0].token_ids)
                total_tokens = prompt_tokens + completion_tokens

                end_time = time.time()
                total_time = end_time - start_time
                speed = total_tokens / total_time if total_time > 0 else 0

                usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "total_time_sec": round(total_time, 3),
                    "tokens_per_sec": round(speed, 2),
                }
            return {"content": final_output, "usage": usage}

    def _chat_cpu_sync(self, messages, temperature, max_tokens):
        import torch

        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_inputs = self._tokenizer([text], return_tensors="pt").to("cpu")
        prompt_tokens = len(model_inputs.input_ids[0])

        start_time = time.time()
        generated_ids = self._engine.generate(
            model_inputs.input_ids,
            attention_mask=model_inputs.attention_mask,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True,
        )
        end_time = time.time()

        new_tokens = generated_ids[0][len(model_inputs.input_ids[0]) :]
        completion_tokens = len(new_tokens)
        total_tokens = prompt_tokens + completion_tokens

        total_time = end_time - start_time
        speed = total_tokens / total_time if total_time > 0 else 0

        response = self._tokenizer.decode(new_tokens, skip_special_tokens=True)

        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "total_time_sec": round(total_time, 3),
            "tokens_per_sec": round(speed, 2),
        }
        return {"content": response, "usage": usage}

    async def _chat_cpu_stream(self, messages, temperature, max_tokens):
        import torch

        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_inputs = self._tokenizer([text], return_tensors="pt").to("cpu")

        streamer = TextIteratorStreamer(
            self._tokenizer, skip_prompt=True, skip_special_tokens=True
        )

        generation_kwargs = dict(
            inputs=model_inputs.input_ids,
            attention_mask=model_inputs.attention_mask,
            streamer=streamer,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True,
        )

        thread = threading.Thread(
            target=self._engine.generate, kwargs=generation_kwargs
        )
        thread.start()

        for new_text in streamer:
            yield new_text
            await asyncio.sleep(0)

    def shutdown(self):
        """
        关闭 LLM 引擎并释放资源。
        """
        logger.info("正在关闭 LLM 引擎...")
        if self._mode == "cuda":
            try:
                import torch.distributed as dist

                if dist.is_initialized():
                    dist.destroy_process_group()
                    logger.info("Distributed process group destroyed.")
            except Exception as e:
                logger.warning(f"Error destroying process group: {e}")

            # 尝试释放显存
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        self._engine = None
        self._tokenizer = None
        logger.info("LLM 引擎已关闭")


llm_engine = LLMEngine()
