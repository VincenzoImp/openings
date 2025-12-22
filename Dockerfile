# JobSpy Dashboard - Docker Container
# Python 3.11 with job search dependencies

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scripts/ ./scripts/
COPY config/ ./config/

# Create output directories
RUN mkdir -p /app/results /app/data /app/logs

# Set working directory to scripts
WORKDIR /app/scripts

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command
CMD ["python", "search_jobs.py"]
