"""
IPFS Cluster REST API client for both cluster service and cluster follow.
Implements the REST API as documented at https://ipfscluster.io/documentation/reference/api/
"""

import asyncio
import json
import logging
import httpx
import subprocess
import os
from typing import Dict, Any, List, Optional, Union
from urllib.parse import quote

logger = logging.getLogger(__name__)


class IPFSClusterAPIClient:
    """REST API client for IPFS Cluster service."""
    
    def __init__(self, api_url: str = "http://127.0.0.1:9094", auth: Optional[Dict[str, str]] = None):
        """Initialize cluster API client.
        
        Args:
            api_url: Base URL for cluster API (default: http://127.0.0.1:9094)
            auth: Authentication credentials {"username": "user", "password": "pass"}
        """
        self.api_url = api_url.rstrip('/')
        self.auth = auth
        self.session = httpx.AsyncClient(timeout=30.0)
        self._jwt_token = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()
        
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication if available."""
        headers = {"Content-Type": "application/json"}
        
        if self._jwt_token:
            headers["Authorization"] = f"Bearer {self._jwt_token}"
        
        return headers
        
    def _get_auth(self) -> Optional[httpx.BasicAuth]:
        """Get basic auth if available."""
        if self.auth:
            return httpx.BasicAuth(self.auth["username"], self.auth["password"])
        return None
        
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to cluster API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            API response as dict
        """
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers()
        auth = self._get_auth()
        
        try:
            response = await self.session.request(
                method=method,
                url=url,
                headers=headers,
                auth=auth,
                **kwargs
            )
            
            # Handle different response types
            if response.status_code == 204:  # No content
                return {"success": True, "status_code": 204}
            elif response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    return {"success": True, "text": response.text, "status_code": 200}
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
                
        except httpx.RequestError as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
    
    async def authenticate(self) -> bool:
        """Authenticate and get JWT token if basic auth is available.
        
        Returns:
            True if authentication successful or not needed
        """
        if not self.auth:
            return True
            
        try:
            response = await self._request("POST", "/token")
            if response.get("success") and "token" in response:
                self._jwt_token = response["token"]
                return True
            return False
        except Exception as e:
            logger.warning(f"Authentication failed: {e}")
            return False
    
    # Core API endpoints
    async def get_id(self) -> Dict[str, Any]:
        """Get cluster peer information."""
        return await self._request("GET", "/id")
    
    async def get_version(self) -> Dict[str, Any]:
        """Get cluster version."""
        return await self._request("GET", "/version")
    
    async def get_peers(self) -> Dict[str, Any]:
        """Get cluster peers."""
        return await self._request("GET", "/peers")
    
    async def remove_peer(self, peer_id: str) -> Dict[str, Any]:
        """Remove a peer from cluster."""
        return await self._request("DELETE", f"/peers/{peer_id}")
    
    async def get_allocations(self, cid: Optional[str] = None) -> Dict[str, Any]:
        """Get pin allocations."""
        endpoint = f"/allocations/{cid}" if cid else "/allocations"
        return await self._request("GET", endpoint)
    
    async def get_pins(self, cid: Optional[str] = None) -> Dict[str, Any]:
        """Get local pin status."""
        endpoint = f"/pins/{cid}" if cid else "/pins"
        return await self._request("GET", endpoint)
    
    async def pin_cid(self, cid: str, **params) -> Dict[str, Any]:
        """Pin a CID."""
        query_params = {k: v for k, v in params.items() if v is not None}
        return await self._request("POST", f"/pins/{cid}", params=query_params)
    
    async def pin_path(self, path: str, **params) -> Dict[str, Any]:
        """Pin using IPFS path."""
        encoded_path = quote(path, safe='')
        query_params = {k: v for k, v in params.items() if v is not None}
        return await self._request("POST", f"/pins/{encoded_path}", params=query_params)
    
    async def unpin_cid(self, cid: str) -> Dict[str, Any]:
        """Unpin a CID."""
        return await self._request("DELETE", f"/pins/{cid}")
    
    async def unpin_path(self, path: str) -> Dict[str, Any]:
        """Unpin using IPFS path."""
        encoded_path = quote(path, safe='')
        return await self._request("DELETE", f"/pins/{encoded_path}")
    
    async def recover_pin(self, cid: Optional[str] = None) -> Dict[str, Any]:
        """Recover pin(s)."""
        endpoint = f"/pins/{cid}/recover" if cid else "/pins/recover"
        return await self._request("POST", endpoint)
    
    async def get_metrics(self, metric_type: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics."""
        endpoint = f"/monitor/metrics/{metric_type}" if metric_type else "/monitor/metrics"
        return await self._request("GET", endpoint)
    
    async def get_health_alerts(self) -> Dict[str, Any]:
        """Get health alerts."""
        return await self._request("GET", "/health/alerts")
    
    async def get_health_graph(self) -> Dict[str, Any]:
        """Get connection graph."""
        return await self._request("GET", "/health/graph")
    
    async def get_health_bandwidth(self) -> Dict[str, Any]:
        """Get bandwidth statistics."""
        return await self._request("GET", "/health/bandwidth")
    
    async def ipfs_gc(self) -> Dict[str, Any]:
        """Perform garbage collection on IPFS nodes."""
        return await self._request("POST", "/ipfs/gc")
    
    async def health_check(self) -> Dict[str, Any]:
        """Simple health check (no auth required)."""
        return await self._request("GET", "/health")


class IPFSClusterFollowAPIClient(IPFSClusterAPIClient):
    """REST API client for IPFS Cluster Follow service."""
    
    def __init__(self, api_url: str = "http://127.0.0.1:9097", auth: Optional[Dict[str, str]] = None):
        """Initialize cluster follow API client.
        
        Args:
            api_url: Base URL for cluster follow API (default: http://127.0.0.1:9097)
            auth: Authentication credentials
        """
        super().__init__(api_url, auth)


class IPFSClusterCTLWrapper:
    """Wrapper for ipfs-cluster-ctl command line tool."""
    
    def __init__(self, api_url: str = "http://127.0.0.1:9094", encoding: str = "json"):
        """Initialize cluster ctl wrapper.
        
        Args:
            api_url: API URL for cluster
            encoding: Output encoding (json or text)
        """
        self.api_url = api_url
        self.encoding = encoding
        
    async def run_command(self, command: List[str], debug: bool = False) -> Dict[str, Any]:
        """Run ipfs-cluster-ctl command.
        
        Args:
            command: Command arguments
            debug: Enable debug output
            
        Returns:
            Command result
        """
        cmd = ["ipfs-cluster-ctl", f"--host={self.api_url}", f"--enc={self.encoding}"]
        
        if debug:
            cmd.append("--debug")
            
        cmd.extend(command)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            result = {
                "success": process.returncode == 0,
                "returncode": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "command": " ".join(cmd)
            }
            
            # Parse JSON output if encoding is json and command succeeded
            if self.encoding == "json" and result["success"] and result["stdout"]:
                try:
                    result["data"] = json.loads(result["stdout"])
                except json.JSONDecodeError:
                    pass  # Keep raw stdout
                    
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": " ".join(cmd)
            }
    
    # Convenience methods for common operations
    async def status(self) -> Dict[str, Any]:
        """Get cluster status."""
        return await self.run_command(["status"])
    
    async def peers_ls(self) -> Dict[str, Any]:
        """List peers."""
        return await self.run_command(["peers", "ls"])
    
    async def pin_add(self, cid: str, **options) -> Dict[str, Any]:
        """Pin a CID."""
        cmd = ["pin", "add", cid]
        for key, value in options.items():
            cmd.extend([f"--{key}", str(value)])
        return await self.run_command(cmd)
    
    async def pin_rm(self, cid: str) -> Dict[str, Any]:
        """Unpin a CID."""
        return await self.run_command(["pin", "rm", cid])
    
    async def pin_ls(self, cid: Optional[str] = None) -> Dict[str, Any]:
        """List pins."""
        cmd = ["pin", "ls"]
        if cid:
            cmd.append(cid)
        return await self.run_command(cmd)
    
    async def health_graph(self) -> Dict[str, Any]:
        """Get health graph."""
        return await self.run_command(["health", "graph"])
    
    async def health_metrics(self, metric_type: Optional[str] = None) -> Dict[str, Any]:
        """Get health metrics."""
        cmd = ["health", "metrics"]
        if metric_type:
            cmd.append(metric_type)
        return await self.run_command(cmd)


class IPFSClusterFollowCTLWrapper(IPFSClusterCTLWrapper):
    """Wrapper for ipfs-cluster-follow command line tool."""
    
    def __init__(self, cluster_name: str, api_url: str = "http://127.0.0.1:9097"):
        """Initialize cluster follow ctl wrapper.
        
        Args:
            cluster_name: Name of the cluster to follow
            api_url: API URL for cluster follow
        """
        super().__init__(api_url)
        self.cluster_name = cluster_name
    
    async def run_follow_command(self, command: List[str]) -> Dict[str, Any]:
        """Run ipfs-cluster-follow command.
        
        Args:
            command: Command arguments
            
        Returns:
            Command result
        """
        cmd = ["ipfs-cluster-follow", self.cluster_name] + command
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            result = {
                "success": process.returncode == 0,
                "returncode": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "command": " ".join(cmd)
            }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": " ".join(cmd)
            }
    
    async def init(self, bootstrap_peer: str) -> Dict[str, Any]:
        """Initialize cluster follow."""
        return await self.run_follow_command(["init", bootstrap_peer])
    
    async def run_daemon(self) -> Dict[str, Any]:
        """Run cluster follow daemon."""
        return await self.run_follow_command(["run"])
    
    async def list_pins(self) -> Dict[str, Any]:
        """List followed pins."""
        return await self.run_follow_command(["list"])
    
    async def info(self) -> Dict[str, Any]:
        """Get cluster follow info."""
        return await self.run_follow_command(["info"])
