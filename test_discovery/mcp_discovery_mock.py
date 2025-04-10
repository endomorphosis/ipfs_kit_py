#!/usr/bin/env python3
"""
MCP Discovery Mock for Testing

This module provides mocked components for testing the MCP Discovery functionality
without requiring libp2p dependencies.
"""

import logging
import sys
import os
import time
import uuid
import json
import threading
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_discovery_mock")

# Import constants and classes from the original module
try:
    from ipfs_kit_py.mcp.models.mcp_discovery_model import (
        MCPServerRole, MCPMessageType, MCPServerCapabilities, MCPFeatureSet, MCPServerInfo
    )
    HAS_ORIGINAL_CLASSES = True
except ImportError:
    # Define fallback classes if imports fail
    logger.warning("Using fallback class definitions for MCP Discovery")
    HAS_ORIGINAL_CLASSES = False
    
    class MCPServerRole:
        """MCP server roles for the discovery protocol."""
        MASTER = "master"  # Coordinates across servers, handles high-level operations
        WORKER = "worker"  # Processes specific tasks, handles computational work
        HYBRID = "hybrid"  # Both master and worker capabilities
        EDGE = "edge"      # Limited capabilities, typically client-facing

    class MCPMessageType:
        """Message types for MCP server communication."""
        ANNOUNCE = "announce"         # Server announcing its presence
        CAPABILITIES = "capabilities"  # Server capabilities advertisement
        HEALTH = "health"             # Health check request/response
        TASK_REQUEST = "task_request"  # Request to process a task
        TASK_RESPONSE = "task_response" # Response with task results
        DISCOVERY = "discovery"       # Request for known servers
        SHUTDOWN = "shutdown"         # Graceful shutdown notification

    class MCPServerCapabilities:
        """Standard capability flags for MCP servers."""
        # Handling capabilities
        IPFS_DAEMON = "ipfs_daemon"             # Has IPFS daemon running
        IPFS_CLUSTER = "ipfs_cluster"           # Has IPFS cluster functionality
        LIBP2P = "libp2p"                       # Has libp2p direct functionality
        
        # Storage backend capabilities
        S3 = "s3"                               # Has S3 storage backend
        STORACHA = "storacha"                   # Has Storacha storage backend
        FILECOIN = "filecoin"                   # Has Filecoin storage backend
        HUGGINGFACE = "huggingface"             # Has HuggingFace integration
        LASSIE = "lassie"                       # Has Lassie retrieval capability
        
        # Feature capabilities
        WEBRTC = "webrtc"                       # Has WebRTC streaming capability
        FS_JOURNAL = "fs_journal"               # Has filesystem journal capability
        PEER_WEBSOCKET = "peer_websocket"       # Has peer websocket capability
        DISTRIBUTED = "distributed"             # Has distributed coordination
        AI_ML = "ai_ml"                         # Has AI/ML integration
        ARIA2 = "aria2"                         # Has Aria2 download capability
    
    class MCPFeatureSet:
        """Represents a set of features that an MCP server supports."""
        
        def __init__(self, features: List[str], version: str = "1.0.0"):
            self.features = set(features)
            self.version = version
            # Create a unique hash of this feature set for comparing compatibility
            feature_string = ",".join(sorted(self.features)) + "|" + self.version
            import hashlib
            self.feature_hash = hashlib.sha256(feature_string.encode()).hexdigest()
        
        def is_compatible_with(self, other: 'MCPFeatureSet') -> bool:
            """Check if this feature set is compatible with another feature set."""
            # For now, simple version match is sufficient
            return self.version == other.version
        
        def shares_features_with(self, other: 'MCPFeatureSet', min_shared: int = 1) -> bool:
            """Check if this feature set shares at least min_shared features with another set."""
            shared_features = self.features.intersection(other.features)
            return len(shared_features) >= min_shared
        
        def can_handle_request(self, required_features: List[str]) -> bool:
            """Check if this feature set can handle a request requiring specific features."""
            required = set(required_features)
            return required.issubset(self.features)
        
        def to_dict(self) -> Dict[str, Any]:
            """Convert to dictionary representation."""
            return {
                "features": list(self.features),
                "version": self.version,
                "feature_hash": self.feature_hash
            }
        
        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> 'MCPFeatureSet':
            """Create from dictionary representation."""
            return cls(
                features=data.get("features", []),
                version=data.get("version", "1.0.0")
            )
    
    class MCPServerInfo:
        """Information about an MCP server for discovery and coordination."""
        
        def __init__(
            self,
            server_id: str,
            role: str,
            feature_set: MCPFeatureSet,
            api_endpoint: Optional[str] = None,
            websocket_endpoint: Optional[str] = None,
            libp2p_peer_id: Optional[str] = None,
            libp2p_addresses: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None
        ):
            """Initialize MCP server information."""
            self.server_id = server_id
            self.role = role
            self.feature_set = feature_set
            self.api_endpoint = api_endpoint
            self.websocket_endpoint = websocket_endpoint
            self.libp2p_peer_id = libp2p_peer_id
            self.libp2p_addresses = libp2p_addresses or []
            self.metadata = metadata or {}
            self.last_seen = time.time()
            self.first_seen = time.time()
            self.health_status = {
                "healthy": True,
                "last_checked": time.time()
            }
            
        def to_dict(self) -> Dict[str, Any]:
            """Convert to dictionary representation."""
            return {
                "server_id": self.server_id,
                "role": self.role,
                "feature_set": self.feature_set.to_dict(),
                "api_endpoint": self.api_endpoint,
                "websocket_endpoint": self.websocket_endpoint,
                "libp2p_peer_id": self.libp2p_peer_id,
                "libp2p_addresses": self.libp2p_addresses,
                "metadata": self.metadata,
                "last_seen": self.last_seen,
                "first_seen": self.first_seen,
                "health_status": self.health_status
            }
        
        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> 'MCPServerInfo':
            """Create from dictionary representation."""
            server_info = cls(
                server_id=data.get("server_id", str(uuid.uuid4())),
                role=data.get("role", MCPServerRole.EDGE),
                feature_set=MCPFeatureSet.from_dict(data.get("feature_set", {"features": []})),
                api_endpoint=data.get("api_endpoint"),
                websocket_endpoint=data.get("websocket_endpoint"),
                libp2p_peer_id=data.get("libp2p_peer_id"),
                libp2p_addresses=data.get("libp2p_addresses", []),
                metadata=data.get("metadata", {})
            )
            
            # Restore timestamps
            server_info.last_seen = data.get("last_seen", time.time())
            server_info.first_seen = data.get("first_seen", time.time())
            server_info.health_status = data.get("health_status", {"healthy": True, "last_checked": time.time()})
            
            return server_info

