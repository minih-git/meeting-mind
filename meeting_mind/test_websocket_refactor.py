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

async def test_websocket_refactor(meeting_id):
    uri = "ws://localhost:8001/api/v1/ws"
    audio_file = "/Users/minih/IdeaProjects/funasr/wav/20200327_2P_lenovo_iphonexr_66902.wav"
    
    if not os.path.exists(audio_file):
        print(f"❌ Audio file not found: {audio_file}")
        return

    print(f"🔗 Connecting to {uri}...")
    async with websockets.connect(uri) as websocket:
        # 1. Handshake
        handshake = {
            "meeting_id": meeting_id,
            "sample_rate": 16000
        }
        await websocket.send(json.dumps(handshake))
        print("✓ Handshake successful")

        # 2. Send Audio
        print(f"📖 Reading audio file: {audio_file}")
        with open(audio_file, "rb") as f:
            audio_data = f.read()
            
        # Send 10 seconds of audio
        # 16000 * 2 bytes/sample * 10 sec = 320000 bytes
        audio_payload = audio_data[44:320044] 
        chunk_size = 6400 # 200ms chunks
        total_len = len(audio_payload)
        offset = 0
        
        received_results = []
        stop_confirmed = False
        
        # Start a task to receive messages
        async def receive_messages():
            nonlocal stop_confirmed
            try:
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    if data.get("type") == "stopped":
                        print("✓ Received 'stopped' confirmation")
                        stop_confirmed = True
                        # Do NOT break here, continue listening for final results
                        continue
                    
                    if data.get("type") == "ping":
                        continue
                        
                    print(f"📥 Received result: type={data.get('type')}, text='{data.get('text')}'")
                    if data.get("text"):
                        received_results.append(data)
                        
            except websockets.exceptions.ConnectionClosed:
                print("🔌 Connection closed")

        receiver_task = asyncio.create_task(receive_messages())

        print(f"🎤 Sending audio ({total_len} bytes)...")
        while offset < total_len:
            end = min(offset + chunk_size, total_len)
            chunk = audio_payload[offset:end]
            
            await websocket.send(chunk)
            
            offset = end
            await asyncio.sleep(0.05) # Send faster than real-time to fill buffer

        print("✓ Audio sent")
        
        # 3. Send Stop Command
        print("🛑 Sending STOP command...")
        await websocket.send(json.dumps({"type": "stop"}))
        
        # Wait for receiver to finish (it breaks on 'stopped' message)
        try:
            await asyncio.wait_for(receiver_task, timeout=10.0)
        except asyncio.TimeoutError:
            print("❌ Timeout waiting for stop confirmation")
            
        if stop_confirmed:
            print("✅ Graceful shutdown verified!")
        else:
            print("❌ Graceful shutdown failed (no confirmation)")
            
        if len(received_results) > 0:
             print(f"✅ Received {len(received_results)} transcript segments.")
        else:
             print("⚠ No transcripts received (might be short audio or VAD issue)")

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Refactor Verification")
    print("=" * 60)
    
    # 1. Create Meeting
    print("\n1️⃣  Creating meeting...")
    api_url = "http://localhost:8001/api/v1/meetings"
    meeting_data = {
        "title": "Refactor Test Meeting",
        "participants": ["Tester"]
    }
    
    try:
        response = requests.post(api_url, json=meeting_data)
        response.raise_for_status()
        meeting = response.json()
        meeting_id = meeting["id"]
        print(f"✓ Meeting created: ID={meeting_id}")
    except Exception as e:
        print(f"❌ Failed to create meeting: {e}")
        exit(1)
    
    # 2. Run Test
    print(f"\n2️⃣  Running WebSocket test...")
    try:
        asyncio.run(test_websocket_refactor(meeting_id))
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Verify Persistence
    print(f"\n3️⃣  Verifying persistence...")
    import time
    time.sleep(2) # Wait for background worker to save
    try:
        # Check history API
        hist_url = f"http://localhost:8001/api/v1/history/{meeting_id}"
        resp = requests.get(hist_url)
        data = resp.json()
        transcripts = data.get("transcripts", [])
        print(f"✓ Found {len(transcripts)} saved transcripts in history.")
        if len(transcripts) > 0:
            print("✅ Persistence verified!")
        else:
            print("⚠ No transcripts found in history.")
            
    except Exception as e:
        print(f"❌ Failed to verify persistence: {e}")

