# main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import json
import re
from pydantic import BaseModel # 422 Error Fix: Pydantic BaseModel

# --- 1. Pydantic মডেল (422 ত্রুটি সমাধানের জন্য) ---
class VideoRequest(BaseModel):
    video_url: str

# --- 2. FastAPI অ্যাপ্লিকেশন ইনস্ট্যান্স তৈরি ---
app = FastAPI(
    title="Video Downloader Backend (Scraping)",
    version="1.0.4",
    description="Backend service using Vidssave scraping to bypass bot detection."
)

# --- 3. CORS Configuration ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. Vidssave.com এর জন্য নির্দিষ্ট কনফিগারেশন ---
VIDSSAVE_API_URL = "https://vidssave.com/api/proxy"
VIDSSAVE_HEADERS = {
    # ব্রাউজার হিসেবে দেখানোর জন্য প্রয়োজনীয় Headers
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://vidssave.com/",
    "Origin": "https://vidssave.com",
    "sec-ch-ua": '"Not.A/Brand";v="99", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# --- Utility Function: Duration Formatter (Frontend এ সহায়ক) ---
def format_duration(seconds):
    if seconds is None or seconds == 0:
        return "N/A"
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    except (TypeError, ValueError):
        return "N/A"


# --- 5. Health Check Endpoint ---
@app.get("/")
def read_root():
    return {"status": "ok", "service": "Backend is running"}


# --- 6. Vidssave Scraping Endpoint (FINAL) ---
@app.post("/scrape/vidssave")
async def scrape_vidssave_info(request: VideoRequest):
    """
    Scrapes download links and info from the Vidssave.com hidden API.
    """
    
    video_url = request.video_url

    # POST রিকোয়েস্টে পাঠানোর জন্য ডেটা (Payload)
    payload = {
        "url": video_url,
        "host": "youtube.com"
    }

    try:
        response = requests.post(
            VIDSSAVE_API_URL,
            headers=VIDSSAVE_HEADERS,
            json=payload,
            timeout=15
        )
        response.raise_for_status()

        data = response.json()
        video_data = data.get('data')

        # 'resources' কী চেক করা হচ্ছে
        if not video_data or not video_data.get('resources'):
            error_message = video_data.get('msg') if video_data else "Vidssave failed to process the link."
            raise HTTPException(status_code=400, detail=f"Scraping Failed: {error_message}")

        title = video_data.get('title') or "Untitled Video"
        thumbnail_url = video_data.get('thumbnail')
        duration_seconds = video_data.get('duration') # Duration in seconds

        extracted_formats = []
        # 'resources' এর ওপর লুপ চলছে
        for link in video_data['resources']: 
            quality = link.get('quality') or link.get('format') or link.get('type') or "Default"
            
            # OPUS (Audio) বা অন্য ফরমেটকে ম্যাপ করা
            ext = link.get('format', '').lower()
            if ext == 'opus' or ext == 'webm':
                 ext = 'm4a' # অডিও ট্যাবে দেখানোর জন্য

            if link.get('type') == 'video':
                # ভিডিও ফরমেটের জন্য শুধু MP4/WebM নেব
                if link.get('format', '').lower() in ('mp4', 'webm'):
                    extracted_formats.append({
                        "resolution": quality,
                        "ext": link.get('format', '').lower(),
                        "url": link.get('download_url'), 
                        "filesize": link.get('size')
                    })
            
            elif link.get('type') == 'audio':
                 extracted_formats.append({
                    "resolution": quality,
                    "ext": ext,
                    "url": link.get('download_url'), 
                    "filesize": link.get('size')
                })

        video_formats = [f for f in extracted_formats if f['ext'] in ('mp4', 'webm')]
        audio_formats = [f for f in extracted_formats if f['ext'] in ('mp3', 'm4a')]

        # Final return structure
        return {
            "title": title,
            "duration": format_duration(duration_seconds), # Formatted Duration
            "thumbnails": [{"url": thumbnail_url, "resolution": "HQ"}] if thumbnail_url else [],
            "video_formats": video_formats,
            "audio_formats": audio_formats,
            "source": "scraped_vidssave",
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Scraping Failed: Connection error or Vidssave blocked the IP. {str(e)}")
    except Exception as e:
        print(f"Scraping Logic Error: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping Logic Error: An internal error occurred.")
