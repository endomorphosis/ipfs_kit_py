"""Compatibility shim for tests.

Some tests import this module directly (without the ipfs_kit_py package prefix).
Re-export the canonical implementation.
"""

from ipfs_kit_py.dashboard.modernized_comprehensive_dashboard import *  # noqa: F401,F403
