"""
Real backend clients for IPFS Kit backends.

This module provides actual implementations (not mocked) for connecting to
and monitoring various IPFS Kit storage backends.
"""

import logging
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BackendClient(ABC):
    """Abstract base class for backend clients."""
    
    def __init__(self, name: str, endpoint: str, **kwargs):
        self.name = name
        self.endpoint = endpoint
        self.config = kwargs
        self.session = None
        self.log_manager = None  # Will be set by health monitor
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def set_log_manager(self, log_manager):
        """Set the log manager for this backend."""
        self.log_manager = log_manager
    
    def log(self, level: str, message: str, extra_data: Optional[Dict] = None):
        """Log a message for this backend."""
        if self.log_manager:
            self.log_manager.add_log_entry(self.name, level, message, extra_data)
        else:
            getattr(logger, level.lower(), logger.info)(f"[{self.name}] {message}")
    
    async def get_logs(self, limit: int = 100) -> List[str]:
        """Get recent logs for this backend."""
        if self.log_manager:
            log_entries = self.log_manager.get_backend_logs(self.name, limit)
            return [f"{entry['timestamp']} [{entry['level']}] {entry['message']}" for entry in log_entries]
        return [f"No log manager configured for {self.name}"]
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of this backend."""
        pass
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed status information."""
        pass
    
    @abstractmethod
    async def get_config(self) -> Dict[str, Any]:
        """Get backend configuration."""
        pass
    
    @abstractmethod
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set backend configuration."""
        pass


class IPFSClient(BackendClient):
    """Client for IPFS backend."""
    
    def __init__(self, endpoint: str = "http://127.0.0.1:5001", **kwargs):
        super().__init__("IPFS", endpoint, **kwargs)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check IPFS health."""
        self.log("INFO", f"Starting health check for {self.endpoint}")
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            async with self.session.get(f"{self.endpoint}/api/v0/id", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    self.log("INFO", f"Health check successful - Peer ID: {data.get('ID', 'unknown')}")
                    return {
                        "status": "healthy",
                        "endpoint": self.endpoint,
                        "peer_id": data.get("ID", "unknown"),
                        "version": data.get("AgentVersion", "unknown"),
                        "public_key": data.get("PublicKey", "unknown")
                    }
                else:
                    error_msg = f"Health check failed - HTTP {response.status}"
                    self.log("WARNING", error_msg)
                    return {
                        "status": "unhealthy",
                        "endpoint": self.endpoint,
                        "error": f"HTTP {response.status}"
                    }
        except asyncio.TimeoutError:
            error_msg = "Health check failed - Connection timeout"
            self.log("ERROR", error_msg)
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": "Connection timeout"
            }
        except Exception as e:
            error_msg = f"Health check failed - {str(e)}"
            self.log("ERROR", error_msg)
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed IPFS status."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Get basic info
            async with self.session.get(f"{self.endpoint}/api/v0/id") as response:
                if response.status != 200:
                    return {"error": f"Failed to get ID: HTTP {response.status}"}
                id_data = await response.json()
            
            # Get repo stats
            async with self.session.get(f"{self.endpoint}/api/v0/repo/stat") as response:
                if response.status == 200:
                    repo_data = await response.json()
                else:
                    repo_data = {"error": f"HTTP {response.status}"}
            
            # Get swarm peers
            async with self.session.get(f"{self.endpoint}/api/v0/swarm/peers") as response:
                if response.status == 200:
                    peers_data = await response.json()
                    peer_count = len(peers_data.get("Peers", []))
                else:
                    peer_count = 0
            
            return {
                "peer_id": id_data.get("ID", "unknown"),
                "version": id_data.get("AgentVersion", "unknown"),
                "public_key": id_data.get("PublicKey", "unknown"),
                "addresses": id_data.get("Addresses", []),
                "repo_size": repo_data.get("RepoSize", 0),
                "repo_objects": repo_data.get("NumObjects", 0),
                "peer_count": peer_count,
                "protocols": id_data.get("Protocols", [])
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_config(self) -> Dict[str, Any]:
        """Get IPFS configuration."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            async with self.session.get(f"{self.endpoint}/api/v0/config/show") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set IPFS configuration."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            # IPFS config setting requires specific key-value pairs
            # This is a simplified implementation
            return False  # Not implemented for safety
        except Exception as e:
            logger.error(f"Failed to set IPFS config: {e}")
            return False


class IPFSClusterClient(BackendClient):
    """Client for IPFS Cluster backend."""
    
    def __init__(self, endpoint: str = "http://127.0.0.1:9094", **kwargs):
        super().__init__("IPFS Cluster", endpoint, **kwargs)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check IPFS Cluster health."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            async with self.session.get(f"{self.endpoint}/id", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "healthy",
                        "endpoint": self.endpoint,
                        "id": data.get("id", "unknown"),
                        "version": data.get("version", "unknown"),
                        "consensus": data.get("consensus", "unknown")
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "endpoint": self.endpoint,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed IPFS Cluster status."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Get cluster info
            async with self.session.get(f"{self.endpoint}/id") as response:
                if response.status == 200:
                    id_data = await response.json()
                else:
                    return {"error": f"HTTP {response.status}"}
            
            # Get peers
            async with self.session.get(f"{self.endpoint}/peers") as response:
                if response.status == 200:
                    peers_data = await response.json()
                else:
                    peers_data = []
            
            # Get pins
            async with self.session.get(f"{self.endpoint}/pins") as response:
                if response.status == 200:
                    pins_data = await response.json()
                else:
                    pins_data = []
            
            return {
                "cluster_id": id_data.get("id", "unknown"),
                "version": id_data.get("version", "unknown"),
                "consensus": id_data.get("consensus", "unknown"),
                "peer_count": len(peers_data),
                "pins_count": len(pins_data),
                "peers": peers_data,
                "addresses": id_data.get("addresses", [])
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_config(self) -> Dict[str, Any]:
        """Get IPFS Cluster configuration."""
        # Configuration endpoint may not be available in all versions
        return {"message": "Config endpoint not available"}
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set IPFS Cluster configuration."""
        return False  # Not implemented for safety


class LotusClient(BackendClient):
    """Client for Lotus backend."""
    
    def __init__(self, endpoint: str = "http://127.0.0.1:1234/rpc/v0", **kwargs):
        super().__init__("Lotus", endpoint, **kwargs)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Lotus health."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            payload = {
                "jsonrpc": "2.0",
                "method": "Filecoin.Version",
                "params": [],
                "id": 1
            }
            
            async with self.session.post(
                self.endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data:
                        return {
                            "status": "healthy",
                            "endpoint": self.endpoint,
                            "version": data["result"].get("Version", "unknown"),
                            "api_version": data["result"].get("APIVersion", "unknown")
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "endpoint": self.endpoint,
                            "error": data.get("error", "Unknown error")
                        }
                else:
                    return {
                        "status": "unhealthy",
                        "endpoint": self.endpoint,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed Lotus status."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Get version info
            version_payload = {
                "jsonrpc": "2.0",
                "method": "Filecoin.Version",
                "params": [],
                "id": 1
            }
            
            async with self.session.post(self.endpoint, json=version_payload) as response:
                if response.status == 200:
                    version_data = await response.json()
                    version_info = version_data.get("result", {})
                else:
                    version_info = {"error": f"HTTP {response.status}"}
            
            # Get sync status
            sync_payload = {
                "jsonrpc": "2.0",
                "method": "Filecoin.SyncState",
                "params": [],
                "id": 2
            }
            
            async with self.session.post(self.endpoint, json=sync_payload) as response:
                if response.status == 200:
                    sync_data = await response.json()
                    sync_info = sync_data.get("result", {})
                else:
                    sync_info = {"error": f"HTTP {response.status}"}
            
            return {
                "version": version_info.get("Version", "unknown"),
                "api_version": version_info.get("APIVersion", "unknown"),
                "sync_state": sync_info,
                "network": "calibration",  # Default for most setups
                "status": "connected" if version_info.get("Version") else "disconnected"
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_config(self) -> Dict[str, Any]:
        """Get Lotus configuration."""
        return {"message": "Lotus config via RPC not typically exposed"}
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set Lotus configuration."""
        return False  # Not implemented for safety


class LassieClient(BackendClient):
    """Client for Lassie Kit backend."""
    
    def __init__(self, binary_path: str = "lassie", **kwargs):
        # Lassie doesn't have a persistent endpoint, it's a CLI tool
        super().__init__("Lassie", "cli", binary_path=binary_path, **kwargs)
        self.binary_path = binary_path
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if Lassie binary is available and working."""
        import subprocess
        
        try:
            # Test if lassie binary is available
            result = subprocess.run(
                [self.binary_path, "version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                version_info = result.stdout.strip()
                self.log("INFO", f"Lassie binary check passed: {version_info}")
                return {
                    "status": "healthy",
                    "binary_available": True,
                    "version": version_info,
                    "binary_path": self.binary_path
                }
            else:
                error_msg = result.stderr or "Unknown error"
                self.log("ERROR", f"Lassie binary error: {error_msg}")
                return {
                    "status": "unhealthy",
                    "binary_available": False,
                    "error": error_msg
                }
                
        except subprocess.TimeoutExpired:
            self.log("ERROR", "Lassie binary check timed out")
            return {
                "status": "unhealthy",
                "binary_available": False,
                "error": "Binary check timed out"
            }
        except FileNotFoundError:
            self.log("ERROR", f"Lassie binary not found at: {self.binary_path}")
            return {
                "status": "unhealthy",
                "binary_available": False,
                "error": f"Binary not found at: {self.binary_path}"
            }
        except Exception as e:
            self.log("ERROR", f"Lassie health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "binary_available": False,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current status of Lassie binary."""
        health_result = await self.health_check()
        return {
            "name": self.name,
            "status": health_result.get("status", "unknown"),
            "binary_available": health_result.get("binary_available", False),
            "version": health_result.get("version", "unknown"),
            "binary_path": self.binary_path
        }
    
    async def get_config(self) -> Dict[str, Any]:
        """Get Lassie configuration."""
        return {
            "binary_path": self.binary_path,
            "integration_mode": self.config.get("integration_mode", "standalone"),
            "timeout": self.config.get("timeout", "30s"),
            "concurrent_downloads": self.config.get("concurrent_downloads", 10),
            "temp_directory": self.config.get("temp_directory", ""),
            "providers": self.config.get("provider_endpoints", "").split('\n') if self.config.get("provider_endpoints") else [],
            "enable_bitswap": self.config.get("enable_bitswap", True),
            "enable_graphsync": self.config.get("enable_graphsync", True)
        }
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set Lassie configuration."""
        # Update internal config
        self.config.update(config)
        if "binary_path" in config:
            self.binary_path = config["binary_path"]
        self.log("INFO", "Lassie configuration updated")
        return True


class StorachaClient(BackendClient):
    """Client for Storacha backend."""
    
    def __init__(self, endpoint: str = "https://up.web3.storage", **kwargs):
        super().__init__("Storacha", endpoint, **kwargs)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Storacha health."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Check if the endpoint is reachable
            async with self.session.get(f"{self.endpoint}/", timeout=5) as response:
                if response.status < 500:  # Any non-server error is considered healthy
                    return {
                        "status": "healthy",
                        "endpoint": self.endpoint,
                        "response_code": response.status
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "endpoint": self.endpoint,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed Storacha status."""
        # Storacha is a cloud service, limited info available
        return {
            "service": "web3.storage",
            "endpoint": self.endpoint,
            "type": "cloud_storage",
            "features": ["IPFS", "Filecoin", "CAR files"]
        }
    
    async def get_config(self) -> Dict[str, Any]:
        """Get Storacha configuration."""
        return {"message": "Storacha config managed via API keys"}
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set Storacha configuration."""
        return False


class SynapseClient(BackendClient):
    """Client for Synapse backend."""
    
    def __init__(self, endpoint: str = "http://127.0.0.1:8008", **kwargs):
        super().__init__("Synapse", endpoint, **kwargs)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Synapse health."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Check Synapse health endpoint
            async with self.session.get(f"{self.endpoint}/health", timeout=5) as response:
                if response.status == 200:
                    return {
                        "status": "healthy",
                        "endpoint": self.endpoint,
                        "response_code": response.status
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "endpoint": self.endpoint,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed Synapse status."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Get version info
            async with self.session.get(f"{self.endpoint}/_synapse/admin/v1/server_version") as response:
                if response.status == 200:
                    version_data = await response.json()
                else:
                    version_data = {"error": f"HTTP {response.status}"}
            
            return {
                "version": version_data.get("server_version", "unknown"),
                "python_version": version_data.get("python_version", "unknown"),
                "status": "running" if version_data.get("server_version") else "stopped"
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_config(self) -> Dict[str, Any]:
        """Get Synapse configuration."""
        return {"message": "Synapse config managed via homeserver.yaml"}
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set Synapse configuration."""
        return False


class S3Client(BackendClient):
    """Client for S3 backend."""
    
    def __init__(self, endpoint: str = "", access_key: str = "", secret_key: str = "", **kwargs):
        super().__init__("S3", endpoint, **kwargs)
        self.access_key = access_key
        self.secret_key = secret_key
    
    async def health_check(self) -> Dict[str, Any]:
        """Check S3 health."""
        try:
            # For S3, we'd typically use boto3, but for simplicity, we'll just check endpoint
            if not self.endpoint:
                return {
                    "status": "unhealthy",
                    "endpoint": self.endpoint,
                    "error": "No endpoint configured"
                }
            
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Basic connectivity check
            async with self.session.get(self.endpoint, timeout=5) as response:
                return {
                    "status": "healthy" if response.status < 500 else "unhealthy",
                    "endpoint": self.endpoint,
                    "response_code": response.status
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed S3 status."""
        return {
            "endpoint": self.endpoint,
            "access_key": self.access_key[:8] + "..." if self.access_key else "not_set",
            "type": "object_storage",
            "features": ["bucket_operations", "object_operations"]
        }
    
    async def get_config(self) -> Dict[str, Any]:
        """Get S3 configuration."""
        return {
            "endpoint": self.endpoint,
            "access_key": self.access_key[:8] + "..." if self.access_key else "not_set",
            "secret_key": "***" if self.secret_key else "not_set"
        }
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set S3 configuration."""
        self.endpoint = config.get("endpoint", self.endpoint)
        self.access_key = config.get("access_key", self.access_key)
        self.secret_key = config.get("secret_key", self.secret_key)
        return True


class HuggingFaceClient(BackendClient):
    """Client for HuggingFace backend."""
    
    def __init__(self, endpoint: str = "https://huggingface.co", token: str = "", **kwargs):
        super().__init__("HuggingFace", endpoint, **kwargs)
        self.token = token
    
    async def health_check(self) -> Dict[str, Any]:
        """Check HuggingFace health."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Check HuggingFace API
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            async with self.session.get(f"{self.endpoint}/api/whoami", headers=headers, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "healthy",
                        "endpoint": self.endpoint,
                        "authenticated": True,
                        "username": data.get("name", "unknown")
                    }
                elif response.status == 401:
                    return {
                        "status": "partial",
                        "endpoint": self.endpoint,
                        "authenticated": False,
                        "error": "Authentication required"
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "endpoint": self.endpoint,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed HuggingFace status."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            async with self.session.get(f"{self.endpoint}/api/whoami", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "username": data.get("name", "unknown"),
                        "email": data.get("email", "unknown"),
                        "avatar": data.get("avatarUrl", ""),
                        "plan": data.get("plan", "free"),
                        "authenticated": True
                    }
                else:
                    return {
                        "authenticated": False,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_config(self) -> Dict[str, Any]:
        """Get HuggingFace configuration."""
        return {
            "endpoint": self.endpoint,
            "token": self.token[:8] + "..." if self.token else "not_set"
        }
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set HuggingFace configuration."""
        self.endpoint = config.get("endpoint", self.endpoint)
        self.token = config.get("token", self.token)
        return True


class ParquetClient(BackendClient):
    """Client for Parquet backend."""
    
    def __init__(self, data_dir: str = "/tmp/parquet_data", **kwargs):
        super().__init__("Parquet", f"file://{data_dir}", **kwargs)
        self.data_dir = data_dir
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Parquet backend health."""
        try:
            import os
            import pathlib
            
            # Check if data directory exists and is accessible
            path = pathlib.Path(self.data_dir)
            if path.exists() and path.is_dir():
                return {
                    "status": "healthy",
                    "endpoint": self.endpoint,
                    "data_dir": self.data_dir,
                    "writable": os.access(self.data_dir, os.W_OK)
                }
            else:
                return {
                    "status": "unhealthy",
                    "endpoint": self.endpoint,
                    "error": "Data directory not accessible"
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "error": str(e)
            }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get detailed Parquet status."""
        try:
            import os
            import pathlib
            
            path = pathlib.Path(self.data_dir)
            if path.exists():
                # Count parquet files
                parquet_files = list(path.glob("**/*.parquet"))
                total_size = sum(f.stat().st_size for f in parquet_files)
                
                return {
                    "data_dir": self.data_dir,
                    "parquet_files": len(parquet_files),
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024*1024), 2),
                    "writable": os.access(self.data_dir, os.W_OK)
                }
            else:
                return {"error": "Data directory not found"}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_config(self) -> Dict[str, Any]:
        """Get Parquet configuration."""
        return {
            "data_dir": self.data_dir,
            "endpoint": self.endpoint
        }
    
    async def set_config(self, config: Dict[str, Any]) -> bool:
        """Set Parquet configuration."""
        self.data_dir = config.get("data_dir", self.data_dir)
        self.endpoint = f"file://{self.data_dir}"
        return True
