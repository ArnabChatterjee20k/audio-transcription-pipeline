from . import celery
import yt_dlp
from pathlib import Path
from typing import Dict
from sqlalchemy.orm import Session
from src.database import SessionLocal
from src.database.models import Note


@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,  # Retry 2 times (3 total attempts: initial + 2 retries)
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def download_audio(self, youtube_link: str, note_id: int) -> Dict[str, str]:
    db: Session = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return {"error": f"Note with id {note_id} not found", "note_id": note_id}

        note.status = "processing"
        db.commit()

        media_dir = Path("media")
        media_dir.mkdir(exist_ok=True)

        import uuid

        audio_id = str(uuid.uuid4())
        output_file = media_dir / f"{audio_id}.mp3"

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(output_file),
            "postprocessors": [],  # disable ffmpeg
        }

        # Download audio - exceptions here will trigger retries
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_link])

        # If download succeeds, save to database
        note.audio_id = audio_id
        note.audio_path = str(output_file)
        note.status = "processing"
        db.commit()

        return {
            "note_id": note_id,
            "audio_id": audio_id,
            "audio_path": str(output_file),
            "youtube_link": youtube_link,
        }
    except Exception as e:
        retry_count = self.request.retries
        if retry_count >= 2:  # Final attempt failed
            try:
                note = db.query(Note).filter(Note.id == note_id).first()
                if note:
                    note.status = "failed"
                    note.error = (
                        f"Download failed after {retry_count + 1} attempts: {str(e)}"
                    )
                    db.commit()
            except:
                pass

        # Re-raise exception to trigger Celery retry mechanism
        raise
    finally:
        db.close()
