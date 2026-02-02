#!/usr/bin/env python3
"""Compatibility shim for UnifiedComprehensiveDashboard.

Allows tests and legacy scripts to import `UnifiedComprehensiveDashboard`
from the repository root.
"""

from ipfs_kit_py.dashboard.unified_comprehensive_dashboard import UnifiedComprehensiveDashboard

__all__ = ["UnifiedComprehensiveDashboard"]
