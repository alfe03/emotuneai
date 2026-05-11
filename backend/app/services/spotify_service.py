# -*- coding: utf-8 -*-
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from app.core.config import settings
import random
import logging

logger = logging.getLogger(__name__)

# Spotify client
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET
    )
)

# ── Türk Sanatçı Havuzu (tür bazlı) ─────────────────────────────────────────
# Spotify aramasında dil filtresi olmadığı için bilinen sanatçı isimleri kullanıyoruz

TR_ARTISTS = {
    "pop": [
        "Tarkan", "Sezen Aksu", "Hadise", "Murat Boz", "Edis",
        "Aleyna Tilki", "Gülşen", "Sıla", "Serdar Ortaç", "Bengü",
        "İrem Derici", "Simge", "Demet Akalın", "Hande Yener", "Kenan Doğulu",
        "Oğuzhan Koç", "Ebru Gündeş", "Mustafa Sandal", "Emre Aydın",
    ],
    "rap": [
        "Ceza", "Sagopa Kajmer", "Şehinşah", "Ben Fero", "Ezhel",
        "Contra", "Norm Ender", "Khontkar", "Massaka", "Joker",
        "Patron", "Allame", "Sansar Salvo", "Hidra", "Defkhan",
        "UZI", "Motive", "Reckol", "Heijan", "Lvbel C5",
        "Blok3", "Muti", "Server Uraz",
    ],
    "rock": [
        "Duman", "maNga", "Mor ve Ötesi", "Pinhani", "Adamlar",
        "Teoman", "Şebnem Ferah", "Hayko Cepkin", "Gripin", "Kurban",
        "Pentagram", "Athena", "Model", "Yüksek Sadakat", "Kolpa",
        "Cem Adrian", "Can Gox",
    ],
    "indie": [
        "Pinhani", "Adamlar", "Büyük Ev Ablukada", "Jakuzi",
        "Yüzyüzeyken Konuşuruz", "TANTANA", "Tamino",
        "Canozan", "Bulent Ortacgil", "Mabel Matiz", "No.1",
    ],
    "electronic": [
        "Mahmut Orhan", "Ilkay Sencan", "Burak Yeter", "Oğuz Yılmaz",
        "Velet", "DJ Snake", "Barış K",
    ],
    "classical": [
        "Fazıl Say", "İdil Biret", "Cihat Aşkın", "Burçin Büke",
    ],
    "default": [
        "Tarkan", "Sezen Aksu", "Duman", "Ceza", "Sıla", "Mabel Matiz",
        "Mor ve Ötesi", "Adamlar", "Ezhel", "Hadise", "Pinhani",
    ],
}

# ── Mood + Genre → Arama Sorguları ───────────────────────────────────────────

MOOD_GENRE_QUERIES = {
    "pop": {
        "energetic":   ["pop party", "pop hits", "dans pop", "upbeat pop"],
        "calm":        ["slow pop", "akustik pop", "soft pop", "ballad"],
        "intense":     ["power pop", "pop rock", "güçlü pop"],
        "chill":       ["chill pop", "easy pop", "pop akustik"],
        "melancholic": ["slow şarkılar", "duygusal pop", "hüzünlü pop", "ayrılık"],
    },
    "rap": {
        "energetic":   ["rap hit", "hip hop", "rap beat", "türkçe rap"],
        "calm":        ["chill rap", "lo-fi rap", "rap akustik"],
        "intense":     ["aggressive rap", "hard rap", "rap diss", "gangsta rap"],
        "chill":       ["chill hip hop", "rap chill", "boom bap"],
        "melancholic": ["sad rap", "duygusal rap", "rap slow"],
    },
    "rock": {
        "energetic":   ["rock hit", "rock anthem", "rock enerjik"],
        "calm":        ["soft rock", "akustik rock", "rock ballad"],
        "intense":     ["hard rock", "metal", "punk rock", "heavy"],
        "chill":       ["indie rock", "alternative rock", "rock chill"],
        "melancholic": ["rock ballad", "grunge", "post rock", "rock hüzün"],
    },
    "indie": {
        "energetic":   ["indie pop", "indie dance", "indie upbeat"],
        "calm":        ["indie akustik", "folk indie", "indie slow"],
        "intense":     ["indie rock", "noise pop", "shoegaze"],
        "chill":       ["indie chill", "dream pop", "indie folk"],
        "melancholic": ["sad indie", "indie melancholy", "slowcore"],
    },
    "electronic": {
        "energetic":   ["edm", "dance", "electro house", "trance"],
        "calm":        ["ambient", "downtempo", "chillwave"],
        "intense":     ["dubstep", "drum and bass", "hardstyle"],
        "chill":       ["lo-fi", "chillhop", "deep house"],
        "melancholic": ["synthwave sad", "dark electronic", "melancholic electronic"],
    },
    "classical": {
        "energetic":   ["classical upbeat", "vivaldi", "classical energetic"],
        "calm":        ["classical piano", "classical peaceful", "debussy"],
        "intense":     ["classical dramatic", "wagner", "beethoven symphony"],
        "chill":       ["classical relaxing", "classical guitar", "satie"],
        "melancholic": ["classical sad", "chopin nocturne", "adagio"],
    },
}

