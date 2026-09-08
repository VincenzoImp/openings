# syntax=docker/dockerfile:1.7
#
# Openings — one image, two roles:
#   openings scheduler   collects on the configured interval
#   openings web         dashboard, REST API and MCP endpoint
#
# All persistent state lives under /data. Mount it and mount settings.yaml at
# /data/config/settings.yaml.

FROM ghcr.io/astral-sh/uv:0.11.6 AS uv

# ---------------------------------------------------------------------------
# Frontend: build the dashboard into static assets
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Python dependencies into a pruned virtual environment
# ---------------------------------------------------------------------------
FROM python:3.11.12-slim AS builder

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY config/settings.example.yaml /opt/openings/defaults/settings.example.yaml
COPY docker/entrypoint.sh /usr/local/bin/openings-entrypoint

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev \
    && find /app/.venv -depth \
         \( -type d \( -name __pycache__ -o -name tests -o -name test \) \
            -o -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyi' \) \
         \) -exec rm -rf {} +

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM python:3.11.12-slim AS runtime

ARG BUILD_DATE=unknown
ARG VCS_REF=unknown
ARG VERSION=dev

LABEL org.opencontainers.image.title="Openings" \
      org.opencontainers.image.description="A configurable job crawler, archive and application tracker you run yourself." \
      org.opencontainers.image.url="https://github.com/VincenzoImp/openings" \
      org.opencontainers.image.source="https://github.com/VincenzoImp/openings" \
      org.opencontainers.image.documentation="https://github.com/VincenzoImp/openings#readme" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}"

RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash appuser \
    && install -d -o appuser -g appuser \
        /app \
        /data /data/config /data/db /data/attachments /data/chroma /data/logs \
        /opt/openings/defaults \
        /opt/openings/frontend

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src
COPY --from=builder --chown=appuser:appuser /opt/openings/defaults/settings.example.yaml /opt/openings/defaults/settings.example.yaml
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist /opt/openings/frontend
COPY --from=builder /usr/local/bin/openings-entrypoint /usr/local/bin/openings-entrypoint
RUN chmod +x /usr/local/bin/openings-entrypoint

USER appuser

ENV PATH=/app/.venv/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV OPENINGS_DATA_DIR=/data
ENV OPENINGS_TEMPLATE_PATH=/opt/openings/defaults/settings.example.yaml
ENV TZ=UTC
# ChromaDB telemetry off, with a local no-op client so no PostHog code runs.
ENV ANONYMIZED_TELEMETRY=False
ENV CHROMA_PRODUCT_TELEMETRY_IMPL=openings.chroma_telemetry.NoOpProductTelemetryClient
ENV CHROMA_TELEMETRY_IMPL=openings.chroma_telemetry.NoOpProductTelemetryClient

VOLUME ["/data"]

HEALTHCHECK --interval=5m --timeout=30s --start-period=60s --retries=3 \
    CMD openings-healthcheck

ENTRYPOINT ["/usr/bin/tini", "--", "openings-entrypoint"]
CMD ["openings", "scheduler"]
