"""
Authentication Service Extensions for API Key Caching

This module adds API key caching capabilities to the authentication service,
addressing the "API key validation could benefit from caching improvements"
issue mentioned in the MCP roadmap.
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List, Callable, Set, Tuple

# Set up logging
logger = logging.getLogger(__name__)

class AuthServiceApiKeyExtension:
    """
    Extension for authentication service to improve API key handling.
    
    This class adds:
    1. Support for key invalidation hooks
    2. Optimized API key updates
    3. Bulk operations for API keys
    """
    
    def __init__(self, auth_service):
        """
        Initialize the extension.
        
        Args:
            auth_service: Authentication service instance to extend
        """
        self.auth_service = auth_service
        
        # Invalidation hooks
        self._invalidation_hooks: List[Callable] = []
        
        # Last used timestamps (to reduce database writes)
        self._last_used_updates = {}
        self._last_update_flush = time.time()
        
        # Add attributes to the auth service
        self.auth_service.register_key_invalidation_hook = self.register_key_invalidation_hook
        self.auth_service.notify_key_invalidation = self.notify_key_invalidation
        self.auth_service.update_api_key_last_used = self.update_api_key_last_used
        
        # Start background task for flushing last used updates
        self._stop_flush_task = asyncio.Event()
        self._flush_task = asyncio.create_task(self._flush_last_used_updates_loop())
        
        logger.info("AuthServiceApiKeyExtension initialized")
    
    def register_key_invalidation_hook(self, hook: Callable) -> None:
        """
        Register a hook to be called when API keys are invalidated.
        
        Args:
            hook: Callback function taking (event_type, data)
        """
        self._invalidation_hooks.append(hook)
    
    def notify_key_invalidation(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Notify all registered hooks of an API key invalidation event.
        
        Args:
            event_type: Type of event (e.g., 'key_revoked', 'user_disabled')
            data: Event data
        """
        for hook in self._invalidation_hooks:
            try:
                hook(event_type, data)
            except Exception as e:
                logger.error(f"Error in API key invalidation hook: {e}")
    
    async def update_api_key_last_used(self, key_id: str) -> None:
        """
        Update the last_used timestamp for an API key.
        
        This method batches updates to reduce database writes.
        
        Args:
            key_id: API key ID
        """
        if not key_id:
            return
            
        # Record update with current timestamp
        self._last_used_updates[key_id] = time.time()
        
        # If too many pending updates or too long since last flush, flush now
        current_time = time.time()
        if (len(self._last_used_updates) > 100 or 
            current_time - self._last_update_flush > 60):
            await self._flush_last_used_updates()
    
    async def _flush_last_used_updates(self) -> None:
        """Flush pending last_used timestamp updates to the database."""
        if not self._last_used_updates:
            return
            
        updates = self._last_used_updates.copy()
        self._last_used_updates.clear()
        self._last_update_flush = time.time()
        
        try:
            # Get API key store from auth service
            api_key_store = getattr(self.auth_service, 'api_key_store', None)
            if not api_key_store:
                logger.warning("API key store not available for flushing updates")
                return
                
            # Process updates in batches
            batch_size = 20
            keys = list(updates.keys())
            
            for i in range(0, len(keys), batch_size):
                batch = keys[i:i+batch_size]
                
                # Process each key in the batch
                for key_id in batch:
                    try:
                        # Get API key data
                        key_data = await api_key_store.get(key_id)
                        if key_data:
                            # Update last_used timestamp
                            key_data["last_used"] = updates[key_id]
                            await api_key_store.update(key_id, key_data)
                    except Exception as e:
                        logger.error(f"Error updating API key {key_id} last_used: {e}")
                
            logger.debug(f"Flushed {len(updates)} API key last_used updates")
                
        except Exception as e:
            logger.error(f"Error flushing API key last_used updates: {e}")
    
    async def _flush_last_used_updates_loop(self) -> None:
        """Background task to periodically flush last_used updates."""
        try:
            while not self._stop_flush_task.is_set():
                # Only flush if there are updates
                if self._last_used_updates:
                    await self._flush_last_used_updates()
                
                # Wait for next flush interval or until stopped
                try:
                    await asyncio.wait_for(
                        self._stop_flush_task.wait(),
                        timeout=30
                    )
                except asyncio.TimeoutError:
                    # Normal timeout, continue
                    pass
                
        except asyncio.CancelledError:
            # Task was cancelled
            logger.info("API key update flush task cancelled")
        except Exception as e:
            logger.error(f"Error in API key update flush loop: {e}")
    
    async def stop(self) -> None:
        """Stop the extension and clean up resources."""
        # Stop the flush task
        self._stop_flush_task.set()
        if self._flush_task:
            try:
                # Cancel the task
                self._flush_task.cancel()
                # Wait for it to complete
                await asyncio.gather(self._flush_task, return_exceptions=True)
            except Exception:
                pass
        
        # Final flush of any pending updates
        await self._flush_last_used_updates()
        
        logger.info("AuthServiceApiKeyExtension stopped")

# Function to extend an existing authentication service
def extend_auth_service(auth_service) -> None:
    """
    Extend an existing authentication service with API key caching capabilities.
    
    Args:
        auth_service: Authentication service to extend
    """
    # Create the extension
    extension = AuthServiceApiKeyExtension(auth_service)
    
    # Add the extension to the service
    auth_service._api_key_extension = extension
    
    # Patch the revoke_api_key method to notify invalidation hooks
    original_revoke_api_key = auth_service.revoke_api_key
    
    async def patched_revoke_api_key(key_id: str, user_id: str) -> Tuple[bool, str]:
        """Patched method that notifies hooks when a key is revoked."""
        result = await original_revoke_api_key(key_id, user_id)
        
        # If successful, notify hooks
        if result[0]:
            auth_service.notify_key_invalidation('key_revoked', {
                'key_id': key_id,
                'user_id': user_id
            })
            
        return result
    
    # Apply the patch
    auth_service.revoke_api_key = patched_revoke_api_key
    
    # Patch revoke_all_user_tokens to notify hooks
    original_revoke_all_user_tokens = auth_service.revoke_all_user_tokens
    
    async def patched_revoke_all_user_tokens(user_id: str) -> int:
        """Patched method that notifies hooks when all user tokens are revoked."""
        count = await original_revoke_all_user_tokens(user_id)
        
        # If any tokens were revoked, notify hooks
        if count > 0:
            auth_service.notify_key_invalidation('user_keys_revoked', {
                'user_id': user_id,
                'count': count
            })
            
        return count
    
    # Apply the patch
    auth_service.revoke_all_user_tokens = patched_revoke_all_user_tokens
    
    logger.info("Authentication service extended with API key caching capabilities")