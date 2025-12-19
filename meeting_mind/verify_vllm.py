import os
from vllm import LLM, SamplingParams

# 设置环境变量以适应 WSL/Windows
os.environ["CUDA_VISIBLE_DEVICES"] = "0"


def test_vllm():
    print("正在测试 vLLM 环境...")
    try:
        # 使用一个小模型或假数据进行测试，或者直接加载目标模型
        # 这里尝试加载目标模型，注意显存
        model_id = "Qwen/Qwen2.5-1.5B-Instruct"
        print(f"尝试加载模型: {model_id}")

        # 注意：LLM 类是同步的，AsyncLLMEngine 是异步的
        # 这里使用同步类进行简单验证
        llm = LLM(model=model_id, trust_remote_code=True, gpu_memory_utilization=0.6)

        prompts = ["Hello, my name is"]
        sampling_params = SamplingParams(temperature=0.8, top_p=0.95)

        outputs = llm.generate(prompts, sampling_params)

        for output in outputs:
            prompt = output.prompt
            generated_text = output.outputs[0].text
            print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")

        print("vLLM 环境验证成功！")

    except Exception as e:
        print(f"vLLM 验证失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_vllm()
