"""
IPFS metadata index synchronization handler.

This module provides handlers for metadata index synchronization using IPFS pubsub.
It manages subscription to relevant topics and routes messages to the appropriate
handlers in the ArrowMetadataIndex.
"""

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

# Create logger
logger = logging.getLogger(__name__)


class MetadataSyncHandler:
    """
    Handler for metadata index synchronization using IPFS pubsub.

    This class manages subscriptions to relevant pubsub topics and routes
    messages to the appropriate handlers in the ArrowMetadataIndex.
    """

    def __init__(self, index, ipfs_client, cluster_id: str = None, node_id: str = None):
        """
        Initialize the metadata sync handler.

        Args:
            index: ArrowMetadataIndex instance to synchronize
            ipfs_client: IPFS client instance for pubsub communication
            cluster_id: ID of the cluster (optional)
            node_id: ID of this node (optional)
        """
        self.index = index
        self.ipfs_client = ipfs_client
        self.cluster_id = cluster_id
        self.node_id = node_id or (
            ipfs_client.get_node_id() if hasattr(ipfs_client, "get_node_id") else None
        )

        # Keep track of subscriptions
        self.subscriptions = {}

        # Flag to indicate if the handler is running
        self.running = False

        # Thread for periodic sync
        self.sync_thread = None
        self.stop_sync = threading.Event()

        logger.info(
            f"Initialized MetadataSyncHandler with node_id={self.node_id}, cluster_id={self.cluster_id}"
        )

    def start(self):
        """
        Start the metadata sync handler.

        This subscribes to the relevant pubsub topics and starts the sync thread.
        """
        if self.running:
            logger.warning("MetadataSyncHandler already running")
            return

        if not self.ipfs_client:
            logger.error("No IPFS client available for pubsub communication")
            return

        logger.info("Starting MetadataSyncHandler")

        try:
            # Subscribe to partition request topic
            self._subscribe(
                f"ipfs-kit/metadata-index/{self.cluster_id}/partitions",
                self._handle_partition_request,
            )

            # Subscribe to partition data request topic
            self._subscribe(
                f"ipfs-kit/metadata-index/{self.cluster_id}/partition-data",
                self._handle_partition_data_request,
            )

            # Mark as running
            self.running = True

            # Start sync thread
            self.stop_sync.clear()
            self.sync_thread = threading.Thread(
                target=self._sync_loop, daemon=True, name="metadata-sync"
            )
            self.sync_thread.start()

            logger.info("MetadataSyncHandler started successfully")

        except Exception as e:
            logger.error(f"Error starting MetadataSyncHandler: {e}")
            self.stop()

    def stop(self):
        """
        Stop the metadata sync handler.

        This unsubscribes from all pubsub topics and stops the sync thread.
        """
        if not self.running:
            return

        logger.info("Stopping MetadataSyncHandler")

        # Stop sync thread
        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_sync.set()
            self.sync_thread.join(timeout=5)

        # Unsubscribe from all topics
        for topic in list(self.subscriptions.keys()):
            self._unsubscribe(topic)

        # Mark as not running
        self.running = False

        logger.info("MetadataSyncHandler stopped")

    def _subscribe(self, topic: str, handler: Callable):
        """
        Subscribe to a pubsub topic.

        Args:
            topic: Topic to subscribe to
            handler: Handler function for messages
        """
        if not self.ipfs_client or not hasattr(self.ipfs_client, "pubsub_subscribe"):
            logger.warning("IPFS client doesn't support pubsub_subscribe")
            return

        # Create wrapper handler
        def wrapper(msg):
            try:
                # Parse message data
                from_peer = msg.get("from")
                data = msg.get("data")

                # Skip messages from self
                if from_peer == self.node_id:
                    return

                # Parse JSON data if possible
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                try:
                    data = json.loads(data)
                except Exception:
                    # Not JSON, pass as-is
                    pass

                # Call handler
                handler(data, from_peer, topic)

            except Exception as e:
                logger.error(f"Error handling pubsub message: {e}")

        # Subscribe to topic
        result = self.ipfs_client.pubsub_subscribe(topic, wrapper)

        if result and result.get("success", False):
            self.subscriptions[topic] = wrapper
            logger.debug(f"Subscribed to topic: {topic}")
        else:
            logger.warning(f"Failed to subscribe to topic: {topic}")

    def _unsubscribe(self, topic: str):
        """
        Unsubscribe from a pubsub topic.

        Args:
            topic: Topic to unsubscribe from
        """
        if not self.ipfs_client or not hasattr(self.ipfs_client, "pubsub_unsubscribe"):
            return

        if topic in self.subscriptions:
            result = self.ipfs_client.pubsub_unsubscribe(topic)

            if result and result.get("success", False):
                del self.subscriptions[topic]
                logger.debug(f"Unsubscribed from topic: {topic}")
            else:
                logger.warning(f"Failed to unsubscribe from topic: {topic}")

    def _handle_partition_request(self, data, from_peer, topic):
        """
        Handle a partition request message.

        Args:
            data: Message data
            from_peer: Peer ID that sent the message
            topic: Topic the message was received on
        """
        if not isinstance(data, dict) or data.get("type") != "partition_request":
            return

        logger.debug(f"Received partition request from {from_peer}")

        # Add the requester from from_peer if not in the data
        if "requester" not in data:
            data["requester"] = from_peer

        # Let the index handle it
        self.index.handle_partition_request(data)

    def _handle_partition_data_request(self, data, from_peer, topic):
        """
        Handle a partition data request message.

        Args:
            data: Message data
            from_peer: Peer ID that sent the message
            topic: Topic the message was received on
        """
        if not isinstance(data, dict) or data.get("type") != "partition_data_request":
            return

        logger.debug(f"Received partition data request from {from_peer}")

        # Add the requester from from_peer if not in the data
        if "requester" not in data:
            data["requester"] = from_peer

        # Let the index handle it
        self.index.handle_partition_data_request(data)

    def _sync_loop(self):
        """
        Background thread that periodically synchronizes with peers.
        """
        # Wait a bit before starting sync to allow other components to initialize
        time.sleep(10)

        while not self.stop_sync.is_set():
            try:
                # Check if the index and client are available
                if not self.index or not self.ipfs_client:
                    time.sleep(60)
                    continue

                # Get list of peers
                if hasattr(self.ipfs_client, "swarm_peers"):
                    peers_result = self.ipfs_client.swarm_peers()

                    if peers_result and peers_result.get("success", False):
                        peers = peers_result.get("peers", [])

                        # Filter out self
                        peers = [p for p in peers if p != self.node_id]

                        logger.debug(f"Found {len(peers)} peers for potential sync")

                        # Sync with a subset of peers
                        # In a real implementation, we would use a more sophisticated
                        # algorithm to select which peers to sync with
                        import random

                        if peers:
                            selected_peers = random.sample(peers, min(3, len(peers)))

                            for peer in selected_peers:
                                try:
                                    # Sync with peer
                                    logger.debug(f"Syncing with peer: {peer}")

                                    # Get peer's partition metadata
                                    partitions = self.index._get_peer_partitions(peer)

                                    if partitions:
                                        # Process partition metadata
                                        for partition_id, metadata in partitions.items():
                                            # Convert to int if it's a string
                                            if isinstance(partition_id, str):
                                                try:
                                                    partition_id = int(partition_id)
                                                except ValueError:
                                                    logger.warning(
                                                        f"Invalid partition ID: {partition_id}"
                                                    )
                                                    continue

                                            # Check if we need this partition
                                            if partition_id not in self.index.partitions:
                                                # New partition, download it
                                                logger.info(
                                                    f"Downloading new partition {partition_id} from peer {peer}"
                                                )
                                                self.index._download_partition(
                                                    peer, partition_id, metadata
                                                )
                                            elif metadata.get("mtime", 0) > self.index.partitions[
                                                partition_id
                                            ].get("mtime", 0):
                                                # Newer version, download it
                                                logger.info(
                                                    f"Updating partition {partition_id} from peer {peer} (newer version)"
                                                )
                                                self.index._download_partition(
                                                    peer, partition_id, metadata
                                                )

                                except Exception as e:
                                    logger.error(f"Error syncing with peer {peer}: {e}")

                # Wait before next sync
                time.sleep(300)  # 5 minutes

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                time.sleep(60)  # Wait a bit before retrying

        logger.info("Sync loop stopped")

    def publish_index(self):
        """
        Publish the metadata index to IPFS DAG for discoverable access.

        Returns:
            Result of the publish operation
        """
        if not self.index:
            return {"success": False, "error": "No index available"}

        try:
            # Publish the index
            result = self.index.publish_index_dag()

            if result and result.get("success", False):
                logger.info(f"Published metadata index with CID: {result.get('dag_cid')}")

            return result

        except Exception as e:
            logger.error(f"Error publishing index: {e}")
            return {"success": False, "error": str(e)}

    def sync_with_peer(self, peer_id: str) -> Dict[str, Any]:
        """
        Manually trigger synchronization with a specific peer.

        Args:
            peer_id: ID of the peer to sync with

        Returns:
            Result of the sync operation
        """
        result = {
            "success": False,
            "operation": "sync_with_peer",
            "peer": peer_id,
            "timestamp": time.time(),
        }

        if not self.index or not self.ipfs_client:
            result["error"] = "No index or IPFS client available"
            return result

        try:
            # Get peer's partition metadata
            partitions = self.index._get_peer_partitions(peer_id)

            if not partitions:
                result["error"] = "Failed to get partition metadata from peer"
                return result

            # Track partitions downloaded
            downloaded = []
            updated = []

            # Process partition metadata
            for partition_id, metadata in partitions.items():
                # Convert to int if it's a string
                if isinstance(partition_id, str):
                    try:
                        partition_id = int(partition_id)
                    except ValueError:
                        logger.warning(f"Invalid partition ID: {partition_id}")
                        continue

                # Check if we need this partition
                if partition_id not in self.index.partitions:
                    # New partition, download it
                    if self.index._download_partition(peer_id, partition_id, metadata):
                        downloaded.append(partition_id)
                elif metadata.get("mtime", 0) > self.index.partitions[partition_id].get("mtime", 0):
                    # Newer version, download it
                    if self.index._download_partition(peer_id, partition_id, metadata):
                        updated.append(partition_id)

            # Update result
            result["success"] = True
            result["partitions_found"] = len(partitions)
            result["partitions_downloaded"] = len(downloaded)
            result["partitions_updated"] = len(updated)
            result["downloaded"] = downloaded
            result["updated"] = updated

            return result

        except Exception as e:
            logger.error(f"Error syncing with peer {peer_id}: {e}")
            result["error"] = str(e)
            return result
