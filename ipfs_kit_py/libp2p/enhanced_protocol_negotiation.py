"""
Enhanced protocol negotiation system for libp2p.

This module implements a more robust protocol negotiation system that supports:
1. Semantic versioning with proper compatibility checking
2. Protocol capabilities discovery and negotiation
3. Fallback mechanisms for compatibility with older versions
4. Efficient handshaking with reduced round trips
5. Protocol feature detection

The module extends the basic multiselect protocol with these additional features
while maintaining backward compatibility with standard libp2p implementations.

Usage:
    from ipfs_kit_py.libp2p.enhanced_protocol_negotiation import EnhancedMultiselect
    
    # Server-side usage
    multiselect = EnhancedMultiselect(handlers={"/my-protocol/1.0.0": my_handler})
    
    # Client-side usage
    client = EnhancedMultiselectClient()
    protocol = await client.select_one_of(["/my-protocol/1.0.0"], communicator)
"""

import re
import logging
import anyio
import semver
from typing import Dict, List, Set, Tuple, Callable, Optional, Any, Union, Sequence
from collections import defaultdict

# Assuming we're using libp2p
try:
    from libp2p.abc import IMultiselectMuxer, IMultiselectClient, IMultiselectCommunicator
    from libp2p.custom_types import StreamHandlerFn, TProtocol
    from libp2p.protocol_muxer.multiselect import Multiselect, is_valid_handshake
    from libp2p.protocol_muxer.multiselect_client import MultiselectClient
    from libp2p.protocol_muxer.exceptions import (
        MultiselectError, 
        MultiselectClientError, 
        MultiselectCommunicatorError
    )
    LIBP2P_AVAILABLE = True
except ImportError:
    # Define stub types for documentation and type checking
    class IMultiselectMuxer:
        pass
    
    class IMultiselectClient:
        pass
    
    class IMultiselectCommunicator:
        pass
    
    class Multiselect:
        pass
    
    class MultiselectClient:
        pass
    
    class MultiselectError(Exception):
        pass
    
    class MultiselectClientError(Exception):
        pass
    
    class MultiselectCommunicatorError(Exception):
        pass
    
    StreamHandlerFn = Callable[[Any], None]
    TProtocol = str
    
    def is_valid_handshake(handshake_contents):
        return False
    
    LIBP2P_AVAILABLE = False


# Configure logger
logger = logging.getLogger(__name__)

# Enhanced multiselect protocol ID with capability support
ENHANCED_MULTISELECT_PROTOCOL_ID = "/multistream-select-enhanced/1.0.0"

# Standard multiselect protocol ID for backward compatibility
STANDARD_MULTISELECT_PROTOCOL_ID = "/multistream/1.0.0"

# Protocol capability marker
CAPABILITY_MARKER = "cap:"

# Protocol not found message
PROTOCOL_NOT_FOUND_MSG = "na"

# Protocol capabilities query command
LIST_CAPABILITIES_CMD = "caps"

# Protocol semver support command
VERSION_QUERY_CMD = "semver:"


