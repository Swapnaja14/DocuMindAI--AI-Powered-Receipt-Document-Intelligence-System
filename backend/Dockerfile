# ==============================================================================
# Multi-Stage Hardened Production Dockerfile for DocuMind AI Backend
# Enforces non-root execution, minimal attack surface, and security hardening.
# ==============================================================================

# Stage 1: Build & Dependency Wheel Cache
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies required for compiling C extensions (argon2, faiss, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt


# Stage 2: Hardened Runtime Container
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Install minimal runtime libraries (libgomp for FAISS CPU, tesseract for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    DEBUG=false

# Create unprivileged system user and group (UID/GID 10001)
RUN groupadd -g 10001 documind && \
    useradd -u 10001 -g documind -d /app -s /bin/false documind

# Create storage directories and set least-privilege permissions
RUN mkdir -p /app/storage/uploads /app/storage/faiss /app/storage/backups /tmp && \
    chown -R documind:documind /app/storage /tmp && \
    chmod 750 /app/storage /app/storage/uploads /app/storage/faiss /app/storage/backups

# Copy application code
COPY --chown=documind:documind . /app

# Switch to non-root user
USER documind

# Expose internal API port
EXPOSE 8000

# Container liveness health check
HEALTHCHECK --interval=20s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health/live || exit 1

# Launch production server via Uvicorn with single process per container (concurrency via orchestration)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
