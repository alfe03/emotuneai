from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routers import auth, mood, music, history
from app.core.database import engine
from app.models import models

limiter = Limiter(key_func=get_remote_address)

# Veritabanı tablolarını oluştur (Eğer alembic kullanılmıyorsa)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EmoTuneAI API",
    description="AI-powered mood-based music recommendation system",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) #type: ignore

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
