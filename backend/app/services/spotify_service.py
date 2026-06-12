# -*- coding: utf-8 -*-
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from app.core.config import settings
import random
import logging
import re
import threading
import concurrent.futures
import time as _time

logger = logging.getLogger(__name__)

# Spotify client — lazy initialization ile oluşturulur (boş key'lerde crash önlenir)
_sp_instance = None
_sp_lock = threading.Lock()

def _get_spotify_client() -> spotipy.Spotify:
    """Thread-safe lazy Spotify client."""
    global _sp_instance
    if _sp_instance is None:
        with _sp_lock:
            if _sp_instance is None:
                _sp_instance = spotipy.Spotify(
                    auth_manager=SpotifyClientCredentials(
                        client_id=settings.SPOTIFY_CLIENT_ID,
                        client_secret=settings.SPOTIFY_CLIENT_SECRET
                    )
                )
    return _sp_instance

# Spotify Recommendations API'si yeni hesaplarda kapalıdır.
# İlk hatada bu flag False olarak işaretlenip doğrudan arama yöntemine geçilecektir.
_recommendations_lock = threading.Lock()
SPOTIFY_RECOMMENDATIONS_SUPPORTED = True

SPAM_KEYWORDS = [
    "binaural", "meditasyon", "meditation", "relaxing", "uyku", "sleep", 
    "432 hz", "432hz", "528 hz", "528hz", "solfeggio", "white noise", 
    "rain sounds", "lullaby", "sound therapy", "healing frequency", 
    "rahatlatıcı müzik", "deep sleep", "focus music", "study beats", 
    "ambient sounds", "frekans", "delta waves", "alfa dalgaları", 
    "beyin dalgaları", "brain waves", "sakinleştirici", "relaxing music",
    "nature sounds", "doğa sesleri"
]

def _is_noise_track(track: dict) -> bool:
    name = track.get("name", "").lower()
    album = track.get("album", {}).get("name", "").lower() if track.get("album") else ""
    artists = " ".join([a.get("name", "").lower() for a in track.get("artists", [])])
    
    for kw in SPAM_KEYWORDS:
        if kw in name or kw in album or kw in artists:
            return True
    return False


# ── Basit In-Memory Cache ─────────────────────────────────────────────────────
_cache: dict = {}
_CACHE_TTL = 1800  # 30 dakika (5'ten artırıldı — aynı mood/dil sorgusu tekrar Spotify'a gitmesin)


def _cache_get(key: str):
    """Cache'den değer al. TTL dolmuşsa None döner."""
    if key in _cache:
        val, ts = _cache[key]
        if _time.time() - ts < _CACHE_TTL:
            return val
        del _cache[key]
    return None


def _cache_set(key: str, value):
    """Cache'e değer yaz. 200 girişten fazlaysa expired olanları temizle."""
    _cache[key] = (value, _time.time())
    if len(_cache) > 200:
        now = _time.time()
        expired = [k for k, (v, t) in _cache.items() if now - t > _CACHE_TTL]
        for k in expired:
            del _cache[k]


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
    "jazz": [
        "Jülide Özçelik", "Birsen Tezer", "Elif Çağlar", "Kerem Görsev", "İlhan Erşahin"
    ],
    "blues": [
        "Sahte Rakı", "Can Gox", "Batu Mutlugil", "Yavuz Çetin"
    ],
    "metal": [
        "Pentagram", "Almora", "Hayko Cepkin", "Murder King"
    ],
    "r&b": [
        "Güneş", "Sefo", "Mela Bedel", "Kardelen"
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
    "jazz": {
        "energetic":   ["upbeat jazz", "swing jazz", "big band swing", "fast jazz"],
        "calm":        ["calm jazz", "peaceful jazz", "soft jazz piano", "ballad jazz"],
        "intense":     ["free jazz", "avant garde jazz", "intense jazz fusion"],
        "chill":       ["chill jazz", "smooth jazz", "cool jazz", "late night jazz"],
        "melancholic": ["sad jazz", "melancholic jazz", "blue jazz", "slow jazz ballad"],
    },
    "blues": {
        "energetic":   ["upbeat blues", "chicago blues", "blues rock", "boogie woogie"],
        "calm":        ["soft blues", "acoustic blues", "calm blues"],
        "intense":     ["electric blues guitar", "hard blues rock", "screaming blues"],
        "chill":       ["chill blues", "smooth blues", "soul blues"],
        "melancholic": ["sad blues", "lonely blues", "melancholic blues", "slow blues ballad"],
    },
    "metal": {
        "energetic":   ["thrash metal", "power metal", "speed metal", "melodic death metal"],
        "calm":        ["acoustic metal", "symphonic metal ballad", "soft metal acoustic"],
        "intense":     ["heavy metal", "death metal", "black metal", "brutal metal"],
        "chill":       ["progressive metal chill", "atmospheric metal", "doom metal slow"],
        "melancholic": ["doom metal", "gothic metal", "melancholic metal", "sad metal ballad"],
    },
    "r&b": {
        "energetic":   ["r&b dance", "uptempo r&b", "r&b club hits", "energetic r&b"],
        "calm":        ["soft r&b", "calm r&b", "acoustic r&b"],
        "intense":     ["powerful r&b", "trapsoul", "intense r&b vocals"],
        "chill":       ["chill r&b", "smooth r&b", "neo soul", "late night r&b"],
        "melancholic": ["sad r&b", "melancholic r&b", "heartbreak r&b", "slow r&b ballad"],
    },
}

