@echo off
echo EmoTuneAI Frontend Baslatiliyor...
echo.
echo Lutfen tarayicinizdan su adrese gidin: http://localhost:8080
echo.
cd "%~dp0frontend"
..\backend\venv\Scripts\python.exe -m http.server 8080
pause
