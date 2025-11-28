# Meeting Mind (会议灵感)

## 项目简介

Meeting Mind 是一个智能会议记录与分析系统，结合了实时语音识别（ASR）、说话人分离（Diarization）和 AI 智能总结功能。它能够实时转录会议内容，区分不同的发言者，并利用大语言模型自动生成会议标题和摘要。

## 核心功能

- **实时语音转写**：基于 FunASR (SenseVoiceSmall) 模型，提供高精度的实时语音转文字功能。
- **说话人分离**：自动识别并区分会议中的不同发言人。
- **智能总结**：集成 OpenAI API，自动为会议生成标题和关键内容摘要。
- **会议回溯**：支持查看历史会议记录、播放录音及下载音频文件。
- **深色/浅色模式**：提供舒适的 UI 体验，支持一键切换主题。

## 技术栈

- **后端**：Python, FastAPI, FunASR (SenseVoiceSmall, FSMN-VAD, Campplus), OpenAI
- **前端**：React, Vite, WebSocket

## 快速开始

### 前置要求

- Python 3.8+
- Node.js 16+
- Git

### 1. 克隆项目

```bash
git clone https://github.com/minih-git/meeting-mind.git
cd meeting-mind
```

### 2. 后端设置 (meeting_mind)

```bash
cd meeting_mind

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 下载模型 (首次运行会自动下载，也可手动执行)
python download_models.py

# 启动后端服务
uvicorn app.main:app --reload
```

### 3. 前端设置 (meeting_web)

```bash
cd meeting_web

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 4. 访问应用

打开浏览器访问前端控制台输出的地址 (通常为 `http://localhost:5173`)。

## 目录结构

- `meeting_mind/`: 后端服务代码
- `meeting_web/`: 前端应用代码
- `recordings/`: 会议录音文件存储

## 许可证

MIT License
