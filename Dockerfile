# Job Search Tool - Docker Container (Multi-stage Build)
# Python 3.11 with job search dependencies
#
# Supports two modes:
# - Single-shot: Run once and exit (default, backward compatible)
# - Scheduled: Run continuously at configured intervals (set scheduler.enabled=true)

# =============================================================================
# Stage 1: Builder - Install dependencies with build tools
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /tmp

COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Stage 2: Runtime - Clean image without build tools
# =============================================================================
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser config/ ./config/

# Create output directories with correct ownership
RUN mkdir -p /app/results /app/data /app/logs \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set working directory to scripts
WORKDIR /app/scripts

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Timezone is now configurable via logging.timezone in settings.yaml
# or override with: docker run -e TZ=America/New_York ...
ENV TZ=UTC

# Health check - verifies imports, config, database, and directories
HEALTHCHECK --interval=5m --timeout=30s --start-period=60s --retries=3 \
    CMD python healthcheck.py

# Default command - uses main.py which handles both modes
CMD ["python", "main.py"]
