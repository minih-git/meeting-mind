import asyncio
import websockets
import json
import wave
import time
import requests
import os

# Configuration
API_URL = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/ws"
AUDIO_FILE = "recordings/b7fe07c6-4699-4c6a-9758-86491a3e053b_20251128_151829.wav"
CHUNK_SIZE = 6400 # 200ms at 16kHz 16bit mono
DELAY = 0.2 # 200ms

async def run_test():
    # 1. Create Meeting
    print(f"Creating meeting...")
    try:
        resp = requests.post(f"{API_URL}/meetings", json={"title": "Debug Session", "participants": ["Debugger"]})
        resp.raise_for_status()
        meeting = resp.json()
        meeting_id = meeting["id"]
        print(f"Meeting created: {meeting_id}")
    except Exception as e:
        print(f"Failed to create meeting: {e}")
        return

    # 2. Connect WebSocket
    print(f"Connecting to WebSocket: {WS_URL}")
    async with websockets.connect(WS_URL) as ws:
        # Handshake
        await ws.send(json.dumps({
            "meeting_id": meeting_id,
            "sample_rate": 16000
        }))
        print("Handshake sent.")

        # 3. Stream Audio
        if not os.path.exists(AUDIO_FILE):
            print(f"Audio file not found: {AUDIO_FILE}")
            return

        print(f"Streaming audio from {AUDIO_FILE}...")
        with wave.open(AUDIO_FILE, "rb") as wf:
            data = wf.readframes(CHUNK_SIZE // 2)
            total_bytes = 0
            
            async def receive_loop():
                try:
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if data.get("type") == "partial":
                             print(f"PARTIAL: {data.get('text')}")
                        elif data.get("type") == "final":
                             print(f"FINAL: {data.get('text')}")
                        elif data.get("type") == "stopped":
                            break
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed.")
                except Exception as e:
                    print(f"Receive error: {e}")

            recv_task = asyncio.create_task(receive_loop())

            while len(data) > 0:
                await ws.send(data)
                total_bytes += len(data)
                # print(f"Sent {len(data)} bytes")
                await asyncio.sleep(DELAY)
                data = wf.readframes(CHUNK_SIZE // 2)
            
            print("Audio streaming finished.")
            
            # Send stop
            await ws.send(json.dumps({"type": "stop"}))
            print("Stop command sent.")
            
            # Wait for processing to finish
            await asyncio.sleep(5)
            recv_task.cancel()

if __name__ == "__main__":
    asyncio.run(run_test())
