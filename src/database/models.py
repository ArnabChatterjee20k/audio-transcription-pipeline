from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from . import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    youtube_url = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=True, index=True)  # Celery task ID
    status = Column(String, default="pending")  # pending, processing, completed, failed

    # Intermediate states
    audio_id = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    transcription = Column(Text, nullable=True)  # Transcribed text

    # Final result
    note = Column(Text, nullable=True)  # llm personlized note

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
