# syntax=docker/dockerfile:1.7
#
# traffic-engine API — multi-stage build
#
# Stages:
#   builder  installs runtime deps into an isolated venv (/opt/venv)
#   test     extends builder with dev deps and runs the full pytest suite.
#            Touches /opt/build-meta/tests-passed only on success.
#   runtime  slim production image. COPYs the marker from `test`, which
#            forces Docker to build (and pass) the test stage before the
#            runtime image can be produced. A failing test fails the build.
#
# Build:
#   docker build -t traffic-engine:latest .
#
# Build only the test stage (useful in CI):
#   docker build --target test -t traffic-engine:test .

ARG PYTHON_VERSION=3.11

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Native deps required to compile wheels for osmnx, shapely, rtree, etc.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      libgeos-dev \
      libspatialindex-dev \
      curl \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV"

# Copy only what install needs first, to keep the deps layer cacheable.
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --upgrade pip \
 && pip install .

# ---------------------------------------------------------------------------
# Stage 2: test  (build gate — pytest must pass before runtime can build)
# ---------------------------------------------------------------------------
FROM builder AS test

RUN pip install ".[dev]"

COPY pytest.ini ./
COPY tests/ ./tests/

# pytest exit code propagates; marker is only created on success.
RUN pytest \
 && mkdir -p /opt/build-meta \
 && touch /opt/build-meta/tests-passed

# ---------------------------------------------------------------------------
# Stage 3: runtime  (slim production image)
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000 \
    UVICORN_WORKERS=2

WORKDIR /app

# Runtime-only native libs (no -dev packages, no compilers).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libgeos-c1v5 \
      libspatialindex6 \
      curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd  --system --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

# Bring in the venv with the installed package.
COPY --from=builder /opt/venv /opt/venv

# Test gate: this COPY makes the `test` stage a hard dependency of `runtime`,
# so Docker must build and pass the test stage before this layer can exist.
COPY --from=test /opt/build-meta/tests-passed /opt/build-meta/tests-passed

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${UVICORN_PORT}/health" || exit 1

# sh -c so UVICORN_* env vars can be overridden at `docker run -e ...`.
# `exec` makes uvicorn PID 1, so it receives SIGTERM directly on stop.
CMD ["sh", "-c", "exec uvicorn traffic_engine.api.app:app \
  --host \"${UVICORN_HOST}\" \
  --port \"${UVICORN_PORT}\" \
  --workers \"${UVICORN_WORKERS}\" \
  --proxy-headers"]
