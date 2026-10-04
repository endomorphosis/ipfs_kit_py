"""LibP2P Controller Module

This module provides the LibP2P controller functionality for the MCP server.
"""

import logging
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)


class LibP2PController:
    """Controller for LibP2P operations."""
    
    def __init__(self, libp2p_model):
        """Initialize with a LibP2P model."""
        self.libp2p_model = libp2p_model
        self.logger = logging.getLogger(__name__)
    
    def start_node(self, request) -> Dict[str, Any]:
        """Start the LibP2P node."""
        self.logger.info("Starting LibP2P node")
        try:
            success = self.libp2p_model.start()
            if success:
                info = self.libp2p_model.get_info()
                return {
                    "success": True,
                    "message": "LibP2P node started successfully",
                    "peer_id": info["peer_id"],
                    "multiaddrs": info["multiaddrs"]
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to start LibP2P node"
                }
        except Exception as e:
            self.logger.error(f"Error starting LibP2P node: {str(e)}")
            return {
                "success": False,
                "message": f"Error starting LibP2P node: {str(e)}"
            }
    
    def stop_node(self, request) -> Dict[str, Any]:
        """Stop the LibP2P node."""
        self.logger.info("Stopping LibP2P node")
        try:
            success = self.libp2p_model.stop()
            return {
                "success": success,
                "message": "LibP2P node stopped successfully" if success else "Failed to stop LibP2P node"
            }
        except Exception as e:
            self.logger.error(f"Error stopping LibP2P node: {str(e)}")
            return {
                "success": False,
                "message": f"Error stopping LibP2P node: {str(e)}"
            }
    
    def connect_peer(self, request) -> Dict[str, Any]:
        """Connect to a peer."""
        peer_addr = request.peer_addr
        self.logger.info(f"Connecting to peer: {peer_addr}")
        try:
            success = self.libp2p_model.connect(peer_addr)
            return {
                "success": success,
                "message": f"Connected to peer: {peer_addr}" if success else f"Failed to connect to peer: {peer_addr}"
            }
        except Exception as e:
            self.logger.error(f"Error connecting to peer: {str(e)}")
            return {
                "success": False,
                "message": f"Error connecting to peer: {str(e)}"
            }
    
    def disconnect_peer(self, request) -> Dict[str, Any]:
        """Disconnect from a peer."""
        peer_id = request.peer_id
        self.logger.info(f"Disconnecting from peer: {peer_id}")
        try:
            success = self.libp2p_model.disconnect(peer_id)
            return {
                "success": success,
                "message": f"Disconnected from peer: {peer_id}" if success else f"Failed to disconnect from peer: {peer_id}"
            }
        except Exception as e:
            self.logger.error(f"Error disconnecting from peer: {str(e)}")
            return {
                "success": False,
                "message": f"Error disconnecting from peer: {str(e)}"
            }
    
    def get_peers(self, request) -> Dict[str, Any]:
        """Get connected peers."""
        self.logger.info("Getting connected peers")
        try:
            peers = self.libp2p_model.get_peers()
            return {
                "success": True,
                "message": f"Found {len(peers)} connected peers",
                "peers": peers
            }
        except Exception as e:
            self.logger.error(f"Error getting connected peers: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting connected peers: {str(e)}",
                "peers": []
            }
    
    def dht_get(self, request) -> Dict[str, Any]:
        """Get a value from the DHT."""
        key = request.key
        self.logger.info(f"Getting value from DHT for key: {key}")
        try:
            value = self.libp2p_model.dht_get(key)
            if value is not None:
                return {
                    "success": True,
                    "message": f"Got value from DHT for key: {key}",
                    "value": value
                }
            else:
                return {
                    "success": False,
                    "message": f"Key not found in DHT: {key}",
                    "value": None
                }
        except Exception as e:
            self.logger.error(f"Error getting value from DHT: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting value from DHT: {str(e)}",
                "value": None
            }
    
    def dht_put(self, request) -> Dict[str, Any]:
        """Put a value in the DHT."""
        key = request.key
        value = request.value
        self.logger.info(f"Putting value in DHT for key: {key}")
        try:
            success = self.libp2p_model.dht_put(key, value)
            return {
                "success": success,
                "message": f"Put value in DHT for key: {key}" if success else f"Failed to put value in DHT for key: {key}"
            }
        except Exception as e:
            self.logger.error(f"Error putting value in DHT: {str(e)}")
            return {
                "success": False,
                "message": f"Error putting value in DHT: {str(e)}"
            }
    
    def dht_find_providers(self, request) -> Dict[str, Any]:
        """Find providers for a CID."""
        cid = request.cid
        self.logger.info(f"Finding providers for CID: {cid}")
        try:
            providers = self.libp2p_model.dht_find_providers(cid)
            return {
                "success": True,
                "message": f"Found {len(providers)} providers for CID: {cid}",
                "providers": providers
            }
        except Exception as e:
            self.logger.error(f"Error finding providers: {str(e)}")
            return {
                "success": False,
                "message": f"Error finding providers: {str(e)}",
                "providers": []
            }
    
    def dht_provide(self, request) -> Dict[str, Any]:
        """Announce that this node can provide a CID."""
        cid = request.cid
        self.logger.info(f"Providing CID: {cid}")
        try:
            success = self.libp2p_model.dht_provide(cid)
            return {
                "success": success,
                "message": f"Providing CID: {cid}" if success else f"Failed to provide CID: {cid}"
            }
        except Exception as e:
            self.logger.error(f"Error providing CID: {str(e)}")
            return {
                "success": False,
                "message": f"Error providing CID: {str(e)}"
            }
    
    def pubsub_subscribe(self, request) -> Dict[str, Any]:
        """Subscribe to a pubsub topic."""
        topic = request.topic
        self.logger.info(f"Subscribing to topic: {topic}")
        try:
            # We need a callback for the subscription
            def message_callback(peer_id, data):
                self.logger.info(f"Received message on topic {topic} from peer {peer_id}")
            
            success = self.libp2p_model.pubsub_subscribe(topic, message_callback)
            return {
                "success": success,
                "message": f"Subscribed to topic: {topic}" if success else f"Failed to subscribe to topic: {topic}"
            }
        except Exception as e:
            self.logger.error(f"Error subscribing to topic: {str(e)}")
            return {
                "success": False,
                "message": f"Error subscribing to topic: {str(e)}"
            }
    
    def pubsub_publish(self, request) -> Dict[str, Any]:
        """Publish to a pubsub topic."""
        topic = request.topic
        data = request.data
        self.logger.info(f"Publishing to topic: {topic}")
        try:
            if isinstance(data, str):
                data = data.encode()
            
            success = self.libp2p_model.pubsub_publish(topic, data)
            return {
                "success": success,
                "message": f"Published to topic: {topic}" if success else f"Failed to publish to topic: {topic}"
            }
        except Exception as e:
            self.logger.error(f"Error publishing to topic: {str(e)}")
            return {
                "success": False,
                "message": f"Error publishing to topic: {str(e)}"
            }
    
    def get_node_info(self, request) -> Dict[str, Any]:
        """Get information about the LibP2P node."""
        self.logger.info("Getting LibP2P node info")
        try:
            info = self.libp2p_model.get_info()
            return {
                "success": True,
                "message": "Got LibP2P node info",
                "info": info
            }
        except Exception as e:
            self.logger.error(f"Error getting LibP2P node info: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting LibP2P node info: {str(e)}",
                "info": {}
            }