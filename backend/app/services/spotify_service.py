# -*- coding: utf-8 -*-
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from app.core.config import settings
import random

# Spotify client
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET
    )
)

# ── Mood → Arama sorguları (dil bazlı) ───────────────────────────────────────

MOOD_QUERIES = {
    "tr": {
        "energetic": [
            "türkçe pop enerjik", "türkçe dans", "turkish party hits",
            "türkçe hit şarkılar", "turkish pop workout", "türkçe neşeli"
        ],
        "calm": [
            "türkçe slow", "türkçe hüzünlü", "turkish acoustic",
            "türkçe sakin", "türkçe piyano", "turkish ballad"
        ],
        "intense": [
            "türkçe rock", "turkish metal", "anadolu rock",
            "türkçe rap agresif", "turkish hard rock", "türkçe punk"
        ],
        "chill": [
            "türkçe indie", "türkçe chill", "turkish lofi",
            "türkçe akustik", "türkçe cafe", "turkish jazz vocal"
        ],
        "melancholic": [
            "türkçe hüzünlü", "türkçe damar", "turkish sad",
            "türkçe ağlatan şarkılar", "türkçe duygusal", "turkish heartbreak"
        ],
    },
    "en": {
        "energetic": [
            "happy hits", "energy boost", "workout motivation",
            "feel good pop", "dance party", "upbeat vibes"
        ],
        "calm": [
            "calm acoustic", "peaceful piano", "relaxing ambient",
            "soft classical", "gentle sleep", "meditation calm"
        ],
        "intense": [
            "intense rock", "metal energy", "aggressive workout",
            "hard rock anthems", "punk power", "rage metal"
        ],
        "chill": [
            "chill vibes", "lofi chill", "indie chill",
            "jazz coffee", "chill soul", "mellow evening"
        ],
        "melancholic": [
            "sad songs", "heartbreak playlist", "crying in the rain",
            "depressing songs", "melancholy vibes", "sad acoustic"
        ],
    },
    "mixed": {
        "energetic": [
            "happy hits", "türkçe pop enerjik", "global top hits",
            "dance party", "türkçe dans", "feel good pop"
        ],
        "calm": [
            "calm acoustic", "türkçe slow", "peaceful piano",
            "türkçe sakin", "soft classical", "turkish ballad"
        ],
        "intense": [
            "intense rock", "türkçe rock", "metal energy",
            "anadolu rock", "hard rock anthems", "türkçe rap agresif"
        ],
        "chill": [
            "chill vibes", "türkçe indie", "lofi chill",
            "türkçe chill", "jazz coffee", "türkçe akustik"
        ],
        "melancholic": [
            "sad songs", "türkçe hüzünlü", "heartbreak playlist",
            "türkçe ağlatan şarkılar", "melancholy vibes", "türkçe damar"
        ],
    },
}

# Podcast sorguları
MOOD_PODCAST_QUERIES = {
    "tr": {
        "energetic": ["motivasyon podcast türkçe", "enerji podcast", "türkçe spor podcast"],
        "calm":      ["meditasyon podcast türkçe", "rahatlatıcı podcast", "uyku podcast türkçe"],
        "intense":   ["türkçe tartışma podcast", "haber analiz podcast", "türkçe bilim podcast"],
        "chill":     ["türkçe sohbet podcast", "kitap podcast türkçe", "günlük podcast"],
        "melancholic": ["hüzünlü podcast", "ayrılık podcast", "duygusal sohbet"],
    },
    "en": {
        "energetic": ["motivation podcast", "energy podcast", "fitness podcast"],
        "calm":      ["meditation podcast", "calm sleep podcast", "mindfulness podcast"],
        "intense":   ["true crime podcast", "debate podcast", "investigative podcast"],
        "chill":     ["comedy podcast", "storytelling podcast", "daily chill podcast"],
        "melancholic": ["sad podcast", "heartbreak podcast", "grief podcast"],
    },
    "mixed": {
        "energetic": ["motivation podcast", "motivasyon podcast türkçe", "energy podcast"],
        "calm":      ["meditation podcast", "meditasyon podcast türkçe", "calm podcast"],
        "intense":   ["true crime podcast", "türkçe tartışma podcast", "debate podcast"],
        "chill":     ["comedy podcast", "türkçe sohbet podcast", "storytelling podcast"],
        "melancholic": ["sad podcast", "ayrılık podcast", "heartbreak podcast", "hüzünlü podcast"],
    },
}

LANG_MARKET = {
    "tr": "TR",
    "en": "US",
    "mixed": None,
}


# ═════════════════════════════════════════════════════════════════════════════
#  ANA FONKSİYON
# ═════════════════════════════════════════════════════════════════════════════

def get_recommendations(mood_category: str, language: str = "mixed",
                        content_type: str = "track", search_query: str = "", genre: str = "", limit: int = 10) -> list:
    """
    Mood + dil + içerik türüne + (opsiyonel) arama kelimesine ve müzik türüne göre Spotify'dan öneriler getirir.
    content_type: "track" | "playlist" | "podcast"
    """
    lang = language.lower() if language else "mixed"
    if lang not in MOOD_QUERIES:
        lang = "mixed"

    if content_type == "playlist":
        return _get_playlists(mood_category, lang, search_query, genre, limit)
    elif content_type == "podcast":
        return _get_podcasts(mood_category, lang, search_query, genre, limit)
    else:
        return _get_tracks(mood_category, lang, search_query, genre, limit)


# ── Şarkı önerileri ──────────────────────────────────────────────────────────

