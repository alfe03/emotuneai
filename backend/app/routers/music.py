from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.models import User, RecommendedTrack, LikedTrack

router = APIRouter()

class LikeRequest(BaseModel):
    spotify_id: str
    track_name: str
    artist_name: str
    album_name: str = ""
    image_url: str = ""
    spotify_url: str = ""
    action: str    # "like" | "dislike"

@router.post("/like")
def like_track(
    request: LikeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Şarkıyı beğen veya favorilerden çıkar."""
    existing_like = db.query(LikedTrack).filter(
        LikedTrack.user_id == current_user.id,
        LikedTrack.spotify_id == request.spotify_id
    ).first()

    if request.action == "like":
        if not existing_like:
            new_like = LikedTrack(
                user_id=current_user.id,
                spotify_id=request.spotify_id,
                track_name=request.track_name,
                artist_name=request.artist_name,
                album_name=request.album_name,
                image_url=request.image_url,
                spotify_url=request.spotify_url
            )
            db.add(new_like)
            db.commit()
            return {"message": "Şarkı beğenilenlere eklendi."}
        return {"message": "Şarkı zaten beğenilmiş."}
        
    elif request.action == "dislike":
        if existing_like:
            db.delete(existing_like)
            db.commit()
            return {"message": "Şarkı beğenilenlerden çıkarıldı."}
        return {"message": "Şarkı zaten favorilerde yok."}

@router.get("/liked")
def get_liked_tracks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının beğendiği şarkıları getirir."""
    tracks = (
        db.query(LikedTrack)
        .filter(LikedTrack.user_id == current_user.id)
        .order_by(LikedTrack.created_at.desc())
        .all()
    )

    return [
        {
            "id": t.spotify_id,
            "track_name": t.track_name,
            "artist_name": t.artist_name,
            "album_name": t.album_name,
            "image_url": t.image_url,
            "spotify_url": t.spotify_url,
        }
        for t in tracks
    ]