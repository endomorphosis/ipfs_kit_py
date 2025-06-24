#!/usr/bin/env python3
"""
Aria2 installation script for ipfs_kit_py.

This script handles the installation of Aria2 dependencies and binaries for the ipfs_kit_py package.
It provides a comprehensive, class-based implementation for installing and configuring Aria2 binaries
on multiple platforms.

Usage:
    As a module: from install_aria2 import install_aria2
                 installer = install_aria2(resources=None, metadata={"force": True})
                 installer.install_aria2_daemon()
                 installer.config_aria2()

    As a script: python install_aria2.py [--version VERSION] [--force] [--bin-dir PATH]
"""

import argparse
import binascii
import hashlib
import json
import logging
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
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("install_aria2")

# Default Aria2 release information
DEFAULT_ARIA2_VERSION = "1.37.0"
ARIA2_RELEASE_BASE_URL = "https://github.com/aria2/aria2/releases/download"
ARIA2_RELEASE_INFO_URL = "https://api.github.com/repos/aria2/aria2/releases/tags/release-{version}"

# Binary name depends on platform
ARIA2_BINARY = "aria2c"
ARIA2_BINARY_WIN = "aria2c.exe"

# Try to import multiformat validator from ipfs_kit_py
try:
    test_folder = os.path.dirname(os.path.dirname(__file__)) + "/test"
    sys.path.append(test_folder)
    from ipfs_kit_py.ipfs_multiformats import ipfs_multiformats_py
except ImportError:
    logger.warning("Could not import ipfs_multiformats_py - CID verification will be limited")
    ipfs_multiformats_py = None


