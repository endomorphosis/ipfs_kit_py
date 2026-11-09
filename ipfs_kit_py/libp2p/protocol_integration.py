"""
Protocol integration module for IPFS Kit libp2p.

This module ensures that the IPFSLibp2pPeer class is enhanced with all available
protocol implementations, including:
1. GossipSub protocol for efficient publish/subscribe messaging
2. Enhanced DHT discovery methods for better peer and content discovery
3. Enhanced protocol negotiation with semantic versioning and capabilities
4. Recursive and delegated routing for content discovery
5. Integrated networking with multiple transport support

It provides a simple integration point for applying these protocol extensions,
creating a cohesive libp2p stack that works well with IPFS Kit.

Usage:
    from ipfs_kit_py.libp2p.protocol_integration import apply_protocol_extensions
    
    # Apply to the class
    IPFSLibp2pPeer = apply_protocol_extensions(IPFSLibp2pPeer)
    
    # Or apply at runtime to an instance
    peer = IPFSLibp2pPeer(...)
    apply_protocol_extensions_to_instance(peer)
"""

import logging
import anyio
import inspect
import importlib
from typing import Any, Type, Dict, List, Set, Optional, Callable, Union, Tuple

# Configure logger
logger = logging.getLogger(__name__)

def apply_protocol_extensions(peer_class: Type) -> Type:
    """
    Apply protocol extensions to the IPFSLibp2pPeer class.
    
    This function enhances the IPFSLibp2pPeer class with additional protocol
    functionality, including:
    - GossipSub protocol support for pub/sub messaging
    - Enhanced DHT discovery methods for better peer and content discovery
    - Enhanced protocol negotiation with versioning and capabilities
    - Recursive and delegated routing for content discovery
    - Kademlia DHT integration
    
    Args:
        peer_class: The IPFSLibp2pPeer class to extend
        
    Returns:
        The enhanced peer class
    """
    try:
        # Apply GossipSub extensions first
        from ipfs_kit_py.libp2p.gossipsub_protocol import enhance_libp2p_peer
        enhanced_class = enhance_libp2p_peer(peer_class)
        logger.info("Successfully applied GossipSub protocol extensions to IPFSLibp2pPeer class")
        
        # Apply enhanced protocol negotiation
        enhanced_class = apply_enhanced_negotiation(enhanced_class)
        logger.info("Successfully applied enhanced protocol negotiation to IPFSLibp2pPeer class")
        
        # Apply recursive routing extensions
        try:
            from ipfs_kit_py.libp2p.recursive_routing import enhance_with_recursive_routing
            enhanced_class = enhance_with_recursive_routing(enhanced_class)
            logger.info("Successfully applied recursive routing extensions to IPFSLibp2pPeer class")
        except (ImportError, Exception) as e:
            logger.warning(f"Could not apply recursive routing extensions: {e}")
        
        # Apply Kademlia DHT extensions
        try:
            enhanced_class = apply_kademlia_extensions(enhanced_class)
            logger.info("Successfully applied Kademlia DHT extensions to IPFSLibp2pPeer class")
        except Exception as e:
            logger.warning(f"Could not apply Kademlia DHT extensions: {e}")
        
        return enhanced_class
    except ImportError as e:
        logger.warning(f"Could not import protocol extensions: {e}")
        return peer_class
    except Exception as e:
        logger.error(f"Error applying protocol extensions: {e}")
        return peer_class

