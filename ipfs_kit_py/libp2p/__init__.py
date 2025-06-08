"""
libp2p package for ipfs_kit_py.

This package provides enhanced libp2p functionality for the ipfs_kit_py project,
including advanced peer discovery, content routing, and direct peer-to-peer
communication without requiring the full IPFS daemon.

Components:
- enhanced_dht_discovery: Advanced DHT-based peer discovery with k-bucket optimization
- recursive_routing: Recursive and delegated content routing mechanisms
- gossipsub_protocol: Advanced publish-subscribe messaging with GossipSub protocol
- content_routing: Intelligent content routing based on peer statistics
- p2p_integration: Integration with IPFSKit and IPFSFileSystem
- ipfs_kit_integration: Extend IPFSKit with libp2p functionality
- high_level_api_integration: Extend IPFSSimpleAPI with peer discovery

The package uses lazy loading and dependency injection to prevent circular imports
and provides graceful degradation when dependencies are not available.
"""

import os
import sys
import importlib
import logging
import subprocess
from importlib.util import find_spec
from typing import Any, Callable, Dict, List, Optional, Union, Type, Tuple

# Configure logger with proper name
logger = logging.getLogger(__name__)

# Apply protobuf compatibility patches early and more aggressively
try:
    # Check if protobuf is already loaded
    if 'google.protobuf.message_factory' in sys.modules:
        # Check if MessageFactory has GetPrototype
        from google.protobuf.message_factory import MessageFactory
        has_prototype = hasattr(MessageFactory, 'GetPrototype')
        if not has_prototype:
            # Import and apply monkey patch more aggressively
            from ipfs_kit_py.tools.protobuf_compat import monkey_patch_message_factory, PROTOBUF_VERSION
            
            # Force the patch to be applied
            success = monkey_patch_message_factory()
            if success:
                logger.info(f"Applied MessageFactory compatibility patch for protobuf {PROTOBUF_VERSION}")
                
                # Double-check the patch worked
                if hasattr(MessageFactory, 'GetPrototype'):
                    logger.info("Verified MessageFactory.GetPrototype patch is working")
                else:
                    logger.warning("MessageFactory.GetPrototype patch did not apply correctly")
                    
                    # Try a direct approach
                    try:
                        # Define a simple compatibility function for GetPrototype
                        def get_prototype(self, descriptor):
                            """Direct compatibility implementation of GetPrototype."""
                            from google.protobuf.message_factory import message_factory_for_descriptor_pool
                            from google.protobuf.descriptor_pool import DescriptorPool
                            pool = getattr(self, '_descriptor_pool', None) or DescriptorPool()
                            factory = message_factory_for_descriptor_pool(pool)
                            return factory.GetPrototype(descriptor)
                            
                        # Add the method directly
                        MessageFactory.GetPrototype = get_prototype
                        logger.info("Applied direct MessageFactory.GetPrototype patch")
                    except Exception as e:
                        logger.error(f"Failed to apply direct GetPrototype patch: {e}")
    else:
        # Try to apply the patch before MessageFactory is imported elsewhere
        from ipfs_kit_py.tools.protobuf_compat import monkey_patch_message_factory, PROTOBUF_VERSION
        success = monkey_patch_message_factory()
        if success:
            logger.info(f"Preemptively applied MessageFactory compatibility patch for protobuf {PROTOBUF_VERSION}")
except ImportError as e:
    # This is fine if the tools module is not available
    logger.debug(f"Couldn't apply protobuf compatibility patch: {e}")
except Exception as e:
    logger.warning(f"Error applying protobuf compatibility patch: {e}")

# Import hooks to automatically apply protocol extensions
try:
    import ipfs_kit_py.libp2p.hooks
except ImportError:
    # This is fine if hooks aren't yet available
    pass

# Define required dependencies
REQUIRED_DEPENDENCIES = [
    "libp2p",
    "multiaddr",
    "base58",
    "cryptography"
]

# Optional dependencies
OPTIONAL_DEPENDENCIES = [
    "google-protobuf",
    "eth-hash",
    "eth-keys"
]

# Check if we're installed with the libp2p extra
try:
    # Try to import pkg_resources which can check for extras
    import pkg_resources
    pkg = pkg_resources.working_set.by_key.get('ipfs_kit_py')
    if pkg:
        # Check if the libp2p extra is installed
        extras = pkg.extras if hasattr(pkg, 'extras') else []
        HAS_LIBP2P_EXTRA = 'libp2p' in extras
    else:
        HAS_LIBP2P_EXTRA = False
except (ImportError, AttributeError):
    # If pkg_resources isn't available or there's any error, assume no extras
    HAS_LIBP2P_EXTRA = False

logger.debug(f"libp2p extra detected: {HAS_LIBP2P_EXTRA}")

# Module-level state
HAS_LIBP2P = False  # Flag indicating if libp2p is available
DEPENDENCIES_CHECKED = False  # Flag indicating if we've performed the check
AUTO_INSTALL = os.environ.get("IPFS_KIT_AUTO_INSTALL_DEPS", "0") == "1"
_attempted_install = False  # Flag to indicate if we've tried manual installation

