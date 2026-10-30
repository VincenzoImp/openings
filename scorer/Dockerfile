FROM python:3.12-slim-bookworm
ARG VERSION=0.5.2
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="Openings CPU scorer" \
      org.opencontainers.image.description="Optional local CPU classification for Openings" \
      org.opencontainers.image.source="https://github.com/VincenzoImp/openings" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 USE_TF=0 HF_HOME=/cache/huggingface OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
WORKDIR /app
RUN pip install --no-cache-dir 'torch==2.15.0+cpu' --index-url https://download.pytorch.org/whl/cpu
COPY scorer/requirements.txt /app/requirements.txt
COPY scorer/constraints.txt /app/constraints.txt
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt && useradd --create-home --uid 1000 scorer && mkdir -p /cache/huggingface && chown -R scorer:scorer /cache /app
COPY --chown=scorer:scorer scorer/app.py /app/app.py
USER scorer
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "4"]
