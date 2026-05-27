# Build stage: install dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps required by osmnx / networkx (gdal/proj are heavy; osmnx uses pyproj)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only the package manifest first — preserves pip install cache layer
COPY pyproject.toml .
# Stub src so pip can resolve the editable install metadata without the full source
RUN mkdir -p src/traffic_engine && touch src/traffic_engine/__init__.py

# Install runtime dependencies (cached unless pyproject.toml changes)
RUN pip install --no-cache-dir --prefix=/install .


# Runtime stage: lean image
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-c1v5 \
    libproj25 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user created before any COPY to keep layers minimal
RUN useradd --no-create-home --shell /bin/false appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=appuser:appuser src/ src/

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# WEB_CONCURRENCY defaults to 1; override at runtime (e.g. -e WEB_CONCURRENCY=4)
CMD ["sh", "-c", "uvicorn traffic_engine.api.app:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1}"]
