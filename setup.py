import os
import shutil
import subprocess
import sys

from setuptools import setup


def _warn_missing_lotus_packages() -> None:
    """Emit a friendly warning if Lotus system dependencies are missing."""
    if os.environ.get("IPFS_KIT_SKIP_LOTUS_CHECK", "").lower() in {"1", "true", "yes"}:
        return

    if not sys.platform.startswith("linux"):
        return

    if not shutil.which("dpkg-query"):
        return

    required_packages = [
        "hwloc",
        "libhwloc-dev",
        "mesa-opencl-icd",
        "ocl-icd-opencl-dev",
    ]

    missing_packages = []
    for package in required_packages:
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Status}", package],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return

        if "install ok installed" not in result.stdout:
            missing_packages.append(package)

    if missing_packages:
        install_hint = (
            "sudo apt-get update && sudo apt-get install -y "
            + " ".join(required_packages)
        )
        print(
            "WARNING: Lotus prerequisites missing: "
            + ", ".join(missing_packages)
            + f". Install them with: {install_hint}",
            file=sys.stderr,
        )


_warn_missing_lotus_packages()

# This file is maintained for backwards compatibility
# Most configuration is now in pyproject.toml

setup(
    name='ipfs_kit_py',
    version='0.3.0',
    description='Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration',
    author='Benjamin Barber',
    author_email='starworks5@gmail.com',
    url='https://github.com/endomorphosis/ipfs_kit_py/',
    python_requires='>=3.10',
    install_requires=[
        'requests>=2.28.0',
        'httpx>=0.24.0',
        'aiohttp>=3.8.4',
        'aiofiles>=23.1.0',
        'watchdog>=3.0.0',
        'psutil>=5.9.0',
        'pyyaml>=6.0',
        'base58>=2.1.1',
        'multiaddr>=0.0.9',  # For libp2p multiaddress support
        'python-magic>=0.4.27',  # For file type detection
        'anyio>=3.7.0',  # For async operations with backend flexibility
        'trio>=0.22.0',  # Optional backend for anyio
        'cryptography>=38.0.0',  # Required for libp2p
    ],
    extras_require={
        'libp2p': [
            'libp2p>=0.2.8',  # Core libp2p functionality
            'multiaddr>=0.0.9',  # For peer addressing
            'multiformats>=0.2.0',  # For content addressing
            'base58>=2.1.1',  # Used by CIDs and peer IDs
            'cryptography>=38.0.0',  # For key generation and encryption
            'protobuf>=3.20.1,<5.0.0',  # For protocol buffer support (compatible with libp2p 0.2.8)
            'eth-hash[pycryptodome]>=0.3.3',  # ETH integration with crypto backend
            'eth-keys>=0.4.0',  # ETH integration for key management
        ],
    },
    # All other configurations come from pyproject.toml
)
