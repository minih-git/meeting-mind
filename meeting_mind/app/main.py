import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from fastapi import FastAPI
from meeting_mind.app.api.v1.router import api_router
from meeting_mind.app.services.asr_engine import asr_engine
from meeting_mind.app.services.llm_engine import llm_engine

from contextlib import asynccontextmanager
from meeting_mind.app.core.logger import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("正在启动 MeetingMind...")

    # 预加载模型
    # 注意：这可能会阻塞启动。
    asr_engine.load_models()
    # 加载 LLM 引擎 (vLLM)
    llm_engine.load_model()

    yield

    # Shutdown
    logger.info("正在停止 MeetingMind...")
    await asr_engine.stop_worker()
    llm_engine.shutdown()
    logger.info("MeetingMind 已停止")


app = FastAPI(title="MeetingMind API", lifespan=lifespan)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "Welcome to MeetingMind API"}


if __name__ == "__main__":
    import uvicorn

    uvicron.run("meeting_mind.app.main:app", host="0.0.0.0", port=9528, reload=True)
