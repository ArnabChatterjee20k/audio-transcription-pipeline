from . import celery
from pathlib import Path
from typing import Dict, Optional
from sqlalchemy.orm import Session
from openai import OpenAI
from src.database import SessionLocal
from src.database.models import Note
import os


@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def translate_audio_to_text(
    self, audio_data: Dict[str, str]
) -> Dict[str, Optional[str]]:
    db: Session = SessionLocal()
    try:
        note_id = audio_data.get("note_id")
        audio_path = audio_data.get("audio_path")
        audio_id = audio_data.get("audio_id")

        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return {
                "note_id": note_id,
                "transcription": None,
                "error": f"Note with id {note_id} not found",
            }

        if not audio_path or not Path(audio_path).exists():
            error_msg = audio_data.get("error", "Audio file not found")
            note.status = "failed"
            db.commit()
            return {
                "note_id": note_id,
                "audio_id": audio_id,
                "transcription": None,
                "error": error_msg,
            }

        base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:8001/v1/")
        api_key = os.getenv("OPENAI_API_KEY", "cant-be-empty")

        client = OpenAI(api_key=api_key, base_url=base_url)

        # TODO:(improvement)
        # Transcribe audio file using Whisper
        # better way -> to chunk into segments and feed to the model for large files
        # Exceptions here will trigger retries
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="Systran/faster-whisper-small",
                file=audio_file,
                response_format="verbose_json",  # needed for timestamps
                timestamp_granularities=["segment"],  # enables segment timestamps
            )

        transcription_lines = []
        if hasattr(transcript, "segments") and transcript.segments:
            for seg in transcript.segments:
                transcription_lines.append(
                    f"[{seg.start:.2f}s -> {seg.end:.2f}s] {seg.text}"
                )
            transcription = "\n".join(transcription_lines)
        else:
            transcription = (
                transcript.text if hasattr(transcript, "text") else str(transcript)
            )

        note.transcription = transcription
        note.status = "processing"  # Still processing (study notes generation pending)
        db.commit()

        return {
            "note_id": note_id,
            "audio_id": audio_id,
            "transcription": transcription,
            "audio_path": audio_path,
            "youtube_link": audio_data.get("youtube_link"),
        }
    except Exception as e:
        retry_count = self.request.retries

        if retry_count >= 2:  # Final attempt failed
            try:
                note = db.query(Note).filter(Note.id == note_id).first()
                if note:
                    note.status = "failed"
                    note.error = f"Transcription failed after {retry_count + 1} attempts: {str(e)}"
                    db.commit()
            except:
                pass
        raise
    finally:
        db.close()
