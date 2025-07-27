"""
IPFS Kit - Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration.

This package provides comprehensive IPFS functionality including:

🌐 **IPFS Operations**: Core IPFS daemon, cluster management, and content operations
🔗 **Filecoin Integration**: Lotus daemon and miner for Filecoin network interaction  
📦 **High-Performance Retrieval**: Lassie client for fast IPFS content retrieval
☁️ **Web3 Storage**: Storacha/Web3.Storage integration for decentralized storage
🤖 **AI/ML Integration**: Machine learning pipeline support with transformers
📡 **MCP Server**: Model Context Protocol server for AI assistant integration

## Just-in-Time (JIT) Import System

This package uses an integrated JIT import system for optimal performance:
- **Fast Startup**: Heavy dependencies loaded only when needed
- **Smart Caching**: Module imports cached for subsequent use
- **Feature Detection**: Graceful fallbacks for missing dependencies
- **Shared State**: Consistent import behavior across CLI, daemon, and MCP server

```python
# Core JIT system is automatically available
from ipfs_kit_py.core import jit_manager

# Check feature availability (fast)
if jit_manager.check_feature('enhanced_features'):
    # Modules loaded on-demand
    enhanced_index = jit_manager.get_module('enhanced_pin_index')

# Use decorators for automatic feature handling
from ipfs_kit_py.core import require_feature, optional_feature

@require_feature('daemon')
def start_daemon():
    # Only runs if daemon components are available
    pass

@optional_feature('analytics', fallback_result={})
def get_analytics():
    # Returns {} if analytics not available
    return complex_analytics()
```

## Automatic Binary Installation

The package automatically downloads and installs required binaries when imported:

- **IPFS**: ipfs, ipfs-cluster-service, ipfs-cluster-ctl, ipfs-cluster-follow
- **Lotus**: lotus, lotus-miner  
- **Lassie**: lassie
- **Storacha**: Python and NPM dependencies

## Quick Start

```python
# Import triggers automatic binary installation and JIT system initialization
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

The package includes a production-ready MCP server with JIT optimization:

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

# Initialize core JIT system early
try:
    from .core import jit_manager, require_feature, optional_feature
    _CORE_JIT_AVAILABLE = True
    logger.debug("Core JIT system initialized successfully")
except ImportError as e:
    logger.warning(f"Core JIT system not available: {e}")
    _CORE_JIT_AVAILABLE = False
    
    # Provide fallback implementations
    class MockJITManager:
        def check_feature(self, feature_name: str) -> bool:
            return False
        
        def get_module(self, module_name: str, fallback=None):
            try:
                return __import__(module_name)
            except ImportError:
                return fallback
    
    jit_manager = MockJITManager()
    
    def require_feature(feature_name: str, error_message: str = None):
        def decorator(func):
            return func
        return decorator
    
    def optional_feature(feature_name: str, fallback_result=None):
        def decorator(func):
            return func
        return decorator

# Set up binary auto-download flag
_BINARIES_DOWNLOADED = False
_DOWNLOAD_BINARIES_AUTOMATICALLY = False  # Changed to False for JIT optimization


@optional_feature('installer_dependencies', fallback_result=None)
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
    
    Uses JIT imports to avoid loading heavy installer modules unless needed.
    
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

    # Download IPFS binaries using JIT imports
    try:
        # Use JIT import to avoid loading heavy installer unless needed
        install_ipfs_module = jit_manager.get_module('install_ipfs')
        if install_ipfs_module is None:
            logger.warning("IPFS installer module not available")
            return
        
        logger.info(f"Auto-downloading IPFS binaries for {platform.system()} {platform.machine()}")
        
        installer = install_ipfs_module.install_ipfs()
        
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

    # Download Lotus binaries using JIT imports
    try:
        install_lotus_module = jit_manager.get_module('install_lotus')
        if install_lotus_module is None:
            logger.warning("Lotus installer module not available")
        else:
            logger.info(f"Auto-downloading Lotus binaries for {platform.system()} {platform.machine()}")
            
            lotus_installer = install_lotus_module.install_lotus()
            
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

    # Download Lassie binaries using JIT imports
    try:
        install_lassie_module = jit_manager.get_module('install_lassie')
        if install_lassie_module is None:
            logger.warning("Lassie installer module not available")
        else:
            logger.info(f"Auto-downloading Lassie binaries for {platform.system()} {platform.machine()}")
            
            lassie_installer = install_lassie_module.install_lassie()
            
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

    # Install Storacha dependencies using JIT imports
    try:
        install_storacha_module = jit_manager.get_module('install_storacha')
        if install_storacha_module is None:
            logger.warning("Storacha installer module not available")
        else:
            logger.info(f"Auto-installing Storacha dependencies for {platform.system()} {platform.machine()}")
            
            storacha_installer = install_storacha_module.install_storacha()
            
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
    # Simple transformers integration using JIT imports
    class SimpleTransformers:
        """Simplified transformers integration with JIT loading."""

        def is_available(self):
            """Check if transformers is available."""
            return jit_manager.check_feature('analytics')  # analytics includes transformers-like deps

        @optional_feature('analytics', fallback_result=None)
        def from_auto_download(self, model_name, **kwargs):
            """Load a model using HuggingFace's from_pretrained."""
            # Use JIT import for transformers
            transformers_module = jit_manager.get_module('transformers')
            if transformers_module is None:
                raise ImportError("transformers package not installed. Install with: pip install transformers")
            return transformers_module.AutoModel.from_pretrained(model_name, **kwargs)

        def from_ipfs(self, cid, **kwargs):
            """Load a model from IPFS (stub implementation)."""
            if not self.is_available():
                raise ImportError("transformers package not installed. Install with: pip install transformers")
            print(f"Loading from IPFS CID: {cid}")
            raise NotImplementedError("Direct IPFS loading not implemented in this simplified version")

    # Export the simple transformers integration - made lazy
    transformers = None
    
    def get_transformers():
        """Get the transformers integration, loading it lazily if needed."""
        global transformers
        if transformers is None:
            transformers = SimpleTransformers()
        return transformers