def apply_protocol_extensions_to_instance(peer_instance: Any) -> Any:
    """
    Apply protocol extensions to an existing IPFSLibp2pPeer instance.
    
    This function enhances an existing IPFSLibp2pPeer instance with additional
    protocol functionality by monkey-patching the instance directly.
    
    Args:
        peer_instance: The IPFSLibp2pPeer instance to extend
        
    Returns:
        The enhanced peer instance
    """
    try:
        # Apply GossipSub methods
        from ipfs_kit_py.libp2p.gossipsub_protocol import add_gossipsub_methods, add_enhanced_dht_discovery_methods
        
        # Apply the GossipSub methods
        add_gossipsub_methods(peer_instance.__class__)
        
        # Apply the enhanced DHT discovery methods
        add_enhanced_dht_discovery_methods(peer_instance.__class__)
        
        # Apply enhanced protocol negotiation methods
        add_enhanced_negotiation_methods(peer_instance.__class__)
        
        # Apply recursive routing methods
        try:
            from ipfs_kit_py.libp2p.recursive_routing import add_recursive_routing_methods
            add_recursive_routing_methods(peer_instance.__class__)
            logger.info("Successfully applied recursive routing methods to IPFSLibp2pPeer instance")
        except (ImportError, Exception) as e:
            logger.warning(f"Could not apply recursive routing methods: {e}")
        
        # Apply Kademlia DHT methods
        try:
            add_kademlia_methods(peer_instance.__class__)
            logger.info("Successfully applied Kademlia DHT methods to IPFSLibp2pPeer instance")
        except Exception as e:
            logger.warning(f"Could not apply Kademlia DHT methods: {e}")
        
        # Initialize components if instance is already started
        if hasattr(peer_instance, '_is_started') and peer_instance._is_started:
            # Initialize enhanced components
            if hasattr(peer_instance, 'initialize_gossipsub'):
                anyio.run(peer_instance.initialize_gossipsub())
                
            if hasattr(peer_instance, 'initialize_recursive_routing'):
                anyio.run(peer_instance.initialize_recursive_routing())
        
        logger.info("Successfully applied all protocol extensions to IPFSLibp2pPeer instance")
        return peer_instance
    except ImportError as e:
        logger.warning(f"Could not import protocol extensions: {e}")
        return peer_instance
    except Exception as e:
        logger.error(f"Error applying protocol extensions: {e}")
        return peer_instance

def apply_enhanced_negotiation(peer_class: Type) -> Type:
    """
    Apply enhanced protocol negotiation to the IPFSLibp2pPeer class.
    
    This function enhances the peer class with semantic versioning support,
    protocol capabilities, and improved negotiation for protocol selection.
    
    Args:
        peer_class: The IPFSLibp2pPeer class to extend
        
    Returns:
        The enhanced peer class
    """
    try:
        # Import enhanced protocol negotiation
        from ipfs_kit_py.libp2p.enhanced_protocol_negotiation import (
            EnhancedMultiselect,
            EnhancedMultiselectClient,
            enhance_protocol_negotiation
        )
        
        # Skip attempting to modify magic methods for MagicMock objects
        import unittest.mock
        if isinstance(peer_class, unittest.mock.MagicMock) or peer_class.__name__ == "MagicMock":
            logger.info("Skipping __init__ modification for MagicMock object")
        else:
            # Store original initialization method
            original_init = peer_class.__init__
            
            # Define new initialization that sets up enhanced protocol negotiation
            def enhanced_init(self, *args, **kwargs):
                # Call original init first
                original_init(self, *args, **kwargs)
                
                # Set up protocol negotiation attributes if they don't exist
                if not hasattr(self, 'protocol_capabilities'):
                    self.protocol_capabilities = {}
                
                # Override multiselect with enhanced version if not already set
                if not hasattr(self, '_using_enhanced_multiselect'):
                    self._using_enhanced_multiselect = True
                    
                    # Replace multiselect implementations if possible
                    try:
                        # For server-side negotiation
                        if hasattr(self, 'multiselect') and self.multiselect is not None:
                            handlers = getattr(self.multiselect, 'handlers', {})
                            self.multiselect = EnhancedMultiselect(default_handlers=handlers)
                        
                        # For client-side negotiation
                        if hasattr(self, 'multiselect_client') and self.multiselect_client is not None:
                            self.multiselect_client = EnhancedMultiselectClient()
                            
                        logger.info("Enhanced protocol negotiation initialized")
                    except Exception as e:
                        logger.warning(f"Could not replace multiselect components: {e}")
            
            # Replace the initialization method
            peer_class.__init__ = enhanced_init
        
        # Add methods for protocol capabilities
        add_enhanced_negotiation_methods(peer_class)
        
        return peer_class
        
    except ImportError as e:
        logger.warning(f"Could not import enhanced protocol negotiation: {e}")
        return peer_class
    except Exception as e:
        logger.error(f"Error applying enhanced protocol negotiation: {e}")
        return peer_class

