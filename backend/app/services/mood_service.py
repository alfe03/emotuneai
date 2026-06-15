import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from deepface import DeepFace
import google.generativeai as genai
from app.core.config import settings
import json
import logging
import re
import time
import concurrent.futures

logging.getLogger("google.generativeai").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


# ── Gemini AI Kurulumu ────────────────────────────────────────────────────────

genai.configure(api_key=settings.GEMINI_API_KEY)

gemini_model_35 = genai.GenerativeModel("gemini-3.5-flash")
gemini_model_31_lite = genai.GenerativeModel("gemini-3.1-flash-lite")
gemini_model_25 = genai.GenerativeModel("gemini-2.5-flash")
gemini_model_25_lite = genai.GenerativeModel("gemini-2.5-flash-lite")

# Öncelik sırası: 3.5-flash -> 3.1-flash-lite -> 2.5-flash -> 2.5-flash-lite
GEMINI_MODELS = [gemini_model_35, gemini_model_31_lite, gemini_model_25, gemini_model_25_lite]

# Retry ayarları
MAX_RETRIES = 1
INITIAL_RETRY_DELAY = 1  # saniye
GEMINI_TIMEOUT = 8  # saniye — tek bir Gemini çağrısı için max bekleme

# ── Gemini devre dışı flag'i ──────────────────────────────────────────────────
# Sadece 401/403 (geçersiz key) için True olur.
# 429 quota/rate-limit geçici hatadır — kalıcı disable YAPILMAZ, her istek tekrar dener.
_GEMINI_DISABLED = False
_GEMINI_DISABLE_REASON = ""


def _disable_gemini(reason: str):
    """Gemini'yi KALICI olarak devre dışı bırakır — sadece geçersiz API key için çağrılmalı."""
    global _GEMINI_DISABLED, _GEMINI_DISABLE_REASON
    _GEMINI_DISABLED = True
    _GEMINI_DISABLE_REASON = reason
    logger.warning(f"Gemini kalıcı devre dışı (geçersiz key): {reason}")


def _is_fatal_gemini_error(error_str: str) -> bool:
    """True → kalıcı hata (key geçersiz), Gemini'yi kapat.
       False → geçici hata (quota/rate-limit/network), sadece bu isteği fallback'e düşür."""
    fatal_keywords = ["api_key_invalid", "invalid api key", "invalid_api_key",
                      " 401 ", "401,", "401\n", "403 ", "403,", "403\n",
                      "permission_denied", "unauthenticated"]
    return any(kw in error_str for kw in fatal_keywords)


def _call_gemini_with_timeout(model, prompt, timeout=None, generation_config=None):
    """Gemini API'yi strict timeout ile çağırır. Yanıt gelmezse TimeoutError fırlatır."""
    if timeout is None:
        timeout = GEMINI_TIMEOUT
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(model.generate_content, prompt, generation_config=generation_config)
        return future.result(timeout=timeout)


def _call_gemini_with_fallback(prompt, timeout=None, generation_config=None):
    """
    GEMINI_MODELS listesindeki modelleri sırayla dener.
    429 (quota) alırsa bir sonraki modele geçer.
    Fatal hata (401/403) veya tüm modeller tükenirse exception fırlatır.
    """
    last_exc = None
    for model in GEMINI_MODELS:
        try:
            return _call_gemini_with_timeout(model, prompt, timeout=timeout, generation_config=generation_config)
        except (TimeoutError, concurrent.futures.TimeoutError):
            raise  # Timeout → direkt yukarı ilet, başka model deneme
        except Exception as e:
            error_str = str(e).lower()
            if _is_fatal_gemini_error(error_str):
                raise  # Key hatası → direkt yukarı ilet
            # 429 / quota → bir sonraki modele geç
            logger.warning(f"Model {model.model_name} quota/hata → sonraki deneniyor: {str(e)[:80]}")
            last_exc = e
            continue
    if last_exc:
        raise last_exc
    raise ValueError("Hiçbir Gemini modeli yanıt veremedi (API veya Kota hatası).")


# ── Sabitler ──────────────────────────────────────────────────────────────────

EMOTION_TO_MOOD = {
    "happy":     "energetic",
    "happiness": "energetic",
    "joy":       "energetic",
    "surprise":  "energetic",
    "neutral":   "chill",
    "sad":       "melancholic",
    "sadness":   "melancholic",
    "disgust":   "melancholic",
    "fear":      "calm",
    "angry":     "intense",
    "anger":     "intense",
}

# DeepFace duygu etiketleri → Türkçe açıklayıcı isimler + emoji
EMOTION_DISPLAY = {
    "happy":     {"label": "Mutlu ve neşeli",         "emoji": "😄"},
    "happiness": {"label": "Mutlu ve neşeli",         "emoji": "😄"},
    "joy":       {"label": "Neşeli ve keyifli",       "emoji": "😊"},
    "surprise":  {"label": "Şaşkın ve heyecanlı",    "emoji": "😮"},
    "neutral":   {"label": "Sakin ve dengeli",        "emoji": "😌"},
    "sad":       {"label": "Üzgün ve hüzünlü",       "emoji": "😢"},
    "sadness":   {"label": "Üzgün ve hüzünlü",       "emoji": "😢"},
    "disgust":   {"label": "Rahatsız ve tedirgin",    "emoji": "😒"},
    "fear":      {"label": "Endişeli ve kaygılı",     "emoji": "😰"},
    "angry":     {"label": "Sinirli ve gergin",       "emoji": "😠"},
    "anger":     {"label": "Sinirli ve gergin",       "emoji": "😠"},
}

MOOD_TO_FEATURES = {
    "energetic":   {"min_energy": 0.7, "min_valence": 0.6, "min_tempo": 120},
    "calm":        {"max_energy": 0.4, "min_valence": 0.4, "max_tempo": 100},
    "intense":     {"min_energy": 0.8, "max_valence": 0.4, "min_tempo": 130},
    "chill":       {"min_energy": 0.3, "max_energy": 0.6, "min_valence": 0.5},
    "melancholic": {"max_energy": 0.5, "max_valence": 0.3, "max_tempo": 100},
}

