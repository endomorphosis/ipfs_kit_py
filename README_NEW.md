# IPFS Kit Python - Production Ready MCP Server

A comprehensive Model Context Protocol (MCP) server for IPFS operations with FastAPI integration.

## 🚀 Quick Start

### Production Server
```bash
# Run the production MCP server
python src/mcp_server/main.py

# Or with Docker
docker build -f docker_files/production/Dockerfile -t ipfs-mcp-server .
docker run -p 8000:8000 ipfs-mcp-server
```

### API Documentation
- Interactive docs: `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/health`

## 📁 Project Structure

```
ipfs_kit_py/
├── src/
│   ├── mcp_server/          # Production MCP server
│   ├── ipfs_kit/           # Core IPFS functionality
│   └── tools/              # Utility tools
├── tests/                  # Test suites
├── docs/                   # Documentation
├── scripts/                # Deployment & utilities
├── docker_files/           # Docker configurations
└── examples/               # Usage examples
```

## 🔧 Development

### Installation
```bash
pip install -r requirements.txt
```

### Testing
```bash
python -m pytest tests/
```

### Validation
```bash
python scripts/deployment/validate_enhanced_server.py
```

## 📦 Features

- **FastAPI REST API** with comprehensive IPFS operations
- **Health Monitoring** with metrics and diagnostics
- **Docker Support** for production deployment
- **Comprehensive Testing** with integration tests
- **VS Code Integration** ready for MCP protocol

## 🚀 Production Deployment

See `docs/deployment/` for detailed deployment guides.

## 📚 Documentation

- [Development Guide](docs/development/)
- [API Documentation](docs/api/)
- [Deployment Guide](docs/deployment/)

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## 📄 License

See [LICENSE](LICENSE) for license information.
