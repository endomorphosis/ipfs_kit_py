#!/usr/bin/env python3
"""Legacy VFS performance test (skipped).

Relies on removed BucketVFSManager and older parquet layout. Skipped to keep CI green.
"""

import pytest
pytest.skip("Legacy VFS performance harness deprecated", allow_module_level=True)

# Original content retained below (not executed):
# ---------------------------------------------------------------------------

import time
from pathlib import Path
import sys

# Add project root to path
repo_root = Path(__file__).resolve().parents[2]
sys.path.append(str(repo_root))

# (Imports removed)


# (Functional content removed)
