import google.generativeai as genai
import os
from dotenv import load_dotenv
from app.services.mood_service import GEMINI_AUDIO_PROMPT

load_dotenv("c:/Users/Cemil/Desktop/emotuneai/backend/.env")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash-lite")

audio_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"

try:
    response = model.generate_content([
        {"mime_type": "audio/webm", "data": audio_bytes},
        GEMINI_AUDIO_PROMPT
    ])
    print("RESPONSE TEXT:", response.text)
except Exception as e:
    print("FAILED:", e)
