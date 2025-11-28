import os
import sys
import time

# Add parent directory (project root) to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from meeting_mind.app.services.asr_engine import asr_engine
from meeting_mind.app.core.config import settings

def test_engine():
    print("正在测试 ASREngine...")
    
    # 1. 加载模型
    print("1. 正在加载模型...")
    start_time = time.time()
    asr_engine.load_models()
    print(f"模型加载完成，耗时 {time.time() - start_time:.2f}s")
    
    # 2. 准备音频
    audio_file = os.path.join(settings.ASR_MODEL_PATH, "example/asr_example.wav")
    if not os.path.exists(audio_file):
        print(f"未找到音频文件: {audio_file}")
        return

    print(f"2. 正在读取音频文件: {audio_file}")
    with open(audio_file, "rb") as f:
        audio_data = f.read()
        
    # 3. 模拟流式推理
    print("3. 正在模拟流式推理...")
    session_id = "test_session_001"
    chunk_size = 16000 * 2 * 2  # 2 seconds of 16k 16bit audio (approx)
    # Note: wav header is small, we might send it in first chunk, model usually handles it or we should skip it.
    # For robustness test, let's just send raw bytes including header for now, or skip 44 bytes.
    
    audio_payload = audio_data[44:] # Skip WAV header
    
    total_len = len(audio_payload)
    offset = 0
    
    while offset < total_len:
        end = min(offset + chunk_size, total_len)
        chunk = audio_payload[offset:end]
        
        print(f"正在发送分片: {offset}-{end} 字节")
        is_last = (end == total_len)
        result = asr_engine.inference_stream(session_id, chunk, is_final=is_last)
        print(f"结果: {result}")
        
        offset = end
        time.sleep(0.5) # 模拟实时延迟

    print("测试完成。")

if __name__ == "__main__":
    test_engine()
