FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    PIP_DEFAULT_TIMEOUT=300

COPY requirements.txt .
# Connexions lentes / PyPI instable : évite ReadTimeoutError sur gros wheels (ex. pycryptodome)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --default-timeout=300 --retries=10 -r requirements.txt

COPY . .

RUN mkdir -p /app/storage

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