def add_enhanced_negotiation_methods(peer_class: Type) -> None:
    """
    Add enhanced protocol negotiation methods to the peer class.
    
    Args:
        peer_class: The peer class to enhance
    """
    try:
        # Import required components
        from ipfs_kit_py.libp2p.enhanced_protocol_negotiation import (
            enhance_protocol_negotiation,
            parse_protocol_id
        )
        
        # Method to register a protocol with capabilities
        def register_protocol_with_capabilities(
            self, 
            protocol_id: str, 
            handler_fn: Any, 
            capabilities: List[str] = None
        ) -> None:
            """
            Register a protocol with specific capabilities.
            
            This allows the peer to advertise and negotiate protocols based on
            their capabilities, enabling more flexible protocol selection.
            
            Args:
                protocol_id: Protocol identifier (e.g., "/ipfs/kad/1.0.0")
                handler_fn: Handler function for this protocol
                capabilities: List of capability strings that this protocol supports
            """
            # Store capabilities for this protocol
            if not hasattr(self, 'protocol_capabilities'):
                self.protocol_capabilities = {}
                
            # Default to empty list if no capabilities provided
            caps = capabilities or []
            self.protocol_capabilities[protocol_id] = set(caps)
            
            # Check if we have the enhanced multiselect
            if hasattr(self, 'multiselect') and hasattr(self.multiselect, 'add_handler_with_capabilities'):
                # Register with enhanced capabilities
                self.multiselect.add_handler_with_capabilities(protocol_id, handler_fn, caps)
            else:
                # Fall back to regular registration
                if hasattr(self, 'multiselect') and hasattr(self.multiselect, 'add_handler'):
                    self.multiselect.add_handler(protocol_id, handler_fn)
        
        # Method to query protocol capabilities
        async def get_protocol_capabilities(self, peer_id: str, protocol_id: str) -> Optional[Set[str]]:
            """
            Query a peer for the capabilities of a specific protocol.
            
            Args:
                peer_id: ID of the peer to query
                protocol_id: Protocol to check capabilities for
                
            Returns:
                Set of capability strings or None if not supported/available
            """
            try:
                # First establish a connection to the peer if needed
                if not self.is_peer_connected(peer_id):
                    if not await self.connect_peer(peer_id):
                        logger.warning(f"Failed to connect to peer {peer_id}")
                        return None
                
                # Create a stream for the protocol
                stream = await self.new_stream(peer_id, protocol_id)
                
                # Use enhanced client to query capabilities if available
                if (hasattr(self, 'multiselect_client') and 
                    hasattr(self.multiselect_client, 'query_capabilities')):
                    
                    # Create communicator for the stream
                    communicator = self._create_communicator(stream)
                    
                    # Query capabilities
                    return await self.multiselect_client.query_capabilities(
                        protocol_id, communicator
                    )
                
                # Close the stream if we didn't use it
                await stream.close()
                return None
                
            except Exception as e:
                logger.warning(f"Error querying protocol capabilities: {e}")
                return None
        
        # Method to select best protocol version
        async def select_best_protocol_version(
            self, 
            peer_id: str, 
            base_protocol: str, 
            min_version: str
        ) -> Optional[str]:
            """
            Select the best available version of a protocol from a peer.
            
            Args:
                peer_id: ID of the peer to negotiate with
                base_protocol: Base protocol name (e.g., "/ipfs/kad")
                min_version: Minimum acceptable version (e.g., "1.0.0")
                
            Returns:
                Selected protocol ID or None if no compatible version found
            """
            try:
                # First establish a connection to the peer if needed
                if not self.is_peer_connected(peer_id):
                    if not await self.connect_peer(peer_id):
                        logger.warning(f"Failed to connect to peer {peer_id}")
                        return None
                
                # Create a stream for negotiation
                # Use the base protocol with min version for initial stream
                protocol = f"{base_protocol}/{min_version}"
                stream = await self.new_stream(peer_id, protocol)
                
                # Use enhanced client to select best version if available
                if (hasattr(self, 'multiselect_client') and 
                    hasattr(self.multiselect_client, 'select_best_version')):
                    
                    # Create communicator for the stream
                    communicator = self._create_communicator(stream)
                    
                    # Select the best version
                    return await self.multiselect_client.select_best_version(
                        base_protocol, min_version, communicator
                    )
                
                # Close the stream if we didn't use it
                await stream.close()
                return None
                
            except Exception as e:
                logger.warning(f"Error selecting best protocol version: {e}")
                return None
        
        # Method to negotiate with multiple peers for optimal protocol/version
        async def negotiate_optimal_protocol(
            self,
            peer_ids: List[str],
            base_protocol: str,
            min_version: str,
            required_capabilities: Optional[Set[str]] = None
        ) -> Optional[Tuple[str, str, Set[str]]]:
            """
            Negotiate with multiple peers to find the optimal protocol implementation.
            
            This function contacts multiple peers and finds the best available
            protocol version with the required capabilities.
            
            Args:
                peer_ids: List of peer IDs to negotiate with
                base_protocol: Base protocol name
                min_version: Minimum acceptable version
                required_capabilities: Set of required capabilities (optional)
                
            Returns:
                Tuple of (peer_id, protocol_id, capabilities) or None if not found
            """
            results = []
            
            for peer_id in peer_ids:
                try:
                    # Select best protocol version
                    protocol_id = await self.select_best_protocol_version(
                        peer_id, base_protocol, min_version
                    )
                    
                    if not protocol_id:
                        continue
                        
                    # Check capabilities if required
                    if required_capabilities:
                        capabilities = await self.get_protocol_capabilities(
                            peer_id, protocol_id
                        )
                        
                        if not capabilities or not required_capabilities.issubset(capabilities):
                            continue
                            
                        results.append((peer_id, protocol_id, capabilities))
                    else:
                        # No capabilities required
                        results.append((peer_id, protocol_id, set()))
                        
                except Exception as e:
                    logger.debug(f"Error negotiating with peer {peer_id}: {e}")
                    continue
            
            # No results
            if not results:
                return None
                
            # Sort by protocol version and capabilities count (higher is better)
            results.sort(
                key=lambda x: (
                    x[1].split("/")[-1],  # Version string
                    len(x[2])  # Number of capabilities
                ),
                reverse=True
            )
            
            # Return the best match
            return results[0]
        
        # Helper method to create a communicator for a stream
        def _create_communicator(self, stream):
            """Create a communicator for a stream."""
            try:
                # Import necessary components
                from libp2p.protocol_muxer.multiselect_communicator import MultiselectCommunicator
                return MultiselectCommunicator(stream)
            except ImportError:
                logger.warning("Could not import MultiselectCommunicator")
                return None
        
        # Add methods for handling protocol sets
        def add_protocol_set(self, protocol_set_name: str, protocols: Dict[str, Dict[str, Any]]) -> None:
            """
            Register a set of related protocols with their handlers and capabilities.
            
            This is useful for registering a complete protocol stack at once.
            
            Args:
                protocol_set_name: Name of the protocol set (for reference)
                protocols: Dictionary mapping protocol IDs to their configuration
                    {
                        "/protocol/1.0.0": {
                            "handler": handler_function, 
                            "capabilities": ["cap1", "cap2"],
                            "fallback": "/protocol/0.9.0"
                        }
                    }
            """
            if not hasattr(self, 'protocol_sets'):
                self.protocol_sets = {}
                
            self.protocol_sets[protocol_set_name] = protocols
            
            # Register each protocol
            for protocol_id, config in protocols.items():
                handler = config.get("handler")
                capabilities = config.get("capabilities", [])
                
                if handler:
                    self.register_protocol_with_capabilities(
                        protocol_id, handler, capabilities
                    )
        
        # Add all methods to the class
        peer_class.register_protocol_with_capabilities = register_protocol_with_capabilities
        peer_class.get_protocol_capabilities = get_protocol_capabilities
        peer_class.select_best_protocol_version = select_best_protocol_version
        peer_class.negotiate_optimal_protocol = negotiate_optimal_protocol
        peer_class._create_communicator = _create_communicator
        peer_class.add_protocol_set = add_protocol_set
        
    except ImportError as e:
        logger.warning(f"Could not import components for enhanced negotiation methods: {e}")
    except Exception as e:
        logger.error(f"Error adding enhanced negotiation methods: {e}")

