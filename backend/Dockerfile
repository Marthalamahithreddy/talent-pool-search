# =============================================================
# FILE: backend/Dockerfile
# PURPOSE: Production Docker image for the FastAPI backend.
#          Used when deploying to Railway, Render, or any
#          container hosting platform.
#
# Build:  docker build -t talent-pool-backend .
# Run:    docker run -p 8000:8000 --env-file .env talent-pool-backend
# =============================================================

FROM python:3.11-slim

WORKDIR /app

# Install OS dependencies needed by PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port and start with uvicorn
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
