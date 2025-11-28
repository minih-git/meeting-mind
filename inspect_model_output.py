import os
import sys
import numpy as np
from funasr import AutoModel
from meeting_mind.app.core.config import settings

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def inspect_model():
    print("Loading Speaker Model...")
    model = AutoModel(model=settings.SPEAKER_MODEL_PATH, disable_update=True)
    
    wav_path = "wav/20200327_2P_lenovo_iphonexr_66902.wav"
    if not os.path.exists(wav_path):
        print(f"File not found: {wav_path}")
        return

    print(f"Processing {wav_path}...")
    # Load a small chunk (e.g. 5 seconds)
    import librosa
    y, sr = librosa.load(wav_path, sr=16000, duration=5.0)
    
    # Run inference
    res = model.generate(input=y)
    print("Result Type:", type(res))
    print("Result:", res)
    
    if isinstance(res, list) and len(res) > 0:
        print("Keys:", res[0].keys())

if __name__ == "__main__":
    inspect_model()