class install_aria2:
    """Class for installing and configuring Aria2 components."""

    def __init__(self, resources=None, metadata=None):
        """
        Initialize Aria2 installer with resources and metadata.

        Args:
            resources: Dictionary of resources that may be shared between components
            metadata: Dictionary of metadata for configuration
                Supported metadata:
                    - version: Specific Aria2 version to install
                    - force: Force reinstallation even if already installed
                    - bin_dir: Custom binary directory path
        """
        self.resources = resources or {}
        self.metadata = metadata or {}

        # Setup environment
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.env_path = os.environ.get("PATH", "")

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

        # Bin directory setup
        self.bin_path = os.path.join(self.this_dir, "bin")
        self.bin_path = self.bin_path.replace("\\", "/")
        self.bin_path = self.bin_path.split("/")
        self.bin_path = "/".join(self.bin_path)
        os.makedirs(self.bin_path, exist_ok=True)

        # Temporary directory setup
        if platform.system() == "Windows":
            self.tmp_path = os.environ.get("TEMP", "/tmp")
        else:
            self.tmp_path = "/tmp"

        # Set up binaries distribution URLs and CIDs
        self._setup_distribution_info()

        # Prepare method references
        self.install_aria2_daemon = self.install_aria2_daemon
        self.config_aria2 = self.config_aria2

    def _setup_distribution_info(self):
        """Set up distribution URLs and CIDs for Aria2 binaries."""
        # Main Aria2 binaries URLs by platform
        # Initialize with latest version as default
        version = self.metadata.get("version", DEFAULT_ARIA2_VERSION)

        self.aria2_dists = {
            "macos arm64": f"{ARIA2_RELEASE_BASE_URL}/release-{version}/aria2-{version}-osx-darwin.tar.gz",
            "macos x86_64": f"{ARIA2_RELEASE_BASE_URL}/release-{version}/aria2-{version}-osx-darwin.tar.gz",
            "linux arm64": f"{ARIA2_RELEASE_BASE_URL}/release-{version}/aria2-{version}-aarch64-linux-gnu.tar.gz",
            "linux x86_64": f"{ARIA2_RELEASE_BASE_URL}/release-{version}/aria2-{version}-linux-gnu.tar.gz",
            "linux x86": f"{ARIA2_RELEASE_BASE_URL}/release-{version}/aria2-{version}-linux-gnu.tar.gz",
            "windows x86_64": f"{ARIA2_RELEASE_BASE_URL}/release-{version}/aria2-{version}-win-64bit-build1.zip",
            "windows x86": f"{ARIA2_RELEASE_BASE_URL}/release-{version}/aria2-{version}-win-32bit-build1.zip"
        }

        # CIDs for content verification (can be extended with actual CIDs)
        self.aria2_dists_cids = {
            "macos arm64": "",
            "macos x86_64": "",
            "linux arm64": "",
            "linux x86_64": "",
            "linux x86": "",
            "windows x86_64": "",
            "windows x86": ""
        }

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

        Returns:
            String identifier for the platform (e.g., "linux x86_64")
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
                aarch = "x86"

        # Default to x86_64 if detection fails
        if not aarch:
            if "64" in hardware["architecture"]:
                aarch = "x86_64"
            else:
                aarch = "x86"

        results = str(hardware["system"]).lower() + " " + aarch
        return results

    def download_file(self, url, target_path):
        """
        Download file from URL to target path with proper error handling.

        Args:
            url: URL to download from
            target_path: Path to save the file to

        Returns:
            Boolean indicating success or failure
        """
        try:
            logger.info(f"Downloading {url} to {target_path}")

            if platform.system() == "Windows":
                # Use PowerShell for Windows
                cmd = f'powershell -Command "Invoke-WebRequest -Uri \'{url}\' -OutFile \'{target_path}\'"'
                subprocess.run(cmd, shell=True, check=True)
            elif platform.system() == "Linux":
                # Use wget for Linux
                cmd = f"wget '{url}' -O '{target_path}'"
                subprocess.run(cmd, shell=True, check=True)
            elif platform.system() == "Darwin":
                # Use curl for macOS
                cmd = f"curl -L '{url}' -o '{target_path}'"
                subprocess.run(cmd, shell=True, check=True)
            else:
                # Fallback to Python's urllib
                with urllib.request.urlopen(url) as response, open(target_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)

            return True
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return False

    def is_aria2_installed(self):
        """
        Check if Aria2 is already installed.

        Returns:
            Boolean indicating if Aria2 is installed and version string if available
        """
        try:
            binary_name = ARIA2_BINARY_WIN if platform.system() == "Windows" else ARIA2_BINARY

            # First check if it's in our bin directory
            bin_path = os.path.join(self.bin_path, binary_name)
            if os.path.exists(bin_path):
                logger.info(f"Found Aria2 at {bin_path}")

                # Check version
                if platform.system() == "Windows":
                    cmd = f'"{bin_path}" --version'
                else:
                    cmd = f"'{bin_path}' --version"

                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0 and "aria2 version" in result.stdout:
                    version = result.stdout.strip().split("\n")[0]
                    return True, version
                return True, "Unknown version"

            # Then check if it's in PATH
            result = subprocess.run(
                f"{binary_name} --version",
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and "aria2 version" in result.stdout:
                version = result.stdout.strip().split("\n")[0]
                logger.info(f"Found Aria2 in PATH: {version}")
                return True, version

            return False, None

        except Exception as e:
            logger.debug(f"Error checking for Aria2 installation: {e}")
            return False, None

    def extract_archive(self, archive_path, extract_path):
        """
        Extract archive file (zip or tar.gz) to specified path.

        Args:
            archive_path: Path to archive file
            extract_path: Path to extract to

        Returns:
            Boolean indicating success or failure
        """
        try:
            logger.info(f"Extracting {archive_path} to {extract_path}")

            if archive_path.endswith('.zip'):
                if platform.system() == "Windows":
                    # Use PowerShell for Windows
                    cmd = f'powershell -Command "Expand-Archive -Path \'{archive_path}\' -DestinationPath \'{extract_path}\' -Force"'
                    subprocess.run(cmd, shell=True, check=True)
                else:
                    # Use unzip command on Linux/macOS
                    cmd = f"unzip -o '{archive_path}' -d '{extract_path}'"
                    subprocess.run(cmd, shell=True, check=True)
            elif archive_path.endswith('.tar.gz'):
                # Use tar command
                cmd = f"tar -xzf '{archive_path}' -C '{extract_path}'"
                subprocess.run(cmd, shell=True, check=True)
            else:
                logger.error(f"Unsupported archive format: {archive_path}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to extract archive: {e}")
            return False

    def find_binary_in_extracted_files(self, extract_path):
        """
        Find the Aria2 binary in extracted files.

        Args:
            extract_path: Path to extracted files

        Returns:
            Path to the binary if found, None otherwise
        """
        try:
            binary_name = ARIA2_BINARY_WIN if platform.system() == "Windows" else ARIA2_BINARY

            # Recursive search for the binary
            for root, dirs, files in os.walk(extract_path):
                if binary_name in files:
                    return os.path.join(root, binary_name)

            return None

        except Exception as e:
            logger.error(f"Error finding binary in extracted files: {e}")
            return None

    def install_aria2_daemon(self):
        """
        Install Aria2 daemon binary.

        Returns:
            Boolean indicating success or failure
        """
        # Check if already installed
        is_installed, version = self.is_aria2_installed()

        # Skip installation if already installed and not forced
        if is_installed and not self.metadata.get("force", False):
            logger.info(f"Aria2 is already installed: {version}")
            return True

        # Get distribution URL
        dist = self.dist_select()
        if dist not in self.aria2_dists:
            logger.error(f"Unsupported platform: {dist}")
            return False

        url = self.aria2_dists[dist]
        logger.info(f"Installing Aria2 from {url}")

        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".download", delete=False) as temp_file:
            try:
                # Download archive
                download_path = temp_file.name
                if not self.download_file(url, download_path):
                    return False

                # Create temporary extraction directory
                extract_dir = tempfile.mkdtemp(dir=self.tmp_path)

                # Extract archive
                if not self.extract_archive(download_path, extract_dir):
                    return False

                # Find binary
                binary_path = self.find_binary_in_extracted_files(extract_dir)
                if not binary_path:
                    logger.error(f"Could not find Aria2 binary in extracted files")
                    return False

                # Ensure bin directory exists
                os.makedirs(self.bin_path, exist_ok=True)

                # Copy binary to bin directory
                target_binary = ARIA2_BINARY_WIN if platform.system() == "Windows" else ARIA2_BINARY
                target_path = os.path.join(self.bin_path, target_binary)

                # Remove existing binary if present
                if os.path.exists(target_path):
                    os.remove(target_path)

                # Copy new binary
                shutil.copy2(binary_path, target_path)

                # Make executable on Unix-like systems
                if platform.system() != "Windows":
                    os.chmod(target_path, 0o755)

                # Verify installation
                is_installed, version = self.is_aria2_installed()
                if is_installed:
                    logger.info(f"Successfully installed Aria2: {version}")
                    return True
                else:
                    logger.error("Failed to verify Aria2 installation")
                    return False

            except Exception as e:
                logger.error(f"Error installing Aria2: {e}")
                return False

            finally:
                # Clean up temporary files
                try:
                    if os.path.exists(download_path):
                        os.unlink(download_path)
                    if os.path.exists(extract_dir):
                        shutil.rmtree(extract_dir)
                except Exception as e:
                    logger.warning(f"Error cleaning up temporary files: {e}")

    def create_systemd_service(self):
        """
        Create a systemd service file for Aria2 on Linux.

        Returns:
            Boolean indicating success or failure
        """
        if platform.system() != "Linux":
            logger.info("Systemd service creation is only supported on Linux")
            return False

        try:
            # Create service file content
            service_content = f"""[Unit]
Description=Aria2 Download Service
After=network.target

[Service]
Type=simple
User={os.environ.get("USER", "root")}
ExecStart={os.path.join(self.bin_path, ARIA2_BINARY)} --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all
Restart=on-failure
RestartSec=3
LimitNOFILE=100000

[Install]
WantedBy=multi-user.target
"""

            # Determine where to write the service file
            if os.geteuid() == 0:
                service_path = "/etc/systemd/system/aria2.service"
            else:
                # User service
                user_systemd_dir = os.path.expanduser("~/.config/systemd/user")
                os.makedirs(user_systemd_dir, exist_ok=True)
                service_path = f"{user_systemd_dir}/aria2.service"

            # Write service file
            with open(service_path, "w") as f:
                f.write(service_content)

            logger.info(f"Created systemd service file at {service_path}")

            # Enable and start service if root
            if os.geteuid() == 0:
                subprocess.run("systemctl daemon-reload", shell=True, check=True)
                subprocess.run("systemctl enable aria2", shell=True, check=True)
                logger.info("Enabled aria2 systemd service")

            return True

        except Exception as e:
            logger.error(f"Failed to create systemd service: {e}")
            return False

    def config_aria2(self):
        """
        Configure Aria2 daemon.

        Returns:
            Boolean indicating success or failure
        """
        try:
            # Create config directory
            if platform.system() == "Windows":
                config_dir = os.path.join(os.environ.get("APPDATA", ""), "aria2")
            else:
                config_dir = os.path.expanduser("~/.aria2")

            os.makedirs(config_dir, exist_ok=True)

            # Create basic configuration file
            config_file = os.path.join(config_dir, "aria2.conf")

            # Default configuration
            config_content = """# Basic Options
dir=~/Downloads
file-allocation=none
continue=true
max-concurrent-downloads=5
max-connection-per-server=5
min-split-size=20M
split=5

# RPC Options
enable-rpc=true
rpc-listen-all=false
rpc-secret=
rpc-max-request-size=10M

# Security Options
rpc-allow-origin-all=false
check-certificate=true

# BitTorrent Options
bt-enable-lpd=true
bt-max-peers=50
bt-request-peer-speed-limit=100K
bt-save-metadata=true
bt-seed-unverified=true
"""

            # Write configuration
            with open(config_file, "w") as f:
                f.write(config_content)

            logger.info(f"Created Aria2 configuration at {config_file}")

            # Create systemd service on Linux if not already installed
            if platform.system() == "Linux":
                self.create_systemd_service()

            return True

        except Exception as e:
            logger.error(f"Failed to configure Aria2: {e}")
            return False

    def __call__(self, method, **kwargs):
        """
        Call methods of the installer.

        Args:
            method: Method name to call
            **kwargs: Arguments for the method

        Returns:
            Result of the method call
        """
        if method == "install_aria2_daemon":
            return self.install_aria2_daemon()
        elif method == "config_aria2":
            return self.config_aria2()
        elif method == "create_systemd_service":
            return self.create_systemd_service()
        else:
            logger.error(f"Unknown method: {method}")
            return False


def main():
    """Command-line entry point for the installer."""
    parser = argparse.ArgumentParser(description="Install and configure Aria2")
    parser.add_argument("--version", help="Specify Aria2 version to install")
    parser.add_argument("--force", action="store_true", help="Force reinstallation")
    parser.add_argument("--bin-dir", help="Specify custom binary directory")
    args = parser.parse_args()

    # Prepare metadata
    metadata = {}
    if args.version:
        metadata["version"] = args.version
    if args.force:
        metadata["force"] = True
    if args.bin_dir:
        metadata["bin_dir"] = args.bin_dir

    # Initialize installer
    installer = install_aria2(metadata=metadata)

    # Install and configure
    if installer.install_aria2_daemon():
        logger.info("Aria2 daemon installed successfully")
    else:
        logger.error("Failed to install Aria2 daemon")
        return 1

    if installer.config_aria2():
        logger.info("Aria2 configured successfully")
    else:
        logger.error("Failed to configure Aria2")
        return 1

    logger.info("Aria2 installation completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
