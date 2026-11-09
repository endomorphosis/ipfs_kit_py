#!/usr/bin/env python3
"""
Cross-Backend Data Migration Example for MCP Server

This example demonstrates how to use the migration module to move data between
different storage backends with advanced features like policy-based migration,
validation, and priority-based queuing.

Key features demonstrated:
1. Setting up multiple storage backends
2. Creating and managing migration tasks
3. Performing different migration types (copy, move, sync)
4. Validation and verification of migrated data
5. Monitoring migration progress
6. Policy-based migration decisions

Usage:
  python migration_example.py [--data-dir DATA_DIR]
"""

import os
import time
import uuid
import random
import json
import hashlib
import argparse
import logging
import tempfile
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("migration-example")

# Import migration components
try:
    from ipfs_kit_py.mcp.storage_manager.migration import (
        MigrationManager, MigrationType, ValidationLevel, MigrationStatus,
        MigrationPriority, MigrationTask, MigrationResult, calculate_content_hash
    )
except ImportError:
    logger.error("Failed to import migration modules. Make sure ipfs_kit_py is installed")
    import sys
    sys.exit(1)


# Mock storage backend for demonstration purposes
class MockStorageBackend:
    """Simple mock storage backend for demonstration."""
    
    def __init__(self, name: str, storage_dir: str, latency: float = 0.0):
        """
        Initialize the mock backend.
        
        Args:
            name: Name of the backend
            storage_dir: Directory for storing data
            latency: Simulated latency in seconds
        """
        self.name = name
        self.storage_dir = os.path.join(storage_dir, name)
        self.latency = latency
        
        # Create storage directory
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Dictionary to store metadata
        self.metadata_file = os.path.join(self.storage_dir, "metadata.json")
        self.metadata = {}
        
        # Load metadata if exists
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata for {name}: {e}")
        
        logger.info(f"Initialized {name} backend at {self.storage_dir}")
    
    def _simulate_latency(self):
        """Simulate network latency."""
        if self.latency > 0:
            time.sleep(self.latency)
    
    def add_content(self, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Add content to the backend.
        
        Args:
            content: Content to store
            metadata: Optional metadata
            
        Returns:
            Result dictionary
        """
        self._simulate_latency()
        
        try:
            # Generate content ID
            content_id = str(uuid.uuid4())
            
            # Calculate hash
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Get file path
            file_path = os.path.join(self.storage_dir, content_id)
            
            # Store content
            with open(file_path, 'wb') as f:
                f.write(content)
            
            # Store metadata
            self.metadata[content_id] = {
                "id": content_id,
                "hash": content_hash,
                "size": len(content),
                "created": datetime.now().isoformat(),
                "backend": self.name,
                **(metadata or {})
            }
            
            # Save metadata to disk
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            
            return {
                "success": True,
                "identifier": content_id,
                "hash": content_hash,
                "size": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error adding content to {self.name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_content(self, content_id: str, container: Optional[str] = None) -> Dict[str, Any]:
        """
        Get content from the backend.
        
        Args:
            content_id: Content identifier
            container: Optional container/bucket
            
        Returns:
            Result dictionary with data
        """
        self._simulate_latency()
        
        try:
            # Check if content exists
            file_path = os.path.join(self.storage_dir, content_id)
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"Content {content_id} not found"
                }
            
            # Read content
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Update metadata
            if content_id in self.metadata:
                self.metadata[content_id]["last_accessed"] = datetime.now().isoformat()
                self.metadata[content_id]["access_count"] = self.metadata[content_id].get("access_count", 0) + 1
                
                # Save metadata to disk
                with open(self.metadata_file, 'w') as f:
                    json.dump(self.metadata, f, indent=2)
            
            return {
                "success": True,
                "identifier": content_id,
                "data": data,
                "size": len(data)
            }
            
        except Exception as e:
            logger.error(f"Error getting content from {self.name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_metadata(self, content_id: str, container: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metadata for content.
        
        Args:
            content_id: Content identifier
            container: Optional container/bucket
            
        Returns:
            Result dictionary with metadata
        """
        self._simulate_latency()
        
        try:
            # Check if content exists
            if content_id not in self.metadata:
                return {
                    "success": False,
                    "error": f"Metadata for {content_id} not found"
                }
            
            return {
                "success": True,
                "identifier": content_id,
                "metadata": self.metadata[content_id]
            }
            
        except Exception as e:
            logger.error(f"Error getting metadata from {self.name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def remove_content(self, content_id: str, container: Optional[str] = None) -> Dict[str, Any]:
        """
        Remove content from the backend.
        
        Args:
            content_id: Content identifier
            container: Optional container/bucket
            
        Returns:
            Result dictionary
        """
        self._simulate_latency()
        
        try:
            # Check if content exists
            file_path = os.path.join(self.storage_dir, content_id)
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"Content {content_id} not found"
                }
            
            # Remove file
            os.remove(file_path)
            
            # Remove metadata
            if content_id in self.metadata:
                del self.metadata[content_id]
                
                # Save metadata to disk
                with open(self.metadata_file, 'w') as f:
                    json.dump(self.metadata, f, indent=2)
            
            return {
                "success": True,
                "identifier": content_id
            }
            
        except Exception as e:
            logger.error(f"Error removing content from {self.name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def exists(self, content_id: str, container: Optional[str] = None) -> bool:
        """
        Check if content exists.
        
        Args:
            content_id: Content identifier
            container: Optional container/bucket
            
        Returns:
            True if content exists, False otherwise
        """
        self._simulate_latency()
        
        file_path = os.path.join(self.storage_dir, content_id)
        return os.path.exists(file_path)
    
    def list_content(self, prefix: Optional[str] = None, container: Optional[str] = None) -> Dict[str, Any]:
        """
        List content in the backend.
        
        Args:
            prefix: Optional prefix filter
            container: Optional container/bucket
            
        Returns:
            Result dictionary with content list
        """
        self._simulate_latency()
        
        try:
            # Build list of content IDs
            content_ids = []
            for content_id in self.metadata:
                if prefix and not content_id.startswith(prefix):
                    continue
                content_ids.append(content_id)
            
            return {
                "success": True,
                "content_ids": content_ids,
                "count": len(content_ids)
            }
            
        except Exception as e:
            logger.error(f"Error listing content from {self.name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Statistics dictionary
        """
        self._simulate_latency()
        
        try:
            # Count objects and total size
            total_size = 0
            for content_id in self.metadata:
                total_size += self.metadata[content_id].get("size", 0)
            
            return {
                "success": True,
                "total_objects": len(self.metadata),
                "total_size": total_size,
                "backend": self.name
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics from {self.name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Optional: optimized migration path for demonstration
    def migrate_to(self, source_identifier: str, target_backend: Any, 
                   target_container: Optional[str] = None,
                   target_path: Optional[str] = None, 
                   source_container: Optional[str] = None,
                   options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Optimized migration to another backend.
        
        Args:
            source_identifier: Content identifier in this backend
            target_backend: Target backend instance
            target_container: Optional target container
            target_path: Optional target path
            source_container: Optional source container
            options: Additional options
            
        Returns:
            Migration result dictionary
        """
        self._simulate_latency()
        logger.info(f"Using optimized migration path from {self.name} to {target_backend.name}")
        
        try:
            # Get content
            content_result = self.get_content(source_identifier, container=source_container)
            if not content_result.get("success", False):
                return {
                    "success": False,
                    "error": f"Failed to get content: {content_result.get('error', 'Unknown error')}"
                }
            
            # Get metadata
            metadata_result = self.get_metadata(source_identifier, container=source_container)
            source_metadata = metadata_result.get("metadata", {}) if metadata_result.get("success", False) else {}
            
            # Add migration metadata
            migration_metadata = {
                **source_metadata,
                **(options.get("migration_metadata", {})),
                "migrated_from": self.name,
                "migration_time": datetime.now().isoformat()
            }
            
            # Store in target
            store_result = target_backend.add_content(
                content=content_result.get("data"),
                metadata=migration_metadata
            )
            
            if not store_result.get("success", False):
                return {
                    "success": False,
                    "error": f"Failed to store content: {store_result.get('error', 'Unknown error')}"
                }
            
            # Get target ID
            target_identifier = store_result.get("identifier")
            
            # Verification if requested
            verification = None
            if options.get("verify", False):
                # Simple hash verification
                source_hash = source_metadata.get("hash")
                target_metadata_result = target_backend.get_metadata(target_identifier)
                target_metadata = target_metadata_result.get("metadata", {}) if target_metadata_result.get("success", False) else {}
                target_hash = target_metadata.get("hash")
                
                verification = {
                    "success": source_hash == target_hash,
                    "validation_strategy": options.get("validation_strategy", "hash"),
                    "source_hash": source_hash,
                    "target_hash": target_hash
                }
            
            return {
                "success": True,
                "source_identifier": source_identifier,
                "target_identifier": target_identifier,
                "source_backend": self.name,
                "target_backend": target_backend.name,
                "verification": verification
            }
            
        except Exception as e:
            logger.error(f"Error in optimized migration: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Policy engine for migration decisions
class MigrationPolicyEngine:
    """Policy engine for making migration decisions."""
    
    def __init__(self, backend_registry: Dict[str, Any]):
        """
        Initialize the policy engine.
        
        Args:
            backend_registry: Dictionary of available backends
        """
        self.backend_registry = backend_registry
        
        # Example policies
        self.policies = {
            "cost_optimization": self._policy_cost_optimization,
            "access_pattern": self._policy_access_pattern,
            "data_type": self._policy_data_type,
            "age_based": self._policy_age_based
        }
        
        logger.info(f"Initialized migration policy engine with {len(self.policies)} policies")
    
    def evaluate_policies(self, content_id: str, source_backend: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate all policies for a content item.
        
        Args:
            content_id: Content identifier
            source_backend: Current backend
            metadata: Content metadata
            
        Returns:
            Policy evaluation results
        """
        results = {}
        recommendations = []
        
        # Apply each policy
        for policy_name, policy_func in self.policies.items():
            try:
                policy_result = policy_func(content_id, source_backend, metadata)
                results[policy_name] = policy_result
                
                # If policy recommends migration, add to recommendations
                if policy_result.get("recommendation") == "migrate":
                    recommendations.append({
                        "policy": policy_name,
                        "target_backend": policy_result.get("target_backend"),
                        "reason": policy_result.get("reason"),
                        "priority": policy_result.get("priority", MigrationPriority.NORMAL.value)
                    })
            except Exception as e:
                logger.error(f"Error evaluating policy {policy_name}: {e}")
        
        # Determine best recommendation if any
        best_recommendation = None
        if recommendations:
            # Sort by priority (highest first)
            recommendations.sort(key=lambda r: r.get("priority", 0), reverse=True)
            best_recommendation = recommendations[0]
        
        return {
            "content_id": content_id,
            "source_backend": source_backend,
            "policy_results": results,
            "recommendations": recommendations,
            "best_recommendation": best_recommendation
        }
    
    def _policy_cost_optimization(self, content_id: str, source_backend: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cost optimization policy.
        
        Recommends moving infrequently accessed large content to cheaper storage.
        
        Args:
            content_id: Content identifier
            source_backend: Current backend
            metadata: Content metadata
            
        Returns:
            Policy evaluation result
        """
        # Example logic: Move large, rarely accessed files to "cold-storage"
        size = metadata.get("size", 0)
        access_count = metadata.get("access_count", 0)
        last_accessed = metadata.get("last_accessed")
        
        # Large file threshold: 10MB
        is_large = size > 10 * 1024 * 1024
        
        # Low access threshold
        is_rarely_accessed = access_count < 5
        
        # Not accessed recently (30 days)
        not_recent = False
        if last_accessed:
            try:
                last_access_date = datetime.fromisoformat(last_accessed)
                not_recent = (datetime.now() - last_access_date).days > 30
            except (ValueError, TypeError):
                pass
        
        # If large and rarely accessed, migrate to cold storage
        if is_large and (is_rarely_accessed or not_recent) and source_backend != "cold-storage":
            return {
                "recommendation": "migrate",
                "target_backend": "cold-storage",
                "reason": "Large file with low access frequency",
                "priority": MigrationPriority.NORMAL.value
            }
        
        # If frequently accessed but in cold storage, move to fast storage
        if access_count > 10 and source_backend == "cold-storage":
            return {
                "recommendation": "migrate",
                "target_backend": "fast-storage",
                "reason": "Frequently accessed file in cold storage",
                "priority": MigrationPriority.HIGH.value
            }
        
        return {
            "recommendation": "keep",
            "reason": "Current placement is optimal"
        }
    
    def _policy_access_pattern(self, content_id: str, source_backend: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Access pattern policy.
        
        Recommends moving frequently accessed content to faster storage.
        
        Args:
            content_id: Content identifier
            source_backend: Current backend
            metadata: Content metadata
            
        Returns:
            Policy evaluation result
        """
        # Example logic: Move frequently accessed files to fast storage
        access_count = metadata.get("access_count", 0)
        
        # High access threshold
        is_frequently_accessed = access_count > 20
        
        # If frequently accessed and not in fast storage, migrate
        if is_frequently_accessed and source_backend != "fast-storage":
            return {
                "recommendation": "migrate",
                "target_backend": "fast-storage",
                "reason": "Frequently accessed file",
                "priority": MigrationPriority.HIGH.value
            }
        
        return {
            "recommendation": "keep",
            "reason": "Access pattern does not warrant migration"
        }
    
    def _policy_data_type(self, content_id: str, source_backend: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Data type policy.
        
        Recommends placing certain types of data in specialized storage.
        
        Args:
            content_id: Content identifier
            source_backend: Current backend
            metadata: Content metadata
            
        Returns:
            Policy evaluation result
        """
        # Example logic: Place media files in media-optimized storage
        content_type = metadata.get("content_type", "")
        
        # Check for media types
        is_media = content_type.startswith(("image/", "video/", "audio/"))
        
        # If media file and not in media storage, migrate
        if is_media and source_backend != "media-storage":
            return {
                "recommendation": "migrate",
                "target_backend": "media-storage",
                "reason": "Media file type",
                "priority": MigrationPriority.NORMAL.value
            }
        
        # If document, use document storage
        is_document = content_type in ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        if is_document and source_backend != "document-storage":
            return {
                "recommendation": "migrate",
                "target_backend": "document-storage",
                "reason": "Document file type",
                "priority": MigrationPriority.NORMAL.value
            }
        
        return {
            "recommendation": "keep",
            "reason": "Data type does not warrant specialized storage"
        }
    
    def _policy_age_based(self, content_id: str, source_backend: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Age-based policy.
        
        Recommends archiving old data.
        
        Args:
            content_id: Content identifier
            source_backend: Current backend
            metadata: Content metadata
            
        Returns:
            Policy evaluation result
        """
        # Example logic: Archive files older than 1 year
        created = metadata.get("created")
        
        if created:
            try:
                creation_date = datetime.fromisoformat(created)
                age_days = (datetime.now() - creation_date).days
                
                # If older than 1 year and not in archive, migrate
                if age_days > 365 and source_backend != "archive-storage":
                    return {
                        "recommendation": "migrate",
                        "target_backend": "archive-storage",
                        "reason": f"File is {age_days} days old",
                        "priority": MigrationPriority.LOW.value
                    }
            except (ValueError, TypeError):
                pass
        
        return {
            "recommendation": "keep",
            "reason": "Age does not warrant archiving"
        }


class MigrationDashboard:
    """Simple text-based dashboard for monitoring migration."""
    
    def __init__(self, migration_manager: MigrationManager, backend_registry: Dict[str, Any], 
                 update_interval: int = 2):
        """
        Initialize the dashboard.
        
        Args:
            migration_manager: Migration manager instance
            backend_registry: Dictionary of storage backends
            update_interval: Update interval in seconds
        """
        self.migration_manager = migration_manager
        self.backend_registry = backend_registry
        self.update_interval = update_interval
        self.stop_event = threading.Event()
    
    def start(self):
        """Start the dashboard."""
        # Start update thread
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def stop(self):
        """Stop the dashboard."""
        self.stop_event.set()
        if self.update_thread:
            self.update_thread.join(timeout=1.0)
    
    def _update_loop(self):
        """Update loop for dashboard."""
        while not self.stop_event.is_set():
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # Print title
            print("\n" + "=" * 80)
            print("  MIGRATION DASHBOARD")
            print("=" * 80)
            
            # Get migration stats
            stats = self.migration_manager.get_stats()
            
            # Print migration stats
            print("\nMIGRATION STATUS:")
            print(f"  Pending:     {stats.get('pending', 0)}")
            print(f"  In Progress: {stats.get('in_progress', 0)}")
            print(f"  Completed:   {stats.get('completed', 0)}")
            print(f"  Failed:      {stats.get('failed', 0)}")
            print(f"  Scheduled:   {stats.get('scheduled', 0)}")
            print(f"  Validating:  {stats.get('validating', 0)}")
            print(f"  Validated:   {stats.get('validated', 0)}")
            print(f"  Queue Size:  {stats.get('queue_size', 0)}")
            print(f"  Workers:     {stats.get('active_workers', 0)} / {self.migration_manager.max_workers}")
            
            # Print backend stats
            print("\nBACKEND STATUS:")
            for name, backend in self.backend_registry.items():
                backend_stats = backend.get_statistics()
                if backend_stats.get("success", False):
                    print(f"  {name}:")
                    print(f"    Objects: {backend_stats.get('total_objects', 0)}")
                    print(f"    Size:    {backend_stats.get('total_size', 0) / (1024*1024):.2f} MB")
            
            # Get recent tasks (limit to 5)
            tasks = self.migration_manager.list_tasks(include_completed=True)
            recent_tasks = sorted(
                tasks, 
                key=lambda t: datetime.fromisoformat(t.get("updated_at", "2000-01-01T00:00:00")),
                reverse=True
            )[:5]
            
            # Print recent tasks
            print("\nRECENT MIGRATION TASKS:")
            for task in recent_tasks:
                task_id = task.get("id", "")[:8]  # Truncate for display
                source = task.get("source_backend", "")
                target = task.get("target_backend", "")
                status = task.get("status", "")
                updated = task.get("updated_at", "").split("T")[1].split(".")[0]  # Extract time
                
                print(f"  {task_id}  {source} → {target}  [{status}]  {updated}")
            
            # Print footer
            print("\n" + "=" * 80)
            print(f"  Update Interval: {self.update_interval}s  |  Press Ctrl+C to exit")
            print("=" * 80 + "\n")
            
            # Wait for next update
            time.sleep(self.update_interval)


def populate_backends(backends: Dict[str, Any], data_dir: str, num_files: int = 20):
    """
    Populate backends with sample data.
    
    Args:
        backends: Dictionary of backends
        data_dir: Data directory
        num_files: Number of files to create
    """
    logger.info(f"Populating backends with {num_files} sample files")
    
    # Create sample content types
    content_types = [
        "text/plain",
        "image/jpeg",
        "application/pdf",
        "video/mp4",
        "application/json"
    ]
    
    # Create sample files
    for i in range(num_files):
        # Choose random size (1KB to 20MB)
        size = random.randint(1024, 20 * 1024 * 1024)
        
        # Choose random content type
        content_type = random.choice(content_types)
        
        # Create random content
        content = os.urandom(size)
        
        # Choose random backend
        backend_name = random.choice(list(backends.keys()))
        backend = backends[backend_name]
        
        # Add to backend
        metadata = {
            "content_type": content_type,
            "original_filename": f"sample_{i}.dat",
            "created": datetime.now().isoformat(),
            "description": f"Sample file {i}",
            "sample": True
        }
        
        result = backend.add_content(content, metadata)
        
        if result.get("success", False):
            # Simulate some access
            if random.random() < 0.7:  # 70% chance of being accessed
                access_count = random.randint(0, 30)
                for _ in range(access_count):
                    backend.get_content(result.get("identifier", ""))
                    
            logger.debug(f"Created sample file {i} in {backend_name} ({size/1024:.2f} KB)")
        else:
            logger.error(f"Failed to create sample file {i}: {result.get('error', 'Unknown error')}")
    
    logger.info("Backend population complete")


def apply_migration_policies(policy_engine: MigrationPolicyEngine, migration_manager: MigrationManager, 
                            backends: Dict[str, Any]):
    """
    Apply migration policies to all content.
    
    Args:
        policy_engine: Policy engine instance
        migration_manager: Migration manager instance
        backends: Dictionary of backends
    """
    logger.info("Applying migration policies")
    
    # Track migration tasks created
    migrations_created = 0
    
    # Process each backend
    for backend_name, backend in backends.items():
        logger.info(f"Evaluating content in {backend_name}")
        
        # List content
        list_result = backend.list_content()
        if not list_result.get("success", False):
            logger.error(f"Failed to list content in {backend_name}: {list_result.get('error', 'Unknown error')}")
            continue
        
        content_ids = list_result.get("content_ids", [])
        logger.info(f"Found {len(content_ids)} items in {backend_name}")
        
        # Evaluate each content item
        for content_id in content_ids:
            # Get metadata
            metadata_result = backend.get_metadata(content_id)
            if not metadata_result.get("success", False):
                logger.warning(f"Failed to get metadata for {content_id}: {metadata_result.get('error', 'Unknown error')}")
                continue
            
            metadata = metadata_result.get("metadata", {})
            
            # Apply policies
            policy_result = policy_engine.evaluate_policies(content_id, backend_name, metadata)
            recommendation = policy_result.get("best_recommendation")
            
            if recommendation:
                target_backend = recommendation.get("target_backend")
                reason = recommendation.get("reason")
                policy = recommendation.get("policy")
                
                if target_backend in backends:
                    # Create migration task
                    priority_value = MigrationPriority(recommendation.get("priority", MigrationPriority.NORMAL.value))
                    
                    logger.info(f"Creating migration task for {content_id} ({backend_name} -> {target_backend}): {reason}")
                    
                    # Determine migration type (use MOVE for cost optimization, COPY for others)
                    migration_type = MigrationType.MOVE if policy == "cost_optimization" else MigrationType.COPY
                    
                    task_id = migration_manager.create_task(
                        source_backend=backend_name,
                        target_backend=target_backend,
                        source_id=content_id,
                        migration_type=migration_type,
                        validation_level=ValidationLevel.HASH,
                        priority=priority_value,
                        options={
                            "reason": reason,
                            "policy": policy,
                            "metadata": {"migration_reason": reason, "policy": policy}
                        }
                    )
                    
                    migrations_created += 1
                    
                    logger.info(f"Created migration task {task_id} ({migration_type.value})")
                else:
                    logger.warning(f"Target backend {target_backend} not found for {content_id}")
    
    logger.info(f"Created {migrations_created} migration tasks based on policies")
    return migrations_created


def demonstrate_manual_migrations(migration_manager: MigrationManager, backends: Dict[str, Any], num_tasks: int = 5):
    """
    Demonstrate manual migration task creation and monitoring.
    
    Args:
        migration_manager: Migration manager instance
        backends: Dictionary of backends
        num_tasks: Number of tasks to create
    """
    logger.info(f"Creating {num_tasks} manual migration tasks")
    
    backend_names = list(backends.keys())
    
    # For each backend pair, create some migration tasks
    for i in range(num_tasks):
        # Choose random source and target backends
        source_backend = random.choice(backend_names)
        
        # Choose a different backend for target
        available_targets = [b for b in backend_names if b != source_backend]
        if not available_targets:
            logger.warning("No available target backends")
            continue
            
        target_backend = random.choice(available_targets)
        
        # List content in source backend
        list_result = backends[source_backend].list_content()
        if not list_result.get("success", False):
            logger.warning(f"Failed to list content in {source_backend}")
            continue
            
        content_ids = list_result.get("content_ids", [])
        if not content_ids:
            logger.warning(f"No content found in {source_backend}")
            continue
            
        # Choose random content
        content_id = random.choice(content_ids)
        
        # Choose random migration type
        migration_types = [MigrationType.COPY, MigrationType.MOVE]
        migration_type = random.choice(migration_types)
        
        # Choose random validation level
        validation_levels = [
            ValidationLevel.NONE, 
            ValidationLevel.EXISTS,
            ValidationLevel.HASH, 
            ValidationLevel.CONTENT
        ]
        validation_level = random.choice(validation_levels)
        
        # Choose random priority
        priorities = [
            MigrationPriority.LOW,
            MigrationPriority.NORMAL,
            MigrationPriority.HIGH
        ]
        priority = random.choice(priorities)
        
        # Create the task
        task_id = migration_manager.create_task(
            source_backend=source_backend,
            target_backend=target_backend,
            source_id=content_id,
            migration_type=migration_type,
            validation_level=validation_level,
            priority=priority,
            options={
                "description": f"Manual migration task {i+1}",
                "metadata": {"manual": True}
            }
        )
        
        logger.info(f"Created manual migration task {task_id}")
        logger.info(f"  Source: {source_backend}")
        logger.info(f"  Target: {target_backend}")
        logger.info(f"  Type: {migration_type.value}")
        logger.info(f"  Validation: {validation_level.value}")
        logger.info(f"  Priority: {priority.value}")
        
        # Add small delay to avoid overloading
        time.sleep(0.5)
    
    logger.info(f"Created {num_tasks} manual migration tasks")
    
    # Wait for migration to start
    time.sleep(2)
    
    # Get current status
    tasks = migration_manager.list_tasks()
    
    # Print task status
    logger.info("\nCurrent migration tasks:")
    for task in tasks:
        logger.info(f"Task {task.get('id')}: {task.get('status')}")
        
    return len(tasks)


def main():
    """Run the migration management example."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Cross-Backend Data Migration Example")
    parser.add_argument(
        "--data-dir", 
        help="Directory for storage data",
        default=os.path.join(tempfile.gettempdir(), "mcp_migration_example")
    )
    parser.add_argument(
        "--populate", 
        action="store_true", 
        help="Populate backends with sample data"
    )
    parser.add_argument(
        "--manual-tasks", 
        type=int, 
        default=5,
        help="Number of manual migration tasks to create"
    )
    parser.add_argument(
        "--policy-based", 
        action="store_true", 
        help="Apply policy-based migration"
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Show migration dashboard"
    )
    parser.add_argument(
        "--run-time",
        type=int,
        default=60,
        help="How long to run the example (seconds)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of migration worker threads"
    )
    args = parser.parse_args()
    
    # Create data directory
    data_dir = args.data_dir
    os.makedirs(data_dir, exist_ok=True)
    
    logger.info(f"Using data directory: {data_dir}")
    
    try:
        # Initialize storage backends
        backends = {
            "fast-storage": MockStorageBackend("fast-storage", data_dir, latency=0.1),
            "standard-storage": MockStorageBackend("standard-storage", data_dir, latency=0.5),
            "cold-storage": MockStorageBackend("cold-storage", data_dir, latency=2.0),
            "archive-storage": MockStorageBackend("archive-storage", data_dir, latency=3.0),
            "media-storage": MockStorageBackend("media-storage", data_dir, latency=0.3),
            "document-storage": MockStorageBackend("document-storage", data_dir, latency=0.4)
        }
        
        logger.info(f"Initialized {len(backends)} storage backends")
        
        # Populate backends if requested
        if args.populate:
            populate_backends(backends, data_dir, num_files=30)
        
        # Create migration manager
        migration_manager = MigrationManager(backends, max_workers=args.workers)
        
        # Create policy engine
        policy_engine = MigrationPolicyEngine(backends)
        
        # Create migration dashboard if requested
        dashboard = None
        if args.dashboard:
            dashboard = MigrationDashboard(migration_manager, backends)
            dashboard.start()
        
        # Create manual migration tasks if requested
        if args.manual_tasks > 0:
            demonstrate_manual_migrations(migration_manager, backends, num_tasks=args.manual_tasks)
        
        # Apply policy-based migration if requested
        if args.policy_based:
            apply_migration_policies(policy_engine, migration_manager, backends)
        
        # Wait for specified run time
        logger.info(f"Running for {args.run_time} seconds...")
        
        # Wait for migration tasks to complete
        start_time = time.time()
        while time.time() - start_time < args.run_time:
            # Display some stats periodically
            if not args.dashboard and (time.time() - start_time) % 5 < 0.1:
                stats = migration_manager.get_stats()
                logger.info(f"Migration stats: {stats}")
            
            time.sleep(0.5)
            
            # Check if all tasks completed
            if migration_manager.task_queue.empty() and migration_manager.active_workers == 0:
                all_tasks = migration_manager.list_tasks(include_completed=True)
                if len(all_tasks) > 0 and all(
                    task.get("status") in ["completed", "validated", "failed"]
                    for task in all_tasks
                ):
                    logger.info("All migration tasks completed")
                    break
        
        # Get final stats
        stats = migration_manager.get_stats()
        
        logger.info("\nMigration Complete")
        logger.info(f"Queue Size: {stats.get('queue_size', 0)}")
        logger.info(f"Active Workers: {stats.get('active_workers', 0)}")
        logger.info(f"Completed: {stats.get('completed', 0) + stats.get('validated', 0)}")
        logger.info(f"Failed: {stats.get('failed', 0)}")
        
        # List storage statistics
        logger.info("\nStorage Statistics:")
        for name, backend in backends.items():
            backend_stats = backend.get_statistics()
            if backend_stats.get("success", False):
                objects = backend_stats.get("total_objects", 0)
                size_mb = backend_stats.get("total_size", 0) / (1024*1024)
                logger.info(f"  {name}: {objects} objects, {size_mb:.2f} MB")
        
        # Shutdown dashboard if running
        if dashboard:
            dashboard.stop()
        
        # Shutdown migration manager
        migration_manager.shutdown()
        
        logger.info("\nMigration example completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Example interrupted by user")
        if dashboard:
            dashboard.stop()
            
        # Shutdown migration manager
        if 'migration_manager' in locals():
            migration_manager.shutdown()
            
    except Exception as e:
        logger.error(f"Error running example: {e}", exc_info=True)
        if dashboard:
            dashboard.stop()
            
        # Shutdown migration manager
        if 'migration_manager' in locals():
            migration_manager.shutdown()


if __name__ == "__main__":
    main()
