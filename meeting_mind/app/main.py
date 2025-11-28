from fastapi import FastAPI
from meeting_mind.app.api.v1.router import api_router
from meeting_mind.app.services.asr_engine import asr_engine

app = FastAPI(title="MeetingMind API")

from meeting_mind.app.core.logger import logger, setup_logging

@app.on_event("startup")
async def startup_event():
    setup_logging()
    logger.info("正在启动 MeetingMind...")
    # 预加载模型
    # 注意：这可能会阻塞启动。在生产环境中，考虑异步加载或预热。
    # 目前为了确保就绪，我们同步加载。
    asr_engine.load_models()

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to MeetingMind API"}
