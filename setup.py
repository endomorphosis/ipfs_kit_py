"""Compatibility entry point for legacy setuptools invocations.

Project metadata is declared once in :file:`pyproject.toml`.  In particular,
installing or querying metadata must not inspect the host operating system,
download binaries, or otherwise mutate user state.

PCPR-051: this file must not declare independent install_requires, must not
discover sibling ipfs_accelerate_py / ipfs_datasets_py / external trees, and
must not pin mutable Git branches. Package discovery and release requires
live in pyproject.toml.
"""

from setuptools import setup

PACKAGE_METADATA_SOURCE = "pyproject.toml"
PYTHON_REQUIRES = ">=3.12"


if __name__ == "__main__":
    setup()