class ProtocolMeta:
    """
    Metadata for a protocol including version information and capabilities.
    """
    
    def __init__(self, protocol_id: str, handler: StreamHandlerFn):
        """
        Initialize protocol metadata.
        
        Args:
            protocol_id: The protocol identifier (e.g., "/ipfs/kad/1.0.0")
            handler: The handler function for this protocol
        """
        self.protocol_id = protocol_id
        self.handler = handler
        self.base_name, self.version = self._parse_protocol_id(protocol_id)
        self.capabilities: Set[str] = set()
    
    def _parse_protocol_id(self, protocol_id: str) -> Tuple[str, str]:
        """
        Parse a protocol ID into base name and version.
        
        Args:
            protocol_id: The protocol identifier (e.g., "/ipfs/kad/1.0.0")
            
        Returns:
            Tuple of (base_name, version)
        """
        # Default to empty version if we can't parse
        base_name = protocol_id
        version = ""
        
        # Common patterns:
        # 1. /ipfs/kad/1.0.0
        # 2. /libp2p/circuit/relay/0.1.0
        # 3. /meshsub/1.1.0
        
        # Try to find version at the end
        parts = protocol_id.split('/')
        
        # Check if the last part looks like a version (e.g., 1.0.0)
        if parts and re.match(r'^\d+\.\d+\.\d+$', parts[-1]):
            version = parts[-1]
            base_name = '/'.join(parts[:-1])
        
        return base_name, version
    
    def add_capability(self, capability: str) -> None:
        """
        Add a capability to this protocol.
        
        Args:
            capability: Capability string
        """
        self.capabilities.add(capability)
    
    def has_capability(self, capability: str) -> bool:
        """
        Check if the protocol has a specific capability.
        
        Args:
            capability: Capability to check
            
        Returns:
            True if the protocol has the capability, False otherwise
        """
        return capability in self.capabilities
    
    def is_version_compatible(self, other_version: str) -> bool:
        """
        Check if this protocol version is compatible with another version.
        
        Args:
            other_version: Version to check compatibility with
            
        Returns:
            True if versions are compatible, False otherwise
        """
        # Empty version means any version is acceptable
        if not self.version or not other_version:
            return True
        
        try:
            # Use semver to check compatibility
            # Only major version changes break compatibility
            v1 = semver.VersionInfo.parse(self.version)
            v2 = semver.VersionInfo.parse(other_version)
            
            return v1.major == v2.major
        except ValueError:
            # If we can't parse as semver, fallback to exact match
            return self.version == other_version
    
    def is_compatible_with(self, protocol_id: str) -> bool:
        """
        Check if this protocol is compatible with the given protocol ID.
        
        Args:
            protocol_id: Protocol ID to check compatibility with
            
        Returns:
            True if protocols are compatible, False otherwise
        """
        other_base, other_version = self._parse_protocol_id(protocol_id)
        
        # Base protocol must match
        if self.base_name != other_base:
            return False
        
        # Check version compatibility
        return self.is_version_compatible(other_version)
    
    def get_capability_string(self) -> str:
        """
        Get a string representation of all capabilities.
        
        Returns:
            Comma-separated list of capabilities
        """
        return ",".join(sorted(self.capabilities))
    
    def __str__(self) -> str:
        """String representation of the protocol metadata."""
        capabilities = f" (caps: {self.get_capability_string()})" if self.capabilities else ""
        return f"{self.protocol_id}{capabilities}"


