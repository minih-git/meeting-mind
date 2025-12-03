import asyncio
import websockets
import os


async def test_connect():
    uri = "wss://echo.websocket.org"
    try:
        async with websockets.connect(
            uri, extra_headers={"Authorization": "Bearer test"}
        ) as websocket:
            print("Connected successfully")
            await websocket.send("Hello")
            response = await websocket.recv()
            print(f"Received: {response}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_connect())
