# syntax=docker/dockerfile:1.7

# Job Search Tool — Docker container
#
# Single image containing the scheduler, the Streamlit dashboard, and every
# runtime dependency. The same image runs both Compose services; the two
# differ only by their command (scheduler loop vs Streamlit UI).
#
# Everything persistent (config, database, vector store, results, logs) lives
# under a single volume at /data. Mount it and that's it.

FROM ghcr.io/astral-sh/uv:0.11.6 AS uv

# =============================================================================
# Builder — install dependencies into a pruned .venv
# =============================================================================
# NOTE: Pin to a specific patch version for reproducible builds.
FROM python:3.11.12-slim AS builder

WORKDIR /app

COPY --from=uv /uv /uvx /bin/

ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY scripts/ ./scripts/
COPY config/settings.example.yaml /opt/job-search-tool/defaults/settings.example.yaml
COPY docker/entrypoint.sh /usr/local/bin/job-search-entrypoint

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project \
    && find /app/.venv -depth \
         \( -type d \( -name __pycache__ -o -name tests -o -name test \) \
            -o -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyi' \) \
         \) -exec rm -rf {} +

# =============================================================================
# Runtime — single stage used by both the scheduler and the dashboard
# =============================================================================
FROM python:3.11.12-slim AS runtime

ARG BUILD_DATE=unknown
ARG VCS_REF=unknown
ARG VERSION=dev

LABEL org.opencontainers.image.title="Job Search Tool" \
      org.opencontainers.image.description="Automated job search aggregation, scoring, notifications, and dashboard tooling." \
      org.opencontainers.image.url="https://github.com/VincenzoImp/job-search-tool" \
      org.opencontainers.image.source="https://github.com/VincenzoImp/job-search-tool" \
      org.opencontainers.image.documentation="https://github.com/VincenzoImp/job-search-tool#readme" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}"

# tini provides clean SIGTERM propagation to the Python process (it becomes PID 1).
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash appuser \
    && install -d -o appuser -g appuser \
        /app \
        /data /data/config /data/db /data/chroma /data/results /data/logs \
        /opt/job-search-tool/defaults

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/scripts /app/scripts
COPY --from=builder --chown=appuser:appuser /opt/job-search-tool/defaults/settings.example.yaml /opt/job-search-tool/defaults/settings.example.yaml
COPY --from=builder /usr/local/bin/job-search-entrypoint /usr/local/bin/job-search-entrypoint

RUN chmod +x /usr/local/bin/job-search-entrypoint

# Run as a non-root user for defence-in-depth. /data is pre-created in the
# layer above with appuser ownership so the matching named volume inherits
# the same permissions on first mount.
USER appuser
WORKDIR /app/scripts

ENV PATH=/app/.venv/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# /data is the single root for all persistent state. Override with
#   docker run -e JOB_SEARCH_DATA_DIR=/custom ... -v /host/path:/custom ...
ENV JOB_SEARCH_DATA_DIR=/data
ENV JOB_SEARCH_TEMPLATE_PATH=/opt/job-search-tool/defaults/settings.example.yaml
# Timezone is configurable via logging.timezone in settings.yaml
# or override with: docker run -e TZ=America/New_York ...
ENV TZ=UTC

VOLUME ["/data"]

HEALTHCHECK --interval=5m --timeout=30s --start-period=60s --retries=3 \
    CMD python healthcheck.py

ENTRYPOINT ["/usr/bin/tini", "--", "job-search-entrypoint"]
CMD ["python", "main.py"]
