import asyncio
import websockets
import json
import os
import sys
import time
import requests

# Add parent directory (project root) to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from meeting_mind.app.core.config import settings

async def test_websocket(meeting_id):
    uri = "ws://localhost:8000/api/v1/ws"
    audio_file = os.path.join("/Users/minih/IdeaProjects/funasr/wav", "20200327_2P_lenovo_iphonexr_66902.wav")
    
    if not os.path.exists(audio_file):
        print(f"❌ 音频文件未找到: {audio_file}")
        return

    print(f"🔗 连接到 {uri}...")
    async with websockets.connect(uri) as websocket:
        # 1. Handshake
        handshake = {
            "meeting_id": meeting_id,
            "sample_rate": 16000
        }
        await websocket.send(json.dumps(handshake))
        print("✓ 握手成功")

        # 2. Send Audio
        print(f"📖 读取音频文件: {audio_file}")
        with open(audio_file, "rb") as f:
            audio_data = f.read()
            
        audio_payload = audio_data[44:] # Skip WAV header
        chunk_size = 32000 # 1s chunks (优化后的缓冲策略)
        total_len = len(audio_payload)
        offset = 0
        
        # Start a task to receive messages
        async def receive_messages():
            try:
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    print(f"📥 收到结果: type={data.get('type')}, text='{data.get('text')}', speaker={data.get('speaker')}")
                    if data.get("type") == "final":
                        print("✓ 收到最终结果")
            except websockets.exceptions.ConnectionClosed:
                print("🔌 连接已关闭")

        receiver_task = asyncio.create_task(receive_messages())

        print(f"🎤 开始发送音频 (总共 {total_len} 字节)...")
        while offset < total_len:
            end = min(offset + chunk_size, total_len)
            chunk = audio_payload[offset:end]
            
            print(f"  📤 发送分片: {offset}-{end} 字节")
            await websocket.send(chunk)
            
            offset = end
            await asyncio.sleep(0.3)  # 模拟实时音频流

        print("✓ 音频发送完成")
        # Wait a bit for final results
        await asyncio.sleep(2)
        receiver_task.cancel()

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket 流式识别测试")
    print("=" * 60)
    
    # 1. 先通过API创建会议
    print("\n1️⃣  创建会议...")
    api_url = "http://localhost:8000/api/v1/meetings"
    meeting_data = {
        "title": "WebSocket Test Meeting",
        "participants": ["Tester"]
    }
    
    try:
        response = requests.post(api_url, json=meeting_data)
        response.raise_for_status()
        meeting = response.json()
        meeting_id = meeting["id"]
        print(f"✓ 会议创建成功: ID={meeting_id}")
    except Exception as e:
        print(f"❌ 创建会议失败: {e}")
        print("请确保服务正在运行: uvicorn meeting_mind.app.main:app --reload")
        exit(1)
    
    # 2. 运行WebSocket测试
    print(f"\n2️⃣  开始WebSocket测试...")
    try:
        asyncio.run(test_websocket(meeting_id))
        print("\n✅ 测试完成!")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. 停止会议
    print(f"\n3️⃣  停止会议...")
    try:
        stop_url = f"{api_url}/{meeting_id}/stop"
        response = requests.post(stop_url)
        response.raise_for_status()
        print("✓ 会议已停止")
    except Exception as e:
        print(f"⚠ 停止会议失败: {e}")