def _get_tracks(mood_category: str, lang: str, search_query: str, genre: str, limit: int) -> list:
    queries = MOOD_QUERIES.get(lang, MOOD_QUERIES["mixed"]).get(mood_category, ["mood"])
    base_query = random.choice(queries)
    
    parts = [base_query]
    if search_query: parts.append(search_query)
    if genre: parts.append(genre)
    query = " ".join(parts)

    market = LANG_MARKET.get(lang)

    try:
        # Playlist'ten şarkı çek
        search_kwargs = {"q": query, "type": "playlist", "limit": 5}
        if market:
            search_kwargs["market"] = market

        playlist_results = sp.search(**search_kwargs)
        playlists = playlist_results.get("playlists", {}).get("items", [])

        if not playlists:
            return _search_tracks_direct(query, limit, market)

        playlist = random.choice(playlists)
        playlist_tracks = sp.playlist_tracks(
            playlist["id"],
            fields="items(track(id,name,artists,album,preview_url,external_urls,duration_ms))",
            limit=50,
            market=market or "TR"
        )

        all_tracks = []
        for item in playlist_tracks.get("items", []):
            track = item.get("track")
            if not track or not track.get("id"):
                continue
            all_tracks.append(_format_track(track))

        if not all_tracks:
            return _search_tracks_direct(query, limit, market)

        random.shuffle(all_tracks)
        return all_tracks[:limit]

    except Exception as e:
        try:
            return _search_tracks_direct(query, limit, market)
        except Exception:
            raise ValueError(f"Spotify öneri hatası: {str(e)}")


def _search_tracks_direct(query: str, limit: int, market: str = None) -> list:
    search_kwargs = {"q": query, "type": "track", "limit": limit}
    if market:
        search_kwargs["market"] = market
    results = sp.search(**search_kwargs)
    tracks = []
    for track in results.get("tracks", {}).get("items", []):
        if track and track.get("id"):
            tracks.append(_format_track(track))
    return tracks


# ── Playlist önerileri ────────────────────────────────────────────────────────

def _get_playlists(mood_category: str, lang: str, search_query: str, genre: str, limit: int) -> list:
    queries = MOOD_QUERIES.get(lang, MOOD_QUERIES["mixed"]).get(mood_category, ["mood"])
    base_query = random.choice(queries)
    
    parts = [base_query]
    if search_query: parts.append(search_query)
    if genre: parts.append(genre)
    query = " ".join(parts)

    market = LANG_MARKET.get(lang)

    try:
        search_kwargs = {"q": query, "type": "playlist", "limit": limit}
        if market:
            search_kwargs["market"] = market

        results = sp.search(**search_kwargs)
        playlists = results.get("playlists", {}).get("items", [])

        return [
            {
                "id":          p["id"],
                "name":        p["name"],
                "artist":      p["owner"]["display_name"] if p.get("owner") else "Spotify",
                "album":       f"{p.get('tracks', {}).get('total', 0)} şarkı",
                "preview_url": None,
                "image_url":   p["images"][0]["url"] if p.get("images") else None,
                "spotify_url": p.get("external_urls", {}).get("spotify", ""),
                "duration_ms": 0,
                "type":        "playlist",
            }
            for p in playlists if p
        ]

    except Exception as e:
        raise ValueError(f"Playlist arama hatası: {str(e)}")


# ── Podcast önerileri ─────────────────────────────────────────────────────────

def _get_podcasts(mood_category: str, lang: str, search_query: str, genre: str, limit: int) -> list:
    queries = MOOD_PODCAST_QUERIES.get(lang, MOOD_PODCAST_QUERIES["mixed"]).get(mood_category, ["podcast"])
    base_query = random.choice(queries)
    
    parts = [base_query]
    if search_query: parts.append(search_query)
    if genre: parts.append(genre)
    query = " ".join(parts)

    market = LANG_MARKET.get(lang) or "TR"

    try:
        results = sp.search(q=query, type="show", limit=limit, market=market)
        shows = results.get("shows", {}).get("items", [])

        return [
            {
                "id":          s["id"],
                "name":        s["name"],
                "artist":      s["publisher"] if s.get("publisher") else "Bilinmiyor",
                "album":       f"{s.get('total_episodes', '?')} bölüm",
                "preview_url": None,
                "image_url":   s["images"][0]["url"] if s.get("images") else None,
                "spotify_url": s.get("external_urls", {}).get("spotify", ""),
                "duration_ms": 0,
                "type":        "podcast",
            }
            for s in shows if s
        ]

    except Exception as e:
        raise ValueError(f"Podcast arama hatası: {str(e)}")


# ── Format helpers ────────────────────────────────────────────────────────────

def _format_track(track: dict) -> dict:
    images = track.get("album", {}).get("images", [])
    return {
        "id":          track["id"],
        "name":        track["name"],
        "artist":      track["artists"][0]["name"] if track.get("artists") else "Bilinmiyor",
        "album":       track.get("album", {}).get("name", ""),
        "preview_url": track.get("preview_url"),
        "image_url":   images[0]["url"] if images else None,
        "spotify_url": track.get("external_urls", {}).get("spotify", ""),
        "duration_ms": track.get("duration_ms", 0),
        "type":        "track",
    }


def create_playlist(mood_category: str, user_id: str, track_ids: list) -> dict:
    """Kullanıcı için Spotify'da playlist oluşturur. (TODO)"""
    playlist_names = {
        "energetic": "⚡ EmoTune – Energy Boost",
        "calm":      "🌊 EmoTune – Calm Vibes",
        "intense":   "🔥 EmoTune – Intense Mode",
        "chill":     "😌 EmoTune – Chill Session",
    }
    return {"message": "Playlist creation coming soon", "mood": mood_category}
