import os
import sys
import json
import time
import logging
import asyncio
import io
import tempfile
import subprocess
import datetime
import requests
import urllib.request
import urllib.parse
import urllib.error
import urllib3
import shutil
import uuid
from .error import (
    IPFSError, IPFSConnectionError, IPFSTimeoutError, IPFSContentNotFoundError,
    IPFSValidationError, IPFSConfigurationError, IPFSPinningError,
    create_result_dict, handle_error, perform_with_retry
)
parent_dir = os.path.dirname(os.path.dirname(__file__))
ipfs_lib_dir = os.path.join(parent_dir, "ipfs_kit_py")
sys.path.append(parent_dir)

# Configure logger
logger = logging.getLogger(__name__)
from .install_ipfs import install_ipfs
from .test_fio  import test_fio
from .ipfs_cluster_ctl import ipfs_cluster_ctl
from .ipfs_cluster_follow import ipfs_cluster_follow
from .ipfs_cluster_service import ipfs_cluster_service
from .storacha_kit import storacha_kit
from .ipget import ipget
from .ipfs import ipfs_py
from .s3_kit import s3_kit
from .ipfs_kit_extensions import extend_ipfs_kit

# Try to import libp2p
try:
    from .libp2p_peer import IPFSLibp2pPeer
    HAS_LIBP2P = True
except ImportError:
    HAS_LIBP2P = False

# Try to import cluster management components
try:
    from .cluster.role_manager import NodeRole 
    from .cluster.distributed_coordination import ClusterCoordinator
    from .cluster.cluster_manager import ClusterManager
    from .cluster.utils import get_gpu_info
    HAS_CLUSTER_MANAGEMENT = True
except ImportError:
    HAS_CLUSTER_MANAGEMENT = False

# Try to import monitoring components
try:
    from .cluster.monitoring import ClusterMonitor, MetricsCollector
    HAS_MONITORING = True
except ImportError:
    HAS_MONITORING = False
    
# GPU information is included in the cluster management imports

# Try to import knowledge graph components
try:
    from .ipld_knowledge_graph import IPLDGraphDB, KnowledgeGraphQuery, GraphRAG
    HAS_KNOWLEDGE_GRAPH = True
except ImportError:
    HAS_KNOWLEDGE_GRAPH = False

