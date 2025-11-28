import wave
import sys
import os
import glob

def convert_pcm_to_wav():
    # Find latest pcm file
    list_of_files = glob.glob('debug_*.pcm')
    if not list_of_files:
        print("No PCM files found.")
        return

    latest_file = max(list_of_files, key=os.path.getctime)
    output_file = latest_file.replace('.pcm', '.wav')

    print(f"Converting {latest_file} to {output_file}...")

    with open(latest_file, 'rb') as pcmfile:
        pcm_data = pcmfile.read()

    with wave.open(output_file, 'wb') as wavfile:
        wavfile.setnchannels(1)
        wavfile.setsampwidth(2) # 16-bit
        wavfile.setframerate(16000)
        wavfile.writeframes(pcm_data)

    print(f"Conversion complete: {output_file}")

if __name__ == "__main__":
    convert_pcm_to_wav()
