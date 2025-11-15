from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import asyncio
from .models import ImportResponseModel, NotesResponse, YoutubeImportModel, Status
from typing import List, Dict
from ..workers import (
    create_audio_transcription_chain,
    download_audio,
    translate_audio_to_text,
    generate_study_notes,
)
from ..database import init_db, get_db
from ..database.models import Note
from pathlib import Path


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await asyncio.to_thread(init_db)
        yield
    except Exception as e:
        raise e
    finally:
        print("closing connection")


def create_api():
    api = FastAPI(lifespan=lifespan)

    @api.get("/")
    @api.get("/health")
    def health():
        return {"status": "ok"}

    @api.post("/notes/youtube", response_model=ImportResponseModel)
    def create_notes_from_youtube(
        youtube_data: YoutubeImportModel, db: Session = Depends(get_db)
    ):
        # Check if a note with the same YouTube URL exists and has completed study notes
        existing_note = (
            db.query(Note)
            .filter(
                Note.youtube_url == youtube_data.url,
                Note.status == "completed",
                Note.note.isnot(None),  # Check for completed study notes
            )
            .order_by(Note.created_at.desc())
            .first()
        )

        # Create new note record
        note = Note(youtube_url=youtube_data.url, status="pending")
        db.add(note)
        db.commit()
        db.refresh(note)

        # If cached study notes exist, copy everything to the new note
        if existing_note and existing_note.note:
            note.transcription = existing_note.transcription
            note.note = existing_note.note
            note.status = "completed"
            note.audio_path = existing_note.audio_path
            note.audio_id = existing_note.audio_id
            db.commit()

            # Return success status (no task ID since we didn't create a task)
            return ImportResponseModel(
                status=Status.COMPLETED,
                import_id=str(note.id),  # Use note ID as import_id for cached results
            )

        chain_result = create_audio_transcription_chain(youtube_data.url, note.id)
        task = chain_result.delay()

        # Update note with task_id
        note.task_id = task.id
        db.commit()

        # Return task ID for tracking
        return ImportResponseModel(status=Status.PENDING, import_id=task.id)

    @api.get("/notes", response_model=List[NotesResponse])
    def list_notes(db: Session = Depends(get_db)):
        """
        List all notes from the database.
        """
        notes = db.query(Note).order_by(Note.created_at.desc()).all()
        return [
            NotesResponse(
                id=note.id,
                status=(
                    Status(note.status)
                    if note.status in [s.value for s in Status]
                    else Status.PENDING
                ),
                youtube_url=note.youtube_url,
                task_id=note.task_id,
                audio_path=note.audio_path,
                transcription=note.transcription,
                note=note.note,
                created_at=note.created_at.isoformat() if note.created_at else "",
                updated_at=note.updated_at.isoformat() if note.updated_at else "",
            )
            for note in notes
        ]

    @api.get("/notes/{notes_id}", response_model=NotesResponse)
    def get_note(notes_id: int, db: Session = Depends(get_db)):
        """
        Get a specific note by ID from the database.
        """
        note = db.query(Note).filter(Note.id == notes_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        return NotesResponse(
            id=note.id,
            status=(
                Status(note.status)
                if note.status in [s.value for s in Status]
                else Status.PENDING
            ),
            youtube_url=note.youtube_url,
            task_id=note.task_id,
            audio_path=note.audio_path,
            transcription=note.transcription,
            note=note.note,
            created_at=note.created_at.isoformat() if note.created_at else "",
            updated_at=note.updated_at.isoformat() if note.updated_at else "",
        )

    @api.post("/notes/{notes_id}/retry", response_model=ImportResponseModel)
    def retry_note(notes_id: int, db: Session = Depends(get_db)):
        """
        Retry a failed note, resuming from the last saved state.

        - If audio_path exists and is valid, only retry transcription
        - If audio_path doesn't exist or is invalid, retry from download
        - If note is already completed, returns success without retrying
        """
        note = db.query(Note).filter(Note.id == notes_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        # If already completed with study notes, return success
        if note.status == "completed" and note.note:
            return ImportResponseModel(status=Status.COMPLETED, import_id=str(note.id))

        # Check if audio file exists and is valid
        audio_exists = note.audio_path and Path(note.audio_path).exists()
        transcription_exists = note.transcription is not None

        if audio_exists and transcription_exists:
            # Audio and transcription exist, only retry study notes generation
            transcription_data = {
                "note_id": note.id,
                "transcription": note.transcription,
                "youtube_link": note.youtube_url,
            }

            # Reset status and clear previous error
            note.status = "processing"
            note.error = None
            db.commit()

            # Start only study notes generation task
            task = generate_study_notes.delay(transcription_data)
            note.task_id = task.id
            db.commit()

            return ImportResponseModel(status=Status.PENDING, import_id=task.id)
        elif audio_exists:
            # Audio exists but transcription missing, retry transcription and study notes
            audio_data = {
                "note_id": note.id,
                "audio_id": note.audio_id or "",
                "audio_path": note.audio_path,
                "youtube_link": note.youtube_url,
            }

            # Reset status and clear previous error
            note.status = "processing"
            note.error = None
            db.commit()

            # Chain transcription and study notes generation
            from celery import chain

            chain_result = chain(
                translate_audio_to_text.s(audio_data), generate_study_notes.s()
            )
            task = chain_result.delay()
            note.task_id = task.id
            db.commit()

            return ImportResponseModel(status=Status.PENDING, import_id=task.id)
        else:
            # Audio not downloaded or file missing, retry full chain
            # Reset status and clear previous error
            note.status = "pending"
            note.error = None
            note.audio_path = None
            note.audio_id = None
            db.commit()

            # Start full chain workflow
            chain_result = create_audio_transcription_chain(note.youtube_url, note.id)
            task = chain_result.delay()

            note.task_id = task.id
            db.commit()

            return ImportResponseModel(status=Status.PENDING, import_id=task.id)

    @api.post("/notes/regenerate-all")
    def regenerate_all_notes(db: Session = Depends(get_db)):
        """
        Find all notes with transcription but no study notes, set status to failed,
        and trigger note generation for them.

        Returns count of notes being regenerated.
        """
        # Find notes with transcription but no note (study notes)
        notes_to_regenerate = (
            db.query(Note)
            .filter(Note.transcription.isnot(None), Note.note.is_(None))
            .all()
        )

        count = 0
        for note in notes_to_regenerate:
            note.status = "failed"
            note.error = None  # Clear previous errors
            db.commit()

            transcription_data = {
                "note_id": note.id,
                "transcription": note.transcription,
                "youtube_link": note.youtube_url,
            }

            task = generate_study_notes.delay(transcription_data)
            note.task_id = task.id
            note.status = "processing"
            db.commit()
            count += 1

        return {
            "regenerated_count": count,
            "message": f"Triggered note generation for {count} notes",
        }

    @api.post("/notes/{notes_id}/regenerate-note", response_model=ImportResponseModel)
    def regenerate_note(notes_id: int, db: Session = Depends(get_db)):
        """
        Regenerate study notes for a specific note that has transcription but no study notes.
        Sets status to failed first, then triggers note generation.
        """
        note = db.query(Note).filter(Note.id == notes_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        if not note.transcription:
            raise HTTPException(
                status_code=400,
                detail="Note does not have transcription. Cannot generate study notes.",
            )

        if note.note:
            # Already has study notes, return success
            return ImportResponseModel(status=Status.COMPLETED, import_id=str(note.id))

        note.status = "failed"
        note.error = None
        db.commit()

        transcription_data = {
            "note_id": note.id,
            "transcription": note.transcription,
            "youtube_link": note.youtube_url,
        }

        task = generate_study_notes.delay(transcription_data)
        note.task_id = task.id
        note.status = "processing"
        db.commit()

        return ImportResponseModel(status=Status.PENDING, import_id=task.id)

    return api