# Gemini'ye gönderilen sistem promptu
GEMINI_MOOD_PROMPT = """Sen bir duygu analizi uzmanısın. Kullanıcının yazdığı metni analiz et ve ruh halini belirle.

## Ruh Hali Kategorileri (mood_category)
Aşağıdaki 5 kategoriden BİRİNİ seç:
- "energetic" → Mutlu, enerjik, heyecanlı, neşeli, coşkulu, motive, eğlenceli, kendini iyi hisseden
- "chill" → Rahat, huzurlu, keyifli, tatmin olmuş, dingin, gevşemiş, kafası rahat
- "melancholic" → Üzgün, hüzünlü, nostaljik, duygusal, kırık, yalnız, özlem dolu, içi buruk
- "intense" → Öfkeli, sinirli, agresif, gergin, isyankâr, patlayacak gibi, sıkılmış, bunalmış
- "calm" → Sakinleşmek isteyen, endişeli, kaygılı, tedirgin, yorgun, stresli ama rahatlamaya ihtiyacı var

## Duygu Etiketi (emotion)
"emotion" alanında basit tek kelime YAZMA. Bunun yerine kullanıcının hissini en iyi özetleyen kısa ve samimi bir Türkçe ifade yaz.

Örnekler:
- "Mutlu ve enerjik" ✅  (sadece "mutlu" ❌)
- "Nostaljik ve hüzünlü" ✅  (sadece "üzgün" ❌)
- "Yorgun ama huzurlu" ✅  (sadece "sakin" ❌)
- "Sinirli ve gergin" ✅  (sadece "kızgın" ❌)
- "Heyecanlı ve meraklı" ✅
- "Kafası rahat ve keyifli" ✅
- "Özlem dolu" ✅
- "Motive ve kararlı" ✅
- "Bunalmış ve stresli" ✅
- "İçi buruk ama umutlu" ✅
- "Romantik ve duygusal" ✅
- "Kaygılı ama umutlu" ✅
- "Neşeli ve coşkulu" ✅

## Emoji
Duyguyu en iyi yansıtan tek bir emoji seç.

## Sanatçı/Şarkıcı Tespiti (requested_artist)
Kullanıcı metninde belirli bir sanatçı, şarkıcı veya grup adı belirterek şarkı önerisi istemişse (örn: "Duman çal", "Tarkan'dan bir şeyler", "Sezen Aksu dinlemek istiyorum", "Duman'ın hüzünlü şarkıları"), bu sanatçı/grup adının yalın halini (örn: "Duman", "Tarkan", "Sezen Aksu") "requested_artist" alanına yaz. Eğer herhangi bir sanatçı/grup adı belirtilmemişse null yap.

## Kurallar
1. Cümlenin genel anlamına, duygusal tonuna ve alt metnine odaklan.
2. Karmaşık veya çelişkili duygular varsa (örn: "yoruldum ama mutluyum") ikisini de yansıt.
3. Türkçe, İngilizce veya karışık dil kullanılabilir — hepsini anla.
4. Sadece JSON formatında yanıt ver, başka hiçbir şey yazma.

JSON formatı:
{
  "emotion": "kullanıcının hissini özetleyen kısa ve açıklayıcı Türkçe ifade (2-4 kelime)",
  "emoji": "duyguyu yansıtan tek emoji",
  "confidence": 0-100 arası güven skoru (sayı),
  "mood_category": "energetic | chill | melancholic | intense | calm",
  "explanation": "Neden bu kategoriyi seçtiğini kısa ve samimi bir şekilde açıkla (türkçe, 1-2 cümle, kullanıcıya hitap et)",
  "requested_artist": "tespit edilen sanatçı/grup adı (string) veya null"
}

Kullanıcının metni: """



# ── Yüz Analizi (DeepFace – değişmedi) ───────────────────────────────────────

