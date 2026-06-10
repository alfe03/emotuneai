@echo off
setlocal EnableDelayedExpansion
title EmoTuneAI

echo.
echo  ================================================
echo   EmoTuneAI - Baslatiliyor...
echo  ================================================
echo.

:: ── Proje kök dizinine git ──────────────────────────────
cd /d "%~dp0"

:: ── venv kontrolü ────────────────────────────────────────
if not exist "backend\venv\Scripts\python.exe" (
    echo [HATA] backend\venv bulunamadi.
    echo        Lutfen once su komutu calistirin:
    echo        py -3.11 -m venv backend\venv
    echo        backend\venv\Scripts\python -m pip install -r backend\requirements.txt
    pause
    exit /b 1
)

:: ── .env kontrolü ────────────────────────────────────────
if not exist "backend\.env" (
    echo [HATA] backend\.env dosyasi bulunamadi.
    echo        backend\.env.example dosyasini kopyalayip doldurun.
    pause
    exit /b 1
)

:: ── PostgreSQL yolunu bul (sürümden bağımsız) ───────────
set PG_BIN=
for /d %%v in ("C:\Program Files\PostgreSQL\*") do (
    if exist "%%v\bin\pg_isready.exe" set PG_BIN=%%v\bin
)

if defined PG_BIN (
    echo [PostgreSQL] Kontrol ediliyor: %PG_BIN%
    "%PG_BIN%\pg_isready.exe" -q
    if errorlevel 1 (
        echo [PostgreSQL] Servis baslatiliyor...
        net start postgresql-x64-16 >nul 2>&1
        net start postgresql-x64-17 >nul 2>&1
        net start postgresql-x64-18 >nul 2>&1
        timeout /t 3 /nobreak >nul
    ) else (
        echo [PostgreSQL] Zaten calisiyor.
    )
) else (
    echo [UYARI] PostgreSQL bulunamadi. Servisin calistigindan emin olun.
)

:: ── Frontend'i arka planda başlat ───────────────────────
echo.
echo [Frontend] http://localhost:8080 adresinde baslatiliyor...
start "EmoTuneAI Frontend" /min cmd /c ^
    "cd /d "%~dp0frontend" && ..\backend\venv\Scripts\python.exe -m http.server 8080"

timeout /t 2 /nobreak >nul

:: ── Tarayıcıyı aç ────────────────────────────────────────
echo [Tarayici] http://localhost:8080 aciliyor...
start "" "http://localhost:8080"

:: ── Backend'i bu pencerede başlat ────────────────────────
echo.
echo [Backend]  http://localhost:8000 adresinde baslatiliyor...
echo            API Docs: http://localhost:8000/docs
echo.
echo  Durdurmak icin: CTRL+C
echo  ================================================
echo.

cd backend
call venv\Scripts\activate
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

pause