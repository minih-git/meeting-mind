import os


class Settings:
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    MODELS_DIR = os.path.join(BASE_DIR, "models")

    # Model IDs / Paths
    ASR_MODEL_PATH = os.path.join(
        MODELS_DIR,
        "iic/SenseVoiceSmall",
    )
    VAD_MODEL_PATH = os.path.join(
        MODELS_DIR, "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    )
    PUNC_MODEL_PATH = os.path.join(
        MODELS_DIR, "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
    )
    SPEAKER_MODEL_PATH = os.path.join(
        MODELS_DIR, "iic/speech_campplus_sv_zh-cn_16k-common"
    )

    # "cuda" or "cpu"
    ASR_DEVICE = "cpu"

    # 是否启用云端 ASR（设为 False 时强制使用本地模型）
    ENABLE_CLOUD_ASR = False

    # LLM Settings
    # "local" or "cloud"
    LLM_PROVIDER = "local"

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

    LLM_MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
    # 预留显存给 ASR/VAD，vLLM 默认占用 90%，这里限制为 30% (根据实际显存调整)
    VLLM_GPU_MEMORY_UTILIZATION = 0.4
    VLLM_MAX_MODEL_LEN = 2048
    # "cuda" (使用 vLLM) 或 "cpu" (使用 Transformers)
    LLM_DEVICE = "cpu"
    # 默认是否流式输出
    LLM_STREAM_RESPONSE = False

    # Audio Settings
    SAMPLE_RATE = 16000


settings = Settings()