def apply_kademlia_extensions(peer_class: Type) -> Type:
    """
    Apply Kademlia DHT extensions to the IPFSLibp2pPeer class.
    
    Args:
        peer_class: The IPFSLibp2pPeer class to extend
        
    Returns:
        The enhanced peer class
    """
    try:
        # Instead of replacing __init__, we'll create a new class that inherits from the original
        class EnhancedKademliaPeer(peer_class):
            def __init__(self, *args, **kwargs):
                # Call the parent class's __init__
                super().__init__(*args, **kwargs)
                
                # Extract DHT configuration
                dht_config = kwargs.get('dht_config', {})
                
                # Set up Kademlia attributes
                self.kademlia_initialized = False
                self.kad_routing_table = None
                self.kad_datastore = None
                
                # Store DHT configuration
                self.dht_config = dht_config
                
            async def start(self):
                # Call the parent class's start method
                if hasattr(super(), 'start'):
                    result = super().start()
                    if inspect.isawaitable(result):
                        await result
                
                # Initialize Kademlia if needed
                if hasattr(self, 'initialize_kademlia') and not self.kademlia_initialized:
                    await self.initialize_kademlia()
                
                return None
        
        # Copy the original class's attributes and methods to avoid losing anything
        for attr_name in dir(peer_class):
            # Skip special methods and attributes
            if attr_name.startswith('__') and attr_name != '__init__':
                continue
                
            # Get the attribute from the original class
            attr = getattr(peer_class, attr_name)
            
            # Skip if the attribute is already in the new class
            if hasattr(EnhancedKademliaPeer, attr_name):
                continue
                
            # Copy the attribute to the new class
            setattr(EnhancedKademliaPeer, attr_name, attr)
        
        # Add Kademlia methods to the new class
        add_kademlia_methods(EnhancedKademliaPeer)
        
        # Return the enhanced class
        return EnhancedKademliaPeer
        
    except Exception as e:
        logger.error(f"Error applying Kademlia extensions: {e}")
        return peer_class

