# syntax=docker/dockerfile:1.7
FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.11.6 AS uv
FROM python:3.12-slim-bookworm AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
COPY backend/ ./backend/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
ARG VERSION=0.8.0
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="Openings" \
      org.opencontainers.image.description="Your job search workspace" \
      org.opencontainers.image.source="https://github.com/VincenzoImp/openings" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"
RUN groupadd --gid 10001 openings \
    && useradd --uid 10001 --gid openings --no-create-home --shell /usr/sbin/nologin openings \
    && install -d -o openings -g openings /data /app/frontend /app/examples
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY --from=frontend /build/frontend/dist /app/frontend
COPY examples/ /app/examples/
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=UTC \
    OPENINGS_HOST=0.0.0.0 OPENINGS_PORT=8080 \
    OPENINGS_DATABASE=/data/openings.sqlite \
    OPENINGS_FRONTEND=/app/frontend OPENINGS_EXAMPLES=/app/examples
USER 10001:10001
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
ENTRYPOINT ["openings"]
