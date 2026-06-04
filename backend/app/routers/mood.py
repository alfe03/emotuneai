from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.services.mood_service import analyze_face, analyze_text, analyze_video
from app.services.spotify_service import get_recommendations
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.models.models import User, MoodHistory, RecommendedTrack

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
        
        # Save to database
        db_history = MoodHistory(
            user_id=current_user.id,
            emotion=mood_result["emotion"],
            mood_category=mood_result["mood_category"],
            confidence=mood_result["confidence"],
            source="face",
            input_text=None
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

        return {**mood_result, "recommendations": tracks, "source": "face"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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

        # Save to database
        db_history = MoodHistory(
            user_id=current_user.id,
            emotion=mood_result["emotion"],
            mood_category=mood_result["mood_category"],
            confidence=mood_result["confidence"],
            source="text",
            input_text=request.text
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

        return {**mood_result, "recommendations": tracks, "source": "text"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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

    # Save to database
    db_history = MoodHistory(
        user_id=current_user.id,
        emotion=request.mood,
        mood_category=mood_category,
        confidence=100.0,
        source="manual",
        input_text=None
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
        
        # Save to database
        db_history = MoodHistory(
            user_id=current_user.id,
            emotion=mood_result["emotion"],
            mood_category=mood_result["mood_category"],
            confidence=mood_result["confidence"],
            source="video",
            input_text=mood_result.get("input_text") or None
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
        
        return {**mood_result, "recommendations": tracks, "source": "video"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