def check_dependencies() -> bool:
    """
    Check if all required libp2p dependencies are installed.
    
    This function checks if all the required dependencies for libp2p functionality
    are installed and available in the current Python environment. The function
    can be called multiple times, but will only perform the actual check once
    unless DEPENDENCIES_CHECKED is reset.
    
    Returns:
        bool: True if all dependencies are available, False otherwise
    """
    global HAS_LIBP2P, DEPENDENCIES_CHECKED

    # Skip rechecking if already performed
    if DEPENDENCIES_CHECKED:
        logger.debug("Dependencies already checked, returning cached result")
        return HAS_LIBP2P

    # If we've detected that the libp2p extra is installed, we can assume all 
    # required dependencies are available, but still verify to be sure
    if HAS_LIBP2P_EXTRA:
        logger.debug("libp2p extra detected, dependencies should be available")
    
    all_available = True
    missing_deps = []

    # Check required dependencies
    for dep in REQUIRED_DEPENDENCIES:
        try:
            # Use importlib to check for all dependencies consistently
            importlib.import_module(dep)
            logger.debug(f"Dependency {dep} is available")
        except (ImportError, ModuleNotFoundError):
            all_available = False
            missing_deps.append(dep)
            logger.debug(f"Dependency {dep} is missing")

    # Set global flag
    HAS_LIBP2P = all_available
    DEPENDENCIES_CHECKED = True

    if not all_available:
        # If libp2p extra is installed but dependencies are missing, this is unexpected
        if HAS_LIBP2P_EXTRA:
            logger.warning(f"Missing libp2p dependencies despite libp2p extra being installed: {', '.join(missing_deps)}")
            # This might indicate an installation issue or version mismatch
            logger.warning("Try reinstalling the package with `pip install -e .[libp2p]` or check for version conflicts")
        else:
            logger.warning(f"Missing libp2p dependencies: {', '.join(missing_deps)}")
            logger.warning("Install with `pip install ipfs_kit_py[libp2p]` to enable libp2p functionality")

        # Attempt auto-installation if enabled
        if AUTO_INSTALL:
            logger.info("Auto-install enabled, attempting to install missing dependencies")
            try:
                if HAS_LIBP2P_EXTRA:
                    # If libp2p extra is installed but dependencies are missing, try reinstalling
                    logger.info("Reinstalling ipfs_kit_py with libp2p extras...")
                    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "ipfs_kit_py[libp2p]"]
                else:
                    # Otherwise just install the missing dependencies directly
                    logger.info("Attempting to auto-install missing dependencies...")
                    cmd = [sys.executable, "-m", "pip", "install", *missing_deps]
                
                subprocess.check_call(cmd)

                # Force recheck after installation
                DEPENDENCIES_CHECKED = False
                logger.debug("Re-checking dependencies after auto-installation")
                return check_dependencies()
            except Exception as e:
                logger.error(f"Failed to auto-install dependencies: {e}")
                # Continue with the current state (missing dependencies)
        else:
            logger.debug("Auto-install disabled, skipping installation attempt")

    # Check optional dependencies if required ones are available
    if all_available:
        optional_available = []
        optional_missing = []
        
        for dep in OPTIONAL_DEPENDENCIES:
            try:
                importlib.import_module(dep)
                optional_available.append(dep)
                logger.debug(f"Optional dependency {dep} is available")
            except (ImportError, ModuleNotFoundError):
                optional_missing.append(dep)
                logger.debug(f"Optional dependency {dep} is missing")
                
        if optional_missing:
            logger.info(f"Optional dependencies missing: {', '.join(optional_missing)}")
            logger.info("Some advanced functionality may be limited")

    return all_available

