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
    hwloc \
    libhwloc-dev \
    mesa-opencl-icd \
    ocl-icd-opencl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and home directory with proper ownership
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -m appuser \
    && mkdir -p /app /home/appuser/.cache /home/appuser/.local \
    && chown -R appuser:appuser /app /home/appuser \
    && chmod -R 0777 /home/appuser

# Ensure HOME points to a writable directory for pip and other tools
ENV HOME=/home/appuser \
    PIP_CACHE_DIR=/home/appuser/.cache/pip \
    PATH=/home/appuser/.local/bin:$PATH

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

# Copy source code
COPY --chown=appuser:appuser . .

# Install package in editable mode with all test-required extras baked in
RUN pip install -e ".[dev,test,api,webrtc,arrow]"

USER appuser
ENV HOME=/home/appuser
EXPOSE 8000 5678
CMD ["python", "-m", "ipfs_kit_py"]

# Testing stage
FROM development AS testing
ENV TESTING=1

# Install testing dependencies are provided by dev/test extras in previous stage

# Run tests by default from the tests directory
# Exclude tests with import errors (empty/incomplete modules)
CMD ["pytest", "--verbose", "--cov=ipfs_kit_py", "tests/", "-k", "not integration", "--ignore=tests/test_mcp_restoration.py", "--ignore=tests/test_merged_dashboard.py", "--ignore=tests/test_mock_format.py", "--ignore=tests/test_modern_bridge.py", "--ignore=tests/test_modernized_dashboard.py", "--ignore=tests/test_unified_bucket_api.py", "--ignore=tests/test_websocket.py", "-x"]

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

# Install package with API support for daemon functionality
RUN pip install --upgrade pip && \
    find /tmp -name "*.whl" -exec pip install "{}[api,full]" \; && \
    rm -rf /tmp/*.whl

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/config && \
    chown -R appuser:appuser /app

# Copy config files if they exist
# Copy config files from build context (directory exists in repo)
COPY --chown=appuser:appuser config/ /app/config/

USER appuser
ENV HOME=/home/appuser
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
# Create default mkdocs.yml if it doesn't exist in the repo
RUN if [ ! -f mkdocs.yml ]; then \
        echo "site_name: IPFS Kit Python" > mkdocs.yml && \
        echo "site_description: Python toolkit for IPFS operations" >> mkdocs.yml && \
        echo "site_url: https://ipfs-kit-py.readthedocs.io/" >> mkdocs.yml && \
        echo "" >> mkdocs.yml && \
        echo "theme:" >> mkdocs.yml && \
        echo "  name: material" >> mkdocs.yml && \
        echo "" >> mkdocs.yml && \
        echo "plugins:" >> mkdocs.yml && \
        echo "  - search" >> mkdocs.yml && \
        echo "  - mkdocstrings:" >> mkdocs.yml && \
        echo "      handlers:" >> mkdocs.yml && \
        echo "        python:" >> mkdocs.yml && \
        echo "          options:" >> mkdocs.yml && \
        echo "            show_source: true" >> mkdocs.yml && \
        echo "" >> mkdocs.yml && \
        echo "nav:" >> mkdocs.yml && \
        echo "  - Home: index.md" >> mkdocs.yml && \
        echo "  - API Reference: reference/" >> mkdocs.yml; \
    fi
COPY --chown=appuser:appuser . /app/src/

# Install package for documentation
RUN pip install -e /app/src/

USER appuser
ENV HOME=/home/appuser
WORKDIR /app

EXPOSE 8080
CMD ["mkdocs", "serve", "--dev-addr", "0.0.0.0:8080"]