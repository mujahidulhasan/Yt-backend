from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="YouTube Info Backend (yt-dlp)")

# CORS: you can restrict origins later for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in production, replace * with your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class YTResponse(BaseModel):
    title: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    formats: list[dict] = []
    audios: list[dict] = []


def _is_progressive(f: dict) -> bool:
    """Video + audio together (progressive stream)."""
    return f.get("vcodec") != "none" and f.get("acodec") != "none"


def _is_audio_only(f: dict) -> bool:
    """Audio-only stream."""
    return f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")


@app.get("/")
async def root():
    return {"ok": True, "message": "YouTube backend is running. Call /yt/info?url=... to use it."}


@app.get("/yt/info", response_model=YTResponse)
async def yt_info(url: str = Query(..., description="YouTube video URL")):
    """Use yt-dlp to extract stream info for a YouTube video."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get("title")
    duration = info.get("duration")
    thumbnail = info.get("thumbnail")

    video_formats: list[dict] = []
    audio_formats: list[dict] = []

    for f in info.get("formats", []):
        fmt = {
            "itag": f.get("format_id"),
            "ext": f.get("ext"),
            "height": f.get("height"),
            "width": f.get("width"),
            "acodec": f.get("acodec"),
            "vcodec": f.get("vcodec"),
            "filesize": f.get("filesize") or f.get("filesize_approx"),
            "url": f.get("url"),
            "format_note": f.get("format_note"),
            "abr": f.get("abr"),
        }

        if _is_progressive(f):
            video_formats.append(fmt)
        elif _is_audio_only(f):
            audio_formats.append(fmt)

    video_formats = sorted(video_formats, key=lambda x: x.get("height") or 0)
    audio_formats = sorted(audio_formats, key=lambda x: x.get("abr") or 0)

    return YTResponse(
        title=title,
        duration=duration,
        thumbnail=thumbnail,
        formats=video_formats,
        audios=audio_formats,
    )
