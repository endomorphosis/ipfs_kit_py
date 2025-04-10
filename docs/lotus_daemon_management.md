# Lotus Daemon Management in IPFS Kit

This document outlines the daemon management capabilities of the `lotus_kit` module within `ipfs_kit_py`.

## Overview

The `lotus_kit` module provides a Python interface to the Lotus API, which is a client implementation for the Filecoin network. The module includes comprehensive daemon management capabilities, allowing for:

- Starting and stopping the Lotus daemon
- Checking daemon status
- Service installation for systemd (Linux) and Windows services
- Binary execution in the `bin` directory
- Auto-recovery of failed daemons
- Role-based configuration

## Integration with ipfs_kit

The `lotus_kit` integration with `ipfs_kit` follows the same patterns used for IPFS daemon management:

1. **Role-Based Auto-Start Configuration**:
   - For master role: daemon auto-start defaults to `True`
   - For worker/leecher roles: daemon auto-start defaults to `False`
   - Can be overridden with `auto_start_lotus_daemon` in metadata

2. **Daemon Status Checking**:
   - The `check_daemon_status` method now checks Lotus daemon status
   - Includes running state, PID, and API readiness information

3. **Lifecycle Management**:
   - The `_start_required_daemons` method starts the Lotus daemon if needed
   - The `stop_daemons` method stops the Lotus daemon before stopping IPFS
   - The `_ensure_daemon_running` method provides manual daemon control

4. **Lazy Initialization**:
   - The daemon manager is lazily loaded for better performance
   - Imports and initializes only when actually needed

## Using Lotus Daemon Management

### Initialization with Auto-Start

```python
from ipfs_kit_py import ipfs_kit

# Master role with auto-start for Lotus daemon
kit = ipfs_kit(role="master", metadata={
    "auto_start_lotus_daemon": True  # Default is True for master
})

# Worker role with auto-start enabled
kit = ipfs_kit(role="worker", metadata={
    "auto_start_lotus_daemon": True  # Default is False for worker
})
```

### Manual Daemon Management

```python
from ipfs_kit_py import ipfs_kit

kit = ipfs_kit()

# Check daemon status
status = kit.check_daemon_status()
lotus_running = status.get("daemons", {}).get("lotus", {}).get("running", False)
print(f"Lotus daemon running: {lotus_running}")

# Start daemon if needed
if not lotus_running:
    result = kit._ensure_daemon_running("lotus")
    print(f"Started lotus daemon: {result.get('success', False)}")

# Stop daemon 
stop_result = kit.stop_daemons()  # Stops all daemons including Lotus
print(f"Stopped daemons: {stop_result.get('success', False)}")
```

### Direct Access to Lotus Kit

```python
from ipfs_kit_py import ipfs_kit

kit = ipfs_kit()

# Direct access to lotus_kit for daemon management
start_result = kit.lotus_kit.daemon_start()
print(f"Started lotus daemon: {start_result.get('success', False)}")

status_result = kit.lotus_kit.daemon_status()
print(f"Daemon status: {status_result}")

stop_result = kit.lotus_kit.daemon_stop()
print(f"Stopped lotus daemon: {stop_result.get('success', False)}")
```

### Service Installation

```python
from ipfs_kit_py import ipfs_kit

kit = ipfs_kit()

# Install as a systemd service on Linux
if platform.system() == "Linux":
    result = kit.lotus_kit.install_service(
        user="filecoin",
        description="Lotus Daemon Service"
    )
    print(f"Installed systemd service: {result.get('success', False)}")

# Install as a Windows service
elif platform.system() == "Windows":
    result = kit.lotus_kit.install_service(
        description="Lotus Daemon Service"
    )
    print(f"Installed Windows service: {result.get('success', False)}")
```

## Platform-Specific Details

### Linux (systemd)

On Linux systems, the Lotus daemon can be managed as a systemd service with the following features:

- Proper dependency on network.target
- Service file creation with appropriate permissions
- User/group configuration
- Automatic start on system boot
- JournalD logging integration

### Windows Services

On Windows systems, the Lotus daemon can be registered as a Windows service with:

- Proper service registration in the Windows registry
- Auto-start configuration
- Service recovery options
- Event log integration

### macOS (launchd)

On macOS systems, the Lotus daemon can be managed as a launchd service with the following features:

- User-level service management via LaunchAgents
- Automatic startup on user login
- Process monitoring and automatic restart
- Configurable environment variables and parameters
- Standard output and error redirection
- Resource controls (CPU priority, I/O priority)

#### LaunchAgent Configuration

The Lotus daemon is installed as a user LaunchAgent with a plist file in `~/Library/LaunchAgents/`:

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
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LOTUS_PATH</key>
        <string>/Users/username/.lotus</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/lotus.daemon.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/lotus.daemon.out</string>
    <key>WorkingDirectory</key>
    <string>/tmp</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
```

#### Using launchctl

The Lotus daemon launchd service can be manually controlled using `launchctl`:

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

#### Advanced Configuration

For better performance on macOS, the plist can be enhanced with:

```xml
<key>LowPriorityIO</key>
<true/>
<key>Nice</key>
<integer>5</integer>
<key>SoftResourceLimits</key>
<dict>
    <key>NumberOfFiles</key>
    <integer>8192</integer>
</dict>
```

#### Implementation Example

```python
from ipfs_kit_py import ipfs_kit

# Initialize kit
kit = ipfs_kit()

# Install Lotus daemon as a launchd service
result = kit.lotus_kit.install_launchd_service(
    user=os.getenv("USER"),
    description="Lotus Filecoin Node",
    service_name="com.user.lotus-daemon"
)

print(f"Installed launchd service: {result.get('success', False)}")
print(f"Service path: {result.get('service_path')}")
```

### Direct Process Management

On all platforms, the Lotus daemon can also be managed as a direct process with:

- PID file tracking
- API socket monitoring
- Graceful shutdown support
- Stale lock detection and recovery

## Auto-Recovery Functionality

The Lotus daemon management includes auto-recovery functionality:

1. **API Failure Detection**: If an API call fails due to a non-responsive daemon
2. **Status Check**: The system checks if the daemon process is still running
3. **Auto-Restart**: If the process has crashed, it is automatically restarted
4. **API Retry**: The original API call is retried after daemon restart

This provides robust operation even if the Lotus daemon crashes unexpectedly.

## Role-Based Configuration

The daemon management behavior is tailored based on the node's role:

- **Master Nodes**: Responsible for orchestrating operations and typically run Lotus daemons by default
- **Worker Nodes**: Optimized for processing with optional Lotus daemon support
- **Leecher Nodes**: Lightweight nodes with minimal daemon requirements

This role-based approach ensures efficient resource utilization across a distributed deployment.