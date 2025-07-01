"""
Policy store for migration operations in MCP server.

This module provides persistent storage for migration policies
as specified in the MCP roadmap Q2 2025 priorities.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import aiofiles

logger = logging.getLogger(__name__)


class PolicyStore:
    """Persistence store for migration policies."""

    def __init__(self, data_dir: str = None):
        """
        Initialize the policy store.

        Args:
            data_dir: Directory for storing policy data
        """
        if data_dir is None:
            # Default to a data directory in the project
            base_dir = os.environ.get("IPFS_KIT_DATA_DIR", "/tmp/ipfs_kit")
            data_dir = os.path.join(base_dir, "mcp", "policies")

        self.data_dir = data_dir

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        logger.debug(f"Policy store initialized with data directory: {self.data_dir}")

    def _get_policy_path(self, policy_name: str) -> str:
        """
        Get the file path for a policy.

        Args:
            policy_name: Name of the policy

        Returns:
            File path for the policy
        """
        # Sanitize policy name for file storage
        sanitized_name = policy_name.replace("/", "_").replace("\\", "_")
        return os.path.join(self.data_dir, f"{sanitized_name}.json")

    async def create(self, policy_name: str, policy_data: Dict[str, Any]) -> bool:
        """
        Create a new policy record.

        Args:
            policy_name: Name of the policy
            policy_data: Policy data to store

        Returns:
            True if creation was successful
        """
        file_path = self._get_policy_path(policy_name)

        try:
            async with aiofiles.open(file_path, "w") as f:
                await f.write(json.dumps(policy_data, indent=2))
            logger.debug(f"Created policy record: {policy_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create policy record {policy_name}: {e}")
            return False

    async def update(self, policy_name: str, policy_data: Dict[str, Any]) -> bool:
        """
        Update an existing policy record.

        Args:
            policy_name: Name of the policy
            policy_data: Updated policy data

        Returns:
            True if update was successful
        """
        # For simplicity, we use the same method as create
        return await self.create(policy_name, policy_data)

    async def get(self, policy_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a policy record.

        Args:
            policy_name: Name of the policy

        Returns:
            Policy data or None if not found
        """
        file_path = self._get_policy_path(policy_name)

        if not os.path.exists(file_path):
            logger.debug(f"Policy record not found: {policy_name}")
            return None

        try:
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to read policy record {policy_name}: {e}")
            return None

    async def delete(self, policy_name: str) -> bool:
        """
        Delete a policy record.

        Args:
            policy_name: Name of the policy

        Returns:
            True if deletion was successful
        """
        file_path = self._get_policy_path(policy_name)

        if not os.path.exists(file_path):
            logger.debug(f"Policy record not found for deletion: {policy_name}")
            return False

        try:
            os.remove(file_path)
            logger.debug(f"Deleted policy record: {policy_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete policy record {policy_name}: {e}")
            return False

    async def load_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all policy records.

        Returns:
            Dictionary of policy name to policy data
        """
        policies = {}

        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".json"):
                    policy_name = filename.replace(".json", "")
                    file_path = os.path.join(self.data_dir, filename)

                    try:
                        async with aiofiles.open(file_path, "r") as f:
                            content = await f.read()
                            policy_data = json.loads(content)
                            policies[policy_name] = policy_data
                    except Exception as e:
                        logger.error(f"Failed to read policy file {filename}: {e}")
        except Exception as e:
            logger.error(f"Failed to list policy files: {e}")

        logger.debug(f"Loaded {len(policies)} policy records")
        return policies

    async def find_by_backend_pair(
        self, source_backend: str, target_backend: str
    ) -> List[Dict[str, Any]]:
        """
        Find policies for a specific backend pair.

        Args:
            source_backend: Source backend name
            target_backend: Target backend name

        Returns:
            List of matching policy records
        """
        matching_policies = []
        all_policies = await self.load_all()

        for policy_name, policy in all_policies.items():
            if (
                policy.get("source_backend") == source_backend
                and policy.get("target_backend") == target_backend
            ):
                # Add policy name to the data for reference
                policy_with_name = policy.copy()
                policy_with_name["name"] = policy_name
                matching_policies.append(policy_with_name)

        return matching_policies