class EnhancedMultiselect(Multiselect):
    """
    Enhanced multiselect implementation with advanced protocol negotiation features.
    
    This class extends the standard Multiselect with:
    1. Semantic versioning support
    2. Protocol capabilities
    3. More efficient handshaking
    4. Negotiation for best protocol version
    """
    
    def __init__(
        self, 
        default_handlers: Dict[TProtocol, StreamHandlerFn] = None,
        backward_compatible: bool = True
    ) -> None:
        """
        Initialize the enhanced multiselect handler.
        
        Args:
            default_handlers: Dictionary mapping protocol IDs to handler functions
            backward_compatible: Whether to be compatible with standard multistream select
        """
        super().__init__(default_handlers or {})
        
        # Additional metadata for protocols
        self.protocol_meta: Dict[TProtocol, ProtocolMeta] = {}
        
        # Group protocols by base name for version negotiation
        self.protocols_by_base: Dict[str, Dict[str, TProtocol]] = defaultdict(dict)
        
        # Whether we should be compatible with standard multistream
        self.backward_compatible = backward_compatible
        
        # Initialize protocol metadata for existing handlers
        for protocol, handler in self.handlers.items():
            self._add_protocol_meta(protocol, handler)
    
    def add_handler(self, protocol: TProtocol, handler: StreamHandlerFn) -> None:
        """
        Store the handler with the given protocol and update metadata.
        
        Args:
            protocol: Protocol name
            handler: Handler function
        """
        # Add to standard handlers
        super().add_handler(protocol, handler)
        
        # Add metadata
        self._add_protocol_meta(protocol, handler)
    
    def add_handler_with_capabilities(
        self, 
        protocol: TProtocol, 
        handler: StreamHandlerFn,
        capabilities: List[str]
    ) -> None:
        """
        Add a handler with specific capabilities.
        
        Args:
            protocol: Protocol name
            handler: Handler function
            capabilities: List of capabilities supported by this handler
        """
        self.add_handler(protocol, handler)
        
        # Add capabilities
        for capability in capabilities:
            self.add_protocol_capability(protocol, capability)
    
    def _add_protocol_meta(self, protocol: TProtocol, handler: StreamHandlerFn) -> None:
        """
        Create and store metadata for a protocol.
        
        Args:
            protocol: Protocol name
            handler: Handler function
        """
        # Create metadata
        meta = ProtocolMeta(protocol, handler)
        self.protocol_meta[protocol] = meta
        
        # Add to protocols by base name for version negotiation
        self.protocols_by_base[meta.base_name][meta.version] = protocol
    
    def add_protocol_capability(self, protocol: TProtocol, capability: str) -> None:
        """
        Add a capability to a protocol.
        
        Args:
            protocol: Protocol name
            capability: Capability string
        """
        if protocol in self.protocol_meta:
            self.protocol_meta[protocol].add_capability(capability)
    
    def get_protocol_capabilities(self, protocol: TProtocol) -> Set[str]:
        """
        Get the capabilities of a protocol.
        
        Args:
            protocol: Protocol name
            
        Returns:
            Set of capabilities
        """
        if protocol in self.protocol_meta:
            return self.protocol_meta[protocol].capabilities
        return set()
    
    async def enhanced_handshake(self, communicator: IMultiselectCommunicator) -> bool:
        """
        Perform enhanced handshake that indicates extended capabilities.
        
        Args:
            communicator: Communicator to use
            
        Returns:
            True if enhanced handshake succeeded, False if fell back to standard
            
        Raises:
            MultiselectError: If handshake fails completely
        """
        try:
            # Start with enhanced protocol ID
            await communicator.write(ENHANCED_MULTISELECT_PROTOCOL_ID)
            
            # Read response
            handshake_contents = await communicator.read()
            
            # Check if the other side supports enhanced protocol
            if handshake_contents == ENHANCED_MULTISELECT_PROTOCOL_ID:
                logger.debug("Enhanced multiselect protocol negotiation successful")
                return True
                
            # If backward compatible and the other side sent standard protocol ID
            if (self.backward_compatible and 
                handshake_contents == STANDARD_MULTISELECT_PROTOCOL_ID):
                logger.debug("Falling back to standard multiselect protocol")
                # Acknowledge standard protocol
                await communicator.write(STANDARD_MULTISELECT_PROTOCOL_ID)
                return False
                
            # Unexpected response
            raise MultiselectError(
                f"Enhanced protocol negotiation failed: unexpected response '{handshake_contents}'"
            )
                
        except MultiselectCommunicatorError as error:
            raise MultiselectError("Enhanced handshake failed") from error
    
    async def fallback_handshake(self, communicator: IMultiselectCommunicator) -> None:
        """
        Fallback to standard handshake.
        
        Args:
            communicator: Communicator to use
            
        Raises:
            MultiselectError: If handshake fails
        """
        try:
            # Perform standard handshake
            await communicator.write(STANDARD_MULTISELECT_PROTOCOL_ID)
            
            # Read response
            handshake_contents = await communicator.read()
            
            # Validate handshake
            if not is_valid_handshake(handshake_contents):
                raise MultiselectError(
                    f"Standard protocol ID mismatch: received {handshake_contents}"
                )
                
        except MultiselectCommunicatorError as error:
            raise MultiselectError("Standard handshake failed") from error
    
    async def handle_capability_query(self, protocol: TProtocol, communicator: IMultiselectCommunicator) -> None:
        """
        Handle a capability query for a specific protocol.
        
        Args:
            protocol: Protocol being queried
            communicator: Communicator to use
            
        Raises:
            MultiselectError: If communication fails
        """
        try:
            if protocol in self.protocol_meta:
                # Get capabilities as a string
                caps = self.protocol_meta[protocol].get_capability_string()
                response = f"{CAPABILITY_MARKER}{caps}"
                await communicator.write(response)
            else:
                # Protocol not found
                await communicator.write(PROTOCOL_NOT_FOUND_MSG)
                
        except MultiselectCommunicatorError as error:
            raise MultiselectError("Failed to respond to capability query") from error
    
    async def handle_version_query(self, base_name: str, communicator: IMultiselectCommunicator) -> None:
        """
        Handle a version query for a protocol base name.
        
        Args:
            base_name: Base protocol name
            communicator: Communicator to use
            
        Raises:
            MultiselectError: If communication fails
        """
        try:
            if base_name in self.protocols_by_base:
                # Get all versions for this base name
                versions = list(self.protocols_by_base[base_name].keys())
                response = f"{VERSION_QUERY_CMD}{','.join(versions)}"
                await communicator.write(response)
            else:
                # Protocol not found
                await communicator.write(PROTOCOL_NOT_FOUND_MSG)
                
        except MultiselectCommunicatorError as error:
            raise MultiselectError("Failed to respond to version query") from error
    
    async def handle_list_capabilities(self, communicator: IMultiselectCommunicator) -> None:
        """
        Handle a request to list all protocols with their capabilities.
        
        Args:
            communicator: Communicator to use
            
        Raises:
            MultiselectError: If communication fails
        """
        try:
            # Build the response
            parts = []
            
            for protocol, meta in self.protocol_meta.items():
                capabilities = meta.get_capability_string()
                if capabilities:
                    parts.append(f"{protocol}:{capabilities}")
                else:
                    parts.append(protocol)
            
            # Send the list
            response = ",".join(parts)
            await communicator.write(response)
                
        except MultiselectCommunicatorError as error:
            raise MultiselectError("Failed to respond to capabilities listing") from error
    
    def find_compatible_protocol(self, requested_protocol: TProtocol) -> Optional[Tuple[TProtocol, StreamHandlerFn]]:
        """
        Find a compatible protocol for the requested protocol ID.
        
        This implements version negotiation by finding the highest compatible version.
        
        Args:
            requested_protocol: Protocol ID requested by the client
            
        Returns:
            Tuple of (protocol_id, handler) if a compatible protocol is found, None otherwise
        """
        # If we have exact match, return it immediately
        if requested_protocol in self.handlers:
            return requested_protocol, self.handlers[requested_protocol]
        
        # Parse the requested protocol
        req_meta = ProtocolMeta(requested_protocol, None)
        
        # Check if we have this base protocol
        if req_meta.base_name not in self.protocols_by_base:
            return None
        
        # Try to find the highest compatible version
        versions = list(self.protocols_by_base[req_meta.base_name].keys())
        
        # Sort versions in descending order (highest first)
        try:
            sorted_versions = sorted(
                versions, 
                key=lambda v: semver.VersionInfo.parse(v) if v else semver.VersionInfo.parse("0.0.0"),
                reverse=True
            )
        except ValueError:
            # Fallback to string sorting if semver parsing fails
            sorted_versions = sorted(versions, reverse=True)
        
        # Find the highest compatible version
        for version in sorted_versions:
            # Skip empty versions
            if not version:
                continue
                
            # Check compatibility
            if req_meta.is_version_compatible(version):
                protocol = self.protocols_by_base[req_meta.base_name][version]
                return protocol, self.handlers[protocol]
        
        # No compatible version found
        return None
    
    async def negotiate(self, communicator: IMultiselectCommunicator) -> Tuple[TProtocol, StreamHandlerFn]:
        """
        Negotiate protocol selection with enhanced features.
        
        Args:
            communicator: Communicator to use
            
        Returns:
            Tuple of (selected_protocol, handler)
            
        Raises:
            MultiselectError: If negotiation fails
        """
        # Perform handshake
        try:
            enhanced_mode = await self.enhanced_handshake(communicator)
        except MultiselectError:
            if self.backward_compatible:
                # Fallback to standard handshake
                logger.debug("Enhanced handshake failed, trying standard handshake")
                await self.fallback_handshake(communicator)
                enhanced_mode = False
            else:
                # Re-raise if not backward compatible
                raise
        
        while True:
            try:
                command = await communicator.read()
            except MultiselectCommunicatorError as error:
                raise MultiselectError("Failed to read command") from error
            
            # Handle enhanced mode commands
            if enhanced_mode:
                # List capabilities command
                if command == LIST_CAPABILITIES_CMD:
                    await self.handle_list_capabilities(communicator)
                    continue
                
                # Version query command
                if command.startswith(VERSION_QUERY_CMD):
                    base_name = command[len(VERSION_QUERY_CMD):]
                    await self.handle_version_query(base_name, communicator)
                    continue
                
                # Capability query command
                if command.startswith(CAPABILITY_MARKER):
                    protocol = command[len(CAPABILITY_MARKER):]
                    await self.handle_capability_query(protocol, communicator)
                    continue
            
            # Standard protocol selection
            if command == "ls":
                # TODO: handle ls command
                pass
            else:
                protocol = TProtocol(command)
                
                # Check for direct match
                if protocol in self.handlers:
                    try:
                        await communicator.write(protocol)
                    except MultiselectCommunicatorError as error:
                        raise MultiselectError() from error
                    
                    return protocol, self.handlers[protocol]
                
                # Try to find compatible protocol if in enhanced mode
                if enhanced_mode:
                    compatible = self.find_compatible_protocol(protocol)
                    if compatible:
                        compatible_protocol, handler = compatible
                        try:
                            # Send the actual protocol we're using
                            await communicator.write(compatible_protocol)
                        except MultiselectCommunicatorError as error:
                            raise MultiselectError() from error
                        
                        return compatible_protocol, handler
                
                # Protocol not found
                try:
                    await communicator.write(PROTOCOL_NOT_FOUND_MSG)
                except MultiselectCommunicatorError as error:
                    raise MultiselectError() from error


