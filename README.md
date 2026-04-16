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

### 6. Uygulamayı Başlat

Proje içerisinde işinizi kolaylaştırmak için iki adet kısayol `.bat` dosyası bulunmaktadır:

1. **Backend İçin (`start.bat`)**: Çift tıklayarak PostgreSQL'i ve FastAPI backend'i başlatabilirsiniz. Sunucu `localhost:8000` üzerinde açılır ve tarayıcınızda otomatik olarak API dokümantasyonu (Swagger) belirir.
2. **Frontend İçin (`start_frontend.bat`)**: Çift tıklayarak frontend arayüzü için yerel bir HTTP sunucusu başlatabilirsiniz. Çalıştığında `http://localhost:8080` üzerinden EmoTuneAI arayüzünü inceleyebilirsiniz.

> **Manuel başlatmak isterseniz:**
> Backend: `venv\Scripts\python -m uvicorn main:app --reload` (backend klasöründe)
> Frontend: `venv\Scripts\python -m http.server 8080` (frontend klasöründe)

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
emotuneai/
├── start.bat                # Backend'i başlatma scripti
├── start_frontend.bat       # Frontend'i başlatma scripti
├── backend/                 # FastAPI & PostgreSQL Backend Servisi
│   ├── main.py
│   ├── requirements.txt
│   └── app/
│       └── ...
└── frontend/                # HTML, CSS, JS Saf Web Arayüzü
    ├── index.html
    ├── css/
    └── js/
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
