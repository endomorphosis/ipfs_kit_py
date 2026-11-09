"""
Persistence stores for authentication and authorization data.

This module provides persistent storage for users, roles, permissions,
API keys, and sessions as part of the Advanced Authentication & Authorization
system specified in the MCP roadmap.
"""

import os
import json
import aiofiles
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseStore:
    """Base class for all persistence stores."""
    def __init__(self, data_dir: str = None, store_name: str = "default"):
        """
        Initialize the base store.

        Args:
            data_dir: Base directory for storing data
            store_name: Name of this specific store
        """
        if data_dir is None:
            # Default to a data directory in the project
            base_dir = os.environ.get("IPFS_KIT_DATA_DIR", "/tmp/ipfs_kit")
            data_dir = os.path.join(base_dir, "mcp", "auth")

        self.data_dir = os.path.join(data_dir, store_name)
        self.store_name = store_name

        # Ensure data directory exists
        self.initialized = False

    async def initialize(self):
        """Initialize the store."""
        if self.initialized:
            return

        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)

        self.initialized = True
        logger.debug(f"Initialized {self.store_name} store in {self.data_dir}")

    def _get_item_path(self, item_id: str) -> str:
        """
        Get the file path for an item.

        Args:
            item_id: ID of the item

        Returns:
            File path for the item
        """
        return os.path.join(self.data_dir, f"{item_id}.json")

    async def create(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Create a new item.

        Args:
            item_id: ID of the item
            item_data: Item data to store

        Returns:
            True if creation was successful
        """
        file_path = self._get_item_path(item_id)

        try:
            async with aiofiles.open(file_path, "w") as f:
                await f.write(json.dumps(item_data, indent=2))
            logger.debug(f"Created {self.store_name} item: {item_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create {self.store_name} item {item_id}: {e}")
            return False

    async def update(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Update an existing item.

        Args:
            item_id: ID of the item
            item_data: Updated item data

        Returns:
            True if update was successful
        """
        file_path = self._get_item_path(item_id)

        try:
            async with aiofiles.open(file_path, "w") as f:
                await f.write(json.dumps(item_data, indent=2))
            logger.debug(f"Updated {self.store_name} item: {item_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update {self.store_name} item {item_id}: {e}")
            return False

    async def get(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an item.

        Args:
            item_id: ID of the item

        Returns:
            Item data or None if not found
        """
        file_path = self._get_item_path(item_id)

        if not os.path.exists(file_path):
            return None

        try:
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to read {self.store_name} item {item_id}: {e}")
            return None

    async def delete(self, item_id: str) -> bool:
        """
        Delete an item.

        Args:
            item_id: ID of the item

        Returns:
            True if deletion was successful
        """
        file_path = self._get_item_path(item_id)

        if not os.path.exists(file_path):
            return False

        try:
            os.remove(file_path)
            logger.debug(f"Deleted {self.store_name} item: {item_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {self.store_name} item {item_id}: {e}")
            return False

    async def load_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all items.

        Returns:
            Dictionary of item ID to item data
        """
        items = {}

        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".json"):
                    item_id = filename.replace(".json", "")
                    file_path = os.path.join(self.data_dir, filename)

                    try:
                        async with aiofiles.open(file_path, "r") as f:
                            content = await f.read()
                            item_data = json.loads(content)
                            items[item_id] = item_data
                    except Exception as e:
                        logger.error(f"Failed to read {self.store_name} file {filename}: {e}")
        except Exception as e:
            logger.error(f"Failed to list {self.store_name} files: {e}")

        return items


class UserStore(BaseStore):
    """Store for user data."""
    def __init__(self, data_dir: str = None):
        """Initialize the user store."""
        super().__init__(data_dir, "users")

        # Index files for fast lookups
        self.username_index_file = os.path.join(self.data_dir, "_username_index.json")
        self.email_index_file = os.path.join(self.data_dir, "_email_index.json")

        # In-memory indexes
        self.username_index = {}  # username -> user_id
        self.email_index = {}  # email -> user_id

    async def initialize(self):
        """Initialize the user store."""
        await super().initialize()

        # Load indexes
        await self._load_indexes()

    async def _load_indexes(self):
        """Load username and email indexes."""
        # Load username index
        if os.path.exists(self.username_index_file):
            try:
                async with aiofiles.open(self.username_index_file, "r") as f:
                    content = await f.read()
                    self.username_index = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load username index: {e}")
                self.username_index = {}

        # Load email index
        if os.path.exists(self.email_index_file):
            try:
                async with aiofiles.open(self.email_index_file, "r") as f:
                    content = await f.read()
                    self.email_index = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load email index: {e}")
                self.email_index = {}

        # If indexes are empty, rebuild them
        if not self.username_index or not self.email_index:
            await self._rebuild_indexes()

    async def _save_indexes(self):
        """Save username and email indexes."""
        # Save username index
        try:
            async with aiofiles.open(self.username_index_file, "w") as f:
                await f.write(json.dumps(self.username_index, indent=2))
        except Exception as e:
            logger.error(f"Failed to save username index: {e}")

        # Save email index
        try:
            async with aiofiles.open(self.email_index_file, "w") as f:
                await f.write(json.dumps(self.email_index, indent=2))
        except Exception as e:
            logger.error(f"Failed to save email index: {e}")

    async def _rebuild_indexes(self):
        """Rebuild username and email indexes from all user files."""
        # Clear indexes
        self.username_index = {}
        self.email_index = {}

        # Load all users
        users = await self.load_all()

        # Build indexes
        for user_id, user_data in users.items():
            username = user_data.get("username")
            email = user_data.get("email")

            if username:
                self.username_index[username] = user_id

            if email:
                self.email_index[email] = user_id

        # Save indexes
        await self._save_indexes()

        logger.info(
            f"Rebuilt user indexes: {len(self.username_index)} usernames, {len(self.email_index)} emails"
        )

    async def create(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Create a new user.

        Args:
            item_id: User ID
            item_data: User data

        Returns:
            True if creation was successful
        """
        # Create user
        success = await super().create(item_id, item_data)
        if not success:
            return False

        # Update indexes
        username = item_data.get("username")
        email = item_data.get("email")

        if username:
            self.username_index[username] = item_id

        if email:
            self.email_index[email] = item_id

        # Save indexes
        await self._save_indexes()

        return True

    async def update(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Update an existing user.

        Args:
            item_id: User ID
            item_data: Updated user data

        Returns:
            True if update was successful
        """
        # Get existing user data
        existing_data = await self.get(item_id)

        # Update user
        success = await super().update(item_id, item_data)
        if not success:
            return False

        # Update indexes if username or email changed
        if existing_data:
            old_username = existing_data.get("username")
            old_email = existing_data.get("email")

            new_username = item_data.get("username")
            new_email = item_data.get("email")

            # Handle username change
            if old_username != new_username:
                if old_username in self.username_index:
                    del self.username_index[old_username]

                if new_username:
                    self.username_index[new_username] = item_id

            # Handle email change
            if old_email != new_email:
                if old_email in self.email_index:
                    del self.email_index[old_email]

                if new_email:
                    self.email_index[new_email] = item_id

            # Save indexes if there were changes
            if old_username != new_username or old_email != new_email:
                await self._save_indexes()

        return True

    async def delete(self, item_id: str) -> bool:
        """
        Delete a user.

        Args:
            item_id: User ID

        Returns:
            True if deletion was successful
        """
        # Get existing user data
        existing_data = await self.get(item_id)

        # Delete user
        success = await super().delete(item_id)
        if not success:
            return False

        # Update indexes
        if existing_data:
            username = existing_data.get("username")
            email = existing_data.get("email")

            if username and username in self.username_index:
                del self.username_index[username]

            if email and email in self.email_index:
                del self.email_index[email]

            # Save indexes
            await self._save_indexes()

        return True

    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by username.

        Args:
            username: Username

        Returns:
            User data or None if not found
        """
        # Check index
        user_id = self.username_index.get(username)
        if not user_id:
            return None

        # Get user by ID
        return await self.get(user_id)

    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email.

        Args:
            email: Email address

        Returns:
            User data or None if not found
        """
        # Check index
        user_id = self.email_index.get(email)
        if not user_id:
            return None

        # Get user by ID
        return await self.get(user_id)


class RoleStore(BaseStore):
    """Store for role data."""
    def __init__(self, data_dir: str = None):
        """Initialize the role store."""
        super().__init__(data_dir, "roles")

        # Index file for fast lookups
        self.name_index_file = os.path.join(self.data_dir, "_name_index.json")

        # In-memory index
        self.name_index = {}  # name -> role_id

    async def initialize(self):
        """Initialize the role store."""
        await super().initialize()

        # Load index
        await self._load_index()

    async def _load_index(self):
        """Load name index."""
        # Load name index
        if os.path.exists(self.name_index_file):
            try:
                async with aiofiles.open(self.name_index_file, "r") as f:
                    content = await f.read()
                    self.name_index = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load role name index: {e}")
                self.name_index = {}

        # If index is empty, rebuild it
        if not self.name_index:
            await self._rebuild_index()

    async def _save_index(self):
        """Save name index."""
        # Save name index
        try:
            async with aiofiles.open(self.name_index_file, "w") as f:
                await f.write(json.dumps(self.name_index, indent=2))
        except Exception as e:
            logger.error(f"Failed to save role name index: {e}")

    async def _rebuild_index(self):
        """Rebuild name index from all role files."""
        # Clear index
        self.name_index = {}

        # Load all roles
        roles = await self.load_all()

        # Build index
        for role_id, role_data in roles.items():
            name = role_data.get("name")

            if name:
                self.name_index[name] = role_id

        # Save index
        await self._save_index()

        logger.info(f"Rebuilt role name index: {len(self.name_index)} names")

    async def create(self, item_id: str, item_data: dict) -> bool:
        """
        Create a new role.

        Args:
            item_id: Role ID
            item_data: Role data

        Returns:
            True if creation was successful
        """
        # Create role
        success = await super().create(item_id, item_data)
        if not success:
            return False

        # Update index
        name = item_data.get("name")

        if name:
            self.name_index[name] = item_id

        # Save index
        await self._save_index()

        return True

    async def update(self, item_id: str, item_data: dict) -> bool:
        """
        Update an existing role.

        Args:
            item_id: Role ID
            item_data: Updated role data

        Returns:
            True if update was successful
        """
        # Get existing role data
        existing_data = await self.get(item_id)

        # Update role
        success = await super().update(item_id, item_data)
        if not success:
            return False

        # Update index if name changed
        if existing_data:
            old_name = existing_data.get("name")
            new_name = item_data.get("name")

            # Handle name change
            if old_name != new_name:
                if old_name in self.name_index:
                    del self.name_index[old_name]

                if new_name:
                    self.name_index[new_name] = item_id

                # Save index
                await self._save_index()

        return True

    async def delete(self, item_id: str) -> bool:
        """
        Delete a role.

        Args:
            item_id: Role ID

        Returns:
            True if deletion was successful
        """
        # Get existing role data
        existing_data = await self.get(item_id)

        # Delete role
        success = await super().delete(item_id)
        if not success:
            return False

        # Update index
        if existing_data:
            name = existing_data.get("name")

            if name and name in self.name_index:
                del self.name_index[name]

            # Save index
            await self._save_index()

        return True

    async def get_by_name(self, name: str) -> Optional[dict]:
        """
        Get a role by name.

        Args:
            name: Role name

        Returns:
            Role data or None if not found
        """
        # Check index
        role_id = self.name_index.get(name)
        if not role_id:
            return None

        # Get role by ID
        return await self.get(role_id)


class PermissionStore(BaseStore):
    """Store for permission data."""
    
    def __init__(self, data_dir: str = None):
        """Initialize the permission store."""
        super().__init__(data_dir, "permissions")

        # Index file for fast lookups
        self.name_index_file = os.path.join(self.data_dir, "_name_index.json")

        # In-memory index
        self.name_index = {}  # name -> permission_id

    async def initialize(self):
        """Initialize the permission store."""
        await super().initialize()

        # Load index
        await self._load_index()

    async def _load_index(self):
        """Load name index."""
        # Load name index
        if os.path.exists(self.name_index_file):
            try:
                async with aiofiles.open(self.name_index_file, "r") as f:
                    content = await f.read()
                    self.name_index = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load permission name index: {e}")
                self.name_index = {}

        # If index is empty, rebuild it
        if not self.name_index:
            await self._rebuild_index()

    async def _save_index(self):
        """Save name index."""
        # Save name index
        try:
            async with aiofiles.open(self.name_index_file, "w") as f:
                await f.write(json.dumps(self.name_index, indent=2))
        except Exception as e:
            logger.error(f"Failed to save permission name index: {e}")

    async def _rebuild_index(self):
        """Rebuild name index from all permission files."""
        # Clear index
        self.name_index = {}

        # Load all permissions
        permissions = await self.load_all()

        # Build index
        for perm_id, perm_data in permissions.items():
            name = perm_data.get("name")

            if name:
                self.name_index[name] = perm_id

        # Save index
        await self._save_index()

        logger.info(f"Rebuilt permission name index: {len(self.name_index)} names")

    async def create(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Create a new permission.

        Args:
            item_id: Permission ID
            item_data: Permission data

        Returns:
            True if creation was successful
        """
        # Create permission
        success = await super().create(item_id, item_data)
        if not success:
            return False

        # Update index
        name = item_data.get("name")

        if name:
            self.name_index[name] = item_id

        # Save index
        await self._save_index()

        return True

    async def update(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Update an existing permission.

        Args:
            item_id: Permission ID
            item_data: Updated permission data

        Returns:
            True if update was successful
        """
        # Get existing permission data
        existing_data = await self.get(item_id)

        # Update permission
        success = await super().update(item_id, item_data)
        if not success:
            return False

        # Update index if name changed
        if existing_data:
            old_name = existing_data.get("name")
            new_name = item_data.get("name")

            # Handle name change
            if old_name != new_name:
                if old_name in self.name_index:
                    del self.name_index[old_name]

                if new_name:
                    self.name_index[new_name] = item_id

                # Save index
                await self._save_index()

        return True

    async def delete(self, item_id: str) -> bool:
        """
        Delete a permission.

        Args:
            item_id: Permission ID

        Returns:
            True if deletion was successful
        """
        # Get existing permission data
        existing_data = await self.get(item_id)

        # Delete permission
        success = await super().delete(item_id)
        if not success:
            return False

        # Update index
        if existing_data:
            name = existing_data.get("name")

            if name and name in self.name_index:
                del self.name_index[name]

            # Save index
            await self._save_index()

        return True

    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a permission by name.

        Args:
            name: Permission name

        Returns:
            Permission data or None if not found
        """
        # Check index
        perm_id = self.name_index.get(name)
        if not perm_id:
            return None

        # Get permission by ID
        return await self.get(perm_id)


class ApiKeyStore(BaseStore):
    """Store for API key data."""

    def __init__(self, data_dir: str = None):
        """Initialize the API key store."""
        super().__init__(data_dir, "apikeys")
        # Index file for mapping users to API keys
        self.user_index_file = os.path.join(self.data_dir, "_user_index.json")

        # In-memory index
        self.user_index = {}  # user_id -> list of key_ids

    async def initialize(self):
        """Initialize the API key store."""
        await super().initialize()

        # Load index
        await self._load_index()

    async def _load_index(self):
        """Load user index."""
        # Load user index
        if os.path.exists(self.user_index_file):
            try:
                async with aiofiles.open(self.user_index_file, "r") as f:
                    content = await f.read()
                    self.user_index = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load API key user index: {e}")
                self.user_index = {}

        # If index is empty, rebuild it
        if not self.user_index:
            await self._rebuild_index()

    async def _save_index(self):
        """Save user index."""
        # Save user index
        try:
            async with aiofiles.open(self.user_index_file, "w") as f:
                await f.write(json.dumps(self.user_index, indent=2))
        except Exception as e:
            logger.error(f"Failed to save API key user index: {e}")

    async def _rebuild_index(self):
        """Rebuild user index from all API key files."""
        # Clear index
        self.user_index = {}

        # Load all API keys
        api_keys = await self.load_all()

        # Build index
        for key_id, key_data in api_keys.items():
            user_id = key_data.get("user_id")

            if user_id:
                if user_id not in self.user_index:
                    self.user_index[user_id] = []

                self.user_index[user_id].append(key_id)

        # Save index
        await self._save_index()

        logger.info(f"Rebuilt API key user index: {len(self.user_index)} users")

    async def create(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Create a new API key.

        Args:
            item_id: API key ID
            item_data: API key data

        Returns:
            True if creation was successful
        """
        # Create API key
        success = await super().create(item_id, item_data)
        if not success:
            return False

        # Update index
        user_id = item_data.get("user_id")

        if user_id:
            if user_id not in self.user_index:
                self.user_index[user_id] = []

            self.user_index[user_id].append(item_id)

        # Save index
        await self._save_index()

        return True

    async def update(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Update an existing API key.

        Args:
            item_id: API key ID
            item_data: Updated API key data

        Returns:
            True if update was successful
        """
        # Get existing API key data
        existing_data = await self.get(item_id)

        # Update API key
        success = await super().update(item_id, item_data)
        if not success:
            return False

        # Update index if user_id changed
        if existing_data:
            old_user_id = existing_data.get("user_id")
            new_user_id = item_data.get("user_id")

            # Handle user_id change
            if old_user_id != new_user_id:
                # Remove from old user's list
                if old_user_id and old_user_id in self.user_index:
                    if item_id in self.user_index[old_user_id]:
                        self.user_index[old_user_id].remove(item_id)

                    # Clean up empty lists
                    if not self.user_index[old_user_id]:
                        del self.user_index[old_user_id]

                # Add to new user's list
                if new_user_id:
                    if new_user_id not in self.user_index:
                        self.user_index[new_user_id] = []

                    self.user_index[new_user_id].append(item_id)

                # Save index
                await self._save_index()

        return True

    async def delete(self, item_id: str) -> bool:
        """
        Delete an API key.

        Args:
            item_id: API key ID

        Returns:
            True if deletion was successful
        """
        # Get existing API key data
        existing_data = await self.get(item_id)

        # Delete API key
        success = await super().delete(item_id)
        if not success:
            return False

        # Update index
        if existing_data:
            user_id = existing_data.get("user_id")

            if user_id and user_id in self.user_index:
                if item_id in self.user_index[user_id]:
                    self.user_index[user_id].remove(item_id)

                # Clean up empty lists
                if not self.user_index[user_id]:
                    del self.user_index[user_id]

                # Save index
                await self._save_index()

        return True

    async def get_by_user(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary of API key ID to API key data
        """
        # Check index
        key_ids = self.user_index.get(user_id, [])

        # Get API keys by ID
        keys = {}
        for key_id in key_ids:
            key_data = await self.get(key_id)
            if key_data:
                keys[key_id] = key_data

        return keys


class SessionStore(BaseStore):
    """Store for session data."""
    
    def __init__(self, data_dir: str = None):
        """Initialize the session store."""
        super().__init__(data_dir, "sessions")

        # Index file for mapping users to sessions
        self.user_index_file = os.path.join(self.data_dir, "_user_index.json")

        # In-memory index
        self.user_index = {}  # user_id -> list of session_ids

    async def initialize(self):
        """Initialize the session store."""
        await super().initialize()

        # Load index
        await self._load_index()

    async def _load_index(self):
        """Load user index."""
        # Load user index
        if os.path.exists(self.user_index_file):
            try:
                async with aiofiles.open(self.user_index_file, "r") as f:
                    content = await f.read()
                    self.user_index = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load session user index: {e}")
                self.user_index = {}

        # If index is empty, rebuild it
        if not self.user_index:
            await self._rebuild_index()

    async def _save_index(self):
        """Save user index."""
        # Save user index
        try:
            async with aiofiles.open(self.user_index_file, "w") as f:
                await f.write(json.dumps(self.user_index, indent=2))
        except Exception as e:
            logger.error(f"Failed to save session user index: {e}")

    async def _rebuild_index(self):
        """Rebuild user index from all session files."""
        # Clear index
        self.user_index = {}

        # Load all sessions
        sessions = await self.load_all()

        # Build index
        for session_id, session_data in sessions.items():
            user_id = session_data.get("user_id")

            if user_id:
                if user_id not in self.user_index:
                    self.user_index[user_id] = []

                self.user_index[user_id].append(session_id)

        # Save index
        await self._save_index()

        logger.info(f"Rebuilt session user index: {len(self.user_index)} users")

    async def create(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Create a new session.

        Args:
            item_id: Session ID
            item_data: Session data

        Returns:
            True if creation was successful
        """
        # Create session
        success = await super().create(item_id, item_data)
        if not success:
            return False

        # Update index
        user_id = item_data.get("user_id")

        if user_id:
            if user_id not in self.user_index:
                self.user_index[user_id] = []

            self.user_index[user_id].append(item_id)

        # Save index
        await self._save_index()

        return True

    async def update(self, item_id: str, item_data: Dict[str, Any]) -> bool:
        """
        Update an existing session.

        Args:
            item_id: Session ID
            item_data: Updated session data

        Returns:
            True if update was successful
        """
        # Get existing session data
        existing_data = await self.get(item_id)

        # Update session
        success = await super().update(item_id, item_data)
        if not success:
            return False

        # Update index if user_id changed
        if existing_data:
            old_user_id = existing_data.get("user_id")
            new_user_id = item_data.get("user_id")

            # Handle user_id change
            if old_user_id != new_user_id:
                # Remove from old user's list
                if old_user_id and old_user_id in self.user_index:
                    if item_id in self.user_index[old_user_id]:
                        self.user_index[old_user_id].remove(item_id)

                    # Clean up empty lists
                    if not self.user_index[old_user_id]:
                        del self.user_index[old_user_id]

                # Add to new user's list
                if new_user_id:
                    if new_user_id not in self.user_index:
                        self.user_index[new_user_id] = []

                    self.user_index[new_user_id].append(item_id)

                # Save index
                await self._save_index()

        return True

    async def delete(self, item_id: str) -> bool:
        """
        Delete a session.

        Args:
            item_id: Session ID

        Returns:
            True if deletion was successful
        """
        # Get existing session data
        existing_data = await self.get(item_id)

        # Delete session
        success = await super().delete(item_id)
        if not success:
            return False

        # Update index
        if existing_data:
            user_id = existing_data.get("user_id")

            if user_id and user_id in self.user_index:
                if item_id in self.user_index[user_id]:
                    self.user_index[user_id].remove(item_id)

                # Clean up empty lists
                if not self.user_index[user_id]:
                    del self.user_index[user_id]

                # Save index
                await self._save_index()

        return True

    async def find_by_user(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary of session ID to session data
        """
        # Check index
        session_ids = self.user_index.get(user_id, [])

        # Get sessions by ID
        sessions = {}
        for session_id in session_ids:
            session_data = await self.get(session_id)
            if session_data:
                sessions[session_id] = session_data

        return sessions

    async def cleanup_expired(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions deleted
        """
        # Get all sessions
        sessions = await self.load_all()

        # Find expired sessions
        now = time.time()
        expired_count = 0

        for session_id, session_data in sessions.items():
            expires_at = session_data.get("expires_at", 0)

            if expires_at < now:
                # Delete expired session
                await self.delete(session_id)
                expired_count += 1

        return expired_count