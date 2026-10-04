#!/usr/bin/env python3
"""
IPFS-Kit Command Line Interface

Simple wrapper that launches the optimized CLI from the package.
"""

import sys
import anyio
from pathlib import Path

# Add the package to the path if needed
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the main CLI
from ipfs_kit_py.cli import main

if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)
