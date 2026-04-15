# syntax=docker/dockerfile:1.7

# Job Search Tool — Docker container
#
# Two variants, selected via the `VARIANT` build arg:
#   VARIANT=dashboard (default) — full image with Streamlit UI
#   VARIANT=core                — slim image, no Streamlit (~200 MB smaller)
#
# Build examples:
#   docker build -t job-search-tool .                              # dashboard
#   docker build --build-arg VARIANT=core -t job-search-tool:core .

ARG VARIANT=dashboard

FROM ghcr.io/astral-sh/uv:0.11.6 AS uv

# =============================================================================
# Builder base — tooling, sources, lockfile. No dependency install yet.
# =============================================================================
# NOTE: Pin to a specific patch version for reproducible builds.
FROM python:3.11.12-slim AS builder-base

WORKDIR /app

COPY --from=uv /uv /uvx /bin/

ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY scripts/ ./scripts/
COPY config/settings.example.yaml ./config/settings.example.yaml
COPY config/settings.example.yaml /opt/job-search-tool/defaults/settings.example.yaml
COPY docker/entrypoint.sh /usr/local/bin/job-search-entrypoint

# =============================================================================
# Variant builders — install deps into `.venv`, then prune.
# =============================================================================
FROM builder-base AS builder-core

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project \
    && find /app/.venv -depth \
         \( -type d \( -name __pycache__ -o -name tests -o -name test \) \
            -o -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyi' \) \
         \) -exec rm -rf {} +

FROM builder-base AS builder-dashboard

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --extra dashboard \
    && find /app/.venv -depth \
         \( -type d \( -name __pycache__ -o -name tests -o -name test \) \
            -o -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyi' \) \
         \) -exec rm -rf {} +

# =============================================================================
# Variant selector — resolves `builder-${VARIANT}` via the global ARG.
# =============================================================================
FROM builder-${VARIANT} AS builder-final

# =============================================================================
# Runtime — single stage, variant-agnostic (differs only by what was installed
# into /app/.venv in the builder stage).
# =============================================================================
FROM python:3.11.12-slim AS runtime

ARG BUILD_DATE=unknown
ARG VCS_REF=unknown
ARG VERSION=dev
ARG VARIANT=dashboard

LABEL org.opencontainers.image.title="Job Search Tool" \
      org.opencontainers.image.description="Automated job search aggregation, scoring, notifications, and dashboard tooling." \
      org.opencontainers.image.url="https://github.com/VincenzoImp/job-search-tool" \
      org.opencontainers.image.source="https://github.com/VincenzoImp/job-search-tool" \
      org.opencontainers.image.documentation="https://github.com/VincenzoImp/job-search-tool#readme" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.variant="${VARIANT}"

RUN useradd -m -u 1000 -s /bin/bash appuser \
    && install -d -o appuser -g appuser \
        /app /app/results /app/data /app/data/chroma /app/logs \
        /opt/job-search-tool/defaults

WORKDIR /app

COPY --from=builder-final --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder-final --chown=appuser:appuser /app/scripts /app/scripts
COPY --from=builder-final --chown=appuser:appuser /app/config/settings.example.yaml /app/config/settings.example.yaml
COPY --from=builder-final --chown=appuser:appuser /opt/job-search-tool/defaults/settings.example.yaml /opt/job-search-tool/defaults/settings.example.yaml
COPY --from=builder-final /usr/local/bin/job-search-entrypoint /usr/local/bin/job-search-entrypoint

RUN chmod +x /usr/local/bin/job-search-entrypoint

USER appuser
WORKDIR /app/scripts

ENV PATH=/app/.venv/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV JOB_SEARCH_CONFIG=/app/config/settings.yaml
ENV JOB_SEARCH_TEMPLATE_PATH=/opt/job-search-tool/defaults/settings.example.yaml
# Timezone is configurable via logging.timezone in settings.yaml
# or override with: docker run -e TZ=America/New_York ...
ENV TZ=UTC

HEALTHCHECK --interval=5m --timeout=30s --start-period=60s --retries=3 \
    CMD python healthcheck.py

ENTRYPOINT ["job-search-entrypoint"]
CMD ["python", "main.py"]
