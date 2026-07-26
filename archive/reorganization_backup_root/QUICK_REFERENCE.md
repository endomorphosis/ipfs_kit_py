# IPFS-Kit Quick Reference Guide

## Quick Start

### 1. Start the Daemon
```bash
python ipfs_kit_daemon.py
```

### 2. Start Enhanced MCP Server
```bash
python enhanced_multiprocessing_mcp_server.py --workers 4
```

### 3. Use Enhanced CLI
```bash
python enhanced_multiprocessing_cli.py ipfs add file1,file2,file3 --parallel
```

## Command Reference

### Daemon Commands
```bash
# Start daemon
python ipfs_kit_daemon.py

# Start with custom config
python ipfs_kit_daemon.py --config /path/to/config.json

# Debug mode
python ipfs_kit_daemon.py --debug

# Check status
python ipfs_kit_daemon.py --status

# Stop daemon
python ipfs_kit_daemon.py --stop
```

### MCP Server Commands
```bash
# Basic start
python enhanced_multiprocessing_mcp_server.py

# With 8 workers
python enhanced_multiprocessing_mcp_server.py --workers 8

# Custom VFS workers
python enhanced_multiprocessing_mcp_server.py --vfs-workers 4

# Custom host/port
python enhanced_multiprocessing_mcp_server.py --host 0.0.0.0 --port 9000
```

### CLI Commands
```bash
# Add files in parallel
python enhanced_multiprocessing_cli.py ipfs add file1.txt,file2.txt --parallel

# Backend health checks
python enhanced_multiprocessing_cli.py backend health --parallel

# Route optimization
python enhanced_multiprocessing_cli.py route optimize QmHash1,QmHash2

# Pin operations
python enhanced_multiprocessing_cli.py pin add QmHash1,QmHash2 --parallel
python enhanced_multiprocessing_cli.py pin remove QmHash1,QmHash2 --parallel

# Get statistics
python enhanced_multiprocessing_cli.py stats
```

## Configuration Quick Setup

### Default Config Location
```
/tmp/ipfs_kit_config/daemon.json
```

### Minimal Configuration
```json
{
  "daemon": {
    "health_check_interval": 30,
    "log_level": "INFO"
  },
  "backends": {
    "ipfs": {"enabled": true, "auto_start": true}
  },
  "replication": {"enabled": false},
  "monitoring": {"health_checks": true}
}
```

## Performance Tuning

### Optimal Worker Counts
```bash
# CPU-intensive: cores/5 to cores/2
--workers 8

# I/O-intensive: cores*2 to cores*4
--workers 32

# Mixed workload: cores/2 to cores
--workers 16
```

### Memory Optimization
```bash
# Reduce memory usage
--workers 4
--max-memory 1GB
```

## API Quick Reference

### Daemon Status
```python
from ipfs_kit_daemon import IPFSKitDaemon

daemon = IPFSKitDaemon()
status = daemon.get_status()
health = daemon.get_backend_health("ipfs")
```

### CLI Operations
```python
from enhanced_multiprocessing_cli import EnhancedMultiprocessingCLI

cli = EnhancedMultiprocessingCLI(max_workers=8)
results = await cli.add_files_batch(["file1.txt", "file2.txt"])
stats = cli.get_stats()
```

## Troubleshooting Quick Fixes

### Daemon Won't Start
```bash
# Check IPFS
ipfs id

# Check ports
netstat -tulpn | grep :5001

# Reset config
rm /tmp/ipfs_kit_config/daemon.json
```

### Poor Performance
```bash
# Check CPU count
python -c "import multiprocessing; print(multiprocessing.cpu_count())"

# Reduce workers
--workers 4

# Monitor resources
htop
```

### Memory Issues
```bash
# Monitor memory
python -c "import psutil; print(f'{psutil.virtual_memory().available/1024/1024/1024:.1f}GB available')"

# Use spawn context
export PYTHONHASHSEED=0
```

## Test Commands

### Run All Tests
```bash
python test_daemon_multiprocessing_comprehensive.py
```

### Performance Tests
```bash
python test_performance_multiprocessing.py
```

### Demo
```bash
python demo_enhanced_multiprocessing.py
```

## Log Locations

```
/tmp/ipfs_kit_logs/ipfs_kit_daemon.log
/tmp/ipfs_kit_logs/enhanced_mcp_server.log
/tmp/ipfs_kit_logs/enhanced_cli.log
```

## Performance Benchmarks

### Our Test Results (40 CPU cores)
- **CPU Tasks**: 3.4x speedup with 8 workers
- **I/O Tasks**: 22.9x speedup with async
- **Memory Usage**: ~37MB overhead
- **Optimal Workers**: 8 for CPU, 25+ for I/O

### Expected Performance
- **2-4 cores**: 1.5-2x speedup
- **8 cores**: 2-3x speedup  
- **16+ cores**: 3-4x speedup

## Environment Variables

```bash
# Python optimization
export PYTHONHASHSEED=0
export PYTHONUNBUFFERED=1

# Multiprocessing
export MP_START_METHOD=spawn

# Logging
export IPFS_KIT_LOG_LEVEL=INFO
export IPFS_KIT_LOG_DIR=/tmp/ipfs_kit_logs
```

## Common Patterns

### Parallel File Processing
```python
files = ["file1.txt", "file2.txt", "file3.txt"]
results = await cli.add_files_batch(files)
```

### Health Monitoring
```python
backends = ["ipfs", "cluster", "lotus"]
health = await cli.check_backend_health_parallel(backends)
```

### Batch Operations
```python
cids = ["QmHash1", "QmHash2", "QmHash3"]
await cli.pin_add_batch(cids)
```

## Emergency Commands

### Kill All Processes
```bash
pkill -f ipfs_kit
```

### Clean Reset
```bash
rm -rf /tmp/ipfs_kit_*
rm -rf /tmp/test_*
```

### Check System Resources
```bash
free -h
df -h
ps aux | grep python
```

---

For detailed documentation, see `DOCUMENTATION.md`
