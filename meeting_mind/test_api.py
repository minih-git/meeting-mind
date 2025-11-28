import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_api():
    print("正在测试 API 接口...")

    # 1. 创建会议
    print("1. 正在创建会议...")
    payload = {
        "title": "API Test Meeting",
        "participants": ["Alice", "Bob"]
    }
    try:
        res = requests.post(f"{BASE_URL}/meetings", json=payload)
        res.raise_for_status()
        meeting = res.json()
        print(f"会议已创建: {meeting}")
        meeting_id = meeting["id"]
    except Exception as e:
        print(f"创建会议失败: {e}")
        return

    # 2. 获取会议
    print(f"2. 正在获取会议 {meeting_id} 的信息...")
    try:
        res = requests.get(f"{BASE_URL}/meetings/{meeting_id}")
        res.raise_for_status()
        info = res.json()
        print(f"会议信息: {info}")
        assert info["title"] == "API Test Meeting"
    except Exception as e:
        print(f"获取会议失败: {e}")

    # 3. 停止会议
    print(f"3. 正在停止会议 {meeting_id}...")
    try:
        res = requests.post(f"{BASE_URL}/meetings/{meeting_id}/stop")
        res.raise_for_status()
        print(f"停止结果: {res.json()}")
    except Exception as e:
        print(f"停止会议失败: {e}")

    # 4. 验证状态
    print("4. 正在验证状态是否已完成...")
    try:
        res = requests.get(f"{BASE_URL}/meetings/{meeting_id}")
        info = res.json()
        print(f"会议状态: {info['status']}")
        assert info["status"] == "finished"
    except Exception as e:
        print(f"验证状态失败: {e}")

    print("API 测试完成。")

if __name__ == "__main__":
    test_api()
