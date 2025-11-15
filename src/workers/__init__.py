from celery import Celery
from celery import chain

# broker -> for coordination with the workers -> where the tasks are stored -> going with redis(ideal but going with sqlite for now)
# result_backend -> for storing task results -> going with sqlite

# for linux -> celery -A src.workers.celery worker --loglevel=info
# for windows -> celery -A src.workers.celery worker --pool=solo --loglevel=info

CELERY_BROKER_BACKEND = "sqla+sqlite:///celery.sqlite"
CELERY_RESULT_BACKEND = "db+sqlite:///celery.sqlite"

# Create typed Celery application
celery: Celery = Celery(
    "worker", broker=CELERY_BROKER_BACKEND, backend=CELERY_RESULT_BACKEND
)

# Set this as the default app so shared_task can be used
# This allows @shared_task decorator to work without importing the celery instance
# celery.set_default()

# celery.autodiscover_tasks(["src.workers"])

# to resolve partial dependencies
from .download_audio import download_audio
from .translate_audio_to_text import translate_audio_to_text
from .generate_study_notes import generate_study_notes


def create_audio_transcription_chain(youtube_link: str, note_id: int):
    """
    Creates a chained workflow: download_audio -> translate_audio_to_text -> generate_study_notes

    The result from each task is automatically passed as the first argument to the next task.

    Args:
        youtube_link: YouTube URL to download and transcribe
        note_id: Database ID of the note record to update

    Returns:
        Celery chain result that can be executed with .delay() or .apply_async()
    """
    return chain(
        download_audio.s(youtube_link, note_id),
        translate_audio_to_text.s(),
        generate_study_notes.s(),
    )


__all__ = [
    "celery",
    "download_audio",
    "translate_audio_to_text",
    "generate_study_notes",
    "create_audio_transcription_chain",
]
