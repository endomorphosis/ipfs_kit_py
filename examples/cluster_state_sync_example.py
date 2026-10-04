import logging
import time
import threading
import os
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
# Assuming access to internal components for demonstration
# In a real application, these might be managed by ClusterManager
try:
    from ipfs_kit_py.cluster_state_sync import ClusterStateSync, StateCRDT
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer # Needed for PubSub simulation
except ImportError:
    logging.error("Required classes not found. Ensure cluster features are installed/available.")
    # Define dummy classes if imports fail, so the rest of the example structure runs
    class ClusterStateSync: pass
    class StateCRDT: pass
    class IPFSLibp2pPeer: pass


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("StateSyncExample")

# --- Configuration ---
# Basic config assuming two nodes communicating
# Node A (will run in main thread)
config_a = {
    'cluster': {
        'node_id': 'node_a',
        'cluster_id': 'sync_test_cluster',
        'state_sync': {
            'enabled': True,
            'sync_interval_seconds': 5, # Sync frequently for demo
            'conflict_resolution': 'lww',
            'pubsub_topic_prefix': '/sync_test/',
            'use_state_patching': True
        }
    },
    # LibP2P config needed for PubSub simulation
    'libp2p': {
         'listen_addrs': ['/ip4/127.0.0.1/tcp/0'], # Use ephemeral ports
         'bootstrap_peers': [] # Connect manually for demo
    }
}

# Node B (will run in a separate thread)
config_b = {
    'cluster': {
        'node_id': 'node_b',
        'cluster_id': 'sync_test_cluster',
        'state_sync': {
            'enabled': True,
            'sync_interval_seconds': 5,
            'conflict_resolution': 'lww',
            'pubsub_topic_prefix': '/sync_test/',
            'use_state_patching': True
        }
    },
    'libp2p': {
         'listen_addrs': ['/ip4/127.0.0.1/tcp/0'],
         'bootstrap_peers': []
    }
}

# --- Simulation Setup ---
# We need to simulate PubSub communication between two instances
# In a real cluster, libp2p handles this automatically.
# Here, we'll use a simple queue or direct calls for demonstration.

class SimulatedPubSub:
    """Very basic PubSub simulation for local testing."""
    def __init__(self):
        self.subscribers = {} # topic -> list of handlers

    def publish(self, topic, message, from_peer=None):
        log.debug(f"SimPubSub Publish on '{topic}' from {from_peer}: {message}")
        if topic in self.subscribers:
            for handler, peer_id in self.subscribers[topic]:
                # Don't send message back to sender
                if peer_id != from_peer:
                    try:
                        # Simulate receiving the message
                        handler({"data": message, "from": from_peer})
                    except Exception as e:
                        log.error(f"Error in handler for {peer_id} on topic {topic}: {e}")

    def subscribe(self, topic, handler, peer_id):
        log.debug(f"SimPubSub Subscribe by {peer_id} to '{topic}'")
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append((handler, peer_id))

    def unsubscribe(self, topic, handler, peer_id):
         log.debug(f"SimPubSub Unsubscribe by {peer_id} from '{topic}'")
         if topic in self.subscribers:
              self.subscribers[topic] = [(h, p) for h, p in self.subscribers[topic] if not (h == handler and p == peer_id)]


# Global simulated PubSub instance
sim_pubsub = SimulatedPubSub()

# --- Mock IPFS Kit / LibP2P Peer for PubSub ---
class MockIPFSClient:
    """Mocks IPFSSimpleAPI/LibP2P Peer for PubSub functionality."""
    def __init__(self, node_id):
        self.node_id = node_id
        self.subscriptions = {} # topic -> handler

    def get_peer_id(self):
        # In reality, this would be the libp2p Peer ID
        return self.node_id

    def pubsub_publish(self, topic, message):
        sim_pubsub.publish(topic, message, from_peer=self.node_id)
        return {"success": True}

    def pubsub_subscribe(self, topic, handler):
        if topic in self.subscriptions:
            # Avoid double subscription if handler is same
            if self.subscriptions[topic] == handler:
                return {"success": True}
            self.pubsub_unsubscribe(topic) # Unsubscribe previous if different

        sim_pubsub.subscribe(topic, handler, self.node_id)
        self.subscriptions[topic] = handler
        return {"success": True}

    def pubsub_unsubscribe(self, topic):
        if topic in self.subscriptions:
            handler = self.subscriptions.pop(topic)
            sim_pubsub.unsubscribe(topic, handler, self.node_id)
        return {"success": True}

    def close(self):
         # Unsubscribe all topics on close
         topics = list(self.subscriptions.keys())
         for topic in topics:
              self.pubsub_unsubscribe(topic)


