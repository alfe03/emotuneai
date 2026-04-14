from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, mood, music, history

app = FastAPI(
    title="EmoTuneAI API",
    description="AI-powered mood-based music recommendation system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da Flutter app URL'ini gir
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router,    prefix="/api/auth",    tags=["Authentication"])
app.include_router(mood.router,    prefix="/api/mood",    tags=["Mood Detection"])
app.include_router(music.router,   prefix="/api/music",   tags=["Music Recommendation"])
app.include_router(history.router, prefix="/api/history", tags=["History"])

@app.get("/")
def root():
    return {"message": "EmoTuneAI API is running 🎵"}
