import subprocess
import yt_dlp
import os


def download_raw(url, output="audio.mp3"):
    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": output,
        "postprocessors": [],  # disable ffmpeg
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def convert_with_docker(input_file, output_file):
    cmd = [
        "docker",
        "exec",
        "ffmpeg_container",
        "ffmpeg",
        "-i",
        f"/media/{input_file}",
        "-vn",
        "-acodec",
        "mp3",
        f"/media/{output_file}",
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    download_raw("https://www.youtube.com/watch?v=Uu2QK9Z9X5E")
    # convert_with_docker("audio.webm", "audio.mp3")