# Tür belirtilmemişse kullanılacak genel sorgular
MOOD_DEFAULT_QUERIES = {
    "energetic":   ["hit şarkılar", "party mix", "enerjik müzik", "dans"],
    "calm":        ["sakin müzik", "slow şarkılar", "akustik", "huzur"],
    "intense":     ["güçlü şarkılar", "rock metal", "agresif müzik"],
    "chill":       ["chill mix", "rahat müzik", "lofi", "akşam keyfi"],
    "melancholic": ["hüzünlü şarkılar", "duygusal", "ayrılık şarkıları", "ağlatan"],
}

# Dil bazlı ek sorgular
LANG_PREFIXES = {
    "tr": ["türkçe", "turkish"],
    "en": ["english", ""],
    "mixed": [""],
}

LANG_MARKET = {
    "tr": "TR",
    "en": "US",
    "mixed": None,
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


# ═════════════════════════════════════════════════════════════════════════════
#  ANA FONKSİYON
# ═════════════════════════════════════════════════════════════════════════════

def get_recommendations(mood_category: str, language: str = "mixed",
                        content_type: str = "track", search_query: str = "", genre: str = "", limit: int = 10) -> list:
    """
    Mood + dil + içerik türüne + (opsiyonel) arama kelimesine ve müzik türüne göre Spotify'dan öneriler getirir.
    """
    lang = language.lower() if language else "mixed"
    if lang not in LANG_MARKET:
        lang = "mixed"

    if content_type == "playlist":
        return _get_playlists(mood_category, lang, search_query, genre, limit)
    elif content_type == "podcast":
        return _get_podcasts(mood_category, lang, search_query, genre, limit)
    else:
        return _get_tracks(mood_category, lang, search_query, genre, limit)


# ── Şarkı önerileri (yeniden yazıldı) ────────────────────────────────────────

def _build_track_query(mood_category: str, lang: str, search_query: str, genre: str) -> str:
    """Akıllı arama sorgusu oluştur — genre öncelikli."""
    parts = []

    # 1) Kullanıcının arama kelimesi varsa öncelik ver
    if search_query:
        parts.append(search_query)

    # 2) Genre + mood bazlı sorgu (GENRE İLK SIRADA)
    genre_key = genre.lower() if genre else ""
    if genre_key and genre_key in MOOD_GENRE_QUERIES:
        mood_queries = MOOD_GENRE_QUERIES[genre_key].get(mood_category, MOOD_GENRE_QUERIES[genre_key].get("chill", [genre_key]))
        parts.append(random.choice(mood_queries))
    elif genre_key:
        parts.append(genre_key)
        default_mood = MOOD_DEFAULT_QUERIES.get(mood_category, ["müzik"])
        parts.append(random.choice(default_mood))
    else:
        default_mood = MOOD_DEFAULT_QUERIES.get(mood_category, ["müzik"])
        parts.append(random.choice(default_mood))

    # 3) Dil bazlı prefix (EN SONA — genre'yi bozmamak için)
    if lang == "tr" and not search_query:
        parts.append("türkçe")

    return " ".join(parts)


def _get_tracks(mood_category: str, lang: str, search_query: str, genre: str, limit: int) -> list:
    """Doğrudan track araması — daha isabetli sonuçlar."""
    market = LANG_MARKET.get(lang)
    existing = []

    # Strateji 1: Sanatçı bazlı arama (Türkçe seçildiyse)
    if lang == "tr" and not search_query:
        try:
            tracks = _search_by_turkish_artists(mood_category, genre, limit, market)
            existing.extend(tracks)
            logger.info(f"Strateji 1 (sanatçı): {len(tracks)} şarkı bulundu")
        except Exception as e:
            logger.error(f"Strateji 1 hatası: {e}")

    if len(existing) >= limit:
        random.shuffle(existing)
        return existing[:limit]

    # Strateji 2: Akıllı sorgu ile track araması
    try:
        query = _build_track_query(mood_category, lang, search_query, genre)
        logger.info(f"Strateji 2 sorgusu: '{query}'")
        tracks = _search_tracks_direct(query, limit * 2, market)
        logger.info(f"Strateji 2: {len(tracks)} şarkı bulundu")

        seen_ids = {t["id"] for t in existing}
        for t in tracks:
            if t["id"] not in seen_ids:
                existing.append(t)
                seen_ids.add(t["id"])
    except Exception as e:
        logger.error(f"Strateji 2 hatası: {e}")

    if len(existing) >= limit:
        random.shuffle(existing)
        return existing[:limit]

    # Strateji 3: Son çare — basit genre/mood araması
    fallback_queries = [
        genre or mood_category,
        f"{genre} music" if genre else f"{mood_category} music",
        "top hits türkçe" if lang == "tr" else "top hits",
    ]
    for fq in fallback_queries:
        if len(existing) >= limit:
            break
        try:
            logger.info(f"Strateji 3 (son çare): '{fq}'")
            tracks = _search_tracks_direct(fq, limit, market)
            seen_ids = {t["id"] for t in existing}
            for t in tracks:
                if t["id"] not in seen_ids:
                    existing.append(t)
                    seen_ids.add(t["id"])
        except Exception as e:
            logger.error(f"Strateji 3 hatası: {e}")

    random.shuffle(existing)
    return existing[:limit]


def _search_by_turkish_artists(mood_category: str, genre: str, limit: int, market: str | None) -> list:
    """
    Bilinen Türk sanatçılarını Spotify search API ile arar.
    artist_top_tracks 403 verdiği için sadece search endpoint'i kullanılır.
    """
    genre_key = genre.lower() if genre else "default"
    artist_pool = TR_ARTISTS.get(genre_key, TR_ARTISTS["default"])

    # Rastgele 6 sanatçı seç
    selected_artists = random.sample(artist_pool, min(6, len(artist_pool)))
    all_tracks = []

    for artist_name in selected_artists:
        try:
            # artist: filtresi ile sanatçının şarkılarını ara
            query = f'artist:{artist_name}'
            search_kwargs = {"q": query, "type": "track", "limit": 5}
            if market:
                search_kwargs["market"] = market

            results = sp.search(**search_kwargs)
            for track in results.get("tracks", {}).get("items", []):
                if track and track.get("id"):
                    all_tracks.append(_format_track(track))

        except Exception as e:
            logger.warning(f"Sanatçı araması başarısız '{artist_name}': {e}")
            continue

    random.shuffle(all_tracks)
    return all_tracks


def _search_tracks_direct(query: str, limit: int, market: str | None = None) -> list:
    search_kwargs = {"q": query, "type": "track", "limit": min(limit, 50)}
    if market:
        search_kwargs["market"] = market
    try:
        results = sp.search(**search_kwargs)
        tracks = []
        for track in results.get("tracks", {}).get("items", []):
            if track and track.get("id"):
                tracks.append(_format_track(track))
        return tracks
    except Exception as e:
        logger.error(f"Track araması başarısız (q='{query}'): {e}")
        return []


# ── Playlist önerileri ────────────────────────────────────────────────────────

def _get_playlists(mood_category: str, lang: str, search_query: str, genre: str, limit: int) -> list:
    query = _build_track_query(mood_category, lang, search_query, genre)
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
