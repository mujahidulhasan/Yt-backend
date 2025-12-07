from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import re
import os
from dotenv import load_dotenv

# Load environment variables (useful for future API keys if needed)
load_dotenv()

app = FastAPI(
    title="Multi-Platform Video Downloader Backend",
    version="1.0.0",
    description="Extracts video information and formats using yt-dlp.",
)

# --- CORS Configuration ---
# Allow all origins for the frontend deployment
origins = [
    "*", # In production, restrict this to your Vercel frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Utility Functions ---

def format_duration(seconds):
    """Converts seconds into HH:MM:SS format."""
    if seconds is None:
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def format_views(views):
    """Formats large numbers for readability (e.g., 1234567 -> 1.2M)."""
    if views is None:
        return "N/A"
    views = int(views)
    if views >= 1_000_000_000:
        return f"{views / 1_000_000_000:.1f}B"
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M"
    if views >= 1_000:
        return f"{views / 1_000:.1f}K"
    return str(views)

# --- Data Filtering Logic (CRITICAL) ---
# This implements the core requirement: only combined streams for MP4 tab
# and only audio streams for Audio tab.

def filter_formats(formats):
    """
    Filters and categorizes formats into combined (video+audio) and audio-only.
    """
    combined_formats = []
    audio_only_formats = []
    seen_resolutions = set()

    for f in formats:
        # Skip DASH/HLS/fragmented formats usually not supported by direct download link
        if f.get('protocol') in ('https', 'http', None) and f.get('url'):
            
            # 1. Combined Video + Audio Streams (For MP4 Tab)
            # Check for both video and audio components and specific extensions
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4':
                res = f.get('height') or f.get('format_note')
                # Use height for resolution grouping
                if res and res not in seen_resolutions:
                    combined_formats.append({
                        "resolution": f"{res}p",
                        "ext": f.get('ext'),
                        "filesize": f.get('filesize') or f.get('filesize_approx'),
                        "url": f['url'],
                        "format_id": f['format_id']
                    })
                    seen_resolutions.add(res)
            
            # 2. Audio-Only Streams (For Audio Tab)
            # Check for audio only (vcodec is 'none') and common audio formats
            elif f.get('vcodec') == 'none' and f.get('acodec') != 'none' and f.get('ext') in ('m4a', 'mp4'):
                # Prioritize itag 140 (M4A) and 251 (Opus) but keep M4A (mp4) for compatibility
                audio_only_formats.append({
                    "quality": f.get('format_note') or f.get('abr') or "Standard",
                    "ext": f.get('ext'),
                    "filesize": f.get('filesize') or f.get('filesize_approx'),
                    "url": f['url'],
                    "format_id": f['format_id']
                })
    
    # Sort combined formats by resolution (ascending)
    combined_formats.sort(key=lambda x: int(x['resolution'].replace('p', '').replace('N/A', '0')) if x['resolution'].replace('p', '').isdigit() else 0)
    
    # Simple deduplication for audio (optional, yt-dlp usually provides best ones)
    unique_audio = {}
    for audio in audio_only_formats:
        key = (audio['ext'], audio['quality'])
        if key not in unique_audio:
            unique_audio[key] = audio
            
    return combined_formats, list(unique_audio.values())


# --- API Endpoint ---

@app.get("/yt/info")
async def get_video_info(url: str):
    """
    Fetches video information and download formats from a YouTube URL.
    """
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True,
        'skip_download': True,
        'force_ipv4': True,
        'cachedir': False,
        'no_warnings': True,
        'simulate': True,
        'outtmpl': '-',
        'forcejson': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            # --- Error Handling for Bot Protection ---
            if info_dict.get('webpage_url_basename') == 'confirm':
                raise HTTPException(
                    status_code=403, 
                    detail="YouTube blocked this video for automated access. Try another video."
                )

            # Extract basic info
            title = info_dict.get('title')
            description = info_dict.get('description')
            duration = info_dict.get('duration')
            views = info_dict.get('view_count')
            thumbnails = info_dict.get('thumbnails', [])
            
            # Process formats using the custom filter
            formats = info_dict.get('formats', [])
            combined_video_formats, audio_only_formats = filter_formats(formats)
            
            # Filter and prepare thumbnails
            processed_thumbnails = sorted([
                {"url": t['url'], "resolution": f"{t.get('width')}x{t.get('height')}"}
                for t in thumbnails if t.get('url')
            ], key=lambda x: int(x['resolution'].split('x')[0]), reverse=True)


            return {
                "title": title,
                "description": description,
                "duration": format_duration(duration), # Formatted string
                "views": format_views(views),       # Formatted string
                "thumbnails": processed_thumbnails,
                "video_formats": combined_video_formats,
                "audio_formats": audio_only_formats,
                "source": "yt-dlp", # For debugging/tracking
            }

    except yt_dlp.utils.DownloadError as e:
        # Catch network/connection errors and specific yt-dlp errors
        error_message = str(e)
        if "confirm you're not a bot" in error_message or "Private video" in error_message:
            raise HTTPException(
                status_code=403, 
                detail="YouTube blocked this video for automated access (or it's private). Try another video."
            )
        elif "Unsupported URL" in error_message:
             raise HTTPException(
                status_code=400, 
                detail="Unsupported URL or video not found."
            )
        raise HTTPException(status_code=500, detail=f"Internal Downloader Error: {error_message}")
        
    except Exception as e:
        print(f"General Error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


# --- Health Check Endpoint (For Render Deployment) ---
@app.get("/")
def read_root():
    return {"status": "ok", "service": "Video Downloader Backend"}

# To run the app: uvicorn main:app --host 0.0.0.0from
