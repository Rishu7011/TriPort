FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PDF and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and install
COPY backend/ocr_service/requirements-render.txt ./requirements-render.txt
RUN pip install --no-cache-dir -r requirements-render.txt

# Copy backend codebase
COPY backend/ ./backend/

ENV PYTHONPATH=/app
ENV LLM_PROVIDER=gemini
ENV LLM_MODEL=gemini-3.5-flash-lite

# Render dynamic port binding
CMD exec uvicorn backend.ocr_service.main:app --host 0.0.0.0 --port ${PORT:-8001}
