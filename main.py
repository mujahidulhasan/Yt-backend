# main.py (Updated for Bot Detection Avoidance)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import os
import subprocess
from starlette.background import BackgroundTask # ফাইল ডিলিট করার জন্য
import re

# --- Constants & Configuration ---
# কুকিজ ফাইলটি আপনার Render সার্ভারের রুটে বা একই ফোল্ডারে থাকতে হবে।
COOKIES_FILE_PATH = "cookies.txt" 

app = FastAPI(
    title="Video Downloader Backend (Anti-Bot)",
    version="1.0.1",
    description="Extracts video information and formats using yt-dlp with enhanced bot-avoidance settings.",
)

# --- CORS Configuration ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Utility Functions (আগের মতোই থাকবে) ---
def format_duration(seconds):
    # ... (আগের কোড) ...
    if seconds is None:
        return "N/A"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def format_views(views):
    # ... (আগের কোড) ...
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

def filter_formats(formats):
    # ... (আগের কোড, যা Combined Video/Audio ফিল্টার করে) ...
    combined_formats = []
    audio_only_formats = []
    seen_resolutions = set()

    for f in formats:
        if f.get('protocol') in ('https', 'http', None) and f.get('url'):
            
            # 1. Combined Video + Audio Streams (For MP4 Tab)
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4':
                res = f.get('height') or f.get('format_note')
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
            elif f.get('vcodec') == 'none' and f.get('acodec') != 'none' and f.get('ext') in ('m4a', 'mp4'):
                audio_only_formats.append({
                    "quality": f.get('format_note') or f.get('abr') or "Standard",
                    "ext": f.get('ext'),
                    "filesize": f.get('filesize') or f.get('filesize_approx'),
                    "url": f['url'],
                    "format_id": f['format_id']
                })
    
    combined_formats.sort(key=lambda x: int(x['resolution'].replace('p', '').replace('N/A', '0')) if x['resolution'].replace('p', '').isdigit() else 0)
    
    unique_audio = {}
    for audio in audio_only_formats:
        key = (audio['ext'], audio['quality'])
        if key not in unique_audio:
            unique_audio[key] = audio
            
    return combined_formats, list(unique_audio.values())


# --- API Endpoint for Info Extraction (/yt/info) ---

@app.get("/yt/info")
async def get_video_info(url: str):
    """
    Fetches video information and download formats from a YouTube URL.
    """
    # 🔴 CORE FIX: yt-dlp অপশনে User-Agent এবং কুকিজ যুক্ত করা হলো
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
        # 🟢 FIX 1: মানুষের ব্রাউজারের User-Agent যুক্ত করা
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    # 🟢 FIX 2: যদি কুকিজ ফাইল পাওয়া যায়, তবে তা yt-dlp-তে যুক্ত করা
    if os.path.exists(COOKIES_FILE_PATH):
        ydl_opts['cookiefile'] = COOKIES_FILE_PATH
        print("Using cookies for enhanced access.")
    else:
        print("Cookies file not found. Running without cookies.")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            # --- Error Handling for Bot Protection ---
            if info_dict.get('webpage_url_basename') == 'confirm' or info_dict.get('title') is None:
                raise HTTPException(
                    status_code=403, 
                    detail="YouTube blocked this video for automated access. Try another video."
                )

            # ... (আগের ডেটা নিষ্কাশন লজিক) ...
            title = info_dict.get('title')
            description = info_dict.get('description')
            duration = info_dict.get('duration')
            views = info_dict.get('view_count')
            thumbnails = info_dict.get('thumbnails', [])
            
            formats = info_dict.get('formats', [])
            combined_video_formats, audio_only_formats = filter_formats(formats)
            
            processed_thumbnails = sorted([
                {"url": t['url'], "resolution": f"{t.get('width')}x{t.get('height')}"}
                for t in thumbnails if t.get('url')
            ], key=lambda x: int(x['resolution'].split('x')[0]) if 'x' in x['resolution'] else 0, reverse=True)


            return {
                "title": title,
                "description": description,
                "duration": format_duration(duration), 
                "views": format_views(views),       
                "thumbnails": processed_thumbnails,
                "video_formats": combined_video_formats,
                "audio_formats": audio_only_formats,
                "source": "yt-dlp",
            }

    except yt_dlp.utils.DownloadError as e:
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


# --- Health Check Endpoint ---
@app.get("/")
def read_root():
    return {"status": "ok", "service": "Video Downloader Backend"}

# --- File Deletion Background Task (For Merging endpoint if needed later) ---
class DeleteFileBackground(BackgroundTask):
    # ... (আগের কোড) ...
    def __init__(self, path):
        super().__init__(self.delete_file, path)
    
    def delete_file(self, path):
        if os.path.exists(path):
            os.remove(path)
            # print(f"Cleaned up temporary file: {path}") # Render logs এ অতিরিক্ত প্রিন্ট এড়াতে কমেন্ট করা হলো
