import os
from funasr import AutoModel

def test_inference():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    
    asr_model_path = os.path.join(models_dir, "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online")
    vad_model_path = os.path.join(models_dir, "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch")
    punc_model_path = os.path.join(models_dir, "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch")
    # Speaker model is usually used separately or with a pipeline, but for simple test we might just test ASR
    
    print("Loading models...")
    try:
        model = AutoModel(
            model=asr_model_path,
            vad_model=vad_model_path,
            punc_model=punc_model_path,
            # model_revision="v2.0.4" 
        )
        print("Models loaded successfully.")
    except Exception as e:
        print(f"Failed to load models: {e}")
        return

    # Test inference
    audio_file = os.path.join(asr_model_path, "example/asr_example.wav")
    if not os.path.exists(audio_file):
        print(f"Audio file not found: {audio_file}")
        return
        
    print(f"Running inference on {audio_file}...")
    try:
        res = model.generate(input=audio_file)
        print("Inference result:")
        print(res)
    except Exception as e:
        print(f"Inference failed: {e}")

if __name__ == "__main__":
    test_inference()
