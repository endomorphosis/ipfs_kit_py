# Lotus Daemon Management on macOS

This guide provides detailed instructions for using the Lotus daemon with macOS, including launchd integration for automatic startup and service management.

## Overview

The IPFS Kit Python package (`ipfs_kit_py`) includes comprehensive support for managing the Lotus daemon on macOS through the native launchd service system, enabling:

- Automatic startup on user login
- Process monitoring and recovery
- Resource usage optimization
- Standardized logging
- Seamless integration with macOS
- Advanced monitoring and auto-recovery
- Performance optimization and reporting

## Installation

### Prerequisites

1. **Install Python Package**
   ```bash
   pip install ipfs_kit_py
   ```

2. **Install Lotus Binary**
   
   Ensure the Lotus binary is installed and available in your PATH:
   ```bash
   # Check if lotus is available
   which lotus
   
   # If not, install it according to Filecoin documentation
   # or use the ipfs_kit_py binary installation helper:
   python -m ipfs_kit_py.lotus_kit install_binary
   ```

### Installing as a launchd Service

The `lotus_daemon` module provides easy installation as a macOS launchd service:

```python
from ipfs_kit_py.lotus_daemon import lotus_daemon

# Initialize with custom settings
daemon = lotus_daemon(metadata={
    "lotus_path": "~/.lotus",  # Path to Lotus data directory
    "service_name": "com.user.lotusd"  # Use reverse-domain style naming
})

# Install launchd service
result = daemon.install_launchd_service(
    user=os.getenv("USER"),  # Current user
    description="Filecoin Lotus Node"
)

print(f"Service installed: {result['success']}")
print(f"Service path: {result['service_path']}")
```

This creates a plist file in `~/Library/LaunchAgents/` configured to:
- Start when you log in
- Restart if it crashes
- Log output to standard locations
- Run with the correct environment variables

## Service Management

### Using launchctl (Command Line)

The launchd service can be managed using the `launchctl` command:

```bash
# Load and start the service
launchctl load ~/Library/LaunchAgents/com.user.lotusd.plist

# Unload/stop the service
launchctl unload ~/Library/LaunchAgents/com.user.lotusd.plist

# Check if service is running
launchctl list | grep lotusd

# View service details
launchctl print gui/$(id -u)/com.user.lotusd
```

### Using Python API

You can manage the daemon programmatically:

```python
from ipfs_kit_py.lotus_kit import lotus_kit

kit = lotus_kit()

# Check status
status = kit.daemon_status()
print(f"Daemon running: {status['process_running']}")

# Start daemon
start_result = kit.daemon_start()

# Stop daemon
stop_result = kit.daemon_stop()

# Uninstall service
uninstall_result = kit.daemon.service_uninstall()
```

## Monitoring and Management

The package now includes advanced monitoring capabilities specifically designed for macOS.

### Integrated Monitoring Tool

The new monitoring tool provides comprehensive daemon management:

```python
from ipfs_kit_py.lotus_kit import lotus_kit

# Initialize with monitoring configuration
kit = lotus_kit(metadata={
    "monitor_config": {
        "interval": 60,        # Check every 60 seconds
        "auto_restart": True,  # Auto-restart daemon if crashed
        "max_memory": 4096,    # Memory threshold in MB
        "report_dir": "~/lotus_monitor_reports"
    }
})

# Start the monitoring service
result = kit.monitor_start()
print(f"Monitor started: {result['success']}")
```

### Advanced Health Checking

The monitor provides automatic health verification and recovery:

```python
# Get current status
status = kit.monitor_status(detailed=True)

if status.get("success", False):
    print(f"Monitor running: {status.get('running', False)}")
    print(f"Daemon health: {status.get('daemon_health', 'unknown')}")
    
    # Show detailed metrics if available
    if "metrics" in status:
        metrics = status["metrics"]
        print(f"CPU Usage: {metrics.get('cpu_percent')}%")
        print(f"Memory Usage: {metrics.get('memory_percent')}%")
        print(f"Disk Usage: {metrics.get('disk_percent')}%")
        print(f"Uptime: {metrics.get('uptime')} seconds")
```

### Performance Optimization

Automatically optimize daemon configuration for macOS:

```python
# Run automatic optimization
optimize_result = kit.monitor_optimize()

if optimize_result.get("success", False):
    print("Optimization completed")
    
    # Show the applied optimizations
    for category, changes in optimize_result.get("optimizations", {}).items():
        print(f"\n{category.upper()} optimizations:")
        for key, value in changes.items():
            print(f"  {key}: {value}")
```

### Performance Reporting

Generate comprehensive performance reports:

```python
# Generate a performance report
report_result = kit.monitor_report(
    format="json",
    period="day",
    output_path="~/lotus_reports/performance.json"
)

if report_result.get("success", False):
    print(f"Report saved to: {report_result.get('report_path')}")
    
    # Show report summary
    if "summary" in report_result:
        summary = report_result["summary"]
        print(f"Period: {summary.get('period')}")
        print(f"Restarts: {summary.get('restart_count')}")
        print(f"Avg CPU: {summary.get('avg_cpu')}%")
        print(f"Max Memory: {summary.get('max_memory')}%")
```

## Advanced Configuration

### Optimized LaunchAgent Configuration

