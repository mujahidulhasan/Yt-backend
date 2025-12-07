from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
from yt_dlp.utils import DownloadError

app = FastAPI(title="YouTube Info Backend (yt-dlp)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # চাইলে চাইলে পরে ভেরসেল ডোমেইন বসাতে পারো
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
    return {
        "ok": True,
        "message": "YouTube backend is running. Call /yt/info?url=... to use it."
    }


@app.get("/yt/info", response_model=YTResponse)
async def yt_info(url: str = Query(..., description="YouTube video URL")):
    """Use yt-dlp to extract stream info for a YouTube video."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

    except DownloadError as e:
        msg = str(e)
        # বিশেষ কেস: bot check
        if "Sign in to confirm you’re not a bot" in msg or "not a bot" in msg:
            raise HTTPException(
                status_code=403,
                detail=(
                    "YouTube এই ভিডিওর জন্য 'sign in to confirm you’re not a bot' চাচ্ছে। "
                    "server-side backend এই check পাশ করতে পারে না। অন্য কোনো ভিডিও ট্রাই করুন।"
                ),
            )
        # অন্য yt-dlp error
        raise HTTPException(status_code=400, detail=msg)

    except Exception as e:
        # generic unexpected error
        raise HTTPException(status_code=500, detail=f"Unexpected backend error: {e}")

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
