import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from deepface import DeepFace
import google.generativeai as genai
from app.core.config import settings
import json
import logging
import re
import time

logging.getLogger("google.generativeai").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


# ── Gemini AI Kurulumu ────────────────────────────────────────────────────────

genai.configure(api_key=settings.GEMINI_API_KEY)
gemini_model_35 = genai.GenerativeModel("gemini-3.5-flash")
gemini_model_20 = genai.GenerativeModel("gemini-2.0-flash")
gemini_model_25 = genai.GenerativeModel("gemini-2.5-flash")
gemini_model_15 = genai.GenerativeModel("gemini-flash-latest")

# Retry ayarları
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5  # saniye


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

        # Türkçe açıklayıcı etiket ve emoji
        display = EMOTION_DISPLAY.get(dominant_emotion, {"label": dominant_emotion, "emoji": "🎵"})

        return {
            "emotion": display["label"],
            "emoji": display["emoji"],
            "confidence": round(confidence, 2),
            "mood_category": mood_category,
            "all_emotions": result[0]["emotion"]
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
        
    # 2. Türkçe kesme işaretli ek kalıpları (örn: Tarkan'dan, Duman'ın, Sezen Aksu'nun)
    apostrophe_match = re.search(r"\b([A-ZÇĞİÖŞÜa-zçğıöşü\s]+)['’](?:dan|den|tan|ten|ın|in|un|ün|nın|nin|nun|nün)\b", text)
    if apostrophe_match:
        candidate = apostrophe_match.group(1).strip()
        words = candidate.split()
        if words:
            if len(words) >= 2 and words[-2][0].isupper():
                return f"{words[-2]} {words[-1]}"
            return words[-1]

    # 3. Türkçe ek kalıpları (kesme işareti olmadan, örn: Tarkandan, Dumandan, cartiden)
    # Yaygın kelimeleri hariç tutuyoruz
    suffix_match = re.search(r"\b([A-ZÇĞİÖŞÜa-zçğıöşü]+)(?:dan|den|tan|ten)\b", text)
    if suffix_match:
        candidate = suffix_match.group(1).strip()
        excluded = {
            "ben", "sen", "neden", "zaten", "aniden", "birden", "hemen", "lütfen", "içten", "bazen", 
            "dünden", "yoldan", "oradan", "buradan", "şuradan", "ordan", "burdan", "şurdan", "ondan",
            "bundan", "şundan", "candan", "tenden", "günden"
        }
        if candidate.lower() not in excluded and len(candidate) > 2:
            pos = text.find(candidate)
            before = text[:pos].strip()
            before_words = before.split()
            if before_words:
                last_before = before_words[-1].strip(".,?!\"'()")
                stop_before = {
                    "ve", "veya", "bir", "bana", "sana", "o", "bu", "şu", "ile", "de", "da", "ki", 
                    "en", "çok", "daha", "ben", "sen", "biz", "siz", "onlar", "ama", "fakat", "lakin"
                }
                if last_before.lower() not in stop_before and len(last_before) > 2:
                    return f"{before_words[-1]} {candidate}"
            return candidate

    # 4. Yönelim/istek kelimelerinden hemen önceki kelimeleri kontrol et
    # Örn: "sezen aksu dinlemek", "duman çal"
    for verb in ["dinlemek", "dinle", "çal", "söyle", "öner", "play", "listen"]:
        pos = text_lower.find(verb)
        if pos != -1:
            before = text[:pos].strip()
            words = before.split()
            if words:
                last_word = words[-1]
                stopwords = {
                    "bir", "biraz", "ve", "veya", "da", "de", "ki", "ben", "sen", "bana", "bi", "daha",
                    "şöyle", "böyle", "kendi", "güzel", "hareketli", "sakin", "yavaş", "hızlı", "hüzünlü"
                }
                if last_word.lower() not in stopwords and len(last_word) > 2:
                    if len(words) >= 2 and words[-2][0].isupper() and words[-1][0].isupper():
                        return f"{words[-2]} {words[-1]}"
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
    for mood, data in KEYWORD_MOODS.items():
        score = 0
        for kw in data["keywords"]:
            if kw in text_lower:
                score += 1
        scores[mood] = score

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
        explanation = "⚡ Gemini API şu an kullanılamadığı için basit analiz kullanıldı."

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
    Gemini 2.0 kota hatası verirse Gemini 1.5 modelini dener.
    Tüm denemeler başarısız olursa anahtar kelime tabanlı fallback kullanır.
    """
    last_error = None
    models_to_try = [
        ("gemini-3.5-flash", gemini_model_35),
        ("gemini-2.0-flash", gemini_model_20),
        ("gemini-2.5-flash", gemini_model_25),
        ("gemini-flash-latest", gemini_model_15)
    ]

    for model_name, model in models_to_try:
        for attempt in range(2):  # Model başına en fazla 2 deneme
            try:
                prompt = GEMINI_MOOD_PROMPT + f'"{text}"'
                response = model.generate_content(prompt)
                raw_response = response.text.strip()

                # JSON bloğunu ayıkla (```json ... ``` veya düz JSON)
                json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', raw_response)
                if not json_match:
                    raise ValueError(f"Gemini'den geçerli JSON alınamadı: {raw_response[:200]}")

                result = json.loads(json_match.group())

                # Gerekli alanları doğrula
                emotion = result.get("emotion", "belirsiz")
                emoji = result.get("emoji", "🎵")
                confidence = float(result.get("confidence", 50))
                mood_category = result.get("mood_category", "chill")
                explanation = result.get("explanation", "")
                requested_artist = result.get("requested_artist")

                # Mood category doğrulaması
                valid_moods = ["energetic", "chill", "melancholic", "intense", "calm"]
                if mood_category not in valid_moods:
                    mood_category = "chill"

                logger.info(f"Metin analizi başarıyla tamamlandı (Model: {model_name})")
                return {
                    "emotion":          emotion,
                    "emoji":            emoji,
                    "confidence":       round(confidence, 2),
                    "mood_category":    mood_category,
                    "input_text":       text,
                    "explanation":      explanation,
                    "requested_artist": requested_artist if requested_artist else _extract_artist_fallback(text),
                }

            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"Gemini yanıtı JSON olarak ayrıştırılamadı ({model_name}): {str(e)}")
                break  # Bu modeli bırak, sonraki modele geç
            except Exception as e:
                last_error = e
                error_str = str(e)

                # 429 Rate Limit hatası mı kontrol et
                if "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower() or "rate_limit" in error_str.lower():
                    if "quota" in error_str.lower() or "limit" in error_str.lower():
                        logger.warning(f"{model_name} günlük kullanım kotası aşılmış. Bir sonraki model/seçeneğe geçiliyor.")
                        break # Bu modeli bırak, sonraki modele geç
                    wait_time = INITIAL_RETRY_DELAY * (2 ** attempt)  # 5s, 10s
                    logger.warning(
                        f"Gemini API geçici rate limit hatası ({model_name}, deneme {attempt + 1}/2). "
                        f"{wait_time} saniye bekleniyor..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    # Diğer hatalar (örn. 401 veya beklenmedik hatalar) için sonraki modele geç
                    logger.error(f"Gemini API hatası ({model_name}): {error_str}")
                    break

    # Tüm denemeler başarısız → fallback kullan
    logger.warning(
        f"Tüm Gemini modelleri denemelerden sonra başarısız oldu. "
        f"Fallback analiz kullanılıyor. Son hata: {last_error}"
    )
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
            "explanation": "⚡ Gemini API şu an kullanılamadığı için sadece yüz ifadesi analizi yapıldı (ses analizi devre dışı)."
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
            if attempts > 30:  # Max 15 saniye bekle
                raise ValueError("Video işleme zaman aşımına uğradı.")
            time.sleep(0.5)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError("Video işleme başarısız oldu (FAILED).")

        logger.info("Video başarıyla işlendi. Analiz başlatılıyor...")

        # Analizi yap
        response = None
        last_err = None
        for model_name, model in [
            ("gemini-3.5-flash", gemini_model_35),
            ("gemini-2.0-flash", gemini_model_20),
            ("gemini-2.5-flash", gemini_model_25),
            ("gemini-flash-latest", gemini_model_15)
        ]:
            try:
                logger.info(f"Video analizi yapılıyor (Model: {model_name})...")
                response = model.generate_content([video_file, GEMINI_VIDEO_PROMPT])
                break
            except Exception as e:
                last_err = e
                logger.warning(f"Video analizi {model_name} ile başarısız oldu: {e}")

        if not response:
            raise ValueError(f"Video analizi tüm modellerle başarısız oldu: {last_err}")

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
        # Gemini API key sorunu veya bağlantı hatası → DeepFace fallback
        is_api_error = any(kw in err_msg.lower() for kw in ["api_key", "expired", "invalid", "401", "403", "400", "quota"])
        if is_api_error or not err_msg:
            logger.warning("Gemini API kullanılamıyor, DeepFace fallback deneniyor...")
            try:
                return _video_fallback_with_deepface(video_bytes)
            except Exception as fallback_err:
                raise ValueError(f"Video analizi başarısız oldu (Gemini ve fallback). Gemini API key'ini yenile: {fallback_err}")
        raise ValueError(f"Video analizi başarısız oldu: {err_msg}")
        
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