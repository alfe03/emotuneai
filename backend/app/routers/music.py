from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.models import User, RecommendedTrack, LikedTrack, MoodHistory

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

    else:
        raise HTTPException(status_code=400, detail=f"Geçersiz action: '{request.action}'. 'like' veya 'dislike' olmalı.")

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


class ExportPlaylistRequest(BaseModel):
    mood_history_id: int
    playlist_name: str


@router.post("/export-playlist")
def export_playlist(
    request: ExportPlaylistRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ruh hali geçmişindeki şarkıları kullanıcının Spotify hesabına playlist olarak kaydeder."""
    mood_entry = db.query(MoodHistory).filter(
        MoodHistory.id == request.mood_history_id,
        MoodHistory.user_id == current_user.id
    ).first()

    if not mood_entry:
        raise HTTPException(status_code=404, detail="Ruh hali geçmiş kaydı bulunamadı.")

    track_ids = [t.spotify_id for t in mood_entry.tracks]
    if not track_ids:
        raise HTTPException(status_code=400, detail="Aktarılacak şarkı bulunamadı.")

    from app.services.spotify_service import get_user_spotify_client
    try:
        sp = get_user_spotify_client(current_user, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spotify bağlantısı kurulurken hata oluştu: {e}")

    try:
        sp_user = sp.current_user()
        spotify_user_id = sp_user["id"]

        playlist = sp.user_playlist_create(
            user=spotify_user_id,
            name=request.playlist_name,
            public=False,
            description=f"EmoTuneAI tarafından '{mood_entry.emotion}' ruh hali için oluşturuldu. 🎵"
        )

        track_uris = [f"spotify:track:{tid}" for tid in track_ids]
        sp.playlist_add_items(playlist_id=playlist["id"], items=track_uris)

        return {
            "message": "Çalma listesi Spotify hesabınıza başarıyla aktarıldı.",
            "playlist_id": playlist["id"],
            "playlist_url": playlist["external_urls"]["spotify"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Çalma listesi oluşturulurken hata oluştu: {str(e)}")