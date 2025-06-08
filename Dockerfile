# Dockerfile for MCP Server with Blue/Green Deployment Capabilities
# This image can be used for both Blue and Green deployments

FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install extra dependencies for monitoring
RUN pip install --no-cache-dir pandas matplotlib prometheus-client

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data/storage /app/data/stats

# Set deployment variant (will be overridden at runtime)
ENV DEPLOYMENT_VARIANT=blue \
    ENVIRONMENT=production \
    CONFIG_PATH=/app/config/blue_green_config.json \
    LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python -c "import requests; exit(0) if requests.get('http://localhost:9998/health').status_code == 200 else exit(1)"

# Expose ports for the final MCP server
EXPOSE 9998

# Command to run the enhanced final MCP server
CMD ["python", "final_mcp_server_enhanced.py", "--host", "0.0.0.0", "--port", "9998"]