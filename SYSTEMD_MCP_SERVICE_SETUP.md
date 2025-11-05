# IPFS-Kit MCP Systemd Service Setup

## Overview

The IPFS-Kit MCP server is now configured as a systemd service that will:
- ✅ **Start automatically on system boot**
- ✅ **Restart automatically if it crashes**
- ✅ **Be managed through standard systemctl commands**
- ✅ **Support the native `ipfs-kit mcp` CLI interface**

## Service Details

**Service Name**: `ipfs-kit-mcp.service`
**User**: `barberb`
**Working Directory**: `/home/barberb/ipfs_kit_py`
**Port**: `8004`
**PID File**: `/home/barberb/.ipfs_kit/mcp_8004.pid`

## Management Commands

### Using systemctl (requires sudo)

```bash
# Start the service
sudo systemctl start ipfs-kit-mcp.service

# Stop the service
sudo systemctl stop ipfs-kit-mcp.service

# Restart the service
sudo systemctl restart ipfs-kit-mcp.service

# Check service status
systemctl status ipfs-kit-mcp.service

# View service logs
sudo journalctl -u ipfs-kit-mcp.service -f

# Enable auto-start on boot (already enabled)
sudo systemctl enable ipfs-kit-mcp.service

# Disable auto-start on boot
sudo systemctl disable ipfs-kit-mcp.service
```

### Using the Management Script

A convenient wrapper script is provided: `./manage-mcp-service.sh`

```bash
# Start the service
./manage-mcp-service.sh start

# Stop the service
./manage-mcp-service.sh stop

# Restart the service
./manage-mcp-service.sh restart

# Check status (both systemd and MCP CLI)
./manage-mcp-service.sh status

# View logs
./manage-mcp-service.sh logs -f

# Use native MCP CLI commands
./manage-mcp-service.sh mcp status
./manage-mcp-service.sh mcp stop
./manage-mcp-service.sh mcp start
```

### Using Native CLI (for compatibility)

The original CLI still works when the service is running:

```bash
# Check status
python ipfs_kit_cli.py mcp status

# Note: start/stop through CLI may conflict with systemd
# Use systemctl or the management script instead
```

## Installation Summary

✅ **Service Created**: `/etc/systemd/system/ipfs-kit-mcp.service`
✅ **Service Enabled**: Will start automatically on boot
✅ **Service Running**: Currently active and responding
✅ **Management Script**: `./manage-mcp-service.sh` for easy management
✅ **Health Check**: Available at `http://127.0.0.1:8004/api/system/health`
✅ **Dashboard**: Available at `http://127.0.0.1:8004/`

## Verification

Check that everything is working:

```bash
# Service status
systemctl status ipfs-kit-mcp.service

# HTTP health check
curl -s http://127.0.0.1:8004/api/system/health

# MCP CLI status
python ipfs_kit_cli.py mcp status

# Management script
./manage-mcp-service.sh status
```

## Features Enabled

- **Auto-restart on failure**: Service will restart if it crashes
- **Boot persistence**: Service starts automatically after system reboot
- **Security hardening**: Service runs with restricted permissions
- **Logging integration**: Logs available through journalctl
- **Process management**: Proper PID file handling
- **CLI compatibility**: Original `ipfs-kit mcp` commands still work

## Troubleshooting

### Check service logs
```bash
sudo journalctl -u ipfs-kit-mcp.service --since "1 hour ago"
```

### Manual restart
```bash
sudo systemctl restart ipfs-kit-mcp.service
```

### Check if port is in use
```bash
sudo netstat -tlnp | grep 8004
```

### Verify service file
```bash
systemctl cat ipfs-kit-mcp.service
```

## Migration from Manual Start

If you were previously starting the MCP server manually:

1. ✅ **Stop manual instances**: All done - service is now managed by systemd
2. ✅ **Use systemctl**: Use `sudo systemctl start/stop/restart ipfs-kit-mcp.service`
3. ✅ **Use management script**: Use `./manage-mcp-service.sh` for convenience
4. ✅ **Auto-start enabled**: Service will start on boot automatically

The service is now fully operational and will persist across reboots!