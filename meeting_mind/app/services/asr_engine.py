import os
import time
import sys
from contextlib import contextmanager
import numpy as np
from funasr import AutoModel
import noisereduce as nr
from meeting_mind.app.core.config import settings
from meeting_mind.app.core.logger import logger


class ASREngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ASREngine, cls).__new__(cls)
            cls._instance.asr_model = None
            cls._instance.vad_model = None
            cls._instance.punc_model = None
            cls._instance.cache = (
                {}
            )  # session_id -> {asr_cache, vad_cache, punc_cache} 会话缓存
            cls._instance.speaker_registry = {}  # speaker_id -> embedding

            # Queue for async processing
            cls._instance.queue = None
            cls._instance.worker_task = None
            cls._instance.callbacks = {}  # session_id -> callback function

        return cls._instance

    @contextmanager
    def _suppress_stdout(self):
        """临时屏蔽 stdout 以隐藏第三方库的 print 输出"""
        with open(os.devnull, "w") as devnull:
            old_stdout = sys.stdout
            sys.stdout = devnull
            try:
                yield
            finally:
                sys.stdout = old_stdout

    def load_models(self):
        """分别加载 FunASR 模型到内存中。"""
        if self.asr_model is not None:
            logger.info("模型已加载。")
            return

        logger.info("正在加载 FunASR 模型...")
        try:
            with self._suppress_stdout():
                # 加载 ASR 模型
                # logger.info("  - 加载 ASR 模型...") # 移动到 suppress 之外或接受它被屏蔽(如果输出到stdout)
                # Loguru 默认输出到 stderr，所以应该不受影响
                pass

                self.asr_model = AutoModel(
                    model=settings.ASR_MODEL_PATH,
                    disable_update=True,
                    device=settings.ASR_DEVICE,
                )

                # 加载 VAD 模型
                self.vad_model = AutoModel(
                    model=settings.VAD_MODEL_PATH,
                    disable_update=True,
                    device=settings.ASR_DEVICE,
                )

                # 加载标点模型
                try:
                    self.punc_model = AutoModel(
                        model=settings.PUNC_MODEL_PATH,
                        disable_update=True,
                        device=settings.ASR_DEVICE,
                    )
                except Exception as e:
                    # logger.warning...
                    self.punc_model = None

                # 加载说话人模型
                self.speaker_model = AutoModel(
                    model=settings.SPEAKER_MODEL_PATH,
                    disable_update=True,
                    device=settings.ASR_DEVICE,
                )

            logger.info("  ✓ ASR 模型加载成功")
            logger.info("  ✓ VAD 模型加载成功")
            if self.punc_model:
                logger.info("  ✓ 标点模型加载成功")
            logger.info("  ✓ 说话人模型加载成功")

            logger.info("🎉 所有模型加载完成!")
        except Exception as e:
            logger.error(f"❌ 加载模型出错: {e}")
            raise e

    def _cosine_similarity(self, v1, v2):
        """计算两个向量的余弦相似度"""
        # 确保是一维数组
        v1 = np.squeeze(v1)
        v2 = np.squeeze(v2)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return np.dot(v1, v2) / (norm1 * norm2)

    def detect_gender(self, audio_chunk: bytes):
        """
        基于音高检测性别 (Heuristic)
        Male: < 165Hz
        Female: > 165Hz
        """
        try:
            import librosa

            # 转换为 float32
            audio_np = (
                np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            )

            # 使用 librosa.pyin 进行音高跟踪
            # 帧长 ~ 30ms
            f0, voiced_flag, voiced_probs = librosa.pyin(
                audio_np,
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7"),
                sr=16000,
            )

            # 过滤 NaN
            f0 = f0[~np.isnan(f0)]

            if len(f0) == 0:
                return "未知"

            avg_pitch = np.mean(f0)
            logger.debug(f"检测到的音高: {avg_pitch:.2f} Hz")

            if avg_pitch < 165:
                return "男"
            else:
                return "女"
        except Exception as e:
            logger.error(f"性别检测失败: {e}")
            return "未知"

    def recognize_speaker(self, audio_segment: bytes):
        """
        提取说话人声纹特征并识别说话人。
        """
        if not self.speaker_model:
            logger.warning("说话人模型未加载")
            return "未知"

        if len(audio_segment) < 16000 * 0.5 * 2:  # 最小 0.5秒 (16k * 2 字节)
            logger.debug(f"音频片段太短，无法进行说话人识别: {len(audio_segment)} 字节")
            return "未知"

        try:
            # 将字节转换为 numpy 数组
            audio_np = (
                np.frombuffer(audio_segment, dtype=np.int16).astype(np.float32)
                / 32768.0
            )

            res = self.speaker_model.generate(input=audio_np, disable_pbar=True)

            if isinstance(res, list) and len(res) > 0:
                embedding = res[0].get("spk_embedding")
                if embedding is not None:
                    # 如果是 Tensor (GPU/CPU)，转换为 numpy
                    if hasattr(embedding, "cpu"):
                        embedding = embedding.detach().cpu().numpy()
                    elif hasattr(embedding, "numpy"):
                        # 可能是 CPU tensor 但没有 .cpu() ? 通常都有
                        embedding = embedding.numpy()

                    # 简单的说话人聚类/识别逻辑
                    # 阈值通常在 0.25 - 0.4 之间，取决于模型
                    # 降低阈值以提高召回率
                    THRESHOLD = 0.25

                    best_score = -1.0
                    best_speaker = None

                    # 与注册的说话人进行比较
                    for spk_id, data in self.speaker_registry.items():
                        spk_emb = data["embedding"]
                        score = self._cosine_similarity(embedding, spk_emb)
                        if score > best_score:
                            best_score = score
                            best_speaker = spk_id

                    logger.debug(
                        f"说话人匹配得分: {best_score:.4f} (匹配: {best_speaker})"
                    )

                    if best_score > THRESHOLD:
                        # 在线更新：更新声纹中心
                        # new_center = alpha * old_center + (1-alpha) * new_emb
                        # alpha 可以是固定的，也可以基于计数
                        old_emb = self.speaker_registry[best_speaker]["embedding"]
                        count = self.speaker_registry[best_speaker]["count"]

                        # 简单的加权平均
                        alpha = 0.8  # 保持旧特征的权重
                        new_emb = alpha * old_emb + (1 - alpha) * np.squeeze(embedding)
                        # 归一化
                        new_emb = new_emb / np.linalg.norm(new_emb)

                        self.speaker_registry[best_speaker]["embedding"] = new_emb
                        self.speaker_registry[best_speaker]["count"] = count + 1

                        gender = self.speaker_registry[best_speaker]["gender"]
                        return f"{best_speaker} ({gender})"
                    else:
                        # 注册新说话人
                        gender = self.detect_gender(audio_segment)

                        new_id = f"Speaker_{len(self.speaker_registry) + 1}"
                        self.speaker_registry[new_id] = {
                            "embedding": np.squeeze(embedding),
                            "gender": gender,
                            "count": 1,
                        }
                        logger.info(
                            f"注册新说话人: {new_id} ({gender}) (得分: {best_score:.4f})"
                        )
                        return f"{new_id} ({gender})"

            logger.debug("未找到说话人嵌入")
            return "未知"
        except Exception as e:
            logger.error(f"说话人识别错误: {e}")
            return "未知"

    def check_audio_quality(
        self, audio_chunk: bytes, min_energy_threshold: float = 100.0
    ):
        """
        检查音频质量,过滤静音或低能量片段。

        Args:
            audio_chunk: 音频字节数据
            min_energy_threshold: 最小能量阈值

        Returns:
            dict: {"is_valid": bool, "energy": float, "max_amplitude": int}
        """
        if len(audio_chunk) == 0:
            return {"is_valid": False, "energy": 0.0, "max_amplitude": 0}

        try:
            # 转换为numpy数组
            audio_np = np.frombuffer(audio_chunk, dtype=np.int16)

            # 计算最大振幅
            max_amp = np.max(np.abs(audio_np))

            # 计算能量 (RMS)
            audio_float = audio_np.astype(np.float32)
            energy = np.sqrt(np.mean(audio_float**2))

            # 判断是否为有效语音
            is_valid = energy >= min_energy_threshold and max_amp > 50

            return {
                "is_valid": is_valid,
                "energy": float(energy),
                "max_amplitude": int(max_amp),
            }

        except Exception as e:
            logger.error(f"音频质量检测错误: {e}")
            # 出错时假设音频有效,避免丢失数据
            return {"is_valid": True, "energy": 0.0, "max_amplitude": 0}

    def start_worker(self):
        """Start the background worker for processing audio queue."""
        import asyncio

        if self.queue is None:
            self.queue = asyncio.Queue()

        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("ASR background worker started.")

    async def stop_worker(self):
        """Stop the background worker gracefully."""
        if self.queue:
            await self.queue.join()  # Wait for all tasks to be done

        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            self.worker_task = None
            logger.info("ASR background worker stopped.")

    async def enqueue_audio(
        self, session_id: str, audio_chunk: bytes, is_final: bool = False
    ):
        """Add audio chunk to the processing queue."""
        if self.queue is None:
            self.start_worker()

        await self.queue.put((session_id, audio_chunk, is_final))

    def register_callback(self, session_id: str, callback):
        """Register a callback to receive results for a session."""
        self.callbacks[session_id] = callback

    def unregister_callback(self, session_id: str):
        """Unregister callback for a session."""
        if session_id in self.callbacks:
            del self.callbacks[session_id]

    async def _worker(self):
        """Background worker to process audio chunks from queue."""
        import asyncio

        logger.info("ASR Worker loop started")
        while True:
            try:
                session_id, audio_chunk, is_final = await self.queue.get()

                try:
                    # Process the chunk
                    # We run CPU-bound inference in a thread pool to avoid blocking the async loop
                    loop = asyncio.get_running_loop()
                    results = await loop.run_in_executor(
                        None,
                        lambda: self._process_stream(session_id, audio_chunk, is_final),
                    )

                    # Send results back via callback
                    if session_id in self.callbacks:
                        callback = self.callbacks[session_id]
                        if asyncio.iscoroutinefunction(callback):
                            await callback(results, is_final)
                        else:
                            callback(results, is_final)

                except Exception as e:
                    logger.error(
                        f"Error processing audio for session {session_id}: {e}"
                    )
                finally:
                    self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on error

    def _process_stream(
        self, session_id: str, audio_chunk: bytes, is_final: bool = False
    ):
        """
        处理特定会话的音频流。
        使用 VAD 进行分段，仅在检测到完整句子（VAD 片段结束）时触发 ASR 和说话人识别。
        """
        logger.debug(
            f"[{session_id[:8]}] inference_stream: {len(audio_chunk)} bytes, is_final={is_final}"
        )
        if self.asr_model is None:
            raise RuntimeError("Models not loaded. Call load_models() first.")

        # 为新会话初始化缓存
        if session_id not in self.cache:
            self.cache[session_id] = {
                "asr": {},
                "vad": {},
                "punc": {},
                "audio_buffer": bytearray(),  # 累积音频缓冲区
                "buffer_offset_bytes": 0,  # 缓冲区起始字节相对于会话开始的偏移量
                "vad_state": {"current_start_ms": -1, "segments": []},  # 跟踪 VAD 状态
            }

        session_cache = self.cache[session_id]

        # 1. 追加到缓冲区
        session_cache["audio_buffer"].extend(audio_chunk)

        # 转换当前 chunk 为 float32 用于 VAD
        # 注意：VAD 需要流式输入，这里我们只传入新到达的 chunk
        if len(audio_chunk) > 0:
            audio_np = (
                np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            )
        else:
            audio_np = np.array([], dtype=np.float32)

        # 2. 运行 VAD (连续)
        vad_segments = []
        if len(audio_np) > 0:
            try:
                vad_res = self.vad_model.generate(
                    input=audio_np,
                    cache=session_cache["vad"],
                    is_final=is_final,
                    batch_size=1,
                    chunk_size=200,  # VAD 块大小
                    disable_pbar=True,
                )
                # VAD 返回的是相对于本次输入流的绝对时间戳（如果 cache 正确维护）
                # FunASR VAD 输出格式通常是 [[start, end], ...] 毫秒
                if isinstance(vad_res, list) and len(vad_res) > 0:
                    vad_segments = vad_res[0].get("value", [])
            except Exception as e:
                logger.error(f"[{session_id[:8]}] VAD 错误: {e}")

            if len(vad_segments) > 0:
                logger.debug(f"[{session_id[:8]}] VAD Segments: {vad_segments}")
            # else:
            #    logger.debug(f"[{session_id[:8]}] No VAD segments")

        results = []

        # 3. 处理 VAD 片段
        # 我们需要维护一个全局的 VAD 状态，因为 segments 可能跨越 chunk

        for seg in vad_segments:
            start_ms, end_ms = seg

            # VAD 输出 -1 表示未开始或未结束
            if start_ms != -1:
                session_cache["vad_state"]["current_start_ms"] = start_ms
                logger.debug(f"[{session_id[:8]}] Speech started at {start_ms}ms (VAD)")

            if end_ms != -1:
                # 句子结束
                start_ms_stored = session_cache["vad_state"]["current_start_ms"]

                if start_ms_stored != -1:
                    # 计算 byte 偏移 (16kHz, 16bit = 32 bytes/ms)
                    # 使用绝对字节偏移计算，避免累积误差

                    abs_start_byte = int(start_ms_stored * 32)
                    abs_end_byte = int(end_ms * 32)

                    buffer_offset_bytes = session_cache["buffer_offset_bytes"]

                    start_byte = abs_start_byte - buffer_offset_bytes
                    end_byte = abs_end_byte - buffer_offset_bytes

                    if start_byte < 0:
                        # 说明开始点已经被移出 buffer 了
                        logger.warning(
                            f"[{session_id[:8]}] 片段开始点已丢失 (延迟: {-start_byte} bytes)"
                        )
                        start_byte = 0

                    # 容错处理：如果 end_byte 稍微超出 buffer (例如 < 100ms / 3200 bytes)，
                    # 可能是 VAD 时间戳的舍入误差或微小的时序不匹配。
                    # 在这种情况下，我们截断到 buffer 结尾并处理，而不是等待永远不会到来的数据。
                    buffer_len = len(session_cache["audio_buffer"])
                    if end_byte > buffer_len and end_byte - buffer_len < 3200:
                        logger.debug(
                            f"[{session_id[:8]}] VAD 结束点微调: {end_byte} -> {buffer_len}"
                        )
                        end_byte = buffer_len

                    if end_byte <= buffer_len:
                        segment_audio = session_cache["audio_buffer"][
                            start_byte:end_byte
                        ]

                        # 4. 对该片段进行 ASR 和 说话人识别
                        if (
                            len(segment_audio) > 16000 * 0.2 * 2
                        ):  # 忽略极短片段 (<200ms)

                            # A. 说话人识别
                            speaker_id = self.recognize_speaker(segment_audio)

                            # B. ASR 识别
                            seg_audio_np = (
                                np.frombuffer(segment_audio, dtype=np.int16).astype(
                                    np.float32
                                )
                                / 32768.0
                            )

                            # Apply Noise Reduction
                            try:
                                # Simple stationary noise reduction
                                # prop_decrease=0.8 means reduce noise by 80% (less aggressive to avoid artifacts)
                                seg_audio_np = nr.reduce_noise(
                                    y=seg_audio_np, sr=16000, prop_decrease=0.8
                                )
                            except Exception as e:
                                logger.error(f"Noise reduction failed: {e}")

                            asr_text = ""
                            try:
                                # 使用 SenseVoice 或 Paraformer 进行整句识别
                                # 注意：这里不使用 cache，因为是独立的句子
                                asr_res = self.asr_model.generate(
                                    input=seg_audio_np,
                                    cache={},  # 句子级别不使用缓存
                                    is_final=True,
                                    batch_size=1,
                                    disable_pbar=True,
                                )
                                logger.debug(f"ASR Raw Result: {asr_res}")
                                if isinstance(asr_res, list) and len(asr_res) > 0:
                                    asr_text = asr_res[0].get("text", "")
                                    # 清理 SenseVoice 标签
                                    import re

                                    asr_text = re.sub(
                                        r"<\|.*?\|>", "", asr_text
                                    ).strip()
                            except Exception as e:
                                logger.error(f"ASR 错误: {e}")

                            # C. 标点 (可选，SenseVoice 通常自带标点)
                            if asr_text and self.punc_model:
                                try:
                                    punc_res = self.punc_model.generate(
                                        input=asr_text, is_final=True, disable_pbar=True
                                    )
                                    if isinstance(punc_res, list) and len(punc_res) > 0:
                                        asr_text = punc_res[0].get("text", asr_text)
                                except Exception:
                                    pass

                            if asr_text:
                                logger.info(
                                    f"[{session_id[:8]}] 识别结果: {speaker_id} - {asr_text}"
                                )
                                results.append(
                                    {
                                        "text": asr_text,
                                        "speaker_id": speaker_id,
                                        "timestamp": end_ms / 1000.0,  # 使用结束时间
                                        "vad_segment": [start_ms, end_ms],
                                    }
                                )

                        # 5. 清理 Buffer
                        # 我们可以安全地移除 end_byte 之前的数据
                        # 更新 offset
                        del session_cache["audio_buffer"][:end_byte]
                        session_cache["buffer_offset_bytes"] += end_byte

                    else:
                        # 数据还不够，等待更多数据
                        # logger.debug(f"[{session_id[:8]}] 等待更多数据: {len(session_cache['audio_buffer'])} < {end_byte}")
                        pass

                    # 重置开始时间
                    session_cache["vad_state"]["current_start_ms"] = -1

        # 3.5 检查长语音强制断句 / VAD 失效兜底
        # 如果当前 buffer 积压超过 2 秒且没有检测到开始，强制认为开始
        # 如果已经开始且超过 10 秒，强制结束

        current_start_ms = session_cache["vad_state"]["current_start_ms"]
        buffer_len_bytes = len(session_cache["audio_buffer"])

        # 兜底逻辑：如果 buffer 太长 (> 2s) 且没有 start_ms，强制设置 start
        if current_start_ms == -1 and buffer_len_bytes > 16000 * 2 * 2:  # 2 seconds
            # 我们假设语音从 buffer 开头就开始了
            # 计算 buffer 开头对应的时间戳
            buffer_start_ms = session_cache["buffer_offset_bytes"] / 32.0
            session_cache["vad_state"]["current_start_ms"] = buffer_start_ms
            current_start_ms = buffer_start_ms
            logger.info(
                f"[{session_id[:8]}] Buffer 积压 ({buffer_len_bytes} bytes)，强制触发语音开始: {buffer_start_ms:.0f}ms"
            )

        if current_start_ms != -1:
            # 计算当前 buffer 结尾对应的时间戳
            # buffer_offset_bytes 是 buffer[0] 的绝对偏移
            # len(buffer) 是 buffer 长度
            # current_audio_end_byte = session_cache["buffer_offset_bytes"] + len(session_cache["audio_buffer"])
            # current_audio_end_ms = current_audio_end_byte // 32

            # 简化计算：持续时间 = (当前 buffer 长度 + (buffer_offset - start_byte)) / 32
            # start_byte = start_ms * 32

            abs_start_byte = int(current_start_ms * 32)
            current_abs_end_byte = session_cache["buffer_offset_bytes"] + len(
                session_cache["audio_buffer"]
            )

            duration_bytes = current_abs_end_byte - abs_start_byte
            duration_ms = duration_bytes / 32.0

            MAX_DURATION_MS = 10000  # 10秒

            # --- Partial Result Logic ---
            # Check if we should generate a partial result
            last_partial_time = session_cache.get("last_partial_time", 0)
            now = time.time()

            if (
                now - last_partial_time > 0.5 and duration_ms > 500
            ):  # Every 500ms, if segment > 500ms
                session_cache["last_partial_time"] = now

                # Extract current segment
                start_byte = abs_start_byte - session_cache["buffer_offset_bytes"]
                if start_byte < 0:
                    start_byte = 0

                partial_audio = session_cache["audio_buffer"][start_byte:]

                if len(partial_audio) > 16000 * 0.2 * 2:
                    seg_audio_np = (
                        np.frombuffer(partial_audio, dtype=np.int16).astype(np.float32)
                        / 32768.0
                    )
                    try:
                        # Use is_final=False for partials if supported, or True but mark result as partial
                        # SenseVoice/Paraformer usually treat input as a sentence.
                        asr_res = self.asr_model.generate(
                            input=seg_audio_np,
                            cache={},
                            is_final=False,  # Partial
                            batch_size=1,
                            disable_pbar=True,
                        )
                        if isinstance(asr_res, list) and len(asr_res) > 0:
                            partial_text = asr_res[0].get("text", "")
                            import re

                            partial_text = re.sub(
                                r"<\|.*?\|>", "", partial_text
                            ).strip()

                            if partial_text:
                                results.append(
                                    {
                                        "text": partial_text,
                                        "speaker_id": "Partial",
                                        "timestamp": time.time(),
                                        "vad_segment": [],
                                        "is_partial": True,
                                    }
                                )
                    except Exception as e:
                        logger.debug(f"Partial ASR error: {e}")

            # --- End Partial Logic ---

            if duration_ms > MAX_DURATION_MS:
                logger.info(
                    f"[{session_id[:8]}] 检测到长语音 ({duration_ms:.0f}ms)，强制断句"
                )

                # 强制构造一个 segment
                # end_ms = current_start_ms + MAX_DURATION_MS
                # 但是我们应该利用当前已有的所有音频，或者截断到 10s
                # 为了用户体验，我们处理当前 buffer 中的所有数据（或者直到 10s 处）

                # 让我们截断到当前 buffer 结尾，作为一段
                force_end_ms = current_start_ms + duration_ms

                # 复用处理逻辑 (提取为函数会更好，但这里先内联)
                # 计算相对偏移
                start_byte = abs_start_byte - session_cache["buffer_offset_bytes"]
                end_byte = len(session_cache["audio_buffer"])  # 全部用完

                if start_byte < 0:
                    start_byte = 0

                if end_byte > start_byte:
                    segment_audio = session_cache["audio_buffer"][start_byte:end_byte]

                    if len(segment_audio) > 16000 * 0.2 * 2:
                        speaker_id = self.recognize_speaker(segment_audio)

                        seg_audio_np = (
                            np.frombuffer(segment_audio, dtype=np.int16).astype(
                                np.float32
                            )
                            / 32768.0
                        )

                        # Apply Noise Reduction (Force segment)
                        try:
                            seg_audio_np = nr.reduce_noise(
                                y=seg_audio_np, sr=16000, prop_decrease=0.8
                            )
                        except Exception as e:
                            logger.error(f"Noise reduction failed (Force): {e}")

                        asr_text = ""
                        try:
                            asr_res = self.asr_model.generate(
                                input=seg_audio_np,
                                cache={},
                                is_final=True,
                                batch_size=1,
                                disable_pbar=True,
                            )
                            logger.debug(f"ASR Raw Result (Force): {asr_res}")
                            if isinstance(asr_res, list) and len(asr_res) > 0:
                                asr_text = asr_res[0].get("text", "")
                                import re

                                asr_text = re.sub(r"<\|.*?\|>", "", asr_text).strip()
                        except Exception as e:
                            logger.error(f"ASR 错误 (Force): {e}")

                        if asr_text:
                            logger.info(
                                f"[{session_id[:8]}] 识别结果 (Force): {speaker_id} - {asr_text}"
                            )
                            results.append(
                                {
                                    "text": asr_text,
                                    "speaker_id": speaker_id,
                                    "timestamp": force_end_ms / 1000.0,
                                    "vad_segment": [current_start_ms, force_end_ms],
                                    "is_partial": False,
                                }
                            )

                    # 清理 buffer
                    del session_cache["audio_buffer"][:end_byte]
                    session_cache["buffer_offset_bytes"] += end_byte

                    # 更新 start_ms 为当前结束时间，相当于开始新的一段
                    # 注意：这里我们实际上把连续的语音切断了。
                    # 下一段的开始时间应该是 force_end_ms
                    session_cache["vad_state"]["current_start_ms"] = force_end_ms

        # 6. 处理 is_final
        if is_final and len(session_cache["audio_buffer"]) > 0:
            # 处理剩余的所有音频
            remaining_audio = session_cache["audio_buffer"]
            if len(remaining_audio) > 16000 * 0.5 * 2:
                speaker_id = self.recognize_speaker(remaining_audio)
                speaker_id = self.recognize_speaker(remaining_audio)
                seg_audio_np = (
                    np.frombuffer(remaining_audio, dtype=np.int16).astype(np.float32)
                    / 32768.0
                )

                # Apply Noise Reduction (Final)
                try:
                    seg_audio_np = nr.reduce_noise(
                        y=seg_audio_np, sr=16000, prop_decrease=0.8
                    )
                except Exception as e:
                    logger.error(f"Noise reduction failed (Final): {e}")

                try:
                    asr_res = self.asr_model.generate(
                        input=seg_audio_np, is_final=True, disable_pbar=True
                    )
                    if isinstance(asr_res, list) and len(asr_res) > 0:
                        text = asr_res[0].get("text", "")
                        import re

                        text = re.sub(r"<\|.*?\|>", "", text).strip()
                        if text:
                            results.append(
                                {
                                    "text": text,
                                    "speaker_id": speaker_id,
                                    "timestamp": time.time(),
                                    "vad_segment": [],
                                    "is_partial": False,
                                }
                            )
                except Exception:
                    pass

            # 清理
            del self.cache[session_id]

        return results

    def transcribe_file(self, file_path: str):
        """
        对音频文件进行完整转写 (VAD -> Speaker -> ASR -> Punc)
        """
        if self.asr_model is None:
            self.load_models()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        import librosa

        # Load audio (resample to 16000)
        try:
            audio, _ = librosa.load(file_path, sr=16000, mono=True)
            # Convert to float32 (librosa loads as float32, normalized -1 to 1)
            # FunASR expects float32 or int16.
            # Our previous logic used int16 bytes -> float32.
            # Here we have float32 directly.
        except Exception as e:
            logger.error(f"Failed to load audio file: {e}")
            raise e

        results = []

        # 1. VAD
        vad_segments = []
        try:
            # FunASR VAD can handle long audio
            vad_res = self.vad_model.generate(
                input=audio, batch_size=1, disable_pbar=True
            )
            if isinstance(vad_res, list) and len(vad_res) > 0:
                vad_segments = vad_res[0].get("value", [])
        except Exception as e:
            logger.error(f"VAD failed for file {file_path}: {e}")
            # Fallback: treat whole file as one segment if short, or fail?
            # Let's try to proceed with whole file if VAD fails
            vad_segments = [[0, len(audio) / 16000 * 1000]]

        logger.info(f"File VAD segments: {len(vad_segments)}")

        # 2. Process segments
        for seg in vad_segments:
            start_ms, end_ms = seg
            if start_ms == -1 or end_ms == -1:
                continue

            start_sample = int(start_ms * 16)  # ms * 16 samples/ms
            end_sample = int(end_ms * 16)

            segment_audio = audio[start_sample:end_sample]

            if len(segment_audio) < 16000 * 0.2:  # Skip < 0.2s
                continue

            # Convert to int16 bytes for speaker recognition (our recognize_speaker expects bytes)
            # Or modify recognize_speaker to accept numpy array.
            # Let's modify recognize_speaker to accept numpy array or bytes to be safe,
            # OR just convert back to bytes here.
            segment_int16 = (segment_audio * 32768).astype(np.int16)
            segment_bytes = segment_int16.tobytes()

            # A. Speaker ID
            speaker_id = self.recognize_speaker(segment_bytes)

            # B. ASR
            # Apply Noise Reduction
            try:
                segment_audio = nr.reduce_noise(
                    y=segment_audio, sr=16000, prop_decrease=0.8
                )
            except Exception as e:
                logger.error(f"Noise reduction failed: {e}")

            asr_text = ""
            try:
                asr_res = self.asr_model.generate(
                    input=segment_audio,
                    cache={},
                    is_final=True,
                    batch_size=1,
                    disable_pbar=True,
                )
                if isinstance(asr_res, list) and len(asr_res) > 0:
                    asr_text = asr_res[0].get("text", "")
                    import re

                    asr_text = re.sub(r"<\|.*?\|>", "", asr_text).strip()
            except Exception as e:
                logger.error(f"ASR error: {e}")

            # C. Punctuation
            if asr_text and self.punc_model:
                try:
                    punc_res = self.punc_model.generate(
                        input=asr_text, is_final=True, disable_pbar=True
                    )
                    if isinstance(punc_res, list) and len(punc_res) > 0:
                        asr_text = punc_res[0].get("text", asr_text)
                except Exception:
                    pass

            if asr_text:
                results.append(
                    {
                        "text": asr_text,
                        "speaker": speaker_id,  # Note: using 'speaker' to match TranscriptItem schema
                        "timestamp": start_ms / 1000.0,  # Use start time for transcript
                    }
                )

        return results

    def reset_session(self, session_id: str):
        """清除会话缓存。"""
        if session_id in self.cache:
            del self.cache[session_id]


asr_engine = ASREngine()
