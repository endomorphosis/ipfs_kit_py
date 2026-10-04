#!/usr/bin/env python3
"""
Network Simulator for IPFS Kit MCP Testing

This file consolidates functionality from:
- run_mcp_network_tests.py
- run_mcp_partition_test.py
- run_mcp_partial_partition_test.py
- run_mcp_asymmetric_partition_test.py
- run_mcp_intermittent_connectivity_test.py
- run_mcp_communication_test.py
- run_mcp_time_based_recovery_test.py

It provides a unified framework for simulating various network conditions
and testing MCP behavior under different failure scenarios.
"""

import os
import sys
import time
import json
import random
import logging
import argparse
import threading
import subprocess
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Set, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("network_simulator")

class NetworkSimulator:
    """Simulates network conditions for MCP testing."""
    
    # Network scenario types
    SCENARIOS = {
        "full_partition": "Complete network partition",
        "partial_partition": "Partial network partition",
        "asymmetric_partition": "Asymmetric network partition",
        "intermittent": "Intermittent connectivity",
        "latency": "High network latency",
        "packet_loss": "Random packet loss",
        "bandwidth_limit": "Limited bandwidth",
        "time_based_recovery": "Time-based recovery",
        "cascading_failure": "Cascading node failures"
    }
    
    def __init__(
        self,
        scenario: str,
        nodes: int = 3,
        duration: int = 60,
        test_dir: str = "data/test_results",
        mcp_args: Optional[Dict[str, Any]] = None,
        network_args: Optional[Dict[str, Any]] = None,
        log_network: bool = True,
        verbose: bool = False
    ):
        """
        Initialize the network simulator.
        
        Args:
            scenario: Network scenario to simulate
            nodes: Number of MCP nodes to create
            duration: Duration of the simulation in seconds
            test_dir: Directory for test output
            mcp_args: Arguments for MCP nodes
            network_args: Arguments for network simulation
            log_network: Enable network event logging
            verbose: Enable verbose output
        """
        self.scenario = scenario
        self.nodes = nodes
        self.duration = duration
        self.test_dir = os.path.abspath(test_dir)
        self.mcp_args = mcp_args or {}
        self.network_args = network_args or {}
        self.log_network = log_network
        self.verbose = verbose
        
        # Validate scenario
        if scenario not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
        
        # Create test directory
        os.makedirs(self.test_dir, exist_ok=True)
        
        # MCP node processes and network conditions
        self.node_processes = {}
        self.node_ports = {}
        self.network_conditions = {}
        
        # Network event log
        self.network_log = []
        self.network_log_lock = threading.Lock()
        
        # Simulation status
        self.running = False
        self.start_time = None
        self.stop_event = threading.Event()
        
        logger.info(f"Initialized network simulator for scenario: {scenario}")
    
    def setup_nodes(self) -> bool:
        """
        Set up MCP nodes for the simulation.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        logger.info(f"Setting up {self.nodes} MCP nodes")
        
        try:
            base_port = self.mcp_args.get("base_port", 9000)
            
            for i in range(self.nodes):
                node_id = f"node_{i}"
                port = base_port + i
                self.node_ports[node_id] = port
                
                # Create node directory
                node_dir = os.path.join(self.test_dir, node_id)
                os.makedirs(node_dir, exist_ok=True)
                
                # Create node configuration
                config = {
                    "node_id": node_id,
                    "port": port,
                    "isolation_mode": True,
                    "debug_mode": True,
                    "persistence_path": os.path.join(node_dir, "data"),
                    "peers": [base_port + j for j in range(self.nodes) if j != i]
                }
                
                # Add additional MCP arguments
                for key, value in self.mcp_args.items():
                    if key not in config and key != "base_port":
                        config[key] = value
                
                # Save configuration
                config_path = os.path.join(node_dir, "config.json")
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                
                logger.info(f"Created configuration for {node_id} at port {port}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up nodes: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def start_nodes(self) -> bool:
        """
        Start MCP nodes for the simulation.
        
        Returns:
            bool: True if all nodes started successfully, False otherwise
        """
        logger.info("Starting MCP nodes")
        
        try:
            # Check for server_runner.py
            server_runner_path = os.path.join(os.path.dirname(__file__), "server_runner.py")
            if not os.path.exists(server_runner_path):
                logger.error(f"Server runner not found: {server_runner_path}")
                return False
            
            # Start each node
            for i in range(self.nodes):
                node_id = f"node_{i}"
                port = self.node_ports[node_id]
                node_dir = os.path.join(self.test_dir, node_id)
                config_path = os.path.join(node_dir, "config.json")
                
                # Create log file
                log_path = os.path.join(node_dir, "node.log")
                
                # Start node process
                cmd = [
                    sys.executable,
                    server_runner_path,
                    "--server-type=anyio",
                    f"--port={port}",
                    "--isolation",
                    "--debug",
                    f"--config={config_path}"
                ]
                
                logger.info(f"Starting {node_id} with command: {' '.join(cmd)}")
                
                with open(log_path, 'w') as log_file:
                    process = subprocess.Popen(
                        cmd,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        cwd=node_dir
                    )
                    
                    self.node_processes[node_id] = process
                
                # Wait a bit for node to start
                time.sleep(1)
                
                # Check if still running
                if process.poll() is not None:
                    logger.error(f"Node {node_id} failed to start (exit code: {process.returncode})")
                    return False
            
            logger.info(f"Started {len(self.node_processes)} MCP nodes")
            return True
            
        except Exception as e:
            logger.error(f"Error starting nodes: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def setup_network_conditions(self) -> bool:
        """
        Set up initial network conditions for the simulation.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        logger.info("Setting up initial network conditions")
        
        try:
            # Initialize fully connected network
            for i in range(self.nodes):
                node_id = f"node_{i}"
                self.network_conditions[node_id] = {
                    f"node_{j}": {"connected": True, "latency": 0, "packet_loss": 0}
                    for j in range(self.nodes) if j != i
                }
            
            # Log initial network state
            self._log_network_event("network_initialized", "Initialized fully connected network")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up network conditions: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _log_network_event(self, event_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """Log a network event."""
        if not self.log_network:
            return
            
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "description": description,
            "elapsed_seconds": (time.time() - self.start_time) if self.start_time else 0
        }
        
        if details:
            event["details"] = details
            
        with self.network_log_lock:
            self.network_log.append(event)
            
        if self.verbose:
            logger.info(f"Network Event: {description}")
    
    def _apply_network_conditions(self):
        """Apply network conditions to the running nodes."""
        # In a real implementation, this would use iptables, tc, or similar
        # tools to modify the network behavior between nodes.
        # For this demonstration, we'll simulate by modifying request handlers
        # in each node through a control API.
        
        logger.info("Applying network conditions")
        
        try:
            for node_id, connections in self.network_conditions.items():
                # Use the node's API to configure network behavior
                port = self.node_ports[node_id]
                
                for peer_id, condition in connections.items():
                    peer_port = self.node_ports[peer_id]
                    
                    # Example API call to set network condition
                    self._configure_node_network(
                        port, 
                        peer_port, 
                        connected=condition["connected"],
                        latency=condition["latency"],
                        packet_loss=condition["packet_loss"]
                    )
                    
            self._log_network_event("network_conditions_applied", "Applied network conditions")
            
        except Exception as e:
            logger.error(f"Error applying network conditions: {e}")
            logger.error(traceback.format_exc())
    
    def _configure_node_network(self, node_port: int, peer_port: int, connected: bool, latency: int, packet_loss: int):
        """
        Configure network conditions between nodes.
        
        In a real implementation, this would make API calls to control
        the network behavior. For this example, we'll just log the changes.
        """
        state = "connected" if connected else "disconnected"
        logger.info(f"Setting node at port {node_port} to be {state} to peer at port {peer_port} "
                   f"(latency: {latency}ms, packet loss: {packet_loss}%)")
    
    def run_scenario(self) -> bool:
        """
        Run the selected network scenario.
        
        Returns:
            bool: True if scenario completed successfully, False otherwise
        """
        logger.info(f"Running network scenario: {self.scenario}")
        
        self.start_time = time.time()
        self.running = True
        self.stop_event.clear()
        
        # Get scenario runner
        scenario_runner = getattr(self, f"_run_{self.scenario}_scenario", None)
        if not scenario_runner:
            logger.error(f"No implementation for scenario: {self.scenario}")
            return False
        
        try:
            # Start scenario thread
            scenario_thread = threading.Thread(
                target=scenario_runner,
                name=f"scenario-{self.scenario}"
            )
            scenario_thread.daemon = True
            scenario_thread.start()
            
            # Wait for completion or interrupt
            end_time = time.time() + self.duration
            while time.time() < end_time and not self.stop_event.is_set():
                time.sleep(1)
                
                # Print progress
                elapsed = time.time() - self.start_time
                remaining = self.duration - elapsed
                if self.verbose and int(elapsed) % 10 == 0:
                    logger.info(f"Scenario in progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining")
            
            # Stop scenario
            self.stop_event.set()
            scenario_thread.join(timeout=5)
            
            # Set final status
            self.running = False
            
            # Save network log
            if self.log_network:
                log_path = os.path.join(self.test_dir, "network_events.json")
                with open(log_path, 'w') as f:
                    json.dump(self.network_log, f, indent=2)
                logger.info(f"Saved network events to {log_path}")
            
            logger.info(f"Completed network scenario: {self.scenario}")
            return True
            
        except Exception as e:
            logger.error(f"Error running scenario: {e}")
            logger.error(traceback.format_exc())
            self.running = False
            return False
    
    def _run_full_partition_scenario(self):
        """Run complete network partition scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            # Create two node groups
            group_size = self.nodes // 2
            group1 = [f"node_{i}" for i in range(group_size)]
            group2 = [f"node_{i}" for i in range(group_size, self.nodes)]
            
            self._log_network_event(
                "partition_groups_created", 
                f"Created partition groups: {group1} and {group2}"
            )
            
            # Disconnect groups from each other
            logger.info(f"Creating network partition between {group1} and {group2}")
            
            for node1 in group1:
                for node2 in group2:
                    # Disconnect in both directions
                    self.network_conditions[node1][node2]["connected"] = False
                    self.network_conditions[node2][node1]["connected"] = False
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "full_partition_created", 
                "Created full network partition"
            )
            
            # Wait for partition duration (half of total scenario time)
            partition_duration = self.duration // 2
            partition_end = time.time() + partition_duration
            
            while time.time() < partition_end and not self.stop_event.is_set():
                time.sleep(1)
            
            # Heal the partition
            logger.info("Healing network partition")
            
            for node1 in group1:
                for node2 in group2:
                    # Reconnect in both directions
                    self.network_conditions[node1][node2]["connected"] = True
                    self.network_conditions[node2][node1]["connected"] = True
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "partition_healed", 
                "Healed network partition"
            )
            
            # Continue until scenario ends
            while not self.stop_event.is_set():
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in full partition scenario: {e}")
            logger.error(traceback.format_exc())
    
    def _run_partial_partition_scenario(self):
        """Run partial network partition scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            # Create three groups: A, B, and C
            # Group A can talk to B and C
            # Group B can talk to A but not C
            # Group C can talk to A but not B
            
            group_size = self.nodes // 3
            group_a = [f"node_{i}" for i in range(group_size)]
            group_b = [f"node_{i}" for i in range(group_size, 2 * group_size)]
            group_c = [f"node_{i}" for i in range(2 * group_size, self.nodes)]
            
            self._log_network_event(
                "partition_groups_created", 
                f"Created partial partition groups: A={group_a}, B={group_b}, C={group_c}"
            )
            
            # Disconnect B from C
            logger.info(f"Creating partial network partition: B={group_b} disconnected from C={group_c}")
            
            for node_b in group_b:
                for node_c in group_c:
                    # Disconnect in both directions
                    self.network_conditions[node_b][node_c]["connected"] = False
                    self.network_conditions[node_c][node_b]["connected"] = False
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "partial_partition_created", 
                "Created partial network partition"
            )
            
            # Wait for partition duration (half of total scenario time)
            partition_duration = self.duration // 2
            partition_end = time.time() + partition_duration
            
            while time.time() < partition_end and not self.stop_event.is_set():
                time.sleep(1)
            
            # Heal the partition
            logger.info("Healing partial network partition")
            
            for node_b in group_b:
                for node_c in group_c:
                    # Reconnect in both directions
                    self.network_conditions[node_b][node_c]["connected"] = True
                    self.network_conditions[node_c][node_b]["connected"] = True
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "partition_healed", 
                "Healed partial network partition"
            )
            
            # Continue until scenario ends
            while not self.stop_event.is_set():
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in partial partition scenario: {e}")
            logger.error(traceback.format_exc())
    
    def _run_asymmetric_partition_scenario(self):
        """Run asymmetric network partition scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            # Create asymmetric partition where:
            # A can send to B but B cannot send to A
            # Both can communicate with all other nodes
            
            node_a = "node_0"
            node_b = "node_1"
            
            self._log_network_event(
                "asymmetric_partition_setup", 
                f"Setting up asymmetric partition between {node_a} and {node_b}"
            )
            
            # Create one-way partition
            logger.info(f"Creating asymmetric partition: {node_b} cannot send to {node_a}")
            
            # B cannot send to A, but A can send to B
            self.network_conditions[node_b][node_a]["connected"] = False
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "asymmetric_partition_created", 
                f"Created asymmetric partition: {node_b} cannot send to {node_a}"
            )
            
            # Wait for partition duration (half of total scenario time)
            partition_duration = self.duration // 2
            partition_end = time.time() + partition_duration
            
            while time.time() < partition_end and not self.stop_event.is_set():
                time.sleep(1)
            
            # Heal the partition
            logger.info("Healing asymmetric partition")
            
            self.network_conditions[node_b][node_a]["connected"] = True
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "partition_healed", 
                "Healed asymmetric partition"
            )
            
            # Continue until scenario ends
            while not self.stop_event.is_set():
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in asymmetric partition scenario: {e}")
            logger.error(traceback.format_exc())
    
    def _run_intermittent_scenario(self):
        """Run intermittent connectivity scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            self._log_network_event(
                "intermittent_connectivity_start", 
                "Starting intermittent connectivity scenario"
            )
            
            # Run until scenario ends
            while not self.stop_event.is_set():
                # Select a random node
                node_a = f"node_{random.randint(0, self.nodes - 1)}"
                
                # Select a random peer
                peers = list(self.network_conditions[node_a].keys())
                if not peers:
                    continue
                    
                node_b = random.choice(peers)
                
                # Disconnect
                logger.info(f"Temporarily disconnecting {node_a} from {node_b}")
                
                self.network_conditions[node_a][node_b]["connected"] = False
                self.network_conditions[node_b][node_a]["connected"] = False
                
                # Apply network changes
                self._apply_network_conditions()
                
                self._log_network_event(
                    "node_disconnected", 
                    f"Temporarily disconnected {node_a} from {node_b}"
                )
                
                # Wait for disconnect duration (1-5 seconds)
                disconnect_duration = random.randint(1, 5)
                disconnect_end = time.time() + disconnect_duration
                
                while time.time() < disconnect_end and not self.stop_event.is_set():
                    time.sleep(0.1)
                
                # Reconnect
                logger.info(f"Reconnecting {node_a} to {node_b}")
                
                self.network_conditions[node_a][node_b]["connected"] = True
                self.network_conditions[node_b][node_a]["connected"] = True
                
                # Apply network changes
                self._apply_network_conditions()
                
                self._log_network_event(
                    "node_reconnected", 
                    f"Reconnected {node_a} to {node_b}"
                )
                
                # Wait for stable duration (5-15 seconds)
                stable_duration = random.randint(5, 15)
                stable_end = time.time() + stable_duration
                
                while time.time() < stable_end and not self.stop_event.is_set():
                    time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in intermittent connectivity scenario: {e}")
            logger.error(traceback.format_exc())
    
    def _run_latency_scenario(self):
        """Run high network latency scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            self._log_network_event(
                "high_latency_start", 
                "Starting high latency scenario"
            )
            
            # Add latency to all connections
            latency_ms = self.network_args.get("latency_ms", 200)
            logger.info(f"Adding {latency_ms}ms latency to all connections")
            
            for node_id, connections in self.network_conditions.items():
                for peer_id in connections:
                    self.network_conditions[node_id][peer_id]["latency"] = latency_ms
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "high_latency_applied", 
                f"Applied {latency_ms}ms latency to all connections"
            )
            
            # Wait for latency duration (half of total scenario time)
            latency_duration = self.duration // 2
            latency_end = time.time() + latency_duration
            
            while time.time() < latency_end and not self.stop_event.is_set():
                time.sleep(1)
            
            # Remove latency
            logger.info("Removing latency from all connections")
            
            for node_id, connections in self.network_conditions.items():
                for peer_id in connections:
                    self.network_conditions[node_id][peer_id]["latency"] = 0
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "latency_removed", 
                "Removed latency from all connections"
            )
            
            # Continue until scenario ends
            while not self.stop_event.is_set():
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in high latency scenario: {e}")
            logger.error(traceback.format_exc())
    
    def _run_packet_loss_scenario(self):
        """Run random packet loss scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            self._log_network_event(
                "packet_loss_start", 
                "Starting packet loss scenario"
            )
            
            # Add packet loss to all connections
            packet_loss_pct = self.network_args.get("packet_loss_pct", 10)
            logger.info(f"Adding {packet_loss_pct}% packet loss to all connections")
            
            for node_id, connections in self.network_conditions.items():
                for peer_id in connections:
                    self.network_conditions[node_id][peer_id]["packet_loss"] = packet_loss_pct
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "packet_loss_applied", 
                f"Applied {packet_loss_pct}% packet loss to all connections"
            )
            
            # Wait for packet loss duration (half of total scenario time)
            packet_loss_duration = self.duration // 2
            packet_loss_end = time.time() + packet_loss_duration
            
            while time.time() < packet_loss_end and not self.stop_event.is_set():
                time.sleep(1)
            
            # Remove packet loss
            logger.info("Removing packet loss from all connections")
            
            for node_id, connections in self.network_conditions.items():
                for peer_id in connections:
                    self.network_conditions[node_id][peer_id]["packet_loss"] = 0
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "packet_loss_removed", 
                "Removed packet loss from all connections"
            )
            
            # Continue until scenario ends
            while not self.stop_event.is_set():
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in packet loss scenario: {e}")
            logger.error(traceback.format_exc())
    
    def _run_bandwidth_limit_scenario(self):
        """Run limited bandwidth scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            self._log_network_event(
                "bandwidth_limit_start", 
                "Starting bandwidth limit scenario"
            )
            
            # Add bandwidth limit (not directly simulated in this example)
            bandwidth_kbps = self.network_args.get("bandwidth_kbps", 100)
            logger.info(f"Limiting bandwidth to {bandwidth_kbps} Kbps for all connections")
            
            self._log_network_event(
                "bandwidth_limited", 
                f"Limited bandwidth to {bandwidth_kbps} Kbps for all connections"
            )
            
            # Wait for bandwidth limit duration (half of total scenario time)
            limit_duration = self.duration // 2
            limit_end = time.time() + limit_duration
            
            while time.time() < limit_end and not self.stop_event.is_set():
                time.sleep(1)
            
            # Remove bandwidth limit
            logger.info("Removing bandwidth limits")
            
            self._log_network_event(
                "bandwidth_limit_removed", 
                "Removed bandwidth limits"
            )
            
            # Continue until scenario ends
            while not self.stop_event.is_set():
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in bandwidth limit scenario: {e}")
            logger.error(traceback.format_exc())
    
    def _run_time_based_recovery_scenario(self):
        """Run time-based recovery scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            self._log_network_event(
                "time_based_recovery_start", 
                "Starting time-based recovery scenario"
            )
            
            # Disconnect all nodes from each other
            logger.info("Disconnecting all nodes")
            
            for node_id, connections in self.network_conditions.items():
                for peer_id in connections:
                    self.network_conditions[node_id][peer_id]["connected"] = False
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "all_nodes_disconnected", 
                "Disconnected all nodes from each other"
            )
            
            # Gradually reconnect nodes over time
            recovery_start = time.time()
            recovery_duration = self.duration * 0.8  # Use 80% of scenario time for recovery
            
            while time.time() < recovery_start + recovery_duration and not self.stop_event.is_set():
                # Calculate progress (0.0 to 1.0)
                progress = (time.time() - recovery_start) / recovery_duration
                
                # Determine number of connections to restore
                total_connections = sum(len(connections) for connections in self.network_conditions.values())
                connections_to_restore = int(progress * total_connections)
                
                # Count current restored connections
                current_restored = sum(
                    1 for node_id, connections in self.network_conditions.items()
                    for peer_id, condition in connections.items()
                    if condition["connected"]
                )
                
                # Restore more if needed
                if connections_to_restore > current_restored:
                    # Find disconnected pairs
                    disconnected_pairs = [
                        (node_id, peer_id)
                        for node_id, connections in self.network_conditions.items()
                        for peer_id, condition in connections.items()
                        if not condition["connected"]
                    ]
                    
                    if disconnected_pairs:
                        # Select a random pair to reconnect
                        node_id, peer_id = random.choice(disconnected_pairs)
                        
                        # Reconnect
                        logger.info(f"Reconnecting {node_id} to {peer_id}")
                        self.network_conditions[node_id][peer_id]["connected"] = True
                        
                        # Also reconnect the reverse direction if it exists
                        if peer_id in self.network_conditions and node_id in self.network_conditions[peer_id]:
                            self.network_conditions[peer_id][node_id]["connected"] = True
                        
                        # Apply network changes
                        self._apply_network_conditions()
                        
                        self._log_network_event(
                            "nodes_reconnected", 
                            f"Reconnected {node_id} to {peer_id}"
                        )
                
                # Wait a bit before next reconnection
                time.sleep(1)
            
            # Ensure all nodes are reconnected at the end
            logger.info("Ensuring all nodes are reconnected")
            
            for node_id, connections in self.network_conditions.items():
                for peer_id in connections:
                    self.network_conditions[node_id][peer_id]["connected"] = True
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "full_recovery_complete", 
                "Completed time-based recovery of all connections"
            )
            
            # Continue until scenario ends
            while not self.stop_event.is_set():
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in time-based recovery scenario: {e}")
            logger.error(traceback.format_exc())
    
    def _run_cascading_failure_scenario(self):
        """Run cascading node failures scenario."""
        try:
            # Wait a bit for system to stabilize
            time.sleep(5)
            
            self._log_network_event(
                "cascading_failure_start", 
                "Starting cascading failure scenario"
            )
            
            # Calculate timing for node failures
            failure_interval = self.duration / (self.nodes + 1)
            recovery_start = self.duration * 0.6  # Start recovery after 60% of duration
            
            # Track failed nodes
            failed_nodes = set()
            
            # Run failure and recovery loop
            scenario_start = time.time()
            
            while not self.stop_event.is_set():
                current_time = time.time() - scenario_start
                
                # Check if it's time to fail a node
                if current_time < recovery_start and len(failed_nodes) < self.nodes - 1:
                    next_failure_time = len(failed_nodes) * failure_interval
                    
                    if current_time >= next_failure_time:
                        # Select a node to fail (that hasn't failed yet)
                        available_nodes = [
                            f"node_{i}" for i in range(self.nodes)
                            if f"node_{i}" not in failed_nodes
                        ]
                        
                        if available_nodes:
                            node_id = available_nodes[0]
                            
                            # Fail the node by disconnecting from all peers
                            logger.info(f"Failing node {node_id}")
                            
                            for peer_id in self.network_conditions[node_id]:
                                self.network_conditions[node_id][peer_id]["connected"] = False
                                
                                # Also disconnect in reverse direction
                                if peer_id in self.network_conditions and node_id in self.network_conditions[peer_id]:
                                    self.network_conditions[peer_id][node_id]["connected"] = False
                            
                            # Apply network changes
                            self._apply_network_conditions()
                            
                            # Add to failed nodes
                            failed_nodes.add(node_id)
                            
                            self._log_network_event(
                                "node_failed", 
                                f"Failed node {node_id}"
                            )
                
                # Check if it's time to recover nodes
                if current_time >= recovery_start and failed_nodes:
                    # Calculate nodes to recover
                    recovery_progress = (current_time - recovery_start) / (self.duration - recovery_start)
                    nodes_to_recover = int(len(failed_nodes) * recovery_progress)
                    
                    # Recover nodes
                    for _ in range(nodes_to_recover):
                        if failed_nodes:
                            node_id = failed_nodes.pop()
                            
                            # Reconnect the node to all peers
                            logger.info(f"Recovering node {node_id}")
                            
                            for peer_id in self.network_conditions[node_id]:
                                self.network_conditions[node_id][peer_id]["connected"] = True
                                
                                # Also reconnect in reverse direction
                                if peer_id in self.network_conditions and node_id in self.network_conditions[peer_id]:
                                    self.network_conditions[peer_id][node_id]["connected"] = True
                            
                            # Apply network changes
                            self._apply_network_conditions()
                            
                            self._log_network_event(
                                "node_recovered", 
                                f"Recovered node {node_id}"
                            )
                
                # Check if scenario is complete
                if current_time >= self.duration:
                    break
                    
                time.sleep(1)
            
            # Ensure all nodes are reconnected at the end
            logger.info("Ensuring all nodes are reconnected")
            
            for node_id, connections in self.network_conditions.items():
                for peer_id in connections:
                    self.network_conditions[node_id][peer_id]["connected"] = True
            
            # Apply network changes
            self._apply_network_conditions()
            
            self._log_network_event(
                "all_nodes_recovered", 
                "Recovered all nodes from cascading failure"
            )
                
        except Exception as e:
            logger.error(f"Error in cascading failure scenario: {e}")
            logger.error(traceback.format_exc())
    
    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")
        
        # Stop all node processes
        for node_id, process in self.node_processes.items():
            try:
                logger.info(f"Stopping node {node_id}")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Node {node_id} did not terminate, killing")
                process.kill()
            except Exception as e:
                logger.error(f"Error stopping node {node_id}: {e}")
        
        self.node_processes.clear()
        logger.info("Cleanup complete")
    
    def analyze_results(self) -> Dict[str, Any]:
        """
        Analyze simulation results.
        
        Returns:
            Dict with analysis results
        """
        logger.info("Analyzing simulation results")
        
        results = {
            "scenario": self.scenario,
            "nodes": self.nodes,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": time.time(),
            "network_events": len(self.network_log),
            "node_statuses": {}
        }
        
        # Check if node processes are still running
        for node_id, process in self.node_processes.items():
            poll_result = process.poll()
            results["node_statuses"][node_id] = {
                "running": poll_result is None,
                "exit_code": poll_result
            }
        
        # Save analysis to file
        analysis_path = os.path.join(self.test_dir, "analysis.json")
        with open(analysis_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved analysis to {analysis_path}")
        
        return results

def main():
    """Run network simulation from command line."""
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Network Simulator for IPFS Kit MCP Testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Simulation configuration
    parser.add_argument("--scenario", choices=list(NetworkSimulator.SCENARIOS.keys()),
                    default="full_partition", help="Network scenario to simulate")
    parser.add_argument("--list-scenarios", action="store_true",
                    help="List available scenarios and exit")
    parser.add_argument("--nodes", type=int, default=3, help="Number of MCP nodes to create")
    parser.add_argument("--duration", type=int, default=60, help="Duration of simulation in seconds")
    parser.add_argument("--test-dir", default="data/test_results",
                    help="Directory for test output")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    # MCP configuration
    parser.add_argument("--mcp-port", type=int, default=9000,
                    help="Base port for MCP nodes")
    
    # Network configuration
    parser.add_argument("--latency", type=int, default=200,
                    help="Latency in ms for latency scenario")
    parser.add_argument("--packet-loss", type=int, default=10,
                    help="Packet loss percentage for packet loss scenario")
    parser.add_argument("--bandwidth", type=int, default=100,
                    help="Bandwidth limit in Kbps for bandwidth limit scenario")
    
    # Parse arguments
    args = parser.parse_args()
    
    # List scenarios if requested
    if args.list_scenarios:
        print("\nAvailable Network Scenarios:")
        print("=" * 50)
        for scenario, description in NetworkSimulator.SCENARIOS.items():
            print(f"{scenario}: {description}")
        print()
        return 0
    
    # Create MCP arguments
    mcp_args = {
        "base_port": args.mcp_port
    }
    
    # Create network arguments
    network_args = {
        "latency_ms": args.latency,
        "packet_loss_pct": args.packet_loss,
        "bandwidth_kbps": args.bandwidth
    }
    
    # Create test directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_dir = os.path.join(
        args.test_dir, 
        f"{args.scenario}_{args.nodes}nodes_{timestamp}"
    )
    
    # Create simulator
    simulator = NetworkSimulator(
        scenario=args.scenario,
        nodes=args.nodes,
        duration=args.duration,
        test_dir=test_dir,
        mcp_args=mcp_args,
        network_args=network_args,
        verbose=args.verbose
    )
    
    try:
        # Setup
        print(f"\nSetting up network simulation for scenario: {args.scenario}")
        
        if not simulator.setup_nodes():
            logger.error("Failed to set up nodes")
            return 1
            
        if not simulator.start_nodes():
            logger.error("Failed to start nodes")
            return 1
            
        if not simulator.setup_network_conditions():
            logger.error("Failed to set up network conditions")
            return 1
        
        # Run scenario
        print(f"Running {args.scenario} scenario for {args.duration} seconds with {args.nodes} nodes")
        
        if not simulator.run_scenario():
            logger.error("Failed to run scenario")
            return 1
        
        # Analyze results
        results = simulator.analyze_results()
        
        # Print summary
        print("\nSimulation completed successfully")
        print(f"Scenario: {args.scenario}")
        print(f"Duration: {results['end_time'] - results['start_time']:.1f} seconds")
        print(f"Network events: {results['network_events']}")
        print(f"Results saved to: {test_dir}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        # Clean up resources
        simulator.cleanup()

if __name__ == "__main__":
    sys.exit(main())