# High-level API import using JIT
@optional_feature('high_level_api', fallback_result=(None, None))
def _import_high_level_api():
    """Import high-level API components with JIT loading."""
    high_level_api = jit_manager.get_module('high_level_api')
    if high_level_api:
        return getattr(high_level_api, 'IPFSSimpleAPI', None), getattr(high_level_api, 'PluginBase', None)
    return None, None

try:
    IPFSSimpleAPI = None
    PluginBase = None
    
    def get_high_level_api():
        """Get high-level API components, loading them lazily if needed."""
        global IPFSSimpleAPI, PluginBase
        if IPFSSimpleAPI is None:
            try:
                IPFSSimpleAPI, PluginBase = _import_high_level_api()
            except Exception:
                IPFSSimpleAPI = None
                PluginBase = None
        return IPFSSimpleAPI, PluginBase
except Exception:
    IPFSSimpleAPI = None
    PluginBase = None

# Import WAL components - made lazy
StorageWriteAheadLog = None
BackendHealthMonitor = None
OperationType = None
OperationStatus = None
BackendType = None

def get_wal_components():
    """Get WAL components, loading them lazily if needed."""
    global StorageWriteAheadLog, BackendHealthMonitor, OperationType, OperationStatus, BackendType
    if StorageWriteAheadLog is None:
        try:
            from .storage_wal import (
                StorageWriteAheadLog,
                BackendHealthMonitor,
                OperationType,
                OperationStatus,
                BackendType
            )
        except ImportError:
            # WAL system might not be available
            StorageWriteAheadLog = None
            BackendHealthMonitor = None
            OperationType = None
            OperationStatus = None
            BackendType = None
    return StorageWriteAheadLog, BackendHealthMonitor, OperationType, OperationStatus, BackendType

# WAL integration - lazy loading
_wal_integration = None
_wal_enabled_api = None
_wal_api = None

def get_wal_integration():
    """Get WAL integration with lazy loading."""
    global _wal_integration
    if _wal_integration is None:
        try:
            module = jit_manager.get_module('wal_integration')
            if module:
                _wal_integration = {
                    'WALIntegration': getattr(module, 'WALIntegration', None),
                    'with_wal': getattr(module, 'with_wal', None)
                }
            else:
                _wal_integration = {'WALIntegration': None, 'with_wal': None}
        except Exception:
            _wal_integration = {'WALIntegration': None, 'with_wal': None}
    return _wal_integration

