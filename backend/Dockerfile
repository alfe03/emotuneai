FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları (OpenCV için)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Güvenlik için appuser oluştur ve /app'e sahiplik ver
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Uygulama kodları
COPY --chown=appuser:appuser . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
