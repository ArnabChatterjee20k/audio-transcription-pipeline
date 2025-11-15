from openai import OpenAI
from pprint import pprint

client = OpenAI(api_key="cant-be-empty", base_url="http://localhost:8001/v1/")

# audio_file = open("audio.mp3", "rb")
# transcript = client.audio.transcriptions.create(
#     model="Systran/faster-whisper-small", file=audio_file
# )

# with open("audio.mp3", "rb") as audio_file:
#     transcript = client.audio.transcriptions.create(
#         model="Systran/faster-whisper-small",
#         file=audio_file,
#         response_format="verbose_json",       # ⬅️ needed for timestamps
#         timestamp_granularities=["segment"]   # ⬅️ enables segment timestamps
#     )

# pprint(transcript)

# print("\n--- English Translation with Timestamps ---\n")
# for seg in transcript.segments:
#     print(f"[{seg.start:.2f}s -> {seg.end:.2f}s] {seg.text}")

with open("audio.mp3", "rb") as audio_file:
    transcript = client.audio.translations.create(
        model="Systran/faster-whisper-small",
        file=audio_file,
        response_format="srt",
    )

print(transcript)
