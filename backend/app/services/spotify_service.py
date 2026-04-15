import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from app.core.config import settings
from app.services.mood_service import get_mood_features
import random

# Spotify client
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET
    )
)

# Mood'a göre seed genre'lar
MOOD_GENRES = {
    "energetic": ["pop", "dance", "electronic", "hip-hop"],
    "calm":      ["acoustic", "ambient", "classical", "piano"],
    "intense":   ["metal", "rock", "hardcore", "punk"],
    "chill":     ["indie", "lo-fi", "jazz", "soul"],
}


def get_recommendations(mood_category: str, limit: int = 10) -> list:
    """
    Mood kategorisine göre Spotify'dan müzik önerileri getirir.
    Döndürür: [ { id, name, artist, album, preview_url, image_url, spotify_url } ]
    """
    features = get_mood_features(mood_category)
    genres = MOOD_GENRES.get(mood_category, ["pop"])
    seed_genres = random.sample(genres, min(2, len(genres)))  # max 5 seed

    try:
        results = sp.recommendations(
            seed_genres=seed_genres,
            limit=limit,
            **features
        )

        tracks = []
        for track in results["tracks"]:
            tracks.append({
                "id":          track["id"],
                "name":        track["name"],
                "artist":      track["artists"][0]["name"],
                "album":       track["album"]["name"],
                "preview_url": track.get("preview_url"),
                "image_url":   track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                "spotify_url": track["external_urls"]["spotify"],
                "duration_ms": track["duration_ms"],
            })

        return tracks

    except Exception as e:
        raise ValueError(f"Spotify öneri hatası: {str(e)}")


def create_playlist(mood_category: str, user_id: str, track_ids: list) -> dict:
    """
    Kullanıcı için Spotify'da playlist oluşturur.
    Not: Bu fonksiyon için kullanıcı OAuth token'ı gerekir.
    """
    playlist_names = {
        "energetic": "⚡ EmoTune – Energy Boost",
        "calm":      "🌊 EmoTune – Calm Vibes",
        "intense":   "🔥 EmoTune – Intense Mode",
        "chill":     "😌 EmoTune – Chill Session",
    }

    # TODO: Kullanıcı OAuth flow eklenecek
    # Bu özellik ileriki aşamada implement edilecek
    return {"message": "Playlist creation coming soon", "mood": mood_category}
