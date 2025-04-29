"""
IPFS Kit - Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration.
"""

__version__ = "0.2.0"
__author__ = "Benjamin Barber"
__email__ = "starworks5@gmail.com"

import logging
import os
import platform
import sys

# Configure logger
logger = logging.getLogger(__name__)

# Set up binary auto-download flag
_BINARIES_DOWNLOADED = False
_DOWNLOAD_BINARIES_AUTOMATICALLY = True


def download_binaries():
    """Download platform-specific binaries for IPFS and related tools."""
    global _BINARIES_DOWNLOADED

    if _BINARIES_DOWNLOADED:
        return

    try:
        # Import the installer
        from .install_ipfs import install_ipfs

        logger.info(f"Auto-downloading IPFS binaries for {platform.system()} {platform.machine()}")

        # Create installer instance
        installer = install_ipfs()

        # Install core binaries based on platform
        try:
            if not os.path.exists(os.path.join(os.path.dirname(__file__), "bin", "ipfs")):
                installer.install_ipfs_daemon()
                logger.info("Downloaded IPFS daemon successfully")
        except Exception as e:
            logger.warning(f"Failed to download IPFS daemon: {e}")

        try:
            if not os.path.exists(
                os.path.join(os.path.dirname(__file__), "bin", "ipfs-cluster-service")
            ):
                installer.install_ipfs_cluster_service()
                logger.info("Downloaded IPFS cluster service successfully")
        except Exception as e:
            logger.warning(f"Failed to download IPFS cluster service: {e}")

        try:
            if not os.path.exists(
                os.path.join(os.path.dirname(__file__), "bin", "ipfs-cluster-ctl")
            ):
                installer.install_ipfs_cluster_ctl()
                logger.info("Downloaded IPFS cluster control successfully")
        except Exception as e:
            logger.warning(f"Failed to download IPFS cluster control: {e}")

        try:
            if not os.path.exists(
                os.path.join(os.path.dirname(__file__), "bin", "ipfs-cluster-follow")
            ):
                installer.install_ipfs_cluster_follow()
                logger.info("Downloaded IPFS cluster follow successfully")
        except Exception as e:
            logger.warning(f"Failed to download IPFS cluster follow: {e}")

        _BINARIES_DOWNLOADED = True
        logger.info("IPFS binary downloads completed")

    except Exception as e:
        logger.error(f"Error downloading IPFS binaries: {e}")


# Auto-download binaries on import if enabled
if _DOWNLOAD_BINARIES_AUTOMATICALLY:
    # Initialize the binary directory
    bin_dir = os.path.join(os.path.dirname(__file__), "bin")
    os.makedirs(bin_dir, exist_ok=True)

    # Check if any binaries need to be downloaded
    if not (
        os.path.exists(os.path.join(bin_dir, "ipfs"))
        or (platform.system() == "Windows" and os.path.exists(os.path.join(bin_dir, "ipfs.exe")))
    ):
        try:
            download_binaries()
        except Exception as e:
            logger.warning(f"Failed to auto-download binaries on import: {e}")
            logger.info("Binaries will be downloaded when specific functions are called")

# Use try/except for all imports to handle optional dependencies gracefully
# Import the transformers integration
try:
    from .transformers_integration import TransformersIntegration

    # Create alias for the integration
    transformers = TransformersIntegration()
    print(f"TransformersIntegration is instantiated successfully")
except ImportError:
    # Simple transformers integration
    try:
        import transformers as _hf_transformers
        _TRANSFORMERS_AVAILABLE = True
    except ImportError:
        _TRANSFORMERS_AVAILABLE = False

    class SimpleTransformers:
        """Simplified transformers integration."""

        def is_available(self):
            """Check if transformers is available."""
            return _TRANSFORMERS_AVAILABLE

        def from_auto_download(self, model_name, **kwargs):
            """Load a model using HuggingFace's from_pretrained."""
            if not _TRANSFORMERS_AVAILABLE:
                raise ImportError("transformers package not installed. Install with: pip install transformers")
            return _hf_transformers.AutoModel.from_pretrained(model_name, **kwargs)

        def from_ipfs(self, cid, **kwargs):
            """Load a model from IPFS (stub implementation)."""
            if not _TRANSFORMERS_AVAILABLE:
                raise ImportError("transformers package not installed. Install with: pip install transformers")
            print(f"Loading from IPFS CID: {cid}")
            raise NotImplementedError("Direct IPFS loading not implemented in this simplified version")

    # Export the simple transformers integration
    transformers = SimpleTransformers()
    print(f"SimpleTransformers is instantiated successfully")


