"""
MCP API endpoints for IPFS Cluster configuration management.
Provides access to cluster service and cluster follow configuration functions.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List

# Import cluster managers
try:
    from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterDaemonManager, IPFSClusterConfig
    from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow
except ImportError as e:
    logging.warning(f"Failed to import cluster modules: {e}")
    # Create stub classes
    class IPFSClusterDaemonManager:
        def __init__(self, *args, **kwargs):
            pass
    class IPFSClusterConfig:
        def __init__(self, *args, **kwargs):
            pass
    class ipfs_cluster_follow:
        def __init__(self, *args, **kwargs):
            pass

logger = logging.getLogger(__name__)


class ClusterConfigurationAPI:
    """MCP API for IPFS Cluster configuration management."""
    
    def __init__(self):
        """Initialize cluster configuration API."""
        self.cluster_manager = None
        self.follow_manager = None
    
    def get_cluster_manager(self, cluster_path: Optional[str] = None) -> IPFSClusterDaemonManager:
        """Get cluster daemon manager instance.
        
        Args:
            cluster_path: Optional path to cluster configuration
            
        Returns:
            Cluster daemon manager instance
        """
        if not self.cluster_manager or cluster_path:
            config = IPFSClusterConfig(cluster_path) if cluster_path else None
            self.cluster_manager = IPFSClusterDaemonManager(config)
        return self.cluster_manager
    
    def get_follow_manager(self, metadata: Optional[Dict[str, Any]] = None) -> ipfs_cluster_follow:
        """Get cluster follow manager instance.
        
        Args:
            metadata: Optional metadata for follow manager
            
        Returns:
            Cluster follow manager instance
        """
        if not self.follow_manager or metadata:
            self.follow_manager = ipfs_cluster_follow(metadata=metadata or {})
        return self.follow_manager
    
    async def cluster_service_config_create(self, cluster_path: Optional[str] = None, 
                                           overwrite: bool = False, 
                                           **custom_settings) -> Dict[str, Any]:
        """Create IPFS Cluster service configuration.
        
        Args:
            cluster_path: Path to cluster configuration directory
            overwrite: Whether to overwrite existing configuration
            **custom_settings: Custom configuration settings
            
        Returns:
            Configuration creation results
        """
        try:
            manager = self.get_cluster_manager(cluster_path)
            
            # Use the config object to create configuration
            return manager.config.config_create(overwrite=overwrite, **custom_settings)
            
        except Exception as e:
            logger.error(f"Error creating cluster service config: {e}")
            return {
                "success": False,
                "errors": [f"Configuration creation failed: {str(e)}"]
            }
    
    async def cluster_service_config_get(self, cluster_path: Optional[str] = None) -> Dict[str, Any]:
        """Get IPFS Cluster service configuration.
        
        Args:
            cluster_path: Path to cluster configuration directory
            
        Returns:
            Current configuration
        """
        try:
            manager = self.get_cluster_manager(cluster_path)
            
            # Use the config object to get configuration
            return manager.config.config_get()
            
        except Exception as e:
            logger.error(f"Error getting cluster service config: {e}")
            return {
                "success": False,
                "errors": [f"Configuration retrieval failed: {str(e)}"]
            }
    
    async def cluster_service_config_set(self, config_updates: Dict[str, Any], 
                                        cluster_path: Optional[str] = None) -> Dict[str, Any]:
        """Update IPFS Cluster service configuration.
        
        Args:
            config_updates: Configuration updates to apply
            cluster_path: Path to cluster configuration directory
            
        Returns:
            Configuration update results
        """
        try:
            manager = self.get_cluster_manager(cluster_path)
            
            # Use the config object to set configuration
            return manager.config.config_set(config_updates)
            
        except Exception as e:
            logger.error(f"Error setting cluster service config: {e}")
            return {
                "success": False,
                "errors": [f"Configuration update failed: {str(e)}"]
            }
    
    async def cluster_follow_config_create(self, cluster_name: str, 
                                          bootstrap_peer: Optional[str] = None,
                                          cluster_path: Optional[str] = None,
                                          overwrite: bool = False,
                                          **custom_settings) -> Dict[str, Any]:
        """Create IPFS Cluster Follow configuration.
        
        Args:
            cluster_name: Name of the cluster to follow
            bootstrap_peer: Bootstrap peer multiaddress
            cluster_path: Path to cluster follow configuration directory
            overwrite: Whether to overwrite existing configuration
            **custom_settings: Custom configuration settings
            
        Returns:
            Configuration creation results
        """
        try:
            metadata = {
                "cluster_name": cluster_name,
                "role": "leecher"
            }
            
            if cluster_path:
                metadata["ipfs_cluster_path"] = cluster_path
                
            manager = self.get_follow_manager(metadata)
            
            return manager.config_create(
                cluster_name=cluster_name,
                bootstrap_peer=bootstrap_peer,
                overwrite=overwrite,
                **custom_settings
            )
            
        except Exception as e:
            logger.error(f"Error creating cluster follow config: {e}")
            return {
                "success": False,
                "errors": [f"Follow configuration creation failed: {str(e)}"]
            }
    
    async def cluster_follow_config_get(self, cluster_name: str,
                                       cluster_path: Optional[str] = None) -> Dict[str, Any]:
        """Get IPFS Cluster Follow configuration.
        
        Args:
            cluster_name: Name of the cluster
            cluster_path: Path to cluster follow configuration directory
            
        Returns:
            Current configuration
        """
        try:
            metadata = {
                "cluster_name": cluster_name,
                "role": "leecher"
            }
            
            if cluster_path:
                metadata["ipfs_cluster_path"] = cluster_path
                
            manager = self.get_follow_manager(metadata)
            
            return manager.config_get()
            
        except Exception as e:
            logger.error(f"Error getting cluster follow config: {e}")
            return {
                "success": False,
                "errors": [f"Follow configuration retrieval failed: {str(e)}"]
            }
    
    async def cluster_follow_config_set(self, cluster_name: str,
                                       config_updates: Dict[str, Any],
                                       cluster_path: Optional[str] = None) -> Dict[str, Any]:
        """Update IPFS Cluster Follow configuration.
        
        Args:
            cluster_name: Name of the cluster
            config_updates: Configuration updates to apply
            cluster_path: Path to cluster follow configuration directory
            
        Returns:
            Configuration update results
        """
        try:
            metadata = {
                "cluster_name": cluster_name,
                "role": "leecher"
            }
            
            if cluster_path:
                metadata["ipfs_cluster_path"] = cluster_path
                
            manager = self.get_follow_manager(metadata)
            
            return manager.config_set(config_updates)
            
        except Exception as e:
            logger.error(f"Error setting cluster follow config: {e}")
            return {
                "success": False,
                "errors": [f"Follow configuration update failed: {str(e)}"]
            }
    
    async def cluster_service_status_via_api(self, cluster_path: Optional[str] = None) -> Dict[str, Any]:
        """Get cluster service status via REST API.
        
        Args:
            cluster_path: Path to cluster configuration directory
            
        Returns:
            Cluster service status
        """
        try:
            manager = self.get_cluster_manager(cluster_path)
            return await manager.get_cluster_status_via_api()
            
        except Exception as e:
            logger.error(f"Error getting cluster service status: {e}")
            return {
                "success": False,
                "errors": [f"Status check failed: {str(e)}"]
            }
    
    async def cluster_follow_status_via_api(self, cluster_name: str,
                                           cluster_path: Optional[str] = None) -> Dict[str, Any]:
        """Get cluster follow status via REST API.
        
        Args:
            cluster_name: Name of the cluster
            cluster_path: Path to cluster follow configuration directory
            
        Returns:
            Cluster follow status
        """
        try:
            metadata = {
                "cluster_name": cluster_name,
                "role": "leecher"
            }
            
            if cluster_path:
                metadata["ipfs_cluster_path"] = cluster_path
                
            manager = self.get_follow_manager(metadata)
            return await manager.get_follow_status_via_api()
            
        except Exception as e:
            logger.error(f"Error getting cluster follow status: {e}")
            return {
                "success": False,
                "errors": [f"Follow status check failed: {str(e)}"]
            }
    
    async def connect_to_networked_cluster(self, remote_host: str, remote_port: int = 9094,
                                          auth: Optional[Dict[str, str]] = None,
                                          cluster_path: Optional[str] = None) -> Dict[str, Any]:
        """Connect to a remote networked cluster.
        
        Args:
            remote_host: Remote cluster host
            remote_port: Remote cluster API port
            auth: Authentication credentials
            cluster_path: Path to local cluster configuration
            
        Returns:
            Connection results
        """
        try:
            manager = self.get_cluster_manager(cluster_path)
            return await manager.connect_to_networked_cluster(remote_host, remote_port, auth)
            
        except Exception as e:
            logger.error(f"Error connecting to networked cluster: {e}")
            return {
                "success": False,
                "errors": [f"Network connection failed: {str(e)}"]
            }
    
    async def connect_follow_to_leader(self, cluster_name: str, leader_host: str, 
                                      leader_port: int = 9094,
                                      auth: Optional[Dict[str, str]] = None,
                                      cluster_path: Optional[str] = None) -> Dict[str, Any]:
        """Connect cluster follow to a cluster leader.
        
        Args:
            cluster_name: Name of the cluster
            leader_host: Cluster leader host
            leader_port: Cluster leader API port
            auth: Authentication credentials
            cluster_path: Path to cluster follow configuration
            
        Returns:
            Connection results
        """
        try:
            metadata = {
                "cluster_name": cluster_name,
                "role": "leecher"
            }
            
            if cluster_path:
                metadata["ipfs_cluster_path"] = cluster_path
                
            manager = self.get_follow_manager(metadata)
            return await manager.connect_to_cluster_leader(leader_host, leader_port, auth)
            
        except Exception as e:
            logger.error(f"Error connecting follow to leader: {e}")
            return {
                "success": False,
                "errors": [f"Leader connection failed: {str(e)}"]
            }


# Global API instance
cluster_config_api = ClusterConfigurationAPI()


# MCP tool definitions
CLUSTER_CONFIG_TOOLS = [
    {
        "name": "cluster_service_config_create",
        "description": "Create IPFS Cluster service configuration with service.json and identity.json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster configuration directory (optional)"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite existing configuration",
                    "default": False
                },
                "custom_settings": {
                    "type": "object",
                    "description": "Custom configuration settings to apply",
                    "default": {}
                }
            }
        }
    },
    {
        "name": "cluster_service_config_get",
        "description": "Get current IPFS Cluster service configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster configuration directory (optional)"
                }
            }
        }
    },
    {
        "name": "cluster_service_config_set",
        "description": "Update IPFS Cluster service configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "config_updates": {
                    "type": "object",
                    "description": "Configuration updates to apply",
                    "required": True
                },
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster configuration directory (optional)"
                }
            },
            "required": ["config_updates"]
        }
    },
    {
        "name": "cluster_follow_config_create",
        "description": "Create IPFS Cluster Follow configuration with service.json and identity.json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_name": {
                    "type": "string",
                    "description": "Name of the cluster to follow",
                    "required": True
                },
                "bootstrap_peer": {
                    "type": "string",
                    "description": "Bootstrap peer multiaddress (optional)"
                },
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster follow configuration directory (optional)"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite existing configuration",
                    "default": False
                },
                "custom_settings": {
                    "type": "object",
                    "description": "Custom configuration settings to apply",
                    "default": {}
                }
            },
            "required": ["cluster_name"]
        }
    },
    {
        "name": "cluster_follow_config_get",
        "description": "Get current IPFS Cluster Follow configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_name": {
                    "type": "string",
                    "description": "Name of the cluster",
                    "required": True
                },
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster follow configuration directory (optional)"
                }
            },
            "required": ["cluster_name"]
        }
    },
    {
        "name": "cluster_follow_config_set",
        "description": "Update IPFS Cluster Follow configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_name": {
                    "type": "string",
                    "description": "Name of the cluster",
                    "required": True
                },
                "config_updates": {
                    "type": "object",
                    "description": "Configuration updates to apply",
                    "required": True
                },
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster follow configuration directory (optional)"
                }
            },
            "required": ["cluster_name", "config_updates"]
        }
    },
    {
        "name": "cluster_service_status_via_api",
        "description": "Get IPFS Cluster service status via REST API",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster configuration directory (optional)"
                }
            }
        }
    },
    {
        "name": "cluster_follow_status_via_api",
        "description": "Get IPFS Cluster Follow status via REST API",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_name": {
                    "type": "string",
                    "description": "Name of the cluster",
                    "required": True
                },
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster follow configuration directory (optional)"
                }
            },
            "required": ["cluster_name"]
        }
    },
    {
        "name": "connect_to_networked_cluster",
        "description": "Connect to a remote networked IPFS Cluster",
        "inputSchema": {
            "type": "object",
            "properties": {
                "remote_host": {
                    "type": "string",
                    "description": "Remote cluster host",
                    "required": True
                },
                "remote_port": {
                    "type": "integer",
                    "description": "Remote cluster API port",
                    "default": 9094
                },
                "auth": {
                    "type": "object",
                    "description": "Authentication credentials (username/password)",
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string"}
                    }
                },
                "cluster_path": {
                    "type": "string",
                    "description": "Path to local cluster configuration directory (optional)"
                }
            },
            "required": ["remote_host"]
        }
    },
    {
        "name": "connect_follow_to_leader",
        "description": "Connect IPFS Cluster Follow to a cluster leader",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_name": {
                    "type": "string",
                    "description": "Name of the cluster",
                    "required": True
                },
                "leader_host": {
                    "type": "string",
                    "description": "Cluster leader host",
                    "required": True
                },
                "leader_port": {
                    "type": "integer",
                    "description": "Cluster leader API port",
                    "default": 9094
                },
                "auth": {
                    "type": "object",
                    "description": "Authentication credentials (username/password)",
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string"}
                    }
                },
                "cluster_path": {
                    "type": "string",
                    "description": "Path to cluster follow configuration directory (optional)"
                }
            },
            "required": ["cluster_name", "leader_host"]
        }
    }
]


# MCP tool handler
async def handle_cluster_config_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle cluster configuration tool calls.
    
    Args:
        name: Tool name
        arguments: Tool arguments
        
    Returns:
        Tool execution result
    """
    try:
        if name == "cluster_service_config_create":
            return await cluster_config_api.cluster_service_config_create(**arguments)
        elif name == "cluster_service_config_get":
            return await cluster_config_api.cluster_service_config_get(**arguments)
        elif name == "cluster_service_config_set":
            return await cluster_config_api.cluster_service_config_set(**arguments)
        elif name == "cluster_follow_config_create":
            return await cluster_config_api.cluster_follow_config_create(**arguments)
        elif name == "cluster_follow_config_get":
            return await cluster_config_api.cluster_follow_config_get(**arguments)
        elif name == "cluster_follow_config_set":
            return await cluster_config_api.cluster_follow_config_set(**arguments)
        elif name == "cluster_service_status_via_api":
            return await cluster_config_api.cluster_service_status_via_api(**arguments)
        elif name == "cluster_follow_status_via_api":
            return await cluster_config_api.cluster_follow_status_via_api(**arguments)
        elif name == "connect_to_networked_cluster":
            return await cluster_config_api.connect_to_networked_cluster(**arguments)
        elif name == "connect_follow_to_leader":
            return await cluster_config_api.connect_follow_to_leader(**arguments)
        else:
            return {
                "success": False,
                "errors": [f"Unknown tool: {name}"]
            }
            
    except Exception as e:
        logger.error(f"Error handling cluster config tool {name}: {e}")
        return {
            "success": False,
            "errors": [f"Tool execution failed: {str(e)}"]
        }
