#!/usr/bin/env python3
"""
First-Time Installation and Configuration Monitor

This script monitors the installation and configuration process when the package
is installed for the first time. It tracks dependency installation, configuration
file creation, daemon setup, and provides detailed progress reporting.

Usage:
    # Monitor a pip installation
    python monitor_first_install.py --command "pip install -e ."
    
    # Monitor with specific Python version
    python monitor_first_install.py --command "pip install ipfs-kit-py" --python python3.11
    
    # Monitor configuration only (after install)
    python monitor_first_install.py --config-only
    
    # Verify installation
    python monitor_first_install.py --verify
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class InstallationMonitor:
    """Monitor first-time installation and configuration."""
    
    def __init__(self, log_dir: str = "/tmp/install_monitor"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.start_time = time.time()
        self.install_log = []
        self.metrics = {
            "system_info": self._collect_system_info(),
            "installation_steps": [],
            "configuration_steps": [],
            "errors": [],
            "warnings": []
        }
        
    def _collect_system_info(self) -> Dict:
        """Collect system information."""
        info = {
            "architecture": platform.machine(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "python_executable": sys.executable,
            "timestamp": datetime.now().isoformat(),
            "os_type": platform.system(),
            "os_release": platform.release()
        }
        
        # Check CPU info
        if platform.system() == "Linux":
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    info["cpu_count"] = cpuinfo.count('processor')
                    # Extract CPU model
                    for line in cpuinfo.split('\n'):
                        if 'model name' in line:
                            info["cpu_model"] = line.split(':')[1].strip()
                            break
            except:
                pass
        
        info["cpu_count"] = info.get("cpu_count", os.cpu_count())
        
        # Check memory
        if platform.system() == "Linux":
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    for line in meminfo.split('\n'):
                        if line.startswith('MemTotal:'):
                            info["memory_total_kb"] = line.split()[1]
                        elif line.startswith('MemAvailable:'):
                            info["memory_available_kb"] = line.split()[1]
            except:
                pass
        
        # Check disk space
        try:
            stat = shutil.disk_usage("/")
            info["disk_total_gb"] = round(stat.total / (1024**3), 2)
            info["disk_free_gb"] = round(stat.free / (1024**3), 2)
        except:
            pass
        
        return info
    
    def log_step(self, step_name: str, status: str, details: Optional[str] = None,
                 step_type: str = "installation"):
        """Log an installation or configuration step."""
        timestamp = datetime.now().isoformat()
        elapsed = time.time() - self.start_time
        
        entry = {
            "timestamp": timestamp,
            "elapsed_seconds": round(elapsed, 2),
            "step": step_name,
            "status": status,
            "details": details,
            "type": step_type
        }
        
        if step_type == "installation":
            self.metrics["installation_steps"].append(entry)
        elif step_type == "configuration":
            self.metrics["configuration_steps"].append(entry)
        
        self.install_log.append(entry)
        
        # Print to console with formatting
        status_symbol = {
            "start": "🔄",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "skip": "⏭️"
        }.get(status, "•")
        
        print(f"{status_symbol} [{elapsed:.1f}s] {step_name}")
        if details:
            for line in details.split('\n'):
                if line.strip():
                    print(f"   {line}")
    
    def run_command(self, command: List[str], step_name: str,
                   capture_output: bool = True, check: bool = False) -> Tuple[int, str, str]:
        """Run a command and monitor its execution."""
        self.log_step(step_name, "start", f"Running: {' '.join(command)}")
        
        start = time.time()
        
        try:
            if capture_output:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
                returncode = result.returncode
                stdout = result.stdout
                stderr = result.stderr
            else:
                result = subprocess.run(command, timeout=600)
                returncode = result.returncode
                stdout = ""
                stderr = ""
            
            duration = time.time() - start
            
            if returncode == 0:
                self.log_step(
                    step_name, "success",
                    f"Completed in {duration:.1f}s"
                )
            else:
                error_detail = stderr[:500] if stderr else "Command failed"
                self.log_step(
                    step_name, "error",
                    f"Failed with exit code {returncode}\n{error_detail}"
                )
                self.metrics["errors"].append({
                    "step": step_name,
                    "error": error_detail,
                    "exit_code": returncode
                })
            
            return returncode, stdout, stderr
            
        except subprocess.TimeoutExpired:
            self.log_step(step_name, "error", "Command timed out after 10 minutes")
            self.metrics["errors"].append({
                "step": step_name,
                "error": "Timeout",
                "exit_code": -1
            })
            return -1, "", "Timeout"
        except Exception as e:
            self.log_step(step_name, "error", f"Exception: {str(e)}")
            self.metrics["errors"].append({
                "step": step_name,
                "error": str(e),
                "exit_code": -2
            })
            return -2, "", str(e)
    
    def check_binary_available(self, binary: str, description: str) -> bool:
        """Check if a binary is available."""
        self.log_step(f"Check {description}", "start", step_type="configuration")
        
        path = shutil.which(binary)
        if path:
            # Try to get version
            version = ""
            try:
                result = subprocess.run(
                    [binary, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                version = result.stdout.split('\n')[0] if result.returncode == 0 else ""
            except:
                pass
            
            self.log_step(
                f"Check {description}", "success",
                f"Found at {path}\n{version}",
                step_type="configuration"
            )
            return True
        else:
            self.log_step(
                f"Check {description}", "warning",
                f"{binary} not found in PATH",
                step_type="configuration"
            )
            self.metrics["warnings"].append({
                "check": description,
                "binary": binary,
                "issue": "not found"
            })
            return False
    
    def check_python_package(self, package: str, import_name: Optional[str] = None) -> bool:
        """Check if a Python package is installed."""
        if import_name is None:
            import_name = package
        
        self.log_step(f"Check Python package: {package}", "start", step_type="configuration")
        
        try:
            __import__(import_name)
            # Try to get version
            try:
                mod = __import__(import_name)
                version = getattr(mod, "__version__", "unknown")
                self.log_step(
                    f"Check Python package: {package}", "success",
                    f"Version: {version}",
                    step_type="configuration"
                )
            except:
                self.log_step(
                    f"Check Python package: {package}", "success",
                    "Installed",
                    step_type="configuration"
                )
            return True
        except ImportError:
            self.log_step(
                f"Check Python package: {package}", "warning",
                f"Package {package} not importable",
                step_type="configuration"
            )
            self.metrics["warnings"].append({
                "check": f"Python package: {package}",
                "issue": "not importable"
            })
            return False
    
    def check_config_file(self, path: Path, description: str) -> bool:
        """Check if a configuration file exists."""
        self.log_step(f"Check config: {description}", "start", step_type="configuration")
        
        if path.exists():
            size = path.stat().st_size
            self.log_step(
                f"Check config: {description}", "success",
                f"Found at {path} ({size} bytes)",
                step_type="configuration"
            )
            return True
        else:
            self.log_step(
                f"Check config: {description}", "info",
                f"Not found at {path} (may be created on first use)",
                step_type="configuration"
            )
            return False
    
    def monitor_installation(self, command: str, python_bin: str = "python3"):
        """Monitor the installation process."""
        print("=" * 60)
        print("Installation Monitoring Started")
        print("=" * 60)
        print("")
        
        # Pre-installation checks
        print("\n📋 Pre-Installation Checks\n")
        self.log_step("Pre-installation checks", "start", step_type="installation")
        
        # Check Python
        returncode, stdout, _ = self.run_command(
            [python_bin, "--version"],
            "Check Python version"
        )
        
        # Check pip
        returncode, stdout, _ = self.run_command(
            [python_bin, "-m", "pip", "--version"],
            "Check pip version"
        )
        
        # Check basic build tools
        self.check_binary_available("gcc", "GCC compiler")
        self.check_binary_available("git", "Git")
        self.check_binary_available("make", "Make")
        
        # Run installation command
        print("\n📦 Running Installation\n")
        cmd_parts = command.split()
        returncode, stdout, stderr = self.run_command(
            cmd_parts,
            "Install package",
            capture_output=True
        )
        
        # Save installation output
        install_log_file = self.log_dir / "installation_output.log"
        with open(install_log_file, "w") as f:
            f.write("=== STDOUT ===\n")
            f.write(stdout)
            f.write("\n\n=== STDERR ===\n")
            f.write(stderr)
        
        print(f"   💾 Installation output saved to: {install_log_file}")
        
        if returncode != 0:
            print("\n❌ Installation failed!")
            self.generate_report()
            return False
        
        # Post-installation verification
        print("\n✅ Installation Completed\n")
        self.verify_installation()
        
        # Configuration checks
        print("\n⚙️ Configuration Checks\n")
        self.check_configuration()
        
        self.generate_report()
        return True
    
    def verify_installation(self):
        """Verify the installation."""
        self.log_step("Post-installation verification", "start", step_type="configuration")
        
        # Check if package is importable
        packages_to_check = [
            ("ipfs_kit_py", "ipfs_kit_py"),
            ("ipfs_kit_py.ipfs_kit", "ipfs_kit"),
            ("ipfs_kit_py.daemon_config_manager", "daemon config manager"),
        ]
        
        for package, description in packages_to_check:
            self.check_python_package(package, description)
        
        # Check CLI availability
        self.check_binary_available("ipfs-kit", "IPFS Kit CLI")
    
    def check_configuration(self):
        """Check configuration files and directories."""
        self.log_step("Configuration checks", "start", step_type="configuration")
        
        home = Path.home()
        
        # Check common config directories
        config_dirs = [
            (home / ".ipfs_kit", "IPFS Kit config directory"),
            (home / ".ipfs", "IPFS config directory"),
            (home / ".lotus", "Lotus config directory"),
        ]
        
        for config_dir, description in config_dirs:
            self.check_config_file(config_dir, description)
        
        # Check specific config files
        config_files = [
            (home / ".ipfs_kit" / "config.json", "IPFS Kit config"),
            (home / ".ipfs" / "config", "IPFS daemon config"),
        ]
        
        for config_file, description in config_files:
            self.check_config_file(config_file, description)
    
    def generate_report(self):
        """Generate monitoring report."""
        print("\n" + "=" * 60)
        print("Installation Monitoring Report")
        print("=" * 60)
        
        elapsed = time.time() - self.start_time
        
        # Console summary
        print(f"\n⏱️ Total Duration: {elapsed:.1f}s")
        print(f"\n📊 Summary:")
        print(f"   • Installation steps: {len(self.metrics['installation_steps'])}")
        print(f"   • Configuration steps: {len(self.metrics['configuration_steps'])}")
        print(f"   • Errors: {len(self.metrics['errors'])}")
        print(f"   • Warnings: {len(self.metrics['warnings'])}")
        
        if self.metrics['errors']:
            print(f"\n❌ Errors encountered:")
            for error in self.metrics['errors']:
                print(f"   • {error['step']}: {error['error'][:100]}")
        
        if self.metrics['warnings']:
            print(f"\n⚠️ Warnings:")
            for warning in self.metrics['warnings']:
                print(f"   • {warning.get('check', warning.get('step', 'Unknown'))}")
        
        # Save detailed report
        report_file = self.log_dir / "installation_report.md"
        with open(report_file, "w") as f:
            f.write("# First-Time Installation Monitoring Report\n\n")
            f.write(f"**Generated**: {datetime.now().isoformat()}\n")
            f.write(f"**Duration**: {elapsed:.1f}s\n\n")
            
            f.write("## System Information\n\n")
            for key, value in self.metrics["system_info"].items():
                f.write(f"- **{key}**: {value}\n")
            
            f.write("\n## Installation Steps\n\n")
            for step in self.metrics["installation_steps"]:
                icon = {"success": "✅", "error": "❌", "warning": "⚠️", "start": "🔄"}.get(step["status"], "•")
                f.write(f"- {icon} [{step['elapsed_seconds']}s] **{step['step']}**: {step['status']}\n")
                if step.get("details"):
                    f.write(f"  - {step['details']}\n")
            
            f.write("\n## Configuration Steps\n\n")
            for step in self.metrics["configuration_steps"]:
                icon = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(step["status"], "•")
                f.write(f"- {icon} **{step['step']}**: {step['status']}\n")
                if step.get("details"):
                    f.write(f"  - {step['details']}\n")
            
            if self.metrics["errors"]:
                f.write("\n## Errors\n\n")
                for error in self.metrics["errors"]:
                    f.write(f"- **{error['step']}**\n")
                    f.write(f"  - Error: {error['error']}\n")
                    f.write(f"  - Exit code: {error.get('exit_code', 'N/A')}\n")
            
            if self.metrics["warnings"]:
                f.write("\n## Warnings\n\n")
                for warning in self.metrics["warnings"]:
                    f.write(f"- {warning.get('check', 'Unknown')}: {warning.get('issue', 'N/A')}\n")
        
        print(f"\n📄 Detailed report: {report_file}")
        
        # Save metrics JSON
        metrics_file = self.log_dir / "installation_metrics.json"
        with open(metrics_file, "w") as f:
            json.dump(self.metrics, f, indent=2)
        print(f"📄 Metrics data: {metrics_file}")
        
        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Monitor first-time installation and configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor pip install from current directory
  python monitor_first_install.py --command "pip install -e ."
  
  # Monitor pip install from PyPI
  python monitor_first_install.py --command "pip install ipfs-kit-py"
  
  # Monitor with specific Python version
  python monitor_first_install.py --command "pip install ipfs-kit-py" --python python3.11
  
  # Only verify existing installation
  python monitor_first_install.py --verify
  
  # Only check configuration
  python monitor_first_install.py --config-only
        """
    )
    
    parser.add_argument("--command", help="Installation command to monitor (e.g., 'pip install ipfs-kit-py')")
    parser.add_argument("--python", default="python3", help="Python interpreter to use (default: python3)")
    parser.add_argument("--verify", action="store_true", help="Only verify existing installation")
    parser.add_argument("--config-only", action="store_true", help="Only check configuration")
    parser.add_argument("--log-dir", default="/tmp/install_monitor",
                       help="Directory for logs and reports (default: /tmp/install_monitor)")
    
    args = parser.parse_args()
    
    monitor = InstallationMonitor(log_dir=args.log_dir)
    
    if args.verify:
        print("🔍 Verifying installation...\n")
        monitor.verify_installation()
        monitor.generate_report()
    elif args.config_only:
        print("⚙️ Checking configuration...\n")
        monitor.check_configuration()
        monitor.generate_report()
    elif args.command:
        success = monitor.monitor_installation(args.command, args.python)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