def add_kademlia_methods(peer_class: Type) -> None:
    """
    Add Kademlia DHT methods to the peer class.
    
    Args:
        peer_class: The peer class to enhance
    """
    try:
        # Method to initialize Kademlia
        async def initialize_kademlia(self):
            """
            Initialize the Kademlia DHT components.
            
            This sets up the routing table, datastore, and protocol handlers for
            Kademlia DHT operations.
            """
            if self.kademlia_initialized:
                return
                
            try:
                # Import Kademlia components
                try:
                    from ipfs_kit_py.libp2p.kademlia import KademliaRoutingTable, DHTDatastore, KademliaNode
                    has_local_kademlia = True
                except ImportError:
                    has_local_kademlia = False
                    
                    # Try importing from libp2p if available
                    try:
                        from libp2p.routing.kademlia.routing_table import RoutingTable as KademliaRoutingTable
                        from libp2p.routing.kademlia.datastore import DataStore as DHTDatastore
                        has_libp2p_kademlia = True
                    except ImportError:
                        has_libp2p_kademlia = False
                
                # Create routing table and datastore if possible
                if has_local_kademlia or has_libp2p_kademlia:
                    # Initialize routing table with our peer ID
                    peer_id = self.get_peer_id()
                    self.kad_routing_table = KademliaRoutingTable(peer_id)
                    
                    # Initialize datastore based on configuration
                    # If persistent storage is requested, use PersistentDHTDatastore
                    use_persistent_datastore = False
                    datastore_config = {}
                    
                    # Check DHT configuration for persistent storage settings
                    if hasattr(self, 'dht_config'):
                        use_persistent_datastore = self.dht_config.get('persistent_storage', False)
                        datastore_config = self.dht_config.get('datastore_config', {})
                    
                    if use_persistent_datastore:
                        try:
                            # Import the persistent datastore
                            from ipfs_kit_py.libp2p.datastore import PersistentDHTDatastore
                            
                            # Create persistent datastore with configuration
                            self.kad_datastore = PersistentDHTDatastore(
                                path=datastore_config.get('path'),
                                max_items=datastore_config.get('max_items', 1000),
                                max_age=datastore_config.get('max_age', 86400),
                                sync_interval=datastore_config.get('sync_interval', 300),
                                flush_threshold=datastore_config.get('flush_threshold', 50)
                            )
                            
                            logger.info("Using persistent DHT datastore for Kademlia")
                        except ImportError as e:
                            logger.warning(f"Could not import PersistentDHTDatastore, falling back to in-memory: {e}")
                            self.kad_datastore = DHTDatastore()
                        except Exception as e:
                            logger.warning(f"Error initializing persistent datastore, falling back to in-memory: {e}")
                            self.kad_datastore = DHTDatastore()
                    else:
                        # Use in-memory datastore
                        self.kad_datastore = DHTDatastore()
                        logger.info("Using in-memory DHT datastore for Kademlia")
                    
                    # Create a KademliaNode if needed
                    if hasattr(self, 'kademlia_node') and self.kademlia_node is None and has_local_kademlia:
                        try:
                            # Create KademliaNode with the configured datastore
                            self.kademlia_node = KademliaNode(
                                peer_id=peer_id,
                                bucket_size=datastore_config.get('bucket_size', BUCKET_SIZE),
                                alpha=datastore_config.get('alpha', ALPHA_VALUE),
                                datastore=self.kad_datastore  # Use our configured datastore
                            )
                            logger.info("Created KademliaNode with configured datastore")
                        except Exception as e:
                            logger.error(f"Error creating KademliaNode: {e}")
                    
                    # Register Kademlia protocols with capabilities
                    self.register_protocol_with_capabilities(
                        "/ipfs/kad/1.0.0",
                        self._handle_kademlia_request,
                        ["basic-dht", "provider-records"]
                    )
                    
                    # Also register newer version if available
                    self.register_protocol_with_capabilities(
                        "/ipfs/kad/2.0.0",
                        self._handle_kademlia_request,
                        ["basic-dht", "provider-records", "value-store", "peer-routing"]
                    )
                    
                    self.kademlia_initialized = True
                    logger.info("Kademlia DHT initialized")
                else:
                    logger.warning("Could not initialize Kademlia DHT: required components not available")
                    
            except Exception as e:
                logger.error(f"Error initializing Kademlia: {e}")
        
        # Method to handle Kademlia protocol requests
        async def _handle_kademlia_request(self, stream):
            """
            Handle incoming Kademlia protocol requests.
            
            Args:
                stream: The network stream for communication
            """
            try:
                # Read the request message
                data = await stream.read(4096)
                if not data:
                    await stream.close()
                    return
                
                # Parse the request
                try:
                    import json
                    request = json.loads(data.decode('utf-8'))
                except Exception:
                    # Invalid request format
                    await stream.close()
                    return
                
                # Process the request based on type
                request_type = request.get('type')
                if not request_type:
                    await stream.close()
                    return
                
                response = {'id': request.get('id')}
                
                if request_type == 'FIND_NODE':
                    # Find closest peers to target
                    target = request.get('target')
                    if target and self.kad_routing_table:
                        closest = self.kad_routing_table.get_closest_peers(target)
                        response['peers'] = closest
                    else:
                        response['peers'] = []
                
                elif request_type == 'FIND_VALUE':
                    # Find value or closest peers
                    key = request.get('key')
                    if key and self.kad_datastore:
                        value = self.kad_datastore.get(key)
                        if value:
                            response['value'] = value
                        else:
                            closest = self.kad_routing_table.get_closest_peers(key)
                            response['peers'] = closest
                    else:
                        response['peers'] = []
                
                elif request_type == 'STORE':
                    # Store key-value pair
                    key = request.get('key')
                    value = request.get('value')
                    if key and value and self.kad_datastore:
                        self.kad_datastore.put(key, value)
                        response['success'] = True
                    else:
                        response['success'] = False
                
                elif request_type == 'ADD_PROVIDER':
                    # Add provider for content
                    cid = request.get('cid')
                    provider = request.get('provider')
                    if cid and provider and self.kad_datastore:
                        self.kad_datastore.add_provider(cid, provider)
                        response['success'] = True
                    else:
                        response['success'] = False
                
                elif request_type == 'GET_PROVIDERS':
                    # Get providers for content
                    cid = request.get('cid')
                    if cid and self.kad_datastore:
                        providers = self.kad_datastore.get_providers(cid)
                        response['providers'] = providers
                    else:
                        response['providers'] = []
                
                # Send the response
                await stream.write(json.dumps(response).encode('utf-8'))
                
            except Exception as e:
                logger.error(f"Error handling Kademlia request: {e}")
            finally:
                await stream.close()
        
        # Method to find closest peers to a key
        async def find_closest_peers(self, key: str, count: int = 20) -> List[str]:
            """
            Find the closest peers to a given key.
            
            Args:
                key: The key to find peers for
                count: Maximum number of peers to return
                
            Returns:
                List of peer IDs closest to the key
            """
            if not self.kademlia_initialized:
                await self.initialize_kademlia()
                
            # Local lookup first
            if self.kad_routing_table:
                closest = self.kad_routing_table.get_closest_peers(key, count)
                if closest:
                    return closest
            
            # If we don't have enough peers locally, do an iterative lookup
            return await self.iterative_find_node(key, count)
                
        # Method to perform iterative find node
        async def iterative_find_node(self, key: str, count: int = 20) -> List[str]:
            """
            Perform an iterative find node operation to locate peers.
            
            Args:
                key: The key to find peers for
                count: Maximum number of peers to return
                
            Returns:
                List of peer IDs closest to the key
            """
            # Get initial peers from our routing table
            if not self.kad_routing_table:
                return []
                
            closest = set(self.kad_routing_table.get_closest_peers(key, count))
            already_queried = set()
            
            # Iteratively query peers
            for _ in range(3):  # Max 3 iterations
                if not closest - already_queried:
                    break
                    
                # Select unqueried peers
                to_query = list(closest - already_queried)
                
                # Query each peer
                for peer_id in to_query:
                    already_queried.add(peer_id)
                    
                    try:
                        # Connect to peer if needed
                        if not self.is_peer_connected(peer_id):
                            if not await self.connect_peer(peer_id):
                                continue
                        
                        # Create a stream for the Kademlia protocol
                        stream = await self.new_stream(peer_id, "/ipfs/kad/1.0.0")
                        
                        # Send find node request
                        import json
                        request = {
                            'type': 'FIND_NODE',
                            'id': self.get_peer_id(),
                            'target': key
                        }
                        await stream.write(json.dumps(request).encode('utf-8'))
                        
                        # Read response
                        data = await stream.read(4096)
                        await stream.close()
                        
                        if data:
                            response = json.loads(data.decode('utf-8'))
                            peers = response.get('peers', [])
                            
                            # Add new peers to closest set
                            closest.update(peers)
                            
                    except Exception as e:
                        logger.debug(f"Error querying peer {peer_id}: {e}")
            
            # Return the closest peers
            return list(closest)[:count]
            
        # Method to store a key-value pair in the DHT
        async def dht_put(self, key: str, value: Any) -> bool:
            """
            Store a key-value pair in the DHT.
            
            Args:
                key: The key to store under
                value: The value to store (will be JSON serialized)
                
            Returns:
                True if successful, False otherwise
            """
            if not self.kademlia_initialized:
                await self.initialize_kademlia()
                
            # Store locally first
            if self.kad_datastore:
                import json
                serialized = json.dumps(value)
                self.kad_datastore.put(key, serialized)
                
            # Find peers to store on
            closest_peers = await self.find_closest_peers(key)
            if not closest_peers:
                return False
                
            # Store on each peer
            success_count = 0
            for peer_id in closest_peers:
                try:
                    # Connect to peer if needed
                    if not self.is_peer_connected(peer_id):
                        if not await self.connect_peer(peer_id):
                            continue
                    
                    # Create a stream for the Kademlia protocol
                    stream = await self.new_stream(peer_id, "/ipfs/kad/1.0.0")
                    
                    # Send store request
                    import json
                    request = {
                        'type': 'STORE',
                        'id': self.get_peer_id(),
                        'key': key,
                        'value': json.dumps(value)
                    }
                    await stream.write(json.dumps(request).encode('utf-8'))
                    
                    # Read response
                    data = await stream.read(4096)
                    await stream.close()
                    
                    if data:
                        response = json.loads(data.decode('utf-8'))
                        if response.get('success'):
                            success_count += 1
                        
                except Exception as e:
                    logger.debug(f"Error storing on peer {peer_id}: {e}")
            
            return success_count > 0
            
        # Method to retrieve a value from the DHT
        async def dht_get(self, key: str) -> Optional[Any]:
            """
            Retrieve a value from the DHT.
            
            Args:
                key: The key to retrieve
                
            Returns:
                The value if found, None otherwise
            """
            if not self.kademlia_initialized:
                await self.initialize_kademlia()
                
            # Check local datastore first
            if self.kad_datastore:
                value = self.kad_datastore.get(key)
                if value:
                    import json
                    return json.loads(value)
            
            # Find peers to query
            closest_peers = await self.find_closest_peers(key)
            if not closest_peers:
                return None
                
            # Query each peer
            for peer_id in closest_peers:
                try:
                    # Connect to peer if needed
                    if not self.is_peer_connected(peer_id):
                        if not await self.connect_peer(peer_id):
                            continue
                    
                    # Create a stream for the Kademlia protocol
                    stream = await self.new_stream(peer_id, "/ipfs/kad/1.0.0")
                    
                    # Send find value request
                    import json
                    request = {
                        'type': 'FIND_VALUE',
                        'id': self.get_peer_id(),
                        'key': key
                    }
                    await stream.write(json.dumps(request).encode('utf-8'))
                    
                    # Read response
                    data = await stream.read(4096)
                    await stream.close()
                    
                    if data:
                        response = json.loads(data.decode('utf-8'))
                        value = response.get('value')
                        if value:
                            return json.loads(value)
                        
                except Exception as e:
                    logger.debug(f"Error querying peer {peer_id}: {e}")
            
            return None
            
        # Method to announce providing a piece of content
        async def provide(self, cid: str) -> bool:
            """
            Announce that this peer can provide a piece of content.
            
            Args:
                cid: The content identifier
                
            Returns:
                True if successful, False otherwise
            """
            if not self.kademlia_initialized:
                await self.initialize_kademlia()
                
            # Add to local datastore first
            if self.kad_datastore:
                self.kad_datastore.add_provider(cid, self.get_peer_id())
                
            # Find peers to announce to
            closest_peers = await self.find_closest_peers(cid)
            if not closest_peers:
                return False
                
            # Announce to each peer
            success_count = 0
            for peer_id in closest_peers:
                try:
                    # Connect to peer if needed
                    if not self.is_peer_connected(peer_id):
                        if not await self.connect_peer(peer_id):
                            continue
                    
                    # Create a stream for the Kademlia protocol
                    stream = await self.new_stream(peer_id, "/ipfs/kad/1.0.0")
                    
                    # Send add provider request
                    import json
                    request = {
                        'type': 'ADD_PROVIDER',
                        'id': self.get_peer_id(),
                        'cid': cid,
                        'provider': self.get_peer_id()
                    }
                    await stream.write(json.dumps(request).encode('utf-8'))
                    
                    # Read response
                    data = await stream.read(4096)
                    await stream.close()
                    
                    if data:
                        response = json.loads(data.decode('utf-8'))
                        if response.get('success'):
                            success_count += 1
                        
                except Exception as e:
                    logger.debug(f"Error announcing to peer {peer_id}: {e}")
            
            return success_count > 0
            
        # Method to find providers for a piece of content
        async def find_providers(self, cid: str, count: int = 20) -> List[str]:
            """
            Find peers that can provide a piece of content.
            
            Args:
                cid: The content identifier
                count: Maximum number of providers to return
                
            Returns:
                List of peer IDs that can provide the content
            """
            if not self.kademlia_initialized:
                await self.initialize_kademlia()
                
            # Check local datastore first
            providers = set()
            if self.kad_datastore:
                local_providers = self.kad_datastore.get_providers(cid)
                providers.update(local_providers)
                
            # If we have enough providers, return them
            if len(providers) >= count:
                return list(providers)[:count]
                
            # Find peers to query
            closest_peers = await self.find_closest_peers(cid)
            if not closest_peers:
                return list(providers)
                
            # Query each peer
            for peer_id in closest_peers:
                if len(providers) >= count:
                    break
                    
                try:
                    # Connect to peer if needed
                    if not self.is_peer_connected(peer_id):
                        if not await self.connect_peer(peer_id):
                            continue
                    
                    # Create a stream for the Kademlia protocol
                    stream = await self.new_stream(peer_id, "/ipfs/kad/1.0.0")
                    
                    # Send get providers request
                    import json
                    request = {
                        'type': 'GET_PROVIDERS',
                        'id': self.get_peer_id(),
                        'cid': cid
                    }
                    await stream.write(json.dumps(request).encode('utf-8'))
                    
                    # Read response
                    data = await stream.read(4096)
                    await stream.close()
                    
                    if data:
                        response = json.loads(data.decode('utf-8'))
                        peer_providers = response.get('providers', [])
                        providers.update(peer_providers)
                        
                except Exception as e:
                    logger.debug(f"Error querying peer {peer_id}: {e}")
            
            return list(providers)[:count]
        
        # Add all methods to the class
        peer_class.initialize_kademlia = initialize_kademlia
        peer_class._handle_kademlia_request = _handle_kademlia_request
        peer_class.find_closest_peers = find_closest_peers
        peer_class.iterative_find_node = iterative_find_node
        peer_class.dht_put = dht_put
        peer_class.dht_get = dht_get
        peer_class.provide = provide
        peer_class.find_providers = find_providers
        
    except Exception as e:
        logger.error(f"Error adding Kademlia methods: {e}")

# Function to detect if a component is available
def is_component_available(component_name: str) -> bool:
    """
    Check if a specific component is available.
    
    Args:
        component_name: Name of the component to check
        
    Returns:
        True if the component is available, False otherwise
    """
    try:
        module_path = f"ipfs_kit_py.libp2p.{component_name}"
        importlib.import_module(module_path)
        return True
    except ImportError:
        return False
    
# Utility function to get available protocol extensions
def get_available_extensions() -> Dict[str, bool]:
    """
    Get a dictionary of available protocol extensions.
    
    Returns:
        Dictionary mapping extension names to availability boolean
    """
    return {
        "gossipsub": is_component_available("gossipsub_protocol"),
        "enhanced_negotiation": is_component_available("enhanced_protocol_negotiation"),
        "recursive_routing": is_component_available("recursive_routing"),
        "kademlia": is_component_available("kademlia")
    }
