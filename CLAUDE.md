# CLAUDE.md - ipfs_kit_py Developer Guide

## Table of Contents
1. [Development Environment](#development-environment)
2. [Current Codebase Analysis](#current-codebase-analysis)
3. [IPFS Core Concepts](#ipfs-core-concepts)
4. [Development Roadmap](#development-roadmap)
5. [Technical Implementation Plan](#technical-implementation-plan)
6. [Advanced Features](#advanced-features)
7. [Technology Selection Guidelines](#technology-selection-guidelines)
8. [Troubleshooting](#troubleshooting)
9. [Documentation Resources](#9-documentation-resources)
   - [IPFS Cluster Documentation](#ipfs-cluster-documentation)
   - [Storacha/W3 Specifications](#storachaw3-specifications)
   - [libp2p Documentation](#libp2p-documentation)
   - [Documentation Relevance to Development Roadmap](#documentation-relevance-to-development-roadmap)
10. [Project Structure and Organization](#project-structure-and-organization)
    - [Directory Layout](#directory-layout)
    - [Component Relationships](#component-relationships)
    - [Versioning Strategy](#versioning-strategy)

## Development Environment

### Build & Test Commands
- **Install**: `pip install -e .`
- **Build**: `python setup.py build`
- **Run all tests**: `python -m test.test`
- **Run single test**: `python -m test.test_ipfs_kit` or `python -m test.test_storacha_kit`
- **Run API server**: `uvicorn ipfs_kit_py.api:app --reload --port 8000`
- **Generate AST**: `python -m astroid ipfs_kit_py > ast_analysis.json`
- **Check for duplications**: `pylint --disable=all --enable=duplicate-code ipfs_kit_py`

### Development Guidelines
- **Test-First Development**: All new features must first be developed in the test/ folder
- **Feature Isolation**: Do not modify code outside of test/ until fully debugged
- **API Exposure**: All functionality should be exposed via FastAPI endpoints
- **Performance Focus**: Use memory-mapped structures and Arrow C Data Interface for low-latency IPC
- **Code Analysis**: Maintain an abstract syntax tree (AST) of the project to identify and prevent code duplication
- **DRY Principle**: Use the AST to enforce Don't Repeat Yourself by detecting similar code structures

### Testing Strategy

The project follows a comprehensive testing approach to ensure reliability and maintainability:

#### Test Organization
- **Unit Tests**: Located in the `test/` directory with file naming pattern `test_*.py`
- **Integration Tests**: Also in `test/` but focused on component interactions
- **Performance Tests**: Specialized tests for measuring throughput and latency

#### Test Coverage Goals
- **Core Library**: Minimum 85% line coverage
- **API Layer**: Minimum 90% line coverage
- **Storage Tiers**: Minimum 80% line coverage
- **Exception Handling**: 100% coverage of error paths

#### Test Patterns
1. **Fixture-Based Testing**: Use pytest fixtures for test setup and teardown
2. **Mocking IPFS Daemon**: Use subprocess mocking to avoid actual daemon dependency
3. **Property-Based Testing**: Use hypothesis for edge case discovery
4. **Snapshot Testing**: For configuration and schema verification
5. **Parallelized Test Execution**: For faster feedback cycles

#### Test Implementation Example
```python
import pytest
from unittest.mock import patch, MagicMock
from ipfs_kit_py.ipfs_kit import IPFSKit

@pytest.fixture
def ipfs_kit_instance():
    """Create a properly configured IPFSKit instance for testing."""
    with patch('subprocess.run') as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-peer-id"}'
        mock_run.return_value = mock_process
        
        # Create instance with test configuration
        instance = IPFSKit(
            role="leecher",
            resources={"max_memory": 100 * 1024 * 1024},
            metadata={"test_mode": True}
        )
        yield instance

def test_add_content(ipfs_kit_instance):
    """Test adding content to IPFS."""
    # Arrange
    test_content = b"Test content"
    expected_cid = "QmTest123"
    
    with patch('subprocess.run') as mock_run:
        # Mock successful content addition
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = f'{{"Hash": "{expected_cid}"}}'.encode()
        mock_run.return_value = mock_process
        
        # Act
        result = ipfs_kit_instance.add(test_content)
        
        # Assert
        assert result["success"] is True
        assert result["cid"] == expected_cid
        mock_run.assert_called_once()
```

#### Continuous Integration Integration
- Tests are run on every PR and commit to main branch
- Test reports and coverage metrics are generated automatically
- Performance regression tests compare against baseline benchmarks

### Required Dependencies
- **Core Dependencies**:
  - Python >=3.8
  - requests>=2.28.0
  - multiformats>=0.1.4
  - boto3>=1.26.0
  - aiohttp>=3.8.4 (for async operations)
  - pydantic>=2.0.0 (for data validation)

### API Documentation

The project includes a FastAPI-based REST interface that exposes core functionality. The API server can be started with:
```bash
uvicorn ipfs_kit_py.api:app --reload --port 8000
```

#### Core API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check endpoint |
| `/api/v0/add` | POST | Add content to IPFS |
| `/api/v0/cat` | GET | Retrieve content by CID |
| `/api/v0/pin/add` | POST | Pin content to local node |
| `/api/v0/pin/rm` | POST | Unpin content |
| `/api/v0/pin/ls` | GET | List pinned content |
| `/api/v0/cluster/peers` | GET | List cluster peers |
| `/api/v0/cluster/pin` | POST | Pin content across cluster |
| `/api/v0/cluster/status` | GET | Get cluster-wide pin status |
| `/api/v0/storage/tiers` | GET | List configured storage tiers |
| `/api/v0/storage/migrate` | POST | Migrate content between tiers |

#### API Integration
The API follows the same patterns as the IPFS HTTP API but extends it with additional functionality for tiered storage, cluster management, and content routing. All API endpoints return JSON responses and accept either query parameters or JSON request bodies.

For detailed API documentation, the server provides an interactive Swagger UI at `/docs` and an OpenAPI specification at `/openapi.json` when running.

- **IPFS Binaries**:
  - Kubo (go-ipfs) >=0.18.0 or compatible implementation 
  - IPFS Cluster tools (for distributed pinning)
  - ipget (for content retrieval)

- **Development Dependencies**:
  - pytest>=7.0.0
  - pytest-cov>=4.1.0
  - pylint>=2.17.0
  - black>=23.3.0
  - mypy>=1.3.0

### Code Style Guidelines
- **Imports**: Standard library first, third-party next
- **Formatting**: 4-space indentation
- **Classes**: Initialize with `__init__(self, resources=None, metadata=None)`, end with `return None`
- **Naming**: snake_case for methods/variables, PascalCase for classes
- **Method Structure**: Methods typically accept `self, resources, metadata` parameters
- **Error Handling**: Use try/except blocks with results dictionary for error collection
- **Subprocess Pattern**: Use subprocess.run() with captured output for system commands
- **Testing Style**: Test classes follow `test_*` naming pattern with `init` and `test` methods

### Standardized Error Handling Approach

All components in the ipfs_kit_py project should follow these error handling patterns:

#### Result Dictionary Pattern
```python
def perform_operation(self, arg1, arg2):
    """Perform some IPFS operation with standardized result handling."""
    result = {
        "success": False,
        "operation": "perform_operation",
        "timestamp": time.time()
    }
    
    try:
        # Perform actual operation
        response = self.ipfs.some_method(arg1, arg2)
        
        # Process successful response
        result["success"] = True
        result["cid"] = response.get("Hash")
        result["size"] = response.get("Size")
        
    except requests.exceptions.ConnectionError as e:
        # Network-related errors
        result["error"] = f"IPFS daemon connection failed: {str(e)}"
        result["error_type"] = "connection_error"
        result["recoverable"] = True
        self.logger.error(f"Connection error in {result['operation']}: {e}")
        
    except requests.exceptions.Timeout as e:
        # Timeout errors
        result["error"] = f"IPFS operation timed out: {str(e)}"
        result["error_type"] = "timeout_error"
        result["recoverable"] = True
        self.logger.error(f"Timeout in {result['operation']}: {e}")
        
    except json.JSONDecodeError as e:
        # Response parsing errors
        result["error"] = f"Invalid response format from IPFS daemon: {str(e)}"
        result["error_type"] = "parse_error"
        result["recoverable"] = False
        self.logger.error(f"Parse error in {result['operation']}: {e}")
        
    except Exception as e:
        # Catch-all for unexpected errors
        result["error"] = f"Unexpected error: {str(e)}"
        result["error_type"] = "unknown_error"
        result["recoverable"] = False
        # Include stack trace in logs but not in result
        self.logger.exception(f"Unexpected error in {result['operation']}")
        
    return result
```

#### Error Hierarchy
Create specialized exceptions for common error scenarios:

```python
class IPFSError(Exception):
    """Base class for all IPFS-related exceptions."""
    pass

class IPFSConnectionError(IPFSError):
    """Error when connecting to IPFS daemon."""
    pass

class IPFSTimeoutError(IPFSError):
    """Timeout when communicating with IPFS daemon."""
    pass

class IPFSContentNotFoundError(IPFSError):
    """Content with specified CID not found."""
    pass

class IPFSValidationError(IPFSError):
    """Input validation failed."""
    pass

class IPFSConfigurationError(IPFSError):
    """IPFS configuration is invalid or missing."""
    pass

class IPFSPinningError(IPFSError):
    """Error during content pinning/unpinning."""
    pass
```

#### Error Recovery Patterns

For recoverable errors like network issues, implement these retry patterns:

```python
def perform_with_retry(self, operation_func, *args, max_retries=3, 
                      backoff_factor=2, **kwargs):
    """Perform operation with exponential backoff retry."""
    attempt = 0
    last_exception = None
    
    while attempt < max_retries:
        try:
            return operation_func(*args, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as e:
            attempt += 1
            last_exception = e
            
            if attempt < max_retries:
                # Calculate sleep time with exponential backoff
                sleep_time = backoff_factor ** attempt
                self.logger.warning(
                    f"Retry attempt {attempt} after error: {str(e)}. "
                    f"Waiting {sleep_time}s before retry."
                )
                time.sleep(sleep_time)
            else:
                self.logger.error(
                    f"All {max_retries} retry attempts failed for operation. "
                    f"Last error: {str(e)}"
                )
    
    # If we get here, all retries failed
    if last_exception:
        raise last_exception
        
    # This should never happen, but just in case
    raise RuntimeError("Retry loop exited without success or exception")
```

#### Batch Operation Error Handling

For operations involving multiple items, use partial success handling:

```python
def pin_multiple(self, cids):
    """Pin multiple CIDs with partial success handling."""
    results = {
        "success": True,  # Overall success (will be False if any operation fails)
        "operation": "pin_multiple",
        "timestamp": time.time(),
        "total": len(cids),
        "successful": 0,
        "failed": 0,
        "items": {}
    }
    
    for cid in cids:
        try:
            pin_result = self.pin(cid)
            results["items"][cid] = pin_result
            
            if pin_result["success"]:
                results["successful"] += 1
            else:
                results["failed"] += 1
                # Overall operation is a failure if any item fails
                results["success"] = False
                
        except Exception as e:
            results["items"][cid] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            results["failed"] += 1
            results["success"] = False
            
    return results
```

#### Subprocess Error Handling

For subprocess calls to IPFS binaries, use this pattern:

```python
def run_ipfs_command(self, cmd_args, check=True, timeout=30):
    """Run IPFS command with proper error handling."""
    result = {
        "success": False,
        "command": cmd_args[0] if cmd_args else None,
        "timestamp": time.time()
    }
    
    try:
        # Never use shell=True for security
        process = subprocess.run(
            cmd_args,
            capture_output=True,
            check=check,  # Will raise CalledProcessError on non-zero exit
            timeout=timeout
        )
        
        # Process successful completion
        result["success"] = True
        result["returncode"] = process.returncode
        result["stdout"] = process.stdout
        
        # Only include stderr if there's content
        if process.stderr:
            result["stderr"] = process.stderr
            
        return result
        
    except subprocess.TimeoutExpired as e:
        result["error"] = f"Command timed out after {timeout} seconds"
        result["error_type"] = "timeout"
        self.logger.error(f"Timeout running command: {' '.join(cmd_args)}")
        
    except subprocess.CalledProcessError as e:
        result["error"] = f"Command failed with return code {e.returncode}"
        result["error_type"] = "process_error"
        result["returncode"] = e.returncode
        result["stdout"] = e.stdout
        result["stderr"] = e.stderr
        self.logger.error(
            f"Command failed: {' '.join(cmd_args)}\n"
            f"Return code: {e.returncode}\n"
            f"Stderr: {e.stderr.decode('utf-8', errors='replace')}"
        )
        
    except Exception as e:
        result["error"] = f"Failed to execute command: {str(e)}"
        result["error_type"] = "execution_error"
        self.logger.exception(f"Exception running command: {' '.join(cmd_args)}")
        
    return result
```

## Current Codebase Analysis

### IPFS Documentation Structure
The project includes comprehensive IPFS documentation in `/docs/ipfs-docs/`, which provides valuable references for implementing IPFS functionality:

- **Concepts** (`/docs/ipfs-docs/docs/concepts/`): Core IPFS concepts and architecture
  - `what-is-ipfs.md`: IPFS overview and basic concepts
  - `content-addressing.md`: How content addressing works (CIDs)
  - `merkle-dag.md`: Data structures underlying IPFS
  - `ipld.md`: InterPlanetary Linked Data format
  - `dht.md`: Distributed Hash Table for content routing
  - `bitswap.md`: Protocol for exchanging blocks
  - `libp2p.md`: Networking stack used by IPFS
  - `ipfs-gateway.md`: Gateway functionality and types

- **How-to Guides** (`/docs/ipfs-docs/docs/how-to/`): Practical implementation guides
  - `configure-node.md`: Node configuration options
  - `kubo-rpc-tls-auth.md`: Securing the RPC API
  - `pin-files.md`: Content pinning functionality
  - `publish-ipns.md`: Using IPNS (naming system)
  - `work-with-blocks.md`: Block-level operations

- **Reference** (`/docs/ipfs-docs/docs/reference/`): API and command references
  - `kubo/cli.md`: Command-line interface reference
  - `kubo/rpc.md`: RPC API reference
  - `http/api.md`: HTTP API endpoints
  - `http/gateway.md`: Gateway API reference

### Core Architecture
The ipfs_kit_py module implements a layered architecture with several key components:

1. **ipfs_kit**: Main orchestrator class providing a unified interface
2. **ipfs_py**: Handles low-level IPFS (Kubo) daemon operations with UnixFS integration
3. **storacha_kit**: Provides Web3.Storage integration
4. **s3_kit**: Manages S3-compatible storage operations
5. **ipfs_multiformats_py**: Handles CID creation and multihash operations

### Class Hierarchy
```
┌───────────────────────────────────────────────────────────┐
│                        ipfs_kit                           │
└───────────┬──────────┬──────────┬───────────┬─────────────┘
            │          │          │           │
            ▼          ▼          ▼           ▼
┌──────────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐
│   ipfs_py    │ │  ipget  │ │ s3_kit  │ │ storacha_kit  │
└──────────────┘ └─────────┘ └─────────┘ └───────────────┘
       │
       │
       ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│ ipfs_cluster_service │◄───┤ Based on role (master only) │
└──────────────────────┘    └─────────────────────────────┘
       │
       │
       ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│   ipfs_cluster_ctl   │◄───┤ Based on role (master only) │
└──────────────────────┘    └─────────────────────────────┘
       │
       │
       ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│ ipfs_cluster_follow  │◄───┤ Based on role (worker only) │
└──────────────────────┘    └─────────────────────────────┘
```

### Key Design Patterns

#### Role-based Architecture
The system implements a specialized role-based model for distributed content processing with three distinct node types:

- **Master Node**: 
  - Orchestrates the entire content ecosystem
  - Aggregates and arranges content into coherent collections
  - Coordinates task distribution across worker nodes
  - Manages metadata indexes and content routing tables
  - Maintains the high-level view of content relationships
  - Handles complex operations like model training coordination and GraphRAG database management
  - Runs the IPFS Cluster service in "master" mode with pinning management responsibilities
  - Typically deployed on high-resource infrastructure with significant storage and bandwidth

- **Worker Node**: 
  - Processes individual content items identified by CIDs
  - Executes specific computational tasks assigned by the master
  - Specializes in content transformation, analysis, and feature extraction
  - Handles CPU/GPU-intensive operations like embedding generation
  - Contributes processing power to the network rather than primarily storage
  - Returns processed results back to the master for aggregation
  - Participates in the IPFS Cluster as a processing-focused node
  - Often deployed in horizontal scaling clusters for parallelized processing

- **Leecher Node**: 
  - Primarily consumes network resources rather than contributing
  - Acts as an edge device (laptops, phones, IoT devices, etc.)
  - Retrieves and utilizes content without significant contribution to the network
  - Maintains minimal local cache for recently accessed content
  - May operate in offline mode with limited subset of content
  - Typically has constrained resources (storage, bandwidth, computation)
  - Does not participate in cluster coordination or content processing
  - Optimized for efficient content consumption with minimal resource usage

This role-based design enables efficient distribution of both content and computation across heterogeneous devices, allowing specialized optimization for each node type's primary function.

#### Implementation in Content Processing Workflows

The role-based architecture is particularly powerful for distributed AI and data processing workflows:

1. **Model Training Pipeline**:
   - **Master**: Coordinates dataset preparation, model parameter distribution, and result aggregation
   - **Workers**: Execute model training on specific data subsets, calculate gradients, and perform feature extraction
   - **Leechers**: Consume trained models for inference at the edge with minimal resource requirements

2. **GraphRAG Knowledge System**:
   - **Master**: Maintains the comprehensive knowledge graph, handles query parsing, and manages embedding indexes
   - **Workers**: Process document chunks, generate embeddings, extract entities/relationships, and perform similarity calculations
   - **Leechers**: Submit queries and receive responses without participating in the knowledge base construction

3. **Content Distribution Network**:
   - **Master**: Orchestrates content pinning strategies, manages metadata, and tracks network-wide content availability
   - **Workers**: Handle content transformation (transcoding, resizing, format conversion) and persistence guarantees
   - **Leechers**: Access content through gateways or direct peer connections with optimal local caching

#### Node Configuration Example

```python
def configure_node_by_role(role, resources=None, metadata=None):
    """Configure an IPFS node based on its role in the cluster.
    
    Args:
        role: One of "master", "worker", or "leecher"
        resources: Dictionary of available resources (RAM, CPU, disk, etc.)
        metadata: Additional configuration parameters
    
    Returns:
        Configured IPFS kit instance
    """
    config = {}
    
    # Base configuration common to all roles
    config["Addresses"] = {
        "Swarm": [
            "/ip4/0.0.0.0/tcp/4001",
            "/ip6/::/tcp/4001",
            "/ip4/0.0.0.0/udp/4001/quic",
            "/ip6/::/udp/4001/quic"
        ],
        "API": "/ip4/127.0.0.1/tcp/5001",
        "Gateway": "/ip4/127.0.0.1/tcp/8080"
    }
    
    # Role-specific configurations
    if role == "master":
        # Master nodes focus on orchestration and content management
        config["Datastore"] = {
            "StorageMax": "1TB", 
            "StorageGCWatermark": 80,
            "GCPeriod": "12h"
        }
        config["Routing"] = {
            "Type": "dhtserver"  # Full DHT node
        }
        config["Pinning"] = {
            "RemoteServices": {
                # Integration with backup pinning services
            }
        }
        # Enable cluster service for master
        config["Cluster"] = {
            "PeerAddresses": [],
            "ReplicationFactor": 3,
            "MonitorPingInterval": "15s"
        }
        
    elif role == "worker":
        # Workers focus on processing power more than storage
        config["Datastore"] = {
            "StorageMax": "100GB",  # Less storage than master
            "StorageGCWatermark": 90,
            "GCPeriod": "1h"  # More frequent GC
        }
        config["Routing"] = {
            "Type": "dhtclient"  # Lighter routing responsibilities
        }
        # Optimize for computational workloads
        config["Swarm"] = {
            "ConnMgr": {
                "LowWater": 100,
                "HighWater": 400,
                "GracePeriod": "20s"
            }
        }
        # Follow cluster rather than manage it
        config["ClusterFollow"] = {
            "MasterAddresses": ["/ip4/master-node-ip/tcp/9096"]
        }
        
    elif role == "leecher":
        # Leechers are optimized for minimal resource usage
        config["Datastore"] = {
            "StorageMax": "10GB",  # Minimal storage
            "StorageGCWatermark": 95,
            "GCPeriod": "30m"
        }
        config["Routing"] = {
            "Type": "dhtclient"
        }
        # Aggressive connection management for resource constrained devices
        config["Swarm"] = {
            "ConnMgr": {
                "LowWater": 20,
                "HighWater": 100,
                "GracePeriod": "10s"
            }
        }
        # Optimize for offline capability
        config["Offline"] = {
            "AllowOfflineExchange": True,
            "MaxOfflineQueue": 100
        }
    
    # Create and return configured node
    return ipfs_kit.initialize(role=role, config=config, resources=resources, metadata=metadata)
```

This architecture supports dynamic scaling with node roles changing based on available resources and network needs.

#### AI/ML Task Distribution Pattern

The master/worker/leecher architecture is particularly well-suited for distributed AI and machine learning workloads with IPFS as the content backbone:

```python
class IPFSDistributedTaskManager:
    """Manages distributed ML tasks across IPFS network using the master/worker model."""
    
    def __init__(self, role="master", cluster_id=None, worker_count=None):
        """Initialize task manager with role-specific behavior.
        
        Args:
            role: Role in the cluster ("master", "worker", or "leecher")
            cluster_id: Unique ID for this compute cluster
            worker_count: Expected number of workers (for master only)
        """
        self.role = role
        self.cluster_id = cluster_id or "default-cluster"
        self.task_queue = {} if role == "master" else None
        self.result_store = {} if role == "master" else None
        self.ipfs = ipfs_kit.initialize(role=role)
        
        # Set up pubsub topics for communication
        self.task_topic = f"/ipfs-ml/{self.cluster_id}/tasks"
        self.result_topic = f"/ipfs-ml/{self.cluster_id}/results"
        self.status_topic = f"/ipfs-ml/{self.cluster_id}/status"
        
        # Subscribe to relevant topics based on role
        if role == "master":
            self.ipfs.pubsub_subscribe(self.result_topic, self._handle_result)
            self.ipfs.pubsub_subscribe(self.status_topic, self._handle_status)
            self.worker_statuses = {}
            self.expected_workers = worker_count or 5
        elif role == "worker":
            self.ipfs.pubsub_subscribe(self.task_topic, self._handle_task)
            # Report status to master
            self._report_status("online")
        # Leechers only consume results, don't participate in computation
    
    def _report_status(self, status, metadata=None):
        """Report worker status to the master node."""
        if self.role != "worker":
            return
            
        status_msg = {
            "worker_id": self.ipfs.get_node_id(),
            "status": status,
            "timestamp": time.time(),
            "resources": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_free": psutil.disk_usage('/').free
            }
        }
        if metadata:
            status_msg["metadata"] = metadata
            
        self.ipfs.pubsub_publish(self.status_topic, json.dumps(status_msg))
    
    def _handle_status(self, msg):
        """Master handler for worker status updates."""
        if self.role != "master":
            return
            
        status = json.loads(msg["data"])
        worker_id = status["worker_id"]
        self.worker_statuses[worker_id] = status
        
        # Potentially reassign tasks based on worker status
        if status["status"] == "idle" and self.task_queue:
            next_task = next(iter(self.task_queue.values()))
            self._assign_task(worker_id, next_task)
    
    def submit_ml_task(self, task_type, data_cid, model_cid=None, params=None):
        """Submit a machine learning task to the cluster.
        
        Args:
            task_type: Type of ML task (embedding, training, inference, etc)
            data_cid: CID of the data to process
            model_cid: CID of the model to use (for inference/fine-tuning)
            params: Additional parameters for the task
        
        Returns:
            task_id: Unique identifier for tracking this task
        """
        if self.role != "master":
            raise ValueError("Only master nodes can submit tasks to the cluster")
            
        task_id = f"task-{uuid.uuid4()}"
        task = {
            "id": task_id,
            "type": task_type,
            "data_cid": data_cid,
            "model_cid": model_cid,
            "params": params or {},
            "status": "pending",
            "submitted_at": time.time()
        }
        
        # Store task in queue
        self.task_queue[task_id] = task
        
        # Find available worker or queue for later
        available_workers = [
            worker_id for worker_id, status in self.worker_statuses.items()
            if status["status"] == "idle" and 
            status["resources"]["cpu_percent"] < 80 and
            status["resources"]["memory_percent"] < 90
        ]
        
        if available_workers:
            worker_id = available_workers[0]  # Simple selection for example
            self._assign_task(worker_id, task)
        
        return task_id
    
    def _assign_task(self, worker_id, task):
        """Assign a specific task to a worker."""
        if self.role != "master":
            return
            
        task["status"] = "assigned"
        task["assigned_to"] = worker_id
        task["assigned_at"] = time.time()
        
        # Publish task to pubsub
        self.ipfs.pubsub_publish(self.task_topic, json.dumps(task))
        
        # Update worker status
        if worker_id in self.worker_statuses:
            self.worker_statuses[worker_id]["status"] = "busy"
    
    def _handle_task(self, msg):
        """Worker handler for incoming tasks."""
        if self.role != "worker":
            return
            
        self._report_status("busy")
        task = json.loads(msg["data"])
        
        # Check if task is for this worker
        if task.get("assigned_to") != self.ipfs.get_node_id():
            return
            
        # Process the task based on type
        try:
            task["status"] = "processing"
            result = self._process_ml_task(task)
            task["status"] = "completed"
            
            # Store result in IPFS
            result_cid = self.ipfs.add_json(result)
            
            # Send result reference back to master
            response = {
                "task_id": task["id"],
                "worker_id": self.ipfs.get_node_id(),
                "status": "success",
                "result_cid": result_cid,
                "completed_at": time.time()
            }
            
            self.ipfs.pubsub_publish(self.result_topic, json.dumps(response))
            
        except Exception as e:
            # Report failure
            response = {
                "task_id": task["id"],
                "worker_id": self.ipfs.get_node_id(),
                "status": "failed",
                "error": str(e),
                "completed_at": time.time()
            }
            self.ipfs.pubsub_publish(self.result_topic, json.dumps(response))
        
        # Update status to idle when done
        self._report_status("idle")
    
    def _process_ml_task(self, task):
        """Execute ML task based on its type."""
        task_type = task["type"]
        data_cid = task["data_cid"]
        
        # Get data from IPFS
        data = self.ipfs.get_json(data_cid)
        
        if task_type == "embedding":
            # Generate embeddings for text data
            return self._generate_embeddings(data, task["params"])
            
        elif task_type == "train":
            model_cid = task.get("model_cid")
            if model_cid:
                # Fine-tuning existing model
                model = self._load_model_from_ipfs(model_cid)
            else:
                # Training from scratch
                model = self._create_new_model(task["params"])
                
            return self._train_model(model, data, task["params"])
            
        elif task_type == "inference":
            model_cid = task["model_cid"]
            if not model_cid:
                raise ValueError("Model CID required for inference tasks")
                
            model = self._load_model_from_ipfs(model_cid)
            return self._run_inference(model, data, task["params"])
            
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    def _handle_result(self, msg):
        """Master handler for task results."""
        if self.role != "master":
            return
            
        result = json.loads(msg["data"])
        task_id = result["task_id"]
        
        # Update task status
        if task_id in self.task_queue:
            self.task_queue[task_id]["status"] = result["status"]
            
        # Store result reference
        self.result_store[task_id] = result
        
        # Mark worker as available
        worker_id = result["worker_id"]
        if worker_id in self.worker_statuses:
            self.worker_statuses[worker_id]["status"] = "idle"
            
        # Assign next task if available
        if self.task_queue:
            next_task_id = next((tid for tid, t in self.task_queue.items() 
                                 if t["status"] == "pending"), None)
            if next_task_id:
                self._assign_task(worker_id, self.task_queue[next_task_id])
                
    def get_task_result(self, task_id):
        """Retrieve result for a completed task."""
        if task_id not in self.result_store:
            return {"status": "unknown", "error": "Task not found"}
            
        result = self.result_store[task_id]
        
        # If result is stored in IPFS, retrieve it
        if result["status"] == "success" and "result_cid" in result:
            result_data = self.ipfs.get_json(result["result_cid"])
            return {"status": "success", "data": result_data}
            
        return result
```

This pattern demonstrates how the master/worker/leecher roles can be implemented in a practical distributed ML system using IPFS as the content backbone. It enables efficient distribution of computational workloads, with the master orchestrating tasks, workers processing individual content items, and leechers consuming the results.

#### Other Design Patterns
- **Facade pattern**: ipfs_kit provides unified interface to underlying components
- **Delegation**: Components handle specific responsibilities
- **Error aggregation**: Results dictionaries collect operation outcomes

### API Integration Points
- **IPFS HTTP API**: REST interface (localhost:5001/api/v0) for core IPFS operations
- **IPFS Cluster API**: REST interface (localhost:9094/api/v0) for cluster coordination
- **IPFS Cluster Proxy**: Proxied IPFS API (localhost:9095/api/v0)
- **IPFS Gateway**: Content retrieval via HTTP (localhost:8080/ipfs/[cid])
- **IPFS Socket Interface**: Unix socket for high-performance local communication (/ip4/127.0.0.1/tcp/4001)
- **IPFS Unix Socket API**: On Linux, Kubo can be configured to expose its API via a Unix domain socket instead of HTTP, providing lower-latency communication for local processes. This can be configured in the IPFS config file by modifying the `API.Addresses` field to include a Unix socket path (e.g., `/unix/path/to/socket`).

These APIs enable creating "swarms of swarms" by allowing distributed clusters to communicate across networks and coordinate content pinning, replication, and routing across organizational boundaries. Socket interfaces provide lower-latency communication for high-performance local operations, with Unix domain sockets being particularly efficient for inter-process communication on the same machine.

### Areas for Improvement
- **Code Structure**: Reduce duplication, improve cohesion, follow single responsibility principle
- **Error Handling**: Standardize approach, preserve stack traces, create error hierarchies
- **Documentation**: Add docstrings, type annotations, parameter validation
- **Testing**: Separate test code from implementation, increase unit test coverage
- **Code Quality**: Address redundant imports, string concatenation, security risks in subprocess calls
- **Code Duplication**: Use AST analysis to identify similar code patterns across modules
- **Refactoring**: Extract common patterns into reusable abstractions guided by AST similarity detection
- **Configuration Management**: Implement centralized configuration management instead of passing parameters
- **Subprocess Security**: Replace shell=True with more secure argument lists in subprocess calls
- **Multiaddress Handling**: Improve multiaddress parsing and validation with proper multiaddr library
- **Error Recovery**: Implement graceful degradation and recovery patterns for network failures
- **Logging**: Add structured logging with correlation IDs for tracing operations across components

## IPFS Core Concepts

The IPFS (InterPlanetary File System) architecture is built on several key concepts and components that are essential to understand for effective implementation:

### Content Addressing
- **Content Identifiers (CIDs)**: Unique fingerprints of content based on cryptographic hashes
- **Multihash Format**: Extensible hashing format supporting multiple hash algorithms (default: SHA-256)
- **Base32/Base58 Encoding**: Human-readable representations of binary CIDs
- **Version Prefixes**: CIDv0 (base58btc-encoded SHA-256) vs CIDv1 (self-describing, supports multicodec)

### Data Structures
- **Merkle DAG (Directed Acyclic Graph)**: Core data structure for content-addressed storage
- **IPLD (InterPlanetary Linked Data)**: Framework for creating data models with content-addressable linking
- **UnixFS**: File system abstraction built on IPLD for representing traditional files/directories
- **Blocks**: Raw data chunks that form the atomic units of the Merkle DAG

### Network Components
- **DHT (Distributed Hash Table)**: Distributed key-value store for content routing
- **Bitswap**: Protocol for exchanging blocks between peers
- **libp2p**: Modular networking stack powering IPFS peer-to-peer communication
- **MultiFormats**: Self-describing protocols, formats, and addressing schemes
- **IPNS (InterPlanetary Name System)**: Mutable naming system for content addressing

### Node Types
- **Full Nodes**: Store and serve content, participate in DHT
- **Gateway Nodes**: Provide HTTP access to IPFS content
- **Client Nodes**: Lightweight nodes that rely on others for content routing/storage
- **Bootstrap Nodes**: Well-known nodes that help new nodes join the network
- **Relay Nodes**: Assist with NAT traversal and indirect connections

### Key Operations
- **Adding Content**: Hash-based deduplication and chunking strategies
- **Retrieving Content**: Resolution process from CID to data
- **Pinning**: Mechanism to prevent content from being garbage collected
- **Publishing**: Making content discoverable through DHT/IPNS
- **Garbage Collection**: Process for reclaiming storage from unpinned content

These concepts are documented thoroughly in `/docs/ipfs-docs/docs/concepts/` and implementation details can be found in the reference documentation.

## Development Roadmap

### Phase 1: Core Infrastructure and Tiered Storage (Q1-Q2 2025)

#### 1.1 Refactor Core Components (Months 1-2)
- Standardize error handling and parameter validation across all modules
- Implement proper multiaddress parsing/handling with the multiaddr library
- Replace shell=True subprocess calls with more secure argument lists
- Add structured logging with correlation IDs for end-to-end operation tracing
- Develop comprehensive test suite with mocking of IPFS daemon interactions

#### 1.2 FSSpec Integration Layer (Months 2-3)
- Implement fsspec filesystem interface for unified access to all storage backends
- Add Unix socket support for high-performance local communication
- Create cached/buffered file-like objects for IPFS content
- Implement efficient cursor operations for large file streaming
- Add upload/download progress tracking and resumability

#### 1.3 Tiered Storage with Adaptive Replacement Cache (Months 3-5)
- Develop adaptive replacement cache (ARC) with data "heat" tracking
- Implement configurable eviction policies based on access patterns
- Create hierarchical storage management system prioritizing:
  1. Local memory cache (fastest, very limited capacity)
  2. Local disk cache (fast, limited capacity)
  3. IPFS node cache (fast, larger capacity)
  4. IPFS cluster (distributed redundancy)
  5. S3 storage (reliable, moderate cost)
  6. Storacha (durable, potentially higher latency)
  7. Filecoin (highest durability, lowest cost, highest latency)
- Add performance metrics collection and bandwidth optimization
- Implement automatic tier migration based on usage patterns

#### 1.4 Direct P2P Communication Layer (Months 5-6)
- Implement libp2p_py for direct peer connections to share IPFS CIDs
- Develop NAT traversal and peer discovery mechanisms
- Create secure authentication for cluster nodes
- Implement resource-aware content routing algorithms
- Add bandwidth throttling and prioritization for network efficiency

### Phase 2: High-Performance Data Management (Q3-Q4 2025)

#### 2.1 Arrow-based Metadata Index (Months 7-8)
- Create Apache Arrow-based routing index for metadata
- Implement Parquet-based persistence for durability
- Design columnar structure for efficient queries and filtering
- Use memory-mapped files for near-instant startup
- Implement delta updates to minimize write amplification
- Create efficient partitioning for parallel processing
- Design distributed index synchronization protocols

#### 2.2 Role-based Architecture Enhancement (Months 9-10)
- Implement full master/worker/leecher role-specific optimizations
- Develop dynamic role switching based on available resources
- Create cluster management dashboard for monitoring node states
- Implement workload balancing algorithms
- Design failure detection and recovery procedures
- Add secure credential management for role-based access control

#### 2.3 Distributed Processing Framework (Months 10-12)
- Implement distributed compute tasks over content (MapReduce pattern)
- Create IPFS-native task queue and result aggregation
- Develop progress monitoring and fault tolerance
- Implement work stealing for load balancing
- Add resource-aware task scheduling
- Design data locality optimization for compute tasks

### Phase 3: Knowledge Management and AI Integration (Q1-Q2 2026)

#### 3.1 IPLD Knowledge Graph Foundation (Months 13-14)
- Develop IPLD schemas for knowledge representation
- Design entity-relationship model with CID-based identifiers
- Implement basic graph operations (traversal, filtering, aggregation)
- Create indexing strategies for efficient graph queries
- Develop versioning and change tracking for graph data

#### 3.2 Vector Storage and Similarity Search (Months 15-16)
- Store embedding vectors in IPLD structures
- Implement vector quantization for storage efficiency
- Design hierarchical navigable small world (HNSW) indexes in IPLD
- Create memory-mapped vector indexes for fast similarity search
- Implement approximate nearest neighbor search algorithms
- Optimize for hardware acceleration (SIMD instructions)

#### 3.3 GraphRAG Integration (Months 17-18)
- Develop hybrid search combining vector and graph traversal
- Implement context-aware retrieval strategies
- Create relevance scoring algorithms combining:
  - Semantic similarity via embedding vectors
  - Graph relationship proximity
  - Content freshness and authority
  - Access patterns and popularity
- Design query planning and optimization for complex searches
- Implement result reranking and diversification strategies

### Phase 4: Integration and Ecosystem Development (Q3-Q4 2026)

#### 4.1 External Systems Integration (Months 19-20)
- Develop Langchain/LlamaIndex integration for LLM workflows
- Create Pandas/Dask connectors for data science pipelines
- Implement HuggingFace integration for model handling
- Design PyTorch/TensorFlow data loaders for ML training
- Create streamlined dataset management for AI workflows

#### 4.2 Performance Optimization and Scaling (Months 21-22)
- Conduct comprehensive performance profiling
- Implement critical path optimization
- Create specialized kernels for high-frequency operations
- Design sharding strategies for extremely large datasets
- Implement adaptive resource utilization
- Develop horizontal and vertical scaling capabilities

#### 4.3 High-Level API and Developer Tools (Months 23-24)
- Create simplified high-level API for common operations
- Design declarative configuration system
- Implement integrated monitoring and debugging tools
- Develop comprehensive documentation and tutorials
- Create example applications and templates
- Design plugin architecture for extensibility

## Technical Implementation Plan

### New Dependencies
```
fsspec>=2023.3.0
pyarrow>=12.0.0
pyarrow-plasma>=12.0.0  # For Arrow C Data Interface via Plasma store
lru-dict>=1.2.0
cachetools>=5.3.0
filecoin-api-client>=0.9.0
multiaddr>=0.0.9
base58>=2.1.1
eth-account>=0.8.0
web3>=6.5.0
fastapi>=0.100.0  # For API server
uvicorn>=0.22.0   # ASGI server for FastAPI
pydantic>=2.0.0   # For data validation
faiss-cpu>=1.7.4  # For vector search
networkx>=3.0     # For knowledge graph operations
# multiprocessing is a standard library module (no version needed)
concurrent.futures  # For parallel processing with thread and process pools
mmap-backed-array>=0.7.0  # For shared memory arrays
astroid>=2.15.0   # For AST generation and code analysis
pylint>=2.17.0    # For code quality checks with AST support
libp2p-py>=0.2.0  # For direct peer-to-peer connections
```

### New Classes and Components

The following classes will be implemented according to the development roadmap:

#### Phase 1: Core Infrastructure and Storage

##### IPFSFileSystem (FSSpec Integration)
```python
class IPFSFileSystem(AbstractFileSystem):
    """FSSpec-compatible filesystem interface with tiered caching."""
    
    def __init__(self, 
                 ipfs_path=None, 
                 socket_path=None, 
                 role="leecher", 
                 cache_config=None, 
                 use_mmap=True,
                 **kwargs):
        """Initialize a high-performance IPFS filesystem interface.
        
        Args:
            ipfs_path: Path to IPFS config directory
            socket_path: Path to Unix socket (for high-performance on Linux)
            role: Node role ("master", "worker", "leecher")
            cache_config: Configuration for the tiered cache system
            use_mmap: Whether to use memory-mapped files for large content
        """
        super().__init__(**kwargs)
        self.ipfs_path = ipfs_path or os.environ.get("IPFS_PATH", "~/.ipfs")
        self.socket_path = socket_path
        self.role = role
        self.use_mmap = use_mmap
        
        # Initialize connection to IPFS
        self._setup_ipfs_connection()
        
        # Initialize tiered cache system
        self.cache = TieredCacheManager(config=cache_config)
     
    def _setup_ipfs_connection(self):
        """Set up the appropriate IPFS connection based on available interfaces."""
        # Prefer Unix socket on Linux for performance
        if self.socket_path and os.path.exists(self.socket_path):
            # Use consistent socket path format throughout the codebase
            self.api_base = f"http://unix:{self.socket_path}:/api/v0"
            self.session = requests.Session()
            self.session.mount("http://unix:", requests_unixsocket.UnixAdapter())
        else:
            # Fall back to HTTP API
            self.api_base = "http://127.0.0.1:5001/api/v0"
            self.session = requests.Session()
        
    def _open(self, path, mode="rb", **kwargs):
        """Open an IPFS object as a file-like object."""
        if mode not in ["rb", "r"]:
            raise NotImplementedError("Only read modes supported")
            
        # Convert path to CID if necessary
        cid = self._resolve_path(path)
        
        # Check cache layers
        content = self.cache.get(cid)
        if content is not None:
            return self._create_file_object(path, content, mode)
        
        # Fetch from IPFS through fastest available interface
        content = self._fetch_from_ipfs(cid)
        
        # Cache content for future access
        self.cache.put(cid, content, metadata={"size": len(content), "path": path})
        
        return self._create_file_object(path, content, mode)
    
    def _create_file_object(self, path, content, mode):
        """Create the appropriate file-like object based on content size."""
        if self.use_mmap and len(content) > 10 * 1024 * 1024:  # >10MB
            return IPFSMemoryMappedFile(self, path, content, mode)
        else:
            return IPFSMemoryFile(self, path, content, mode)
            
    # Other FSSpec interface methods
    def ls(self, path, detail=True, **kwargs): pass
    def find(self, path, maxdepth=None, **kwargs): pass
    def glob(self, path, **kwargs): pass
    def info(self, path, **kwargs): pass
    def copy(self, path1, path2, **kwargs): pass
    def cat(self, path, **kwargs): pass
    def get(self, path, local_path, **kwargs): pass
    def put(self, local_path, path, **kwargs): pass
    def exists(self, path, **kwargs): pass
    def isdir(self, path): pass
    def isfile(self, path): pass
    def walk(self, path, maxdepth=None, **kwargs): pass
    def rm(self, path, recursive=False, **kwargs): pass
    def mkdir(self, path, create_parents=True, **kwargs): pass

    # Added methods for IPFS-specific operations
    def pin(self, path): pass
    def unpin(self, path): pass
    def get_pins(self): pass
    def publish_to_ipns(self, path, key=None): pass
    def resolve_ipns(self, name): pass
```

##### TieredCacheManager
```python
class TieredCacheManager:
    """Manages hierarchical caching with Adaptive Replacement policy."""
    
    def __init__(self, config=None):
        """Initialize the tiered cache system.
        
        Args:
            config: Configuration dictionary for cache tiers
                {
                    'memory_cache_size': 100MB,
                    'local_cache_size': 1GB,
                    'local_cache_path': '/path/to/cache',
                    'max_item_size': 50MB,
                    'min_access_count': 2
                }
        """
        self.config = config or {
            'memory_cache_size': 100 * 1024 * 1024,  # 100MB
            'local_cache_size': 1 * 1024 * 1024 * 1024,  # 1GB
            'local_cache_path': os.path.expanduser('~/.ipfs_cache'),
            'max_item_size': 50 * 1024 * 1024,  # 50MB
            'min_access_count': 2
        }
        
        # Initialize cache tiers
        self.memory_cache = ARCache(maxsize=self.config['memory_cache_size'])
        self.disk_cache = DiskCache(
            directory=self.config['local_cache_path'],
            size_limit=self.config['local_cache_size']
        )
        
        # Access statistics for heat scoring
        self.access_stats = {}
        
    def get(self, key):
        """Get content from the fastest available cache tier."""
        # Try memory cache first (fastest)
        content = self.memory_cache.get(key)
        if content is not None:
            self._update_stats(key, 'memory_hit')
            return content
            
        # Try disk cache next
        content = self.disk_cache.get(key)
        if content is not None:
            # Promote to memory cache if it fits
            if len(content) <= self.config['max_item_size']:
                self.memory_cache.put(key, content)
            self._update_stats(key, 'disk_hit')
            return content
            
        # Cache miss
        self._update_stats(key, 'miss')
        return None
        
    def put(self, key, content, metadata=None):
        """Store content in appropriate cache tiers."""
        size = len(content)
        
        # Update metadata
        if metadata is None:
            metadata = {}
        metadata.update({
            'size': size,
            'added_time': time.time(),
            'last_access': time.time(),
            'access_count': 1
        })
        
        # Store in memory cache if size appropriate
        if size <= self.config['max_item_size']:
            self.memory_cache.put(key, content)
            
        # Store in disk cache
        self.disk_cache.put(key, content, metadata)
        
    def _update_stats(self, key, access_type):
        """Update access statistics for content item."""
        if key not in self.access_stats:
            self.access_stats[key] = {
                'access_count': 0,
                'first_access': time.time(),
                'last_access': time.time(),
                'tier_hits': {'memory': 0, 'disk': 0, 'miss': 0}
            }
            
        stats = self.access_stats[key]
        stats['access_count'] += 1
        stats['last_access'] = time.time()
        
        if access_type == 'memory_hit':
            stats['tier_hits']['memory'] += 1
        elif access_type == 'disk_hit':
            stats['tier_hits']['disk'] += 1
        else:
            stats['tier_hits']['miss'] += 1
            
        # Recalculate heat score
        age = stats['last_access'] - stats['first_access']
        frequency = stats['access_count']
        recency = 1.0 / (1.0 + (time.time() - stats['last_access']) / 3600)  # Decay by hour
        
        # Heat formula: combination of frequency and recency
        stats['heat_score'] = frequency * recency * (1 + math.log(1 + age / 86400))  # Age boost in days
        
    def evict(self, target_size=None):
        """Intelligent eviction based on heat scores and tier."""
        if target_size is None:
            # Default to 10% of memory cache
            target_size = self.config['memory_cache_size'] / 10
            
        # Find coldest items for eviction
        items = sorted(
            self.access_stats.items(),
            key=lambda x: x[1]['heat_score']
        )
        
        freed = 0
        for key, stats in items:
            if freed >= target_size:
                break
                
            # Check if in memory and evict
            if self.memory_cache.contains(key):
                size = stats.get('size', 0)
                self.memory_cache.evict(key)
                freed += size
                
        return freed
```

##### IPFSLibp2pPeer
```python
class IPFSLibp2pPeer:
    """Direct peer-to-peer connection interface for IPFS content exchange.
    
    Implementation based on patterns described in:
    - /docs/libp2p_docs/content/concepts/fundamentals/peers.md 
    - /docs/libp2p_docs/content/guides/getting-started/
    """
    
    def __init__(self, 
                 host_id=None, 
                 bootstrap_peers=None, 
                 listen_addrs=None, 
                 role="leecher"):
        """Initialize a libp2p peer for direct IPFS content exchange.
        See /docs/libp2p_docs/content/concepts/fundamentals/protocols.md for protocol negotiation details.
        
        Args:
            host_id: Optional peer identity (keypair)
            bootstrap_peers: List of peers to connect to initially
            listen_addrs: Network addresses to listen on
            role: This node's role in the cluster
        """
        self.role = role
        self.host = None
        self.dht = None
        self.pubsub = None
        self.protocols = {}
        
        # Default listen addresses if none provided
        if listen_addrs is None:
            listen_addrs = [
                "/ip4/0.0.0.0/tcp/0",
                "/ip4/0.0.0.0/udp/0/quic"
            ]
        self.listen_addrs = listen_addrs
        
        # Initialize the libp2p host
        self._init_host(host_id)
        
        # Connect to bootstrap peers
        if bootstrap_peers:
            for peer in bootstrap_peers:
                self.connect_peer(peer)
                
        # Set up default protocols based on role
        self._setup_role_protocols()
        
    def _init_host(self, host_id=None):
        """Initialize the libp2p host with appropriate options."""
        # Create or load host identity
        if host_id:
            self.identity = host_id
        else:
            # Generate or load from config directory
            self.identity = self._load_or_create_identity()
            
        # Create libp2p host
        self.host = libp2p_host.new_host(
            identity=self.identity,
            listen_addrs=self.listen_addrs,
            transport_options={
                "tcp": {"socket_backlog": 128},
                "quic": {"max_streams": 1000}
            },
            muxer_options={
                "mplex": {"max_streams": 1000}
            },
            security_options={
                "noise": {"static_key": True}
            }
        )
        
        # Initialize DHT for content routing
        self.dht = libp2p_dht.new_dht(
            host=self.host,
            validator=libp2p_dht.DefaultValidator(),
            mode="server" if self.role == "master" else "client"
        )
        
        # Initialize pubsub for messaging
        self.pubsub = libp2p_pubsub.new_pubsub(
            host=self.host,
            router_type="gossipsub",
            signing_key=self.identity.private_key,
            strict_signing=True
        )
        
    def connect_peer(self, peer_info):
        """Connect to a remote peer."""
        if isinstance(peer_info, str):
            # Parse multiaddr
            addr = multiaddr.Multiaddr(peer_info)
            peer_id = addr.value_for_protocol('p2p')
            peer_info = {'id': peer_id, 'addrs': [addr]}
            
        try:
            self.host.connect(peer_info)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer_info}: {e}")
            return False
            
    def request_content(self, cid, timeout=60):
        """Request content directly from connected peers."""
        # Create a protocol-specific request
        content_request = {
            "cid": cid,
            "requester": self.host.get_id().pretty(),
            "timestamp": time.time(),
            "request_id": str(uuid.uuid4())
        }
        
        # Send request to all connected peers via bitswap protocol
        responses = []
        futures = []
        
        for peer_id in self.host.get_peer_store().peers():
            future = asyncio.ensure_future(
                self.host.new_stream(
                    peer_id=peer_id,
                    protocol_id="/ipfs/bitswap/1.2.0"
                )
            )
            futures.append((peer_id, future))
            
        # Wait for responses with timeout
        async def collect_responses():
            for peer_id, future in futures:
                try:
                    stream = await asyncio.wait_for(future, timeout=10)
                    await stream.write(json.dumps(content_request).encode())
                    
                    response_data = await stream.read(10 * 1024 * 1024)  # 10MB max
                    if response_data:
                        responses.append((peer_id, response_data))
                        # Return early if we got the content
                        return True
                except Exception as e:
                    logger.debug(f"Error requesting from {peer_id}: {e}")
                finally:
                    if 'stream' in locals():
                        await stream.close()
            return False
            
        # Run collection with timeout
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(
            asyncio.wait_for(collect_responses(), timeout=timeout)
        )
        
        if responses:
            # Return the first successful response
            return responses[0][1]
        else:
            raise ContentNotFoundError(f"Content with CID {cid} not found among connected peers")
            
    def announce_content(self, cid, metadata=None):
        """Announce available content to the network."""
        if metadata is None:
            metadata = {}
            
        announcement = {
            "provider": self.host.get_id().pretty(),
            "cid": cid,
            "timestamp": time.time(),
            "size": metadata.get("size", 0),
            "type": metadata.get("type", "unknown")
        }
        
        # Provide to DHT
        self.dht.provide(cid)
        
        # Announce via pubsub
        self.pubsub.publish(
            topic=f"/ipfs/announce/{cid[:8]}",
            data=json.dumps(announcement).encode()
        )
        
    def start_discovery(self, rendezvous_string="ipfs-discovery"):
        """Start peer discovery mechanisms."""
        # Set up mDNS discovery
        mdns = libp2p_mdns.NewMdnsService(
            host=self.host,
            interval=60,
            service_tag=rendezvous_string
        )
        mdns.start()
        
        # Set up DHT-based discovery for WAN
        self.dht.bootstrap(bootstrap_peers)
        
        # Set up random-walk discovery
        if self.role != "leecher":  # Preserve resources on leechers
            random_walk = libp2p_discovery.RandomWalk(
                host=self.host,
                dht=self.dht,
                interval=300,  # 5 minutes
                queries_per_period=3
            )
            random_walk.Start()
            
        return mdns
```

#### Phase 2: High-Performance Data Management

##### IPFSArrowIndex
```python
class IPFSArrowIndex:
    """High-performance Arrow-based metadata index for IPFS content."""
    
    def __init__(self, 
                 base_path="~/.ipfs_index", 
                 role="master",
                 schema=None,
                 partition_size=1000000,
                 sync_interval=300):
        """Initialize the Arrow-based IPFS content index.
        
        Args:
            base_path: Directory to store index files
            role: Node role affecting index behavior
            schema: Custom schema if default is not sufficient
            partition_size: Max records per partition file
            sync_interval: How often to sync with peers (seconds)
        """
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        self.base_path = os.path.expanduser(base_path)
        os.makedirs(self.base_path, exist_ok=True)
        
        self.role = role
        self.partition_size = partition_size
        self.sync_interval = sync_interval
        
        # Set up schema
        self.schema = schema or self._create_default_schema()
        
        # Initialize partitions
        self.partitions = self._discover_partitions()
        self.current_partition_id = max(self.partitions.keys()) if self.partitions else 0
        
        # Memory-mapped access to partition files
        self.mmap_files = {}
        
        # In-memory record batch for fast writes
        self.record_batch = None
        
        # Load current partition
        self._load_current_partition()
        
        # Set up sync if master or worker
        if role in ("master", "worker"):
            self._schedule_sync()
    
    def _create_default_schema(self):
        """Create the default Arrow schema for IPFS metadata."""
        return pa.schema([
            # Content identifiers
            pa.field('cid', pa.string()),
            pa.field('cid_version', pa.int8()),
            pa.field('multihash_type', pa.string()),
            
            # Basic metadata
            pa.field('size_bytes', pa.int64()),
            pa.field('blocks', pa.int32()),
            pa.field('links', pa.int32()),
            pa.field('mime_type', pa.string()),
            
            # Storage status
            pa.field('local', pa.bool_()),
            pa.field('pinned', pa.bool_()),
            pa.field('pin_types', pa.list_(pa.string())),
            pa.field('replication', pa.int16()),
            
            # Temporal metadata
            pa.field('created_at', pa.timestamp('ms')),
            pa.field('last_accessed', pa.timestamp('ms')),
            pa.field('access_count', pa.int32()),
            
            # Content organization
            pa.field('path', pa.string()),
            pa.field('filename', pa.string()),
            pa.field('extension', pa.string()),
            
            # Custom metadata
            pa.field('tags', pa.list_(pa.string())),
            pa.field('metadata', pa.struct([
                pa.field('title', pa.string()),
                pa.field('description', pa.string()),
                pa.field('creator', pa.string()),
                pa.field('source', pa.string()),
                pa.field('license', pa.string())
            ])),
            
            # Extended properties as key-value pairs
            pa.field('properties', pa.map_(pa.string(), pa.string()))
        ])
    
    def _discover_partitions(self):
        """Scan the index directory to discover all partition files."""
        partitions = {}
        for filename in os.listdir(self.base_path):
            if not filename.startswith('ipfs_index_') or not filename.endswith('.parquet'):
                continue
                
            try:
                # Extract partition ID from filename
                partition_id = int(filename.split('_')[2].split('.')[0])
                partition_path = os.path.join(self.base_path, filename)
                
                # Get metadata without loading full content
                file_stats = os.stat(partition_path)
                
                partitions[partition_id] = {
                    'path': partition_path,
                    'size': file_stats.st_size,
                    'mtime': file_stats.st_mtime,
                    'rows': None  # Lazy-loaded
                }
                
            except Exception as e:
                logger.warning(f"Invalid partition file {filename}: {e}")
                
        return partitions
    
    def _load_current_partition(self):
        """Load the current partition into memory for fast access/writes."""
        if self.current_partition_id in self.partitions:
            partition_path = self.partitions[self.current_partition_id]['path']
            
            if os.path.exists(partition_path):
                # Read using memory mapping for performance
                table = pq.read_table(partition_path, memory_map=True)
                
                # Extract as record batch for efficient updates
                if table.num_rows > 0:
                    self.record_batch = table.to_batches()[0]
                else:
                    self.record_batch = None
                    
                # Keep reference to memory mapping
                file_obj = open(partition_path, 'rb')
                mmap_obj = mmap.mmap(file_obj.fileno(), 0, access=mmap.ACCESS_READ)
                self.mmap_files[partition_path] = (file_obj, mmap_obj)
                
                # Update partition metadata
                self.partitions[self.current_partition_id]['rows'] = table.num_rows
            else:
                self.record_batch = None
        else:
            self.record_batch = None
    
    def add(self, record):
        """Add a new record to the index."""
        # Convert to Arrow arrays
        arrays = []
        for field in self.schema:
            field_name = field.name
            if field_name in record:
                arrays.append(pa.array([record[field_name]], type=field.type))
            else:
                arrays.append(pa.array([None], type=field.type))
                
        # Create a new record batch with just this record
        new_batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
        
        # Add to existing batch or create new one
        if self.record_batch is None:
            self.record_batch = new_batch
        else:
            self.record_batch = pa.concat_batches([self.record_batch, new_batch])
            
        # Check if we need to write and create a new partition
        if self.record_batch.num_rows >= self.partition_size:
            self._write_current_batch()
            self.current_partition_id += 1
            self.record_batch = None
            
        return True
    
    def _write_current_batch(self):
        """Write the current record batch to a parquet file."""
        if self.record_batch is None or self.record_batch.num_rows == 0:
            return False
            
        # Convert batch to table
        table = pa.Table.from_batches([self.record_batch])
        
        # Write with compression
        pq.write_table(
            table, 
            self._get_partition_path(self.current_partition_id),
            compression='zstd',
            compression_level=5,
            use_dictionary=True,
            write_statistics=True
        )
        
        # Update partitions metadata
        self.partitions[self.current_partition_id] = {
            'path': partition_path,
            'size': os.path.getsize(partition_path),
            'mtime': os.path.getmtime(partition_path),
            'rows': table.num_rows
        }
        
        return True
    
    def query(self, filters=None, columns=None, limit=None):
        """Query the index using predicates."""
        # Create dataset from all partitions
        ds = dataset(self.base_path, format="parquet")
        
        # Build filter expression
        filter_expr = None
        if filters:
            for field, op, value in filters:
                field_expr = ds.field(field)
                
                if op == "==":
                    expr = field_expr == value
                elif op == "!=":
                    expr = field_expr != value
                elif op == ">":
                    expr = field_expr > value
                elif op == ">=":
                    expr = field_expr >= value
                elif op == "<":
                    expr = field_expr < value
                elif op == "<=":
                    expr = field_expr <= value
                elif op == "in":
                    expr = field_expr.isin(value)
                else:
                    raise ValueError(f"Unsupported operator: {op}")
                    
                if filter_expr is None:
                    filter_expr = expr
                else:
                    filter_expr = filter_expr & expr
        
        # Execute query
        table = ds.to_table(
            filter=filter_expr,
            columns=columns
        )
        
        # Apply limit if specified
        if limit and limit < table.num_rows:
            table = table.slice(0, limit)
            
        return table
        
    def get_by_cid(self, cid):
        """Fast lookup by CID."""
        result = self.query(filters=[("cid", "==", cid)])
        if result.num_rows == 0:
            return None
        
        # Convert first row to Python dict
        return {col: result[col][0].as_py() for col in result.column_names}
        
    def update_stats(self, cid, access_type="read"):
        """Update access statistics for a CID."""
        record = self.get_by_cid(cid)
        if record:
            # Update access time and count
            now = int(time.time() * 1000)  # ms timestamp
            record["last_accessed"] = now
            record["access_count"] = record["access_count"] + 1 if "access_count" in record else 1
            
            # Update heat score based on recency and frequency
            decay_factor = 0.5  # Half life in days
            days_since_added = (now - record["added_timestamp"]) / (1000 * 3600 * 24)
            time_factor = 2 ** (-days_since_added * decay_factor)
            record["heat_score"] = record["access_count"] * time_factor
            
            # Remove existing record and add updated one
            self.delete_by_cid(cid)
            self.add(record)
            
            return True
        return False
        
    def delete_by_cid(self, cid):
        """Remove a record by CID."""
        # This implementation is inefficient for parquet
        # A real implementation would mark as deleted and compact later
        result = self.query(filters=[("cid", "!=", cid)])
        
        # Clear all partitions
        for partition_id in list(self.partitions.keys()):
            path = self.partitions[partition_id]['path']
            if os.path.exists(path):
                # Close any open memory maps
                if path in self.mmap_files:
                    file_obj, mmap_obj = self.mmap_files[path]
                    mmap_obj.close()
                    file_obj.close()
                    del self.mmap_files[path]
                
                os.remove(path)
                del self.partitions[partition_id]
                
        # Reset state
        self.current_partition_id = 0
        self.record_batch = None
        
        # Write new data if we have any records
        if result.num_rows > 0:
            self.record_batch = result.to_batches()[0]
            self._write_current_batch()
            
        return True
        
    def sync_with_peer(self, peer_url):
        """Synchronize index with another peer."""
        if self.role == "leecher":
            # Leechers don't participate in index distribution
            return False
            
        try:
            # Get peer's partition list
            response = requests.get(f"{peer_url}/api/v0/index/partitions")
            peer_partitions = response.json()
            
            # Download missing or outdated partitions
            for partition_id, metadata in peer_partitions.items():
                partition_id = int(partition_id)
                
                # Skip if we have a newer version
                if (partition_id in self.partitions and 
                    self.partitions[partition_id]['mtime'] >= metadata['mtime']):
                    continue
                    
                # Download partition
                response = requests.get(
                    f"{peer_url}/api/v0/index/partition/{partition_id}",
                    stream=True
                )
                
                # Save to temporary file first
                temp_path = os.path.join(self.base_path, f"temp_{uuid.uuid4()}.parquet")
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                # Validate Arrow file
                try:
                    pq.read_metadata(temp_path)
                    
                    # Move to final location
                    final_path = os.path.join(
                        self.base_path, 
                        f"ipfs_index_{partition_id:06d}.parquet"
                    )
                    
                    shutil.move(temp_path, final_path)
                    
                    # Update partitions metadata
                    self.partitions[partition_id] = {
                        'path': final_path,
                        'size': os.path.getsize(final_path),
                        'mtime': os.path.getmtime(final_path),
                        'rows': metadata['rows']
                    }
                    
                except Exception as e:
                    os.remove(temp_path)
                    logger.error(f"Invalid partition from peer: {e}")
                    
            # Update current partition ID if needed
            if self.partitions:
                self.current_partition_id = max(self.partitions.keys())
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync with peer {peer_url}: {e}")
            return False
            
    def _schedule_sync(self):
        """Schedule periodic synchronization with peers."""
        if self.role in ("master", "worker"):
            # Get list of peers to sync with
            peers = self._get_peer_list()
            
            # Schedule sync tasks
            for peer in peers:
                threading.Timer(
                    self.sync_interval,
                    self.sync_with_peer,
                    args=[peer]
                ).start()
```

#### Phase 3: Knowledge Management and AI Integration

##### IPLDGraphDB
```python
class IPLDGraphDB:
    """IPLD-based knowledge graph database with vector capabilities."""
    
    def __init__(self, ipfs_client, base_path="~/.ipfs_graph"):
        """Initialize the IPLD-based graph database.
        
        Args:
            ipfs_client: IPFS client instance
            base_path: Local storage for graph indexes
        """
               self.ipfs = ipfs_client
        self.base_path = os.path.expanduser(base_path)
        os.makedirs(self.base_path, exist_ok=True)
        
        # Root CID contains graph structure pointers
        self.root_cid = self._load_or_create_root()
        
        # In-memory indexes for fast access
        self._load_indexes()
        
    def _load_or_create_root(self):
        """Load existing graph root or create a new one."""
        root_path = os.path.join(self.base_path, "root.json")
        
        if os.path.exists(root_path):
            with open(root_path) as f:
                root_data = json.load(f)
                return root_data.get("root_cid")
        
        # Create new empty graph root
        root = {
            "schema_version": "1.0",
            "created_at": time.time(),
            "updated_at": time.time(),
            "entity_count": 0,
            "relationship_count": 0,
            "entities_index_cid": None,
            "relationships_index_cid": None,
            "vector_index_cid": None
        }
        
        # Store in IPFS
        root_cid = self.ipfs.dag_put(root)
        
        # Save locally
        with open(root_path, 'w') as f:
            json.dump({"root_cid": new_root_cid}, f)
            
        return root_cid
        
    def _load_indexes(self):
        """Load in-memory indexes for fast access."""
        # Load root object from IPFS
        root = self.ipfs.dag_get(self.root_cid)
        
        # Initialize in-memory indexes
        self.entities = {}
        self.relationships = {}
        self.vectors = {}
        
        # Load entities if exists
        if root.get("entities_index_cid"):
            entities_index = self.ipfs.dag_get(root["entities_index_cid"])
            for entity_id, entity_cid in entities_index.items():
                # Lazy load actual entity data
                self.entities[entity_id] = {"cid": entity_cid, "data": None}
                
        # Load relationships if exists
        if root.get("relationships_index_cid"):
            relationships_index = self.ipfs.dag_get(root["relationships_index_cid"])
            self.relationships = relationships_index
            
        # Load vector index if exists
        if root.get("vector_index_cid"):
            # Load only metadata, not the full vectors
            vector_index = self.ipfs.dag_get(root["vector_index_cid"])
            self.vectors = {
                "metadata": vector_index["metadata"],
                "index_type": vector_index["index_type"],
                "dimension": vector_index["dimension"],
                "count": vector_index["count"],
                "entities": vector_index["entity_map"]
            }
            
    def add_entity(self, entity_id, properties, vector=None):
        """Add an entity to the graph.
        
        Args:
            entity_id: Unique identifier for the entity
            properties: Dict of entity properties
            vector: Optional embedding vector for similarity search
        """
        # Create entity object
        entity = {
            "id": entity_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "properties": properties,
            "relationships": [],
            "vector": vector.tolist() if vector is not None else None
        }
        
        # Store in IPFS
        entity_cid = self.ipfs.dag_put(entity)
        
        # Update in-memory index
        self.entities[entity_id] = {"cid": entity_cid, "data": entity}
        
        # Update vector index if vector provided
        if vector is not None:
            if "vectors" not in self.vectors:
                self.vectors["vectors"] = []
                self.vectors["entity_map"] = {}
                self.vectors["dimension"] = len(vector)
                self.vectors["count"] = 0
                self.vectors["index_type"] = "flat"  # Simple implementation
                
            vector_idx = self.vectors["count"]
            self.vectors["vectors"].append(vector.tolist())
            self.vectors["entity_map"][vector_idx] = entity_id
            self.vectors["count"] += 1
            
        # Schedule index persistence
        self._schedule_persist()
        
        return entity_id

    def add_relationship(self, from_entity, to_entity, relationship_type, properties=None):
        """Add a relationship between entities."""
        if from_entity not in self.entities or to_entity not in self.entities:
            raise ValueError("Both entities must exist")
            
        # Create relationship object
        relationship = {
            "from": from_entity,
            "to": to_entity,
            "type": relationship_type,
            "created_at": time.time(),
            "properties": properties or {}
        }
        
        # Store in IPFS
        relationship_cid = self.ipfs.dag_put(relationship)
        
        # Update in-memory indexes
        relationship_id = f"{from_entity}:{relationship_type}:{to_entity}"
        
        if "relationship_cids" not in self.relationships:
            self.relationships["relationship_cids"] = {}
            self.relationships["entity_rels"] = {}
            
        self.relationships["relationship_cids"][relationship_id] = relationship_cid
        
        # Update entity relationship lists
        if from_entity not in self.relationships["entity_rels"]:
            self.relationships["entity_rels"][from_entity] = []
        self.relationships["entity_rels"][from_entity].append(relationship_id)
        
        # Schedule index persistence
        self._schedule_persist()
        
        return relationship_id
        
    def get_entity(self, entity_id):
        """Retrieve an entity by ID."""
        if entity_id not in self.entities:
            return None
            
        # Lazy load entity data if needed
        if self.entities[entity_id]["data"] is None:
            cid = self.entities[entity_id]["cid"]
            self.entities[entity_id]["data"] = self.ipfs.dag_get(cid)
            
        return self.entities[entity_id]["data"]
        
    def query_related(self, entity_id, relationship_type=None, direction="outgoing"):
        """Find entities related to the given entity."""
        if entity_id not in self.entities:
            return []
            
        if "entity_rels" not in self.relationships:
            return []
            
        related_entities = []
        
        # Get relationships for this entity
        entity_rels = self.relationships["entity_rels"].get(entity_id, [])
        
        for rel_id in entity_rels:
            # Parse relationship ID
            from_id, rel_type, to_id = rel_id.split(":")
            
            # Skip if relationship type doesn't match filter
            if relationship_type and rel_type != relationship_type:
                continue
                
            # Handle direction
            if direction == "outgoing" and from_id == entity_id:
                related_entities.append({
                    "entity_id": to_id,
                    "relationship_type": rel_type,
                    "direction": "outgoing"
                })
            elif direction == "incoming" and to_id == entity_id:
                related_entities.append({
                    "entity_id": from_id,
                    "relationship_type": rel_type,
                    "direction": "incoming"
                })
            elif direction == "both":
                other_id = to_id if from_id == entity_id else from_id
                related_entities.append({
                    "entity_id": other_id,
                    "relationship_type": rel_type,
                    "direction": "outgoing" if from_id == entity_id else "incoming"
                })
                
        return related_entities
        
    def vector_search(self, query_vector, top_k=10):
        """Find entities similar to the given vector."""
        if "vectors" not in self.vectors or not self.vectors["vectors"]:
            return []
            
        # Simple vector searchimplementation (for production use a proper ANN library)
        query_vector = np.array(query_vector)
        all_vectors = np.array(self.vectors["vectors"])
        
        # Calculate cosine similarities
        similarities = np.dot(all_vectors, query_vector) / (
            np.linalg.norm(all_vectors, axis=1) * np.linalg.norm(query_vector)
        )
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # Map to entities with scores
        results = []
        for idx in top_indices:
            entity_id = self.vectors["entity_map"][str(idx)]
            score = float(similarities[idx])
            results.append({
                "entity_id": entity_id,
                "score": score
            })
            
        return results
        
    def graph_vector_search(self, query_vector, hop_count=2, top_k=10):
        """Combined graph and vector search (GraphRAG)."""
        # First get vector search results
        vector_results = self.vector_search(query_vector, top_k=top_k)
        
        # Then explore graph neighborhood
        expanded_results = {}
        for result in vector_results:
            entity_id = result["entity_id"]
            score = result["score"]
            
            # Add to results with original score
            expanded_results[entity_id] = {
                "entity_id": entity_id,
                "score": score,
                "path": [entity_id],
                "distance": 0
            }
            
            # Explore neighborhood up to hop_count
            self._explore_neighborhood(
                entity_id, 
                expanded_results, 
                max_hops=hop_count,
                current_hop=0,
                origin_score=score,
                path=[entity_id]
            )
            
        # Sort by score and return top results
        sorted_results = sorted(
            expanded_results.values(),
            key=lambda x: x["score"],
            reverse=True
        )
        
        return sorted_results[:top_k]
        
    def _explore_neighborhood(self, entity_id, results, max_hops, current_hop, origin_score, path):
        """Recursively explore entity neighborhood for graph search."""
        if current_hop >= max_hops:
            return
            
        # Get related entities
        related = self.query_related(entity_id, direction="both")
        
        for rel in related:
            neighbor_id = rel["entity_id"]
            
            # Skip if already in path (avoid cycles)
            if neighbor_id in path:
                continue
                
            # Calculate score decay based on distance
            hop_penalty = 0.5 ** (current_hop + 1)  # Score decays by half each hop
            neighbor_score = origin_score * hop_penalty
            
            new_path = path + [neighbor_id]
            
            # Add or update in results
            if neighbor_id not in results or neighbor_score > results[neighbor_id]["score"]:
                results[neighbor_id] = {
                    "entity_id": neighbor_id,
                    "score": neighbor_score,
                    "path": new_path,
                    "distance": current_hop + 1
                }
                
            # Continue exploration
            self._explore_neighborhood(
                neighbor_id,
                results,
                max_hops,
                current_hop + 1,
                origin_score,
                new_path
            )
```

#### Phase 4: Integration and Ecosystem

##### IPFSDataLoader
```python
class IPFSDataLoader:
    """IPFS-based data loader for ML frameworks."""
    
    def __init__(self, ipfs_client, batch_size=32, shuffle=True, prefetch=2):
        """Initialize data loader for machine learning workloads.
        
        Args:
            ipfs_client: IPFS client for content access
            batch_size: Number of samples per batch
            shuffle: Whether to shuffle the dataset
            prefetch: Number of batches to prefetch
        """
        self.ipfs = ipfs_client
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.prefetch = prefetch
        
        # Dataset-related attributes
        self.dataset_cid = None
        self.dataset_metadata = None
        self.sample_cids = []
        self.total_samples = 0
        
        # Prefetching attributes
        self.prefetch_queue = queue.Queue(maxsize=prefetch)
        self.prefetch_threads = []
        self.stop_prefetch = threading.Event()
        
    def load_dataset(self, dataset_cid):
        """Load dataset metadata from IPFS."""
        self.dataset_cid = dataset_cid
        
        # Fetch dataset metadata
        try:
            self.dataset_metadata = self.ipfs.dag_get(dataset_cid)
            
            # Extract sample CIDs
            if "samples" in self.dataset_metadata:
                self.sample_cids = self.dataset_metadata["samples"]
                self.total_samples = len(self.sample_cids)
            else:
                raise ValueError("Dataset doesn't contain samples list")
                
            # Start prefetching
            self._start_prefetch()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load dataset {dataset_cid}: {e}")
            return False
            
    def _start_prefetch(self):
        """Start prefetching thread."""
        # Stop existing threads if any
        self.stop_prefetch.set()
        for thread in self.prefetch_threads:
            thread.join()
            
        # Clear queue and reset stop event
        self.prefetch_queue = queue.Queue(maxsize=self.prefetch)
        self.stop_prefetch.clear()
        
        # Start new prefetch thread
        thread = threading.Thread(target=self._prefetch_worker)
        thread.daemon = True
        thread.start()
        self.prefetch_threads = [thread]
        
    def _prefetch_worker(self):
        """Prefetch worker that loads batches in background."""
        # Create sample indices
        indices = list(range(self.total_samples))
        
        # Main prefetch loop
        while not self.stop_prefetch.is_set():
            # Shuffle if needed
            if self.shuffle:
                random.shuffle(indices)
                
            # Process in batches
            for i in range(0, self.total_samples, self.batch_size):
                if self.stop_prefetch.is_set():
                    break
                    
                # Get batch indices
                batch_indices = indices[i:i+self.batch_size]
                
                # Load samples
                batch = self._load_batch(batch_indices)
                
                # Add to queue (with timeout to allow stopping)
                try:
                    self.prefetch_queue.put(batch, timeout=1.0)
                except queue.Full:
                    pass
                    
    def _load_batch(self, indices):
        """Load a batch of samples by indices."""
        batch = []
        
        for idx in indices:
            if idx >= self.total_samples:
                continue
                
            # Get sample CID
            sample_cid = self.sample_cids[idx]
            
            try:
                # Load sample from IPFS
                sample = self.ipfs.dag_get(sample_cid)
                batch.append(sample)
            except Exception as e:
                logger.warning(f"Failed to load sample {sample_cid}: {e}")
                
        return batch
        
    def __iter__(self):
        """Iterator interface for dataset."""
        return self
        
    def __next__(self):
        """Get next batch from dataset."""
        if self.total_samples == 0:
            raise StopIteration
            
        try:
            # Get batch from prefetch queue
            batch = self.prefetch_queue.get(timeout=10.0)
            return batch
        except queue.Empty:
            # If prefetch is too slow or exhausted
            raise StopIteration
            
    def __len__(self):
        """Number of batches in dataset."""
        return (self.total_samples + self.batch_size - 1) // self.batch_size
        
    def to_pytorch(self):
        """Convert to PyTorch DataLoader."""
        try:
            import torch
            from torch.utils.data import IterableDataset, DataLoader
            
            # Create wrapper class
            class IPFSIterableDataset(IterableDataset):
                def __init__(self, ipfs_loader):
                    self.ipfs_loader = ipfs_loader
                    
                def __iter__(self):
                    for batch in self.ipfs_loader:
                        for sample in batch:
                            # Convert to tensors based on sample format
                            if "features" in sample and "labels" in sample:
                                features = torch.tensor(sample["features"])
                                labels = torch.tensor(sample["labels"])
                                yield features, labels
                            else:
                                # Just return the whole sample as a dict
                                yield {k: torch.tensor(v) if isinstance(v, list) else v 
                                      for k, v in sample.items()}
                                
            # Create and return DataLoader
            dataset = IPFSIterableDataset(self)
            return DataLoader(
                dataset,
                batch_size=self.batch_size,
                num_workers=0  # Already using our own prefetching
            )
            
        except ImportError:
            logger.error("PyTorch not available")
            return None
```


### Implementation Phases

#### Phase 1: FSSpec Filesystem Interface (3 weeks)
- FSSpec adapter implementation
- Adaptive replacement cache
- Integration with existing IPFS methods
- Performance optimization
- FastAPI server exposure for RESTful access
- Test-driven development in test/ folder only until features are fully debugged
- Multiprocessing implementation with memory queues (mmap or Arrow C Data Interface) for low-latency IPC
- AST-based code analysis to detect and prevent duplication across components

##### Implementation Example: FSSpec with Unix Socket Performance

```python
class IPFSFileSystem(AbstractFileSystem):
    """High-performance IPFS filesystem with Unix socket support."""
    
    protocol = "ipfs"
    
    def __init__(self, ipfs_path=None, socket_path=None, use_mmap=True, **kwargs):
        super().__init__(**kwargs)
        self.ipfs_path = ipfs_path or os.environ.get("IPFS_PATH", "~/.ipfs")
        self.socket_path = socket_path
        self.use_mmap = use_mmap
        
        # Use Unix socket if available (Linux only) for better performance
        if self.socket_path and os.path.exists(self.socket_path):
            self.api_base = f"http://unix:{self.socket_path}:/api/v0"
            self.session = requests.Session()
            self.session.mount("http://unix:", requests_unixsocket.UnixAdapter())
        else:
            self.api_base = "http://127.0.0.1:5001/api/v0"
            self.session = requests.Session()
        
        # Initialize adaptive cache
        self.cache = ARCache(maxsize=1024)  # Adaptive Replacement Cache
        
        # Create mmap handler if enabled
        if self.use_mmap:
            self.mmap_store = {}  # Tracks memory-mapped files
            
    def _open(self, path, mode="rb", **kwargs):
        """Open an IPFS object for reading/writing with optimized access."""
        if mode != "rb":
            raise NotImplementedError("Only read mode supported")
            
        cid = self._path_to_cid(path)
        cache_key = f"ipfs://{cid}"
        
        # Check cache first
        if cache_key in self.cache:
            data = self.cache[cache_key]
            return IPFSMemoryFile(self, path, data, mode)
        
        # Fetch content via socket if available
        if hasattr(self, 'socket_path') and os.path.exists(self.socket_path):
            # Unix socket fetch for better performance
            response = self.session.post(
                f"{self.api_base}/cat", 
                params={"arg": cid}
            )
            data = response.content
        else:
            # Fall back to HTTP API
            response = self.session.post(
                f"{self.api_base}/cat", 
                params={"arg": cid}
            )
            data = response.content
            
        # Cache the result
        self.cache[cache_key] = data
        
        # Use memory mapping for large files if enabled
        if self.use_mmap and len(data) > 10 * 1024 * 1024:  # >10MB
            # Create temp file and memory-map it
            fd, temp_path = tempfile.mkstemp()
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            
            # Memory map the file
            mmap_obj = mmap.mmap(
                os.open(temp_path, os.O_RDONLY),
                0,
                access=mmap.ACCESS_READ
            )
            
            # Track for cleanup
            self.mmap_store[cache_key] = (temp_path, mmap_obj)
            
            return IPFSMappedFile(self, path, mmap_obj, temp_path, mode)
        else:
            return IPFSMemoryFile(self, path, data, mode)
```

#### Phase 2: Arrow-based Metadata Index (4 weeks)
- Schema design
- Parquet persistence
- Query mechanisms
- Performance benchmarking
- Distributed index synchronization
- Partitioning strategy for large-scale metadata

##### Implementation Example: Arrow-based IPFS Metadata Index

```python
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
from pyarrow.dataset import dataset
import os
import time
import mmap
from typing import Dict, List, Optional, Union, Any

class IPFSArrowIndex:
    """Arrow-based metadata index for IPFS content using C Data Interface for zero-copy access."""
    
    def __init__(self, index_dir: str = "~/.ipfs_index", partition_size: int = 1000000,
                 role: str = "leecher", enable_c_interface: bool = True):
        """Initialize the Arrow-based IPFS metadata index with C Data Interface support.
        
        Args:
            index_dir: Directory to store index partitions
            partition_size: Maximum number of records per partition
            role: Node role ("master", "worker", or "leecher")
            enable_c_interface: Whether to enable Arrow C Data Interface for zero-copy access
        """
        self.index_dir = os.path.expanduser(index_dir)
        os.makedirs(self.index_dir, exist_ok=True)
        self.partition_size = partition_size
        self.role = role
        self.enable_c_interface = enable_c_interface
        self.schema = self._create_schema()
        self.current_partition = self._get_latest_partition()
        self.mmap_files = {}
        self.in_memory_batch = None
        self.c_data_interfaces = {}  # Stores C Data Interface exports
        self._load_latest_partition()
        
        # Create shared memory region for real-time access
        self._create_shared_memory_region()
        
        # Set up sync if master or worker
        if role in ("master", "worker"):
            self._schedule_sync()
    
    def _create_shared_memory_region(self):
        """Create a shared memory region for real-time access via C Data Interface."""
        # Initialize shared memory for active records
        self.shared_memory_name = f"ipfs_index_{os.getpid()}"
        self.shared_memory_path = f"/dev/shm/{self.shared_memory_name}"
        
        # Create an initial empty table with the schema
        empty_arrays = []
        for field in self.schema:
            empty_arrays.append(pa.array([], type=field.type))
        
        self.shared_table = pa.Table.from_arrays(empty_arrays, schema=self.schema)
        
        # Export to shared memory using Arrow C Data Interface
        if self.enable_c_interface:
            self._export_to_c_data_interface()
    
    def _create_schema(self) -> pa.Schema:
        """Define the Arrow schema for IPFS metadata."""
        return pa.schema([
            # Content identifier fields
            pa.field('cid', pa.string()),  # Primary IPFS identifier
            pa.field('cid_version', pa.int8()),
            pa.field('multihash_type', pa.string()),
            
            # File metadata
            pa.field('unixfs_path', pa.string()),  # Complete UnixFS path
            pa.field('filename', pa.string()),  # Extracted filename
            pa.field('mimetype', pa.string()),  # Content MIME type
            pa.field('size_bytes', pa.int64()),  # File size
            pa.field('block_count', pa.int32()),  # Number of blocks
            
            # Access patterns
            pa.field('added_timestamp', pa.timestamp('ms')),
            pa.field('last_accessed', pa.timestamp('ms')),
            pa.field('access_count', pa.int32()),
            pa.field('heat_score', pa.float32()),  # Computed value for cache priority
            
            # Multi-system storage locations
            pa.field('storage_locations', pa.struct([
                # IPFS-based locations
                pa.field('ipfs', pa.struct([
                    pa.field('pinned', pa.bool_()),
                    pa.field('pin_types', pa.list_(pa.string())),
                    pa.field('local', pa.bool_()),
                    pa.field('gateway_urls', pa.list_(pa.string())),
                ])),
                
                # IPFS Cluster locations
                pa.field('ipfs_cluster', pa.struct([
                    pa.field('pinned', pa.bool_()),
                    pa.field('replication_factor', pa.int8()),
                    pa.field('allocation_nodes', pa.list_(pa.string())),
                    pa.field('pin_status', pa.string()),
                ])),
                
                # libp2p direct peers that have this content
                pa.field('libp2p', pa.struct([
                    pa.field('peers', pa.list_(pa.string())),  # Peer IDs
                    pa.field('protocols', pa.list_(pa.string())),  # Supported protocols
                    pa.field('multiaddrs', pa.list_(pa.string())),  # Connection addresses
                ])),
                
                # Storacha/W3 locations
                pa.field('storacha', pa.struct([
                    pa.field('car_cid', pa.string()),  # CAR file CID containing this content
                    pa.field('upload_id', pa.string()),
                    pa.field('space_did', pa.string()),  # DID for the space where content is stored
                    pa.field('stored_timestamp', pa.timestamp('ms')),
                ])),
                
                # S3 storage locations (multi-region, multi-bucket)
                pa.field('s3', pa.list_(pa.struct([
                    pa.field('provider', pa.string()),  # 'aws', 'gcp', 'azure', etc.
                    pa.field('region', pa.string()),
                    pa.field('bucket', pa.string()),
                    pa.field('key', pa.string()),
                    pa.field('storage_class', pa.string()),  # 'STANDARD', 'GLACIER', etc.
                    pa.field('etag', pa.string()),
                    pa.field('version_id', pa.string()),
                ]))),
                
                # Filecoin storage
                pa.field('filecoin', pa.struct([
                    pa.field('deal_id', pa.string()),
                    pa.field('providers', pa.list_(pa.string())),
                    pa.field('replication_factor', pa.int8()),
                    pa.field('deal_expiration', pa.timestamp('ms')),
                    pa.field('verified_deal', pa.bool_()),
                ])),
                
                # HuggingFace Hub
                pa.field('huggingface_hub', pa.struct([
                    pa.field('repo_id', pa.string()),
                    pa.field('repo_type', pa.string()),
                    pa.field('file_path', pa.string()),
                    pa.field('revision', pa.string()),
                    pa.field('commit_hash', pa.string()),
                ])),
            ])),
            
            # Current storage tier 
            pa.field('current_tier', pa.string()),  # 'memory', 'disk', 'cluster', 'storacha', 'filecoin', etc.
            
            # Extended metadata (schematized)
            pa.field('metadata', pa.struct([
                pa.field('name', pa.string()),
                pa.field('description', pa.string()),
                pa.field('tags', pa.list_(pa.string())),
                pa.field('source', pa.string()),
                pa.field('license', pa.string()),
                pa.field('created_by', pa.string()),
                pa.field('original_path', pa.string()),
            ])),
            
            # Arbitrary unstructured metadata (flexible)
            pa.field('extra', pa.map_(pa.string(), pa.string()))
        ])
    
    def _get_latest_partition(self) -> int:
        """Find the latest partition number."""
        partitions = [f for f in os.listdir(self.index_dir) 
                      if f.startswith('ipfs_index_') and f.endswith('.parquet')]
        if not partitions:
            return 0
        return max([int(p.split('_')[2].split('.')[0]) for p in partitions])
    
    def _get_partition_path(self, partition_num: int) -> str:
        """Get the path for a specific partition."""
        return os.path.join(self.index_dir, f"ipfs_index_{partition_num:06d}.parquet")
    
    def _export_to_c_data_interface(self):
        """Export the shared table using Arrow C Data Interface.
        
        This allows zero-copy access from other languages and processes.
        """
        try:
            import pyarrow.plasma as plasma
            
            # Create or connect to plasma store for shared memory
            if not hasattr(self, 'plasma_client'):
                self.plasma_client = plasma.connect(self.shared_memory_path)
                
            # Generate object ID for the table
            import hashlib
            object_id = plasma.ObjectID(hashlib.md5(f"{self.shared_memory_name}_{time.time()}".encode()).digest()[:20])
            
            # Create and seal the object
            data_size = self.shared_table.nbytes
            buffer = self.plasma_client.create(object_id, data_size)
            writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), self.shared_table.schema)
            writer.write_table(self.shared_table)
            writer.close()
            self.plasma_client.seal(object_id)
            
            # Store the object ID for reference
            self.current_object_id = object_id
            
            # Store C Data Interface export
            self.c_data_interface_handle = {
                'object_id': object_id.binary().hex(),
                'plasma_socket': self.shared_memory_path,
                'schema_json': self.schema.to_string(),
                'num_rows': self.shared_table.num_rows,
                'timestamp': time.time()
            }
            
            # Write C Data Interface metadata to disk for other processes
            cdi_path = os.path.join(self.index_dir, 'c_data_interface.json')
            with open(cdi_path, 'w') as f:
                import json
                json.dump(self.c_data_interface_handle, f)
                
            self.logger.info(f"Exported index to C Data Interface: {cdi_path}")
            return self.c_data_interface_handle
            
        except ImportError:
            self.logger.warning("PyArrow Plasma not available. C Data Interface export disabled.")
            return None
        except Exception as e:
            self.logger.error(f"Failed to export C Data Interface: {str(e)}")
            return None
            
    def get_c_data_interface(self):
        """Get the C Data Interface handle for external access.
        
        Returns:
            Dictionary with C Data Interface metadata for accessing the shared table
        """
        if hasattr(self, 'c_data_interface_handle'):
            return self.c_data_interface_handle
        else:
            return None
    
    def _load_latest_partition(self):
        """Load the latest partition into memory for fast access using memory mapping."""
        partition_path = self._get_partition_path(self.current_partition)
        if os.path.exists(partition_path):
            try:
                # Memory-map the parquet file for fast random access
                self.logger.info(f"Memory-mapping parquet file: {partition_path}")
                
                # Use PyArrow's native memory mapping 
                table = pq.read_table(partition_path, memory_map=True)
                
                # Get record batch for in-memory work
                self.in_memory_batch = table.to_batches()[0] if table.num_rows > 0 else None
                
                # Keep reference to the memory-mapped file
                file_obj = open(partition_path, 'rb')
                mmap_obj = mmap.mmap(file_obj.fileno(), 0, access=mmap.ACCESS_READ)
                self.mmap_files[partition_path] = (file_obj, mmap_obj)
                
                # Update the shared table for C Data Interface access
                if self.in_memory_batch is not None:
                    self.shared_table = pa.Table.from_batches([self.in_memory_batch])
                    if self.enable_c_interface:
                        self._export_to_c_data_interface()
                
                self.logger.info(f"Loaded partition with {table.num_rows} records")
                
            except Exception as e:
                self.logger.error(f"Error memory-mapping partition: {str(e)}")
                self.in_memory_batch = None
        else:
            self.in_memory_batch = None
    
    def add_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Add a metadata record to the index.
        
        Args:
            record: Dictionary containing metadata fields matching the schema
            
        Returns:
            Status dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "add_record",
            "timestamp": time.time()
        }
        
        try:
            # Validate and prepare the record
            self._validate_record(record)
            
            # Add required timestamps if missing
            current_time = pa.scalar(time.time() * 1000).cast(pa.timestamp('ms'))
            if 'added_timestamp' not in record:
                record['added_timestamp'] = current_time
            if 'last_accessed' not in record:
                record['last_accessed'] = current_time
                
            # Set default values for required fields if missing
            if 'access_count' not in record:
                record['access_count'] = 1
            if 'heat_score' not in record:
                record['heat_score'] = self._calculate_heat_score(record)
                
            # Convert record to PyArrow format
            arrays = []
            for field in self.schema:
                field_name = field.name
                if field_name in record:
                    arrays.append(pa.array([record[field_name]], type=field.type))
                else:
                    arrays.append(pa.array([None], type=field.type))
                    
            # Create a record batch
            batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
            
            # Append to in-memory batch
            if self.in_memory_batch is None:
                self.in_memory_batch = batch
            else:
                self.in_memory_batch = pa.concat_batches([self.in_memory_batch, batch])
                
            # Update shared table for C Data Interface access
            self.shared_table = pa.Table.from_batches([self.in_memory_batch])
            
            # Re-export via C Data Interface if enabled
            if self.enable_c_interface:
                cdi_result = self._export_to_c_data_interface()
                if cdi_result:
                    result["c_data_interface_updated"] = True
            
            # Check if we need to create a new partition
            if self.in_memory_batch.num_rows >= self.partition_size:
                self._persist_current_partition()
                self.current_partition += 1
                self.in_memory_batch = None
                result["partition_rotated"] = True
                
            # Schedule async persistence if needed
            self._schedule_persist()
            
            result["success"] = True
            result["record_added"] = True
            result["cid"] = record.get("cid", None)
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            self.logger.error(f"Error adding record: {e}")
            
        return result
    
    def _get_peer_list(self) -> List[str]:
        """Discover peers for index synchronization.
        
        Returns:
            List of peer identifiers that can share index data
        """
        # Request peer list from IPFS
        peers = []
        
        # If we're a master, get cluster nodes
        if self.role == "master":
            try:
                cluster_peers = self.ipfs_cluster.peers()
                if cluster_peers.get("success", False):
                    peers.extend([p["id"] for p in cluster_peers.get("peers", [])])
            except Exception as e:
                self.logger.warning(f"Failed to get cluster peers: {str(e)}")
        
        # For all roles, get connected libp2p peers supporting our protocol
        try:
            libp2p_peers = self.libp2p_host.get_peers_with_protocol("/ipfs-index/sync/1.0.0")
            peers.extend(libp2p_peers)
        except Exception as e:
            self.logger.warning(f"Failed to get libp2p peers: {str(e)}")
        
        return list(set(peers))  # Deduplicate
            
    def sync_with_peers(self) -> Dict[str, Any]:
        """Synchronize index with other peers.
        
        Fetches and merges index updates from peers, and publishes
        our own updates to the network.
        
        Returns:
            Status information about the sync operation
        """
        result = {
            "success": False,
            "peers_contacted": 0,
            "records_received": 0,
            "records_sent": 0,
            "errors": []
        }
        
        # Get list of peers to sync with
        peers = self._get_peer_list()
        result["peers_available"] = len(peers)
        
        if not peers:
            result["success"] = True  # No peers is still a successful sync
            return result
            
        # Sync with each peer
        for peer_id in peers:
            try:
                # Exchange index data with peer
                peer_result = self._sync_with_peer(peer_id)
                
                # Update statistics
                result["peers_contacted"] += 1
                result["records_received"] += peer_result.get("records_received", 0)
                result["records_sent"] += peer_result.get("records_sent", 0)
                
            except Exception as e:
                error_msg = f"Failed to sync with peer {peer_id}: {str(e)}"
                result["errors"].append(error_msg)
                self.logger.error(error_msg)
        
        # Set overall success if we contacted at least one peer
        result["success"] = result["peers_contacted"] > 0
        
        return result
        
    def find_content_locations(self, cid: str = None, path: str = None, mimetype: str = None) -> Dict[str, Any]:
        """Find all storage locations for a specific piece of content.
        
        Search by CID, path, or other metadata to locate all storage systems
        where this content is available.
        
        Args:
            cid: Content Identifier to search for
            path: UnixFS path to search for
            mimetype: MIME type to filter by
            
        Returns:
            Dictionary with search results and available storage locations
        """
        result = {
            "success": False,
            "content_found": False,
            "locations": [],
            "fastest_retrieval_path": None,
            "error": None
        }
        
        try:
            # Build filtering conditions
            conditions = []
            if cid:
                conditions.append(pc.equal(pc.field('cid'), pa.scalar(cid)))
            if path:
                conditions.append(pc.equal(pc.field('unixfs_path'), pa.scalar(path)))
            if mimetype:
                conditions.append(pc.equal(pc.field('mimetype'), pa.scalar(mimetype)))
                
            if not conditions:
                result["error"] = "At least one search parameter is required"
                return result
                
            # Combine conditions with AND
            filter_expr = conditions[0]
            for condition in conditions[1:]:
                filter_expr = pc.and_(filter_expr, condition)
                
            # Search in-memory batch if it exists
            records = []
            if self.in_memory_batch is not None:
                table = pa.Table.from_batches([self.in_memory_batch])
                filtered_table = table.filter(filter_expr)
                if filtered_table.num_rows > 0:
                    records.extend(filtered_table.to_pylist())
                    
            # Search on-disk partitions
            dataset_path = self.index_dir
            if os.path.exists(dataset_path):
                ds = dataset(dataset_path, format="parquet")
                filtered_ds = ds.to_table(filter=filter_expr)
                if filtered_ds.num_rows > 0:
                    records.extend(filtered_ds.to_pylist())
                    
            # Process results
            if records:
                result["content_found"] = True
                result["record_count"] = len(records)
                
                # Extract storage locations from all matching records
                for record in records:
                    locations = self._extract_storage_locations(record)
                    result["locations"].extend(locations)
                    
                # Determine fastest retrieval path
                result["fastest_retrieval_path"] = self._determine_fastest_path(result["locations"])
                
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Error finding content locations: {e}")
            
        return result
        
    def _extract_storage_locations(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all storage locations from a record.
        
        Converts the structured storage_locations field into a list of 
        available locations with metadata about each.
        
        Args:
            record: PyArrow record converted to Python dict
            
        Returns:
            List of storage location dictionaries with access info
        """
        locations = []
        storage_data = record.get("storage_locations", {})
        
        # Process IPFS locations
        ipfs_data = storage_data.get("ipfs", {})
        if ipfs_data and ipfs_data.get("local", False):
            locations.append({
                "type": "ipfs",
                "local": True,
                "access_method": "ipfs.cat",
                "cid": record.get("cid"),
                "latency_estimate_ms": 10,  # Local access is fastest
                "gateway_urls": ipfs_data.get("gateway_urls", []),
                "pinned": ipfs_data.get("pinned", False)
            })
            
        # Process IPFS Cluster locations
        cluster_data = storage_data.get("ipfs_cluster", {})
        if cluster_data and cluster_data.get("pinned", False):
            locations.append({
                "type": "ipfs_cluster",
                "access_method": "cluster.get",
                "cid": record.get("cid"),
                "latency_estimate_ms": 50,
                "allocation_nodes": cluster_data.get("allocation_nodes", []),
                "replication_factor": cluster_data.get("replication_factor", 1)
            })
            
        # Process libp2p locations
        libp2p_data = storage_data.get("libp2p", {})
        if libp2p_data and libp2p_data.get("peers", []):
            locations.append({
                "type": "libp2p",
                "access_method": "libp2p.direct_fetch",
                "cid": record.get("cid"),
                "latency_estimate_ms": 100,
                "peers": libp2p_data.get("peers", []),
                "multiaddrs": libp2p_data.get("multiaddrs", [])
            })
            
        # Process S3 locations
        s3_entries = storage_data.get("s3", [])
        for s3_data in s3_entries:
            locations.append({
                "type": "s3",
                "access_method": "s3.get_object",
                "provider": s3_data.get("provider", "aws"),
                "region": s3_data.get("region"),
                "bucket": s3_data.get("bucket"),
                "key": s3_data.get("key"),
                "latency_estimate_ms": 200,
                "storage_class": s3_data.get("storage_class")
            })
            
        # Process Storacha locations
        storacha_data = storage_data.get("storacha", {})
        if storacha_data and storacha_data.get("car_cid"):
            locations.append({
                "type": "storacha",
                "access_method": "storacha.get",
                "car_cid": storacha_data.get("car_cid"),
                "cid": record.get("cid"),
                "latency_estimate_ms": 500,
                "space_did": storacha_data.get("space_did")
            })
            
        # Process Filecoin locations
        filecoin_data = storage_data.get("filecoin", {})
        if filecoin_data and filecoin_data.get("deal_id"):
            locations.append({
                "type": "filecoin",
                "access_method": "filecoin.retrieve",
                "deal_id": filecoin_data.get("deal_id"),
                "cid": record.get("cid"),
                "latency_estimate_ms": 10000,  # Slowest retrieval typically
                "providers": filecoin_data.get("providers", [])
            })
            
        # Process HuggingFace Hub locations
        hf_data = storage_data.get("huggingface_hub", {})
        if hf_data and hf_data.get("repo_id"):
            locations.append({
                "type": "huggingface_hub",
                "access_method": "hf_hub_download",
                "repo_id": hf_data.get("repo_id"),
                "repo_type": hf_data.get("repo_type", "model"),
                "file_path": hf_data.get("file_path"),
                "revision": hf_data.get("revision", "main"),
                "latency_estimate_ms": 300
            })
            
        return locations
        
    def _determine_fastest_path(self, locations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Determine the fastest retrieval path from available locations.
        
        Analyzes all available storage locations and determines the
        optimal retrieval strategy based on latency, availability,
        and current system state.
        
        Args:
            locations: List of available storage locations
            
        Returns:
            Dictionary with access information for fastest retrieval path
        """
        if not locations:
            return None
            
        # Sort locations by estimated latency
        sorted_locations = sorted(locations, key=lambda x: x.get("latency_estimate_ms", float('inf')))
        
        # Additional logic could weigh other factors beyond just latency
        # - Network conditions
        # - Storage tier preferences
        # - Cost considerations
        # - Node role and resource availability
        
        return sorted_locations[0]
        
    def query(self, filters: List[tuple]) -> pa.Table:
        """Query the index with filters.
        
        Args:
            filters: List of filter tuples in format (field, op, value)
                     e.g. [("size_bytes", ">", 1024), ("pinned", "==", True)]
        
        Returns:
            Arrow Table with matching records
        """
        # Create dataset from all partitions
        ds = dataset(self.index_dir, format="parquet")
        
        # Convert filters to Arrow filter expressions
        filter_expr = None
        for field_name, op, value in filters:
            # Convert operation string to Arrow compute function
            if op == "==":
                expr = pc.equal(pc.field(field_name), pa.scalar(value))
            elif op == "!=":
                expr = pc.not_equal(pc.field(field_name), pa.scalar(value))
            elif op == ">":
                expr = pc.greater(pc.field(field_name), pa.scalar(value))
            elif op == ">=":
                expr = pc.greater_equal(pc.field(field_name), pa.scalar(value))
            elif op == "<":
                expr = pc.less(pc.field(field_name), pa.scalar(value))
            elif op == "<=":
                expr = pc.less_equal(pc.field(field_name), pa.scalar(value))
            elif op == "in":
                if not isinstance(value, (list, tuple)):
                    value = [value]
                expr = pc.is_in(pc.field(field_name), pa.array(value))
            elif op == "contains":
                expr = pc.match_substring(pc.field(field_name), value)
            else:
                raise ValueError(f"Unsupported operation: {op}")
            
            # Combine expressions with AND
            if filter_expr is None:
                filter_expr = expr
            else:
                filter_expr = pc.and_(filter_expr, expr)
        
        # Apply filters and return results
        if filter_expr is not None:
            return ds.to_table(filter=filter_expr)
        else:
            return ds.to_table()
    
    @staticmethod
    def access_via_c_data_interface(index_dir: str = "~/.ipfs_index") -> Dict[str, Any]:
        """Access the IPFS index from another process via Arrow C Data Interface.
        
        This static method enables external processes to access the memory-mapped
        index without copying the data. This is particularly useful for:
        - Multi-language access (C++, Rust, etc.)
        - Zero-copy data exchange with other processes
        - Low-latency IPC for performance-critical operations
        
        Args:
            index_dir: Directory where the index is stored
            
        Returns:
            Dictionary with access handle and metadata
        """
        result = {
            "success": False,
            "operation": "access_via_c_data_interface",
            "timestamp": time.time()
        }
        
        try:
            # Import necessary components
            import pyarrow as pa
            import pyarrow.plasma as plasma
            import json
            import os
            
            # Expand path
            index_dir = os.path.expanduser(index_dir)
            
            # Find C Data Interface metadata file
            cdi_path = os.path.join(index_dir, 'c_data_interface.json')
            if not os.path.exists(cdi_path):
                result["error"] = f"C Data Interface metadata not found at {cdi_path}"
                return result
                
            # Load C Data Interface metadata
            with open(cdi_path, 'r') as f:
                cdi_metadata = json.load(f)
                
            # Connect to plasma store
            plasma_socket = cdi_metadata.get('plasma_socket')
            if not plasma_socket or not os.path.exists(plasma_socket):
                result["error"] = f"Plasma socket not found at {plasma_socket}"
                return result
                
            # Connect to plasma store
            plasma_client = plasma.connect(plasma_socket)
            
            # Get object ID
            object_id_hex = cdi_metadata.get('object_id')
            if not object_id_hex:
                result["error"] = "Object ID not found in metadata"
                return result
                
            # Convert hex to binary object ID
            object_id = plasma.ObjectID(bytes.fromhex(object_id_hex))
            
            # Get the object from plasma store
            if not plasma_client.contains(object_id):
                result["error"] = f"Object {object_id_hex} not found in plasma store"
                return result
                
            # Get the table from plasma store
            buffer = plasma_client.get_buffers([object_id])[object_id]
            reader = pa.RecordBatchStreamReader(buffer)
            table = reader.read_all()
            
            # Success!
            result["success"] = True
            result["table"] = table
            result["schema"] = table.schema
            result["num_rows"] = table.num_rows
            result["metadata"] = cdi_metadata
            result["access_method"] = "c_data_interface"
            
            # Return the handle for cleanup
            result["plasma_client"] = plasma_client
            
            return result
            
        except ImportError as e:
            result["error"] = f"Required module not available: {str(e)}"
            return result
        except Exception as e:
            result["error"] = f"Error accessing via C Data Interface: {str(e)}"
            return result
    
    @staticmethod
    def c_data_interface_example():
        """Example of accessing the index from external languages via C Data Interface.
        
        This demonstrates how to access the IPFS metadata index from C++, Rust,
        or other languages that support the Arrow C Data Interface.
        """
        # C++ Example Using Arrow C++
        cpp_example = """
        #include <arrow/api.h>
        #include <arrow/io/api.h>
        #include <arrow/ipc/api.h>
        #include <arrow/json/api.h>
        #include <arrow/util/logging.h>
        #include <plasma/client.h>
        
        #include <iostream>
        #include <string>
        
        using namespace arrow;
        
        int main() {
            // Read JSON metadata to get the plasma store socket and object ID
            std::string json_path = "/home/user/.ipfs_index/c_data_interface.json";
            std::string plasma_socket;
            std::string object_id_hex;
            
            // ... parse JSON to extract plasma_socket and object_id_hex ...
            
            // Connect to plasma store
            std::shared_ptr<plasma::PlasmaClient> client;
            plasma::Status status = plasma::Connect(plasma_socket, "", 0, &client);
            if (!status.ok()) {
                std::cerr << "Failed to connect to plasma store: " << status.message() << std::endl;
                return 1;
            }
            
            // Convert hex object ID to binary
            plasma::ObjectID object_id = plasma::ObjectID::from_binary(object_id_hex);
            
            // Get the object from plasma store
            std::shared_ptr<Buffer> buffer;
            status = client->Get(&object_id, 1, -1, &buffer);
            if (!status.ok()) {
                std::cerr << "Failed to get object: " << status.message() << std::endl;
                return 1;
            }
            
            // Create Arrow buffer reader
            auto buffer_reader = std::make_shared<io::BufferReader>(buffer);
            
            // Read the record batch stream
            std::shared_ptr<ipc::RecordBatchStreamReader> reader;
            status = ipc::RecordBatchStreamReader::Open(buffer_reader, &reader);
            if (!status.ok()) {
                std::cerr << "Failed to open record batch reader: " << status.message() << std::endl;
                return 1;
            }
            
            // Read the first record batch
            std::shared_ptr<RecordBatch> batch;
            status = reader->ReadNext(&batch);
            if (!status.ok()) {
                std::cerr << "Failed to read record batch: " << status.message() << std::endl;
                return 1;
            }
            
            // Now we can access the data without copying
            std::cout << "Number of rows: " << batch->num_rows() << std::endl;
            std::cout << "Number of columns: " << batch->num_columns() << std::endl;
            
            // Example: access CID column
            auto cid_array = std::static_pointer_cast<StringArray>(batch->column(0));
            for (int i = 0; i < std::min(10, batch->num_rows()); i++) {
                std::cout << "CID " << i << ": " << cid_array->GetString(i) << std::endl;
            }
            
            return 0;
        }
        """
        
        # Rust Example Using Arrow Rust
        rust_example = """
        use std::fs::File;
        use std::path::Path;
        
        use arrow::array::{StringArray, StructArray};
        use arrow::datatypes::Schema;
        use arrow::ipc::reader::StreamReader;
        use arrow::record_batch::RecordBatch;
        use plasma::PlasmaClient;
        use serde_json::Value;
        
        fn main() -> Result<(), Box<dyn std::error::Error>> {
            // Read JSON metadata
            let json_path = Path::new("/home/user/.ipfs_index/c_data_interface.json");
            let file = File::open(json_path)?;
            let metadata: Value = serde_json::from_reader(file)?;
            
            // Extract plasma socket and object ID
            let plasma_socket = metadata["plasma_socket"].as_str().unwrap();
            let object_id_hex = metadata["object_id"].as_str().unwrap();
            
            // Convert hex to binary object ID
            let object_id = hex::decode(object_id_hex)?;
            
            // Connect to plasma store
            let mut client = PlasmaClient::connect(plasma_socket, "")?;
            
            // Get the object from plasma store
            let buffer = client.get(&object_id, -1)?;
            
            // Create Arrow reader from buffer
            let reader = StreamReader::try_new(&buffer[..])?;
            
            // Read the schema
            let schema = reader.schema();
            println!("Schema: {:?}", schema);
            
            // Read the first record batch
            let batch = reader.next().unwrap()?;
            println!("Number of rows: {}", batch.num_rows());
            
            // Example: access CID column
            let cid_array = batch.column(0).as_any().downcast_ref::<StringArray>().unwrap();
            for i in 0..std::cmp::min(10, batch.num_rows()) {
                println!("CID {}: {}", i, cid_array.value(i));
            }
            
            // Example: access storage locations struct
            let locations = batch.column(batch.schema().index_of("storage_locations").unwrap())
                                .as_any().downcast_ref::<StructArray>().unwrap();
            
            // Access nested IPFS struct
            let ipfs = locations.field(locations.type_().field_indices()["ipfs"])
                               .as_any().downcast_ref::<StructArray>().unwrap();
            
            // Check if content is pinned locally
            let pinned = ipfs.field(ipfs.type_().field_indices()["pinned"]);
            println!("First 10 pinning statuses:");
            for i in 0..std::cmp::min(10, batch.num_rows()) {
                println!("  Row {}: pinned = {}", i, pinned.is_valid(i));
            }
            
            Ok(())
        }
        """
        
        return {
            "cpp_example": cpp_example,
            "rust_example": rust_example,
            "note": "These examples demonstrate zero-copy access to the memory-mapped Arrow data"
        }
```

### Estimated Effort

| Phase | Duration | Effort (person-months) | Key Deliverables |
|-------|----------|------------------------|------------------|
| **Phase 1: Core Infrastructure** | 6 months | 12 person-months | Refactored codebase, FSSpec interface, Tiered storage, P2P communication |
| 1.1 Refactor Core Components | 2 months | 2 person-months | Standardized error handling, Secure subprocess handling, Logging system |
| 1.2 FSSpec Integration Layer | 2 months | 2 person-months | Filesystem abstraction, Unix socket support, Streaming interfaces |
| 1.3 Tiered Storage with ARC | 3 months | 4 person-months | Multi-tier caching, Automatic migration, Performance metrics |
| 1.4 Direct P2P Communication | 2 months | 4 person-months | libp2p integration, NAT traversal, Resource-aware routing |
| **Phase 2: High-Performance Data** | 6 months | 12 person-months | Arrow metadata index, Enhanced role architecture, Distributed processing |
| 2.1 Arrow-based Metadata Index | 2 months | 4 person-months | Columnar metadata, Parquet persistence, Efficient partitioning |
| 2.2 Role-based Architecture | 2 months | 4 person-months | Role optimizations, Dynamic switching, Cluster dashboard |
| 2.3 Distributed Processing | 2 months | 4 person-months | Task distribution, Fault tolerance, Resource-aware scheduling |
| **Phase 3: Knowledge Management** | 6 months | 12 person-months | IPLD knowledge graph, Vector storage, GraphRAG integration |
| 3.1 IPLD Knowledge Graph | 2 months | 4 person-months | Graph schemas, Entity-relationship model, Query indexing |
| 3.2 Vector Storage | 2 months | 4 person-months | Embedding storage, HNSW indexes, ANN search optimization |
| 3.3 GraphRAG Integration | 2 months | 4 person-months | Hybrid search, Context-aware retrieval, Relevance scoring |
| **Phase 4: Ecosystem Integration** | 6 months | 12 person-months | External integrations, Performance optimization, Developer tools |
| 4.1 External Systems Integration | 2 months | 4 person-months | LLM/ML framework integrations, Data pipeline connectors |
| 4.2 Performance Optimization | 2 months | 4 person-months | Profiling, Critical path optimization, Scaling strategies |
| 4.3 Developer Tools | 2 months | 4 person-months | High-level API, Documentation, Example applications |
| **Total** | **24 months** | **48 person-months** | Complete IPFS ecosystem with AI/ML integration |

#### Resource Allocation by Skill Set

| Skill Area | Junior (person-months) | Mid-level (person-months) | Senior (person-months) | Total |
|------------|------------------------|---------------------------|------------------------|-------|
| Core Development | 6 | 10 | 8 | 24 |
| Data Engineering | 4 | 6 | 6 | 16 |
| ML/AI Engineering | 2 | 4 | 6 | 12 |
| DevOps/Infrastructure | 2 | 4 | 2 | 8 |
| Documentation/QA | 6 | 2 | 0 | 8 |
| **Total** | **20** | **26** | **22** | **68** |

*Note: The person-month estimates include overlap between different roles and parallel work.*

## Advanced Features

### GraphRAG Search with IPLD

The IPLD-based GraphRAG system combines vector similarity search with knowledge graph traversal:

1. **Vector Component**:
   - Store document/chunk embeddings in IPLD structures
   - Implement approximate nearest neighbor search
   - Use FAISS or similar libraries with IPLD persistence

2. **Knowledge Graph Component**:
   - Entities represented as IPLD nodes with CIDs
   - Relationships as typed links between nodes
   - Properties stored as node attributes
   - Graph schema defined via IPLD schemas

3. **Hybrid Search Process**:
   - Convert query to embedding vector
   - Find similar vectors via ANN search
   - Expand results through graph relationships
   - Apply path-based relevance scoring
   - Rank by combined vector similarity and graph relevance

4. **IPLD Schema for Vectors**:
```json
{
  "type": "struct",
  "fields": {
    "dimension": {"type": "int"},
    "metric": {"type": "string"},
    "vectors": {
      "type": "list",
      "valueType": {
        "type": "struct",
        "fields": {
          "id": {"type": "string"},
          "values": {"type": "list", "valueType": "float"},
          "metadata": {"type": "map", "keyType": "string", "valueType": "any"}
        }
      }
    }
  }
}
```

5. **IPLD Schema for Knowledge Graph Nodes**:
```json
{
  "type": "struct",
  "fields": {
    "id": {"type": "string"},
    "type": {"type": "string"},
    "properties": {"type": "map", "keyType": "string", "valueType": "any"},
    "relationships": {
      "type": "list",
      "valueType": {
        "type": "struct",
        "fields": {
          "type": {"type": "string"},
          "target": {"type": "link"},
          "properties": {"type": "map", "keyType": "string", "valueType": "any"}
        }
      }
    }
  }
}
```

### Practical GraphRAG Example with LLM Integration

Here's a practical example of using the GraphRAG system with a large language model:

```python
import torch
from transformers import AutoTokenizer, AutoModel
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.graph_rag import IPLDGraphRAG

# Initialize components
ipfs = IPFSKit(role="worker")  # Use worker role for processing capabilities
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
embedding_model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
graph_rag = IPLDGraphRAG(ipfs_client=ipfs)

# 1. Create a knowledge graph with vector-enabled nodes
def add_document_to_graph(doc_text, doc_metadata):
    """Process a document and add it to the knowledge graph with vector embeddings."""
    # Generate embedding for the document
    inputs = tokenizer(doc_text, padding=True, truncation=True, return_tensors="pt")
    with torch.no_grad():
        outputs = embedding_model(**inputs)
    embeddings = mean_pooling(outputs, inputs['attention_mask'])
    embedding_vector = embeddings[0].numpy()  # Get the vector
    
    # Create document entity in graph with vector
    doc_id = f"doc_{uuid.uuid4()}"
    graph_rag.add_entity(
        entity_id=doc_id,
        properties={
            "type": "document",
            "text": doc_text,
            "title": doc_metadata.get("title", ""),
            "source": doc_metadata.get("source", ""),
            "created_at": doc_metadata.get("created_at", time.time())
        },
        vector=embedding_vector
    )
    
    # Extract concepts and create relationships
    concepts = extract_key_concepts(doc_text)  # Custom extraction function
    for concept in concepts:
        # Create or get concept entity
        concept_id = f"concept_{slugify(concept)}"
        if not graph_rag.get_entity(concept_id):
            graph_rag.add_entity(
                entity_id=concept_id,
                properties={"type": "concept", "name": concept}
            )
        
        # Link document to concept
        graph_rag.add_relationship(
            from_entity=doc_id,
            to_entity=concept_id,
            relationship_type="mentions",
            properties={"confidence": 0.85}
        )
    
    return doc_id

# 2. Perform hybrid search combining vector similarity and graph traversal
def query_knowledge_graph(query_text, top_k=5):
    """Retrieve relevant information using hybrid vector+graph search."""
    # Generate embedding for the query
    inputs = tokenizer(query_text, padding=True, truncation=True, return_tensors="pt")
    with torch.no_grad():
        outputs = embedding_model(**inputs)
    query_embedding = mean_pooling(outputs, inputs['attention_mask'])
    query_vector = query_embedding[0].numpy()
    
    # Perform hybrid search with 2-hop graph exploration
    results = graph_rag.graph_vector_search(
        query_vector=query_vector,
        hop_count=2,
        top_k=top_k
    )
    
    # Extract and format the results
    formatted_results = []
    for result in results:
        entity = graph_rag.get_entity(result["entity_id"])
        formatted_results.append({
            "id": result["entity_id"],
            "score": result["score"],
            "properties": entity["properties"],
            "path": result["path"],  # The graph traversal path
            "distance": result["distance"]  # Graph distance (hops)
        })
    
    return formatted_results

# Helper function for embedding generation
def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

# 3. Use the retrieved context with an LLM
def answer_with_rag(query, llm_client):
    """Generate an answer using retrieved context from the knowledge graph."""
    # Retrieve relevant context
    context_items = query_knowledge_graph(query)
    
    # Format context for the LLM
    context_text = "\n\n".join([
        f"Document: {item['properties'].get('title', 'Untitled')}\n"
        f"Content: {item['properties'].get('text', '')[:500]}...\n"
        f"Relevance: {item['score']:.2f}"
        for item in context_items
    ])
    
    # Build prompt with context
    prompt = f"""Answer the following question based on the provided context:

Context:
{context_text}

Question: {query}

Answer:"""
    
    # Get response from LLM
    response = llm_client.generate_text(prompt)
    
    return {
        "answer": response,
        "sources": [item["id"] for item in context_items],
        "context_used": context_text
    }
```


This example demonstrates how to:
1. Add documents to a knowledge graph with vector embeddings
2. Create relationships between entities based on content analysis
3. Perform hybrid retrieval combining vector similarity and graph traversal
4. Use the retrieved context with an LLM to answer queries

The GraphRAG approach provides more context-aware and relationship-informed retrieval compared to traditional vector-only approaches, enabling more accurate and explanatory responses from language models.

## Technology Selection Guidelines

### Choosing the Right Technology

| Use case | Best choice |
|----------|-------------|
| Large binary or tabular data | mmap or Arrow |
| Cross-language IPC (no overhead) | Arrow C Data Interface |
| Multiple processes, same machine | mmap / Arrow |
| Flexible, decoupled architecture | Queues / Message Passing |
| Network-distributed components | gRPC / HTTP |
| Peer-to-peer communication | libp2p_py (see `/docs/libp2p_docs/content/concepts/fundamentals/`) |
| Decentralized content routing | libp2p_py + DHT (see `/docs/libp2p_docs/content/concepts/discovery-routing/`) |
| Self-organizing networks | libp2p_py (see `/docs/libp2p_docs/content/concepts/pubsub/`) |
| Content-addressed data transfer | libp2p_py + IPLD (see `/docs/libp2p_docs/content/concepts/fundamentals/overview.md`) |
| Direct CID sharing between peers | libp2p_py + custom protocols (see `/docs/libp2p_docs/content/guides/getting-started/`) |
| Vector similarity search | FAISS + Arrow |
| Graph data and traversals | IPLD + custom indexing |
| Hybrid search (vectors + graphs) | GraphRAG with IPLD storage |

## Troubleshooting

### Common IPFS Issues

#### Daemon Issues
| Issue | Diagnosis | Resolution |
|-------|-----------|------------|
| Daemon won't start | Check logs, port conflicts | `ipfs daemon --debug` or check for process using port 5001 |
| High CPU usage | Analyze peer connections, DHT activity | Limit connections with `Swarm.ConnMgr` settings |
| High memory usage | Check pinned content, DHT table size | Adjust `Datastore.StorageMax`, run garbage collection |
| Peer connection issues | Check network configuration | Verify port forwarding, adjust bootstrap list |

#### API Communication Issues
| Issue | Diagnosis | Resolution |
|-------|-----------|------------|
| API connection refused | Check daemon status, endpoint config | Verify daemon is running, check API config in `~/.ipfs/config` |
| CORS errors | API security restrictions | Add origins to `API.HTTPHeaders.Access-Control-Allow-Origin` |
| Socket errors | Check socket permissions | Verify Unix socket path permissions, file exists |
| Authentication failures | API credential issues | Check `API.Authorizations` configuration |

#### Content Management Issues
| Issue | Diagnosis | Resolution |
|-------|-----------|------------|
| Content not found | Check pin status, network propagation | Pin content, connect to peers with content |
| Slow content retrieval | Network issues, DHT resolution | Use direct peer connections, ensure content is pinned |
| Failed garbage collection | Pin status issues | Check pinning status with `ipfs pin ls` |
| Storage space low | Too much pinned content | Adjust `Datastore.StorageMax`, unpin unused content |

### Debugging Commands

#### Common Debug Commands
```bash
# Check IPFS version
ipfs version

# Get node ID and addresses
ipfs id

# Verify daemon status
systemctl status ipfs

# Check daemon logs
journalctl -u ipfs -f

# Inspect configuration
ipfs config show

# Check connectivity
ipfs swarm peers

# Test API connectivity
curl -X POST "http://127.0.0.1:5001/api/v0/id"

# Test Unix socket connectivity
curl --unix-socket /path/to/ipfs.sock -X POST "http://localhost/api/v0/id"

# Get diagnostic information
ipfs diag cmds
ipfs diag sys
```

#### Configuration Backups
Always back up your IPFS configuration before making changes:

```bash
# Backup config
cp -r ~/.ipfs ~/.ipfs.backup

# Restore config
rm -rf ~/.ipfs
cp -r ~/.ipfs.backup ~/.ipfs
```

For more detailed troubleshooting, refer to the `/docs/ipfs-docs/docs/how-to/troubleshooting.md` guide.

## 9. Documentation Resources

### IPFS Cluster Documentation
The project includes IPFS Cluster documentation in `/docs/ipfs_cluster/`, which provides comprehensive information about IPFS Cluster's architecture and capabilities:

- **Architecture Overview** (`/docs/ipfs_cluster/content/documentation/deployment/architecture.md`): Explains the key components of IPFS Cluster
  - Three main binaries: `ipfs-cluster-service`, `ipfs-cluster-ctl`, and `ipfs-cluster-follow`
  - Cluster peers form a separate libp2p private network secured by a shared secret
  - Two consensus implementations available: CRDT-based (recommended) and Raft-based

- **Deployment Guides** (`/docs/ipfs_cluster/content/documentation/deployment/`): 
  - Setup procedures for various cluster configurations
  - Bootstrap and automated deployment options
  - Security considerations for production deployments

- **Reference Documentation** (`/docs/ipfs_cluster/content/documentation/reference/`):
  - Service API specifications
  - Configuration parameters and options
  - Control tool commands and usage
  - Proxy endpoints

- **Collaborative Clusters** (`/docs/ipfs_cluster/content/documentation/collaborative/`):
  - Setting up and joining collaborative clusters
  - Follower node configuration

- **Guides** (`/docs/ipfs_cluster/content/documentation/guides/`):
  - Consensus mechanisms (CRDT vs Raft)
  - Pinning strategies and management
  - Monitoring and metrics collection
  - Troubleshooting cluster issues
  - Security hardening recommendations

IPFS Cluster enables multiple IPFS nodes to coordinate and replicate content, providing a distributed pinning system that ensures high availability of critical content across a network of IPFS nodes.

### Storacha/W3 Specifications
The project includes Web3.Storage (Storacha) specifications in `/docs/storacha_specs/`, which details the W3UP protocol and associated subsystems:

- **Core Capabilities** (`/docs/storacha_specs/w3-store.md`, `/docs/storacha_specs/w3-upload.md`):
  - Content storage via CAR (Content Archive) files
  - Upload management for content DAGs
  - IPLD-based data structures

- **Authorization System** (`/docs/storacha_specs/w3-ucan.md`):
  - UCAN (User Controlled Authorization Networks) implementation
  - Capability-based security model
  - Delegation patterns for space/content sharing

- **Storage Management** (`/docs/storacha_specs/w3-store.md`):
  - Adding, removing, and listing content archives
  - Content addressing via CIDs
  - Pagination and cursor-based retrieval

- **Filecoin Integration** (`/docs/storacha_specs/w3-filecoin.md`):
  - Verifiable content deals with Filecoin network
  - Deal tracking and aggregation
  - Storage provider interactions

- **Account & Session Management** (`/docs/storacha_specs/w3-account.md`, `/docs/storacha_specs/w3-session.md`):
  - DID-based identity system
  - Delegated capabilities via email verification
  - Session management and recovery procedures

- **Rate Limiting & Administration** (`/docs/storacha_specs/w3-rate-limit.md`, `/docs/storacha_specs/w3-admin.md`):
  - Usage throttling mechanisms
  - Administrative capabilities for service providers

The W3UP/Storacha specifications define protocols for content-addressed storage with a focus on capability-based security, enabling fine-grained access control and delegation while leveraging both IPFS for content addressing and Filecoin for long-term storage guarantees.

### libp2p Documentation
The project includes comprehensive libp2p documentation in `/docs/libp2p_docs/`, which details the peer-to-peer networking stack that powers IPFS:

- **Core Networking Concepts** (`/docs/libp2p_docs/content/concepts/fundamentals/`):
  - `addressing.md`: Multiaddress protocol for network addressing
  - `peers.md`: Peer identity and connection management
  - `protocols.md`: Protocol negotiation and handshakes
  - `dht.md`: Distributed Hash Table for content routing
  - `overview.md`: High-level architectural overview

- **Transport Protocols** (`/docs/libp2p_docs/content/concepts/transports/`):
  - `overview.md`: Transport protocol abstraction
  - `quic.md`: QUIC protocol implementation
  - `webrtc.md`: WebRTC for browser-based P2P connections
  - `webtransport.md`: WebTransport protocol support
  - `listen-and-dial.md`: Connection establishment patterns

- **NAT Traversal** (`/docs/libp2p_docs/content/concepts/nat/`):
  - `overview.md`: NAT challenges in P2P networking
  - `hole-punching.md`: Direct connection establishment techniques
  - `circuit-relay.md`: Relay-based connectivity
  - `autonat.md`: NAT detection and classification
  - `dcutr.md`: Direct connection upgrade through relay

- **Publish/Subscribe** (`/docs/libp2p_docs/content/concepts/pubsub/`):
  - `overview.md`: Gossipsub protocol for efficient message distribution
  - Illustrations of message propagation patterns

- **Discovery and Routing** (`/docs/libp2p_docs/content/concepts/discovery-routing/`):
  - `overview.md`: Peer discovery mechanisms
  - `kaddht.md`: Kademlia DHT implementation
  - `mDNS.md`: Local network peer discovery
  - `rendezvous.md`: Peer discovery through rendezvous points

- **Getting Started Guides** (`/docs/libp2p_docs/content/guides/getting-started/`):
  - Language-specific implementation guides (Go, JavaScript, Rust, Nim)
  - `webrtc.md`: Browser-based P2P networking guide

The libp2p documentation is particularly relevant for implementing the role-based architecture (master/worker/leecher) outlined in this guide, as it provides the networking foundation for peer discovery, direct connections, and distributed content routing. The publish/subscribe mechanism is essential for coordinating distributed task processing across nodes.

## Documentation Relevance to Development Roadmap

### Tiered Storage with Adaptive Replacement Cache Implementation

The documentation resources provide key insights for implementing the planned Tiered Storage with Adaptive Replacement Cache (ARC) system:

#### Relevant IPFS Cluster Documentation
- **Content Replication Strategies** (`/docs/ipfs_cluster/content/documentation/guides/pinning.md`): 
  - Leverage the pin management documentation to understand how IPFS Cluster handles content replication
  - Useful for implementing tier #4 (IPFS cluster distributed redundancy) in the hierarchical storage system
  - ⭐ **Key Insight**: Study how the cluster's pinning status tracking can be integrated with cache tier migration decisions

- **Datastore Configuration** (`/docs/ipfs_cluster/content/documentation/guides/datastore.md`):
  - Contains information about configuring persistent storage for IPFS Cluster
  - Provides patterns for implementing the local disk cache tier (tier #2)
  - ⭐ **Key Insight**: Examine the datastore configuration patterns for optimizing persistent cache storage

#### Relevant Storacha/W3 Documentation
- **Content Archive Management** (`/docs/storacha_specs/w3-store.md`):
  - Detailed protocol for managing Content Archive (CAR) files 
  - Essential for implementing tier #6 (Storacha) of the hierarchical storage
  - Contains request/response patterns for store/add, store/get, store/list operations
  - ⭐ **Key Insight**: The `StoreAdd` and `StoreGet` capabilities provide patterns for efficient content transfer between tiers

- **Filecoin Integration** (`/docs/storacha_specs/w3-filecoin.md`):
  - Provides protocols for interacting with Filecoin storage
  - Critical for implementing tier #7 (Filecoin) for cold storage with highest durability
  - ⭐ **Key Insight**: Study the deal-making process to optimize when/how to move content to the most durable but highest-latency tier

### Implementation Guidelines for ARC

When implementing the `TieredCacheManager` class (as outlined in the Development Roadmap), consider these specific documentation-informed approaches:

1. **Cache Admission Policy**:
   - The IPFS Cluster documentation on metrics collection (`/docs/ipfs_cluster/content/documentation/guides/metrics.md`) provides insights for developing cache admission heuristics
   - Use similar metrics to determine which content should enter higher cache tiers

2. **Heat Tracking Implementation**:
   - Study the Storacha protocol's timestamp handling in API results
   - Implement similar timestamp tracking in the cache's heat scoring formula
   - Consider tracking both frequency (access count) and recency (time decay function)

3. **Tier Migration Strategy**:
   - Review the IPFS pinning protocols to understand content persistence guarantees
   - Implement state transitions between tiers based on observed access patterns
   - Leverage the CAR file specifications from Storacha for efficient content packaging during tier migration

4. **Eviction Policy**:
   - Implement a true ARC algorithm with four internal queues (T1, B1, T2, B2)
   - Track both recency and frequency combined with content size for optimal space utilization
   - Use the "heat score" formula as shown in the `TieredCacheManager` implementation to prioritize eviction targets

The comprehensive documentation in both IPFS Cluster and Storacha specifications provides the necessary protocol details to implement an efficient tiered storage system with sophisticated caching policies leveraging the best aspects of both technologies.

#### Relevant libp2p Documentation
- **Peer Discovery Mechanisms** (`/docs/libp2p_docs/content/concepts/discovery-routing/overview.md`):
  - Provides patterns for discovering peer nodes across the network
  - Essential for implementing the dynamic peer discovery in the distributed cache system
  - ⭐ **Key Insight**: The peer discovery mechanisms can be used to find nearby cache nodes with desired content

- **Publish/Subscribe System** (`/docs/libp2p_docs/content/concepts/pubsub/overview.md`):
  - Details the publish/subscribe messaging system used for peer coordination
  - Critical for implementing cache invalidation and update notifications
  - ⭐ **Key Insight**: The gossipsub protocol enables efficient broadcast of cache state changes to all relevant nodes

## Project Structure and Organization

### Directory Layout
```
ipfs_kit_py/            # Main package directory
  ├── __init__.py       # Package initialization
  ├── ipfs_kit.py       # Main orchestrator class
  ├── ipfs.py           # Low-level IPFS (Kubo) operations
  ├── ipfs_multiformats.py  # CID and multihash handling
  ├── s3_kit.py         # S3-compatible storage operations
  ├── storacha_kit.py   # Web3.Storage integration
  ├── ipfs_cluster_service.py  # Cluster service management (master role)
  ├── ipfs_cluster_ctl.py      # Cluster control operations
  ├── ipfs_cluster_follow.py   # Follower mode operations (worker role)
  ├── ipget.py          # Content retrieval utility
  ├── install_ipfs.py   # Binary installation utilities
  └── bin/              # IPFS binaries directory
      ├── ipfs          # Kubo binary (platform-specific)
      ├── ipfs-cluster-service
      ├── ipfs-cluster-ctl
      └── ipfs-cluster-follow
test/                   # Test directory
  ├── __init__.py
  ├── test.py           # Test runner
  ├── test_ipfs_kit.py  # Tests for main orchestrator
  ├── test_storacha_kit.py  # Tests for Web3.Storage integration
  └── test_s3_kit.py    # Tests for S3 storage
docs/                   # Documentation
  ├── ipfs-docs/        # Core IPFS documentation
  ├── ipfs_cluster/     # IPFS Cluster documentation
  ├── libp2p_docs/      # libp2p networking documentation
  └── storacha_specs/   # Web3.Storage specifications
```

### Component Relationships
- **ipfs_kit.py**: Central orchestrator that coordinates other components
- **ipfs.py**: Direct interaction with IPFS daemon (via HTTP API and Unix socket)
- **ipfs_cluster_*.py**: Optional cluster components activated in master/worker roles
- **s3_kit.py** and **storacha_kit.py**: Alternative storage backends

### Versioning Strategy

The ipfs_kit_py package follows Semantic Versioning (SemVer):

- **MAJOR version** increments for incompatible API changes
- **MINOR version** increments for new functionality in a backward-compatible manner
- **PATCH version** increments for backward-compatible bug fixes

#### Compatibility Guarantees

| Component | Compatibility Promise |
|-----------|----------------------|
| Public API | Backward compatible within same MAJOR version |
| Configuration | May require updates within MINOR versions |
| Internal Implementation | May change at any time |
| Role-based Features | May require reconfiguration across MINOR versions |

#### Upgrading Guidelines
- Always read the CHANGELOG.md before upgrading
- Test upgrades in non-production environments first
- MAJOR version upgrades require careful migration planning
- Configuration files should be version-controlled

### Implementation Dependencies and Imports

When implementing the Adaptive Replacement Cache and other components, make sure to include these necessary imports:

```python
# Standard library imports
import os
import time
import math
import uuid
import mmap
import queue
import random
import logging
import tempfile
import threading
from typing import Dict, List, Optional, Union, Any

# Third-party imports
import numpy as np
import requests
import requests_unixsocket  # For Unix socket support
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
from pyarrow.dataset import dataset
import faiss  # For vector search
import networkx as nx  # For knowledge graph operations
```

Additionally, ensure you implement these referenced but undefined methods:

1. `_schedule_persist()` in the `IPLDGraphDB` class - used to schedule persistence of indexes
2. `_get_peer_list()` in the `IPFSArrowIndex` class - used to discover peers for synchronization
3. Create a proper logger instead of using undefined `logger` references:
   ```python
   # Initialize logger
   logger = logging.getLogger(__name__)
   ```

### Connection with Implementation Code

The role-based architecture (master/worker/leecher) described in this document should align with the actual implementation in `ipfs_kit.py`. When implementing these concepts:

1. Ensure the role handling in `ipfs_kit.py` properly differentiates between:
   - Master nodes: Full orchestration and coordination
   - Worker nodes: Processing focus with cluster participation
   - Leecher nodes: Lightweight consumption with minimal resource contribution

2. Verify that Unix socket support is properly implemented for high-performance local operations on Linux systems.

3. Ensure Arrow schema definitions remain consistent throughout the codebase and match the definitions in this document.


## Containerization and Kubernetes Deployment

### Docker Containerization

The ipfs_kit_py library can be containerized to ensure consistent deployment across environments. Here is a sample Dockerfile:

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    jq \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY . /app/

# Install python dependencies
RUN pip install -e .

# Create necessary directories
RUN mkdir -p /data/ipfs /data/ipfs-cluster

# Set environment variables
ENV IPFS_PATH=/data/ipfs
ENV IPFS_CLUSTER_PATH=/data/ipfs-cluster

# Expose ports for IPFS daemon, API, gateway, and Cluster
EXPOSE 4001 5001 8080 9094 9095 9096

# Entry point script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
# Default command starts the daemon based on role
CMD ["master"]
```

### Kubernetes Deployment

For production deployments, a Kubernetes StatefulSet is recommended to ensure stable network identities and persistent storage for IPFS nodes.

#### ConfigMap for ipfs_kit_py:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ipfs-kit-config
data:
  config.yaml: |
    role: master  # Can be master, worker, or leecher
    resources:
      max_memory: 4G
      max_storage: 500G
    bootstrap_nodes:
      - /dns4/ipfs-bootstrap-1/tcp/4001/p2p/QmNode1
      - /dns4/ipfs-bootstrap-2/tcp/4001/p2p/QmNode2
    ipfs_api_port: 5001
    gateway_port: 8080
```

#### StatefulSet for Master Node:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ipfs-master
spec:
  serviceName: "ipfs-master"
  replicas: 1  # Only one master per cluster
  selector:
    matchLabels:
      app: ipfs-master
  template:
    metadata:
      labels:
        app: ipfs-master
    spec:
      containers:
      - name: ipfs-master
        image: ipfs-kit-py:latest
        args: ["master"]
        ports:
        - containerPort: 4001
          name: swarm
        - containerPort: 5001
          name: api
        - containerPort: 8080
          name: gateway
        - containerPort: 9096
          name: cluster
        env:
        - name: IPFS_PATH
          value: /data/ipfs
        - name: IPFS_CLUSTER_PATH
          value: /data/ipfs-cluster
        volumeMounts:
        - name: ipfs-storage
          mountPath: /data
        - name: config-volume
          mountPath: /app/config
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
  volumeClaimTemplates:
  - metadata:
      name: ipfs-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 500Gi
```

#### Deployment for Worker Nodes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ipfs-worker
spec:
  replicas: 3  # Adjust based on processing needs
  selector:
    matchLabels:
      app: ipfs-worker
  template:
    metadata:
      labels:
        app: ipfs-worker
    spec:
      containers:
      - name: ipfs-worker
        image: ipfs-kit-py:latest
        args: ["worker", "--master=ipfs-master:9096"]
        ports:
        - containerPort: 4001
          name: swarm
        - containerPort: 5001
          name: api
        env:
        - name: IPFS_PATH
          value: /data/ipfs
        - name: IPFS_CLUSTER_PATH
          value: /data/ipfs-cluster
        volumeMounts:
        - name: ipfs-worker-storage
          mountPath: /data
        - name: config-volume
          mountPath: /app/config
        resources:
          requests:
            memory: "1Gi"
            cpu: "1"
          limits:
            memory: "2Gi"
            cpu: "2"
      volumes:
      - name: config-volume
        configMap:
          name: ipfs-kit-config
      - name: ipfs-worker-storage
        persistentVolumeClaim:
          claimName: ipfs-worker-storage
```


#### Deployment for Leecher Nodes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ipfs-worker
spec:
  replicas: 1  # Adjust based on processing needs
  selector:
    matchLabels:
      app: ipfs-worker
  template:
    metadata:
      labels:
        app: ipfs-worker
    spec:
      containers:
      - name: ipfs-worker
        image: ipfs-kit-py:latest
        args: ["leecher", "--master=ipfs-master:9096"]
        ports:
        - containerPort: 4001
          name: swarm
        - containerPort: 5001
          name: api
        env:
        - name: IPFS_PATH
          value: /data/ipfs
        - name: IPFS_CLUSTER_PATH
          value: /data/ipfs-cluster
        volumeMounts:
        - name: ipfs-worker-storage
          mountPath: /data
        - name: config-volume
          mountPath: /app/config
        resources:
          requests:
            memory: "1Gi"
            cpu: "1"
          limits:
            memory: "2Gi"
            cpu: "2"
      volumes:
      - name: config-volume
        configMap:
          name: ipfs-kit-config
      - name: ipfs-leecher-storage
        persistentVolumeClaim:
          claimName: ipfs-leecher-storage
```


#### Services for Network Discovery:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ipfs-master
spec:
  selector:
    app: ipfs-master
  ports:
  - name: swarm
    port: 4001
    targetPort: 4001
  - name: api
    port: 5001
    targetPort: 5001
  - name: gateway
    port: 8080
    targetPort: 8080
  - name: cluster
    port: 9096
    targetPort: 9096
```

### Scaling Considerations

When deploying to Kubernetes:

1. **Master Node**: Deploy as StatefulSet with a single replica for cluster coordination.
2. **Worker Nodes**: Deploy as a Deployment with multiple replicas for processing tasks.
3. **Storage**: Use appropriate storage classes for different node types:
   - Master: High-capacity persistent storage
   - Workers: Faster, lower-capacity storage optimized for processing
   - Consider using local SSDs for the in-memory cache tier
4. **Network Policies**: Implement network policies to secure the IPFS swarm and cluster communications
5. **Resource Quotas**: Set appropriate CPU and memory limits based on workload characteristics
6. **Autoscaling**: Configure Horizontal Pod Autoscaler for worker nodes based on processing queue length

### Testing in Containerized Environments

To test the ipfs_kit_py implementation in containerized environments:

```bash
# Build the Docker image
docker build -t ipfs-kit-py:test .

# Run tests in container
docker run --rm ipfs-kit-py:test python -m test.test

# Start a master node
docker run -d --name ipfs-master -p 5001:5001 -p 8080:8080 ipfs-kit-py:test master

# Start a worker node connected to master
docker run -d --name ipfs-worker --link ipfs-master  ipfs-kit-py:test worker --master=ipfs-master:9096

# Start a leecher node connected to master
docker run -d --name ipfs-leecher --link ipfs-master  ipfs-kit-py:test worker --master=ipfs-master:9096

# Run a test against the containerized instance
docker run --rm --link ipfs-master -e IPFS_API_URL=http://ipfs-master:5001 ipfs-kit-py:test python -m test.test_distributed

```