# Define a mock for MCPDiscoveryModel that doesn't require libp2p
class MockMCPDiscoveryModel:
    """
    Mocked model for MCP server discovery and collaboration.
    
    This mock implementation provides the same interface as the real MCPDiscoveryModel
    but doesn't depend on libp2p or other problematic dependencies.
    """
    
    def __init__(
        self,
        server_id: Optional[str] = None,
        role: str = MCPServerRole.MASTER,
        features: Optional[List[str]] = None,
        libp2p_model=None,
        ipfs_model=None,
        cache_manager=None,
        credential_manager=None,
        resources=None,
        metadata=None
    ):
        """Initialize the mock MCP discovery model."""
        # Core attributes
        self.server_id = server_id or f"mcp-{str(uuid.uuid4())[:8]}"
        self.role = role
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Store optional components (not used in mock)
        self.libp2p_model = libp2p_model
        self.ipfs_model = ipfs_model
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        
        # Determine available features
        if features is None:
            features = self._detect_available_features()
        self.feature_set = MCPFeatureSet(features)
        
        # Create server info for this server
        self.server_info = self._create_local_server_info()
        
        # Track discovered servers
        self.known_servers = {}  # server_id -> MCPServerInfo
        self.server_lock = threading.Lock()  # For thread-safe access to server list
        
        # Create feature hash groups for compatible servers
        self.feature_groups = {}  # feature_hash -> [server_id, ...]
        
        # Store task handlers for collaborative processing
        self.task_handlers = {}  # task_type -> handler_function
        
        # Statistics
        self.stats = {
            "servers_discovered": 0,
            "announcements_sent": 0,
            "announcements_received": 0,
            "tasks_dispatched": 0,
            "tasks_received": 0,
            "tasks_processed": 0,
            "discovery_requests": 0,
            "health_checks": 0,
            "start_time": time.time()
        }
        
        # Determine if websocket discovery is available (always false in mock)
        self.has_websocket = False
        
        # Determine if libp2p discovery is available (always false in mock)
        self.has_libp2p = False
        
        logger.info(f"Mock MCP Discovery Model initialized with ID {self.server_id} and role {self.role}")
        logger.info(f"Features: {', '.join(self.feature_set.features)}")

    def _detect_available_features(self) -> List[str]:
        """Detect available features for the mock."""
        # In the mock, we include basic features
        return [
            MCPServerCapabilities.IPFS_DAEMON,
            MCPServerCapabilities.PEER_WEBSOCKET,
            MCPServerCapabilities.WEBRTC
        ]
    
    def _create_local_server_info(self) -> MCPServerInfo:
        """Create server info for this local server."""
        # Create basic server info with minimal data
        return MCPServerInfo(
            server_id=self.server_id,
            role=self.role,
            feature_set=self.feature_set,
            api_endpoint="http://localhost:8000/api",  # Simulated endpoint
            websocket_endpoint="ws://localhost:8000/ws",  # Simulated endpoint
            metadata={
                "version": "1.0.0",
                "uptime": 0,
                "resources": self.resources
            }
        )
    
    def update_server_info(self, **kwargs) -> Dict[str, Any]:
        """Update local server info with new values."""
        # Update server info attributes
        for key, value in kwargs.items():
            if hasattr(self.server_info, key):
                setattr(self.server_info, key, value)
            elif key == "features":
                # Special case for updating features
                self.feature_set = MCPFeatureSet(value)
                self.server_info.feature_set = self.feature_set
            elif key == "metadata":
                # Update metadata dict
                self.server_info.metadata.update(value)
        
        # Update uptime in metadata
        self.server_info.metadata["uptime"] = time.time() - self.stats["start_time"]
        
        # Return updated server info
        return self.get_server_info(self.server_id)
    
    def announce_server(self) -> Dict[str, Any]:
        """Simulate announcing this server to the network."""
        # Prepare result
        result = {
            "success": True,
            "operation": "announce_server",
            "timestamp": time.time(),
            "announcement_channels": ["mock"]
        }
        
        # Update statistics
        self.stats["announcements_sent"] += 1
        
        return result
    
    def discover_servers(self, 
                         methods: Optional[List[str]] = None, 
                         compatible_only: bool = True,
                         feature_requirements: Optional[List[str]] = None) -> Dict[str, Any]:
        """Discover MCP servers (return already known servers in the mock)."""
        # In mock, we just return already known servers
        result = {
            "success": True,
            "operation": "discover_servers",
            "timestamp": time.time(),
            "methods": methods or ["manual"],
            "servers": []
        }
        
        # Filter known servers based on criteria
        with self.server_lock:
            filtered_servers = []
            
            for server_id, server_info in self.known_servers.items():
                # Skip our own server
                if server_id == self.server_id:
                    continue
                
                # Filter by compatibility if requested
                if compatible_only and not self.feature_set.is_compatible_with(server_info.feature_set):
                    continue
                
                # Filter by feature requirements if specified
                if feature_requirements and not server_info.feature_set.can_handle_request(feature_requirements):
                    continue
                
                # Add to filtered list
                filtered_servers.append(server_info.to_dict())
        
        # Update result
        result["servers"] = filtered_servers
        result["server_count"] = len(filtered_servers)
        result["new_servers"] = 0
        
        # Update statistics
        self.stats["discovery_requests"] += 1
        
        return result
    
    def register_server(self, server_info_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Register a server from discovery."""
        # Prepare result
        result = {
            "success": False,
            "operation": "register_server",
            "timestamp": time.time()
        }
        
        try:
            # Parse server info
            server_info = MCPServerInfo.from_dict(server_info_dict)
            
            # Skip our own server
            if server_info.server_id == self.server_id:
                result["success"] = True
                result["message"] = "Skipped registering own server"
                return result
            
            # Add or update server in known servers
            with self.server_lock:
                is_new = server_info.server_id not in self.known_servers
                
                if is_new:
                    # Track as new discovery
                    self.stats["servers_discovered"] += 1
                
                # Update or add server info
                self.known_servers[server_info.server_id] = server_info
                
                # Update feature hash groups
                feature_hash = server_info.feature_set.feature_hash
                if feature_hash not in self.feature_groups:
                    self.feature_groups[feature_hash] = []
                if server_info.server_id not in self.feature_groups[feature_hash]:
                    self.feature_groups[feature_hash].append(server_info.server_id)
            
            # Return success
            result["success"] = True
            result["server_id"] = server_info.server_id
            result["is_new"] = is_new
            
            # Log discovery
            if is_new:
                logger.info(f"Discovered new MCP server: {server_info.server_id} (role: {server_info.role})")
            else:
                logger.debug(f"Updated existing MCP server: {server_info.server_id}")
                
        except Exception as e:
            logger.error(f"Error registering server: {e}")
            result["error"] = str(e)
        
        return result
    
    def get_server_info(self, server_id: str) -> Dict[str, Any]:
        """Get information about a specific server."""
        # Prepare result
        result = {
            "success": False,
            "operation": "get_server_info",
            "timestamp": time.time(),
            "server_id": server_id
        }
        
        # Check if this is our own server
        if server_id == self.server_id:
            # Update our server info first
            self.update_server_info()
            result["success"] = True
            result["server_info"] = self.server_info.to_dict()
            result["is_local"] = True
            return result
        
        # Look for server in known servers
        with self.server_lock:
            if server_id in self.known_servers:
                result["success"] = True
                result["server_info"] = self.known_servers[server_id].to_dict()
                result["is_local"] = False
                return result
        
        # Server not found
        result["error"] = f"Server not found: {server_id}"
        return result
    
    def get_compatible_servers(self, feature_requirements: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all servers with compatible feature sets."""
        # Prepare result
        result = {
            "success": True,
            "operation": "get_compatible_servers",
            "timestamp": time.time(),
            "servers": []
        }
        
        # Get compatible servers
        with self.server_lock:
            # First filter by feature hash for quick compatibility check
            compatible_server_ids = []
            
            # If we have specific feature requirements, we need to check each server
            if feature_requirements:
                for server_id, server_info in self.known_servers.items():
                    # Skip our own server
                    if server_id == self.server_id:
                        continue
                        
                    # Check if server can handle required features
                    if server_info.feature_set.can_handle_request(feature_requirements):
                        compatible_server_ids.append(server_id)
            else:
                # Without specific requirements, use feature hash groups
                our_feature_hash = self.feature_set.feature_hash
                for feature_hash, server_ids in self.feature_groups.items():
                    # Version compatibility check (simplified)
                    for server_id in server_ids:
                        # Skip our own server
                        if server_id == self.server_id:
                            continue
                        
                        if server_id in self.known_servers:
                            server_info = self.known_servers[server_id]
                            if self.feature_set.is_compatible_with(server_info.feature_set):
                                compatible_server_ids.append(server_id)
            
            # Get server info for compatible servers
            compatible_servers = []
            for server_id in compatible_server_ids:
                if server_id in self.known_servers:
                    compatible_servers.append(self.known_servers[server_id].to_dict())
        
        # Update result
        result["servers"] = compatible_servers
        result["server_count"] = len(compatible_servers)
        
        return result
    
    def check_server_health(self, server_id: str) -> Dict[str, Any]:
        """Check health status of a specific server."""
        # Prepare result
        result = {
            "success": False,
            "operation": "check_server_health",
            "timestamp": time.time(),
            "server_id": server_id
        }
        
        # Update statistics
        self.stats["health_checks"] += 1
        
        # Check if this is our own server
        if server_id == self.server_id:
            # For local server, we can immediately return healthy
            result["success"] = True
            result["healthy"] = True
            result["is_local"] = True
            return result
        
        # Look for server in known servers
        with self.server_lock:
            if server_id not in self.known_servers:
                result["error"] = f"Server not found: {server_id}"
                return result
            
            server_info = self.known_servers[server_id]
        
        # In mock, always report healthy if recently seen
        time_since_last_seen = time.time() - server_info.last_seen
        is_healthy = time_since_last_seen < 300  # 5 minutes
        
        # Update server health info
        with self.server_lock:
            if server_id in self.known_servers:
                self.known_servers[server_id].health_status = {
                    "healthy": is_healthy,
                    "last_checked": time.time()
                }
        
        # Set result
        result["success"] = True
        result["healthy"] = is_healthy
        result["health_source"] = "mock"
        
        return result
    
    def remove_server(self, server_id: str) -> Dict[str, Any]:
        """Remove a server from known servers."""
        # Prepare result
        result = {
            "success": False,
            "operation": "remove_server",
            "timestamp": time.time(),
            "server_id": server_id
        }
        
        # Can't remove our own server
        if server_id == self.server_id:
            result["error"] = "Cannot remove local server"
            return result
        
        # Remove server from known servers
        with self.server_lock:
            if server_id in self.known_servers:
                # Get server info before removing
                server_info = self.known_servers[server_id]
                
                # Remove from known servers
                del self.known_servers[server_id]
                
                # Remove from feature groups
                feature_hash = server_info.feature_set.feature_hash
                if feature_hash in self.feature_groups and server_id in self.feature_groups[feature_hash]:
                    self.feature_groups[feature_hash].remove(server_id)
                
                result["success"] = True
            else:
                result["error"] = f"Server not found: {server_id}"
        
        return result
    
    def clean_stale_servers(self, max_age_seconds: int = 3600) -> Dict[str, Any]:
        """Remove servers that haven't been seen for a specified time."""
        # Prepare result
        result = {
            "success": True,
            "operation": "clean_stale_servers",
            "timestamp": time.time(),
            "max_age_seconds": max_age_seconds,
            "removed_servers": []
        }
        
        # Calculate cutoff time
        cutoff_time = time.time() - max_age_seconds
        
        # Find and remove stale servers
        with self.server_lock:
            for server_id, server_info in list(self.known_servers.items()):
                # Skip our own server
                if server_id == self.server_id:
                    continue
                
                # Check if server is stale
                if server_info.last_seen < cutoff_time:
                    # Get feature hash before removing
                    feature_hash = server_info.feature_set.feature_hash
                    
                    # Remove server
                    del self.known_servers[server_id]
                    
                    # Remove from feature groups
                    if feature_hash in self.feature_groups and server_id in self.feature_groups[feature_hash]:
                        self.feature_groups[feature_hash].remove(server_id)
                    
                    # Add to removed list
                    result["removed_servers"].append(server_id)
        
        # Update result
        result["removed_count"] = len(result["removed_servers"])
        
        return result
    
    def register_task_handler(self, task_type: str, handler: Callable) -> Dict[str, Any]:
        """Register a handler for a specific task type."""
        # Prepare result
        result = {
            "success": True,
            "operation": "register_task_handler",
            "timestamp": time.time(),
            "task_type": task_type
        }
        
        # Register handler
        self.task_handlers[task_type] = handler
        
        return result
    
    def dispatch_task(self, 
                    task_type: str, 
                    task_data: Any, 
                    required_features: Optional[List[str]] = None,
                    preferred_server_id: Optional[str] = None) -> Dict[str, Any]:
        """Dispatch a task to a compatible server."""
        # Prepare result
        result = {
            "success": False,
            "operation": "dispatch_task",
            "timestamp": time.time(),
            "task_type": task_type
        }
        
        # Check if we can handle the task locally
        can_handle_locally = task_type in self.task_handlers
        
        # If specific features are required, check if we have them
        if required_features and not self.feature_set.can_handle_request(required_features):
            can_handle_locally = False
        
        # If we can handle locally, do it
        if can_handle_locally and (preferred_server_id is None or preferred_server_id == self.server_id):
            try:
                # Call task handler
                handler = self.task_handlers[task_type]
                task_result = handler(task_data)
                
                # Update statistics
                self.stats["tasks_processed"] += 1
                
                # Update result
                result["success"] = True
                result["server_id"] = self.server_id
                result["task_result"] = task_result
                result["processed_locally"] = True
                
                return result
            except Exception as e:
                logger.error(f"Error processing task locally: {e}")
                # Fall through to remote processing
        
        # Find a compatible server to handle the task
        target_server_id = None
        target_server = None
        
        # Use preferred server if specified
        if preferred_server_id and preferred_server_id != self.server_id:
            with self.server_lock:
                if preferred_server_id in self.known_servers:
                    server_info = self.known_servers[preferred_server_id]
                    
                    # Check if server has required features
                    if not required_features or server_info.feature_set.can_handle_request(required_features):
                        # Check if server is healthy
                        if server_info.health_status.get("healthy", False):
                            target_server_id = preferred_server_id
                            target_server = server_info
        
        # Find another compatible server if preferred server not available
        if target_server_id is None:
            compatible_servers = self.get_compatible_servers(feature_requirements=required_features)
            
            if compatible_servers.get("success", False) and compatible_servers.get("server_count", 0) > 0:
                # Pick the first compatible server
                server_dict = compatible_servers["servers"][0]
                target_server_id = server_dict["server_id"]
                
                with self.server_lock:
                    if target_server_id in self.known_servers:
                        target_server = self.known_servers[target_server_id]
        
        # If we didn't find a suitable server, return error
        if target_server_id is None or target_server is None:
            result["error"] = "No compatible server found for task"
            return result
        
        # In mock, simulate successful dispatch
        self.stats["tasks_dispatched"] += 1
        
        # Create a simulated task result
        task_result = {
            "success": True,
            "message": f"Task {task_type} processed by {target_server_id}",
            "timestamp": time.time()
        }
        
        # Update result
        result["success"] = True
        result["server_id"] = target_server_id
        result["task_result"] = task_result
        result["processed_locally"] = False
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the discovery model."""
        # Prepare result
        result = {
            "success": True,
            "operation": "get_stats",
            "timestamp": time.time()
        }
        
        # Update uptime
        uptime = time.time() - self.stats["start_time"]
        
        # Count servers by role
        role_counts = {}
        with self.server_lock:
            for server_info in self.known_servers.values():
                role = server_info.role
                if role not in role_counts:
                    role_counts[role] = 0
                role_counts[role] += 1
        
        # Add stats to result
        result["stats"] = {
            "uptime": uptime,
            "servers_discovered": self.stats["servers_discovered"],
            "known_servers": len(self.known_servers),
            "servers_by_role": role_counts,
            "announcements_sent": self.stats["announcements_sent"],
            "announcements_received": self.stats["announcements_received"],
            "tasks_dispatched": self.stats["tasks_dispatched"],
            "tasks_received": self.stats["tasks_received"],
            "tasks_processed": self.stats["tasks_processed"],
            "discovery_requests": self.stats["discovery_requests"],
            "health_checks": self.stats["health_checks"]
        }
        
        return result
    
    def reset(self) -> Dict[str, Any]:
        """Reset the discovery model, clearing all state."""
        # Prepare result
        result = {
            "success": True,
            "operation": "reset",
            "timestamp": time.time()
        }
        
        # Save start time
        start_time = self.stats["start_time"]
        
        # Clear known servers
        with self.server_lock:
            self.known_servers = {}
            self.feature_groups = {}
        
        # Reset statistics
        self.stats = {
            "servers_discovered": 0,
            "announcements_sent": 0,
            "announcements_received": 0,
            "tasks_dispatched": 0,
            "tasks_received": 0,
            "tasks_processed": 0,
            "discovery_requests": 0,
            "health_checks": 0,
            "start_time": start_time  # Preserve start time
        }
        
        return result