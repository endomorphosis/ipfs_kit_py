#!/usr/bin/env python3
"""
Consolidated Daemon Manager for IPFS Kit

This script consolidates functionality from all daemon management scripts:
- start_ipfs_daemon.py
- start_aria2_daemon.py
- start_lotus_client.py
- start_mcp_with_daemon.py

It provides a comprehensive solution for managing various daemons used in IPFS Kit.
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import subprocess
import threading
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("daemon_manager")

class DaemonTypes:
    """Constants for supported daemon types."""
    IPFS = "ipfs"
    ARIA2 = "aria2"
    LOTUS = "lotus"
    ALL = "all"

    @classmethod
    def get_all(cls):
        """Get all supported daemon types."""
        return [cls.IPFS, cls.ARIA2, cls.LOTUS, cls.ALL]

class DaemonManager:
    """Manager for various daemons used in IPFS Kit."""

    def __init__(
        self,
        daemon_type: str = DaemonTypes.IPFS,
        config_dir: Optional[str] = None,
        work_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
        debug: bool = False,
        init_if_missing: bool = True,
        health_check: bool = True,
        health_check_interval: int = 30,
        api_port: Optional[int] = None,
        gateway_port: Optional[int] = None,
        swarm_port: Optional[int] = None,
        extra_args: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the daemon manager.

        Args:
            daemon_type: Type of daemon to manage (ipfs, aria2, lotus)
            config_dir: Directory for daemon configuration
            work_dir: Working directory for the daemon
            log_dir: Directory for daemon logs
            debug: Enable debug mode
            init_if_missing: Initialize daemon if not already initialized
            health_check: Enable health checking
            health_check_interval: Interval for health checks in seconds
            api_port: Port for API server
            gateway_port: Port for gateway (IPFS only)
            swarm_port: Port for swarm connections (IPFS only)
            extra_args: Additional command-line arguments
            config: Additional configuration options
        """
        self.daemon_type = daemon_type
        self.config_dir = config_dir or self._get_default_config_dir(daemon_type)
        self.work_dir = work_dir or os.path.join(os.path.expanduser("~"), f".{daemon_type}")
        self.log_dir = log_dir or os.path.join(os.path.expanduser("~"), f".{daemon_type}/logs")
        self.debug = debug
        self.init_if_missing = init_if_missing
        self.health_check = health_check
        self.health_check_interval = health_check_interval
        self.api_port = api_port or self._get_default_api_port(daemon_type)
        self.gateway_port = gateway_port or 8080
        self.swarm_port = swarm_port or 4001
        self.extra_args = extra_args or []
        self.config = config or {}

        # Process management
        self.process = None
        self.health_check_thread = None
        self.running = False
        self.stop_event = threading.Event()

        # Create directories if they don't exist
        self._ensure_directories()

        logger.info(f"Initialized daemon manager for {daemon_type}")

    def _get_default_config_dir(self, daemon_type: str) -> str:
        """Get default configuration directory for a daemon type."""
        home = os.path.expanduser("~")
        if daemon_type == DaemonTypes.IPFS:
            return os.path.join(home, ".ipfs")
        elif daemon_type == DaemonTypes.ARIA2:
            return os.path.join(home, ".aria2")
        elif daemon_type == DaemonTypes.LOTUS:
            return os.path.join(home, ".lotus")
        else:
            return os.path.join(home, f".{daemon_type}")

    def _get_default_api_port(self, daemon_type: str) -> int:
        """Get default API port for a daemon type."""
        if daemon_type == DaemonTypes.IPFS:
            return 5001
        elif daemon_type == DaemonTypes.ARIA2:
            return 6800
        elif daemon_type == DaemonTypes.LOTUS:
            return 1234
        else:
            return 9000

    def _ensure_directories(self):
        """Ensure required directories exist."""
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.work_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

    def is_initialized(self) -> bool:
        """Check if daemon is initialized."""
        if self.daemon_type == DaemonTypes.IPFS:
            # Check for IPFS config file
            config_file = os.path.join(self.config_dir, "config")
            return os.path.exists(config_file)
        elif self.daemon_type == DaemonTypes.ARIA2:
            # Aria2 doesn't need initialization
            return True
        elif self.daemon_type == DaemonTypes.LOTUS:
            # Check for Lotus data directory
            data_dir = os.path.join(self.config_dir, "datastore")
            return os.path.exists(data_dir)
        else:
            # Unknown daemon type, assume it's initialized
            return True

    def initialize(self) -> bool:
        """Initialize the daemon if needed."""
        if self.is_initialized():
            logger.info(f"{self.daemon_type} is already initialized")
            return True

        logger.info(f"Initializing {self.daemon_type}...")

        if self.daemon_type == DaemonTypes.IPFS:
            # Initialize IPFS
            cmd = ["ipfs", "init"]

            # Add extra initialization arguments
            if self.debug:
                cmd.append("--debug")

            # Use config directory if specified
            if self.config_dir:
                os.environ["IPFS_PATH"] = self.config_dir

            # Run initialization
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.info(f"IPFS initialized: {result.stdout.strip()}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to initialize IPFS: {e.stderr.strip()}")
                return False

        elif self.daemon_type == DaemonTypes.LOTUS:
            # Initialize Lotus
            cmd = ["lotus", "daemon", "--init", "--genesis=/dev/null"]

            # Add environment variables for Lotus
            env = os.environ.copy()
            env["LOTUS_PATH"] = self.config_dir

            # Run initialization
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
                logger.info(f"Lotus initialized: {result.stdout.strip()}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to initialize Lotus: {e.stderr.strip()}")
                return False

        else:
            logger.warning(f"Initialization not implemented for {self.daemon_type}")
            return False

    def start(self) -> bool:
        """Start the daemon."""
        if self.is_running():
            logger.info(f"{self.daemon_type} daemon is already running")
            return True

        # Initialize if needed
        if self.init_if_missing and not self.is_initialized():
            if not self.initialize():
                logger.error(f"Failed to initialize {self.daemon_type}, cannot start daemon")
                return False

        logger.info(f"Starting {self.daemon_type} daemon...")

        # Prepare command based on daemon type
        cmd = self._build_start_command()

        # Prepare environment
        env = self._prepare_environment()

        # Log file paths
        stdout_log = os.path.join(self.log_dir, f"{self.daemon_type}_stdout.log")
        stderr_log = os.path.join(self.log_dir, f"{self.daemon_type}_stderr.log")

        try:
            # Open log files
            stdout_file = open(stdout_log, "a")
            stderr_file = open(stderr_log, "a")

            # Start process
            self.process = subprocess.Popen(
                cmd,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=self.work_dir,
                start_new_session=True  # Detach from parent process
            )

            logger.info(f"Started {self.daemon_type} daemon (PID: {self.process.pid})")

            # Wait a moment to ensure process starts
            time.sleep(2)

            # Check if process is still running
            if self.process.poll() is not None:
                logger.error(f"{self.daemon_type} daemon failed to start (exit code: {self.process.returncode})")
                return False

            # Start health check if enabled
            if self.health_check:
                self._start_health_check()

            self.running = True
            return True

        except Exception as e:
            logger.error(f"Failed to start {self.daemon_type} daemon: {e}")
            return False

    def _build_start_command(self) -> List[str]:
        """Build command to start the daemon."""
        if self.daemon_type == DaemonTypes.IPFS:
            cmd = ["ipfs", "daemon"]

            # Add API port if specified
            if self.api_port:
                cmd.extend(["--api-addr", f"/ip4/127.0.0.1/tcp/{self.api_port}"])

            # Add gateway port if specified
            if self.gateway_port:
                cmd.extend(["--gateway-addr", f"/ip4/127.0.0.1/tcp/{self.gateway_port}"])

            # Add swarm port if specified
            if self.swarm_port:
                cmd.extend(["--swarm-addr", f"/ip4/0.0.0.0/tcp/{self.swarm_port}"])

            # Add debug flag if enabled
            if self.debug:
                cmd.append("--debug")

        elif self.daemon_type == DaemonTypes.ARIA2:
            cmd = ["aria2c", "--daemon=true", "--enable-rpc=true"]

            # Add RPC port if specified
            if self.api_port:
                cmd.append(f"--rpc-listen-port={self.api_port}")

            # Add configuration file if it exists
            config_file = os.path.join(self.config_dir, "aria2.conf")
            if os.path.exists(config_file):
                cmd.append(f"--conf-path={config_file}")

            # Add debug flag if enabled
            if self.debug:
                cmd.append("--log-level=debug")
                cmd.append(f"--log={os.path.join(self.log_dir, 'aria2.log')}")

        elif self.daemon_type == DaemonTypes.LOTUS:
            cmd = ["lotus", "daemon"]

            # Add API port if specified
            if self.api_port:
                cmd.extend(["--api", f"127.0.0.1:{self.api_port}"])

            # Add debug flag if enabled
            if self.debug:
                cmd.append("--debug")

        else:
            logger.warning(f"Unsupported daemon type: {self.daemon_type}")
            cmd = [self.daemon_type]

        # Add any extra arguments
        cmd.extend(self.extra_args)

        logger.debug(f"Command: {' '.join(cmd)}")
        return cmd

    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for the daemon."""
        env = os.environ.copy()

        if self.daemon_type == DaemonTypes.IPFS:
            env["IPFS_PATH"] = self.config_dir

        elif self.daemon_type == DaemonTypes.LOTUS:
            env["LOTUS_PATH"] = self.config_dir

        return env

    def stop(self) -> bool:
        """Stop the daemon."""
        if not self.is_running():
            logger.info(f"{self.daemon_type} daemon is not running")
            return True

        logger.info(f"Stopping {self.daemon_type} daemon...")

        # Stop health check thread
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.stop_event.set()
            self.health_check_thread.join(timeout=5)

        # Try graceful shutdown first
        success = self._graceful_shutdown()

        if not success or self.process.poll() is None:
            # If graceful shutdown failed, force kill the process
            try:
                logger.warning(f"Forcefully terminating {self.daemon_type} daemon")
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                # Wait for process to terminate
                for _ in range(10):
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.5)

                # If still not terminated, use SIGKILL
                if self.process.poll() is None:
                    logger.warning(f"Process did not terminate, using SIGKILL")
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    self.process.wait(timeout=5)

            except (ProcessLookupError, OSError) as e:
                logger.error(f"Error killing process: {e}")
                return False

        logger.info(f"Stopped {self.daemon_type} daemon")
        self.running = False
        self.process = None
        return True

    def _graceful_shutdown(self) -> bool:
        """Attempt graceful shutdown of the daemon."""
        try:
            if self.daemon_type == DaemonTypes.IPFS:
                # Use IPFS client to shut down
                shutdown_cmd = ["ipfs", "shutdown"]
                env = os.environ.copy()
                env["IPFS_PATH"] = self.config_dir

                result = subprocess.run(
                    shutdown_cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    logger.info("Graceful shutdown of IPFS succeeded")
                    return True
                else:
                    logger.warning(f"Graceful shutdown of IPFS failed: {result.stderr}")
                    return False

            elif self.daemon_type == DaemonTypes.ARIA2:
                # Aria2 doesn't have a clean shutdown method via CLI
                # We'll try to send SIGTERM to the process
                self.process.terminate()
                return self.process.wait(timeout=10) is not None

            elif self.daemon_type == DaemonTypes.LOTUS:
                # Use Lotus client to shut down
                shutdown_cmd = ["lotus", "daemon", "stop"]
                env = os.environ.copy()
                env["LOTUS_PATH"] = self.config_dir

                result = subprocess.run(
                    shutdown_cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    logger.info("Graceful shutdown of Lotus succeeded")
                    return True
                else:
                    logger.warning(f"Graceful shutdown of Lotus failed: {result.stderr}")
                    return False

            else:
                # Unknown daemon type, just send SIGTERM
                self.process.terminate()
                return self.process.wait(timeout=10) is not None

        except subprocess.TimeoutExpired:
            logger.warning(f"Graceful shutdown of {self.daemon_type} timed out")
            return False
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            return False

    def is_running(self) -> bool:
        """Check if daemon is running."""
        # If we have a process object, check its status
        if self.process is not None:
            if self.process.poll() is None:
                return True
            else:
                # Process has terminated
                self.running = False
                self.process = None
                return False

        # Otherwise check by checking the API
        if self.daemon_type == DaemonTypes.IPFS:
            try:
                cmd = ["ipfs", "id"]
                env = os.environ.copy()
                env["IPFS_PATH"] = self.config_dir

                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                return result.returncode == 0
            except Exception:
                return False

        elif self.daemon_type == DaemonTypes.ARIA2:
            import urllib.request
            import urllib.error

            try:
                url = f"http://localhost:{self.api_port}/jsonrpc"
                req = urllib.request.Request(
                    url,
                    data=json.dumps({
                        "jsonrpc": "2.0",
                        "method": "aria2.getVersion",
                        "id": "check",
                        "params": []
                    }).encode(),
                    headers={"Content-Type": "application/json"}
                )

                with urllib.request.urlopen(req, timeout=5):
                    return True
            except Exception:
                return False

        elif self.daemon_type == DaemonTypes.LOTUS:
            try:
                cmd = ["lotus", "net", "peers"]
                env = os.environ.copy()
                env["LOTUS_PATH"] = self.config_dir

                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                return result.returncode == 0
            except Exception:
                return False

        return False

    def _start_health_check(self):
        """Start a thread to periodically check daemon health."""
        if self.health_check_thread and self.health_check_thread.is_alive():
            # Already running
            return

        self.stop_event.clear()
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self.health_check_thread.start()

    def _health_check_loop(self):
        """Periodically check the health of the daemon."""
        logger.info(f"Starting health check for {self.daemon_type} daemon")

        while not self.stop_event.is_set():
            try:
                # Check if the daemon is still running
                if not self.is_running():
                    logger.warning(f"{self.daemon_type} daemon is not running, attempting to restart")

                    # Clear process reference
                    self.process = None

                    # Attempt to restart
                    if not self.start():
                        logger.error(f"Failed to restart {self.daemon_type} daemon")
                else:
                    logger.debug(f"{self.daemon_type} daemon health check: OK")

            except Exception as e:
                logger.error(f"Error during health check: {e}")

            # Wait for next check interval or until stop event
            self.stop_event.wait(self.health_check_interval)

        logger.info(f"Stopped health check for {self.daemon_type} daemon")

    def get_status(self) -> Dict[str, Any]:
        """Get daemon status information."""
        status = {
            "daemon_type": self.daemon_type,
            "running": self.is_running(),
            "initialized": self.is_initialized(),
            "config_dir": self.config_dir,
            "api_port": self.api_port
        }

        # Add daemon-specific information
        if self.daemon_type == DaemonTypes.IPFS:
            try:
                # Get IPFS ID information
                if status["running"]:
                    cmd = ["ipfs", "id", "--format=json"]
                    env = os.environ.copy()
                    env["IPFS_PATH"] = self.config_dir

                    result = subprocess.run(
                        cmd,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    if result.returncode == 0:
                        ipfs_info = json.loads(result.stdout)
                        status["peer_id"] = ipfs_info.get("ID")
                        status["addresses"] = ipfs_info.get("Addresses")
            except Exception as e:
                logger.error(f"Error getting IPFS status: {e}")

        elif self.daemon_type == DaemonTypes.LOTUS:
            try:
                # Get Lotus node information
                if status["running"]:
                    cmd = ["lotus", "net", "id"]
                    env = os.environ.copy()
                    env["LOTUS_PATH"] = self.config_dir

                    result = subprocess.run(
                        cmd,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    if result.returncode == 0:
                        status["peer_id"] = result.stdout.strip()
            except Exception as e:
                logger.error(f"Error getting Lotus status: {e}")

        # Add process information if available
        if self.process is not None:
            status["pid"] = self.process.pid

        return status


def main():
    """Run the daemon manager from command line."""
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Daemon Manager for IPFS Kit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Add common arguments
    parser.add_argument("--daemon", choices=DaemonTypes.get_all(), default=DaemonTypes.IPFS,
                  help="Daemon type to manage")
    parser.add_argument("--action", choices=["start", "stop", "restart", "status"], default="status",
                  help="Action to perform")
    parser.add_argument("--config-dir", help="Directory for daemon configuration")
    parser.add_argument("--work-dir", help="Working directory for the daemon")
    parser.add_argument("--log-dir", help="Directory for daemon logs")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-init", dest="init_if_missing", action="store_false",
                  help="Don't initialize daemon if missing")
    parser.add_argument("--no-health-check", dest="health_check", action="store_false",
                  help="Disable health checking")
    parser.add_argument("--health-check-interval", type=int, default=30,
                  help="Interval for health checks in seconds")
    parser.add_argument("--api-port", type=int, help="Port for API server")

    # IPFS-specific arguments
    ipfs_group = parser.add_argument_group("IPFS Options")
    ipfs_group.add_argument("--gateway-port", type=int, help="Port for IPFS gateway")
    ipfs_group.add_argument("--swarm-port", type=int, help="Port for IPFS swarm connections")

    # Extra arguments
    parser.add_argument("--extra-args", nargs=argparse.REMAINDER,
                  help="Additional command-line arguments for the daemon")

    # Parse arguments
    args = parser.parse_args()

    # Set logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create daemon manager
    manager = DaemonManager(
        daemon_type=args.daemon,
        config_dir=args.config_dir,
        work_dir=args.work_dir,
        log_dir=args.log_dir,
        debug=args.debug,
        init_if_missing=args.init_if_missing,
        health_check=args.health_check,
        health_check_interval=args.health_check_interval,
        api_port=args.api_port,
        gateway_port=args.gateway_port,
        swarm_port=args.swarm_port,
        extra_args=args.extra_args
    )

    # Perform action
    if args.action == "start":
        if manager.start():
            logger.info(f"{args.daemon} daemon started successfully")
            return 0
        else:
            logger.error(f"Failed to start {args.daemon} daemon")
            return 1

    elif args.action == "stop":
        if manager.stop():
            logger.info(f"{args.daemon} daemon stopped successfully")
            return 0
        else:
            logger.error(f"Failed to stop {args.daemon} daemon")
            return 1

    elif args.action == "restart":
        manager.stop()
        if manager.start():
            logger.info(f"{args.daemon} daemon restarted successfully")
            return 0
        else:
            logger.error(f"Failed to restart {args.daemon} daemon")
            return 1

    elif args.action == "status":
        status = manager.get_status()
        print(json.dumps(status, indent=2))
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
