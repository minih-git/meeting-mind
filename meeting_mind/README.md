# MeetingMind (实时多人会议记录系统)

MeetingMind 是一个基于阿里巴巴 FunASR 的实时会议记录与转写系统。它提供 WebSocket 接口用于低延迟音频流传输，以及 REST API 用于会议管理。

## 功能特性

- **实时语音转文字 (ASR)**: 使用 `Paraformer-large-online` 模型提供高精度转写。
- **语音活动检测 (VAD)**: 使用 `Fsmn-vad-online` 进行自动语音切分。
- **实时标点**: 使用 `Ct-punc` 模型进行实时标点恢复。
- **说话人分离 (Diarization)**: 使用 `Cam++` 模型进行说话人识别。
- **WebSocket API**: 支持低延迟的音频流输入和结果输出。
- **REST API**: 支持会议创建、状态查询和转写记录获取。

## 项目结构

```
meeting_mind/
├── app/
│   ├── api/            # API 接口 (WebSocket & HTTP)
│   ├── core/           # 核心配置
│   ├── schemas/        # Pydantic 数据模型
│   └── services/       # 业务逻辑 (ASREngine, SessionManager)
├── models/             # FunASR 模型文件
├── download_models.py  # 模型下载脚本
├── test_integration.py # 端到端集成测试脚本
└── requirements.txt    # 项目依赖
```

## 安装指南

1. **前提条件**: Python 3.10+
2. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```
3. **下载模型**:
   ```bash
   python download_models.py
   ```

## 使用说明

### 1. 启动服务

```bash
uvicorn meeting_mind.app.main:app --host 0.0.0.0 --port 8000
```

### 2. 运行集成测试

```bash
python test_integration.py
```

## API 文档

### WebSocket 流式接口

- **URL**: `ws://localhost:8000/api/v1/ws`
- **协议流程**:
  1. **握手 (Handshake)**: 客户端发送 `{"meeting_id": "...", "sample_rate": 16000}`
  2. **音频流 (Audio)**: 客户端发送二进制音频分片 (PCM 16k 16bit)。
  3. **停止 (Stop)**: 客户端发送 `{"type": "stop"}` 结束会话。
  4. **响应 (Response)**: 服务端返回 JSON `{"type": "partial"|"final", "text": "...", "speaker": "..."}`。

### REST API

- **创建会议**: `POST /api/v1/meetings`
- **获取会议信息**: `GET /api/v1/meetings/{id}`
- **停止会议**: `POST /api/v1/meetings/{id}/stop`
- **获取转写记录**: `GET /api/v1/meetings/{id}/transcript`

## 许可证

MIT
