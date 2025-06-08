# MCP Server Check Tool

This script provides tools to check, manage, and test the MCP server implementation.

## Features

- Check if server is running and responsive
- Test JSON-RPC endpoint with ping requests
- List all registered tools
- Get detailed server information
- Start, stop, and restart the server
- Comprehensive error handling and reporting

## Usage

### Basic Server Status Check

```bash
./check_server.py
```

This will check if the server is running on the default host (localhost) and port (9998).

### Using Different Host or Port

```bash
./check_server.py --host 192.168.1.100 --port 8080
```

### Starting the Server

```bash
./check_server.py --start
```

This will attempt to start the MCP server if it's not already running.

### Stopping the Server

```bash
./check_server.py --stop
```

### Restarting the Server

```bash
./check_server.py --restart
```

### Listing All Registered Tools

```bash
./check_server.py --list-tools
```

This will fetch and display all tools registered in the MCP server, organized by category.

### Getting Detailed Server Information

```bash
./check_server.py --info
```

This will display detailed information about the server, including version, uptime, and registered tool categories.

### Combining Options

You can combine multiple options in a single command:

```bash
./check_server.py --port 9998 --info --list-tools
```

## Exit Codes

- `0`: Success
- `1`: Error (server not running or operation failed)

## Example Workflow

1. Check if server is running:
   ```bash
   ./check_server.py
   ```

2. If not running, start it:
   ```bash
   ./check_server.py --start
   ```

3. Once running, check tools and server info:
   ```bash
   ./check_server.py --info --list-tools
   ```

4. When done, stop the server:
   ```bash
   ./check_server.py --stop
   ```
