FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for OpenCV and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from root directory of backend/validation_and_tampering
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all contents of validation_and_tampering into app structure
COPY . ./backend/validation_and_tampering/
COPY ./validation_service ./backend/validation_service
COPY ./tampering_service ./backend/tampering_service
COPY logging_config.py ./backend/logging_config.py
COPY config.py ./backend/config.py

ENV PYTHONPATH=/app

# Start unified validation & tampering service
CMD exec uvicorn backend.validation_and_tampering.main:app --host 0.0.0.0 --port ${PORT:-8000}
