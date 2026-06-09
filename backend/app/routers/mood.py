from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.services.mood_service import analyze_face, analyze_text, analyze_video
from app.services.spotify_service import get_recommendations
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.models.models import User, MoodHistory, RecommendedTrack
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _save_mood_and_tracks(
    db: Session, user_id: int, emotion: str, mood_category: str,
    confidence: float, source: str, tracks: list, input_text: str | None = None
) -> None:
    """Mood geçmişi ve önerilen şarkıları veritabanına kaydeder."""
    try:
        db_history = MoodHistory(
            user_id=user_id,
            emotion=emotion,
            mood_category=mood_category,
            confidence=confidence,
            source=source,
            input_text=input_text
        )
        db.add(db_history)
        db.commit()
        db.refresh(db_history)

        for track in tracks:
            db_track = RecommendedTrack(
                mood_history_id=db_history.id,
                spotify_id=track["id"],
                track_name=track["name"],
                artist_name=track["artist"],
                album_name=track.get("album") or "",
                image_url=track.get("image_url") or "",
                spotify_url=track.get("spotify_url") or "",
                is_liked=0
            )
            db.add(db_track)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"DB kaydetme hatası ({source}): {e}")


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
    requested_artist: Optional[str] = None


class VideoAnalysisRequest(BaseModel):
    video_base64: str                # Base64 WebM video
    language: str = "mixed"
    content_type: str = "track"
    search_query: Optional[str] = ""
    genre: Optional[str] = ""

class MoodResponse(BaseModel):
    emotion: str
    confidence: float
    mood_category: str
    recommendations: list
    explanation: Optional[str] = None
    input_text: Optional[str] = None
    source: Optional[str] = None
    requested_artist: Optional[str] = None



# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze/face", response_model=MoodResponse)
async def analyze_face_endpoint(
    request: FaceAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
        
        _save_mood_and_tracks(
            db, current_user.id, mood_result["emotion"],
            mood_result["mood_category"], mood_result["confidence"],
            "face", tracks
        )

        return {**mood_result, "recommendations": tracks, "source": "face"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Yüz analizi endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail="Yüz analizi sırasında beklenmeyen bir hata oluştu.")


@router.post("/analyze/text", response_model=MoodResponse)
async def analyze_text_endpoint(
    request: TextAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının yazdığı metni analiz eder ve müzik önerir."""
    if len(request.text.strip()) < 3:
        raise HTTPException(status_code=400, detail="Lütfen daha uzun bir metin girin.")
    try:
        mood_result = analyze_text(request.text)
        requested_artist = mood_result.get("requested_artist")
        tracks = get_recommendations(
            mood_result["mood_category"],
            language=request.language,
            content_type=request.content_type,
            search_query=request.search_query or "",
            genre=request.genre or "",
            requested_artist=requested_artist
        )

        _save_mood_and_tracks(
            db, current_user.id, mood_result["emotion"],
            mood_result["mood_category"], mood_result["confidence"],
            "text", tracks, input_text=request.text
        )

        return {**mood_result, "recommendations": tracks, "source": "text"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Metin analizi endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail="Metin analizi sırasında beklenmeyen bir hata oluştu.")


@router.post("/manual", response_model=MoodResponse)
async def manual_mood_endpoint(
    request: ManualMoodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının manuel seçtiği mood'a göre müzik önerir."""
    from app.services.mood_service import EMOTION_TO_MOOD
    mood_category = EMOTION_TO_MOOD.get(request.mood.lower(), "chill")
    tracks = get_recommendations(
        mood_category,
        language=request.language,
        content_type=request.content_type,
        search_query=request.search_query or "",
        genre=request.genre or "",
        requested_artist=request.requested_artist
    )

    _save_mood_and_tracks(
        db, current_user.id, request.mood,
        mood_category, 100.0, "manual", tracks
    )

    return {
        "emotion": request.mood,
        "confidence": 100.0,
        "mood_category": mood_category,
        "recommendations": tracks,
        "source": "manual",
        "requested_artist": request.requested_artist
    }


@router.post("/analyze/video", response_model=MoodResponse)
async def analyze_video_endpoint(
    request: VideoAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının kaydettiği videoyu analiz eder ve müzik önerir."""
    try:
        import base64
        video_bytes = base64.b64decode(request.video_base64)
        
        mood_result = analyze_video(video_bytes)
        from app.services.mood_service import _extract_artist_fallback
        requested_artist = _extract_artist_fallback(mood_result.get("input_text", ""))
        mood_result["requested_artist"] = requested_artist
        
        tracks = get_recommendations(
            mood_result["mood_category"],
            language=request.language,
            content_type=request.content_type,
            search_query=request.search_query or "",
            genre=request.genre or "",
            requested_artist=requested_artist
        )
        
        _save_mood_and_tracks(
            db, current_user.id, mood_result["emotion"],
            mood_result["mood_category"], mood_result["confidence"],
            "video", tracks, input_text=mood_result.get("input_text")
        )
        
        return {**mood_result, "recommendations": tracks, "source": "video"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Video analizi endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail="Video analizi sırasında beklenmeyen bir hata oluştu.")

