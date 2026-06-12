from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.services.mood_service import analyze_face, analyze_text, analyze_audio
from app.services.spotify_service import get_recommendations
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.models.models import User, MoodHistory, RecommendedTrack
import logging
import concurrent.futures

logger = logging.getLogger(__name__)

router = APIRouter()


def _save_mood_and_tracks(
    db: Session, user_id: int, emotion: str, mood_category: str,
    confidence: float, source: str, tracks: list, input_text: str | None = None
) -> int | None:
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
        return db_history.id
    except Exception as e:
        db.rollback()
        logger.error(f"DB kaydetme hatası ({source}): {e}")
        return None


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
    no_save: bool = False            # True ise DB'ye kayıt yapılmaz (yenile/filtre değişimi için)




class MoodResponse(BaseModel):
    id: Optional[int] = None
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
def analyze_face_endpoint(
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
        
        history_id = _save_mood_and_tracks(
            db, current_user.id, mood_result["emotion"],  # type: ignore
            mood_result["mood_category"], mood_result["confidence"],
            "face", tracks
        )

        return {**mood_result, "recommendations": tracks, "source": "face", "id": history_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Yüz analizi endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail="Yüz analizi sırasında beklenmeyen bir hata oluştu.")


@router.post("/analyze/text", response_model=MoodResponse)
def analyze_text_endpoint(
    request: TextAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının yazdığı metni analiz eder ve müzik önerir."""
    if len(request.text.strip()) < 3:
        raise HTTPException(status_code=400, detail="Lütfen daha uzun bir metin girin.")
    try:
        # ── Gemini analizi ve Spotify aramasını PARALEL başlat ──────────────────
        # Spotify için önce hızlı bir keyword tahmini yapıyoruz (Gemini bitmeden)
        from app.services.mood_service import _extract_artist_fallback, _fallback_analyze_text, EMOTION_TO_MOOD

        # Hızlı ön-tahmin: keyword tabanlı mood (Gemini beklenmeden Spotify'a başlamak için)
        quick_mood = _fallback_analyze_text(request.text)
        quick_mood_category = quick_mood.get("mood_category", "chill")
        quick_artist = _extract_artist_fallback(request.text)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Gemini analizi (daha derin)
            gemini_future = executor.submit(analyze_text, request.text)
            # Spotify araması hemen başlasın (quick_mood ile)
            spotify_future = executor.submit(
                get_recommendations,
                quick_mood_category,
                request.language,
                request.content_type,
                request.search_query or "",
                request.genre or "",
                10,
                quick_artist
            )

            mood_result = gemini_future.result()   # Gemini sonucu
            requested_artist = mood_result.get("requested_artist") or quick_artist

            # Gemini farklı bir mood kategorisi verdiyse Spotify'ı tekrar çek,
            # aynıysa zaten hazır olan sonucu kullan
            if mood_result["mood_category"] != quick_mood_category or (
                requested_artist and requested_artist != quick_artist
            ):
                tracks = get_recommendations(
                    mood_result["mood_category"],
                    language=request.language,
                    content_type=request.content_type,
                    search_query=request.search_query or "",
                    genre=request.genre or "",
                    requested_artist=requested_artist
                )
            else:
                tracks = spotify_future.result()

        history_id = _save_mood_and_tracks(
            db, current_user.id, mood_result["emotion"],  # type: ignore
            mood_result["mood_category"], mood_result["confidence"],
            "text", tracks, input_text=request.text
        )

        return {**mood_result, "recommendations": tracks, "source": "text", "id": history_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Metin analizi endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail="Metin analizi sırasında beklenmeyen bir hata oluştu.")


@router.post("/manual", response_model=MoodResponse)
def manual_mood_endpoint(
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

    # Yenile/filtre değişiminde DB'ye kaydetme (no_save=True ise atla)
    history_id = None
    if not request.no_save:
        history_id = _save_mood_and_tracks(
            db, current_user.id, request.mood,  # type: ignore
            mood_category, 100.0, "manual", tracks
        )

    return {
        "id": history_id,
        "emotion": request.mood,
        "confidence": 100.0,
        "mood_category": mood_category,
        "recommendations": tracks,
        "source": "manual",
        "requested_artist": request.requested_artist
    }





class AudioAnalysisRequest(BaseModel):
    audio_base64: str                # Base64 WebM/WAV ses verisi
    language: str = "mixed"
    content_type: str = "track"
    search_query: Optional[str] = ""
    genre: Optional[str] = ""


@router.post("/analyze/audio", response_model=MoodResponse)
def analyze_audio_endpoint(
    request: AudioAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının kaydettiği ses kaydını analiz eder ve müzik önerir."""
    try:
        import base64
        audio_bytes = base64.b64decode(request.audio_base64)
        
        mood_result = analyze_audio(audio_bytes)
        requested_artist = mood_result.get("requested_artist")
        
        tracks = get_recommendations(
            mood_result["mood_category"],
            language=request.language,
            content_type=request.content_type,
            search_query=request.search_query or "",
            genre=request.genre or "",
            requested_artist=requested_artist
        )
        
        history_id = _save_mood_and_tracks(
            db, current_user.id, mood_result["emotion"],  # type: ignore
            mood_result["mood_category"], mood_result["confidence"],
            "voice", tracks, input_text=mood_result.get("input_text")
        )
        
        return {**mood_result, "recommendations": tracks, "source": "voice", "id": history_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ses analizi endpoint hatası: {e}")
        raise HTTPException(status_code=500, detail="Ses analizi sırasında beklenmeyen bir hata oluştu.")

