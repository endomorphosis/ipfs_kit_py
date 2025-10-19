#!/usr/bin/env python3
"""
ARM64 Dependency Installation Monitor

This script monitors and logs the installation and configuration of ARM64 dependencies
in GitHub Actions workflows. It provides detailed progress tracking, error reporting,
and performance metrics.
"""

import os
import sys
import json
import time
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ARM64InstallationMonitor:
    """Monitor ARM64 dependency installation and configuration."""
    
    def __init__(self, log_dir: str = "/tmp/arm64_monitor"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.start_time = time.time()
        self.installation_log = []
        self.metrics = {
            "system_info": self._collect_system_info(),
            "installations": {},
            "errors": [],
            "warnings": []
        }
        
    def _collect_system_info(self) -> Dict:
        """Collect system information."""
        info = {
            "architecture": platform.machine(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "timestamp": datetime.now().isoformat()
        }
        
        # Get CPU info
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                info["cpu_count"] = cpuinfo.count('processor')
        except:
            info["cpu_count"] = os.cpu_count()
            
        # Get memory info
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                for line in meminfo.split('\n'):
                    if line.startswith('MemTotal:'):
                        info["memory_total"] = line.split()[1]
                        break
        except:
            info["memory_total"] = "unknown"
            
        return info
        
    def log_step(self, step_name: str, status: str, details: Optional[str] = None):
        """Log an installation step."""
        timestamp = datetime.now().isoformat()
        elapsed = time.time() - self.start_time
        
        entry = {
            "timestamp": timestamp,
            "elapsed_seconds": round(elapsed, 2),
            "step": step_name,
            "status": status,
            "details": details
        }
        
        self.installation_log.append(entry)
        
        # Print to console with formatting
        status_symbol = {
            "start": "🔄",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }.get(status, "•")
        
        print(f"{status_symbol} [{elapsed:.1f}s] {step_name}")
        if details:
            print(f"   {details}")
            
    def run_command(self, command: List[str], step_name: str, 
                   check: bool = True) -> Tuple[bool, str, str]:
        """Run a command and monitor its execution."""
        self.log_step(step_name, "start", f"Command: {' '.join(command)}")
        
        try:
            start = time.time()
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            duration = time.time() - start
            
            if result.returncode == 0:
                self.log_step(step_name, "success", 
                            f"Completed in {duration:.2f}s")
                self.metrics["installations"][step_name] = {
                    "status": "success",
                    "duration": duration,
                    "command": ' '.join(command)
                }
                return True, result.stdout, result.stderr
            else:
                error_msg = f"Exit code: {result.returncode}\n{result.stderr}"
                self.log_step(step_name, "error", error_msg)
                self.metrics["errors"].append({
                    "step": step_name,
                    "error": error_msg,
                    "command": ' '.join(command)
                })
                if check:
                    return False, result.stdout, result.stderr
                return True, result.stdout, result.stderr
                
        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after 600s"
            self.log_step(step_name, "error", error_msg)
            self.metrics["errors"].append({
                "step": step_name,
                "error": error_msg,
                "command": ' '.join(command)
            })
            return False, "", str(e)
            
        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            self.log_step(step_name, "error", error_msg)
            self.metrics["errors"].append({
                "step": step_name,
                "error": error_msg,
                "command": ' '.join(command)
            })
            return False, "", str(e)
            
    def check_binary(self, binary_name: str, version_flag: str = "--version") -> Dict:
        """Check if a binary is installed and get its version."""
        step_name = f"Check {binary_name}"
        self.log_step(step_name, "start")
        
        result = {
            "binary": binary_name,
            "installed": False,
            "version": None,
            "path": None
        }
        
        # Check if binary exists
        which_result = subprocess.run(
            ["which", binary_name],
            capture_output=True,
            text=True
        )
        
        if which_result.returncode == 0:
            result["installed"] = True
            result["path"] = which_result.stdout.strip()
            
            # Get version
            version_result = subprocess.run(
                [binary_name, version_flag],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if version_result.returncode == 0:
                result["version"] = version_result.stdout.strip()
                self.log_step(step_name, "success", 
                            f"Found: {result['path']}, Version: {result['version']}")
            else:
                self.log_step(step_name, "warning", 
                            f"Found but cannot get version: {result['path']}")
        else:
            self.log_step(step_name, "warning", f"Not found: {binary_name}")
            
        return result
        
    def check_python_package(self, package_name: str) -> Dict:
        """Check if a Python package is installed."""
        step_name = f"Check Python package: {package_name}"
        self.log_step(step_name, "start")
        
        result = {
            "package": package_name,
            "installed": False,
            "version": None
        }
        
        try:
            import importlib.metadata
            version = importlib.metadata.version(package_name)
            result["installed"] = True
            result["version"] = version
            self.log_step(step_name, "success", f"Version: {version}")
        except:
            self.log_step(step_name, "warning", f"Not installed: {package_name}")
            
        return result
        
    def generate_report(self) -> str:
        """Generate a detailed monitoring report."""
        total_duration = time.time() - self.start_time
        
        report = ["# ARM64 Dependency Installation Monitor Report\n"]
        report.append(f"**Generated**: {datetime.now().isoformat()}\n")
        report.append(f"**Total Duration**: {total_duration:.2f} seconds\n\n")
        
        # System Information
        report.append("## System Information\n")
        for key, value in self.metrics["system_info"].items():
            report.append(f"- **{key}**: {value}\n")
        report.append("\n")
        
        # Installation Steps
        report.append("## Installation Steps\n")
        if self.metrics["installations"]:
            for step, info in self.metrics["installations"].items():
                status_icon = "✅" if info["status"] == "success" else "❌"
                report.append(f"- {status_icon} **{step}**: {info['duration']:.2f}s\n")
                report.append(f"  - Command: `{info['command']}`\n")
        else:
            report.append("No installations recorded.\n")
        report.append("\n")
        
        # Errors
        if self.metrics["errors"]:
            report.append("## Errors\n")
            for error in self.metrics["errors"]:
                report.append(f"### {error['step']}\n")
                report.append(f"- Command: `{error['command']}`\n")
                report.append(f"- Error: ```\n{error['error']}\n```\n\n")
        
        # Warnings
        if self.metrics["warnings"]:
            report.append("## Warnings\n")
            for warning in self.metrics["warnings"]:
                report.append(f"- {warning}\n")
            report.append("\n")
            
        # Timeline
        report.append("## Installation Timeline\n")
        for entry in self.installation_log:
            status_icon = {
                "start": "🔄",
                "success": "✅",
                "error": "❌",
                "warning": "⚠️",
                "info": "ℹ️"
            }.get(entry["status"], "•")
            report.append(f"- [{entry['elapsed_seconds']}s] {status_icon} {entry['step']}\n")
            if entry["details"]:
                report.append(f"  - {entry['details']}\n")
        
        return "".join(report)
        
    def save_report(self, filename: str = "arm64_monitor_report.md"):
        """Save the monitoring report to a file."""
        report = self.generate_report()
        report_path = self.log_dir / filename
        
        with open(report_path, 'w') as f:
            f.write(report)
            
        self.log_step("Save Report", "success", f"Saved to: {report_path}")
        
        # Also save JSON metrics
        json_path = self.log_dir / "arm64_monitor_metrics.json"
        with open(json_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)
            
        return report_path
        
    def add_to_github_summary(self):
        """Add monitoring results to GitHub Actions summary."""
        if "GITHUB_STEP_SUMMARY" not in os.environ:
            return
            
        summary_file = os.environ["GITHUB_STEP_SUMMARY"]
        report = self.generate_report()
        
        with open(summary_file, 'a') as f:
            f.write("\n---\n\n")
            f.write(report)
            
        self.log_step("GitHub Summary", "success", "Added to step summary")


def main():
    """Main monitoring workflow."""
    monitor = ARM64InstallationMonitor()
    
    print("\n" + "="*70)
    print("ARM64 Dependency Installation Monitor")
    print("="*70 + "\n")
    
    # Check system requirements
    monitor.log_step("System Check", "start")
    
    if platform.machine() != "aarch64" and platform.machine() != "arm64":
        monitor.log_step("System Check", "warning", 
                        f"Not running on ARM64 (detected: {platform.machine()})")
    else:
        monitor.log_step("System Check", "success", 
                        f"Running on ARM64 ({platform.machine()})")
    
    # Check build tools
    build_tools = ["gcc", "g++", "make", "go", "git"]
    for tool in build_tools:
        result = monitor.check_binary(tool)
        monitor.metrics["installations"][f"build_tool_{tool}"] = result
    
    # Check Python packages
    python_packages = ["ipfs_kit_py", "pytest", "requests"]
    for package in python_packages:
        result = monitor.check_python_package(package)
        monitor.metrics["installations"][f"python_{package}"] = result
    
    # Save reports
    report_path = monitor.save_report()
    
    # Add to GitHub Actions summary if available
    monitor.add_to_github_summary()
    
    print("\n" + "="*70)
    print(f"Monitoring complete. Report saved to: {report_path}")
    print("="*70 + "\n")
    
    # Exit with error if there were errors
    if monitor.metrics["errors"]:
        print(f"❌ {len(monitor.metrics['errors'])} errors detected")
        return 1
    else:
        print("✅ No errors detected")
        return 0


if __name__ == "__main__":
    sys.exit(main())
