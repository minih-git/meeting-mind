#!/usr/bin/env python3
"""
文件上传脚本 - 调用 meeting_mind API 上传文件

用法:
    python upload_file.py <文件路径> [--base-url BASE_URL]

示例:
    python upload_file.py /path/to/audio.wav
    python upload_file.py audio.mp3 --base-url http://localhost:8000
"""

import argparse
import sys
from pathlib import Path

import requests

# 默认服务器地址
DEFAULT_BASE_URL = "https://devapp.bocommlife.com/meeting"


def upload_file(file_path: str, base_url: str = DEFAULT_BASE_URL) -> dict:
    """
    上传文件到服务器

    Args:
        file_path: 要上传的文件路径
        base_url: 服务器基础 URL

    Returns:
        服务器响应的 JSON 数据
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"路径不是文件: {file_path}")

    # 移除末尾斜杠，确保 URL 格式正确
    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/v1/upload"

    print(f"正在上传文件: {file_path.name}")
    print(f"文件大小: {file_path.stat().st_size / 1024:.2f} KB")
    print(f"目标地址: {url}")
    print("-" * 40)

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f)}
        response = requests.post(url, files=files)

    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(
        description="上传文件到 meeting_mind 服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    %(prog)s /path/to/audio.wav
    %(prog)s audio.mp3 --base-url http://localhost:8000
        """,
    )
    parser.add_argument("file", help="要上传的文件路径")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"服务器基础 URL (默认: {DEFAULT_BASE_URL})",
    )

    args = parser.parse_args()

    try:
        result = upload_file(args.file, args.base_url)
        print("上传成功!")
        print(f"  状态: {result.get('status')}")
        print(f"  文件名: {result.get('filename')}")
        print(f"  服务器路径: {result.get('path')}")
        print(f"  大小: {result.get('size', 0) / 1024:.2f} KB")
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"错误: 无法连接到服务器 {args.base_url}", file=sys.stderr)
        print("请确认服务器是否已启动", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP 错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"未知错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
