#!/usr/bin/env python3
"""
Force LibP2P installation and verification

This script ensures that LibP2P dependencies required for MCP server integration
are properly installed and functioning.
"""

import os
import sys
import logging
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("force_libp2p")

def install_libp2p_dependencies():
    """Install all LibP2P dependencies necessary for MCP server integration."""
    logger.info("Installing LibP2P dependencies...")

    # Set environment variable to enable auto-installation
    os.environ["IPFS_KIT_AUTO_INSTALL_DEPS"] = "1"

    try:
        # Import our dependency manager and force installation
        from install_libp2p import install_dependencies_auto

        result = install_dependencies_auto(
            force=True,
            verbose=True,
            mcp_integration=True
        )

        if result:
            logger.info("LibP2P dependencies installed successfully")
            return True
        else:
            logger.error("Failed to install LibP2P dependencies automatically")
            return False
    except ImportError:
        logger.error("Could not import install_libp2p module")
        return False
    except Exception as e:
        logger.error(f"Error installing LibP2P dependencies: {e}")
        return False

def install_with_pip():
    """Install dependencies directly with pip as a fallback."""
    logger.info("Installing LibP2P dependencies with pip directly...")

    dependencies = [
        "libp2p>=0.1.5",
        "multiaddr>=0.0.9",
        "base58",
        "cryptography",
        "fastapi>=0.100.0",
        "uvicorn",
        "anyio>=3.7.0",
        "pydantic>=2.0.0",
        "google-protobuf",
        "eth-hash",
        "eth-keys"
    ]

    try:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + dependencies
        logger.info(f"Running: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        logger.info("Package installation completed")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"pip installation failed: {e}")
        return False

def verify_installations():
    """Verify that all necessary dependencies are installed and working."""
    logger.info("Verifying installations...")
    missing = []

    # Check required packages
    packages = [
        "libp2p", "multiaddr", "base58", "cryptography",
        "fastapi", "uvicorn", "anyio", "pydantic"
    ]

    for package in packages:
        try:
            module = __import__(package)
            logger.info(f"✓ {package} is installed")
        except ImportError:
            missing.append(package)
            logger.error(f"✗ {package} is NOT installed")

    # Verify libp2p functionality specifically
    try:
        import libp2p
        from libp2p.crypto.keys import KeyPair
        logger.info("✓ libp2p.crypto.keys imported successfully")
    except (ImportError, AttributeError) as e:
        logger.error(f"✗ libp2p.crypto.keys verification failed: {e}")
        missing.append("libp2p.crypto.keys")

    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        return False
    else:
        logger.info("All dependencies are successfully installed")
        return True

def main():
    """Main function."""
    logger.info("Starting forced LibP2P dependency installation")

    # Try our automated installer first
    success = install_libp2p_dependencies()

    # If that fails, try direct pip installation
    if not success:
        logger.info("Automated installation failed, trying direct pip installation")
        success = install_with_pip()

    # Verify the installations
    if success:
        verified = verify_installations()
        if verified:
            logger.info("LibP2P dependencies successfully installed and verified")
            return 0
        else:
            logger.error("Some dependencies failed verification")
            return 1
    else:
        logger.error("Failed to install dependencies")
        return 1

if __name__ == "__main__":
    sys.exit(main())
