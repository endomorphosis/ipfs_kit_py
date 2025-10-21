#!/usr/bin/env python3
"""
Lotus installation script for ipfs_kit_py.

This script handles the installation of Lotus dependencies and binaries for the ipfs_kit_py package.
It provides a comprehensive, class-based implementation for installing and configuring Lotus binaries
on multiple platforms.

Usage:
    As a module: from install_lotus import install_lotus
                 installer = install_lotus(resources=None, metadata={"role": "master"})
                 installer.install_lotus_daemon()
                 installer.config_lotus()

    As a script: python install_lotus.py [--version VERSION] [--force] [--bin-dir PATH]
"""

import argparse
import binascii
import hashlib
import json
import logging
import math
import mmap
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# For dependency installation
import importlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("install_lotus")

DEFAULT_AUTO_INSTALL_DEPS = False
APT_LIKE_DISTROS = {
    "debian",
    "ubuntu",
    "linuxmint",
    "pop",
    "pop-os",
    "raspbian",
    "elementary",
    "zorin",
}
RPM_DISTROS = {"fedora", "centos", "rhel", "rocky", "almalinux", "amazon", "oracle"}
APK_DISTROS = {"alpine"}
PACMAN_DISTROS = {"arch", "manjaro"}
REQUIRED_DEPENDENCY_PACKAGES = {
    "apt": ["hwloc", "libhwloc-dev", "mesa-opencl-icd", "ocl-icd-opencl-dev"],
    "rpm": ["hwloc", "hwloc-devel", "opencl-headers", "ocl-icd-devel"],
    "apk": ["hwloc", "hwloc-dev", "opencl-headers", "opencl-icd-loader-dev"],
    "pacman": ["hwloc", "opencl-headers", "opencl-icd-loader"],
}
BREW_DEPENDENCIES = ["hwloc"]

# Default Lotus release information
DEFAULT_LOTUS_VERSION = "1.24.0"
LOTUS_GITHUB_API_URL = "https://api.github.com/repos/filecoin-project/lotus/releases"
LOTUS_RELEASE_BASE_URL = "https://github.com/filecoin-project/lotus/releases/download"
LOTUS_RELEASE_INFO_URL = "https://api.github.com/repos/filecoin-project/lotus/releases/tags/v{version}"

# Filecoin trusted setup directory URL
FILECOIN_PROOFS_URL = "https://proofs.filecoin.io/"

# Binary names to install
LOTUS_BINARIES = ["lotus", "lotus-miner", "lotus-worker", "lotus-gateway"]

# Try to import multiformat validator from ipfs_kit_py
try:
    test_folder = os.path.dirname(os.path.dirname(__file__)) + "/test"
    sys.path.append(test_folder)
    from ipfs_kit_py.ipfs_multiformats import ipfs_multiformats_py
except ImportError:
    logger.warning("Could not import ipfs_multiformats_py - CID verification will be limited")
    ipfs_multiformats_py = None


