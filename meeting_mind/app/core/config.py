import os


class Settings:
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    MODELS_DIR = os.path.join(BASE_DIR, "models")

    # 本地模型路径配置
    # 路径格式：MODELS_DIR + ModelScope 模型 ID，首次加载时自动下载
    ASR_MODEL_PATH = os.path.join(MODELS_DIR, "iic/SenseVoiceSmall")  # 语音识别
    VAD_MODEL_PATH = os.path.join(
        MODELS_DIR, "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    )  # 语音活动检测
    PUNC_MODEL_PATH = os.path.join(
        MODELS_DIR, "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
    )  # 标点恢复
    SPEAKER_MODEL_PATH = os.path.join(
        MODELS_DIR, "iic/speech_campplus_sv_zh-cn_16k-common"
    )  # 说话人识别
    LLM_MODEL_PATH = os.path.join(
        MODELS_DIR, "Qwen/Qwen2.5-1.5B-Instruct"
    )  # 大语言模型

    # 是否启用云端 ASR（设为 False 时强制使用本地模型）
    ENABLE_CLOUD_ASR = False

    # 是否启用全局录音锁（防止多用户并发录音）
    ENABLE_GLOBAL_LOCK = os.getenv("ENABLE_GLOBAL_LOCK", "False").lower() == "true"

    # 调用远程模型设置 (从环境变量读取，避免泄露)
    CLOUD_LLM_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

    # 默认使用开发环境配置，可被环境变量覆盖
    CLOUD_LLM_API_BASE = os.getenv(
        "CLOUD_LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    CLOUD_ASR_API_BASE = os.getenv(
        "CLOUD_ASR_API_BASE", "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"
    )
    CLOUD_LLM_MODEL = "qwen3-max"
    CLOUD_ASR_MODEL = "fun-asr-realtime"

    # 推理设备: "cuda" 或 "cpu"
    DEVICE = "cpu"
    # 预留显存给 ASR/VAD，vLLM 默认占用 90%，这里限制为 30% (根据实际显存调整)
    VLLM_GPU_MEMORY_UTILIZATION = 0.4
    VLLM_MAX_MODEL_LEN = 2048

    # Audio Settings
    SAMPLE_RATE = 16000


settings = Settings()
