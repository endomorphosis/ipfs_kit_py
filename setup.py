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
    # All other configurations (including dependencies and extras) come from pyproject.toml
)
