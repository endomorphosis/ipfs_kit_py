# IPFS-Kit Enhanced README v2.0

## 🚀 IPFS-Kit: Advanced IPFS Infrastructure Management

[![CI/CD Pipeline](https://github.com/endomorphosis/ipfs_kit_py/actions/workflows/enhanced-ci-cd.yml/badge.svg)](https://github.com/endomorphosis/ipfs_kit_py/actions)
[![Docker Pulls](https://img.shields.io/docker/pulls/endomorphosis/ipfs_kit_py.svg)](https://hub.docker.com/r/endomorphosis/ipfs_kit_py)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A comprehensive toolkit for managing IPFS infrastructure with advanced daemon management, multiprocessing optimizations, and integrated backend support. Built for high-performance, scalable operations across distributed storage networks.

## ✨ Key Features

### 🔧 **Enhanced Daemon Management**
- Standalone daemon architecture for backend infrastructure management
- Comprehensive health monitoring and auto-recovery
- Configuration hot-reloading and dynamic backend management
- Advanced logging and observability

### ⚡ **Performance Optimizations**
- **3.4x CPU speedup** with advanced multiprocessing
- **22.9x I/O performance improvement** for concurrent operations
- Intelligent worker pool management and load balancing
- Memory-efficient content handling

### 🛠️ **Comprehensive CLI Tools**
- Full-featured command-line interface for all operations
- Pin management with enhanced metadata
- Backend control and health monitoring
- Configuration management and real-time metrics

### 🐳 **Container-Native Deployment**
- Multi-platform Docker images (linux/amd64, linux/arm64)
- Kubernetes-ready with health checks and probes
- Multiple deployment modes (daemon-only, cluster, full-stack)
- Integrated monitoring with Prometheus and Grafana

### 📊 **Monitoring and Observability**
- Real-time performance metrics and health dashboards
- Comprehensive logging with structured output
- Alerting and notification integration
- Performance benchmarking and regression detection

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Run with Docker Compose
curl -O https://raw.githubusercontent.com/endomorphosis/ipfs_kit_py/main/docker/docker-compose.enhanced.yml
docker-compose -f docker-compose.enhanced.yml up -d

# Check status
curl http://localhost:9999/api/v1/status

# Access dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

### Option 2: Local Installation

```bash
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py
pip install -r requirements.txt
pip install -e .

# Start the enhanced daemon
python ipfs_kit_enhanced_cli.py daemon start --detach

# Use the CLI
python ipfs_kit_enhanced_cli.py daemon status
python ipfs_kit_enhanced_cli.py pin add QmYourCIDHere --name "my-file"
python ipfs_kit_enhanced_cli.py metrics
```

### Option 3: Container Registry

```bash
# Pull and run latest image
docker run -d \
  --name ipfs-kit \
  -p 9999:9999 -p 5001:5001 -p 8080:8080 \
  -v ipfs_data:/home/ipfs_user/.ipfs \
  ghcr.io/endomorphosis/ipfs_kit_py:latest
```

## 📋 Requirements

- **Python**: 3.9+
- **Docker**: 20.10+ (for containerized deployment)
- **System**: Linux, macOS, Windows (WSL2)
- **Memory**: 2GB+ recommended
- **Storage**: 10GB+ for IPFS data

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    IPFS-Kit Enhanced                        │
├─────────────────────────────────────────────────────────────┤
│  CLI Tools          │  HTTP API        │  MCP Server        │
├─────────────────────────────────────────────────────────────┤
│                 IPFS-Kit Daemon                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Health    │ │ Replication │ │    Pin      │           │
│  │ Monitoring  │ │  Manager    │ │   Manager   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│               Backend Infrastructure                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │  IPFS   │ │ Cluster │ │  Lotus  │ │ Lassie  │           │
│  │ Daemon  │ │ Service │ │ Daemon  │ │ Client  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 📖 Documentation

### Essential Guides
- [📚 Complete Technical Documentation](DOCUMENTATION.md)
- [⚡ Quick Reference Guide](QUICK_REFERENCE.md)
- [🐳 Docker Deployment Guide](docker/README.md)
- [🔧 API Reference](docs/api-reference.md)

### Advanced Topics
- [🚀 Performance Optimization](docs/performance.md)
- [🏥 Health Monitoring](docs/monitoring.md)
- [🔒 Security Best Practices](docs/security.md)
- [🐛 Troubleshooting Guide](docs/troubleshooting.md)

## 🛠️ Usage Examples

### CLI Operations

```bash
# Daemon Management
python ipfs_kit_enhanced_cli.py daemon start --detach
python ipfs_kit_enhanced_cli.py daemon status
python ipfs_kit_enhanced_cli.py daemon restart

# Pin Management
python ipfs_kit_enhanced_cli.py pin add QmHash --name "important-data"
python ipfs_kit_enhanced_cli.py pin list --metadata
python ipfs_kit_enhanced_cli.py pin remove QmHash

# Backend Control
python ipfs_kit_enhanced_cli.py backend start ipfs
python ipfs_kit_enhanced_cli.py backend status
python ipfs_kit_enhanced_cli.py health check

# Performance Monitoring
python ipfs_kit_enhanced_cli.py metrics --detailed
python ipfs_kit_enhanced_cli.py replication status
```

### HTTP API

```bash
# Status and Health
curl http://localhost:9999/api/v1/status
curl http://localhost:9999/api/v1/health

# Pin Operations
curl -X POST http://localhost:9999/api/v1/pins \
  -H "Content-Type: application/json" \
  -d '{"cid": "QmHash", "name": "my-file"}'

# Backend Management
curl -X POST http://localhost:9999/api/v1/backends/ipfs \
  -H "Content-Type: application/json" \
  -d '{"action": "start"}'
```

### Docker Deployment

```bash
# Single container with all services
docker run -d \
  --name ipfs-kit-full \
  -p 4001:4001 -p 5001:5001 -p 8080:8080 -p 9999:9999 \
  -v ipfs_data:/home/ipfs_user/.ipfs \
  -v config_data:/tmp/ipfs_kit_config \
  ghcr.io/endomorphosis/ipfs_kit_py:latest all

# Lightweight daemon-only mode
docker run -d \
  --name ipfs-kit-daemon \
  -p 9999:9999 \
  ghcr.io/endomorphosis/ipfs_kit_py:latest daemon-only

# Cluster deployment
docker-compose -f docker/docker-compose.enhanced.yml up -d
```

## 📊 Performance Benchmarks

### Multiprocessing Performance

| Operation Type | Single Thread | Multi-Process | Speedup |
|----------------|---------------|---------------|---------|
| CPU-Intensive  | 1.0x          | 3.4x          | 240%    |
| I/O Operations | 1.0x          | 22.9x         | 2190%   |
| Mixed Workload | 1.0x          | 8.7x          | 770%    |

### System Requirements

| Deployment Mode | CPU Cores | Memory | Storage |
|-----------------|-----------|--------|---------|
| Daemon Only     | 1-2       | 512MB  | 1GB     |
| Full Stack      | 2-4       | 2GB    | 10GB    |
| Cluster Node    | 4-8       | 4GB    | 50GB    |

## 🔄 CI/CD and Development

### Continuous Integration

- **Automated Testing**: Unit, integration, and performance tests
- **Security Scanning**: Vulnerability detection and dependency analysis
- **Multi-Platform Builds**: Docker images for multiple architectures
- **Quality Gates**: Code formatting, linting, and type checking

### Development Workflow

```bash
# Setup development environment
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py
pip install -r requirements.txt
pip install -e .

# Run tests
python test_daemon_multiprocessing_comprehensive.py
python test_performance_multiprocessing.py

# Run linting
black --check .
flake8 .
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Process

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the full test suite
5. Submit a pull request

### Code Standards

- **Python**: Black formatting, PEP 8 compliance
- **Documentation**: Comprehensive docstrings and README updates
- **Testing**: Unit tests for all new functionality
- **Security**: Security scanning and vulnerability assessment

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **IPFS Community**: For the foundational IPFS protocol and tools
- **Contributors**: All the developers who have contributed to this project
- **Open Source Libraries**: The amazing ecosystem of Python and Go libraries

## 📧 Support

- **Documentation**: [Complete Technical Docs](DOCUMENTATION.md)
- **Issues**: [GitHub Issues](https://github.com/endomorphosis/ipfs_kit_py/issues)
- **Discussions**: [GitHub Discussions](https://github.com/endomorphosis/ipfs_kit_py/discussions)
- **Security**: [Security Policy](SECURITY.md)

---

**Made with ❤️ by the IPFS-Kit team**

*Building the future of decentralized storage infrastructure*
