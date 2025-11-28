import os


class Settings:
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    MODELS_DIR = os.path.join(BASE_DIR, "models")

    # Model IDs / Paths
    ASR_MODEL_PATH = os.path.join(
        MODELS_DIR,
        # "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
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

    # Audio Settings
    SAMPLE_RATE = 16000


settings = Settings()