# Try to import AI/ML integration components
try:
    from .ai_ml_integration import (
        ModelRegistry, DatasetManager, LangchainIntegration, 
        LlamaIndexIntegration, DistributedTraining, IPFSDataLoader
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
    from .ipfs_fsspec import IPFSFileSystem, TieredCacheManager
    FSSPEC_AVAILABLE = True
except ImportError:
    FSSPEC_AVAILABLE = False
import subprocess
import os
import json
import time

class ipfs_kit:
    def __init__(self, resources=None, metadata=None, enable_libp2p=False, enable_cluster_management=False, enable_metadata_index=False):
        # Initialize logger
        self.logger = logger
        
        # Set up method aliases
        self.ipfs_get_config = self.ipfs_get_config
        self.ipfs_set_config = self.ipfs_set_config
        self.ipfs_get_config_value = self.ipfs_get_config_value
        self.ipfs_set_config_value = self.ipfs_set_config_value
        self.test_install = self.test_install
        self.ipfs_get = self.ipget_download_object
        
        # FSSpec filesystem instance (initialized on first use)
        self._filesystem = None
        
        # Metadata index and sync handler (initialized on demand)
        self._metadata_index = None
        self._metadata_sync_handler = None
        
        # Initialize path variables
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ['PATH']
        self.path = self.path + ":" + os.path.join(self.this_dir, "bin")
        self.path_string = "PATH="+ self.path
        
        # Set default role
        self.role = "leecher"
        
        # Default configuration
        self.config = {}
        
        # Process metadata
        if metadata is not None:
            if "config" in metadata:
                if metadata['config'] is not None:
                    self.config = metadata['config']
            if "role" in metadata:
                if metadata['role'] is not None:
                    self.role = metadata['role']
                    if self.role not in  ["master","worker","leecher"]:
                        self.role = "leecher"
            if "cluster_name" in metadata:
                if metadata["cluster_name"] is not None:
                    self.cluster_name = metadata['cluster_name']
                    # Store cluster_name in config as cluster_id for cluster manager
                    self.config["cluster_id"] = metadata['cluster_name']
                    pass
            if "ipfs_path" in metadata:
                if metadata["ipfs_path"] is not None:
                    self.ipfs_path = metadata['ipfs_path']
                    pass
            if "enable_libp2p" in metadata:
                enable_libp2p = metadata.get("enable_libp2p", False)
            if "enable_cluster_management" in metadata:
                enable_cluster_management = metadata.get("enable_cluster_management", False)
            if "enable_metadata_index" in metadata:
                enable_metadata_index = metadata.get("enable_metadata_index", False)
                
            if self.role == "leecher" or self.role == "worker" or self.role == "master":
                self.ipfs = ipfs_py(resources, metadata)
                self.ipget = ipget(resources, metadata)
                self.s3_kit = s3_kit(resources, metadata)
                self.storacha_kit = storacha_kit(resources, metadata)
                pass
            if self.role == "worker":
                self.ipfs = ipfs_py(resources, metadata)
                self.ipget = ipget(resources, metadata)
                self.s3_kit = s3_kit(resources, metadata)
                self.ipfs_cluster_follow = ipfs_cluster_follow(resources, metadata)
                self.storacha_kit = storacha_kit(resources, metadata)
                pass
            if self.role == "master":
                self.ipfs = ipfs_py(resources, metadata)
                self.ipget = ipget(resources, metadata)
                self.s3_kit = s3_kit(resources, metadata)
                self.ipfs_cluster_ctl = ipfs_cluster_ctl(resources, metadata)
                self.ipfs_cluster_service = ipfs_cluster_service(resources, metadata)
                self.storacha_kit = storacha_kit(resources, metadata)
                pass
        
        # Initialize libp2p peer if enabled
        self.libp2p = None
        if enable_libp2p and HAS_LIBP2P:
            self._setup_libp2p(resources, metadata)
        elif enable_libp2p and not HAS_LIBP2P:
            self.logger.warning("libp2p is not available. Skipping initialization.")
            self.logger.info("To enable libp2p direct P2P communication, make sure libp2p_py is installed.")
            
        # Initialize cluster management if enabled
        self.cluster_manager = None
        if enable_cluster_management and HAS_CLUSTER_MANAGEMENT:
            self._setup_cluster_management(resources, metadata)
        elif enable_cluster_management and not HAS_CLUSTER_MANAGEMENT:
            self.logger.warning("Cluster management is not available. Skipping initialization.")
            self.logger.info("To enable cluster management, make sure the cluster package components are available.")
            
        # Initialize Arrow-based metadata index if enabled
        if enable_metadata_index and HAS_ARROW_INDEX:
            self._setup_metadata_index(resources, metadata)
        elif enable_metadata_index and not HAS_ARROW_INDEX:
            self.logger.warning("Arrow metadata index is not available. Skipping initialization.")
            self.logger.info("To enable the metadata index, make sure PyArrow is installed and arrow_metadata_index.py is available.")
            
    def _setup_cluster_management(self, resources=None, metadata=None):
        """Set up the cluster management component with standardized error handling.
        
        This method initializes the role-based cluster management system which enables:
        - Distributed task coordination and execution via a master/worker model
        - Resource-aware task scheduling and assignment
        - Content distribution and replication management
        - Peer discovery and health monitoring
        - Direct peer-to-peer communication via libp2p
        
        The method automatically detects available system resources through 
        psutil for optimal resource allocation and reporting.
        
        Args:
            resources: Dictionary with available resources (CPU, memory, disk, GPU, etc.)
            metadata: Additional metadata for configuration including optional node_id
                      and cluster_id settings
            
        Returns:
            Boolean indicating whether setup was successful
        """
        try:
            self.logger.info("Setting up cluster management...")
            
            # Get node ID (use hostname as fallback)
            import socket
            node_id = metadata.get("node_id") if metadata and "node_id" in metadata else socket.gethostname()
            
            # Get peer ID from libp2p or IPFS identity
            peer_id = None
            if hasattr(self, 'libp2p') and self.libp2p:
                # Try to get peer ID from libp2p
                try:
                    peer_id = self.libp2p.get_peer_id()
                except Exception as e:
                    self.logger.warning(f"Failed to get peer ID from libp2p: {str(e)}")
            
            if not peer_id and hasattr(self, 'ipfs'):
                # Try to get peer ID from IPFS
                try:
                    id_result = self.ipfs.ipfs_id()
                    if id_result.get("success", False) and "ID" in id_result:
                        peer_id = id_result["ID"]
                except Exception as e:
                    self.logger.warning(f"Failed to get peer ID from IPFS: {str(e)}")
            
            # Fallback to a generated ID if needed
            if not peer_id:
                import uuid
                peer_id = f"peer-{uuid.uuid4()}"
                self.logger.warning(f"Using generated peer ID: {peer_id}")
            
            # Prepare configuration
            config = {}
            if hasattr(self, 'config'):
                config = self.config.copy()
            
            # Add cluster-specific parameters
            if metadata and "cluster_id" in metadata:
                config["cluster_id"] = metadata["cluster_id"]
            elif "cluster_id" not in config:
                config["cluster_id"] = "default"
                
            # Convert the resources dict to the structure expected by ClusterManager
            if not resources:
                resources = {}
                
            # Try to get resource information automatically using psutil if available
            try:
                import psutil
                
                # CPU information
                if "cpu_count" not in resources:
                    resources["cpu_count"] = psutil.cpu_count(logical=True)
                if "cpu_usage" not in resources:
                    resources["cpu_percent"] = psutil.cpu_percent(interval=0.1)
                
                # Memory information
                if "memory_total" not in resources:
                    resources["memory_total"] = psutil.virtual_memory().total
                if "memory_available" not in resources:
                    resources["memory_available"] = psutil.virtual_memory().available
                
                # Disk information
                if "disk_total" not in resources:
                    resources["disk_total"] = psutil.disk_usage('/').total
                if "disk_free" not in resources:
                    resources["disk_free"] = psutil.disk_usage('/').free
                    
                # GPU information if available
                if "gpu_count" not in resources and "gpu_available" not in resources:
                    try:
                        # Try to detect NVIDIA GPUs with pynvml (doesn't require import)
                        gpu_info = self._get_gpu_info()
                        if gpu_info:
                            resources.update(gpu_info)
                    except Exception as e:
                        self.logger.debug(f"Failed to get GPU information: {str(e)}")
                
            except ImportError:
                self.logger.warning("psutil not available, using default resource values")
                
                # Set reasonable defaults
                if "cpu_count" not in resources:
                    resources["cpu_count"] = 1
                if "memory_total" not in resources:
                    resources["memory_total"] = 1024 * 1024 * 1024  # 1GB
                if "memory_available" not in resources:
                    resources["memory_available"] = 512 * 1024 * 1024  # 512MB
                if "disk_total" not in resources:
                    resources["disk_total"] = 10 * 1024 * 1024 * 1024  # 10GB
                if "disk_free" not in resources:
                    resources["disk_free"] = 5 * 1024 * 1024 * 1024  # 5GB
                    
            except Exception as e:
                self.logger.warning(f"Error getting system resources: {str(e)}")
            
            # Initialize the cluster manager
            self.cluster_manager = ClusterManager(
                node_id=node_id,
                role=self.role,
                peer_id=peer_id,
                config=config,
                resources=resources,
                metadata=metadata,
                enable_libp2p=hasattr(self, 'libp2p') and self.libp2p is not None
            )
            
            # Start the cluster manager
            result = self.cluster_manager.start()
            
            if not result.get("success", False):
                self.logger.error(f"Failed to start cluster manager: {result}")
                return False
                
            self.logger.info("Cluster management setup complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set up cluster management: {str(e)}")
            return False
    
    def _setup_metadata_index(self, resources=None, metadata=None):
        """Set up the Arrow-based metadata index component with standardized error handling.
        
        This method initializes the Arrow-based metadata index which enables:
        - Efficient metadata storage and retrieval using Apache Arrow columnar format
        - Parquet persistence for durability
        - Fast querying capabilities 
        - Distributed index synchronization
        - Zero-copy access via Arrow C Data Interface
        
        Args:
            resources: Optional resource constraints
            metadata: Optional configuration metadata
            
        Returns:
            Dictionary with status information
        """
        from .error import create_result_dict, handle_error
        
        result = create_result_dict("setup_metadata_index")
        
        try:
            # Get configuration values
            index_dir = metadata.get("metadata_index_dir") if metadata else None
            partition_size = metadata.get("metadata_partition_size") if metadata else None
            sync_interval = metadata.get("metadata_sync_interval", 300) if metadata else 300  # Default 5 minutes
            auto_sync = metadata.get("metadata_auto_sync", True) if metadata else True
            
            # Get cluster ID for topic namespacing
            cluster_id = metadata.get("cluster_name", None) if metadata else None
            if not cluster_id and "cluster_id" in self.config:
                cluster_id = self.config["cluster_id"]
                
            # Initialize metadata index
            self._metadata_index = ArrowMetadataIndex(
                base_path=index_dir,
                role=self.role,
                partition_size=partition_size,
                ipfs_client=self.ipfs  # Pass the IPFS client for API access
            )
            
            # Initialize sync handler if in master or worker role
            if self.role in ("master", "worker"):  # Leechers don't participate in index distribution
                self._metadata_sync_handler = MetadataSyncHandler(
                    index=self._metadata_index,
                    ipfs_client=self.ipfs,
                    cluster_id=cluster_id,
                    node_id=self.ipfs.get_node_id() if hasattr(self.ipfs, 'get_node_id') else None
                )
                
                # Start sync handler if auto-sync is enabled
                if auto_sync:
                    self._metadata_sync_handler.start(sync_interval=sync_interval)
                    
            result["success"] = True
            result["metadata_index_enabled"] = True
            result["auto_sync"] = auto_sync
            
            self.logger.info(f"Arrow metadata index enabled. Auto-sync: {auto_sync}")
            
        except Exception as e:
            handle_error(result, e, "Failed to initialize Arrow metadata index")
            self.logger.error(f"Error initializing Arrow metadata index: {str(e)}")
            
        return result
    
    def get_cluster_status(self, **kwargs):
        """Get comprehensive status information about the cluster.
        
        Retrieves information about connected nodes, their roles, health status,
        resource utilization, and task statistics.
        
        Args:
            **kwargs: Additional arguments like correlation_id
            
        Returns:
            Result dictionary with cluster status information
        """
        operation = "get_cluster_status"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if cluster management is available
            if not hasattr(self, 'cluster_manager') or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
                
            # Get cluster status from manager
            status = self.cluster_manager.get_cluster_status()
            
            # Transfer status info to result
            result.update(status)
            result["success"] = status.get("success", False)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
            
    # Initialize monitoring components
    self.monitoring = None
    self.dashboard = None
    enable_monitoring = metadata.get("enable_monitoring", False) if metadata else False
    
    if enable_monitoring and HAS_MONITORING:
        self._setup_monitoring(resources, metadata)
    elif enable_monitoring and not HAS_MONITORING:
        self.logger.warning("Monitoring is not available. Skipping initialization.")
        self.logger.info("To enable monitoring, make sure cluster_monitoring.py is available.")
        
    def submit_cluster_task(self, task_type, payload, priority=1, timeout=None, **kwargs):
        """Submit a task to the cluster for distributed processing.
        
        Args:
            task_type: Type of task to execute
            payload: Task data and parameters
            priority: Task priority (1-10, higher is more important)
            timeout: Maximum time to wait for task completion (seconds)
            **kwargs: Additional arguments like correlation_id
            
        Returns:
            Result dictionary with task submission status and task_id
        """
        operation = "submit_cluster_task"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if cluster management is available
            if not hasattr(self, 'cluster_manager') or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
                
            # Validate task parameters
            if not task_type:
                return handle_error(result, IPFSValidationError("Task type must be specified"))
                
            if not isinstance(payload, dict):
                return handle_error(result, IPFSValidationError("Payload must be a dictionary"))
                
            # Submit task to cluster manager
            task_result = self.cluster_manager.submit_task(
                task_type=task_type,
                payload=payload,
                priority=priority,
                timeout=timeout
            )
            
            # Transfer result info
            result.update(task_result)
            result["success"] = task_result.get("success", False)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
            
    # Initialize knowledge graph components
    self.knowledge_graph = None
    self.graph_query = None
    self.graph_rag = None
    enable_knowledge_graph = metadata.get("enable_knowledge_graph", False) if metadata else False
    
    if enable_knowledge_graph and HAS_KNOWLEDGE_GRAPH:
        self._setup_knowledge_graph(resources, metadata)
    elif enable_knowledge_graph and not HAS_KNOWLEDGE_GRAPH:
        self.logger.warning("Knowledge graph is not available. Skipping initialization.")
        self.logger.info("To enable knowledge graph, make sure ipld_knowledge_graph.py is available.")
        
    def get_task_status(self, task_id, **kwargs):
        """Get the status of a submitted cluster task.
        
        Args:
            task_id: ID of the task to check
            **kwargs: Additional arguments like correlation_id
            
        Returns:
            Result dictionary with task status information
        """
        operation = "get_task_status"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if cluster management is available
            if not hasattr(self, 'cluster_manager') or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
                
            # Validate task_id
            if not task_id:
                return handle_error(result, IPFSValidationError("Task ID must be specified"))
                
            # Get task status from cluster manager
            status_result = self.cluster_manager.get_task_status(task_id)
            
            # Transfer status info to result
            result.update(status_result)
            result["success"] = True
            result["task_id"] = task_id
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
            
    # Initialize AI/ML integration components
    self.model_registry = None
    self.dataset_manager = None
    self.langchain_integration = None
    self.llama_index_integration = None
    self.distributed_training = None
    enable_ai_ml = metadata.get("enable_ai_ml", False) if metadata else False
    
    if enable_ai_ml and HAS_AI_ML_INTEGRATION:
        self._setup_ai_ml_integration(resources, metadata)
    elif enable_ai_ml and not HAS_AI_ML_INTEGRATION:
        self.logger.warning("AI/ML integration is not available. Skipping initialization.")
            self.logger.info("To enable AI/ML integration, make sure ai_ml_integration.py is available.")
            
    def _setup_libp2p(self, resources=None, metadata=None):
        """Set up the libp2p direct peer-to-peer communication component.
        
        This method initializes the libp2p peer for direct P2P communication, enabling:
        - Direct content exchange between peers without full IPFS daemon
        - NAT traversal through hole punching and relays
        - Peer discovery via DHT and mDNS
        - Content routing with provider tracking
        - Role-specific optimizations for master, worker, and leecher nodes
        
        Args:
            resources: Dictionary with available resources
            metadata: Additional configuration parameters including optional
                    bootstrap_peers, enable_hole_punching, and enable_relay settings
                    
        Returns:
            Boolean indicating whether setup was successful
        """
        try:
            self.logger.info("Setting up libp2p peer for direct P2P communication...")
            
            # Extract libp2p configuration from metadata
            libp2p_config = metadata.get("libp2p_config", {}) if metadata else {}
            
            # Get identity path
            identity_path = libp2p_config.get("identity_path")
            if not identity_path:
                # Default to ipfs directory with libp2p subfolder
                ipfs_path = metadata.get("ipfs_path", "~/.ipfs") if metadata else "~/.ipfs"
                identity_path = os.path.join(os.path.expanduser(ipfs_path), "libp2p", "identity")
                # Ensure directory exists
                os.makedirs(os.path.dirname(identity_path), exist_ok=True)
            
            # Get bootstrap peers
            bootstrap_peers = libp2p_config.get("bootstrap_peers", [])
            
            # Add well-known peers if specified
            if libp2p_config.get("use_well_known_peers", True):
                # Standard bootstrap nodes that also support libp2p
                well_known_peers = [
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb"
                ]
                bootstrap_peers.extend(well_known_peers)
                
            # Get libp2p-specific listen addresses
            listen_addrs = libp2p_config.get("listen_addrs")
            
            # Get feature flags
            enable_mdns = libp2p_config.get("enable_mdns", True)
            enable_hole_punching = libp2p_config.get("enable_hole_punching", False)
            enable_relay = libp2p_config.get("enable_relay", False)
            
            # Enable relay server by default for master and worker nodes if relay is enabled
            enable_relay_server = libp2p_config.get("enable_relay_server", self.role in ["master", "worker"]) and enable_relay
            
            # Configure integration with tiered storage
            tiered_storage_manager = None
            if hasattr(self, "_filesystem") and self._filesystem is not None:
                tiered_storage_manager = getattr(self._filesystem, "cache", None)
            
            # Initialize the libp2p peer
            self.libp2p = IPFSLibp2pPeer(
                identity_path=identity_path,
                bootstrap_peers=bootstrap_peers,
                listen_addrs=listen_addrs,
                role=self.role,
                enable_mdns=enable_mdns,
                enable_hole_punching=enable_hole_punching,
                enable_relay=enable_relay,
                tiered_storage_manager=tiered_storage_manager
            )
            
            # Start discovery
            if libp2p_config.get("auto_start_discovery", True):
                cluster_name = metadata.get("cluster_name", "ipfs-kit-cluster") if metadata else "ipfs-kit-cluster"
                self.libp2p.start_discovery(rendezvous_string=cluster_name)
                
            # Enable relay if configured
            if enable_relay:
                self.libp2p.enable_relay()
                
            self.logger.info(f"libp2p peer initialized with ID: {self.libp2p.get_peer_id()}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set up libp2p peer: {str(e)}")
            return False
            
    def _setup_knowledge_graph(self, resources=None, metadata=None):
        """Set up the IPLD knowledge graph component.
        
        This method initializes the IPLD knowledge graph system which enables:
        - Entity and relationship management with IPLD schemas
        - Graph traversal and query capabilities
        - Basic vector operations for knowledge graph integration
        - Hybrid graph-vector search (GraphRAG)
        - Versioning and change tracking
        - Efficient indexing for graph queries
        
        Note: Advanced vector storage and specialized embedding operations are handled
        by the separate package 'ipfs_embeddings_py'. This implementation provides only
        the basic vector operations needed for knowledge graph functionality. For
        production-grade vector operations, use the dedicated ipfs_embeddings_py package.
        
        Args:
            resources: Dictionary with available resources
            metadata: Additional configuration parameters including optional
                     base_path and embedding_model settings
                     
        Returns:
            Boolean indicating whether setup was successful
        """
        try:
            self.logger.info("Setting up IPLD knowledge graph...")
            
            # Extract configuration from metadata
            kg_config = metadata.get("knowledge_graph_config", {}) if metadata else {}
            base_path = kg_config.get("base_path", "~/.ipfs_graph")
            
            # Initialize the knowledge graph with IPFS client
            self.knowledge_graph = IPLDGraphDB(
                ipfs_client=self.ipfs,
                base_path=base_path,
                schema_version=kg_config.get("schema_version", "1.0.0")
            )
            
            # Initialize query interface
            self.graph_query = KnowledgeGraphQuery(self.knowledge_graph)
            
            # Initialize GraphRAG if embedding model is provided
            embedding_model = kg_config.get("embedding_model")
            if embedding_model:
                self.graph_rag = GraphRAG(
                    graph_db=self.knowledge_graph,
                    embedding_model=embedding_model
                )
                self.logger.info("GraphRAG initialized with embedding model")
            else:
                self.graph_rag = GraphRAG(graph_db=self.knowledge_graph)
                self.logger.info("GraphRAG initialized without embedding model")
            
            self.logger.info("IPLD knowledge graph setup complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set up IPLD knowledge graph: {str(e)}")
            return False
            
    def _check_libp2p_and_call(self, method_name, *args, **kwargs):
        """Check if libp2p component is available and call a method on it.
        
        This helper method checks if the libp2p peer component is initialized,
        and if so, calls the specified method on it. If the component is not 
        available, it returns an appropriate error result.
        
        Args:
            method_name: Name of the method to call on the libp2p component
            *args: Positional arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            Result from the method call, or error result if component unavailable
        """
        operation = f"libp2p_{method_name}"
        correlation_id = kwargs.pop('correlation_id', None)
        result = create_result_dict(operation, correlation_id)
        
        if not HAS_LIBP2P:
            return handle_error(result, IPFSError("libp2p is not available. Install with pip install libp2p"))
            
        if self.libp2p is None:
            return handle_error(result, IPFSError("libp2p peer is not initialized. Enable with enable_libp2p=True"))
            
        try:
            method = getattr(self.libp2p, method_name, None)
            if method is None:
                return handle_error(result, IPFSError(f"Method {method_name} not found in libp2p peer"))
                
            # Call the method and get the result
            method_result = method(*args, **kwargs)
            
            # Set success and return the result
            result["success"] = True
            result["data"] = method_result
            return result
            
        except Exception as e:
            return handle_error(result, e)

    # libp2p direct P2P communication methods
    
    def libp2p_get_peer_id(self, **kwargs):
        """Get the local peer ID.
        
        Returns:
            Result dictionary containing peer ID
        """
        return self._check_libp2p_and_call("get_peer_id", **kwargs)
    
    def libp2p_get_multiaddrs(self, **kwargs):
        """Get the local peer's multiaddresses.
        
        Returns:
            Result dictionary containing multiaddresses
        """
        return self._check_libp2p_and_call("get_multiaddrs", **kwargs)
    
    def libp2p_connect_peer(self, peer_addr, **kwargs):
        """Connect to a remote peer by multiaddress.
        
        Args:
            peer_addr: Multiaddress of the peer to connect to
            **kwargs: Additional arguments including correlation_id
            
        Returns:
            Result dictionary with connection status
        """
        return self._check_libp2p_and_call("connect_peer", peer_addr, **kwargs)
    
    def libp2p_is_connected(self, peer_id, **kwargs):
        """Check if connected to a specific peer.
        
        Args:
            peer_id: ID of the peer to check
            **kwargs: Additional arguments including correlation_id
            
        Returns:
            Result dictionary with connection status
        """
        return self._check_libp2p_and_call("is_connected_to", peer_id, **kwargs)
    
    def libp2p_announce_content(self, cid, metadata=None, **kwargs):
        """Announce available content to the network.
        
        Args:
            cid: Content identifier
            metadata: Optional metadata about the content
            **kwargs: Additional arguments including correlation_id
            
        Returns:
            Result dictionary with announcement status
        """
        return self._check_libp2p_and_call("announce_content", cid, metadata, **kwargs)
    
    def libp2p_find_providers(self, cid, count=20, timeout=30, **kwargs):
        """Find providers for a specific content item.
        
        Args:
            cid: Content identifier to search for
            count: Maximum number of providers to find
            timeout: Maximum time to wait in seconds
            **kwargs: Additional arguments including correlation_id
            
        Returns:
            Result dictionary with list of providers
        """
        return self._check_libp2p_and_call("find_providers", cid, count, timeout, **kwargs)
    
    def libp2p_request_content(self, cid, timeout=30, **kwargs):
        """Request content directly from connected peers.
        
        Args:
            cid: Content identifier to request
            timeout: Maximum time to wait in seconds
            **kwargs: Additional arguments including correlation_id
            
        Returns:
            Result dictionary with content data if successful
        """
        return self._check_libp2p_and_call("request_content", cid, timeout, **kwargs)
    
    def libp2p_store_content(self, cid, data, **kwargs):
        """Store content in the local libp2p content store.
        
        Args:
            cid: Content identifier
            data: Content data as bytes
            **kwargs: Additional arguments including correlation_id
            
        Returns:
            Result dictionary indicating success or failure
        """
        return self._check_libp2p_and_call("store_bytes", cid, data, **kwargs)
    
    def libp2p_start_discovery(self, rendezvous_string="ipfs-kit", **kwargs):
        """Start peer discovery mechanisms.
        
        Args:
            rendezvous_string: Identifier for local network discovery
            **kwargs: Additional arguments including correlation_id
            
        Returns:
            Result dictionary indicating success or failure
        """
        return self._check_libp2p_and_call("start_discovery", rendezvous_string, **kwargs)
    
    def libp2p_enable_relay(self, **kwargs):
        """Enable relay support for NAT traversal.
        
        Returns:
            Result dictionary indicating success or failure
        """
        return self._check_libp2p_and_call("enable_relay", **kwargs)
    
    def libp2p_connect_via_relay(self, peer_id, relay_addr, **kwargs):
        """Connect to a peer through a relay.
        
        Args:
            peer_id: ID of the peer to connect to
            relay_addr: Multiaddress of the relay node
            **kwargs: Additional arguments including correlation_id
            
        Returns:
            Result dictionary indicating success or failure
        """
        return self._check_libp2p_and_call("connect_via_relay", peer_id, relay_addr, **kwargs)
        
    def _check_knowledge_graph_and_call(self, method_name, *args, **kwargs):
        """Check if knowledge graph component is available and call a method on it.
        
        This helper method checks if the knowledge graph component is initialized,
        and if so, calls the specified method on it. If the component is not 
        available, it returns an appropriate error result.
        
        Args:
            method_name: Name of the method to call on the knowledge graph component
            *args: Positional arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            Result from the method call, or error result if component unavailable
        """
        operation = f"knowledge_graph_{method_name}"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if knowledge graph component is available
            if not HAS_KNOWLEDGE_GRAPH:
                error_msg = "Knowledge graph component is not available"
                self.logger.warning(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            if not hasattr(self, 'knowledge_graph') or self.knowledge_graph is None:
                error_msg = "Knowledge graph component is not initialized"
                self.logger.warning(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Check if method exists
            if not hasattr(self.knowledge_graph, method_name):
                error_msg = f"Method '{method_name}' not found in knowledge graph component"
                self.logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Call the method
            method = getattr(self.knowledge_graph, method_name)
            method_result = method(*args, **kwargs)
            
            # Process and return results
            if isinstance(method_result, dict):
                # If method returns a dictionary, merge with our result
                result.update(method_result)
                if "success" not in result:
                    result["success"] = True
            else:
                # Otherwise, add the result as the value
                result["success"] = True
                result["result"] = method_result
                
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def _check_graph_query_and_call(self, method_name, *args, **kwargs):
        """Call a method on the graph query interface with proper error handling."""
        operation = f"graph_query_{method_name}"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if graph query component is available
            if not HAS_KNOWLEDGE_GRAPH:
                error_msg = "Knowledge graph component is not available"
                self.logger.warning(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            if not hasattr(self, 'graph_query') or self.graph_query is None:
                error_msg = "Graph query interface is not initialized"
                self.logger.warning(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Check if method exists
            if not hasattr(self.graph_query, method_name):
                error_msg = f"Method '{method_name}' not found in graph query interface"
                self.logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Call the method
            method = getattr(self.graph_query, method_name)
            method_result = method(*args, **kwargs)
            
            # Process and return results
            if isinstance(method_result, dict):
                # If method returns a dictionary, merge with our result
                result.update(method_result)
                if "success" not in result:
                    result["success"] = True
            else:
                # Otherwise, add the result as the value
                result["success"] = True
                result["result"] = method_result
                
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def _check_graph_rag_and_call(self, method_name, *args, **kwargs):
        """Call a method on the GraphRAG component with proper error handling."""
        operation = f"graph_rag_{method_name}"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if GraphRAG component is available
            if not HAS_KNOWLEDGE_GRAPH:
                error_msg = "Knowledge graph component is not available"
                self.logger.warning(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            if not hasattr(self, 'graph_rag') or self.graph_rag is None:
                error_msg = "GraphRAG component is not initialized"
                self.logger.warning(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Check if method exists
            if not hasattr(self.graph_rag, method_name):
                error_msg = f"Method '{method_name}' not found in GraphRAG component"
                self.logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Call the method
            method = getattr(self.graph_rag, method_name)
            method_result = method(*args, **kwargs)
            
            # Process and return results
            if isinstance(method_result, dict):
                # If method returns a dictionary, merge with our result
                result.update(method_result)
                if "success" not in result:
                    result["success"] = True
            else:
                # Otherwise, add the result as the value
                result["success"] = True
                result["result"] = method_result
                
            return result
            
        except Exception as e:
            return handle_error(result, e)
            
    def _setup_ai_ml_integration(self, resources=None, metadata=None):
        """Set up the AI/ML integration components.
        
        This method initializes the AI/ML integration system which enables:
        1. Langchain/LlamaIndex connectors for knowledge graph and content-addressed storage
        2. ML model storage and distribution using IPFS content addressing
        3. Dataset management for AI workloads with versioning and distribution
        4. Distributed training capabilities leveraging the cluster architecture
        
        Args:
            resources: Dictionary with available resources
            metadata: Additional configuration parameters
                    
        Returns:
            Boolean indicating whether setup was successful
        """
        try:
            self.logger.info("Setting up AI/ML integration...")
            
            # Extract configuration from metadata
            ai_ml_config = metadata.get("ai_ml_config", {}) if metadata else {}
            
            # Initialize model registry
            model_registry_path = ai_ml_config.get("model_registry_path", "~/.ipfs_models")
            self.model_registry = ModelRegistry(
                ipfs_client=self.ipfs,
                base_path=model_registry_path
            )
            self.logger.info(f"Model registry initialized at {model_registry_path}")
            
            # Initialize dataset manager
            dataset_manager_path = ai_ml_config.get("dataset_manager_path", "~/.ipfs_datasets")
            self.dataset_manager = DatasetManager(
                ipfs_client=self.ipfs,
                base_path=dataset_manager_path
            )
            self.logger.info(f"Dataset manager initialized at {dataset_manager_path}")
            
            # Initialize Langchain integration
            self.langchain_integration = LangchainIntegration(
                ipfs_client=self.ipfs
            )
            self.logger.info("Langchain integration initialized")
            
            # Initialize LlamaIndex integration
            self.llama_index_integration = LlamaIndexIntegration(
                ipfs_client=self.ipfs
            )
            self.logger.info("LlamaIndex integration initialized")
            
            # Initialize distributed training (with cluster manager if available)
            cluster_manager = None
            if hasattr(self, 'cluster_manager') and self.cluster_manager is not None:
                cluster_manager = self.cluster_manager
                
            self.distributed_training = DistributedTraining(
                ipfs_client=self.ipfs,
                cluster_manager=cluster_manager
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
    
    def _check_ai_ml_and_call(self, component_name, method_name, *args, **kwargs):
        """Check if AI/ML component is available and call a method on it.
        
        This helper method checks if the specified AI/ML component is initialized,
        and if so, calls the specified method on it. If the component is not 
        available, it returns an appropriate error result.
        
        Args:
            component_name: Name of the AI/ML component ('model_registry', 
                          'dataset_manager', 'langchain_integration', 
                          'llama_index_integration', or 'distributed_training')
            method_name: Name of the method to call on the component
            *args: Positional arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            Result from the method call, or error result if component unavailable
        """
        operation = f"ai_ml_{component_name}_{method_name}"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Check if AI/ML integration is available
            if not HAS_AI_ML_INTEGRATION:
                error_msg = "AI/ML integration is not available"
                self.logger.warning(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Check if the component exists
            if not hasattr(self, component_name) or getattr(self, component_name) is None:
                error_msg = f"AI/ML component '{component_name}' is not initialized"
                self.logger.warning(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Get the component
            component = getattr(self, component_name)
            
            # Check if method exists
            if not hasattr(component, method_name):
                error_msg = f"Method '{method_name}' not found in {component_name}"
                self.logger.error(error_msg)
                return handle_error(result, IPFSError(error_msg))
                
            # Call the method
            method = getattr(component, method_name)
            method_result = method(*args, **kwargs)
            
            # Process and return results
            if isinstance(method_result, dict):
                # If method returns a dictionary, merge with our result
                result.update(method_result)
                if "success" not in result:
                    result["success"] = True
            else:
                # Otherwise, add the result as the value
                result["success"] = True
                result["result"] = method_result
                
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def __call__(self, method, **kwargs):
        """Call a method by name with keyword arguments.
        
        This provides a dynamic dispatch mechanism for invoking methods
        by name, with appropriate role-based access control.
        
        Args:
            method: Method name to call
            **kwargs: Arguments to pass to the method
            
        Returns:
            Result of the method call
        """
        # Basic operations
        if method == "ipfs_kit_stop":
            return self.ipfs_kit_stop(**kwargs)
        if method == "ipfs_kit_start":
            return self.ipfs_kit_start(**kwargs)
        if method == "ipfs_kit_ready":
            return self.ipfs_kit_ready(**kwargs)
            
        # IPFS operations
        if method == 'ipfs_get_pinset':
            return self.ipfs.ipfs_get_pinset(**kwargs)
        if method == 'ipfs_ls_pinset':
            return self.ipfs.ipfs_ls_pinset(**kwargs)
        if method == 'ipfs_add_pin':
            return self.ipfs.ipfs_add_pin(**kwargs)
        if method == 'ipts_ls_pin':
            return self.ipfs.ipfs_ls_pin(**kwargs)
        if method == 'ipfs_remove_pin':
            return self.ipfs.ipfs_remove_pin(**kwargs)
        if method == 'ipfs_get':
            return self.ipfs.ipfs_get(**kwargs)
        if method == 'ipfs_upload_object':
            self.method = 'ipfs_upload_object'
            return self.ipfs.ipfs_upload_object(**kwargs)
        
        # IPFS Cluster operations (role-specific)
        if method == "ipfs_follow_list":
            if self.role == "master":
                return self.ipfs_cluster_ctl.ipfs_follow_list(**kwargs)
            else:
                raise Exception("role is not master")
        if method == "ipfs_follow_ls":
            if self.role != "master":
                return self.ipfs_cluster_follow.ipfs_follow_ls(**kwargs)
            else:
                raise Exception("role is not master")
        if method == "ipfs_follow_info":
            if self.role != "master":
                return self.ipfs_cluster_follow.ipfs_follow_info(**kwargs)
            else:
                raise Exception("role is not master")
        if method == 'ipfs_cluster_get_pinset':
            return self.ipfs_cluster_get_pinset(**kwargs)
        if method == 'ipfs_cluster_ctl_add_pin':
            if self.role == "master":
                return self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(**kwargs)
            else:
                raise Exception("role is not master")
        if method == 'ipfs_cluster_ctl_rm_pin':
            if self.role == "master":
                return self.ipfs_cluster_ctl.ipfs_cluster_ctl_rm_pin(**kwargs)
            else:
                raise Exception("role is not master")
                
        # IPGet operations
        if method == 'ipget_download_object':
            self.method = 'download_object'
            return self.ipget.ipget_download_object(**kwargs)
            
        # Collection operations
        if method == 'load_collection':
            return self.load_collection(**kwargs)
            
        # libp2p operations
        if method == 'get_from_peers':
            return self.get_from_peers(**kwargs)
        if method == 'find_content_providers':
            return self.find_content_providers(**kwargs)
        if method == 'get_content':
            return self.get_content(**kwargs)
        if method == 'close_libp2p':
            return self.close_libp2p()
            
        # Cluster management operations
        if method == 'create_task':
            return self._check_cluster_manager_and_call('create_task', **kwargs)
        if method == 'get_task_status':
            return self._check_cluster_manager_and_call('get_task_status', **kwargs)
        if method == 'cancel_task':
            return self._check_cluster_manager_and_call('cancel_task', **kwargs)
        if method == 'get_tasks':
            return self._check_cluster_manager_and_call('get_tasks', **kwargs)
        if method == 'get_nodes':
            return self._check_cluster_manager_and_call('get_nodes', **kwargs)
        if method == 'get_cluster_status':
            return self._check_cluster_manager_and_call('get_cluster_status', **kwargs)
        if method == 'find_content_providers':
            return self._check_cluster_manager_and_call('find_content_providers', **kwargs)
        if method == 'get_content':
            return self._check_cluster_manager_and_call('get_content', **kwargs)
        if method == 'stop_cluster_manager':
            return self.stop_cluster_manager(**kwargs)
        if method == 'get_state_interface_info':
            return self._check_cluster_manager_and_call('get_state_interface_info', **kwargs)
        if method == 'access_state_from_external_process':
            if 'state_path' not in kwargs:
                raise ValueError("Missing required parameter: state_path")
            return self._call_static_cluster_manager('access_state_from_external_process', **kwargs)
            
        # Monitoring operations
        if method == 'start_monitoring':
            return self.start_monitoring(**kwargs)
        if method == 'stop_monitoring':
            return self.stop_monitoring(**kwargs)
        if method == 'collect_metrics':
            return self.collect_metrics(**kwargs)
        if method == 'check_alert_thresholds':
            return self.check_alert_thresholds(**kwargs)
        if method == 'process_alerts':
            return self.process_alerts(**kwargs)
        if method == 'start_dashboard':
            return self.start_dashboard(**kwargs)
        if method == 'stop_dashboard':
            return self.stop_dashboard(**kwargs)
        if method == 'get_aggregated_metrics':
            return self.get_aggregated_metrics(**kwargs)
        if method == 'export_metrics':
            return self.export_metrics(**kwargs)
        if method == 'validate_cluster_config':
            return self.validate_cluster_config(**kwargs)
        if method == 'distribute_cluster_config':
            return self.distribute_cluster_config(**kwargs)
            
        # Knowledge graph operations
        # Note: Advanced vector storage and specialized embedding operations are handled
        # by the separate package 'ipfs_embeddings_py', while this implementation
        # provides basic graph operations with minimal vector functionality
        if method == 'add_entity':
            return self._check_knowledge_graph_and_call('add_entity', **kwargs)
        if method == 'update_entity':
            return self._check_knowledge_graph_and_call('update_entity', **kwargs)
        if method == 'get_entity':
            return self._check_knowledge_graph_and_call('get_entity', **kwargs)
        if method == 'delete_entity':
            return self._check_knowledge_graph_and_call('delete_entity', **kwargs)
        if method == 'add_relationship':
            return self._check_knowledge_graph_and_call('add_relationship', **kwargs)
        if method == 'get_relationship':
            return self._check_knowledge_graph_and_call('get_relationship', **kwargs)
        if method == 'delete_relationship':
            return self._check_knowledge_graph_and_call('delete_relationship', **kwargs)
        if method == 'query_related':
            return self._check_knowledge_graph_and_call('query_related', **kwargs)
        if method == 'vector_search':
            return self._check_knowledge_graph_and_call('vector_search', **kwargs)
        if method == 'graph_vector_search':
            return self._check_knowledge_graph_and_call('graph_vector_search', **kwargs)
        if method == 'get_statistics':
            return self._check_knowledge_graph_and_call('get_statistics', **kwargs)
        if method == 'export_subgraph':
            return self._check_knowledge_graph_and_call('export_subgraph', **kwargs)
        if method == 'import_subgraph':
            return self._check_knowledge_graph_and_call('import_subgraph', **kwargs)
        if method == 'get_version_history':
            return self._check_knowledge_graph_and_call('get_version_history', **kwargs)
        
        # Graph query operations
        if method == 'find_entities':
            return self._check_graph_query_and_call('find_entities', **kwargs)
        if method == 'find_related':
            return self._check_graph_query_and_call('find_related', **kwargs)
        if method == 'find_paths':
            return self._check_graph_query_and_call('find_paths', **kwargs)
        if method == 'hybrid_search':
            return self._check_graph_query_and_call('hybrid_search', **kwargs)
        if method == 'get_knowledge_cards':
            return self._check_graph_query_and_call('get_knowledge_cards', **kwargs)
        
        # GraphRAG operations
        # Note: For production use with advanced embedding operations,
        # use the dedicated ipfs_embeddings_py package
        if method == 'generate_embedding':
            return self._check_graph_rag_and_call('generate_embedding', **kwargs)
        if method == 'retrieve':
            return self._check_graph_rag_and_call('retrieve', **kwargs)
        if method == 'format_context_for_llm':
            return self._check_graph_rag_and_call('format_context_for_llm', **kwargs)
        if method == 'generate_llm_prompt':
            return self._check_graph_rag_and_call('generate_llm_prompt', **kwargs)
            
        # AI/ML integration operations
        # Model Registry operations
        if method == 'add_model':
            return self._check_ai_ml_and_call('model_registry', 'add_model', **kwargs)
        if method == 'get_model':
            return self._check_ai_ml_and_call('model_registry', 'get_model', **kwargs)
        if method == 'list_models':
            return self._check_ai_ml_and_call('model_registry', 'list_models', **kwargs)
            
        # Dataset Manager operations
        if method == 'add_dataset':
            return self._check_ai_ml_and_call('dataset_manager', 'add_dataset', **kwargs)
        if method == 'get_dataset':
            return self._check_ai_ml_and_call('dataset_manager', 'get_dataset', **kwargs)
        if method == 'list_datasets':
            return self._check_ai_ml_and_call('dataset_manager', 'list_datasets', **kwargs)
            
        # Langchain integration operations
        if method == 'langchain_check_availability':
            return self._check_ai_ml_and_call('langchain_integration', 'check_availability', **kwargs)
        if method == 'langchain_create_vectorstore':
            return self._check_ai_ml_and_call('langchain_integration', 'create_ipfs_vectorstore', **kwargs)
        if method == 'langchain_create_document_loader':
            return self._check_ai_ml_and_call('langchain_integration', 'create_document_loader', **kwargs)
            
        # LlamaIndex integration operations
        if method == 'llamaindex_check_availability':
            return self._check_ai_ml_and_call('llama_index_integration', 'check_availability', **kwargs)
        if method == 'llamaindex_create_document_reader':
            return self._check_ai_ml_and_call('llama_index_integration', 'create_ipfs_document_reader', **kwargs)
        if method == 'llamaindex_create_storage_context':
            return self._check_ai_ml_and_call('llama_index_integration', 'create_ipfs_storage_context', **kwargs)
            
        # Distributed Training operations
        if method == 'prepare_distributed_task':
            return self._check_ai_ml_and_call('distributed_training', 'prepare_distributed_task', **kwargs)
        if method == 'execute_training_task':
            return self._check_ai_ml_and_call('distributed_training', 'execute_training_task', **kwargs)
        if method == 'aggregate_training_results':
            return self._check_ai_ml_and_call('distributed_training', 'aggregate_training_results', **kwargs)
            
        # Data Loader operations
        if method == 'get_data_loader':
            data_loader = self.get_data_loader(**kwargs)
            return {
                "success": True,
                "operation": "get_data_loader", 
                "data_loader": data_loader
            }
            
        # Handle unknown method
        raise ValueError(f"Unknown method: {method}")

    def ipfs_kit_ready(self, **kwargs):
        """Check if IPFS and IPFS Cluster services are ready with standardized error handling.
        
        Args:
            **kwargs: Additional arguments like 'cluster_name'
            
        Returns:
            Result dictionary with service readiness status
        """
        operation = "ipfs_kit_ready"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate command arguments for security
            try:
                from .validation import validate_command_args
                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)
                
            # Get cluster name if applicable
            cluster_name = None
            if "cluster_name" in kwargs:
                cluster_name = kwargs["cluster_name"]
            elif hasattr(self, 'cluster_name'):
                cluster_name = self.cluster_name
            elif self.role != "leecher":
                return handle_error(result, IPFSError("cluster_name is not defined"))
                
            # Track readiness status
            ipfs_ready = False
            ipfs_cluster_ready = False
            
            # Check if IPFS daemon is running using pgrep instead of ps | grep
            try:
                cmd = ["pgrep", "-f", "ipfs daemon"]
                env = os.environ.copy()
                
                # Use run_ipfs_command if available, otherwise fallback to subprocess
                if hasattr(self.ipfs, 'run_ipfs_command'):
                    ps_result = self.ipfs.run_ipfs_command(cmd, check=False, correlation_id=correlation_id)
                    ipfs_ready = ps_result.get("success", False) and ps_result.get("stdout", "").strip() != ""
                else:
                    # Fallback to direct subprocess call
                    process = subprocess.run(
                        cmd,
                        capture_output=True,
                        check=False,
                        shell=False,
                        env=env
                    )
                    ipfs_ready = process.returncode == 0 and process.stdout.decode().strip() != ""
            except Exception as e:
                self.logger.warning(f"Error checking IPFS daemon status: {str(e)}")
                # Continue with ipfs_ready = False
            
            # Check cluster service status based on role
            if self.role == "master" and hasattr(self, 'ipfs_cluster_service'):
                # For master, use cluster service status
                cluster_result = self.ipfs_cluster_service.ipfs_cluster_service_ready()
                
                # Update our result with the cluster service result
                result["success"] = True
                result["ipfs_ready"] = ipfs_ready
                result["cluster_ready"] = cluster_result.get("success", False)
                result["ready"] = ipfs_ready and cluster_result.get("success", False)
                result["cluster_status"] = cluster_result
                
                return result
                
            elif self.role == "worker" and hasattr(self, 'ipfs_cluster_follow'):
                # For worker, check follower info
                try:
                    follow_result = self.ipfs_cluster_follow.ipfs_follow_info()
                    
                    # Check if cluster follow is ready
                    if (isinstance(follow_result, dict) and 
                        "cluster_peer_online" in follow_result and 
                        "ipfs_peer_online" in follow_result):
                        
                        # Validate cluster name if provided
                        if cluster_name is None or follow_result.get("cluster_name") == cluster_name:
                            if (follow_result.get("cluster_peer_online") == 'true' and 
                                follow_result.get("ipfs_peer_online") == 'true'):
                                ipfs_cluster_ready = True
                                
                    # Store follow info for future reference
                    if ipfs_cluster_ready:
                        self.ipfs_follow_info = follow_result
                        
                except Exception as e:
                    self.logger.warning(f"Error checking cluster follower status: {str(e)}")
                    # Continue with ipfs_cluster_ready = False
            
            # Check libp2p status if available
            libp2p_ready = False
            if hasattr(self, 'libp2p') and self.libp2p is not None:
                try:
                    # Check if libp2p is running by getting peer ID
                    peer_id = self.libp2p.get_peer_id()
                    libp2p_ready = peer_id is not None
                    self.logger.debug(f"libp2p peer is ready with ID: {peer_id}")
                except Exception as e:
                    self.logger.warning(f"Error checking libp2p status: {str(e)}")
                    libp2p_ready = False
            
            # Check cluster manager status if available
            cluster_manager_ready = False
            if hasattr(self, 'cluster_manager') and self.cluster_manager is not None:
                try:
                    # Get cluster status
                    cluster_status = self.cluster_manager.get_cluster_status()
                    cluster_manager_ready = cluster_status.get("success", False)
                    result["cluster_manager_status"] = cluster_status
                except Exception as e:
                    self.logger.warning(f"Error checking cluster manager status: {str(e)}")
                    result["cluster_manager_error"] = str(e)
            
            # Determine overall readiness based on role
            if self.role == "leecher":
                # For leecher, either IPFS or libp2p needs to be ready
                ready = ipfs_ready or (hasattr(self, 'libp2p') and libp2p_ready)
            else:
                # For master/worker, IPFS and cluster need to be ready
                # libp2p is optional but tracked
                # Cluster manager is also optional but tracked
                ready = ipfs_ready and (ipfs_cluster_ready or cluster_manager_ready)
                
            # Build and return result
            result["success"] = True
            result["ready"] = ready
            result["ipfs_ready"] = ipfs_ready
            
            if self.role != "leecher":
                result["cluster_ready"] = ipfs_cluster_ready
                
            # Include libp2p status if it exists
            if hasattr(self, 'libp2p'):
                result["libp2p_ready"] = libp2p_ready
                
            # Include cluster manager status if it exists
            if hasattr(self, 'cluster_manager'):
                result["cluster_manager_ready"] = cluster_manager_ready
                
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def load_collection(self, cid=None, **kwargs):
        """Load a collection from IPFS with standardized error handling.
        
        Args:
            cid: Content ID of the collection to load
            **kwargs: Additional arguments including 'path' for destination 
                      and 'correlation_id' for tracing
                      
        Returns:
            Result dictionary with operation outcome and collection data
        """
        operation = "load_collection"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if cid is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
                
            # Validate command arguments for security
            try:
                from .validation import validate_command_args, validate_required_parameter, validate_parameter_type
                validate_command_args(kwargs)
                validate_required_parameter(cid, "cid")
                validate_parameter_type(cid, str, "cid")
                
                # Validate CID format if possible
                try:
                    from .validation import is_valid_cid
                    if not is_valid_cid(cid):
                        return handle_error(result, IPFSValidationError(f"Invalid CID format: {cid}"))
                except ImportError:
                    # If validation module is not fully available, continue with basic checks
                    pass
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Determine destination path
            if "path" in kwargs:
                dst_path = kwargs["path"]
                
                # Validate path if provided
                try:
                    from .validation import validate_path
                    validate_path(dst_path, "path")
                except (ImportError, IPFSValidationError) as e:
                    if isinstance(e, IPFSValidationError):
                        return handle_error(result, e)
                    # If validation module is not available, continue with basic path
            else:
                # Use default path hierarchy
                try:
                    dst_path = self.ipfs_path if hasattr(self, 'ipfs_path') else os.path.expanduser("~/.ipfs")
                    
                    # Create directory structure if needed
                    if not os.path.exists(dst_path):
                        os.makedirs(dst_path)
                        
                    pins_dir = os.path.join(dst_path, "pins")
                    if not os.path.exists(pins_dir):
                        os.makedirs(pins_dir)
                        
                    dst_path = os.path.join(pins_dir, cid)
                except Exception as e:
                    return handle_error(result, IPFSError(f"Failed to create destination directory: {str(e)}"))
            
            # Download the collection using ipget
            try:
                download_result = self.ipget.ipget_download_object(
                    cid=cid,
                    path=dst_path,
                    correlation_id=correlation_id
                )
                
                if not isinstance(download_result, dict) or not download_result.get("success", False):
                    error_msg = download_result.get("error") if isinstance(download_result, dict) else str(download_result)
                    return handle_error(result, IPFSError(f"Failed to download collection: {error_msg}"))
                    
                result["download"] = download_result
            except Exception as e:
                return handle_error(result, IPFSError(f"Failed to download collection: {str(e)}"))
            
            # Read the collection file
            try:
                with open(dst_path, 'r') as f:
                    collection_str = f.read()
            except Exception as e:
                return handle_error(result, IPFSError(f"Failed to read collection file: {str(e)}"))
            
            # Parse the collection as JSON if possible
            try:
                collection_data = json.loads(collection_str)
                
                # Update result with success and collection data
                result["success"] = True
                result["cid"] = cid
                result["collection"] = collection_data
                result["format"] = "json"
                
                return result
            except json.JSONDecodeError:
                # Not valid JSON, return as text
                result["success"] = True
                result["cid"] = cid
                result["collection"] = collection_str
                result["format"] = "text"
                result["warning"] = "Collection could not be parsed as JSON"
                
                return result
            
        except Exception as e:
            return handle_error(result, e)

    def ipfs_add_pin(self, pin=None, **kwargs):
        """Pin content in IPFS and cluster with standardized error handling.
        
        Args:
            pin: Content ID to pin
            **kwargs: Additional arguments including 'path' for destination 
                     and 'correlation_id' for tracing
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_add_pin"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if pin is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: pin"))
                
            # Validate command arguments for security
            try:
                from .validation import validate_command_args, validate_required_parameter, validate_parameter_type
                validate_command_args(kwargs)
                validate_required_parameter(pin, "pin")
                validate_parameter_type(pin, str, "pin")
                
                # Validate CID format if possible
                try:
                    from .validation import is_valid_cid
                    if not is_valid_cid(pin):
                        return handle_error(result, IPFSValidationError(f"Invalid CID format: {pin}"))
                except ImportError:
                    # If validation module is not fully available, continue with basic checks
                    pass
            except IPFSValidationError as e:
                return handle_error(result, e)
                
            # Determine destination path
            if "path" in kwargs:
                dst_path = kwargs["path"]
                
                # Validate path if provided
                try:
                    from .validation import validate_path
                    validate_path(dst_path, "path")
                except (ImportError, IPFSValidationError) as e:
                    if isinstance(e, IPFSValidationError):
                        return handle_error(result, e)
                    # If validation module is not available, continue with basic path
            else:
                # Use default path hierarchy
                try:
                    dst_path = self.ipfs_path if hasattr(self, 'ipfs_path') else os.path.expanduser("~/.ipfs")
                    
                    # Create directory structure if needed
                    if not os.path.exists(dst_path):
                        os.makedirs(dst_path)
                        
                    pins_dir = os.path.join(dst_path, "pins")
                    if not os.path.exists(pins_dir):
                        os.makedirs(pins_dir)
                        
                    dst_path = os.path.join(pins_dir, pin)
                except Exception as e:
                    return handle_error(result, IPFSError(f"Failed to create destination directory: {str(e)}"))
            
            # Download the content using ipget
            try:
                download_result = self.ipget.ipget_download_object(
                    cid=pin,
                    path=dst_path,
                    correlation_id=correlation_id
                )
                
                # Store download result, but continue even if download fails
                # as we can still pin the CID without having the content locally
                if isinstance(download_result, dict) and download_result.get("success", False):
                    result["download_success"] = True
                    result["download"] = download_result
                else:
                    error_msg = download_result.get("error") if isinstance(download_result, dict) else str(download_result)
                    result["download_success"] = False
                    result["download_error"] = error_msg
                    self.logger.warning(f"Download failed, continuing with pin operation: {error_msg}")
            except Exception as e:
                result["download_success"] = False
                result["download_error"] = str(e)
                self.logger.warning(f"Download failed, continuing with pin operation: {str(e)}")
            
            # Pin content based on role
            result1 = None
            result2 = None
            
            # Add the correlation ID to kwargs for propagation
            kwargs['correlation_id'] = correlation_id
            
            if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                # For master, pin in both IPFS and cluster
                try:
                    # Pin in IPFS cluster
                    result1 = self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(dst_path, **kwargs)
                except Exception as e:
                    result["cluster_pin_error"] = str(e)
                    self.logger.error(f"Cluster pin operation failed: {str(e)}")
                
                try:
                    # Pin in local IPFS node
                    result2 = self.ipfs.ipfs_add_pin(pin, **kwargs)
                except Exception as e:
                    result["ipfs_pin_error"] = str(e)
                    self.logger.error(f"IPFS pin operation failed: {str(e)}")
                
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, 'ipfs'):
                # For worker/leecher, just pin in IPFS
                try:
                    result2 = self.ipfs.ipfs_add_pin(pin, **kwargs)
                except Exception as e:
                    result["ipfs_pin_error"] = str(e)
                    self.logger.error(f"IPFS pin operation failed: {str(e)}")
            
            # Determine overall success based on pin operations
            cluster_success = isinstance(result1, dict) and result1.get("success", False) if result1 is not None else False
            ipfs_success = isinstance(result2, dict) and result2.get("success", False) if result2 is not None else False
            
            if self.role == "master":
                result["success"] = cluster_success and ipfs_success
            else:
                result["success"] = ipfs_success
                
            # Include individual operation results
            result["cid"] = pin
            result["ipfs_cluster"] = result1
            result["ipfs"] = result2
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def ipfs_add_path(self, path=None, **kwargs):
        """Add a file or directory to IPFS and cluster with standardized error handling.
        
        Args:
            path: Path to the file or directory to add
            **kwargs: Additional arguments including 'correlation_id' for tracing
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_add_path"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))
                
            # Validate command arguments for security
            try:
                from .validation import validate_command_args, validate_required_parameter, validate_parameter_type, validate_path
                validate_command_args(kwargs)
                validate_required_parameter(path, "path")
                validate_parameter_type(path, str, "path")
                validate_path(path, "path")
                
                # Check if path exists
                if not os.path.exists(path):
                    return handle_error(result, IPFSValidationError(f"Path does not exist: {path}"))
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Add the correlation ID to kwargs for propagation
            kwargs['correlation_id'] = correlation_id
            
            # Add the path to IPFS and optionally to cluster based on role
            result1 = None
            result2 = None
            
            if self.role == "master" and hasattr(self, 'ipfs') and hasattr(self, 'ipfs_cluster_ctl'):
                # For master, add to both IPFS and cluster
                try:
                    # First add to IPFS
                    result2 = self.ipfs.ipfs_add_path(path, **kwargs)
                    
                    # Then add to cluster if IPFS operation was successful
                    if isinstance(result2, dict) and result2.get("success", False):
                        try:
                            result1 = self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_path(path, **kwargs)
                        except Exception as e:
                            result["cluster_add_error"] = str(e)
                            self.logger.error(f"Cluster add operation failed: {str(e)}")
                    else:
                        result["ipfs_add_error"] = "IPFS add operation failed, skipping cluster add"
                        self.logger.error("IPFS add operation failed, skipping cluster add")
                except Exception as e:
                    result["ipfs_add_error"] = str(e)
                    self.logger.error(f"IPFS add operation failed: {str(e)}")
                
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, 'ipfs'):
                # For worker/leecher, just add to IPFS
                try:
                    result2 = self.ipfs.ipfs_add_path(path, **kwargs)
                except Exception as e:
                    result["ipfs_add_error"] = str(e)
                    self.logger.error(f"IPFS add operation failed: {str(e)}")
            
            # Determine overall success based on add operations
            cluster_success = isinstance(result1, dict) and result1.get("success", False) if result1 is not None else False
            ipfs_success = isinstance(result2, dict) and result2.get("success", False) if result2 is not None else False
            
            if self.role == "master":
                result["success"] = ipfs_success  # Consider success if IPFS add worked, even if cluster failed
                result["fully_successful"] = ipfs_success and cluster_success  # Flag for complete success
            else:
                result["success"] = ipfs_success
                
            # Include individual operation results
            result["path"] = path
            result["ipfs_cluster"] = result1
            result["ipfs"] = result2
            
            # If IPFS add was successful, include CIDs for convenience
            if ipfs_success and "files" in result2:
                result["files"] = result2["files"]
                
                # For a single file, include the CID directly
                if os.path.isfile(path) and "cid" in result2:
                    result["cid"] = result2["cid"]
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def ipfs_ls_path(self, path=None, **kwargs):
        """List contents of an IPFS path with standardized error handling.
        
        Args:
            path: The IPFS path to list contents of
            **kwargs: Additional arguments for the ls operation
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_ls_path"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))
                
            # Validate command arguments for security
            try:
                from .validation import validate_command_args, validate_required_parameter, validate_parameter_type
                validate_command_args(kwargs)
                validate_required_parameter(path, "path")
                validate_parameter_type(path, str, "path")
                
                # Special handling for MFS paths
                if not path.startswith("/ipfs/") and not path.startswith("/ipns/"):
                    # For MFS paths, we should check for command injection
                    from .validation import COMMAND_INJECTION_PATTERNS
                    import re
                    if any(re.search(pattern, path) for pattern in COMMAND_INJECTION_PATTERNS):
                        return handle_error(result, IPFSValidationError(f"Path contains potentially malicious patterns: {path}"))
                
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Add the correlation ID to kwargs for propagation
            kwargs['correlation_id'] = correlation_id
            
            # Call the ipfs_ls_path method from ipfs.py
            ls_result = self.ipfs.ipfs_ls_path(path, **kwargs)
            
            if not isinstance(ls_result, dict):
                # Handle case where the result is not a dictionary (legacy format)
                result["success"] = True
                result["path"] = path
                
                # Filter out empty items
                items = []
                if isinstance(ls_result, list):
                    items = [item for item in ls_result if item != ""]
                
                result["items"] = items
                result["count"] = len(items)
            else:
                # Modern result format is a dictionary
                if ls_result.get("success", False):
                    # Copy relevant fields from the ipfs_ls_path result
                    result["success"] = True
                    result["path"] = path
                    result["items"] = ls_result.get("items", [])
                    result["count"] = ls_result.get("count", 0)
                else:
                    # Propagate error information
                    return handle_error(
                        result,
                        IPFSError(f"Failed to list path: {ls_result.get('error', 'Unknown error')}"),
                        {"ipfs_result": ls_result}
                    )
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def name_resolve(self, **kwargs):
        """Resolve IPNS name to CID with standardized error handling.
        
        Args:
            **kwargs: Arguments including 'path' for the IPNS name to resolve and 
                     'correlation_id' for tracing
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "name_resolve"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate path parameter if provided
            path = kwargs.get('path')
            if path is not None:
                try:
                    from .validation import validate_parameter_type
                    validate_parameter_type(path, str, "path")
                    
                    # Check for command injection in path
                    from .validation import COMMAND_INJECTION_PATTERNS
                    import re
                    if any(re.search(pattern, path) for pattern in COMMAND_INJECTION_PATTERNS):
                        return handle_error(result, IPFSValidationError(f"Path contains potentially malicious patterns: {path}"))
                except IPFSValidationError as e:
                    return handle_error(result, e)
            
            # Validate command arguments for security
            try:
                from .validation import validate_command_args
                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Add the correlation ID to kwargs for propagation
            kwargs['correlation_id'] = correlation_id
            
            # Call the ipfs_name_resolve method from ipfs.py
            resolve_result = self.ipfs.ipfs_name_resolve(**kwargs)
            
            if isinstance(resolve_result, dict) and resolve_result.get("success", False):
                # Modern result format
                result["success"] = True
                result["ipns_name"] = resolve_result.get("ipns_name")
                result["resolved_cid"] = resolve_result.get("resolved_cid")
            elif isinstance(resolve_result, str):
                # Legacy format (directly returning a CID string)
                result["success"] = True
                result["resolved_cid"] = resolve_result
                if path:
                    result["ipns_name"] = path
            else:
                # Propagate error information
                return handle_error(
                    result,
                    IPFSError(f"Failed to resolve IPNS name: {resolve_result.get('error', 'Unknown error')}"),
                    {"ipfs_result": resolve_result}
                )
            
            return result
            
        except Exception as e:
            return handle_error(result, e)


    def name_publish(self, path=None, **kwargs):
        """Publish content to IPNS with standardized error handling.
        
        Args:
            path: Path to the file to publish
            **kwargs: Additional arguments for the publish operation including
                     'correlation_id' for tracing
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "name_publish"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))
                
            # Validate command arguments for security
            try:
                from .validation import validate_command_args, validate_required_parameter, validate_parameter_type, validate_path
                validate_command_args(kwargs)
                validate_required_parameter(path, "path")
                validate_parameter_type(path, str, "path")
                validate_path(path, "path")
                
                # Additional check to ensure path exists
                if not os.path.exists(path):
                    return handle_error(result, IPFSValidationError(f"Path does not exist: {path}"))
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Add the correlation ID to kwargs for propagation
            kwargs['correlation_id'] = correlation_id
            
            # Call the ipfs_name_publish method from ipfs.py
            publish_result = self.ipfs.ipfs_name_publish(path, **kwargs)
            
            if isinstance(publish_result, dict):
                if publish_result.get("success", False):
                    # Copy relevant fields from the publish result
                    result["success"] = True
                    result["path"] = path
                    
                    # Include add and publish info if available
                    if "add" in publish_result:
                        result["add"] = publish_result["add"]
                        
                    if "publish" in publish_result:
                        result["publish"] = publish_result["publish"]
                        
                        # For convenience, extract key fields to the top level
                        if "ipns_name" in publish_result["publish"]:
                            result["ipns_name"] = publish_result["publish"]["ipns_name"]
                        if "cid" in publish_result["publish"]:
                            result["cid"] = publish_result["publish"]["cid"]
                else:
                    # Propagate error information
                    error_msg = publish_result.get("error", "Unknown error")
                    error_type = publish_result.get("error_type", "unknown_error")
                    
                    # Still include partial results if available
                    extra_data = {}
                    if "add" in publish_result:
                        extra_data["add"] = publish_result["add"]
                    
                    return handle_error(
                        result, 
                        IPFSError(f"Failed to publish to IPNS: {error_msg}"),
                        extra_data
                    )
            else:
                # Handle legacy format (directly returning a string or non-dictionary)
                result["success"] = True
                result["path"] = path
                result["legacy_result"] = publish_result
                
                # Warn about legacy format
                result["warning"] = "Using legacy result format"
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    
    def ipfs_remove_path(self, path=None, **kwargs):
        """Remove a file or directory from IPFS with standardized error handling.
        
        Args:
            path: Path to the file or directory to remove
            **kwargs: Additional arguments for the remove operation including
                     'correlation_id' for tracing
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_remove_path"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if path is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: path"))
                
            # Validate command arguments for security
            try:
                from .validation import validate_command_args, validate_required_parameter, validate_parameter_type
                validate_command_args(kwargs)
                validate_required_parameter(path, "path")
                validate_parameter_type(path, str, "path")
                
                # For MFS paths, we don't need to validate as filesystem paths
                if not path.startswith("/ipfs/") and not path.startswith("/ipns/"):
                    # Check for command injection in path
                    from .validation import COMMAND_INJECTION_PATTERNS
                    import re
                    if any(re.search(pattern, path) for pattern in COMMAND_INJECTION_PATTERNS):
                        return handle_error(result, IPFSValidationError(f"Path contains potentially malicious patterns: {path}"))
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Add the correlation ID to kwargs for propagation
            kwargs['correlation_id'] = correlation_id
            
            # Track results from cluster and IPFS operations
            cluster_result = None
            ipfs_result = None
            
            # Execute operations based on role
            if self.role == "master":
                # For master, remove from both IPFS cluster and local IPFS
                try:
                    # First remove from IPFS cluster
                    cluster_result = self.ipfs_cluster_ctl.ipfs_cluster_ctl_remove_path(path, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error removing from IPFS cluster: {str(e)}")
                    result["cluster_error"] = str(e)
                
                try:
                    # Then remove from local IPFS
                    ipfs_result = self.ipfs.ipfs_remove_path(path, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error removing from IPFS: {str(e)}")
                    result["ipfs_error"] = str(e)
                    
            elif self.role == "worker" or self.role == "leecher":
                # For worker/leecher, just remove from local IPFS
                try:
                    ipfs_result = self.ipfs.ipfs_remove_path(path, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error removing from IPFS: {str(e)}")
                    result["ipfs_error"] = str(e)
            
            # Determine overall success based on role
            if self.role == "master":
                # Cluster operation is optional for success
                cluster_success = isinstance(cluster_result, dict) and cluster_result.get("success", False)
                ipfs_success = isinstance(ipfs_result, dict) and ipfs_result.get("success", False)
                
                result["success"] = ipfs_success  # Consider success if IPFS operation worked
            else:
                # For non-master, success depends only on IPFS operation
                ipfs_success = isinstance(ipfs_result, dict) and ipfs_result.get("success", False)
                result["success"] = ipfs_success
            
            # Include individual operation results
            result["path"] = path
            if cluster_result is not None:
                result["ipfs_cluster"] = cluster_result
            result["ipfs"] = ipfs_result
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def ipfs_remove_pin(self, pin=None, **kwargs):
        """Remove a pin from IPFS with standardized error handling.
        
        Args:
            pin: CID to unpin
            **kwargs: Additional arguments for the unpin operation including
                     'correlation_id' for tracing
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_remove_pin"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if pin is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: pin"))
                
            # Validate command arguments for security
            try:
                from .validation import validate_command_args, validate_required_parameter, validate_parameter_type
                validate_command_args(kwargs)
                validate_required_parameter(pin, "pin")
                validate_parameter_type(pin, str, "pin")
                
                # Validate CID format
                try:
                    from .validation import is_valid_cid
                    if not is_valid_cid(pin):
                        return handle_error(result, IPFSValidationError(f"Invalid CID format: {pin}"))
                except ImportError:
                    # If validation module is not fully available, continue with basic checks
                    pass
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Add the correlation ID to kwargs for propagation
            kwargs['correlation_id'] = correlation_id
            
            # Track results from cluster and IPFS operations
            cluster_result = None
            ipfs_result = None
            
            # Execute operations based on role
            if self.role == "master":
                # For master, unpin from both IPFS cluster and local IPFS
                try:
                    # First unpin from IPFS cluster
                    cluster_result = self.ipfs_cluster_ctl.ipfs_cluster_ctl_remove_pin(pin, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error removing pin from IPFS cluster: {str(e)}")
                    result["cluster_error"] = str(e)
                
                try:
                    # Then unpin from local IPFS
                    ipfs_result = self.ipfs.ipfs_remove_pin(pin, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error removing pin from IPFS: {str(e)}")
                    result["ipfs_error"] = str(e)
                    
            elif self.role == "worker" or self.role == "leecher":
                # For worker/leecher, just unpin from local IPFS
                try:
                    ipfs_result = self.ipfs.ipfs_remove_pin(pin, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error removing pin from IPFS: {str(e)}")
                    result["ipfs_error"] = str(e)
            
            # Determine overall success based on role
            if self.role == "master":
                # Cluster operation is optional for success
                cluster_success = isinstance(cluster_result, dict) and cluster_result.get("success", False)
                ipfs_success = isinstance(ipfs_result, dict) and ipfs_result.get("success", False)
                
                result["success"] = ipfs_success  # Consider success if IPFS operation worked
                result["fully_successful"] = ipfs_success and cluster_success  # Flag for complete success
            else:
                # For non-master, success depends only on IPFS operation
                ipfs_success = isinstance(ipfs_result, dict) and ipfs_result.get("success", False)
                result["success"] = ipfs_success
            
            # Include individual operation results
            result["cid"] = pin
            if cluster_result is not None:
                result["ipfs_cluster"] = cluster_result
            result["ipfs"] = ipfs_result
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def test_install(self, **kwargs):
        if self.role == "master":
            return {
                "ipfs_cluster_service": self.install_ipfs.ipfs_cluster_service_test_install(),
                "ipfs_cluster_ctl": self.install_ipfs.ipfs_cluster_ctl_test_install(),
                "ipfs": self.install_ipfs.ipfs_test_install()
            }
        elif self.role == "worker":
            return {
                "ipfs_cluster_follow": self.install_ipfs.ipfs_cluster_follow_test_install(),
                "ipfs": self.install_ipfs.ipfs_test_install()
            }
        elif self.role == "leecher":
            return self.install_ipfs.ipfs_test_install()
        else:
            raise Exception("role is not master, worker, or leecher")
        
    def ipfs_get_pinset(self, **kwargs):

        ipfs_pinset =  self.ipfs.ipfs_get_pinset(**kwargs)

        ipfs_cluster = None
        if self.role == "master":
            ipfs_cluster = self.ipfs_cluster_ctl.ipfs_cluster_get_pinset(**kwargs)
        elif self.role == "worker":
            ipfs_cluster = self.ipfs_cluster_follow.ipfs_follow_list(**kwargs)
        elif self.role == "leecher":
            pass

        results = {
            "ipfs_cluster": ipfs_cluster,
            "ipfs": ipfs_pinset
        }
        return results
            
    def ipfs_kit_stop(self, **kwargs):
        """Stop all IPFS services with standardized error handling.
        
        This stops the IPFS daemon, IPFS cluster components, and libp2p peer
        based on the node's role.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with stop status for each component
        """
        ipfs_cluster_service = None
        ipfs_cluster_follow = None
        ipfs = None
        libp2p = None

        # Stop components based on role
        if self.role == "master":
            try:
                ipfs_cluster_service = self.ipfs_cluster_service.ipfs_cluster_service_stop()
            except Exception as e:
                ipfs_cluster_service = str(e)
            try:
                ipfs = self.ipfs.daemon_stop()
            except Exception as e:
                ipfs = str(e)
        elif self.role == "worker":
            try:
                ipfs_cluster_follow = self.ipfs_cluster_follow.ipfs_follow_stop()
            except Exception as e:
                ipfs_cluster_follow = str(e)
            try:
                ipfs = self.ipfs.daemon_stop()
            except Exception as e:
                ipfs = str(e)
        elif self.role == "leecher":
            try:
                ipfs = self.ipfs.daemon_stop()
            except Exception as e:
                ipfs = str(e)
        
        # Stop libp2p peer if it exists
        if hasattr(self, 'libp2p') and self.libp2p is not None:
            try:
                self.close_libp2p()
                libp2p = "Stopped"
            except Exception as e:
                libp2p = str(e)
        
        return {
            "ipfs_cluster_service": ipfs_cluster_service,
            "ipfs_cluster_follow": ipfs_cluster_follow,
            "ipfs": ipfs,
            "libp2p": libp2p
        }
        
    def ipfs_kit_start(self, **kwargs):
        """Start all IPFS services with standardized error handling.
        
        This starts the IPFS daemon, IPFS cluster components, and optionally
        the libp2p peer based on the node's role and configuration.
        
        Args:
            **kwargs: Additional arguments including 'enable_libp2p'
            
        Returns:
            Dictionary with start status for each component
        """
        ipfs_cluster_service = None
        ipfs_cluster_follow = None
        ipfs = None
        libp2p = None
        
        # Process arguments
        enable_libp2p = kwargs.get('enable_libp2p', False)
        
        # Start components based on role
        if self.role == "master":
            try:
                ipfs = self.ipfs.daemon_start()
            except Exception as e:
                ipfs = str(e)
            try:
                ipfs_cluster_service = self.ipfs_cluster_service.ipfs_cluster_service_start()
            except Exception as e:
                ipfs_cluster_service = str(e)
        elif self.role == "worker":
            try:
                ipfs = self.ipfs.daemon_start()
            except Exception as e:
                ipfs = str(e)
            try:
                ipfs_cluster_follow = self.ipfs_cluster_follow.ipfs_follow_start()
            except Exception as e:
                ipfs_cluster_follow = str(e)
        elif self.role == "leecher":
            try:
                ipfs = self.ipfs.daemon_start()
            except Exception as e:
                ipfs = str(e)
        
        # Start libp2p peer if requested
        if enable_libp2p:
            try:
                # Close existing peer if any
                if hasattr(self, 'libp2p') and self.libp2p:
                    self.close_libp2p()
                
                # Initialize new peer
                success = self._setup_libp2p(**kwargs)
                libp2p = "Started" if success else "Failed to start"
            except Exception as e:
                libp2p = str(e)

        return {
            "ipfs_cluster_service": ipfs_cluster_service,
            "ipfs_cluster_follow": ipfs_cluster_follow,
            "ipfs": ipfs,
            "libp2p": libp2p
        }
    
    def ipfs_get_config(self, **kwargs):
        """Get IPFS configuration with standardized error handling.
        
        Args:
            **kwargs: Additional arguments like correlation_id
            
        Returns:
            Result dictionary with IPFS configuration
        """
        operation = "ipfs_get_config"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate command arguments for security
            try:
                from .validation import validate_command_args
                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Build command with proper arguments
            cmd = ["ipfs", "config", "show"]
            
            # Use run_ipfs_command if available, otherwise fallback to subprocess
            if hasattr(self.ipfs, 'run_ipfs_command'):
                cmd_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
                
                if not cmd_result["success"]:
                    return handle_error(result, IPFSError(f"Failed to get config: {cmd_result.get('error', 'Unknown error')}"))
                
                # Parse JSON output
                try:
                    output = cmd_result.get("stdout", "")
                    config_data = json.loads(output)
                    
                    # Store for future reference
                    self.ipfs_config = config_data
                    
                    # Set result information
                    result["success"] = True
                    result["config"] = config_data
                    
                    return result
                except json.JSONDecodeError as e:
                    return handle_error(result, IPFSError(f"Failed to parse config JSON: {str(e)}"))
            else:
                # Fallback to direct subprocess call
                try:
                    env = os.environ.copy()
                    process = subprocess.run(
                        cmd,
                        capture_output=True,
                        check=True,
                        shell=False,
                        env=env
                    )
                    
                    # Parse JSON output
                    try:
                        config_data = json.loads(process.stdout)
                        
                        # Store for future reference
                        self.ipfs_config = config_data
                        
                        # Set result information
                        result["success"] = True
                        result["config"] = config_data
                        
                        return result
                    except json.JSONDecodeError as e:
                        return handle_error(result, IPFSError(f"Failed to parse config JSON: {str(e)}"))
                        
                except subprocess.CalledProcessError as e:
                    return handle_error(result, IPFSError(f"Command failed with return code {e.returncode}: {e.stderr.decode()}"))
                except Exception as e:
                    return handle_error(result, e)
            
        except Exception as e:
            return handle_error(result, e)
    
    def ipfs_set_config(self, new_config=None, **kwargs):
        """Set IPFS configuration with standardized error handling.
        
        Args:
            new_config: New configuration to apply (dictionary)
            **kwargs: Additional arguments like correlation_id
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_set_config"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if new_config is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: new_config"))
                
            if not isinstance(new_config, dict):
                return handle_error(result, IPFSValidationError(f"Invalid config type: expected dict, got {type(new_config).__name__}"))
            
            # Validate command arguments for security
            try:
                from .validation import validate_command_args
                validate_command_args(kwargs)
            except IPFSValidationError as e:
                return handle_error(result, e)
            
            # Write config to temporary file
            try:
                with tempfile.NamedTemporaryFile(suffix=".json", mode="w+", delete=False) as temp_file:
                    json.dump(new_config, temp_file)
                    temp_file_path = temp_file.name
            except Exception as e:
                return handle_error(result, IPFSError(f"Failed to create temporary config file: {str(e)}"))
            
            try:
                # Build command with proper arguments
                cmd = ["ipfs", "config", "replace", temp_file_path]
                
                # Use run_ipfs_command if available, otherwise fallback to subprocess
                if hasattr(self.ipfs, 'run_ipfs_command'):
                    cmd_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
                    
                    # Clean up temp file
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        # Log but don't fail operation if cleanup fails
                        self.logger.warning(f"Failed to remove temporary file {temp_file_path}: {str(e)}")
                    
                    if not cmd_result["success"]:
                        return handle_error(result, IPFSError(f"Failed to set config: {cmd_result.get('error', 'Unknown error')}"))
                    
                    # Set result information
                    result["success"] = True
                    result["message"] = "Configuration updated successfully"
                    self.ipfs_config = new_config
                    
                    return result
                else:
                    # Fallback to direct subprocess call
                    try:
                        env = os.environ.copy()
                        process = subprocess.run(
                            cmd,
                            capture_output=True,
                            check=True,
                            shell=False,
                            env=env
                        )
                        
                        # Clean up temp file
                        try:
                            os.unlink(temp_file_path)
                        except Exception as e:
                            # Log but don't fail operation if cleanup fails
                            self.logger.warning(f"Failed to remove temporary file {temp_file_path}: {str(e)}")
                        
                        # Set result information
                        result["success"] = True
                        result["message"] = "Configuration updated successfully"
                        result["output"] = process.stdout.decode()
                        self.ipfs_config = new_config
                        
                        return result
                            
                    except subprocess.CalledProcessError as e:
                        # Clean up temp file before returning error
                        try:
                            os.unlink(temp_file_path)
                        except Exception:
                            pass
                            
                        return handle_error(result, IPFSError(f"Command failed with return code {e.returncode}: {e.stderr.decode()}"))
                    except Exception as e:
                        # Clean up temp file before returning error
                        try:
                            os.unlink(temp_file_path)
                        except Exception:
                            pass
                            
                        return handle_error(result, e)
            except Exception as e:
                # Clean up temp file on any other exception
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
                    
                return handle_error(result, e)
            
        except Exception as e:
            return handle_error(result, e)
        
    def ipfs_get_config_value(self, key=None, **kwargs):
        """Get a specific IPFS configuration value with standardized error handling.
        
        Args:
            key: Configuration key to retrieve
            **kwargs: Additional arguments like correlation_id
            
        Returns:
            Result dictionary with configuration value
        """
        operation = "ipfs_get_config_value"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if key is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: key"))
                
            if not isinstance(key, str):
                return handle_error(result, IPFSValidationError(f"Invalid key type: expected string, got {type(key).__name__}"))
            
            # Validate command arguments for security
            try:
                from .validation import validate_command_args
                validate_command_args(kwargs)
                
                # Check for command injection in key
                from .validation import COMMAND_INJECTION_PATTERNS
                if any(re.search(pattern, key) for pattern in COMMAND_INJECTION_PATTERNS):
                    return handle_error(result, IPFSValidationError(f"Key contains potentially malicious patterns: {key}"))
            except IPFSValidationError as e:
                return handle_error(result, e)
            except ImportError:
                # If we can't import the validation module, do a basic check
                import re
                if re.search(r'[;&|`$]', key):
                    return handle_error(result, IPFSError(f"Key contains invalid characters: {key}"))
            
            # Build command with proper arguments
            cmd = ["ipfs", "config", key]
            
            # Use run_ipfs_command if available, otherwise fallback to subprocess
            if hasattr(self.ipfs, 'run_ipfs_command'):
                cmd_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
                
                if not cmd_result["success"]:
                    return handle_error(result, IPFSError(f"Failed to get config value: {cmd_result.get('error', 'Unknown error')}"))
                
                # Parse output
                try:
                    output = cmd_result.get("stdout", "")
                    
                    # Try to parse as JSON
                    try:
                        config_value = json.loads(output)
                    except json.JSONDecodeError:
                        # Not JSON, just use the string value
                        config_value = output.strip()
                    
                    # Set result information
                    result["success"] = True
                    result["key"] = key
                    result["value"] = config_value
                    
                    return result
                except Exception as e:
                    return handle_error(result, IPFSError(f"Failed to parse config value: {str(e)}"))
            else:
                # Fallback to direct subprocess call
                try:
                    env = os.environ.copy()
                    process = subprocess.run(
                        cmd,
                        capture_output=True,
                        check=True,
                        shell=False,
                        env=env
                    )
                    
                    # Parse output
                    try:
                        output = process.stdout.decode()
                        
                        # Try to parse as JSON
                        try:
                            config_value = json.loads(output)
                        except json.JSONDecodeError:
                            # Not JSON, just use the string value
                            config_value = output.strip()
                        
                        # Set result information
                        result["success"] = True
                        result["key"] = key
                        result["value"] = config_value
                        
                        return result
                    except Exception as e:
                        return handle_error(result, IPFSError(f"Failed to parse config value: {str(e)}"))
                        
                except subprocess.CalledProcessError as e:
                    return handle_error(result, IPFSError(f"Command failed with return code {e.returncode}: {e.stderr.decode()}"))
                except Exception as e:
                    return handle_error(result, e)
            
        except Exception as e:
            return handle_error(result, e)

    def ipfs_set_config_value(self, key=None, value=None, **kwargs):
        """Set a specific IPFS configuration value with standardized error handling.
        
        Args:
            key: Configuration key to set
            value: Configuration value to set
            **kwargs: Additional arguments like correlation_id
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "ipfs_set_config_value"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate required parameters
            if key is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: key"))
                
            if value is None:
                return handle_error(result, IPFSValidationError("Missing required parameter: value"))
                
            if not isinstance(key, str):
                return handle_error(result, IPFSValidationError(f"Invalid key type: expected string, got {type(key).__name__}"))
            
            # Ensure value is a string or can be converted to a string
            if isinstance(value, (dict, list)):
                # Convert dict/list to JSON string
                value_str = json.dumps(value)
            else:
                # Convert other types to string
                value_str = str(value)
            
            # Validate command arguments for security
            try:
                from .validation import validate_command_args
                validate_command_args(kwargs)
                
                # Check for command injection in key and value
                from .validation import COMMAND_INJECTION_PATTERNS
                if any(re.search(pattern, key) for pattern in COMMAND_INJECTION_PATTERNS):
                    return handle_error(result, IPFSValidationError(f"Key contains potentially malicious patterns: {key}"))
                
                if any(re.search(pattern, value_str) for pattern in COMMAND_INJECTION_PATTERNS):
                    return handle_error(result, IPFSValidationError(f"Value contains potentially malicious patterns"))
            except IPFSValidationError as e:
                return handle_error(result, e)
            except ImportError:
                # If we can't import the validation module, do a basic check
                import re
                if re.search(r'[;&|`$]', key) or re.search(r'[;&|`$]', value_str):
                    return handle_error(result, IPFSError(f"Key or value contains invalid characters"))
            
            # Check if we need to set as JSON value
            is_json_value = isinstance(value, (dict, list))
            
            # Build command with proper arguments
            if is_json_value:
                # Use --json flag for structured data
                cmd = ["ipfs", "config", "--json", key, value_str]
            else:
                cmd = ["ipfs", "config", key, value_str]
            
            # Use run_ipfs_command if available, otherwise fallback to subprocess
            if hasattr(self.ipfs, 'run_ipfs_command'):
                cmd_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
                
                if not cmd_result["success"]:
                    return handle_error(result, IPFSError(f"Failed to set config value: {cmd_result.get('error', 'Unknown error')}"))
                
                # Set result information
                result["success"] = True
                result["key"] = key
                result["value"] = value
                result["message"] = "Configuration value set successfully"
                
                return result
            else:
                # Fallback to direct subprocess call
                try:
                    env = os.environ.copy()
                    process = subprocess.run(
                        cmd,
                        capture_output=True,
                        check=True,
                        shell=False,
                        env=env
                    )
                    
                    # Set result information
                    result["success"] = True
                    result["key"] = key
                    result["value"] = value
                    result["message"] = "Configuration value set successfully"
                    
                    return result
                        
                except subprocess.CalledProcessError as e:
                    return handle_error(result, IPFSError(f"Command failed with return code {e.returncode}: {e.stderr.decode()}"))
                except Exception as e:
                    return handle_error(result, e)
            
        except Exception as e:
            return handle_error(result, e)
   

    def check_collection(self, collection):
        status = {}
        collection_keys = list(collection.keys())
        pinset_keys = list(self.pinset.keys())
        orphan_models = []
        orphan_pins = []
        active_pins = []
        active_models = []

        for this_model in collection_keys:
            if this_model != "cache":
                this_manifest = collection[this_model]
                this_id = this_manifest["id"]
                this_cache = this_manifest["cache"]
                this_ipfs_cache = this_cache["ipfs"]
                this_ipfs_cache_keys = list(this_ipfs_cache.keys())
                found_all = True

                for this_cache_basename in this_ipfs_cache_keys:
                    this_cache_item = this_ipfs_cache[this_cache_basename]
                    this_cache_item_path = this_cache_item["path"]
                    this_cache_item_url = this_cache_item["url"]

                    if this_cache_item_path in pinset_keys:
                        active_pins.append(this_cache_item_path)
                    else:
                        found_all = False

                if found_all:
                    active_models.append(this_model)
                else:
                    orphan_models.append(this_model)

        for this_pin in pinset_keys:
            if this_pin not in active_pins:
                orphan_pins.append(this_pin)

        status["orphan_models"] = orphan_models
        status["orphan_pins"] = orphan_pins
        status["active_pins"] = active_pins
        status["active_models"] = active_models

        return status
    
    def ipfs_upload_object(self, **kwargs):
        return self.upload_object(kwargs['file'])
    
    def ipget_download_object(self, **kwargs):
        return self.ipget.ipget_download_object(**kwargs)

    def perform_with_retry(self, operation_func, *args, max_retries=3, backoff_factor=2, **kwargs):
        """Perform operation with exponential backoff retry for recoverable errors.
        
        This is a wrapper for the perform_with_retry function in the error module.
        
        Args:
            operation_func: Function to execute
            args: Positional arguments for the function
            max_retries: Maximum number of retry attempts
            backoff_factor: Factor to multiply retry delay by after each attempt
            kwargs: Keyword arguments for the function
            
        Returns:
            Result from the operation function or error result if all retries fail
        """
        return perform_with_retry(operation_func, *args, max_retries=max_retries, 
                                 backoff_factor=backoff_factor, **kwargs)
    
    def update_collection_ipfs(self, collection, collection_path, **kwargs):
        """Update a collection in IPFS with standardized error handling and retries.
        
        Args:
            collection: Collection data structure to update
            collection_path: Path to the collection file
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with operation outcome
        """
        operation = "update_collection_ipfs"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Validate inputs
            if not collection_path or not os.path.exists(collection_path):
                raise IPFSValidationError(f"Collection path not found: {collection_path}")
                
            # Ensure collection is a dictionary
            if not isinstance(collection, dict):
                raise IPFSValidationError("Collection must be a dictionary")
                
            # Add the file to IPFS
            cmd = ["ipfs", "add", "-r", collection_path]
            add_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
            
            if not add_result["success"]:
                return add_result
                
            # Parse the output to get the CID
            stdout = add_result.get("stdout", "")
            collection_cid = None
            
            for line in stdout.split("\n"):
                if line.strip():
                    parts = line.strip().split(" ")
                    if len(parts) >= 2 and parts[0] == "added":
                        collection_cid = parts[1]
                        # The last one will be the root CID
            
            if not collection_cid:
                return handle_error(result, IPFSError("Failed to extract CID from add command output"))
                
            # Pin the collection in the cluster if we're a master
            if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                metadata = ["path=/collection.json"]
                pin_args = ["ipfs-cluster-ctl", "pin", "add"]
                
                # Add metadata
                for meta in metadata:
                    pin_args.extend(["--metadata", meta])
                    
                # Add the CID
                pin_args.append(collection_cid)
                
                # Run the command
                pin_result = self.ipfs.run_ipfs_command(pin_args, correlation_id=correlation_id)
                
                if not pin_result["success"]:
                    result["add_success"] = True
                    result["pin_success"] = False
                    result["cid"] = collection_cid
                    result["warning"] = "Added to IPFS but failed to pin in cluster"
                    result["pin_error"] = pin_result["error"]
                    return result
            
            # Update the collection cache
            if "cache" not in collection:
                collection["cache"] = {}
            collection["cache"]["ipfs"] = collection_cid
            
            # Set result information
            result["success"] = True
            result["cid"] = collection_cid
            result["collection_updated"] = True
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def test(self):
        results = {}
        test_ipfs_kit_install = None
        test_ipfs_kit = None
        test_ipfs_kit_stop = None
        test_ipfs_kit_start = None
        test_ipfs_kit_ready = None
        test_ipfs_kit_get_config = None
        test_ipfs_kit_set_config = None
        test_ipfs_kit_get_config_value = None
        test_ipfs_kit_set_config_value = None
        test_ipfs_kit_get_pinset = None
        test_ipfs_kit_add_pin = None
        test_ipfs_kit_remove_pin = None
        test_ipfs_kit_upload_object = None
        test_ipfs_kit_download_object = None
        test_ipfs_kit_name_resolve = None
        test_ipfs_kit_name_publish = None
        test_ipfs_kit_add_path = None
        test_ipfs_kit_ls_path = None
        test_ipfs_kit_remove_path = None
        test_ipfs_kit_get = None
        test_ipfs_kit_get_pinset = None
        test_ipfs_kit_load_collection = None
        test_ipfs_kit_update_collection_ipfs = None
        test_ipfs_kit_check_collection = None
        test_ipfs_kit_ipfs_get_config = None
        test_ipfs_kit_ipfs_set_config = None
        test_ipfs_kit_ipfs_get_config_value = None
        test_ipfs_kit_ipfs_set_config_value = None
        test_ipfs_kit_storacha_kit = None
        try:
            results["test_install"] = self.test_install()
        except Exception as e:
            results["test_install"] = e
        try:
            results["test_ipfs_kit_stop"] = self.ipfs_kit_stop()
        except Exception as e:
            results["test_ipfs_kit_stop"] = e
        try:
            results["test_ipfs_kit_start"] = self.ipfs_kit_start()
        except Exception as e:
            results["test_ipfs_kit_start"] = e
        try:
            results["test_ipfs_kit_ready"] = self.ipfs_kit_ready()
        except Exception as e:
            results["test_ipfs_kit_ready"] = e
        try:
            results["test_ipfs_kit_get_config"] = self.ipfs_get_config()
        except Exception as e:
            results["test_ipfs_kit_get_config"] = e
        try:
            results["test_ipfs_kit_set_config"] = self.ipfs_set_config()
        except Exception as e:
            results["test_ipfs_kit_set_config"] = e
        try:
            results["test_ipfs_kit_get_config_value"] = self.ipfs_get_config_value()
        except Exception as e:
            results["test_ipfs_kit_get_config_value"] = e
        try:
            results["test_ipfs_kit_set_config_value"] = self.ipfs_set_config_value()
        except Exception as e:
            results["test_ipfs_kit_set_config_value"] = e
        try:    
            results["test_ipfs_kit_get_pinset"] = self.ipfs_get_pinset()
        except Exception as e:
            results["test_ipfs_kit_get_pinset"] = e
        try:
            results["test_ipfs_kit_add_pin"] = self.ipfs_add_pin()
        except Exception as e:
            results["test_ipfs_kit_add_pin"] = e
        try:
            results["test_ipfs_kit_remove_pin"] = self.ipfs_remove_pin()
        except Exception as e:
            results["test_ipfs_kit_remove_pin"] = e
        try:
            results["test_ipfs_kit_upload_object"] = self.ipfs_upload_object()
        except Exception as e:
            results["test_ipfs_kit_upload_object"] = e
        try:
            results["test_ipfs_kit_download_object"] = self.ipget_download_object()
        except Exception as e:
            results["test_ipfs_kit_download_object"] = e
        try:
            results["test_ipfs_kit_name_resolve"] = self.name_resolve()
        except Exception as e:
            results["test_ipfs_kit_name_resolve"] = e
        try:
            results["test_ipfs_kit_name_publish"] = self.name_publish()
        except Exception as e:
            results["test_ipfs_kit_name_publish"] = e
        try:
            results["test_ipfs_kit_add_path"] = self.ipfs_add_path()
        except Exception as e:
            results["test_ipfs_kit_add_path"] = e
        try:
            results["test_ipfs_kit_ls_path"] = self.ipfs_ls_path()
        except Exception as e:
            results["test_ipfs_kit_ls_path"] = e
        try:
            results["test_ipfs_kit_remove_path"] = self.ipfs_remove_path()
        except Exception as e:
            results["test_ipfs_kit_remove_path"] = e
        try:
            results["test_ipfs_kit_get"] = self.ipfs_get()
        except Exception as e:
            results["test_ipfs_kit_get"] = e
        try:
            results["test_ipfs_kit_storacha_kit"] = self.storacha_kit.test()
        except Exception as e:
            results["test_ipfs_kit_storacha_kit"] = e                
        try:
            results["test_ipfs_kit"] = self.test()
        except Exception as e:
            results["test_ipfs_kit"] = e
        return results
    
    def _setup_libp2p(self, resources=None, metadata=None):
        """Set up the libp2p peer for direct P2P communication.
        
        This initializes the libp2p peer component with appropriate
        configuration based on node role and available resources.
        
        Args:
            resources: Available resources for the peer
            metadata: Additional configuration parameters
        
        Returns:
            True if setup succeeded, False otherwise
        """
        if not HAS_LIBP2P:
            self.logger.warning(
                "libp2p functionality is not available. Install libp2p "
                "package for direct peer-to-peer communication."
            )
            return False
            
        try:
            # Get IPFS path for storing identity
            ipfs_path = getattr(self, 'ipfs_path', os.path.expanduser("~/.ipfs"))
            
            # Set up identity path
            identity_path = os.path.join(ipfs_path, "libp2p", "identity.key")
            
            # Create directory if needed
            os.makedirs(os.path.dirname(identity_path), exist_ok=True)
            
            # Extract bootstrap peers if available
            bootstrap_peers = None
            if hasattr(self, 'config') and isinstance(self.config, dict):
                # Try to extract bootstrap peers from IPFS config
                if "Bootstrap" in self.config:
                    bootstrap_peers = self.config["Bootstrap"]
                    
            # Configure based on role
            enable_mdns = True
            enable_hole_punching = False
            enable_relay = False
            
            if self.role == "master":
                # Master nodes focus on coordination
                enable_hole_punching = True
                enable_relay = True
            elif self.role == "worker":
                # Worker nodes participate in content exchange
                enable_hole_punching = True
                enable_relay = self.role == "worker"
            
            # Initialize the libp2p peer
            self.libp2p = IPFSLibp2pPeer(
                identity_path=identity_path,
                bootstrap_peers=bootstrap_peers,
                role=self.role,
                enable_mdns=enable_mdns,
                enable_hole_punching=enable_hole_punching,
                enable_relay=enable_relay
            )
            
            self.logger.info(f"Initialized libp2p peer with ID: {self.libp2p.get_peer_id()}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize libp2p peer: {str(e)}")
            self.libp2p = None
            return False
            
    def _setup_cluster_management(self, resources=None, metadata=None):
        """Set up the cluster management components.
        
        This initializes the ClusterManager component, which integrates
        the ClusterCoordinator and IPFSLibp2pPeer for distributed
        task coordination and content management.
        
        Args:
            resources: Available resources for the cluster
            metadata: Additional configuration parameters
        
        Returns:
            True if setup succeeded, False otherwise
        """
        if not HAS_CLUSTER_MANAGEMENT:
            self.logger.warning(
                "Cluster management functionality is not available. "
                "Check that cluster_coordinator.py and cluster_management.py are installed."
            )
            return False
            
        try:
            # Get node ID (use hostname if not specified)
            node_id = metadata.get("node_id") if metadata else None
            if not node_id:
                import socket
                node_id = socket.gethostname()
                
            # Get peer ID from libp2p if available, otherwise use IPFS identity
            peer_id = None
            if hasattr(self, 'libp2p') and self.libp2p:
                peer_id = self.libp2p.get_peer_id()
            else:
                # Try to get from IPFS identity
                try:
                    id_info = self.ipfs.ipfs_id()
                    if isinstance(id_info, dict) and "ID" in id_info:
                        peer_id = id_info["ID"]
                except Exception as e:
                    self.logger.warning(f"Failed to get IPFS identity: {str(e)}")
                    
            if not peer_id:
                self.logger.warning("No peer ID available, using node ID as fallback")
                peer_id = node_id
                
            # Prepare configuration
            config = dict(self.config) if hasattr(self, 'config') else {}
            
            # Add cluster-specific configuration
            if "cluster_id" not in config and hasattr(self, 'cluster_name'):
                config["cluster_id"] = self.cluster_name
                
            # Default cluster ID if none specified
            if "cluster_id" not in config:
                config["cluster_id"] = "default"
                
            # Add IP address information if available
            if "address" not in config:
                try:
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    config["address"] = s.getsockname()[0]
                    s.close()
                except Exception:
                    config["address"] = "127.0.0.1"
                    
            # Set up resources information
            if resources:
                config["resources"] = resources
            else:
                # Try to detect resources
                try:
                    import psutil
                    
                    # Get CPU, memory, and disk information
                    cpu_count = psutil.cpu_count()
                    memory_info = psutil.virtual_memory()
                    disk_info = psutil.disk_usage('/')
                    
                    config["resources"] = {
                        "cpu_cores": cpu_count,
                        "memory_mb": memory_info.total // (1024 * 1024),
                        "disk_space_mb": disk_info.total // (1024 * 1024)
                    }
                    
                    # Try to get GPU information if available
                    try:
                        import gputil
                        gpus = gputil.getGPUs()
                        if gpus:
                            # Sum memory across all GPUs
                            gpu_memory = sum(gpu.memoryTotal for gpu in gpus)
                            config["resources"]["gpu_memory_mb"] = gpu_memory
                    except ImportError:
                        pass
                        
                except ImportError:
                    self.logger.warning("psutil not available, using minimal resource information")
                    config["resources"] = {
                        "cpu_cores": 1,
                        "memory_mb": 1024,
                        "disk_space_mb": 10240
                    }
                    
            # Initialize the ClusterManager
            self.cluster_manager = ClusterManager(
                node_id=node_id,
                role=self.role,
                peer_id=peer_id,
                config=config,
                resources=resources,
                metadata=metadata,
                enable_libp2p=hasattr(self, 'libp2p') and self.libp2p is not None
            )
            
            # Start the cluster manager
            start_result = self.cluster_manager.start()
            
            if not start_result.get("success", False):
                self.logger.warning(f"Cluster manager started with warnings: {start_result}")
                
            self.logger.info(f"Initialized cluster manager with role: {self.role}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize cluster manager: {str(e)}")
            self.cluster_manager = None
            return False
    
    def get_from_peers(self, cid):
        """Get content directly from peers using libp2p.
        
        This method attempts to retrieve content directly from connected peers
        using libp2p without going through the IPFS daemon.
        
        Args:
            cid: Content identifier to retrieve
            
        Returns:
            Content data if found, None otherwise
        """
        if not self.libp2p:
            self.logger.warning("libp2p not available, can't get content from peers")
            return None
            
        try:
            # Request content from peers
            content = self.libp2p.request_content(cid)
            return content
        except Exception as e:
            self.logger.error(f"Error getting content from peers: {str(e)}")
            return None
    
    def find_content_providers(self, cid, count=20):
        """Find peers that have the requested content.
        
        This method uses the DHT to find peers that can provide the specified content.
        
        Args:
            cid: Content identifier to look for
            count: Maximum number of providers to find
            
        Returns:
            List of provider information dictionaries
        """
        if not self.libp2p:
            self.logger.warning("libp2p not available, can't find content providers")
            return []
            
        try:
            # Find providers via DHT
            providers = self.libp2p.find_providers(cid, count=count)
            return providers
        except Exception as e:
            self.logger.error(f"Error finding content providers: {str(e)}")
            return []
    
    def get_content(self, cid, use_p2p=False, use_fallback=True):
        """Get content with optional P2P retrieval and fallback.
        
        This method provides a flexible way to retrieve content, with options to
        try direct peer-to-peer retrieval and/or fallback to the IPFS daemon.
        
        Args:
            cid: Content identifier to retrieve
            use_p2p: Whether to try direct P2P retrieval first
            use_fallback: Whether to fall back to daemon if P2P fails
            
        Returns:
            Content data if found, None otherwise
        """
        result = None
        
        # Try P2P retrieval if requested
        if use_p2p and self.libp2p:
            try:
                result = self.get_from_peers(cid)
                if result:
                    return result
            except Exception as e:
                self.logger.warning(f"P2P retrieval failed: {str(e)}")
                
        # Fall back to daemon if needed
        if (not result and use_fallback) or not use_p2p:
            try:
                resp = self.ipfs.cat(cid)
                if isinstance(resp, dict) and "Data" in resp:
                    return resp["Data"]
                return resp
            except Exception as e:
                self.logger.error(f"Daemon retrieval failed: {str(e)}")
                
        return result
    
    def add(self, data, **kwargs):
        """Add content to IPFS with optional P2P announcement.
        
        This method adds data to IPFS and optionally announces it to the
        P2P network for direct retrieval by peers.
        
        Args:
            data: Content to add
            **kwargs: Additional arguments for the add operation
            
        Returns:
            Result dictionary with operation details
        """
        # Add to IPFS using regular method
        result = self.ipfs.add(data, **kwargs)
        
        # Check if add was successful
        if isinstance(result, dict) and "Hash" in result:
            cid = result["Hash"]
            
            # Announce to P2P network if libp2p is available
            if self.libp2p:
                try:
                    # Determine content size for metadata
                    size = None
                    if hasattr(data, 'read'):
                        # For file-like objects, get size if possible
                        if hasattr(data, 'seek') and hasattr(data, 'tell'):
                            pos = data.tell()
                            data.seek(0, os.SEEK_END)
                            size = data.tell()
                            data.seek(pos)
                    elif isinstance(data, (bytes, bytearray)):
                        size = len(data)
                        
                    # Prepare metadata
                    metadata = {}
                    if size is not None:
                        metadata["size"] = size
                    
                    # If it's bytes data, we can store it directly in the libp2p peer
                    if isinstance(data, (bytes, bytearray)):
                        self.libp2p.store_bytes(cid, data)
                        
                    # Announce to the network
                    self.libp2p.announce_content(cid, metadata)
                    
                    # Add announcement status to result
                    result["p2p_announced"] = True
                    
                except Exception as e:
                    self.logger.warning(f"Failed to announce content to P2P network: {str(e)}")
                    result["p2p_announced"] = False
                    result["p2p_error"] = str(e)
            
        return result
    
    def close_libp2p(self):
        """Close the libp2p peer and clean up resources."""
        if self.libp2p:
            try:
                self.libp2p.close()
                self.libp2p = None
                return True
            except Exception as e:
                self.logger.error(f"Error closing libp2p peer: {str(e)}")
                return False
        return True
    
    def _setup_monitoring(self, resources=None, metadata=None):
        """Set up monitoring components.
        
        This initializes the ClusterMonitoring and ClusterDashboard components
        for cluster monitoring, visualization, and management.
        
        Args:
            resources: Available resources for monitoring
            metadata: Additional configuration parameters
        
        Returns:
            True if setup succeeded, False otherwise
        """
        if not HAS_MONITORING:
            self.logger.warning(
                "Monitoring functionality is not available. "
                "Check that cluster_monitoring.py is installed."
            )
            return False
            
        try:
            # Initialize the monitoring component
            self.monitoring = ClusterMonitoring(self)
            
            # Check if dashboard is enabled
            dashboard_enabled = False
            if hasattr(self, 'config') and isinstance(self.config, dict):
                dashboard_config = self.config.get("Dashboard", {})
                if isinstance(dashboard_config, dict):
                    dashboard_enabled = dashboard_config.get("Enabled", False)
            
            # Initialize dashboard if enabled
            if dashboard_enabled:
                self.dashboard = ClusterDashboard(self, self.monitoring)
                self.logger.info("Initialized cluster dashboard")
                
                # Start the dashboard if auto-start is enabled
                auto_start = False
                if hasattr(self, 'config') and isinstance(self.config, dict):
                    dashboard_config = self.config.get("Dashboard", {})
                    if isinstance(dashboard_config, dict):
                        auto_start = dashboard_config.get("AutoStart", False)
                        
                if auto_start:
                    self.dashboard.start_dashboard()
                    self.logger.info("Auto-started cluster dashboard")
            
            # Start monitoring if auto-start is enabled
            auto_start = False
            if hasattr(self, 'config') and isinstance(self.config, dict):
                monitoring_config = self.config.get("Monitoring", {})
                if isinstance(monitoring_config, dict):
                    auto_start = monitoring_config.get("AutoStart", False)
                    
            if auto_start:
                self.monitoring.start_monitoring()
                self.logger.info("Auto-started cluster monitoring")
                
            self.logger.info("Initialized cluster monitoring")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitoring: {str(e)}")
            self.monitoring = None
            self.dashboard = None
            return False
            
    def start_monitoring(self, **kwargs):
        """Start the monitoring system.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with operation status
        """
        operation = "start_monitoring"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING:
                return handle_error(result, IPFSError("Monitoring is not available"))
                
            if not self.monitoring:
                self._setup_monitoring(metadata=getattr(self, 'metadata', None))
                
            if not self.monitoring:
                return handle_error(result, IPFSError("Failed to set up monitoring"))
                
            monitoring_result = self.monitoring.start_monitoring()
            result.update(monitoring_result)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def stop_monitoring(self, **kwargs):
        """Stop the monitoring system.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with operation status
        """
        operation = "stop_monitoring"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.monitoring:
                return handle_error(result, IPFSError("Monitoring is not active"))
                
            monitoring_result = self.monitoring.stop_monitoring()
            result.update(monitoring_result)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def collect_metrics(self, **kwargs):
        """Collect metrics from all cluster nodes.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with collected metrics
        """
        operation = "collect_metrics"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.monitoring:
                return handle_error(result, IPFSError("Monitoring is not active"))
                
            metrics_result = self.monitoring.collect_cluster_metrics()
            result.update(metrics_result)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def check_alert_thresholds(self, metrics_data=None, **kwargs):
        """Check metrics against alert thresholds.
        
        Args:
            metrics_data: Metrics data to check (optional, will use latest if not provided)
            **kwargs: Additional arguments
            
        Returns:
            List of generated alerts
        """
        operation = "check_alert_thresholds"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.monitoring:
                return handle_error(result, IPFSError("Monitoring is not active"))
                
            # Get latest metrics if not provided
            if metrics_data is None:
                metrics_data = self.monitoring.get_latest_metrics()
                
            if metrics_data is None:
                return handle_error(result, IPFSError("No metrics available to check"))
                
            alerts = self.monitoring.check_alert_thresholds(metrics_data)
            
            result["success"] = True
            result["alerts"] = alerts
            result["alert_count"] = len(alerts)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def process_alerts(self, alerts=None, **kwargs):
        """Process alerts and determine recovery actions.
        
        Args:
            alerts: Alerts to process (optional, will use active alerts if not provided)
            **kwargs: Additional arguments
            
        Returns:
            List of recovery actions
        """
        operation = "process_alerts"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.monitoring:
                return handle_error(result, IPFSError("Monitoring is not active"))
                
            # Use active alerts if not provided
            if alerts is None:
                # This will require accessing the monitoring's active_alerts directly
                # which is not ideal but necessary for the delegation pattern
                alerts = getattr(self.monitoring, "active_alerts", [])
                
            if not alerts:
                result["success"] = True
                result["actions"] = []
                result["message"] = "No alerts to process"
                return result
                
            actions = self.monitoring.process_alerts(alerts)
            
            result["success"] = True
            result["actions"] = actions
            result["action_count"] = len(actions)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def start_dashboard(self, **kwargs):
        """Start the monitoring dashboard.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with operation status
        """
        operation = "start_dashboard"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING:
                return handle_error(result, IPFSError("Monitoring is not available"))
                
            # Create monitoring if not already created
            if not self.monitoring:
                self._setup_monitoring(metadata=getattr(self, 'metadata', None))
                
            # Create dashboard if not already created
            if not self.dashboard:
                self.dashboard = ClusterDashboard(self, self.monitoring)
                
            if not self.dashboard:
                return handle_error(result, IPFSError("Failed to set up dashboard"))
                
            dashboard_result = self.dashboard.start_dashboard()
            result.update(dashboard_result)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def stop_dashboard(self, **kwargs):
        """Stop the monitoring dashboard.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            Result dictionary with operation status
        """
        operation = "stop_dashboard"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.dashboard:
                return handle_error(result, IPFSError("Dashboard is not active"))
                
            dashboard_result = self.dashboard.stop_dashboard()
            result.update(dashboard_result)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def get_aggregated_metrics(self, time_range="24h", interval="1h", **kwargs):
        """Get aggregated metrics for visualization.
        
        Args:
            time_range: Time range to include (e.g., "24h", "7d")
            interval: Interval for aggregation (e.g., "1h", "5m")
            **kwargs: Additional arguments
            
        Returns:
            Aggregated metrics data
        """
        operation = "get_aggregated_metrics"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.monitoring:
                return handle_error(result, IPFSError("Monitoring is not active"))
                
            metrics = self.monitoring.aggregate_metrics(time_range, interval)
            
            result["success"] = True
            result["metrics"] = metrics
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def export_metrics(self, format="json", time_range="24h", interval="1h", **kwargs):
        """Export metrics in specified format.
        
        Args:
            format: Export format ("json" or "csv")
            time_range: Time range to include
            interval: Interval for aggregation
            **kwargs: Additional arguments
            
        Returns:
            Exported metrics data
        """
        operation = "export_metrics"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.monitoring:
                return handle_error(result, IPFSError("Monitoring is not active"))
                
            if format.lower() == "json":
                metrics_data = self.monitoring.export_metrics_json(time_range, interval)
            elif format.lower() == "csv":
                metrics_data = self.monitoring.export_metrics_csv(time_range, interval)
            else:
                return handle_error(result, IPFSValidationError(f"Unsupported format: {format}"))
                
            result["success"] = True
            result["format"] = format.lower()
            result["data"] = metrics_data
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def validate_cluster_config(self, config, **kwargs):
        """Validate cluster configuration.
        
        Args:
            config: Configuration to validate
            **kwargs: Additional arguments
            
        Returns:
            Validation results
        """
        operation = "validate_cluster_config"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.monitoring:
                return handle_error(result, IPFSError("Monitoring is not active"))
                
            validation_result = self.monitoring.validate_cluster_config(config)
            
            result["success"] = True
            result["validation"] = validation_result
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
    
    def distribute_cluster_config(self, config, **kwargs):
        """Distribute configuration to cluster nodes.
        
        Args:
            config: Configuration to distribute
            **kwargs: Additional arguments
            
        Returns:
            Distribution results
        """
        operation = "distribute_cluster_config"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not HAS_MONITORING or not self.monitoring:
                return handle_error(result, IPFSError("Monitoring is not active"))
                
            # Validate config first
            validation_result = self.monitoring.validate_cluster_config(config)
            if not validation_result.get("valid", False):
                result["success"] = False
                result["error"] = "Invalid configuration"
                result["validation"] = validation_result
                return result
                
            distribution_result = self.monitoring.distribute_cluster_config(config)
            result.update(distribution_result)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
            
    def get_filesystem(self, socket_path=None, cache_config=None, use_mmap=True, enable_metrics=True,
                    gateway_urls=None, gateway_only=False, use_gateway_fallback=False):
        """Create a filesystem interface for IPFS using FSSpec.
        
        This creates a filesystem-like interface to IPFS content using the
        fsspec specification, enabling standard filesystem operations (open,
        read, write, ls, etc.) on IPFS content with tiered caching for
        improved performance.
        
        Args:
            socket_path: Path to Unix socket for high-performance communication
            cache_config: Configuration for the tiered cache system
            use_mmap: Whether to use memory-mapped files for large content
            enable_metrics: Whether to collect performance metrics
            gateway_urls: List of IPFS gateway URLs to use (e.g. ["https://ipfs.io/ipfs/"])
            gateway_only: If True, only use gateways (ignore local daemon)
            use_gateway_fallback: If True, try gateways if local daemon fails
            
        Returns:
            An IPFSFileSystem instance that implements the fsspec interface,
            or None if fsspec is not available
            
        Example:
            ```python
            # Get a filesystem interface with metrics enabled
            fs = ipfs_kit_instance.get_filesystem(enable_metrics=True)
            
            # Use standard filesystem operations
            with fs.open("QmSomeContentID", "rb") as f:
                data = f.read()
                
            # Get performance metrics
            metrics = fs.get_performance_metrics()
            print(f"Cache hit rate: {metrics['cache']['overall_hit_rate']:.2%}")
                
            # List directory contents
            files = fs.ls("QmSomeDirectoryID")
            
            # Read a file directly
            content = fs.cat("QmSomeFileID")
            
            # Check if a file exists
            if fs.exists("QmSomeContentID"):
                print("Content exists!")
            ```
        """
        if not FSSPEC_AVAILABLE:
            self.logger.warning(
                "FSSpec is not available. Install fsspec package for "
                "filesystem interface functionality."
            )
            return None
            
        # If we already have a filesystem and no new params, return it
        if (self._filesystem is not None and socket_path is None and 
            cache_config is None and gateway_urls is None and 
            not gateway_only and not use_gateway_fallback):
            return self._filesystem
            
        # Get the IPFS path
        ipfs_path = getattr(self, 'ipfs_path', None)
        
        # Get the role
        role = getattr(self, 'role', 'leecher')
        
        # Create the filesystem
        try:
            self._filesystem = IPFSFileSystem(
                ipfs_path=ipfs_path,
                socket_path=socket_path,
                role=role,
                cache_config=cache_config,
                use_mmap=use_mmap,
                enable_metrics=enable_metrics,
                gateway_urls=gateway_urls,
                gateway_only=gateway_only,
                use_gateway_fallback=use_gateway_fallback
            )
            return self._filesystem
        except Exception as e:
            self.logger.error(f"Failed to create filesystem interface: {str(e)}")
            return None
    
    def get_metadata_index(self, index_dir=None, partition_size=None, sync_interval=300, auto_sync=True):
        """Get an Arrow-based metadata index for IPFS content.
        
        This creates or returns a metadata index for storing and retrieving 
        information about IPFS content using Apache Arrow for efficient columnar 
        storage and Parquet for persistence.
        
        Args:
            index_dir: Directory to store index files
            partition_size: Maximum number of records per partition file
            sync_interval: How often to sync with peers (seconds)
            auto_sync: Whether to automatically sync with peers
            
        Returns:
            ArrowMetadataIndex instance or None if Arrow is not available
            
        Example:
            ```python
            # Get a metadata index with auto-sync enabled
            index = ipfs_kit_instance.get_metadata_index(auto_sync=True)
            
            # Add metadata for a CID
            index.add_record({
                "cid": "QmSomeContentID",
                "size_bytes": 1024,
                "mime_type": "text/plain",
                "filename": "example.txt",
                "metadata": {
                    "title": "Example Document",
                    "description": "This is an example document"
                }
            })
            
            # Query the index
            results = index.query([
                ("mime_type", "==", "text/plain"),
                ("size_bytes", "<", 10000)
            ])
            
            # Find all storage locations for a CID
            locations = index.find_content_locations(cid="QmSomeContentID")
            ```
        """
        from .error import create_result_dict, handle_error
        
        result = create_result_dict("get_metadata_index")
        
        try:
            # Check if Arrow is available
            if not HAS_ARROW_INDEX:
                error_msg = "Arrow metadata index is not available"
                self.logger.warning(error_msg)
                return handle_error(result, ImportError(error_msg))
                
            # Initialize metadata index if needed
            if not self._metadata_index:
                # Create metadata object
                metadata = {
                    "metadata_index_dir": index_dir,
                    "metadata_partition_size": partition_size,
                    "metadata_sync_interval": sync_interval,
                    "metadata_auto_sync": auto_sync,
                    "enable_metadata_index": True
                }
                
                # Set up metadata index
                setup_result = self._setup_metadata_index(metadata=metadata)
                if not setup_result.get("success", False):
                    error_msg = f"Failed to initialize metadata index: {setup_result.get('error', 'Unknown error')}"
                    self.logger.error(error_msg)
                    return handle_error(result, Exception(error_msg))
            
            # Return success with metadata index
            result["success"] = True
            result["metadata_index"] = self._metadata_index
            return self._metadata_index
            
        except Exception as e:
            self.logger.error(f"Failed to get metadata index: {str(e)}")
            return None
            
    def get_data_loader(self, batch_size=32, shuffle=True, prefetch=2):
        """Get a data loader for machine learning workloads.
        
        This creates a data loader for efficiently loading datasets from IPFS
        content storage, with features for batching, prefetching, and framework
        integrations.
        
        Args:
            batch_size: Number of samples per batch
            shuffle: Whether to shuffle the dataset
            prefetch: Number of batches to prefetch
            
        Returns:
            IPFSDataLoader instance or None if AI/ML integration is not available
            
        Example:
            ```python
            # Get a data loader
            loader = ipfs_kit_instance.get_data_loader(batch_size=64, shuffle=True)
            
            # Load a dataset by CID
            loader.load_dataset("QmDatasetCID")
            
            # Iterate through batches
            for batch in loader:
                process_batch(batch)
                
            # Convert to PyTorch DataLoader
            pytorch_loader = loader.to_pytorch()
            
            # Or use with TensorFlow
            tf_dataset = loader.to_tensorflow()
            ```
        """
        if not HAS_AI_ML_INTEGRATION:
            self.logger.warning("AI/ML integration not available. Cannot create data loader.")
            return None
            
        try:
            # Create an IPFSDataLoader instance
            return IPFSDataLoader(
                ipfs_client=self.ipfs,
                batch_size=batch_size,
                shuffle=shuffle,
                prefetch=prefetch
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create data loader: {e}")
            return None
            
    def sync_metadata_index(self, peer_ids=None, timeout=60):
        """Synchronize the metadata index with other peers.
        
        This method triggers a manual synchronization of the metadata index
        with the specified peers or with all known peers if none are specified.
        
        Args:
            peer_ids: List of specific peer IDs to sync with (optional)
            timeout: Maximum time to wait for synchronization (seconds)
            
        Returns:
            Dictionary with synchronization results
            
        Example:
            ```python
            # Sync with all known peers
            result = ipfs_kit_instance.sync_metadata_index()
            
            # Sync with specific peers
            result = ipfs_kit_instance.sync_metadata_index(
                peer_ids=["QmPeerID1", "QmPeerID2"]
            )
            ```
        """
        from .error import create_result_dict, handle_error
        
        result = create_result_dict("sync_metadata_index")
        
        try:
            # Check if metadata index is available
            if not self._metadata_index:
                error_msg = "Metadata index not initialized"
                self.logger.warning(error_msg)
                return handle_error(result, Exception(error_msg))
                
            # Check if sync handler is available
            if not self._metadata_sync_handler:
                error_msg = "Metadata sync handler not initialized"
                self.logger.warning(error_msg)
                return handle_error(result, Exception(error_msg))
                
            # Perform synchronization
            if peer_ids:
                # Sync with specific peers
                for peer_id in peer_ids:
                    sync_result = self._metadata_sync_handler.sync_with_peer(peer_id)
                    result[f"peer_{peer_id}"] = sync_result
            else:
                # Sync with all known peers
                sync_result = self._metadata_sync_handler.sync_with_all_peers(timeout=timeout)
                result.update(sync_result)
                
            result["success"] = True
            return result
            
        except Exception as e:
            return handle_error(result, e)
            
    def publish_metadata_index(self):
        """Publish the metadata index to IPFS DAG for discoverable access.
        
        This method publishes the current state of the metadata index to IPFS DAG,
        making it discoverable and accessible to other peers. It also updates IPNS
        to provide a stable reference to the latest version.
        
        Returns:
            Dictionary with publication results including DAG CID and IPNS name
            
        Example:
            ```python
            # Publish the metadata index
            result = ipfs_kit_instance.publish_metadata_index()
            
            # Get the DAG CID
            dag_cid = result.get("dag_cid")
            
            # Get the IPNS name
            ipns_name = result.get("ipns_name")
            ```
        """
        from .error import create_result_dict, handle_error
        
        result = create_result_dict("publish_metadata_index")
        
        try:
            # Check if metadata index is available
            if not self._metadata_index:
                error_msg = "Metadata index not initialized"
                self.logger.warning(error_msg)
                return handle_error(result, Exception(error_msg))
                
            # Publish index to DAG
            publish_result = self._metadata_index.publish_index_dag()
            result.update(publish_result)
            
            # Set success flag if not already set
            if "success" not in result:
                result["success"] = True
                
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def _check_cluster_manager_and_call(self, method_name, **kwargs):
        """Check if cluster manager is available and call the specified method with standardized error handling.
        
        This helper method simplifies interaction with the ClusterManager by:
        1. Checking if cluster management is enabled and available
        2. Verifying that the requested method exists
        3. Handling exceptions consistently
        
        Args:
            method_name: Name of the method to call on the cluster manager
            **kwargs: Arguments to pass to the method including 'correlation_id' for tracing
            
        Returns:
            Result from the method call or an error dictionary if unavailable/failed
        """
        result = {
            "success": False,
            "operation": method_name,
            "timestamp": time.time()
        }
        
        # Check if cluster manager is available
        if not hasattr(self, 'cluster_manager') or self.cluster_manager is None:
            result["error"] = "Cluster management is not enabled or available"
            return result
            
        # Check if the requested method exists
        if not hasattr(self.cluster_manager, method_name):
            result["error"] = f"Method {method_name} not available in cluster manager"
            return result
            
        try:
            # Call the method on the cluster manager
            method = getattr(self.cluster_manager, method_name)
            return method(**kwargs)
        except Exception as e:
            self.logger.error(f"Error calling cluster manager method {method_name}: {str(e)}")
            result["error"] = str(e)
            return result
            
    def _call_static_cluster_manager(self, method_name, **kwargs):
        """Call a static method on the ClusterManager class with standardized error handling.
        
        This helper method is used for accessing static methods that don't require
        an initialized ClusterManager instance, such as external state access.
        
        Args:
            method_name: Name of the static method to call on the ClusterManager class
            **kwargs: Arguments to pass to the method
            
        Returns:
            Result from the method call or an error dictionary if unavailable/failed
        """
        result = {
            "success": False,
            "operation": method_name,
            "timestamp": time.time()
        }
        
        try:
            # Import the ClusterManager class dynamically
            from .cluster_management import ClusterManager
            
            # Check if the requested method exists as a static method
            if not hasattr(ClusterManager, method_name):
                result["error"] = f"Static method {method_name} not available in ClusterManager"
                return result
                
            # Call the static method
            method = getattr(ClusterManager, method_name)
            return method(**kwargs)
        except Exception as e:
            self.logger.error(f"Error calling static cluster manager method {method_name}: {str(e)}")
            result["error"] = str(e)
            return result
            
    def _setup_cluster_management(self, resources=None, metadata=None):
        """Set up the cluster management component with standardized error handling.
        
        This method initializes the role-based cluster management system which enables:
        - Distributed task coordination and execution via a master/worker model
        - Resource-aware task scheduling and assignment
        - Content distribution and replication management
        - Peer discovery and health monitoring
        - Direct peer-to-peer communication via libp2p
        
        The method automatically detects available system resources through 
        psutil for optimal resource allocation and reporting.
        
        Args:
            resources: Dictionary with available resources (CPU, memory, disk, GPU, etc.)
            metadata: Additional metadata for configuration including optional node_id
                      and cluster_id settings
            
        Returns:
            Boolean indicating whether setup was successful
        """
        try:
            self.logger.info("Setting up cluster management...")
            
            # Get node ID (use hostname as fallback)
            import socket
            node_id = metadata.get("node_id") if metadata and "node_id" in metadata else socket.gethostname()
            
            # Get peer ID from libp2p or IPFS identity
            peer_id = None
            if self.libp2p:
                # Try to get peer ID from libp2p
                try:
                    peer_id = self.libp2p.get_peer_id()
                except Exception as e:
                    self.logger.warning(f"Failed to get peer ID from libp2p: {str(e)}")
            
            if not peer_id and hasattr(self, 'ipfs'):
                # Try to get peer ID from IPFS
                try:
                    id_result = self.ipfs.ipfs_id()
                    if isinstance(id_result, dict) and "ID" in id_result:
                        peer_id = id_result["ID"]
                except Exception as e:
                    self.logger.warning(f"Failed to get peer ID from IPFS: {str(e)}")
            
            # Fallback to a generated ID if needed
            if not peer_id:
                import uuid
                peer_id = f"peer-{uuid.uuid4()}"
                self.logger.warning(f"Using generated peer ID: {peer_id}")
            
            # Prepare configuration
            config = {}
            if hasattr(self, 'config'):
                config = self.config.copy()
            
            # Add cluster-specific parameters
            if metadata and "cluster_id" in metadata:
                config["cluster_id"] = metadata["cluster_id"]
            elif "cluster_id" not in config:
                config["cluster_id"] = "default"
                
            # Convert the resources dict to the structure expected by ClusterManager
            if not resources:
                resources = {}
                
            # Try to get resource information automatically using psutil if available
            try:
                import psutil
                
                # CPU information
                if "cpu_count" not in resources:
                    resources["cpu_count"] = psutil.cpu_count(logical=True)
                if "cpu_usage" not in resources:
                    resources["cpu_usage"] = psutil.cpu_percent(interval=0.1)
                
                # Memory information
                if "memory_total" not in resources:
                    resources["memory_total"] = psutil.virtual_memory().total
                if "memory_available" not in resources:
                    resources["memory_available"] = psutil.virtual_memory().available
                
                # Disk information
                if "disk_total" not in resources:
                    resources["disk_total"] = psutil.disk_usage('/').total
                if "disk_free" not in resources:
                    resources["disk_free"] = psutil.disk_usage('/').free
                    
                # GPU information if available
                if "gpu_count" not in resources and "gpu_available" not in resources:
                    try:
                        # Try to detect NVIDIA GPUs with pynvml (doesn't require import)
                        gpu_info = self._get_gpu_info()
                        if gpu_info:
                            resources.update(gpu_info)
                    except Exception as e:
                        self.logger.debug(f"Failed to get GPU information: {str(e)}")
                
            except ImportError:
                self.logger.warning("psutil not available, using default resource values")
                
                # Set reasonable defaults
                if "cpu_count" not in resources:
                    resources["cpu_count"] = 1
                if "memory_total" not in resources:
                    resources["memory_total"] = 1024 * 1024 * 1024  # 1GB
                if "memory_available" not in resources:
                    resources["memory_available"] = 512 * 1024 * 1024  # 512MB
                if "disk_total" not in resources:
                    resources["disk_total"] = 10 * 1024 * 1024 * 1024  # 10GB
                if "disk_free" not in resources:
                    resources["disk_free"] = 5 * 1024 * 1024 * 1024  # 5GB
                    
            except Exception as e:
                self.logger.warning(f"Error getting system resources: {str(e)}")
            
            # Initialize the cluster manager
            self.cluster_manager = ClusterManager(
                node_id=node_id,
                role=self.role,
                peer_id=peer_id,
                config=config,
                resources=resources,
                metadata=metadata,
                enable_libp2p=hasattr(self, 'libp2p') and self.libp2p is not None
            )
            
            # Start the cluster manager
            result = self.cluster_manager.start()
            
            if not result.get("success", False):
                self.logger.error(f"Failed to start cluster manager: {result}")
                return False
                
            self.logger.info("Cluster management setup complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set up cluster management: {str(e)}")
            return False
    
    def stop_cluster_manager(self, **kwargs):
        """Stop the cluster manager with standardized error handling.
        
        Safely shuts down the distributed cluster management system, which includes:
        - Gracefully closing peer connections
        - Publishing departure notifications to the cluster
        - Completing or canceling in-progress tasks based on criticality
        - Releasing system resources
        - Storing state for potential recovery
        
        Args:
            **kwargs: Additional parameters including 'correlation_id' for tracing
                     and optional 'force' flag to force immediate shutdown
            
        Returns:
            Dictionary with stop status including component-specific results
        """
        operation = "stop_cluster_manager"
        correlation_id = kwargs.get('correlation_id')
        result = {
            "success": False,
            "operation": operation,
            "timestamp": time.time()
        }
        
        if correlation_id:
            result["correlation_id"] = correlation_id
        
        try:
            # Check if cluster manager exists
            if not hasattr(self, 'cluster_manager') or self.cluster_manager is None:
                result["success"] = True
                result["message"] = "Cluster manager is not running"
                return result
                
            # Stop the cluster manager
            stop_result = self.cluster_manager.stop()
            
            # Copy relevant fields
            if isinstance(stop_result, dict):
                for key, value in stop_result.items():
                    result[key] = value
                    
                # Ensure we have a success field
                if "success" not in result:
                    result["success"] = True
            else:
                result["success"] = True
                result["message"] = "Cluster manager stopped successfully"
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error stopping cluster manager: {str(e)}")
            result["error"] = str(e)
            return result
    
    def _get_gpu_info(self):
        """Get GPU information using available tools (pynvml, torch, tensorflow).
        
        Attempts to detect and query GPU devices through multiple methods:
        1. NVIDIA Management Library (pynvml) for NVIDIA GPUs
        2. PyTorch CUDA detection as fallback
        3. TensorFlow GPU detection as secondary fallback
        
        The gathered information includes:
        - gpu_count: Number of GPU devices detected
        - gpu_available: Boolean indicating if GPUs are available
        - gpu_type: Type of GPU detected ("nvidia", "cuda", "tensorflow")
        - gpu_memory_total: Total memory for first GPU (NVIDIA only)
        - gpu_memory_free: Available memory on first GPU (NVIDIA only)
        
        Returns:
            Dictionary with GPU information or None if no GPUs detected
        """
        gpu_info = {}
        
        # Try NVIDIA GPUs with pynvml
        try:
            import pynvml
            pynvml.nvmlInit()
            gpu_count = pynvml.nvmlDeviceGetCount()
            
            gpu_info["gpu_count"] = gpu_count
            gpu_info["gpu_available"] = gpu_count > 0
            gpu_info["gpu_type"] = "nvidia"
            
            # Get memory information for first GPU
            if gpu_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_info["gpu_memory_total"] = mem_info.total
                gpu_info["gpu_memory_free"] = mem_info.free
                
            pynvml.nvmlShutdown()
            return gpu_info
            
        except (ImportError, Exception):
            # Fall back to checking for common GPU libs
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_count = torch.cuda.device_count()
                    gpu_info["gpu_count"] = gpu_count
                    gpu_info["gpu_available"] = gpu_count > 0
                    gpu_info["gpu_type"] = "cuda"
                    return gpu_info
            except ImportError:
                pass
                
            try:
                import tensorflow as tf
                gpus = tf.config.list_physical_devices('GPU')
                gpu_count = len(gpus)
                gpu_info["gpu_count"] = gpu_count
                gpu_info["gpu_available"] = gpu_count > 0
                gpu_info["gpu_type"] = "tensorflow"
                return gpu_info
            except ImportError:
                pass
        
        return None

# Apply the extensions to the ipfs_kit class
extend_ipfs_kit(ipfs_kit)

if __name__ == "__main__":
    ipfs = ipfs_kit(None, None)
    results = ipfs.test()
    print(results)
    pass
