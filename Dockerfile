FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    python-jobspy \
    pandas \
    openpyxl \
    pyyaml \
    matplotlib \
    seaborn

# Copy project files
COPY scripts/ ./scripts/
COPY config/ ./config/

# Create results directory
RUN mkdir -p /app/results

# Set working directory to scripts
WORKDIR /app/scripts

# Default command
CMD ["python", "search_jobs.py"]
