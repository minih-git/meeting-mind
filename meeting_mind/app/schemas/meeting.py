from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class MeetingCreate(BaseModel):
    title: str
    participants: Optional[List[str]] = []

class MeetingResponse(BaseModel):
    id: str
    title: str
    status: str  # "active", "finished"
    start_time: float
    participants: List[str]

class TranscriptItem(BaseModel):
    text: str
    speaker: Optional[str]
    timestamp: float

class TranscriptResponse(BaseModel):
    meeting_id: str
    items: List[TranscriptItem]
