#!/usr/bin/env python3
"""
Comprehensive Dependency Checker and Installer for IPFS Kit Python

This script detects the hardware architecture and operating system,
then installs the appropriate dependencies for the platform.

Supports:
- Linux (amd64/x86_64, arm64/aarch64)
- macOS (Intel x86_64, Apple Silicon arm64)
- Windows (x86_64)

Can be run standalone or imported as a module.

Usage:
    python scripts/check_and_install_dependencies.py [--dry-run] [--verbose]
    
    As a module:
        from scripts.check_and_install_dependencies import DependencyChecker
        checker = DependencyChecker()
        checker.check_and_install_all()
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DependencyChecker:
    """Check and install dependencies across different platforms."""
    
    def __init__(self, verbose: bool = False, dry_run: bool = False):
        self.verbose = verbose
        self.dry_run = dry_run
        self.platform_info = self._detect_platform()
        self.results = {
            "platform": self.platform_info,
            "checks": {},
            "installations": {},
            "errors": []
        }
        
    def _log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        if self.verbose or level in ["ERROR", "WARNING"]:
            prefix = f"[{level}]"
            print(f"{prefix} {message}", file=sys.stderr if level == "ERROR" else sys.stdout)
    
    def _detect_platform(self) -> Dict[str, str]:
        """
        Detect the current platform, OS, and architecture.
        
        Returns:
            Dictionary with platform information
        """
        system = platform.system()
        machine = platform.machine().lower()
        
        # Normalize architecture names
        if machine in ["x86_64", "amd64"]:
            arch = "amd64"
            arch_alt = "x86_64"
        elif machine in ["aarch64", "arm64"]:
            arch = "arm64"
            arch_alt = "aarch64"
        elif machine in ["armv7l", "armv6l"]:
            arch = "arm"
            arch_alt = machine
        else:
            arch = machine
            arch_alt = machine
        
        info = {
            "system": system,
            "machine": machine,
            "arch": arch,
            "arch_alt": arch_alt,
            "python_version": platform.python_version(),
            "platform": f"{system.lower()}-{arch}"
        }
        
        # Detect Linux distribution
        if system == "Linux":
            info["distro"] = self._detect_linux_distro()
            
        self._log(f"Detected platform: {info['platform']}")
        self._log(f"Architecture: {arch} (machine: {machine})")
        
        return info
    
    def _detect_linux_distro(self) -> str:
        """Detect Linux distribution."""
        # Try /etc/os-release first (most modern systems)
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("ID="):
                            distro = line.split("=")[1].strip().strip('"\'')
                            self._log(f"Detected Linux distribution: {distro}")
                            return distro
            except Exception as e:
                self._log(f"Failed to read /etc/os-release: {e}", "WARNING")
        
        # Fallback to checking specific files
        if os.path.exists("/etc/debian_version"):
            return "debian"
        elif os.path.exists("/etc/redhat-release"):
            return "rhel"
        elif os.path.exists("/etc/alpine-release"):
            return "alpine"
        elif os.path.exists("/etc/arch-release"):
            return "arch"
        
        return "unknown"
    
    def check_python_version(self) -> bool:
        """Check if Python version is compatible."""
        self._log("Checking Python version...")
        
        version_info = sys.version_info
        min_version = (3, 12)
        recommended_version = (3, 12)
        
        is_compatible = version_info >= min_version
        is_recommended = version_info >= recommended_version
        
        self.results["checks"]["python_version"] = {
            "version": f"{version_info.major}.{version_info.minor}.{version_info.micro}",
            "compatible": is_compatible,
            "recommended": is_recommended
        }
        
        if not is_compatible:
            self._log(f"Python {min_version[0]}.{min_version[1]}+ required, found {version_info.major}.{version_info.minor}", "ERROR")
            return False
        
        if not is_recommended:
            self._log(f"Python {recommended_version[0]}.{recommended_version[1]}+ recommended for best compatibility", "WARNING")
        else:
            self._log(f"✓ Python version {version_info.major}.{version_info.minor}.{version_info.micro}")
        
        return True
    
    def check_system_packages(self) -> Dict[str, bool]:
        """Check for required system packages."""
        self._log("Checking system packages...")
        
        system = self.platform_info["system"]
        
        if system == "Linux":
            return self._check_linux_packages()
        elif system == "Darwin":
            return self._check_macos_packages()
        elif system == "Windows":
            return self._check_windows_packages()
        
        return {}
    
    def _check_linux_packages(self) -> Dict[str, bool]:
        """Check Linux system packages."""
        distro = self.platform_info.get("distro", "unknown")
        
        # Define packages by package manager
        packages_by_pm = {
            "apt": ["build-essential", "git", "curl", "wget", "hwloc", "libhwloc-dev", 
                    "mesa-opencl-icd", "ocl-icd-opencl-dev", "golang-go"],
            "yum": ["gcc", "gcc-c++", "make", "git", "curl", "wget", "hwloc", 
                    "hwloc-devel", "opencl-headers", "ocl-icd-devel", "golang"],
            "dnf": ["gcc", "gcc-c++", "make", "git", "curl", "wget", "hwloc", 
                    "hwloc-devel", "opencl-headers", "ocl-icd-devel", "golang"],
            "apk": ["build-base", "git", "curl", "wget", "hwloc", "hwloc-dev", 
                    "opencl-headers", "opencl-icd-loader-dev", "go"],
            "pacman": ["base-devel", "git", "curl", "wget", "hwloc", 
                       "opencl-headers", "opencl-icd-loader", "go"]
        }
        
        # Detect package manager
        pm = self._detect_package_manager(distro)
        if not pm:
            self._log("Could not detect package manager", "WARNING")
            return {}
        
        packages = packages_by_pm.get(pm, [])
        results = {}
        
        for package in packages:
            installed = self._is_package_installed(package, pm)
            results[package] = installed
            
            if installed:
                self._log(f"✓ {package}")
            else:
                self._log(f"✗ {package} (not installed)", "WARNING")
        
        self.results["checks"]["system_packages"] = results
        return results
    
    def _detect_package_manager(self, distro: str) -> Optional[str]:
        """Detect which package manager to use."""
        # Check by distro first
        if distro in ["ubuntu", "debian", "linuxmint", "pop"]:
            return "apt"
        elif distro in ["fedora"]:
            return "dnf"
        elif distro in ["centos", "rhel", "rocky", "almalinux"]:
            return "yum"
        elif distro in ["alpine"]:
            return "apk"
        elif distro in ["arch", "manjaro"]:
            return "pacman"
        
        # Fallback: check for package manager commands
        for pm in ["apt-get", "dnf", "yum", "apk", "pacman"]:
            if shutil.which(pm):
                return pm.replace("-get", "")
        
        return None
    
    def _is_package_installed(self, package: str, pm: str) -> bool:
        """Check if a package is installed."""
        try:
            if pm == "apt":
                result = subprocess.run(
                    ["dpkg", "-s", package],
                    capture_output=True,
                    check=False
                )
                return result.returncode == 0
            elif pm in ["yum", "dnf"]:
                result = subprocess.run(
                    [pm, "list", "installed", package],
                    capture_output=True,
                    check=False
                )
                return result.returncode == 0
            elif pm == "apk":
                result = subprocess.run(
                    ["apk", "info", "-e", package],
                    capture_output=True,
                    check=False
                )
                return result.returncode == 0
            elif pm == "pacman":
                result = subprocess.run(
                    ["pacman", "-Qi", package],
                    capture_output=True,
                    check=False
                )
                return result.returncode == 0
        except Exception as e:
            self._log(f"Error checking package {package}: {e}", "WARNING")
        
        return False
    
    def _check_macos_packages(self) -> Dict[str, bool]:
        """Check macOS packages (via Homebrew)."""
        # Check if Homebrew is installed
        if not shutil.which("brew"):
            self._log("Homebrew not found", "WARNING")
            self.results["checks"]["homebrew"] = False
            return {}
        
        self._log("✓ Homebrew found")
        self.results["checks"]["homebrew"] = True
        
        packages = ["hwloc", "go"]
        results = {}
        
        for package in packages:
            try:
                result = subprocess.run(
                    ["brew", "list", package],
                    capture_output=True,
                    check=False
                )
                installed = result.returncode == 0
                results[package] = installed
                
                if installed:
                    self._log(f"✓ {package}")
                else:
                    self._log(f"✗ {package} (not installed)", "WARNING")
            except Exception as e:
                self._log(f"Error checking {package}: {e}", "WARNING")
                results[package] = False
        
        self.results["checks"]["system_packages"] = results
        return results
    
    def _check_windows_packages(self) -> Dict[str, bool]:
        """Check Windows packages."""
        # On Windows, most dependencies are bundled or installed via pip
        self._log("Windows detected - most dependencies will be Python packages")
        
        results = {
            "git": shutil.which("git") is not None,
            "go": shutil.which("go") is not None
        }
        
        for package, installed in results.items():
            if installed:
                self._log(f"✓ {package}")
            else:
                self._log(f"✗ {package} (not found in PATH)", "WARNING")
        
        self.results["checks"]["system_packages"] = results
        return results
    
    def check_python_packages(self) -> Dict[str, bool]:
        """Check for required Python packages."""
        self._log("Checking Python packages...")
        
        # Core packages from pyproject.toml
        required_packages = [
            "requests",
            "httpx",
            "aiohttp",
            "aiofiles",
            "watchdog",
            "psutil",
            "pyyaml",
            "base58",
            "multiaddr",
            "python-magic",
            "anyio",
            "cryptography"
        ]
        
        results = {}
        
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                results[package] = True
                self._log(f"✓ {package}")
            except ImportError:
                results[package] = False
                self._log(f"✗ {package} (not installed)", "WARNING")
        
        self.results["checks"]["python_packages"] = results
        return results
    
    def install_system_packages(self, packages: List[str]) -> bool:
        """Install missing system packages."""
        if self.dry_run:
            self._log(f"[DRY RUN] Would install: {', '.join(packages)}")
            return True
        
        system = self.platform_info["system"]
        
        if system == "Linux":
            return self._install_linux_packages(packages)
        elif system == "Darwin":
            return self._install_macos_packages(packages)
        elif system == "Windows":
            return self._install_windows_packages(packages)
        
        return False
    
    def _install_linux_packages(self, packages: List[str]) -> bool:
        """Install packages on Linux."""
        distro = self.platform_info.get("distro", "unknown")
        pm = self._detect_package_manager(distro)
        
        if not pm:
            self._log("Cannot install packages: package manager not found", "ERROR")
            return False
        
        # Check if running with sudo
        needs_sudo = os.geteuid() != 0
        
        try:
            # Update package lists
            self._log(f"Updating package lists...")
            if pm == "apt":
                cmd = (["sudo"] if needs_sudo else []) + ["apt-get", "update"]
            elif pm == "dnf":
                cmd = (["sudo"] if needs_sudo else []) + ["dnf", "check-update"]
            elif pm == "yum":
                cmd = (["sudo"] if needs_sudo else []) + ["yum", "check-update"]
            elif pm == "apk":
                cmd = (["sudo"] if needs_sudo else []) + ["apk", "update"]
            elif pm == "pacman":
                cmd = (["sudo"] if needs_sudo else []) + ["pacman", "-Sy"]
            
            subprocess.run(cmd, check=False, timeout=120)
            
            # Install packages
            self._log(f"Installing packages: {', '.join(packages)}")
            if pm == "apt":
                cmd = (["sudo"] if needs_sudo else []) + ["apt-get", "install", "-y"] + packages
            elif pm in ["dnf", "yum"]:
                cmd = (["sudo"] if needs_sudo else []) + [pm, "install", "-y"] + packages
            elif pm == "apk":
                cmd = (["sudo"] if needs_sudo else []) + ["apk", "add"] + packages
            elif pm == "pacman":
                cmd = (["sudo"] if needs_sudo else []) + ["pacman", "-S", "--noconfirm"] + packages
            
            result = subprocess.run(cmd, check=False, timeout=600)
            
            if result.returncode == 0:
                self._log("✓ Packages installed successfully")
                self.results["installations"]["system_packages"] = packages
                return True
            else:
                self._log(f"Package installation failed with code {result.returncode}", "ERROR")
                return False
                
        except subprocess.TimeoutExpired:
            self._log("Package installation timed out", "ERROR")
            return False
        except Exception as e:
            self._log(f"Error installing packages: {e}", "ERROR")
            return False
    
    def _install_macos_packages(self, packages: List[str]) -> bool:
        """Install packages on macOS via Homebrew."""
        if not shutil.which("brew"):
            self._log("Homebrew not installed. Install from https://brew.sh/", "ERROR")
            return False
        
        try:
            for package in packages:
                self._log(f"Installing {package}...")
                result = subprocess.run(
                    ["brew", "install", package],
                    check=False,
                    timeout=300
                )
                
                if result.returncode != 0:
                    self._log(f"Failed to install {package}", "WARNING")
            
            self._log("✓ Homebrew packages installed")
            self.results["installations"]["system_packages"] = packages
            return True
            
        except Exception as e:
            self._log(f"Error installing packages: {e}", "ERROR")
            return False
    
    def _install_windows_packages(self, packages: List[str]) -> bool:
        """Install packages on Windows."""
        self._log("Manual installation required for Windows packages", "WARNING")
        self._log("Please install the following manually:")
        for package in packages:
            self._log(f"  - {package}")
        return False
    
    def install_python_packages(self, extras: str = "full") -> bool:
        """Install Python package and dependencies.

        Args:
            extras: Optional extras set to install (e.g., "full", "libp2p,api").
        """
        if self.dry_run:
            self._log("[DRY RUN] Would install Python package with pip")
            return True
        
        self._log("Installing Python package...")
        
        try:
            # Upgrade pip first
            self._log("Upgrading pip, setuptools, wheel...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", 
                 "pip", "setuptools", "wheel"],
                check=True,
                timeout=300
            )
            
            extras = (extras or "").strip()
            extras_suffix = f"[{extras}]" if extras else ""
            target = f".{extras_suffix}"

            # Install package in editable mode (with extras)
            self._log(f"Installing ipfs_kit_py package: {target}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", target],
                check=False,
                timeout=600
            )
            
            if result.returncode == 0:
                self._log("✓ Python package installed successfully")
                self.results["installations"]["python_package"] = True
                return True
            else:
                self._log(f"Package installation failed with code {result.returncode}", "ERROR")
                return False
                
        except subprocess.TimeoutExpired:
            self._log("Python package installation timed out", "ERROR")
            return False
        except Exception as e:
            self._log(f"Error installing Python package: {e}", "ERROR")
            return False
    
    def check_docker_support(self) -> bool:
        """Check if Docker is available and working."""
        self._log("Checking Docker support...")
        
        # Check if docker command exists
        docker_cmd = shutil.which("docker")
        if not docker_cmd:
            self._log("✗ Docker not found in PATH", "WARNING")
            self.results["checks"]["docker"] = False
            return False
        
        # Try to run docker version
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                check=False,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse version
                output = result.stdout.decode()
                version_match = re.search(r"Version:\s+(\S+)", output)
                version = version_match.group(1) if version_match else "unknown"
                
                self._log(f"✓ Docker version {version}")
                self.results["checks"]["docker"] = True
                self.results["checks"]["docker_version"] = version
                
                # Check if we can run containers
                try:
                    subprocess.run(
                        ["docker", "run", "--rm", "hello-world"],
                        capture_output=True,
                        check=True,
                        timeout=30
                    )
                    self._log("✓ Docker can run containers")
                    self.results["checks"]["docker_functional"] = True
                    return True
                except:
                    self._log("✗ Docker installed but cannot run containers", "WARNING")
                    self.results["checks"]["docker_functional"] = False
                    return False
            else:
                self._log("✗ Docker installed but not responding", "WARNING")
                self.results["checks"]["docker"] = False
                return False
                
        except subprocess.TimeoutExpired:
            self._log("✗ Docker command timed out", "WARNING")
            self.results["checks"]["docker"] = False
            return False
        except Exception as e:
            self._log(f"✗ Error checking Docker: {e}", "WARNING")
            self.results["checks"]["docker"] = False
            return False
    
    def check_and_install_all(self, extras: str = "full") -> bool:
        """Run all checks and install missing dependencies.

        Args:
            extras: Optional extras set to install when installing the project.
        """
        self._log("=" * 60)
        self._log("IPFS Kit Python - Dependency Checker")
        self._log("=" * 60)
        
        all_ok = True
        
        # 1. Check Python version
        if not self.check_python_version():
            all_ok = False
            self.results["errors"].append("Python version too old")
        
        # 2. Check system packages
        self._log("\n--- System Packages ---")
        sys_packages = self.check_system_packages()
        missing_sys_packages = [pkg for pkg, installed in sys_packages.items() if not installed]
        
        if missing_sys_packages and not self.dry_run:
            self._log(f"\nInstalling {len(missing_sys_packages)} missing system packages...")
            if not self.install_system_packages(missing_sys_packages):
                self._log("Some system packages could not be installed", "WARNING")
        
        # 3. Check Python packages
        self._log("\n--- Python Packages ---")
        py_packages = self.check_python_packages()
        missing_py_packages = [pkg for pkg, installed in py_packages.items() if not installed]
        
        if missing_py_packages:
            self._log(f"\n{len(missing_py_packages)} Python packages missing")
            self._log("Installing Python package will resolve these...")
            if not self.dry_run:
                if not self.install_python_packages(extras=extras):
                    all_ok = False
                    self.results["errors"].append("Python package installation failed")
        
        # 4. Check Docker
        self._log("\n--- Docker Support ---")
        self.check_docker_support()
        
        # Summary
        self._log("\n" + "=" * 60)
        self._log("Summary")
        self._log("=" * 60)
        
        if all_ok and not missing_py_packages:
            self._log("✓ All dependencies satisfied!", "INFO")
        elif self.dry_run:
            self._log("Dry run completed - no changes made", "INFO")
        else:
            self._log("⚠ Some dependencies may be missing", "WARNING")
            if self.results["errors"]:
                self._log("Errors encountered:", "ERROR")
                for error in self.results["errors"]:
                    self._log(f"  - {error}", "ERROR")
        
        return all_ok
    
    def save_report(self, output_path: str = "dependency_report.json"):
        """Save dependency check report to JSON."""
        try:
            with open(output_path, "w") as f:
                json.dump(self.results, f, indent=2)
            self._log(f"Report saved to {output_path}")
        except Exception as e:
            self._log(f"Failed to save report: {e}", "ERROR")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check and install dependencies for IPFS Kit Python"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check dependencies without installing anything"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--report",
        default="dependency_report.json",
        help="Path to save JSON report (default: dependency_report.json)"
    )
    parser.add_argument(
        "--docker-only",
        action="store_true",
        help="Only check Docker support"
    )

    parser.add_argument(
        "--extras",
        default=os.environ.get("IPFS_KIT_EXTRAS", "full"),
        help=(
            "Extras to install with the package (default: 'full'). "
            "Set IPFS_KIT_EXTRAS to override. Use comma-separated extras, e.g. 'api,libp2p'."
        ),
    )
    
    args = parser.parse_args()
    
    checker = DependencyChecker(verbose=args.verbose, dry_run=args.dry_run)
    
    if args.docker_only:
        success = checker.check_docker_support()
    else:
        success = checker.check_and_install_all(extras=args.extras)
    
    # Save report
    checker.save_report(args.report)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
