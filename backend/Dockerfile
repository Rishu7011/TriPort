FROM python:3.11-slim

WORKDIR /app

# System deps: curl (healthchecks), libGL (OpenCV), libgomp (PaddleOCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend package (imports use `backend.*`)
COPY backend/ ./backend/

ENV PYTHONPATH=/app

# Default CMD is overridden per-service in docker-compose.yml
CMD ["uvicorn", "backend.orchestrator.main:app", "--host", "0.0.0.0", "--port", "8007"]
