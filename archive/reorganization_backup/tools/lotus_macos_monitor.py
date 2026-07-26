#!/usr/bin/env python3
"""
Lotus Daemon Monitoring Tool for macOS

This tool provides monitoring and health checking capabilities 
for Lotus daemons running on macOS via launchd.

Features:
- Daemon health checking
- Auto-recovery for crashed daemons
- Performance metrics collection
- Alert notifications (command line and/or email)
- Integration with launchd for better service management
"""

import os
import sys
import time
import json
import logging
import argparse
import platform
import subprocess
import shutil
import plistlib
import signal
import datetime
from pathlib import Path
import socket
import smtplib
from email.message import EmailMessage
import psutil


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.expanduser("~/Library/Logs/lotus_monitor.log"))
    ]
)
logger = logging.getLogger("lotus_macos_monitor")


class LotusMonitor:
    """Monitors and manages Lotus daemon on macOS."""
    
    def __init__(self, config_path=None):
        """Initialize the Lotus monitor.
        
        Args:
            config_path: Path to configuration file (JSON)
        """
        self.check_macos()
        
        # Set default configuration
        self.config = {
            "service_name": "com.user.lotusd",
            "lotus_path": os.path.expanduser("~/.lotus"),
            "check_interval": 60,  # seconds
            "auto_recover": True,
            "max_restart_attempts": 3,
            "restart_cooldown": 300,  # seconds
            "collect_metrics": True,
            "metrics_path": os.path.expanduser("~/Library/Logs/lotus_metrics.json"),
            "notification": {
                "enabled": False,
                "email": {
                    "enabled": False,
                    "smtp_server": "smtp.example.com",
                    "smtp_port": 587,
                    "username": "user@example.com",
                    "password": "",
                    "from_addr": "user@example.com",
                    "to_addr": "user@example.com",
                    "use_tls": True
                }
            },
            "resource_thresholds": {
                "cpu_percent": 90,
                "memory_percent": 80,
                "disk_percent": 90
            }
        }
        
        # Load configuration from file if provided
        if config_path:
            self.load_config(config_path)
            
        # Initialize state
        self.restart_attempts = 0
        self.last_restart_time = 0
        self.metrics_history = self._load_metrics_history()
        
        # Get user ID for launchctl commands
        self.user_id = os.getuid()
        
        # Ensure metrics directory exists
        os.makedirs(os.path.dirname(self.config["metrics_path"]), exist_ok=True)
        
        logger.info(f"Lotus Monitor initialized for service: {self.config['service_name']}")
    
    def check_macos(self):
        """Verify we're running on macOS."""
        if platform.system() != "Darwin":
            logger.error("This tool is designed for macOS only")
            sys.exit(1)
    
    def load_config(self, config_path):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                
            # Update the default config with user values
            self._deep_update(self.config, user_config)
            logger.info(f"Configuration loaded from {config_path}")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
    
    def _deep_update(self, d, u):
        """Recursively update a dictionary."""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
    
    def _load_metrics_history(self):
        """Load metrics history from file."""
        try:
            with open(self.config["metrics_path"], 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "daemon_starts": 0,
                "daemon_stops": 0,
                "daemon_crashes": 0,
                "auto_recoveries": 0,
                "uptime_seconds": 0,
                "last_start_time": None,
                "history": []
            }
    
    def _save_metrics_history(self):
        """Save metrics history to file."""
        try:
            with open(self.config["metrics_path"], 'w') as f:
                json.dump(self.metrics_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metrics: {str(e)}")
    
    def check_daemon_status(self):
        """Check if Lotus daemon is running using launchctl."""
        status = {
            "running": False,
            "pid": None,
            "uptime": 0,
            "status_code": None,
            "last_exit_reason": None,
            "resources": {},
            "api_responsive": False
        }
        
        # Check using launchctl list
        try:
            cmd = ["launchctl", "list"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Error running launchctl list: {result.stderr}")
            else:
                # Parse output to find service
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 3 and self.config["service_name"] in line:
                        pid_str = parts[0]
                        status_code = parts[1]
                        
                        if pid_str.isdigit() and int(pid_str) > 0:
                            status["running"] = True
                            status["pid"] = int(pid_str)
                            status["status_code"] = status_code
                        break
        except Exception as e:
            logger.error(f"Error checking launchctl status: {str(e)}")
            
        # Get more detailed info using launchctl print
        if status["running"]:
            try:
                cmd = ["launchctl", "print", f"gui/{self.user_id}/{self.config['service_name']}"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # Parse the output
                    lines = result.stdout.splitlines()
                    for line in lines:
                        if "last exit reason" in line.lower():
                            status["last_exit_reason"] = line.strip()
                            
                    # Get process info using psutil
                    if status["pid"]:
                        try:
                            proc = psutil.Process(status["pid"])
                            status["resources"] = {
                                "cpu_percent": proc.cpu_percent(interval=0.5),
                                "memory_percent": proc.memory_percent(),
                                "memory_info": {
                                    "rss": proc.memory_info().rss,
                                    "vms": proc.memory_info().vms
                                },
                                "num_threads": proc.num_threads(),
                                "open_files": len(proc.open_files()),
                                "connections": len(proc.connections())
                            }
                            
                            # Calculate uptime
                            proc_create_time = proc.create_time()
                            status["uptime"] = time.time() - proc_create_time
                            
                            # Update metrics
                            if self.metrics_history.get("last_start_time") is None:
                                self.metrics_history["last_start_time"] = proc_create_time
                                self.metrics_history["daemon_starts"] += 1
                                self._save_metrics_history()
                        except psutil.NoSuchProcess:
                            logger.warning(f"Process with PID {status['pid']} no longer exists")
                            status["running"] = False
                        except Exception as e:
                            logger.error(f"Error getting process info: {str(e)}")
            except Exception as e:
                logger.error(f"Error getting detailed service info: {str(e)}")
        
        # Check API responsiveness
        if status["running"]:
            try:
                # Try calling a simple API method (chain head)
                cmd = ["lotus", "chain", "head"]
                env = os.environ.copy()
                env["LOTUS_PATH"] = self.config["lotus_path"]
                
                api_result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=5,
                    env=env
                )
                
                status["api_responsive"] = api_result.returncode == 0
                if not status["api_responsive"]:
                    logger.warning(f"API not responsive: {api_result.stderr}")
            except subprocess.TimeoutExpired:
                logger.warning("API check timed out")
                status["api_responsive"] = False
            except Exception as e:
                logger.error(f"Error checking API: {str(e)}")
                status["api_responsive"] = False
        
        return status
    
    def restart_daemon(self):
        """Restart the Lotus daemon using launchctl."""
        if time.time() - self.last_restart_time < self.config["restart_cooldown"]:
            logger.warning("Skipping restart - in cooldown period")
            return False
            
        if self.restart_attempts >= self.config["max_restart_attempts"]:
            logger.error("Maximum restart attempts reached - giving up")
            self.send_notification(
                "Lotus Daemon Recovery Failed", 
                f"Failed to restart daemon after {self.restart_attempts} attempts"
            )
            return False
            
        logger.info(f"Attempting to restart Lotus daemon (attempt {self.restart_attempts + 1})")
        
        # First stop the service
        try:
            cmd = ["launchctl", "unload", self._get_plist_path()]
            unload_result = subprocess.run(cmd, capture_output=True, text=True)
            
            if unload_result.returncode != 0:
                logger.error(f"Error unloading service: {unload_result.stderr}")
        except Exception as e:
            logger.error(f"Error unloading service: {str(e)}")
        
        # Check for lock file and remove if necessary
        self._check_and_clear_locks()
        
        # Reload the service
        try:
            cmd = ["launchctl", "load", self._get_plist_path()]
            load_result = subprocess.run(cmd, capture_output=True, text=True)
            
            if load_result.returncode != 0:
                logger.error(f"Error loading service: {load_result.stderr}")
                self.restart_attempts += 1
                self.last_restart_time = time.time()
                return False
                
            logger.info("Service reloaded successfully")
            
            # Wait a bit for the service to start
            time.sleep(5)
            
            # Check if it's running
            status = self.check_daemon_status()
            if status["running"]:
                logger.info(f"Daemon successfully restarted with PID {status['pid']}")
                self.restart_attempts = 0
                self.last_restart_time = time.time()
                
                # Update metrics
                self.metrics_history["auto_recoveries"] += 1
                self.metrics_history["last_start_time"] = time.time()
                self.metrics_history["daemon_starts"] += 1
                self._save_metrics_history()
                
                self.send_notification(
                    "Lotus Daemon Recovered", 
                    f"Lotus daemon was successfully restarted"
                )
                
                return True
            else:
                logger.error("Daemon failed to start after reload")
                self.restart_attempts += 1
                self.last_restart_time = time.time()
                return False
                
        except Exception as e:
            logger.error(f"Error restarting service: {str(e)}")
            self.restart_attempts += 1
            self.last_restart_time = time.time()
            return False
    
    def _check_and_clear_locks(self):
        """Check for and remove stale lock files."""
        repo_lock = os.path.join(self.config["lotus_path"], "repo.lock")
        api_lock = os.path.join(self.config["lotus_path"], "api")
        
        if os.path.exists(repo_lock):
            logger.info(f"Removing stale lock file: {repo_lock}")
            try:
                os.remove(repo_lock)
            except Exception as e:
                logger.error(f"Error removing repo lock: {str(e)}")
                
        if os.path.exists(api_lock):
            logger.info(f"Removing API socket: {api_lock}")
            try:
                os.remove(api_lock)
            except Exception as e:
                logger.error(f"Error removing API socket: {str(e)}")
    
    def _get_plist_path(self):
        """Get the path to the launchd plist file."""
        return os.path.expanduser(f"~/Library/LaunchAgents/{self.config['service_name']}.plist")
    
    def collect_system_metrics(self):
        """Collect system-wide metrics."""
        metrics = {
            "timestamp": time.time(),
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count(),
                "freq": psutil.cpu_freq().current if psutil.cpu_freq() else None
            },
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            },
            "network": {
                "connections": len(psutil.net_connections()),
                "stats": {
                    k: v for k, v in psutil.net_io_counters(pernic=True).items()
                    if k in ['en0', 'en1', 'lo0']  # Common macOS interfaces
                }
            }
        }
        
        # Get lotus path disk usage
        try:
            lotus_usage = psutil.disk_usage(self.config["lotus_path"])
            metrics["lotus_disk"] = {
                "total": lotus_usage.total,
                "used": lotus_usage.used,
                "free": lotus_usage.free,
                "percent": lotus_usage.percent
            }
        except:
            # May fail if on different filesystem
            pass
            
        # Check if any metrics exceed thresholds
        alerts = []
        thresholds = self.config["resource_thresholds"]
        
        if metrics["cpu"]["percent"] > thresholds["cpu_percent"]:
            alerts.append(f"CPU usage at {metrics['cpu']['percent']}% (threshold: {thresholds['cpu_percent']}%)")
            
        if metrics["memory"]["percent"] > thresholds["memory_percent"]:
            alerts.append(f"Memory usage at {metrics['memory']['percent']}% (threshold: {thresholds['memory_percent']}%)")
            
        if metrics["disk"]["percent"] > thresholds["disk_percent"]:
            alerts.append(f"Disk usage at {metrics['disk']['percent']}% (threshold: {thresholds['disk_percent']}%)")
            
        if alerts and self.config["notification"]["enabled"]:
            self.send_notification(
                "Lotus Resource Alert", 
                "Resource usage exceeds thresholds:\n" + "\n".join(alerts)
            )
            
        return metrics
    
    def update_metrics(self, status, system_metrics):
        """Update and save metrics history."""
        if not self.config["collect_metrics"]:
            return
            
        # Create a new metric point
        metric_point = {
            "timestamp": time.time(),
            "running": status["running"],
            "uptime": status["uptime"] if status["running"] else 0,
            "api_responsive": status["api_responsive"],
            "resources": status.get("resources", {}),
            "system": system_metrics
        }
        
        # Add to history, keeping only the last 1000 points
        self.metrics_history["history"].append(metric_point)
        if len(self.metrics_history["history"]) > 1000:
            self.metrics_history["history"] = self.metrics_history["history"][-1000:]
            
        # Update uptime if running
        if status["running"] and self.metrics_history.get("last_start_time"):
            self.metrics_history["uptime_seconds"] = int(time.time() - self.metrics_history["last_start_time"])
            
        # Save metrics
        self._save_metrics_history()
    
    def send_notification(self, subject, message):
        """Send a notification about daemon status."""
        if not self.config["notification"]["enabled"]:
            return
            
        # Always log the notification
        logger.info(f"NOTIFICATION: {subject} - {message}")
        
        # Send email if configured
        if self.config["notification"]["email"]["enabled"]:
            try:
                email_config = self.config["notification"]["email"]
                
                msg = EmailMessage()
                msg.set_content(message)
                msg["Subject"] = f"[Lotus Monitor] {subject}"
                msg["From"] = email_config["from_addr"]
                msg["To"] = email_config["to_addr"]
                
                server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
                
                if email_config["use_tls"]:
                    server.starttls()
                    
                if email_config["username"] and email_config["password"]:
                    server.login(email_config["username"], email_config["password"])
                    
                server.send_message(msg)
                server.quit()
                
                logger.info(f"Email notification sent: {subject}")
                
            except Exception as e:
                logger.error(f"Error sending email notification: {str(e)}")
    
    def generate_report(self):
        """Generate a detailed status report."""
        status = self.check_daemon_status()
        system_metrics = self.collect_system_metrics()
        
        report = [
            f"Lotus Daemon Status Report - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'=' * 50}",
            f"Service Name: {self.config['service_name']}",
            f"Lotus Path: {self.config['lotus_path']}",
            f"",
            f"DAEMON STATUS",
            f"  Running: {status['running']}",
            f"  PID: {status['pid']}",
            f"  Uptime: {datetime.timedelta(seconds=int(status['uptime']))}",
            f"  API Responsive: {status['api_responsive']}",
            f"  Last Exit Reason: {status['last_exit_reason']}",
            f"",
            f"RESOURCE USAGE",
        ]
        
        if status["resources"]:
            report.extend([
                f"  CPU: {status['resources'].get('cpu_percent', 'N/A')}%",
                f"  Memory: {status['resources'].get('memory_percent', 'N/A')}%",
                f"  Threads: {status['resources'].get('num_threads', 'N/A')}",
                f"  Open Files: {status['resources'].get('open_files', 'N/A')}",
                f"  Network Connections: {status['resources'].get('connections', 'N/A')}",
            ])
        else:
            report.append("  No resource data available")
            
        report.extend([
            f"",
            f"SYSTEM RESOURCES",
            f"  CPU Usage: {system_metrics['cpu']['percent']}%",
            f"  Memory Usage: {system_metrics['memory']['percent']}%",
            f"  Disk Usage: {system_metrics['disk']['percent']}%",
            f"",
            f"METRICS SUMMARY",
            f"  Total Starts: {self.metrics_history['daemon_starts']}",
            f"  Total Stops: {self.metrics_history['daemon_stops']}",
            f"  Crashes: {self.metrics_history['daemon_crashes']}",
            f"  Auto-Recoveries: {self.metrics_history['auto_recoveries']}",
            f"  Total Uptime: {datetime.timedelta(seconds=self.metrics_history['uptime_seconds'])}",
            f"",
            f"PLIST INFORMATION",
        ])
        
        # Add plist details
        plist_path = self._get_plist_path()
        if os.path.exists(plist_path):
            try:
                with open(plist_path, 'rb') as f:
                    plist_data = plistlib.load(f)
                    
                # Extract key information
                report.extend([
                    f"  Label: {plist_data.get('Label', 'N/A')}",
                    f"  RunAtLoad: {plist_data.get('RunAtLoad', 'N/A')}",
                    f"  KeepAlive: {plist_data.get('KeepAlive', 'N/A')}",
                    f"  WorkingDirectory: {plist_data.get('WorkingDirectory', 'N/A')}",
                    f"  StandardOutPath: {plist_data.get('StandardOutPath', 'N/A')}",
                    f"  StandardErrorPath: {plist_data.get('StandardErrorPath', 'N/A')}",
                ])
                
                # Add environment variables if present
                if "EnvironmentVariables" in plist_data:
                    report.append(f"  Environment Variables:")
                    for k, v in plist_data["EnvironmentVariables"].items():
                        report.append(f"    {k}: {v}")
            except Exception as e:
                report.append(f"  Error reading plist: {str(e)}")
        else:
            report.append(f"  Plist file not found: {plist_path}")
        
        return "\n".join(report)
    
    def check_and_recover(self):
        """Check daemon status and recover if needed."""
        logger.info("Performing daemon health check")
        
        status = self.check_daemon_status()
        system_metrics = self.collect_system_metrics()
        
        # Update metrics
        self.update_metrics(status, system_metrics)
        
        # Check if need to recover
        needs_recovery = False
        recovery_reason = ""
        
        if not status["running"]:
            needs_recovery = True
            recovery_reason = "Daemon not running"
            self.metrics_history["daemon_crashes"] += 1
            self._save_metrics_history()
        elif not status["api_responsive"]:
            needs_recovery = True
            recovery_reason = "API not responsive"
        
        # Attempt recovery if needed and enabled
        if needs_recovery and self.config["auto_recover"]:
            logger.warning(f"Recovery needed: {recovery_reason}")
            self.send_notification(
                "Lotus Daemon Recovery Needed", 
                f"Recovery reason: {recovery_reason}"
            )
            self.restart_daemon()
        elif needs_recovery:
            logger.warning(f"Recovery needed but auto-recover disabled: {recovery_reason}")
            self.send_notification(
                "Lotus Daemon Issue Detected", 
                f"Issue detected but auto-recovery disabled: {recovery_reason}"
            )
        else:
            logger.info("Daemon is healthy")
        
        return {
            "status": status,
            "system_metrics": system_metrics,
            "needs_recovery": needs_recovery,
            "recovery_reason": recovery_reason if needs_recovery else None
        }
    
    def optimize_plist(self):
        """Optimize the daemon's plist file for better performance."""
        plist_path = self._get_plist_path()
        
        if not os.path.exists(plist_path):
            logger.error(f"Plist file not found at {plist_path}")
            return False
            
        logger.info(f"Optimizing plist file: {plist_path}")
        
        try:
            # Read existing plist
            with open(plist_path, 'rb') as f:
                plist_data = plistlib.load(f)
                
            # Create backup
            backup_path = f"{plist_path}.bak"
            shutil.copy2(plist_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
            
            # Optimize settings
            
            # 1. Enhance KeepAlive with better restart behavior
            if isinstance(plist_data.get('KeepAlive'), bool):
                # Convert simple boolean to dictionary for more control
                plist_data['KeepAlive'] = {
                    'Crashed': True,
                    'SuccessfulExit': False,
                    'NetworkState': True  # Only run when network available
                }
            elif isinstance(plist_data.get('KeepAlive'), dict):
                # Update existing dictionary
                keep_alive = plist_data['KeepAlive']
                keep_alive['Crashed'] = True
                keep_alive['SuccessfulExit'] = False
                keep_alive['NetworkState'] = True
            else:
                # Create new dictionary
                plist_data['KeepAlive'] = {
                    'Crashed': True,
                    'SuccessfulExit': False,
                    'NetworkState': True
                }
                
            # 2. Add ThrottleInterval to prevent rapid respawning
            plist_data['ThrottleInterval'] = 30
            
            # 3. Move logs to better location
            home_dir = os.path.expanduser("~")
            log_dir = os.path.join(home_dir, "Library/Logs/lotus")
            os.makedirs(log_dir, exist_ok=True)
            
            plist_data['StandardOutPath'] = os.path.join(log_dir, "lotus.daemon.out")
            plist_data['StandardErrorPath'] = os.path.join(log_dir, "lotus.daemon.err")
            
            # 4. Add resource limits
            plist_data['LowPriorityIO'] = True  # Reduce I/O priority
            plist_data['Nice'] = 5  # Lower CPU priority (higher number = lower priority)
            plist_data['WorkingDirectory'] = home_dir
            
            # 5. Memory and file limits
            plist_data['SoftResourceLimits'] = {
                'NumberOfFiles': 8192,
                'NumberOfProcesses': 512
            }
            
            # 6. Process type
            plist_data['ProcessType'] = 'Background'
            
            # Write optimized plist
            with open(plist_path, 'wb') as f:
                plistlib.dump(plist_data, f)
                
            logger.info("Plist optimization complete")
            
            # Reload service for changes to take effect
            try:
                subprocess.run(["launchctl", "unload", plist_path], capture_output=True, check=False)
                subprocess.run(["launchctl", "load", plist_path], capture_output=True, check=False)
                logger.info("Service reloaded with optimized configuration")
            except Exception as e:
                logger.error(f"Error reloading service: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing plist: {str(e)}")
            return False
    
    def run_monitor_loop(self):
        """Run the monitoring loop."""
        logger.info(f"Starting Lotus monitor loop with {self.config['check_interval']}s interval")
        try:
            while True:
                self.check_and_recover()
                time.sleep(self.config["check_interval"])
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
        except Exception as e:
            logger.error(f"Error in monitor loop: {str(e)}")
    
    def run_single_check(self):
        """Run a single health check."""
        result = self.check_and_recover()
        return result


def setup_argparse():
    """Set up command line argument parsing."""
    parser = argparse.ArgumentParser(description="Lotus Daemon Monitor for macOS")
    
    # Main commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Start continuous monitoring")
    monitor_parser.add_argument("--config", help="Path to configuration file")
    monitor_parser.add_argument("--interval", type=int, help="Check interval in seconds")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check current status")
    status_parser.add_argument("--config", help="Path to configuration file")
    status_parser.add_argument("--service", help="Service name")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate detailed report")
    report_parser.add_argument("--config", help="Path to configuration file")
    report_parser.add_argument("--output", help="Output file for report")
    
    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart daemon")
    restart_parser.add_argument("--config", help="Path to configuration file")
    restart_parser.add_argument("--force", action="store_true", help="Force restart")
    
    # Optimize command
    optimize_parser = subparsers.add_parser("optimize", help="Optimize plist configuration")
    optimize_parser.add_argument("--config", help="Path to configuration file")
    optimize_parser.add_argument("--backup", action="store_true", help="Create backup only")
    
    # Optional global arguments
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    return parser


def main():
    """Main entry point."""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Set log level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Initialize monitor
    monitor = LotusMonitor(config_path=args.config)
    
    # Override config with command line arguments
    if hasattr(args, "interval") and args.interval:
        monitor.config["check_interval"] = args.interval
    
    if hasattr(args, "service") and args.service:
        monitor.config["service_name"] = args.service
    
    # Execute command
    if args.command == "monitor":
        monitor.run_monitor_loop()
        
    elif args.command == "status":
        status = monitor.check_daemon_status()
        system_metrics = monitor.collect_system_metrics()
        
        print(f"Lotus Daemon Status ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"Running: {status['running']}")
        
        if status["running"]:
            print(f"PID: {status['pid']}")
            print(f"Uptime: {datetime.timedelta(seconds=int(status['uptime']))}")
            print(f"API Responsive: {status['api_responsive']}")
            
            if status["resources"]:
                print(f"CPU Usage: {status['resources'].get('cpu_percent', 'N/A')}%")
                print(f"Memory Usage: {status['resources'].get('memory_percent', 'N/A')}%")
                print(f"Threads: {status['resources'].get('num_threads', 'N/A')}")
        else:
            print(f"Last Exit Reason: {status['last_exit_reason']}")
            
    elif args.command == "report":
        report = monitor.generate_report()
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Report written to {args.output}")
        else:
            print(report)
            
    elif args.command == "restart":
        if args.force:
            monitor.restart_attempts = 0
            monitor.last_restart_time = 0
            
        result = monitor.restart_daemon()
        print(f"Restart {'successful' if result else 'failed'}")
        
    elif args.command == "optimize":
        if args.backup:
            plist_path = monitor._get_plist_path()
            backup_path = f"{plist_path}.bak"
            shutil.copy2(plist_path, backup_path)
            print(f"Backup created at {backup_path}")
        else:
            result = monitor.optimize_plist()
            print(f"Optimization {'successful' if result else 'failed'}")
    else:
        # Default to showing status if no command specified
        status = monitor.check_daemon_status()
        if status["running"]:
            print(f"Lotus daemon is running with PID {status['pid']}")
            if status["api_responsive"]:
                print("API is responsive")
            else:
                print("API is not responsive")
        else:
            print("Lotus daemon is not running")
        

if __name__ == "__main__":
    main()