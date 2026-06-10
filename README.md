# EmoTuneAI

AI destekli yüz ve duygu analizine dayalı müzik öneri sistemi.
Bu depo hem Backend'i (FastAPI & PostgreSQL) hem de Frontend'i (HTML, CSS, JS) içermektedir.

---

## Gereksinimler

- Python 3.11
- PostgreSQL 16+
- Spotify Developer hesabı

---

## Kurulum

### 1. Repoyu klonla

```bash
git clone https://github.com/alfe03/emotuneai.git
cd emotuneai
```

### 2. Ortam değişkenlerini ayarla

```bash
cp backend/.env.example backend/.env
```

`backend/.env` dosyasını aç ve şu alanları doldur:

```env
DATABASE_URL=postgresql://postgres:sifren@localhost:5432/emotune
SPOTIFY_CLIENT_ID=spotify_client_id
SPOTIFY_CLIENT_SECRET=spotify_client_secret
SECRET_KEY=gizli-bir-key-yaz
GEMINI_API_KEY=gemini_api_key
FRONTEND_URL=http://127.0.0.1:8080/index.html
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/auth/spotify/callback
CORS_ORIGINS=http://127.0.0.1:8080,http://localhost:8080
```

> **Spotify API anahtarları:** https://developer.spotify.com/dashboard
> **Gemini API Key:** https://ai.google.dev

---

## Çalıştırma

### Yöntem 1: start.bat (Yerel Geliştirme)

Sanal ortamı bir kere oluştur:

```bash
py -3.11 -m venv backend\venv
backend\venv\Scripts\python -m pip install -r backend\requirements.txt
```

Sonra çift tıkla:

```
start.bat
```

Bu script otomatik olarak:
- PostgreSQL servisini kontrol eder ve gerekirse başlatır (sürümden bağımsız)
- Frontend'i `http://localhost:8080` üzerinde başlatır
- Backend'i `http://localhost:8000` üzerinde başlatır
- Tarayıcıyı otomatik açar

### Yöntem 2: Docker Compose (Tavsiye Edilen)

Docker kuruluysa tek komutla tüm stack ayağa kalkar:

```bash
docker-compose up --build
```

Bu komut şunları başlatır:
- **PostgreSQL** → `localhost:5432`
- **Backend (FastAPI)** → `http://localhost:8000`
- **Frontend (nginx)** → `http://localhost:8080`

Durdurmak için:

```bash
docker-compose down
```

Veritabanı verileriyle birlikte tamamen temizlemek için:

```bash
docker-compose down -v
```

---

## Adresler

| Servis | URL |
|--------|-----|
| Frontend | http://localhost:8080 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

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
emotuneai/
├── start.bat               # Tek tıkla başlatma scripti (yerel)
├── docker-compose.yml      # Tam stack Docker yapılandırması
├── nginx.conf              # Frontend nginx yapılandırması
├── backend/                # FastAPI & PostgreSQL Backend
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── app/
│       └── ...
└── frontend/               # HTML, CSS, JS Arayüzü
    ├── index.html
    ├── css/
    └── js/
```

---

## Sık Karşılaşılan Hatalar

**`tensorflow` kurulamıyor**
Python versiyonunu kontrol et. TensorFlow yalnızca Python 3.11 ve altını destekler.
```bash
py -3.11 -m pip install -r backend\requirements.txt
```

**`ModuleNotFoundError: No module named 'pkg_resources'`**
```bash
backend\venv\Scripts\python -m pip install "setuptools<81"
backend\venv\Scripts\python -m pip install -r backend\requirements.txt
```

**`pg_config not found`**
PostgreSQL kurulu değil. https://www.postgresql.org/download adresinden kur.

**`connection refused` (veritabanı hatası)**
PostgreSQL servisinin çalıştığından emin ol:
```bash
# Windows
net start postgresql-x64-16
```
