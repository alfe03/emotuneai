from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.models import MoodHistory, RecommendedTrack, User

router = APIRouter()

@router.get("/")
def get_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının mood geçmişini ve önerilen şarkıları getirir."""
    history = (
        db.query(MoodHistory)
        .filter(MoodHistory.user_id == current_user.id)
        .order_by(MoodHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    return history


@router.get("/graph")
def get_mood_graph(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının son 7 gün içindeki mood dağılımını getirir."""
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=days)

    results = (
        db.query(
            MoodHistory.mood_category,
            MoodHistory.created_at
        )
        .filter(
            MoodHistory.user_id == current_user.id,
            MoodHistory.created_at >= since
        )
        .order_by(MoodHistory.created_at.asc())
        .all()
    )

    return [
        {"mood_category": r.mood_category, "date": r.created_at.strftime("%Y-%m-%d")}
        for r in results
    ]


@router.get("/analytics")
def get_mood_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının son X gün içindeki mood analitik verilerini getirir."""
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=days)

    results = (
        db.query(
            MoodHistory.mood_category,
            MoodHistory.emotion,
            MoodHistory.source,
            MoodHistory.confidence,
            MoodHistory.created_at
        )
        .filter(
            MoodHistory.user_id == current_user.id,
            MoodHistory.created_at >= since
        )
        .order_by(MoodHistory.created_at.asc())
        .all()
    )

    return [
        {
            "mood_category": r.mood_category,
            "emotion": r.emotion,
            "source": r.source,
            "confidence": r.confidence,
            "date": r.created_at.strftime("%Y-%m-%d")
        }
        for r in results
    ]


@router.delete("/{history_id}")
def delete_history(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Belirli bir mood geçmişi kaydını siler."""
    entry = db.query(MoodHistory).filter(
        MoodHistory.id == history_id,
        MoodHistory.user_id == current_user.id
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    
    db.delete(entry)
    db.commit()
    return {"message": "Silindi."}