from . import celery
from typing import Dict, Optional
from sqlalchemy.orm import Session
import google.generativeai as genai
from src.database import SessionLocal
from src.database.models import Note
import os
import re

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))


@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def generate_study_notes(
    self, transcription_data: Dict[str, Optional[str]]
) -> Dict[str, Optional[str]]:
    """
    Generates markdown format study notes and summary from transcription.
    Includes video timestamps to specific sections.

    Args:
        transcription_data: Dictionary containing note_id, transcription, and youtube_link

    Returns:
        Dictionary with generated study notes
    """
    db: Session = SessionLocal()
    try:
        note_id = transcription_data.get("note_id")
        transcription = transcription_data.get("transcription")
        youtube_link = transcription_data.get("youtube_link")

        # Get note from database
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return {
                "note_id": note_id,
                "study_notes": None,
                "error": f"Note with id {note_id} not found",
            }

        if not transcription:
            error_msg = transcription_data.get("error", "Transcription not found")
            note.status = "failed"
            note.error = error_msg
            db.commit()
            return {"note_id": note_id, "study_notes": None, "error": error_msg}

        # Parse transcription to extract segments with timestamps
        # Format: [start_time -> end_time] text
        segments = []
        timestamp_pattern = r"\[(\d+\.?\d*)s\s*->\s*(\d+\.?\d*)s\]\s*(.+)"

        for line in transcription.split("\n"):
            match = re.match(timestamp_pattern, line)
            if match:
                start_time = float(match.group(1))
                end_time = float(match.group(2))
                text = match.group(3).strip()
                segments.append({"start": start_time, "end": end_time, "text": text})

        segments_text = "\n".join(
            [
                f"[{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}"
                for seg in segments
            ]
        )

        prompt = f"""You are an expert note-taking assistant specializing in creating comprehensive, well-structured study notes from video transcriptions.

TASK: Generate detailed study notes in XML-structured format from the following video transcription.

The transcription includes timestamps in the format [start_time - end_time] text, where times are in seconds.

OUTPUT FORMAT - CRITICAL: You MUST generate the output using the following XML-like markup structure:

<notes>
  <summary>
    <title>Summary</title>
    <body>
      [2-3 paragraphs capturing main topics and key takeaways]
    </body>
  </summary>
  
  <section>
    <title>[Section Title]</title>
    <timestamp>[MM:SS]</timestamp>
    <body>
      [Content for this section with markdown formatting:
      - Bullet points
      - **Bold** for emphasis
      - *Italic* for subtle emphasis
      - `Code blocks` for technical terms
      - Numbered lists
      - > Blockquotes for important quotes]
    </body>
  </section>
  
  <section>
    <title>[Another Section Title]</title>
    <timestamp>[MM:SS]</timestamp>
    <body>
      [Content for this section]
    </body>
  </section>
  
  [Continue with more sections as needed]
</notes>

REQUIREMENTS:
1. **XML Structure**: Use the exact XML tags: <notes>, <summary>, <section>, <title>, <timestamp>, <body>
2. **Summary Section**: Must have <summary> with <title> and <body> containing 2-3 paragraphs
3. **Sections**: Each main topic/concept should be a separate <section> with:
   - <title>: Clear, descriptive section title
   - <timestamp>: Video timestamp in [MM:SS] or [HH:MM:SS] format (convert from seconds in transcription)
   - <body>: Content with markdown formatting
4. **Timestamps**: CRITICAL - Each section MUST include a <timestamp> tag with the relevant video timestamp in [MM:SS] or [HH:MM:SS] format based on the start_time from transcription segments
5. **Content Quality**: Include:
   - Key concepts and definitions
   - Important points and insights
   - Examples and explanations
   - Action items or takeaways
6. **Markdown in Body**: Use markdown formatting inside <body> tags:
   - Bullet points (- or *)
   - Numbered lists
   - **Bold** for emphasis
   - *Italic* for subtle emphasis
   - `Code blocks` for technical terms
   - > Blockquotes for important quotes
7. **Organization**: Structure logically with:
   - Clear hierarchy of sections
   - Related concepts grouped together
   - Progressive complexity (simple to advanced)

IMPORTANT: 
- Always wrap the entire output in <notes> tags
- Each section must have all three tags: <title>, <timestamp>, and <body>
- Timestamps should reference the actual video time from the transcription
- Use proper XML structure - close all tags properly

TRANSCRIPTION WITH TIMESTAMPS:
{segments_text}

Generate comprehensive, well-structured XML-formatted study notes:"""

        try:
            # Initialize Gemini model
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                },
            )

            # Generate study notes using Gemini
            response = model.generate_content(prompt)

            # Handle Gemini response - check for blocked content or errors
            if not response.text:
                # Check if response was blocked
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    raise ValueError(
                        f"Content generation blocked: {response.prompt_feedback.block_reason}"
                    )
                raise ValueError("Empty response from Gemini API")

            study_notes = response.text

            # Post-process: Add clickable YouTube timestamps
            # Convert timestamps in format [MM:SS] or [HH:MM:SS] to clickable YouTube links
            def add_youtube_timestamps(markdown_text: str, youtube_url: str) -> str:
                # Pattern to find timestamps like [12:34] or [1:23:45] in markdown
                # Matches [MM:SS] or [H:MM:SS] or [HH:MM:SS]
                timestamp_pattern = r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]"

                def replace_timestamp(match):
                    # Check if it's HH:MM:SS format (3 groups) or MM:SS format (2 groups)
                    if match.group(3):  # HH:MM:SS format
                        hours = int(match.group(1))
                        minutes = int(match.group(2))
                        seconds = int(match.group(3))
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        display_time = f"{hours}:{minutes:02d}:{seconds:02d}"
                    else:  # MM:SS format
                        minutes = int(match.group(1))
                        seconds = int(match.group(2))
                        total_seconds = minutes * 60 + seconds
                        display_time = f"{minutes}:{seconds:02d}"

                    # Create YouTube timestamp link
                    timestamp_link = f"{youtube_url}?t={total_seconds}"
                    return f"[{display_time}]({timestamp_link})"

                return re.sub(timestamp_pattern, replace_timestamp, markdown_text)

            # Add YouTube timestamps to the markdown
            if youtube_link:
                study_notes = add_youtube_timestamps(study_notes, youtube_link)

            # Save study notes to database
            note.note = study_notes
            note.status = "completed"
            db.commit()

            return {
                "note_id": note_id,
                "study_notes": study_notes,
                "youtube_link": youtube_link,
            }

        except Exception as e:
            # Get current retry count
            retry_count = self.request.retries

            # Only update database status if this is the final attempt
            if retry_count >= 2:
                try:
                    note = db.query(Note).filter(Note.id == note_id).first()
                    if note:
                        note.status = "failed"
                        note.error = f"Study notes generation failed after {retry_count + 1} attempts: {str(e)}"
                        db.commit()
                except:
                    pass

            raise

    finally:
        db.close()
