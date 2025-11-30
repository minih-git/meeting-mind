from fastapi import APIRouter, HTTPException, BackgroundTasks
from meeting_mind.app.schemas.meeting import (
    MeetingCreate,
    MeetingResponse,
    TranscriptResponse,
)
from meeting_mind.app.services.session_mgr import session_manager

router = APIRouter()


@router.post("/meetings", response_model=MeetingResponse)
def create_meeting(meeting: MeetingCreate):
    return session_manager.create_meeting(meeting.title, meeting.participants)


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
def get_meeting(meeting_id: str):
    meeting = session_manager.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.post("/meetings/{meeting_id}/stop")
def stop_meeting(meeting_id: str):
    if not session_manager.stop_meeting(meeting_id):
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"status": "success", "message": "Meeting stopped"}


@router.get("/meetings/{meeting_id}/transcript", response_model=TranscriptResponse)
def get_transcript(meeting_id: str):
    items = session_manager.get_transcript(meeting_id)
    return TranscriptResponse(meeting_id=meeting_id, items=items)


@router.post("/meetings/{meeting_id}/analyze")
async def analyze_meeting(meeting_id: str):
    """
    触发会议 AI 分析 (总结、要点、行动项)
    """
    result = await session_manager.generate_analysis(meeting_id)
    if not result:
        raise HTTPException(status_code=400, detail="无法生成分析 (可能会议内容为空)")
    return result


@router.post("/meetings/{meeting_id}/retranscribe")
async def retranscribe_meeting(meeting_id: str, background_tasks: BackgroundTasks):
    """
    重新转写会议音频 (异步)
    """
    # 验证会议是否存在
    meeting = session_manager.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    async def _run_retranscribe(mid: str):
        try:
            await session_manager.retranscribe_meeting(mid)
        except Exception as e:
            # 这里无法直接返回 HTTP 错误给用户，建议记录日志
            # session_manager 内部已有日志记录
            pass

    background_tasks.add_task(_run_retranscribe, meeting_id)

    return {"status": "processing", "message": "后台转写任务已启动，请稍后刷新查看结果"}


@router.post("/meetings/{meeting_id}/generate_title")
async def generate_meeting_title(meeting_id: str):
    """
    生成智能标题
    """
    title = await session_manager.generate_title(meeting_id)
    if not title:
        raise HTTPException(status_code=400, detail="无法生成标题")
    return {"title": title}
