"""
Protobuf compatibility layer.

This module provides compatibility wrappers for different versions of the protobuf library.
It handles API differences between older and newer versions of protobuf, particularly
around MessageFactory which changed significantly between versions.
"""

import logging
import importlib
from typing import Any, Dict, Optional, Type, Callable, Union

# Configure logger
logger = logging.getLogger(__name__)

# Check protobuf version
try:
    from google.protobuf import __version__ as PROTOBUF_VERSION
    logger.info(f"Detected protobuf version: {PROTOBUF_VERSION}")
except ImportError:
    PROTOBUF_VERSION = "unknown"
    logger.warning("Could not determine protobuf version")

# Define compatibility flags
HAS_OLD_MESSAGE_FACTORY = False
HAS_NEW_MESSAGE_FACTORY = False

logger.info(f"HAS_OLD_MESSAGE_FACTORY: {HAS_OLD_MESSAGE_FACTORY}")
logger.info(f"HAS_NEW_MESSAGE_FACTORY: {HAS_NEW_MESSAGE_FACTORY}")

# Normalized version components
PROTOBUF_MAJOR_VERSION = 0
PROTOBUF_MINOR_VERSION = 0
PROTOBUF_PATCH_VERSION = 0

# Parse version string
if PROTOBUF_VERSION != "unknown":
    try:
        version_parts = PROTOBUF_VERSION.split('.')
        PROTOBUF_MAJOR_VERSION = int(version_parts[0])
        if len(version_parts) > 1:
            PROTOBUF_MINOR_VERSION = int(version_parts[1])
        if len(version_parts) > 2:
            # Handle potential suffixes like '1.2.3rc1'
            patch_str = ''.join(c for c in version_parts[2] if c.isdigit())
            PROTOBUF_PATCH_VERSION = int(patch_str) if patch_str else 0
    except (ValueError, IndexError) as e:
        logger.warning(f"Error parsing protobuf version: {e}")

# Check for message factory compatibility
try:
    from google.protobuf.descriptor_pool import DescriptorPool
    from google.protobuf.message_factory import MessageFactory
    
    # Try old API (GetPrototype)
    try:
        factory = MessageFactory()
        # This will raise AttributeError if the method doesn't exist
        get_prototype_method = getattr(factory, "GetPrototype", None)
        if get_prototype_method is not None:
            HAS_OLD_MESSAGE_FACTORY = True
            logger.debug("MessageFactory.GetPrototype method is available")
    except (AttributeError, TypeError):
        pass
    
    # Try new API (message_factory_for_descriptor_pool)
    try:
        from google.protobuf.message_factory import message_factory_for_descriptor_pool
        HAS_NEW_MESSAGE_FACTORY = True
        logger.debug("message_factory_for_descriptor_pool function is available")
    except ImportError:
        pass
        
except ImportError as e:
    logger.warning(f"Protobuf message factory not available: {e}")


class CompatMessageFactory:
    """
    Compatibility wrapper for MessageFactory.
    
    This class provides a consistent interface for MessageFactory across
    different protobuf versions, particularly handling the removal of
    GetPrototype method in newer versions.
    """
    
    def __init__(self):
        """Initialize the compatible message factory."""
        self.descriptor_pool = DescriptorPool()
        
        # Create the appropriate factory based on available API
        if HAS_NEW_MESSAGE_FACTORY:
            # New API (protobuf v3.19.0+)
            from google.protobuf.message_factory import message_factory_for_descriptor_pool
            self._factory_func = message_factory_for_descriptor_pool
            self._factory = None  # Not needed with new API
            logger.debug("Using new MessageFactory API")
        elif HAS_OLD_MESSAGE_FACTORY:
            # Old API
            self._factory = MessageFactory(self.descriptor_pool)
            self._factory_func = None  # Not needed with old API
            logger.debug("Using old MessageFactory API")
        else:
            raise ImportError("Neither old nor new MessageFactory API is available")
    
    def GetPrototype(self, descriptor):
        """
        Get a message class based on the descriptor.
        
        This method provides compatibility with the old GetPrototype method.
        
        Args:
            descriptor: The descriptor for the message
            
        Returns:
            Message class for the descriptor
        """
        if HAS_NEW_MESSAGE_FACTORY:
            # New API approach
            return self._factory_func(self.descriptor_pool).GetPrototype(descriptor)
        else:
            # Old API approach
            return self._factory.GetPrototype(descriptor)
    
    def get_prototype(self, descriptor):
        """
        Pythonic alias for GetPrototype.
        
        Args:
            descriptor: The descriptor for the message
            
        Returns:
            Message class for the descriptor
        """
        return self.GetPrototype(descriptor)


def get_compatible_message_factory():
    """
    Get a MessageFactory instance that works across protobuf versions.
    
    This function provides a consistent interface for creating message
    factories regardless of the protobuf version.
    
    Returns:
        CompatMessageFactory: A compatible message factory instance
        
    Raises:
        ImportError: If protobuf is not available or if no compatible
                     message factory implementation can be found
    """
    try:
        return CompatMessageFactory()
    except ImportError as e:
        logger.error(f"Could not create compatible message factory: {e}")
        raise


def monkey_patch_message_factory():
    """
    Monkey patch the protobuf MessageFactory to ensure compatibility.
    
    This function applies patches to the MessageFactory class to ensure
    that older code expecting the GetPrototype method will continue to
    work with newer protobuf versions.
    
    Returns:
        bool: True if patching was successful, False otherwise
    """
    if not HAS_NEW_MESSAGE_FACTORY or HAS_OLD_MESSAGE_FACTORY:
        # No need to patch if using old API or if new API is not available
        return False
        
    try:
        from google.protobuf.message_factory import MessageFactory
        from google.protobuf.message_factory import message_factory_for_descriptor_pool
        
        # Check if GetPrototype already exists
        if hasattr(MessageFactory, 'GetPrototype'):
            logger.debug("MessageFactory.GetPrototype already exists, no patching needed")
            return True
            
        # Define the compatibility method
        def get_prototype(self, descriptor):
            """
            Compatibility wrapper for GetPrototype.
            
            This method provides backwards compatibility with older protobuf versions
            by implementing the GetPrototype method using the new API.
            
            Args:
                descriptor: The descriptor for the message
                
            Returns:
                Message class for the descriptor
            """
            # Use the new API to create a message class
            pool = getattr(self, '_descriptor_pool', None)
            if pool is None:
                from google.protobuf.descriptor_pool import DescriptorPool
                pool = DescriptorPool()
            
            # Get the message class using the new API
            factory = message_factory_for_descriptor_pool(pool)
            return factory.GetPrototype(descriptor)
        
        # Add the method to the class
        setattr(MessageFactory, 'GetPrototype', get_prototype)
        logger.info("Successfully patched MessageFactory.GetPrototype")
        return True
        
    except (ImportError, AttributeError, TypeError) as e:
        logger.error(f"Failed to patch MessageFactory: {e}")
        return False


# Apply monkey patch if the old GetPrototype method is not available
if not HAS_OLD_MESSAGE_FACTORY:
    success = monkey_patch_message_factory()
    if success:
        logger.info("Successfully applied MessageFactory compatibility patch")
    else:
        logger.warning("Failed to apply MessageFactory compatibility patch")
