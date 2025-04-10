# Build stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only requirements files to leverage Docker cache
COPY pyproject.toml setup.py README.md MANIFEST.in ./
COPY .gitmodules ./

# Install dependencies into the builder image
RUN pip install --no-cache-dir build wheel
RUN python -m build

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Set up a non-root user
RUN groupadd -r ipfs && useradd -r -g ipfs ipfs

# Create necessary directories with correct permissions
RUN mkdir -p /data/ipfs /data/ipfs-cluster /app \
    && chown -R ipfs:ipfs /data

WORKDIR /app

# Copy wheel from builder
COPY --from=builder /build/dist/*.whl /app/

# Install the wheel with optimized settings
RUN pip install --no-cache-dir /app/*.whl[full] && rm /app/*.whl

# Copy entrypoint and configuration files
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/health-check.sh /health-check.sh
COPY docker/config.yaml /etc/ipfs-kit/default-config.yaml

# Set proper permissions
RUN chmod +x /entrypoint.sh /health-check.sh && \
    chown -R ipfs:ipfs /app

# Set environment variables
ENV IPFS_PATH=/data/ipfs \
    IPFS_CLUSTER_PATH=/data/ipfs-cluster \
    IPFS_KIT_CONFIG=/etc/ipfs-kit/default-config.yaml

# Expose ports for IPFS daemon, API, gateway, and Cluster
EXPOSE 4001 5001 8080 9094 9095 9096

# Switch to non-root user
USER ipfs

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ["/health-check.sh"]

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]

# Default command starts the daemon as leecher
CMD ["leecher"]