For better performance and resource management, you can enhance the plist file:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.lotusd</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/lotus</string>
        <string>daemon</string>
        <!-- Add custom arguments here -->
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LOTUS_PATH</key>
        <string>/Users/username/.lotus</string>
        <!-- Add additional environment variables -->
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>Crashed</key>
        <true/>
        <key>SuccessfulExit</key>
        <false/>
        <key>NetworkState</key>
        <true/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>StandardErrorPath</key>
    <string>/Users/username/Library/Logs/lotus.daemon.err</string>
    <key>StandardOutPath</key>
    <string>/Users/username/Library/Logs/lotus.daemon.out</string>
    <key>WorkingDirectory</key>
    <string>/Users/username</string>
    <key>ProcessType</key>
    <string>Background</string>
    <key>LowPriorityIO</key>
    <true/>
    <key>Nice</key>
    <integer>5</integer>
    <key>SoftResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>8192</integer>
        <key>NumberOfProcesses</key>
        <integer>512</integer>
    </dict>
</dict>
</plist>
```

Key enhancements include:
- Better restart handling with `KeepAlive` dictionary options
- Process priority management with `Nice` and `LowPriorityIO`
- Resource limits for files and processes
- Network-aware startup with `NetworkState`
- Throttling to prevent excessive restarts
- Improved log locations in user's Library/Logs directory

### Implementing Enhanced Plist

You can use the Python API to generate and install an enhanced plist:

```python
from ipfs_kit_py.lotus_daemon import lotus_daemon
import os

# Create custom plist content
home_dir = os.path.expanduser("~")
log_dir = os.path.join(home_dir, "Library/Logs")
lotus_path = os.path.join(home_dir, ".lotus")

enhanced_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.lotusd</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/lotus</string>
        <string>daemon</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LOTUS_PATH</key>
        <string>{lotus_path}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>Crashed</key>
        <true/>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardErrorPath</key>
    <string>{log_dir}/lotus.daemon.err</string>
    <key>StandardOutPath</key>
    <string>{log_dir}/lotus.daemon.out</string>
    <key>LowPriorityIO</key>
    <true/>
    <key>Nice</key>
    <integer>5</integer>
</dict>
</plist>
"""

# Write custom plist
os.makedirs(log_dir, exist_ok=True)
plist_path = os.path.join(home_dir, "Library/LaunchAgents/com.user.lotusd.plist")

with open(plist_path, 'w') as f:
    f.write(enhanced_plist)

# Load the service
import subprocess
subprocess.run(["launchctl", "load", plist_path])
```

## Troubleshooting

### Common Issues and Solutions

1. **Service fails to start**
   - Check error logs: `cat ~/Library/Logs/lotus.daemon.err`
   - Verify permissions: `chmod 644 ~/Library/LaunchAgents/com.user.lotusd.plist`
   - Check binary path: `which lotus`
   - Ensure Lotus path exists: `ls -la ~/.lotus`

2. **Access denied errors**
   - Check file ownership: `ls -la ~/Library/LaunchAgents/com.user.lotusd.plist`
   - Fix with: `chown $(whoami) ~/Library/LaunchAgents/com.user.lotusd.plist`

3. **Service loads but crashes**
   - Check for stale lock files: `ls -la ~/.lotus/repo.lock`
   - Remove stale locks: `rm ~/.lotus/repo.lock`
   - Try running manually to see errors: `lotus daemon`

4. **Service not starting on login**
   - Check plist is properly loaded: `launchctl list | grep lotusd`
   - Reload service: `launchctl unload ~/Library/LaunchAgents/com.user.lotusd.plist && launchctl load ~/Library/LaunchAgents/com.user.lotusd.plist`

5. **Performance issues**
   - Adjust Nice value in plist (higher = lower priority)
   - Enable LowPriorityIO for better system responsiveness
   - Configure SoftResourceLimits appropriately

### Debugging

For debugging services, launchd provides several tools:

```bash
# View all loaded services for current user
launchctl list

# View detailed service information
launchctl print gui/$(id -u)/com.user.lotusd

# Check exit status and timestamps
launchctl blame gui/$(id -u)/com.user.lotusd

# Enable debug logging for launchd
sudo launchctl debug gui/$(id -u)/com.user.lotusd --stdout --stderr
```

## Running the Example Scripts

The package includes comprehensive example scripts demonstrating macOS integration:

### Daemon Management Example

```bash
# Run the daemon management example
python -m ipfs_kit_py.examples.lotus_daemon_macos_example
```

This script shows:
- Installing the launchd service
- Managing the service
- Using launchctl
- Creating optimized plist files
- Using the high-level API

### Monitoring Tools Example

```bash
# Run the monitoring tools example
python -m ipfs_kit_py.examples.lotus_monitor_example
```

This new example demonstrates:
- Configuring and starting the monitoring service
- Checking daemon health and status
- Getting detailed performance metrics
- Running optimization for macOS
- Generating performance reports
- Handling platform-specific features

## Best Practices

1. **Use a dedicated user account** for production deployments
2. **Store logs in Library/Logs** instead of /tmp for persistence
3. **Configure resource limits** appropriate to your machine
4. **Use network-aware KeepAlive** to avoid unnecessary restarts
5. **Use the integrated monitoring tool** for automatic health checking
6. **Generate periodic performance reports** to track system behavior
7. **Run the optimization tool** after major OS or Lotus updates
8. **Regularly update** your Lotus binary
9. **Backup critical files** in the Lotus data directory
10. **Use unencrypted storage** for Lotus data (performance reasons)

## Additional Resources

- [Official Lotus Documentation](https://lotus.filecoin.io/)
- [macOS launchd Documentation](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [Filecoin Docs](https://docs.filecoin.io/)
- [IPFS Kit Documentation](/docs/lotus_daemon_management.md)