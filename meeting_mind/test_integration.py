import asyncio
import websockets
import json
import os
import sys
import time
import requests

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from meeting_mind.app.core.config import settings

BASE_URL = "http://localhost:8000/api/v1"
WS_URL = "ws://localhost:8000/api/v1/ws"

async def test_integration():
    print("开始集成测试...")

    # 1. 创建会议
    print("1. 正在创建会议...")
    payload = {
        "title": "Integration Test Meeting",
        "participants": ["Alice", "Bob"]
    }
    try:
        res = requests.post(f"{BASE_URL}/meetings", json=payload)
        res.raise_for_status()
        meeting = res.json()
        meeting_id = meeting["id"]
        print(f"会议已创建: {meeting_id}")
    except Exception as e:
        print(f"创建会议失败: {e}")
        return

    # 2. 连接 WebSocket
    print(f"2. 正在连接会议 {meeting_id} 的 WebSocket...")
    
    audio_file = os.path.join(settings.ASR_MODEL_PATH, "example/asr_example.wav")
    if not os.path.exists(audio_file):
        print(f"未找到音频文件: {audio_file}")
        return

    async with websockets.connect(WS_URL) as websocket:
        # 握手
        handshake = {
            "meeting_id": meeting_id,
            "sample_rate": 16000
        }
        await websocket.send(json.dumps(handshake))
        print("握手已发送。")

        # 音频流
        print(f"3. 正在从 {audio_file} 传输音频...")
        with open(audio_file, "rb") as f:
            audio_data = f.read()
            
        audio_payload = audio_data[44:] # 跳过 WAV 头
        chunk_size = 16000 * 2 * 2 # 2s chunks
        total_len = len(audio_payload)
        offset = 0
        
        # 接收任务
        async def receive_messages():
            try:
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    print(f"WS 收到: {data['type']} - {data.get('text', '')[:20]}...")
            except websockets.exceptions.ConnectionClosed:
                print("WS 连接已关闭。")

        receiver_task = asyncio.create_task(receive_messages())

        while offset < total_len:
            end = min(offset + chunk_size, total_len)
            chunk = audio_payload[offset:end]
            await websocket.send(chunk)
            offset = end
            await asyncio.sleep(0.5)

        print("音频发送完成。")
        # 发送停止消息
        await websocket.send(json.dumps({"type": "stop"}))
        print("停止消息已发送。")
        
        await asyncio.sleep(2) # 等待处理
        receiver_task.cancel()

    # 4. 通过 API 验证转写
    print(f"4. 正在验证会议 {meeting_id} 的转写...")
    try:
        res = requests.get(f"{BASE_URL}/meetings/{meeting_id}/transcript")
        res.raise_for_status()
        transcript = res.json()
        items = transcript["items"]
        print(f"转写条目数量: {len(items)}")
        if len(items) > 0:
            print(f"第一条: {items[0]}")
        else:
            print("警告: 未找到转写条目！")
    except Exception as e:
        print(f"获取转写失败: {e}")

    # 5. 停止会议
    print(f"5. 正在停止会议 {meeting_id}...")
    try:
        res = requests.post(f"{BASE_URL}/meetings/{meeting_id}/stop")
        res.raise_for_status()
        print("会议已停止。")
    except Exception as e:
        print(f"停止会议失败: {e}")

    print("集成测试完成。")

if __name__ == "__main__":
    asyncio.run(test_integration())
