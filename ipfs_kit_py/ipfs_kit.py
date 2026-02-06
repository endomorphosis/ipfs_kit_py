import anyio
import datetime
import io
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from unittest.mock import MagicMock

import requests
import urllib3
import functools
from typing import Callable, TypeVar, Optional, Any, Dict, List

from .error import (
    IPFSConfigurationError,
    IPFSConnectionError,
    IPFSContentNotFoundError,
    IPFSError,
    IPFSTimeoutError,
    IPFSValidationError,
    create_result_dict,
    handle_error,
    perform_with_retry,
)
from .performance_metrics import PerformanceMetrics
from .observability_api import observability_router
# Avoid importing cluster monitoring at module import time.
# It can pull in large portions of the stack and has historically triggered
# circular imports / side effects during test collection.
try:
    from .cluster.monitoring import ClusterMonitor, MetricsCollector
except Exception:
    ClusterMonitor = None  # type: ignore
    MetricsCollector = None  # type: ignore
from .program_state import get_program_state_manager

# Define a generic type variable for the return type
RT = TypeVar('RT')

def auto_retry_on_daemon_failure(daemon_type: str = "ipfs", max_retries: int = 3):
    """
    Decorator that automatically retries operations when they fail due to a daemon not running.

    This decorator will:
    1. Check if the operation fails due to daemon not running
    2. Attempt to start the required daemon
    3. Retry the operation

    Args:
        daemon_type (str): Type of daemon required ("ipfs", "ipfs_cluster_service", or "ipfs_cluster_follow")
        max_retries (int): Maximum number of retry attempts

    Returns:
        Decorated function with automatic daemon startup and retry capability
    """
    def decorator(func: Callable[..., RT]) -> Callable[..., RT]:
        @functools.wraps(func)
        def wrapper(self, *args: Any, **kwargs: Any) -> RT:
            retry_count = 0

            while retry_count <= max_retries:
                # Attempt the operation
                result = func(self, *args, **kwargs)

                # Check if operation failed due to daemon not running
                if (not result.get("success", False) and # type: ignore
                    isinstance(result.get("error"), str) and # Ensure error is a string before calling lower() # type: ignore
                    result.get("error", "").lower().find("daemon") >= 0 and # type: ignore
                    "not running" in result.get("error", "").lower()): # type: ignore

                    # Only retry if automatic daemon startup is enabled
                    if not getattr(self, "auto_start_daemons", False):
                        # Add note that automatic retry is disabled
                        result["daemon_retry_disabled"] = True # type: ignore
                        return result

                    # Increment retry counter
                    retry_count += 1

                    # Log the retry attempt
                    self.logger.info(f"Operation failed due to {daemon_type} daemon not running. "
                                     f"Attempt {retry_count}/{max_retries} to start daemon and retry.")

                    # Try to start the daemon
                    daemon_result = self._ensure_daemon_running(daemon_type)

                    if not daemon_result.get("success", False): # type: ignore
                        # Failed to start daemon, add details and return
                        result["daemon_start_attempted"] = True # type: ignore
                        result["daemon_start_failed"] = True # type: ignore
                        result["daemon_start_error"] = daemon_result.get("error") # type: ignore
                        return result

                    # Daemon started successfully, retry operation
                    self.logger.info(f"Successfully started {daemon_type} daemon, retrying operation.")
                    result["daemon_restarted"] = True # type: ignore

                    # If this is the last retry, break to avoid exceeding max_retries
                    if retry_count >= max_retries:
                        break

                    # Add a small delay to ensure daemon is fully up
                    time.sleep(1)

                    # Continue loop to retry operation
                    continue

                # Operation succeeded or failed for reasons other than daemon not running
                return result

            # If we get here, we've used all our retries
            if not result.get("success", False): # type: ignore
                result["max_retries_exceeded"] = True # type: ignore

            return result

        return wrapper

    return decorator

parent_dir = os.path.dirname(os.path.dirname(__file__))
ipfs_lib_dir = os.path.join(parent_dir, "ipfs_kit_py")
sys.path.append(parent_dir)

# Configure logger
logger = logging.getLogger(__name__)
from .install_ipfs import install_ipfs
from .ipfs import ipfs_py
from .ipfs_cluster_ctl import ipfs_cluster_ctl
from .ipfs_cluster_follow import ipfs_cluster_follow
from .ipfs_cluster_service import ipfs_cluster_service
from .ipfs_kit_extensions import extend_ipfs_kit
from .ipget import ipget
from .s3_kit import s3_kit
from .storacha_kit import storacha_kit
from .gdrive_kit import gdrive_kit
from .test_fio import test_fio

# Try to import synapse_storage
try:
    from .synapse_storage import synapse_storage
    HAS_SYNAPSE = True
except ImportError:
    HAS_SYNAPSE = False

# Try to import lotus_kit
try:
    from .lotus_kit import lotus_kit
    HAS_LOTUS = True
except ImportError:
    HAS_LOTUS = False

# Make HAS_LOTUS available globally
globals()['HAS_LOTUS'] = HAS_LOTUS

# Try to import huggingface_kit
try:
    from .huggingface_kit import huggingface_kit
    HAS_HUGGINGFACE = True
except ImportError:
    HAS_HUGGINGFACE = False

# Try to import libp2p (DISABLED due to protobuf conflicts)
try:
    # DISABLED: from .libp2p_peer import IPFSLibp2pPeer
    # LibP2P peer functionality disabled to avoid protobuf conflicts
    raise ImportError("LibP2P disabled due to protobuf conflicts")
    
    HAS_LIBP2P = True
except ImportError:
    HAS_LIBP2P = False

# Make HAS_LIBP2P and HAS_LOTUS global variables
__all__ = ['HAS_LIBP2P', 'HAS_LOTUS', 'ipfs_kit', 'IPFSKit']

# Try to import IPLD extension
try:
    from .ipld_extension import IPLDExtension
    HAS_IPLD_EXTENSION = True
except ImportError:
    HAS_IPLD_EXTENSION = False

# Try to import cluster management components
try:
    from .cluster.cluster_manager import ClusterManager
    from .cluster.distributed_coordination import ClusterCoordinator
    from .cluster.role_manager import NodeRole
    from .cluster.utils import get_gpu_info

    HAS_CLUSTER_MANAGEMENT = True
except ImportError:
    HAS_CLUSTER_MANAGEMENT = False

# Monitoring components are imported (best-effort) near the top of this module.
HAS_MONITORING = ClusterMonitor is not None and MetricsCollector is not None

# GPU information is included in the cluster management imports

# Try to import knowledge graph components
try:
    from .ipld_knowledge_graph import GraphRAG, IPLDGraphDB, KnowledgeGraphQuery

    HAS_KNOWLEDGE_GRAPH = True
except ImportError:
    HAS_KNOWLEDGE_GRAPH = False

# Try to import AI/ML integration components
try:
    from .ai_ml_integration import (
        DatasetManager,
        DistributedTraining,
        IPFSDataLoader,
        LangchainIntegration,
        LlamaIndexIntegration,
        ModelRegistry,
    )

    HAS_AI_ML_INTEGRATION = True
except ImportError:
    HAS_AI_ML_INTEGRATION = False

# Try to import Arrow metadata index components
try:
    from .arrow_metadata_index import ArrowMetadataIndex
    from .metadata_sync_handler import MetadataSyncHandler

    HAS_ARROW_INDEX = True
except ImportError:
    HAS_ARROW_INDEX = False

# Import FSSpec integration (with fallback for when fsspec isn't installed)
try:
    from .ipfs_fsspec import IPFSFSSpecFileSystem # Changed import to IPFSFSSpecFileSystem
    from .tiered_cache_manager import TieredCacheManager
    FSSPEC_AVAILABLE = True
    HAS_TIERED_CACHE_MANAGER = True # Added flag for tiered cache manager
except ImportError:
    FSSPEC_AVAILABLE = False
    HAS_TIERED_CACHE_MANAGER = False # Added flag for tiered cache manager

# Import WebSocket peer discovery components (with fallback if not available)
#
# Note: this import can trigger noisy stdout from optional third-party deps
# (e.g. libp2p_kit_py) at import time. Keep it opt-in so core imports remain
# side-effect free and tests don't hang waiting on network-ish initialization.
_ENABLE_WS = os.environ.get("IPFS_KIT_ENABLE_WEBSOCKET_PEER_DISCOVERY", "").strip().lower() in {"1", "true", "yes", "on"}
if _ENABLE_WS:
    try:
        from .peer_websocket import (
            PeerInfo, PeerWebSocketServer, PeerWebSocketClient,
            create_peer_info_from_ipfs_kit, PeerRole, WEBSOCKET_AVAILABLE
        )

        HAS_WEBSOCKET_PEER_DISCOVERY = True
    except ImportError:
        HAS_WEBSOCKET_PEER_DISCOVERY = False
else:
    HAS_WEBSOCKET_PEER_DISCOVERY = False
import json
import os
import subprocess
import time


