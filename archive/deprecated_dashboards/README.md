# Deprecated Dashboard Files

This directory contains deprecated dashboard implementations that have been replaced by the new unified MCP dashboard.

## What was replaced

The old architecture used separate ports for:
- MCP server (port 8004)
- Dashboard (port 8085 or 8086)
- WebSocket connections for real-time updates

## New unified architecture

The new unified MCP dashboard is consolidated in `consolidated_mcp_dashboard.py` and runnable via the CLI (`python -m ipfs_kit_py.cli mcp start`). It provides:
- **Single port operation** (8004) for both MCP and dashboard
- **Direct MCP command integration** (no WebSockets needed)
- **Modern aesthetic design** with pleasing color gradients
- **Responsive layout** that works on mobile and desktop
- **Better performance** with efficient caching and API polling

## How to use the new dashboard

```bash
# Start the consolidated MCP server + dashboard
python -m ipfs_kit_py.cli mcp start

# Check status
ipfs-kit mcp status  

# Stop the server
ipfs-kit mcp stop
```

The dashboard will be available at: http://127.0.0.1:8004
MCP endpoints are available at: http://127.0.0.1:8004/mcp/*

## Key improvements

1. **Single port**: No more port conflicts or confusion
2. **No WebSockets**: Direct API calls are more reliable
3. **Better CSS**: Modern gradients, smooth animations, responsive design
4. **MCP integration**: Direct MCP command execution instead of HTTP proxying
5. **Clean architecture**: Simplified codebase with better error handling

## Files in this directory

- `comprehensive_mcp_dashboard.py` - The old multi-port dashboard
- `run_dashboard_directly.py` - Old standalone launcher
- Various other prototype dashboards from development

These files are kept for reference but should not be used in production.