class EnhancedMultiselectClient(MultiselectClient):
    """
    Enhanced multiselect client implementation with advanced protocol negotiation features.
    
    This class extends the standard MultiselectClient with:
    1. Semantic versioning support
    2. Protocol capabilities discovery
    3. More efficient handshaking
    4. Negotiation for best protocol version
    """
    
    def __init__(self, backward_compatible: bool = True) -> None:
        """
        Initialize the enhanced multiselect client.
        
        Args:
            backward_compatible: Whether to fall back to standard multistream select
        """
        super().__init__()
        self.backward_compatible = backward_compatible
        self.enhanced_mode = False
    
    async def enhanced_handshake(self, communicator: IMultiselectCommunicator) -> bool:
        """
        Perform enhanced handshake that indicates extended capabilities.
        
        Args:
            communicator: Communicator to use
            
        Returns:
            True if enhanced handshake succeeded, False if fell back to standard
            
        Raises:
            MultiselectClientError: If handshake fails completely
        """
        try:
            # Start with enhanced protocol ID
            await communicator.write(ENHANCED_MULTISELECT_PROTOCOL_ID)
            
            # Read response
            handshake_contents = await communicator.read()
            
            # Check if the other side supports enhanced protocol
            if handshake_contents == ENHANCED_MULTISELECT_PROTOCOL_ID:
                logger.debug("Enhanced multiselect protocol negotiation successful")
                return True
                
            # If backward compatible and the other side sent standard protocol ID
            if (self.backward_compatible and 
                handshake_contents == STANDARD_MULTISELECT_PROTOCOL_ID):
                logger.debug("Falling back to standard multiselect protocol")
                return False
                
            # Unexpected response
            raise MultiselectClientError(
                f"Enhanced protocol negotiation failed: unexpected response '{handshake_contents}'"
            )
                
        except MultiselectCommunicatorError as error:
            raise MultiselectClientError("Enhanced handshake failed") from error
    
    async def handshake(self, communicator: IMultiselectCommunicator) -> None:
        """
        Perform handshake to agree on multiselect protocol.
        
        Args:
            communicator: Communicator to use
            
        Raises:
            MultiselectClientError: If handshake fails
        """
        try:
            # Try enhanced handshake first
            self.enhanced_mode = await self.enhanced_handshake(communicator)
        except MultiselectClientError:
            if self.backward_compatible:
                # Fall back to standard handshake
                logger.debug("Enhanced handshake failed, trying standard handshake")
                await self._standard_handshake(communicator)
                self.enhanced_mode = False
            else:
                # Re-raise if not backward compatible
                raise
    
    async def _standard_handshake(self, communicator: IMultiselectCommunicator) -> None:
        """
        Perform standard handshake.
        
        Args:
            communicator: Communicator to use
            
        Raises:
            MultiselectClientError: If handshake fails
        """
        try:
            await communicator.write(STANDARD_MULTISELECT_PROTOCOL_ID)
        except MultiselectCommunicatorError as error:
            raise MultiselectClientError() from error
        
        try:
            handshake_contents = await communicator.read()
        except MultiselectCommunicatorError as error:
            raise MultiselectClientError() from error
        
        if not is_valid_handshake(handshake_contents):
            raise MultiselectClientError("multiselect protocol ID mismatch")
    
    async def query_capabilities(
        self, 
        protocol: TProtocol, 
        communicator: IMultiselectCommunicator
    ) -> Optional[Set[str]]:
        """
        Query capabilities for a specific protocol.
        
        Args:
            protocol: Protocol to query
            communicator: Communicator to use
            
        Returns:
            Set of capabilities if successful, None if not supported
            
        Raises:
            MultiselectClientError: If query fails
        """
        if not self.enhanced_mode:
            # Capabilities are not supported in standard mode
            return None
        
        try:
            # Send capability query
            query = f"{CAPABILITY_MARKER}{protocol}"
            await communicator.write(query)
            
            # Read response
            response = await communicator.read()
            
            # Check if the response is a capability list
            if response.startswith(CAPABILITY_MARKER):
                # Parse capabilities
                caps_str = response[len(CAPABILITY_MARKER):]
                if caps_str:
                    return set(caps_str.split(','))
                return set()
                
            # Not found or error
            return None
                
        except MultiselectCommunicatorError as error:
            raise MultiselectClientError("Failed to query capabilities") from error
    
    async def query_versions(
        self, 
        base_name: str, 
        communicator: IMultiselectCommunicator
    ) -> Optional[List[str]]:
        """
        Query available versions for a protocol base name.
        
        Args:
            base_name: Base protocol name
            communicator: Communicator to use
            
        Returns:
            List of versions if successful, None if not supported
            
        Raises:
            MultiselectClientError: If query fails
        """
        if not self.enhanced_mode:
            # Version query not supported in standard mode
            return None
        
        try:
            # Send version query
            query = f"{VERSION_QUERY_CMD}{base_name}"
            await communicator.write(query)
            
            # Read response
            response = await communicator.read()
            
            # Check if the response is a version list
            if response.startswith(VERSION_QUERY_CMD):
                # Parse versions
                versions_str = response[len(VERSION_QUERY_CMD):]
                if versions_str:
                    return versions_str.split(',')
                return []
                
            # Not found or error
            return None
                
        except MultiselectCommunicatorError as error:
            raise MultiselectClientError("Failed to query versions") from error
    
    async def list_capabilities(
        self, 
        communicator: IMultiselectCommunicator
    ) -> Optional[Dict[str, Set[str]]]:
        """
        List all protocols with their capabilities.
        
        Args:
            communicator: Communicator to use
            
        Returns:
            Dictionary mapping protocol IDs to their capabilities
            
        Raises:
            MultiselectClientError: If listing fails
        """
        if not self.enhanced_mode:
            # Listing capabilities not supported in standard mode
            return None
        
        try:
            # Send list capabilities command
            await communicator.write(LIST_CAPABILITIES_CMD)
            
            # Read response
            response = await communicator.read()
            
            # Parse the response
            result: Dict[str, Set[str]] = {}
            
            if response:
                for part in response.split(','):
                    if ':' in part:
                        protocol, caps_str = part.split(':', 1)
                        result[protocol] = set(caps_str.split(','))
                    else:
                        result[part] = set()
            
            return result
                
        except MultiselectCommunicatorError as error:
            raise MultiselectClientError("Failed to list capabilities") from error
    
    async def select_best_version(
        self, 
        base_protocol: str, 
        min_version: str, 
        communicator: IMultiselectCommunicator
    ) -> Optional[str]:
        """
        Select the best available version of a protocol.
        
        Args:
            base_protocol: Base protocol name
            min_version: Minimum acceptable version
            communicator: Communicator to use
            
        Returns:
            Selected protocol ID or None if no compatible version found
            
        Raises:
            MultiselectClientError: If selection fails
        """
        if not self.enhanced_mode:
            # Version negotiation not supported in standard mode
            # Try the direct protocol request instead
            protocol = f"{base_protocol}/{min_version}"
            try:
                return await self.try_select(communicator, protocol)
            except MultiselectClientError:
                return None
        
        # Query available versions
        versions = await self.query_versions(base_protocol, communicator)
        
        if not versions:
            # No versions available
            return None
        
        # Convert min_version to semver
        try:
            min_semver = semver.VersionInfo.parse(min_version)
        except ValueError:
            # If we can't parse as semver, use string comparison
            # Try to select the exact version
            protocol = f"{base_protocol}/{min_version}"
            try:
                return await self.try_select(communicator, protocol)
            except MultiselectClientError:
                return None
        
        # Filter and sort versions
        compatible_versions = []
        
        for version in versions:
            try:
                v = semver.VersionInfo.parse(version)
                
                # Check compatibility (same major version)
                if v.major == min_semver.major and v >= min_semver:
                    compatible_versions.append((v, version))
            except ValueError:
                # Skip versions we can't parse
                pass
        
        # Sort by version (highest first)
        compatible_versions.sort(reverse=True)
        
        # Try to select the highest compatible version
        for _, version in compatible_versions:
            protocol = f"{base_protocol}/{version}"
            try:
                return await self.try_select(communicator, protocol)
            except MultiselectClientError:
                continue
        
        # No compatible version found
        return None
    
    async def select_with_capabilities(
        self, 
        protocol: TProtocol, 
        required_capabilities: Set[str], 
        communicator: IMultiselectCommunicator
    ) -> Optional[Tuple[TProtocol, Set[str]]]:
        """
        Select a protocol ensuring it has the required capabilities.
        
        Args:
            protocol: Protocol to select
            required_capabilities: Set of required capabilities
            communicator: Communicator to use
            
        Returns:
            Tuple of (selected_protocol, available_capabilities) or None if not supported
            
        Raises:
            MultiselectClientError: If selection fails
        """
        if not self.enhanced_mode:
            # Capabilities are not supported in standard mode
            # Try the direct protocol request instead
            try:
                selected = await self.try_select(communicator, protocol)
                return selected, set()
            except MultiselectClientError:
                return None
        
        # First select the protocol
        try:
            selected_protocol = await self.try_select(communicator, protocol)
        except MultiselectClientError:
            return None
        
        # Query capabilities
        capabilities = await self.query_capabilities(selected_protocol, communicator)
        
        if capabilities is None:
            # Capabilities query failed
            # Protocol is selected but we don't know its capabilities
            return selected_protocol, set()
        
        # Check if all required capabilities are supported
        if required_capabilities and not required_capabilities.issubset(capabilities):
            # Some required capabilities are missing
            missing = required_capabilities - capabilities
            logger.warning(f"Protocol {protocol} is missing required capabilities: {missing}")
            return None
        
        # Return selected protocol and its capabilities
        return selected_protocol, capabilities
    
    async def select_one_of(
        self, 
        protocols: Sequence[TProtocol], 
        communicator: IMultiselectCommunicator
    ) -> TProtocol:
        """
        For each protocol, send message to multiselect selecting protocol and
        fail if multiselect does not return same protocol. Returns first
        protocol that multiselect agrees on (i.e. that multiselect selects)
        
        Args:
            protocols: Protocol choices to select from
            communicator: Communicator to use
            
        Returns:
            Selected protocol
            
        Raises:
            MultiselectClientError: If no protocol is selected
        """
        await self.handshake(communicator)
        
        for protocol in protocols:
            try:
                selected_protocol = await self.try_select(communicator, protocol)
                return selected_protocol
            except MultiselectClientError:
                continue
        
        raise MultiselectClientError("protocols not supported")


