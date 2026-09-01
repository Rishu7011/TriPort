FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PDF and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and install
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase
COPY backend/ ./backend/

ENV PYTHONPATH=/app
ENV LLM_PROVIDER=local

CMD exec uvicorn backend.ocr_service.main:app --host 0.0.0.0 --port ${PORT:-8001}
