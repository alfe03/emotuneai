from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.models import User, RecommendedTrack

router = APIRouter()


class LikeRequest(BaseModel):
    track_id: int
    action: str    # "like" | "dislike" | "neutral"


@router.post("/like")
def like_track(
    request: LikeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Şarkıyı beğen / beğenme / nötr olarak işaretle."""
    track = db.query(RecommendedTrack).filter(
        RecommendedTrack.id == request.track_id
    ).first()

    if not track:
        raise HTTPException(status_code=404, detail="Şarkı bulunamadı.")
    
    action_map = { "like": 1, "dislike": -1, "neutral": 0 }
    track.is_liked = action_map.get(request.action, 0)
    db.commit()

    return {"message": f"Şarkı {request.action} olarak işaretlendi."}


@router.get("/liked")
def get_liked_tracks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının beğendiği şarkıları getirir."""
    tracks = (
        db.query(RecommendedTrack)
        .join(RecommendedTrack.mood_entry)
        .filter(
            RecommendedTrack.is_liked == 1,
        )
        .order_by(RecommendedTrack.created_at.desc())
        .all()
    )

    return [
        {
            "id": t.id,
            "track_name": t.track_name,
            "artist_name": t.artist_name,
            "album_name": t.album_name,
            "image_url": t.image_url,
            "spotify_url": t.spotify_url,
        }
        for t in tracks
    ]