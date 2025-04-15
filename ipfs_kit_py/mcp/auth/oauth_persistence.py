"""
OAuth Persistence Extensions for MCP Server

This module extends the persistence system to support OAuth functionality:
- OAuth provider configuration storage
- User OAuth connection management 
- Token and state management

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import aiofiles

from ipfs_kit_py.mcp.auth.persistence import BaseStore, get_persistence_manager

logger = logging.getLogger(__name__)


class OAuthStore(BaseStore):
    """
    Persistent storage for OAuth-related data.
    
    Stores:
    - Provider configurations
    - User OAuth connections
    - OAuth states for CSRF protection
    """
    
    def __init__(self, data_dir: str = None):
        """Initialize the OAuth store."""
        super().__init__(data_dir, "oauth")
        self.providers_file = os.path.join(self.data_dir, "providers.json")
        self.connections_file = os.path.join(self.data_dir, "connections.json")
        self.states_file = os.path.join(self.data_dir, "states.json")
        
    async def initialize(self):
        """Initialize the OAuth store."""
        await super().initialize()
        
        # Create initial files if they don't exist
        for file_path in [self.providers_file, self.connections_file, self.states_file]:
            if not os.path.exists(file_path):
                async with aiofiles.open(file_path, "w") as f:
                    await f.write("{}")
    
    async def get_oauth_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all OAuth provider configurations.
        
        Returns:
            Dictionary of provider ID to provider config
        """
        await self.initialize()
        try:
            async with aiofiles.open(self.providers_file, "r") as f:
                content = await f.read()
                providers = json.loads(content if content else "{}")
            return providers
        except Exception as e:
            logger.error(f"Error loading OAuth providers: {e}")
            return {}
    
    async def save_oauth_provider(self, provider_id: str, config: Dict[str, Any]) -> bool:
        """
        Save an OAuth provider configuration.
        
        Args:
            provider_id: Provider ID
            config: Provider configuration
            
        Returns:
            True if saved successfully
        """
        await self.initialize()
        try:
            # Load existing providers
            providers = await self.get_oauth_providers()
            
            # Update provider
            providers[provider_id] = config
            
            # Save back to file
            async with aiofiles.open(self.providers_file, "w") as f:
                await f.write(json.dumps(providers, indent=2))
            
            return True
        except Exception as e:
            logger.error(f"Error saving OAuth provider {provider_id}: {e}")
            return False
    
    async def delete_oauth_provider(self, provider_id: str) -> bool:
        """
        Delete an OAuth provider configuration.
        
        Args:
            provider_id: Provider ID
            
        Returns:
            True if deleted successfully
        """
        await self.initialize()
        try:
            # Load existing providers
            providers = await self.get_oauth_providers()
            
            # Remove provider if it exists
            if provider_id in providers:
                del providers[provider_id]
                
                # Save back to file
                async with aiofiles.open(self.providers_file, "w") as f:
                    await f.write(json.dumps(providers, indent=2))
                
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error deleting OAuth provider {provider_id}: {e}")
            return False
    
    async def find_user_by_oauth(
        self, provider_id: str, provider_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a user by OAuth provider ID and provider user ID.
        
        Args:
            provider_id: Provider ID
            provider_user_id: User ID from the provider
            
        Returns:
            User data if found, None otherwise
        """
        await self.initialize()
        try:
            # Load connections
            async with aiofiles.open(self.connections_file, "r") as f:
                content = await f.read()
                connections = json.loads(content if content else "{}")
            
            # Look for matching connection
            for user_id, user_connections in connections.items():
                for connection in user_connections:
                    if (connection.get("provider_id") == provider_id and 
                        connection.get("provider_user_id") == provider_user_id):
                        # Get the user from the main persistence store
                        persistence = get_persistence_manager()
                        return await persistence.get_user(user_id)
            
            return None
        except Exception as e:
            logger.error(f"Error finding user by OAuth: {e}")
            return None
    
    async def find_oauth_connection(
        self, user_id: str, provider_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find an OAuth connection for a user.
        
        Args:
            user_id: User ID
            provider_id: Provider ID
            
        Returns:
            Connection data if found, None otherwise
        """
        await self.initialize()
        try:
            # Load connections
            async with aiofiles.open(self.connections_file, "r") as f:
                content = await f.read()
                connections = json.loads(content if content else "{}")
            
            # Get user connections
            user_connections = connections.get(user_id, [])
            
            # Find matching connection
            for connection in user_connections:
                if connection.get("provider_id") == provider_id:
                    return connection
            
            return None
        except Exception as e:
            logger.error(f"Error finding OAuth connection: {e}")
            return None
    
    async def create_oauth_connection(
        self, user_id: str, provider_id: str, provider_user_id: str, 
        provider_data: Dict[str, Any]
    ) -> bool:
        """
        Create an OAuth connection for a user.
        
        Args:
            user_id: User ID
            provider_id: Provider ID
            provider_user_id: User ID from the provider
            provider_data: Additional provider-specific data
            
        Returns:
            True if created successfully
        """
        await self.initialize()
        try:
            # Load connections
            async with aiofiles.open(self.connections_file, "r") as f:
                content = await f.read()
                connections = json.loads(content if content else "{}")
            
            # Get or create user connections
            user_connections = connections.get(user_id, [])
            
            # Create new connection
            now = datetime.utcnow().isoformat()
            connection = {
                "provider_id": provider_id,
                "provider_user_id": provider_user_id,
                "created_at": now,
                "updated_at": now,
                "last_used": now,
                **provider_data
            }
            
            # Add to user connections
            user_connections.append(connection)
            connections[user_id] = user_connections
            
            # Save back to file
            async with aiofiles.open(self.connections_file, "w") as f:
                await f.write(json.dumps(connections, indent=2))
            
            return True
        except Exception as e:
            logger.error(f"Error creating OAuth connection: {e}")
            return False
    
    async def update_oauth_connection(
        self, user_id: str, provider_id: str, provider_user_id: str, 
        provider_data: Dict[str, Any]
    ) -> bool:
        """
        Update an OAuth connection for a user.
        
        Args:
            user_id: User ID
            provider_id: Provider ID
            provider_user_id: User ID from the provider
            provider_data: Additional provider-specific data
            
        Returns:
            True if updated successfully
        """
        await self.initialize()
        try:
            # Load connections
            async with aiofiles.open(self.connections_file, "r") as f:
                content = await f.read()
                connections = json.loads(content if content else "{}")
            
            # Get user connections
            user_connections = connections.get(user_id, [])
            
            # Find and update existing connection
            updated = False
            for i, connection in enumerate(user_connections):
                if connection.get("provider_id") == provider_id:
                    # Update connection
                    now = datetime.utcnow().isoformat()
                    user_connections[i] = {
                        **connection,
                        "provider_user_id": provider_user_id,
                        "updated_at": now,
                        "last_used": now,
                        **provider_data
                    }
                    updated = True
                    break
            
            if not updated:
                # Connection not found, create new one
                return await self.create_oauth_connection(
                    user_id, provider_id, provider_user_id, provider_data
                )
            
            # Save back to file
            connections[user_id] = user_connections
            async with aiofiles.open(self.connections_file, "w") as f:
                await f.write(json.dumps(connections, indent=2))
            
            return True
        except Exception as e:
            logger.error(f"Error updating OAuth connection: {e}")
            return False
    
    async def delete_oauth_connection(
        self, user_id: str, provider_id: str
    ) -> bool:
        """
        Delete an OAuth connection for a user.
        
        Args:
            user_id: User ID
            provider_id: Provider ID
            
        Returns:
            True if deleted successfully
        """
        await self.initialize()
        try:
            # Load connections
            async with aiofiles.open(self.connections_file, "r") as f:
                content = await f.read()
                connections = json.loads(content if content else "{}")
            
            # Get user connections
            user_connections = connections.get(user_id, [])
            if not user_connections:
                return False
            
            # Filter out the connection to delete
            new_connections = [
                conn for conn in user_connections 
                if conn.get("provider_id") != provider_id
            ]
            
            if len(new_connections) == len(user_connections):
                # No connection was removed
                return False
            
            # Update user connections
            connections[user_id] = new_connections
            
            # Save back to file
            async with aiofiles.open(self.connections_file, "w") as f:
                await f.write(json.dumps(connections, indent=2))
            
            return True
        except Exception as e:
            logger.error(f"Error deleting OAuth connection: {e}")
            return False
    
    async def get_user_oauth_connections(
        self, user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all OAuth connections for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of connection data
        """
        await self.initialize()
        try:
            # Load connections
            async with aiofiles.open(self.connections_file, "r") as f:
                content = await f.read()
                connections = json.loads(content if content else "{}")
            
            # Get user connections
            return connections.get(user_id, [])
        except Exception as e:
            logger.error(f"Error getting user OAuth connections: {e}")
            return []
    
    async def save_oauth_state(
        self, state: str, data: Dict[str, Any], expires_in: int = 600
    ) -> bool:
        """
        Save an OAuth state for CSRF protection.
        
        Args:
            state: State string
            data: Associated state data
            expires_in: Time in seconds until the state expires
            
        Returns:
            True if saved successfully
        """
        await self.initialize()
        try:
            # Load states
            async with aiofiles.open(self.states_file, "r") as f:
                content = await f.read()
                states = json.loads(content if content else "{}")
            
            # Clean up expired states
            now = time.time()
            states = {
                k: v for k, v in states.items() 
                if v.get("expires_at", 0) > now
            }
            
            # Add new state
            states[state] = {
                "data": data,
                "created_at": now,
                "expires_at": now + expires_in
            }
            
            # Save back to file
            async with aiofiles.open(self.states_file, "w") as f:
                await f.write(json.dumps(states, indent=2))
            
            return True
        except Exception as e:
            logger.error(f"Error saving OAuth state: {e}")
            return False
    
    async def verify_oauth_state(self, state: str) -> Optional[Dict[str, Any]]:
        """
        Verify an OAuth state and return the associated data.
        
        Args:
            state: State string
            
        Returns:
            State data if valid, None otherwise
        """
        await self.initialize()
        try:
            # Load states
            async with aiofiles.open(self.states_file, "r") as f:
                content = await f.read()
                states = json.loads(content if content else "{}")
            
            # Get state if it exists and hasn't expired
            state_data = states.get(state)
            if not state_data:
                return None
            
            now = time.time()
            if state_data.get("expires_at", 0) < now:
                # State has expired
                return None
            
            # Remove the used state
            del states[state]
            
            # Save back to file
            async with aiofiles.open(self.states_file, "w") as f:
                await f.write(json.dumps(states, indent=2))
            
            return state_data.get("data", {})
        except Exception as e:
            logger.error(f"Error verifying OAuth state: {e}")
            return None


# Create singleton instance
_oauth_store_instance = None

def get_oauth_store() -> OAuthStore:
    """
    Get the OAuth store singleton instance.
    
    Returns:
        OAuthStore instance
    """
    global _oauth_store_instance
    if _oauth_store_instance is None:
        _oauth_store_instance = OAuthStore()
    return _oauth_store_instance


# Extend the persistence manager with OAuth methods
def extend_persistence_manager():
    """
    Extend the persistence manager with OAuth methods.
    
    This function adds OAuth-related methods to the base persistence manager.
    """
    from ipfs_kit_py.mcp.auth.persistence import PersistenceManager
    
    # Get the OAuth store
    oauth_store = get_oauth_store()
    
    # Add OAuth methods to the persistence manager
    PersistenceManager.get_oauth_providers = oauth_store.get_oauth_providers
    PersistenceManager.save_oauth_provider = oauth_store.save_oauth_provider
    PersistenceManager.delete_oauth_provider = oauth_store.delete_oauth_provider
    PersistenceManager.find_user_by_oauth = oauth_store.find_user_by_oauth
    PersistenceManager.find_oauth_connection = oauth_store.find_oauth_connection
    PersistenceManager.create_oauth_connection = oauth_store.create_oauth_connection
    PersistenceManager.update_oauth_connection = oauth_store.update_oauth_connection
    PersistenceManager.delete_oauth_connection = oauth_store.delete_oauth_connection
    PersistenceManager.get_user_oauth_connections = oauth_store.get_user_oauth_connections
    PersistenceManager.save_oauth_state = oauth_store.save_oauth_state
    PersistenceManager.verify_oauth_state = oauth_store.verify_oauth_state
    
    logger.info("Extended persistence manager with OAuth methods")