def analyze_face(image_base64: str) -> dict:
    try:
        import base64
        import numpy as np
        import cv2

        img_bytes = base64.b64decode(image_base64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        result = DeepFace.analyze(
            img_path=img,
            actions=["emotion"],
            enforce_detection=False
        )

        dominant_emotion = result[0]["dominant_emotion"]
        confidence = result[0]["emotion"][dominant_emotion]
        mood_category = EMOTION_TO_MOOD.get(dominant_emotion, "chill")
        display = EMOTION_DISPLAY.get(dominant_emotion, {"label": dominant_emotion, "emoji": "🎵"})

        emotion_label = display["label"]
        emoji = display["emoji"]
        explanation = f"Yüz ifadenizde '{emotion_label}' durumu tespit edildi."

        # Gemini Vision Hibrit Eklentisi
        if not _GEMINI_DISABLED and settings.GEMINI_API_KEY:
            try:
                gemini_prompt = f"""Sen bir duygu ve empati uzmanısın. Eklenen fotoğraftaki kişinin yüz ifadesini ve bulunduğu ortamı incele.
Zaten yapay zeka tarafından bu kişinin temel duygusu '{dominant_emotion}' (Kategori: {mood_category}) olarak tespit edildi.
Görevlerin:
1. Kişinin yüz ifadesindeki ince detayları (gözler, tebessüm, yorgunluk vs.) ve ortamı gözlemleyerek o anki ruh halini 2 cümleyle, empati kurarak açıkla. Açıklaman "explanation" alanına yazılmalı (Kullanıcıya "sen" diye hitap et).
2. Duyguyu en iyi yansıtan 1 adet emojiyi "emoji" alanına yaz.
3. Kısa ve vurucu Türkçe bir duygu etiketi oluştur (örn: "Hafif yorgun ama umutlu") ve "emotion" alanına yaz.

Sadece JSON dön. Format:
{{
  "emotion": "...",
  "explanation": "...",
  "emoji": "..."
}}"""
                image_part = {"mime_type": "image/jpeg", "data": image_base64}
                response = _call_gemini_with_fallback([image_part, gemini_prompt], timeout=GEMINI_TIMEOUT + 3)
                
                raw_response = response.text.strip()
                json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', raw_response)
                
                if json_match:
                    gemini_result = json.loads(json_match.group())
                    emotion_label = gemini_result.get("emotion", emotion_label)
                    emoji = gemini_result.get("emoji", emoji)
                    explanation = gemini_result.get("explanation", explanation)

            except Exception as e:
                logger.warning(f"Gemini Yüz Analizi Hatası (Fallback'e geçildi): {e}")

        return {
            "emotion": emotion_label,
            "emoji": emoji,
            "confidence": round(confidence, 2),
            "mood_category": mood_category,
            "all_emotions": result[0]["emotion"],
            "explanation": explanation
        }
    except Exception as e:
        raise ValueError(f"Yüz analizi başarısız: {str(e)}")


# ── Anahtar Kelime Tabanlı Yedek Analiz (Çoklu Duygu Desteği) ─────────────────

KEYWORD_MOODS = {
    "energetic": {
        "keywords": [
            "mutlu", "neşeli", "harika", "süper", "muhteşem", "enerjik",
            "heyecanlı", "coşkulu", "motive", "eğlenceli", "iyi", "güzel",
            "sevinçli", "keyifli", "happy", "excited", "great", "amazing",
            "awesome", "wonderful", "fantastic", "love", "fun", "joy",
        ],
        "label": "Enerjik",
        "emoji": "⚡",
    },
    "melancholic": {
        "keywords": [
            "üzgün", "hüzünlü", "kötü", "mutsuz", "ağla", "yalnız",
            "özlem", "nostalji", "nostaljik", "kırık", "acı", "kayıp",
            "sad", "depressed", "lonely", "miss", "cry", "unhappy",
            "grief", "heartbroken", "melancholy", "sorrow", "lost",
        ],
        "label": "Hüzünlü",
        "emoji": "😢",
    },
    "intense": {
        "keywords": [
            "sinir", "kızgın", "öfke", "nefret", "bıktım", "sıkıldım",
            "gergin", "agresif", "patlayacak", "bunalmış", "çıldır",
            "angry", "furious", "hate", "rage", "annoyed", "frustrated",
            "mad", "irritated", "aggressive",
        ],
        "label": "Gergin",
        "emoji": "😠",
    },
    "calm": {
        "keywords": [
            "endişe", "kaygı", "stres", "yorgun", "tedirgin", "korku",
            "panik", "anxious", "stressed", "tired", "worried", "afraid",
            "exhausted", "nervous", "overwhelmed", "sakinleş", "rahatla",
        ],
        "label": "Sakin",
        "emoji": "😌",
    },
    "chill": {
        "keywords": [
            "rahat", "huzur", "dingin", "gevşe", "tatmin", "sakin",
            "kafam rahat", "relax", "chill", "peaceful", "cool",
            "content", "comfortable", "easy",
        ],
        "label": "Rahat",
        "emoji": "😎",
    },
}

# İstek/yönelim belirten kelimeler — kullanıcının ne istediğini anlamak için
# "sakin şeyler istiyorum" → sakin'e ağırlık ver
_DESIRE_WORDS = ["istiyorum", "isterim", "lazım", "ihtiyaç", "arıyorum", "dinle",
                 "want", "need", "looking for", "give me", "i want", "dinlemek"]

# Zıtlık/geçiş belirten kelimeler — "ama", "fakat" sonrasına ağırlık ver
_CONTRAST_WORDS = ["ama", "fakat", "ancak", "yine de", "buna rağmen", "lakin",
                   "but", "however", "although", "yet", "though"]

# "biraz", "daha" gibi yoğunluk azaltıcılar
_SOFTENER_WORDS = ["biraz", "birazcık", "hafif", "az", "azıcık", "daha",
                   "slightly", "a bit", "a little", "somewhat", "kinda"]


# Karma duygu açıklamaları — (birincil, ikincil) → Türkçe ifade + emoji
_BLEND_MAP = {
    ("energetic", "melancholic"): {"emotion": "Enerjik ama hüzünlü",           "emoji": "🥲"},
    ("energetic", "calm"):        {"emotion": "Enerjik ama sakinleşmek istiyor","emoji": "🌅"},
    ("energetic", "chill"):       {"emotion": "Neşeli ve rahat",               "emoji": "😊"},
    ("energetic", "intense"):     {"emotion": "Coşkulu ve ateşli",             "emoji": "🔥"},
    ("melancholic", "energetic"): {"emotion": "Hüzünlü ama umutlu",            "emoji": "🌧️"},
    ("melancholic", "calm"):      {"emotion": "Hüzünlü ve yorgun",             "emoji": "😔"},
    ("melancholic", "chill"):     {"emotion": "Duygusal ama dingin",            "emoji": "🌙"},
    ("melancholic", "intense"):   {"emotion": "İçi buruk ve gergin",           "emoji": "💔"},
    ("intense", "energetic"):     {"emotion": "Öfkeli ama enerjik",            "emoji": "💪"},
    ("intense", "calm"):          {"emotion": "Gergin ama sakinleşmek istiyor", "emoji": "🌊"},
    ("intense", "melancholic"):   {"emotion": "Sinirli ve kırgın",             "emoji": "😤"},
    ("intense", "chill"):         {"emotion": "Sıkılmış, rahatlık arıyor",     "emoji": "😮‍💨"},
    ("calm", "energetic"):        {"emotion": "Yorgun ama motive",             "emoji": "🌤️"},
    ("calm", "melancholic"):      {"emotion": "Kaygılı ve duygusal",           "emoji": "😰"},
    ("calm", "chill"):            {"emotion": "Yorgun ve dinlenmek istiyor",   "emoji": "😴"},
    ("calm", "intense"):          {"emotion": "Stresli ve gergin",             "emoji": "😣"},
    ("chill", "energetic"):       {"emotion": "Keyifli ve hafif enerjik",      "emoji": "🎶"},
    ("chill", "melancholic"):     {"emotion": "Rahat ama biraz hüzünlü",      "emoji": "🍂"},
    ("chill", "calm"):            {"emotion": "Huzurlu ve sakin",              "emoji": "🧘"},
    ("chill", "intense"):         {"emotion": "Rahat ama biraz gergin",        "emoji": "🤔"},
}

# Birincil mood + istek ile ikincil mood arasında hangi Spotify mood'unun kullanılacağı
# Kullanıcının asıl istediği yöne karar veriyoruz
_BLEND_MOOD_RESOLUTION = {
    ("energetic", "melancholic"): "chill",        # ortası: ne çok enerjik ne çok hüzünlü
    ("energetic", "calm"):        "chill",        # enerjik ama sakin → chill
    ("melancholic", "energetic"): "chill",        # üzgün ama umutlu → chill
    ("melancholic", "calm"):      "melancholic",  # hüzünlü+yorgun → melancholic kalır
    ("intense", "calm"):          "calm",         # gergin ama sakinleşmek istiyor → calm
    ("intense", "melancholic"):   "melancholic",  # sinirli+kırgın → melancholic
    ("calm", "energetic"):        "chill",        # yorgun ama motive → chill
}


def _extract_artist_fallback(text: str) -> str | None:
    """
    Kullanıcı metninden basit regex ve kelime eşleşmeleriyle sanatçı adını ayıklar.
    Örn: "Tarkan'dan", "Duman çal", "Sezen Aksu dinlemek istiyorum", "sanatçı: Ceza"
    """
    text_lower = text.lower()
    
    # 1. Sanatçı/Şarkıcı belirten özel etiketler (örn: "sanatçı: duman", "artist: tarkan")
    label_match = re.search(r"(?:sanatçı|şarkıcı|artist)\s*:\s*([A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,25})", text, re.IGNORECASE)
    if label_match:
        candidate = label_match.group(1).strip()
        words = candidate.split()
        if words:
            if len(words) >= 2 and words[0][0].isupper() and words[1][0].isupper():
                return f"{words[0]} {words[1]}"
            return words[0]
        
    # 2 & 3. Türkçe ek kalıpları (kesme işaretli, kesme işaretsiz, boşluklu/boşluksuz)
    # Tek kelimelik adayları eşleştirir ve ardından önceki kelimeyle birleştirilebilir olup olmadığını kontrol eder.
    for m in re.finditer(r"\b([A-ZÇĞİÖŞÜa-zçğıöşü]+)\s*['’]?\s*(?:dan|den|tan|ten|ın|in|un|ün|nın|nin|nun|nün)\b", text, re.IGNORECASE):
        candidate = m.group(1).strip()
        full_match = m.group(0).lower().strip()
        
        excluded_full = {
            "sakin", "gergin", "üzgün", "yorgun", "kızgın", "kesin", "serin", "derin", "zaten", "hemen", 
            "aniden", "birden", "lütfen", "bazen", "dünden", "yoldan", "candan", "tenden", "günden",
            "bugün", "bugun", "için", "icin", "yarın", "yarin", "bütün", "butun", "yakın", "yakin",
            "uzun", "oyun", "koyun", "boyun", "kadın", "kadin", "altın", "altin", "aydın", "aydin"
        }
        if full_match in excluded_full:
            continue
            
        excluded_candidates = {
            "ben", "sen", "o", "biz", "siz", "onlar", "neden", "oradan", "buradan", "şuradan", "ordan", 
            "burdan", "şurdan", "ondan", "bundan", "şundan", "bir", "ve", "veya", "ama", "fakat",
            "şarkı", "sarkı", "müzik", "muzik", "albüm", "album", "ses", "grup", "sanatçı", "sanatcı", 
            "şarkıcı", "sarkıcı", "sarkilar", "şarkılar", "sarkiları", "şarkıları",
            "istiyorum", "isterim", "olsun", "çal", "çalsın", "calsın", "gelsin", "dinle", "dinlemek", "öner", "oner", "istediğim", "istedigim",
            "mis", "mıs", "mus", "müs", "misin", "mısın", "musun", "müsün", "önerir", "onerir", "verecek", "için", "icin", "gibi", "kadar",
            "bana", "sana", "ona", "bize", "size", "onlara"
        }
        if candidate.lower() not in excluded_candidates and len(candidate) > 2:
            # Önündeki kelimeyi kontrol et (örn: "sezen aksu dan" -> "sezen" + "aksu")
            pos = text_lower.find(full_match)
            before = text[:pos].strip()
            before_words = before.split()
            if before_words:
                last_word_raw = before_words[-1]
                # Noktalama işaretiyle bitiyorsa yeni cümledir, birleştirme!
                if not last_word_raw.endswith((".", "!", "?", ":", ";")):
                    last_before = last_word_raw.strip(".,?!\"'()")
                    if last_before.lower() not in excluded_candidates and len(last_before) > 2:
                        return f"{last_before} {candidate}"
            return candidate

    # 4. Yönelim/istek kelimelerinden hemen önceki kelimeleri kontrol et
    # Örn: "sezen aksu dinlemek", "duman çal"
    for verb in ["dinlemek", "dinle", "çal", "cal", "söyle", "soyle", "öner", "oner", "play", "listen", "olsun", "çalsın", "calsın", "calsin", "gelsin"]:
        pos = text_lower.find(verb)
        if pos != -1:
            before = text[:pos].strip()
            words = before.split()
            if words:
                stopwords = {
                    "bir", "biraz", "ve", "veya", "da", "de", "ki", "ben", "sen", "bana", "sana", "bi", "daha",
                    "şöyle", "böyle", "kendi", "güzel", "hareketli", "sakin", "yavaş", "hızlı", "hüzünlü",
                    "şarkı", "sarkı", "müzik", "muzik", "albüm", "album", "ses", "grup", "sanatçı", "sanatcı", 
                    "şarkıcı", "sarkıcı", "dan", "den", "tan", "ten", "sarkilar", "şarkılar", "sarkiları", "şarkıları",
                    "istiyorum", "istiyorum.", "olsun", "çalsın", "gelsin", "önerir", "onerir", "misin", "mısın",
                    "verecek", "için", "icin", "gibi", "kadar"
                }
                last_word = words[-1].strip(".,?!\"'()")
                if last_word.lower() not in stopwords and len(last_word) > 2:
                    if len(words) >= 2:
                        second_last = words[-2].strip(".,?!\"'()")
                        if second_last.lower() not in stopwords and len(second_last) > 2:
                            return f"{second_last} {last_word}"
                    return last_word
                    
    return None


def _fallback_analyze_text(text: str) -> dict:
    """
    Gemini API kullanılamadığında çoklu duygu algılayan akıllı fallback.
    Karışık duyguları anlayıp harmanlanmış sonuç üretir.
    """
    text_lower = text.lower()

    # ── 1) Her mood kategorisi için skor hesapla ──
    scores = {}
    
    # "iyi", "mutlu" gibi kelimeleri tersine çevirmek için negasyon kontrolü
    negation_words = ["değil", "hissetmiyor", "yok", "hiç", "kötü"]
    has_negation = any(nw in text_lower for nw in negation_words)

    for mood, data in KEYWORD_MOODS.items():
        score = 0
        for kw in data["keywords"]:
            if kw in text_lower:
                if has_negation and mood in ("energetic", "chill") and kw in ("iyi", "mutlu", "harika", "süper", "güzel", "rahat", "huzurlu"):
                    continue # Eğer negasyon varsa pozitif kelimelerden puan verme
                score += 1
        scores[mood] = score

    # Eğer cümlede belirgin bir negasyon varsa ama hiçbir olumsuz kelime (üzgün vb.) geçmiyorsa
    # varsayılan olarak melankolik ağırlık verelim ki yanlışlıkla 0 puan alıp chill'e düşmesin.
    if has_negation and scores.get("melancholic", 0) == 0 and scores.get("intense", 0) == 0:
        scores["melancholic"] += 2


    # ── 2) Zıtlık kelimelerini kontrol et ──
    # "ama", "fakat" gibi kelimelerden SONRA gelen duyguya ekstra ağırlık ver
    # çünkü kullanıcı genellikle "X ama Y istiyorum" der → Y'yi vurgular
    has_contrast = False
    contrast_pos = -1
    for cw in _CONTRAST_WORDS:
        pos = text_lower.find(cw)
        if pos != -1:
            has_contrast = True
            contrast_pos = pos + len(cw)
            break

    if has_contrast and contrast_pos > 0:
        after_contrast = text_lower[contrast_pos:]
        for mood, data in KEYWORD_MOODS.items():
            for kw in data["keywords"]:
                if kw in after_contrast:
                    scores[mood] += 2  # "ama" sonrası kelimeler 2x bonus

    # ── 3) İstek kelimelerini kontrol et ──
    # "sakin şeyler istiyorum" → sakin'e ağırlık
    has_desire = any(dw in text_lower for dw in _DESIRE_WORDS)
    if has_desire:
        # İstek kelimesine yakın olan mood'a bonus
        for dw in _DESIRE_WORDS:
            dw_pos = text_lower.find(dw)
            if dw_pos == -1:
                continue
            # İstek kelimesinden önceki 30 karaktere bak
            before_desire = text_lower[max(0, dw_pos - 30):dw_pos]
            for mood, data in KEYWORD_MOODS.items():
                for kw in data["keywords"]:
                    if kw in before_desire:
                        scores[mood] += 3  # "sakin şeyler istiyorum" → sakin +3

    # ── 4) Softener kontrolü ("biraz", "daha") ──
    has_softener = any(sw in text_lower for sw in _SOFTENER_WORDS)

    # ── 5) Birincil ve ikincil mood'u bul ──
    sorted_moods = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary_mood = sorted_moods[0][0]
    primary_score = sorted_moods[0][1]
    secondary_mood = sorted_moods[1][0] if len(sorted_moods) > 1 else None
    secondary_score = sorted_moods[1][1] if len(sorted_moods) > 1 else 0

    # ── 6) Karışık duygu mu, tek duygu mu? ──
    is_blended = (
        secondary_score > 0
        and primary_mood != secondary_mood
        and (has_contrast or has_softener or secondary_score >= primary_score * 0.5)
    )

    if is_blended and secondary_mood:
        # Harmanlanmış duygu
        blend_key = (primary_mood, secondary_mood)
        blend = _BLEND_MAP.get(blend_key, None)

        if blend:
            emotion = blend["emotion"]
            emoji = blend["emoji"]
        else:
            # Map'te yoksa dinamik oluştur
            p_label = KEYWORD_MOODS[primary_mood]["label"]
            s_label = KEYWORD_MOODS[secondary_mood]["label"].lower()
            emotion = f"{p_label} ama biraz {s_label}"
            emoji = KEYWORD_MOODS[primary_mood]["emoji"]

        # Mood kategorisini belirle: harmanlanmış bir ortaya mı düşsün?
        resolved_mood = _BLEND_MOOD_RESOLUTION.get(blend_key, None)
        if resolved_mood:
            mood_category = resolved_mood
        elif has_contrast and secondary_score >= primary_score:
            # "ama" sonrası daha baskınsa, ikincili seç
            mood_category = secondary_mood
        else:
            mood_category = primary_mood

        confidence = round(min((primary_score + secondary_score) * 15, 75), 2)
        explanation = (
            f"⚡ Karışık duygular algılandı: hem {KEYWORD_MOODS[primary_mood]['label'].lower()} "
            f"hem {KEYWORD_MOODS[secondary_mood]['label'].lower()}. "
            f"Sana en uygun ortayı bulmaya çalıştım!"
        )
    else:
        # Tek duygu
        chosen = KEYWORD_MOODS[primary_mood]
        mood_category = primary_mood
        confidence = round(min(primary_score * 20, 80), 2)

        # Tek duygu için daha açıklayıcı emotion metni
        _SINGLE_EMOTIONS = {
            "energetic":   "Mutlu ve enerjik",
            "melancholic": "Üzgün ve hüzünlü",
            "intense":     "Sinirli ve gergin",
            "calm":        "Yorgun ve sakinleşmek istiyor",
            "chill":       "Rahat ve huzurlu",
        }
        emotion = _SINGLE_EMOTIONS.get(primary_mood, chosen["label"])
        emoji = chosen["emoji"]
        explanation = ""

    return {
        "emotion":          emotion,
        "emoji":            emoji,
        "confidence":       confidence,
        "mood_category":    mood_category,
        "input_text":       text,
        "explanation":      explanation,
        "requested_artist": _extract_artist_fallback(text),
    }


# ── Metin Analizi (Gemini AI – Retry + Fallback) ─────────────────────────────

def analyze_text(text: str) -> dict:
    """
    Kullanıcının yazdığı metni Gemini AI ile analiz eder.
    - API key geçersizse (401/403) Gemini kalıcı devre dışı → fallback.
    - 429 quota/rate-limit → sadece bu isteği fallback'e düşür, sonraki istekte tekrar dene.
    - Timeout → fallback.
    """
    global _GEMINI_DISABLED

    # ── 1. Kalıcı key hatası varsa direkt fallback ─────────────────────────────
    if _GEMINI_DISABLED:
        logger.info(f"Gemini kalıcı devre dışı ({_GEMINI_DISABLE_REASON}) → fallback.")
        return _fallback_analyze_text(text)

    if not settings.GEMINI_API_KEY or len(settings.GEMINI_API_KEY.strip()) < 10:
        logger.warning("Gemini API key eksik → fallback.")
        _disable_gemini("API key eksik")
        return _fallback_analyze_text(text)

    # ── 2. Gemini çağrısı — önce 2.0-flash, quota doluysa 2.5-flash-lite ─────────
    prompt = GEMINI_MOOD_PROMPT + f'"{text}"'
    import google.generativeai as genai
    try:
        response = _call_gemini_with_fallback(
            prompt, 
            timeout=GEMINI_TIMEOUT,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        raw_response = response.text.strip()

        json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', raw_response)
        if not json_match:
            logger.warning("Gemini'den geçerli JSON alınamadı → fallback.")
            return _fallback_analyze_text(text)

        result = json.loads(json_match.group())
        mood_category = result.get("mood_category", "chill")
        if mood_category not in ("energetic", "chill", "melancholic", "intense", "calm"):
            mood_category = "chill"

        requested_artist = result.get("requested_artist")
        logger.info("Metin analizi Gemini ile tamamlandı.")
        return {
            "emotion":          result.get("emotion", "belirsiz"),
            "emoji":            result.get("emoji", "🎵"),
            "confidence":       round(float(result.get("confidence", 50)), 2),
            "mood_category":    mood_category,
            "input_text":       text,
            "explanation":      result.get("explanation", ""),
            "requested_artist": requested_artist,
        }

    except (TimeoutError, concurrent.futures.TimeoutError):
        logger.warning(f"Gemini timeout ({GEMINI_TIMEOUT}s) → fallback.")
        return _fallback_analyze_text(text)

    except json.JSONDecodeError:
        logger.warning("Gemini JSON parse hatası → fallback.")
        return _fallback_analyze_text(text)

    except Exception as e:
        with open('gemini_error_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"ERROR: {str(e)}\n")
        error_str = str(e).lower()
        if _is_fatal_gemini_error(error_str):
            # Geçersiz key → kalıcı kapat
            _disable_gemini(str(e)[:120])
            logger.error(f"Gemini key geçersiz, kalıcı kapatıldı: {str(e)[:120]}")
        else:
            # 429 quota, rate-limit, network hatası → geçici, sadece bu istek fallback
            logger.warning(f"Gemini geçici hata (bu istek fallback, sonraki denenir): {str(e)[:120]}")
        return _fallback_analyze_text(text)



# ── Mood → Spotify özellikleri ────────────────────────────────────────────────

def get_mood_features(mood_category: str) -> dict:
    return MOOD_TO_FEATURES.get(mood_category, MOOD_TO_FEATURES["chill"])


# ── Çok Modlu Video Analizi (Gemini Multimodal Video & Audio) ──────────────────

GEMINI_VIDEO_PROMPT = """Sen bir çok modlu (multimodal) duygu analizi uzmanısın. Gönderilen kısa videoyu hem görsel (yüz ifadesi, mimikler) hem de işitsel (konuşma içeriği, ses tonu) olarak analiz et.

## Yapılacak Analiz
1. Kişinin yüz ifadesinden, göz ve ağız hareketlerinden, mimiklerinden nasıl hissettiğini çıkar.
2. Videodaki ses kaydında söylenen sözleri tespit et ve Türkçe yazıya dök (transcript).
3. Konuşmacının ses tonundan (gergin, neşeli, fısıltılı, yavaş, sakin vb.) hislerini analiz et.
4. Tüm bu analizleri (görüntü, transkript ve ses tonu) birleştirerek nihai bir duygu durumuna karar ver.

## Ruh Hali Kategorileri (mood_category)
Aşağıdaki 5 kategoriden BİRİNİ seç:
- "energetic" → Mutlu, enerjik, heyecanlı, neşeli, coşkulu, motive, eğlenceli, kendini iyi hisseden
- "chill" → Rahat, huzurlu, keyifli, tatmin olmuş, dingin, gevşemiş, kafası rahat
- "melancholic" → Üzgün, hüzünlü, nostaljik, duygusal, kırık, yalnız, özlem dolu, içi buruk
- "intense" → Öfkeli, sinirli, agresif, gergin, isyankâr, patlayacak gibi, sıkılmış, bunalmış
- "calm" → Sakinleşmek isteyen, endişeli, kaygılı, tedirgin, yorgun, stresli ama rahatlamaya ihtiyacı var

## Duygu Etiketi (emotion)
Kullanıcının hissini en iyi özetleyen kısa ve samimi bir Türkçe ifade yaz (örn: "Heyecanlı ve coşkulu", "Yorgun ama sakin", "Hüzünlü ve dalgın").

## Emoji
Duyguyu en iyi yansıtan tek bir emoji seç.

## Kurallar
1. Videodaki konuşmanın tam transkriptini (transcription) çıkar ve "input_text" alanına yaz. Konuşma yoksa bu alanı boş bırak veya "Konuşma algılanamadı" yaz.
2. Sadece JSON formatında yanıt ver, başka hiçbir şey yazma.

JSON formatı:
{
  "emotion": "kullanıcının hissini özetleyen kısa Türkçe ifade",
  "emoji": "tek emoji",
  "confidence": 0-100 arası güven skoru (sayı),
  "mood_category": "energetic | chill | melancholic | intense | calm",
  "input_text": "videodaki konuşmanın Türkçe transkripti",
  "explanation": "Analizini (hem yüz ifadesi hem ses tonu/sözler açısından) kısa ve samimi bir şekilde açıklayan Türkçe 1-2 cümle."
}
"""

def _video_fallback_with_deepface(video_bytes: bytes) -> dict:
    """Gemini kullanılamadığında video'dan frame çekip DeepFace ile yüz analizi yapar."""
    import tempfile
    import cv2
    import numpy as np

    logger.info("Video fallback: DeepFace ile yüz analizi deneniyor...")
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(video_bytes)
        tmp_path = f.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        # Videonun ortasındaki frame'i al
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total_frames // 2))
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            raise ValueError("Video'dan kare okunamadı.")

        result = DeepFace.analyze(
            img_path=frame,
            actions=["emotion"],
            enforce_detection=False
        )
        dominant_emotion = result[0]["dominant_emotion"]
        confidence = result[0]["emotion"][dominant_emotion]
        mood_category = EMOTION_TO_MOOD.get(dominant_emotion, "chill")
        display = EMOTION_DISPLAY.get(dominant_emotion, {"label": dominant_emotion, "emoji": "🎵"})

        logger.info(f"Video fallback başarılı: {dominant_emotion} ({mood_category})")
        return {
            "emotion": display["label"],
            "emoji": display["emoji"],
            "confidence": round(confidence, 2),
            "mood_category": mood_category,
            "input_text": "",
            "explanation": ""
        }
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def analyze_video(video_bytes: bytes) -> dict:
    """
    Kullanıcının kaydettiği 3 saniyelik videoyu Gemini 2.0 Flash ile analiz eder.
    Hem görüntüyü (yüz ifadeleri) hem de sesi (söylenen sözler + ses tonu) kullanarak duygu tespiti yapar.
    Gemini kullanılamıyorsa DeepFace fallback devreye girer.
    """
    # Hızlı kontrol: kalıcı key hatası varsa direkt DeepFace
    if _GEMINI_DISABLED:
        logger.warning(f"Gemini kalıcı devre dışı ({_GEMINI_DISABLE_REASON}) → DeepFace fallback.")
        return _video_fallback_with_deepface(video_bytes)

    if not settings.GEMINI_API_KEY or len(settings.GEMINI_API_KEY.strip()) < 10:
        logger.warning("Gemini API key eksik → DeepFace fallback.")
        return _video_fallback_with_deepface(video_bytes)

    import tempfile

    # Geçici dosyaya yaz
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
        temp_file.write(video_bytes)
        temp_video_path = temp_file.name

    video_file = None
    try:
        logger.info(f"Geçici video dosyası oluşturuldu: {temp_video_path}")

        # Gemini Files API ile yükle
        video_file = genai.upload_file(path=temp_video_path)
        logger.info(f"Video Gemini'ye yüklendi, isim: {video_file.name}. İşlenmesi bekleniyor...")

        # İşlenme durumunu kontrol et
        attempts = 0
        while video_file.state.name == "PROCESSING":
            attempts += 1
            if attempts > 12:  # Max 6 saniye bekle
                raise ValueError("Video işleme zaman aşımına uğradı.")
            time.sleep(0.5)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError("Video işleme başarısız oldu (FAILED).")

        logger.info("Video başarıyla işlendi. Analiz başlatılıyor...")

        # Analizi yap — önce 2.0-flash, quota doluysa 2.5-flash-lite
        try:
            response = _call_gemini_with_fallback(
                [video_file, GEMINI_VIDEO_PROMPT], timeout=GEMINI_TIMEOUT + 2
            )
        except (TimeoutError, concurrent.futures.TimeoutError):
            logger.warning("Video analizi timeout → DeepFace fallback.")
            return _video_fallback_with_deepface(video_bytes)
        except Exception as e:
            error_str = str(e).lower()
            if _is_fatal_gemini_error(error_str):
                _disable_gemini(str(e)[:120])
                logger.error(f"Video: Gemini key geçersiz, kalıcı kapatıldı: {str(e)[:120]}")
            else:
                logger.warning(f"Video analizi geçici Gemini hatası → DeepFace fallback: {str(e)[:120]}")
            return _video_fallback_with_deepface(video_bytes)

        raw_response = response.text.strip()

        # JSON'ı ayıkla ve çöz
        json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', raw_response)
        if not json_match:
            raise ValueError(f"Gemini geçerli bir JSON dönmedi: {raw_response[:200]}")

        result = json.loads(json_match.group())

        # Alanları doğrula ve temizle
        emotion = result.get("emotion", "belirsiz")
        emoji = result.get("emoji", "🎵")
        confidence = float(result.get("confidence", 50.0))
        mood_category = result.get("mood_category", "chill")
        input_text = result.get("input_text", "")
        explanation = result.get("explanation", "")

        valid_moods = ["energetic", "chill", "melancholic", "intense", "calm"]
        if mood_category not in valid_moods:
            mood_category = "chill"

        return {
            "emotion": emotion,
            "emoji": emoji,
            "confidence": round(confidence, 2),
            "mood_category": mood_category,
            "input_text": input_text,
            "explanation": explanation
        }

    except Exception as e:
        err_msg = str(e) or repr(e) or type(e).__name__
        logger.error(f"Video analizi sırasında hata: {err_msg}")
        logger.warning("Gemini kullanılamıyor → DeepFace fallback deneniyor...")
        try:
            return _video_fallback_with_deepface(video_bytes)
        except Exception as fallback_err:
            raise ValueError(f"Video analizi başarısız (Gemini + fallback): {fallback_err}")

    finally:
        # Google bulutundaki dosyayı temizle
        if video_file:
            try:
                genai.delete_file(video_file.name)
                logger.info(f"Gemini bulut dosyası silindi: {video_file.name}")
            except Exception as e:
                logger.warning(f"Gemini bulut dosyası silinemedi: {e}")

        # Yerel geçici dosyayı sil
        if os.path.exists(temp_video_path):
            try:
                os.unlink(temp_video_path)
                logger.info(f"Geçici yerel dosya silindi: {temp_video_path}")
            except Exception as e:
                logger.warning(f"Geçici yerel dosya silinemedi: {e}")


GEMINI_AUDIO_PROMPT = """Sen bir çok modlu (multimodal) ses ve duygu analizi uzmanısın. Gönderilen kısa ses kaydını hem sözel içerik (söylenen sözler) hem de akustik özellikler (ses tonu, konuşma hızı, sesin perdesi, tınısı, duraklamalar, heyecan/yorgunluk belirtileri) açısından analiz et.

## Yapılacak Analiz
1. Kişinin konuşmasından ne söylediğini kelimesi kelimesine Türkçe transkript (yazıya döküm) olarak çıkar.
2. Sesin perdesini (pitch), konuşma hızını (tempo), tonlama ve tınısını (timbre) analiz et. Gerginlik, yorgunluk, sakinlik, heyecan, hüzün gibi duygusal ipuçlarını yakala.
3. Transkript içeriğini ve akustik analizi birleştirerek nihai duygu durumunu belirle.

## Ruh Hali Kategorileri (mood_category)
Aşağıdaki 5 kategoriden BİRİNİ seç:
- "energetic" → Mutlu, enerjik, heyecanlı, neşeli, coşkulu, motive, eğlenceli, kendini iyi hisseden
- "chill" → Rahat, huzurlu, keyifli, tatmin olmuş, dingin, gevşemiş, kafası rahat
- "melancholic" → Üzgün, hüzünlü, nostaljik, duygusal, kırık, yalnız, özlem dolu, içi buruk
- "intense" → Öfkeli, sinirli, agresif, gergin, isyankâr, patlayacak gibi, sıkılmış, bunalmış
- "calm" → Sakinleşmek isteyen, endişeli, kaygılı, tedirgin, yorgun, stresli ama rahatlamaya ihtiyacı var

## Duygu Etiketi (emotion)
Kullanıcının hissini en iyi özetleyen kısa ve samimi bir Türkçe ifade yaz (örn: "Yorgun ama huzurlu", "Heyecanlı ve kıpır kıpır", "İçi buruk ve duygusal").

## Emoji
Duyguyu en iyi yansıtan tek bir emoji seç.

## Sanatçı/Şarkıcı Tespiti (requested_artist)
Eğer kullanıcı ses kaydında belirli bir sanatçı, şarkıcı veya grup adı belirterek şarkı önerisi istemişse (örn: "Duman çal", "Tarkan'dan bir şeyler", "Sezen Aksu dinlemek istiyorum", "mangadan şarkı öner"), bu sanatçı/grup adının yalın halini (örn: "Duman", "Tarkan", "Sezen Aksu", "manga") "requested_artist" alanına yaz. Eğer herhangi bir sanatçı/grup adı belirtilmemişse null yap.

## Kurallar
1. Sesi tam transkripte et ve "input_text" alanına yaz. Konuşma yoksa bu alanı boş bırak veya "Konuşma algılanamadı" yaz.
2. Sadece JSON formatında yanıt ver, başka hiçbir şey yazma.

JSON formatı:
{
  "emotion": "kullanıcının hissini özetleyen kısa Türkçe ifade",
  "emoji": "tek emoji",
  "confidence": 0-100 arası güven skoru (sayı),
  "mood_category": "energetic | chill | melancholic | intense | calm",
  "input_text": "ses kaydındaki konuşmanın Türkçe transkripti",
  "explanation": "Analizini (hem kelimeler hem de ses tonu/akustik açıdan) kısa ve samimi açıklayan Türkçe 1-2 cümle.",
  "requested_artist": "tespit edilen sanatçı/grup adı (string) veya null"
}
"""

def analyze_audio(audio_bytes: bytes) -> dict:
    """
    Kullanıcının kaydettiği 5-10 saniyelik ses verisini Gemini ile analiz eder.
    Hem transkripti çıkarır hem de ses tonuna göre duygu durumunu belirler.
    Gemini devre dışıysa veya hata alırsa keyword fallback'e düşer.
    """
    if _GEMINI_DISABLED:
        logger.warning(f"Gemini kalıcı devre dışı ({_GEMINI_DISABLE_REASON})")
        raise ValueError("Yapay zeka servisi şu an kullanılamıyor (API kapalı). Lütfen manuel analizi kullanın.")

    if not settings.GEMINI_API_KEY or len(settings.GEMINI_API_KEY.strip()) < 10:
        logger.warning("Gemini API key eksik.")
        raise ValueError("Yapay zeka servisi şu an kullanılamıyor (API anahtarı eksik).")

    audio_part = {
        "mime_type": "audio/webm",
        "data": audio_bytes
    }

    try:
        logger.info("Ses analizine başlanıyor (inline data ile)...")

        # Analizi yap — önce 2.0-flash, quota doluysa 2.5-flash-lite
        import google.generativeai as genai
        try:
            response = _call_gemini_with_fallback(
                [audio_part, GEMINI_AUDIO_PROMPT], 
                timeout=GEMINI_TIMEOUT + 15,
                generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
            )
        except (TimeoutError, concurrent.futures.TimeoutError):
            logger.warning("Ses analizi timeout.")
            raise ValueError("Ses analizi çok uzun sürdü, lütfen tekrar deneyin.")
        except Exception as e:
            error_str = str(e).lower()
            if _is_fatal_gemini_error(error_str):
                _disable_gemini(str(e)[:120])
                logger.error(f"Ses: Gemini key geçersiz, kalıcı kapatıldı: {str(e)[:120]}")
                raise ValueError("Yapay zeka servisi şu an kullanılamıyor.")
            else:
                logger.warning(f"Ses analizi geçici Gemini hatası: {str(e)[:120]}")
                raise ValueError(f"API Hatası (Ekran görüntüsü alın): {str(e)[:150]}")

        raw_response = response.text.strip()

        # JSON'ı ayıkla ve çöz
        json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', raw_response)
        if not json_match:
            raise ValueError("Söyledikleriniz tam anlaşılamadı, lütfen daha net konuşarak tekrar deneyin.")

        result = json.loads(json_match.group())

        # Alanları doğrula ve temizle
        emotion = result.get("emotion", "Sakin")
        emoji = result.get("emoji", "🎙️")
        confidence = float(result.get("confidence", 50.0))
        mood_category = result.get("mood_category", "chill")
        input_text = result.get("input_text", "").strip()
        explanation = result.get("explanation", "")
        
        # Eğer kullanıcı konuşmadıysa veya sadece gürültü varsa
        if not input_text or len(input_text) < 2 or "algılanamadı" in input_text.lower():
            raise ValueError("Sesiniz net alınamadı veya konuşmadınız. Lütfen tekrar deneyin.")

        valid_moods = ["energetic", "chill", "melancholic", "intense", "calm"]
        if mood_category not in valid_moods:
            mood_category = "chill"

        # Şarkı araması yaparken faydalanmak üzere requested_artist ayıklaması
        requested_artist = result.get("requested_artist")

        return {
            "emotion": emotion,
            "emoji": emoji,
            "confidence": round(confidence, 2),
            "mood_category": mood_category,
            "input_text": input_text,
            "explanation": explanation,
            "requested_artist": requested_artist
        }
    except ValueError as ve:
        raise ve
    except Exception as e:
        error_str = str(e).lower()
        if _is_fatal_gemini_error(error_str):
            _disable_gemini(str(e)[:120])
            logger.error(f"Ses: Gemini key geçersiz, kalıcı kapatıldı: {str(e)[:120]}")
            raise ValueError("Yapay zeka servisi şu an kullanılamıyor.")
        else:
            logger.warning(f"Ses analizi sırasında hata: {str(e)[:120]}")
            raise ValueError("Analiz sırasında bir sorun oluştu, lütfen tekrar deneyin.")