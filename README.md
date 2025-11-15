# Audio Transcription Pipeline

A FastAPI-based pipeline for downloading YouTube videos, transcribing audio, and generating structured study notes with timestamps using AI.

## Features

- 🎥 Download audio from YouTube videos
- 🎤 Transcribe audio to text with timestamps using Whisper
- 📝 Generate structured study notes in XML format using Gemini AI
- 🔄 Automatic retry mechanism (2 retries per task)
- 💾 Database caching to avoid reprocessing duplicate videos
- 🔗 Clickable YouTube timestamps in study notes

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- GEMINI_API_KEY from Google AI Studio
- (Optional) OPENAI_BASE_URL and OPENAI_API_KEY for local Whisper server

## Installation

### Quick Setup (Recommended)

Run the automated setup script:

```bash
python setup.py
```

This script will:
- ✅ Check Python version
- ✅ Install dependencies (using uv or pip)
- ✅ Create necessary directories
- ✅ Set up environment variables (.env file)
- ✅ Start Docker Compose services (Faster Whisper server)
- ✅ Initialize database

### Manual Setup

1. **Clone the repository** (if applicable) or navigate to the project directory

2. **Install dependencies using uv:**
   
   **Option 1: Using uv sync (Recommended):**
   ```bash
   uv sync
   ```
   
   **Option 2: Using uv pip install:**
   ```bash
   # Install from pyproject.toml
   uv pip install -e .
   
   # Or install dependencies directly
   uv pip install aiosqlite celery[redis] fastapi[standard] google-generativeai openai pytube sqlalchemy yt-dlp[default]
   ```
   
   **Option 3: Using pip (if not using uv):**
   ```bash
   pip install -e .
   ```

3. **Set up environment variables:**
   
   Create a `.env` file or export the following environment variables:
   
   ```bash
   # Required: Gemini API key for generating study notes
   export GEMINI_API_KEY="your-gemini-api-key-here"
   
   # Optional: OpenAI settings for local Whisper server
   export OPENAI_BASE_URL="http://localhost:8001/v1/"
   export OPENAI_API_KEY="cant-be-empty"
   ```
   
   **Getting GEMINI_API_KEY:**
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Copy and set it as `GEMINI_API_KEY` environment variable

## Running the Application

### 1. Start Celery Worker

The Celery worker processes the background tasks (download, transcription, note generation).

**For Linux/Mac:**
```bash
celery -A src.workers.celery worker --loglevel=info
```

**For Windows:**
```bash
celery -A src.workers.celery worker --pool=solo --loglevel=info
```

The worker will process tasks from the queue. Keep this terminal running.

### 2. Start FastAPI Server

In a separate terminal, start the FastAPI application:

```bash
fastapi dev main.py
```

The API will be available at `http://localhost:8000`

### 3. Access API Documentation

Once the FastAPI server is running, you can access:

- **Swagger UI (Interactive Docs):** http://localhost:8000/docs
- **ReDoc (Alternative Docs):** http://localhost:8000/redoc

## API Usage Guide

### 1. Create Notes from YouTube URL

Submit a YouTube URL to start the transcription and note generation process.

**Endpoint:** `POST /notes/youtube`

**Request:**
```bash
curl -X POST "http://localhost:8000/notes/youtube" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID"
  }'
```

**Response:**
```json
{
  "status": "pending",
  "import_id": "task-id-or-note-id"
}
```

**Note:** If a completed note with the same YouTube URL already exists, it will return immediately with `status: "completed"` and copy the existing data.

### 2. Check Note Status

Get the status and details of a specific note by ID.

**Endpoint:** `GET /notes/{notes_id}`

**Request:**
```bash
curl "http://localhost:8000/notes/1"
```

**Response:**
```json
{
  "id": 1,
  "status": "completed",
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "task_id": "task-id",
  "audio_path": "media/audio-id.mp3",
  "transcription": "[0.00s -> 5.23s] Hello world...",
  "note": "<notes><summary>...</summary><section>...</section></notes>",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:05:00"
}
```

**Status Values:**
- `pending` - Task is queued
- `processing` - Task is being processed
- `completed` - Task completed successfully
- `failed` - Task failed after all retries

### 3. List All Notes

Get a list of all notes in the database.

**Endpoint:** `GET /notes`

**Request:**
```bash
curl "http://localhost:8000/notes"
```

**Response:**
```json
[
  {
    "id": 1,
    "status": "completed",
    "youtube_url": "...",
    "transcription": "...",
    "note": "...",
    ...
  },
  ...
]
```

