import anyio
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Configure logger
logger = logging.getLogger(__name__)

# Import error handling utilities
try:
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
except ImportError:
    # For standalone testing
    from error import (
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


class NodeRole(Enum):
    """Enumeration of node roles in the cluster."""

    MASTER = "master"
    WORKER = "worker"
    LEECHER = "leecher"

    @staticmethod
    def from_str(role_str: str) -> "NodeRole":
        """Convert string to NodeRole enum."""
        role_str = role_str.lower()
        if role_str == "master":
            return NodeRole.MASTER
        elif role_str == "worker":
            return NodeRole.WORKER
        elif role_str == "leecher":
            return NodeRole.LEECHER
        else:
            raise ValueError(f"Invalid role: {role_str}")


class NodeStatus(Enum):
    """Enumeration of node statuses in the cluster."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"  # Partial failure
    STARTING = "starting"  # In the process of starting up
    STOPPING = "stopping"  # In the process of shutting down
    UNKNOWN = "unknown"  # Status cannot be determined


class TaskStatus(Enum):
    """Enumeration of task statuses."""

    PENDING = "pending"  # Waiting to be assigned
    ASSIGNED = "assigned"  # Assigned to a worker but not started
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed to complete
    CANCELLED = "cancelled"  # Cancelled before completion
    TIMEOUT = "timeout"  # Timed out before completion


@dataclass
class NodeResources:
    """Class for tracking a node's resources."""

    cpu_cores: int = 0
    memory_mb: int = 0
    disk_space_mb: int = 0
    bandwidth_mbps: int = 0
    gpu_memory_mb: int = 0

    # Current usage (as percentages)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    bandwidth_usage: float = 0.0
    gpu_usage: float = 0.0

    # Maximum allowed usage (as percentages)
    max_cpu_usage: float = 80.0
    max_memory_usage: float = 80.0
    max_disk_usage: float = 90.0
    max_bandwidth_usage: float = 80.0
    max_gpu_usage: float = 80.0

    def has_available_resources(self, required_resources: Dict[str, float]) -> bool:
        """Check if the node has available resources to handle a task."""
        # Check CPU availability
        if "cpu_cores" in required_resources and self.cpu_cores > 0:
            available_cores = self.cpu_cores * (1.0 - self.cpu_usage / 100.0)
            if available_cores < required_resources["cpu_cores"]:
                return False

        # Check memory availability
        if "memory_mb" in required_resources and self.memory_mb > 0:
            available_memory = self.memory_mb * (1.0 - self.memory_usage / 100.0)
            if available_memory < required_resources["memory_mb"]:
                return False

        # Check disk availability
        if "disk_space_mb" in required_resources and self.disk_space_mb > 0:
            available_disk = self.disk_space_mb * (1.0 - self.disk_usage / 100.0)
            if available_disk < required_resources["disk_space_mb"]:
                return False

        # Check GPU availability
        if "gpu_memory_mb" in required_resources and self.gpu_memory_mb > 0:
            available_gpu = self.gpu_memory_mb * (1.0 - self.gpu_usage / 100.0)
            if available_gpu < required_resources["gpu_memory_mb"]:
                return False

        return True

    def get_resource_score(self) -> float:
        """Calculate a resource availability score (0-100)."""
        # Higher is better (more available resources)
        scores = []

        if self.cpu_cores > 0:
            scores.append(100.0 - self.cpu_usage)

        if self.memory_mb > 0:
            scores.append(100.0 - self.memory_usage)

        if self.disk_space_mb > 0:
            scores.append(100.0 - self.disk_usage)

        if self.gpu_memory_mb > 0:
            scores.append(100.0 - self.gpu_usage)

        # Average the scores, or return 0 if no resources reported
        return sum(scores) / len(scores) if scores else 0


@dataclass
class NodeInfo:
    """Class for tracking information about a node in the cluster."""

    id: str
    peer_id: str
    role: NodeRole
    status: NodeStatus = NodeStatus.UNKNOWN
    resources: NodeResources = field(default_factory=NodeResources)
    address: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_seen: float = field(default_factory=time.time)
    assigned_tasks: Set[str] = field(default_factory=set)
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the node info to a dictionary."""
        result = {
            "id": self.id,
            "peer_id": self.peer_id,
            "role": self.role.value,
            "status": self.status.value,
            "resources": asdict(self.resources),
            "address": self.address,
            "metadata": self.metadata,
            "last_seen": self.last_seen,
            "assigned_tasks": list(self.assigned_tasks),
            "capabilities": self.capabilities,
        }
        return result

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "NodeInfo":
        """Create a NodeInfo object from a dictionary."""
        # Convert role and status strings to enums
        role = NodeRole.from_str(data["role"])
        status = NodeStatus(data["status"])

        # Convert resources dict to NodeResources object
        resources_data = data.get("resources", {})
        resources = NodeResources(**resources_data)

        # Convert assigned_tasks to a set
        assigned_tasks = set(data.get("assigned_tasks", []))

        return NodeInfo(
            id=data["id"],
            peer_id=data["peer_id"],
            role=role,
            status=status,
            resources=resources,
            address=data.get("address", ""),
            metadata=data.get("metadata", {}),
            last_seen=data.get("last_seen", time.time()),
            assigned_tasks=assigned_tasks,
            capabilities=data.get("capabilities", []),
        )

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update the node info from a dictionary."""
        if "status" in data:
            self.status = NodeStatus(data["status"])

        if "resources" in data:
            # Update individual resource fields rather than replacing the whole object
            for key, value in data["resources"].items():
                if hasattr(self.resources, key):
                    setattr(self.resources, key, value)

        if "address" in data:
            self.address = data["address"]

        if "metadata" in data:
            self.metadata.update(data["metadata"])

        if "last_seen" in data:
            self.last_seen = data["last_seen"]

        if "assigned_tasks" in data:
            self.assigned_tasks = set(data["assigned_tasks"])

        if "capabilities" in data:
            self.capabilities = data["capabilities"]


@dataclass
class Task:
    """Class representing a task in the distributed task system."""

    id: str
    type: str
    parameters: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    timeout: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    priority: int = 0  # Higher values have higher priority
    required_resources: Dict[str, float] = field(default_factory=dict)
    required_capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the task to a dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "parameters": self.parameters,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "timeout": self.timeout,
            "result": self.result,
            "error": self.error,
            "priority": self.priority,
            "required_resources": self.required_resources,
            "required_capabilities": self.required_capabilities,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Task":
        """Create a Task object from a dictionary."""
        # Convert status string to enum
        status = TaskStatus(data["status"])

        return Task(
            id=data["id"],
            type=data["type"],
            parameters=data["parameters"],
            status=status,
            assigned_to=data.get("assigned_to"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            timeout=data.get("timeout"),
            result=data.get("result"),
            error=data.get("error"),
            priority=data.get("priority", 0),
            required_resources=data.get("required_resources", {}),
            required_capabilities=data.get("required_capabilities", []),
        )

    def update_status(self, status: TaskStatus) -> None:
        """Update the task status and updated_at timestamp."""
        self.status = status
        self.updated_at = time.time()


class ClusterCoordinator:
    """Class for coordinating nodes and tasks in a distributed cluster."""

    def __init__(
        self,
        node_id: str,
        role: str = "worker",
        peer_id: str = None,
        config: Dict[str, Any] = None,
        cluster_id: str = None,
        is_master: bool = False,
        election_timeout: int = 30,
        leadership_callback: Callable = None,
        membership_manager=None,
    ):
        """Initialize the cluster coordinator.

        Args:
            node_id: Unique identifier for this node
            role: Role of this node ("master", "worker", or "leecher")
            peer_id: IPFS peer ID for this node
            config: Configuration parameters
            cluster_id: Identifier for the cluster
            is_master: Whether this node is a master
            election_timeout: Timeout for elections in seconds
            leadership_callback: Callback for leadership changes
            membership_manager: Manager for cluster membership
        """
        self.node_id = node_id
        self.role = NodeRole.from_str(role) if isinstance(role, str) else role
        self.peer_id = peer_id or f"QmDefault{node_id}"
        self.config = config or {}
        self.cluster_id = cluster_id or self.config.get("cluster_id", "default")
        self.is_master = is_master
        self.election_timeout = election_timeout
        self.leadership_callback = leadership_callback
        self.membership_manager = membership_manager
        self.current_leader = self.node_id if is_master else None
        self.cluster_peers = []

        # Node registry
        self.nodes: Dict[str, NodeInfo] = {}

        # Task registry and queues
        self.tasks: Dict[str, Task] = {}
        self.task_queue: Queue = Queue()
        self.results_queue: Queue = Queue()

        # State synchronization
        self.sync_interval = self.config.get("sync_interval", 30)  # seconds
        self.sync_thread = None
        self.running = False

        # Heartbeat and health checking
        self.heartbeat_interval = self.config.get("heartbeat_interval", 15)  # seconds
        self.heartbeat_thread = None
        self.node_timeout = self.config.get("node_timeout", 60)  # seconds

        # Task scheduling and execution
        self.scheduler_thread = None
        self.max_retries = self.config.get("max_task_retries", 3)

        # Topic names for pubsub
        self.cluster_topic = f"ipfs-cluster/{self.config.get('cluster_id', 'default')}"
        self.tasks_topic = f"{self.cluster_topic}/tasks"
        self.results_topic = f"{self.cluster_topic}/results"
        self.status_topic = f"{self.cluster_topic}/status"

        # Register this node
        self._register_self()

    def create_cluster(self, cluster_id: str) -> None:
        """Create a new cluster with this node as master.

        Args:
            cluster_id: Identifier for the new cluster
        """
        self.cluster_id = cluster_id
        self.is_master = True
        self.current_leader = self.node_id
        self.cluster_peers = []

        # Update configuration
        self.config["cluster_id"] = cluster_id

        # Re-register self with updated role/status
        self._register_self()

        logger.info(f"Created new cluster with ID: {cluster_id}")

    def _register_self(self) -> None:
        """Register this node in the node registry."""
        # Create NodeInfo for this node
        self_info = NodeInfo(
            id=self.node_id,
            peer_id=self.peer_id,
            role=self.role,
            status=NodeStatus.STARTING,
            address=self.config.get("address", ""),
            metadata=self.config.get("metadata", {}),
        )

        # Initialize resources
        resources_config = self.config.get("resources", {})
        if resources_config:
            self_info.resources = NodeResources(**resources_config)

        # Initialize capabilities
        self_info.capabilities = self.config.get("capabilities", [])

        # Add to registry
        self.nodes[self.node_id] = self_info

    def start(self) -> None:
        """Start the cluster coordinator services."""
        if self.running:
            logger.warning("Cluster coordinator is already running")
            return

        self.running = True

        # Start threads based on role
        if self.role == NodeRole.MASTER:
            # Masters handle synchronization, health checking, and task scheduling
            self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()

            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()

            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()

        elif self.role == NodeRole.WORKER:
            # Workers handle heartbeats and task execution
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()

            # Start task handler
            self.scheduler_thread = threading.Thread(target=self._task_handler_loop, daemon=True)
            self.scheduler_thread.start()

        # Update node status
        self.nodes[self.node_id].status = NodeStatus.ONLINE
        logger.info(f"Cluster coordinator started with role: {self.role.value}")

    def stop(self) -> None:
        """Stop the cluster coordinator services."""
        if not self.running:
            logger.warning("Cluster coordinator is not running")
            return

        # Signal threads to stop
        self.running = False

        # Wait for threads to complete (with timeout)
        threads = []
        if self.sync_thread and self.sync_thread.is_alive():
            threads.append(self.sync_thread)

        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            threads.append(self.heartbeat_thread)

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            threads.append(self.scheduler_thread)

        # Update node status
        if self.node_id in self.nodes:
            self.nodes[self.node_id].status = NodeStatus.STOPPING

        # Wait for threads to complete
        for thread in threads:
            thread.join(timeout=2.0)

        # Final status update
        if self.node_id in self.nodes:
            self.nodes[self.node_id].status = NodeStatus.OFFLINE

        logger.info("Cluster coordinator stopped")

    def _heartbeat_loop(self) -> None:
        """Thread function for sending regular heartbeats."""
        while self.running:
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {str(e)}")

            # Wait for next interval
            time.sleep(self.heartbeat_interval)

    def _send_heartbeat(self) -> None:
        """Send a heartbeat message to update node status."""
        # Get the current resource utilization
        resources = self._get_resource_usage()

        # Create heartbeat message
        heartbeat = {
            "type": "heartbeat",
            "node_id": self.node_id,
            "peer_id": self.peer_id,
            "role": self.role.value,
            "timestamp": time.time(),
            "resources": asdict(resources),
            "status": self.nodes[self.node_id].status.value,
            "assigned_tasks": list(self.nodes[self.node_id].assigned_tasks),
        }

        # TODO: Add message signature for authentication

        # Publish to status topic (implementation depends on pubsub mechanism)
        self._publish_message(self.status_topic, heartbeat)

        # Update own node info
        if self.node_id in self.nodes:
            self.nodes[self.node_id].resources = resources
            self.nodes[self.node_id].last_seen = time.time()

    def _get_resource_usage(self) -> NodeResources:
        """Get current resource usage statistics."""
        # Start with existing resources
        resources = self.nodes[self.node_id].resources

        try:
            # Try to get actual system metrics
            import psutil

            # CPU usage
            resources.cpu_usage = psutil.cpu_percent(interval=0.1)

            # Memory usage
            memory = psutil.virtual_memory()
            resources.memory_usage = memory.percent
            if resources.memory_mb == 0:
                resources.memory_mb = memory.total // (1024 * 1024)

            # Disk usage
            disk = psutil.disk_usage("/")
            resources.disk_usage = disk.percent
            if resources.disk_space_mb == 0:
                resources.disk_space_mb = disk.total // (1024 * 1024)

            # Try to get GPU metrics if possible
            try:
                import gputil

                gpus = gputil.getGPUs()
                if gpus:
                    # Average across GPUs
                    gpu_usage = sum(gpu.load * 100 for gpu in gpus) / len(gpus)
                    gpu_memory = sum(gpu.memoryTotal for gpu in gpus)

                    resources.gpu_usage = gpu_usage
                    if resources.gpu_memory_mb == 0:
                        resources.gpu_memory_mb = gpu_memory
            except ImportError:
                # GPU utilities not available
                pass

        except ImportError:
            # psutil not available, use static values
            logger.warning("psutil not available, using static resource values")

        except Exception as e:
            logger.error(f"Error getting resource usage: {str(e)}")

        return resources

    def _sync_loop(self) -> None:
        """Thread function for synchronizing cluster state (master only)."""
        if self.role != NodeRole.MASTER:
            logger.warning("Sync loop should only run on master nodes")
            return

        while self.running:
            try:
                self._sync_cluster_state()
            except Exception as e:
                logger.error(f"Error in sync loop: {str(e)}")

            # Wait for next interval
            time.sleep(self.sync_interval)

    def _sync_cluster_state(self) -> None:
        """Synchronize cluster state with other nodes (master only)."""
        if self.role != NodeRole.MASTER:
            return

        # Check node health and timeout inactive nodes
        current_time = time.time()
        for node_id, node_info in list(self.nodes.items()):
            # Skip self
            if node_id == self.node_id:
                continue

            # Check if node has timed out
            if current_time - node_info.last_seen > self.node_timeout:
                # Node hasn't been seen recently
                if node_info.status not in (NodeStatus.OFFLINE, NodeStatus.UNKNOWN):
                    logger.warning(f"Node {node_id} timed out, marking as offline")
                    node_info.status = NodeStatus.OFFLINE

                    # Handle tasks assigned to this node
                    self._handle_node_failure(node_id)

        # Publish current cluster state (filtered for each role)
        self._publish_cluster_state()

    def _publish_cluster_state(self) -> None:
        """Publish current cluster state to all nodes."""
        # Create cluster state message
        state = {
            "type": "cluster_state",
            "timestamp": time.time(),
            "master_id": self.node_id,
            "nodes": {node_id: node_info.to_dict() for node_id, node_info in self.nodes.items()},
            "task_count": {
                "pending": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.PENDING
                ),
                "processing": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.PROCESSING
                ),
                "completed": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.COMPLETED
                ),
                "failed": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.FAILED
                ),
            },
        }

        # Publish to cluster topic
        self._publish_message(self.cluster_topic, state)

    def _handle_node_failure(self, node_id: str) -> None:
        """Handle failure of a node by reassigning its tasks."""
        # Find tasks assigned to this node
        reassigned_count = 0
        for task_id, task in self.tasks.items():
            if task.assigned_to == node_id and task.status in (
                TaskStatus.ASSIGNED,
                TaskStatus.PROCESSING,
            ):
                # Reset task to pending state
                task.update_status(TaskStatus.PENDING)
                task.assigned_to = None
                task.error = f"Node {node_id} failed or timed out"

                # Add back to queue with higher priority (to handle quickly)
                task.priority += 1
                self.task_queue.put(task)
                reassigned_count += 1

        # Clear assigned tasks for this node
        if node_id in self.nodes:
            self.nodes[node_id].assigned_tasks.clear()

        if reassigned_count > 0:
            logger.info(f"Reassigned {reassigned_count} tasks from failed node {node_id}")

    def _scheduler_loop(self) -> None:
        """Thread function for scheduling tasks (master only)."""
        if self.role != NodeRole.MASTER:
            logger.warning("Scheduler loop should only run on master nodes")
            return

        while self.running:
            try:
                # Check for completed tasks
                self._process_results()

                # Schedule pending tasks
                self._schedule_tasks()

                # Check for timed out tasks
                self._check_task_timeouts()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")

            # Brief sleep to prevent CPU spinning
            time.sleep(0.1)

    def _process_results(self) -> None:
        """Process task results from the results queue."""
        try:
            # Check for results without blocking
            while not self.results_queue.empty():
                result = self.results_queue.get_nowait()
                task_id = result.get("task_id")

                if task_id in self.tasks:
                    task = self.tasks[task_id]

                    # Update task with result
                    if result.get("success", False):
                        task.update_status(TaskStatus.COMPLETED)
                        task.result = result.get("data")
                    else:
                        task.update_status(TaskStatus.FAILED)
                        task.error = result.get("error", "Unknown error")

                        # Check if task should be retried
                        retry_count = task.parameters.get("retry_count", 0)
                        if retry_count < self.max_retries:
                            # Increment retry count and requeue
                            task.parameters["retry_count"] = retry_count + 1
                            task.update_status(TaskStatus.PENDING)
                            task.assigned_to = None
                            self.task_queue.put(task)
                            logger.info(
                                f"Requeued task {task_id} for retry ({retry_count + 1}/{self.max_retries})"
                            )

                    # Remove from assigned tasks if completed or failed
                    node_id = task.assigned_to
                    if node_id in self.nodes and task_id in self.nodes[node_id].assigned_tasks:
                        self.nodes[node_id].assigned_tasks.remove(task_id)
                        task.assigned_to = None

                self.results_queue.task_done()
        except Empty:
            pass
        except Exception as e:
            logger.error(f"Error processing results: {str(e)}")

    def _schedule_tasks(self) -> None:
        """Schedule pending tasks to available workers."""
        # Get eligible worker nodes (online and with worker role)
        workers = [
            node
            for node_id, node in self.nodes.items()
            if node.role == NodeRole.WORKER and node.status == NodeStatus.ONLINE
        ]

        if not workers:
            # No workers available
            return

        # Process task queue without blocking
        while not self.task_queue.empty():
            try:
                # Get task from queue
                task = self.task_queue.get_nowait()

                # Skip if task is no longer pending
                if task.status != TaskStatus.PENDING:
                    self.task_queue.task_done()
                    continue

                # Find best worker for this task
                best_worker = self._select_worker(task, workers)

                if best_worker:
                    # Assign task to worker
                    task.assigned_to = best_worker.id
                    task.update_status(TaskStatus.ASSIGNED)

                    # Update worker's assigned tasks
                    best_worker.assigned_tasks.add(task.id)

                    # Send task to worker
                    self._send_task_to_worker(task, best_worker)
                    logger.info(f"Assigned task {task.id} to worker {best_worker.id}")
                else:
                    # No suitable worker found, put back in queue with delay
                    # to avoid spinning on the same task
                    self.task_queue.task_done()

                    # Wait a bit before requeuing
                    threading.Timer(5.0, lambda t=task: self.task_queue.put(t)).start()
                    continue

                self.task_queue.task_done()

            except Empty:
                break
            except Exception as e:
                logger.error(f"Error scheduling tasks: {str(e)}")
                try:
                    self.task_queue.task_done()
                except:
                    pass

    def _select_worker(self, task: Task, workers: List[NodeInfo]) -> Optional[NodeInfo]:
        """Select the best worker for a task based on resources and capabilities."""
        eligible_workers = []

        for worker in workers:
            # Check if worker has required capabilities
            if task.required_capabilities:
                if not all(cap in worker.capabilities for cap in task.required_capabilities):
                    continue

            # Check if worker has required resources
            if task.required_resources:
                if not worker.resources.has_available_resources(task.required_resources):
                    continue

            # Check if worker is not overloaded with tasks
            max_tasks = self.config.get("max_tasks_per_worker", 10)
            if len(worker.assigned_tasks) >= max_tasks:
                continue

            # Worker is eligible
            eligible_workers.append(worker)

        if not eligible_workers:
            return None

        # Select worker with best resource availability
        return max(eligible_workers, key=lambda w: w.resources.get_resource_score())

    def _send_task_to_worker(self, task: Task, worker: NodeInfo) -> None:
        """Send a task to a worker node."""
        # Create task message
        message = {
            "type": "task",
            "task_id": task.id,
            "task_type": task.type,
            "parameters": task.parameters,
            "sender": self.node_id,
            "timestamp": time.time(),
        }

        # Publish to tasks topic
        self._publish_message(self.tasks_topic, message)

    def _check_task_timeouts(self) -> None:
        """Check for tasks that have timed out."""
        current_time = time.time()

        for task_id, task in self.tasks.items():
            # Skip tasks that don't have timeouts or aren't processing
            if task.timeout is None or task.status not in (
                TaskStatus.ASSIGNED,
                TaskStatus.PROCESSING,
            ):
                continue

            # Check if task has timed out
            if task.updated_at + task.timeout < current_time:
                logger.warning(f"Task {task_id} timed out after {task.timeout} seconds")

                # Update task status
                task.update_status(TaskStatus.TIMEOUT)
                task.error = f"Task timed out after {task.timeout} seconds"

                # Remove from assigned tasks
                node_id = task.assigned_to
                if node_id in self.nodes and task_id in self.nodes[node_id].assigned_tasks:
                    self.nodes[node_id].assigned_tasks.remove(task_id)

                # Check if task should be retried
                retry_count = task.parameters.get("retry_count", 0)
                if retry_count < self.max_retries:
                    # Increment retry count and requeue
                    task.parameters["retry_count"] = retry_count + 1
                    task.update_status(TaskStatus.PENDING)
                    task.assigned_to = None
                    self.task_queue.put(task)
                    logger.info(
                        f"Requeued timed out task {task_id} for retry ({retry_count + 1}/{self.max_retries})"
                    )

    def _task_handler_loop(self) -> None:
        """Thread function for handling assigned tasks (worker only)."""
        if self.role != NodeRole.WORKER:
            logger.warning("Task handler loop should only run on worker nodes")
            return

        while self.running:
            try:
                # Wait for new task messages (implementation depends on pubsub mechanism)
                message = self._get_next_task_message()

                if message:
                    self._handle_task_message(message)
            except Exception as e:
                logger.error(f"Error in task handler loop: {str(e)}")

            # Brief sleep to prevent CPU spinning
            time.sleep(0.1)

    def _get_next_task_message(self) -> Optional[Dict[str, Any]]:
        """Get the next task message from the pubsub queue.

        This is a placeholder - actual implementation will depend on
        the pubsub mechanism being used.
        """
        # Placeholder for getting messages
        # In a real implementation, this would subscribe to the tasks topic
        # and return messages as they arrive
        return None

    def _handle_task_message(self, message: Dict[str, Any]) -> None:
        """Handle a task message from the master."""
        # Validate message
        if message.get("type") != "task":
            logger.warning(f"Received non-task message: {message}")
            return

        task_id = message.get("task_id")
        if not task_id:
            logger.warning("Received task message without task_id")
            return

        # Check if this task is for us
        if message.get("target") not in (None, self.node_id):
            # Task is for another node
            return

        # Extract task information
        task_type = message.get("task_type")
        parameters = message.get("parameters", {})

        # Log task receipt
        logger.info(f"Received task {task_id} of type {task_type}")

        # Add to assigned tasks
        if self.node_id in self.nodes:
            self.nodes[self.node_id].assigned_tasks.add(task_id)

        # Execute task in a separate thread to avoid blocking
        threading.Thread(
            target=self._execute_task, args=(task_id, task_type, parameters), daemon=True
        ).start()

    def _execute_task(self, task_id: str, task_type: str, parameters: Dict[str, Any]) -> None:
        """Execute a task and send back the result."""
        # Create result structure
        result = {
            "task_id": task_id,
            "worker_id": self.node_id,
            "timestamp": time.time(),
            "success": False,
            "task_type": task_type,
        }

        try:
            # Notify task start
            self._send_task_status(task_id, TaskStatus.PROCESSING)

            # Execute task based on type
            if task_type == "pin":
                # Pin content task
                result["data"] = self._execute_pin_task(parameters)
                result["success"] = True

            elif task_type == "unpin":
                # Unpin content task
                result["data"] = self._execute_unpin_task(parameters)
                result["success"] = True

            elif task_type == "retrieve":
                # Retrieve content task
                result["data"] = self._execute_retrieve_task(parameters)
                result["success"] = True

            elif task_type == "process":
                # Generic processing task
                result["data"] = self._execute_process_task(parameters)
                result["success"] = True

            else:
                # Unknown task type
                raise ValueError(f"Unknown task type: {task_type}")

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {str(e)}")
            result["success"] = False
            result["error"] = str(e)

        finally:
            # Send result back to master
            self._send_task_result(result)

            # Update task status
            status = TaskStatus.COMPLETED if result["success"] else TaskStatus.FAILED
            self._send_task_status(task_id, status)

            # Remove from assigned tasks
            if self.node_id in self.nodes:
                self.nodes[self.node_id].assigned_tasks.discard(task_id)

    def _execute_pin_task(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a content pinning task."""
        # Extract parameters
        cid = parameters.get("cid")
        if not cid:
            raise ValueError("Missing required parameter: cid")

        # Pin options
        recursive = parameters.get("recursive", True)
        name = parameters.get("name", "")

        # This is a placeholder - in a real implementation, this would
        # use the IPFS client to pin the content
        logger.info(f"Pinning content {cid} (recursive={recursive})")

        # Simulate pinning delay
        time.sleep(1.0)

        # Return result
        return {"cid": cid, "pinned": True, "name": name}

    def _execute_unpin_task(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a content unpinning task."""
        # Extract parameters
        cid = parameters.get("cid")
        if not cid:
            raise ValueError("Missing required parameter: cid")

        # Unpin options
        recursive = parameters.get("recursive", True)

        # This is a placeholder - in a real implementation, this would
        # use the IPFS client to unpin the content
        logger.info(f"Unpinning content {cid} (recursive={recursive})")

        # Simulate unpinning delay
        time.sleep(0.5)

        # Return result
        return {"cid": cid, "unpinned": True}

    def _execute_retrieve_task(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a content retrieval task."""
        # Extract parameters
        cid = parameters.get("cid")
        if not cid:
            raise ValueError("Missing required parameter: cid")

        # Retrieve options
        offset = parameters.get("offset", 0)
        length = parameters.get("length", None)

        # This is a placeholder - in a real implementation, this would
        # use the IPFS client to retrieve the content
        logger.info(f"Retrieving content {cid} (offset={offset}, length={length})")

        # Simulate retrieval delay
        time.sleep(2.0)

        # Return result (but don't include actual content in the result,
        # as that could be large - this would typically be stored separately)
        return {"cid": cid, "retrieved": True, "size": 1024}  # Placeholder size

    def _execute_process_task(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a generic processing task."""
        # Extract parameters
        process_type = parameters.get("process_type")
        if not process_type:
            raise ValueError("Missing required parameter: process_type")

        # Process based on type
        if process_type == "transform":
            # Content transformation task
            return self._execute_transform_task(parameters)
        elif process_type == "analyze":
            # Content analysis task
            return self._execute_analyze_task(parameters)
        else:
            # Unknown process type
            raise ValueError(f"Unknown process type: {process_type}")

    def _execute_transform_task(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a content transformation task."""
        # Extract parameters
        cid = parameters.get("cid")
        if not cid:
            raise ValueError("Missing required parameter: cid")

        transform_type = parameters.get("transform_type")
        if not transform_type:
            raise ValueError("Missing required parameter: transform_type")

        # This is a placeholder - in a real implementation, this would
        # use the appropriate tools to transform the content
        logger.info(f"Transforming content {cid} with {transform_type}")

        # Simulate transformation delay
        time.sleep(3.0)

        # Return result
        return {
            "cid": cid,
            "transformed": True,
            "transform_type": transform_type,
            "result_cid": f"transformed-{cid}",  # Placeholder for the transformed content CID
        }

    def _execute_analyze_task(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a content analysis task."""
        # Extract parameters
        cid = parameters.get("cid")
        if not cid:
            raise ValueError("Missing required parameter: cid")

        analysis_type = parameters.get("analysis_type")
        if not analysis_type:
            raise ValueError("Missing required parameter: analysis_type")

        # This is a placeholder - in a real implementation, this would
        # use the appropriate tools to analyze the content
        logger.info(f"Analyzing content {cid} with {analysis_type}")

        # Simulate analysis delay
        time.sleep(2.5)

        # Return result
        return {
            "cid": cid,
            "analyzed": True,
            "analysis_type": analysis_type,
            "results": {
                "size": 1024,  # Placeholder size
                "type": "unknown",  # Placeholder type
                "properties": {},  # Placeholder properties
            },
        }

    def _send_task_status(self, task_id: str, status: TaskStatus) -> None:
        """Send a task status update."""
        # Create status message
        message = {
            "type": "task_status",
            "task_id": task_id,
            "worker_id": self.node_id,
            "status": status.value,
            "timestamp": time.time(),
        }

        # Publish to status topic
        self._publish_message(self.status_topic, message)

    def _send_task_result(self, result: Dict[str, Any]) -> None:
        """Send a task result back to the master."""
        # Add additional result metadata
        result["type"] = "task_result"
        result["timestamp"] = time.time()

        # Publish to results topic
        self._publish_message(self.results_topic, result)

    def _publish_message(self, topic: str, message: Dict[str, Any]) -> None:
        """Publish a message to a topic.

        This is a placeholder - actual implementation will depend on
        the pubsub mechanism being used.
        """
        # Placeholder for publishing messages
        # In a real implementation, this would publish to the specified topic
        logger.debug(f"Publishing to {topic}: {message}")

    def create_task(
        self,
        task_type: str,
        parameters: Dict[str, Any],
        priority: int = 0,
        timeout: Optional[float] = None,
        required_resources: Dict[str, float] = None,
        required_capabilities: List[str] = None,
    ) -> str:
        """Create a new task and add it to the queue.

        Args:
            task_type: Type of task to create
            parameters: Parameters for the task
            priority: Priority of the task (higher values have higher priority)
            timeout: Timeout for the task in seconds
            required_resources: Resources required for the task
            required_capabilities: Capabilities required for the task

        Returns:
            Task ID
        """
        # Generate task ID
        task_id = str(uuid.uuid4())

        # Create task object
        task = Task(
            id=task_id,
            type=task_type,
            parameters=parameters,
            status=TaskStatus.PENDING,
            priority=priority,
            timeout=timeout,
            required_resources=required_resources or {},
            required_capabilities=required_capabilities or [],
        )

        # Add to task registry
        self.tasks[task_id] = task

        # Add to task queue
        self.task_queue.put(task)

        logger.info(f"Created task {task_id} of type {task_type}")
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task if it hasn't been completed yet.

        Args:
            task_id: ID of the task to cancel

        Returns:
            True if the task was cancelled, False otherwise
        """
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id} not found")
            return False

        task = self.tasks[task_id]

        # Check if task can be cancelled
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            logger.warning(f"Task {task_id} already in final state: {task.status.value}")
            return False

        # Update task status
        task.update_status(TaskStatus.CANCELLED)
        task.error = "Task cancelled by user"

        # If task is assigned to a worker, notify the worker
        if task.assigned_to:
            # Create cancel message
            message = {
                "type": "task_cancel",
                "task_id": task_id,
                "sender": self.node_id,
                "timestamp": time.time(),
            }

            # Publish to tasks topic
            self._publish_message(self.tasks_topic, message)

            # Remove from assigned tasks
            node_id = task.assigned_to
            if node_id in self.nodes and task_id in self.nodes[node_id].assigned_tasks:
                self.nodes[node_id].assigned_tasks.remove(task_id)
                task.assigned_to = None

        logger.info(f"Cancelled task {task_id}")
        return True

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a task.

        Args:
            task_id: ID of the task to check

        Returns:
            Task status dictionary, or None if task not found
        """
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]

        # Create status dictionary
        status = {
            "id": task.id,
            "type": task.type,
            "status": task.status.value,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "assigned_to": task.assigned_to,
        }

        # Add result or error if available
        if task.result:
            status["result"] = task.result

        if task.error:
            status["error"] = task.error

        return status

    def get_tasks(
        self,
        status_filter: Optional[List[str]] = None,
        type_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get a list of tasks with optional filtering.

        Args:
            status_filter: Optional list of statuses to filter by
            type_filter: Optional task type to filter by
            limit: Maximum number of tasks to return

        Returns:
            List of task dictionaries
        """
        # Convert status strings to enums if provided
        status_enums = None
        if status_filter:
            status_enums = [TaskStatus(s) for s in status_filter]

        # Filter tasks
        filtered_tasks = []
        for task in self.tasks.values():
            # Apply status filter
            if status_enums and task.status not in status_enums:
                continue

            # Apply type filter
            if type_filter and task.type != type_filter:
                continue

            # Add to filtered list
            filtered_tasks.append(task)

            # Check limit
            if len(filtered_tasks) >= limit:
                break

        # Convert to dictionaries
        return [task.to_dict() for task in filtered_tasks]

    def get_nodes(
        self, role_filter: Optional[str] = None, status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get a list of nodes with optional filtering.

        Args:
            role_filter: Optional role to filter by ("master", "worker", or "leecher")
            status_filter: Optional status to filter by

        Returns:
            List of node dictionaries
        """
        # Convert role string to enum if provided
        role_enum = None
        if role_filter:
            role_enum = NodeRole.from_str(role_filter)

        # Convert status string to enum if provided
        status_enum = None
        if status_filter:
            status_enum = NodeStatus(status_filter)

        # Filter nodes
        filtered_nodes = []
        for node in self.nodes.values():
            # Apply role filter
            if role_enum and node.role != role_enum:
                continue

            # Apply status filter
            if status_enum and node.status != status_enum:
                continue

            # Add to filtered list
            filtered_nodes.append(node)

        # Convert to dictionaries
        return [node.to_dict() for node in filtered_nodes]

    def get_cluster_status(self) -> Dict[str, Any]:
        """Get overall cluster status information.

        Returns:
            Cluster status dictionary
        """
        # Count nodes by role and status
        node_counts = {
            "total": len(self.nodes),
            "by_role": {
                "master": sum(1 for node in self.nodes.values() if node.role == NodeRole.MASTER),
                "worker": sum(1 for node in self.nodes.values() if node.role == NodeRole.WORKER),
                "leecher": sum(1 for node in self.nodes.values() if node.role == NodeRole.LEECHER),
            },
            "by_status": {
                "online": sum(
                    1 for node in self.nodes.values() if node.status == NodeStatus.ONLINE
                ),
                "offline": sum(
                    1 for node in self.nodes.values() if node.status == NodeStatus.OFFLINE
                ),
                "degraded": sum(
                    1 for node in self.nodes.values() if node.status == NodeStatus.DEGRADED
                ),
                "starting": sum(
                    1 for node in self.nodes.values() if node.status == NodeStatus.STARTING
                ),
                "stopping": sum(
                    1 for node in self.nodes.values() if node.status == NodeStatus.STOPPING
                ),
                "unknown": sum(
                    1 for node in self.nodes.values() if node.status == NodeStatus.UNKNOWN
                ),
            },
        }

        # Count tasks by status
        task_counts = {
            "total": len(self.tasks),
            "by_status": {
                "pending": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.PENDING
                ),
                "assigned": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.ASSIGNED
                ),
                "processing": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.PROCESSING
                ),
                "completed": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.COMPLETED
                ),
                "failed": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.FAILED
                ),
                "cancelled": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.CANCELLED
                ),
                "timeout": sum(
                    1 for task in self.tasks.values() if task.status == TaskStatus.TIMEOUT
                ),
            },
        }

        # Calculate cluster health
        active_workers = sum(
            1
            for node in self.nodes.values()
            if node.role == NodeRole.WORKER and node.status == NodeStatus.ONLINE
        )

        if self.role != NodeRole.MASTER:
            # Non-master nodes have limited information
            health_status = "unknown"
            master_node = next(
                (node for node in self.nodes.values() if node.role == NodeRole.MASTER), None
            )

            if master_node and master_node.status == NodeStatus.ONLINE:
                health_status = "ok"
            elif master_node:
                health_status = "degraded"
            else:
                health_status = "critical"
        else:
            # Master can determine full cluster health
            min_workers = self.config.get("min_workers", 1)

            if active_workers >= min_workers:
                health_status = "ok"
            elif active_workers > 0:
                health_status = "degraded"
            else:
                health_status = "critical"

        # Create status dictionary
        status = {
            "cluster_id": self.config.get("cluster_id", "default"),
            "self_id": self.node_id,
            "self_role": self.role.value,
            "health_status": health_status,
            "timestamp": time.time(),
            "nodes": node_counts,
            "tasks": task_counts,
        }

        return status


# Example usage when run as script
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create test coordinator
    coord = ClusterCoordinator(
        node_id="test-node",
        role="master",
        peer_id="QmTest",
        config={"cluster_id": "test-cluster", "sync_interval": 5, "heartbeat_interval": 3},
    )

    # Start coordinator
    coord.start()

    try:
        # Create a few test tasks
        for i in range(5):
            task_id = coord.create_task(
                task_type="pin", parameters={"cid": f"QmTest{i}"}, priority=i
            )
            print(f"Created task {task_id}")

        # Run for a while
        print("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        # Stop coordinator
        print("Stopping coordinator...")
        coord.stop()
