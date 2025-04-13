# setup-wal-cli.py

import os
from setuptools import setup, find_packages

setup(
    name="ipfs-wal-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "ipfs_kit_py",
    ],
    entry_points={
        'console_scripts': [
            'wal-cli=ipfs_kit_py.wal_cli:main',
        ],
    },
    description="Command-line interface for the IPFS Kit WAL system",
    author="IPFS Kit Team",
    author_email="info@example.com",
    url="https://example.com/ipfs-kit",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)