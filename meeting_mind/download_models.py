import os
from modelscope import snapshot_download


def download_models():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")

    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    models = {
        "asr": "iic/SenseVoiceSmall",
        "vad": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        "punc": "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        "speaker": "iic/speech_campplus_sv_zh-cn_16k-common",
        "llm": "Qwen/Qwen2.5-1.5B-Instruct",
    }

    print(f"Downloading models to {models_dir}...")

    for name, model_id in models.items():
        print(f"Downloading {name} model: {model_id}")
        try:
            model_path = snapshot_download(model_id, cache_dir=models_dir)
            print(f"Successfully downloaded {name} to {model_path}")
        except Exception as e:
            print(f"Failed to download {name}: {e}")


if __name__ == "__main__":
    download_models()
