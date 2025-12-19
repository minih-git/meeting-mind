# Meeting Mind (会议灵感)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

## 项目简介

Meeting Mind 是一个**智能会议记录与分析系统**，结合了实时语音识别（ASR）、说话人分离（Diarization）和本地大语言模型（LLM）智能分析功能。它能够实时转录会议内容，区分不同的发言者，并利用本地部署的 LLM 自动生成会议标题、总结、关键要点和行动项，**确保数据隐私和安全**。

## ✨ 核心功能

| 功能                     | 描述                                                                              |
| ------------------------ | --------------------------------------------------------------------------------- |
| 🎙️ **实时语音转写**      | 基于 FunASR (SenseVoiceSmall) 模型，提供高精度的实时语音转文字功能                |
| 🤖 **本地 LLM 智能分析** | 集成 Transformers/vLLM，支持 Qwen2.5 等本地大模型，自动生成会议总结、要点和行动项 |
| 👥 **说话人分离**        | 自动识别并区分会议中的不同发言人（基于 CAM++ 说话人识别模型）                     |
| 🔄 **异步重新转写**      | 支持对历史会议录音进行后台重新转写，优化转录质量                                  |
| 🛡️ **涉密模式切换**      | 支持本地处理（涉密）与云端高精度转写（非涉密）两种模式                            |
| 📱 **移动端适配**        | 响应式设计，支持手机和平板访问                                                    |
| 🌓 **深色/浅色模式**     | 提供舒适的 UI 体验，支持一键切换主题                                              |

## 🖥️ 界面预览

- **首页**：开始新会议、实时录音转写
- **历史记录**：查看过往会议、进行 AI 分析、重新转写、下载录音

## 🛠️ 技术栈

### 后端

- **框架**：Python 3.10+, FastAPI
- **ASR**：FunASR (SenseVoiceSmall, FSMN-VAD, CAM++)
- **LLM**：Transformers / vLLM (GPU 加速), Qwen2.5-1.5B-Instruct
- **依赖管理**：uv

### 前端

- **框架**：React 18, Vite, React Router
- **通信**：WebSocket (实时语音流)
- **UI**：原生 CSS + 毛玻璃效果

## 🚀 快速开始

### 前置要求

- Python 3.10+
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
# 安装 uv (如未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 在项目根目录下
uv sync

# 下载模型
uv run python meeting_mind/download_models.py

# 启动后端服务
uv run uvicorn meeting_mind.app.main:app --host 0.0.0.0 --port 9528 --reload
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

打开浏览器访问 `http://localhost:5173`

## ⚙️ 配置说明

可以在 `meeting_mind/app/core/config.py` 中修改配置：

| 配置项         | 默认值       | 说明                               |
| -------------- | ------------ | ---------------------------------- |
| `LLM_DEVICE`   | `"cuda"`     | LLM 推理设备 (`"cuda"` 或 `"cpu"`) |
| `LLM_MODEL_ID` | Qwen2.5-1.5B | 本地 LLM 模型路径或 HuggingFace ID |
| `ASR_DEVICE`   | `"cuda"`     | ASR 推理设备                       |

## 📁 目录结构

```
meeting-mind/
├── meeting_mind/           # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── services/       # 核心服务 (ASR, LLM, Session)
│   │   └── core/           # 配置与日志
│   └── download_models.py  # 模型下载脚本
├── meeting_web/            # 前端应用
│   ├── src/
│   │   ├── components/     # React 组件
│   │   └── utils/          # 工具函数 (WebSocket, Audio)
│   └── index.html
├── recordings/             # 会议录音文件
├── data/                   # 会议元数据
└── docker-compose.yml      # Docker 部署配置
```

## 🐳 Docker 部署

```bash
docker-compose up -d
```

## 📝 更新日志

### v1.1.0 (2024-12-19)

- ✨ 新增优雅的停止动画效果和处理中 Toast 提示
- 🐛 修复后台处理状态显示不正确的问题
- 📱 优化移动端 UI 布局
- 🎨 增强深色/浅色模式对比度

### v1.0.0

- 🎉 首次发布

## 📄 许可证

MIT License

---

<p align="center">Made with ❤️ by minih</p>