def install_dependencies(force: bool = False) -> bool:
    """
    Attempt to install required dependencies for libp2p functionality.
    
    This function first tries to install the libp2p extras package,
    and if that fails, falls back to installing individual dependencies.
    It also attempts to install optional dependencies, but doesn't fail if
    those installations don't succeed.
    
    Args:
        force: Force reinstallation even if dependencies are already installed.
              Set to True to reinstall all dependencies.
    
    Returns:
        bool: True if installation succeeded, False otherwise
    """
    global HAS_LIBP2P, _attempted_install, DEPENDENCIES_CHECKED, HAS_LIBP2P_EXTRA

    # Skip if we've already tried or dependencies are available and not forcing
    if (_attempted_install and not force) or (HAS_LIBP2P and not force):
        if HAS_LIBP2P:
            logger.debug("libp2p dependencies already available, skipping installation")
        else:
            logger.debug("Installation already attempted and force=False, skipping")
        return HAS_LIBP2P

    _attempted_install = True
    
    # First, check if we're in a pip-installable package
    # Try to get the package location to determine if we're in development mode
    package_location = None
    try:
        import ipfs_kit_py
        package_location = os.path.dirname(os.path.dirname(ipfs_kit_py.__file__))
        logger.debug(f"Package location: {package_location}")
    except (ImportError, AttributeError):
        # Package not installed, likely in development mode
        package_location = os.getcwd()
        logger.debug(f"Assuming development mode in: {package_location}")
    
    # Try to detect if we're in a git repository (development mode)
    in_dev_mode = os.path.exists(os.path.join(package_location, '.git'))
    logger.debug(f"Development mode detected: {in_dev_mode}")
    
    # Try to install using extras first
    logger.info("Attempting to install libp2p dependencies via package extras")
    
    try:
        if in_dev_mode:
            # If in development mode, install with -e flag
            install_cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-e", 
                f"{package_location}[libp2p]",
                "--upgrade"
            ]
        else:
            # Normal installation
            install_cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "ipfs_kit_py[libp2p]",
                "--upgrade"
            ]
        
        # Run the installation
        logger.debug(f"Running: {' '.join(install_cmd)}")
        result = subprocess.run(
            install_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False  # Don't raise exception, we'll handle errors
        )
        
        # Log detailed output for debugging
        if result.returncode == 0:
            logger.debug("Installation with extras succeeded")
            HAS_LIBP2P_EXTRA = True
            for line in result.stdout.splitlines():
                if "Installing" in line or "Requirement already satisfied" in line:
                    logger.debug(f"Pip: {line.strip()}")
        else:
            # If extras installation fails, fall back to individual dependencies
            logger.warning(f"Failed to install with extras: {result.stderr.strip()}")
            logger.info(f"Falling back to installing individual dependencies: {', '.join(REQUIRED_DEPENDENCIES)}")
            
            # Install required dependencies with pip upgrade
            dep_install_cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade"
            ]
            
            # Add dependencies
            dep_install_cmd.extend(REQUIRED_DEPENDENCIES)
            
            # Run the installation
            logger.debug(f"Running: {' '.join(dep_install_cmd)}")
            dep_result = subprocess.run(
                dep_install_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if dep_result.returncode != 0:
                logger.error(f"Failed to install dependencies: {dep_result.stderr.strip()}")
                return False

        # Try installing optional dependencies
        try:
            logger.debug(f"Installing optional dependencies: {', '.join(OPTIONAL_DEPENDENCIES)}")
            opt_install_cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade"
            ]
            opt_install_cmd.extend(OPTIONAL_DEPENDENCIES)
            
            opt_result = subprocess.run(
                opt_install_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if opt_result.returncode == 0:
                logger.debug("Optional dependencies installed successfully")
            else:
                logger.warning(f"Some optional dependencies could not be installed: {opt_result.stderr.strip()}")
        except Exception as e:
            logger.warning(f"Error installing optional dependencies: {e}")
            # Continue even if optional dependencies fail

        # Force recheck dependencies
        logger.info("Re-checking dependencies after installation")
        DEPENDENCIES_CHECKED = False
        has_deps = check_dependencies()
        
        if has_deps:
            logger.info("Successfully installed all libp2p dependencies")
        else:
            logger.error("Failed to install all required dependencies despite successful pip command")
            
        return has_deps

    except Exception as e:
        logger.error(f"Failed to install dependencies: {str(e)}", exc_info=True)
        return False

# Perform initial dependency check
logger.debug("Performing initial dependency check")
HAS_LIBP2P = check_dependencies()

# Initialize module exports
__all__ = [
    # Core functionality
    "HAS_LIBP2P",
    "check_dependencies",
    "install_dependencies",
    "patch_stream_read_until",
    
    # Protocol extensions
    "apply_protocol_extensions",
    "apply_protocol_extensions_to_instance",
    
    # Lazy loading functions
    "get_enhanced_dht_discovery",
    "get_content_routing_manager",
    "get_recursive_content_router",
    "get_delegated_content_router",
    "get_provider_record_manager",
    "get_content_routing_system",
    "get_libp2p_integration",
    "register_libp2p_with_ipfs_kit",
    "apply_ipfs_kit_integration",
    "apply_high_level_api_integration",
    
    # Enhanced protocol negotiation
    "get_enhanced_protocol_negotiation",
    "apply_enhanced_protocol_negotiation"
]

# Patch stream read_until method if required
def patch_stream_read_until():
    """
    Patch the Stream class with a read_until method if it's missing.
    
    This is a common method used in libp2p_peer.py for protocol handling
    that might not be available in all versions of libp2p.
    """
    if not HAS_LIBP2P:
        return  # No libp2p available to patch
    
    try:
        # First try to import our custom interface
        try:
            from ipfs_kit_py.libp2p.network.stream.net_stream_interface import INetStream
            logger.debug("Using custom stream interface from ipfs_kit_py")
        except ImportError:
            # Fall back to standard libp2p if available
            from libp2p.network.stream.net_stream_interface import INetStream
            logger.debug("Using standard libp2p stream interface")
        
        # Check if read_until is already defined
        if hasattr(INetStream, 'read_until'):
            logger.debug("Stream read_until method already available")
            return  # Already has the method
        
        # Define the read_until method
        async def read_until(self, delimiter, max_bytes=None):
            """
            Read from the stream until delimiter is found.
            
            Args:
                delimiter: Bytes delimiter to read until
                max_bytes: Maximum number of bytes to read
                
            Returns:
                Bytes read including the delimiter
            """
            if not isinstance(delimiter, bytes):
                raise ValueError("Delimiter must be bytes")
                
            result = bytearray()
            chunk_size = 1024  # Read in chunks
            
            while True:
                # Check max bytes limit
                if max_bytes is not None and len(result) >= max_bytes:
                    break
                    
                # Calculate next chunk size
                next_chunk_size = chunk_size
                if max_bytes is not None:
                    next_chunk_size = min(chunk_size, max_bytes - len(result))
                    
                # Read chunk
                chunk = await self.read(next_chunk_size)
                
                # End of stream
                if not chunk:
                    break
                    
                # Add to result
                result.extend(chunk)
                
                # Check for delimiter
                if delimiter in chunk:
                    # Find the complete data up to and including delimiter
                    all_data = bytes(result)
                    delimiter_pos = all_data.find(delimiter) + len(delimiter)
                    return all_data[:delimiter_pos]
            
            # Return all data if delimiter not found
            return bytes(result)
        
        # Add method to class
        setattr(INetStream, 'read_until', read_until)
        logger.info("Successfully patched INetStream with read_until method")
            
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not patch stream read_until method: {e}")
    except Exception as e:
        logger.error(f"Unexpected error patching stream: {e}")

# Inform about libp2p availability
if HAS_LIBP2P:
    logger.info("libp2p dependencies are available")
    # Apply patches when libp2p is available
    patch_stream_read_until()
else:
    logger.warning("libp2p dependencies not available. Some functionality will be limited.")

# Protocol extension functions
def apply_protocol_extensions(peer_class):
    """Apply protocol extensions to IPFSLibp2pPeer class.
    
    This is a proxy function that delegates to the proper implementation
    in protocol_integration.py, importing it only when needed.
    
    Args:
        peer_class: The IPFSLibp2pPeer class to extend
        
    Returns:
        The enhanced peer class
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot apply protocol extensions: libp2p is not available")
        return peer_class
    
    try:
        from .protocol_integration import apply_protocol_extensions as apply_func
        return apply_func(peer_class)
    except ImportError as e:
        logger.warning(f"Could not import protocol_integration module: {e}")
        return peer_class
    except Exception as e:
        logger.error(f"Error applying protocol extensions: {e}")
        return peer_class

def apply_protocol_extensions_to_instance(peer_instance):
    """Apply protocol extensions to IPFSLibp2pPeer instance.
    
    This is a proxy function that delegates to the proper implementation
    in protocol_integration.py, importing it only when needed.
    
    Args:
        peer_instance: The IPFSLibp2pPeer instance to extend
        
    Returns:
        The enhanced peer instance
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot apply protocol extensions: libp2p is not available")
        return peer_instance
    
    try:
        from .protocol_integration import apply_protocol_extensions_to_instance as apply_func
        return apply_func(peer_instance)
    except ImportError as e:
        logger.warning(f"Could not import protocol_integration module: {e}")
        return peer_instance
    except Exception as e:
        logger.error(f"Error applying protocol extensions: {e}")
        return peer_instance

# Define lazy loading functions to avoid circular imports
def get_enhanced_dht_discovery() -> Optional[Type]:
    """
    Get the EnhancedDHTDiscovery class for DHT-based peer discovery.
    
    This function dynamically imports and returns the EnhancedDHTDiscovery class
    from the enhanced_dht_discovery module. This approach avoids circular imports
    by only loading the class when it's explicitly requested.
    
    Returns:
        EnhancedDHTDiscovery class or None if libp2p is not available or import fails
    
    Example:
        EnhancedDHTDiscovery = get_enhanced_dht_discovery()
        if EnhancedDHTDiscovery:
            discovery = EnhancedDHTDiscovery(peer)
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot get EnhancedDHTDiscovery: libp2p is not available")
        return None
    
    try:
        from .enhanced_dht_discovery import EnhancedDHTDiscovery
        return EnhancedDHTDiscovery
    except ImportError as e:
        logger.error(f"Error importing EnhancedDHTDiscovery: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting EnhancedDHTDiscovery: {str(e)}", exc_info=True)
        return None

def get_content_routing_manager() -> Optional[Type]:
    """
    Get the ContentRoutingManager class for intelligent content routing.
    
    This function dynamically imports and returns the ContentRoutingManager class
    from the enhanced_dht_discovery module. The ContentRoutingManager provides
    advanced content routing capabilities based on peer statistics and reputation.
    
    Returns:
        ContentRoutingManager class or None if libp2p is not available or import fails
    
    Example:
        ContentRoutingManager = get_content_routing_manager()
        if ContentRoutingManager:
            router = ContentRoutingManager(peer)
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot get ContentRoutingManager: libp2p is not available")
        return None
    
    try:
        from .enhanced_dht_discovery import ContentRoutingManager
        return ContentRoutingManager
    except ImportError as e:
        logger.error(f"Error importing ContentRoutingManager: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting ContentRoutingManager: {str(e)}", exc_info=True)
        return None

def get_recursive_content_router() -> Optional[Type]:
    """
    Get the RecursiveContentRouter class for advanced recursive content routing.
    
    This function dynamically imports and returns the RecursiveContentRouter class
    from the recursive_routing module. The RecursiveContentRouter provides
    enhanced content routing capabilities with multi-level recursive lookups.
    
    Returns:
        RecursiveContentRouter class or None if libp2p is not available or import fails
    
    Example:
        RecursiveContentRouter = get_recursive_content_router()
        if RecursiveContentRouter:
            router = RecursiveContentRouter(dht_discovery)
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot get RecursiveContentRouter: libp2p is not available")
        return None
    
    try:
        from .recursive_routing import RecursiveContentRouter
        return RecursiveContentRouter
    except ImportError as e:
        logger.error(f"Error importing RecursiveContentRouter: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting RecursiveContentRouter: {str(e)}", exc_info=True)
        return None
        
def get_delegated_content_router() -> Optional[Type]:
    """
    Get the DelegatedContentRouter class for delegated content routing.
    
    This function dynamically imports and returns the DelegatedContentRouter class
    from the recursive_routing module. The DelegatedContentRouter allows
    resource-constrained devices to offload content discovery to trusted nodes.
    
    Returns:
        DelegatedContentRouter class or None if libp2p is not available or import fails
    
    Example:
        DelegatedContentRouter = get_delegated_content_router()
        if DelegatedContentRouter:
            router = DelegatedContentRouter(libp2p_peer, delegate_peers=["peer1", "peer2"])
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot get DelegatedContentRouter: libp2p is not available")
        return None
    
    try:
        from .recursive_routing import DelegatedContentRouter
        return DelegatedContentRouter
    except ImportError as e:
        logger.error(f"Error importing DelegatedContentRouter: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting DelegatedContentRouter: {str(e)}", exc_info=True)
        return None
        
def get_provider_record_manager() -> Optional[Type]:
    """
    Get the ProviderRecordManager class for advanced provider tracking.
    
    This function dynamically imports and returns the ProviderRecordManager class
    from the recursive_routing module. The ProviderRecordManager provides
    sophisticated provider record management with reputation tracking.
    
    Returns:
        ProviderRecordManager class or None if libp2p is not available or import fails
    
    Example:
        ProviderRecordManager = get_provider_record_manager()
        if ProviderRecordManager:
            provider_manager = ProviderRecordManager()
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot get ProviderRecordManager: libp2p is not available")
        return None
    
    try:
        from .recursive_routing import ProviderRecordManager
        return ProviderRecordManager
    except ImportError as e:
        logger.error(f"Error importing ProviderRecordManager: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting ProviderRecordManager: {str(e)}", exc_info=True)
        return None
        
def get_content_routing_system() -> Optional[Type]:
    """
    Get the ContentRoutingSystem class for unified routing management.
    
    This function dynamically imports and returns the ContentRoutingSystem class
    from the recursive_routing module. The ContentRoutingSystem provides a
    unified interface for all content routing strategies.
    
    Returns:
        ContentRoutingSystem class or None if libp2p is not available or import fails
    
    Example:
        ContentRoutingSystem = get_content_routing_system()
        if ContentRoutingSystem:
            routing_system = ContentRoutingSystem(libp2p_peer, dht_discovery, role="worker")
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot get ContentRoutingSystem: libp2p is not available")
        return None
    
    try:
        from .recursive_routing import ContentRoutingSystem
        return ContentRoutingSystem
    except ImportError as e:
        logger.error(f"Error importing ContentRoutingSystem: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting ContentRoutingSystem: {str(e)}", exc_info=True)
        return None

def get_libp2p_integration() -> Optional[Type]:
    """
    Get the LibP2PIntegration class for filesystem cache integration.
    
    This function dynamically imports and returns the LibP2PIntegration class
    from the p2p_integration module. The LibP2PIntegration class provides the
    connection between libp2p peers and the filesystem cache system.
    
    Returns:
        LibP2PIntegration class or None if libp2p is not available or import fails
    
    Example:
        LibP2PIntegration = get_libp2p_integration()
        if LibP2PIntegration:
            integration = LibP2PIntegration(peer, cache_manager)
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot get LibP2PIntegration: libp2p is not available")
        return None
    
    try:
        from .p2p_integration import LibP2PIntegration
        return LibP2PIntegration
    except ImportError as e:
        logger.error(f"Error importing LibP2PIntegration: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting LibP2PIntegration: {str(e)}", exc_info=True)
        return None

def register_libp2p_with_ipfs_kit(ipfs_kit_instance: Any, libp2p_peer: Any, extend_cache: bool = True) -> Optional[Any]:
    """
    Register libp2p with an IPFSKit instance for direct peer-to-peer content exchange.
    
    This function integrates a libp2p peer with an IPFSKit instance, optionally
    extending the cache manager to handle cache misses using libp2p content retrieval.
    
    Args:
        ipfs_kit_instance: The IPFSKit instance to register with
        libp2p_peer: The libp2p peer to register
        extend_cache: Whether to extend the cache manager with libp2p integration
        
    Returns:
        LibP2PIntegration instance or None if registration failed
    
    Example:
        # Create a libp2p peer
        from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
        libp2p_peer = IPFSLibp2pPeer(role="worker")
        
        # Register with IPFSKit
        integration = register_libp2p_with_ipfs_kit(ipfs_kit, libp2p_peer)
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot register libp2p: libp2p is not available")
        return None
    
    try:
        from .p2p_integration import register_libp2p_with_ipfs_kit as reg_func
        result = reg_func(ipfs_kit_instance, libp2p_peer, extend_cache)
        logger.debug(f"Registered libp2p with IPFSKit instance: {result}")
        return result
    except ImportError as e:
        logger.error(f"Error importing register_libp2p_with_ipfs_kit: {e}")
        return None
    except Exception as e:
        logger.error(f"Error registering libp2p with ipfs_kit: {e}")
        return None

def apply_ipfs_kit_integration(ipfs_kit_class: Type) -> Type:
    """
    Apply libp2p integration to the IPFSKit class by extending its functionality.
    
    This function extends the IPFSKit class with additional methods and functionality
    for libp2p integration, including direct content retrieval and caching. The
    extension is done through monkey patching rather than inheritance to avoid
    circular imports.
    
    Args:
        ipfs_kit_class: The IPFSKit class to extend
        
    Returns:
        Extended IPFSKit class or original class if integration failed
    
    Example:
        from ipfs_kit_py.ipfs_kit import IPFSKit
        enhanced_kit_class = apply_ipfs_kit_integration(IPFSKit)
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot apply IPFSKit integration: libp2p is not available")
        return ipfs_kit_class
    
    try:
        from .ipfs_kit_integration import apply_ipfs_kit_integration as apply_func
        result = apply_func(ipfs_kit_class)
        logger.debug(f"Applied libp2p integration to IPFSKit class: {result}")
        return result
    except ImportError as e:
        logger.error(f"Error importing apply_ipfs_kit_integration: {e}")
        return ipfs_kit_class
    except Exception as e:
        logger.error(f"Error applying libp2p integration to IPFSKit: {str(e)}", exc_info=True)
        return api_class

def apply_high_level_api_integration(api_class: Type) -> Type:
    """
    Apply libp2p integration to the high-level API class.
    
    This function extends the high-level API class (IPFSSimpleAPI) with additional
    methods for peer discovery and direct content retrieval using libp2p. This
    integration enables direct peer-to-peer communication through the simplified API.
    
    Args:
        api_class: The high-level API class to extend
        
    Returns:
        Extended API class or original class if integration failed
    
    Example:
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        enhanced_api_class = apply_high_level_api_integration(IPFSSimpleAPI)
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot apply high-level API integration: libp2p is not available")
        return api_class
    
    try:
        from .high_level_api_integration import apply_high_level_api_integration as apply_func
        result = apply_func(api_class)
        logger.debug(f"Applied libp2p integration to high-level API class: {result}")
        return result
    except ImportError as e:
        logger.error(f"Error importing apply_high_level_api_integration: {e}")
        return api_class
    except Exception as e:
        logger.error(f"Error applying libp2p integration to high-level API: {str(e)}", exc_info=True)
        return api_class

def get_enhanced_protocol_negotiation() -> Dict[str, Any]:
    """
    Get the enhanced protocol negotiation components.
    
    Returns a dictionary containing the key classes for enhanced protocol negotiation:
    - EnhancedMultiselect: Server-side protocol selection with capabilities
    - EnhancedMultiselectClient: Client-side protocol selection
    - ProtocolMeta: Protocol metadata with version and capabilities
    - Helper functions: parse_protocol_id, is_version_compatible, etc.
    
    Returns:
        Dictionary of protocol negotiation components or empty dict if not available
    
    Example:
        negotiation = get_enhanced_protocol_negotiation()
        if negotiation:
            EnhancedMultiselect = negotiation["EnhancedMultiselect"]
            multiselect = EnhancedMultiselect()
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot get enhanced protocol negotiation: libp2p is not available")
        return {}
    
    try:
        # Import all necessary components
        from .enhanced_protocol_negotiation import (
            EnhancedMultiselect,
            EnhancedMultiselectClient,
            ProtocolMeta,
            parse_protocol_id,
            is_version_compatible,
            enhance_protocol_negotiation
        )
        
        # Return a dictionary of components
        return {
            "EnhancedMultiselect": EnhancedMultiselect,
            "EnhancedMultiselectClient": EnhancedMultiselectClient,
            "ProtocolMeta": ProtocolMeta,
            "parse_protocol_id": parse_protocol_id,
            "is_version_compatible": is_version_compatible,
            "enhance_protocol_negotiation": enhance_protocol_negotiation,
            # Constants
            "ENHANCED_MULTISELECT_PROTOCOL_ID": getattr(
                EnhancedMultiselect, "ENHANCED_MULTISELECT_PROTOCOL_ID", 
                "/multistream-select-enhanced/1.0.0"
            ),
            "STANDARD_MULTISELECT_PROTOCOL_ID": getattr(
                EnhancedMultiselect, "STANDARD_MULTISELECT_PROTOCOL_ID",
                "/multistream/1.0.0"
            )
        }
    except ImportError as e:
        logger.error(f"Error importing enhanced protocol negotiation: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error getting enhanced protocol negotiation: {str(e)}", exc_info=True)
        return {}

def apply_enhanced_protocol_negotiation(target: Any) -> Any:
    """
    Apply enhanced protocol negotiation to a class or instance.
    
    This is a convenience function that applies enhanced protocol negotiation
    to either a class or an instance, determining the appropriate approach
    automatically.
    
    Args:
        target: Class or instance to enhance with protocol negotiation
        
    Returns:
        Enhanced class or instance, or original if enhancement failed
    
    Example:
        # Enhance a class
        EnhancedPeer = apply_enhanced_protocol_negotiation(IPFSLibp2pPeer)
        
        # Or enhance an instance
        peer = IPFSLibp2pPeer()
        apply_enhanced_protocol_negotiation(peer)
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot apply enhanced protocol negotiation: libp2p is not available")
        return target
    
    try:
        # Import necessary modules
        from .protocol_integration import apply_enhanced_negotiation, add_enhanced_negotiation_methods
        
        # Determine if target is a class or instance
        if isinstance(target, type):
            # It's a class, apply class-level enhancement
            logger.debug(f"Applying enhanced protocol negotiation to class {target.__name__}")
            return apply_enhanced_negotiation(target)
        else:
            # It's an instance, apply instance-level enhancement
            logger.debug("Applying enhanced protocol negotiation to instance")
            # First apply methods to the class if needed
            add_enhanced_negotiation_methods(target.__class__)
            
            # Then initialize enhanced negotiation in the instance
            if hasattr(target, 'multiselect') or hasattr(target, 'multiselect_client'):
                try:
                    from .enhanced_protocol_negotiation import EnhancedMultiselect, EnhancedMultiselectClient
                    
                    # Replace existing components
                    if hasattr(target, 'multiselect') and target.multiselect is not None:
                        handlers = getattr(target.multiselect, 'handlers', {})
                        target.multiselect = EnhancedMultiselect(default_handlers=handlers)
                        
                    if hasattr(target, 'multiselect_client') and target.multiselect_client is not None:
                        target.multiselect_client = EnhancedMultiselectClient()
                    
                    # Mark as enhanced
                    target._using_enhanced_multiselect = True
                    
                    logger.info("Enhanced protocol negotiation initialized for instance")
                except Exception as e:
                    logger.warning(f"Could not replace multiselect components for instance: {e}")
            
            # Initialize protocol capabilities dict if needed
            if not hasattr(target, 'protocol_capabilities'):
                target.protocol_capabilities = {}
                
            return target
            
    except ImportError as e:
        logger.error(f"Error importing protocol negotiation components: {e}")
        return target
    except Exception as e:
        logger.error(f"Error applying enhanced protocol negotiation: {str(e)}", exc_info=True)
        return target

def setup_advanced_routing(ipfs_kit_instance, libp2p_peer, dht_discovery=None, role=None):
    """
    Set up advanced routing components for an IPFSKit instance.
    
    This function creates and configures the advanced routing components (recursive,
    delegated, provider record manager) for an IPFSKit instance. This enhances the
    content discovery capabilities with sophisticated multi-level routing.
    
    Args:
        ipfs_kit_instance: The IPFSKit instance to enhance
        libp2p_peer: The LibP2P peer instance
        dht_discovery: Optional EnhancedDHTDiscovery instance (created if None)
        role: Node role ("master", "worker", or "leecher")
        
    Returns:
        ContentRoutingSystem instance or None if setup failed
    
    Example:
        from ipfs_kit_py.ipfs_kit import IPFSKit
        from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
        
        kit = IPFSKit()
        peer = IPFSLibp2pPeer()
        routing_system = setup_advanced_routing(kit, peer, role="worker")
    """
    if not HAS_LIBP2P:
        logger.warning("Cannot set up advanced routing: libp2p is not available")
        return None
    
    try:
        # Get roles
        if role is None:
            role = getattr(ipfs_kit_instance, "role", "leecher")
            
        # Create DHT discovery if not provided
        if dht_discovery is None and libp2p_peer is not None:
            EnhancedDHTDiscovery = get_enhanced_dht_discovery()
            if EnhancedDHTDiscovery:
                dht_discovery = EnhancedDHTDiscovery(libp2p_peer)
                
        # Get content routing system
        ContentRoutingSystem = get_content_routing_system()
        if not ContentRoutingSystem:
            logger.warning("ContentRoutingSystem not available")
            return None
            
        # Create content routing system
        routing_system = ContentRoutingSystem(
            libp2p_peer=libp2p_peer,
            dht_discovery=dht_discovery,
            role=role
        )
        
        # Store in IPFS kit instance
        if hasattr(ipfs_kit_instance, "routing_components"):
            ipfs_kit_instance.routing_components["advanced_routing"] = routing_system
        else:
            ipfs_kit_instance.routing_components = {"advanced_routing": routing_system}
            
        # Add convenience method for content lookup
        if not hasattr(ipfs_kit_instance, "find_providers_advanced"):
            async def find_providers_advanced(self, cid, count=5, timeout=30, **kwargs):
                """
                Find content providers using advanced routing strategies.
                
                Args:
                    cid: Content ID to find providers for
                    count: Maximum number of providers to return
                    timeout: Maximum time to spend searching
                    **kwargs: Additional arguments for the routing strategy
                    
                Returns:
                    List of provider information dictionaries
                """
                if not hasattr(self, "routing_components") or "advanced_routing" not in self.routing_components:
                    logger.warning("Advanced routing not configured")
                    return []
                    
                return await self.routing_components["advanced_routing"].find_providers(
                    cid, count, timeout, **kwargs
                )
                
            # Add method to instance
            import types
            ipfs_kit_instance.find_providers_advanced = types.MethodType(
                find_providers_advanced, ipfs_kit_instance
            )
            
        # Add method for content announcement
        if not hasattr(ipfs_kit_instance, "announce_content_advanced"):
            async def announce_content_advanced(self, cid, **kwargs):
                """
                Announce that this node can provide specific content.
                
                Args:
                    cid: Content ID to announce
                    **kwargs: Additional arguments for the provide operation
                    
                Returns:
                    Boolean indicating success
                """
                if not hasattr(self, "routing_components") or "advanced_routing" not in self.routing_components:
                    logger.warning("Advanced routing not configured")
                    return False
                    
                return await self.routing_components["advanced_routing"].provide(cid, **kwargs)
                
            # Add method to instance
            import types
            ipfs_kit_instance.announce_content_advanced = types.MethodType(
                announce_content_advanced, ipfs_kit_instance
            )
            
        logger.info("Advanced routing system successfully configured")
        return routing_system
        
    except Exception as e:
        logger.error(f"Error setting up advanced routing: {str(e)}", exc_info=True)
        return None

def compatible_new_host(key_pair=None, listen_addrs=None, transport_opt=None, 
                        muxer_opt=None, sec_opt=None, peerstore_opt=None, **kwargs):
    """
    Compatibility wrapper for the libp2p.new_host function to handle API differences.
    
    Different versions of libp2p have different parameter requirements for the new_host function.
    This function provides a unified interface that handles these differences by adapting
    parameters to match the installed version.
    
    Args:
        key_pair: Key pair for the host identity
        listen_addrs: List of multiaddresses to listen on
        transport_opt: Transport options
        muxer_opt: Multiplexer options
        sec_opt: Security options
        peerstore_opt: Peer store options
        **kwargs: Additional keyword arguments
        
    Returns:
        libp2p host instance
    
    Raises:
        Exception: If host creation fails after attempting all compatibility modes
    """
    if not HAS_LIBP2P:
        logger.error("Cannot create host: libp2p is not available")
        raise ImportError("libp2p is not available")
    
    # Import the new_host function
    try:
        from libp2p import new_host
    except ImportError:
        logger.error("Cannot import new_host from libp2p")
        raise ImportError("Cannot import new_host from libp2p")
    
    # Try different parameter combinations
    attempts = []
    
    # Try with the parameters exactly as provided
    try:
        logger.debug("Attempting to create host with original parameters")
        host = new_host(
            key_pair=key_pair,
            listen_addrs=listen_addrs,
            transport_opt=transport_opt,
            muxer_opt=muxer_opt,
            sec_opt=sec_opt,
            peerstore_opt=peerstore_opt,
            **kwargs
        )
        logger.debug("Successfully created host with original parameters")
        return host
    except TypeError as e:
        attempts.append(("Original parameters", str(e)))
        logger.debug(f"Host creation with original parameters failed: {e}")
    
    # Try without listen_addrs (common issue)
    if listen_addrs is not None:
        try:
            logger.debug("Attempting to create host without listen_addrs")
            
            # Combine transport_opt and listen_addrs
            combined_transport_opt = transport_opt or []
            if not isinstance(combined_transport_opt, list):
                combined_transport_opt = [combined_transport_opt]
            
            # Add listen addresses to transport_opt
            # Some versions expect addresses in transport_opt instead of listen_addrs
            host = new_host(
                key_pair=key_pair,
                transport_opt=combined_transport_opt,
                muxer_opt=muxer_opt,
                sec_opt=sec_opt,
                peerstore_opt=peerstore_opt,
                **kwargs
            )
            
            # Manually set listen addresses after creation
            for addr in listen_addrs:
                host.get_network().listen(addr)
                
            logger.debug("Successfully created host without listen_addrs parameter")
            return host
        except (TypeError, AttributeError) as e:
            attempts.append(("Without listen_addrs", str(e)))
            logger.debug(f"Host creation without listen_addrs failed: {e}")
    
    # Try with minimal parameters
    try:
        logger.debug("Attempting to create host with minimal parameters")
        host = new_host(key_pair=key_pair)
        
        # Manually configure components after creation
        if listen_addrs:
            for addr in listen_addrs:
                host.get_network().listen(addr)
        
        logger.debug("Successfully created host with minimal parameters")
        return host
    except TypeError as e:
        attempts.append(("Minimal parameters", str(e)))
        logger.debug(f"Host creation with minimal parameters failed: {e}")
    
    # Try with signature-based approach (older versions)
    try:
        logger.debug("Attempting to create host with old-style parameters")
        # Some older versions used positional arguments
        host = new_host(key_pair)
        
        # Manually configure components after creation
        if listen_addrs:
            for addr in listen_addrs:
                host.get_network().listen(addr)
        
        logger.debug("Successfully created host with old-style parameters")
        return host
    except TypeError as e:
        attempts.append(("Old-style parameters", str(e)))
        logger.debug(f"Host creation with old-style parameters failed: {e}")
    
    # If we reach here, all attempts failed
    error_msg = "Failed to create libp2p host after trying multiple compatibility modes:\n"
    for attempt, error in attempts:
        error_msg += f"  - {attempt}: {error}\n"
    logger.error(error_msg)
    
    # Raise the most recent error
    raise TypeError(error_msg)

# Add additional functions to __all__
__all__.append("compatible_new_host")
__all__.append("setup_advanced_routing")
