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

    # Constants
    SAMPLE_RATE = 16000
    BYTES_PER_SAMPLE = 2  # int16
    SAMPLES_PER_MS = int(SAMPLE_RATE / 1000)  # 16
    BYTES_PER_MS = int(SAMPLE_RATE * BYTES_PER_SAMPLE / 1000)  # 32
    PCM_NORM_FACTOR = 32768.0

    # Thresholds
    MIN_SPEAKER_AUDIO_LEN_SEC = 0.5
    MIN_SEGMENT_LEN_SEC = 0.3  # 提高最小段长度，过滤噪声片段
    MAX_SEGMENT_DURATION_MS = 8000  # 降低强制断句时长，使句子更自然
    SPEAKER_SIMILARITY_THRESHOLD = 0.35  # 提高阈值，减少说话人误判
    NOISE_REDUCTION_PROP = 0.75  # 略微降低降噪强度，保留更多语音细节
    GENDER_FREQ_THRESHOLD = 165

    # VAD
    VAD_CHUNK_SIZE = 300  # 增大chunk size，减少碎片化分段

    # 静音检测
    SILENCE_ENERGY_THRESHOLD = 150.0  # 静音能量阈值
    SILENCE_DURATION_MS = 400  # 静音时长阈值，超过此时长认为是停顿

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ASREngine, cls).__new__(cls)
            cls._instance.asr_model = None
            cls._instance.vad_model = None
            cls._instance.punc_model = None
            cls._instance.cache = {}
            cls._instance.speaker_registry = {}

            # Queue for async processing
            cls._instance.queue = None
            cls._instance.worker_task = None
            cls._instance.callbacks = {}

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
                self.punc_model = AutoModel(
                    model=settings.PUNC_MODEL_PATH,
                    disable_update=True,
                    device=settings.ASR_DEVICE,
                )

                # 加载说话人模型
                self.speaker_model = AutoModel(
                    model=settings.SPEAKER_MODEL_PATH,
                    disable_update=True,
                    device=settings.ASR_DEVICE,
                )

            if self.asr_model:
                logger.info("  ✓ ASR 模型加载成功")
            if self.vad_model:
                logger.info("  ✓ VAD 模型加载成功")
            if self.punc_model:
                logger.info("  ✓ 标点模型加载成功")
            if self.speaker_model:
                logger.info("  ✓ 说话人模型加载成功")
            logger.info("🎉 语音识别所需模型加载完成!")
        except Exception as e:
            logger.error(f"❌ 加载模型出错: {e}")
            raise e

    def _cosine_similarity(self, v1, v2):
        """计算两个向量的余弦相似度"""
        v1 = np.squeeze(v1)
        v2 = np.squeeze(v2)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return np.dot(v1, v2) / (norm1 * norm2)

    def detect_gender(self, audio_chunk: bytes):
        """
        基于音高检测性别 - 使用多指标综合判断

        优化方案：
        1. 使用中位数而非平均值，更抗噪声
        2. 增加有效语音帧比例检查
        3. 使用更宽松的阈值范围，对边界情况返回未知
        """
        try:
            import librosa

            # 最小音频长度检查 (至少需要0.5秒)
            if len(audio_chunk) < self.SAMPLE_RATE * 0.5 * self.BYTES_PER_SAMPLE:
                return "未知"

            # 转换为 float32
            audio_np = (
                np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            )

            # 使用 librosa.pyin 进行音高跟踪
            f0, voiced_flag, voiced_probs = librosa.pyin(
                audio_np,
                fmin=librosa.note_to_hz("C2"),  # ~65 Hz
                fmax=librosa.note_to_hz("C6"),  # ~1047 Hz
                sr=self.SAMPLE_RATE,
                frame_length=2048,
            )

            # 过滤 NaN 并获取有效帧
            valid_f0 = f0[~np.isnan(f0)]

            # 检查有效语音帧比例（至少30%的帧有有效音高）
            voiced_ratio = len(valid_f0) / len(f0) if len(f0) > 0 else 0

            if len(valid_f0) < 5 or voiced_ratio < 0.3:
                logger.debug(
                    f"有效语音帧不足: {len(valid_f0)}, 比例: {voiced_ratio:.2%}"
                )
                return "未知"

            # 使用中位数更稳健
            median_pitch = np.median(valid_f0)
            # 同时计算四分位距检查变异性
            q1, q3 = np.percentile(valid_f0, [25, 75])
            iqr = q3 - q1

            logger.debug(
                f"音高统计: 中位数={median_pitch:.1f}Hz, Q1={q1:.1f}, Q3={q3:.1f}, IQR={iqr:.1f}"
            )

            # 使用阈值范围，边界情况返回未知
            # 男性典型范围: 85-180 Hz
            # 女性典型范围: 165-255 Hz
            # 重叠区域 165-180 Hz 较难判断

            if median_pitch < 150:
                return "男"
            elif median_pitch > 190:
                return "女"
            else:
                # 边界区域，根据分布形态辅助判断
                # 如果变异范围偏低，可能是男性
                if q3 < 170:
                    return "男"
                elif q1 > 160:
                    return "女"
                else:
                    return "未知"

        except Exception as e:
            logger.error(f"性别检测失败: {e}")
            return "未知"

    def recognize_speaker(self, audio_segment: bytes, previous_speaker: str = None):
        """
        提取说话人声纹特征并识别说话人。

        Args:
            audio_segment: 音频字节数据
            previous_speaker: 上一个识别的说话人ID，用于连续性判断
        """
        if not self.speaker_model:
            logger.warning("说话人模型未加载")
            return "未知"

        if (
            len(audio_segment)
            < self.SAMPLE_RATE * self.MIN_SPEAKER_AUDIO_LEN_SEC * self.BYTES_PER_SAMPLE
        ):
            logger.debug(f"音频片段太短，无法进行说话人识别: {len(audio_segment)} 字节")
            # 如果音频太短，优先返回上一个说话人以保持连续性
            if previous_speaker and previous_speaker in self.speaker_registry:
                return previous_speaker
            return "未知"

        try:
            # 将字节转换为 numpy 数组
            audio_np = (
                np.frombuffer(audio_segment, dtype=np.int16).astype(np.float32)
                / self.PCM_NORM_FACTOR
            )

            res = self.speaker_model.generate(input=audio_np, disable_pbar=True)

            if isinstance(res, list) and len(res) > 0:
                embedding = res[0].get("spk_embedding")
                if embedding is not None:
                    # 如果是 Tensor (GPU/CPU)，转换为 numpy
                    if hasattr(embedding, "cpu"):
                        embedding = embedding.detach().cpu().numpy()
                    elif hasattr(embedding, "numpy"):
                        embedding = embedding.numpy()

                    embedding = np.squeeze(embedding)
                    THRESHOLD = self.SPEAKER_SIMILARITY_THRESHOLD

                    best_score = -1.0
                    second_best_score = -1.0
                    best_speaker = None

                    # 与注册的说话人进行比较
                    for spk_id, data in self.speaker_registry.items():
                        spk_emb = data["embedding"]
                        score = self._cosine_similarity(embedding, spk_emb)
                        if score > best_score:
                            second_best_score = best_score
                            best_score = score
                            best_speaker = spk_id
                        elif score > second_best_score:
                            second_best_score = score

                    # 计算置信度差距 - 如果最佳和次佳差距小，说明不确定
                    confidence_gap = (
                        best_score - second_best_score
                        if second_best_score > 0
                        else best_score
                    )

                    logger.debug(
                        f"说话人匹配得分: {best_score:.4f} (匹配: {best_speaker}, 差距: {confidence_gap:.4f})"
                    )

                    # 对于边界情况（分数接近阈值且置信度差距小），优先保持连续性
                    if previous_speaker and best_speaker != previous_speaker:
                        prev_score = 0.0
                        if previous_speaker in self.speaker_registry:
                            prev_emb = self.speaker_registry[previous_speaker][
                                "embedding"
                            ]
                            prev_score = self._cosine_similarity(embedding, prev_emb)

                        # 如果上一个说话人的分数也超过阈值且差距不大，保持连续性
                        if prev_score > THRESHOLD and (best_score - prev_score) < 0.1:
                            best_speaker = previous_speaker
                            best_score = prev_score
                            logger.debug(f"保持说话人连续性: {previous_speaker}")

                    if best_score > THRESHOLD:
                        # 使用自适应权重更新嵌入 - 样本越多，新样本权重越小
                        old_emb = self.speaker_registry[best_speaker]["embedding"]
                        count = self.speaker_registry[best_speaker]["count"]

                        # 自适应权重：count=1时alpha=0.5, count=10时alpha≈0.9, count=50时alpha≈0.98
                        alpha = 1 - 1 / (1 + count * 0.5)
                        new_emb = alpha * old_emb + (1 - alpha) * embedding
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
                            "embedding": embedding,
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

    def detect_silence_segments(self, audio_chunk: bytes, window_ms: int = 50):
        """
        检测音频中的静音段落，用于辅助VAD进行二次分段。

        Args:
            audio_chunk: 音频字节数据
            window_ms: 滑动窗口大小（毫秒）

        Returns:
            list: 静音段的起止位置列表 [(start_ms, end_ms), ...]
        """
        if len(audio_chunk) < self.BYTES_PER_MS * window_ms:
            return []

        try:
            audio_np = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
            window_samples = int(self.SAMPLE_RATE * window_ms / 1000)
            hop_samples = window_samples // 2

            silence_segments = []
            silence_start = None

            for i in range(0, len(audio_np) - window_samples, hop_samples):
                window = audio_np[i : i + window_samples]
                energy = np.sqrt(np.mean(window**2))

                if energy < self.SILENCE_ENERGY_THRESHOLD:
                    if silence_start is None:
                        silence_start = i / self.SAMPLE_RATE * 1000
                else:
                    if silence_start is not None:
                        silence_end = i / self.SAMPLE_RATE * 1000
                        duration = silence_end - silence_start
                        if duration >= self.SILENCE_DURATION_MS:
                            silence_segments.append((silence_start, silence_end))
                        silence_start = None

            return silence_segments

        except Exception as e:
            logger.debug(f"静音检测错误: {e}")
            return []

    def _process_audio_segment(
        self,
        audio_bytes: bytes,
        session_id: str = "unknown",
        previous_speaker: str = None,
    ):
        """
        处理单个音频片段：降噪 -> 说话人识别 -> ASR -> 标点

        Args:
            audio_bytes: 音频字节数据
            session_id: 会话ID
            previous_speaker: 上一个说话人ID，用于连续性判断
        """
        results = []

        # 1. 检查长度
        if (
            len(audio_bytes)
            < self.SAMPLE_RATE * self.MIN_SEGMENT_LEN_SEC * self.BYTES_PER_SAMPLE
        ):
            return results

        # 2. 说话人识别 (传递上一个说话人信息)
        speaker_id = self.recognize_speaker(audio_bytes, previous_speaker)

        # 3. 准备音频数据 (float32)
        audio_np = (
            np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            / self.PCM_NORM_FACTOR
        )

        # 4. 降噪
        try:
            audio_np = nr.reduce_noise(
                y=audio_np, sr=self.SAMPLE_RATE, prop_decrease=self.NOISE_REDUCTION_PROP
            )
        except Exception as e:
            logger.error(f"Noise reduction failed: {e}")

        # 5. ASR 识别
        asr_text = ""
        try:
            asr_res = self.asr_model.generate(
                input=audio_np,
                cache={},  # 句子级别不使用缓存
                is_final=True,
                batch_size=1,
                disable_pbar=True,
            )
            logger.debug(f"ASR Raw Result: {asr_res}")
            if isinstance(asr_res, list) and len(asr_res) > 0:
                asr_text = asr_res[0].get("text", "")
                import re

                asr_text = re.sub(r"<\|.*?\|>", "", asr_text).strip()
        except Exception as e:
            logger.error(f"ASR 错误: {e}")

        # 6. 标点
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
            logger.info(f"[{session_id[:8]}] 识别结果: {speaker_id} - {asr_text}")
            results.append(
                {
                    "text": asr_text,
                    "speaker_id": speaker_id,
                    # timestamp 需要在外部添加
                }
            )

        return results

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
                "last_speaker": None,  # 追踪上一个说话人用于连续性判断
            }

        session_cache = self.cache[session_id]

        # 1. 追加到缓冲区
        session_cache["audio_buffer"].extend(audio_chunk)

        # 转换当前 chunk 为 float32 用于 VAD
        if len(audio_chunk) > 0:
            audio_np = (
                np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
                / self.PCM_NORM_FACTOR
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
                    chunk_size=self.VAD_CHUNK_SIZE,  # VAD 块大小
                    disable_pbar=True,
                )
                # VAD 返回的是相对于本次输入流的绝对时间戳
                if isinstance(vad_res, list) and len(vad_res) > 0:
                    vad_segments = vad_res[0].get("value", [])
            except Exception as e:
                logger.error(f"[{session_id[:8]}] VAD 错误: {e}")

            if len(vad_segments) > 0:
                logger.debug(f"[{session_id[:8]}] VAD Segments: {vad_segments}")

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

                    abs_start_byte = int(start_ms_stored * self.BYTES_PER_MS)
                    abs_end_byte = int(end_ms * self.BYTES_PER_MS)

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
                        # 使用 helper method，传递上一个说话人信息
                        previous_speaker = session_cache.get("last_speaker")
                        seg_results = self._process_audio_segment(
                            segment_audio, session_id, previous_speaker
                        )

                        for res in seg_results:
                            res["timestamp"] = end_ms / 1000.0
                            res["vad_segment"] = [start_ms, end_ms]
                            results.append(res)
                            # 更新 last_speaker
                            if res.get("speaker_id") and res["speaker_id"] != "未知":
                                session_cache["last_speaker"] = res["speaker_id"]

                        # 5. 清理 Buffer
                        # 我们可以安全地移除 end_byte 之前的数据
                        # 更新 offset
                        del session_cache["audio_buffer"][:end_byte]
                        session_cache["buffer_offset_bytes"] += end_byte

                    else:
                        # 数据还不够，等待更多数据
                        pass

                    # 重置开始时间
                    session_cache["vad_state"]["current_start_ms"] = -1

        # 3.5 检查长语音强制断句 / VAD 失效兜底
        # 如果当前 buffer 积压超过 2 秒且没有检测到开始，强制认为开始
        # 如果已经开始且超过 10 秒，强制结束

        current_start_ms = session_cache["vad_state"]["current_start_ms"]
        buffer_len_bytes = len(session_cache["audio_buffer"])

        # 兜底逻辑：如果 buffer 太长 (> 5s) 且没有 start_ms，强制设置 start
        if (
            current_start_ms == -1
            and buffer_len_bytes > self.SAMPLE_RATE * self.BYTES_PER_SAMPLE * 5
        ):  # 5 seconds
            # 我们假设语音从 buffer 开头就开始了
            # 计算 buffer 开头对应的时间戳
            buffer_start_ms = session_cache["buffer_offset_bytes"] / float(
                self.BYTES_PER_MS
            )
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

            abs_start_byte = int(current_start_ms * self.BYTES_PER_MS)
            current_abs_end_byte = session_cache["buffer_offset_bytes"] + len(
                session_cache["audio_buffer"]
            )

            duration_bytes = current_abs_end_byte - abs_start_byte
            duration_ms = duration_bytes / float(self.BYTES_PER_MS)

            MAX_DURATION_MS = self.MAX_SEGMENT_DURATION_MS

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

                if (
                    len(partial_audio)
                    > self.SAMPLE_RATE
                    * self.MIN_SEGMENT_LEN_SEC
                    * self.BYTES_PER_SAMPLE
                ):
                    seg_audio_np = (
                        np.frombuffer(partial_audio, dtype=np.int16).astype(np.float32)
                        / self.PCM_NORM_FACTOR
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

                # 让我们截断到当前 buffer 结尾，作为一段
                force_end_ms = current_start_ms + duration_ms

                # 计算相对偏移
                start_byte = abs_start_byte - session_cache["buffer_offset_bytes"]
                end_byte = len(session_cache["audio_buffer"])  # 全部用完

                if start_byte < 0:
                    start_byte = 0

                if end_byte > start_byte:
                    segment_audio = session_cache["audio_buffer"][start_byte:end_byte]

                    # 使用 helper method，传递上一个说话人信息
                    previous_speaker = session_cache.get("last_speaker")
                    seg_results = self._process_audio_segment(
                        segment_audio, session_id, previous_speaker
                    )

                    for res in seg_results:
                        res["timestamp"] = force_end_ms / 1000.0
                        res["vad_segment"] = [current_start_ms, force_end_ms]
                        res["is_partial"] = False
                        results.append(res)
                        # 更新 last_speaker
                        if res.get("speaker_id") and res["speaker_id"] != "未知":
                            session_cache["last_speaker"] = res["speaker_id"]

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

            previous_speaker = session_cache.get("last_speaker")
            seg_results = self._process_audio_segment(
                remaining_audio, session_id, previous_speaker
            )
            for res in seg_results:
                res["timestamp"] = time.time()
                res["vad_segment"] = []
                res["is_partial"] = False
                results.append(res)

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
            audio, _ = librosa.load(file_path, sr=self.SAMPLE_RATE, mono=True)
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
            vad_segments = [[0, len(audio) / self.SAMPLE_RATE * 1000]]

        logger.info(f"File VAD segments: {len(vad_segments)}")

        # 2. Process segments
        for seg in vad_segments:
            start_ms, end_ms = seg
            if start_ms == -1 or end_ms == -1:
                continue

            start_sample = int(start_ms * self.SAMPLES_PER_MS)  # ms * 16 samples/ms

            end_sample = int(end_ms * self.SAMPLES_PER_MS)

            segment_audio = audio[start_sample:end_sample]

            if (
                len(segment_audio) < self.SAMPLE_RATE * self.MIN_SEGMENT_LEN_SEC
            ):  # Skip < 0.2s
                continue

            # OR just convert back to bytes here.
            segment_int16 = (segment_audio * self.PCM_NORM_FACTOR).astype(np.int16)
            segment_bytes = segment_int16.tobytes()

            speaker_id = self.recognize_speaker(segment_bytes)

            # Apply Noise Reduction
            try:
                segment_audio = nr.reduce_noise(
                    y=segment_audio,
                    sr=self.SAMPLE_RATE,
                    prop_decrease=self.NOISE_REDUCTION_PROP,
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
