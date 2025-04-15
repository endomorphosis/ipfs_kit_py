"""
Migration Controller Framework for MCP server.

This module implements the policy-based migration controller mentioned in the roadmap,
which enables content migration between different storage backends.
"""

import os
import sys
import json
import time
import logging
import asyncio
import threading
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

# Configure logger
logger = logging.getLogger(__name__)

class MigrationStatus(Enum):
    """Migration task status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MigrationPriority(Enum):
    """Migration task priority."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class MigrationPolicy:
    """Configuration for automated content migration between backends."""
    name: str
    source_backend: str
    destination_backend: str
    content_filter: Dict[str, Any] = field(default_factory=dict)
    schedule: str = "manual"  # "manual", "daily", "weekly", or cron expression
    priority: MigrationPriority = MigrationPriority.NORMAL
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to string values
        data["priority"] = self.priority.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationPolicy":
        """Create policy from dictionary."""
        # Convert string/integer values back to enums
        if "priority" in data and not isinstance(data["priority"], MigrationPriority):
            data["priority"] = MigrationPriority(data["priority"])
        return cls(**data)

@dataclass
class MigrationTask:
    """Task for migrating content between storage backends."""
    id: str = field(default_factory=lambda: f"task_{int(time.time())}_{id(object())}")
    source_backend: str = ""
    destination_backend: str = ""
    content_id: str = ""
    status: MigrationStatus = MigrationStatus.PENDING
    priority: int = MigrationPriority.NORMAL.value
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to string values
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationTask":
        """Create task from dictionary."""
        # Convert string values back to enums
        if "status" in data and not isinstance(data["status"], MigrationStatus):
            data["status"] = MigrationStatus(data["status"])
        return cls(**data)

