from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String, unique=True, index=True, nullable=False)
    username   = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    spotify_access_token = Column(String, nullable=True)
    spotify_refresh_token = Column(String, nullable=True)
    spotify_token_expires_at = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    mood_history = relationship("MoodHistory", back_populates="user", cascade="all, delete-orphan")

    @property
    def spotify_connected(self) -> bool:
        return self.spotify_refresh_token is not None


class MoodHistory(Base):
    __tablename__ = "mood_history"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    emotion       = Column(String, nullable=False)     # happy, sad, angry...
    mood_category = Column(String, nullable=False)     # energetic, calm, intense, chill
    confidence    = Column(Float, default=0.0)
    source        = Column(String, nullable=False)     # "face" | "text" | "manual"
    input_text    = Column(Text, nullable=True)        # Metin analizi için
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    user   = relationship("User", back_populates="mood_history")
    tracks = relationship("RecommendedTrack", back_populates="mood_entry", cascade="all, delete-orphan")


class RecommendedTrack(Base):
    __tablename__ = "recommended_tracks"

    id             = Column(Integer, primary_key=True, index=True)
    mood_history_id = Column(Integer, ForeignKey("mood_history.id"), nullable=False)
    spotify_id     = Column(String, nullable=False)
    track_name     = Column(String, nullable=False)
    artist_name    = Column(String, nullable=False)
    album_name     = Column(String, nullable=True)
    image_url      = Column(String, nullable=True)
    spotify_url    = Column(String, nullable=True)
    is_liked       = Column(Integer, default=0)     # 0: nötr, 1: beğendi, -1: beğenmedi
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    mood_entry = relationship("MoodHistory", back_populates="tracks")


class LikedTrack(Base):
    __tablename__ = "liked_tracks"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    spotify_id     = Column(String, nullable=False)
    track_name     = Column(String, nullable=False)
    artist_name    = Column(String, nullable=False)
    album_name     = Column(String, nullable=True)
    image_url      = Column(String, nullable=True)
    spotify_url    = Column(String, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="liked_tracks")