# High-level API import
try:
    from .high_level_api import IPFSSimpleAPI, PluginBase
except ImportError:
    IPFSSimpleAPI = None
    PluginBase = None

# Import WAL components
try:
    from .storage_wal import (
        StorageWriteAheadLog,
        BackendHealthMonitor,
        OperationType,
        OperationStatus,
        BackendType
    )
except ImportError:
    StorageWriteAheadLog = None
    BackendHealthMonitor = None
    OperationType = None
    OperationStatus = None
    BackendType = None

# Import WAL integration
try:
    from .wal_integration import WALIntegration, with_wal
except ImportError:
    WALIntegration = None
    with_wal = None

# Import WAL-enabled API
try:
    from .wal_api_extension import WALEnabledAPI
except ImportError:
    WALEnabledAPI = None

# Import WAL API
try:
    from .wal_api import register_wal_api
except ImportError:
    register_wal_api = None

try:
    from .install_ipfs import install_ipfs
except ImportError:
    install_ipfs = None

try:
    from .ipfs import ipfs_py
except ImportError:
    ipfs_py = None

try:
    from .ipfs_cluster_ctl import ipfs_cluster_ctl
except ImportError:
    ipfs_cluster_ctl = None

try:
    from .ipfs_cluster_follow import ipfs_cluster_follow
except ImportError:
    ipfs_cluster_follow = None

try:
    from .ipfs_cluster_service import ipfs_cluster_service
except ImportError:
    ipfs_cluster_service = None

try:
    from .ipfs_kit import ipfs_kit
except ImportError:
    ipfs_kit = None

try:
    from .ipfs_multiformats import ipfs_multiformats_py
except ImportError:
    ipfs_multiformats_py = None

try:
    from .s3_kit import s3_kit
except ImportError:
    s3_kit = None

try:
    from .storacha_kit import storacha_kit
except ImportError:
    storacha_kit = None

try:
    from .lotus_kit import lotus_kit
    LOTUS_KIT_AVAILABLE = True
except ImportError:
    lotus_kit = None
    LOTUS_KIT_AVAILABLE = False

try:
    from .lassie_kit import lassie_kit
    LASSIE_KIT_AVAILABLE = True
except ImportError:
    lassie_kit = None
    LASSIE_KIT_AVAILABLE = False

try:
    from .test_fio import test_fio
except ImportError:
    test_fio = None

try:
    from .arc_cache import ARCache
    from .disk_cache import DiskCache
    from .tiered_cache_manager import TieredCacheManager
except ImportError:
    ARCache = None
    DiskCache = None
    TieredCacheManager = None

# Expose the High-Level API singleton for easy import
try:
    from .high_level_api import ipfs
except ImportError:
    # High-level API might not be available in some environments
    ipfs = None

from .error import (
    IPFSConfigurationError,
    IPFSConnectionError,
    IPFSContentNotFoundError,
    IPFSError,
    IPFSPinningError,
    IPFSTimeoutError,
    IPFSValidationError,
    create_result_dict,
    handle_error,
    perform_with_retry,
)

# Optional imports - these might not be available if optional dependencies are not installed
# Disabled due to syntax errors
try:
    from .ipfs_fsspec import IPFSFileSystem
except ImportError:
    IPFSFileSystem = None

# Try to import the CLI entry point
try:
    from .cli import main as cli_main
except ImportError:
    cli_main = None

# Import our router modules
from .api import app
from . import api

# Register Storage Backends router if available
if hasattr(api, 'STORAGE_BACKENDS_AVAILABLE') and api.STORAGE_BACKENDS_AVAILABLE:
    from .storage_backends_api import storage_router
    app.include_router(storage_router)

# Register Observability router if available
if hasattr(api, 'OBSERVABILITY_AVAILABLE') and api.OBSERVABILITY_AVAILABLE:
    from .observability_api import observability_router
    app.include_router(observability_router)
