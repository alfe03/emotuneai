# MoodTune – Backend

AI destekli duygu tabanlı müzik öneri sisteminin backend servisi.

---

## Gereksinimler

- Python 3.11
- PostgreSQL 16+
- Spotify Developer hesabı

---

## Kurulum

### 1. Repoyu klonla

```bash
git clone https://github.com/kullanici-adin/emotuneai.git
cd moodtune/backend
```

### 2. Sanal ortam oluştur

```bash
py -3.11 -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

Mac / Linux:
```bash
source venv/bin/activate
```

### 3. Bağımlılıkları yükle

```bash
venv\Scripts\python -m pip install -r requirements.txt
```

### 4. Ortam değişkenlerini ayarla

```bash
cp .env.example .env
```

`.env` dosyasını aç ve şu alanları doldur:

```env
DATABASE_URL=postgresql://postgres:SIFREN@localhost:5432/moodtune
SPOTIFY_CLIENT_ID=spotify_client_id
SPOTIFY_CLIENT_SECRET=spotify_client_secret
SECRET_KEY=gizli-bir-key-yaz
```

> **Spotify API anahtarları:** https://developer.spotify.com/dashboard adresine gidip uygulama oluştur, oradan al.

### 5. Veritabanını oluştur

PostgreSQL kuruluyken:

```bash
# psql'e gir
psql -U postgres

# Veritabanı oluştur
CREATE DATABASE moodtune;
\q
```

Sonra tabloları oluştur:

```bash
alembic upgrade head
```

### 6. Sunucuyu başlat

```bash
uvicorn main:app --reload
```

Sunucu `http://localhost:8000` adresinde çalışmaya başlar.
API dokümantasyonu için: `http://localhost:8000/docs`

---

## Docker ile Çalıştırma (Opsiyonel)

Docker kuruluysa tek komutla her şeyi başlatabilirsin:

```bash
docker-compose up --build
```

Bu komut hem API'yi hem de PostgreSQL'i otomatik olarak başlatır.

---

## API Endpoint'leri

| Method | URL | Açıklama |
|--------|-----|----------|
| GET | `/` | Sunucu durumu |
| POST | `/api/mood/analyze/face` | Fotoğraftan duygu analizi |
| POST | `/api/mood/analyze/text` | Metinden duygu analizi |
| POST | `/api/mood/manual` | Manuel mood seçimi |
| POST | `/api/auth/register` | Kayıt ol |
| POST | `/api/auth/login` | Giriş yap |

---

## Proje Yapısı

```
backend/
├── main.py                  # Uygulama giriş noktası
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── app/
    ├── core/
    │   ├── config.py        # Ortam değişkenleri
    │   └── database.py      # Veritabanı bağlantısı
    ├── models/
    │   └── models.py        # Veritabanı tabloları
    ├── routers/
    │   ├── auth.py
    │   ├── mood.py
    │   ├── music.py
    │   └── history.py
    └── services/
        ├── mood_service.py      # DeepFace + HuggingFace
        └── spotify_service.py   # Spotify API
```

---

## Sık Karşılaşılan Hatalar

**`tensorflow` kurulamıyor**
Python versiyonunu kontrol et. TensorFlow yalnızca Python 3.11 ve altını destekler.
```bash
py -3.11 -m pip install -r requirements.txt
```

**`ModuleNotFoundError: No module named 'pkg_resources'`**
Bu hata bazı paketlerin build aşamasında eski `pkg_resources` API'sini kullanmasından kaynaklanır.
Projede bu yüzden `setuptools<81` sabitlendi. Elle düzeltmek için:
```bash
venv\Scripts\python -m pip install "setuptools<81"
venv\Scripts\python -m pip install -r requirements.txt
```

**`pg_config not found`**
PostgreSQL kurulu değil. https://www.postgresql.org/download adresinden kur.

**`connection refused` (veritabanı hatası)**
PostgreSQL servisinin çalıştığından emin ol:
```bash
# Windows
net start postgresql-x64-16

# Mac
brew services start postgresql
```
