"""
Migration persistence store for MCP server.

This module provides persistent storage for migration operations
as specified in the MCP roadmap Q2 2025 priorities.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import aiofiles

logger = logging.getLogger(__name__)


class MigrationStore:
    """Persistence store for migration operations."""

    def __init__(self, data_dir: str = None):
        """
        Initialize the migration store.

        Args:
            data_dir: Directory for storing migration data
        """
        if data_dir is None:
            # Default to a data directory in the project
            base_dir = os.environ.get("IPFS_KIT_DATA_DIR", "/tmp/ipfs_kit")
            data_dir = os.path.join(base_dir, "mcp", "migrations")

        self.data_dir = data_dir

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        logger.debug(f"Migration store initialized with data directory: {self.data_dir}")

    def _get_migration_path(self, migration_id: str) -> str:
        """
        Get the file path for a migration.

        Args:
            migration_id: ID of the migration

        Returns:
            File path for the migration
        """
        return os.path.join(self.data_dir, f"{migration_id}.json")

    async def create(self, migration_id: str, migration_data: Dict[str, Any]) -> bool:
        """
        Create a new migration record.

        Args:
            migration_id: ID of the migration
            migration_data: Migration data to store

        Returns:
            True if creation was successful
        """
        file_path = self._get_migration_path(migration_id)

        try:
            async with aiofiles.open(file_path, "w") as f:
                await f.write(json.dumps(migration_data, indent=2))
            logger.debug(f"Created migration record: {migration_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create migration record {migration_id}: {e}")
            return False

    async def update(self, migration_id: str, migration_data: Dict[str, Any]) -> bool:
        """
        Update an existing migration record.

        Args:
            migration_id: ID of the migration
            migration_data: Updated migration data

        Returns:
            True if update was successful
        """
        file_path = self._get_migration_path(migration_id)

        try:
            async with aiofiles.open(file_path, "w") as f:
                await f.write(json.dumps(migration_data, indent=2))
            logger.debug(f"Updated migration record: {migration_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update migration record {migration_id}: {e}")
            return False

    async def get(self, migration_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a migration record.

        Args:
            migration_id: ID of the migration

        Returns:
            Migration data or None if not found
        """
        file_path = self._get_migration_path(migration_id)

        if not os.path.exists(file_path):
            logger.debug(f"Migration record not found: {migration_id}")
            return None

        try:
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to read migration record {migration_id}: {e}")
            return None

    async def delete(self, migration_id: str) -> bool:
        """
        Delete a migration record.

        Args:
            migration_id: ID of the migration

        Returns:
            True if deletion was successful
        """
        file_path = self._get_migration_path(migration_id)

        if not os.path.exists(file_path):
            logger.debug(f"Migration record not found for deletion: {migration_id}")
            return False

        try:
            os.remove(file_path)
            logger.debug(f"Deleted migration record: {migration_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete migration record {migration_id}: {e}")
            return False

    async def load_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all migration records.

        Returns:
            Dictionary of migration ID to migration data
        """
        migrations = {}

        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".json"):
                    migration_id = filename.replace(".json", "")
                    file_path = os.path.join(self.data_dir, filename)

                    try:
                        async with aiofiles.open(file_path, "r") as f:
                            content = await f.read()
                            migration_data = json.loads(content)
                            migrations[migration_id] = migration_data
                    except Exception as e:
                        logger.error(f"Failed to read migration file {filename}: {e}")
        except Exception as e:
            logger.error(f"Failed to list migration files: {e}")

        logger.debug(f"Loaded {len(migrations)} migration records")
        return migrations

    async def find_by_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        """
        Find migrations by batch ID.

        Args:
            batch_id: Batch ID to search for

        Returns:
            List of migration records in the batch
        """
        batch_migrations = []
        all_migrations = await self.load_all()

        for migration in all_migrations.values():
            if migration.get("batch_id") == batch_id:
                batch_migrations.append(migration)

        return batch_migrations

    async def find_by_cid(self, cid: str) -> List[Dict[str, Any]]:
        """
        Find migrations by content ID.

        Args:
            cid: Content ID to search for

        Returns:
            List of migration records for the CID
        """
        cid_migrations = []
        all_migrations = await self.load_all()

        for migration in all_migrations.values():
            if migration.get("cid") == cid:
                cid_migrations.append(migration)

        return cid_migrations

    async def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of migration statistics.

        Returns:
            Dictionary with migration summary
        """
        all_migrations = await self.load_all()

        # Initialize counters
        total = len(all_migrations)
        active = 0
        completed = 0
        failed = 0
        queued = 0
        total_bytes = 0
        total_cost = 0.0
        source_backends = {}
        target_backends = {}

        # Process migrations
        for migration in all_migrations.values():
            status = migration.get("status", "unknown")

            if status == "in_progress":
                active += 1
            elif status == "completed":
                completed += 1

                # Add to total bytes if available
                if "result" in migration and "size_bytes" in migration["result"]:
                    total_bytes += migration["result"]["size_bytes"]

                # Add to total cost if available
                if "result" in migration and "cost" in migration["result"]:
                    total_cost += migration["result"]["cost"]
            elif status == "failed":
                failed += 1
            elif status == "queued":
                queued += 1

            # Track backend usage
            source = migration.get("source_backend")
            if source:
                source_backends[source] = source_backends.get(source, 0) + 1

            target = migration.get("target_backend")
            if target:
                target_backends[target] = target_backends.get(target, 0) + 1

        # Find most used backends
        most_used_source = (
            max(source_backends.items(), key=lambda x: x[1])[0] if source_backends else None
        )
        most_used_target = (
            max(target_backends.items(), key=lambda x: x[1])[0] if target_backends else None
        )

        # Compile active backends list
        active_backends = list(set(source_backends.keys()).union(set(target_backends.keys())))

        return {
            "total_migrations": total,
            "active_migrations": active,
            "completed_migrations": completed,
            "failed_migrations": failed,
            "queued_migrations": queued,
            "total_bytes_migrated": total_bytes,
            "total_cost": total_cost,
            "active_backends": active_backends,
            "most_used_source": most_used_source,
            "most_used_target": most_used_target,
            "last_updated": time.time(),
        }

    async def cleanup_old_migrations(self, days: int = 30) -> int:
        """
        Clean up migration records older than specified days.

        Args:
            days: Number of days to keep records for

        Returns:
            Number of records cleaned up
        """
        all_migrations = await self.load_all()
        cleanup_count = 0
        current_time = time.time()
        cutoff_time = current_time - (days * 86400)  # 86400 seconds in a day

        for migration_id, migration in all_migrations.items():
            # Skip if still active
            if migration.get("status") == "in_progress":
                continue

            # Check creation time
            created_at = migration.get("created_at", 0)
            if created_at < cutoff_time:
                success = await self.delete(migration_id)
                if success:
                    cleanup_count += 1

        logger.info(f"Cleaned up {cleanup_count} old migration records")
        return cleanup_count