def get_wal_enabled_api():
    """Get WAL-enabled API with lazy loading."""
    global _wal_enabled_api
    if _wal_enabled_api is None:
        try:
            module = jit_manager.get_module('wal_api_extension')
            if module:
                _wal_enabled_api = getattr(module, 'WALEnabledAPI', None)
            else:
                _wal_enabled_api = None
        except Exception:
            _wal_enabled_api = None
    return _wal_enabled_api

def get_register_wal_api():
    """Get WAL API registration with lazy loading."""
    global _wal_api
    if _wal_api is None:
        try:
            module = jit_manager.get_module('wal_api')
            if module:
                _wal_api = getattr(module, 'register_wal_api', None)
            else:
                _wal_api = None
        except Exception:
            _wal_api = None
    return _wal_api

# Legacy attributes for backward compatibility - set as module level variables that resolve lazily
WALIntegration = None
with_wal = None
WALEnabledAPI = None  
register_wal_api = None

def _initialize_wal_legacy_attrs():
    """Initialize WAL legacy attributes lazily."""
    global WALIntegration, with_wal, WALEnabledAPI, register_wal_api
    if WALIntegration is None:
        wal_integration = get_wal_integration()
        WALIntegration = wal_integration.get('WALIntegration')
        with_wal = wal_integration.get('with_wal')
        WALEnabledAPI = get_wal_enabled_api()
        register_wal_api = get_register_wal_api()

# Export installer modules using JIT imports
@optional_feature('installer_dependencies', fallback_result=(None, False))
def _import_install_ipfs():
    """Import IPFS installer with JIT loading."""
    module = jit_manager.get_module('install_ipfs')
    if module:
        return getattr(module, 'install_ipfs', None), True
    return None, False

install_ipfs, INSTALL_IPFS_AVAILABLE = _import_install_ipfs()

@optional_feature('installer_dependencies', fallback_result=(None, False))
def _import_install_lotus():
    """Import Lotus installer with JIT loading."""
    module = jit_manager.get_module('install_lotus')
    if module:
        return getattr(module, 'install_lotus', None), True
    return None, False

install_lotus, INSTALL_LOTUS_AVAILABLE = _import_install_lotus()

@optional_feature('installer_dependencies', fallback_result=(None, False))
def _import_install_lassie():
    """Import Lassie installer with JIT loading."""
    module = jit_manager.get_module('install_lassie')
    if module:
        return getattr(module, 'install_lassie', None), True
    return None, False

install_lassie, INSTALL_LASSIE_AVAILABLE = _import_install_lassie()

@optional_feature('installer_dependencies', fallback_result=(None, False))
def _import_install_storacha():
    """Import Storacha installer with JIT loading."""
    module = jit_manager.get_module('install_storacha')
    if module:
        return getattr(module, 'install_storacha', None), True
    return None, False

install_storacha, INSTALL_STORACHA_AVAILABLE = _import_install_storacha()

# Import IPFS core modules using JIT
@optional_feature('ipfs_core', fallback_result=None)
def _import_ipfs_modules():
    """Import IPFS core modules with JIT loading."""
    modules = {}
    for module_name in ['ipfs', 'ipfs_cluster_ctl', 'ipfs_cluster_follow', 'ipfs_cluster_service', 'ipfs_kit', 'ipfs_multiformats']:
        try:
            if module_name == 'ipfs':
                module = jit_manager.get_module('ipfs')
                if module:
                    modules['ipfs_py'] = getattr(module, 'ipfs_py', None)
            elif module_name == 'ipfs_multiformats':
                module = jit_manager.get_module('ipfs_multiformats')
                if module:
                    modules['ipfs_multiformats_py'] = getattr(module, 'ipfs_multiformats_py', None)
            else:
                module = jit_manager.get_module(module_name)
                if module:
                    modules[module_name] = getattr(module, module_name, None)
        except Exception as e:
            logger.debug(f"Failed to import {module_name}: {e}")
            modules[module_name] = None
    return modules

