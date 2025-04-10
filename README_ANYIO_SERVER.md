# MCP Server with AnyIO Support

This is the AnyIO-compatible version of the MCP (Model-Controller-Persistence) server for IPFS Kit. It provides a structured API for IPFS operations with support for both asyncio and trio asynchronous backends.

## Features

- **AnyIO Backend Support**: Run with either asyncio or trio backend
- **Structured API**: Model-Controller-Persistence pattern for clear organization
- **Debug Mode**: Enhanced logging and operation tracking
- **Isolation Mode**: Test safely without affecting the host system
- **Role-Based Implementation**: Supports master, worker, and leecher roles

## Getting Started

### Installation

Make sure you have the required dependencies:

```bash
pip install anyio fastapi uvicorn httpx trio trio_asyncio
```

### Running the Server

#### Basic Usage

Start the server with default settings (asyncio backend):

```bash
python run_mcp_server_anyio.py
```

#### With Debug Mode

```bash
python run_mcp_server_anyio.py --debug
```

#### With Trio Backend

```bash
python run_mcp_server_anyio.py --backend trio
```

#### Custom Port and Host

```bash
python run_mcp_server_anyio.py --port 9000 --host 0.0.0.0
```

### Command-Line Options

- `--debug`: Enable debug mode with enhanced logging and debug endpoints
- `--isolation`: Run in isolated mode (separate IPFS repo for testing)
- `--port PORT`: Port to run the server on (default: 8002)
- `--host HOST`: Host to bind to (default: 0.0.0.0)
- `--persistence-path PATH`: Path for storing persistence files
- `--api-prefix PREFIX`: Prefix for API endpoints (default: /api/v0/mcp)
- `--log-level LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `--backend BACKEND`: AnyIO backend to use (asyncio, trio)

## API Endpoints

The server provides the following main endpoint categories:

- `/api/v0/mcp/health`: Server health check
- `/api/v0/mcp/ipfs/*`: IPFS operations
- `/api/v0/mcp/cli/*`: CLI-compatible operations
- `/api/v0/mcp/daemon/*`: Daemon management (admin only)

### Example Curl Commands

Health check:
```bash
curl http://localhost:8002/api/v0/mcp/health
```

IPFS version:
```bash
curl http://localhost:8002/api/v0/mcp/cli/version
```

List pins:
```bash
curl http://localhost:8002/api/v0/mcp/cli/pins
```

## Testing

Run the automated tests to verify server functionality:

```bash
python test_anyio_server.py
```

Test specific backend:
```bash
python test_anyio_server.py --backend asyncio
python test_anyio_server.py --backend trio
```

## Architecture

The server follows an MCP (Model-Controller-Persistence) architecture:

1. **Models**: Business logic for IPFS operations
2. **Controllers**: HTTP request handling
3. **Persistence**: Caching and data storage

### Key Components:

- `server_anyio.py`: Core server implementation
- `run_mcp_server_anyio.py`: Server launcher script
- `test_anyio_server.py`: Automated tests

## Developer Notes

- For extended debug information, visit `/api/v0/mcp/debug` when running in debug mode
- Logs operations at `/api/v0/mcp/operations` in debug mode
- Supports role-based functionality with the isolation mode for testing

For full details on the AnyIO migration and implementation, see the `ANYIO_MIGRATION.md` file.