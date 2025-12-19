from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class TranscriptItem(BaseModel):
    text: str
    speaker: Optional[str] = None
    timestamp: float


class AIAnalysis(BaseModel):
    summary: str
    key_points: str
    action_items: str


class MeetingCreate(BaseModel):
    title: str
    participants: Optional[List[str]] = []


class MeetingResponse(BaseModel):
    id: str
    title: str
    status: str  # "active", "finished"
    start_time: float
    participants: List[str]
    audio_file: Optional[str] = None
    transcripts: Optional[List[TranscriptItem]] = []
    ai_analysis: Optional[AIAnalysis] = None
    use_cloud_model: bool = False


class TranscriptResponse(BaseModel):
    meeting_id: str
    items: List[TranscriptItem]