# Helper functions for protocol handling

def parse_protocol_id(protocol_id: str) -> Tuple[str, str]:
    """
    Parse a protocol ID into base name and version.
    
    Args:
        protocol_id: The protocol identifier (e.g., "/ipfs/kad/1.0.0")
        
    Returns:
        Tuple of (base_name, version)
    """
    # Default to empty version if we can't parse
    base_name = protocol_id
    version = ""
    
    # Common patterns:
    # 1. /ipfs/kad/1.0.0
    # 2. /libp2p/circuit/relay/0.1.0
    # 3. /meshsub/1.1.0
    
    # Try to find version at the end
    parts = protocol_id.split('/')
    
    # Check if the last part looks like a version (e.g., 1.0.0)
    if parts and re.match(r'^\d+\.\d+\.\d+$', parts[-1]):
        version = parts[-1]
        base_name = '/'.join(parts[:-1])
    
    return base_name, version

def is_version_compatible(version1: str, version2: str) -> bool:
    """
    Check if two versions are compatible (same major version).
    
    Args:
        version1: First version
        version2: Second version
        
    Returns:
        True if versions are compatible, False otherwise
    """
    # Empty version means any version is acceptable
    if not version1 or not version2:
        return True
    
    try:
        # Use semver to check compatibility
        # Only major version changes break compatibility
        v1 = semver.VersionInfo.parse(version1)
        v2 = semver.VersionInfo.parse(version2)
        
        return v1.major == v2.major
    except ValueError:
        # If we can't parse as semver, fallback to exact match
        return version1 == version2

def enhance_protocol_negotiation(protocol_id: str, handler_fn: StreamHandlerFn, capabilities: List[str] = None) -> Tuple[str, StreamHandlerFn, List[str]]:
    """
    Enhance a protocol handler with metadata and capabilities.
    
    This is a helper function to make it easier to define protocols with
    capabilities and proper versioning.
    
    Args:
        protocol_id: Protocol ID
        handler_fn: Handler function
        capabilities: List of capabilities (optional)
        
    Returns:
        Tuple of (protocol_id, enhanced_handler_fn, capabilities)
    """
    base_name, version = parse_protocol_id(protocol_id)
    
    # Use empty list if no capabilities provided
    caps = capabilities or []
    
    # We could wrap the handler to add protocol negotiation info
    # but for now we just return the original handler
    
    return protocol_id, handler_fn, caps