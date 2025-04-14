"""
Migration Controller for MCP server.

This module provides a unified interface for managing data migrations between
different storage backends in the MCP system. It implements advanced features like:
- Cross-backend data migration with policy-based management
- Cost-optimized storage placement
- Batch migration operations with monitoring and reporting
- Migration scheduling and prioritization
- Automatic verification and integrity checking
"""

import logging
import time
import json
import os
import threading
import queue
import uuid
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Union, Tuple, Callable

# Configure logger
logger = logging.getLogger(__name__)


class MigrationPriority(Enum):
    """Priority levels for migrations."""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


class MigrationStatus(Enum):
    """Status values for migration operations."""
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    VERIFICATION_FAILED = auto()


class MigrationPolicy:
    """Defines policies for data migration between backends."""

    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize a migration policy.

        Args:
            name: Policy name
            config: Policy configuration dictionary containing:
                - source_backend: Source backend type (ipfs, s3, storacha, etc.)
                - target_backend: Target backend type
                - content_filters: Filters to apply when selecting content to migrate
                - cost_threshold: Maximum cost allowed for migration
                - bandwidth_limit: Maximum bandwidth to use (KB/s)
                - verification_required: Whether to verify content after migration
                - schedule: When to run this policy (cron-like string)
                - retention: Whether to keep the content on source after migration
        """
        self.name = name
        self.config = config
        self.source_backend = config.get("source_backend")
        self.target_backend = config.get("target_backend")
        self.content_filters = config.get("content_filters", {})
        self.cost_threshold = config.get("cost_threshold", float("inf"))
        self.bandwidth_limit = config.get("bandwidth_limit", 0)  # 0 means no limit
        self.verification_required = config.get("verification_required", True)
        self.schedule = config.get("schedule", "")
        self.retention = config.get("retention", True)

    def matches_content(self, content_metadata: Dict[str, Any]) -> bool:
        """
        Check if content matches this policy's filters.

        Args:
            content_metadata: Metadata about the content to check

        Returns:
            True if the content matches the policy filters
        """
        # If no filters, match everything
        if not self.content_filters:
            return True

        # Check each filter
        for key, expected_value in self.content_filters.items():
            if key not in content_metadata:
                return False
            
            actual_value = content_metadata[key]
            
            # Handle different filter types
            if isinstance(expected_value, list):
                # Check if actual value is in the list
                if actual_value not in expected_value:
                    return False
            elif isinstance(expected_value, dict) and "min" in expected_value and "max" in expected_value:
                # Range check
                if not (expected_value["min"] <= actual_value <= expected_value["max"]):
                    return False
            elif actual_value != expected_value:
                # Direct comparison
                return False
                
        return True

    def estimate_cost(self, content_size: int) -> float:
        """
        Estimate the cost of migrating content under this policy.

        Args:
            content_size: Size of the content in bytes

        Returns:
            Estimated cost as a float
        """
        # This is a simplified cost model - should be expanded based on
        # actual backend pricing models
        base_costs = {
            "ipfs": 0.00005,  # per MB
            "s3": 0.00002,    # per MB
            "storacha": 0.00003,  # per MB
            "filecoin": 0.00001,  # per MB
            "huggingface": 0.00004,  # per MB
            "lassie": 0.00003  # per MB
        }
        
        source_cost = base_costs.get(self.source_backend, 0.00005)
        target_cost = base_costs.get(self.target_backend, 0.00005)
        
        # Calculate transfer cost (depends on size)
        mb_size = content_size / (1024 * 1024)  # Convert to MB
        transfer_cost = mb_size * (source_cost + target_cost)
        
        # Add operation overhead
        overhead = 0.01  # Fixed overhead per operation
        
        return transfer_cost + overhead
    
    def is_cost_effective(self, content_size: int) -> bool:
        """
        Check if migration is cost-effective under this policy.

        Args:
            content_size: Size of the content in bytes

        Returns:
            True if the migration is cost-effective
        """
        estimated_cost = self.estimate_cost(content_size)
        return estimated_cost <= self.cost_threshold


class MigrationTask:
    """Represents a single migration task between backends."""

    def __init__(
        self,
        source_backend: str,
        target_backend: str,
        content_id: str,
        policy_name: Optional[str] = None,
        priority: MigrationPriority = MigrationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a migration task.

        Args:
            source_backend: Source backend name
            target_backend: Target backend name
            content_id: Content identifier in the source backend
            policy_name: Name of the policy this task belongs to (if any)
            priority: Task priority
            metadata: Additional metadata about the content
        """
        self.id = str(uuid.uuid4())
        self.source_backend = source_backend
        self.target_backend = target_backend
        self.content_id = content_id
        self.policy_name = policy_name
        self.priority = priority
        self.metadata = metadata or {}
        self.status = MigrationStatus.PENDING
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.source_size = metadata.get("size", 0) if metadata else 0
        self.target_identifier = None
        self.verification_result = None
        self.transfer_speed = 0  # Bytes per second

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            "id": self.id,
            "source_backend": self.source_backend,
            "target_backend": self.target_backend,
            "content_id": self.content_id,
            "policy_name": self.policy_name,
            "priority": self.priority.name,
            "status": self.status.name,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "source_size": self.source_size,
            "target_identifier": self.target_identifier,
            "verification_result": self.verification_result,
            "transfer_speed": self.transfer_speed,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MigrationTask':
        """Create task from dictionary representation."""
        task = cls(
            source_backend=data["source_backend"],
            target_backend=data["target_backend"],
            content_id=data["content_id"],
            policy_name=data.get("policy_name"),
            priority=MigrationPriority[data["priority"]],
            metadata=data.get("metadata", {})
        )
        task.id = data["id"]
        task.status = MigrationStatus[data["status"]]
        task.created_at = data["created_at"]
        task.started_at = data.get("started_at")
        task.completed_at = data.get("completed_at")
        task.error = data.get("error")
        task.source_size = data.get("source_size", 0)
        task.target_identifier = data.get("target_identifier")
        task.verification_result = data.get("verification_result")
        task.transfer_speed = data.get("transfer_speed", 0)
        return task


