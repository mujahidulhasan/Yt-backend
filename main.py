# main.py (Vidssave Scraping Endpoint)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import json
import re

# ... (আগের সব ইমপোর্ট, CORS কনফিগারেশন, এবং app = FastAPI() ঠিক থাকবে) ...

# 🛑 Vidssave.com এর জন্য নির্দিষ্ট কনফিগারেশন 🛑
VIDSSAVE_API_URL = "https://vidssave.com/api/proxy"
VIDSSAVE_HEADERS = {
    # Node.js কোড থেকে নেওয়া, টার্গেট সার্ভারকে ব্রাউজার হিসেবে দেখানোর জন্য
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json", # API রিকোয়েস্টটি JSON Payload পাঠায়
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://vidssave.com/", 
    "Origin": "https://vidssave.com",
    # অতিরিক্ত Headers যা Node.js উদাহরণে ছিল, বট ডিটেকশন এড়াতে সাহায্য করবে
    "sec-ch-ua": '"Not.A/Brand";v="99", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

@app.post("/scrape/vidssave")
async def scrape_vidssave_info(video_url: str):
    """
    Scrapes download links and info from the Vidssave.com hidden API.
    NOTE: This is unstable as Vidssave can change its API or block the IP.
    """
    
    # POST রিকোয়েস্টে পাঠানোর জন্য ডেটা (Payload)
    # এটি Vidssave এর জন্য প্রয়োজনীয় দুটি প্রধান প্যারামিটার: URL এবং Host
    payload = {
        "url": video_url,
        "host": "youtube.com" # যদিও এটি মাল্টি-প্লাটফর্ম, আমরা YouTube কে টার্গেট করছি
    }

    try:
        # POST রিকোয়েস্ট পাঠানো হচ্ছে (JSON payload সহ)
        response = requests.post(
            VIDSSAVE_API_URL, 
            headers=VIDSSAVE_HEADERS,
            json=payload, # JSON payload পাঠানোর জন্য
            timeout=15
        )
        response.raise_for_status()
        
        # 1. API রেসপন্স ডিকোড করা
        data = response.json()
        
        # Vidssave API থেকে ডেটা এক্সট্র্যাক্ট করা
        video_data = data.get('data')

        if not video_data or not video_data.get('download_links'):
            error_message = video_data.get('msg') if video_data else "Vidssave failed to process the link."
            raise HTTPException(status_code=400, detail=f"Scraping Failed: {error_message}")
        
        # 2. ডেটা পার্সিং
        
        title = video_data.get('title') or "Untitled Video"
        thumbnail_url = video_data.get('thumbnail')
        
        extracted_formats = []
        # download_links এর মধ্যে সাধারণত ভিডিও, অডিও এবং অন্যান্য ফরম্যাট থাকে
        for link in video_data['download_links']:
            quality = link.get('quality') or link.get('type') or "Default"
            
            # শুধুমাত্র Video (mp4) এবং Audio (mp3, m4a) ফরম্যাটগুলো নেওয়া হচ্ছে
            if link.get('ext') in ('mp4', 'mp3', 'm4a'):
                 extracted_formats.append({
                    "resolution": quality,
                    "ext": link.get('ext'),
                    "url": link.get('url'),
                    "filesize": link.get('size') # যদি API সাইজ পাঠায়
                })

        # Vidssave এর ডেটা স্ট্রাকচার আপনার ফ্রন্টএন্ডের প্রয়োজন অনুযায়ী ফরম্যাট করা
        video_formats = [f for f in extracted_formats if f['ext'] == 'mp4']
        audio_formats = [f for f in extracted_formats if f['ext'] in ('mp3', 'm4a')]

        # 3. ফ্রন্টএন্ডের জন্য পরিষ্কার JSON ডেটা রিটার্ন করা
        return {
            "title": title,
            "thumbnails": [{"url": thumbnail_url, "resolution": "HQ"}] if thumbnail_url else [],
            "video_formats": video_formats,
            "audio_formats": audio_formats,
            # যেহেতু Vidssave প্রায়শই কম্বাইন্ড স্ট্রিম দেয়, তাই এখানে শব্দ থাকার সম্ভাবনা বেশি
            "source": "scraped_vidssave", 
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Scraping Failed: Connection error or Vidssave blocked the IP. {str(e)}")
    except Exception as e:
        print(f"Scraping Logic Error: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping Logic Error: An internal error occurred.")

# --- (আগের /yt/info এবং / এন্ডপয়েন্টগুলি ঠিক থাকবে) ---
