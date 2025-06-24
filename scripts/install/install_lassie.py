#!/usr/bin/env python3
"""
Lassie installation script for ipfs_kit_py.

This script handles the installation of Lassie dependencies and binaries for the ipfs_kit_py package.
It provides a comprehensive, class-based implementation for installing and configuring Lassie binaries
on multiple platforms.

Usage:
    As a module: from install_lassie import install_lassie
                 installer = install_lassie(resources=None, metadata={"force": True})
                 installer.install_lassie_daemon()
                 installer.config_lassie()

    As a script: python install_lassie.py [--version VERSION] [--force] [--bin-dir PATH]
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
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("install_lassie")

# Default Lassie release information
DEFAULT_LASSIE_VERSION = "0.13.0"
LASSIE_GITHUB_API_URL = "https://api.github.com/repos/filecoin-project/lassie/releases"
LASSIE_RELEASE_BASE_URL = "https://github.com/filecoin-project/lassie/releases/download"
LASSIE_RELEASE_INFO_URL = "https://api.github.com/repos/filecoin-project/lassie/releases/tags/v{version}"

# Binary name
LASSIE_BINARY = "lassie"

# Try to import multiformat validator from ipfs_kit_py
try:
    test_folder = os.path.dirname(os.path.dirname(__file__)) + "/test"
    sys.path.append(test_folder)
    from ipfs_kit_py.ipfs_multiformats import ipfs_multiformats_py
except ImportError:
    logger.warning("Could not import ipfs_multiformats_py - CID verification will be limited")
    ipfs_multiformats_py = None


class install_lassie:
    """Class for installing and configuring Lassie components."""

    def __init__(self, resources=None, metadata=None):
        """
        Initialize Lassie installer with resources and metadata.

        Args:
            resources: Dictionary of resources that may be shared between components
            metadata: Dictionary of metadata for configuration
                Supported metadata:
                    - version: Specific Lassie version to install
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
        self.install_lassie_daemon = self.install_lassie_daemon

    def _setup_distribution_info(self):
        """Set up distribution URLs and CIDs for Lassie binaries."""
        # Main Lassie binaries URLs by platform
        # Initialize with latest version as default
        version = self.metadata.get("version", DEFAULT_LASSIE_VERSION)

        self.lassie_dists = {
            "macos arm64": f"{LASSIE_RELEASE_BASE_URL}/v{version}/lassie_{version}_darwin-arm64.tar.gz",
            "macos x86_64": f"{LASSIE_RELEASE_BASE_URL}/v{version}/lassie_{version}_darwin-amd64.tar.gz",
            "linux arm64": f"{LASSIE_RELEASE_BASE_URL}/v{version}/lassie_{version}_linux-arm64.tar.gz",
            "linux x86_64": f"{LASSIE_RELEASE_BASE_URL}/v{version}/lassie_{version}_linux-amd64.tar.gz",
            "linux x86": f"{LASSIE_RELEASE_BASE_URL}/v{version}/lassie_{version}_linux-386.tar.gz",
            "windows x86_64": f"{LASSIE_RELEASE_BASE_URL}/v{version}/lassie_{version}_windows-amd64.zip"
        }

        # CIDs for content verification (can be extended with actual CIDs)
        self.lassie_dists_cids = {
            "macos arm64": "",
            "macos x86_64": "",
            "linux arm64": "",
            "linux x86_64": "",
            "linux x86": "",
            "windows x86_64": ""
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
                aarch = "x86_64"
        # Default to x86_64 if we can't determine architecture
        else:
            if "64" in hardware["architecture"] or "64" in hardware["machine"].lower():
                aarch = "x86_64"
            else:
                aarch = "x86"

        results = str(hardware["system"]).lower() + " " + aarch
        return results

    def get_latest_lassie_version(self):
        """
        Get the latest stable Lassie release version from GitHub.

        Returns:
            Version string (e.g., "0.13.0")
        """
        try:
            with urllib.request.urlopen(LASSIE_GITHUB_API_URL) as response:
                data = json.loads(response.read().decode("utf-8"))
                for release in data:
                    # Skip pre-releases
                    if release.get("prerelease", False):
                        continue

                    tag_name = release["tag_name"]
                    # Extract version number (e.g., "0.13.0" from "v0.13.0")
                    match = re.match(r"v?(\d+\.\d+\.\d+)", tag_name)
                    if match:
                        return match.group(1)

                # If no suitable release found, return default
                logger.warning(f"Could not find latest release, using default: {DEFAULT_LASSIE_VERSION}")
                return DEFAULT_LASSIE_VERSION
        except Exception as e:
            logger.warning(f"Error checking latest release: {e}")
            logger.warning(f"Using default version: {DEFAULT_LASSIE_VERSION}")
            return DEFAULT_LASSIE_VERSION

    def get_release_info(self, version=None):
        """
        Get information about a specific Lassie release.

        Args:
            version: Lassie version string (e.g., "0.13.0"), or None for default

        Returns:
            Dictionary with release information
        """
        if version is None:
            if "version" in self.metadata:
                version = self.metadata["version"]
            else:
                version = self.get_latest_lassie_version()

        url = LASSIE_RELEASE_INFO_URL.format(version=version)
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
        Get the download URL for Lassie binaries from release info.

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
        asset_pattern = f"lassie_.*_{os_name}_{arch}\\.(tar\\.gz|zip)$"

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
            for file in files:
                if file == binary_name:
                    return os.path.join(root, file)

        return None

    def install_binary(self, source_dir, bin_dir):
        """
        Install Lassie binary to the bin directory.

        Args:
            source_dir: Directory containing extracted binary
            bin_dir: Target bin directory

        Returns:
            Path to installed binary if successful, None otherwise
        """
        logger.info(f"Installing Lassie binary to {bin_dir}")

        # Create bin directory if it doesn't exist
        os.makedirs(bin_dir, exist_ok=True)

        # Determine binary name based on platform
        binary_name = LASSIE_BINARY
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

            logger.info(f"Installed {binary_name} to {dest_path}")
            return dest_path
        else:
            logger.error(f"Could not find Lassie binary in {source_dir}")
            return None

    def check_existing_installation(self, bin_dir=None):
        """
        Check if Lassie is already installed in the bin directory.

        Args:
            bin_dir: Path to binary directory, or None for default

        Returns:
            Dictionary with installation status and version information
        """
        if bin_dir is None:
            bin_dir = self.bin_path

        lassie_path = os.path.join(bin_dir, LASSIE_BINARY)
        if platform.system() == "Windows":
            lassie_path += ".exe"

        result = {
            "installed": False,
            "version": None
        }

        if not os.path.exists(lassie_path):
            return result

        # Check lassie version
        try:
            output = subprocess.check_output([lassie_path, "--version"],
                                            stderr=subprocess.STDOUT,
                                            universal_newlines=True)
            version_match = re.search(r"lassie\s+version\s+v?(\d+\.\d+\.\d+)", output, re.IGNORECASE)
            if version_match:
                result["version"] = version_match.group(1)
            else:
                result["version"] = "unknown"

            result["installed"] = True
            logger.info(f"Found existing Lassie installation: {output.strip()}")

            return result
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.info(f"Lassie binary exists but could not determine version: {e}")
            result["installed"] = True
            return result

    def test_lassie_installation(self, bin_dir=None):
        """
        Test if the Lassie installation works.

        Args:
            bin_dir: Path to binary directory, or None for default

        Returns:
            True if installation test passes, False otherwise
        """
        logger.info("Testing Lassie installation")

        if bin_dir is None:
            bin_dir = self.bin_path

        lassie_bin = os.path.join(bin_dir, LASSIE_BINARY)
        if platform.system() == "Windows":
            lassie_bin += ".exe"

        if not os.path.exists(lassie_bin):
            logger.error(f"Lassie binary not found at {lassie_bin}")
            return False

        try:
            # Test version command
            result = subprocess.run(
                [lassie_bin, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            logger.info(f"Lassie version: {result.stdout.strip()}")

            # Test help command
            result = subprocess.run(
                [lassie_bin, "help"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )

            logger.info("Installation test completed successfully")
            return True
        except Exception as e:
            logger.error(f"Installation test failed: {e}")
            return False

    def _setup_systemd_service(self):
        """
        Set up systemd service for Lassie daemon on Linux.

        Returns:
            True if successful, False otherwise
        """
        if platform.system() != "Linux" or os.geteuid() != 0:
            logger.info("Systemd service setup skipped (not Linux or not root)")
            return False

        logger.info("Setting up systemd service for Lassie daemon")

        # Create service file
        service_content = f"""[Unit]
Description=Lassie Daemon
After=network-online.target
Wants=network-online.target

[Service]
ExecStart={os.path.join(self.bin_path, "lassie")} daemon
Restart=always
RestartSec=10
LimitNOFILE=8192:1048576
LimitNPROC=8192:1048576

[Install]
WantedBy=multi-user.target
"""

        # Write service file
        with open("/etc/systemd/system/lassie.service", "w") as f:
            f.write(service_content)

        # Reload systemd and enable service
        try:
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", "lassie.service"], check=True)
            logger.info("Lassie systemd service installed and enabled")
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to enable systemd service: {e}")
            return False

    def generate_lassie_helper_script(self, bin_dir=None):
        """
        Generate helper script to start and manage Lassie daemon.

        Args:
            bin_dir: Path to binary directory, or None for default

        Returns:
            Path to the generated script
        """
        if bin_dir is None:
            bin_dir = "bin"

        script_path = os.path.join("tools", "lassie_helper.py")
        os.makedirs("tools", exist_ok=True)

        with open(script_path, "w") as f:
            f.write(f"""#!/usr/bin/env python3
'''
Helper script for managing Lassie daemon.

This script provides simplified commands for starting, stopping, and
checking the status of the Lassie daemon.
'''

import argparse
import os
import signal
import subprocess
import sys
import time
import json
import re
import urllib.request
import socket

# Setup paths
BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "{bin_dir}"))
LASSIE_BIN = os.path.join(BIN_DIR, "lassie")
if sys.platform == "win32":
    LASSIE_BIN += ".exe"

# Default port for Lassie daemon
DEFAULT_PORT = 41443

# Get PID of running Lassie daemon
def get_daemon_pid():
    # Try to find process by port
    port = DEFAULT_PORT
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                f'netstat -ano | findstr ":{port}"',
                shell=True,
                text=True
            )
            for line in output.strip().split('\\n'):
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    return int(pid)
        except subprocess.CalledProcessError:
            pass
    else:
        try:
            output = subprocess.check_output(
                f"lsof -i :{port} -t",
                shell=True,
                text=True
            )
            return int(output.strip())
        except subprocess.CalledProcessError:
            pass

    # Try listing processes
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq lassie.exe" /FO CSV /NH',
                shell=True,
                text=True
            )
            if "lassie.exe" in output:
                pid_match = re.search(r'"lassie.exe","([0-9]+)"', output)
                if pid_match:
                    return int(pid_match.group(1))
        except subprocess.CalledProcessError:
            pass
    else:
        try:
            output = subprocess.check_output(
                "pgrep -f 'lassie daemon'",
                shell=True,
                text=True
            )
            if output.strip():
                return int(output.strip())
        except subprocess.CalledProcessError:
            pass

    return None

# Check if Lassie daemon is running
def is_daemon_running():
    # First check process
    pid = get_daemon_pid()
    if pid is None:
        return False

    # Check if process exists
    try:
        os.kill(pid, 0)
        # Additionally check if API is responsive
        try:
            urllib.request.urlopen(f"http://localhost:{DEFAULT_PORT}/health", timeout=1)
            return True
        except (urllib.error.URLError, socket.timeout):
            # Process exists but API not responding
            return False
    except OSError:
        return False

# Start Lassie daemon
def start_daemon(port=DEFAULT_PORT):
    if is_daemon_running():
        print("Lassie daemon is already running")
        return True

    # Build command
    cmd = [LASSIE_BIN, "daemon", "-p", str(port)]

    # Start daemon process
    try:
        print(f"Starting Lassie daemon on port {port}...")

        if sys.platform == "win32":
            # Use subprocess.CREATE_NEW_CONSOLE on Windows
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # Use nohup on Unix-like systems
            nohup_cmd = f"nohup {' '.join(cmd)} > /tmp/lassie-daemon.log 2>&1 &"
            subprocess.run(nohup_cmd, shell=True, check=True)

        # Wait for daemon to start
        for i in range(10):
            time.sleep(1)
            if is_daemon_running():
                print("Lassie daemon started successfully")
                return True

        print("Warning: Daemon process started but API not responding yet. Will retry a few more times...")

        # Extra wait time
        for i in range(5):
            time.sleep(2)
            if is_daemon_running():
                print("Lassie daemon started successfully")
                return True

        print("Warning: Daemon seems to be starting, but API not yet available")
        return True
    except Exception as e:
        print(f"Error starting Lassie daemon: {{e}}")
        return False

# Stop Lassie daemon
def stop_daemon():
    pid = get_daemon_pid()
    if pid is None:
        print("Lassie daemon is not running")
        return True

    try:
        # Try graceful shutdown first (Ctrl+C)
        if sys.platform == "win32":
            subprocess.run(f"taskkill /PID {pid}", shell=True, check=False)
        else:
            os.kill(pid, signal.SIGTERM)

        # Wait for process to exit
        for i in range(10):
            time.sleep(1)
            if not is_daemon_running():
                print("Lassie daemon stopped successfully")
                return True

        # Force kill if still running
        print("Daemon not responding to graceful shutdown, force killing...")
        if sys.platform == "win32":
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=False)
        else:
            os.kill(pid, signal.SIGKILL)

        time.sleep(1)
        if not is_daemon_running():
            print("Lassie daemon stopped successfully (force kill)")
            return True
        else:
            print("Failed to stop Lassie daemon")
            return False
    except Exception as e:
        print(f"Error stopping Lassie daemon: {{e}}")
        return False

# Check daemon status
def check_status():
    if is_daemon_running():
        pid = get_daemon_pid()
        print(f"Lassie daemon is running (PID: {{pid}}, Port: {DEFAULT_PORT})")

        # Get additional info
        try:
            with urllib.request.urlopen(f"http://localhost:{DEFAULT_PORT}/health") as response:
                health_data = json.loads(response.read().decode())
                print(f"Health status: {{'uptime': {health_data.get('uptime', 'unknown')}, 'version': {health_data.get('version', 'unknown')}}}")
        except Exception as e:
            print(f"Warning: Could not get daemon health status: {e}")
    else:
        print("Lassie daemon is not running")

# Simple fetch test
def fetch_test(cid="bafybeic56z3yccnla3cutmvqsn5zy3g24muupcsjtoyp3pu5pm5amurjx4"):
    if not is_daemon_running():
        print("Lassie daemon is not running. Starting daemon...")
        start_daemon()
        if not is_daemon_running():
            print("Failed to start Lassie daemon")
            return False

    try:
        print(f"Testing Lassie fetch with CID: {cid}")
        temp_file = os.path.join(tempfile.gettempdir(), f"{cid}.car")

        # Use API endpoint
        api_url = f"http://localhost:{DEFAULT_PORT}/ipfs/{cid}?filename=test.car"
        print(f"Fetching from: {api_url}")

        # Use urllib to fetch with a longer timeout (30 seconds)
        try:
            with urllib.request.urlopen(api_url, timeout=30) as response:
                with open(temp_file, 'wb') as f:
                    f.write(response.read())

            print(f"Successfully fetched CID {cid} to {temp_file}")
            print("Test passed!")
            return True
        except Exception as e:
            print(f"Error fetching via API: {e}")

            # Try direct command
            print("Trying direct command...")
            result = subprocess.run(
                [LASSIE_BIN, "fetch", "-o", temp_file, cid],
                check=False,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"Successfully fetched CID {cid} to {temp_file}")
                print("Test passed!")
                return True
            else:
                print(f"Error fetching with direct command: {result.stderr}")
                return False

    except Exception as e:
        print(f"Error during fetch test: {e}")
        return False

# Main function
def main():
    parser = argparse.ArgumentParser(description="Lassie daemon helper")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start Lassie daemon")
    start_parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help=f"Port number (default: {DEFAULT_PORT})")

    # Stop command
    subparsers.add_parser("stop", help="Stop Lassie daemon")

    # Status command
    subparsers.add_parser("status", help="Check Lassie daemon status")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test Lassie fetch with a sample CID")
    test_parser.add_argument("-c", "--cid", default="bafybeic56z3yccnla3cutmvqsn5zy3g24muupcsjtoyp3pu5pm5amurjx4",
                           help="CID to fetch (default: sample birb.mp4)")

    args = parser.parse_args()

    if args.command == "start":
        start_daemon(args.port)
    elif args.command == "stop":
        stop_daemon()
    elif args.command == "status":
        check_status()
    elif args.command == "test":
        fetch_test(args.cid)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
""")

        # Make script executable
        if platform.system() != "windows":
            os.chmod(script_path, 0o755)

        logger.info(f"Created helper script at {script_path}")
        logger.info("You can use it to manage the Lassie daemon:")
        logger.info("  python tools/lassie_helper.py start   # Start daemon")
        logger.info("  python tools/lassie_helper.py stop    # Stop daemon")
        logger.info("  python tools/lassie_helper.py status  # Check status")
        logger.info("  python tools/lassie_helper.py test    # Test fetch")

        return script_path

    def install_lassie_daemon(self):
        """
        Install the Lassie daemon binary.

        Returns:
            CID of the installed binary if successful, False otherwise
        """
        # Check if already installed
        logger.info("Checking for existing Lassie installation")
        installation = self.check_existing_installation()
        if installation["installed"] and not self.metadata.get("force", False):
            logger.info(f"Lassie is already installed (version: {installation['version']})")
            if self.ipfs_multiformats:
                lassie_path = os.path.join(self.bin_path, LASSIE_BINARY)
                if platform.system() == "Windows":
                    lassie_path += ".exe"
                return self.ipfs_multiformats.get_cid(lassie_path)
            return True

        # Get release information
        version = self.metadata.get("version", self.get_latest_lassie_version())
        logger.info(f"Installing Lassie version {version}")

        release_info = self.get_release_info(version)
        if not release_info:
            return False

        # Get download URL
        download_url, filename = self.get_download_url(release_info)
        if not download_url:
            return False

        # Create temp directory for download
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download archive
            archive_path = os.path.join(temp_dir, filename)
            if not self.download_file(download_url, archive_path):
                return False

            # Verify download
            if not self.verify_download(archive_path):
                logger.error("Download verification failed")
                return False

            # Extract archive
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            if not self.extract_archive(archive_path, extract_dir):
                return False

            # Install binary
            binary_path = self.install_binary(extract_dir, self.bin_path)
            if not binary_path:
                logger.error("Failed to install Lassie binary")
                return False

        # Verify installation
        installation = self.check_existing_installation()
        if not installation["installed"]:
            logger.error("Lassie installation verification failed")
            return False

        logger.info(f"Lassie {version} installed successfully")

        # Get CID if possible
        if self.ipfs_multiformats:
            lassie_path = os.path.join(self.bin_path, LASSIE_BINARY)
            if platform.system() == "Windows":
                lassie_path += ".exe"
            return self.ipfs_multiformats.get_cid(lassie_path)

        return True

    def config_lassie(self, **kwargs):
        """
        Configure Lassie daemon.

        Args:
            **kwargs: Additional configuration parameters
                - port: Port for the Lassie daemon (default: 41443)

        Returns:
            Dictionary with configuration results
        """
        results = {}

        # Process parameters
        port = kwargs.get("port", 41443)

        # Test lassie installation
        if not self.test_lassie_installation():
            results["success"] = False
            results["error"] = "Lassie installation test failed"
            return results

        # Set up systemd service on Linux if running as root
        if platform.system() == "Linux" and os.geteuid() == 0:
            systemd_result = self._setup_systemd_service()
            results["systemd_configured"] = systemd_result

        # Generate helper script
        helper_script = self.generate_lassie_helper_script()
        results["helper_script"] = helper_script

        # Overall success
        results["success"] = True

        return results

    def run_lassie_daemon(self, **kwargs):
        """
        Run the Lassie daemon.

        Args:
            **kwargs: Additional parameters
                - port: Port number for daemon to listen on (default: 41443)
                - background: Run in background (default: True)

        Returns:
            Process object if successful, False otherwise
        """
        # Check if lassie binary exists
        lassie_cmd_path = os.path.join(self.bin_path, LASSIE_BINARY)
        if platform.system() == "Windows":
            lassie_cmd_path += ".exe"

        if not os.path.exists(lassie_cmd_path):
            logger.error(f"Lassie binary not found at {lassie_cmd_path}")
            return False

        # Process parameters
        port = kwargs.get("port", 41443)
        background = kwargs.get("background", True)

        # Build command
        cmd = [lassie_cmd_path, "daemon", "-p", str(port)]

        try:
            logger.info(f"Starting Lassie daemon on port {port}")

            if background:
                # Start in background
                if platform.system() == "Windows":
                    # Use subprocess.CREATE_NEW_CONSOLE on Windows
                    process = subprocess.Popen(
                        cmd,
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:
                    # Use nohup on Unix-like systems
                    nohup_cmd = f"nohup {' '.join(cmd)} > /tmp/lassie-daemon.log 2>&1 &"
                    process = subprocess.Popen(
                        nohup_cmd,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            else:
                # Start in foreground
                process = subprocess.Popen(cmd)

            logger.info(f"Lassie daemon started with PID {process.pid}")
            return process

        except Exception as e:
            logger.error(f"Error starting Lassie daemon: {e}")
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

    def uninstall_lassie(self):
        """
        Uninstall Lassie components.

        Returns:
            True if successful, False otherwise
        """
        # Stop any running processes
        self.kill_process_by_pattern("lassie")

        # Remove binary
        binary_path = os.path.join(self.bin_path, LASSIE_BINARY)
        if platform.system() == "Windows":
            binary_path += ".exe"

        if os.path.exists(binary_path):
            try:
                os.remove(binary_path)
                logger.info(f"Removed {binary_path}")
            except Exception as e:
                logger.error(f"Failed to remove {binary_path}: {e}")

        # Remove systemd service on Linux if running as root
        if platform.system() == "Linux" and os.geteuid() == 0:
            try:
                # Disable and remove service
                service_path = "/etc/systemd/system/lassie.service"
                if os.path.exists(service_path):
                    subprocess.run(["systemctl", "disable", "lassie.service"], check=False)
                    os.remove(service_path)
                    logger.info("Removed systemd service: lassie.service")

                # Reload systemd
                subprocess.run(["systemctl", "daemon-reload"], check=False)
            except Exception as e:
                logger.error(f"Error removing systemd service: {e}")

        logger.info("Lassie uninstallation completed")
        return True


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Install Lassie for ipfs_kit_py")
    parser.add_argument("--version", help=f"Lassie version to install (default: latest)")
    parser.add_argument("--force", action="store_true", help="Force reinstallation")
    parser.add_argument("--bin-dir", default="bin", help="Binary directory (default: bin)")
    args = parser.parse_args()

    # Resolve bin directory to absolute path
    bin_dir = os.path.abspath(args.bin_dir)

    # Create installer with metadata
    metadata = {
        "version": args.version,
        "force": args.force,
        "bin_dir": bin_dir
    }
    installer = install_lassie(metadata=metadata)

    # Check if already installed
    installation = installer.check_existing_installation(bin_dir)
    if not args.force and installation["installed"]:
        logger.info(f"Lassie is already installed (version: {installation['version']})")
        response = input("Do you want to reinstall? [y/N] ")
        if response.lower() != "y":
            logger.info("Installation aborted")
            return

    # Install Lassie daemon
    if installer.install_lassie_daemon():
        # Configure Lassie
        installer.config_lassie()

        # Test installation
        if installer.test_lassie_installation(bin_dir):
            logger.info("Lassie installation completed successfully!")
            logger.info(f"Binary installed in: {bin_dir}")
            logger.info("To use Lassie:")
            logger.info("1. Start the daemon with: python tools/lassie_helper.py start")
            logger.info("2. Fetch content with: lassie fetch <cid>")
            logger.info("3. Or use the HTTP API at http://localhost:41443/ipfs/<cid>")
        else:
            logger.error("Lassie installation test failed")
            sys.exit(1)
    else:
        logger.error("Lassie installation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
