FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libffi-dev \
    tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "-b", "0.0.0.0:8000", "main:app"]
