import sys
import logging
from loguru import logger

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging():
    # 移除默认的 handler
    logger.remove()

    # 添加控制台 handler，设置格式
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    # 拦截标准 logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 设置第三方库的日志级别，屏蔽杂音
    for lib in ["uvicorn", "fastapi", "funasr", "modelscope", "torch", "multipart", "numba"]:
        logging.getLogger(lib).handlers = [] # 清除原有 handler
        logging.getLogger(lib).propagate = True # 允许冒泡到 root (被 InterceptHandler 捕获)
        # 将这些库的级别设置为 WARNING，减少 INFO 输出
        logging.getLogger(lib).setLevel(logging.WARNING)

    # 特别处理 uvicorn.access，保留访问日志但转为 loguru
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

__all__ = ["logger", "setup_logging"]
