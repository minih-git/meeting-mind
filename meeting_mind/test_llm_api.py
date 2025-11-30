import requests
import json
import sys


def test_chat_api():
    url = "http://localhost:8000/api/v1/chat"
    headers = {"Content-Type": "application/json"}

    # 在此处切换测试模式
    USE_STREAM = False

    data = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "你好，请介绍一下你自己。"},
        ],
        "temperature": 0.7,
        # "stream": USE_STREAM, # 不传 stream 参数以测试默认配置，或显式传递覆盖
        "stream": USE_STREAM,
    }

    print(f"Sending request to {url} (Stream={USE_STREAM})...")

    try:
        with requests.post(
            url, headers=headers, json=data, stream=USE_STREAM
        ) as response:
            response.raise_for_status()
            print("Response status:", response.status_code)

            if USE_STREAM:
                print("Response content (Stream):")
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        print(chunk.decode("utf-8"), end="", flush=True)
                print("\nDone.")
            else:
                result = response.json()
                print("Response content:", result["content"])
                if "usage" in result:
                    usage = result["usage"]
                    print("-" * 30)
                    print(f"Token Usage:")
                    print(f"  Prompt: {usage.get('prompt_tokens')}")
                    print(f"  Completion: {usage.get('completion_tokens')}")
                    print(f"  Total: {usage.get('total_tokens')}")
                    print(f"Performance:")
                    print(f"  Time: {usage.get('total_time_sec')}s")
                    print(f"  Speed: {usage.get('tokens_per_sec')} tokens/sec")
                    print("-" * 30)
                else:
                    print("No usage info returned.")

    except Exception as e:
        print(f"API request failed: {e}")


if __name__ == "__main__":
    test_chat_api()
