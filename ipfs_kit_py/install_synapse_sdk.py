#!/usr/bin/env python3
"""
Synapse SDK installation script for ipfs_kit_py.

This script handles the installation of Synapse SDK dependencies and Node.js runtime
for the ipfs_kit_py package. It provides a comprehensive, class-based implementation for 
installing and configuring Synapse SDK components on multiple platforms.

Usage:
    As a module: from install_synapse_sdk import install_synapse_sdk
                 installer = install_synapse_sdk(resources=None, metadata={"force": True})
                 installer.install_synapse_sdk_dependencies()
                 installer.config_synapse_sdk()

    As a script: python install_synapse_sdk.py [--force] [--verbose] [--node-version VERSION]
"""

import os
import sys
import json
import logging
import platform
import subprocess
import tempfile
import shutil
import importlib
try:
    import requests
except ModuleNotFoundError:
    requests = None
import tarfile
import zipfile
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("install_synapse_sdk")

def _ensure_requests() -> bool:
    """Ensure the requests library is available."""
    global requests
    if requests is not None:
        return True
    try:
        logger.info("Installing requests...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "requests"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            requests = importlib.import_module("requests")
            return True
        logger.warning(f"Failed to install requests: {result.stderr}")
    except Exception as e:
        logger.warning(f"Error installing requests: {e}")
    return False

# Synapse SDK NPM package information
SYNAPSE_SDK_PACKAGE = "@filoz/synapse-sdk"
ETHERS_PACKAGE = "ethers"
DEFAULT_SYNAPSE_VERSION = "latest"
DEFAULT_ETHERS_VERSION = "^6.0.0"

# Node.js version requirements
MIN_NODE_VERSION = "16.0.0"
RECOMMENDED_NODE_VERSION = "18.0.0"
NODE_DOWNLOAD_BASE_URL = "https://nodejs.org/dist"

# JavaScript wrapper files
JS_WRAPPER_FILES = {
    "synapse_wrapper.js": """
import { Synapse, RPC_URLS, TOKENS, CONTRACT_ADDRESSES } from '@filoz/synapse-sdk';
import { ethers } from 'ethers';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);

class SynapseWrapper {
    constructor() {
        this.synapse = null;
        this.storage = null;
    }

    async initialize(config) {
        try {
            const options = {
                privateKey: config.privateKey,
                rpcURL: config.rpcUrl || RPC_URLS.calibration.http
            };

            if (config.authorization) {
                options.authorization = config.authorization;
            }

            if (config.pandoraAddress) {
                options.pandoraAddress = config.pandoraAddress;
            }

            this.synapse = await Synapse.create(options);
            return { success: true, network: this.synapse.getNetwork() };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async createStorage(options = {}) {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            this.storage = await this.synapse.createStorage(options);
            return {
                success: true,
                proofSetId: this.storage.proofSetId,
                storageProvider: this.storage.storageProvider
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async storeData(data, options = {}) {
        try {
            if (!this.storage) {
                await this.createStorage();
            }

            const dataBuffer = Buffer.from(data, 'base64');
            const result = await this.storage.upload(dataBuffer, options);
            
            return {
                success: true,
                commp: result.commp,
                size: result.size,
                rootId: result.rootId
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async retrieveData(commp, options = {}) {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const data = await this.synapse.download(commp, options);
            return {
                success: true,
                data: Buffer.from(data).toString('base64')
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getBalance(token = 'USDFC') {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const balance = await this.synapse.payments.balance();
            const walletBalance = await this.synapse.payments.walletBalance(token);
            
            return {
                success: true,
                contractBalance: balance.toString(),
                walletBalance: walletBalance.toString()
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async depositFunds(amount, token = 'USDFC') {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const amountBigInt = ethers.parseUnits(amount, 18);
            const tx = await this.synapse.payments.deposit(amountBigInt, token);
            
            return {
                success: true,
                transactionHash: tx.hash
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async approveService(serviceAddress, rateAllowance, lockupAllowance) {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const rateAmount = ethers.parseUnits(rateAllowance, 18);
            const lockupAmount = ethers.parseUnits(lockupAllowance, 18);
            
            const tx = await this.synapse.payments.approveService(
                serviceAddress,
                rateAmount,
                lockupAmount
            );
            
            return {
                success: true,
                transactionHash: tx.hash
            };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getStorageInfo() {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const info = await this.synapse.getStorageInfo();
            return { success: true, info };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getProviderInfo(providerAddress) {
        try {
            if (!this.synapse) {
                throw new Error('Synapse not initialized');
            }

            const info = await this.synapse.getProviderInfo(providerAddress);
            return { success: true, info };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async getPieceStatus(commp) {
        try {
            if (!this.storage) {
                throw new Error('Storage service not created');
            }

            const status = await this.storage.pieceStatus(commp);
            return { success: true, status };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
}

// CLI interface for Python integration
const wrapper = new SynapseWrapper();

process.stdin.setEncoding('utf8');
let inputData = '';

process.stdin.on('data', (chunk) => {
    inputData += chunk;
});

process.stdin.on('end', async () => {
    try {
        const command = JSON.parse(inputData);
        let result;
        
        switch (command.method) {
            case 'initialize':
                result = await wrapper.initialize(command.params);
                break;
            case 'createStorage':
                result = await wrapper.createStorage(command.params || {});
                break;
            case 'storeData':
                result = await wrapper.storeData(command.params.data, command.params.options || {});
                break;
            case 'retrieveData':
                result = await wrapper.retrieveData(command.params.commp, command.params.options || {});
                break;
            case 'getBalance':
                result = await wrapper.getBalance(command.params.token);
                break;
            case 'depositFunds':
                result = await wrapper.depositFunds(command.params.amount, command.params.token);
                break;
            case 'approveService':
                result = await wrapper.approveService(
                    command.params.serviceAddress,
                    command.params.rateAllowance,
                    command.params.lockupAllowance
                );
                break;
            case 'getStorageInfo':
                result = await wrapper.getStorageInfo();
                break;
            case 'getProviderInfo':
                result = await wrapper.getProviderInfo(command.params.providerAddress);
                break;
            case 'getPieceStatus':
                result = await wrapper.getPieceStatus(command.params.commp);
                break;
            default:
                result = { success: false, error: 'Unknown method: ' + command.method };
        }
        
        console.log(JSON.stringify(result));
    } catch (error) {
        console.log(JSON.stringify({ success: false, error: error.message }));
    }
});

export default SynapseWrapper;
""",
    "package.json": """
{
  "name": "ipfs-kit-synapse-bridge",
  "version": "1.0.0",
  "description": "JavaScript bridge for Synapse SDK integration with IPFS Kit Python",
  "type": "module",
  "main": "synapse_wrapper.js",
  "dependencies": {
    "@filoz/synapse-sdk": "^0.19.0",
    "ethers": "^6.0.0"
  },
  "engines": {
    "node": ">=16.0.0"
  },
  "scripts": {
    "test": "node synapse_wrapper.js"
  },
  "keywords": [
    "filecoin",
    "synapse",
    "storage",
    "ipfs-kit"
  ],
  "license": "MIT"
}
"""
}


class install_synapse_sdk:
    """Class for installing and configuring Synapse SDK components."""
    
    def __init__(self, resources=None, metadata=None):
        """
        Initialize Synapse SDK installer with resources and metadata.
        
        Args:
            resources: Dictionary of resources that may be shared between components
            metadata: Dictionary of metadata for configuration
                Supported metadata:
                    - force: Force reinstallation even if already installed
                    - verbose: Enable verbose output
                    - node_version: Specific Node.js version to install
                    - synapse_version: Specific Synapse SDK version to install
                    - skip_node_check: Skip Node.js version checking
        """
        # Initialize basic properties
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Setup environment
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.env_path = os.environ.get("PATH", "")
        
        # Configuration options
        self.force = self.metadata.get("force", False)
        self.verbose = self.metadata.get("verbose", False)
        self.skip_node_check = self.metadata.get("skip_node_check", False)
        self.node_version = self.metadata.get("node_version", RECOMMENDED_NODE_VERSION)
        self.synapse_version = self.metadata.get("synapse_version", DEFAULT_SYNAPSE_VERSION)
        
        # Set up logging level
        if self.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            
        # Setup paths
        self.bin_path = os.path.join(self.this_dir, "bin")
        self.js_path = os.path.join(self.this_dir, "js")
        self.tmp_path = tempfile.gettempdir()
        
        # Create directories
        os.makedirs(self.bin_path, exist_ok=True)
        os.makedirs(self.js_path, exist_ok=True)
        
        # Platform detection
        self.platform = platform.system().lower()
        self.arch = self._detect_architecture()
        
    def _detect_architecture(self) -> str:
        """Detect system architecture for Node.js downloads."""
        machine = platform.machine().lower()
        if machine in ['x86_64', 'amd64']:
            return 'x64'
        elif machine in ['aarch64', 'arm64']:
            return 'arm64'
        elif machine.startswith('arm'):
            return 'armv7l'
        else:
            return 'x64'  # Default fallback
    
    def _check_node_installed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if Node.js is installed and get version.
        
        Returns:
            tuple: (is_installed, version)
        """
        try:
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip().lstrip('v')
                return True, version
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return False, None
    
    def _check_npm_installed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if npm is installed and get version.
        
        Returns:
            tuple: (is_installed, version)
        """
        try:
            npm_cmd = shutil.which('npm') or shutil.which('npm.cmd')
            if not npm_cmd:
                npm_candidates = [
                    os.path.join(self.bin_path, 'npm.cmd'),
                    os.path.join(self.bin_path, 'npm'),
                    os.path.join("C:\\Program Files", "nodejs", "npm.cmd"),
                ]
                for candidate in npm_candidates:
                    if os.path.exists(candidate):
                        npm_cmd = candidate
                        break
            if not npm_cmd:
                return False, None

            result = subprocess.run([npm_cmd, '--version'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, version
        except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return False, None
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two semantic versions.
        
        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
        """
        def parse_version(v):
            return tuple(map(int, v.split('.')))
        
        try:
            v1_parts = parse_version(version1)
            v2_parts = parse_version(version2)
            
            if v1_parts < v2_parts:
                return -1
            elif v1_parts > v2_parts:
                return 1
            else:
                return 0
        except ValueError:
            return 0
    
    def _get_node_download_url(self, version: str) -> str:
        """Get Node.js download URL for the current platform."""
        if self.platform == "windows":
            filename = f"node-v{version}-win-{self.arch}.zip"
        elif self.platform == "darwin":
            filename = f"node-v{version}-darwin-{self.arch}.tar.gz"
        else:  # linux
            filename = f"node-v{version}-linux-{self.arch}.tar.xz"
        
        return f"{NODE_DOWNLOAD_BASE_URL}/v{version}/{filename}"
    
    def _download_file(self, url: str, dest_path: str) -> bool:
        """Download file from URL to destination path."""
        try:
            logger.info(f"Downloading {url}...")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded to {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return False
    
    def _extract_archive(self, archive_path: str, extract_dir: str) -> bool:
        """Extract archive to specified directory."""
        try:
            logger.info(f"Extracting {archive_path} to {extract_dir}...")
            
            if archive_path.endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif archive_path.endswith(('.tar.gz', '.tar.xz')):
                mode = 'r:gz' if archive_path.endswith('.tar.gz') else 'r:xz'
                with tarfile.open(archive_path, mode) as tar_ref:
                    tar_ref.extractall(extract_dir)
            else:
                logger.error(f"Unsupported archive format: {archive_path}")
                return False
            
            logger.info("Extraction completed")
            return True
        except Exception as e:
            logger.error(f"Failed to extract {archive_path}: {e}")
            return False
    
    def install_nodejs(self, version: str = None) -> bool:
        """
        Install Node.js if not present or version is insufficient.
        
        Args:
            version: Specific version to install (defaults to recommended)
            
        Returns:
            bool: True if installation successful or not needed
        """
        version = version or self.node_version
        
        # Check if Node.js is already installed with sufficient version
        node_installed, current_version = self._check_node_installed()
        
        if node_installed and not self.force:
            if self._compare_versions(current_version, MIN_NODE_VERSION) >= 0:
                logger.info(f"Node.js {current_version} already installed and sufficient")
                return True
            else:
                logger.warning(f"Node.js {current_version} is below minimum version {MIN_NODE_VERSION}")
        
        # Try system package manager first
        if self._try_system_node_install():
            node_installed, current_version = self._check_node_installed()
            if node_installed and self._compare_versions(current_version, MIN_NODE_VERSION) >= 0:
                logger.info(f"Node.js {current_version} installed via system package manager")
                return True
        
        # Manual installation
        logger.info(f"Installing Node.js {version} manually...")
        
        # Download Node.js
        download_url = self._get_node_download_url(version)
        archive_name = os.path.basename(download_url)
        archive_path = os.path.join(self.tmp_path, archive_name)
        
        if not self._download_file(download_url, archive_path):
            return False
        
        # Extract and install
        extract_dir = os.path.join(self.tmp_path, f"node-v{version}")
        if not self._extract_archive(archive_path, extract_dir):
            return False
        
        # Find extracted directory
        extracted_dirs = [d for d in os.listdir(extract_dir) if d.startswith('node-')]
        if not extracted_dirs:
            logger.error("Could not find extracted Node.js directory")
            return False
        
        node_dir = os.path.join(extract_dir, extracted_dirs[0])
        
        # Copy binaries to bin directory
        if self.platform == "windows":
            src_files = ['node.exe', 'npm.cmd', 'npx.cmd']
        else:
            src_files = ['bin/node', 'bin/npm', 'bin/npx']
        
        for src_file in src_files:
            src_path = os.path.join(node_dir, src_file)
            if os.path.exists(src_path):
                dest_name = os.path.basename(src_file)
                dest_path = os.path.join(self.bin_path, dest_name)
                shutil.copy2(src_path, dest_path)
                if self.platform != "windows":
                    os.chmod(dest_path, 0o755)

        # Refresh PATH for this process
        for candidate in (self.bin_path, os.path.join("C:\\Program Files", "nodejs")):
            if candidate and os.path.exists(candidate) and candidate not in os.environ.get("PATH", ""):
                os.environ["PATH"] += os.pathsep + candidate
        
        # Copy lib directory for npm
        if self.platform != "windows":
            lib_src = os.path.join(node_dir, 'lib')
            lib_dest = os.path.join(self.bin_path, '..', 'lib')
            if os.path.exists(lib_src) and not os.path.exists(lib_dest):
                shutil.copytree(lib_src, lib_dest)
        
        # Cleanup
        try:
            os.remove(archive_path)
            shutil.rmtree(extract_dir)
        except Exception:
            pass
        
        # Verify installation
        node_installed, installed_version = self._check_node_installed()
        if node_installed:
            logger.info(f"Node.js {installed_version} installed successfully")
            return True
        else:
            logger.error("Node.js installation verification failed")
            return False
    
    def _try_system_node_install(self) -> bool:
        """Try to install Node.js using system package manager."""
        try:
            if self.platform == "linux":
                # Try different package managers
                package_managers = [
                    ['apt-get', 'update', '&&', 'apt-get', 'install', '-y', 'nodejs', 'npm'],
                    ['yum', 'install', '-y', 'nodejs', 'npm'],
                    ['dnf', 'install', '-y', 'nodejs', 'npm'],
                    ['pacman', '-S', '--noconfirm', 'nodejs', 'npm']
                ]
                
                for cmd in package_managers:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                        if result.returncode == 0:
                            return True
                    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                        continue
                        
            elif self.platform == "darwin":
                # Try Homebrew
                try:
                    subprocess.run(['brew', 'install', 'node'], check=True, timeout=300)
                    return True
                except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                    pass
                    
        except Exception:
            pass
        
        return False
    
    def create_js_wrapper_files(self) -> bool:
        """Create JavaScript wrapper files for Synapse SDK integration."""
        logger.info("Creating JavaScript wrapper files...")
        
        try:
            for filename, content in JS_WRAPPER_FILES.items():
                file_path = os.path.join(self.js_path, filename)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.debug(f"Created {file_path}")
            
            logger.info("JavaScript wrapper files created successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create JavaScript wrapper files: {e}")
            return False
    
    def install_npm_dependencies(self) -> bool:
        """Install required NPM dependencies."""
        logger.info("Installing NPM dependencies...")
        
        # Check if npm is available
        npm_installed, npm_version = self._check_npm_installed()
        if not npm_installed:
            logger.warning("npm is not available. Attempting to install Node.js/npm...")
            if not self.install_nodejs():
                logger.error("npm is not available and Node.js install failed.")
                return False
            npm_installed, npm_version = self._check_npm_installed()
            if not npm_installed:
                logger.error("npm is still not available after Node.js install.")
                return False
        
        try:
            # Change to js directory
            original_cwd = os.getcwd()
            os.chdir(self.js_path)
            
            # Install dependencies
            npm_cmd = shutil.which('npm') or shutil.which('npm.cmd')
            if not npm_cmd:
                candidate = os.path.join(self.bin_path, 'npm.cmd')
                if os.path.exists(candidate):
                    npm_cmd = candidate
            if not npm_cmd:
                logger.error("npm command not found after install.")
                return False
            cmd = [npm_cmd, 'install']
            if self.verbose:
                cmd.append('--verbose')
            
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                logger.info("NPM dependencies installed successfully")
                return True
            else:
                logger.error(f"npm install failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to install NPM dependencies: {e}")
            return False
        finally:
            os.chdir(original_cwd)
    
    def verify_synapse_installation(self) -> bool:
        """Verify that Synapse SDK is properly installed and functioning."""
        logger.info("Verifying Synapse SDK installation...")
        
        try:
            # Test the JavaScript wrapper
            test_script = os.path.join(self.js_path, 'synapse_wrapper.js')
            if not os.path.exists(test_script):
                logger.error("Synapse wrapper script not found")
                return False
            
            # Test basic module loading
            test_command = {
                "method": "test",
                "params": {}
            }
            
            result = subprocess.run(
                ['node', test_script],
                input=json.dumps(test_command),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("Synapse SDK installation verified successfully")
                return True
            else:
                logger.error(f"Synapse SDK verification failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to verify Synapse SDK installation: {e}")
            return False
    
    def install_synapse_sdk_dependencies(self) -> bool:
        """
        Install all required dependencies for Synapse SDK functionality.
        
        Returns:
            bool: True if installation successful, False otherwise
        """
        if not _ensure_requests():
            logger.error("requests is required to download dependencies")
            return False
        logger.info("Installing Synapse SDK dependencies...")
        
        # Check and install Node.js
        if not self.skip_node_check:
            if not self.install_nodejs():
                logger.error("Failed to install Node.js")
                return False
        
        # Create JavaScript wrapper files
        if not self.create_js_wrapper_files():
            logger.error("Failed to create JavaScript wrapper files")
            return False
        
        # Install NPM dependencies
        if not self.install_npm_dependencies():
            logger.error("Failed to install NPM dependencies")
            return False
        
        # Verify installation
        if not self.verify_synapse_installation():
            logger.error("Synapse SDK installation verification failed")
            return False
        
        logger.info("Synapse SDK dependencies installed successfully")
        return True
    
    def config_synapse_sdk(self, **kwargs) -> bool:
        """
        Configure Synapse SDK with provided settings.
        
        Returns:
            bool: True if configuration successful
        """
        logger.info("Configuring Synapse SDK...")
        
        # Configuration will be handled by the main synapse_storage module
        # This method is here for consistency with other install modules
        
        config = {
            "network": kwargs.get("network", "calibration"),
            "js_path": self.js_path,
            "wrapper_script": os.path.join(self.js_path, "synapse_wrapper.js")
        }
        
        # Store configuration in resources for other modules to use
        if "synapse_config" not in self.resources:
            self.resources["synapse_config"] = config
        
        logger.info("Synapse SDK configuration completed")
        return True
    
    def uninstall_synapse_sdk(self) -> bool:
        """
        Uninstall Synapse SDK components.
        
        Returns:
            bool: True if uninstallation successful
        """
        logger.info("Uninstalling Synapse SDK...")
        
        try:
            # Remove JavaScript files
            if os.path.exists(self.js_path):
                shutil.rmtree(self.js_path)
                logger.info("Removed JavaScript wrapper files")
            
            # Note: We don't remove Node.js as it might be used by other applications
            
            logger.info("Synapse SDK uninstalled successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall Synapse SDK: {e}")
            return False


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Install Synapse SDK for ipfs_kit_py")
    parser.add_argument("--force", action="store_true", help="Force reinstallation")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--skip-node-check", action="store_true", help="Skip Node.js version checking")
    parser.add_argument("--node-version", default=RECOMMENDED_NODE_VERSION, help="Node.js version to install")
    parser.add_argument("--synapse-version", default=DEFAULT_SYNAPSE_VERSION, help="Synapse SDK version to install")
    args = parser.parse_args()
    
    # Create installer instance
    metadata = {
        "force": args.force,
        "verbose": args.verbose,
        "skip_node_check": args.skip_node_check,
        "node_version": args.node_version,
        "synapse_version": args.synapse_version
    }
    
    installer = install_synapse_sdk(metadata=metadata)
    
    # Print welcome message
    logger.info("IPFS Kit - Synapse SDK Dependency Installer")
    logger.info("==========================================")
    
    # Install dependencies
    success = installer.install_synapse_sdk_dependencies()
    
    if success:
        logger.info("✅ Synapse SDK installation completed successfully!")
        logger.info("You can now use Synapse SDK storage backend with IPFS Kit")
        return 0
    else:
        logger.error("❌ Synapse SDK installation failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
