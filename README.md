# Meeting Mind (会议灵感)

## 项目简介

Meeting Mind 是一个智能会议记录与分析系统，结合了实时语音识别（ASR）、说话人分离（Diarization）和本地大语言模型（LLM）智能分析功能。它能够实时转录会议内容，区分不同的发言者，并利用本地部署的 LLM 自动生成会议标题、总结、关键要点和行动项，确保数据隐私和安全。

## 核心功能

- **实时语音转写**：基于 FunASR (SenseVoiceSmall) 模型，提供高精度的实时语音转文字功能。
- **本地 LLM 智能分析**：集成 vLLM/Transformers，支持部署本地大模型（如 Qwen2.5），自动生成会议标题、总结、关键要点和行动项，无需依赖外部 API。
- **说话人分离**：自动识别并区分会议中的不同发言人。
- **异步重新转写**：支持对历史会议录音进行后台重新转写，优化转录质量。
- **会议回溯与管理**：
  - 全新的历史记录页面，支持按时间查看。
  - 详情页展示 AI 分析结果（总结、要点、行动项）。
  - 支持下载录音文件。
- **深色/浅色模式**：提供舒适的 UI 体验，支持一键切换主题。

## 技术栈

- **后端**：
  - Python, FastAPI
  - **ASR**: FunASR (SenseVoiceSmall, FSMN-VAD, Campplus)
  - **LLM**: vLLM (GPU加速) / Transformers (CPU兼容), Qwen2.5
- **前端**：
  - React, Vite, React Router
  - WebSocket (实时通信)

## 快速开始

### 前置要求

- Python 3.10+ (建议)
- Node.js 16+
- Git
- (可选) NVIDIA GPU + CUDA (用于 vLLM 加速)

### 1. 克隆项目

```bash
git clone https://github.com/minih-git/meeting-mind.git
cd meeting-mind
```

### 2. 后端设置 (meeting_mind)

该项目使用 `uv` 进行依赖管理。

```bash
# 在项目根目录下 (确保已安装 uv)
uv sync

# 下载模型 (通过 uv 运行)
uv run python meeting_mind/download_models.py

# 启动后端服务
uv run uvicorn meeting_mind.app.main:app --host 0.0.0.0 --port 8000 --reload
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

- **首页 (/home)**: 开始新会议、实时录音转写。
- **历史记录 (/history)**: 查看过往会议、进行 AI 分析、重新转写。

## 配置说明

可以在 `meeting_mind/app/core/config.py` 中修改配置：

- `LLM_DEVICE`: `"cuda"` (默认) 或 `"cpu"`。
- `LLM_MODEL_ID`: 本地 LLM 模型路径或 HuggingFace ID。
- `ASR_DEVICE`: ASR 推理设备。

## 目录结构

- `meeting_mind/`: 后端服务代码
  - `app/services/llm_engine.py`: 本地 LLM 引擎实现
  - `app/services/asr_engine.py`: ASR 语音识别引擎
- `meeting_web/`: 前端应用代码
  - `src/components/RecorderPage.jsx`: 录音主页
  - `src/components/HistoryPage.jsx`: 历史详情与分析
- `recordings/`: 会议录音文件存储
- `data/`: 会议元数据存储

## 许可证

MIT License
