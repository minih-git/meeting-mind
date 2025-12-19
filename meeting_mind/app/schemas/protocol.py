from pydantic import BaseModel
from typing import Optional, List, Union


class HandshakeMessage(BaseModel):
    meeting_id: str
    sample_rate: int = 16000
    use_cloud_asr: bool = False


class RecognitionResult(BaseModel):
    type: str  # "partial" | "final"
    text: str
    speaker: Optional[str] = None
    timestamp: float
    vad_segments: Optional[List[List[int]]] = None
    session_id: str
