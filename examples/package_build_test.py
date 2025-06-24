#!/usr/bin/env python3
"""
Test script for building the package.

This script tests the package build process without actually publishing to PyPI.
"""

import os
import sys
import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, cwd=None, env=None):
    """Run a command and return output."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(f"Command failed with code {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return False
    return True


def test_build(repo_dir, venv_dir=None, clean=False):
    """
    Test building the package.

    Args:
        repo_dir: Path to the repository
        venv_dir: Path to create a virtual environment (if None, use a temp dir)
        clean: Whether to clean build artifacts first
    """
    # Convert to Path objects
    repo_dir = Path(repo_dir).resolve()

    # Create temporary venv directory if not provided
    if venv_dir is None:
        venv_dir = tempfile.mkdtemp(prefix="ipfs_kit_test_venv_")
        print(f"Created temporary venv at: {venv_dir}")
    else:
        venv_dir = Path(venv_dir).resolve()
        os.makedirs(venv_dir, exist_ok=True)

    # Clean build artifacts if requested
    if clean:
        print("Cleaning build artifacts...")
        for path in ["build", "dist", "*.egg-info"]:
            for item in repo_dir.glob(path):
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    # Get Python executable
    python = sys.executable

    # Create virtual environment
    print(f"Creating virtual environment at {venv_dir}...")
    if not run_command([python, "-m", "venv", str(venv_dir)]):
        print("Failed to create virtual environment")
        return False

    # Determine path to Python in the virtual environment
    if os.name == "nt":  # Windows
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        venv_pip = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:  # Unix
        venv_python = os.path.join(venv_dir, "bin", "python")
        venv_pip = os.path.join(venv_dir, "bin", "pip")

    # Upgrade pip
    print("Upgrading pip...")
    if not run_command([venv_python, "-m", "pip", "install", "--upgrade", "pip"]):
        print("Failed to upgrade pip")
        return False

    # Install build tools
    print("Installing build tools...")
    if not run_command([venv_pip, "install", "build", "wheel", "twine"]):
        print("Failed to install build tools")
        return False

    # Build the package
    print("Building the package...")
    if not run_command([venv_python, "-m", "build"], cwd=repo_dir):
        print("Failed to build the package")
        return False

    # Check built distributions with twine
    print("Checking build...")
    if not run_command([venv_python, "-m", "twine", "check", "dist/*"], cwd=repo_dir):
        print("Twine check failed")
        return False

    # Find the built wheel or sdist
    wheel = list(repo_dir.glob("dist/*.whl"))
    sdist = list(repo_dir.glob("dist/*.tar.gz"))

    if wheel:
        package_path = wheel[0]
    elif sdist:
        package_path = sdist[0]
    else:
        print("No built packages found")
        return False

    print(f"Testing installation of {package_path}...")

    # Create a new temporary directory for testing installation
    test_dir = tempfile.mkdtemp(prefix="ipfs_kit_test_install_")
    print(f"Created temporary test directory at: {test_dir}")

    try:
        # Create a new virtual environment for testing installation
        test_venv_dir = os.path.join(test_dir, "venv")
        if not run_command([python, "-m", "venv", test_venv_dir]):
            print("Failed to create test virtual environment")
            return False

        # Determine path to Python in the test virtual environment
        if os.name == "nt":  # Windows
            test_python = os.path.join(test_venv_dir, "Scripts", "python.exe")
            test_pip = os.path.join(test_venv_dir, "Scripts", "pip.exe")
        else:  # Unix
            test_python = os.path.join(test_venv_dir, "bin", "python")
            test_pip = os.path.join(test_venv_dir, "bin", "pip.exe")

        # Upgrade pip in test venv
        if not run_command([test_python, "-m", "pip", "install", "--upgrade", "pip"]):
            print("Failed to upgrade pip in test environment")
            return False

        # Install the built package
        if not run_command([test_pip, "install", str(package_path)]):
            print("Failed to install the built package")
            return False

        # Test importing the package
        print("Testing import...")
        test_script = os.path.join(test_dir, "test_import.py")
        with open(test_script, "w") as f:
            f.write("""
try:
    import ipfs_kit_py
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    print(f"Successfully imported ipfs_kit_py version {ipfs_kit_py.__version__}")
    print("Import test passed!")
except Exception as e:
    print(f"Import test failed: {e}")
    exit(1)
""")

        if not run_command([test_python, test_script]):
            print("Import test failed")
            return False

        print("All tests passed!")
        return True

    finally:
        # Clean up the test directory
        try:
            shutil.rmtree(test_dir)
        except Exception as e:
            print(f"Warning: Failed to clean up test directory: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test package build process")
    parser.add_argument(
        "--repo-dir",
        default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        help="Path to the repository (default: parent of script directory)"
    )
    parser.add_argument(
        "--venv-dir",
        help="Path to create a virtual environment (default: temp dir)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts before building"
    )
    args = parser.parse_args()

    success = test_build(args.repo_dir, args.venv_dir, args.clean)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
