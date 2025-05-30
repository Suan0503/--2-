FROM python:3.11-slim

# 安裝系統套件與 Tesseract OCR
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libffi-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    tesseract-ocr-chi-tra \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# 使用 gunicorn 啟動 Flask App（port 由 Railway 控管）
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "main:app"]