# Lazy module loading cache
_ipfs_modules_cache = None

def _get_ipfs_modules():
    """Lazy getter for IPFS modules."""
    global _ipfs_modules_cache
    if _ipfs_modules_cache is None:
        _ipfs_modules_cache = _import_ipfs_modules()
    return _ipfs_modules_cache

# Extract individual modules (backward compatibility) - these are now lazy
def get_ipfs_py():
    modules = _get_ipfs_modules()
    return modules.get('ipfs_py') if modules else None

def get_ipfs_cluster_ctl():
    modules = _get_ipfs_modules()
    return modules.get('ipfs_cluster_ctl') if modules else None

def get_ipfs_cluster_follow():
    modules = _get_ipfs_modules()
    return modules.get('ipfs_cluster_follow') if modules else None

def get_ipfs_cluster_service():
    modules = _get_ipfs_modules()
    return modules.get('ipfs_cluster_service') if modules else None

def get_ipfs_kit():
    modules = _get_ipfs_modules()
    return modules.get('ipfs_kit') if modules else None

def get_ipfs_multiformats_py():
    modules = _get_ipfs_modules()
    return modules.get('ipfs_multiformats_py') if modules else None

# Backward compatibility - set these to None initially, load on first access
ipfs_py = None
ipfs_cluster_ctl = None
ipfs_cluster_follow = None
ipfs_cluster_service = None
ipfs_kit = None
ipfs_multiformats_py = None

# Import storage kit modules using JIT
@optional_feature('storage_kits', fallback_result=(None, None, None, False, None, False))
def _import_storage_kits():
    """Import storage kit modules with JIT loading."""
    s3_kit = jit_manager.get_module('s3_kit')
    storacha_kit = jit_manager.get_module('storacha_kit')
    lotus_kit = jit_manager.get_module('lotus_kit')
    lassie_kit = jit_manager.get_module('lassie_kit')
    
    return (
        getattr(s3_kit, 's3_kit', None) if s3_kit else None,
        getattr(storacha_kit, 'storacha_kit', None) if storacha_kit else None,
        getattr(lotus_kit, 'lotus_kit', None) if lotus_kit else None,
        lotus_kit is not None,
        getattr(lassie_kit, 'lassie_kit', None) if lassie_kit else None,
        lassie_kit is not None
    )

# Lazy storage kits loading cache
_storage_kits_cache = None

def _get_storage_kits():
    """Lazy getter for storage kits."""
    global _storage_kits_cache
    if _storage_kits_cache is None:
        _storage_kits_cache = _import_storage_kits()
    return _storage_kits_cache

# Backward compatibility - set these to None initially, load on first access  
s3_kit = None
storacha_kit = None
lotus_kit = None
LOTUS_KIT_AVAILABLE = False
lassie_kit = None
LASSIE_KIT_AVAILABLE = False

# Import testing and cache modules using JIT
@optional_feature('testing_and_cache', fallback_result=(None, None, None, None))
def _import_testing_and_cache():
    """Import testing and cache modules with JIT loading."""
    test_fio = jit_manager.get_module('test_fio')
    arc_cache = jit_manager.get_module('arc_cache')
    disk_cache = jit_manager.get_module('disk_cache')
    tiered_cache_manager = jit_manager.get_module('tiered_cache_manager')
    
    return (
        getattr(test_fio, 'test_fio', None) if test_fio else None,
        getattr(arc_cache, 'ARCache', None) if arc_cache else None,
        getattr(disk_cache, 'DiskCache', None) if disk_cache else None,
        getattr(tiered_cache_manager, 'TieredCacheManager', None) if tiered_cache_manager else None
    )

# Lazy testing and cache loading cache
_testing_cache_cache = None

def _get_testing_and_cache():
    """Lazy getter for testing and cache modules."""
    global _testing_cache_cache
    if _testing_cache_cache is None:
        _testing_cache_cache = _import_testing_and_cache()
    return _testing_cache_cache

# Backward compatibility - set these to None initially, load on first access
test_fio = None
ARCache = None
DiskCache = None
TieredCacheManager = None

