from deepface import DeepFace
from transformers import pipeline
from deep_translator import GoogleTranslator  # ← YENİ
from langdetect import detect                 # ← YENİ
import numpy as np
import cv2
import base64

sentiment_analyzer = pipeline(
    "text-classification",
    model="j-hartmann/emotion-english-distilroberta-base",
    top_k=1
)

translator = GoogleTranslator(source="auto", target="en")  # ← YENİ


def translate_to_english(text: str) -> tuple[str, str]:    # ← YENİ FONKSİYON
    """
    Metni İngilizce'ye çevirir.
    Metin zaten İngilizceyse olduğu gibi döner.
    """
    try:
        detected_lang = detect(text)
        if detected_lang == "en":
            return text, "en"
        translated = translator.translate(text)
        return translated, detected_lang
    except Exception:
        try:
            translated = translator.translate(text)
            return translated, "unknown"
        except Exception:
            return text, "unknown"


EMOTION_TO_MOOD = {
    "happy":    "energetic",
    "surprise": "energetic",
    "neutral":  "chill",
    "sad":      "calm",
    "disgust":  "calm",
    "fear":     "calm",
    "angry":    "intense",
}

MOOD_TO_FEATURES = {
    "energetic": {"min_energy": 0.7, "min_valence": 0.6, "min_tempo": 120},
    "calm":      {"max_energy": 0.4, "min_valence": 0.4, "max_tempo": 100},
    "intense":   {"min_energy": 0.8, "max_valence": 0.4, "min_tempo": 130},
    "chill":     {"min_energy": 0.3, "max_energy": 0.6, "min_valence": 0.5},
}


def analyze_face(image_base64: str) -> dict:
    try:
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

        return {
            "emotion": dominant_emotion,
            "confidence": round(confidence, 2),
            "mood_category": mood_category,
            "all_emotions": result[0]["emotion"]
        }
    except Exception as e:
        raise ValueError(f"Yüz analizi başarısız: {str(e)}")


def analyze_text(text: str) -> dict:
    try:
        translated_text, detected_lang = translate_to_english(text)  # ← GÜNCELLENDİ

        result = sentiment_analyzer(translated_text)[0][0]
        emotion = result["label"].lower()
        confidence = round(result["score"] * 100, 2)
        mood_category = EMOTION_TO_MOOD.get(emotion, "chill")

        return {
            "emotion":           emotion,
            "confidence":        confidence,
            "mood_category":     mood_category,
            "input_text":        text,            # ← YENİ: orijinal Türkçe metin
            "translated_text":   translated_text, # ← YENİ: AI'a verilen İngilizce
            "detected_language": detected_lang,   # ← YENİ: "tr", "en" ...
        }
    except Exception as e:
        raise ValueError(f"Metin analizi başarısız: {str(e)}")


def get_mood_features(mood_category: str) -> dict:
    return MOOD_TO_FEATURES.get(mood_category, MOOD_TO_FEATURES["chill"])