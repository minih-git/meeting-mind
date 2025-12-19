from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from meeting_mind.app.services.llm_engine import llm_engine
from meeting_mind.app.core.logger import logger

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512
    stream: Optional[bool] = None  # None 表示使用全局默认配置


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    与本地 LLM 进行对话。
    """
    try:
        # 确定是否流式输出（默认非流式）
        use_stream = request.stream if request.stream is not None else False

        # 转换 messages 格式
        messages_dict = [msg.model_dump() for msg in request.messages]

        if use_stream:

            async def generate_stream():
                try:
                    generator = await llm_engine.chat(
                        messages=messages_dict,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        stream=True,
                    )
                    async for chunk in generator:
                        yield chunk
                except Exception as e:
                    logger.error(f"Stream generation error: {e}")
                    yield f"Error: {str(e)}"

            return StreamingResponse(generate_stream(), media_type="text/plain")
        else:
            result = await llm_engine.chat(
                messages=messages_dict,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
            )
            return {
                "role": "assistant",
                "content": result["content"],
                "usage": result["usage"],
            }

    except Exception as e:
        logger.error(f"Chat API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