class install_lotus:
    """Class for installing and configuring Lotus components."""
    
    def __init__(self, resources=None, metadata=None):
        """
        Initialize Lotus installer with resources and metadata.
        
        Args:
            resources: Dictionary of resources that may be shared between components
            metadata: Dictionary of metadata for configuration
                Supported metadata:
                    - role: Node role (master, worker, leecher)
                    - lotus_path: Custom path for Lotus data
                    - version: Specific Lotus version to install
                    - force: Force reinstallation even if already installed
                    - bin_dir: Custom binary directory path
                    - skip_params: Skip parameter download
                                        - auto_install_deps: Automatically install dependencies (default: False).
                                            Set to True or export IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS=1 to opt-in.
        """
        # Initialize basic properties first
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Setup environment
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.env_path = os.environ.get("PATH", "")
        
        # Bin directory setup - MUST be before _install_system_dependencies
        default_bin_dir = os.path.join(self.this_dir, "bin")
        metadata_bin_dir = self.metadata.get("bin_dir")
        if metadata_bin_dir:
            if not os.path.isabs(metadata_bin_dir):
                metadata_bin_dir = os.path.abspath(metadata_bin_dir)
            self.bin_path = os.path.normpath(metadata_bin_dir)
        else:
            self.bin_path = os.path.normpath(default_bin_dir)

        # Ensure the resolved path is discoverable by downstream helpers
        self.metadata["bin_dir"] = self.bin_path
        os.makedirs(self.bin_path, exist_ok=True)
        
        # Determine whether system dependency installation is allowed
        metadata_auto_install = self.metadata.get("auto_install_deps")
        if metadata_auto_install is None:
            env_value = (
                os.environ.get("IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS", "")
                or os.environ.get("IPFS_KIT_AUTO_INSTALL_DEPS", "")
            ).strip().lower()
            if env_value:
                self.auto_install_deps = env_value in {"1", "true", "yes", "on"}
            else:
                self.auto_install_deps = DEFAULT_AUTO_INSTALL_DEPS
        else:
            self.auto_install_deps = bool(metadata_auto_install)

        # Check and install system dependencies if needed
        self._install_system_dependencies()
        
        # Import multiformat handler if available
        if "ipfs_multiformats" in list(self.resources.keys()):
            self.ipfs_multiformats = resources["ipfs_multiformats"]
        elif ipfs_multiformats_py:
            self.resources["ipfs_multiformats"] = ipfs_multiformats_py(resources, metadata)
            self.ipfs_multiformats = self.resources["ipfs_multiformats"]
        else:
            self.ipfs_multiformats = None
            
        # Setup paths
        if metadata and "path" in list(metadata.keys()):
            self.path = metadata["path"]
        else:
            self.path = self.env_path
            
        # Normalize paths for platform
        if platform.system() == "Windows":
            bin_path = os.path.join(self.this_dir, "bin").replace("/", "\\")
            self.path = f'"{self.path};{bin_path}"'
            self.path = self.path.replace("\\", "/")
            self.path = self.path.split("/")
            self.path = "/".join(self.path)
            self.path_string = "set PATH=" + self.path + " ; "
        elif platform.system() in ["Linux", "Darwin"]:
            self.path = self.path + ":" + os.path.join(self.this_dir, "bin")
            self.path_string = "PATH=" + self.path
            
        # Bin directory is already set up above
        
        # Temporary directory setup
        if platform.system() == "Windows":
            self.tmp_path = os.environ.get("TEMP", "/tmp")
        else:
            self.tmp_path = "/tmp"
            
        # Set up binaries distribution URLs and CIDs
        self._setup_distribution_info()
        
        # Extract role and paths from metadata
        self.role = metadata.get("role", "leecher") if metadata else "leecher"
        if self.role not in ["master", "worker", "leecher"]:
            logger.warning(f"Invalid role '{self.role}', defaulting to 'leecher'")
            self.role = "leecher"
            
        # Set up Lotus path
        self._setup_lotus_path()
            
        # Prepare method references
        self.install_lotus_daemon = self.install_lotus_daemon
        self.install_lotus_miner = self.install_lotus_miner
        self.install_lotus_worker = self.install_lotus_worker
        self.install_lotus_gateway = self.install_lotus_gateway
        
        # Prepare config methods based on role
        if self.role in ["master", "worker", "leecher"] and hasattr(self, "lotus_path"):
            self.lotus_install_command = self.install_lotus_daemon
            self.lotus_config_command = self.config_lotus
            
        # Set up mining components for master role
        if self.role == "master":
            self.miner_install = self.install_lotus_miner
            self.miner_config = self.config_lotus_miner
            
        # Initialize disk stats if needed
        self._init_disk_stats()
        
    def _setup_distribution_info(self):
        """Set up distribution URLs and CIDs for Lotus binaries."""
        # Main Lotus binaries URLs by platform
        self.lotus_dists = {
            "macos arm64": f"{LOTUS_RELEASE_BASE_URL}/v{DEFAULT_LOTUS_VERSION}/lotus_{DEFAULT_LOTUS_VERSION}_darwin-arm64.tar.gz",
            "macos x86_64": f"{LOTUS_RELEASE_BASE_URL}/v{DEFAULT_LOTUS_VERSION}/lotus_{DEFAULT_LOTUS_VERSION}_darwin-amd64.tar.gz",
            "linux arm64": f"{LOTUS_RELEASE_BASE_URL}/v{DEFAULT_LOTUS_VERSION}/lotus_{DEFAULT_LOTUS_VERSION}_linux-arm64.tar.gz",
            "linux x86_64": f"{LOTUS_RELEASE_BASE_URL}/v{DEFAULT_LOTUS_VERSION}/lotus_{DEFAULT_LOTUS_VERSION}_linux-amd64.tar.gz",
            "windows x86_64": f"{LOTUS_RELEASE_BASE_URL}/v{DEFAULT_LOTUS_VERSION}/lotus_{DEFAULT_LOTUS_VERSION}_windows-amd64.zip"
        }
        
        # CIDs for content verification (can be extended with actual CIDs)
        self.lotus_dists_cids = {
            "macos arm64": "",
            "macos x86_64": "",
            "linux arm64": "",
            "linux x86_64": "",
            "windows x86_64": ""
        }
    
    def _setup_lotus_path(self):
        """Set up Lotus data directory path based on platform and metadata."""
        if self.metadata and "lotus_path" in self.metadata:
            self.lotus_path = self.metadata["lotus_path"]
            if not os.path.exists(self.lotus_path):
                os.makedirs(self.lotus_path)
        else:
            # Default paths by platform
            if platform.system() == "Windows":
                self.lotus_path = os.path.join(os.path.expanduser("~"), ".lotus")
                self.lotus_path = self.lotus_path.replace("\\", "/")
                self.lotus_path = self.lotus_path.split("/")
                self.lotus_path = "/".join(self.lotus_path)
            elif platform.system() == "Linux" and os.getuid() == 0:
                self.lotus_path = "/var/lib/lotus"
            elif platform.system() == "Linux" and os.getuid() != 0:
                self.lotus_path = os.path.join(os.path.expanduser("~"), ".lotus")
            elif platform.system() == "Darwin":
                self.lotus_path = os.path.join(os.path.expanduser("~"), ".lotus")
                
            # Create directory if it doesn't exist
            if not os.path.exists(self.lotus_path):
                os.makedirs(self.lotus_path)
    
    def _init_disk_stats(self):
        """Initialize disk statistics for the Lotus path."""
        try:
            # Try to get disk stats
            self.disk_stats = {
                "disk_size": self._get_disk_total_capacity(self.lotus_path),
                "disk_used": self._get_disk_used_capacity(self.lotus_path),
                "disk_avail": self._get_disk_avail_capacity(self.lotus_path),
                "disk_name": self._get_disk_device_name(self.lotus_path)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk stats: {e}")
            self.disk_stats = {
                "disk_size": 0,
                "disk_used": 0,
                "disk_avail": 0,
                "disk_name": ""
            }
    
    def _get_disk_device_name(self, path):
        """Get device name for the disk containing the specified path."""
        try:
            if platform.system() == "Windows":
                # Extract drive letter
                drive = os.path.splitdrive(path)[0]
                return drive if drive else "C:"
            else:
                # Use df command on Unix-like systems
                result = subprocess.check_output(["df", path], universal_newlines=True)
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].split()[0]
                return ""
        except Exception as e:
            logger.warning(f"Failed to get disk device name: {e}")
            return ""
    
    def _get_disk_total_capacity(self, path):
        """Get total capacity of the disk containing the specified path."""
        try:
            if platform.system() == "Windows":
                import ctypes
                drive = os.path.splitdrive(path)[0]
                if not drive:
                    drive = "C:"
                sectorsPerCluster = ctypes.c_ulonglong(0)
                bytesPerSector = ctypes.c_ulonglong(0)
                freeClusters = ctypes.c_ulonglong(0)
                totalClusters = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(drive), 
                    None, 
                    ctypes.pointer(totalClusters), 
                    None
                )
                return totalClusters.value
            else:
                # Use df command on Unix-like systems
                result = subprocess.check_output(["df", "-k", path], universal_newlines=True)
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    # Convert KB to bytes
                    return int(lines[1].split()[1]) * 1024
                return 0
        except Exception as e:
            logger.warning(f"Failed to get disk total capacity: {e}")
            return 0
    
    def _get_disk_used_capacity(self, path):
        """Get used capacity of the disk containing the specified path."""
        try:
            if platform.system() == "Windows":
                import ctypes
                drive = os.path.splitdrive(path)[0]
                if not drive:
                    drive = "C:"
                totalBytes = ctypes.c_ulonglong(0)
                freeBytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(drive), 
                    None, 
                    ctypes.pointer(totalBytes), 
                    ctypes.pointer(freeBytes)
                )
                return totalBytes.value - freeBytes.value
            else:
                # Use df command on Unix-like systems
                result = subprocess.check_output(["df", "-k", path], universal_newlines=True)
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    # Convert KB to bytes
                    return int(lines[1].split()[2]) * 1024
                return 0
        except Exception as e:
            logger.warning(f"Failed to get disk used capacity: {e}")
            return 0
    
    def _get_disk_avail_capacity(self, path):
        """Get available capacity of the disk containing the specified path."""
        try:
            if platform.system() == "Windows":
                import ctypes
                drive = os.path.splitdrive(path)[0]
                if not drive:
                    drive = "C:"
                freeBytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(drive), 
                    None, 
                    None, 
                    ctypes.pointer(freeBytes)
                )
                return freeBytes.value
            else:
                # Use df command on Unix-like systems
                result = subprocess.check_output(["df", "-k", path], universal_newlines=True)
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    # Convert KB to bytes
                    return int(lines[1].split()[3]) * 1024
                return 0
        except Exception as e:
            logger.warning(f"Failed to get disk available capacity: {e}")
            return 0

    def hardware_detect(self):
        """
        Detect hardware platform for binary selection.
        
        Returns:
            Dictionary with system, processor, and architecture information
        """
        architecture = platform.architecture()
        system = platform.system()
        processor = platform.processor()
        machine = platform.machine()
        
        results = {
            "system": system, 
            "processor": processor, 
            "architecture": architecture,
            "machine": machine
        }
        return results

    def dist_select(self):
        """
        Select the appropriate distribution based on hardware detection.
        Uses platform.machine() as primary detection method for better ARM64 support.
        
        Returns:
            String identifier for the platform (e.g., "linux arm64")
        """
        hardware = self.hardware_detect()
        hardware["architecture"] = " ".join([str(x) for x in hardware["architecture"]])
        aarch = ""
        
        # Determine architecture
        if "Intel" in hardware["processor"] or "AMD" in hardware["processor"]:
            if "64" in hardware["architecture"]:
                aarch = "x86_64"
            elif "32" in hardware["architecture"]:
                aarch = "x86"
        elif "Qualcomm" in hardware["processor"] or "ARM" in hardware["processor"]:
            if "64" in hardware["architecture"]:
                aarch = "arm64"
            elif "32" in hardware["architecture"]:
                aarch = "arm"
        elif "Apple" in hardware["processor"]:
            if "64" in hardware["architecture"] or "arm64" in hardware["machine"].lower():
                aarch = "arm64"
            else:
                aarch = "x86_64"
        # Default to x86_64 if we can't determine architecture
        else:
            if "64" in hardware["architecture"] or "64" in hardware["machine"].lower():
                aarch = "x86_64"
            else:
                aarch = "x86"
                
        results = str(hardware["system"]).lower() + " " + aarch
        return results

    def get_latest_lotus_version(self):
        """
        Get the latest stable Lotus release version from GitHub.
        
        Returns:
            Version string (e.g., "1.24.0")
        """
        try:
            with urllib.request.urlopen(LOTUS_GITHUB_API_URL) as response:
                data = json.loads(response.read().decode("utf-8"))
                for release in data:
                    # Skip pre-releases
                    if release.get("prerelease", False):
                        continue
                    
                    tag_name = release["tag_name"]
                    # Extract version number (e.g., "1.23.0" from "v1.23.0")
                    match = re.match(r"v?(\d+\.\d+\.\d+)", tag_name)
                    if match:
                        return match.group(1)
                
                # If no suitable release found, return default
                logger.warning(f"Could not find latest release, using default: {DEFAULT_LOTUS_VERSION}")
                return DEFAULT_LOTUS_VERSION
        except Exception as e:
            logger.warning(f"Error checking latest release: {e}")
            logger.warning(f"Using default version: {DEFAULT_LOTUS_VERSION}")
            return DEFAULT_LOTUS_VERSION

    def get_release_info(self, version=None):
        """
        Get information about a specific Lotus release.
        
        Args:
            version: Lotus version string (e.g., "1.23.0"), or None for default
            
        Returns:
            Dictionary with release information
        """
        if version is None:
            if "version" in self.metadata:
                version = self.metadata["version"]
            else:
                version = self.get_latest_lotus_version()
                
        url = LOTUS_RELEASE_INFO_URL.format(version=version)
        try:
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.error(f"Release version {version} not found")
            else:
                logger.error(f"Error fetching release info: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing release info: {e}")
            return None

    def get_download_url(self, release_info, os_name=None, arch=None):
        """
        Get the download URL for Lotus binaries from release info.
        
        Args:
            release_info: Release information dictionary
            os_name: Operating system name (e.g., "linux"), or None to detect
            arch: Architecture name (e.g., "amd64"), or None to detect
            
        Returns:
            Tuple of (download_url, filename)
        """
        if os_name is None or arch is None:
            platform_info = self.dist_select().split()
            if os_name is None:
                os_name = platform_info[0]
            
            if arch is None:
                arch_map = {
                    "x86_64": "amd64",
                    "x86": "386",
                    "arm64": "arm64"
                }
                arch = arch_map.get(platform_info[1], "amd64")
        
        # Construct expected asset name pattern
        asset_pattern = f"lotus_.*_{os_name}_{arch}(?:_v\\d+)?\\.(tar\\.gz|zip)$"
        
        for asset in release_info.get("assets", []):
            name = asset.get("name", "")
            if re.match(asset_pattern, name):
                return asset["browser_download_url"], name
        
        logger.error(f"Could not find download for {os_name}_{arch} in release {release_info.get('tag_name')}")
        return None, None

    def download_file(self, url, dest_path):
        """
        Download a file with progress reporting.
        
        Args:
            url: URL to download
            dest_path: Destination file path
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Downloading from {url}")
        
        try:
            # Implement a simple progress reporter
            def report_progress(block_count, block_size, total_size):
                if total_size > 0:
                    percent = min(100, block_count * block_size * 100 / total_size)
                    sys.stdout.write(f"\rDownload progress: {percent:.1f}%")
                    sys.stdout.flush()
            
            urllib.request.urlretrieve(url, dest_path, reporthook=report_progress)
            print()  # New line after progress reporting
            logger.info(f"Download completed: {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return False

    def verify_download(self, file_path, expected_hash=None):
        """
        Verify the integrity of a downloaded file.
        
        Args:
            file_path: Path to downloaded file
            expected_hash: Expected SHA256 hash (optional)
            
        Returns:
            True if verification passes
        """
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False
        
        # If no hash provided, just check file size
        if not expected_hash:
            size = os.path.getsize(file_path)
            if size < 1000000:  # Less than 1MB is suspicious
                logger.warning(f"Downloaded file is suspiciously small: {size} bytes")
            return True
        
        # Verify hash if provided
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for block in iter(lambda: f.read(65536), b""):
                    sha256.update(block)
            
            actual_hash = sha256.hexdigest()
            if actual_hash != expected_hash.lower():
                logger.error(f"Hash verification failed. Expected: {expected_hash}, Got: {actual_hash}")
                return False
                
            logger.info("Hash verification passed")
            return True
        except Exception as e:
            logger.error(f"Error verifying download: {e}")
            return False

    def extract_archive(self, archive_path, extract_dir):
        """
        Extract downloaded archive.
        
        Args:
            archive_path: Path to the archive file
            extract_dir: Directory to extract to
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Extracting archive to {extract_dir}")
        
        try:
            if archive_path.endswith(".tar.gz"):
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(path=extract_dir)
            elif archive_path.endswith(".zip"):
                shutil.unpack_archive(archive_path, extract_dir)
            else:
                logger.error(f"Unsupported archive format: {archive_path}")
                return False
                
            logger.info("Extraction completed")
            return True
        except Exception as e:
            logger.error(f"Error extracting archive: {e}")
            return False

    def find_binary_in_dir(self, directory, binary_name):
        """
        Find a binary file in a directory structure.
        
        Args:
            directory: Base directory to search in
            binary_name: Name of the binary to find
            
        Returns:
            Full path to the binary if found, None otherwise
        """
        if platform.system() == "Windows" and not binary_name.endswith(".exe"):
            binary_name += ".exe"
            
        # Look for the binary in the directory and its subdirectories
        for root, _, files in os.walk(directory):
            if binary_name in files:
                return os.path.join(root, binary_name)
                
        return None

    def install_binaries(self, source_dir, bin_dir):
        """
        Install Lotus binaries to the bin directory.
        
        Args:
            source_dir: Directory containing extracted binaries
            bin_dir: Target bin directory
            
        Returns:
            List of installed binary paths
        """
        logger.info(f"Installing Lotus binaries to {bin_dir}")
        
        # Create bin directory if it doesn't exist
        os.makedirs(bin_dir, exist_ok=True)
        
        installed_binaries = []
        
        # Find and install each binary
        for binary in LOTUS_BINARIES:
            binary_name = binary
            if platform.system() == "Windows":
                binary_name += ".exe"
            
            # Look for the binary in source_dir and its subdirectories
            binary_path = self.find_binary_in_dir(source_dir, binary_name)
            
            if binary_path:
                dest_path = os.path.join(bin_dir, binary_name)
                
                # Copy and set executable permissions
                shutil.copy2(binary_path, dest_path)
                if platform.system() != "Windows":
                    os.chmod(dest_path, 0o755)
                
                logger.info(f"Installed {binary_name}")
                installed_binaries.append(dest_path)
            else:
                logger.warning(f"Could not find binary: {binary_name}")
        
        logger.info("Binary installation completed")
        return installed_binaries

    def _remove_installed_binaries(self, binaries):
        """Remove previously installed binaries when a fallback path is required."""
        for binary_path in binaries:
            try:
                os.remove(binary_path)
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning(f"Failed to remove binary {binary_path}: {exc}")

    def _verify_lotus_binary_execution(self):
        """Run `lotus --version` to confirm the binary is executable on this system."""
        lotus_path = os.path.join(self.bin_path, "lotus")
        if platform.system() == "Windows":
            lotus_path += ".exe"

        try:
            output = subprocess.check_output(
                [lotus_path, "--version"],
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )
            logger.info(output.strip())
            return True, output.strip()
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
            # Capture as much diagnostic detail as possible for logging.
            if isinstance(exc, subprocess.SubprocessError) and hasattr(exc, "output") and exc.output:
                message = exc.output
            else:
                message = str(exc)
            return False, message
        
    def _install_system_dependencies(self):
        """
        Detect and install system dependencies required by Lotus.
        
        This method checks for required system libraries and installs
        them if missing, using the appropriate package manager for the
        detected operating system.
        
        This implementation includes:
        - Improved detection of installed libraries
        - Better handling of package manager locks
        - Fallback mechanisms when system package managers fail
        - Comprehensive error handling and retry logic
        
        Returns:
            bool: True if dependencies are available or successfully installed
        """
        logger.info("Checking for required system dependencies...")
        
        # Detect operating system
        os_name = platform.system().lower()
        
        # Define dependencies by OS
        dependencies = {
            "linux": {
                "ubuntu": {
                    "packages": ["hwloc", "libhwloc-dev", "mesa-opencl-icd", "ocl-icd-opencl-dev"],
                    "install_cmd": ["apt-get", "update"],
                    "package_cmd": ["apt-get", "install", "-y"],
                    "alternative_package_cmd": ["apt-get", "install", "-y", "--no-install-recommends"],
                    "lock_files": ["/var/lib/apt/lists/lock", "/var/lib/dpkg/lock", "/var/lib/dpkg/lock-frontend"],
                    "package_check_cmd": ["dpkg", "-s"]
                },
                "debian": {
                    "packages": ["hwloc", "libhwloc-dev", "mesa-opencl-icd", "ocl-icd-opencl-dev"],
                    "install_cmd": ["apt-get", "update"],
                    "package_cmd": ["apt-get", "install", "-y"],
                    "alternative_package_cmd": ["apt-get", "install", "-y", "--no-install-recommends"],
                    "lock_files": ["/var/lib/apt/lists/lock", "/var/lib/dpkg/lock", "/var/lib/dpkg/lock-frontend"],
                    "package_check_cmd": ["dpkg", "-s"]
                },
                "fedora": {
                    "packages": ["hwloc", "hwloc-devel", "opencl-headers", "ocl-icd-devel"],
                    "install_cmd": ["dnf", "check-update"],
                    "package_cmd": ["dnf", "install", "-y"],
                    "alternative_package_cmd": ["dnf", "install", "-y", "--setopt=install_weak_deps=False"],
                    "lock_files": ["/var/lib/dnf/lock"],
                    "package_check_cmd": ["rpm", "-q"]
                },
                "centos": {
                    "packages": ["hwloc", "hwloc-devel", "opencl-headers", "ocl-icd-devel"],
                    "install_cmd": ["yum", "check-update"],
                    "package_cmd": ["yum", "install", "-y"],
                    "alternative_package_cmd": ["yum", "install", "-y", "--setopt=install_weak_deps=False"],
                    "lock_files": ["/var/run/yum.pid"],
                    "package_check_cmd": ["rpm", "-q"]
                },
                "alpine": {
                    "packages": ["hwloc", "hwloc-dev", "opencl-headers", "opencl-icd-loader-dev"],
                    "install_cmd": ["apk", "update"],
                    "package_cmd": ["apk", "add"],
                    "alternative_package_cmd": ["apk", "add", "--no-cache"],
                    "lock_files": ["/var/lib/apk/lock"],
                    "package_check_cmd": ["apk", "info", "-e"]
                },
                "arch": {
                    "packages": ["hwloc", "opencl-headers", "opencl-icd-loader"],
                    "install_cmd": ["pacman", "-Sy"],
                    "package_cmd": ["pacman", "-S", "--noconfirm"],
                    "alternative_package_cmd": ["pacman", "-S", "--noconfirm", "--needed"],
                    "lock_files": ["/var/lib/pacman/db.lck"],
                    "package_check_cmd": ["pacman", "-Qi"]
                }
            },
            "darwin": {
                "packages": ["hwloc"],
                "install_cmd": ["brew", "update"],
                "package_cmd": ["brew", "install"],
                "alternative_package_cmd": ["brew", "install", "--force"],
                "lock_files": [],  # Homebrew doesn't use lock files in the same way
                "package_check_cmd": ["brew", "list"]
            }
        }
        
        # Detect library directly first, regardless of OS - most reliable method
        # This will work even if package management is broken or unavailable
        if self._check_hwloc_library_direct():
            logger.info("Found libhwloc library installed on the system")
            return True

        if not getattr(self, "auto_install_deps", False):
            hint = self._dependency_install_hint(os_name)
            logger.error(
                "Required Lotus system dependencies are missing and automatic installation"
                " is disabled."
            )
            if hint:
                logger.error(hint)
            message = (
                "Lotus system dependencies were not detected. Install them before rerunning the"
                " installer or opt-in via metadata['auto_install_deps']=True."
            )
            if hint:
                message = f"{message}\n{hint}"
            raise RuntimeError(message)

        logger.info("Automatic dependency installation enabled; attempting to install prerequisites.")
            
        # Continue with OS-specific package management
        if os_name == "linux":
            return self._install_linux_dependencies(dependencies)
        elif os_name == "darwin":
            return self._install_darwin_dependencies(dependencies)
        elif os_name == "windows":
            # Windows doesn't typically need additional dependencies for Lotus
            # The binary should include all necessary DLLs
            logger.info("Windows platform detected, no additional dependencies required")
            return True
        else:
            logger.warning(f"Unsupported operating system: {os_name}")
            logger.warning("Checking for libraries directly...")
            # Try direct library check again (already did this above, but being explicit)
            if self._check_hwloc_library_direct():
                logger.info("Found libhwloc library installed on the system")
                return True
            else:
                logger.warning("You may need to manually install hwloc and OpenCL libraries")
                return False
                
    def _check_hwloc_library_direct(self):
        """
        Check for libhwloc library files directly on the system.
        
        This is a more reliable method than checking package installation
        as it directly verifies the library files exist.
        
        Returns:
            bool: True if libhwloc is found, False otherwise
        """
        # Common library paths to check
        lib_paths = [
            "/usr/lib", 
            "/usr/local/lib", 
            "/lib", 
            "/lib64", 
            "/usr/lib64",
            # Add homebrew paths for macOS
            "/usr/local/opt/hwloc/lib",
            "/opt/homebrew/lib",
            # Add common Windows paths
            "C:\\Windows\\System32",
            os.path.expanduser("~/.lotus/bin"),
            os.path.join(self.bin_path),
        ]
        
        # Library name patterns to look for (covering different versions)
        lib_patterns = [
            "libhwloc.so",       # Base name
            "libhwloc.so.15",    # Specific version
            "libhwloc.so.5",     # Older version
            "libhwloc.so.15.5.0", # Full versioned name
            "libhwloc.dylib",    # macOS
            "libhwloc.15.dylib", # macOS versioned
            "hwloc.dll",         # Windows
        ]
        
        # Check each path for matching libraries
        for path in lib_paths:
            if not os.path.exists(path):
                continue
                
            try:
                # Look for any matching library in this path
                for filename in os.listdir(path):
                    for pattern in lib_patterns:
                        if filename.startswith(pattern) or filename == pattern:
                            logger.info(f"Found hwloc library: {os.path.join(path, filename)}")
                            return True
            except (PermissionError, OSError) as e:
                # Skip paths we can't access
                logger.debug(f"Could not access {path}: {e}")
                continue
                
        # Also try using ldconfig to find the library (Linux only)
        if platform.system() == "Linux":
            try:
                result = subprocess.run(
                    ["ldconfig", "-p"], 
                    capture_output=True, 
                    text=True, 
                    check=False
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if "libhwloc.so" in line:
                            logger.info(f"Found hwloc library via ldconfig: {line.strip()}")
                            return True
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
                
        # Library not found
        return False

    def _dependency_install_hint(self, os_name):
        """Provide installation guidance for system dependencies."""
        distro = ""
        if os_name == "linux":
            try:
                distro = (self._detect_linux_distribution() or "").lower()
            except Exception:
                distro = ""

        if distro in APT_LIKE_DISTROS:
            packages = " ".join(REQUIRED_DEPENDENCY_PACKAGES["apt"])
            return (
                "Install Lotus prerequisites with:"
                f" sudo apt-get update && sudo apt-get install -y {packages}"
            )

        if distro in RPM_DISTROS:
            packages = " ".join(REQUIRED_DEPENDENCY_PACKAGES["rpm"])
            install_cmd = "dnf" if distro == "fedora" else "yum"
            return (
                "Install Lotus prerequisites with:"
                f" sudo {install_cmd} install -y {packages}"
            )

        if distro in APK_DISTROS:
            packages = " ".join(REQUIRED_DEPENDENCY_PACKAGES["apk"])
            return (
                "Install Lotus prerequisites with:"
                f" sudo apk add {packages}"
            )

        if distro in PACMAN_DISTROS:
            packages = " ".join(REQUIRED_DEPENDENCY_PACKAGES["pacman"])
            return (
                "Install Lotus prerequisites with:"
                f" sudo pacman -S --needed {packages}"
            )

        if os_name == "darwin":
            packages = " ".join(BREW_DEPENDENCIES)
            return f"Install Lotus prerequisites with: brew install {packages}"

        if os_name == "windows":
            return (
                "Install Lotus prerequisites by installing hwloc and the OpenCL ICD loader,"
                " then ensure their DLLs are discoverable via PATH."
            )

        return (
            "Install Lotus prerequisites by ensuring libhwloc and an OpenCL ICD loader"
            " are installed via your system package manager."
        )

    def _check_package_manager_available(self, distro_deps):
        """
        Check if package manager is available and not locked.
        
        Args:
            distro_deps: Dictionary with distribution dependencies info
            
        Returns:
            tuple: (bool indicating availability, string with lock info if locked)
        """
        # Check if any lock files exist
        lock_info = []
        for lock_file in distro_deps.get("lock_files", []):
            if os.path.exists(lock_file):
                try:
                    # Check if the lock is stale by checking process
                    with open(lock_file, "r") as f:
                        try:
                            pid = int(f.read().strip())
                            # Check if process exists
                            try:
                                os.kill(pid, 0)
                                lock_info.append(f"Lock file {lock_file} is held by active process {pid}")
                            except OSError:
                                lock_info.append(f"Lock file {lock_file} exists but process {pid} is not running (stale lock)")
                        except ValueError:
                            # Not a PID in the file
                            lock_info.append(f"Lock file {lock_file} exists")
                except (PermissionError, IOError):
                    # Can't read the file
                    lock_info.append(f"Lock file {lock_file} exists but cannot be read")
                    
        if lock_info:
            return False, ", ".join(lock_info)
            
        # Check if package manager commands exist
        try:
            if distro_deps.get("package_check_cmd"):
                check_cmd = distro_deps["package_check_cmd"][0]
                subprocess.run([check_cmd, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True, None
        except (subprocess.SubprocessError, FileNotFoundError):
            return False, "Package manager not found or not functioning"
            
        return True, None
        
    def _wait_for_lock_release(self, distro_deps, timeout=300):
        """
        Wait for package manager locks to be released.
        
        Args:
            distro_deps: Dictionary with distribution dependencies info
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if locks were released, False if timed out
        """
        logger.info(f"Waiting for package manager locks to be released (timeout: {timeout}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            available, lock_info = self._check_package_manager_available(distro_deps)
            if available:
                logger.info("Package manager is now available")
                return True
                
            # Wait before checking again
            wait_time = min(10, timeout / 10)  # Wait up to 10 seconds between checks
            logger.debug(f"Package manager still locked: {lock_info}. Waiting {wait_time}s...")
            time.sleep(wait_time)
            
        logger.error(f"Timed out waiting for package manager locks ({timeout}s)")
        return False
        
    def _check_packages_installed(self, distro, distro_deps, packages):
        """
        Check which packages are missing using the appropriate package manager.
        
        Args:
            distro: Distribution name
            distro_deps: Dictionary with distribution dependencies info
            packages: List of packages to check
            
        Returns:
            list: List of missing packages
        """
        missing_packages = []
        
        for package in packages:
            # For hwloc, we can also check for the library directly
            if package == "hwloc" and self._check_hwloc_library_direct():
                continue
                
            # Check using package manager
            try:
                if distro_deps.get("package_check_cmd"):
                    cmd = distro_deps["package_check_cmd"] + [package]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if result.returncode != 0:
                        missing_packages.append(package)
            except (subprocess.SubprocessError, FileNotFoundError):
                # If command fails, assume package is missing
                missing_packages.append(package)
                
        return missing_packages
        
    def _try_direct_library_installation(self):
        """
        Try to directly download and install the hwloc library without using package managers.
        This is a fallback method when system package managers fail.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Attempting direct hwloc library installation...")
        
        # Create lib directory in bin folder if it doesn't exist
        lib_dir = os.path.join(self.bin_path, "lib")
        os.makedirs(lib_dir, exist_ok=True)
        
        # HWLoc binary URLs by platform - Using GitHub mirror for reliability
        hwloc_bins = {
            "linux-x86_64": "https://github.com/open-mpi/hwloc/releases/download/hwloc-2.8.0/hwloc-2.8.0-linux-x86_64.tar.gz",
            "linux-aarch64": "https://github.com/open-mpi/hwloc/releases/download/hwloc-2.8.0/hwloc-2.8.0-linux-aarch64.tar.gz",
            "macos-x86_64": "https://github.com/open-mpi/hwloc/releases/download/hwloc-2.8.0/hwloc-2.8.0-darwin-x86_64.tar.gz",
            "macos-arm64": "https://github.com/open-mpi/hwloc/releases/download/hwloc-2.8.0/hwloc-2.8.0-darwin-x86_64.tar.gz",  # Use x86_64 for arm64 too
        }
        
        # Determine platform
        os_name = platform.system().lower()
        arch = platform.machine().lower()
        
        # Map architecture to expected format
        if "x86_64" in arch or "amd64" in arch:
            arch = "x86_64"
        elif "aarch64" in arch or "arm64" in arch:
            arch = "aarch64" if os_name == "linux" else "arm64"
        else:
            logger.error(f"Unsupported architecture for direct hwloc installation: {arch}")
            return False
            
        # Get download URL
        platform_key = f"{os_name}-{arch}"
        if platform_key not in hwloc_bins:
            logger.error(f"No direct hwloc download available for {platform_key}")
            return False
            
        url = hwloc_bins[platform_key]
        
        try:
            # Download hwloc binary package
            with tempfile.TemporaryDirectory() as temp_dir:
                tar_path = os.path.join(temp_dir, "hwloc.tar.gz")
                
                # Download file
                logger.info(f"Downloading hwloc from {url}...")
                urllib.request.urlretrieve(url, tar_path)
                
                # Extract archive
                logger.info("Extracting hwloc library...")
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(path=temp_dir)
                    
                # Find extracted directory (should be only one)
                extracted_dirs = [d for d in os.listdir(temp_dir) 
                                 if os.path.isdir(os.path.join(temp_dir, d)) and d.startswith("hwloc")]
                if not extracted_dirs:
                    logger.error("Could not find extracted hwloc directory")
                    return False
                    
                # Copy library files to bin/lib directory
                extract_path = os.path.join(temp_dir, extracted_dirs[0])
                lib_src_dir = os.path.join(extract_path, "lib")
                
                # Check if the lib directory exists
                if not os.path.isdir(lib_src_dir):
                    logger.error(f"Could not find lib directory in extracted hwloc package: {lib_src_dir}")
                    return False
                    
                # Copy all .so files
                copied_files = []
                for filename in os.listdir(lib_src_dir):
                    if filename.endswith(".so") or filename.endswith(".dylib") or filename.endswith(".dll"):
                        src_path = os.path.join(lib_src_dir, filename)
                        dst_path = os.path.join(lib_dir, filename)
                        shutil.copy2(src_path, dst_path)
                        copied_files.append(filename)
                        
                if not copied_files:
                    logger.error("No library files found to copy")
                    return False
                    
                logger.info(f"Installed hwloc libraries directly: {', '.join(copied_files)}")
                
                # Create an LD_LIBRARY_PATH file to help with runtime loading
                ldpath_script = os.path.join(self.bin_path, "set_lotus_env.sh")
                with open(ldpath_script, "w") as f:
                    f.write(f"""#!/bin/bash
# Set LD_LIBRARY_PATH for Lotus binaries
export LD_LIBRARY_PATH="{lib_dir}:$LD_LIBRARY_PATH"
""")
                os.chmod(ldpath_script, 0o755)
                
                return True
                
        except Exception as e:
            logger.error(f"Error during direct hwloc installation: {e}")
            return False
            
    def _install_linux_dependencies(self, dependencies):
        """
        Install dependencies on Linux systems.
        
        Args:
            dependencies: Dictionary with dependencies information by OS
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First try to detect distribution
            distro = self._detect_linux_distribution()
            
            if not distro or distro not in dependencies["linux"]:
                # Use a fallback if distribution not specifically supported
                if os.path.exists("/etc/debian_version"):
                    distro = "debian"
                elif os.path.exists("/etc/fedora-release"):
                    distro = "fedora"
                elif os.path.exists("/etc/centos-release"):
                    distro = "centos"
                elif os.path.exists("/etc/alpine-release"):
                    distro = "alpine"
                elif os.path.exists("/etc/arch-release"):
                    distro = "arch"
                else:
                    # Default to debian-based if we can't determine
                    distro = "debian"
                    logger.warning("Could not determine Linux distribution, assuming Debian-based")
                    
            logger.info(f"Detected Linux distribution: {distro}")
            distro_deps = dependencies["linux"].get(distro, dependencies["linux"]["debian"])
            
            # Check if we need to use sudo (if not running as root)
            sudo_prefix = []
            if os.geteuid() != 0:
                sudo_prefix = ["sudo"]
                
            # Check for package manager availability and lock status
            available, lock_info = self._check_package_manager_available(distro_deps)
            if not available:
                logger.warning(f"Package manager is not available: {lock_info}")
                
                # Wait for locks to be released (only for lock issues, not missing package manager)
                if "lock" in lock_info.lower() and not "not found" in lock_info.lower():
                    if not self._wait_for_lock_release(distro_deps):
                        logger.warning("Could not wait for package manager locks, trying direct library installation")
                        # Try direct library installation as fallback
                        if self._try_direct_library_installation():
                            return True
                        else:
                            # Check one more time directly for libraries
                            if self._check_hwloc_library_direct():
                                logger.info("Found hwloc library installed on the system")
                                return True
                            else:
                                logger.error("Could not install dependencies via package manager or direct installation")
                                return False
                else:
                    # Package manager not found, try direct installation
                    logger.warning("Package manager not functional, trying direct library installation")
                    if self._try_direct_library_installation():
                        return True
                    else:
                        # Check one more time for libraries
                        if self._check_hwloc_library_direct():
                            logger.info("Found hwloc library installed on the system")
                            return True
                        else:
                            logger.error("Could not install dependencies via package manager or direct installation")
                            return False
                            
            # Check for missing packages
            missing_packages = self._check_packages_installed(
                distro, distro_deps, distro_deps["packages"])
            
            # Install missing packages if any
            if missing_packages:
                logger.info(f"Missing required packages: {', '.join(missing_packages)}")
                
                # Try package manager installation
                return self._try_package_installation(distro, distro_deps, missing_packages, sudo_prefix)
            else:
                logger.info("All required system dependencies are already installed")
                return True
                
        except Exception as e:
            logger.error(f"Error checking/installing Linux dependencies: {e}")
            logger.warning("Trying direct library installation as fallback...")
            
            # Try direct installation as last resort
            if self._try_direct_library_installation():
                return True
            # Check library presence one last time    
            elif self._check_hwloc_library_direct():
                logger.info("Found hwloc library installed on the system despite errors")
                return True
            else:
                logger.warning("You may need to manually install hwloc and OpenCL libraries")
                return False
                
    def _detect_linux_distribution(self):
        """
        Detect Linux distribution more reliably.
        
        Returns:
            str: Distribution name or None if detection fails
        """
        # First check /etc/os-release (most modern distros)
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if line.startswith("ID="):
                            return line.split("=")[1].strip().strip('"\'')
            except (PermissionError, IOError):
                pass
                
        # Try lsb_release command if available
        try:
            result = subprocess.run(
                ["lsb_release", "-is"], 
                capture_output=True, 
                text=True, 
                check=False
            )
            if result.returncode == 0:
                return result.stdout.strip().lower()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
            
        # Try specific distribution files
        if os.path.exists("/etc/debian_version"):
            return "debian"
        elif os.path.exists("/etc/fedora-release"):
            return "fedora"
        elif os.path.exists("/etc/centos-release") or os.path.exists("/etc/redhat-release"):
            return "centos"
        elif os.path.exists("/etc/alpine-release"):
            return "alpine"
        elif os.path.exists("/etc/arch-release"):
            return "arch"
            
        # Could not determine
        return None
        
    def _try_package_installation(self, distro, distro_deps, missing_packages, sudo_prefix):
        """
        Try to install packages using package manager with fallback options.
        
        Args:
            distro: Distribution name
            distro_deps: Dictionary with distribution dependencies info
            missing_packages: List of packages to install
            sudo_prefix: List containing "sudo" if needed
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Try standard installation first
        try:
            # First update package lists
            logger.info("Updating package lists...")
            update_cmd = sudo_prefix + distro_deps["install_cmd"]
            
            # Some package managers don't like having their update commands check=True
            # (e.g., dnf check-update can return 100 for "updates available")
            try:
                subprocess.run(update_cmd, check=False, timeout=120)
            except subprocess.TimeoutExpired:
                logger.warning("Package manager update timed out, continuing with installation")
                
            # Install missing packages
            logger.info(f"Installing missing packages: {', '.join(missing_packages)}")
            install_cmd = sudo_prefix + distro_deps["package_cmd"] + missing_packages
            
            try:
                subprocess.run(install_cmd, check=True, timeout=300)
                logger.info("Required system dependencies installed successfully")
                return True
            except subprocess.SubprocessError as e:
                logger.warning(f"Standard package installation failed: {e}")
                
                # Try alternative installation command if available
                if "alternative_package_cmd" in distro_deps:
                    logger.info("Trying alternative package installation method...")
                    alt_install_cmd = sudo_prefix + distro_deps["alternative_package_cmd"] + missing_packages
                    
                    try:
                        subprocess.run(alt_install_cmd, check=True, timeout=300)
                        logger.info("Required system dependencies installed with alternative method")
                        return True
                    except subprocess.SubprocessError as e2:
                        logger.warning(f"Alternative package installation also failed: {e2}")
                
                # If both methods failed, try direct library installation
                logger.warning("Package manager installation failed, trying direct library installation")
                if self._try_direct_library_installation():
                    return True
                
                # As a last check, see if the libraries are actually there despite installation errors
                if self._check_hwloc_library_direct():
                    logger.info("Found hwloc library installed on the system despite package manager errors")
                    return True
                    
                logger.error("All installation methods failed")
                logger.warning("You may need to manually install the following packages:")
                logger.warning(f"  {' '.join(missing_packages)}")
                return False
                
        except Exception as e:
            logger.error(f"Error during package installation: {e}")
            
            # Try direct installation as last resort
            logger.warning("Trying direct library installation as fallback...")
            if self._try_direct_library_installation():
                return True
            else:
                logger.warning("You may need to manually install the following packages:")
                logger.warning(f"  {' '.join(missing_packages)}")
                return False
                
    def _install_darwin_dependencies(self, dependencies):
        """
        Install dependencies on macOS using Homebrew.
        
        Args:
            dependencies: Dictionary with dependencies information by OS
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if Homebrew is installed
            try:
                subprocess.run(["brew", "--version"], stdout=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("Homebrew is required to install dependencies on macOS")
                logger.warning("Please install Homebrew from https://brew.sh/ and try again")
                # Try direct library check as fallback
                if self._check_hwloc_library_direct():
                    logger.info("Found hwloc library installed without Homebrew")
                    return True
                else:
                    logger.warning("Direct library check also failed")
                    return False
            
            # Check for required packages
            missing_packages = []
            for package in dependencies["darwin"]["packages"]:
                try:
                    result = subprocess.run(
                        ["brew", "list", package], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        check=False
                    )
                    if result.returncode != 0:
                        missing_packages.append(package)
                except subprocess.SubprocessError:
                    missing_packages.append(package)
            
            # Install missing packages
            if missing_packages:
                logger.info(f"Missing required packages: {', '.join(missing_packages)}")
                
                try:
                    # Update Homebrew first (not critical if it fails)
                    logger.info("Updating Homebrew...")
                    try:
                        subprocess.run(dependencies["darwin"]["install_cmd"], check=False, timeout=120)
                    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                        logger.warning(f"Homebrew update failed but continuing: {e}")
                    
                    # Install each package
                    for package in missing_packages:
                        logger.info(f"Installing {package}...")
                        try:
                            subprocess.run(dependencies["darwin"]["package_cmd"] + [package], check=True, timeout=300)
                        except subprocess.SubprocessError:
                            # Try alternative installation if available
                            logger.warning(f"Standard installation of {package} failed, trying alternative...")
                            subprocess.run(
                                dependencies["darwin"]["alternative_package_cmd"] + [package], 
                                check=True, 
                                timeout=300
                            )
                        
                    # Verify installation
                    if self._check_hwloc_library_direct():
                        logger.info("Required system dependencies installed and verified successfully")
                        return True
                    else:
                        logger.warning("Package installed but library not found, may need a restart")
                        return True
                        
                except Exception as e:
                    logger.error(f"Failed to install system dependencies: {e}")
                    # Check library directly one more time
                    if self._check_hwloc_library_direct():
                        logger.info("Found hwloc library installed despite errors")
                        return True
                    else:
                        logger.warning("You may need to manually install the following packages:")
                        logger.warning(f"  brew install {' '.join(missing_packages)}")
                        return False
            else:
                logger.info("All required system dependencies are already installed")
                return True
                
        except Exception as e:
            logger.error(f"Error checking/installing macOS dependencies: {e}")
            # Try direct library check one more time
            if self._check_hwloc_library_direct():
                logger.info("Found hwloc library installed despite errors")
                return True
            else:
                logger.warning("You may need to manually install hwloc using Homebrew")
                return False

    def check_existing_installation(self, bin_dir=None):
        """
        Check if Lotus is already installed in the bin directory.
        
        Args:
            bin_dir: Path to binary directory, or None for default
            
        Returns:
            Dictionary with installation status and version information
        """
        if bin_dir is None:
            bin_dir = self.bin_path
            
        lotus_path = os.path.join(bin_dir, "lotus")
        if platform.system() == "Windows":
            lotus_path += ".exe"
        
        result = {
            "installed": False,
            "version": None,
            "binaries": {}
        }
        
        if not os.path.exists(lotus_path):
            return result
        
        # Check lotus version
        try:
            output = subprocess.check_output([lotus_path, "--version"], 
                                            stderr=subprocess.STDOUT, 
                                            universal_newlines=True)
            version_match = re.search(r"lotus version (\d+\.\d+\.\d+)", output)
            if version_match:
                result["version"] = version_match.group(1)
            else:
                result["version"] = "unknown"
                
            result["installed"] = True
            logger.info(f"Found existing Lotus installation: {output.strip()}")
            
            # Check which binaries are installed
            for binary in LOTUS_BINARIES:
                binary_path = os.path.join(bin_dir, binary)
                if platform.system() == "Windows":
                    binary_path += ".exe"
                
                if os.path.exists(binary_path):
                    result["binaries"][binary] = True
                else:
                    result["binaries"][binary] = False
            
            return result
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.info("Lotus binary exists but could not determine version")
            result["installed"] = True
            return result

    def setup_lotus_env(self):
        """
        Set up Lotus environment variables and configuration.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Setting up Lotus environment")
        
        # Create Lotus directory structure
        os.makedirs(self.lotus_path, exist_ok=True)
        
        # Create basic config file if it doesn't exist
        config_file = os.path.join(self.lotus_path, "config.toml")
        if not os.path.exists(config_file):
            with open(config_file, "w") as f:
                f.write("""# Default config file created by ipfs_kit_py installer
[API]
  ListenAddress = "/ip4/127.0.0.1/tcp/1234/http"
  # RemoteListenAddress = ""
  Timeout = "30s"

[Libp2p]
  ListenAddresses = ["/ip4/0.0.0.0/tcp/1235", "/ip6/::/tcp/1235"]
  # AnnounceAddresses = []
  # NoAnnounceAddresses = []
  DisableNatPortMap = false

[Client]
  UseIpfs = false
  IpfsMAddr = ""
  IpfsUseForRetrieval = false
""")
            logger.info(f"Created default config at {config_file}")
        
        logger.info("Lotus environment setup completed")
        return True

    def download_params(self):
        """
        Download required parameters for Lotus.
        This uses lotus fetch-params to download the required parameters.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Checking for required Filecoin parameters")
        
        # Use the lotus binary to download parameters
        lotus_bin = os.path.join(os.path.abspath(self.bin_path), "lotus")
        if platform.system() == "Windows":
            lotus_bin += ".exe"
        
        if not os.path.exists(lotus_bin):
            logger.error(f"Lotus binary not found at {lotus_bin}")
            logger.error("Please run installer.install_lotus_daemon() first")
            return False
        
        try:
            env = os.environ.copy()
            env["LOTUS_PATH"] = self.lotus_path

            logger.info("Fetching Filecoin parameters (this may take a while)")

            sector_size = (
                self.metadata.get("params_sector_size")
                or self.metadata.get("sector_size")
                or os.environ.get("LOTUS_FETCH_PARAMS_SECTOR_SIZE")
                or "32GiB"
            )

            def _fetch_params_capabilities() -> Dict[str, bool]:
                info = {
                    "proving_flag": False,
                    "sector_flag": False,
                    "positional_sector": False,
                }
                try:
                    help_result = subprocess.run(
                        [lotus_bin, "fetch-params", "--help"],
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    help_text = ((help_result.stdout or "") + (help_result.stderr or "")).lower()
                    info["proving_flag"] = "--proving-params" in help_text
                    info["sector_flag"] = "--sector-size" in help_text
                    if "[sectorsize]" in help_text or "<sectorsize>" in help_text:
                        info["positional_sector"] = True
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("Failed to detect fetch-params flags: %s", exc)
                return info

            def _run_and_log(command):
                process = subprocess.Popen(
                    command,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                )
                output_lines = []
                if process.stdout is not None:
                    for line in process.stdout:
                        clean = line.strip()
                        if clean:
                            logger.info(clean)
                        output_lines.append(line)
                process.wait()
                return process.returncode, "".join(output_lines)

            base_command = [lotus_bin, "fetch-params"]
            capabilities = _fetch_params_capabilities()

            commands_to_try: List[List[str]] = []
            if capabilities.get("proving_flag"):
                commands_to_try.append(base_command + ["--proving-params"])
            if capabilities.get("sector_flag"):
                commands_to_try.append(base_command + ["--sector-size", sector_size])
            if capabilities.get("positional_sector"):
                commands_to_try.append(base_command + [sector_size])
            commands_to_try.append(base_command)

            seen_commands = set()
            deduped_commands = []
            for command in commands_to_try:
                key = tuple(command)
                if key not in seen_commands:
                    deduped_commands.append(command)
                    seen_commands.add(key)

            last_code = None
            for command in deduped_commands:
                logger.info("Running: %s", " ".join(command))
                last_code, _ = _run_and_log(command)
                if last_code == 0:
                    logger.info("Parameter download completed")
                    return True

            logger.error("Parameter download failed with return code %s", last_code)
            return False

        except subprocess.SubprocessError as exc:
            logger.error(f"Error downloading parameters: {exc}")
            logger.warning("You may need to download parameters manually using 'lotus fetch-params'")
            return False

    def test_lotus_installation(self, bin_dir=None):
        """
        Test if the Lotus installation works.
        
        Args:
            bin_dir: Path to binary directory, or None for default
            
        Returns:
            True if installation test passes, False otherwise
        """
        logger.info("Testing Lotus installation")
        
        if bin_dir is None:
            bin_dir = self.bin_path
            
        lotus_bin = os.path.join(bin_dir, "lotus")
        if platform.system() == "Windows":
            lotus_bin += ".exe"
        
        if not os.path.exists(lotus_bin):
            logger.error(f"Lotus binary not found at {lotus_bin}")
            return False
        
        try:
            env = os.environ.copy()
            env["LOTUS_PATH"] = self.lotus_path
            
            # Test version command
            result = subprocess.run(
                [lotus_bin, "--version"], 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                env=env
            )
            logger.info(f"Lotus version: {result.stdout.strip()}")
            
            # Test basic command (daemon not running)
            result = subprocess.run(
                [lotus_bin, "net", "id"], 
                check=False,
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                env=env
            )
            
            # If daemon not running, this is expected to fail but still shows the binary works
            logger.info("Installation test completed")
            logger.info("Note: To use Lotus functionality, you'll need to start the Lotus daemon")
            logger.info("Run 'bin/lotus daemon' in a separate terminal")
            
            return True
        except Exception as e:
            logger.error(f"Installation test failed: {e}")
            return False

    def generate_lotus_helper_script(self, bin_dir=None):
        """
        Generate helper script to start and manage Lotus daemon.
        
        Args:
            bin_dir: Path to binary directory, or None for default
            
        Returns:
            Path to the generated script
        """
        if bin_dir is None:
            bin_dir = self.bin_path
            
        script_path = os.path.join("tools", "lotus_helper.py")
        os.makedirs("tools", exist_ok=True)
        
        with open(script_path, "w") as f:
            f.write(f"""#!/usr/bin/env python3
'''
Helper script for managing Lotus daemon.

This script provides simplified commands for starting, stopping, and
checking the status of the Lotus daemon.
'''

import argparse
import os
import signal
import subprocess
import sys
import time

# Setup paths
BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "{bin_dir}"))
LOTUS_BIN = os.path.join(BIN_DIR, "lotus")
if sys.platform == "win32":
    LOTUS_BIN += ".exe"

# Find and read PID file
def get_daemon_pid():
    lotus_dir = os.path.expanduser("~/.lotus")
    pid_file = os.path.join(lotus_dir, "daemon.pid")
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None

# Check if daemon is running
def is_daemon_running():
    pid = get_daemon_pid()
    if pid is None:
        return False
    
    # Check if process exists
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

# Start Lotus daemon
def start_daemon(lite=False):
    if is_daemon_running():
        print("Lotus daemon is already running")
        return True
    
    # Build command
    cmd = [LOTUS_BIN, "daemon"]
    if lite:
        cmd.append("--lite")
        
    # Start daemon process
    try:
        print("Starting Lotus daemon...")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Wait for daemon to start
        for i in range(10):
            time.sleep(1)
            if is_daemon_running():
                print("Lotus daemon started successfully")
                return True
        
        print("Warning: Daemon seems to be starting, but PID file not found yet")
        print("Check 'lotus net id' to verify if daemon is ready")
        return True
    except Exception as e:
        print(f"Error starting Lotus daemon: {{e}}")
        return False

# Stop Lotus daemon
def stop_daemon():
    pid = get_daemon_pid()
    if pid is None:
        print("Lotus daemon is not running")
        return True
    
    try:
        # Try graceful shutdown first
        subprocess.run([LOTUS_BIN, "daemon", "stop"], check=True)
        
        # Wait for process to exit
        for i in range(10):
            time.sleep(1)
            if not is_daemon_running():
                print("Lotus daemon stopped successfully")
                return True
        
        # Force kill if still running
        print("Daemon not responding to graceful shutdown, force killing...")
        os.kill(pid, signal.SIGKILL)
        return True
    except Exception as e:
        print(f"Error stopping Lotus daemon: {{e}}")
        return False

# Check daemon status
def check_status():
    if is_daemon_running():
        pid = get_daemon_pid()
        print(f"Lotus daemon is running (PID: {{pid}})")
        
        # Get additional info
        try:
            info = subprocess.check_output([LOTUS_BIN, "net", "id"], universal_newlines=True)
            print(info.strip())
        except subprocess.SubprocessError:
            print("Warning: Could not get daemon status")
    else:
        print("Lotus daemon is not running")

# Main function
def main():
    parser = argparse.ArgumentParser(description="Lotus daemon helper")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start Lotus daemon")
    start_parser.add_argument("--lite", action="store_true", help="Start in lite mode")
    
    # Stop command
    subparsers.add_parser("stop", help="Stop Lotus daemon")
    
    # Status command
    subparsers.add_parser("status", help="Check Lotus daemon status")
    
    args = parser.parse_args()
    
    if args.command == "start":
        start_daemon(args.lite)
    elif args.command == "stop":
        stop_daemon()
    elif args.command == "status":
        check_status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
""")
        
        # Make script executable
        if platform.system() != "windows":
            os.chmod(script_path, 0o755)
        
        logger.info(f"Created helper script at {script_path}")
        logger.info("You can use it to manage the Lotus daemon:")
        logger.info("  python tools/lotus_helper.py start  # Start daemon")
        logger.info("  python tools/lotus_helper.py stop   # Stop daemon")
        logger.info("  python tools/lotus_helper.py status # Check status")
        
        return script_path

    def build_lotus_from_source(self, version="v1.24.0"):
        """
        Build Lotus from source when binary is not available.
        
        Args:
            version: Version to build (default: v1.24.0)
            
        Returns:
            True if successful, False otherwise
        """
        # Default to string form for consistent logging and git branch usage.
        version_str = str(version) if version is not None else "v1.24.0"
        branch = version_str if version_str.startswith("v") else f"v{version_str}"

        logger.info(f"Building Lotus from source (version {version_str})...")
        
        required_go = (1, 23, 10)
        required_go_str = ".".join(str(part) for part in required_go)

        def _parse_go_version(output):
            match = re.search(r"go(\d+)\.(\d+)(?:\.(\d+))?", output)
            if not match:
                return None
            major, minor, patch = match.groups()
            return int(major), int(minor), int(patch or 0)

        go_version_str = None
        try:
            go_version_str = subprocess.check_output(
                ["go", "version"],
                stderr=subprocess.STDOUT,
                text=True,
            ).strip()
            logger.info(f"Go is installed: {go_version_str}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.info("Go is not installed. Installing Go...")
            if not self._install_go_for_build():
                logger.error("Failed to install Go. Cannot build from source.")
                return False
        else:
            go_version_tuple = _parse_go_version(go_version_str)
            if go_version_tuple is None or go_version_tuple < required_go:
                reported_version = go_version_str.split()[2] if go_version_str else "unknown"
                logger.info(
                    "Go version %s is below required go%s. Upgrading Go for Lotus build...",
                    reported_version,
                    required_go_str,
                )
                if not self._install_go_for_build():
                    logger.error("Failed to upgrade Go. Cannot build from source.")
                    return False

        try:
            go_version_str = subprocess.check_output(
                ["go", "version"],
                stderr=subprocess.STDOUT,
                text=True,
            ).strip()
            logger.info(f"Using Go version: {go_version_str}")
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.error(f"Unable to verify Go installation: {exc}")
            return False
        
        # Check for required build tools
        required_tools = ["make", "git"]
        for tool in required_tools:
            try:
                subprocess.run([tool, "--version"], check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error(f"Required build tool '{tool}' not found")
                return False

        if not self._ensure_jq_available():
            logger.error("jq is required for Lotus source builds")
            return False
        
        # Create temporary directory for building
        build_dir = tempfile.mkdtemp(prefix="lotus_build_")
        try:
            logger.info(f"Using build directory: {build_dir}")
            
            # Clone Lotus repository
            logger.info("Cloning Lotus repository...")
            clone_cmd = ["git", "clone", "--depth=1", "--branch", branch, 
                        "https://github.com/filecoin-project/lotus.git", build_dir]
            subprocess.run(clone_cmd, check=True, capture_output=True)
            
            # Build the binaries
            logger.info("Building Lotus binaries (this may take several minutes)...")
            build_cmd = ["make", "all"]
            env = os.environ.copy()
            env["GO111MODULE"] = "on"
            env["CGO_ENABLED"] = "1"
            
            # For ARM64, ensure proper GOARCH setting
            machine = platform.machine().lower()
            if "aarch64" in machine or "arm64" in machine:
                env["GOARCH"] = "arm64"
            
            result = subprocess.run(
                build_cmd,
                cwd=build_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes timeout for build
            )
            
            if result.returncode != 0:
                logger.error(f"Build failed: {result.stderr}")
                return False
            
            logger.info("Build successful!")
            
            # Install the built binaries
            logger.info("Installing built binaries...")
            os.makedirs(self.bin_path, exist_ok=True)
            
            binaries_installed = 0
            for binary in LOTUS_BINARIES:
                binary_name = binary
                if platform.system() == "Windows":
                    binary_name += ".exe"
                
                # Look for the binary in build directory
                built_binary = os.path.join(build_dir, binary_name)
                if not os.path.exists(built_binary):
                    logger.warning(f"Binary {binary_name} not found after build")
                    continue
                
                dest_binary = os.path.join(self.bin_path, binary_name)
                
                # Copy binary
                shutil.copy2(built_binary, dest_binary)
                
                # Make executable on Unix-like systems
                if platform.system() != "Windows":
                    os.chmod(dest_binary, 0o755)
                
                logger.info(f"Installed {binary_name}")
                binaries_installed += 1
            
            if binaries_installed == 0:
                logger.error("No binaries were installed")
                return False
            
            logger.info(f"Installed {binaries_installed} binaries to {self.bin_path}")
            
            # Verify the main binary works
            try:
                lotus_binary = os.path.join(self.bin_path, "lotus")
                if platform.system() == "Windows":
                    lotus_binary += ".exe"
                    
                version_output = subprocess.check_output([lotus_binary, "--version"])
                logger.info(f"Verification successful: {version_output.decode().strip()}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Binary verification failed: {e}")
                return False
            
        except subprocess.TimeoutExpired:
            logger.error("Build timed out after 30 minutes")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during build: {e}")
            if hasattr(e, 'output') and e.output:
                logger.error(f"Output: {e.output}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during build: {e}")
            return False
        finally:
            # Clean up build directory
            try:
                shutil.rmtree(build_dir)
                logger.info(f"Cleaned up build directory: {build_dir}")
            except Exception as e:
                logger.warning(f"Could not clean up build directory: {e}")
    
    def _install_go_for_build(self):
        """
        Install Go if not present (for building Lotus).
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Attempting to install Go...")
        
        system = platform.system()
        machine = platform.machine()
        
        # Determine Go download URL based on system and architecture
        go_version = "1.24.1"  # Minimum version required for current Lotus builds
        
        if system == "Linux":
            if "aarch64" in machine or "arm64" in machine.lower():
                go_url = f"https://go.dev/dl/go{go_version}.linux-arm64.tar.gz"
            elif "x86_64" in machine or "amd64" in machine:
                go_url = f"https://go.dev/dl/go{go_version}.linux-amd64.tar.gz"
            else:
                logger.error(f"Unsupported architecture for Go installation: {machine}")
                return False
        elif system == "Darwin":
            if "arm64" in machine.lower():
                go_url = f"https://go.dev/dl/go{go_version}.darwin-arm64.tar.gz"
            else:
                go_url = f"https://go.dev/dl/go{go_version}.darwin-amd64.tar.gz"
        else:
            logger.error(f"Unsupported system for automatic Go installation: {system}")
            logger.error("Please install Go manually from https://go.dev/dl/")
            return False
        
        try:
            # Download Go
            logger.info(f"Downloading Go from {go_url}...")
            go_tar = os.path.join(self.tmp_path, f"go{go_version}.tar.gz")
            
            if system == "Linux":
                subprocess.run(["wget", "-O", go_tar, go_url], check=True)
            elif system == "Darwin":
                subprocess.run(["curl", "-L", "-o", go_tar, go_url], check=True)
            
            # Extract Go
            go_install_dir = os.path.join(os.path.expanduser("~"), ".local")
            os.makedirs(go_install_dir, exist_ok=True)
            
            logger.info(f"Extracting Go to {go_install_dir}...")
            existing_go_dir = os.path.join(go_install_dir, "go")
            if os.path.exists(existing_go_dir):
                shutil.rmtree(existing_go_dir, ignore_errors=True)

            subprocess.run(["tar", "-C", go_install_dir, "-xzf", go_tar], check=True)
            try:
                os.remove(go_tar)
            except OSError:
                pass
            
            # Update PATH for current process
            go_bin = os.path.join(go_install_dir, "go", "bin")
            os.environ["PATH"] = f"{go_bin}:{os.environ.get('PATH', '')}"
            
            # Verify installation
            go_version_output = subprocess.check_output(["go", "version"], text=True).strip()
            logger.info(f"Go installed successfully: {go_version_output}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error installing Go: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error installing Go: {e}")
            return False

    def _ensure_jq_available(self):
        """Ensure jq is available for Lotus source builds."""
        if shutil.which("jq"):
            return True

        system = platform.system().lower()
        arch = platform.machine().lower()

        jq_downloads = {
            ("linux", "x86_64"): ("https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64", "jq"),
            ("linux", "amd64"): ("https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64", "jq"),
            ("darwin", "x86_64"): ("https://github.com/stedolan/jq/releases/download/jq-1.6/jq-osx-amd64", "jq"),
            ("darwin", "arm64"): ("https://github.com/stedolan/jq/releases/download/jq-1.6/jq-osx-arm64", "jq"),
            ("windows", "x86_64"): ("https://github.com/stedolan/jq/releases/download/jq-1.6/jq-win64.exe", "jq.exe"),
            ("windows", "amd64"): ("https://github.com/stedolan/jq/releases/download/jq-1.6/jq-win64.exe", "jq.exe"),
        }

        download_key = (system, arch)
        if download_key not in jq_downloads:
            logger.error(
                "jq is required for Lotus builds but cannot be automatically installed on %s/%s.",
                system,
                arch,
            )
            return False

        jq_url, jq_filename = jq_downloads[download_key]
        target_dir = os.path.join(self.bin_path, "build-tools")
        os.makedirs(target_dir, exist_ok=True)
        jq_path = os.path.join(target_dir, jq_filename)

        logger.info("jq not found; downloading portable binary for Lotus build...")
        try:
            urllib.request.urlretrieve(jq_url, jq_path)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to download jq: %s", exc)
            if os.path.exists(jq_path):
                os.remove(jq_path)
            return False

        if system != "windows":
            os.chmod(jq_path, 0o755)

        os.environ["PATH"] = f"{target_dir}:{os.environ.get('PATH', '')}"
        logger.info("jq installed at %s", jq_path)
        return True

    def install_lotus_daemon(self):
        """
        Install the Lotus daemon binary.
        
        Returns:
            CID of the installed binary if successful, False otherwise
        """
        # Check if already installed
        logger.info("Checking for existing Lotus installation")
        installation = self.check_existing_installation()
        if installation["installed"] and not self.metadata.get("force", False):
            logger.info(f"Lotus is already installed (version: {installation['version']})")
            if self.ipfs_multiformats:
                lotus_path = os.path.join(self.bin_path, "lotus")
                if platform.system() == "Windows":
                    lotus_path += ".exe"
                return self.ipfs_multiformats.get_cid(lotus_path)
            return True
            
        # Get release information
        version = self.metadata.get("version") or self.get_latest_lotus_version()
        logger.info(f"Installing Lotus version {version}")
        
        release_info = self.get_release_info(version)
        if not release_info:
            return False
            
        # Get download URL
        download_url, filename = self.get_download_url(release_info)
        if not download_url:
            logger.warning("No pre-built binary available for this platform")
            logger.info("Attempting to build Lotus from source...")
            if self.build_lotus_from_source(version):
                logger.info("Successfully built and installed Lotus from source")
                return True
            else:
                logger.error("Failed to build Lotus from source")
                return False
            
        # Create temp directory for download
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download archive
            archive_path = os.path.join(temp_dir, filename)
            if not self.download_file(download_url, archive_path):
                logger.warning("Failed to download binary, trying build from source...")
                if self.build_lotus_from_source(version):
                    logger.info("Successfully built and installed Lotus from source")
                    return True
                else:
                    logger.error("Failed to build Lotus from source")
                    return False
                
            # Verify download
            if not self.verify_download(archive_path):
                logger.error("Download verification failed")
                logger.info("Attempting to build Lotus from source as fallback...")
                if self.build_lotus_from_source(version):
                    logger.info("Successfully built and installed Lotus from source")
                    return True
                else:
                    logger.error("Failed to build Lotus from source")
                    return False
                
            # Extract archive
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            if not self.extract_archive(archive_path, extract_dir):
                logger.error("Failed to extract archive")
                logger.info("Attempting to build Lotus from source as fallback...")
                if self.build_lotus_from_source(version):
                    logger.info("Successfully built and installed Lotus from source")
                    return True
                else:
                    logger.error("Failed to build Lotus from source")
                    return False
                
            # Install binaries
            installed_binaries = self.install_binaries(extract_dir, self.bin_path)
            if not installed_binaries:
                logger.error("Failed to install Lotus binaries")
                logger.info("Attempting to build Lotus from source as fallback...")
                if self.build_lotus_from_source(version):
                    logger.info("Successfully built and installed Lotus from source")
                    return True
                else:
                    logger.error("Failed to build Lotus from source")
                    return False

            # Execute the binary to confirm runtime compatibility before proceeding.
            binary_ok, binary_output = self._verify_lotus_binary_execution()
            if not binary_ok:
                logger.error("Prebuilt Lotus binary failed to execute:")
                for line in binary_output.splitlines():
                    logger.error(line)

                # Remove incompatible binaries so the source build can proceed cleanly.
                self._remove_installed_binaries(installed_binaries)

                logger.info("Attempting to build Lotus from source as fallback...")
                if self.build_lotus_from_source(version):
                    logger.info("Successfully built and installed Lotus from source")
                    return True
                else:
                    logger.error("Failed to build Lotus from source")
                    return False
        
        # Verify installation
        installation = self.check_existing_installation()
        if not installation["installed"]:
            logger.error("Lotus installation verification failed")
            return False
            
        logger.info(f"Lotus {version} installed successfully")
        
        # Get CID if possible
        if self.ipfs_multiformats:
            lotus_path = os.path.join(self.bin_path, "lotus")
            if platform.system() == "Windows":
                lotus_path += ".exe"
            return self.ipfs_multiformats.get_cid(lotus_path)
            
        return True
        
    def install_lotus_miner(self):
        """
        Install the Lotus miner binary.
        
        Returns:
            CID of the installed binary if successful, False otherwise
        """
        # The miner binary is part of the same package, so if we have lotus installed,
        # we should already have lotus-miner
        installation = self.check_existing_installation()
        if installation["installed"] and installation["binaries"].get("lotus-miner", False):
            logger.info("Lotus miner already installed")
            if self.ipfs_multiformats:
                lotus_miner_path = os.path.join(self.bin_path, "lotus-miner")
                if platform.system() == "Windows":
                    lotus_miner_path += ".exe"
                return self.ipfs_multiformats.get_cid(lotus_miner_path)
            return True
            
        # If lotus is installed but the miner binary is missing,
        # we need to reinstall the full package
        if installation["installed"]:
            logger.info("Lotus installed but miner binary missing, reinstalling")
            result = self.install_lotus_daemon()
            
            # Check if miner is now installed
            new_installation = self.check_existing_installation()
            if new_installation["binaries"].get("lotus-miner", False):
                logger.info("Lotus miner successfully installed")
                if self.ipfs_multiformats:
                    lotus_miner_path = os.path.join(self.bin_path, "lotus-miner")
                    if platform.system() == "Windows":
                        lotus_miner_path += ".exe"
                    return self.ipfs_multiformats.get_cid(lotus_miner_path)
                return True
            else:
                logger.error("Failed to install lotus-miner binary")
                return False
        else:
            # If lotus isn't installed, install the full package
            logger.info("Lotus not installed, installing full package")
            result = self.install_lotus_daemon()
            
            # Check if miner is now installed
            new_installation = self.check_existing_installation()
            if new_installation["binaries"].get("lotus-miner", False):
                logger.info("Lotus miner successfully installed")
                if self.ipfs_multiformats:
                    lotus_miner_path = os.path.join(self.bin_path, "lotus-miner")
                    if platform.system() == "Windows":
                        lotus_miner_path += ".exe"
                    return self.ipfs_multiformats.get_cid(lotus_miner_path)
                return True
            else:
                logger.error("Failed to install lotus-miner binary")
                return False
                
    def install_lotus_worker(self):
        """
        Install the Lotus worker binary.
        
        Returns:
            CID of the installed binary if successful, False otherwise
        """
        # Similar to miner, the worker is part of the same package
        installation = self.check_existing_installation()
        if installation["installed"] and installation["binaries"].get("lotus-worker", False):
            logger.info("Lotus worker already installed")
            if self.ipfs_multiformats:
                lotus_worker_path = os.path.join(self.bin_path, "lotus-worker")
                if platform.system() == "Windows":
                    lotus_worker_path += ".exe"
                return self.ipfs_multiformats.get_cid(lotus_worker_path)
            return True
            
        # If lotus is installed but the worker binary is missing, reinstall
        if installation["installed"]:
            logger.info("Lotus installed but worker binary missing, reinstalling")
            result = self.install_lotus_daemon()
            
            # Check if worker is now installed
            new_installation = self.check_existing_installation()
            if new_installation["binaries"].get("lotus-worker", False):
                logger.info("Lotus worker successfully installed")
                if self.ipfs_multiformats:
                    lotus_worker_path = os.path.join(self.bin_path, "lotus-worker")
                    if platform.system() == "Windows":
                        lotus_worker_path += ".exe"
                    return self.ipfs_multiformats.get_cid(lotus_worker_path)
                return True
            else:
                logger.error("Failed to install lotus-worker binary")
                return False
        else:
            # If lotus isn't installed, install the full package
            logger.info("Lotus not installed, installing full package")
            result = self.install_lotus_daemon()
            
            # Check if worker is now installed
            new_installation = self.check_existing_installation()
            if new_installation["binaries"].get("lotus-worker", False):
                logger.info("Lotus worker successfully installed")
                if self.ipfs_multiformats:
                    lotus_worker_path = os.path.join(self.bin_path, "lotus-worker")
                    if platform.system() == "Windows":
                        lotus_worker_path += ".exe"
                    return self.ipfs_multiformats.get_cid(lotus_worker_path)
                return True
            else:
                logger.error("Failed to install lotus-worker binary")
                return False
                
    def install_lotus_gateway(self):
        """
        Install the Lotus gateway binary.
        
        Returns:
            CID of the installed binary if successful, False otherwise
        """
        # Similar to miner and worker, the gateway is part of the same package
        installation = self.check_existing_installation()
        if installation["installed"] and installation["binaries"].get("lotus-gateway", False):
            logger.info("Lotus gateway already installed")
            if self.ipfs_multiformats:
                lotus_gateway_path = os.path.join(self.bin_path, "lotus-gateway")
                if platform.system() == "Windows":
                    lotus_gateway_path += ".exe"
                return self.ipfs_multiformats.get_cid(lotus_gateway_path)
            return True
            
        # If lotus is installed but the gateway binary is missing, reinstall
        if installation["installed"]:
            logger.info("Lotus installed but gateway binary missing, reinstalling")
            result = self.install_lotus_daemon()
            
            # Check if gateway is now installed
            new_installation = self.check_existing_installation()
            if new_installation["binaries"].get("lotus-gateway", False):
                logger.info("Lotus gateway successfully installed")
                if self.ipfs_multiformats:
                    lotus_gateway_path = os.path.join(self.bin_path, "lotus-gateway")
                    if platform.system() == "Windows":
                        lotus_gateway_path += ".exe"
                    return self.ipfs_multiformats.get_cid(lotus_gateway_path)
                return True
            else:
                logger.error("Failed to install lotus-gateway binary")
                return False
        else:
            # If lotus isn't installed, install the full package
            logger.info("Lotus not installed, installing full package")
            result = self.install_lotus_daemon()
            
            # Check if gateway is now installed
            new_installation = self.check_existing_installation()
            if new_installation["binaries"].get("lotus-gateway", False):
                logger.info("Lotus gateway successfully installed")
                if self.ipfs_multiformats:
                    lotus_gateway_path = os.path.join(self.bin_path, "lotus-gateway")
                    if platform.system() == "Windows":
                        lotus_gateway_path += ".exe"
                    return self.ipfs_multiformats.get_cid(lotus_gateway_path)
                return True
            else:
                logger.error("Failed to install lotus-gateway binary")
                return False

    def config_lotus(self, **kwargs):
        """
        Configure Lotus daemon.
        
        Args:
            **kwargs: Additional configuration parameters
                - secret: Secret key for securing the Lotus node
                - api_port: Port for the Lotus API
                - p2p_port: Port for Lotus P2P connections
                
        Returns:
            Dictionary with configuration results
        """
        results = {}
        
        # Process parameters
        secret = kwargs.get("secret")
        if not secret and hasattr(self, "secret"):
            secret = self.secret
        if not secret:
            # Generate a random secret if not provided
            secret = binascii.hexlify(random.randbytes(32)).decode()
            self.secret = secret
            
        api_port = kwargs.get("api_port", 1234)
        p2p_port = kwargs.get("p2p_port", 1235)
        
        # Ensure Lotus path exists
        os.makedirs(self.lotus_path, exist_ok=True)
        
        # Get disk stats
        disk_available = self.disk_stats.get("disk_avail", 0)
        min_free_space = 32 * 1024 * 1024 * 1024  # 32 GB
        
        # Initialize lotus if needed
        lotus_cmd_path = os.path.join(self.bin_path, "lotus")
        if platform.system() == "Windows":
            lotus_cmd_path += ".exe"
            
        # Prepare environment
        env = os.environ.copy()
        env["LOTUS_PATH"] = self.lotus_path
        env["PATH"] = self.path
        
        try:
            # Initialize Lotus repo if needed
            if not os.path.exists(os.path.join(self.lotus_path, "config.toml")):
                logger.info("Initializing Lotus repository")
                
                init_cmd = [lotus_cmd_path, "init"]
                process = subprocess.run(
                    init_cmd,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True
                )
                
                if process.returncode != 0 and "already initialized" not in process.stderr:
                    logger.error(f"Failed to initialize Lotus: {process.stderr}")
                    results["init"] = False
                    return results
                else:
                    if "already initialized" in process.stderr:
                        logger.info("Lotus repository already initialized")
                    else:
                        logger.info("Lotus repository initialized successfully")
                    results["init"] = True
            else:
                logger.info("Lotus repository already exists")
                results["init"] = True
                
            # Configure API and P2P ports
            config_cmd = [
                lotus_cmd_path, 
                "config", 
                "set", 
                "API.ListenAddress", 
                f"/ip4/127.0.0.1/tcp/{api_port}/http"
            ]
            subprocess.run(config_cmd, env=env, check=True)
            
            config_cmd = [
                lotus_cmd_path,
                "config",
                "set",
                "Libp2p.ListenAddresses",
                f"[\"/ip4/0.0.0.0/tcp/{p2p_port}\", \"/ip6/::/tcp/{p2p_port}\"]"
            ]
            subprocess.run(config_cmd, env=env, check=True)
            
            # Configure storage space if we have enough disk space
            if disk_available > min_free_space:
                allocate = math.ceil(((disk_available - min_free_space) * 0.8) / 1024 / 1024 / 1024)
                logger.info(f"Configuring storage space: {allocate}GB")
                
                config_cmd = [
                    lotus_cmd_path,
                    "config",
                    "set",
                    "Storage.StorageMax",
                    f"{allocate}GB"
                ]
                subprocess.run(config_cmd, env=env, check=True)
                results["storage_configured"] = True
            else:
                logger.warning("Insufficient disk space for optimal configuration")
                results["storage_configured"] = False
                
            # Get node identity
            id_cmd = [lotus_cmd_path, "net", "id"]
            process = subprocess.run(
                id_cmd,
                env=env,
                check=False,
                capture_output=True,
                text=True
            )
            
            if process.returncode == 0:
                try:
                    peer_id = json.loads(process.stdout)
                    results["identity"] = peer_id.get("ID")
                except json.JSONDecodeError:
                    logger.warning("Failed to parse peer ID response")
                    results["identity"] = None
            else:
                # This is expected if the daemon isn't running
                logger.info("Could not get peer ID (daemon not running)")
                results["identity"] = None
                
            # Set up systemd service on Linux if running as root
            if platform.system() == "Linux" and os.geteuid() == 0:
                self._setup_systemd_service()
                results["systemd_configured"] = True
                
            # Overall success
            results["success"] = True
            
        except Exception as e:
            logger.error(f"Error configuring Lotus: {e}")
            results["success"] = False
            results["error"] = str(e)
            
        return results
            
    def config_lotus_miner(self, **kwargs):
        """
        Configure Lotus miner.
        
        Args:
            **kwargs: Additional configuration parameters
                - owner_address: Owner wallet address
                - sector_size: Sector size for storage
                - max_workers: Maximum number of worker threads
                
        Returns:
            Dictionary with configuration results
        """
        results = {}
        
        # Process parameters
        owner_address = kwargs.get("owner_address")
        sector_size = kwargs.get("sector_size", "32GiB")
        max_workers = kwargs.get("max_workers", 4)
        
        # Check if lotus-miner binary exists
        miner_cmd_path = os.path.join(self.bin_path, "lotus-miner")
        if platform.system() == "Windows":
            miner_cmd_path += ".exe"
            
        if not os.path.exists(miner_cmd_path):
            logger.error(f"Lotus miner binary not found at {miner_cmd_path}")
            results["success"] = False
            results["error"] = "Binary not found"
            return results
            
        # Prepare miner path
        miner_path = os.path.join(os.path.dirname(self.lotus_path), ".lotusminer")
        os.makedirs(miner_path, exist_ok=True)
        
        # Prepare environment
        env = os.environ.copy()
        env["LOTUS_PATH"] = self.lotus_path
        env["LOTUS_MINER_PATH"] = miner_path
        env["PATH"] = self.path
        
        try:
            # Check if miner is already initialized
            if os.path.exists(os.path.join(miner_path, "config.toml")):
                logger.info("Lotus miner already initialized")
                results["init"] = True
            else:
                # We need an owner address to initialize the miner
                if not owner_address:
                    logger.error("Owner address is required for miner initialization")
                    results["success"] = False
                    results["error"] = "Missing owner address"
                    return results
                    
                # Initialize miner
                logger.info(f"Initializing Lotus miner with owner {owner_address} and sector size {sector_size}")
                init_cmd = [
                    miner_cmd_path,
                    "init",
                    "--owner", owner_address,
                    "--sector-size", sector_size
                ]
                
                process = subprocess.run(
                    init_cmd,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True
                )
                
                if process.returncode != 0:
                    logger.error(f"Failed to initialize miner: {process.stderr}")
                    results["init"] = False
                    results["success"] = False
                    results["error"] = process.stderr
                    return results
                else:
                    logger.info("Miner initialized successfully")
                    results["init"] = True
            
            # Configure max workers
            config_cmd = [
                miner_cmd_path,
                "config",
                "set",
                "Mining.MaxWorkers",
                str(max_workers)
            ]
            subprocess.run(config_cmd, env=env, check=True)
            logger.info(f"Configured miner with {max_workers} max workers")
            
            # Configure API settings for the miner
            config_cmd = [
                miner_cmd_path,
                "config",
                "set",
                "API.ListenAddress",
                "/ip4/127.0.0.1/tcp/2345/http"
            ]
            subprocess.run(config_cmd, env=env, check=True)
            
            # Set up systemd service on Linux if running as root
            if platform.system() == "Linux" and os.geteuid() == 0:
                self._setup_miner_systemd_service()
                results["systemd_configured"] = True
                
            # Overall success
            results["success"] = True
            
        except Exception as e:
            logger.error(f"Error configuring Lotus miner: {e}")
            results["success"] = False
            results["error"] = str(e)
            
        return results

    def _setup_systemd_service(self):
        """
        Set up systemd service for Lotus daemon on Linux.
        
        Returns:
            True if successful, False otherwise
        """
        if platform.system() != "Linux" or os.geteuid() != 0:
            logger.info("Systemd service setup skipped (not Linux or not root)")
            return False
            
        logger.info("Setting up systemd service for Lotus daemon")
        
        # Create service file
        service_content = f"""[Unit]
Description=Lotus Daemon
After=network-online.target
Wants=network-online.target

[Service]
Environment=LOTUS_PATH={self.lotus_path}
ExecStart={os.path.join(self.bin_path, "lotus")} daemon
Restart=always
RestartSec=10
LimitNOFILE=8192:1048576
LimitNPROC=8192:1048576

[Install]
WantedBy=multi-user.target
"""

        # Write service file
        with open("/etc/systemd/system/lotus.service", "w") as f:
            f.write(service_content)
            
        # Reload systemd and enable service
        try:
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", "lotus.service"], check=True)
            logger.info("Lotus systemd service installed and enabled")
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to enable systemd service: {e}")
            return False

    def _setup_miner_systemd_service(self):
        """
        Set up systemd service for Lotus miner on Linux.
        
        Returns:
            True if successful, False otherwise
        """
        if platform.system() != "Linux" or os.geteuid() != 0:
            logger.info("Miner systemd service setup skipped (not Linux or not root)")
            return False
            
        logger.info("Setting up systemd service for Lotus miner")
        
        # Create service file
        miner_path = os.path.join(os.path.dirname(self.lotus_path), ".lotusminer")
        service_content = f"""[Unit]
Description=Lotus Miner
After=network-online.target lotus.service
Wants=network-online.target
Requires=lotus.service

[Service]
Environment=LOTUS_PATH={self.lotus_path}
Environment=LOTUS_MINER_PATH={miner_path}
ExecStart={os.path.join(self.bin_path, "lotus-miner")} run
Restart=always
RestartSec=10
LimitNOFILE=8192:1048576
LimitNPROC=8192:1048576

[Install]
WantedBy=multi-user.target
"""

        # Write service file
        with open("/etc/systemd/system/lotus-miner.service", "w") as f:
            f.write(service_content)
            
        # Reload systemd and enable service
        try:
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", "lotus-miner.service"], check=True)
            logger.info("Lotus miner systemd service installed and enabled")
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to enable miner systemd service: {e}")
            return False
            
    def run_lotus_daemon(self, **kwargs):
        """
        Run the Lotus daemon.
        
        Args:
            **kwargs: Additional parameters
                - background: Run in background (default: True)
                - lite: Run in lite mode (default: False)
                
        Returns:
            Process object if successful, False otherwise
        """
        # Check if lotus binary exists
        lotus_cmd_path = os.path.join(self.bin_path, "lotus")
        if platform.system() == "Windows":
            lotus_cmd_path += ".exe"
            
        if not os.path.exists(lotus_cmd_path):
            logger.error(f"Lotus binary not found at {lotus_cmd_path}")
            return False
            
        # Process parameters
        background = kwargs.get("background", True)
        lite = kwargs.get("lite", False)
        
        # Prepare environment
        env = os.environ.copy()
        env["LOTUS_PATH"] = self.lotus_path
        env["PATH"] = self.path
        
        # Build command
        cmd = [lotus_cmd_path, "daemon"]
        if lite:
            cmd.append("--lite")
            
        try:
            logger.info("Starting Lotus daemon")
            
            if background:
                # Start in background
                if platform.system() == "Windows":
                    # Use subprocess.CREATE_NEW_CONSOLE on Windows
                    import subprocess
                    process = subprocess.Popen(
                        cmd,
                        env=env,
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:
                    # Use nohup on Unix-like systems
                    cmd = ["nohup"] + cmd + ["&"]
                    process = subprocess.Popen(
                        " ".join(cmd),
                        env=env,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            else:
                # Start in foreground
                process = subprocess.Popen(
                    cmd,
                    env=env
                )
                
            logger.info(f"Lotus daemon started with PID {process.pid}")
            return process
            
        except Exception as e:
            logger.error(f"Error starting Lotus daemon: {e}")
            return False
            
    def run_lotus_miner(self, **kwargs):
        """
        Run the Lotus miner.
        
        Args:
            **kwargs: Additional parameters
                - background: Run in background (default: True)
                
        Returns:
            Process object if successful, False otherwise
        """
        # Check if lotus-miner binary exists
        miner_cmd_path = os.path.join(self.bin_path, "lotus-miner")
        if platform.system() == "Windows":
            miner_cmd_path += ".exe"
            
        if not os.path.exists(miner_cmd_path):
            logger.error(f"Lotus miner binary not found at {miner_cmd_path}")
            return False
            
        # Process parameters
        background = kwargs.get("background", True)
        
        # Prepare miner path
        miner_path = os.path.join(os.path.dirname(self.lotus_path), ".lotusminer")
        
        # Prepare environment
        env = os.environ.copy()
        env["LOTUS_PATH"] = self.lotus_path
        env["LOTUS_MINER_PATH"] = miner_path
        env["PATH"] = self.path
        
        # Build command
        cmd = [miner_cmd_path, "run"]
        
        try:
            logger.info("Starting Lotus miner")
            
            if background:
                # Start in background
                if platform.system() == "Windows":
                    # Use subprocess.CREATE_NEW_CONSOLE on Windows
                    import subprocess
                    process = subprocess.Popen(
                        cmd,
                        env=env,
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:
                    # Use nohup on Unix-like systems
                    cmd = ["nohup"] + cmd + ["&"]
                    process = subprocess.Popen(
                        " ".join(cmd),
                        env=env,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            else:
                # Start in foreground
                process = subprocess.Popen(
                    cmd,
                    env=env
                )
                
            logger.info(f"Lotus miner started with PID {process.pid}")
            return process
            
        except Exception as e:
            logger.error(f"Error starting Lotus miner: {e}")
            return False
                
    def kill_process_by_pattern(self, pattern):
        """
        Kill processes matching a pattern.
        
        Args:
            pattern: String pattern to match in process names
            
        Returns:
            True if successful, False on error
        """
        try:
            if platform.system() == "Windows":
                # Use tasklist and taskkill on Windows
                cmd = f'powershell -Command "Get-Process | Where-Object {{ $_.Name -like \'*{pattern}*\' }} | Select-Object Id"'
                output = subprocess.check_output(cmd, shell=True, text=True)
                
                for line in output.strip().split('\n'):
                    if line.strip() and line.strip().isdigit():
                        pid = line.strip()
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True)
                        logger.info(f"Killed process with PID {pid}")
            else:
                # Use pkill on Unix-like systems
                subprocess.run(["pkill", "-f", pattern], check=False)
                logger.info(f"Killed processes matching pattern: {pattern}")
                
            return True
        except Exception as e:
            logger.error(f"Error killing processes: {e}")
            return False
            
    def uninstall_lotus(self):
        """
        Uninstall Lotus components.
        
        Returns:
            True if successful, False otherwise
        """
        # Stop any running processes
        self.kill_process_by_pattern("lotus")
        
        # Remove binaries
        for binary in LOTUS_BINARIES:
            binary_path = os.path.join(self.bin_path, binary)
            if platform.system() == "Windows":
                binary_path += ".exe"
                
            if os.path.exists(binary_path):
                try:
                    os.remove(binary_path)
                    logger.info(f"Removed {binary_path}")
                except Exception as e:
                    logger.error(f"Failed to remove {binary_path}: {e}")
        
        # Remove systemd services on Linux if running as root
        if platform.system() == "Linux" and os.geteuid() == 0:
            try:
                # Disable and remove services
                for service in ["lotus.service", "lotus-miner.service"]:
                    service_path = f"/etc/systemd/system/{service}"
                    if os.path.exists(service_path):
                        subprocess.run(["systemctl", "disable", service], check=False)
                        os.remove(service_path)
                        logger.info(f"Removed systemd service: {service}")
                        
                # Reload systemd
                subprocess.run(["systemctl", "daemon-reload"], check=False)
            except Exception as e:
                logger.error(f"Error removing systemd services: {e}")
        
        # Offer to remove data directories
        logger.info(f"Data directories at {self.lotus_path} were not removed")
        logger.info("To completely remove Lotus data, manually delete these directories")
        
        return True

    def _install_go_for_build(self):
        """Install Go programming language for building from source."""
        try:
            print("Installing Go for building Lotus from source...")
            
            # Check if Go is already installed
            if shutil.which('go'):
                print("Go is already installed")
                return True
            
            # Download and install Go for ARM64
            go_version = "1.24.1"
            go_url = f"https://go.dev/dl/go{go_version}.linux-arm64.tar.gz"
            
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
                print(f"Downloading Go from {go_url}")
                command = f"wget {go_url} -O {tmp_file.name}"
                subprocess.run(command, shell=True, check=True)
                
                # Extract Go to /usr/local
                print("Extracting Go...")
                command = f"sudo tar -C /usr/local -xzf {tmp_file.name}"
                subprocess.run(command, shell=True, check=True)
                
                # Add Go to PATH
                go_path = "/usr/local/go/bin"
                if go_path not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = f"{go_path}:{os.environ.get('PATH', '')}"
                
                print("Go installation completed")
                return True
                
        except Exception as e:
            print(f"Error installing Go: {e}")
            return False

    def build_lotus_from_source(self, version=None):
        """Build Lotus from source code as fallback when binaries are not available."""
        try:
            print("Building Lotus from source...")
            
            # Install Go if not available
            if not shutil.which('go') and not self._install_go_for_build():
                raise Exception("Failed to install Go")
            
            # Use latest version if not specified
            if version is None:
                version = self.get_latest_lotus_version()
            
            # Remove 'v' prefix if present
            version = version.lstrip('v')
            
            with tempfile.TemporaryDirectory() as build_dir:
                print(f"Building Lotus {version} in {build_dir}")
                
                # Clone the Lotus repository
                repo_url = "https://github.com/filecoin-project/lotus.git"
                repo_path = os.path.join(build_dir, "lotus")
                
                command = f"git clone --branch v{version} --depth 1 {repo_url} {repo_path}"
                subprocess.run(command, shell=True, check=True, cwd=build_dir)
                
                # Build Lotus
                print("Compiling Lotus (this may take a while)...")
                command = "make clean && make all"
                subprocess.run(command, shell=True, check=True, cwd=repo_path, timeout=3600)
                
                # Install the binaries
                built_binaries = []
                for binary in LOTUS_BINARIES:
                    built_binary = os.path.join(repo_path, binary)
                    if os.path.exists(built_binary):
                        built_binaries.append(built_binary)
                
                if built_binaries:
                    # Create bin directory if it doesn't exist
                    os.makedirs(self.bin_path, exist_ok=True)
                    
                    # Copy binaries to bin directory
                    for binary_path in built_binaries:
                        binary_name = os.path.basename(binary_path)
                        dest_path = os.path.join(self.bin_path, binary_name)
                        shutil.copy2(binary_path, dest_path)
                        os.chmod(dest_path, 0o755)
                        print(f"Installed {binary_name} to {dest_path}")
                    
                    print(f"Lotus built and installed successfully ({len(built_binaries)} binaries)")
                    return True
                else:
                    raise Exception("No built binaries found")
                    
        except subprocess.TimeoutExpired:
            print("Build timed out after 60 minutes")
            return False
        except Exception as e:
            print(f"Error building Lotus from source: {e}")
            return False


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Install Lotus for ipfs_kit_py")
    parser.add_argument("--version", help=f"Lotus version to install (default: latest)")
    parser.add_argument("--force", action="store_true", help="Force reinstallation")
    parser.add_argument("--bin-dir", default="bin", help="Binary directory (default: bin)")
    parser.add_argument("--skip-params", action="store_true", help="Skip parameter download")
    args = parser.parse_args()
    
    # Resolve bin directory to absolute path
    bin_dir = os.path.abspath(args.bin_dir)
    
    # Create installer with metadata
    metadata = {
        "force": args.force,
        "bin_dir": bin_dir,
        "skip_params": args.skip_params
    }
    if args.version:
        metadata["version"] = args.version
    installer = install_lotus(metadata=metadata)
    
    # Check if already installed
    installation = installer.check_existing_installation(bin_dir)
    if not args.force and installation["installed"]:
        logger.info(f"Lotus is already installed (version: {installation['version']})")
        response = input("Do you want to reinstall? [y/N] ")
        if response.lower() != "y":
            logger.info("Installation aborted")
            return
    
    # Install Lotus daemon
    if installer.install_lotus_daemon():
        # Set up environment
        installer.setup_lotus_env()
        
        # Generate helper script
        installer.generate_lotus_helper_script(bin_dir)
        
        # Download parameters if not skipped
        if not args.skip_params:
            installer.download_params()
        
        # Test installation
        if installer.test_lotus_installation(bin_dir):
            logger.info("Lotus installation completed successfully!")
            logger.info(f"Binaries installed in: {bin_dir}")
            logger.info("To use Lotus with ipfs_kit_py, you need to:")
            logger.info("1. Start the Lotus daemon with: python tools/lotus_helper.py start")
            logger.info("2. Wait for the daemon to sync with the Filecoin network")
            logger.info("3. The lotus_kit module will then be able to connect to the daemon")
        else:
            logger.error("Lotus installation test failed")
            sys.exit(1)
    else:
        logger.error("Lotus installation failed")
        sys.exit(1)

if __name__ == "__main__":

    def ensure_daemon_configured(self):
        """Ensure Lotus daemon is properly configured before starting."""
        try:
            # Check if configuration exists
            config_file = os.path.join(self.lotus_path, "config.toml")
            if not os.path.exists(config_file):
                print(f"Lotus configuration not found at {config_file}, creating...")
                
                # Run configuration
                config_result = self.config_lotus(
                    api_port=getattr(self, 'api_port', 1234),
                    p2p_port=getattr(self, 'p2p_port', 1235)
                )
                
                if not config_result.get("success", False):
                    print(f"Failed to configure Lotus: {config_result.get('error', 'Unknown error')}")
                    return False
                
                print("Lotus configured successfully")
                return True
            else:
                print("Lotus configuration already exists")
                return True
                
        except Exception as e:
            print(f"Error ensuring Lotus configuration: {e}")
            return False

    main()