# --- Node B Worker Thread ---
node_b_sync = None
node_b_stop_event = threading.Event()

def run_node_b():
    global node_b_sync
    log.info("Starting Node B...")
    mock_ipfs_b = MockIPFSClient(node_id='node_b')
    # Initialize state sync for Node B
    node_b_sync = ClusterStateSync(ipfs_kit_instance=mock_ipfs_b, config=config_b['cluster'])
    node_b_sync.initialize_distributed_state(initial_data={'tasks': {}, 'nodes': {'node_b': {'status': 'online'}}})
    node_b_sync.start_automatic_sync()
    log.info("Node B initialized and sync started.")

    # Simulate Node B making an update after a delay
    time.sleep(8)
    if not node_b_stop_event.is_set():
        log.info("Node B updating its state...")
        node_b_sync.crdt.apply_updates([
             {'op': 'add', 'path': '/nodes/node_b/load', 'value': 0.75, 'timestamp': time.time()}
        ])
        # Manually trigger announcement after local update for demo
        node_b_sync._announce_state_to_peers()

    # Keep running until stop event
    node_b_stop_event.wait()
    log.info("Node B stopping...")
    node_b_sync.stop_automatic_sync()
    mock_ipfs_b.close()
    log.info("Node B stopped.")


# --- Main Thread (Node A) ---
def main():
    log.info("Starting Node A...")
    mock_ipfs_a = MockIPFSClient(node_id='node_a')
    # Initialize state sync for Node A
    node_a_sync = ClusterStateSync(ipfs_kit_instance=mock_ipfs_a, config=config_a['cluster'])
    node_a_sync.initialize_distributed_state(initial_data={'tasks': {}, 'nodes': {'node_a': {'status': 'online'}}})
    node_a_sync.start_automatic_sync()
    log.info("Node A initialized and sync started.")

    # Start Node B in a separate thread
    thread_b = threading.Thread(target=run_node_b, daemon=True)
    thread_b.start()

    # Give Node B time to start and potentially connect/sync
    time.sleep(2)

    # Simulate Node A making an update
    log.info("Node A updating its state...")
    node_a_sync.crdt.apply_updates([
         {'op': 'add', 'path': '/tasks/task123', 'value': {'status': 'pending'}, 'timestamp': time.time()}
    ])
    # Manually trigger announcement after local update for demo
    node_a_sync._announce_state_to_peers()

    # Monitor state changes for a while
    for i in range(4):
        time.sleep(5) # Wait for sync interval + processing
        state_a = node_a_sync.crdt.state
        state_b = node_b_sync.crdt.state if node_b_sync else {}
        log.info(f"--- Sync Check {i+1} ---")
        log.info(f"Node A State: {state_a}")
        log.info(f"Node B State: {state_b}")
        # Check if states have converged (simple check for demo)
        if state_a == state_b and len(state_a.get('nodes', {})) == 2 and 'task123' in state_a.get('tasks', {}):
             log.info("States appear to have converged.")
             # break # Keep running to see Node B's update propagate

    # Stop Node B and Node A
    log.info("Signaling Node B to stop...")
    node_b_stop_event.set()
    thread_b.join(timeout=10)

    log.info("Stopping Node A...")
    node_a_sync.stop_automatic_sync()
    mock_ipfs_a.close()
    log.info("Node A stopped.")
    log.info("Cluster state sync example finished.")

if __name__ == "__main__":
    # Note: This example simulates PubSub locally.
    # A real cluster uses libp2p for communication.
    main()
