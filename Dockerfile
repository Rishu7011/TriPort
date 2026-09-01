FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for OpenCV and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/validation_and_tampering/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase
COPY backend/ ./backend/

ENV PYTHONPATH=/app

# Start unified validation & tampering service for Render deployment
CMD exec uvicorn backend.validation_and_tampering.main:app --host 0.0.0.0 --port ${PORT:-8000}
