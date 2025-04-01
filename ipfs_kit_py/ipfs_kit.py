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
import re
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
        
        # This line is problematic - replacing with a lambda that calls the method properly
        # self.ipfs_get = self.ipget_download_object # Alias for ipget download
        # Define a lambda that will call the ipget's method when invoked
        self.ipfs_get = lambda **kwargs: self.ipget.ipget_download_object(**kwargs) if hasattr(self, 'ipget') else None

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
                    if self.role not in ["master", "worker", "leecher"]:
                        raise ValueError(f"Invalid role: {self.role}. Must be one of: master, worker, leecher")
            if "cluster_name" in metadata:
                if metadata["cluster_name"] is not None:
                    self.cluster_name = metadata['cluster_name']
                    # Store cluster_name in config as cluster_id for cluster manager
                    self.config["cluster_id"] = metadata['cluster_name']
            if "ipfs_path" in metadata:
                if metadata["ipfs_path"] is not None:
                    self.ipfs_path = metadata['ipfs_path']
            if "enable_libp2p" in metadata:
                enable_libp2p = metadata.get("enable_libp2p", False)
            if "enable_cluster_management" in metadata:
                enable_cluster_management = metadata.get("enable_cluster_management", False)
            if "enable_metadata_index" in metadata:
                enable_metadata_index = metadata.get("enable_metadata_index", False)

            # Initialize components based on role
            if self.role == "leecher":
                self.ipfs = ipfs_py(resources, metadata)
                self.ipget = ipget(resources, metadata)
                self.s3_kit = s3_kit(resources, metadata)
                self.storacha_kit = storacha_kit(resources, metadata)
            elif self.role == "worker":
                self.ipfs = ipfs_py(resources, metadata)
                self.ipget = ipget(resources, metadata)
                self.s3_kit = s3_kit(resources, metadata)
                self.ipfs_cluster_follow = ipfs_cluster_follow(resources, metadata)
                self.storacha_kit = storacha_kit(resources, metadata)
            elif self.role == "master":
                self.ipfs = ipfs_py(resources, metadata)
                self.ipget = ipget(resources, metadata)
                self.s3_kit = s3_kit(resources, metadata)
                self.ipfs_cluster_ctl = ipfs_cluster_ctl(resources, metadata)
                self.ipfs_cluster_service = ipfs_cluster_service(resources, metadata)
                self.storacha_kit = storacha_kit(resources, metadata)

        # Initialize monitoring components
        self.monitoring = None
        self.dashboard = None
        enable_monitoring = metadata.get("enable_monitoring", False) if metadata else False

        # Initialize knowledge graph components
        self.knowledge_graph = None
        self.graph_query = None
        self.graph_rag = None
        enable_knowledge_graph = metadata.get("enable_knowledge_graph", False) if metadata else False

        # Initialize AI/ML integration components
        self.model_registry = None
        self.dataset_manager = None
        self.langchain_integration = None
        self.llama_index_integration = None
        self.distributed_training = None
        enable_ai_ml = metadata.get("enable_ai_ml", False) if metadata else False

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
            self.logger.info("To enable knowledge graph, make sure ipld_knowledge_graph.py is available.")

        # Initialize AI/ML integration components if enabled
        if enable_ai_ml and HAS_AI_ML_INTEGRATION:
            self._setup_ai_ml_integration(resources, metadata)
        elif enable_ai_ml and not HAS_AI_ML_INTEGRATION:
            self.logger.warning("AI/ML integration is not available. Skipping initialization.")
            self.logger.info("To enable AI/ML integration, make sure ai_ml_integration.py is available.")

    def _setup_cluster_management(self, resources=None, metadata=None):
        """Set up the cluster management component with standardized error handling."""
        try:
            self.logger.info("Setting up cluster management...")
            import socket
            node_id = metadata.get("node_id") if metadata and "node_id" in metadata else socket.gethostname()
            peer_id = None
            if hasattr(self, 'libp2p') and self.libp2p:
                try:
                    peer_id = self.libp2p.get_peer_id()
                except Exception as e:
                    self.logger.warning(f"Failed to get peer ID from libp2p: {str(e)}")
            if not peer_id and hasattr(self, 'ipfs'):
                try:
                    id_result = self.ipfs.ipfs_id()
                    if id_result.get("success", False) and "ID" in id_result:
                        peer_id = id_result["ID"]
                except Exception as e:
                    self.logger.warning(f"Failed to get peer ID from IPFS: {str(e)}")
            if not peer_id:
                import uuid
                peer_id = f"peer-{uuid.uuid4()}"
                self.logger.warning(f"Using generated peer ID: {peer_id}")
            config = self.config.copy() if hasattr(self, 'config') else {}
            if metadata and "cluster_id" in metadata:
                config["cluster_id"] = metadata["cluster_id"]
            elif "cluster_id" not in config:
                config["cluster_id"] = "default"
            if not resources: resources = {}
            try:
                import psutil
                if "cpu_count" not in resources: resources["cpu_count"] = psutil.cpu_count(logical=True)
                if "cpu_usage" not in resources: resources["cpu_percent"] = psutil.cpu_percent(interval=0.1)
                if "memory_total" not in resources: resources["memory_total"] = psutil.virtual_memory().total
                if "memory_available" not in resources: resources["memory_available"] = psutil.virtual_memory().available
                if "disk_total" not in resources: resources["disk_total"] = psutil.disk_usage('/').total
                if "disk_free" not in resources: resources["disk_free"] = psutil.disk_usage('/').free
                if "gpu_count" not in resources and "gpu_available" not in resources:
                    try:
                        gpu_info = self._get_gpu_info() # Assuming _get_gpu_info exists
                        if gpu_info: resources.update(gpu_info)
                    except Exception as e: self.logger.debug(f"Failed to get GPU information: {str(e)}")
            except ImportError:
                self.logger.warning("psutil not available, using default resource values")
                if "cpu_count" not in resources: resources["cpu_count"] = 1
                if "memory_total" not in resources: resources["memory_total"] = 1024 * 1024 * 1024
                if "memory_available" not in resources: resources["memory_available"] = 512 * 1024 * 1024
                if "disk_total" not in resources: resources["disk_total"] = 10 * 1024 * 1024 * 1024
                if "disk_free" not in resources: resources["disk_free"] = 5 * 1024 * 1024 * 1024
            except Exception as e: self.logger.warning(f"Error getting system resources: {str(e)}")

            self.cluster_manager = ClusterManager(
                node_id=node_id, role=self.role, peer_id=peer_id, config=config,
                resources=resources, metadata=metadata,
                enable_libp2p=hasattr(self, 'libp2p') and self.libp2p is not None
            )
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
        """Set up the Arrow-based metadata index component."""
        from .error import create_result_dict, handle_error
        result = create_result_dict("setup_metadata_index")
        try:
            index_dir = metadata.get("metadata_index_dir") if metadata else None
            partition_size = metadata.get("metadata_partition_size") if metadata else None
            sync_interval = metadata.get("metadata_sync_interval", 300) if metadata else 300
            auto_sync = metadata.get("metadata_auto_sync", True) if metadata else True
            cluster_id = metadata.get("cluster_name") if metadata else None
            if not cluster_id and "cluster_id" in self.config: cluster_id = self.config["cluster_id"]

            self._metadata_index = ArrowMetadataIndex(
                base_path=index_dir, role=self.role, partition_size=partition_size,
                ipfs_client=self.ipfs
            )
            if self.role in ("master", "worker"):
                node_id = self.ipfs.get_node_id() if hasattr(self.ipfs, 'get_node_id') else None
                self._metadata_sync_handler = MetadataSyncHandler(
                    index=self._metadata_index, ipfs_client=self.ipfs,
                    cluster_id=cluster_id, node_id=node_id
                )
                if auto_sync: self._metadata_sync_handler.start(sync_interval=sync_interval)
            result["success"] = True
            result["metadata_index_enabled"] = True
            result["auto_sync"] = auto_sync
            self.logger.info(f"Arrow metadata index enabled. Auto-sync: {auto_sync}")
        except Exception as e:
            handle_error(result, e, "Failed to initialize Arrow metadata index")
            self.logger.error(f"Error initializing Arrow metadata index: {str(e)}")
        return result

    def get_cluster_status(self, **kwargs):
        """Get comprehensive status information about the cluster."""
        operation = "get_cluster_status"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if not hasattr(self, 'cluster_manager') or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
            status = self.cluster_manager.get_cluster_status()
            result.update(status)
            result["success"] = status.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)

    def submit_cluster_task(self, task_type, payload, priority=1, timeout=None, **kwargs):
        """Submit a task to the cluster for distributed processing."""
        operation = "submit_cluster_task"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if not hasattr(self, 'cluster_manager') or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
            if not task_type: return handle_error(result, IPFSValidationError("Task type must be specified"))
            if not isinstance(payload, dict): return handle_error(result, IPFSValidationError("Payload must be a dictionary"))
            task_result = self.cluster_manager.submit_task(
                task_type=task_type, payload=payload, priority=priority, timeout=timeout
            )
            result.update(task_result)
            result["success"] = task_result.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)

    def get_task_status(self, task_id, **kwargs):
        """Get the status of a submitted cluster task."""
        operation = "get_task_status"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if not hasattr(self, 'cluster_manager') or self.cluster_manager is None:
                return handle_error(result, IPFSError("Cluster management is not enabled"))
            if not task_id: return handle_error(result, IPFSValidationError("Task ID must be specified"))
            status_result = self.cluster_manager.get_task_status(task_id)
            result.update(status_result)
            result["success"] = True
            result["task_id"] = task_id
            return result
        except Exception as e:
            return handle_error(result, e)

    def _setup_libp2p(self, resources=None, metadata=None):
        """Set up the libp2p direct peer-to-peer communication component."""
        try:
            self.logger.info("Setting up libp2p peer for direct P2P communication...")
            libp2p_config = metadata.get("libp2p_config", {}) if metadata else {}
            identity_path = libp2p_config.get("identity_path")
            if not identity_path:
                ipfs_path = metadata.get("ipfs_path", "~/.ipfs") if metadata else "~/.ipfs"
                identity_path = os.path.join(os.path.expanduser(ipfs_path), "libp2p", "identity")
                os.makedirs(os.path.dirname(identity_path), exist_ok=True)
            bootstrap_peers = libp2p_config.get("bootstrap_peers", [])
            if libp2p_config.get("use_well_known_peers", True):
                well_known_peers = [
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb"
                ]
                bootstrap_peers.extend(well_known_peers)
            listen_addrs = libp2p_config.get("listen_addrs")
            enable_mdns = libp2p_config.get("enable_mdns", True)
            enable_hole_punching = libp2p_config.get("enable_hole_punching", False)
            enable_relay = libp2p_config.get("enable_relay", False)
            tiered_storage_manager = getattr(self._filesystem, "cache", None) if hasattr(self, "_filesystem") and self._filesystem is not None else None
            self.libp2p = IPFSLibp2pPeer(
                identity_path=identity_path, bootstrap_peers=bootstrap_peers, listen_addrs=listen_addrs,
                role=self.role, enable_mdns=enable_mdns, enable_hole_punching=enable_hole_punching,
                enable_relay=enable_relay, tiered_storage_manager=tiered_storage_manager
            )
            if libp2p_config.get("auto_start_discovery", True):
                cluster_name = metadata.get("cluster_name", "ipfs-kit-cluster") if metadata else "ipfs-kit-cluster"
                self.libp2p.start_discovery(rendezvous_string=cluster_name)
            if enable_relay: self.libp2p.enable_relay()
            self.logger.info(f"libp2p peer initialized with ID: {self.libp2p.get_peer_id()}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set up libp2p peer: {str(e)}")
            return False

    def _setup_knowledge_graph(self, resources=None, metadata=None):
        """Set up the IPLD knowledge graph component."""
        try:
            self.logger.info("Setting up IPLD knowledge graph...")
            kg_config = metadata.get("knowledge_graph_config", {}) if metadata else {}
            base_path = kg_config.get("base_path", "~/.ipfs_graph")
            self.knowledge_graph = IPLDGraphDB(
                ipfs_client=self.ipfs, base_path=base_path,
                schema_version=kg_config.get("schema_version", "1.0.0")
            )
            self.graph_query = KnowledgeGraphQuery(self.knowledge_graph)
            embedding_model = kg_config.get("embedding_model")
            self.graph_rag = GraphRAG(graph_db=self.knowledge_graph, embedding_model=embedding_model)
            if embedding_model: self.logger.info("GraphRAG initialized with embedding model")
            else: self.logger.info("GraphRAG initialized without embedding model")
            self.logger.info("IPLD knowledge graph setup complete")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set up IPLD knowledge graph: {str(e)}")
            return False

    def _check_libp2p_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call libp2p methods."""
        operation = f"libp2p_{method_name}"
        correlation_id = kwargs.pop('correlation_id', None)
        result = create_result_dict(operation, correlation_id)
        if not HAS_LIBP2P: return handle_error(result, IPFSError("libp2p is not available. Install with pip install libp2p"))
        if self.libp2p is None: return handle_error(result, IPFSError("libp2p peer is not initialized. Enable with enable_libp2p=True"))
        try:
            method = getattr(self.libp2p, method_name, None)
            if method is None: return handle_error(result, IPFSError(f"Method {method_name} not found in libp2p peer"))
            method_result = method(*args, **kwargs)
            result["success"] = True
            result["data"] = method_result
            return result
        except Exception as e:
            return handle_error(result, e)

    # libp2p direct P2P communication methods
    def libp2p_get_peer_id(self, **kwargs): return self._check_libp2p_and_call("get_peer_id", **kwargs)
    def libp2p_get_multiaddrs(self, **kwargs): return self._check_libp2p_and_call("get_multiaddrs", **kwargs)
    def libp2p_connect_peer(self, peer_addr, **kwargs): return self._check_libp2p_and_call("connect_peer", peer_addr, **kwargs)
    def libp2p_is_connected(self, peer_id, **kwargs): return self._check_libp2p_and_call("is_connected_to", peer_id, **kwargs)
    def libp2p_announce_content(self, cid, metadata=None, **kwargs): return self._check_libp2p_and_call("announce_content", cid, metadata, **kwargs)
    def libp2p_find_providers(self, cid, count=20, timeout=30, **kwargs): return self._check_libp2p_and_call("find_providers", cid, count, timeout, **kwargs)
    def libp2p_request_content(self, cid, timeout=30, **kwargs): return self._check_libp2p_and_call("request_content", cid, timeout, **kwargs)
    def libp2p_store_content(self, cid, data, **kwargs): return self._check_libp2p_and_call("store_bytes", cid, data, **kwargs)
    def libp2p_start_discovery(self, rendezvous_string="ipfs-kit", **kwargs): return self._check_libp2p_and_call("start_discovery", rendezvous_string, **kwargs)
    def libp2p_enable_relay(self, **kwargs): return self._check_libp2p_and_call("enable_relay", **kwargs)
    def libp2p_connect_via_relay(self, peer_id, relay_addr, **kwargs): return self._check_libp2p_and_call("connect_via_relay", peer_id, relay_addr, **kwargs)

    def _check_knowledge_graph_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call knowledge graph methods."""
        operation = f"knowledge_graph_{method_name}"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_KNOWLEDGE_GRAPH: return handle_error(result, IPFSError("Knowledge graph component is not available"))
            if not hasattr(self, 'knowledge_graph') or self.knowledge_graph is None: return handle_error(result, IPFSError("Knowledge graph component is not initialized"))
            if not hasattr(self.knowledge_graph, method_name): return handle_error(result, IPFSError(f"Method '{method_name}' not found in knowledge graph component"))
            method = getattr(self.knowledge_graph, method_name)
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result)
                if "success" not in result: result["success"] = True
            else:
                result["success"] = True
                result["result"] = method_result
            return result
        except Exception as e:
            return handle_error(result, e)

    def _check_graph_query_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call graph query methods."""
        operation = f"graph_query_{method_name}"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_KNOWLEDGE_GRAPH: return handle_error(result, IPFSError("Knowledge graph component is not available"))
            if not hasattr(self, 'graph_query') or self.graph_query is None: return handle_error(result, IPFSError("Graph query interface is not initialized"))
            if not hasattr(self.graph_query, method_name): return handle_error(result, IPFSError(f"Method '{method_name}' not found in graph query interface"))
            method = getattr(self.graph_query, method_name)
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result)
                if "success" not in result: result["success"] = True
            else:
                result["success"] = True
                result["result"] = method_result
            return result
        except Exception as e:
            return handle_error(result, e)

    def _check_graph_rag_and_call(self, method_name, *args, **kwargs):
        """Helper to check and call GraphRAG methods."""
        operation = f"graph_rag_{method_name}"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_KNOWLEDGE_GRAPH: return handle_error(result, IPFSError("Knowledge graph component is not available"))
            if not hasattr(self, 'graph_rag') or self.graph_rag is None: return handle_error(result, IPFSError("GraphRAG component is not initialized"))
            if not hasattr(self.graph_rag, method_name): return handle_error(result, IPFSError(f"Method '{method_name}' not found in GraphRAG component"))
            method = getattr(self.graph_rag, method_name)
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result)
                if "success" not in result: result["success"] = True
            else:
                result["success"] = True
                result["result"] = method_result
            return result
        except Exception as e:
            return handle_error(result, e)

    def _setup_ai_ml_integration(self, resources=None, metadata=None):
        """Set up the AI/ML integration components."""
        try:
            self.logger.info("Setting up AI/ML integration...")
            ai_ml_config = metadata.get("ai_ml_config", {}) if metadata else {}
            model_registry_path = ai_ml_config.get("model_registry_path", "~/.ipfs_models")
            self.model_registry = ModelRegistry(ipfs_client=self.ipfs, base_path=model_registry_path)
            self.logger.info(f"Model registry initialized at {model_registry_path}")
            dataset_manager_path = ai_ml_config.get("dataset_manager_path", "~/.ipfs_datasets")
            self.dataset_manager = DatasetManager(ipfs_client=self.ipfs, base_path=dataset_manager_path)
            self.logger.info(f"Dataset manager initialized at {dataset_manager_path}")
            self.langchain_integration = LangchainIntegration(ipfs_client=self.ipfs)
            self.logger.info("Langchain integration initialized")
            self.llama_index_integration = LlamaIndexIntegration(ipfs_client=self.ipfs)
            self.logger.info("LlamaIndex integration initialized")
            cluster_manager = self.cluster_manager if hasattr(self, 'cluster_manager') and self.cluster_manager is not None else None
            self.distributed_training = DistributedTraining(ipfs_client=self.ipfs, cluster_manager=cluster_manager)
            if cluster_manager: self.logger.info("Distributed training initialized with cluster manager")
            else: self.logger.info("Distributed training initialized without cluster manager")
            self.logger.info("AI/ML integration setup complete")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set up AI/ML integration: {str(e)}")
            return False

    def _check_ai_ml_and_call(self, component_name, method_name, *args, **kwargs):
        """Helper to check and call AI/ML methods."""
        operation = f"ai_ml_{component_name}_{method_name}"
        correlation_id = kwargs.get('correlation_id', str(uuid.uuid4()))
        result = create_result_dict(operation, correlation_id)
        try:
            if not HAS_AI_ML_INTEGRATION: return handle_error(result, IPFSError("AI/ML integration is not available"))
            if not hasattr(self, component_name) or getattr(self, component_name) is None: return handle_error(result, IPFSError(f"AI/ML component '{component_name}' is not initialized"))
            component = getattr(self, component_name)
            if not hasattr(component, method_name): return handle_error(result, IPFSError(f"Method '{method_name}' not found in {component_name}"))
            method = getattr(component, method_name)
            method_result = method(*args, **kwargs)
            if isinstance(method_result, dict):
                result.update(method_result)
                if "success" not in result: result["success"] = True
            else:
                result["success"] = True
                result["result"] = method_result
            return result
        except Exception as e:
            return handle_error(result, e)

    def __call__(self, method, **kwargs):
        """Call a method by name with keyword arguments."""
        # Basic operations
        if method == "ipfs_kit_stop": return self.ipfs_kit_stop(**kwargs)
        if method == "ipfs_kit_start": return self.ipfs_kit_start(**kwargs)
        if method == "ipfs_kit_ready": return self.ipfs_kit_ready(**kwargs)

        # IPFS operations (delegated to self.ipfs)
        if method.startswith('ipfs_') and hasattr(self, 'ipfs') and hasattr(self.ipfs, method):
             # Handle specific case for upload_object alias if needed
            if method == 'ipfs_upload_object':
                self.method = 'ipfs_upload_object' # Why is this set? Seems like a potential bug. Keeping for now.
            return getattr(self.ipfs, method)(**kwargs)

        # IPFS Cluster operations (role-specific)
        if method == "ipfs_follow_list":
            if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                return self.ipfs_cluster_ctl.ipfs_follow_list(**kwargs)
            elif self.role == "master": raise AttributeError("ipfs_cluster_ctl component not initialized for master role")
            else: raise PermissionError("Method 'ipfs_follow_list' requires master role")
        if method == "ipfs_follow_ls":
            if self.role != "master" and hasattr(self, 'ipfs_cluster_follow'):
                return self.ipfs_cluster_follow.ipfs_follow_ls(**kwargs)
            elif self.role != "master": raise AttributeError("ipfs_cluster_follow component not initialized for non-master role")
            else: raise PermissionError("Method 'ipfs_follow_ls' cannot be called by master role")
        if method == "ipfs_follow_info":
            if self.role != "master" and hasattr(self, 'ipfs_cluster_follow'):
                return self.ipfs_cluster_follow.ipfs_follow_info(**kwargs)
            elif self.role != "master": raise AttributeError("ipfs_cluster_follow component not initialized for non-master role")
            else: raise PermissionError("Method 'ipfs_follow_info' cannot be called by master role")
        if method == 'ipfs_cluster_get_pinset':
             # Delegate based on role if the method isn't directly on ipfs_kit
             if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                 return self.ipfs_cluster_ctl.ipfs_cluster_get_pinset(**kwargs)
             elif self.role == "worker" and hasattr(self, 'ipfs_cluster_follow'):
                 # Assuming worker needs to list pins via follow list
                 return self.ipfs_cluster_follow.ipfs_follow_list(**kwargs)
             elif hasattr(self, 'ipfs_get_pinset'): # Check if it's a method on self (unlikely based on code)
                 return self.ipfs_get_pinset(**kwargs)
             else: raise AttributeError("Cannot get cluster pinset in current role/state")
        if method == 'ipfs_cluster_ctl_add_pin':
            if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                return self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(**kwargs)
            elif self.role == "master": raise AttributeError("ipfs_cluster_ctl component not initialized for master role")
            else: raise PermissionError("Method 'ipfs_cluster_ctl_add_pin' requires master role")
        if method == 'ipfs_cluster_ctl_rm_pin':
            if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                return self.ipfs_cluster_ctl.ipfs_cluster_ctl_rm_pin(**kwargs)
            elif self.role == "master": raise AttributeError("ipfs_cluster_ctl component not initialized for master role")
            else: raise PermissionError("Method 'ipfs_cluster_ctl_rm_pin' requires master role")

        # IPGet operations
        if method == 'ipget_download_object':
            self.method = 'download_object' # Why is this set? Seems like a potential bug. Keeping for now.
            if hasattr(self, 'ipget'):
                return self.ipget.ipget_download_object(**kwargs)
            else: raise AttributeError("ipget component not initialized")

        # Collection operations
        if method == 'load_collection': return self.load_collection(**kwargs)

        # libp2p operations
        if method.startswith('libp2p_'): return self._check_libp2p_and_call(method.replace('libp2p_', ''), **kwargs)
        if method == 'close_libp2p':
             if self.libp2p: return self.libp2p.close()
             else: return {"success": True, "message": "libp2p not initialized"} # Or raise error?

        # Cluster management operations
        if method in ['create_task', 'get_task_status', 'cancel_task', 'get_tasks', 'get_nodes', 'get_cluster_status', 'find_content_providers', 'get_content', 'get_state_interface_info']:
            return self._check_cluster_manager_and_call(method, **kwargs)
        if method == 'stop_cluster_manager':
            if hasattr(self, 'cluster_manager') and self.cluster_manager: return self.cluster_manager.stop()
            else: return {"success": True, "message": "Cluster manager not initialized"}
        if method == 'access_state_from_external_process':
            if 'state_path' not in kwargs: raise ValueError("Missing required parameter: state_path")
            # Assuming _call_static_cluster_manager exists or needs implementation
            if hasattr(self, '_call_static_cluster_manager'):
                return self._call_static_cluster_manager('access_state_from_external_process', **kwargs)
            else: raise NotImplementedError("_call_static_cluster_manager not implemented")

        # Monitoring operations (Assuming these are methods on ipfs_kit or need helpers)
        # Example: if method == 'start_monitoring': return self.start_monitoring(**kwargs)
        # Add checks similar to others if these depend on HAS_MONITORING and self.monitoring
        # ... (Add similar checks for all monitoring methods)

        # Knowledge graph operations
        if method in ['add_entity', 'update_entity', 'get_entity', 'delete_entity', 'add_relationship', 'get_relationship', 'delete_relationship', 'query_related', 'vector_search', 'graph_vector_search', 'get_statistics', 'export_subgraph', 'import_subgraph', 'get_version_history']:
            return self._check_knowledge_graph_and_call(method, **kwargs)

        # Graph query operations
        if method in ['find_entities', 'find_related', 'find_paths', 'hybrid_search', 'get_knowledge_cards']:
            return self._check_graph_query_and_call(method, **kwargs)

        # GraphRAG operations
        if method in ['generate_embedding', 'retrieve', 'format_context_for_llm', 'generate_llm_prompt']:
            return self._check_graph_rag_and_call(method, **kwargs)

        # AI/ML integration operations
        if method in ['add_model', 'get_model', 'list_models']:
            return self._check_ai_ml_and_call('model_registry', method, **kwargs)
        if method in ['add_dataset', 'get_dataset', 'list_datasets']:
            return self._check_ai_ml_and_call('dataset_manager', method, **kwargs)
        if method in ['langchain_check_availability', 'langchain_create_vectorstore', 'langchain_create_document_loader']:
            return self._check_ai_ml_and_call('langchain_integration', method.replace('langchain_', ''), **kwargs)
        if method in ['llamaindex_check_availability', 'llamaindex_create_document_reader', 'llamaindex_create_storage_context']:
            return self._check_ai_ml_and_call('llama_index_integration', method.replace('llamaindex_', ''), **kwargs)
        if method in ['prepare_distributed_task', 'execute_training_task', 'aggregate_training_results']:
            return self._check_ai_ml_and_call('distributed_training', method, **kwargs)

        # Data Loader operations
        if method == 'get_data_loader':
            # Assuming get_data_loader is a method of ipfs_kit or needs a helper
            if hasattr(self, 'get_data_loader'):
                data_loader = self.get_data_loader(**kwargs)
                return {"success": True, "operation": "get_data_loader", "data_loader": data_loader}
            else: raise NotImplementedError("get_data_loader not implemented or available")

        # Handle unknown method
        raise ValueError(f"Unknown method: {method}")

    def ipfs_kit_ready(self, **kwargs):
        """Check if IPFS and IPFS Cluster services are ready."""
        operation = "ipfs_kit_ready"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)
                 # else: pass # Continue if validation module not found

            cluster_name = kwargs.get("cluster_name") or getattr(self, 'cluster_name', None)
            if self.role != "leecher" and not cluster_name:
                return handle_error(result, IPFSError("cluster_name is required for master/worker roles"))

            ipfs_ready = False
            ipfs_cluster_ready = False
            try:
                cmd = ["pgrep", "-f", "ipfs daemon"]
                env = os.environ.copy()
                if hasattr(self.ipfs, 'run_ipfs_command'):
                    ps_result = self.ipfs.run_ipfs_command(cmd, check=False, correlation_id=correlation_id)
                    ipfs_ready = ps_result.get("success", False) and ps_result.get("stdout", "").strip() != ""
                else:
                    process = subprocess.run(cmd, capture_output=True, check=False, shell=False, env=env)
                    ipfs_ready = process.returncode == 0 and process.stdout.decode().strip() != ""
            except Exception as e: self.logger.warning(f"Error checking IPFS daemon status: {str(e)}")

            if self.role == "master" and hasattr(self, 'ipfs_cluster_service'):
                cluster_result = self.ipfs_cluster_service.ipfs_cluster_service_ready()
                result["success"] = True
                result["ipfs_ready"] = ipfs_ready
                result["cluster_ready"] = cluster_result.get("success", False)
                result["ready"] = ipfs_ready and result["cluster_ready"]
                result["cluster_status"] = cluster_result
                return result
            elif self.role == "worker" and hasattr(self, 'ipfs_cluster_follow'):
                try:
                    follow_result = self.ipfs_cluster_follow.ipfs_follow_info()
                    if (isinstance(follow_result, dict) and
                        follow_result.get("cluster_peer_online") == 'true' and
                        follow_result.get("ipfs_peer_online") == 'true' and
                        (cluster_name is None or follow_result.get("cluster_name") == cluster_name)):
                        ipfs_cluster_ready = True
                        self.ipfs_follow_info = follow_result # Store for reference
                except Exception as e: self.logger.warning(f"Error checking cluster follower status: {str(e)}")

            libp2p_ready = False
            if hasattr(self, 'libp2p') and self.libp2p is not None:
                try: libp2p_ready = self.libp2p.get_peer_id() is not None
                except Exception as e: self.logger.warning(f"Error checking libp2p status: {str(e)}")

            cluster_manager_ready = False
            if hasattr(self, 'cluster_manager') and self.cluster_manager is not None:
                try:
                    cluster_status = self.cluster_manager.get_cluster_status()
                    cluster_manager_ready = cluster_status.get("success", False)
                    result["cluster_manager_status"] = cluster_status
                except Exception as e:
                    self.logger.warning(f"Error checking cluster manager status: {str(e)}")
                    result["cluster_manager_error"] = str(e)

            if self.role == "leecher": ready = ipfs_ready or (hasattr(self, 'libp2p') and libp2p_ready)
            else: ready = ipfs_ready and (ipfs_cluster_ready or cluster_manager_ready)

            result["success"] = True
            result["ready"] = ready
            result["ipfs_ready"] = ipfs_ready
            if self.role != "leecher": result["cluster_ready"] = ipfs_cluster_ready
            if hasattr(self, 'libp2p'): result["libp2p_ready"] = libp2p_ready
            if hasattr(self, 'cluster_manager'): result["cluster_manager_ready"] = cluster_manager_ready
            return result
        except Exception as e:
            return handle_error(result, e)

    def load_collection(self, cid=None, **kwargs):
        """Load a collection from IPFS."""
        operation = "load_collection"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if cid is None: return handle_error(result, IPFSValidationError("Missing required parameter: cid"))
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            dst_path = kwargs.get("path")
            if not dst_path:
                try:
                    base_path = self.ipfs_path if hasattr(self, 'ipfs_path') else os.path.expanduser("~/.ipfs")
                    pins_dir = os.path.join(base_path, "pins")
                    os.makedirs(pins_dir, exist_ok=True)
                    dst_path = os.path.join(pins_dir, cid)
                except Exception as e: return handle_error(result, IPFSError(f"Failed to create destination directory: {str(e)}"))
            else:
                 # Validate provided path (assuming it exists)
                 try: from .validation import validate_path; validate_path(dst_path, "path")
                 except (ImportError, IPFSValidationError) as e:
                      if isinstance(e, IPFSValidationError): return handle_error(result, e)

            try:
                download_result = self.ipget.ipget_download_object(cid=cid, path=dst_path, correlation_id=correlation_id)
                if not isinstance(download_result, dict) or not download_result.get("success", False):
                    error_msg = download_result.get("error") if isinstance(download_result, dict) else str(download_result)
                    return handle_error(result, IPFSError(f"Failed to download collection: {error_msg}"))
                result["download"] = download_result
            except Exception as e: return handle_error(result, IPFSError(f"Failed to download collection: {str(e)}"))

            try:
                with open(dst_path, 'r') as f: collection_str = f.read()
            except Exception as e: return handle_error(result, IPFSError(f"Failed to read collection file: {str(e)}"))

            try:
                collection_data = json.loads(collection_str)
                result["success"], result["cid"], result["collection"], result["format"] = True, cid, collection_data, "json"
            except json.JSONDecodeError:
                result["success"], result["cid"], result["collection"], result["format"], result["warning"] = True, cid, collection_str, "text", "Collection could not be parsed as JSON"
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_add_pin(self, pin=None, **kwargs):
        """Pin content in IPFS and cluster."""
        operation = "ipfs_add_pin"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if pin is None: return handle_error(result, IPFSValidationError("Missing required parameter: pin"))
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            dst_path = kwargs.get("path")
            if not dst_path:
                try:
                    base_path = self.ipfs_path if hasattr(self, 'ipfs_path') else os.path.expanduser("~/.ipfs")
                    pins_dir = os.path.join(base_path, "pins")
                    os.makedirs(pins_dir, exist_ok=True)
                    dst_path = os.path.join(pins_dir, pin)
                except Exception as e: return handle_error(result, IPFSError(f"Failed to create destination directory: {str(e)}"))
            else:
                 # Validate provided path (assuming it exists)
                 try: from .validation import validate_path; validate_path(dst_path, "path")
                 except (ImportError, IPFSValidationError) as e:
                      if isinstance(e, IPFSValidationError): return handle_error(result, e)

            try:
                download_result = self.ipget.ipget_download_object(cid=pin, path=dst_path, correlation_id=correlation_id)
                if isinstance(download_result, dict) and download_result.get("success", False):
                    result["download_success"], result["download"] = True, download_result
                else:
                    error_msg = download_result.get("error") if isinstance(download_result, dict) else str(download_result)
                    result["download_success"], result["download_error"] = False, error_msg
                    self.logger.warning(f"Download failed, continuing with pin operation: {error_msg}")
            except Exception as e:
                result["download_success"], result["download_error"] = False, str(e)
                self.logger.warning(f"Download failed, continuing with pin operation: {str(e)}")

            result1, result2 = None, None
            kwargs['correlation_id'] = correlation_id # Ensure propagation

            if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                try: result1 = self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(dst_path, **kwargs)
                except Exception as e: result["cluster_pin_error"] = str(e); self.logger.error(f"Cluster pin operation failed: {str(e)}")
                try: result2 = self.ipfs.ipfs_add_pin(pin, **kwargs)
                except Exception as e: result["ipfs_pin_error"] = str(e); self.logger.error(f"IPFS pin operation failed: {str(e)}")
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, 'ipfs'):
                try: result2 = self.ipfs.ipfs_add_pin(pin, **kwargs)
                except Exception as e: result["ipfs_pin_error"] = str(e); self.logger.error(f"IPFS pin operation failed: {str(e)}")

            cluster_success = isinstance(result1, dict) and result1.get("success", False) if result1 is not None else False
            ipfs_success = isinstance(result2, dict) and result2.get("success", False) if result2 is not None else False

            result["success"] = (cluster_success and ipfs_success) if self.role == "master" else ipfs_success
            result["cid"] = pin
            result["ipfs_cluster"] = result1
            result["ipfs"] = result2
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_add_path(self, path=None, **kwargs):
        """Add a file or directory to IPFS and cluster."""
        operation = "ipfs_add_path"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if path is None: return handle_error(result, IPFSValidationError("Missing required parameter: path"))
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            kwargs['correlation_id'] = correlation_id # Ensure propagation
            result1, result2 = None, None

            self.logger.info(f"ipfs_kit calling ipfs_py.ipfs_add_path with path: {repr(path)}") # ADDED LOGGING

            if self.role == "master" and hasattr(self, 'ipfs') and hasattr(self, 'ipfs_cluster_ctl'):
                try:
                    result2 = self.ipfs.ipfs_add_path(path, **kwargs)
                    if isinstance(result2, dict) and result2.get("success", False):
                        try: result1 = self.ipfs_cluster_ctl.ipfs_cluster_ctl_add_path(path, **kwargs)
                        except Exception as e: result["cluster_add_error"] = str(e); self.logger.error(f"Cluster add operation failed: {str(e)}")
                    else: result["ipfs_add_error"] = "IPFS add operation failed, skipping cluster add"; self.logger.error("IPFS add operation failed, skipping cluster add")
                except Exception as e: result["ipfs_add_error"] = str(e); self.logger.error(f"IPFS add operation failed: {str(e)}")
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, 'ipfs'):
                try: result2 = self.ipfs.ipfs_add_path(path, **kwargs)
                except Exception as e: result["ipfs_add_error"] = str(e); self.logger.error(f"IPFS add operation failed: {str(e)}")

            cluster_success = isinstance(result1, dict) and result1.get("success", False) if result1 is not None else False
            ipfs_success = isinstance(result2, dict) and result2.get("success", False) if result2 is not None else False

            result["success"] = ipfs_success # Base success on IPFS add
            if self.role == "master": result["fully_successful"] = ipfs_success and cluster_success
            result["path"] = path
            result["ipfs_cluster"] = result1
            result["ipfs"] = result2
            if ipfs_success and "files" in result2: result["files"] = result2["files"]
            if ipfs_success and os.path.isfile(path) and "cid" in result2: result["cid"] = result2["cid"]
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_ls_path(self, path=None, **kwargs):
        """List contents of an IPFS path."""
        operation = "ipfs_ls_path"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if path is None: return handle_error(result, IPFSValidationError("Missing required parameter: path"))
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            kwargs['correlation_id'] = correlation_id # Ensure propagation
            ls_result = self.ipfs.ipfs_ls_path(path, **kwargs)

            if not isinstance(ls_result, dict):
                result["success"], result["path"] = True, path
                items = [item for item in ls_result if item != ""] if isinstance(ls_result, list) else []
                result["items"], result["count"] = items, len(items)
            elif ls_result.get("success", False):
                result["success"], result["path"] = True, path
                result["items"] = ls_result.get("items", [])
                result["count"] = ls_result.get("count", 0)
            else:
                return handle_error(result, IPFSError(f"Failed to list path: {ls_result.get('error', 'Unknown error')}"), {"ipfs_result": ls_result})
            return result
        except Exception as e:
            return handle_error(result, e)

    def name_resolve(self, **kwargs):
        """Resolve IPNS name to CID."""
        operation = "name_resolve"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            path = kwargs.get('path')
            if path is not None:
                try:
                    from .validation import validate_parameter_type, COMMAND_INJECTION_PATTERNS
                    validate_parameter_type(path, str, "path")
                    if any(re.search(pattern, path) for pattern in COMMAND_INJECTION_PATTERNS):
                        return handle_error(result, IPFSValidationError(f"Path contains potentially malicious patterns: {path}"))
                except (ImportError, IPFSValidationError) as e:
                     if isinstance(e, IPFSValidationError): return handle_error(result, e)

            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            kwargs['correlation_id'] = correlation_id # Ensure propagation
            resolve_result = self.ipfs.ipfs_name_resolve(**kwargs)

            if isinstance(resolve_result, dict) and resolve_result.get("success", False):
                result["success"] = True
                result["ipns_name"] = resolve_result.get("ipns_name")
                result["resolved_cid"] = resolve_result.get("resolved_cid")
            elif isinstance(resolve_result, str):
                result["success"], result["resolved_cid"] = True, resolve_result
                if path: result["ipns_name"] = path
            else:
                return handle_error(result, IPFSError(f"Failed to resolve IPNS name: {resolve_result.get('error', 'Unknown error')}"), {"ipfs_result": resolve_result})
            return result
        except Exception as e:
            return handle_error(result, e)

    def name_publish(self, path=None, **kwargs):
        """Publish content to IPNS."""
        operation = "name_publish"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if path is None: return handle_error(result, IPFSValidationError("Missing required parameter: path"))
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            kwargs['correlation_id'] = correlation_id # Ensure propagation
            publish_result = self.ipfs.ipfs_name_publish(path, **kwargs)

            if isinstance(publish_result, dict):
                if publish_result.get("success", False):
                    result["success"], result["path"] = True, path
                    if "add" in publish_result: result["add"] = publish_result["add"]
                    if "publish" in publish_result:
                        result["publish"] = publish_result["publish"]
                        if "ipns_name" in publish_result["publish"]: result["ipns_name"] = publish_result["publish"]["ipns_name"]
                        if "cid" in publish_result["publish"]: result["cid"] = publish_result["publish"]["cid"]
                else:
                    error_msg = publish_result.get("error", "Unknown error")
                    extra_data = {"add": publish_result["add"]} if "add" in publish_result else {}
                    return handle_error(result, IPFSError(f"Failed to publish to IPNS: {error_msg}"), extra_data)
            else:
                result["success"], result["path"], result["legacy_result"], result["warning"] = True, path, publish_result, "Using legacy result format"
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_remove_path(self, path=None, **kwargs):
        """Remove a file or directory from IPFS."""
        operation = "ipfs_remove_path"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if path is None: return handle_error(result, IPFSValidationError("Missing required parameter: path"))
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            kwargs['correlation_id'] = correlation_id # Ensure propagation
            cluster_result, ipfs_result = None, None

            if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                try: cluster_result = self.ipfs_cluster_ctl.ipfs_cluster_ctl_remove_path(path, **kwargs)
                except Exception as e: self.logger.error(f"Error removing from IPFS cluster: {str(e)}"); result["cluster_error"] = str(e)
                try: ipfs_result = self.ipfs.ipfs_remove_path(path, **kwargs)
                except Exception as e: self.logger.error(f"Error removing from IPFS: {str(e)}"); result["ipfs_error"] = str(e)
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, 'ipfs'):
                try: ipfs_result = self.ipfs.ipfs_remove_path(path, **kwargs)
                except Exception as e: self.logger.error(f"Error removing from IPFS: {str(e)}"); result["ipfs_error"] = str(e)

            ipfs_success = isinstance(ipfs_result, dict) and ipfs_result.get("success", False) if ipfs_result is not None else False
            result["success"] = ipfs_success # Base success on IPFS operation
            result["path"] = path
            if cluster_result is not None: result["ipfs_cluster"] = cluster_result
            result["ipfs"] = ipfs_result
            return result
        except Exception as e:
            return handle_error(result, e)

    def ipfs_remove_pin(self, pin=None, **kwargs):
        """Remove a pin from IPFS."""
        operation = "ipfs_remove_pin"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if pin is None: return handle_error(result, IPFSValidationError("Missing required parameter: pin"))
            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args, is_valid_cid
                validate_command_args(kwargs)
                if not is_valid_cid(pin): return handle_error(result, IPFSValidationError(f"Invalid CID format: {pin}"))
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)
                 # else: pass # Continue if validation module not found

            kwargs['correlation_id'] = correlation_id # Ensure propagation
            cluster_result, ipfs_result = None, None

            if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
                try: cluster_result = self.ipfs_cluster_ctl.ipfs_cluster_ctl_remove_pin(pin, **kwargs)
                except Exception as e: self.logger.error(f"Error removing pin from IPFS cluster: {str(e)}"); result["cluster_error"] = str(e)
                try: ipfs_result = self.ipfs.ipfs_remove_pin(pin, **kwargs)
                except Exception as e: self.logger.error(f"Error removing pin from IPFS: {str(e)}"); result["ipfs_error"] = str(e)
            elif (self.role == "worker" or self.role == "leecher") and hasattr(self, 'ipfs'):
                try: ipfs_result = self.ipfs.ipfs_remove_pin(pin, **kwargs)
                except Exception as e: self.logger.error(f"Error removing pin from IPFS: {str(e)}"); result["ipfs_error"] = str(e)

            ipfs_success = isinstance(ipfs_result, dict) and ipfs_result.get("success", False) if ipfs_result is not None else False
            cluster_success = isinstance(cluster_result, dict) and cluster_result.get("success", False) if cluster_result is not None else False

            result["success"] = ipfs_success # Base success on IPFS operation
            if self.role == "master": result["fully_successful"] = ipfs_success and cluster_success
            result["cid"] = pin
            if cluster_result is not None: result["ipfs_cluster"] = cluster_result
            result["ipfs"] = ipfs_result
            return result
        except Exception as e:
            return handle_error(result, e)

    def test_install(self, **kwargs):
        """Test installation of components based on role."""
        if not hasattr(self, 'install_ipfs'):
             # Attempt to dynamically import if not done during init (unlikely needed)
             try: from .install_ipfs import install_ipfs as install_ipfs_mod; self.install_ipfs = install_ipfs_mod()
             except ImportError: raise ImportError("install_ipfs module not found")

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
            raise ValueError("role is not master, worker, or leecher")

    def ipfs_get_pinset(self, **kwargs):
        """Get pinset from IPFS and potentially cluster."""
        ipfs_pinset = self.ipfs.ipfs_get_pinset(**kwargs) if hasattr(self, 'ipfs') else None
        ipfs_cluster = None
        if self.role == "master" and hasattr(self, 'ipfs_cluster_ctl'):
            ipfs_cluster = self.ipfs_cluster_ctl.ipfs_cluster_get_pinset(**kwargs)
        elif self.role == "worker" and hasattr(self, 'ipfs_cluster_follow'):
            ipfs_cluster = self.ipfs_cluster_follow.ipfs_follow_list(**kwargs) # Assuming list gives pinset for worker
        return {"ipfs_cluster": ipfs_cluster, "ipfs": ipfs_pinset}

    def ipfs_kit_stop(self, **kwargs):
        """Stop all relevant IPFS services."""
        results = {}
        if self.role == "master":
            if hasattr(self, 'ipfs_cluster_service'):
                try: results["ipfs_cluster_service"] = self.ipfs_cluster_service.ipfs_cluster_service_stop()
                except Exception as e: results["ipfs_cluster_service"] = str(e)
            if hasattr(self, 'ipfs'):
                try: results["ipfs"] = self.ipfs.daemon_stop()
                except Exception as e: results["ipfs"] = str(e)
        elif self.role == "worker":
            if hasattr(self, 'ipfs_cluster_follow'):
                try: results["ipfs_cluster_follow"] = self.ipfs_cluster_follow.ipfs_follow_stop()
                except Exception as e: results["ipfs_cluster_follow"] = str(e)
            if hasattr(self, 'ipfs'):
                try: results["ipfs"] = self.ipfs.daemon_stop()
                except Exception as e: results["ipfs"] = str(e)
        elif self.role == "leecher":
            if hasattr(self, 'ipfs'):
                try: results["ipfs"] = self.ipfs.daemon_stop()
                except Exception as e: results["ipfs"] = str(e)

        if hasattr(self, 'libp2p') and self.libp2p is not None:
            try: self.libp2p.close(); results["libp2p"] = "Stopped"
            except Exception as e: results["libp2p"] = str(e)

        if hasattr(self, 'cluster_manager') and self.cluster_manager is not None:
             try: self.cluster_manager.stop(); results["cluster_manager"] = "Stopped"
             except Exception as e: results["cluster_manager"] = str(e)

        if hasattr(self, '_metadata_sync_handler') and self._metadata_sync_handler is not None:
             try: self._metadata_sync_handler.stop(); results["metadata_sync"] = "Stopped"
             except Exception as e: results["metadata_sync"] = str(e)

        # Add stop for monitoring if implemented
        if hasattr(self, 'monitoring') and self.monitoring is not None:
             try: self.monitoring.stop(); results["monitoring"] = "Stopped"
             except Exception as e: results["monitoring"] = str(e)
        if hasattr(self, 'dashboard') and self.dashboard is not None:
             try: self.dashboard.stop(); results["dashboard"] = "Stopped"
             except Exception as e: results["dashboard"] = str(e)

        return results

    def ipfs_kit_start(self, **kwargs):
        """Start all relevant IPFS services."""
        results = {}
        enable_libp2p = kwargs.get('enable_libp2p', hasattr(self, 'libp2p') and self.libp2p is not None) # Default to keeping current state

        if self.role == "master":
            if hasattr(self, 'ipfs'):
                try: results["ipfs"] = self.ipfs.daemon_start()
                except Exception as e: results["ipfs"] = str(e)
            if hasattr(self, 'ipfs_cluster_service'):
                try: results["ipfs_cluster_service"] = self.ipfs_cluster_service.ipfs_cluster_service_start()
                except Exception as e: results["ipfs_cluster_service"] = str(e)
        elif self.role == "worker":
            if hasattr(self, 'ipfs'):
                try: results["ipfs"] = self.ipfs.daemon_start()
                except Exception as e: results["ipfs"] = str(e)
            if hasattr(self, 'ipfs_cluster_follow'):
                try: results["ipfs_cluster_follow"] = self.ipfs_cluster_follow.ipfs_follow_start()
                except Exception as e: results["ipfs_cluster_follow"] = str(e)
        elif self.role == "leecher":
            if hasattr(self, 'ipfs'):
                try: results["ipfs"] = self.ipfs.daemon_start()
                except Exception as e: results["ipfs"] = str(e)

        if enable_libp2p and HAS_LIBP2P:
            try:
                if hasattr(self, 'libp2p') and self.libp2p: self.libp2p.close() # Close existing first
                success = self._setup_libp2p(**kwargs) # Re-initialize
                results["libp2p"] = "Started" if success else "Failed to start"
            except Exception as e: results["libp2p"] = str(e)
        elif enable_libp2p and not HAS_LIBP2P:
             results["libp2p"] = "Not available"

        if hasattr(self, 'cluster_manager') and self.cluster_manager is not None:
             try: self.cluster_manager.start(); results["cluster_manager"] = "Started"
             except Exception as e: results["cluster_manager"] = str(e)

        if hasattr(self, '_metadata_sync_handler') and self._metadata_sync_handler is not None:
             try:
                 sync_interval = kwargs.get("metadata_sync_interval", 300) # Allow override
                 self._metadata_sync_handler.start(sync_interval=sync_interval); results["metadata_sync"] = "Started"
             except Exception as e: results["metadata_sync"] = str(e)

        # Add start for monitoring if implemented
        if hasattr(self, 'monitoring') and self.monitoring is not None:
             try: self.monitoring.start(); results["monitoring"] = "Started"
             except Exception as e: results["monitoring"] = str(e)
        if hasattr(self, 'dashboard') and self.dashboard is not None:
             try: self.dashboard.start(); results["dashboard"] = "Started"
             except Exception as e: results["dashboard"] = str(e)

        return results

    def ipfs_get_config(self, **kwargs):
        """Get IPFS configuration."""
        operation = "ipfs_get_config"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            cmd = ["ipfs", "config", "show"]
            if hasattr(self.ipfs, 'run_ipfs_command'):
                cmd_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
                if not cmd_result["success"]: return handle_error(result, IPFSError(f"Failed to get config: {cmd_result.get('error', 'Unknown error')}"))
                try:
                    config_data = json.loads(cmd_result.get("stdout", ""))
                    self.ipfs_config = config_data # Cache config
                    result["success"], result["config"] = True, config_data
                    return result
                except json.JSONDecodeError as e: return handle_error(result, IPFSError(f"Failed to parse config JSON: {str(e)}"))
            else: # Fallback
                try:
                    env = os.environ.copy()
                    process = subprocess.run(cmd, capture_output=True, check=True, shell=False, env=env)
                    config_data = json.loads(process.stdout)
                    self.ipfs_config = config_data # Cache config
                    result["success"], result["config"] = True, config_data
                    return result
                except json.JSONDecodeError as e: return handle_error(result, IPFSError(f"Failed to parse config JSON: {str(e)}"))
                except subprocess.CalledProcessError as e: return handle_error(result, IPFSError(f"Command failed: {e.stderr.decode()}"))
        except Exception as e:
            return handle_error(result, e)

    def ipfs_set_config(self, new_config=None, **kwargs):
        """Set IPFS configuration."""
        operation = "ipfs_set_config"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if new_config is None: return handle_error(result, IPFSValidationError("Missing required parameter: new_config"))
            if not isinstance(new_config, dict): return handle_error(result, IPFSValidationError(f"Invalid config type: expected dict"))
            # Security validation (assuming it exists)
            try: from .validation import validate_command_args; validate_command_args(kwargs)
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)

            temp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".json", mode="w+", delete=False) as temp_file:
                    json.dump(new_config, temp_file)
                    temp_file_path = temp_file.name
                cmd = ["ipfs", "config", "replace", temp_file_path]
                if hasattr(self.ipfs, 'run_ipfs_command'):
                    cmd_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
                    if not cmd_result["success"]: return handle_error(result, IPFSError(f"Failed to set config: {cmd_result.get('error', 'Unknown error')}"))
                    result["success"], result["message"] = True, "Configuration updated successfully"
                    self.ipfs_config = new_config # Update cache
                    return result
                else: # Fallback
                    env = os.environ.copy()
                    process = subprocess.run(cmd, capture_output=True, check=True, shell=False, env=env)
                    result["success"], result["message"], result["output"] = True, "Configuration updated successfully", process.stdout.decode()
                    self.ipfs_config = new_config # Update cache
                    return result
            except subprocess.CalledProcessError as e: return handle_error(result, IPFSError(f"Command failed: {e.stderr.decode()}"))
            except Exception as e: return handle_error(result, e)
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    try: 
                        os.unlink(temp_file_path)                    
                    except Exception as e_clean: 
                        self.logger.warning(f"Failed to remove temp file {temp_file_path}: {str(e_clean)}")
        except Exception as e:
            return handle_error(result, e)

    def ipfs_get_config_value(self, key=None, **kwargs):
        """Get a specific IPFS configuration value."""
        operation = "ipfs_get_config_value"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if key is None: return handle_error(result, IPFSValidationError("Missing required parameter: key"))
            if not isinstance(key, str): return handle_error(result, IPFSValidationError(f"Invalid key type: expected string"))
            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args, COMMAND_INJECTION_PATTERNS
                validate_command_args(kwargs)
                if any(re.search(pattern, key) for pattern in COMMAND_INJECTION_PATTERNS):
                    return handle_error(result, IPFSValidationError(f"Key contains potentially malicious patterns: {key}"))
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)
                 elif isinstance(e, ImportError): # Basic check if validation missing
                     if re.search(r'[;&|`$]', key): return handle_error(result, IPFSError(f"Key contains invalid characters: {key}"))

            cmd = ["ipfs", "config", key]
            if hasattr(self.ipfs, 'run_ipfs_command'):
                cmd_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
                if not cmd_result["success"]: return handle_error(result, IPFSError(f"Failed to get config value: {cmd_result.get('error', 'Unknown error')}"))
                try:
                    output = cmd_result.get("stdout", "")
                    try: config_value = json.loads(output)
                    except json.JSONDecodeError: config_value = output.strip()
                    result["success"], result["key"], result["value"] = True, key, config_value
                    return result
                except Exception as e: return handle_error(result, IPFSError(f"Failed to parse config value: {str(e)}"))
            else: # Fallback
                try:
                    env = os.environ.copy()
                    process = subprocess.run(cmd, capture_output=True, check=True, shell=False, env=env)
                    output = process.stdout.decode()
                    try: config_value = json.loads(output)
                    except json.JSONDecodeError: config_value = output.strip()
                    result["success"], result["key"], result["value"] = True, key, config_value
                    return result
                except json.JSONDecodeError as e: return handle_error(result, IPFSError(f"Failed to parse config value: {str(e)}"))
                except subprocess.CalledProcessError as e: return handle_error(result, IPFSError(f"Command failed: {e.stderr.decode()}"))
        except Exception as e:
            return handle_error(result, e)

    def ipfs_set_config_value(self, key=None, value=None, **kwargs):
        """Set a specific IPFS configuration value."""
        operation = "ipfs_set_config_value"
        correlation_id = kwargs.get('correlation_id')
        result = create_result_dict(operation, correlation_id)
        try:
            if key is None: return handle_error(result, IPFSValidationError("Missing required parameter: key"))
            if value is None: return handle_error(result, IPFSValidationError("Missing required parameter: value"))
            if not isinstance(key, str): return handle_error(result, IPFSValidationError(f"Invalid key type: expected string"))

            value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            is_json_value = isinstance(value, (dict, list))

            # Security validation (assuming it exists)
            try:
                from .validation import validate_command_args, COMMAND_INJECTION_PATTERNS
                validate_command_args(kwargs)
                if any(re.search(pattern, key) for pattern in COMMAND_INJECTION_PATTERNS):
                    return handle_error(result, IPFSValidationError(f"Key contains potentially malicious patterns: {key}"))
                if any(re.search(pattern, value_str) for pattern in COMMAND_INJECTION_PATTERNS):
                    return handle_error(result, IPFSValidationError(f"Value contains potentially malicious patterns"))
            except (ImportError, IPFSValidationError) as e:
                 if isinstance(e, IPFSValidationError): return handle_error(result, e)
                 elif isinstance(e, ImportError): # Basic check if validation missing
                     if re.search(r'[;&|`$]', key) or re.search(r'[;&|`$]', value_str):
                         return handle_error(result, IPFSError(f"Key or value contains invalid characters"))

            cmd = ["ipfs", "config"]
            if is_json_value: cmd.append("--json")
            cmd.extend([key, value_str])

            if hasattr(self.ipfs, 'run_ipfs_command'):
                cmd_result = self.ipfs.run_ipfs_command(cmd, correlation_id=correlation_id)
                if not cmd_result["success"]: return handle_error(result, IPFSError(f"Failed to set config value: {cmd_result.get('error', 'Unknown error')}"))
                result["success"], result["key"], result["value"], result["message"] = True, key, value, "Configuration value set successfully"
                return result
            else: # Fallback
                try:
                    env = os.environ.copy()
                    process = subprocess.run(cmd, capture_output=True, check=True, shell=False, env=env)
                    result["success"], result["key"], result["value"], result["message"] = True, key, value, "Configuration value set successfully"
                    return result
                except subprocess.CalledProcessError as e: return handle_error(result, IPFSError(f"Command failed: {e.stderr.decode()}"))
        except Exception as e:
            return handle_error(result, e)

# Extend the class with methods from ipfs_kit_extensions
extend_ipfs_kit(ipfs_kit)
