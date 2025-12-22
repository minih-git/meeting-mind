import asyncio
import websockets
import json
import uuid
import httpx

SERVER_BASE = "http://localhost:9528/api/v1"
WS_URL = "ws://localhost:9528/api/v1/stream/ws"


def create_meeting(title):
    try:
        resp = httpx.post(
            f"{SERVER_BASE}/meetings",
            json={"title": title, "participants": ["TestUser"]},
        )
        if resp.status_code == 503:
            print(f"[create_meeting] SUCCESS: Server busy 503 received for {title}")
            # Check message content if possible
            return "BUSY"
        resp.raise_for_status()
        return resp.json()["id"]
    except Exception as e:
        print(f"Failed to create meeting: {e}")
        return None


async def connect_client(name, meeting_id, hold_time=2):
    uri = WS_URL
    print(f"[{name}] Connecting to {uri} with meeting_id={meeting_id}...")

    if meeting_id == "BUSY":
        print(f"[{name}] Skipping WS connect because meeting creation returned BUSY")
        return "BUSY"

    try:
        async with websockets.connect(uri) as websocket:
            # 1. Handshake
            handshake = {
                "meeting_id": meeting_id,
                "sample_rate": 16000,
                "token": "test-token",
            }
            await websocket.send(json.dumps(handshake))
            print(f"[{name}] Handshake sent.")

            # Receive response (could be lock error or silence/ping)
            try:
                # Wait for a bit (loop a few times to catch immediate error)
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"[{name}] Received: {response}")

                resp_json = json.loads(response)
                if (
                    resp_json.get("type") == "error"
                    and resp_json.get("code") == "resource_busy"
                ):
                    print(f"[{name}] SUCCESS: Received expected busy error.")
                    return "BUSY"

            except asyncio.TimeoutError:
                print(f"[{name}] No immediate response (Good if first client).")
            except websockets.exceptions.ConnectionClosed as e:
                print(f"[{name}] Connection closed: {e.code} {e.reason}")
                if e.code == 1008 and "Server Busy" in str(
                    e.reason
                ):  # websockets library might not expose reason text in exception nicely depending on version
                    return "BUSY"  # treat as busy if closed with 1008
                return "CLOSED"

            print(f"[{name}] Holding connection for {hold_time}s...")
            await asyncio.sleep(hold_time)

            # Send stop
            print(f"[{name}] Sending stop...")
            await websocket.send(json.dumps({"type": "stop"}))

            # Wait for close
            try:
                while True:
                    msg = await websocket.recv()
                    print(f"[{name}] Received loop: {msg}")
            except websockets.exceptions.ConnectionClosed:
                print(f"[{name}] Connection closed normally.")

            return "OK"

    except Exception as e:
        print(f"[{name}] Error: {e}")
        return str(e)


async def test_concurrency():
    # 0. Create meetings
    id_a = create_meeting("Meeting A")
    # id_b creation moved to later step

    if not id_a:
        print("Failed to create meetings. Aborting.")
        return

    if not id_a:  # Only check id_a here, id_b will be created later
        print("Failed to create Meeting A. Aborting.")
        return

    # 1. Start Client A
    # We want Client A to stay connected while Client B tries to connect.
    print(f"\n--- Starting Client A (The Lock Holder, ID={id_a}) ---")
    task_a = asyncio.create_task(connect_client("Client A", id_a, hold_time=5))

    await asyncio.sleep(2)

    # 2. Start Client B
    # Meeting B creation should fail if lock is working!
    print(f"\n--- Creating Meeting B (Should Fail) ---")
    id_b = create_meeting("Meeting B")

    if id_b == "BUSY":
        print("\n>>> TEST PASS (Part 1): Meeting B creation was blocked with 503.")
        res_b = "BUSY"
    else:
        print(f"\n>>> RESULT B: Created ID={id_b} (UNEXPECTED, should be blocked)")
        # Proceed to connect just in case logic is different
        res_b = await connect_client("Client B", id_b, hold_time=1)

    await task_a
    print("\n--- Client A finished ---")


if __name__ == "__main__":
    try:
        asyncio.run(test_concurrency())
    except KeyboardInterrupt:
        pass
