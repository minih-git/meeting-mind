import librosa
import soundfile as sf
import os
from meeting_mind.app.core.config import settings

def convert_mp3_to_wav():
    mp3_path = os.path.join(settings.ASR_MODEL_PATH, "example/zh.mp3")
    wav_path = os.path.join(settings.ASR_MODEL_PATH, "example/zh.wav")
    
    print(f"Converting {mp3_path} to {wav_path}...")
    
    if not os.path.exists(mp3_path):
        print(f"Error: {mp3_path} does not exist.")
        return

    # Load audio (resample to 16000 Hz)
    y, sr = librosa.load(mp3_path, sr=16000, mono=True)
    
    # Save as WAV (16-bit PCM)
    sf.write(wav_path, y, sr, subtype='PCM_16')
    print(f"Conversion complete: {wav_path}")

if __name__ == "__main__":
    convert_mp3_to_wav()
