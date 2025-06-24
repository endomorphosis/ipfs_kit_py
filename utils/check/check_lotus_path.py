#!/usr/bin/env python
import os
import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("lotus_path_check")

def check_lotus_installation():
    """Check if Lotus is installed and find its location."""

    # Check environment
    logger.info("ENVIRONMENT VARIABLES:")
    for var in ["PATH", "LOTUS_PATH", "LOTUS_BIN"]:
        if var in os.environ:
            logger.info(f"{var}={os.environ.get(var)}")
        else:
            logger.info(f"{var} not set")

    # Check if 'lotus' is in PATH
    try:
        which_result = subprocess.run(["which", "lotus"], capture_output=True, text=True)
        if which_result.returncode == 0:
            lotus_path = which_result.stdout.strip()
            logger.info(f"'lotus' found in PATH at: {lotus_path}")
        else:
            logger.info("'lotus' not found in PATH")
    except Exception as e:
        logger.error(f"Error checking lotus in PATH: {e}")

    # Check lotus version
    try:
        version_result = subprocess.run(["lotus", "--version"], capture_output=True, text=True)
        if version_result.returncode == 0:
            logger.info(f"Lotus version: {version_result.stdout}")
        else:
            logger.info(f"Failed to get Lotus version - error: {version_result.stderr}")
    except Exception as e:
        logger.error(f"Error running 'lotus --version': {e}")

    # Check common installation directories
    common_bin_dirs = [
        "/usr/local/bin",
        "/usr/bin",
        os.path.expanduser("~/.lotus/bin"),
        os.path.expanduser("~/bin"),
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/ipfs_kit_py/bin"),
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "bin")
    ]

    logger.info("\nCHECKING COMMON INSTALLATION DIRECTORIES:")
    for bin_dir in common_bin_dirs:
        lotus_bin_path = os.path.join(bin_dir, "lotus")
        if os.path.exists(lotus_bin_path):
            logger.info(f"Found lotus binary at: {lotus_bin_path}")
            try:
                # Check if it's executable
                is_executable = os.access(lotus_bin_path, os.X_OK)
                logger.info(f"  Executable: {is_executable}")

                # Try to run it
                if is_executable:
                    run_result = subprocess.run([lotus_bin_path, "--version"], capture_output=True, text=True)
                    logger.info(f"  Version check: {run_result.stdout if run_result.returncode == 0 else 'Failed'}")
            except Exception as e:
                logger.error(f"  Error checking binary: {e}")
        else:
            logger.info(f"No lotus binary at: {bin_dir}")

    # Look for lotus in ipfs_kit_py package
    try:
        import ipfs_kit_py
        pkg_path = os.path.dirname(ipfs_kit_py.__file__)
        bin_path = os.path.join(pkg_path, "bin")
        logger.info(f"\nIPFS_KIT_PY PACKAGE PATH: {pkg_path}")

        if os.path.exists(bin_path):
            logger.info(f"bin directory exists in package at: {bin_path}")
            lotus_bin_path = os.path.join(bin_path, "lotus")
            if os.path.exists(lotus_bin_path):
                logger.info(f"Found lotus binary in package at: {lotus_bin_path}")
                try:
                    # Check if it's executable
                    is_executable = os.access(lotus_bin_path, os.X_OK)
                    logger.info(f"  Executable: {is_executable}")
                except Exception as e:
                    logger.error(f"  Error checking binary: {e}")
            else:
                logger.info(f"No lotus binary in package bin directory")
        else:
            logger.info(f"No bin directory in package path")
    except ImportError:
        logger.error("Could not import ipfs_kit_py package")

    # Try to find using find command
    logger.info("\nSEARCHING FOR LOTUS BINARY:")
    try:
        find_result = subprocess.run(
            ["find", "/", "-name", "lotus", "-type", "f", "-executable", "-not", "-path", "*/\\.*", "-maxdepth", "5"],
            capture_output=True, text=True
        )
        if find_result.returncode == 0 and find_result.stdout.strip():
            for path in find_result.stdout.strip().split('\n'):
                logger.info(f"Found executable lotus at: {path}")
        else:
            logger.info("No lotus binary found with find command (limited search)")
    except Exception as e:
        logger.error(f"Error using find command: {e}")

    # Report conclusion
    logger.info("\nCONCLUSION:")
    if which_result.returncode == 0:
        logger.info("Lotus is available in PATH")
    else:
        logger.info("Lotus is NOT available in PATH")
        if os.path.exists(os.path.expanduser("~/.lotus")):
            logger.info("Lotus configuration directory exists, but binary not found in PATH")

        # Suggest solutions
        logger.info("\nPOTENTIAL SOLUTIONS:")
        logger.info("1. Install Lotus: https://lotus.filecoin.io/lotus/install/")
        logger.info("2. Add Lotus binary directory to PATH")
        logger.info("3. Set LOTUS_BIN environment variable to point to Lotus binary")

if __name__ == "__main__":
    check_lotus_installation()
