from pydantic import BaseModel
from enum import Enum
from typing import Optional


class Status(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    COMPLETED = "completed"  # Changed from 'successfull' to match database


class YoutubeImportModel(BaseModel):
    url: str


class ImportResponseModel(BaseModel):
    status: Status
    import_id: str  # Celery task ID is a string

    class Config:
        use_enum_values = True


class NotesResponse(BaseModel):
    id: int
    status: Status
    youtube_url: str
    task_id: Optional[str] = None
    audio_path: Optional[str] = None
    transcription: Optional[str] = None
    note: Optional[str] = None  # LLM generated study notes in markdown
    created_at: str
    updated_at: str

    class Config:
        use_enum_values = True