# Expose the High-Level API singleton for easy import using JIT
@optional_feature('high_level_api', fallback_result=None)
def _import_ipfs_singleton():
    """Import IPFS singleton with JIT loading."""
    high_level_api = jit_manager.get_module('high_level_api')
    if high_level_api:
        return getattr(high_level_api, 'ipfs', None)
    return None

# Lazy IPFS singleton - set to None initially, load on first access
ipfs = None

def get_ipfs_singleton():
    """Get the IPFS singleton, loading it lazily if needed."""
    global ipfs
    if ipfs is None:
        try:
            ipfs = _import_ipfs_singleton()
        except Exception:
            # High-level API might not be available in some environments
            ipfs = None
    return ipfs

# Error handling - lazy loading
_error_module = None

def get_error_module():
    """Get error module with lazy loading."""
    global _error_module
    if _error_module is None:
        try:
            module = jit_manager.get_module('error')
            if module:
                _error_module = {
                    'IPFSConfigurationError': getattr(module, 'IPFSConfigurationError', None),
                    'IPFSConnectionError': getattr(module, 'IPFSConnectionError', None),
                    'IPFSContentNotFoundError': getattr(module, 'IPFSContentNotFoundError', None),
                    'IPFSError': getattr(module, 'IPFSError', None),
                    'IPFSPinningError': getattr(module, 'IPFSPinningError', None),
                    'IPFSTimeoutError': getattr(module, 'IPFSTimeoutError', None),
                    'IPFSValidationError': getattr(module, 'IPFSValidationError', None),
                    'create_result_dict': getattr(module, 'create_result_dict', None),
                    'handle_error': getattr(module, 'handle_error', None),
                    'perform_with_retry': getattr(module, 'perform_with_retry', None),
                }
            else:
                _error_module = {}
        except Exception:
            _error_module = {}
    return _error_module

# Legacy error attributes for backward compatibility - set as module level variables that resolve lazily
IPFSConfigurationError = None
IPFSConnectionError = None
IPFSContentNotFoundError = None
IPFSError = None
IPFSPinningError = None
IPFSTimeoutError = None
IPFSValidationError = None
create_result_dict = None
handle_error = None
perform_with_retry = None

def _initialize_error_legacy_attrs():
    """Initialize error legacy attributes lazily."""
    global IPFSConfigurationError, IPFSConnectionError, IPFSContentNotFoundError
    global IPFSError, IPFSPinningError, IPFSTimeoutError, IPFSValidationError
    global create_result_dict, handle_error, perform_with_retry
    
    if IPFSConfigurationError is None:
        error_mod = get_error_module()
        IPFSConfigurationError = error_mod.get('IPFSConfigurationError')
        IPFSConnectionError = error_mod.get('IPFSConnectionError')
        IPFSContentNotFoundError = error_mod.get('IPFSContentNotFoundError')
        IPFSError = error_mod.get('IPFSError')
        IPFSPinningError = error_mod.get('IPFSPinningError')
        IPFSTimeoutError = error_mod.get('IPFSTimeoutError')
        IPFSValidationError = error_mod.get('IPFSValidationError')
        create_result_dict = error_mod.get('create_result_dict')
        handle_error = error_mod.get('handle_error')
        perform_with_retry = error_mod.get('perform_with_retry')

# Optional imports - these might not be available if optional dependencies are not installed
# Made lazy to avoid heavy loading on import
IPFSFileSystem = None
cli_main = None
app = None
api = None

def get_ipfs_filesystem():
    """Lazy import of IPFSFileSystem."""
    global IPFSFileSystem
    if IPFSFileSystem is None:
        try:
            from .ipfs_fsspec import IPFSFileSystem
        except ImportError:
            IPFSFileSystem = None
    return IPFSFileSystem

def get_cli_main():
    """Lazy import of CLI main function."""
    global cli_main
    if cli_main is None:
        try:
            from .cli import main as cli_main
        except ImportError:
            cli_main = None
    return cli_main

def get_api_app():
    """Lazy import of API app."""
    global app, api
    if app is None:
        try:
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
        except ImportError:
            app = None
            api = None
    return app
