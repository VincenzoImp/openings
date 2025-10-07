FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    python-jobspy \
    pandas \
    openpyxl \
    matplotlib \
    seaborn

# Copy scripts
COPY scripts/ ./scripts/
COPY config/ ./config/

# Create results directory
RUN mkdir -p /app/results

# Set working directory to scripts
WORKDIR /app/scripts

CMD ["python", "search_jobs.py"]
