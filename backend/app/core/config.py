from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    APP_NAME: str = "EmoTuneAI"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-in-production"

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/emotune"

    # Spotify API
    # → https://developer.spotify.com/dashboard adresinden alınır
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    SPOTIFY_REDIRECT_URI: str = "http://127.0.0.1:8000/api/auth/spotify/callback"

    # Frontend
    FRONTEND_URL: str = "http://127.0.0.1:8080/index.html"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 gün

    class Config:
        env_file = ".env"

settings = Settings()
