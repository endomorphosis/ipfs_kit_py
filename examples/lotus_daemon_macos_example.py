#!/usr/bin/env python3
"""
Example script demonstrating Lotus daemon management on macOS.

This script shows how to use the lotus_daemon module to install,
manage, and interact with the Lotus daemon on macOS using launchd.
"""

import os
import platform
import time
from ipfs_kit_py.lotus_daemon import lotus_daemon
from ipfs_kit_py import ipfs_kit

def check_is_macos():
    """Check if running on macOS."""
    if platform.system() != "Darwin":
        print("This example is specific to macOS. Please run on a macOS system.")
        return False
    return True

def install_launchd_service_example():
    """Example of installing Lotus daemon as a macOS launchd service."""
    print("\n=== Installing Lotus daemon as a launchd service ===")

    # Create daemon manager with custom settings
    daemon = lotus_daemon(metadata={
        "lotus_path": os.path.expanduser("~/.lotus"),
        "service_name": "com.user.lotusd"  # Using reverse-domain naming convention
    })

    # Install as a launchd service (user-level)
    result = daemon.install_launchd_service(
        user=os.getenv("USER"),
        description="Filecoin Lotus Node Service"
    )

    if result.get("success", False):
        print(f"Service installed successfully at: {result.get('service_path')}")
        print("You can view the service details in ~/Library/LaunchAgents/")
    else:
        print(f"Failed to install service: {result.get('error')}")
        if result.get("error_type") == "platform_error":
            print("This script must be run on macOS.")

    return result

def control_daemon_example():
    """Example of controlling the Lotus daemon on macOS."""
    print("\n=== Controlling the Lotus daemon ===")

    # Create daemon manager
    daemon = lotus_daemon()

    # Check current status
    status_result = daemon.daemon_status()

    if status_result.get("process_running", False):
        print(f"Lotus daemon is already running with PID: {status_result.get('pid')}")

        # Stop daemon example
        print("\nStopping daemon...")
        stop_result = daemon.daemon_stop()

        if stop_result.get("success", False):
            print("Daemon stopped successfully")
        else:
            print(f"Failed to stop daemon: {stop_result.get('error')}")
    else:
        print("Lotus daemon is not running")

        # Start daemon example
        print("\nStarting daemon...")
        start_result = daemon.daemon_start()

        if start_result.get("success", False):
            print(f"Daemon started successfully with PID: {start_result.get('pid')}")
        else:
            print(f"Failed to start daemon: {start_result.get('error')}")

    # Final status check
    print("\nFinal status check:")
    final_status = daemon.daemon_status()
    print(f"Daemon running: {final_status.get('process_running', False)}")

    return final_status

def launchctl_management_example():
    """Example of using launchctl to manage the Lotus daemon service."""
    print("\n=== Using launchctl for service management ===")

    daemon = lotus_daemon(metadata={
        "service_name": "com.user.lotusd"  # Match the service name used during installation
    })

    # Create command strings for user to execute
    plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{daemon.service_name}.plist")

    print("Example launchctl commands for managing your service:")
    print(f"\n# Load and start the service")
    print(f"launchctl load {plist_path}")

    print(f"\n# Unload/stop the service")
    print(f"launchctl unload {plist_path}")

    print(f"\n# Check if service is running")
    print(f"launchctl list | grep {daemon.service_name}")

    print(f"\n# View service details")
    print(f"launchctl print gui/$(id -u)/{daemon.service_name}")

    print(f"\n# View service logs")
    print("cat /tmp/lotus.daemon.out")
    print("cat /tmp/lotus.daemon.err")

def enhanced_plist_example():
    """Example of creating an enhanced plist with performance optimizations."""
    print("\n=== Enhanced LaunchAgent Plist Example ===")

    # Define an optimized plist template
    enhanced_plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.lotus-optimized</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/lotus</string>
        <string>daemon</string>
        <!-- Optional: Add custom daemon arguments here -->
        <string>--api-ListenAddress</string>
        <string>/ip4/127.0.0.1/tcp/1234/http</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LOTUS_PATH</key>
        <string>{lotus_path}</string>
        <key>LOTUS_SKIP_GENESIS_CHECK</key>
        <string>_yes_</string>
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
    <string>{log_dir}/lotus.daemon.err</string>
    <key>StandardOutPath</key>
    <string>{log_dir}/lotus.daemon.out</string>
    <key>WorkingDirectory</key>
    <string>{home_dir}</string>
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
"""

    # Fill in template variables
    home_dir = os.path.expanduser("~")
    log_dir = os.path.join(home_dir, "Library/Logs")
    lotus_path = os.path.join(home_dir, ".lotus")

    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Format plist with actual paths
    formatted_plist = enhanced_plist.format(
        lotus_path=lotus_path,
        log_dir=log_dir,
        home_dir=home_dir
    )

    # Print example plist
    print("Enhanced plist with performance optimizations:")
    print(formatted_plist)

    # Write plist to file (commented out - for example only)
    """
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.user.lotus-optimized.plist")
    with open(plist_path, 'w') as f:
        f.write(formatted_plist)

    print(f"Written enhanced plist to: {plist_path}")
    print("You can load it with: launchctl load -w {plist_path}")
    """

    # Just show instructions instead
    print("\nTo use this enhanced plist:")
    print("1. Save the above XML to ~/Library/LaunchAgents/com.user.lotus-optimized.plist")
    print("2. Edit the paths and settings as needed")
    print("3. Load with: launchctl load -w ~/Library/LaunchAgents/com.user.lotus-optimized.plist")

def high_level_api_example():
    """Example of using the high-level ipfs_kit API for daemon management."""
    print("\n=== Using High-Level API for Daemon Management ===")

    # Initialize ipfs_kit with Lotus integration
    kit = ipfs_kit(metadata={
        "auto_start_lotus_daemon": False  # Don't auto-start for this example
    })

    # Check daemon status through the high-level API
    status = kit.check_daemon_status()
    lotus_status = status.get("daemons", {}).get("lotus", {})

    print(f"Lotus daemon status: {lotus_status.get('running', False)}")

    # Start daemon if not running
    if not lotus_status.get("running", False):
        print("\nStarting Lotus daemon through high-level API...")
        result = kit._ensure_daemon_running("lotus")

        if result.get("success", False):
            print("Lotus daemon started successfully")
        else:
            print(f"Failed to start Lotus daemon: {result.get('error', 'Unknown error')}")

    # Run a simple Lotus API operation
    print("\nPerforming Lotus chain head operation...")
    chain_result = kit.lotus_kit.chain_head()

    if chain_result.get("success", False):
        height = chain_result.get("head", {}).get("Height", "unknown")
        print(f"Current chain height: {height}")
    else:
        print(f"Failed to get chain head: {chain_result.get('error', 'Unknown error')}")

    # For cleanup, stop the daemon
    print("\nStopping daemon for cleanup...")
    stop_result = kit.stop_daemons()

    if stop_result.get("success", False):
        print("Daemons stopped successfully")
    else:
        print(f"Error stopping daemons: {stop_result.get('error', 'Unknown error')}")

def main():
    """Run the macOS examples."""
    if not check_is_macos():
        return

    print("LOTUS DAEMON MANAGEMENT ON MACOS EXAMPLES")
    print("=========================================")

    # Run examples
    install_launchd_service_example()
    control_daemon_example()
    launchctl_management_example()
    enhanced_plist_example()
    high_level_api_example()

    print("\nExamples completed. Review the outputs above to learn about macOS Lotus daemon management.")

if __name__ == "__main__":
    main()