# Tür belirtilmemişse kullanılacak genel sorgular
MOOD_DEFAULT_QUERIES = {
    "energetic":   ["pop hits", "party dance hits", "upbeat pop", "dans pop hits"],
    "calm":        ["akustik pop slow", "soft acoustic", "sakin pop", "slow akustik"],
    "intense":     ["rock anthems", "power rock metal", "aggressive rap", "sert rap"],
    "chill":       ["chill lofi beats", "chill pop hits", "easy listening pop", "akşam keyfi lofi"],
    "melancholic": ["duygusal slow pop", "sad indie ballad", "hüzünlü slow", "slow şarkılar"],
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


def _is_matching_artist(artist_name: str, track_artists: list) -> bool:
    """
    İstenen sanatçı adının, parça sanatçılarından biriyle tam kelime bazlı eşleşip eşleşmediğini kontrol eder.
    Böylece 'carti' aramasının 'cameron cartio' ile eşleşmesi gibi alt-kelime (substring) hataları önlenir.
    """
    artist_lower = artist_name.lower()
    for ta in track_artists:
        ta_lower = ta.lower()
        if artist_lower == ta_lower:
            return True
        # Kelime sınırları kullanarak arama yap (örn: \bplayboi carti\b)
        pattern = r'\b' + re.escape(artist_lower) + r'\b'
        if re.search(pattern, ta_lower):
            return True
    return False


def _get_tracks_by_artist_mood(artist_name: str, mood_category: str, limit: int = 10) -> list:
    """
    Spesifik bir sanatçının (artist_name) şarkılarını çeker.
    audio_features API'si Spotify tarafından yeni uygulamalara kapatıldığı için (403),
    arama sorgusuna duygu durumuna uygun anahtar kelimeler ekleyerek arama yapar.
    """
    logger.info(f"Artist mood filter running for artist='{artist_name}', mood='{mood_category}'")
    
    sp = _get_spotify_client()
    
    # Duygu durumuna uygun Türkçe ve İngilizce anahtar kelimeler
    mood_keywords = {
        "energetic": ["hareketli", "dans", "dance", "party", "coşkulu", "remix", "hızlı", "upbeat", "hit"],
        "calm": ["sakin", "akustik", "acoustic", "soft", "slow", "huzurlu", "dinlendirici"],
        "intense": ["sert", "agresif", "rock", "metal", "rap", "güçlü", "kızgın"],
        "chill": ["chill", "rahat", "akşam", "lofi", "akustik", "soft"],
        "melancholic": ["hüzünlü", "duygusal", "slow", "ayrılık", "ağlatan", "dram", "acı", "efkar", "damar"],
    }
    
    keywords = mood_keywords.get(mood_category, ["müzik"])
    tracks = []
    seen_ids = set()
    
    # Spotify search limiti maksimum 10'dur (2026 kısıtlaması nedeniyle limit=10 üst sınır)
    search_limit = min(limit, 10)
    
    # 1. Deneme: Sanatçı + Duygu Anahtar Kelimeleri ile arama yap (örn: "Duman hüzünlü")
    # Her anahtar kelimeyi tek tek deneyerek en iyi sonuçları harmanlayalım
    def _search_kw(kw):
        try:
            query = f'{artist_name} {kw}'
            search_results = sp.search(q=query, type='track', limit=search_limit)
            items = search_results.get("tracks", {}).get("items", []) if search_results else []
            results = []
            for track in items:
                if track and track.get("id"):
                    track_artists = [a["name"] for a in track.get("artists", [])]
                    if _is_matching_artist(artist_name, track_artists) and not _is_noise_track(track):
                        results.append(_format_track(track))
            return results
        except Exception as e:
            logger.warning(f"Error searching {artist_name} {kw}: {e}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(_search_kw, kw) for kw in keywords[:3]]
        for future in concurrent.futures.as_completed(futures, timeout=3):  # 5s → 3s
            try:
                for t in future.result():
                    if t["id"] not in seen_ids:
                        seen_ids.add(t["id"])
                        tracks.append(t)
            except Exception:
                pass
            
    # 2. Deneme: Eğer yeterli şarkı bulunamadıysa, genel sanatçı araması yap (örn: artist:"Duman")
    if len(tracks) < search_limit:
        try:
            query = f'artist:"{artist_name}"'
            search_results = sp.search(q=query, type='track', limit=10)
            items = search_results.get("tracks", {}).get("items", []) if search_results else []
            if not items:
                # Tırnaksız dene
                search_results = sp.search(q=artist_name, type='track', limit=10)
                items = search_results.get("tracks", {}).get("items", []) if search_results else []
                
            for track in items:
                if len(tracks) >= search_limit:
                    break
                if track and track.get("id"):
                    track_artists = [a["name"] for a in track.get("artists", [])]
                    if _is_matching_artist(artist_name, track_artists) and not _is_noise_track(track):
                        tid = track["id"]
                        if tid not in seen_ids:
                            seen_ids.add(tid)
                            tracks.append(_format_track(track))
        except Exception as e:
            logger.error(f"Error in artist general fallback search: {e}")
            
    logger.info(f"Artist mood filter found {len(tracks)} tracks for artist='{artist_name}' and mood='{mood_category}'")
    return tracks[:search_limit]



# ═════════════════════════════════════════════════════════════════════════════
#  ANA FONKSİYON
# ═════════════════════════════════════════════════════════════════════════════

def get_recommendations(mood_category: str, language: str = "mixed",
                        content_type: str = "track", search_query: str = "", genre: str = "", limit: int = 10,
                        requested_artist: str | None = None) -> list:
    """
    Mood + dil + içerik türüne + (opsiyonel) arama kelimesine ve müzik türüne göre Spotify'dan öneriler getirir.
    """
    lang = language.lower() if language else "mixed"
    if lang not in LANG_MARKET:
        lang = "mixed"

    if content_type == "playlist":
        return _get_playlists(mood_category, lang, search_query, genre, limit, requested_artist)
    elif content_type == "podcast":
        return _get_podcasts(mood_category, lang, search_query, genre, limit)
    else:
        # If no requested_artist is explicitly passed, try to deduce it from search_query
        if not requested_artist and search_query:
            from .mood_service import _extract_artist_fallback
            extracted = _extract_artist_fallback(search_query)
            if extracted:
                requested_artist = extracted
            else:
                # If search_query itself is likely an artist name (e.g. "Tarkan", "Duman", "Playboi Carti")
                lowered_sq = search_query.lower()
                common_keywords = {
                    "dans", "dance", "party", "upbeat", "hareketli", "coşkulu", "remix", 
                    "sakin", "akustik", "acoustic", "soft", "slow", "huzurlu", "dinlendirici",
                    "sert", "agresif", "rock", "metal", "rap", "güçlü", "kızgın", "chill",
                    "rahat", "akşam", "lofi", "hüzünlü", "duygusal", "ayrılık", "ağlatan", "pop", "classical"
                }
                if len(lowered_sq) >= 3 and lowered_sq not in common_keywords and re.match(r"^[A-Za-zÇĞİÖŞÜa-zçğıöşü\s\-\.]+$", search_query):
                    requested_artist = search_query

        if requested_artist:
            artist_tracks = _get_tracks_by_artist_mood(requested_artist, mood_category, limit)
            if artist_tracks:
                return artist_tracks
            logger.warning(f"Artist specific tracks failed for '{requested_artist}', falling back to standard recommendations.")
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


def _get_recommendations_api(mood_category: str, lang: str, genre: str, limit: int) -> list:
    """Spotify Recommendations API ile duygu durumuna göre şarkı önerir."""
    sp = _get_spotify_client()
    
    # 1) Target audio features mapping
    target_features = {}
    if mood_category == "energetic":
        target_features = {"target_energy": 0.8, "target_valence": 0.7, "target_danceability": 0.7}
    elif mood_category == "calm":
        target_features = {"target_energy": 0.35, "target_valence": 0.45, "target_acousticness": 0.6}
    elif mood_category == "intense":
        target_features = {"target_energy": 0.85, "target_valence": 0.35, "target_tempo": 130}
    elif mood_category == "chill":
        target_features = {"target_energy": 0.5, "target_valence": 0.55, "target_acousticness": 0.3}
    elif mood_category == "melancholic":
        target_features = {"target_energy": 0.3, "target_valence": 0.25, "target_acousticness": 0.5}

    # 2) Map genre to Spotify seed genres
    genre_map = {
        "pop": "pop",
        "rap": "hip-hop",
        "rock": "rock",
        "indie": "indie",
        "electronic": "edm",
        "classical": "classical",
        "jazz": "jazz",
        "blues": "blues",
        "metal": "metal",
        "r&b": "r-n-b"
    }
    
    seed_genres = []
    g = genre_map.get(genre.lower()) if genre else None
    if g:
        seed_genres.append(g)
    else:
        # Default seed genre based on mood
        mood_genre_defaults = {
            "energetic": "dance",
            "calm": "ambient",
            "intense": "metal",
            "chill": "chill",
            "melancholic": "rainy-day",
        }
        seed_genres.append(mood_genre_defaults.get(mood_category, "pop"))

    # 3) Sadece seed_genres kullan (sanatçı ID'leri yerine — sahte ID'ler 404 hatası veriyordu)
    params: dict = {
        "seed_genres": seed_genres[:5],
        "limit": limit,
        **target_features
    }
    
    if lang == "tr":
        params["market"] = "TR"
    elif lang == "en":
        params["market"] = "US"

    results = sp.recommendations(**params)
    tracks = []
    if isinstance(results, dict):
        for track in results.get("tracks", []):
            tracks.append(_format_track(track))
    return tracks


def _get_tracks(mood_category: str, lang: str, search_query: str, genre: str, limit: int) -> list:
    """Doğrudan track araması — daha isabetli sonuçlar. Cache destekli."""
    cache_key = f"tracks:{mood_category}:{lang}:{search_query}:{genre}:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        logger.info(f"Cache hit: {cache_key}")
        random.shuffle(cached)
        return cached[:limit]

    market = LANG_MARKET.get(lang)
    existing = []

    global SPOTIFY_RECOMMENDATIONS_SUPPORTED
    # Strateji 0: Spotify Recommendations API (Arama filtresi yoksa ve en kaliteli sonuçları istiyorsak)
    if not search_query and SPOTIFY_RECOMMENDATIONS_SUPPORTED:
        try:
            logger.info(f"Using Spotify Recommendations API for mood='{mood_category}', lang='{lang}', genre='{genre}'")
            tracks = _get_recommendations_api(mood_category, lang, genre, limit)
            if tracks:
                logger.info(f"Recommendations API returned {len(tracks)} tracks")
                return tracks
        except Exception as e:
            error_str = str(e)
            if "404" in error_str or "403" in error_str or "not found" in error_str.lower() or "forbidden" in error_str.lower():
                with _recommendations_lock:
                    SPOTIFY_RECOMMENDATIONS_SUPPORTED = False
                logger.warning(
                    "Spotify Recommendations API is restricted/deprecated for this developer account (404/403). "
                    "Bypassing Strateji 0 and falling back to search query recommendations permanently."
                )
            else:
                logger.error(f"Recommendations API failed, falling back to search: {e}")

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
    result = existing[:limit]
    _cache_set(cache_key, list(result))
    return result


def _search_by_turkish_artists(mood_category: str, genre: str, limit: int, market: str | None) -> list:
    """
    Bilinen Türk sanatçılarını Spotify search API ile arar.
    artist_top_tracks 403 verdiği için sadece search endpoint'i kullanılır.
    """
    genre_key = genre.lower() if genre else "default"
    artist_pool = TR_ARTISTS.get(genre_key, TR_ARTISTS["default"])

    # Rastgele 6 sanatçı seç
    selected_artists = random.sample(artist_pool, min(3, len(artist_pool)))  # 4 → 3 sanatçı
    all_tracks = []

    def _search_artist(a_name):
        try:
            query = f'artist:{a_name}'
            search_kwargs = {"q": query, "type": "track", "limit": 4}  # 5 → 4 sonuç/sanatçı
            if market:
                search_kwargs["market"] = market
            results = _get_spotify_client().search(**search_kwargs)
            items = results.get("tracks", {}).get("items", []) if results else []
            return [_format_track(t) for t in items if t and t.get("id") and not _is_noise_track(t)]
        except Exception as e:
            logger.warning(f"Sanatçı araması başarısız '{a_name}': {e}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_search_artist, name) for name in selected_artists]
        for future in concurrent.futures.as_completed(futures, timeout=3):  # 5s → 3s
            try:
                all_tracks.extend(future.result())
            except Exception:
                pass

    random.shuffle(all_tracks)
    return all_tracks


def _search_tracks_direct(query: str, limit: int, market: str | None = None) -> list:
    search_kwargs = {"q": query, "type": "track", "limit": min(limit, 10)}
    if market:
        search_kwargs["market"] = market
    try:
        results = _get_spotify_client().search(**search_kwargs)
        tracks = []
        items = results.get("tracks", {}).get("items", []) if results else []
        for track in items:
            if track and track.get("id") and not _is_noise_track(track):
                tracks.append(_format_track(track))
        return tracks
    except Exception as e:
        logger.error(f"Track araması başarısız (q='{query}'): {e}")
        return []


# ── Playlist önerileri ────────────────────────────────────────────────────────

def _get_playlists(mood_category: str, lang: str, search_query: str, genre: str, limit: int, requested_artist: str | None = None) -> list:
    """Playlist önerileri. Sanatçı belirtildiyse önce o sanatçıya ait playlistler aranır."""
    market = LANG_MARKET.get(lang)

    def _fetch_playlists(query: str) -> list:
        try:
            search_kwargs = {"q": query, "type": "playlist", "limit": min(limit, 10)}
            if market:
                search_kwargs["market"] = market
            results = _get_spotify_client().search(**search_kwargs)
            playlists = results.get("playlists", {}).get("items", []) if results else []
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

    # Sanatçı belirtildiyse önce sanatçı adını sorguya ekle
    if requested_artist:
        try:
            artist_query = f"{requested_artist} playlist"
            logger.info(f"Sanatçı bazlı playlist araması: '{artist_query}'")
            results = _fetch_playlists(artist_query)
            if results:
                return results
            logger.warning(f"Sanatçı '{requested_artist}' için playlist bulunamadı, genel aramaya geçiliyor.")
        except Exception as e:
            logger.error(f"Sanatçı playlist araması hatası: {e}")

    # Standart mood+genre bazlı sorgu
    query = _build_track_query(mood_category, lang, search_query, genre)
    return _fetch_playlists(query)


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
        results = _get_spotify_client().search(q=query, type="show", limit=min(limit, 10), market=market)
        shows = results.get("shows", {}).get("items", []) if results else []


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


def get_user_spotify_client(user, db) -> spotipy.Spotify:
    """
    Kullanıcının veritabanında kayıtlı Spotify token'ını alan,
    eğer süresi dolmuşsa refresh token ile yenileyip veritabanını güncelleyen,
    ve yetkilendirilmiş spotipy.Spotify istemcisini dönen fonksiyon.
    """
    import time
    from spotipy.oauth2 import SpotifyOAuth
    from sqlalchemy.orm import Session
    
    if not user.spotify_access_token or not user.spotify_refresh_token:
        raise ValueError("Spotify hesabı bağlanmamış.")
        
    expires_at = user.spotify_token_expires_at or 0
    # 60 saniye pay bırakarak kontrol et
    if expires_at - time.time() < 60:
        logger.info(f"Kullanıcı id={user.id} için Spotify token süresi dolmuş veya dolmak üzere. Yenileniyor...")
        sp_oauth = SpotifyOAuth(
            client_id=settings.SPOTIFY_CLIENT_ID,
            client_secret=settings.SPOTIFY_CLIENT_SECRET,
            redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        )
        try:
            token_info = sp_oauth.refresh_access_token(user.spotify_refresh_token)
            if token_info:
                user.spotify_access_token = token_info.get("access_token")
                if token_info.get("refresh_token"):
                    user.spotify_refresh_token = token_info.get("refresh_token")
                user.spotify_token_expires_at = int(time.time() + token_info.get("expires_in", 3600))
                db.commit()
                logger.info("Spotify token başarıyla yenilendi ve veritabanına kaydedildi.")
        except Exception as e:
            logger.error(f"Spotify token yenileme hatası: {e}")
            # Hata durumunda yine de mevcut token'ı denemesi için fırlatmıyoruz
            
    return spotipy.Spotify(auth=user.spotify_access_token)

