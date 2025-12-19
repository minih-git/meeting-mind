from fastapi import APIRouter
from meeting_mind.app.api.v1.endpoints import stream, meeting, llm

api_router = APIRouter()
api_router.include_router(stream.router, tags=["stream"])
api_router.include_router(meeting.router, tags=["meeting"])
api_router.include_router(llm.router, tags=["llm"])
