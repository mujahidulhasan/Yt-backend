YouTube Backend (for Render)

This is a simple FastAPI + yt-dlp backend that exposes:

  GET /yt/info?url=YOUTUBE_VIDEO_URL

It returns JSON with:
- title
- duration (seconds)
- thumbnail
- formats: progressive video+audio streams
- audios: audio-only streams

Deploy steps (Render.com):

1. Create a new GitHub repo with the contents of the `backend` folder.
2. On Render, create a new Web Service:
   - Environment: Python
   - Build Command:    pip install -r requirements.txt
   - Start Command:    uvicorn main:app --host 0.0.0.0 --port 10000
3. After deploy, note the base URL, e.g.:
   https://your-app.onrender.com
4. In the frontend Sidebar → "YouTube Backend URL", enter:
   https://your-app.onrender.com/yt/info
