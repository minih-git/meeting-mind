import asyncio
import websockets
import json
import wave
import sys
import os

# Create a dummy wav file if not exists (16kHz, mono, 16bit)
def create_dummy_wav(filename, duration_sec=5):
    import numpy as np
    sample_rate = 16000
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    # Generate a 440Hz sine wave (A4)
    audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    print(f"Created dummy audio: {filename}")

async def test_stream():
    uri = "ws://127.0.0.1:8000/api/v1/ws"
    meeting_id = "test_debug_session"
    
    # Ensure recording dir exists
    if not os.path.exists("test_audio.wav"):
        create_dummy_wav("test_audio.wav")

    async with websockets.connect(uri) as websocket:
        # 1. Handshake
        handshake = {
            "meeting_id": meeting_id,
            "sample_rate": 16000
        }
        await websocket.send(json.dumps(handshake))
        print("Handshake sent.")

        # 2. Send Audio
        with wave.open("test_audio.wav", "rb") as wf:
            chunk_size = 3200 # 100ms
            data = wf.readframes(chunk_size // 2) # readframes takes num frames, not bytes
            
            while len(data) > 0:
                await websocket.send(data)
                # print(f"Sent {len(data)} bytes")
                await asyncio.sleep(0.1)
                
                # Check for responses
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                    print(f"Received: {response}")
                except asyncio.TimeoutError:
                    pass
                
                data = wf.readframes(chunk_size // 2)

        # 3. Stop
        await websocket.send(json.dumps({"type": "stop"}))
        print("Stop command sent.")
        
        # Wait for final results
        try:
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"Received (Final): {response}")
                if "stopped" in response:
                    break
        except asyncio.TimeoutError:
            print("Timeout waiting for final response.")

if __name__ == "__main__":
    # Need to mock session manager or ensure meeting exists?
    # The backend checks `session_manager.get_meeting(session_id)`.
    # We might need to create a meeting first via API, or mock it.
    # For simplicity, let's assume we need to create it.
    
    import requests
    try:
        res = requests.post("http://127.0.0.1:8000/api/v1/meetings", json={"title": "Debug Meeting"})
        if res.status_code == 200:
            meeting_id = res.json()["id"]
            print(f"Created meeting: {meeting_id}")
            
            # Update the meeting_id in test_stream
            # Hacky way to pass it
            
            async def test_stream_wrapper():
                uri = "ws://127.0.0.1:8000/api/v1/ws"
                
                if not os.path.exists("test_audio.wav"):
                    create_dummy_wav("test_audio.wav")

                async with websockets.connect(uri) as websocket:
                    handshake = {"meeting_id": meeting_id, "sample_rate": 16000}
                    await websocket.send(json.dumps(handshake))
                    print(f"Handshake sent for {meeting_id}")
                    
                    with wave.open("test_audio.wav", "rb") as wf:
                        chunk_size = 3200 
                        data = wf.readframes(chunk_size // 2)
                        while len(data) > 0:
                            await websocket.send(data)
                            await asyncio.sleep(0.1)
                            try:
                                response = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                                print(f"Received: {response}")
                            except asyncio.TimeoutError:
                                pass
                            data = wf.readframes(chunk_size // 2)
                    
                    await websocket.send(json.dumps({"type": "stop"}))
                    print("Stop sent")
                    try:
                        while True:
                            response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                            print(f"Received: {response}")
                    except asyncio.TimeoutError:
                        pass

            asyncio.run(test_stream_wrapper())
        else:
            print(f"Failed to create meeting: {res.text}")
    except Exception as e:
        print(f"Error: {e}")
