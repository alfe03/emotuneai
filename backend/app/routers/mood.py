from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.services.mood_service import analyze_face, analyze_text
from app.services.spotify_service import get_recommendations
from app.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()


# ── Request / Response Modelleri ──────────────────────────────────────────────

class FaceAnalysisRequest(BaseModel):
    image_base64: str
    language: str = "mixed"          # "tr" | "en" | "mixed"
    content_type: str = "track"      # "track" | "playlist" | "podcast"
    search_query: Optional[str] = ""
    genre: Optional[str] = ""

class TextAnalysisRequest(BaseModel):
    text: str
    language: str = "mixed"
    content_type: str = "track"
    search_query: Optional[str] = ""
    genre: Optional[str] = ""

class ManualMoodRequest(BaseModel):
    mood: str                        # "happy" | "sad" | "angry" | "neutral" | "surprise"
    language: str = "mixed"
    content_type: str = "track"
    search_query: Optional[str] = ""
    genre: Optional[str] = ""

class MoodResponse(BaseModel):
    emotion: str
    confidence: float
    mood_category: str
    recommendations: list


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze/face", response_model=MoodResponse)
async def analyze_face_endpoint(request: FaceAnalysisRequest):
    """Fotoğraftaki yüz ifadesini analiz eder ve müzik önerir."""
    try:
        mood_result = analyze_face(request.image_base64)
        tracks = get_recommendations(
            mood_result["mood_category"],
            language=request.language,
            content_type=request.content_type,
            search_query=request.search_query or "",
            genre=request.genre or ""
        )
        return {**mood_result, "recommendations": tracks}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analyze/text", response_model=MoodResponse)
async def analyze_text_endpoint(request: TextAnalysisRequest):
    """Kullanıcının yazdığı metni analiz eder ve müzik önerir."""
    if len(request.text.strip()) < 3:
        raise HTTPException(status_code=400, detail="Lütfen daha uzun bir metin girin.")
    try:
        mood_result = analyze_text(request.text)
        tracks = get_recommendations(
            mood_result["mood_category"],
            language=request.language,
            content_type=request.content_type,
            search_query=request.search_query or "",
            genre=request.genre or ""
        )
        return {**mood_result, "recommendations": tracks}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/manual", response_model=MoodResponse)
async def manual_mood_endpoint(request: ManualMoodRequest):
    """Kullanıcının manuel seçtiği mood'a göre müzik önerir."""
    from app.services.mood_service import EMOTION_TO_MOOD
    mood_category = EMOTION_TO_MOOD.get(request.mood.lower(), "chill")
    tracks = get_recommendations(
        mood_category,
        language=request.language,
        content_type=request.content_type,
            search_query=request.search_query or "",
            genre=request.genre or ""
    )
    return {
        "emotion": request.mood,
        "confidence": 100.0,
        "mood_category": mood_category,
        "recommendations": tracks
    }
