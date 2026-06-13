from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.routers import auth, mood, music, history
from app.core.database import engine
from app.models import models
from app.core.limiter import limiter
import os

# Veritabanı tablolarını oluştur (Eğer alembic kullanılmıyorsa)
models.Base.metadata.create_all(bind=engine)

# Otomatik migrasyon: users tablosuna yeni kolonları ekle
from sqlalchemy import text
from sqlalchemy.inspection import inspect
try:
    inspector = inspect(engine)
    if inspector.has_table("users"):
        columns = [col['name'] for col in inspector.get_columns('users')]
        with engine.connect() as conn:
            # PostgreSQL ve SQLite uyumlu ALTER TABLE işlemleri
            trans = conn.begin()
            try:
                modified = False
                if 'spotify_access_token' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN spotify_access_token VARCHAR"))
                    modified = True
                if 'spotify_refresh_token' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN spotify_refresh_token VARCHAR"))
                    modified = True
                if 'spotify_token_expires_at' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN spotify_token_expires_at INTEGER"))
                    modified = True
                if 'avatar_url' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR"))
                    modified = True
                if modified:
                    trans.commit()
                    print("Veritabanı migrasyonu tamamlandı: Yeni kolonlar eklendi.")
                else:
                    trans.rollback()
            except Exception as e:
                trans.rollback()
                print(f"Migrasyon hatası oluştu: {e}")
except Exception as e:
    print(f"Tablo inceleme hatası: {e}")

app = FastAPI(
    title="EmoTuneAI API",
    description="AI-powered mood-based music recommendation system",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) #type: ignore

# CORS Configuration
from app.core.config import settings
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Create static directory if it doesn't exist
os.makedirs("static/avatars", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(auth.router,    prefix="/api/auth",    tags=["Authentication"])
app.include_router(mood.router,    prefix="/api/mood",    tags=["Mood Detection"])
app.include_router(music.router,   prefix="/api/music",   tags=["Music Recommendation"])
app.include_router(history.router, prefix="/api/history", tags=["History"])

@app.get("/")
def root():
    return {"message": "EmoTuneAI API is running 🎵"}