class MigrationController:
    """
    Controller for managing content migration between storage backends.
    
    This implements the policy-based migration mentioned in the roadmap.
    """
    
    def __init__(self, backend_manager=None, config_path=None):
        """
        Initialize the migration controller.
        
        Args:
            backend_manager: Storage backend manager for accessing backends
            config_path: Path to configuration and state file
        """
        self.backend_manager = backend_manager
        self.config_path = config_path or os.path.join(
            os.path.expanduser("~"), ".ipfs_kit", "migration_config.json"
        )
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        # Migration policies
        self.policies: Dict[str, MigrationPolicy] = {}
        
        # Task queue
        self.tasks: Dict[str, MigrationTask] = {}
        
        # Completed tasks history
        self.history: List[MigrationTask] = []
        
        # Thread for background migrations
        self._migration_thread = None
        self._stop_migration = threading.Event()
        
        # Load configuration and state
        self._load_config()
    
    def _load_config(self):
        """Load migration configuration and state from file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                
                # Load policies
                if "policies" in data:
                    self.policies = {
                        name: MigrationPolicy.from_dict(policy_data)
                        for name, policy_data in data["policies"].items()
                    }
                
                # Load pending tasks
                if "tasks" in data:
                    self.tasks = {
                        task_data["id"]: MigrationTask.from_dict(task_data)
                        for task_data in data["tasks"]
                    }
                
                # Load task history
                if "history" in data:
                    self.history = [
                        MigrationTask.from_dict(task_data)
                        for task_data in data["history"]
                    ]
                
                logger.info(f"Loaded {len(self.policies)} policies and {len(self.tasks)} pending tasks")
        except Exception as e:
            logger.error(f"Error loading migration config: {e}")
    
    def _save_config(self):
        """Save migration configuration and state to file."""
        try:
            data = {
                "policies": {
                    name: policy.to_dict()
                    for name, policy in self.policies.items()
                },
                "tasks": [task.to_dict() for task in self.tasks.values()],
                "history": [task.to_dict() for task in self.history[-100:]]  # Keep last 100 tasks
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Migration configuration saved")
        except Exception as e:
            logger.error(f"Error saving migration config: {e}")
    
    def add_policy(self, policy: MigrationPolicy) -> bool:
        """
        Add a new migration policy.
        
        Args:
            policy: Migration policy to add
            
        Returns:
            True if policy was added successfully
        """
        if policy.name in self.policies:
            logger.warning(f"Policy {policy.name} already exists, updating")
        
        self.policies[policy.name] = policy
        self._save_config()
        
        return True
    
    def get_policy(self, name: str) -> Optional[MigrationPolicy]:
        """
        Get a migration policy by name.
        
        Args:
            name: Name of the policy
            
        Returns:
            Migration policy or None if not found
        """
        return self.policies.get(name)
    
    def list_policies(self) -> List[MigrationPolicy]:
        """
        List all migration policies.
        
        Returns:
            List of migration policies
        """
        return list(self.policies.values())
    
    def remove_policy(self, name: str) -> bool:
        """
        Remove a migration policy.
        
        Args:
            name: Name of the policy
            
        Returns:
            True if policy was removed
        """
        if name in self.policies:
            del self.policies[name]
            self._save_config()
            return True
        
        return False
    
    def schedule_migration(self, task: MigrationTask) -> bool:
        """
        Schedule a content migration task.
        
        Args:
            task: Migration task to schedule
            
        Returns:
            True if task was scheduled
        """
        self.tasks[task.id] = task
        self._save_config()
        
        # Start background thread if not running
        self._ensure_migration_thread()
        
        return True
    
    def _ensure_migration_thread(self):
        """Ensure the background migration thread is running."""
        if self._migration_thread is None or not self._migration_thread.is_alive():
            self._stop_migration.clear()
            self._migration_thread = threading.Thread(
                target=self._migration_worker,
                daemon=True
            )
            self._migration_thread.start()
            logger.info("Started background migration worker thread")
    
    def _migration_worker(self):
        """Background worker for processing migration tasks."""
        logger.info("Migration worker thread started")
        
        while not self._stop_migration.is_set():
            try:
                # Get highest priority task
                pending_tasks = [
                    task for task in self.tasks.values() 
                    if task.status == MigrationStatus.PENDING
                ]
                
                if not pending_tasks:
                    # Sleep and check again
                    time.sleep(10)
                    continue
                
                # Sort by priority (highest first)
                pending_tasks.sort(key=lambda t: t.priority, reverse=True)
                task = pending_tasks[0]
                
                # Update task status
                task.status = MigrationStatus.IN_PROGRESS
                task.started_at = time.time()
                self._save_config()
                
                # Execute the migration
                success = self._execute_migration(task)
                
                # Update task status
                if success:
                    task.status = MigrationStatus.COMPLETED
                    logger.info(f"Migration task {task.id} completed successfully")
                else:
                    task.status = MigrationStatus.FAILED
                    logger.warning(f"Migration task {task.id} failed")
                
                task.completed_at = time.time()
                
                # Move to history and remove from queue
                self.history.append(task)
                del self.tasks[task.id]
                self._save_config()
                
            except Exception as e:
                logger.error(f"Error in migration worker: {e}")
                time.sleep(60)  # Wait a bit longer after an error
    
    def _execute_migration(self, task: MigrationTask) -> bool:
        """
        Execute a content migration task.
        
        Args:
            task: Migration task to execute
            
        Returns:
            True if migration was successful
        """
        try:
            if not self.backend_manager:
                task.error = "Backend manager not available"
                return False
            
            # Get source and destination backends
            source = self.backend_manager.get_backend(task.source_backend)
            destination = self.backend_manager.get_backend(task.destination_backend)
            
            if not source:
                task.error = f"Source backend '{task.source_backend}' not found"
                return False
            
            if not destination:
                task.error = f"Destination backend '{task.destination_backend}' not found"
                return False
            
            # Get content from source
            result = source.get_content(task.content_id)
            if not result.get("success"):
                task.error = f"Failed to get content from source: {result.get('error')}"
                return False
            
            content_data = result.get("data")
            
            # Get metadata if available
            metadata_result = source.get_metadata(task.content_id)
            content_metadata = metadata_result.get("metadata") if metadata_result.get("success") else {}
            
            # Store in destination
            store_result = destination.add_content(content_data, metadata=content_metadata)
            if not store_result.get("success"):
                task.error = f"Failed to store content in destination: {store_result.get('error')}"
                return False
            
            # Store new identifier in task metadata for reference
            new_id = store_result.get("identifier")
            task.metadata["destination_id"] = new_id
            
            # Verify content was migrated successfully
            verify_result = destination.get_content(new_id)
            if not verify_result.get("success"):
                task.error = f"Failed to verify migrated content: {verify_result.get('error')}"
                return False
            
            # Update task with success metrics
            task.metadata["source_size"] = len(content_data)
            task.metadata["migration_time"] = time.time() - task.started_at
            
            return True
            
        except Exception as e:
            task.error = str(e)
            logger.error(f"Migration error for task {task.id}: {e}")
            return False
    
    def get_migration_status(self, task_id: str) -> Optional[MigrationTask]:
        """
        Get the status of a migration task.
        
        Args:
            task_id: ID of the migration task
            
        Returns:
            Migration task or None if not found
        """
        # Check pending tasks
        if task_id in self.tasks:
            return self.tasks[task_id]
        
        # Check history
        for task in self.history:
            if task.id == task_id:
                return task
        
        return None
    
    def cancel_migration(self, task_id: str) -> bool:
        """
        Cancel a migration task.
        
        Args:
            task_id: ID of the migration task
            
        Returns:
            True if task was cancelled
        """
        if task_id in self.tasks:
            task = self.tasks[task_id]
            
            # Allow cancelling tasks in PENDING or IN_PROGRESS state
            if task.status in [MigrationStatus.PENDING, MigrationStatus.IN_PROGRESS]:
                task.status = MigrationStatus.CANCELLED
                task.completed_at = time.time()
                self.history.append(task)
                del self.tasks[task_id]
                self._save_config()
                return True
            else:
                logger.warning(f"Cannot cancel task {task_id} with status {task.status}")
                return False
        
        logger.warning(f"Task {task_id} not found")
        return False
    
    def execute_policy(self, policy_name: str) -> List[str]:
        """
        Execute a migration policy, creating tasks for matching content.
        
        Args:
            policy_name: Name of the policy to execute
            
        Returns:
            List of created task IDs
        """
        policy = self.get_policy(policy_name)
        if not policy:
            logger.warning(f"Policy {policy_name} not found")
            return []
        
        if not policy.enabled:
            logger.warning(f"Policy {policy_name} is disabled")
            return []
        
        if not self.backend_manager:
            logger.warning("Backend manager not available")
            return []
        
        # Get source backend
        source = self.backend_manager.get_backend(policy.source_backend)
        if not source:
            logger.warning(f"Source backend '{policy.source_backend}' not found")
            return []
        
        # List content from source (with filter if available)
        content_filter = policy.content_filter or {}
        prefix = content_filter.get("prefix", "")
        
        list_result = source.list(prefix=prefix)
        if not list_result.get("success"):
            logger.warning(f"Failed to list content from source: {list_result.get('error')}")
            return []
        
        items = list_result.get("items", [])
        logger.info(f"Found {len(items)} items in source matching filter")
        
        # Create tasks for each item
        task_ids = []
        for item in items:
            content_id = item.get("identifier")
            
            # Skip if content doesn't match filter
            if not self._matches_filter(item, content_filter):
                continue
            
            # Create migration task
            task = MigrationTask(
                source_backend=policy.source_backend,
                destination_backend=policy.destination_backend,
                content_id=content_id,
                priority=policy.priority.value,
                metadata={"policy": policy_name}
            )
            
            # Schedule the task
            if self.schedule_migration(task):
                task_ids.append(task.id)
        
        logger.info(f"Created {len(task_ids)} migration tasks for policy {policy_name}")
        return task_ids
    
    def _matches_filter(self, item: Dict[str, Any], content_filter: Dict[str, Any]) -> bool:
        """
        Check if an item matches the content filter.
        
        Args:
            item: Content item
            content_filter: Filter criteria
            
        Returns:
            True if item matches filter
        """
        # If filter is empty or filter type is "all", match everything
        if not content_filter or content_filter.get("type") == "all":
            return True
        
        # Prefix match
        if "prefix" in content_filter:
            prefix = content_filter["prefix"]
            identifier = item.get("identifier", "")
            if not identifier.startswith(prefix):
                return False
        
        # Metadata match
        if "metadata" in content_filter:
            metadata_filter = content_filter["metadata"]
            metadata = item.get("metadata", {})
            
            for key, value in metadata_filter.items():
                if key not in metadata or metadata[key] != value:
                    return False
        
        # Size range match
        if "min_size" in content_filter or "max_size" in content_filter:
            size = item.get("size", 0)
            
            if "min_size" in content_filter and size < content_filter["min_size"]:
                return False
                
            if "max_size" in content_filter and size > content_filter["max_size"]:
                return False
        
        return True
    
    def start(self):
        """Start the migration controller."""
        self._ensure_migration_thread()
    
    def stop(self):
        """Stop the migration controller."""
        if self._migration_thread and self._migration_thread.is_alive():
            self._stop_migration.set()
            self._migration_thread.join(timeout=5)
            logger.info("Stopped migration controller")

# Command-line interface
def main():
    """Command-line interface for migration controller."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Content Migration Controller")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Policy commands
    policy_parser = subparsers.add_parser("policy", help="Manage migration policies")
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command")
    
    # Add policy
    add_parser = policy_subparsers.add_parser("add", help="Add a migration policy")
    add_parser.add_argument("--name", required=True, help="Policy name")
    add_parser.add_argument("--source", required=True, help="Source backend")
    add_parser.add_argument("--destination", required=True, help="Destination backend")
    add_parser.add_argument("--filter", help="Content filter as JSON")
    add_parser.add_argument("--schedule", default="manual", help="Schedule (manual, daily, weekly)")
    add_parser.add_argument("--priority", type=int, default=2, help="Priority (1-4)")
    
    # List policies
    list_parser = policy_subparsers.add_parser("list", help="List migration policies")
    
    # Show policy
    show_parser = policy_subparsers.add_parser("show", help="Show migration policy")
    show_parser.add_argument("name", help="Policy name")
    
    # Remove policy
    remove_parser = policy_subparsers.add_parser("remove", help="Remove migration policy")
    remove_parser.add_argument("name", help="Policy name")
    
    # Execute policy
    execute_parser = policy_subparsers.add_parser("execute", help="Execute migration policy")
    execute_parser.add_argument("name", help="Policy name")
    
    # Task commands
    task_parser = subparsers.add_parser("task", help="Manage migration tasks")
    task_subparsers = task_parser.add_subparsers(dest="task_command")
    
    # Add task
    add_task_parser = task_subparsers.add_parser("add", help="Add a migration task")
    add_task_parser.add_argument("--source", required=True, help="Source backend")
    add_task_parser.add_argument("--destination", required=True, help="Destination backend")
    add_task_parser.add_argument("--content-id", required=True, help="Content ID")
    add_task_parser.add_argument("--priority", type=int, default=2, help="Priority (1-4)")
    
    # List tasks
    list_tasks_parser = task_subparsers.add_parser("list", help="List migration tasks")
    list_tasks_parser.add_argument("--status", help="Filter by status")
    
    # Show task
    show_task_parser = task_subparsers.add_parser("show", help="Show migration task")
    show_task_parser.add_argument("id", help="Task ID")
    
    # Cancel task
    cancel_task_parser = task_subparsers.add_parser("cancel", help="Cancel migration task")
    cancel_task_parser.add_argument("id", help="Task ID")
    
    args = parser.parse_args()
    
    # Initialize controller
    controller = MigrationController()
    
    if args.command == "policy":
        if args.policy_command == "add":
            content_filter = {}
            if args.filter:
                content_filter = json.loads(args.filter)
            
            policy = MigrationPolicy(
                name=args.name,
                source_backend=args.source,
                destination_backend=args.destination,
                content_filter=content_filter,
                schedule=args.schedule,
                priority=MigrationPriority(args.priority)
            )
            
            if controller.add_policy(policy):
                print(f"Policy {args.name} added successfully")
            else:
                print(f"Failed to add policy {args.name}")
        
        elif args.policy_command == "list":
            policies = controller.list_policies()
            print(f"Found {len(policies)} policies:")
            for policy in policies:
                print(f"- {policy.name}: {policy.source_backend} -> {policy.destination_backend}")
        
        elif args.policy_command == "show":
            policy = controller.get_policy(args.name)
            if policy:
                print(f"Policy: {policy.name}")
                print(f"Source: {policy.source_backend}")
                print(f"Destination: {policy.destination_backend}")
                print(f"Schedule: {policy.schedule}")
                print(f"Priority: {policy.priority.name}")
                print(f"Enabled: {policy.enabled}")
                print(f"Content Filter: {policy.content_filter}")
            else:
                print(f"Policy {args.name} not found")
        
        elif args.policy_command == "remove":
            if controller.remove_policy(args.name):
                print(f"Policy {args.name} removed successfully")
            else:
                print(f"Policy {args.name} not found")
        
        elif args.policy_command == "execute":
            task_ids = controller.execute_policy(args.name)
            print(f"Created {len(task_ids)} migration tasks")
            for task_id in task_ids:
                print(f"- {task_id}")
    
    elif args.command == "task":
        if args.task_command == "add":
            task = MigrationTask(
                source_backend=args.source,
                destination_backend=args.destination,
                content_id=args.content_id,
                priority=args.priority
            )
            
            if controller.schedule_migration(task):
                print(f"Task {task.id} scheduled successfully")
            else:
                print("Failed to schedule task")
        
        elif args.task_command == "list":
            tasks = list(controller.tasks.values())
            if args.status:
                tasks = [t for t in tasks if t.status.value == args.status]
            
            print(f"Found {len(tasks)} tasks:")
            for task in tasks:
                print(f"- {task.id}: {task.source_backend} -> {task.destination_backend}, Status: {task.status.value}")
        
        elif args.task_command == "show":
            task = controller.get_migration_status(args.id)
            if task:
                print(f"Task: {task.id}")
                print(f"Source: {task.source_backend}")
                print(f"Destination: {task.destination_backend}")
                print(f"Content ID: {task.content_id}")
                print(f"Status: {task.status.value}")
                print(f"Priority: {task.priority}")
                print(f"Created: {datetime.fromtimestamp(task.created_at)}")
                if task.started_at:
                    print(f"Started: {datetime.fromtimestamp(task.started_at)}")
                if task.completed_at:
                    print(f"Completed: {datetime.fromtimestamp(task.completed_at)}")
                if task.error:
                    print(f"Error: {task.error}")
                print(f"Metadata: {task.metadata}")
            else:
                print(f"Task {args.id} not found")
        
        elif args.task_command == "cancel":
            if controller.cancel_migration(args.id):
                print(f"Task {args.id} cancelled successfully")
            else:
                print(f"Failed to cancel task {args.id}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()