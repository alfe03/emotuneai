from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    APP_NAME: str = "EmoTuneAI"
    DEBUG: bool = False  # DO NOT use True in production
    SECRET_KEY: str = "your-super-secret-key-change-it"

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@db:5432/emotune"  # Use environment variable in production


    # Spotify API
    # → https://developer.spotify.com/dashboard adresinden alınır
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    SPOTIFY_REDIRECT_URI: str = "http://127.0.0.1:8000/api/auth/spotify/callback"

    # Frontend
    FRONTEND_URL: str = "http://127.0.0.1:8080/index.html"

    # CORS Origins (virgülle ayrılmış)
    CORS_ORIGINS: str = "http://127.0.0.1:8080,http://localhost:8080"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 gün

    # Gemini AI
    GEMINI_API_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
