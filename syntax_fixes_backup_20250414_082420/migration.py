"""
Migration Controller for cross-backend data migration.

This module implements the MigrationController class that handles
policy-based migration of content between different storage backends.
"""

import logging
import time
import json
import os
import uuid
import threading
import queue
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from .storage_types import StorageBackendType, ContentReference

# Configure logger
logger = logging.getLogger(__name__)


class MigrationPriorityLevel(Enum):
    """Priority levels for migration tasks."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MigrationPolicy:
    """
    Migration policy for automated content migration between backends.

    Policies define when and how content should be migrated between
    different storage backends based on various criteria.
    """
    def __init__(
        self
        name: str,
        source_backend: Union[StorageBackendType, str],
        target_backend: Union[StorageBackendType, str],
        description: Optional[str] = None,
        criteria: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a migration policy.

        Args:
            name: Unique name for this policy
            source_backend: Source backend type
            target_backend: Target backend type
            description: Policy description
            criteria: Criteria for selecting content to migrate
            options: Additional migration options
        """
        self.name = name

        # Convert backend types to enum if needed
        if isinstance(source_backend, str):
            self.source_backend = StorageBackendType.from_string(source_backend)
        else:
            self.source_backend = source_backend

        if isinstance(target_backend, str):
            self.target_backend = StorageBackendType.from_string(target_backend)
        else:
            self.target_backend = target_backend

        self.description = (
            description
            or f"Migrate content from {self.source_backend.value} to {self.target_backend.value}"
        )
        self.criteria = criteria or {}
        self.options = options or {}

        # Migration tracking
        self.last_run = None
        self.run_count = 0
        self.total_migrations = 0
        self.total_bytes_migrated = 0
        self.enabled = True

    def matches_content(self, content_ref: ContentReference) -> bool:
        """
        Check if content matches the criteria for migration.

        Args:
            content_ref: Content reference to check

        Returns:
            True if content should be migrated according to this policy
        """
        # Check if content is in source backend
        if not content_ref.has_location(self.source_backend):
            return False

        # Check if content is already in target backend
        if content_ref.has_location(self.target_backend):
            return False

        # Check size criteria
        if "min_size" in self.criteria:
            if content_ref.metadata.get("size", 0) < self.criteria["min_size"]:
                return False

        if "max_size" in self.criteria:
            if content_ref.metadata.get("size", 0) > self.criteria["max_size"]:
                return False

        # Check age criteria
        if "min_age_days" in self.criteria:
            created_at = content_ref.created_at
            age_days = (time.time() - created_at) / (60 * 60 * 24)
            if age_days < self.criteria["min_age_days"]:
                return False

        # Check access criteria
        if "min_access_count" in self.criteria:
            if content_ref.access_count < self.criteria["min_access_count"]:
                return False

        if "days_since_last_access" in self.criteria:
            if content_ref.last_accessed:
                days_idle = (time.time() - content_ref.last_accessed) / (60 * 60 * 24)
                if days_idle < self.criteria["days_since_last_access"]:
                    return False

        # Check content type criteria
        if "content_types" in self.criteria:
            content_type = content_ref.metadata.get("content_type", "")
            if content_type and not any(
                ct in content_type for ct in self.criteria["content_types"]
            ):
                return False

        # Check tag criteria
        if "tags" in self.criteria:
            content_tags = content_ref.metadata.get("tags", [])
            if not any(tag in content_tags for tag in self.criteria["tags"]):
                return False

        # All criteria satisfied
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary representation."""
        return {
            "name": self.name,
            "source_backend": self.source_backend.value,
            "target_backend": self.target_backend.value,
            "description": self.description,
            "criteria": self.criteria,
            "options": self.options,
            "last_run": self.last_run,
            "run_count": self.run_count,
            "total_migrations": self.total_migrations,
            "total_bytes_migrated": self.total_bytes_migrated,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationPolicy":
        """Create policy from dictionary representation."""
        policy = cls(
            name=data["name"],
            source_backend=data["source_backend"],
            target_backend=data["target_backend"],
            description=data.get("description"),
            criteria=data.get("criteria", {}),
            options=data.get("options", {}),
        )

        # Set tracking properties
        policy.last_run = data.get("last_run")
        policy.run_count = data.get("run_count", 0)
        policy.total_migrations = data.get("total_migrations", 0)
        policy.total_bytes_migrated = data.get("total_bytes_migrated", 0)
        policy.enabled = data.get("enabled", True)

        return policy


class MigrationTask:
    """
    A task for migrating content between backends.

    Represents a single content migration operation with
    tracking and status information.
    """
    class Status(Enum):
        """Status of a migration task."""
        PENDING = "pending"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        FAILED = "failed"
        CANCELLED = "cancelled"

    def __init___v2(
        self
        content_id: str,
        source_backend: StorageBackendType,
        target_backend: StorageBackendType,
        policy_name: Optional[str] = None,
        priority: MigrationPriorityLevel = MigrationPriorityLevel.NORMAL,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a migration task.

        Args:
            content_id: Content ID to migrate
            source_backend: Source backend type
            target_backend: Target backend type
            policy_name: Name of policy that created this task (if any)
            priority: Priority level for this task
            options: Additional migration options
        """
        self.id = str(uuid.uuid4())
        self.content_id = content_id
        self.source_backend = source_backend
        self.target_backend = target_backend
        self.policy_name = policy_name
        self.priority = priority
        self.options = options or {}

        self.status = MigrationTask.Status.PENDING
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.result = None
        self.log = []

    def update_status(self, status: Status, message: Optional[str] = None):
        """
        Update the status of this task.

        Args:
            status: New status
            message: Optional status message
        """
        self.status = status

        if message:
            self.log.append({"timestamp": time.time(), "status": status.value, "message": message})

        if status == MigrationTask.Status.IN_PROGRESS and not self.started_at:
            self.started_at = time.time()
        elif status in (
            MigrationTask.Status.COMPLETED,
            MigrationTask.Status.FAILED,
            MigrationTask.Status.CANCELLED,
        ):
            self.completed_at = time.time()

    def to_dict_v2(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            "id": self.id,
            "content_id": self.content_id,
            "source_backend": self.source_backend.value,
            "target_backend": self.target_backend.value,
            "policy_name": self.policy_name,
            "priority": self.priority.value,
            "options": self.options,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "result": self.result,
            "log": self.log,
        }

    @classmethod
    def from_dict_v2(cls, data: Dict[str, Any]) -> "MigrationTask":
        """Create task from dictionary representation."""
        task = cls(
            content_id=data["content_id"],
            source_backend=StorageBackendType.from_string(data["source_backend"]),
            target_backend=StorageBackendType.from_string(data["target_backend"]),
            policy_name=data.get("policy_name"),
            priority=MigrationPriorityLevel(
                data.get("priority", MigrationPriorityLevel.NORMAL.value)
            ),
            options=data.get("options", {}),
        )

        # Set additional properties
        task.id = data["id"]
        task.status = MigrationTask.Status(data["status"])
        task.created_at = data["created_at"]
        task.started_at = data.get("started_at")
        task.completed_at = data.get("completed_at")
        task.error = data.get("error")
        task.result = data.get("result")
        task.log = data.get("log", [])

        return task


