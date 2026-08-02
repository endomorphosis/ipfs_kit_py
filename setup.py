"""Compatibility entry point for legacy setuptools invocations.

Project metadata is declared once in :file:`pyproject.toml`.  In particular,
installing or querying metadata must not inspect the host operating system,
download binaries, or otherwise mutate user state.
"""

from setuptools import setup


if __name__ == "__main__":
    setup()
