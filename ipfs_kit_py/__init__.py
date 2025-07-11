"""
IPFS Kit - Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration.

This package provides comprehensive IPFS functionality including:

🌐 **IPFS Operations**: Core IPFS daemon, cluster management, and content operations
🔗 **Filecoin Integration**: Lotus daemon and miner for Filecoin network interaction  
📦 **High-Performance Retrieval**: Lassie client for fast IPFS content retrieval
☁️ **Web3 Storage**: Storacha/Web3.Storage integration for decentralized storage
🤖 **AI/ML Integration**: Machine learning pipeline support with transformers
📡 **MCP Server**: Model Context Protocol server for AI assistant integration

## Automatic Binary Installation

The package automatically downloads and installs required binaries when imported:

- **IPFS**: ipfs, ipfs-cluster-service, ipfs-cluster-ctl, ipfs-cluster-follow
- **Lotus**: lotus, lotus-miner  
- **Lassie**: lassie
- **Storacha**: Python and NPM dependencies

## Quick Start

```python
# Import triggers automatic binary installation
from ipfs_kit_py import install_ipfs, install_lotus, install_lassie, install_storacha

# Check installation status
from ipfs_kit_py import (
    INSTALL_IPFS_AVAILABLE,
    INSTALL_LOTUS_AVAILABLE, 
    INSTALL_LASSIE_AVAILABLE,
    INSTALL_STORACHA_AVAILABLE
)

# Use installers directly
ipfs_installer = install_ipfs()
ipfs_installer.install_ipfs_daemon()

# Or use the MCP server for IPFS operations
# Start server: python final_mcp_server_enhanced.py --host 0.0.0.0 --port 9998
```

## MCP Server Integration

The package includes a production-ready MCP server:

```bash
python final_mcp_server_enhanced.py --host 0.0.0.0 --port 9998
```

For detailed documentation, see: https://github.com/endomorphosis/ipfs_kit_py
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
    """
    Download platform-specific binaries and install dependencies for IPFS, Lotus, Lassie, and Storacha.
    
    This function automatically:
    1. Downloads IPFS binaries (ipfs, ipfs-cluster-service, ipfs-cluster-ctl, ipfs-cluster-follow)
    2. Downloads Lotus binaries (lotus, lotus-miner) 
    3. Downloads Lassie binary (lassie)
    4. Installs Storacha Python and NPM dependencies
    
    All binaries are platform-specific and downloaded from official sources.
    Installation progress is logged and errors are handled gracefully.
    
    Returns:
        None
        
    Raises:
        Exception: If critical installation steps fail (logged as warnings)
    """
    global _BINARIES_DOWNLOADED

    if _BINARIES_DOWNLOADED:
        return

    bin_dir = os.path.join(os.path.dirname(__file__), "bin")
    os.makedirs(bin_dir, exist_ok=True)

    # Download IPFS binaries
    try:
        from .install_ipfs import install_ipfs
        logger.info(f"Auto-downloading IPFS binaries for {platform.system()} {platform.machine()}")
        
        installer = install_ipfs()
        
        # Install core IPFS binaries
        try:
            ipfs_binary = "ipfs.exe" if platform.system() == "Windows" else "ipfs"
            if not os.path.exists(os.path.join(bin_dir, ipfs_binary)):
                installer.install_ipfs_daemon()
                logger.info("Downloaded IPFS daemon successfully")
        except Exception as e:
            logger.warning(f"Failed to download IPFS daemon: {e}")

        try:
            cluster_service_binary = "ipfs-cluster-service.exe" if platform.system() == "Windows" else "ipfs-cluster-service"
            if not os.path.exists(os.path.join(bin_dir, cluster_service_binary)):
                installer.install_ipfs_cluster_service()
                logger.info("Downloaded IPFS cluster service successfully")
        except Exception as e:
            logger.warning(f"Failed to download IPFS cluster service: {e}")

        try:
            cluster_ctl_binary = "ipfs-cluster-ctl.exe" if platform.system() == "Windows" else "ipfs-cluster-ctl"
            if not os.path.exists(os.path.join(bin_dir, cluster_ctl_binary)):
                installer.install_ipfs_cluster_ctl()
                logger.info("Downloaded IPFS cluster control successfully")
        except Exception as e:
            logger.warning(f"Failed to download IPFS cluster control: {e}")

        try:
            cluster_follow_binary = "ipfs-cluster-follow.exe" if platform.system() == "Windows" else "ipfs-cluster-follow"
            if not os.path.exists(os.path.join(bin_dir, cluster_follow_binary)):
                installer.install_ipfs_cluster_follow()
                logger.info("Downloaded IPFS cluster follow successfully")
        except Exception as e:
            logger.warning(f"Failed to download IPFS cluster follow: {e}")

    except Exception as e:
        logger.error(f"Error downloading IPFS binaries: {e}")

    # Download Lotus binaries
    try:
        from .install_lotus import install_lotus
        logger.info(f"Auto-downloading Lotus binaries for {platform.system()} {platform.machine()}")
        
        lotus_installer = install_lotus()
        
        # Install Lotus binaries
        try:
            lotus_binary = "lotus.exe" if platform.system() == "Windows" else "lotus"
            if not os.path.exists(os.path.join(bin_dir, lotus_binary)):
                lotus_installer.install_lotus_daemon()
                logger.info("Downloaded Lotus daemon successfully")
        except Exception as e:
            logger.warning(f"Failed to download Lotus daemon: {e}")

        try:
            lotus_miner_binary = "lotus-miner.exe" if platform.system() == "Windows" else "lotus-miner"
            if not os.path.exists(os.path.join(bin_dir, lotus_miner_binary)):
                lotus_installer.install_lotus_miner()
                logger.info("Downloaded Lotus miner successfully")
        except Exception as e:
            logger.warning(f"Failed to download Lotus miner: {e}")

    except Exception as e:
        logger.error(f"Error downloading Lotus binaries: {e}")

    # Download Lassie binaries
    try:
        from .install_lassie import install_lassie
        logger.info(f"Auto-downloading Lassie binaries for {platform.system()} {platform.machine()}")
        
        lassie_installer = install_lassie()
        
        # Install Lassie binary
        try:
            lassie_binary = "lassie.exe" if platform.system() == "Windows" else "lassie"
            if not os.path.exists(os.path.join(bin_dir, lassie_binary)):
                lassie_installer.install_lassie_daemon()
                logger.info("Downloaded Lassie daemon successfully")
        except Exception as e:
            logger.warning(f"Failed to download Lassie daemon: {e}")

    except Exception as e:
        logger.error(f"Error downloading Lassie binaries: {e}")

    # Install Storacha dependencies
    try:
        from .install_storacha import install_storacha
        logger.info(f"Auto-installing Storacha dependencies for {platform.system()} {platform.machine()}")
        
        storacha_installer = install_storacha()
        
        # Install Storacha Python and NPM dependencies
        try:
            storacha_installer.install_storacha_dependencies()
            logger.info("Installed Storacha dependencies successfully")
        except Exception as e:
            logger.warning(f"Failed to install Storacha dependencies: {e}")

        # Install w3 CLI tool
        try:
            storacha_installer.install_w3_cli()
            logger.info("Installed w3 CLI tool successfully")
        except Exception as e:
            logger.warning(f"Failed to install w3 CLI tool: {e}")

    except Exception as e:
        logger.error(f"Error installing Storacha dependencies: {e}")

    _BINARIES_DOWNLOADED = True
    logger.info("All binary downloads completed")


# Auto-download binaries on import if enabled
if _DOWNLOAD_BINARIES_AUTOMATICALLY:
    # Initialize the binary directory
    bin_dir = os.path.join(os.path.dirname(__file__), "bin")
    os.makedirs(bin_dir, exist_ok=True)

    # Check if any binaries need to be downloaded
    ipfs_binary = "ipfs.exe" if platform.system() == "Windows" else "ipfs"
    lotus_binary = "lotus.exe" if platform.system() == "Windows" else "lotus"
    lassie_binary = "lassie.exe" if platform.system() == "Windows" else "lassie"
    storacha_marker = os.path.join(bin_dir, ".storacha_installed")
    
    if not (
        os.path.exists(os.path.join(bin_dir, ipfs_binary))
        and os.path.exists(os.path.join(bin_dir, lotus_binary))
        and os.path.exists(os.path.join(bin_dir, lassie_binary))
        and os.path.exists(storacha_marker)
    ):
        try:
            download_binaries()
        except Exception as e:
            logger.warning(f"Failed to auto-download binaries on import: {e}")
            logger.info("Binaries will be downloaded when specific functions are called")

# Use try/except for all imports to handle optional dependencies gracefully
# Import the transformers integration (DISABLED due to protobuf conflicts)
try:
    # DISABLED: from .transformers_integration import TransformersIntegration
    # The transformers integration causes protobuf conflicts with libp2p
    raise ImportError("TransformersIntegration disabled to avoid protobuf conflicts")
    
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

# Export installer modules
try:
    from .install_ipfs import install_ipfs
    INSTALL_IPFS_AVAILABLE = True
except ImportError:
    install_ipfs = None
    INSTALL_IPFS_AVAILABLE = False

try:
    from .install_lotus import install_lotus
    INSTALL_LOTUS_AVAILABLE = True
except ImportError:
    install_lotus = None
    INSTALL_LOTUS_AVAILABLE = False

try:
    from .install_lassie import install_lassie
    INSTALL_LASSIE_AVAILABLE = True
except ImportError:
    install_lassie = None
    INSTALL_LASSIE_AVAILABLE = False

try:
    from .install_storacha import install_storacha
    INSTALL_STORACHA_AVAILABLE = True
except ImportError:
    install_storacha = None
    INSTALL_STORACHA_AVAILABLE = False

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
