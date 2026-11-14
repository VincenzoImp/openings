# syntax=docker/dockerfile:1.7
FROM node:26-bookworm-slim@sha256:5df79989ed685e09f0a98019db4cebfb22fb9df1a53c0161664a011f7ff6b0f1 AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
# The dashboard only: the design system gallery (ui.html) is for the browser tests.
RUN npm run build -- --mode dashboard

FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv
FROM python:3.14-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# The locked dependencies first, so a change of the code alone reuses their layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --no-install-project
COPY README.md ./
COPY backend/ ./backend/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

FROM python:3.14-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b AS runtime
ARG VERSION=0.24.2
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="Openings" \
      org.opencontainers.image.description="A self-hosted job-search workspace: collect jobs, prepare applications and track replies, by hand or with your own AI agent." \
      org.opencontainers.image.source="https://github.com/VincenzoImp/openings" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"
RUN groupadd --gid 10001 openings \
    && useradd --uid 10001 --gid openings --no-create-home --shell /usr/sbin/nologin openings \
    && install -d -o openings -g openings /data /app/frontend /app/examples /app/skills
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY --from=frontend /build/frontend/dist /app/frontend
COPY examples/ /app/examples/
COPY skills/ /app/skills/
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=UTC \
    OPENINGS_HOST=0.0.0.0 OPENINGS_PORT=8080 \
    OPENINGS_DATABASE=/data/openings.sqlite \
    OPENINGS_FRONTEND=/app/frontend OPENINGS_EXAMPLES=/app/examples \
    OPENINGS_SKILLS=/app/skills
USER 10001:10001
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
ENTRYPOINT ["openings"]
