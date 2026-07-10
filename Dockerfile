FROM python:3.11-slim

# Tesseract OCR system binary + English language data. This is exactly what
# Render's native Python runtime cannot install (no apt-get access) - the
# reason this Docker-based service exists at all.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installs from the same file Render already uses for the native deploy -
# nothing about your existing dependency list changes.
COPY optionA.txt .
RUN pip install --no-cache-dir -r optionA.txt

COPY . .

# Render sets $PORT at runtime; must bind 0.0.0.0, not 127.0.0.1
EXPOSE 10000
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]