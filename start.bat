@echo off
echo EmoTuneAı Backend başlatılıyor...

:: PostgreSQL'i başlat
start "PostgreSQL" "C:\Program Files\PostgreSQL\18\bin\postgres.exe" -D "C:\Program Files\PostgreSQL\18\data"

:: 8 saniye bekle
timeout /t 8 /nobreak

:: Tarayıcıyı aç
start "" "http://localhost:8000/docs"

:: Backend'i başlat
cd /d "%~dp0"
cd backend
call venv\Scripts\activate
set PATH=%PATH%;C:\Program Files\PostgreSQL\18\bin
python -m uvicorn main:app --reload

pause