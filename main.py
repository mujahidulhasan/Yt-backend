# main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import json
import re

# --- FastAPI অ্যাপ্লিকেশন ইনস্ট্যান্স তৈরি (ত্রুটি সমাধান: NameError) ---
app = FastAPI(
    title="Video Downloader Backend (Scraping)",
    version="1.0.3",
    description="Backend service using Vidssave scraping to bypass bot detection."
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

# 🛑 Vidssave.com এর জন্য নির্দিষ্ট কনফিগারেশন 🛑
VIDSSAVE_API_URL = "https://vidssave.com/api/proxy"
VIDSSAVE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://vidssave.com/",
    "Origin": "https://vidssave.com",
    "sec-ch-ua": '"Not.A/Brand";v="99", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


# --- Health Check Endpoint ---
@app.get("/")
def read_root():
    return {"status": "ok", "service": "Backend is running"}


# --- Vidssave Scraping Endpoint ---
@app.post("/scrape/vidssave")
async def scrape_vidssave_info(video_url: str):
    """
    Scrapes download links and info from the Vidssave.com hidden API.
    """

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

        if not video_data or not video_data.get('download_links'):
            error_message = video_data.get('msg') if video_data else "Vidssave failed to process the link."
            raise HTTPException(status_code=400, detail=f"Scraping Failed: {error_message}")

        title = video_data.get('title') or "Untitled Video"
        thumbnail_url = video_data.get('thumbnail')

        extracted_formats = []
        for link in video_data['download_links']:
            quality = link.get('quality') or link.get('type') or "Default"

            # শুধুমাত্র প্রয়োজনীয় ফরম্যাটগুলো নেওয়া হচ্ছে
            if link.get('ext') in ('mp4', 'mp3', 'm4a', 'webm'):
                extracted_formats.append({
                    "resolution": quality,
                    "ext": link.get('ext'),
                    "url": link.get('url'),
                    "filesize": link.get('size')
                })

        video_formats = [f for f in extracted_formats if f['ext'] in ('mp4', 'webm')]
        audio_formats = [f for f in extracted_formats if f['ext'] in ('mp3', 'm4a')]

        return {
            "title": title,
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


# --- পুরনো /yt/info এন্ডপয়েন্ট (ঐচ্ছিক, যদি আপনি এটি রাখেন) ---
# [এখানে আপনার পুরোনো /yt/info কোড থাকতে পারে]
# ...