class ipfs_kit:
    """
    Main orchestrator class for IPFS Kit.

    Provides a unified interface to various IPFS and cluster functionalities,
    adapting its behavior and available components based on the configured
    node role (master, worker, leecher) and enabled features.

    Manages underlying components like IPFS daemon interaction (`ipfs_py`),
    IPFS Cluster components (`ipfs_cluster_service`, `ipfs_cluster_ctl`,
    `ipfs_cluster_follow`), storage integrations (`s3_kit`, `storacha_kit`, `gdrive_kit`),
    FSSpec interface, tiered caching, metadata indexing, libp2p networking,
    advanced cluster management, AI/ML tools, and more.

    Configuration is primarily driven by the `metadata` dictionary passed
    during initialization.
    """

    @classmethod
    def create(cls, role="leecher", auto_start_daemons=True, **kwargs):
        """
        Create and initialize an ipfs_kit instance with the specified role.

        This convenience method creates an instance and ensures all required
        daemons are running before returning it to the caller.

        Args:
            role (str): Node role ('master', 'worker', or 'leecher')
            auto_start_daemons (bool): Whether to automatically start required daemons
            **kwargs: Additional parameters to pass to the constructor

        Returns:
            ipfs_kit: Initialized instance ready for use

        Raises:
            IPFSError: If initialization fails with auto_start_daemons=True
        """
        # Create metadata dictionary if not provided
        metadata = kwargs.get("metadata", {})
        metadata["role"] = role
        metadata["auto_start_daemons"] = auto_start_daemons

        # Create instance
        instance = cls(metadata=metadata, **kwargs)

        # Initialize and start daemons if requested
        if auto_start_daemons:
            init_result = instance.initialize(start_daemons=auto_start_daemons)
            if not init_result.get("success", False): # type: ignore
                from .error import IPFSError
                error_msg = init_result.get("error", "Unknown initialization error") # type: ignore
                raise IPFSError(f"Failed to initialize IPFS Kit: {error_msg}")

            # Set initialization state
            instance._initialized = True
        else:
            instance._initialized = False

        return instance

    @property
    def is_initialized(self):
        """
        Check if the SDK has been properly initialized and daemons are running.

        Returns:
            bool: True if initialized and daemons are running, False otherwise
        """
        if not hasattr(self, "_initialized") or not self._initialized:
            return False

        # Check daemon status
        daemon_status = self.check_daemon_status()
        if not daemon_status.get("success", False): # type: ignore
            return False

        # Check if required daemons are running
        daemons = daemon_status.get("daemons", {}) # type: ignore
        if not daemons.get("ipfs", {}).get("running", False):
            return False

        # Check role-specific daemons
        if self.role == "master":
            if not daemons.get("ipfs_cluster_service", {}).get("running", False):
                return False
        elif self.role == "worker":
            if not daemons.get("ipfs_cluster_follow", {}).get("running", False):
                return False

        return True

    def __init__(
        self,
        resources=None,
        metadata=None,
        enable_libp2p=False,
        enable_cluster_management=False,
        enable_metadata_index=False,
        auto_start_daemons=True,
    ):
        """
        Initializes the IPFS Kit instance.

        Args:
            resources (dict, optional): Dictionary describing available node
                resources (e.g., {'memory': '8GB', 'cpu': 4}). Used by some
                sub-components like storage kits or cluster management. Defaults to None.
            metadata (dict, optional): Core configuration dictionary. Key fields include:
                - 'role' (str): Node role ('master', 'worker', 'leecher'). Defaults to 'leecher'.
                - 'cluster_name' (str): Name of the IPFS Cluster.
                - 'ipfs_path' (str): Path to the IPFS repository.
                - 'config' (dict): General configuration settings.
                - 'security' (dict): Security-related configurations.
                - 'libp2p_config' (dict): Configuration for the libp2p peer.
                - 'knowledge_graph_config' (dict): Configuration for IPLD knowledge graph.
                - 'ai_ml_config' (dict): Configuration for AI/ML components.
                - 'metadata_index_dir' (str): Path for the Arrow metadata index.
                - 'enable_libp2p' (bool): Overrides enable_libp2p parameter.
                - 'enable_cluster_management' (bool): Overrides enable_cluster_management parameter.
                - 'enable_metadata_index' (bool): Overrides enable_metadata_index parameter.
                - 'enable_monitoring' (bool): Enables cluster monitoring features.
                - 'auto_download_binaries' (bool): Controls automatic binary downloads.
                - 'auto_start_daemons' (bool): Controls automatic daemon initialization.
                Defaults to True. Can be overridden by `metadata['auto_start_daemons']`.
        """
        # Initialize logger
        self.logger = logger

        # Store metadata
        self.metadata = metadata or {}
        # Normalize local variable so downstream logic doesn't treat None as
        # "skip initialization". Many call sites construct ipfs_kit() without
        # passing metadata.
        metadata = self.metadata

        # Initialize _initialized attribute
        self._initialized = False

        # Properly set up method aliases - avoid infinite recursion by removing self-referential assignments
        # These will be assigned later as we implement the methods
        # For now, we'll initialize ipfs_get as a lambda to call ipget's method when available
        self.ipfs_get = lambda **kwargs: (
            self.ipget.ipget_download_object(**kwargs) if hasattr(self, "ipget") else None
        )

        # We need to define the methods first before creating aliases

        # FSSpec filesystem instance (initialized on first use)
        self._filesystem = None
        self._tiered_cache_manager = None # Initialize tiered cache manager

        # Ensure optional kits are always present as attributes
        self.lotus_kit = None

        # Metadata index and sync handler (initialized on demand)
        self._metadata_index = None
        self._metadata_sync_handler = None
        
        # Daemon management (initialized when needed)
        self.daemon_manager = None

        # Check if we need to download binaries
        # Default to NOT downloading binaries automatically. This avoids
        # surprising network activity during imports/tests; users can opt-in
        # via metadata["auto_download_binaries"] = True.
        auto_download = self.metadata.get("auto_download_binaries", False)
        if auto_download:
            # Check if binaries directory exists and has the required binaries
            this_dir = os.path.dirname(os.path.realpath(__file__))
            bin_dir = os.path.join(this_dir, "bin")
            ipfs_bin = os.path.join(bin_dir, "ipfs")
            ipfs_cluster_service_bin = os.path.join(bin_dir, "ipfs-cluster-service")

            # On Windows, check for .exe files
            if platform.system() == "Windows":
                ipfs_bin += ".exe"
                ipfs_cluster_service_bin += ".exe"

            # Download binaries if they don't exist
            if not os.path.exists(ipfs_bin) or not os.path.exists(ipfs_cluster_service_bin):
                try:
                    # Import from package root to ensure we get the package-level function
                    from ipfs_kit_py import download_binaries

                    download_binaries()
                except Exception as e:
                    self.logger.warning(f"Failed to download binaries: {e}")
                    self.logger.info("Will attempt to continue with available binaries")

        # Initialize path variables
        this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ.get("PATH", "")
        self.path = self.path + ":" + os.path.join(this_dir, "bin")
        self.path_string = "PATH=" + self.path

        # Set default role
        self.role = "leecher"

        # Default configuration
        self.config = {}

        # Check if we should auto-start daemons
        self.auto_start_daemons = auto_start_daemons

        # Process metadata
        if metadata is not None:
            if "config" in metadata:
                self.config = metadata["config"]

            if "role" in metadata:
                self.role = metadata["role"]

            if "cluster_name" in metadata:
                self.cluster_name = metadata["cluster_name"]

            if "ipfs_path" in metadata:
                self.ipfs_path = metadata["ipfs_path"]

            if "enable_libp2p" in metadata:
                enable_libp2p = metadata["enable_libp2p"]

            if "enable_cluster_management" in metadata:
                enable_cluster_management = metadata["enable_cluster_management"]

            if "enable_metadata_index" in metadata:
                enable_metadata_index = metadata["enable_metadata_index"]

            if "auto_start_daemons" in metadata:
                self.auto_start_daemons = metadata["auto_start_daemons"]

            # Initialize components based on role
            if self.role == "leecher":
                # Check for disabled components
                disabled_components = metadata.get("disabled_components", [])
                
                # Leecher only needs IPFS daemon
                self.ipfs = ipfs_py(metadata={"role": self.role, "testing": False}) # Explicitly set testing to False
                # Add storage kit for S3 connectivity
                self.s3_kit = s3_kit(resources=resources)
                self.storacha_kit = storacha_kit(resources=resources, metadata=metadata)
                self.gdrive_kit = gdrive_kit(resources=resources, metadata=metadata)
                
                # Initialize Synapse storage if available and not disabled
                if HAS_SYNAPSE and "synapse" not in disabled_components:
                    self.synapse_storage = synapse_storage(resources=resources, metadata=metadata)
                    self.logger.info("Initialized Synapse storage for Filecoin PDP integration")
                else:
                    self.synapse_storage = None # Initialize to None
                    if "synapse" in disabled_components:
                        self.logger.info("Synapse storage disabled for leecher role")
                        
                # Initialize HuggingFace Hub integration if available
                if HAS_HUGGINGFACE:
                    self.huggingface_kit = huggingface_kit(resources=resources, metadata=metadata)
                else:
                    self.huggingface_kit = None # Initialize to None
                    
                # Initialize ipget component
                self.ipget = ipget(resources=resources, metadata={"role": self.role})
                
                # Initialize Lotus Kit if available and not disabled
                if HAS_LOTUS and "lotus" not in disabled_components:
                    # Auto-start is opted into based on metadata, default to True for leecher role too
                    lotus_metadata = self.metadata.copy()
                    lotus_metadata["auto_start_daemon"] = lotus_metadata.get("auto_start_lotus_daemon", True)
                    self.lotus_kit = lotus_kit(resources=resources, metadata=lotus_metadata)
                    self.logger.info("Initialized Lotus Kit for Filecoin integration")
                else:
                    self.lotus_kit = None # Initialize to None
                    if "lotus" in disabled_components:
                        self.logger.info("Lotus Kit disabled for leecher role")

            elif self.role == "worker":
                # Check for disabled components
                disabled_components = metadata.get("disabled_components", [])
                
                # Worker needs IPFS daemon and cluster-follow
                self.ipfs = ipfs_py(metadata={"role": self.role, "testing": False}) # Explicitly set testing to False
                
                # Initialize cluster-follow if not disabled
                if "ipfs_cluster_follow" not in disabled_components:
                    self.ipfs_cluster_follow = ipfs_cluster_follow(
                        resources=resources,
                        metadata={"role": self.role, "cluster_name": metadata.get("cluster_name")},
                    )
                else:
                    self.ipfs_cluster_follow = None
                    self.logger.info("IPFS Cluster Follow disabled for worker role")
                    
                # Add storage kit for S3 connectivity
                self.s3_kit = s3_kit(resources=resources)
                self.storacha_kit = storacha_kit(resources=resources, metadata=metadata)
                self.gdrive_kit = gdrive_kit(resources=resources, metadata=metadata)
                
                # Initialize Synapse storage if available and not disabled
                if HAS_SYNAPSE and "synapse" not in disabled_components:
                    self.synapse_storage = synapse_storage(resources=resources, metadata=metadata)
                    self.logger.info("Initialized Synapse storage for Filecoin PDP integration")
                else:
                    self.synapse_storage = None # Initialize to None
                    if "synapse" in disabled_components:
                        self.logger.info("Synapse storage disabled for worker role")
                        
                # Initialize HuggingFace Hub integration if available
                if HAS_HUGGINGFACE:
                    self.huggingface_kit = huggingface_kit(resources=resources, metadata=metadata)
                else:
                    self.huggingface_kit = None # Initialize to None
                    
                # Initialize ipget component
                self.ipget = ipget(resources=resources, metadata={"role": self.role})
                
                # Initialize Lotus Kit if available and not disabled
                if HAS_LOTUS and "lotus" not in disabled_components:
                    # Auto-start is opted into based on metadata, default to True for worker role too
                    lotus_metadata = self.metadata.copy()
                    lotus_metadata["auto_start_daemon"] = lotus_metadata.get("auto_start_lotus_daemon", True)
                    self.lotus_kit = lotus_kit(resources=resources, metadata=lotus_metadata)
                    self.logger.info("Initialized Lotus Kit for Filecoin integration")
                else:
                    self.lotus_kit = None # Initialize to None
                    if "lotus" in disabled_components:
                        self.logger.info("Lotus Kit disabled for worker role")

            elif self.role == "master":
                # Check for disabled components
                disabled_components = metadata.get("disabled_components", [])
                
                # Master needs IPFS daemon, cluster-service, and cluster-ctl
                self.ipfs = ipfs_py(metadata={"role": self.role, "testing": False}) # Explicitly set testing to False
                
                # Initialize cluster service if not disabled
                if "ipfs_cluster" not in disabled_components:
                    self.ipfs_cluster_service = ipfs_cluster_service(
                        resources=resources, metadata={"role": self.role}
                    )
                    self.ipfs_cluster_ctl = ipfs_cluster_ctl(
                        resources=resources, metadata={"role": self.role}
                    )
                else:
                    self.ipfs_cluster_service = None
                    self.ipfs_cluster_ctl = None
                    self.logger.info("IPFS Cluster service and ctl disabled for master role")
                    
                # Add storage kit for S3 connectivity
                self.s3_kit = s3_kit(resources=resources)
                self.storacha_kit = storacha_kit(resources=resources, metadata=metadata)
                self.gdrive_kit = gdrive_kit(resources=resources, metadata=metadata)
                
                # Initialize Synapse storage if available and not disabled
                if HAS_SYNAPSE and "synapse" not in disabled_components:
                    self.synapse_storage = synapse_storage(resources=resources, metadata=metadata)
                    self.logger.info("Initialized Synapse storage for Filecoin PDP integration")
                else:
                    self.synapse_storage = None # Initialize to None
                    if "synapse" in disabled_components:
                        self.logger.info("Synapse storage disabled for master role")
                        
                # Initialize HuggingFace Hub integration if available
                if HAS_HUGGINGFACE:
                    self.huggingface_kit = huggingface_kit(resources=resources, metadata=metadata)
                else:
                    self.huggingface_kit = None # Initialize to None
                    
                # Initialize ipget component
                self.ipget = ipget(resources=resources, metadata={"role": self.role})
                
                # Initialize Lotus Kit if available and not disabled
                if HAS_LOTUS and "lotus" not in disabled_components:
                    # Auto-start is opted into based on metadata, but default to true for master role
                    lotus_metadata = self.metadata.copy()
                    lotus_metadata["auto_start_daemon"] = lotus_metadata.get("auto_start_lotus_daemon", True)
                    self.lotus_kit = lotus_kit(resources=resources, metadata=lotus_metadata)
                    self.logger.info("Initialized Lotus Kit for Filecoin integration")
                else:
                    self.lotus_kit = None # Initialize to None
                    if "lotus" in disabled_components:
                        self.logger.info("Lotus Kit disabled for master role")

        # Initialize monitoring components
        self.monitoring = None
        self.dashboard = None
        self.observability = None # Initialize observability API
        self.performance_metrics = None # Initialize performance metrics tracker
        enable_monitoring = metadata.get("enable_monitoring", False) if metadata else False

        # Initialize knowledge graph components
        self.knowledge_graph = None
        self.graph_query = None
        self.graph_rag = None
        enable_knowledge_graph = (
            metadata.get("enable_knowledge_graph", False) if metadata else False
        )

        # Initialize AI/ML integration components
        self.model_registry = None
        self.dataset_manager = None
        self.langchain_integration = None
        self.llama_index_integration = None
        self.distributed_training = None
        enable_ai_ml = metadata.get("enable_ai_ml", False) if metadata else False

        # Initialize IPLD extension components
        self.ipld_extension = None
        enable_ipld = metadata.get("enable_ipld", False) if metadata else False

        # Initialize libp2p peer if enabled
        self.libp2p = None
        
        # Check if libp2p is enabled and try to initialize it if so
        if enable_libp2p:
            # Try to import libp2p directly to check availability
            try:
                import libp2p
                libp2p_installed = True
            except ImportError:
                libp2p_installed = False
                
            # Only attempt setup if it's actually installed
            if libp2p_installed:
                self._setup_libp2p(resources, metadata)
            else:
                self.logger.warning("libp2p package is not installed. Skipping initialization.")
                self.logger.info(
                    "To enable libp2p direct P2P communication, install from GitHub main: "
                    "pip install 'libp2p @ git+https://github.com/libp2p/py-libp2p.git@main'"
                )

        # Initialize cluster management if enabled
        self.cluster_manager = None
        if enable_cluster_management and HAS_CLUSTER_MANAGEMENT:
            self._setup_cluster_management(resources, metadata)
        elif enable_cluster_management and not HAS_CLUSTER_MANAGEMENT:
            self.logger.warning("Cluster management is not available. Skipping initialization.")
            self.logger.info(
                "To enable cluster management, make sure the cluster package components are available."
            )

        # Initialize Arrow-based metadata index if enabled
        if enable_metadata_index and HAS_ARROW_INDEX:
            self._setup_metadata_index(resources, metadata)
        elif enable_metadata_index and not HAS_ARROW_INDEX:
            self.logger.warning("Arrow metadata index is not available. Skipping initialization.")
            self.logger.info(
                "To enable the metadata index, make sure PyArrow is installed and arrow_metadata_index.py is available."
            )

        # Initialize monitoring components if enabled
        if enable_monitoring and HAS_MONITORING:
            self._setup_monitoring(resources, metadata)
        elif enable_monitoring and not HAS_MONITORING:
            self.logger.warning("Monitoring is not available. Skipping initialization.")
            self.logger.info("To enable monitoring, make sure cluster_monitoring.py is available.")

        # Initialize knowledge graph components if enabled
        if enable_knowledge_graph and HAS_KNOWLEDGE_GRAPH:
            self._setup_knowledge_graph(resources, metadata)
        elif enable_knowledge_graph and not HAS_KNOWLEDGE_GRAPH:
            self.logger.warning("Knowledge graph is not available. Skipping initialization.")
            self.logger.info(
                "To enable knowledge graph, make sure ipld_knowledge_graph.py is available."
            )

        # Initialize AI/ML integration components if enabled
        if enable_ai_ml and HAS_AI_ML_INTEGRATION:
            self._setup_ai_ml_integration(resources, metadata)
        elif enable_ai_ml and not HAS_AI_ML_INTEGRATION:
            self.logger.warning("AI/ML integration is not available. Skipping initialization.")
            self.logger.info(
                "To enable AI/ML integration, make sure ai_ml_integration.py is available."
            )

        # Start all required daemons based on role if auto-start is enabled
        if self.auto_start_daemons:
            self._start_required_daemons()

        # Initialize program state manager for tracking system state
        try:
            self.program_state = get_program_state_manager()
            self.logger.info("Program state manager initialized")
            
            # Initialize state with basic information
            self.program_state.update_system_state(
                ipfs_version=getattr(self.ipfs, 'version', ''),
                last_updated=time.time()
            )
        except Exception as e:
            self.logger.warning(f"Failed to initialize program state manager: {e}")
            self.program_state = None

    def _setup_cluster_management(self, resources=None, metadata=None):
        """Set up the cluster management component with standardized error handling."""
        try:
            self.logger.info("Setting up cluster management...")
            import socket

            node_id = (
                metadata.get("node_id")
                if metadata and "node_id" in metadata
                else socket.gethostname()
            )
            peer_id = None
            if hasattr(self, "libp2p") and self.libp2p:
                try:
                    peer_id = self.libp2p.get_peer_id()
                except Exception as e:
                    self.logger.warning(f"Failed to get peer ID from libp2p: {str(e)}")
            if not peer_id and hasattr(self, "ipfs"):
                try:
                    id_result = self.ipfs.ipfs_id() # type: ignore
                    if id_result.get("success", False) and "ID" in id_result:
                        peer_id = id_result["ID"]
                except Exception as e:
                    self.logger.warning(f"Failed to get peer ID from IPFS: {str(e)}")
            if not peer_id:
                import uuid

                peer_id = f"peer-{uuid.uuid4()}"
                self.logger.warning(f"Using generated peer ID: {peer_id}")
            config = self.config.copy() if hasattr(self, "config") else {}
            if metadata and "cluster_id" in metadata:
                config["cluster_id"] = metadata["cluster_id"]
            elif "cluster_id" not in config:
                config["cluster_id"] = "default"
            if not resources:
                resources = {}
            try:
                import psutil

                if "cpu_count" not in resources:
                    resources["cpu_count"] = psutil.cpu_count(logical=True)
                if "cpu_usage" not in resources:
                    resources["cpu_percent"] = psutil.cpu_percent(interval=0.1)
                if "memory_total" not in resources:
                    resources["memory_total"] = psutil.virtual_memory().total
                if "memory_available" not in resources:
                    resources["memory_available"] = psutil.virtual_memory().available
                if "disk_total" not in resources:
                    resources["disk_total"] = psutil.disk_usage("/").total
                if "disk_free" not in resources:
                    resources["disk_free"] = psutil.disk_usage("/").free
                if "gpu_count" not in resources and "gpu_available" not in resources:
                    try:
                        gpu_info = self._get_gpu_info()  # Assuming _get_gpu_info exists
                        if gpu_info:
                            resources.update(gpu_info)
                    except Exception as e:
                        self.logger.debug(f"Failed to get GPU information: {str(e)}")
            except ImportError:
                self.logger.warning("psutil not available, using default resource values")
                if "cpu_count" not in resources:
                    resources["cpu_count"] = 1
                if "memory_total" not in resources:
                    resources["memory_total"] = 1024 * 1024 * 1024
                if "memory_available" not in resources:
                    resources["memory_available"] = 512 * 1024 * 1024
                if "disk_total" not in resources:
                    resources["disk_total"] = 10 * 1024 * 1024 * 1024
                if "disk_free" not in resources:
                    resources["disk_free"] = 5 * 1024 * 1024 * 1024
            except Exception as e:
                self.logger.warning(f"Error getting system resources: {str(e)}")

            self.cluster_manager = ClusterManager( # type: ignore
                node_id=node_id,
                role=self.role,
                peer_id=peer_id,
                config=config,
                resources=resources,
                metadata=metadata,
                enable_libp2p=hasattr(self, "libp2p") and self.libp2p is not None,
            )
            result = self.cluster_manager.start()
            if not result.get("success", False): # type: ignore
                self.logger.error(f"Failed to start cluster manager: {result}")
                return False
            self.logger.info("Cluster management setup complete")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set up cluster management: {str(e)}")
            return False

    def _setup_metadata_index(self, resources=None, metadata=None):
        """Set up the Arrow-based metadata index component."""
        from .error import create_result_dict, handle_error

        result = create_result_dict("setup_metadata_index")
        try:
            index_dir = self.metadata.get("metadata_index_dir") if self.metadata else None
            partition_size = self.metadata.get("metadata_partition_size") if self.metadata else None
            sync_interval = self.metadata.get("metadata_sync_interval", 300) if self.metadata else 300
            auto_sync = self.metadata.get("metadata_auto_sync", True) if self.metadata else True
            cluster_id = self.metadata.get("cluster_name") if self.metadata else None
            if not cluster_id and hasattr(self, "config") and "cluster_id" in self.config:
                cluster_id = self.config["cluster_id"]

            self._metadata_index = ArrowMetadataIndex( # type: ignore
                index_dir=index_dir,
                role=self.role,
                partition_size=partition_size,
                ipfs_client=self.ipfs,
            )
            if self.role in ("master", "worker"):
                node_id = self.ipfs.get_node_id() if hasattr(self.ipfs, "get_node_id") else None # type: ignore
                self._metadata_sync_handler = MetadataSyncHandler( # type: ignore
                    index=self._metadata_index,
                    ipfs_client=self.ipfs,
                    cluster_id=cluster_id,
                    node_id=node_id,
                )
                if auto_sync:
                    self._metadata_sync_handler.start(sync_interval=sync_interval)
            result["success"] = True # type: ignore
            result["metadata_index_enabled"] = True # type: ignore
            result["auto_sync"] = auto_sync # type: ignore
            self.logger.info(f"Arrow metadata index enabled. Auto-sync: {auto_sync}")
        except Exception as e:
            handle_error(result, e, "Failed to initialize Arrow metadata index")
            self.logger.error(f"Error initializing Arrow metadata index: {str(e)}")
        return result

    def _start_required_daemons(self):
        """Start all required daemon processes based on the node's role.

        Initializes and starts the appropriate daemon processes according to
        the configured node role (master, worker, or leecher).

        Returns:
            bool: True if all required daemons were started successfully, False otherwise.
        """
        self.logger.info(f"Starting required daemons for role: {self.role}")

        # Ensure all daemons are properly configured before starting
        try:
            from .daemon_config_manager import DaemonConfigManager
            self.daemon_manager = DaemonConfigManager(self)
            config_result = self.daemon_manager.check_and_configure_all_daemons()
            if not config_result.get('success', False): # type: ignore
                self.logger.warning('Some daemon configurations failed, but continuing...')
                error_summary = []
                if 'errors' in config_result:
                    error_summary.extend(config_result['errors'])
                if 'daemon_results' in config_result:
                    for daemon, result in config_result['daemon_results'].items():
                        if not result.get('success', False):
                            error_summary.append(f"{daemon}: {result.get('message', 'Unknown error')}")
                summary = '; '.join(error_summary) if error_summary else 'Configuration issues detected'
                self.logger.warning(f'Config summary: {summary}')
            else:
                self.logger.info('All daemon configurations validated successfully')
                if config_result.get('all_configured', False):
                    self.logger.info('All required daemons are properly configured')
        except Exception as config_error:
            self.logger.warning(f'Daemon configuration check failed: {config_error}')
            self.logger.warning('Continuing with daemon startup...')


        try:
            # All roles need the IPFS daemon
            if hasattr(self, 'ipfs'):
                # Use the appropriate method based on what's available
                if hasattr(self.ipfs, 'daemon_start'):
                    ipfs_result = self.ipfs.daemon_start() # type: ignore
                else:
                    # If daemon_start is not available, try using add() as a test to ensure daemon is running
                    self.logger.warning("daemon_start method not found on ipfs object, attempting alternate checks")
                    ipfs_result = {"success": False, "error": "No daemon start method available"}
                    # Try to run a simple command to see if daemon is running or start it with system commands
                    try:
                        # First check if daemon is already running
                        if hasattr(self.ipfs, 'run_ipfs_command'):
                            test_result = self.ipfs.run_ipfs_command(["ipfs", "id"])
                            if test_result.get("success", False): # type: ignore
                                ipfs_result = {"success": True, "status": "already_running"}
                        else:
                            # Try enhanced daemon manager
                            from .enhanced_daemon_manager import EnhancedDaemonManager
                            manager = EnhancedDaemonManager(ipfs_path=getattr(self, "ipfs_path", None))
                            start_result = manager.start_daemon(detach=True, init_if_needed=True)
                            status = start_result.get("status")
                            if status in ("started", "already_running"):
                                ipfs_result = {"success": True, "status": status}
                            else:
                                ipfs_result = {"success": False, "error": start_result.get("message", "Failed to start IPFS daemon")}
                    except Exception as e:
                        self.logger.error(f"Alternate daemon check failed: {str(e)}")
                    
                if not ipfs_result.get("success", False): # type: ignore
                    self.logger.error(f"Failed to start IPFS daemon: {ipfs_result.get('error', 'Unknown error')}") # type: ignore
                else:
                    self.logger.info(f"IPFS daemon started successfully: {ipfs_result.get('status', 'running')}") # type: ignore
                    
            # Start Lotus daemon if available and auto-start is configured and not disabled
            disabled_components = self.metadata.get("disabled_components", [])
            
            if hasattr(self, 'lotus_kit') and self.lotus_kit is not None and "lotus" not in disabled_components:
                # Check if auto-start is enabled for lotus daemon
                should_start_lotus = False
                if hasattr(self.lotus_kit, 'auto_start_daemon'):
                    should_start_lotus = self.lotus_kit.auto_start_daemon # type: ignore
                
                if should_start_lotus:
                    lotus_result = self.lotus_kit.daemon_start() # type: ignore
                    if not lotus_result.get("success", False): # type: ignore
                        self.logger.error(f"Failed to start Lotus daemon: {lotus_result.get('error', 'Unknown error')}") # type: ignore
                    else:
                        self.logger.info(f"Lotus daemon started successfully: {lotus_result.get('status', 'running')}") # type: ignore
            elif "lotus" in disabled_components:
                self.logger.info("Lotus daemon startup skipped - disabled for this role")

            # Master role needs IPFS Cluster Service (if not disabled)
            if self.role == "master" and hasattr(self, 'ipfs_cluster_service') and self.ipfs_cluster_service is not None and "ipfs_cluster" not in disabled_components:
                cluster_service_result = self.ipfs_cluster_service.ipfs_cluster_service_start() # type: ignore
                if not cluster_service_result.get("success", False): # type: ignore
                    self.logger.error(f"Failed to start IPFS Cluster Service: {cluster_service_result.get('error', 'Unknown error')}") # type: ignore
                else:
                    self.logger.info("IPFS Cluster Service started successfully")
            elif self.role == "master" and "ipfs_cluster" in disabled_components:
                self.logger.info("IPFS Cluster Service startup skipped - disabled for this role")

            # Worker role needs IPFS Cluster Follow (if not disabled)
            if self.role == "worker" and hasattr(self, 'ipfs_cluster_follow') and self.ipfs_cluster_follow is not None and "ipfs_cluster_follow" not in disabled_components:
                # Get cluster name from metadata
                cluster_name = None
                if hasattr(self, "cluster_name"):
                    cluster_name = self.cluster_name
                elif hasattr(self, "metadata") and "cluster_name" in self.metadata:
                    cluster_name = self.metadata["cluster_name"]

                if cluster_name:
                    cluster_follow_result = self.ipfs_cluster_follow.ipfs_follow_start(cluster_name=cluster_name) # type: ignore
                    if not cluster_follow_result.get("success", False): # type: ignore
                        self.logger.error(f"Failed to start IPFS Cluster Follow: {cluster_follow_result.get('error', 'Unknown error')}") # type: ignore
                    else:
                        self.logger.info("IPFS Cluster Follow started successfully")
                else:
                    self.logger.error("Cannot start IPFS Cluster Follow: No cluster name provided")
            elif self.role == "worker" and "ipfs_cluster_follow" in disabled_components:
                self.logger.info("IPFS Cluster Follow startup skipped - disabled for this role")

            # Verify daemon status
            status = self.check_daemon_status()
            if status.get("success", False): # type: ignore
                daemon_status = status.get("daemons", {}) # type: ignore
                all_running = all(daemon.get("running", False) for daemon in daemon_status.values())
                if all_running:
                    self.logger.info("All required daemons are running")
                    
                    # Start background state updates if program state is available
                    if hasattr(self, 'program_state') and self.program_state is not None:
                        self._start_background_state_updates()
                    
                    return {
                        'success': True,
                        'message': 'All required daemons are running',
                        'status': self.daemon_manager.get_detailed_status_report() if self.daemon_manager else {}
                    }
                else:
                    # List daemons that aren't running
                    not_running = [name for name, info in daemon_status.items() if not info.get("running", False)]
                    self.logger.warning(f"Not all daemons are running. Non-running daemons: {', '.join(not_running)}")
                    return {
                        'success': False,
                        'message': f"Not all daemons are running: {', '.join(not_running)}",
                        'not_running': not_running,
                        'status': self.daemon_manager.get_detailed_status_report() if self.daemon_manager else {}
                    }
            else:
                self.logger.warning("Could not verify daemon status")
                return {
                    'success': False,
                    'message': 'Could not verify daemon status',
                    'status': {}
                }

        except Exception as e:
            self.logger.error(f"Error starting daemons: {str(e)}")
            return {
                'success': False,
                'message': f'Error starting daemons: {str(e)}',
                'error': str(e),
                'status': {}
            }

    def check_daemon_status(self):
        """Check the status of all daemon processes required for this node's role.

        Returns:
            dict: A dictionary containing status information for all daemons.
        """
        from .error import create_result_dict

        result = create_result_dict("check_daemon_status")
        result["daemons"] = {}

        try:
            # Check IPFS daemon
            if hasattr(self, 'ipfs'):
                ipfs_running = False
                
                # First attempt: try ipfs id as a direct check
                try:
                    id_result = self.ipfs.run_ipfs_command(["id"]) # type: ignore
                    if id_result.get("success", False): # type: ignore
                        ipfs_running = True
                        self.logger.debug("IPFS daemon detected as running using 'ipfs id' command")
                except Exception as e:
                    self.logger.debug(f"Error checking IPFS daemon with 'ipfs id': {str(e)}")
                
                # Second attempt: use ps command if the first attempt fails
                if not ipfs_running:
                    try:
                        ps_result = self.ipfs.run_ipfs_command(["ps", "-ef"]) # type: ignore
                        if ps_result.get("success", False) and "stdout" in ps_result: # type: ignore
                            # Look for ipfs daemon process
                            for line in ps_result["stdout"].splitlines(): # type: ignore
                                if "ipfs daemon" in line and "grep" not in line:
                                    ipfs_running = True
                                    self.logger.debug("IPFS daemon detected as running using 'ps' command")
                                    break
                    except Exception as e:
                        self.logger.debug(f"Error checking IPFS daemon with 'ps': {str(e)}")
                
                # Third attempt: direct process check
                if not ipfs_running:
                    try:
                        import subprocess
                        if os.name == "nt":
                            try:
                                import psutil
                                for proc in psutil.process_iter(["name", "cmdline"]):
                                    name = (proc.info.get("name") or "").lower()
                                    cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                                    if "ipfs" in name and "daemon" in cmdline:
                                        ipfs_running = True
                                        self.logger.debug("IPFS daemon detected as running using psutil")
                                        break
                            except Exception as e:
                                self.logger.debug(f"Error checking IPFS daemon with psutil: {str(e)}")
                        else:
                            # Try using 'pgrep' to find daemon on Unix-like systems
                            pgrep_result = subprocess.run(
                                ["pgrep", "-f", "ipfs daemon"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=False
                            )
                            if pgrep_result.returncode == 0 and pgrep_result.stdout.strip():
                                ipfs_running = True
                                self.logger.debug("IPFS daemon detected as running using 'pgrep' command")
                    except Exception as e:
                        self.logger.debug(f"Error checking IPFS daemon with direct process check: {str(e)}")

                result["daemons"]["ipfs"] = {
                    "running": ipfs_running,
                    "type": "ipfs_daemon"
                }

            # Check IPFS Cluster Service (master only)
            if self.role == "master" and hasattr(self, 'ipfs_cluster_service'):
                ps_result = self.ipfs_cluster_service.run_cluster_service_command(["ps", "-ef"]) # type: ignore
                cluster_running = False

                if ps_result.get("success", False) and "stdout" in ps_result: # type: ignore
                    # Look for ipfs-cluster-service daemon process
                    for line in ps_result["stdout"].splitlines(): # type: ignore
                        if "ipfs-cluster-service daemon" in line and "grep" not in line:
                            cluster_running = True
                            break

                result["daemons"]["ipfs_cluster_service"] = {
                    "running": cluster_running,
                    "type": "cluster_service"
                }

            # Check IPFS Cluster Follow (worker only)
            if self.role == "worker" and hasattr(self, 'ipfs_cluster_follow'):
                ps_result = self.ipfs_cluster_follow.run_cluster_follow_command(["ps", "-ef"]) # type: ignore
                follow_running = False

                if ps_result.get("success", False) and "stdout" in ps_result: # type: ignore
                    # Look for ipfs-cluster-follow process
                    for line in ps_result["stdout"].splitlines(): # type: ignore
                        if "ipfs-cluster-follow" in line and "grep" not in line:
                            follow_running = True
                            break

                result["daemons"]["ipfs_cluster_follow"] = {
                    "running": follow_running,
                    "type": "cluster_follow"
                }
                
            # Check Lotus daemon if available
            if hasattr(self, 'lotus_kit'):
                lotus_status = self.lotus_kit.daemon_status() # type: ignore
                
                # Extract information from the lotus daemon status
                lotus_running = lotus_status.get("process_running", False)
                lotus_pid = lotus_status.get("pid", None)
                lotus_api_ready = lotus_status.get("api_ready", False)
                
                result["daemons"]["lotus"] = {
                    "running": lotus_running,
                    "type": "lotus_daemon",
                    "pid": lotus_pid,
                    "api_ready": lotus_api_ready
                }

            result["success"] = True # type: ignore
            return result
        except Exception as e:
            result["success"] = False # type: ignore
            result["error"] = str(e) # type: ignore
            result["error_type"] = type(e).__name__ # type: ignore
            self.logger.error(f"Error checking daemon status: {str(e)}")
            return result

    def stop_daemons(self):
        """Stop all running daemon processes.

        Returns:
            dict: A dictionary containing the results of stopping each daemon.
        """
        from .error import create_result_dict

        result = create_result_dict("stop_daemons")
        result["stopped"] = {}

        try:
            # Stop in reverse order of starting

            # Stop IPFS Cluster Follow (worker only)
            if self.role == "worker" and hasattr(self, 'ipfs_cluster_follow'):
                cluster_name = None
                if hasattr(self, "cluster_name"):
                    cluster_name = self.cluster_name
                elif hasattr(self, "metadata") and "cluster_name" in self.metadata:
                    cluster_name = self.metadata["cluster_name"]

                if cluster_name:
                    follow_stopped = self.ipfs_cluster_follow.ipfs_follow_stop(cluster_name=cluster_name) # type: ignore
                    result["stopped"]["ipfs_cluster_follow"] = follow_stopped # type: ignore
                    self.logger.info(f"IPFS Cluster Follow stopped: {follow_stopped.get('success', False)}") # type: ignore

            # Stop IPFS Cluster Service (master only)
            if self.role == "master" and hasattr(self, 'ipfs_cluster_service'):
                service_stopped = self.ipfs_cluster_service.ipfs_cluster_service_stop() # type: ignore
                result["stopped"]["ipfs_cluster_service"] = service_stopped # type: ignore
                self.logger.info(f"IPFS Cluster Service stopped: {service_stopped.get('success', False)}") # type: ignore
                
            # Stop Lotus daemon if available (lotus should be stopped before IPFS)
            if hasattr(self, 'lotus_kit'):
                lotus_stopped = self.lotus_kit.daemon_stop() # type: ignore
                result["stopped"]["lotus"] = lotus_stopped # type: ignore
                self.logger.info(f"Lotus daemon stopped: {lotus_stopped.get('success', False)}") # type: ignore

            # Stop IPFS daemon (all roles)
            if hasattr(self, 'ipfs'):
                ipfs_stopped = self.ipfs.daemon_stop() # type: ignore
                result["stopped"]["ipfs"] = ipfs_stopped # type: ignore
                self.logger.info(f"IPFS daemon stopped: {ipfs_stopped.get('success', False)}") # type: ignore

            result["success"] = True # type: ignore
            return result
        except Exception as e:
            result["success"] = False # type: ignore
            result["error"] = str(e) # type: ignore
            result["error_type"] = type(e).__name__ # type: ignore
            self.logger.error(f"Error stopping daemons: {str(e)}")
            return result

    def initialize(self, start_daemons=True):
        """
        Initialize the SDK and ensure all required daemons are running.

        This is a convenience method to ensure the SDK is fully initialized and ready for use.
        It will start all required daemons based on the node's role if start_daemons is True.

        Args:
            start_daemons (bool): Whether to start the daemons automatically

        Returns:
            dict: Result dictionary with initialization status and daemon information
        """
        from .error import create_result_dict

        result = create_result_dict("initialize")
        result["daemons_started"] = [] # type: ignore
        result["daemons_status"] = {} # type: ignore

        try:
            # If auto-start is enabled, start required daemons
            if start_daemons:
                self.auto_start_daemons = True
                daemon_result = self._start_required_daemons()
                result["daemons_started_result"] = daemon_result # type: ignore

            # Check status of all daemons
            status_result = self.check_daemon_status()
            result["daemons_status"] = status_result.get("daemons", {}) # type: ignore

            # Overall success if all required daemons are running or if we're not starting daemons
            all_running = all(daemon.get("running", False) for daemon in result["daemons_status"].values()) # type: ignore
            result["all_daemons_running"] = all_running # type: ignore

            if start_daemons and not all_running:
                result["success"] = False # type: ignore
                result["error"] = "Not all required daemons are running after initialization" # type: ignore
            else:
                result["success"] = True # type: ignore

            return result
        except Exception as e:
            result["success"] = False # type: ignore
            result["error"] = str(e) # type: ignore
            result["error_type"] = type(e).__name__ # type: ignore
            self.logger.error(f"Error initializing SDK: {str(e)}")
            return result

    def _ensure_daemon_running(self, daemon_type="ipfs"):
        """
        Ensures a specific daemon is running, starting it if necessary and if auto_start_daemons is True.

        Args:
            daemon_type (str): Type of daemon to check ("ipfs", "ipfs_cluster_service", "ipfs_cluster_follow", or "lotus")

        Returns:
            dict: Result dictionary with success status and error information if applicable
        """
        from .error import create_result_dict

        result = create_result_dict(f"ensure_{daemon_type}_running")

        try:
            # Check current daemon status
            daemon_status = self.check_daemon_status()
            if not daemon_status.get("success", False): # type: ignore
                result["success"] = False # type: ignore
                result["error"] = "Failed to check daemon status" # type: ignore
                result["original_error"] = daemon_status.get("error") # type: ignore
                return result

            # Check if the requested daemon is running
            is_running = daemon_status.get("daemons", {}).get(daemon_type, {}).get("running", False) # type: ignore
            result["was_running"] = is_running # type: ignore

            if is_running:
                result["success"] = True # type: ignore
                result["message"] = f"{daemon_type} daemon already running" # type: ignore
                return result

            # Daemon is not running, check if we should auto-start it
            if not self.auto_start_daemons:
                result["success"] = False # type: ignore
                result["error"] = f"{daemon_type} daemon is not running and auto_start_daemons is disabled" # type: ignore
                return result

            # Check if the daemon type is disabled
            disabled_components = self.metadata.get("disabled_components", [])
            if disabled_components:
                # Map daemon types to component names
                daemon_to_component = {
                    "ipfs_cluster_service": "ipfs_cluster",
                    "ipfs_cluster_follow": "ipfs_cluster_follow", 
                    "lotus": "lotus"
                }
                
                component_name = daemon_to_component.get(daemon_type)
                if component_name and component_name in disabled_components:
                    result["success"] = False # type: ignore
                    result["error"] = f"{daemon_type} daemon startup disabled - component '{component_name}' is disabled for this role" # type: ignore
                    self.logger.info(f"Skipping {daemon_type} daemon startup - disabled for this role")
                    return result

            # Start the requested daemon
            self.logger.info(f"{daemon_type} daemon not running, attempting to start it automatically")

            if daemon_type == "ipfs" and hasattr(self, "ipfs"):
                start_result = self.ipfs.daemon_start() # type: ignore
            elif daemon_type == "ipfs_cluster_service" and hasattr(self, "ipfs_cluster_service"):
                start_result = self.ipfs_cluster_service.ipfs_cluster_service_start() # type: ignore
            elif daemon_type == "ipfs_cluster_follow" and hasattr(self, "ipfs_cluster_follow"):
                # Need cluster name for this one
                cluster_name = None
                if hasattr(self, "cluster_name"):
                    cluster_name = self.cluster_name
                elif hasattr(self, "metadata") and "cluster_name" in self.metadata:
                    cluster_name = self.metadata["cluster_name"]

                if not cluster_name:
                    result["success"] = False # type: ignore
                    result["error"] = "Cannot start IPFS Cluster Follow: No cluster name provided" # type: ignore
                    return result

                start_result = self.ipfs_cluster_follow.ipfs_follow_start(cluster_name=cluster_name) # type: ignore
            elif daemon_type == "lotus" and hasattr(self, "lotus_kit"):
                # Start Lotus daemon
                start_result = self.lotus_kit.daemon_start() # type: ignore
            else:
                result["success"] = False # type: ignore
                result["error"] = f"Unknown daemon type '{daemon_type}' or component not initialized" # type: ignore
                return result

            if not start_result.get("success", False): # type: ignore
                result["success"] = False # type: ignore
                result["error"] = f"Failed to start {daemon_type} daemon" # type: ignore
                result["start_result"] = start_result # type: ignore
                return result

            # Daemon started successfully
            result["success"] = True # type: ignore
            result["message"] = f"{daemon_type} daemon started automatically" # type: ignore
            result["start_result"] = start_result # type: ignore
            return result

        except Exception as e:
            result["success"] = False # type: ignore
            result["error"] = str(e) # type: ignore
            result["error_type"] = type(e).__name__ # type: ignore
            self.logger.error(f"Error ensuring {daemon_type} daemon is running: {str(e)}")
            return result

    def get_metadata_index(self, index_dir=None, **kwargs):
        """Get or initialize the Arrow-based metadata index.

        Args:
            index_dir: Directory to store the index files (overrides any previously set path)
            **kwargs: Additional configuration options for the index

        Returns:
            Initialized ArrowMetadataIndex instance
        """
        from .error import create_result_dict, handle_error

        result = create_result_dict("setup_metadata_index")
        try:
            index_dir = self.metadata.get("metadata_index_dir") if self.metadata else None
            partition_size = self.metadata.get("metadata_partition_size") if self.metadata else None
            sync_interval = self.metadata.get("metadata_sync_interval", 300) if self.metadata else 300
            auto_sync = self.metadata.get("metadata_auto_sync", True) if self.metadata else True
            cluster_id = self.metadata.get("cluster_name") if self.metadata else None
            if not cluster_id and hasattr(self, "config") and "cluster_id" in self.config:
                cluster_id = self.config["cluster_id"]

            self._metadata_index = ArrowMetadataIndex( # type: ignore
                index_dir=index_dir,
                role=self.role,
                partition_size=partition_size,
                ipfs_client=self.ipfs,
            )
            if self.role in ("master", "worker"):
                node_id = self.ipfs.get_node_id() if hasattr(self.ipfs, "get_node_id") else None # type: ignore
                self._metadata_sync_handler = MetadataSyncHandler( # type: ignore
                    index=self._metadata_index,
                    ipfs_client=self.ipfs,
                    cluster_id=cluster_id,
                    node_id=node_id,
                )
                if auto_sync:
                    self._metadata_sync_handler.start(sync_interval=sync_interval)
            result["success"] = True # type: ignore
            result["metadata_index_enabled"] = True # type: ignore
            result["auto_sync"] = auto_sync # type: ignore
            self.logger.info(f"Arrow metadata index enabled. Auto-sync: {auto_sync}")
        except Exception as e:
            handle_error(result, e, "Failed to initialize Arrow metadata index")
            self.logger.error(f"Error initializing Arrow metadata index: {str(e)}")
        return result

    def sync_metadata_index(self, **kwargs):
        """Synchronize the metadata index with peers.

        Args:
            **kwargs: Additional options for synchronization

        Returns:
            Dictionary with synchronization results
        """
        from .error import create_result_dict, handle_error

        result = create_result_dict("sync_metadata_index")

        try:
            # Ensure index is initialized
            if self._metadata_index is None:
                self.get_metadata_index(**kwargs)

            # Ensure sync handler is available
            if self._metadata_sync_handler is None:
                result["success"] = False # type: ignore
                result["error"] = "Metadata sync handler not initialized" # type: ignore
                return result

            # Perform synchronization
            sync_result = self._metadata_sync_handler.sync_with_all_peers() # type: ignore
            result.update(sync_result) # type: ignore
            return result

        except Exception as e:
            handle_error(result, e, "Failed to synchronize metadata index")
            self.logger.error(f"Error synchronizing metadata index: {str(e)}")
            return result

    def publish_metadata_index(self, **kwargs):
        """Publish the metadata index to IPFS DAG.

        Args:
            **kwargs: Additional options for publishing

        Returns:
            Dictionary with publishing results
        """
        from .error import create_result_dict, handle_error

        result = create_result_dict("publish_metadata_index")

        try:
            # Ensure index is initialized
            if self._metadata_index is None:
                self.get_metadata_index(**kwargs)

            # Publish the index
            publish_result = self._metadata_index.publish_index_dag() # type: ignore
            result.update(publish_result) # Corrected from `publish`
            return result

        except Exception as e:
            handle_error(result, e, "Failed to publish metadata index")
            self.logger.error(f"Error publishing metadata index: {str(e)}")
            return result

    def get_cluster_status(self, **kwargs):
        """Get comprehensive status information about the cluster."""
        operation = "get_cluster_status"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if not hasattr(self, "cluster_manager") or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
            status = self.cluster_manager.get_cluster_status() # type: ignore
            result.update(status) # type: ignore
            result["success"] = status.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def submit_cluster_task(self, task_type, payload, priority=1, timeout=None, **kwargs):
        """Submit a task to the cluster for distributed processing."""
        operation = "submit_cluster_task"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if not hasattr(self, "cluster_manager") or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
            if not task_type:
                return handle_error(result, IPFSValidationError("Task type must be specified"))
            if not isinstance(payload, dict):
                return handle_error(result, IPFSValidationError("Payload must be a dictionary"))
            task_result = self.cluster_manager.submit_task( # type: ignore
                task_type=task_type, payload=payload, priority=priority, timeout=timeout
            )
            result.update(task_result) # type: ignore
            result["success"] = task_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def get_task_status(self, task_id, **kwargs):
        """Get the status of a submitted cluster task."""
        operation = "get_task_status"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if not hasattr(self, "cluster_manager") or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
            if not task_id:
                return handle_error(result, IPFSValidationError("Task ID must be specified"))
            status_result = self.cluster_manager.get_task_status(task_id) # type: ignore
            result.update(status_result) # type: ignore
            result["success"] = True # type: ignore
            result["task_id"] = task_id # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def _setup_libp2p(self, resources=None, metadata=None):
        """Set up the libp2p direct peer-to-peer communication component."""
        try:
            # Check if libp2p is available before importing
            # This prevents circular imports and provides better error messages
            try:
                import libp2p
                libp2p_installed = True
            except ImportError:
                libp2p_installed = False
                
            # Only attempt setup if it's actually installed
            if libp2p_installed:
                try:
                    self.libp2p = IPFSLibp2pPeer( # type: ignore
                        identity_path=libp2p_config.get("identity_path"), # type: ignore
                        bootstrap_peers=libp2p_config.get("bootstrap_peers", []), # type: ignore
                        listen_addrs=libp2p_config.get("listen_addrs"), # type: ignore
                        role=self.role,
                        enable_mdns=libp2p_config.get("enable_mdns", True), # type: ignore
                        enable_hole_punching=libp2p_config.get("enable_hole_punching", False), # type: ignore
                        enable_relay=libp2p_config.get("enable_relay", False), # type: ignore
                        tiered_storage_manager=tiered_storage_manager, # type: ignore
                    )
                    
                    # Start discovery if configured
                    if libp2p_config.get("auto_start_discovery", True): # type: ignore
                        cluster_name = (
                            metadata.get("cluster_name", "ipfs-kit-cluster") # type: ignore
                            if metadata
                            else "ipfs-kit-cluster"
                        )
                        self.libp2p.start_discovery(rendezvous_string=cluster_name) # type: ignore
                        
                    # Enable relay if configured
                    if libp2p_config.get("enable_relay", False): # type: ignore
                        self.libp2p.enable_relay() # type: ignore
                        
                    self.logger.info(f"libp2p peer initialized with ID: {self.libp2p.get_peer_id()}") # type: ignore
                    return True
                    
                except ImportError as e:
                    self.logger.error(f"Failed to create libp2p peer due to missing dependencies: {str(e)}")
                    self.logger.info("Make sure all required libp2p dependencies are installed")
                    return False
        except Exception as e:
            self.logger.error(f"Failed to set up libp2p peer: {str(e)}")
            return False

    def _setup_knowledge_graph(self, resources=None, metadata=None):
        """Set up the IPLD knowledge graph component."""
        try:
            self.logger.info("Setting up IPLD knowledge graph...")
            kg_config = metadata.get("knowledge_graph_config", {}) if metadata else {} # type: ignore
            base_path = kg_config.get("base_path", "~/.ipfs_graph")
            self.knowledge_graph = IPLDGraphDB( # type: ignore
                ipfs_client=self.ipfs,
                base_path=base_path,
                schema_version=kg_config.get("schema_version", "1.0.0"),
            )
            self.graph_query = KnowledgeGraphQuery(self.knowledge_graph) # type: ignore
            embedding_model = kg_config.get("embedding_model")
            self.graph_rag = GraphRAG( # type: ignore
                graph_db=self.knowledge_graph, embedding_model=embedding_model
            )
            if embedding_model:
                self.logger.info("GraphRAG initialized with embedding model")
            else:
                self.logger.info("GraphRAG initialized without embedding model")
            self.logger.info("IPLD knowledge graph setup complete")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set up IPLD knowledge graph: {str(e)}")
            return False

    def _check_libp2p_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call libp2p methods."""
        operation = f"libp2p_{method_name}"
        correlation_id = kwargs.pop("correlation_id", None)
        result = create_result_dict(operation, correlation_id)
        
        # Check if libp2p is installed
        try:
            import libp2p
            libp2p_installed = True
        except ImportError:
            libp2p_installed = False
        
        if not libp2p_installed:
            return handle_error(
                result,
                IPFSError(
                    "libp2p is not available. Install from GitHub main with: "
                    "pip install 'libp2p @ git+https://github.com/libp2p/py-libp2p.git@main'"
                ),
            )
        if self.libp2p is None:
            return handle_error(
                result, IPFSError("libp2p peer is not initialized. Enable with enable_libp2p=True")
            )
        try:
            method = getattr(self.libp2p, method_name, None)
            if method is None:
                return handle_error(
                    result, IPFSError(f"Method {method_name} not found in libp2p peer")
                )
            method_result = method(*args, **kwargs)
            result["success"] = True # type: ignore
            result["data"] = method_result # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    # libp2p direct P2P communication methods
    def libp2p_get_peer_id(self, **kwargs):
        return self._check_libp2p_and_call("get_peer_id", **kwargs)

    def libp2p_get_multiaddrs(self, **kwargs):
        return self._check_libp2p_and_call("get_multiaddrs", **kwargs)

    def libp2p_connect_peer(self, peer_addr, **kwargs):
        return self._check_libp2p_and_call("connect_peer", peer_addr, **kwargs)

    def libp2p_is_connected(self, peer_id, **kwargs):
        return self._check_libp2p_and_call("is_connected_to", peer_id, **kwargs)

    def libp2p_announce_content(self, cid, metadata=None, **kwargs):
        return self._check_libp2p_and_call("announce_content", cid, metadata, **kwargs)

    def libp2p_find_providers(self, cid, count=20, timeout=30, **kwargs):
        return self._check_libp2p_and_call("find_providers", cid, count, timeout, **kwargs)

    def libp2p_request_content(self, cid, timeout=30, **kwargs):
        return self._check_libp2p_and_call("request_content", cid, timeout, **kwargs)

    def libp2p_store_content(self, cid, data, **kwargs):
        return self._check_libp2p_and_call("store_bytes", cid, data, **kwargs)

    def libp2p_start_discovery(self, rendezvous_string="ipfs-kit", **kwargs):
        return self._check_libp2p_and_call("start_discovery", rendezvous_string, **kwargs)

    def libp2p_enable_relay(self, **kwargs):
        return self._check_libp2p_and_call("enable_relay", **kwargs)

    def libp2p_connect_via_relay(self, peer_id, relay_addr, **kwargs):
        return self._check_libp2p_and_call("connect_via_relay", peer_id, relay_addr, **kwargs)

    @auto_retry_on_daemon_failure(daemon_type="ipfs", max_retries=3)
    def ipfs_add(self, file_path, recursive=False, **kwargs):
        """Add content to IPFS.

        Args:
            file_path: Path to the file to add
            recursive: Whether to add directory contents recursively
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information

        Note:
            This method uses auto_retry_on_daemon_failure decorator to automatically
            start the IPFS daemon and retry the operation if it fails due to the
            daemon not running.
        """
        operation = "ipfs_add"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            # Call the ipfs module's implementation
            add_result = self.ipfs.add(file_path, recursive=recursive) # type: ignore
            result.update(add_result) # type: ignore
            result["success"] = add_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    @auto_retry_on_daemon_failure(daemon_type="ipfs", max_retries=3)
    def ipfs_cat(self, cid, **kwargs):
        """Retrieve content from IPFS by CID.

        Args:
            cid: Content identifier to retrieve
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information

        Note:
            This method uses auto_retry_on_daemon_failure decorator to automatically
            start the IPFS daemon and retry the operation if it fails due to the
            daemon not running.
        """
        operation = "ipfs_cat"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            # Call the ipfs module's implementation
            cat_result = self.ipfs.cat(cid) # type: ignore
            result.update(cat_result) # type: ignore
            result["success"] = cat_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    @auto_retry_on_daemon_failure(daemon_type="ipfs", max_retries=3)
    def ipfs_pin_add(self, cid, recursive=True, **kwargs):
        """Pin content by CID to the local IPFS node.

        Args:
            cid: Content identifier to pin
            recursive: Whether to pin recursively
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information

        Note:
            This method uses auto_retry_on_daemon_failure decorator to automatically
            start the IPFS daemon and retry the operation if it fails due to the
            daemon not running.
        """
        operation = "ipfs_pin_add"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            # Call the ipfs module's implementation
            pin_result = self.ipfs.pin_add(cid, recursive=recursive) # type: ignore
            result.update(pin_result) # type: ignore
            result["success"] = pin_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    @auto_retry_on_daemon_failure(daemon_type="ipfs", max_retries=3)
    def ipfs_pin_ls(self, **kwargs):
        """List pinned content on the local IPFS node.

        Args:
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information

        Note:
            This method uses auto_retry_on_daemon_failure decorator to automatically
            start the IPFS daemon and retry the operation if it fails due to the
            daemon not running.
        """
        operation = "ipfs_pin_ls"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            # Call the ipfs module's implementation
            pin_ls_result = self.ipfs.pin_ls() # type: ignore
            result.update(pin_ls_result) # type: ignore
            result["success"] = pin_ls_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    @auto_retry_on_daemon_failure(daemon_type="ipfs", max_retries=3)
    def ipfs_pin_rm(self, cid, recursive=True, **kwargs):
        """Remove pinned content from the local IPFS node.

        Args:
            cid: Content identifier to unpin
            recursive: Whether to unpin recursively
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information

        Note:
            This method uses auto_retry_on_daemon_failure decorator to automatically
            start the IPFS daemon and retry the operation if it fails due to the
            daemon not running.
        """
        operation = "ipfs_pin_rm"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            # Call the ipfs module's implementation
            pin_rm_result = self.ipfs.pin_rm(cid, recursive=recursive) # type: ignore
            result.update(pin_rm_result) # type: ignore
            result["success"] = pin_rm_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    @auto_retry_on_daemon_failure(daemon_type="ipfs", max_retries=3)
    def ipfs_swarm_peers(self, **kwargs):
        """Get the list of connected peers.

        Args:
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information

        Note:
            This method uses auto_retry_on_daemon_failure decorator to automatically
            start the IPFS daemon and retry the operation if it fails due to the
            daemon not running.
        """
        operation = "ipfs_swarm_peers"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            # Call the ipfs module's implementation
            peers_result = self.ipfs.swarm_peers() # type: ignore
            result.update(peers_result) # type: ignore
            result["success"] = peers_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def _setup_ipld_extension(self, resources=None, metadata=None):
        """Set up the IPLD extension component."""
        try:
            self.logger.info("Setting up IPLD extension...")

            # Create IPLD extension with the IPFS client
            self.ipld_extension = IPLDExtension(self.ipfs) # type: ignore

            # Check component availability
            if not self.ipld_extension.car_handler.available: # type: ignore
                self.logger.warning("CAR file operations are not available.")
                self.logger.info("To enable CAR file operations, install py-ipld-car package.")

            if not self.ipld_extension.dag_pb_handler.available: # type: ignore
                self.logger.warning("DAG-PB operations are not available.")
                self.logger.info("To enable DAG-PB operations, install py-ipld-dag-pb package.")

            if not self.ipld_extension.unixfs_handler.available: # type: ignore
                self.logger.warning("UnixFS operations are not available.")
                self.logger.info("To enable UnixFS operations, install py-ipld-unixfs package.")

            self.logger.info("IPLD extension setup complete.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set up IPLD extension: {str(e)}")
            return False

    # IPLD Extension Methods

    def create_car(self, roots, blocks, **kwargs):
        """Create a CAR file from roots and blocks.

        Args:
            roots: List of root CID strings
            blocks: List of (CID, data) tuples
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result
        """
        operation = "create_car"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipld_extension") or self.ipld_extension is None:
                return handle_error(result, IPFSError("IPLD extension not initialized"))

            if not self.ipld_extension.car_handler.available: # type: ignore
                return handle_error(result, IPFSError("CAR file operations not available"))

            car_result = self.ipld_extension.create_car(roots, blocks) # type: ignore
            result.update(car_result) # type: ignore
            result["success"] = car_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def extract_car(self, car_data, **kwargs):
        """Extract contents of a CAR file.

        Args:
            car_data: CAR file data (binary or base64 encoded string)
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result
        """
        operation = "extract_car"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipld_extension") or self.ipld_extension is None:
                return handle_error(result, IPFSError("IPLD extension not initialized"))

            if not self.ipld_extension.car_handler.available: # type: ignore
                return handle_error(result, IPFSError("CAR file operations not available"))

            extract_result = self.ipld_extension.extract_car(car_data) # type: ignore
            result.update(extract_result) # type: ignore
            result["success"] = extract_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def save_car(self, car_data, file_path, **kwargs):
        """Save CAR data to a file.

        Args:
            car_data: CAR file data (binary or base64 encoded string)
            file_path: Path to save the file
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result
        """
        operation = "save_car"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipld_extension") or self.ipld_extension is None:
                return handle_error(result, IPFSError("IPLD extension not initialized"))

            if not self.ipld_extension.car_handler.available: # type: ignore
                return handle_error(result, IPFSError("CAR file operations not available"))

            # Call the extension
            save_result = self.ipld_extension.save_car(car_data, file_path) # type: ignore

            # Copy all results
            for key, value in save_result.items(): # type: ignore
                result[key] = value # type: ignore

            result["success"] = save_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def load_car(self, file_path, **kwargs):
        """Load CAR data from a file.

        Args:
            file_path: Path to the CAR file
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result, roots and blocks
        """
        operation = "load_car"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipld_extension") or self.ipld_extension is None:
                return handle_error(result, IPFSError("IPLD extension not initialized"))

            if not self.ipld_extension.car_handler.available: # type: ignore
                return handle_error(result, IPFSError("CAR file operations not available"))

            # Call the extension
            load_result = self.ipld_extension.load_car(file_path) # type: ignore

            # Copy all results
            for key, value in load_result.items(): # type: ignore
                result[key] = value # type: ignore

            result["success"] = load_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def add_car_to_ipfs(self, car_data, **kwargs):
        """Import a CAR file into IPFS.

        Args:
            car_data: CAR file data (binary or base64 encoded string)
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result
        """
        operation = "add_car_to_ipfs"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipld_extension") or self.ipld_extension is None:
                return handle_error(result, IPFSError("IPLD extension not initialized"))

            if not self.ipld_extension.car_handler.available: # type: ignore
                return handle_error(result, IPFSError("CAR file operations not available"))

            add_car_result = self.ipld_extension.add_car_to_ipfs(car_data) # type: ignore
            result.update(add_car_result) # type: ignore
            result["success"] = add_car_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def create_dag_node(self, data=None, links=None, **kwargs):
        """Create a DAG-PB node.

        Args:
            data: Optional binary data for the node
            links: Optional list of links to other nodes
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result
        """
        operation = "create_dag_node"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipld_extension") or self.ipld_extension is None:
                return handle_error(result, IPFSError("IPLD extension not initialized"))

            if not self.ipld_extension.dag_pb_handler.available: # type: ignore
                return handle_error(result, IPFSError("DAG-PB operations not available"))

            node_result = self.ipld_extension.create_node(data, links) # type: ignore
            result.update(node_result) # type: ignore
            result["success"] = node_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def chunk_file(self, file_path, chunk_size=262144, **kwargs):
        """Chunk a file using fixed-size chunker.

        Args:
            file_path: Path to the file to chunk
            chunk_size: Size of chunks in bytes (default: 256KB)
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result
        """
        operation = "chunk_file"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipld_extension") or self.ipld_extension is None:
                return handle_error(result, IPFSError("IPLD extension not initialized"))

            if not self.ipld_extension.unixfs_handler.available: # type: ignore
                return handle_error(result, IPFSError("UnixFS operations not available"))

            chunk_result = self.ipld_extension.chunk_file(file_path, chunk_size) # type: ignore
            result.update(chunk_result) # type: ignore
            result["success"] = chunk_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    @auto_retry_on_daemon_failure(daemon_type="ipfs", max_retries=3)
    def ipfs_dag_get(self, cid, **kwargs):
        """Get a DAG node from IPFS."""
        operation = "ipfs_dag_get"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            dag_result = self.ipfs.dag_get(cid, **kwargs) # type: ignore
            result.update(dag_result) # type: ignore
            result["success"] = dag_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    @auto_retry_on_daemon_failure(daemon_type="ipfs", max_retries=3)
    def ipfs_dag_put(self, data, **kwargs):
        """Add a DAG node to IPFS."""
        operation = "ipfs_dag_put"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            dag_result = self.ipfs.dag_put(data, **kwargs) # type: ignore
            result.update(dag_result) # type: ignore
            result["success"] = dag_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_id(self, **kwargs):
        """Get node information.

        Args:
            **kwargs: Additional parameters for the operation

        Returns:
            Dictionary with operation result information
        """
        operation = "ipfs_id"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)

        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))

            # Call the ipfs module's implementation
            id_result = self.ipfs.id() # type: ignore
            result.update(id_result) # type: ignore
            result["success"] = id_result.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def _check_knowledge_graph_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call knowledge graph methods."""
        operation = f"knowledge_graph_{method_name}"
        correlation_id = kwargs.get("correlation_id", str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_KNOWLEDGE_GRAPH:
                return handle_error(result, IPFSError("Knowledge graph component is not available"))
            if not hasattr(self, "knowledge_graph") or self.knowledge_graph is None:
                return handle_error(
                    result, IPFSError("Knowledge graph component is not initialized")
                )
            if not hasattr(self.knowledge_graph, method_name):
                return handle_error(
                    result,
                    IPFSError(f"Method '{method_name}' not found in knowledge graph component"),
                )
            method = getattr(self.knowledge_graph, method_name)
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result) # type: ignore
                if "success" not in result: # type: ignore
                    result["success"] = True # type: ignore
            else:
                result["success"] = True # type: ignore
                result["result"] = method_result # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def _check_graph_query_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call graph query methods."""
        operation = f"graph_query_{method_name}"
        correlation_id = kwargs.get("correlation_id", str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_KNOWLEDGE_GRAPH:
                return handle_error(result, IPFSError("Knowledge graph component is not available"))
            if not hasattr(self, "graph_query") or self.graph_query is None:
                return handle_error(result, IPFSError("Graph query interface is not initialized"))
            if not hasattr(self.graph_query, method_name):
                return handle_error(
                    result, IPFSError(f"Method '{method_name}' not found in graph query interface")
                )
            method = getattr(self.graph_query, method_name)
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result) # type: ignore
                if "success" not in result: # type: ignore
                    result["success"] = True # type: ignore
            else:
                result["success"] = True # type: ignore
                result["result"] = method_result # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def _check_graph_rag_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call GraphRAG methods."""
        operation = f"graph_rag_{method_name}"
        correlation_id = kwargs.get("correlation_id", str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_KNOWLEDGE_GRAPH:
                return handle_error(result, IPFSError("Knowledge graph component is not available"))
            if not hasattr(self, "graph_rag") or self.graph_rag is None:
                return handle_error(result, IPFSError("GraphRAG component is not initialized"))
            if not hasattr(self.graph_rag, method_name):
                return handle_error(
                    result, IPFSError(f"Method '{method_name}' not found in GraphRAG component")
                )
            method = getattr(self.graph_rag, method_name)
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result) # type: ignore
                if "success" not in result: # type: ignore
                    result["success"] = True # type: ignore
            else:
                result["success"] = True # type: ignore
                result["result"] = method_result # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def _setup_ai_ml_integration(self, resources=None, metadata=None):
        """Set up the AI/ML integration components."""
        try:
            self.logger.info("Setting up AI/ML integration...")
            ai_ml_config = metadata.get("ai_ml_config", {}) if metadata else {} # type: ignore
            model_registry_path = ai_ml_config.get("model_registry_path", "~/.ipfs_models")
            self.model_registry = ModelRegistry( # type: ignore
                ipfs_client=self.ipfs, base_path=model_registry_path
            )
            self.logger.info(f"Model registry initialized at {model_registry_path}")
            dataset_manager_path = ai_ml_config.get("dataset_manager_path", "~/.ipfs_datasets")
            self.dataset_manager = DatasetManager( # type: ignore
                ipfs_client=self.ipfs, base_path=dataset_manager_path
            )
            self.logger.info(f"Dataset manager initialized at {dataset_manager_path}")
            self.langchain_integration = LangchainIntegration(ipfs_client=self.ipfs) # type: ignore
            self.logger.info("Langchain integration initialized")
            self.llama_index_integration = LlamaIndexIntegration(ipfs_client=self.ipfs) # type: ignore
            self.logger.info("LlamaIndex integration initialized")
            cluster_manager = (
                self.cluster_manager
                if hasattr(self, "cluster_manager") and self.cluster_manager is not None
                else None
            )
            self.distributed_training = DistributedTraining( # type: ignore
                ipfs_client=self.ipfs, cluster_manager=cluster_manager
            )
            if cluster_manager:
                self.logger.info("Distributed training initialized with cluster manager")
            else:
                self.logger.info("Distributed training initialized without cluster manager")
            self.logger.info("AI/ML integration setup complete")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set up AI/ML integration: {str(e)}")
            return False

    def _setup_monitoring(self, resources=None, metadata=None):
        """Set up the monitoring components."""
        try:
            self.logger.info("Setting up monitoring...")
            node_id = metadata.get("node_id") if metadata else "unknown_node"
            metrics_dir = metadata.get("metrics_dir") if metadata else None
            collection_interval = metadata.get("metrics_collection_interval", 60)
            retention_days = metadata.get("metrics_retention_days", 7)

            self.performance_metrics = PerformanceMetrics(
                metrics_dir=metrics_dir,
                collection_interval=collection_interval,
                retention_days=retention_days,
                track_system_resources=True # Always track system resources for dashboard
            )

            self.metrics_collector = MetricsCollector(
                node_id=node_id,
                metrics_dir=metrics_dir,
                collection_interval=collection_interval,
                retention_days=retention_days
            )

            # Register performance_metrics as a source for metrics_collector
            self.metrics_collector.register_metric_source(
                "performance", self.performance_metrics.analyze_metrics
            )

            # Initialize ObservabilityAPI
            self.observability = ObservabilityAPI(
                metrics_collector=self.metrics_collector,
                performance_metrics=self.performance_metrics,
                ipfs_api_instance=self # Pass self to allow ObservabilityAPI to access IPFSKit methods
            )

            self.monitoring = ClusterMonitor(
                node_id=node_id,
                metrics_collector=self.metrics_collector,
                check_interval=collection_interval,
                alert_callback=self.observability.record_alert # Use observability's alert recorder
            )

            self.logger.info("Monitoring setup complete")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set up monitoring: {str(e)}")
            return False

    def _get_gpu_info(self):
        """Placeholder for getting GPU information."""
        self.logger.debug("Attempting to get GPU info (placeholder)")
        return {"gpu_count": 0, "gpu_available": False}

    def get_filesystem(self, **kwargs):
        from .ipfs_fsspec import IPFSFileSystem
        """Get or initialize the FSSpec filesystem interface for IPFS.

        Args:
            **kwargs: Additional parameters to pass to IPFSFSSpecFileSystem constructor
                gateway_urls: List of gateway URLs to use for content retrieval
                gateway_only: Whether to use only gateways and not local daemon
                use_gateway_fallback: Whether to fall back to gateways if local daemon fails
                enable_metrics: Whether to enable performance metrics collection

        Returns:
            IPFSFSSpecFileSystem instance for interacting with IPFS content as a filesystem
        """
        if not FSSPEC_AVAILABLE:
            self.logger.error("FSSpec integration not available. Integration is disabled.")
            return None

        # Initialize TieredCacheManager if not already done
        if not hasattr(self, '_tiered_cache_manager') or self._tiered_cache_manager is None:
            if HAS_TIERED_CACHE_MANAGER:
                self._tiered_cache_manager = TieredCacheManager(
                    cache_dir=kwargs.pop("cache_dir", None),
                    max_memory_size=kwargs.pop("max_memory_size", None),
                    max_disk_size=kwargs.pop("max_disk_size", None),
                    logger=self.logger
                )
            else:
                self.logger.warning("TieredCacheManager not available. FSSpec will operate without caching.")
                self._tiered_cache_manager = MagicMock() # Provide a mock if not available

        # Create the filesystem instance
        fs = IPFSFSSpecFileSystem(
            ipfs_client=self.ipfs,
            tiered_cache_manager=self._tiered_cache_manager,
            api_addr=kwargs.pop("api_addr", "/ip4/127.0.0.1/tcp/5001"),
            role=kwargs.pop("role", self.role),
            gateway_urls=kwargs.pop("gateway_urls", None),
            gateway_only=kwargs.pop("gateway_only", False),
            use_gateway_fallback=kwargs.pop("use_gateway_fallback", True),
            cache_options=kwargs.pop("cache_options", None),
            enable_metrics=kwargs.pop("enable_metrics", False),
            **kwargs
        )

        # Store the instance for future reference
        self._filesystem = fs

        self.logger.info("Initialized FSSpec filesystem interface for IPFS")

        # Return the filesystem instance
        return fs

    def _check_ai_ml_and_call(self, component_name, method_name, *args, **kwargs):
        """Helper to check and call AI/ML methods."""
        operation = f"ai_ml_{component_name}_{method_name}"
        correlation_id = kwargs.get("correlation_id", str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_AI_ML_INTEGRATION:
                return handle_error(result, IPFSError("AI/ML integration is not available"))
            if not hasattr(self, component_name) or getattr(self, component_name) is None:
                return handle_error(
                    result, IPFSError(f"AI/ML component '{component_name}' is not initialized")
                )
            if not hasattr(getattr(self, component_name), method_name): # type: ignore
                return handle_error(
                    result, IPFSError(f"Method '{method_name}' not found in {component_name}")
                )
            method = getattr(getattr(self, component_name), method_name) # type: ignore
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result) # type: ignore
                if "success" not in result: # type: ignore
                    result["success"] = True # type: ignore
            else:
                result["success"] = True # type: ignore
                result["result"] = method_result # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def _check_huggingface_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call Hugging Face Hub methods."""
        operation = f"huggingface_{method_name}"
        correlation_id = kwargs.get("correlation_id", str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_HUGGINGFACE:
                return handle_error(result, IPFSError("Hugging Face Hub integration is not available"))
            if not hasattr(self, "huggingface_kit") or self.huggingface_kit is None:
                return handle_error(
                    result, IPFSError("Hugging Face Hub component is not initialized")
                )
            if not hasattr(self.huggingface_kit, method_name): # type: ignore
                return handle_error(
                    result, IPFSError(f"Method '{method_name}' not found in huggingface_kit")
                )
            method = getattr(self.huggingface_kit, method_name) # type: ignore
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result) # type: ignore
                if "success" not in result: # type: ignore
                    result["success"] = True # type: ignore
            else:
                result["success"] = True # type: ignore
                result["result"] = method_result # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def __call__(self, method, **kwargs):
        """Call a method by name with keyword arguments."""
        # Basic operations
        if method == "ipfs_kit_stop":
            return self.ipfs_kit_stop(**kwargs)
        if method == "ipfs_kit_start":
            return self.ipfs_kit_start(**kwargs)
        if method == "ipfs_kit_ready":
            return self.ipfs_kit_ready(**kwargs)

        # IPFS operations (delegated to self.ipfs)
        if method.startswith("ipfs_") and hasattr(self, "ipfs") and hasattr(self.ipfs, method):
            # Handle specific case for upload_object alias if needed
            if method == "ipfs_upload_object":
                self.method = "ipfs_upload_object"  # Why is this set? Seems like a potential bug. Keeping for now.
            return getattr(self.ipfs, method)(**kwargs)

        # IPFS Cluster operations (role-specific)
        if method == "ipfs_follow_list":
            if self.role == "master" and hasattr(self, "ipfs_cluster_ctl"):
                return self.ipfs_cluster_ctl.ipfs_follow_list(**kwargs) # type: ignore
            elif self.role == "master":
                raise AttributeError("ipfs_cluster_ctl component not initialized for master role")
            else:
                raise PermissionError("Method 'ipfs_follow_list' requires master role")
        if method == "ipfs_follow_ls":
            if self.role != "master" and hasattr(self, "ipfs_cluster_follow"):
                return self.ipfs_cluster_follow.ipfs_follow_ls(**kwargs) # type: ignore
            elif self.role != "master":
                raise AttributeError(
                    "ipfs_cluster_follow component not initialized for non-master role"
                )
            else:
                raise PermissionError("Method 'ipfs_follow_ls' cannot be called by master role")
        if method == "ipfs_follow_info":
            if self.role != "master" and hasattr(self, "ipfs_cluster_follow"):
                return self.ipfs_cluster_follow.ipfs_follow_info(**kwargs) # type: ignore
            elif self.role != "master":
                raise AttributeError(
                    "ipfs_cluster_follow component not initialized for non-master role"
                )
            else:
                raise PermissionError("Method 'ipfs_follow_info' cannot be called by master role")
        if method == "ipfs_cluster_get_pinset":
            # Delegate based on role if the method isn't directly on ipfs_kit
            if self.role == "master" and hasattr(self, "ipfs_cluster_ctl"):
                return self.ipfs_cluster_ctl.ipfs_cluster_get_pinset(**kwargs) # type: ignore
            elif self.role == "worker" and hasattr(self, "ipfs_cluster_follow"):
                # Assuming worker needs to list pins via follow list
                return self.ipfs_cluster_follow.ipfs_follow_list(**kwargs) # type: ignore
            elif hasattr(
                self, "ipfs_get_pinset"
            ):  # Check if it's a method on self (unlikely based on code)
                return self.ipfs_get_pinset(**kwargs)
            else:
                raise AttributeError("Cannot get cluster pinset in current role/state")
        if method == "ipfs_cluster_ctl_add_pin":
            if self.role == "master" and hasattr(self, "ipfs_cluster_ctl"):
                return self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(**kwargs) # type: ignore
            elif self.role == "master":
                raise AttributeError("ipfs_cluster_ctl component not initialized for master role")
            else:
                raise PermissionError("Method 'ipfs_cluster_ctl_add_pin' requires master role")
        if method == "ipfs_cluster_ctl_rm_pin":
            if self.role == "master" and hasattr(self, "ipfs_cluster_ctl"):
                return self.ipfs_cluster_ctl.ipfs_cluster_ctl_rm_pin(**kwargs) # type: ignore
            elif self.role == "master":
                raise AttributeError("ipfs_cluster_ctl component not initialized for master role")
            else:
                raise PermissionError("Method 'ipfs_cluster_ctl_rm_pin' requires master role")

        # IPGet operations
        if method == "ipget_download_object":
            self.method = (
                "download_object"  # Why is this set? Seems like a potential bug. Keeping for now.
            )
            if hasattr(self, "ipget"):
                return self.ipget.ipget_download_object(**kwargs)
            else:
                raise AttributeError("ipget component not initialized")

        # Collection operations
        if method == "load_collection":
            return self.load_collection(**kwargs)

        # libp2p operations
        if method.startswith("libp2p_"):
            return self._check_libp2p_and_call(method.replace("libp2p_", ""), **kwargs)
        if method == "close_libp2p":
            if self.libp2p:
                return self.libp2p.close() # type: ignore
            else:
                return {"success": True, "message": "libp2p not initialized"}  # Or raise error?

        # Cluster management operations
        if method in [
            "create_task",
            "get_task_status",
            "cancel_task",
            "get_tasks",
            "get_nodes",
            "get_cluster_status",
            "find_content_providers",
            "get_content",
            "get_state_interface_info",
        ]:
            return self._check_cluster_manager_and_call(method, **kwargs)
        if method == "stop_cluster_manager":
            if hasattr(self, "cluster_manager") and self.cluster_manager:
                return self.cluster_manager.stop() # type: ignore
            else:
                return {"success": True, "message": "Cluster manager not initialized"}
        if method == "access_state_from_external_process":
            if "state_path" not in kwargs:
                raise ValueError("Missing required parameter: state_path")
            # Assuming _call_static_cluster_manager exists or needs implementation
            if hasattr(self, "_call_static_cluster_manager"):
                return self._call_static_cluster_manager( # type: ignore
                    "access_state_from_external_process", **kwargs
                )
            else:
                raise NotImplementedError("_call_static_cluster_manager not implemented")

        # Monitoring operations (Assuming these are methods on ipfs_kit or need helpers)
        # Example: if method == 'start_monitoring': return self.start_monitoring(**kwargs)
        # Add checks similar to others if these depend on HAS_MONITORING and self.monitoring
        # ... (Add similar checks for all monitoring methods)

        # Knowledge graph operations
        if method in [
            "add_entity",
            "update_entity",
            "get_entity",
            "delete_entity",
            "add_relationship",
            "get_relationship",
            "delete_relationship",
            "query_related",
            "vector_search",
            "graph_vector_search",
            "get_statistics",
            "export_subgraph",
            "import_subgraph",
            "get_version_history",
        ]:
            return self._check_knowledge_graph_and_call(method, **kwargs)

        # Graph query operations
        if method in [
            "find_entities",
            "find_related",
            "find_paths",
            "hybrid_search",
            "get_knowledge_cards",
        ]:
            return self._check_graph_query_and_call(method, **kwargs)

        # GraphRAG operations
        if method in [
            "generate_embedding",
            "retrieve",
            "format_context_for_llm",
            "generate_llm_prompt",
        ]:
            return self._check_graph_rag_and_call(method, **kwargs)

        # AI/ML integration operations
        if method in ["add_model", "get_model", "list_models"]:
            return self._check_ai_ml_and_call("model_registry", method, **kwargs)
        if method in ["add_dataset", "get_dataset", "list_datasets"]:
            return self._check_ai_ml_and_call("dataset_manager", method, **kwargs)
        if method in [
            "langchain_check_availability",
            "langchain_create_vectorstore",
            "langchain_create_document_loader",
        ]:
            return self._check_ai_ml_and_call(
                "langchain_integration", method.replace("langchain_", ""), **kwargs
            )
        if method in [
            "llamaindex_check_availability",
            "llamaindex_create_document_reader",
            "llamaindex_create_storage_context",
        ]:
            return self._check_ai_ml_and_call(
                "llama_index_integration", method.replace("llamaindex_", ""), **kwargs
            )
        if method in [
            "prepare_distributed_task",
            "execute_training_task",
            "aggregate_training_results",
        ]:
            return self._check_ai_ml_and_call("distributed_training", method, **kwargs)

        # Data Loader operations
        if method == "get_data_loader":
            # Assuming get_data_loader is a method of ipfs_kit or needs a helper
            if hasattr(self, "get_data_loader"):
                data_loader = self.get_data_loader(**kwargs)
                return {"success": True, "operation": "get_data_loader", "data_loader": data_loader}
            else:
                raise NotImplementedError("get_data_loader not implemented or available")

        # Hugging Face Hub operations
        if method.startswith("huggingface_"):
            # Extract the actual method name (remove the huggingface_ prefix)
            hf_method = method.replace("huggingface_", "")
            return self._check_huggingface_and_call(hf_method, **kwargs)

        # Handle unknown method
        raise ValueError(f"Unknown method: {method}")

    def ipfs_kit_ready(self, **kwargs):
        """Check if IPFS and IPFS Cluster services are ready."""
        operation = "ipfs_kit_ready"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)
                # else: pass # Continue if validation module not found

            cluster_name = kwargs.get("cluster_name") or getattr(self, "cluster_name", None)
            if self.role != "leecher" and not cluster_name:
                return handle_error(
                    result, IPFSError("cluster_name is required for master/worker roles")
                )

            ipfs_ready = False
            ipfs_cluster_ready = False
            try:
                cmd = ["pgrep", "-f", "ipfs daemon"]
                env = os.environ.copy()
                if hasattr(self.ipfs, "run_ipfs_command"):
                    ps_result = self.ipfs.run_ipfs_command(
                        cmd, correlation_id=correlation_id
                    )
                    ipfs_ready = (
                        ps_result.get("success", False) # type: ignore
                        and ps_result.get("stdout", "").strip() != "" # type: ignore
                    )
                else:
                    process = subprocess.run(
                        cmd, capture_output=True, check=False, shell=False, env=env
                    )
                    ipfs_ready = process.returncode == 0 and process.stdout.decode().strip() != ""
            except Exception as e:
                self.logger.warning(f"Error checking IPFS daemon status: {str(e)}")

            if self.role == "master" and hasattr(self, "ipfs_cluster_service"):
                cluster_result = self.ipfs_cluster_service.ipfs_cluster_service_ready() # type: ignore
                result["success"] = True # type: ignore
                result["ipfs_ready"] = ipfs_ready # type: ignore
                result["cluster_ready"] = cluster_result.get("success", False) # type: ignore
                result["ready"] = ipfs_ready and result["cluster_ready"] # type: ignore
                result["cluster_status"] = cluster_result # type: ignore
                return result
            elif self.role == "worker" and hasattr(self, "ipfs_cluster_follow"):
                try:
                    follow_result = self.ipfs_cluster_follow.ipfs_follow_info() # type: ignore
                    if (
                        isinstance(follow_result, dict)
                        and follow_result.get("cluster_peer_online") == "true"
                        and follow_result.get("ipfs_peer_online") == "true"
                        and (
                            cluster_name is None
                            or follow_result.get("cluster_name") == cluster_name
                        )
                    ):
                        ipfs_cluster_ready = True
                        self.ipfs_follow_info = follow_result  # Store for reference
                except Exception as e:
                    self.logger.warning(f"Error checking cluster follower status: {str(e)}")

            libp2p_ready = False
            if hasattr(self, "libp2p") and self.libp2p is not None:
                try:
                    libp2p_ready = self.libp2p.get_peer_id() is not None # type: ignore
                except Exception as e:
                    self.logger.warning(f"Error checking libp2p status: {str(e)}")

            cluster_manager_ready = False
            if hasattr(self, "cluster_manager") and self.cluster_manager is not None:
                try:
                    cluster_status = self.cluster_manager.get_cluster_status() # type: ignore
                    cluster_manager_ready = cluster_status.get("success", False) # type: ignore
                    result["cluster_manager_status"] = cluster_status # type: ignore
                except Exception as e:
                    self.logger.warning(f"Error checking cluster manager status: {str(e)}")
                    result["cluster_manager_error"] = str(e) # type: ignore

            if self.role == "leecher":
                ready = ipfs_ready or (hasattr(self, "libp2p") and libp2p_ready)
            else:
                ready = ipfs_ready and (ipfs_cluster_ready or cluster_manager_ready)

            result["success"] = True # type: ignore
            result["ready"] = ready # type: ignore
            result["ipfs_ready"] = ipfs_ready # type: ignore
            if self.role != "leecher":
                result["cluster_ready"] = ipfs_cluster_ready # type: ignore
            if hasattr(self, "libp2p"):
                result["libp2p_ready"] = libp2p_ready # type: ignore
            if hasattr(self, "cluster_manager"):
                result["cluster_manager_ready"] = cluster_manager_ready # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def load_collection(self, cid=None, **kwargs):
        """Load a collection from IPFS."""
        operation = "load_collection"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if cid is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)

            dst_path = kwargs.get("path")
            if not dst_path:
                try:
                    base_path = (
                        self.ipfs_path
                        if hasattr(self, "ipfs_path")
                        else os.path.expanduser("~/.ipfs")
                    )
                    pins_dir = os.path.join(base_path, "pins")
                    os.makedirs(pins_dir, exist_ok=True)
                    dst_path = os.path.join(pins_dir, cid)
                except Exception as e:
                    return handle_error(
                        result, IPFSError(f"Failed to create destination directory: {str(e)}")
                    )
            else:
                # Validate provided path (assuming it exists)
                try:
                    from .validation import validate_path

                    validate_path(dst_path, "path")
                except (ImportError, IPFSValidationError) as e:
                    if isinstance(e, IPFSValidationError):
                        return handle_error(result, e)

            try:
                download_result = self.ipget.ipget_download_object(
                    cid=cid, path=dst_path, correlation_id=correlation_id
                )
                if not isinstance(download_result, dict) or not download_result.get(
                    "success", False
                ):
                    error_msg = (
                        download_result.get("error")
                        if isinstance(download_result, dict)
                        else str(download_result)
                    )
                    return handle_error(
                        result, IPFSError(f"Failed to download collection: {error_msg}")
                    )
                result["download"] = download_result # type: ignore
            except Exception as e:
                return handle_error(result, IPFSError(f"Failed to download collection: {str(e)}"))

            try:
                with open(dst_path, "r") as f:
                    collection_str = f.read()
            except Exception as e:
                return handle_error(result, IPFSError(f"Failed to read collection file: {str(e)}"))

            try:
                collection_data = json.loads(collection_str)
                result["success"], result["cid"], result["collection"], result["format"] = ( # type: ignore
                    True,
                    cid,
                    collection_data,
                    "json",
                )
            except json.JSONDecodeError:
                (
                    result["success"], # type: ignore
                    result["cid"], # type: ignore
                    result["collection"], # type: ignore
                    result["format"], # type: ignore
                    result["warning"], # type: ignore
                ) = (True, cid, collection_str, "text", "Collection could not be parsed as JSON")
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_add_pin(self, pin=None, **kwargs):
        """Pin content in IPFS and cluster."""
        operation = "ipfs_add_pin"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if pin is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: pin"))
            # Security validation (assuming it exists)
            try:
                from .validation import is_valid_cid, validate_command_args

                validate_command_args(kwargs)
                if not is_valid_cid(pin):
                    raise IPFSValidationError(f"Invalid CID format: {pin}")
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)
                # else: pass # Continue if validation module not found

            kwargs["correlation_id"] = correlation_id  # Ensure propagation
            result1, result2 = None, None # Initialize result1 and result2

            if self.role == "master" and hasattr(self, "ipfs_cluster_ctl"):
                try:
                    result1 = self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(dst_path, **kwargs) # type: ignore
                except Exception as e:
                    self.logger.error(f"Cluster pin operation failed: {str(e)}")
                    result["cluster_error"] = str(e) # type: ignore
                try:
                    result2 = self.ipfs.ipfs_add_pin(pin, **kwargs) # type: ignore
                except Exception as e:
                    self.logger.error(f"IPFS pin operation failed: {str(e)}")
                    result["ipfs_error"] = str(e) # type: ignore
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, "ipfs"):
                try:
                    result2 = self.ipfs.ipfs_add_pin(pin, **kwargs) # type: ignore
                except Exception as e:
                    self.logger.error(f"IPFS pin operation failed: {str(e)}")
                    result["ipfs_error"] = str(e) # type: ignore

            cluster_success = (
                isinstance(result1, dict) and result1.get("success", False)
                if result1 is not None
                else False
            )
            ipfs_success = (
                isinstance(result2, dict) and result2.get("success", False)
                if result2 is not None
                else False
            )

            result["success"] = ( # type: ignore
                (cluster_success and ipfs_success) if self.role == "master" else ipfs_success
            )
            result["cid"] = pin # type: ignore

            # Only include ipfs_cluster key for master role
            if self.role == "master":
                result["ipfs_cluster"] = result1 # type: ignore

            result["ipfs"] = result2 # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_add_path(self, path=None, **kwargs):
        """Add a file or directory to IPFS and cluster."""
        operation = "ipfs_add_path"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))
            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)

            kwargs["correlation_id"] = correlation_id  # Ensure propagation
            result1, result2 = None, None

            self.logger.info(
                f"ipfs_kit calling ipfs_py.ipfs_add_path with path: {repr(path)}"
            )  # ADDED LOGGING

            if (
                self.role == "master"
                and hasattr(self, "ipfs")
                and hasattr(self, "ipfs_cluster_ctl")
            ):
                try:
                    result2 = self.ipfs.ipfs_add_path(path, **kwargs) # type: ignore
                    if isinstance(result2, dict) and result2.get("success", False):
                        try:
                            result1 = self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_path( # type: ignore
                                path, **kwargs
                            )
                        except Exception as e:
                            self.logger.error(f"Cluster add operation failed: {str(e)}")
                            result["cluster_add_error"] = str(e) # type: ignore
                    else:
                        self.logger.error("IPFS add operation failed, skipping cluster add")
                        result["ipfs_add_error"] = "IPFS add operation failed, skipping cluster add" # type: ignore
                except Exception as e:
                    self.logger.error(f"IPFS add operation failed: {str(e)}")
                    result["ipfs_add_error"] = str(e) # type: ignore
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, "ipfs"):
                try:
                    result2 = self.ipfs.ipfs_add_path(path, **kwargs) # type: ignore
                except Exception as e:
                    self.logger.error(f"IPFS add operation failed: {str(e)}")
                    result["ipfs_add_error"] = str(e) # type: ignore

            cluster_success = (
                isinstance(result1, dict) and result1.get("success", False)
                if result1 is not None
                else False
            )
            ipfs_success = (
                isinstance(result2, dict) and result2.get("success", False)
                if result2 is not None
                else False
            )

            result["success"] = ipfs_success  # Base success on IPFS add # type: ignore
            if self.role == "master":
                result["fully_successful"] = ipfs_success and cluster_success # type: ignore
            result["path"] = path # type: ignore
            result["ipfs_cluster"] = result1 # type: ignore
            result["ipfs"] = result2 # type: ignore
            if ipfs_success and "files" in result2: # type: ignore
                result["files"] = result2["files"] # type: ignore
            if ipfs_success and os.path.isfile(path) and "cid" in result2: # type: ignore
                result["cid"] = result2["cid"] # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_ls_path(self, path=None, **kwargs):
        """List contents of an IPFS path."""
        operation = "ipfs_ls_path"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))
            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)

            kwargs["correlation_id"] = correlation_id  # Ensure propagation
            ls_result = self.ipfs.ipfs_ls_path(path, **kwargs) # type: ignore

            if not isinstance(ls_result, dict):
                result["success"], result["path"] = True, path # type: ignore
                items = (
                    [item for item in ls_result if item != ""]
                    if isinstance(ls_result, list)
                    else []
                )
                result["items"], result["count"] = items, len(items) # type: ignore
            elif ls_result.get("success", False): # type: ignore
                result["success"], result["path"] = True, path # type: ignore
                result["items"] = ls_result.get("items", []) # type: ignore
                result["count"] = ls_result.get("count", 0) # type: ignore
            else:
                return handle_error(
                    result,
                    IPFSError(f"Failed to list path: {ls_result.get('error', 'Unknown error')}"), # type: ignore
                    {"ipfs_result": ls_result},
                )
            return result
        except Exception as e:
            return handle_error(result, e)

    def name_resolve(self, **kwargs):
        """Resolve IPNS name to CID."""
        operation = "name_resolve"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            path = kwargs.get("path")
            if path is not None:
                try:
                    from .validation import COMMAND_INJECTION_PATTERNS, validate_parameter_type

                    validate_parameter_type(path, str, "path")
                    if any(re.search(pattern, path) for pattern in COMMAND_INJECTION_PATTERNS):
                        return handle_error(
                            result,
                            IPFSValidationError(
                                f"Path contains potentially malicious patterns: {path}"
                            ),
                        )
                except (ImportError, IPFSValidationError) as e:
                    if isinstance(e, IPFSValidationError):
                        return handle_error(result, e)

            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)

            kwargs["correlation_id"] = correlation_id  # Ensure propagation
            resolve_result = self.ipfs.ipfs_name_resolve(**kwargs) # type: ignore

            if isinstance(resolve_result, dict) and resolve_result.get("success", False):
                result["success"] = True # type: ignore
                result["ipns_name"] = resolve_result.get("ipns_name") # type: ignore
                result["resolved_cid"] = resolve_result.get("resolved_cid") # type: ignore
            elif isinstance(resolve_result, str):
                result["success"], result["resolved_cid"] = True, resolve_result # type: ignore
                if path:
                    result["ipns_name"] = path # type: ignore
            else:
                return handle_error(
                    result,
                    IPFSError(
                        f"Failed to resolve IPNS name: {resolve_result.get('error', 'Unknown error')}" # type: ignore
                    ),
                    {"ipfs_result": resolve_result},
                )
            return result
        except Exception as e:
            return handle_error(result, e)

    def name_publish(self, path=None, **kwargs):
        """Publish content to IPNS."""
        operation = "name_publish"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))
            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)

            kwargs["correlation_id"] = correlation_id  # Ensure propagation
            publish_result = self.ipfs.ipfs_name_publish(path, **kwargs) # type: ignore

            if isinstance(publish_result, dict):
                if publish_result.get("success", False):
                    result["success"], result["path"] = True, path # type: ignore
                    if "add" in publish_result:
                        result["add"] = publish_result["add"] # type: ignore
                    if "publish" in publish_result:
                        result["publish"] = publish_result["publish"] # type: ignore
                        if "ipns_name" in publish_result["publish"]:
                            result["ipns_name"] = publish_result["publish"]["ipns_name"] # type: ignore
                        if "cid" in publish_result["publish"]:
                            result["cid"] = publish_result["publish"]["cid"] # type: ignore
                else:
                    error_msg = publish_result.get("error", "Unknown error") # type: ignore
                    extra_data = {"add": publish_result["add"]} if "add" in publish_result else {} # type: ignore
                    return handle_error(
                        result, IPFSError(f"Failed to publish to IPNS: {error_msg}"), extra_data
                    )
            else:
                result["success"], result["path"], result["legacy_result"], result["warning"] = ( # type: ignore
                    True,
                    path,
                    publish_result,
                    "Using legacy result format",
                )
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_remove_path(self, path=None, **kwargs):
        """Remove a file or directory from IPFS."""
        operation = "ipfs_remove_path"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))
            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args

                validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)

            kwargs["correlation_id"] = correlation_id  # Ensure propagation
            cluster_result, ipfs_result = None, None

            if self.role == "master" and hasattr(self, "ipfs_cluster_ctl"):
                try:
                    cluster_result = self.ipfs_cluster_ctl.ipfs_cluster_ctl_remove_path( # type: ignore
                        path, **kwargs
                    )
                except Exception as e:
                    self.logger.error(f"Error removing from IPFS cluster: {str(e)}")
                    result["cluster_error"] = str(e) # type: ignore
                try:
                    ipfs_result = self.ipfs.ipfs_remove_path(path, **kwargs) # type: ignore
                except Exception as e:
                    self.logger.error(f"Error removing from IPFS: {str(e)}")
                    result["ipfs_error"] = str(e) # type: ignore
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, "ipfs"):
                try:
                    ipfs_result = self.ipfs.ipfs_remove_path(path, **kwargs) # type: ignore
                except Exception as e:
                    self.logger.error(f"Error removing from IPFS: {str(e)}")
                    result["ipfs_error"] = str(e) # type: ignore

            ipfs_success = (
                isinstance(ipfs_result, dict) and ipfs_result.get("success", False)
                if ipfs_result is not None
                else False
            )
            result["success"] = ipfs_success  # Base success on IPFS operation # type: ignore
            result["path"] = path # type: ignore
            if cluster_result is not None:
                result["ipfs_cluster"] = cluster_result # type: ignore
            result["ipfs"] = ipfs_result # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_remove_pin(self, pin=None, **kwargs):
        """Remove a pin from IPFS."""
        operation = "ipfs_remove_pin"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        try:
            if pin is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: pin"))
            # Security validation (assuming it exists)
            try:
                from .validation import is_valid_cid, validate_command_args

                validate_command_args(kwargs)
                if not is_valid_cid(pin):
                    raise IPFSValidationError(f"Invalid CID format: {pin}")
            except (ImportError, IPFSValidationError) as e:
                if isinstance(e, IPFSValidationError):
                    return handle_error(result, e)
                # else: pass # Continue if validation module not found

            kwargs["correlation_id"] = correlation_id  # Ensure propagation
            cluster_result, ipfs_result = None, None

            if self.role == "master" and hasattr(self, "ipfs_cluster_ctl"):
                try:
                    cluster_result = self.ipfs_cluster_ctl.ipfs_cluster_ctl_remove_pin( # type: ignore
                        pin, **kwargs
                    )
                except Exception as e:
                    self.logger.error(f"Error removing pin from IPFS cluster: {str(e)}")
                    result["cluster_error"] = str(e) # type: ignore
                try:
                    ipfs_result = self.ipfs.ipfs_remove_pin(pin, **kwargs) # type: ignore
                except Exception as e:
                    self.logger.error(f"Error removing pin from IPFS: {str(e)}")
                    result["ipfs_error"] = str(e) # type: ignore
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, "ipfs"):
                try:
                    ipfs_result = self.ipfs.ipfs_remove_pin(pin, **kwargs) # type: ignore
                except Exception as e:
                    self.logger.error(f"Error removing pin from IPFS: {str(e)}")
                    result["ipfs_error"] = str(e) # type: ignore

            ipfs_success = (
                isinstance(ipfs_result, dict) and ipfs_result.get("success", False)
                if ipfs_result is not None
                else False
            )
            cluster_success = (
                isinstance(cluster_result, dict) and cluster_result.get("success", False)
                if cluster_result is not None
                else False
            )

            result["success"] = ipfs_success  # Base success on IPFS operation # type: ignore
            if self.role == "master":
                result["fully_successful"] = ipfs_success and cluster_success # type: ignore
            result["cid"] = pin # type: ignore

            # Only include ipfs_cluster key for master role
            if self.role == "master":
                result["ipfs_cluster"] = result1 # type: ignore

            result["ipfs"] = result2 # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def test_install(self, **kwargs):
        """Test installation of components based on role."""
        if not hasattr(self, "install_ipfs"):
            # Attempt to dynamically import if not done during init (unlikely needed)
            try:
                from .install_ipfs import install_ipfs as install_ipfs_mod

                self.install_ipfs = install_ipfs_mod()
            except ImportError:
                raise ImportError("install_ipfs module not found")

        if self.role == "master":
            return {
                "ipfs_cluster_service": self.install_ipfs.ipfs_cluster_service_test_install(), # type: ignore
                "ipfs_cluster_ctl": self.install_ipfs.ipfs_cluster_ctl_test_install(), # type: ignore
                "ipfs": self.install_ipfs.ipfs_test_install(), # type: ignore
            }
        elif self.role == "worker":
            return {
                "ipfs_cluster_follow": self.install_ipfs.ipfs_cluster_follow_test_install(), # type: ignore
                "ipfs": self.install_ipfs.ipfs_test_install(), # type: ignore
            }
        elif self.role == "leecher":
            return self.install_ipfs.ipfs_test_install() # type: ignore
        else:
            raise ValueError("role is not master, worker, or leecher")

    def ipfs_get_pinset(self, **kwargs):
        """Get pinset from IPFS and potentially cluster."""
        ipfs_pinset = self.ipfs.ipfs_get_pinset(**kwargs) if hasattr(self, "ipfs") else None # type: ignore
        ipfs_cluster = None
        if self.role == "master" and hasattr(self, "ipfs_cluster_ctl"):
            ipfs_cluster = self.ipfs_cluster_ctl.ipfs_cluster_get_pinset(**kwargs) # type: ignore
        elif self.role == "worker" and hasattr(self, "ipfs_cluster_follow"):
            ipfs_cluster = self.ipfs_cluster_follow.ipfs_follow_list( # type: ignore
                **kwargs
            )  # Assuming list gives pinset for worker
        return {"ipfs_cluster": ipfs_cluster, "ipfs": ipfs_pinset}
        
    def dht_findpeer(self, peer_id, **kwargs):
        """Find a specific peer via the DHT and retrieve addresses.
        
        Args:
            peer_id: The ID of the peer to find
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing peer multiaddresses
        """
        operation = "dht_findpeer"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.dht_findpeer(peer_id) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def dht_findprovs(self, cid, num_providers=None, **kwargs):
        """Find providers for a CID via the DHT.
        
        Args:
            cid: The Content ID to find providers for
            num_providers: Maximum number of providers to find
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing provider information
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "dht_findprovs"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.dht_findprovs(cid, num_providers=num_providers) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    # IPFS MFS (Mutable File System) Methods
    def files_mkdir(self, path, parents=False, **kwargs):
        """Create a directory in the MFS.
        
        Args:
            path: Path to create in the MFS
            parents: Whether to create parent directories if they don't exist
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_mkdir"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_mkdir(path, parents) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)
            
    def files_ls(self, path="/", long=False):
        """List directory contents in the MFS.
        
        Args:
            path: Directory path in the MFS to list
            long: Whether to use a long listing format with details
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing directory entries
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_ls"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_ls(path, long) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)
            
    def files_stat(self, path, **kwargs):
        """Get file or directory information in the MFS (Mutable File System).
        
        Args:
            path: Path to stat in MFS
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing file/directory information
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_stat"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_stat(path, **kwargs) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def files_cp(self, src, dst, **kwargs):
        """Copy a file or directory in the MFS.
        
        Args:
            src: Source path in the MFS to copy from
            dst: Destination path in the MFS to copy to
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result indicating success or failure
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_cp"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_cp(src, dst, **kwargs) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)
        
    def files_mv(self, src, dst, **kwargs):
        """Move a file or directory in the MFS.
        
        Args:
            src: Source path in the MFS to move from
            dst: Destination path in the MFS to move to
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result indicating success or failure
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_mv"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_mv(src, dst, **kwargs) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)
        
    def files_rm(self, path, **kwargs):
        """Remove a file or directory from the MFS.
        
        Args:
            path: Path to remove in the MFS
            **kwargs: Additional parameters for the operation
        Returns:
            Dict with operation result indicating success or failure
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_rm"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_rm(path, **kwargs) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)
        
    def files_read(self, path, **kwargs):
        """Read a file from the MFS.
        
        Args:
            path: Path to the file in the MFS to read
            **kwargs: Additional parameters for the operation
        Returns:
            Dict with operation result containing file content or error
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_read"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_read(path, **kwargs) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)
        
    def files_write(self, path, content, **kwargs):
        """Write content to a file in the MFS.
        
        Args:
            path: Path to the file in the MFS to write to
            content: Content to write to the file
            **kwargs: Additional parameters for the operation   
        Returns:
            Dict with operation result indicating success or failure
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_write"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_write(path, content, **kwargs) # type: ignore
            result.update(response) # type: ignore
            result["success"] = response.get("success", False) # type: ignore
            return result
        except Exception as e:
            return handle_error(result, e)

    def update_program_state(self):
        """Update the program state with current system information"""
        if not hasattr(self, 'program_state') or self.program_state is None:
            return
        
        try:
            # Update system state
            system_updates = {}
            
            # Get bandwidth information if available
            try:
                if hasattr(self, 'ipfs') and self.ipfs:
                    # Try to get stats
                    stats_result = self.ipfs.get_stats() if hasattr(self.ipfs, 'get_stats') else None
                    if stats_result and stats_result.get('success'):
                        stats = stats_result.get('data', {})
                        system_updates['bandwidth_in'] = stats.get('bandwidth_in', 0)
                        system_updates['bandwidth_out'] = stats.get('bandwidth_out', 0)
                        system_updates['repo_size'] = stats.get('repo_size', 0)
            except Exception:
                pass  # Skip if stats not available
            
            # Get peer count
            try:
                if hasattr(self, 'ipfs') and self.ipfs:
                    peers_result = self.ipfs.get_peers() if hasattr(self.ipfs, 'get_peers') else None
                    if peers_result and peers_result.get('success'):
                        peers = peers_result.get('data', [])
                        system_updates['peer_count'] = len(peers) if isinstance(peers, list) else 0
            except Exception:
                pass  # Skip if peers not available
            
            # Get IPFS version
            try:
                if hasattr(self, 'ipfs') and self.ipfs:
                    version_result = self.ipfs.version() if hasattr(self.ipfs, 'version') else None
                    if version_result and version_result.get('success'):
                        system_updates['ipfs_version'] = version_result.get('version', '')
            except Exception:
                pass  # Skip if version not available
            
            if system_updates:
                self.program_state.update_system_state(**system_updates)
            
            # Update storage state
            storage_updates = {}
            backends_active = []
            backends_healthy = []
            
            # Check storage backends
            if hasattr(self, 's3_kit') and self.s3_kit:
                backends_active.append('s3')
                # Could add health check here
                backends_healthy.append('s3')
            
            if hasattr(self, 'storacha_kit') and self.storacha_kit:
                backends_active.append('storacha')
                backends_healthy.append('storacha')
            
            if hasattr(self, 'gdrive_kit') and self.gdrive_kit:
                backends_active.append('gdrive') 
                backends_healthy.append('gdrive')
            
            if hasattr(self, 'synapse_storage') and self.synapse_storage:
                backends_active.append('synapse')
                backends_healthy.append('synapse')
            
            if hasattr(self, 'huggingface_kit') and self.huggingface_kit:
                backends_active.append('huggingface')
                backends_healthy.append('huggingface')
            
            storage_updates['backends_active'] = backends_active
            storage_updates['backends_healthy'] = backends_healthy
            
            if storage_updates:
                self.program_state.update_storage_state(**storage_updates)
            
            # Update network state
            network_updates = {}
            
            # Determine network health based on daemon status
            daemon_status = self.check_daemon_status()
            if daemon_status.get('success'):
                daemons = daemon_status.get('daemons', {})
                ipfs_running = daemons.get('ipfs', {}).get('running', False)
                network_updates['network_health'] = 'healthy' if ipfs_running else 'degraded'
                
                # Check cluster status
                cluster_running = daemons.get('ipfs_cluster_service', {}).get('running', False)
                network_updates['cluster_status'] = 'running' if cluster_running else 'stopped'
            else:
                network_updates['network_health'] = 'unknown'
                network_updates['cluster_status'] = 'unknown'
            
            if network_updates:
                self.program_state.update_network_state(**network_updates)
            
            # Export to Parquet for external access
            self.program_state.export_to_parquet()
            
        except Exception as e:
            self.logger.warning(f"Failed to update program state: {e}")

    def get_program_state_summary(self):
        """Get a summary of the current program state"""
        if not hasattr(self, 'program_state') or self.program_state is None:
            return {"error": "Program state not initialized"}
        
        try:
            return self.program_state.get_state_summary()
        except Exception as e:
            return {"error": f"Failed to get program state: {e}"}

    def _start_background_state_updates(self):
        """Start a background thread to periodically update program state"""
        if hasattr(self, '_state_update_thread') and self._state_update_thread.is_alive():
            return  # Already running
        
        import threading
        
        def state_update_loop():
            """Background loop to update program state every 30 seconds"""
            while getattr(self, '_state_update_running', True):
                try:
                    self.update_program_state()
                    time.sleep(30)  # Update every 30 seconds
                except Exception as e:
                    self.logger.warning(f"Background state update failed: {e}")
                    time.sleep(60)  # Wait longer on error
        
        self._state_update_running = True
        self._state_update_thread = threading.Thread(target=state_update_loop, daemon=True)
        self._state_update_thread.start()
        self.logger.info("Started background program state updates")

    def stop_background_state_updates(self):
        """Stop the background state update thread"""
        self._state_update_running = False
        if hasattr(self, '_state_update_thread'):
            try:
                self._state_update_thread.join(timeout=5)
            except Exception:
                pass  # Thread cleanup can fail silently

    # IPFS DHT Methods
    def dht_findpeer(self, peer_id, **kwargs):
        """Find a specific peer via the DHT and retrieve addresses.
        
        Args:
            peer_id: The ID of the peer to find
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing peer multiaddresses
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "dht_findpeer"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.dht_findpeer(peer_id)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)

    def dht_findprovs(self, cid, num_providers=None, **kwargs):
        """Find providers for a CID via the DHT.
        
        Args:
            cid: The Content ID to find providers for
            num_providers: Maximum number of providers to find
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing provider information
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "dht_findprovs"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Build kwargs to pass to ipfs
            ipfs_kwargs = {}
            if num_providers is not None:
                ipfs_kwargs["num_providers"] = num_providers
                
            # Call the ipfs module's implementation
            response = self.ipfs.dht_findprovs(cid, **ipfs_kwargs)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)
            
    # IPFS MFS (Mutable File System) Methods
    def files_mkdir(self, path, parents=False, **kwargs):
        """Create a directory in the MFS.
        
        Args:
            path: Path to create in the MFS
            parents: Whether to create parent directories if they don't exist
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_mkdir"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_mkdir(path, parents)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)
            
    def files_ls(self, path="/", **kwargs):
        """List directory contents in the MFS.
        
        Args:
            path: Directory path in the MFS to list
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing directory entries
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_ls"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_ls(path)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)
            
    def files_stat(self, path, **kwargs):
        """Get file information from the MFS.
        
        Args:
            path: Path to file or directory in the MFS
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing file statistics
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_stat"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_stat(path)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)

# Create CamelCase alias for compatibility
IPFSKit = ipfs_kit
        
if __name__ == "__main__":
    print("🚀 IPFS Kit Py Module Loaded")
    print("=" * 50)
    print("This module is designed to be imported and used within an application.")
    print("It does not run standalone. Please import it in your application code.")
    print("=" * 50)