class MigrationController:
    """
    Controller for managing content migration between backends.

    Implements policy-based migration with priority queue, scheduling,
    and background execution.
    """
    # DISABLED REDEFINITION
        self
        storage_manager,
        policies: Optional[List[MigrationPolicy]] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the migration controller.

        Args:
            storage_manager: UnifiedStorageManager instance
            policies: Initial migration policies
            options: Configuration options
        """
        self.storage_manager = storage_manager
        self.policies = {p.name: p for p in (policies or [])}
        self.options = options or {}

        # Task queue organized by priority
        self.task_queues = {
            MigrationPriorityLevel.LOW: queue.PriorityQueue(),
            MigrationPriorityLevel.NORMAL: queue.PriorityQueue(),
            MigrationPriorityLevel.HIGH: queue.PriorityQueue(),
            MigrationPriorityLevel.CRITICAL: queue.PriorityQueue(),
        }

        # Track all tasks by ID
        self.tasks = {}

        # Worker thread for background processing
        self.worker_thread = None
        self.running = False
        self.worker_lock = threading.Lock()

        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "total_bytes_migrated": 0,
            "policy_runs": {},
        }

        # Load tasks and policies from persistent storage
        self._load_state()

    def _load_state(self):
        """Load migration state from persistent storage."""
        state_path = self.options.get("state_path")

        if state_path and os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    state = json.load(f)

                # Load policies
                for policy_data in state.get("policies", []):
                    policy = MigrationPolicy.from_dict(policy_data)
                    self.policies[policy.name] = policy

                # Load pending tasks
                for task_data in state.get("pending_tasks", []):
                    task = MigrationTask.from_dict(task_data)
                    if task.status == MigrationTask.Status.PENDING:
                        self.tasks[task.id] = task

                        # Add to appropriate queue
                        queue_time = task.created_at
                        self.task_queues[task.priority].put((queue_time, task.id))

                # Load stats
                if "stats" in state:
                    self.stats.update(state["stats"])

                logger.info(
                    f"Loaded {len(self.policies)} policies and {len(self.tasks)} pending tasks"
                )
            except Exception as e:
                logger.error(f"Failed to load migration state: {e}")

    def _save_state(self):
        """Save migration state to persistent storage."""
        state_path = self.options.get("state_path")

        if state_path:
            try:
                # Convert policies to dict
                policy_data = [policy.to_dict() for policy in self.policies.values()]

                # Get pending tasks
                pending_tasks = [
                    task.to_dict()
                    for task in self.tasks.values()
                    if task.status == MigrationTask.Status.PENDING
                ]

                state = {
                    "policies": policy_data,
                    "pending_tasks": pending_tasks,
                    "stats": self.stats,
                    "updated_at": time.time(),
                }

                with open(state_path, "w") as f:
                    json.dump(state, f, indent=2)

                logger.info(
                    f"Saved migration state with {len(policy_data)} policies and {len(pending_tasks)} pending tasks"
                )
            except Exception as e:
                logger.error(f"Failed to save migration state: {e}")

    def add_policy(self, policy: MigrationPolicy) -> bool:
        """
        Add a new migration policy.

        Args:
            policy: Migration policy to add

        Returns:
            True if policy was added successfully
        """
        if policy.name in self.policies:
            logger.warning(f"Policy with name '{policy.name}' already exists")
            return False

        self.policies[policy.name] = policy
        self.stats["policy_runs"][policy.name] = {
            "last_run": None,
            "run_count": 0,
            "total_migrations": 0,
        }

        # Save updated state
        self._save_state()

        return True

    def remove_policy(self, policy_name: str) -> bool:
        """
        Remove a migration policy.

        Args:
            policy_name: Name of policy to remove

        Returns:
            True if policy was removed successfully
        """
        if policy_name not in self.policies:
            logger.warning(f"Policy '{policy_name}' not found")
            return False

        del self.policies[policy_name]

        if policy_name in self.stats["policy_runs"]:
            del self.stats["policy_runs"][policy_name]

        # Save updated state
        self._save_state()

        return True

    def update_policy(self, policy_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing migration policy.

        Args:
            policy_name: Name of policy to update
            updates: Dictionary of properties to update

        Returns:
            True if policy was updated successfully
        """
        if policy_name not in self.policies:
            logger.warning(f"Policy '{policy_name}' not found")
            return False

        policy = self.policies[policy_name]

        # Update policy properties
        if "description" in updates:
            policy.description = updates["description"]

        if "criteria" in updates:
            policy.criteria.update(updates["criteria"])

        if "options" in updates:
            policy.options.update(updates["options"])

        if "enabled" in updates:
            policy.enabled = updates["enabled"]

        # Save updated state
        self._save_state()

        return True

    def list_policies(self) -> List[Dict[str, Any]]:
        """
        List all migration policies.

        Returns:
            List of policy information dictionaries
        """
        return [policy.to_dict() for policy in self.policies.values()]

    def run_policy(self, policy_name: str) -> Dict[str, Any]:
        """
        Run a specific migration policy.

        Args:
            policy_name: Name of policy to run

        Returns:
            Dictionary with operation result
        """
        if policy_name not in self.policies:
            return {"success": False, "error": f"Policy '{policy_name}' not found"}

        policy = self.policies[policy_name]

        if not policy.enabled:
            return {"success": False, "error": f"Policy '{policy_name}' is disabled"}

        # Find content that matches policy criteria
        matching_content = []

        for content_id, content_ref in self.storage_manager.content_registry.items():
            if policy.matches_content(content_ref):
                matching_content.append(content_id)

        # Create migration tasks for matching content
        task_ids = []

        for content_id in matching_content:
            task = MigrationTask(
                content_id=content_id,
                source_backend=policy.source_backend,
                target_backend=policy.target_backend,
                policy_name=policy_name,
                priority=MigrationPriorityLevel.NORMAL,
                options=policy.options,
            )

            self.tasks[task.id] = task
            task_ids.append(task.id)

            # Add to queue
            self.task_queues[task.priority].put((task.created_at, task.id))

        # Update policy statistics
        policy.last_run = time.time()
        policy.run_count += 1

        if policy_name in self.stats["policy_runs"]:
            self.stats["policy_runs"][policy_name]["last_run"] = time.time()
            self.stats["policy_runs"][policy_name]["run_count"] += 1
        else:
            self.stats["policy_runs"][policy_name] = {
                "last_run": time.time(),
                "run_count": 1,
                "total_migrations": 0,
            }

        # Update total task count
        self.stats["total_tasks"] += len(task_ids)

        # Save updated state
        self._save_state()

        # Start worker if not already running
        self._ensure_worker_running()

        return {
            "success": True,
            "policy": policy_name,
            "matching_content": len(matching_content),
            "created_tasks": len(task_ids),
            "task_ids": task_ids,
        }

    def run_all_policies(self) -> Dict[str, Any]:
        """
        Run all enabled migration policies.

        Returns:
            Dictionary with operation result
        """
        results = {}
        total_tasks = 0

        for policy_name, policy in self.policies.items():
            if policy.enabled:
                result = self.run_policy(policy_name)
                results[policy_name] = result

                if result.get("success", False):
                    total_tasks += result.get("created_tasks", 0)

        return {"success": True, "results": results, "total_tasks": total_tasks}

    def add_task(
        self
        content_id: str,
        source_backend: Union[StorageBackendType, str],
        target_backend: Union[StorageBackendType, str],
        priority: Union[MigrationPriorityLevel, int] = MigrationPriorityLevel.NORMAL,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a migration task to the queue.

        Args:
            content_id: Content ID to migrate
            source_backend: Source backend type
            target_backend: Target backend type
            priority: Priority level for this task
            options: Additional migration options

        Returns:
            Dictionary with operation result
        """
        try:
            # Check if content exists
            if content_id not in self.storage_manager.content_registry:
                return {
                    "success": False,
                    "error": f"Content ID '{content_id}' not found",
                }

            # Get content reference
            content_ref = self.storage_manager.content_registry[content_id]

            # Convert backend types to enum if needed
            if isinstance(source_backend, str):
                source_backend = StorageBackendType.from_string(source_backend)

            if isinstance(target_backend, str):
                target_backend = StorageBackendType.from_string(target_backend)

            # Check if content is in source backend
            if not content_ref.has_location(source_backend):
                return {
                    "success": False,
                    "error": f"Content not available in source backend: {source_backend.value}",
                }

            # Check if content is already in target backend
            if content_ref.has_location(target_backend):
                return {
                    "success": False,
                    "error": f"Content already exists in target backend: {target_backend.value}",
                }

            # Convert priority to enum if needed
            if isinstance(priority, int):
                priority = MigrationPriorityLevel(priority)

            # Create task
            task = MigrationTask(
                content_id=content_id,
                source_backend=source_backend,
                target_backend=target_backend,
                priority=priority,
                options=options,
            )

            # Add to tracking and queue
            self.tasks[task.id] = task
            self.task_queues[task.priority].put((task.created_at, task.id))

            # Update statistics
            self.stats["total_tasks"] += 1

            # Save updated state
            self._save_state()

            # Start worker if not already running
            self._ensure_worker_running()

            return {
                "success": True,
                "task_id": task.id,
                "content_id": content_id,
                "source_backend": source_backend.value,
                "target_backend": target_backend.value,
                "priority": priority.value,
            }

        except Exception as e:
            logger.exception(f"Error adding migration task: {e}")
            return {"success": False, "error": str(e)}

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a pending migration task.

        Args:
            task_id: ID of task to cancel

        Returns:
            Dictionary with operation result
        """
        if task_id not in self.tasks:
            return {"success": False, "error": f"Task '{task_id}' not found"}

        task = self.tasks[task_id]

        # Can only cancel pending tasks
        if task.status != MigrationTask.Status.PENDING:
            return {
                "success": False,
                "error": f"Task '{task_id}' is already {task.status.value}",
            }

        # Update task status
        task.update_status(MigrationTask.Status.CANCELLED, "Task cancelled by user")

        # Update statistics
        self.stats["cancelled_tasks"] += 1

        # Save updated state
        self._save_state()

        return {"success": True, "task_id": task_id, "status": task.status.value}

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a migration task.

        Args:
            task_id: ID of task to get

        Returns:
            Task information dictionary or None if not found
        """
        if task_id not in self.tasks:
            return None

        return self.tasks[task_id].to_dict()

    def list_tasks(
        self, status: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        """
        List migration tasks.

        Args:
            status: Filter by task status
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip

        Returns:
            Dictionary with task list and pagination info
        """
        # Filter tasks by status if specified
        if status:
            try:
                status_enum = MigrationTask.Status(status)
                filtered_tasks = [
                    task for task in self.tasks.values() if task.status == status_enum
                ]
            except ValueError:
                filtered_tasks = []
        else:
            filtered_tasks = list(self.tasks.values())

        # Sort by creation time (newest first)
        sorted_tasks = sorted(filtered_tasks, key=lambda t: t.created_at, reverse=True)

        # Apply pagination
        paginated_tasks = sorted_tasks[offset : offset + limit]

        return {
            "success": True,
            "tasks": [task.to_dict() for task in paginated_tasks],
            "total": len(filtered_tasks),
            "limit": limit,
            "offset": offset,
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get migration statistics.

        Returns:
            Dictionary with migration statistics
        """
        # Update task counts
        pending_count = 0
        in_progress_count = 0

        for task in self.tasks.values():
            if task.status == MigrationTask.Status.PENDING:
                pending_count += 1
            elif task.status == MigrationTask.Status.IN_PROGRESS:
                in_progress_count += 1

        return {
            "total_tasks": self.stats["total_tasks"],
            "completed_tasks": self.stats["completed_tasks"],
            "failed_tasks": self.stats["failed_tasks"],
            "cancelled_tasks": self.stats["cancelled_tasks"],
            "pending_tasks": pending_count,
            "in_progress_tasks": in_progress_count,
            "total_bytes_migrated": self.stats["total_bytes_migrated"],
            "policies": {
                name: {
                    "name": name,
                    "enabled": self.policies[name].enabled if name in self.policies else False,
                    "last_run": stats.get("last_run"),
                    "run_count": stats.get("run_count", 0),
                    "total_migrations": stats.get("total_migrations", 0),
                }
                for name, stats in self.stats["policy_runs"].items()
            },
            "worker_running": self.running,
        }

    def start_worker(self) -> bool:
        """
        Start the background worker thread.

        Returns:
            True if worker was started
        """
        with self.worker_lock:
            if self.running:
                return False

            self.running = True
            self.worker_thread = threading.Thread(
                target=self._worker_loop, name="MigrationWorker", daemon=True
            )
            self.worker_thread.start()
            logger.info("Started migration worker thread")

            return True

    def stop_worker(self, wait: bool = True) -> bool:
        """
        Stop the background worker thread.

        Args:
            wait: Whether to wait for worker to stop

        Returns:
            True if worker was stopped
        """
        with self.worker_lock:
            if not self.running:
                return False

            self.running = False

            if wait and self.worker_thread:
                self.worker_thread.join(timeout=5)

            logger.info("Stopped migration worker thread")
            return True

    def _ensure_worker_running(self):
        """Ensure worker thread is running if needed."""
        if not self.running and any(not q.empty() for q in self.task_queues.values()):
            self.start_worker()

    def _worker_loop(self):
        """Main worker loop for processing migration tasks."""
        logger.info("Migration worker started")

        try:
            while self.running:
                # Check if there are any tasks to process
                task = self._get_next_task()

                if not task:
                    # No tasks, sleep and check again
                    time.sleep(1)
                    continue

                # Process the task
                self._process_task(task)

                # Save state periodically
                self._save_state()

        except Exception as e:
            logger.exception(f"Error in migration worker: {e}")
        finally:
            logger.info("Migration worker stopped")

    def _get_next_task(self) -> Optional[MigrationTask]:
        """
        Get the next task to process from the queues.

        Returns:
            Next task to process or None if no tasks
        """
        # Check queues in priority order
        for priority in reversed(list(MigrationPriorityLevel)):
            q = self.task_queues[priority]

            if not q.empty():
                try:
                    # Get task from queue
                    _, task_id = q.get_nowait()

                    # Find task object
                    if task_id in self.tasks:
                        task = self.tasks[task_id]

                        # Only process pending tasks
                        if task.status == MigrationTask.Status.PENDING:
                            return task

                except queue.Empty:
                    # Queue became empty, continue to next queue
                    pass

        # No tasks found
        return None

    def _process_task(self, task: MigrationTask):
        """
        Process a migration task.

        Args:
            task: Task to process
        """
        logger.info(f"Processing migration task {task.id} for content {task.content_id}")

        # Update task status
        task.update_status(
            MigrationTask.Status.IN_PROGRESS,
            f"Starting migration from {task.source_backend.value} to {task.target_backend.value}",
        )

        try:
            # Check if content still exists
            if task.content_id not in self.storage_manager.content_registry:
                task.update_status(
                    MigrationTask.Status.FAILED, f"Content {task.content_id} not found"
                )
                task.error = "Content not found"
                self.stats["failed_tasks"] += 1
                return

            # Get content reference
            content_ref = self.storage_manager.content_registry[task.content_id]

            # Check if still needed
            if not content_ref.has_location(task.source_backend):
                task.update_status(
                    MigrationTask.Status.FAILED,
                    f"Content not available in source backend {task.source_backend.value}",
                )
                task.error = "Content not in source backend"
                self.stats["failed_tasks"] += 1
                return

            if content_ref.has_location(task.target_backend):
                task.update_status(
                    MigrationTask.Status.COMPLETED,
                    f"Content already exists in target backend {task.target_backend.value}",
                )
                task.result = {"message": "Content already in target backend, no migration needed"}
                self.stats["completed_tasks"] += 1
                return

            # Perform the migration
            task.update_status(
                MigrationTask.Status.IN_PROGRESS,
                f"Retrieving content from {task.source_backend.value}",
            )

            # Retrieve from source backend
            retrieve_options = task.options.get("retrieve_options", {})
            retrieve_result = self.storage_manager.retrieve(
                content_id=task.content_id,
                backend_preference=task.source_backend,
                options=retrieve_options,
            )

            if not retrieve_result.get("success", False):
                task.update_status(
                    MigrationTask.Status.FAILED,
                    f"Failed to retrieve content: {retrieve_result.get('error')}",
                )
                task.error = f"Retrieval failed: {retrieve_result.get('error')}"
                self.stats["failed_tasks"] += 1
                return

            # Get data
            data = retrieve_result.get("data")
            content_size = len(data) if data else 0

            task.update_status(
                MigrationTask.Status.IN_PROGRESS,
                f"Storing content ({content_size} bytes) to {task.target_backend.value}",
            )

            # Store in target backend
            store_options = task.options.get("store_options", {})
            container = task.options.get("container")
            path = task.options.get("path")

            # Add content metadata
            store_metadata = content_ref.metadata.copy()
            store_metadata["migrated_from"] = task.source_backend.value
            store_metadata["migration_task"] = task.id
            store_metadata["migration_time"] = time.time()

            # Get target backend instance
            target_backend = self.storage_manager.backends.get(task.target_backend)

            if not target_backend:
                task.update_status(
                    MigrationTask.Status.FAILED,
                    f"Target backend {task.target_backend.value} not available",
                )
                task.error = "Target backend not available"
                self.stats["failed_tasks"] += 1
                return

            # Store in target backend
            store_result = target_backend.store(
                data=data,
                container=container,
                path=path,
                options={**store_options, "metadata": store_metadata},
            )

            if not store_result.get("success", False):
                task.update_status(
                    MigrationTask.Status.FAILED,
                    f"Failed to store content: {store_result.get('error')}",
                )
                task.error = f"Storage failed: {store_result.get('error')}"
                self.stats["failed_tasks"] += 1
                return

            # Update content reference
            content_ref.add_location(task.target_backend, store_result.get("identifier"))

            # Update task status
            task.update_status(MigrationTask.Status.COMPLETED, "Migration completed successfully")
            task.result = {
                "source_location": content_ref.get_location(task.source_backend),
                "target_location": store_result.get("identifier"),
                "size": content_size,
            }

            # Update statistics
            self.stats["completed_tasks"] += 1
            self.stats["total_bytes_migrated"] += content_size

            # Update policy statistics if from a policy
            if task.policy_name and task.policy_name in self.policies:
                policy = self.policies[task.policy_name]
                policy.total_migrations += 1
                policy.total_bytes_migrated += content_size

                if task.policy_name in self.stats["policy_runs"]:
                    self.stats["policy_runs"][task.policy_name]["total_migrations"] += 1

            # Delete from source if requested
            if task.options.get("delete_source", False):
                task.update_status(
                    MigrationTask.Status.IN_PROGRESS,
                    f"Deleting content from source backend {task.source_backend.value}",
                )

                delete_result = self.storage_manager.delete(
                    content_id=task.content_id, backend=task.source_backend
                )

                if delete_result.get("success", False):
                    task.update_status(
                        MigrationTask.Status.COMPLETED,
                        "Content deleted from source backend",
                    )
                else:
                    task.update_status(
                        MigrationTask.Status.COMPLETED,
                        f"Migration completed but failed to delete from source: {delete_result.get('error')}",
                    )

            # Save content registry
            self.storage_manager._save_content_registry()

        except Exception as e:
            logger.exception(f"Error processing migration task {task.id}: {e}")
            task.update_status(
                MigrationTask.Status.FAILED, f"Migration failed with error: {str(e)}"
            )
            task.error = str(e)
            self.stats["failed_tasks"] += 1
