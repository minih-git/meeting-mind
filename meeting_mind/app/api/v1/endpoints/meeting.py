from fastapi import APIRouter, HTTPException
from meeting_mind.app.schemas.meeting import MeetingCreate, MeetingResponse, TranscriptResponse
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
