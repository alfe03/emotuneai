import sys
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
load_dotenv('c:/Users/Cemil/Desktop/emotuneai/backend/.env')
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

GEMINI_MOOD_PROMPT = """Sen bir duygu analizi uzmanısın. Kullanıcının yazdığı metni analiz et ve ruh halini belirle.

## Ruh Hali Kategorileri (mood_category)
Aşağıdaki 5 kategoriden BİRİNİ seç:
- "energetic" -> Mutlu, enerjik, heyecanlı, neşeli, coşkulu, motive, eğlenceli, kendini iyi hisseden
- "chill" -> Rahat, huzurlu, keyifli, tatmin olmuş, dingin, gevşemiş, kafası rahat
- "melancholic" -> Üzgün, hüzünlü, nostaljik, duygusal, kırık, yalnız, özlem dolu, içi buruk
- "intense" -> Öfkeli, sinirli, agresif, gergin, isyankâr, patlayacak gibi, sıkılmış, bunalmış
- "calm" -> Sakinleşmek isteyen, endişeli, kaygılı, tedirgin, yorgun, stresli ama rahatlamaya ihtiyacı var

## Duygu Etiketi (emotion)
"emotion" alanında basit tek kelime YAZMA. Bunun yerine kullanıcının hissini en iyi özetleyen kısa ve samimi bir Türkçe ifade yaz.

Örnekler:
- "Mutlu ve enerjik" ✅  (sadece "mutlu" ❌)
- "Nostaljik ve hüzünlü" ✅  (sadece "üzgün" ❌)
- "Yorgun ama huzurlu" ✅  (sadece "sakin" ❌)
- "Sinirli ve gergin" ✅  (sadece "kızgın" ❌)

## Emoji
Duyguyu en iyi yansıtan tek bir emoji seç.

## Sanatçı/Şarkıcı Tespiti (requested_artist)
Kullanıcı metninde belirli bir sanatçı, şarkıcı veya grup adı belirterek şarkı önerisi istemişse (örn: "Duman çal"), bu sanatçı/grup adının yalın halini "requested_artist" alanına yaz. Eğer herhangi bir sanatçı/grup adı belirtilmemişse null yap.

## Kurallar
1. Cümlenin genel anlamına, duygusal tonuna ve alt metnine odaklan.
2. Karmaşık veya çelişkili duygular varsa ikisini de yansıt.
3. Sadece JSON formatında yanıt ver, başka hiçbir şey yazma.

JSON formatı:
{
  "emotion": "kullanıcının hissini özetleyen kısa ve açıklayıcı Türkçe ifade (2-4 kelime)",
  "emoji": "duyguyu yansıtan tek emoji",
  "confidence": 0-100 arası güven skoru (sayı),
  "mood_category": "energetic | chill | melancholic | intense | calm",
  "explanation": "Neden bu kategoriyi seçtiğini kısa ve samimi bir şekilde açıkla",
  "requested_artist": "tespit edilen sanatçı/grup adı (string) veya null"
}

Kullanıcının metni: """

text = 'Kendimi bugün çok iyi hissetmiyorum.'
prompt = GEMINI_MOOD_PROMPT + f'"{text}"'

model = genai.GenerativeModel('gemini-3.5-flash')
try:
    response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(response_mime_type='application/json'))
    with open('gemini_output.txt', 'w', encoding='utf-8') as f:
        f.write(response.text)
except Exception as e:
    with open('gemini_output.txt', 'w', encoding='utf-8') as f:
        f.write('ERROR: ' + str(e))
