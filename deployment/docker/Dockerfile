# Multi-stage Dockerfile for IPFS Kit MCP Server with Cluster Support
# Supports multi-architecture builds (amd64, arm64)

ARG TARGETPLATFORM
ARG BUILDPLATFORM

FROM python:3.12-slim as base

# Platform information for debugging
RUN echo "Building on $BUILDPLATFORM, targeting $TARGETPLATFORM"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies including Go for building from source
# Also include Lotus prerequisites (hwloc, OpenCL) so installer detects them
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    gcc \
    g++ \
    make \
    pkg-config \
    libffi-dev \
    libssl-dev \
    golang-go \
    hwloc \
    libhwloc-dev \
    mesa-opencl-icd \
    ocl-icd-opencl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd --create-home --shell /bin/bash --uid 1000 ipfs_user

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Install the package with a complete, maintained dependency set
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e ".[full]"

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/config /app/ipfs_data && \
    chown -R ipfs_user:ipfs_user /app

# Switch to application user
USER ipfs_user

# Expose ports
EXPOSE 9998 5001 8080 4001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9998/health || exit 1

# Default command
CMD ["python", "containerized_mcp_server.py", "--host", "0.0.0.0", "--port", "9998"]

# Development stage with additional tools
FROM base as development

USER root

# Install development dependencies
RUN pip install \
    pytest-html \
    pytest-xdist \
    pytest-benchmark \
    pytest-timeout \
    ipython \
    jupyter \
    black \
    flake8 \
    mypy

USER ipfs_user

CMD ["python", "containerized_mcp_server.py", "--host", "0.0.0.0", "--port", "9998", "--debug"]

# Production stage
FROM base as production

# Remove unnecessary files
RUN rm -rf tests/ docs/ examples/ .git* && \
    find /app -name "*.pyc" -delete && \
    find /app -name "__pycache__" -type d -exec rm -rf {} + || true

# Use non-root user
USER ipfs_user

# Production command with optimizations
CMD ["python", "-O", "containerized_mcp_server.py", "--host", "0.0.0.0", "--port", "9998"]