class MigrationController:
    """
    Controller for managing migrations between different storage backends.
    
    This class implements the unified data management features from the MCP roadmap,
    providing a centralized interface for handling migrations between any supported
    backend type.
    """

    def __init__(self, resources=None, metadata=None):
        """
        Initialize the migration controller.

        Args:
            resources: Dictionary of available resources
            metadata: Additional configuration metadata
        """
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Dictionary to store backend handlers
        self.backend_handlers = {}
        
        # Load migration tools
        self._load_migration_tools()
        
        # Migration policies
        self.policies = {}
        
        # Migration tasks
        self.tasks = {}
        
        # Worker thread and queue
        self.worker_queue = queue.PriorityQueue()
        self.worker_thread = None
        self.stop_event = threading.Event()
        
        # Statistics
        self.stats = {
            "total_migrations": 0,
            "successful_migrations": 0,
            "failed_migrations": 0,
            "bytes_transferred": 0,
            "backend_stats": {}
        }
        
        # Load policies from config
        self._load_policies()
        
        # Start worker thread
        self._start_worker()

    def _load_migration_tools(self):
        """Load all available migration tools."""
        # Import all migration tools dynamically
        try:
            from ipfs_kit_py.migration_tools.ipfs_to_s3 import ipfs_to_s3
            self._register_migration_tool("ipfs", "s3", ipfs_to_s3)

            from ipfs_kit_py.migration_tools.ipfs_to_storacha import ipfs_to_storacha
            self._register_migration_tool("ipfs", "storacha", ipfs_to_storacha)

            from ipfs_kit_py.migration_tools.s3_to_ipfs import s3_to_ipfs
            self._register_migration_tool("s3", "ipfs", s3_to_ipfs)

            from ipfs_kit_py.migration_tools.s3_to_storacha import s3_to_storacha
            self._register_migration_tool("s3", "storacha", s3_to_storacha)

            from ipfs_kit_py.migration_tools.storacha_to_ipfs import storacha_to_ipfs
            self._register_migration_tool("storacha", "ipfs", storacha_to_ipfs)

            from ipfs_kit_py.migration_tools.storacha_to_s3 import storacha_to_s3
            self._register_migration_tool("storacha", "s3", storacha_to_s3)
            
            # Track which backend combinations are available
            logger.info(f"Loaded migration tools for combinations: {list(self.backend_handlers.keys())}")
        except ImportError as e:
            logger.error(f"Failed to import migration tools: {e}")

    def _register_migration_tool(self, source_backend, target_backend, tool_class):
        """Register a migration tool for a specific backend combination."""
        key = f"{source_backend}:{target_backend}"
        self.backend_handlers[key] = tool_class
        
        # Initialize backend stats
        if source_backend not in self.stats["backend_stats"]:
            self.stats["backend_stats"][source_backend] = {
                "outgoing_migrations": 0,
                "outgoing_bytes": 0
            }
            
        if target_backend not in self.stats["backend_stats"]:
            self.stats["backend_stats"][target_backend] = {
                "incoming_migrations": 0,
                "incoming_bytes": 0
            }

    def _load_policies(self):
        """Load migration policies from configuration."""
        policy_config_path = self.metadata.get("policy_config_path", "")
        
        if policy_config_path and os.path.exists(policy_config_path):
            try:
                with open(policy_config_path, 'r') as f:
                    policy_configs = json.load(f)
                
                for name, config in policy_configs.items():
                    self.add_policy(name, config)
                
                logger.info(f"Loaded {len(policy_configs)} migration policies")
            except Exception as e:
                logger.error(f"Failed to load migration policies: {e}")
        else:
            logger.warning("No policy configuration found or specified")

    def add_policy(self, name: str, config: Dict[str, Any]) -> MigrationPolicy:
        """
        Add a new migration policy.

        Args:
            name: Policy name
            config: Policy configuration

        Returns:
            MigrationPolicy object
        """
        policy = MigrationPolicy(name, config)
        self.policies[name] = policy
        logger.info(f"Added migration policy '{name}': {policy.source_backend} -> {policy.target_backend}")
        return policy

    def remove_policy(self, name: str) -> bool:
        """
        Remove a migration policy.

        Args:
            name: Policy name to remove

        Returns:
            True if successfully removed
        """
        if name in self.policies:
            del self.policies[name]
            logger.info(f"Removed migration policy '{name}'")
            return True
        return False

    def list_policies(self) -> List[Dict[str, Any]]:
        """
        Get a list of all migration policies.

        Returns:
            List of policy dictionaries
        """
        return [
            {"name": name, "config": policy.config}
            for name, policy in self.policies.items()
        ]

    def _start_worker(self):
        """Start the migration worker thread."""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.stop_event.clear()
            self.worker_thread = threading.Thread(
                target=self._migration_worker,
                daemon=True
            )
            self.worker_thread.start()
            logger.info("Started migration worker thread")

    def _stop_worker(self):
        """Stop the migration worker thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self.worker_thread.join(timeout=5)
            logger.info("Stopped migration worker thread")

    def _migration_worker(self):
        """Worker thread that processes migration tasks."""
        logger.info("Migration worker thread started")
        
        while not self.stop_event.is_set():
            try:
                # Get the next task (with timeout to allow checking stop_event)
                try:
                    priority, task_id = self.worker_queue.get(timeout=1)
                    task = self.tasks.get(task_id)
                    
                    if task is None:
                        logger.warning(f"Task {task_id} not found")
                        continue
                        
                    # Update task status
                    task.status = MigrationStatus.IN_PROGRESS
                    task.started_at = time.time()
                    
                    # Get the migration tool for this backend combination
                    backend_key = f"{task.source_backend}:{task.target_backend}"
                    
                    if backend_key not in self.backend_handlers:
                        task.status = MigrationStatus.FAILED
                        task.error = f"No migration tool available for {backend_key}"
                        logger.error(task.error)
                        continue
                    
                    # Initialize the migration tool
                    migration_tool = self.backend_handlers[backend_key](
                        self.resources, self.metadata
                    )
                    
                    # Perform the migration
                    result = self._execute_migration(migration_tool, task)
                    
                    # Clean up the migration tool
                    if hasattr(migration_tool, "cleanup"):
                        migration_tool.cleanup()
                    
                    # Verify the migration if required
                    if result.get("success", False) and task.policy_name:
                        policy = self.policies.get(task.policy_name)
                        if policy and policy.verification_required:
                            verification_result = self._verify_migration(task, result)
                            task.verification_result = verification_result
                            
                            if not verification_result.get("success", False):
                                task.status = MigrationStatus.VERIFICATION_FAILED
                                task.error = verification_result.get("error", "Verification failed")
                                self.stats["failed_migrations"] += 1
                                continue
                    
                    # Update task status
                    if result.get("success", False):
                        task.status = MigrationStatus.COMPLETED
                        task.target_identifier = result.get("target_identifier")
                        
                        # Calculate transfer speed
                        if task.started_at and task.source_size > 0:
                            duration = time.time() - task.started_at
                            if duration > 0:
                                task.transfer_speed = task.source_size / duration
                        
                        # Update statistics
                        self.stats["successful_migrations"] += 1
                        self.stats["bytes_transferred"] += task.source_size
                        self.stats["backend_stats"][task.source_backend]["outgoing_migrations"] += 1
                        self.stats["backend_stats"][task.source_backend]["outgoing_bytes"] += task.source_size
                        self.stats["backend_stats"][task.target_backend]["incoming_migrations"] += 1
                        self.stats["backend_stats"][task.target_backend]["incoming_bytes"] += task.source_size
                    else:
                        task.status = MigrationStatus.FAILED
                        task.error = result.get("error", "Migration failed")
                        self.stats["failed_migrations"] += 1
                    
                    task.completed_at = time.time()
                    
                    # Mark the task as done in the queue
                    self.worker_queue.task_done()
                    
                except queue.Empty:
                    # No tasks to process, just continue
                    continue
                    
            except Exception as e:
                logger.exception(f"Error in migration worker: {e}")
        
        logger.info("Migration worker thread stopped")

    def _execute_migration(self, migration_tool, task):
        """
        Execute a migration task using the appropriate migration tool.

        Args:
            migration_tool: The migration tool instance
            task: The migration task to execute

        Returns:
            Dictionary with migration result
        """
        # Get policy if available
        policy = self.policies.get(task.policy_name) if task.policy_name else None
        
        # Prepare result dictionary
        result = {
            "success": False,
            "task_id": task.id,
            "source_backend": task.source_backend,
            "target_backend": task.target_backend,
            "content_id": task.content_id,
            "policy_name": task.policy_name,
            "started_at": task.started_at,
            "completed_at": None,
            "error": None
        }
        
        try:
            # Determine the migration method based on task metadata
            if task.metadata.get("type") == "directory":
                # Handle directory migration
                if hasattr(migration_tool, "migrate_directory"):
                    migration_result = migration_tool.migrate_directory(
                        task.content_id,
                        task.metadata.get("target_container", "default"),
                        task.metadata.get("target_path", "")
                    )
                else:
                    raise NotImplementedError(f"Migration tool does not support directory migration")
            else:
                # Handle file migration
                if hasattr(migration_tool, "migrate_file"):
                    migration_result = migration_tool.migrate_file(
                        task.content_id,
                        task.metadata.get("target_container", "default"),
                        task.metadata.get("target_path", ""),
                        task.metadata.get("file_name")
                    )
                else:
                    raise NotImplementedError(f"Migration tool does not support file migration")
            
            # Extract relevant information from the migration result
            result.update({
                "success": migration_result.get("success", False),
                "error": migration_result.get("error"),
                "target_identifier": migration_result.get("destination", {}).get("path"),
                "details": migration_result
            })
            
            # Check if we should retain content in source backend
            if policy and not policy.retention and result.get("success", False):
                # TODO: Implement content deletion from source backend
                pass
                
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            logger.exception(f"Error executing migration task {task.id}: {e}")
        
        result["completed_at"] = time.time()
        return result

    def _verify_migration(self, task, migration_result):
        """
        Verify that a migration was successful by comparing content.

        Args:
            task: The migration task
            migration_result: The result of the migration operation

        Returns:
            Dictionary with verification result
        """
        # This is a placeholder for actual verification logic
        # In a real implementation, this would:
        # 1. Retrieve content metadata from source
        # 2. Retrieve content metadata from target
        # 3. Compare checksums/hashes
        # 4. Optionally do content sampling for large files
        
        return {
            "success": True,
            "verified_at": time.time(),
            "method": "placeholder",
            "details": "Verification not fully implemented yet"
        }

    def create_migration_task(
        self,
        source_backend: str,
        target_backend: str,
        content_id: str,
        policy_name: Optional[str] = None,
        priority: MigrationPriority = MigrationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MigrationTask:
        """
        Create a new migration task.

        Args:
            source_backend: Source backend name
            target_backend: Target backend name
            content_id: Content identifier in the source backend
            policy_name: Name of the policy to apply (optional)
            priority: Task priority
            metadata: Additional metadata about the content

        Returns:
            MigrationTask object
        """
        task = MigrationTask(
            source_backend=source_backend,
            target_backend=target_backend,
            content_id=content_id,
            policy_name=policy_name,
            priority=priority,
            metadata=metadata
        )
        
        # Store the task
        self.tasks[task.id] = task
        
        # Add to queue with priority
        self.worker_queue.put((priority.value, task.id))
        
        # Update statistics
        self.stats["total_migrations"] += 1
        
        logger.info(f"Created migration task {task.id}: {source_backend} -> {target_backend}, content: {content_id}")
        
        return task

    def get_task(self, task_id: str) -> Optional[MigrationTask]:
        """
        Get a migration task by ID.

        Args:
            task_id: Task ID

        Returns:
            MigrationTask object or None if not found
        """
        return self.tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[MigrationStatus] = None,
        source_backend: Optional[str] = None,
        target_backend: Optional[str] = None,
        policy_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List migration tasks with optional filtering.

        Args:
            status: Filter by task status
            source_backend: Filter by source backend
            target_backend: Filter by target backend
            policy_name: Filter by policy name
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip

        Returns:
            List of task dictionaries
        """
        filtered_tasks = []
        
        for task in self.tasks.values():
            # Apply filters
            if status and task.status != status:
                continue
            if source_backend and task.source_backend != source_backend:
                continue
            if target_backend and task.target_backend != target_backend:
                continue
            if policy_name and task.policy_name != policy_name:
                continue
            
            filtered_tasks.append(task.to_dict())
        
        # Sort by creation time (newest first)
        filtered_tasks.sort(key=lambda t: t["created_at"], reverse=True)
        
        # Apply pagination
        return filtered_tasks[offset:offset+limit]

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending migration task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if successfully cancelled
        """
        task = self.tasks.get(task_id)
        
        if task and task.status == MigrationStatus.PENDING:
            task.status = MigrationStatus.CANCELLED
            logger.info(f"Cancelled migration task {task_id}")
            return True
        
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get migration statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_migrations": self.stats["total_migrations"],
            "successful_migrations": self.stats["successful_migrations"],
            "failed_migrations": self.stats["failed_migrations"],
            "bytes_transferred": self.stats["bytes_transferred"],
            "backend_stats": self.stats["backend_stats"],
            "pending_tasks": sum(1 for task in self.tasks.values() if task.status == MigrationStatus.PENDING),
            "in_progress_tasks": sum(1 for task in self.tasks.values() if task.status == MigrationStatus.IN_PROGRESS),
            "completed_tasks": sum(1 for task in self.tasks.values() if task.status == MigrationStatus.COMPLETED),
            "failed_tasks": sum(1 for task in self.tasks.values() if task.status == MigrationStatus.FAILED),
            "policies": len(self.policies),
            "supported_backend_pairs": list(self.backend_handlers.keys())
        }

    def apply_policy_to_content(
        self,
        policy_name: str,
        content_list: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Apply a migration policy to a list of content items.

        Args:
            policy_name: Name of the policy to apply
            content_list: List of content items with metadata

        Returns:
            List of created task IDs
        """
        policy = self.policies.get(policy_name)
        if not policy:
            logger.error(f"Policy '{policy_name}' not found")
            return []
        
        task_ids = []
        
        for content in content_list:
            content_id = content.get("id")
            if not content_id:
                logger.warning("Content item missing ID, skipping")
                continue
            
            # Check if content matches policy filters
            if not policy.matches_content(content):
                logger.debug(f"Content {content_id} does not match policy filters, skipping")
                continue
            
            # Check if migration is cost-effective
            content_size = content.get("size", 0)
            if not policy.is_cost_effective(content_size):
                logger.info(f"Migration of {content_id} not cost-effective, skipping")
                continue
            
            # Create migration task
            task = self.create_migration_task(
                source_backend=policy.source_backend,
                target_backend=policy.target_backend,
                content_id=content_id,
                policy_name=policy_name,
                metadata=content
            )
            
            task_ids.append(task.id)
        
        logger.info(f"Applied policy '{policy_name}' to {len(task_ids)} content items")
        return task_ids

    def analyze_migration_cost(
        self,
        source_backend: str,
        target_backend: str,
        content_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze the cost of migrating content between backends.

        Args:
            source_backend: Source backend name
            target_backend: Target backend name
            content_list: List of content items with size metadata

        Returns:
            Dictionary with cost analysis
        """
        # Create a temporary policy for cost estimation
        temp_policy = MigrationPolicy(
            "temp_cost_analysis",
            {
                "source_backend": source_backend,
                "target_backend": target_backend
            }
        )
        
        total_size = sum(item.get("size", 0) for item in content_list)
        total_items = len(content_list)
        total_cost = 0.0
        
        for item in content_list:
            size = item.get("size", 0)
            cost = temp_policy.estimate_cost(size)
            total_cost += cost
        
        avg_cost_per_item = total_cost / total_items if total_items > 0 else 0
        avg_cost_per_mb = total_cost / (total_size / (1024 * 1024)) if total_size > 0 else 0
        
        return {
            "source_backend": source_backend,
            "target_backend": target_backend,
            "total_items": total_items,
            "total_size_bytes": total_size,
            "total_cost": total_cost,
            "avg_cost_per_item": avg_cost_per_item,
            "avg_cost_per_mb": avg_cost_per_mb,
            "timestamp": time.time()
        }

    def get_optimal_backend(
        self,
        content_metadata: Dict[str, Any],
        available_backends: List[str]
    ) -> str:
        """
        Determine the optimal backend for storing content based on its metadata.

        Args:
            content_metadata: Content metadata including size, type, access patterns
            available_backends: List of available backends to consider

        Returns:
            Name of the optimal backend
        """
        # Simple scoring system for backends based on content characteristics
        scores = {}
        
        # Get content properties
        size = content_metadata.get("size", 0)
        content_type = content_metadata.get("content_type", "")
        access_frequency = content_metadata.get("access_frequency", "medium")
        durability_requirement = content_metadata.get("durability", "medium")
        latency_requirement = content_metadata.get("latency", "medium")
        
        # Convert string values to numeric scores
        freq_scores = {"low": 1, "medium": 2, "high": 3}
        access_score = freq_scores.get(access_frequency, 2)
        
        durability_scores = {"low": 1, "medium": 2, "high": 3}
        durability_score = durability_scores.get(durability_requirement, 2)
        
        latency_scores = {"low": 3, "medium": 2, "high": 1}  # Lower latency is better
        latency_score = latency_scores.get(latency_requirement, 2)
        
        # Backend characteristics (simplified)
        backend_profiles = {
            "ipfs": {
                "size_efficiency": lambda s: 3 if s < 10*1024*1024 else 2 if s < 100*1024*1024 else 1,
                "content_type_match": lambda t: 3 if "image" in t or "text" in t else 2,
                "access_match": lambda a: 3 if a >= 2 else 2,
                "durability_match": lambda d: 2,
                "latency_match": lambda l: 3 if l >= 2 else 1
            },
            "s3": {
                "size_efficiency": lambda s: 2 if s < 1*1024*1024 else 3,
                "content_type_match": lambda t: 3,  # Good for all content types
                "access_match": lambda a: 2 if a == 1 else 3,
                "durability_match": lambda d: 3,
                "latency_match": lambda l: 3
            },
            "storacha": {
                "size_efficiency": lambda s: 3 if s < 50*1024*1024 else 2 if s < 200*1024*1024 else 1,
                "content_type_match": lambda t: 3 if "document" in t or "text" in t else 2,
                "access_match": lambda a: 2 if a == 3 else 3,
                "durability_match": lambda d: 3 if d == 3 else 2,
                "latency_match": lambda l: 2
            },
            "filecoin": {
                "size_efficiency": lambda s: 1 if s < 100*1024*1024 else 3,
                "content_type_match": lambda t: 2,
                "access_match": lambda a: 3 if a == 1 else 1,
                "durability_match": lambda d: 3,
                "latency_match": lambda l: 1
            },
            "huggingface": {
                "size_efficiency": lambda s: 3 if s < 20*1024*1024 else 2 if s < 100*1024*1024 else 1,
                "content_type_match": lambda t: 3 if "model" in t or "data" in t else 2,
                "access_match": lambda a: 3 if a >= 2 else 2,
                "durability_match": lambda d: 2,
                "latency_match": lambda l: 2
            },
            "lassie": {
                "size_efficiency": lambda s: 2,
                "content_type_match": lambda t: 2,
                "access_match": lambda a: 3 if a >= 2 else 2,
                "durability_match": lambda d: 2,
                "latency_match": lambda l: 2
            }
        }
        
        # Calculate scores for each available backend
        for backend in available_backends:
            if backend in backend_profiles:
                profile = backend_profiles[backend]
                
                size_score = profile["size_efficiency"](size)
                type_score = profile["content_type_match"](content_type)
                access_match = profile["access_match"](access_score)
                durability_match = profile["durability_match"](durability_score)
                latency_match = profile["latency_match"](latency_score)
                
                # Calculate overall score with weights
                scores[backend] = (
                    size_score * 0.25 +
                    type_score * 0.15 +
                    access_match * 0.2 +
                    durability_match * 0.2 +
                    latency_match * 0.2
                )
        
        # Find backend with highest score
        if not scores:
            # Default to first available if no scores
            return available_backends[0] if available_backends else ""
        
        return max(scores.items(), key=lambda x: x[1])[0]

    def cleanup(self):
        """Clean up resources when shutting down."""
        logger.info("Cleaning up migration controller resources")
        self._stop_worker()