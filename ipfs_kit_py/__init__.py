"""
IPFS Kit - Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration.
"""

__version__ = "0.1.0"
__author__ = "Benjamin Barber"
__email__ = "starworks5@gmail.com"

from .install_ipfs import install_ipfs
from .test_fio  import test_fio
from .ipfs_kit import ipfs_kit
from .ipfs_cluster_ctl import ipfs_cluster_ctl
from .ipfs_cluster_follow import ipfs_cluster_follow
from .ipfs_cluster_service import ipfs_cluster_service
from .storacha_kit import storacha_kit
from .s3_kit import s3_kit
from .ipfs import ipfs_py
from .ipfs_multiformats import ipfs_multiformats_py
from .tiered_cache import TieredCacheManager, ARCache, DiskCache
from .high_level_api import IPFSSimpleAPI, PluginBase

# Expose the High-Level API singleton for easy import
try:
    from .high_level_api import ipfs
except ImportError:
    # High-level API might not be available in some environments
    ipfs = None

from .error import (
    IPFSError, IPFSConnectionError, IPFSTimeoutError, IPFSContentNotFoundError,
    IPFSValidationError, IPFSConfigurationError, IPFSPinningError,
    create_result_dict, handle_error, perform_with_retry
)

# Optional imports - these might not be available if optional dependencies are not installed
try:
    from .ipfs_fsspec import IPFSFileSystem
except ImportError:
    IPFSFileSystem = None

# Try to import the CLI entry point
try:
    from .cli import main as cli_main
except ImportError:
    cli_main = None