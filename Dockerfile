# Multi-stage Dockerfile for production builds
# Based on generative-protein-binder-design Docker patterns
# Supports multi-architecture builds (amd64, arm64)

ARG PYTHON_VERSION=3.11
ARG BUILD_TYPE=production
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Base stage with Python and system dependencies
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

# Platform information for debugging
RUN echo "Building on $BUILDPLATFORM, targeting $TARGETPLATFORM"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies including Go for building from source
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg2 \
    software-properties-common \
    golang-go \
    make \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN mkdir -p /app && chown appuser:appuser /app

WORKDIR /app

# Development stage
FROM base AS development
ENV DEVELOPMENT=1

# Install development dependencies
RUN apt-get update && apt-get install -y \
    vim \
    nano \
    tree \
    htop \
    strace \
    gdb \
    valgrind \
    && rm -rf /var/lib/apt/lists/*

# Install Python development tools
RUN pip install --upgrade pip setuptools wheel
COPY requirements-dev.txt requirements-dev.txt
RUN pip install -r requirements-dev.txt

# Copy source code
COPY --chown=appuser:appuser . .

# Install package in editable mode
RUN pip install -e ".[dev,test]"

USER appuser
EXPOSE 8000 5678
CMD ["python", "-m", "ipfs_kit_py"]

# Testing stage
FROM development AS testing
ENV TESTING=1

# Install testing dependencies
COPY requirements-test.txt requirements-test.txt
RUN pip install -r requirements-test.txt

# Run tests by default
CMD ["pytest", "tests/", "--verbose", "--cov=ipfs_kit_py"]

# Production build stage
FROM base AS builder

# Install build dependencies
RUN pip install --upgrade pip setuptools wheel build

# Copy source files
COPY . /app/src/
WORKDIR /app/src

# Build wheel
RUN python -m build --wheel

# Production stage
FROM base AS production
ENV BUILD_TYPE=production

# Copy wheel from builder
COPY --from=builder /app/src/dist/*.whl /tmp/

# Install package
RUN pip install --upgrade pip && \
    pip install /tmp/*.whl && \
    rm -rf /tmp/*.whl

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/config && \
    chown -R appuser:appuser /app

# Copy config files if they exist
COPY --chown=appuser:appuser config/ /app/config/ 2>/dev/null || true

USER appuser
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import ipfs_kit_py; print('OK')" || exit 1

EXPOSE 8000
CMD ["python", "-m", "ipfs_kit_py"]

# Documentation stage
FROM base AS documentation

# Install documentation dependencies
RUN apt-get update && apt-get install -y \
    pandoc \
    texlive-latex-base \
    texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/*

# Install Python documentation tools
RUN pip install mkdocs mkdocs-material mkdocstrings[python] \
    mkdocs-jupyter mkdocs-mermaid2-plugin

COPY --chown=appuser:appuser docs/ /app/docs/
COPY --chown=appuser:appuser mkdocs.yml /app/
COPY --chown=appuser:appuser . /app/src/

# Install package for documentation
RUN pip install -e /app/src/

USER appuser
WORKDIR /app

EXPOSE 8080
CMD ["mkdocs", "serve", "--dev-addr", "0.0.0.0:8080"]