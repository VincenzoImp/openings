# Job Search Tool - Docker Container
# Python 3.11 with job search dependencies
#
# Supports two modes:
# - Single-shot: Run once and exit (default, backward compatible)
# - Scheduled: Run continuously at configured intervals (set scheduler.enabled=true)

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
COPY templates/ ./templates/

# Create output directories
RUN mkdir -p /app/results /app/data /app/logs

# Set working directory to scripts
WORKDIR /app/scripts

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=Europe/Zurich

# Health check for scheduled mode
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command - uses main.py which handles both modes
CMD ["python", "main.py"]
