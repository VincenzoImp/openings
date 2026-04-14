# Job Search Tool - Docker Container (Multi-stage Build)
# Python 3.11 with job search dependencies
#
# Supports two modes:
# - Single-shot: Run once and exit (default, backward compatible)
# - Scheduled: Run continuously at configured intervals (set scheduler.enabled=true)

# =============================================================================
# Stage 1: Builder - Install dependencies with build tools
# =============================================================================
# NOTE: Pin to a specific patch version for reproducible builds.
# TODO: Consider using --require-hashes in pip install for supply-chain security.
FROM python:3.11.12-slim AS builder

ARG TORCH_VERSION=2.10.0

WORKDIR /tmp

COPY requirements.txt .

# Keep the published image CPU-only unless users intentionally build their own GPU variant.
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && pip install --no-cache-dir --prefix=/install \
        --index-url https://download.pytorch.org/whl/cpu \
        torch=="${TORCH_VERSION}" \
    && PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu \
        pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Stage 2: Runtime - Clean image without build tools
# =============================================================================
FROM python:3.11.12-slim

ARG BUILD_DATE=unknown
ARG VCS_REF=unknown
ARG VERSION=dev

# OCI image metadata
LABEL org.opencontainers.image.title="Job Search Tool" \
      org.opencontainers.image.description="Automated job search aggregation, scoring, notifications, and dashboard tooling." \
      org.opencontainers.image.url="https://github.com/VincenzoImp/job-search-tool" \
      org.opencontainers.image.source="https://github.com/VincenzoImp/job-search-tool" \
      org.opencontainers.image.documentation="https://github.com/VincenzoImp/job-search-tool#readme" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}"

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser config/settings.example.yaml ./config/settings.example.yaml
COPY --chown=appuser:appuser config/settings.example.yaml /opt/job-search-tool/defaults/settings.example.yaml
COPY docker/entrypoint.sh /usr/local/bin/job-search-entrypoint

# Create output directories with correct ownership
RUN chmod +x /usr/local/bin/job-search-entrypoint \
    && mkdir -p /app/results /app/data /app/data/chroma /app/logs /opt/job-search-tool/defaults \
    && chown -R appuser:appuser /app /opt/job-search-tool

# Switch to non-root user
USER appuser

# Set working directory to scripts
WORKDIR /app/scripts

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV JOB_SEARCH_CONFIG=/app/config/settings.yaml
ENV JOB_SEARCH_TEMPLATE_PATH=/opt/job-search-tool/defaults/settings.example.yaml
# Timezone is now configurable via logging.timezone in settings.yaml
# or override with: docker run -e TZ=America/New_York ...
ENV TZ=UTC

# Health check - verifies imports, config, database, and directories
HEALTHCHECK --interval=5m --timeout=30s --start-period=60s --retries=3 \
    CMD python healthcheck.py

ENTRYPOINT ["job-search-entrypoint"]

# Default command - uses main.py which handles both modes
CMD ["python", "main.py"]
