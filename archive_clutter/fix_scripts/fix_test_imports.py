#!/usr/bin/env python3
"""
Fix import issues in test modules.

This script is imported by conftest.py to fix common import issues
in the test suite. It patches builtins.__import__ to handle missing
modules gracefully and creates mock objects as needed.
"""

import os
import sys
import types
import builtins
import logging
from pathlib import Path
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_test_imports")

# Store the original import
original_import = builtins.__import__