### 4. Retry Failed Notes

Retry a failed note, resuming from the last saved state.

**Endpoint:** `POST /notes/{notes_id}/retry`

**Request:**
```bash
curl -X POST "http://localhost:8000/notes/1/retry"
```

**Response:**
```json
{
  "status": "pending",
  "import_id": "new-task-id"
}
```

**How it works:**
- If audio and transcription exist → Only retries study notes generation
- If only audio exists → Retries transcription + study notes
- If nothing exists → Retries full chain (download → transcription → notes)

### 5. Regenerate All Notes

Regenerate study notes for all notes that have transcription but no study notes.

**Endpoint:** `POST /notes/regenerate-all`

**Request:**
```bash
curl -X POST "http://localhost:8000/notes/regenerate-all"
```

**Response:**
```json
{
  "regenerated_count": 5,
  "message": "Triggered note generation for 5 notes"
}
```

### 6. Regenerate Specific Note

Regenerate study notes for a specific note that has transcription.

**Endpoint:** `POST /notes/{notes_id}/regenerate-note`

**Request:**
```bash
curl -X POST "http://localhost:8000/notes/1/regenerate-note"
```

## Workflow

The system processes videos through a chained workflow:

1. **Download Audio** (`download_audio`)
   - Downloads audio from YouTube
   - Saves audio file path to database
   - Status: `processing`

2. **Transcribe Audio** (`translate_audio_to_text`)
   - Transcribes audio using Whisper
   - Saves transcription with timestamps to database
   - Status: `processing`

3. **Generate Study Notes** (`generate_study_notes`)
   - Generates structured XML study notes using Gemini AI
   - Includes clickable YouTube timestamps
   - Saves to database
   - Status: `completed`

## Caching & Optimization

- **Automatic Caching:** If a YouTube URL was previously processed and completed, the system automatically copies the existing data instead of reprocessing
- **Intermediate State Storage:** Each step saves its results to the database, allowing retries from any point
- **Task Cancellation:** When an existing completed note is found, remaining tasks in the chain are automatically cancelled

## Database

The application uses SQLite databases:

- `db.sqlite` - Main database for notes and intermediate states
- `celery.sqlite` - Celery broker and result backend

Database schema is automatically created on first run.

## Troubleshooting

### Celery Worker Not Processing Tasks

- Ensure the worker is running: `celery -A src.workers.celery worker --loglevel=info`
- Check worker logs for errors
- Verify database files are accessible

### GEMINI_API_KEY Error

- Ensure `GEMINI_API_KEY` is set in your environment
- Verify the API key is valid at [Google AI Studio](https://aistudio.google.com/app/apikey)

### Tasks Stuck in Pending

- Check if Celery worker is running
- Verify worker can access the database
- Check worker logs for errors

### Transcription Fails

- Ensure Whisper server is running (if using local server)
- Check `OPENAI_BASE_URL` and `OPENAI_API_KEY` are set correctly
- Verify audio file was downloaded successfully

## Example Workflow

```bash
# 1. Start Celery worker (Terminal 1)
celery -A src.workers.celery worker --pool=solo --loglevel=info

# 2. Start FastAPI server (Terminal 2)
uvicorn main:api --reload

# 3. Submit a YouTube URL
curl -X POST "http://localhost:8000/notes/youtube" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Response: {"status": "pending", "import_id": "abc123"}

# 4. Check status (replace 1 with your note ID)
curl "http://localhost:8000/notes/1"

# 5. Once completed, retrieve the study notes
curl "http://localhost:8000/notes/1" | jq '.note'
```

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` or `/health` | Health check |
| POST | `/notes/youtube` | Create notes from YouTube URL |
| GET | `/notes` | List all notes |
| GET | `/notes/{notes_id}` | Get specific note by ID |
| POST | `/notes/{notes_id}/retry` | Retry failed note |
| POST | `/notes/regenerate-all` | Regenerate all incomplete notes |
| POST | `/notes/{notes_id}/regenerate-note` | Regenerate specific note |

## Study Notes Format

Generated study notes use XML structure:

```xml
<notes>
  <summary>
    <title>Summary</title>
    <body>Main topics and takeaways...</body>
  </summary>
  <section>
    <title>Section Title</title>
    <timestamp>[5:23](youtube_url?t=323)</timestamp>
    <body>
      - Key points
      - **Important concepts**
    </body>
  </section>
</notes>
```

## License

[Add your license here]

