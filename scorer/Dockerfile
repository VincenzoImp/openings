FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 USE_TF=0 HF_HOME=/cache/huggingface OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
WORKDIR /app
RUN pip install --no-cache-dir 'torch==2.15.0+cpu' --index-url https://download.pytorch.org/whl/cpu
COPY scorer/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 1000 scorer && mkdir -p /cache/huggingface && chown -R scorer:scorer /cache /app
COPY --chown=scorer:scorer scorer/app.py /app/app.py
USER scorer
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "4"]
