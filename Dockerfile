FROM python:3.11-slim

# 安裝必需套件與 tesseract
RUN apt-get update && \
    apt-get install -y gcc build-essential libffi-dev \
    tesseract-ocr tesseract-ocr-chi-tra \
    libgl1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8080"]
