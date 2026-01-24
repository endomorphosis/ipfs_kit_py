#!/usr/bin/env python3
"""
SSHFS Kit - SSH/SCP storage backend for IPFS-Kit

This module provides SSHFS (SSH Filesystem) support as a storage backend,
allowing file storage and retrieval over SSH/SCP protocols with virtual
filesystem integration.

Key Features:
- SSH key-based authentication
- SCP file transfer operations
- Remote directory management
- Integration with VFS buckets
- Support for both file paths and CID storage
"""

import os
import json
import anyio
import subprocess
import tempfile
import logging
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import time
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    logger.warning("paramiko not available - falling back to subprocess SSH/SCP")

try:
    import stat
    STAT_AVAILABLE = True
except ImportError:
    STAT_AVAILABLE = False


def create_result_dict(operation, correlation_id=None):
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }


class SSHFSKit:
    """
    SSHFS storage backend for IPFS-Kit virtual filesystem.
    
    Provides SSH/SCP-based file storage with VFS integration.
    """
    
    def __init__(self, 
                 host: str,
                 username: str, 
                 port: int = 22,
                 key_path: Optional[str] = None,
                 password: Optional[str] = None,
                 remote_base_path: str = "/tmp/ipfs_kit_sshfs",
                 connection_timeout: int = 30,
                 keepalive_interval: int = 60):
        """
        Initialize SSHFS Kit.
        
        Args:
            host: SSH server hostname/IP
            username: SSH username
            port: SSH port (default 22)
            key_path: Path to SSH private key file
            password: SSH password (if not using key auth)
            remote_base_path: Base path on remote server
            connection_timeout: SSH connection timeout
            keepalive_interval: SSH keepalive interval
        """
        self.host = host
        self.username = username
        self.port = port
        self.key_path = key_path
        self.password = password
        self.remote_base_path = remote_base_path
        self.connection_timeout = connection_timeout
        self.keepalive_interval = keepalive_interval
        
        # Connection management
        self.ssh_client = None
        self.sftp_client = None
        self.is_connected = False
        
        # Storage tracking
        self.stored_files: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"SSHFSKit initialized for {username}@{host}:{port}")
    
    async def connect(self) -> Dict[str, Any]:
        """Establish SSH connection."""
        result = create_result_dict("connect")
        
        try:
            if PARAMIKO_AVAILABLE:
                return await self._connect_paramiko()
            else:
                return await self._connect_subprocess()
                
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            result["error"] = f"Connection failed: {str(e)}"
            return result
    
    async def _connect_paramiko(self) -> Dict[str, Any]:
        """Connect using paramiko library."""
        result = create_result_dict("connect_paramiko")
        
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Prepare connection arguments
            connect_kwargs = {
                "hostname": self.host,
                "username": self.username,
                "port": self.port,
                "timeout": self.connection_timeout
            }
            
            # Add authentication
            if self.key_path and os.path.exists(self.key_path):
                connect_kwargs["key_filename"] = self.key_path
                logger.info(f"Using SSH key: {self.key_path}")
            elif self.password:
                connect_kwargs["password"] = self.password
                logger.info("Using password authentication")
            else:
                # Try default SSH keys
                ssh_dir = Path.home() / ".ssh"
                for key_name in ["id_rsa", "id_ed25519", "id_ecdsa"]:
                    key_path = ssh_dir / key_name
                    if key_path.exists():
                        connect_kwargs["key_filename"] = str(key_path)
                        logger.info(f"Using default SSH key: {key_path}")
                        break
            
            # Connect
            self.ssh_client.connect(**connect_kwargs)
            
            # Create SFTP client
            self.sftp_client = self.ssh_client.open_sftp()
            
            # Test connection
            test_result = await self._test_connection()
            if not test_result["success"]:
                raise Exception(test_result.get("error", "Connection test failed"))
            
            self.is_connected = True
            
            result["success"] = True
            result["message"] = f"Connected to {self.username}@{self.host}:{self.port}"
            result["remote_base_path"] = self.remote_base_path
            
            logger.info(f"✅ SSH connection established to {self.host}")
            return result
            
        except Exception as e:
            logger.error(f"Paramiko connection failed: {e}")
            result["error"] = f"Paramiko connection failed: {str(e)}"
            return result
    
    async def _connect_subprocess(self) -> Dict[str, Any]:
        """Connect using subprocess SSH commands."""
        result = create_result_dict("connect_subprocess")
        
        try:
            # Test SSH connection
            ssh_cmd = [
                "ssh", "-o", "ConnectTimeout=10", 
                "-o", "BatchMode=yes",  # Disable interactive prompts
                f"{self.username}@{self.host}",
                "echo 'SSH connection test successful'"
            ]
            
            if self.key_path:
                ssh_cmd.extend(["-i", self.key_path])
            
            if self.port != 22:
                ssh_cmd.extend(["-p", str(self.port)])
            
            process = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.is_connected = True
                result["success"] = True
                result["message"] = f"SSH connection verified to {self.username}@{self.host}:{self.port}"
                result["method"] = "subprocess"
                
                # Ensure remote base path exists
                await self._ensure_remote_path(self.remote_base_path)
                
                logger.info(f"✅ SSH connection verified to {self.host}")
                return result
            else:
                raise Exception(f"SSH test failed: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Subprocess SSH connection failed: {e}")
            result["error"] = f"SSH connection failed: {str(e)}"
            return result
    
    async def _test_connection(self) -> Dict[str, Any]:
        """Test SSH connection and create remote directories."""
        result = create_result_dict("test_connection")
        
        try:
            if PARAMIKO_AVAILABLE and self.sftp_client:
                # Test SFTP connection
                try:
                    self.sftp_client.listdir(".")
                except Exception as e:
                    raise Exception(f"SFTP test failed: {e}")
                
                # Create remote base path
                await self._ensure_remote_path_sftp(self.remote_base_path)
                
            else:
                # Test with subprocess
                await self._ensure_remote_path(self.remote_base_path)
            
            result["success"] = True
            result["message"] = "Connection test successful"
            return result
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            result["error"] = f"Connection test failed: {str(e)}"
            return result
    
    async def _ensure_remote_path_sftp(self, remote_path: str):
        """Ensure remote path exists using SFTP."""
        try:
            # Try to stat the path
            self.sftp_client.stat(remote_path)
        except FileNotFoundError:
            # Path doesn't exist, create it
            parts = Path(remote_path).parts
            current_path = ""
            
            for part in parts:
                if not part:  # Skip empty parts (from leading slash)
                    continue
                    
                current_path = f"{current_path}/{part}" if current_path else f"/{part}"
                
                try:
                    self.sftp_client.stat(current_path)
                except FileNotFoundError:
                    self.sftp_client.mkdir(current_path)
                    logger.info(f"Created remote directory: {current_path}")
    
    async def _ensure_remote_path(self, remote_path: str):
        """Ensure remote path exists using subprocess SSH."""
        ssh_cmd = [
            "ssh", f"{self.username}@{self.host}",
            f"mkdir -p {remote_path}"
        ]
        
        if self.key_path:
            ssh_cmd.extend(["-i", self.key_path])
        
        if self.port != 22:
            ssh_cmd.extend(["-p", str(self.port)])
        
        process = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"Failed to create remote path: {stderr.decode()}")
    
    async def disconnect(self) -> Dict[str, Any]:
        """Close SSH connection."""
        result = create_result_dict("disconnect")
        
        try:
            if self.sftp_client:
                self.sftp_client.close()
                self.sftp_client = None
            
            if self.ssh_client:
                self.ssh_client.close()
                self.ssh_client = None
            
            self.is_connected = False
            
            result["success"] = True
            result["message"] = "SSH connection closed"
            
            logger.info(f"✅ SSH connection closed")
            return result
            
        except Exception as e:
            logger.error(f"Error closing SSH connection: {e}")
            result["error"] = f"Error closing connection: {str(e)}"
            return result
    
    async def store_file(self, 
                        local_path: str, 
                        remote_name: Optional[str] = None,
                        bucket: str = "default",
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Store a file on the remote SSH server.
        
        Args:
            local_path: Local file path to upload
            remote_name: Remote filename (defaults to local filename)
            bucket: VFS bucket name for organization
            metadata: Additional metadata to store
        """
        result = create_result_dict("store_file")
        
        try:
            if not self.is_connected:
                connect_result = await self.connect()
                if not connect_result["success"]:
                    return connect_result
            
            local_file = Path(local_path)
            if not local_file.exists():
                raise FileNotFoundError(f"Local file not found: {local_path}")
            
            # Determine remote path
            if not remote_name:
                remote_name = local_file.name
            
            remote_bucket_path = f"{self.remote_base_path}/{bucket}"
            remote_file_path = f"{remote_bucket_path}/{remote_name}"
            
            # Create bucket directory
            if PARAMIKO_AVAILABLE and self.sftp_client:
                await self._ensure_remote_path_sftp(remote_bucket_path)
                
                # Upload file
                self.sftp_client.put(str(local_file), remote_file_path)
            else:
                # Use SCP
                await self._ensure_remote_path(remote_bucket_path)
                await self._scp_upload(str(local_file), remote_file_path)
            
            # Store metadata
            file_stats = local_file.stat()
            file_metadata = {
                "original_path": str(local_file),
                "remote_path": remote_file_path,
                "bucket": bucket,
                "size": file_stats.st_size,
                "uploaded_at": time.time(),
                "metadata": metadata or {}
            }
            
            # Generate a storage ID (CID-like)
            storage_id = f"sshfs_{bucket}_{remote_name}_{int(time.time())}"
            self.stored_files[storage_id] = file_metadata
            
            result["success"] = True
            result["storage_id"] = storage_id
            result["remote_path"] = remote_file_path
            result["size"] = file_stats.st_size
            result["bucket"] = bucket
            
            logger.info(f"✅ Stored file {local_path} -> {remote_file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to store file {local_path}: {e}")
            result["error"] = f"Store failed: {str(e)}"
            return result
    
    async def _scp_upload(self, local_path: str, remote_path: str):
        """Upload file using SCP."""
        scp_cmd = ["scp"]
        
        if self.key_path:
            scp_cmd.extend(["-i", self.key_path])
        
        if self.port != 22:
            scp_cmd.extend(["-P", str(self.port)])
        
        scp_cmd.extend([
            local_path,
            f"{self.username}@{self.host}:{remote_path}"
        ])
        
        process = await asyncio.create_subprocess_exec(
            *scp_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"SCP upload failed: {stderr.decode()}")
    
    async def retrieve_file(self, 
                           storage_id: str, 
                           local_path: str) -> Dict[str, Any]:
        """
        Retrieve a file from the remote SSH server.
        
        Args:
            storage_id: Storage identifier returned from store_file
            local_path: Local path to save the file
        """
        result = create_result_dict("retrieve_file")
        
        try:
            if storage_id not in self.stored_files:
                raise KeyError(f"Storage ID not found: {storage_id}")
            
            if not self.is_connected:
                connect_result = await self.connect()
                if not connect_result["success"]:
                    return connect_result
            
            file_metadata = self.stored_files[storage_id]
            remote_path = file_metadata["remote_path"]
            
            # Create local directory if needed
            local_file = Path(local_path)
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Download file
            if PARAMIKO_AVAILABLE and self.sftp_client:
                self.sftp_client.get(remote_path, str(local_file))
            else:
                await self._scp_download(remote_path, str(local_file))
            
            result["success"] = True
            result["local_path"] = str(local_file)
            result["remote_path"] = remote_path
            result["size"] = file_metadata["size"]
            result["bucket"] = file_metadata["bucket"]
            
            logger.info(f"✅ Retrieved file {remote_path} -> {local_path}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to retrieve file {storage_id}: {e}")
            result["error"] = f"Retrieve failed: {str(e)}"
            return result
    
    async def _scp_download(self, remote_path: str, local_path: str):
        """Download file using SCP."""
        scp_cmd = ["scp"]
        
        if self.key_path:
            scp_cmd.extend(["-i", self.key_path])
        
        if self.port != 22:
            scp_cmd.extend(["-P", str(self.port)])
        
        scp_cmd.extend([
            f"{self.username}@{self.host}:{remote_path}",
            local_path
        ])
        
        process = await asyncio.create_subprocess_exec(
            *scp_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"SCP download failed: {stderr.decode()}")
    
    async def list_files(self, bucket: str = None) -> Dict[str, Any]:
        """
        List files stored on the remote server.
        
        Args:
            bucket: Filter by bucket name (optional)
        """
        result = create_result_dict("list_files")
        
        try:
            files = []
            
            for storage_id, metadata in self.stored_files.items():
                if bucket and metadata["bucket"] != bucket:
                    continue
                
                files.append({
                    "storage_id": storage_id,
                    "remote_path": metadata["remote_path"],
                    "bucket": metadata["bucket"],
                    "size": metadata["size"],
                    "uploaded_at": metadata["uploaded_at"],
                    "metadata": metadata.get("metadata", {})
                })
            
            result["success"] = True
            result["files"] = files
            result["total_files"] = len(files)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            result["error"] = f"List failed: {str(e)}"
            return result
    
    async def delete_file(self, storage_id: str) -> Dict[str, Any]:
        """
        Delete a file from the remote server.
        
        Args:
            storage_id: Storage identifier to delete
        """
        result = create_result_dict("delete_file")
        
        try:
            if storage_id not in self.stored_files:
                raise KeyError(f"Storage ID not found: {storage_id}")
            
            if not self.is_connected:
                connect_result = await self.connect()
                if not connect_result["success"]:
                    return connect_result
            
            file_metadata = self.stored_files[storage_id]
            remote_path = file_metadata["remote_path"]
            
            # Delete remote file
            if PARAMIKO_AVAILABLE and self.sftp_client:
                self.sftp_client.remove(remote_path)
            else:
                ssh_cmd = [
                    "ssh", f"{self.username}@{self.host}",
                    f"rm -f {remote_path}"
                ]
                
                if self.key_path:
                    ssh_cmd.extend(["-i", self.key_path])
                
                if self.port != 22:
                    ssh_cmd.extend(["-p", str(self.port)])
                
                process = await asyncio.create_subprocess_exec(
                    *ssh_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    raise Exception(f"SSH delete failed: {stderr.decode()}")
            
            # Remove from tracking
            del self.stored_files[storage_id]
            
            result["success"] = True
            result["storage_id"] = storage_id
            result["remote_path"] = remote_path
            
            logger.info(f"✅ Deleted file {remote_path}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete file {storage_id}: {e}")
            result["error"] = f"Delete failed: {str(e)}"
            return result
    
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get information about the SSHFS storage backend."""
        result = create_result_dict("get_storage_info")
        
        try:
            info = {
                "backend_type": "sshfs",
                "host": self.host,
                "username": self.username,
                "port": self.port,
                "remote_base_path": self.remote_base_path,
                "is_connected": self.is_connected,
                "total_files": len(self.stored_files),
                "paramiko_available": PARAMIKO_AVAILABLE,
                "authentication_method": "key" if self.key_path else "password" if self.password else "default_keys"
            }
            
            # Calculate total size
            total_size = sum(f["size"] for f in self.stored_files.values())
            info["total_size"] = total_size
            
            # Get bucket statistics
            buckets = {}
            for metadata in self.stored_files.values():
                bucket = metadata["bucket"]
                if bucket not in buckets:
                    buckets[bucket] = {"files": 0, "size": 0}
                buckets[bucket]["files"] += 1
                buckets[bucket]["size"] += metadata["size"]
            
            info["buckets"] = buckets
            
            result["success"] = True
            result["storage_info"] = info
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            result["error"] = f"Info failed: {str(e)}"
            return result


# Factory function for creating SSHFS instances
def create_sshfs_kit(config: Dict[str, Any]) -> SSHFSKit:
    """
    Create an SSHFSKit instance from configuration.
    
    Args:
        config: Configuration dictionary with SSH parameters
        
    Returns:
        SSHFSKit instance
    """
    required_fields = ["host", "username"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required configuration field: {field}")
    
    return SSHFSKit(
        host=config["host"],
        username=config["username"],
        port=config.get("port", 22),
        key_path=config.get("key_path"),
        password=config.get("password"),
        remote_base_path=config.get("remote_base_path", "/tmp/ipfs_kit_sshfs"),
        connection_timeout=config.get("connection_timeout", 30),
        keepalive_interval=config.get("keepalive_interval", 60)
    )


# Example usage
if __name__ == "__main__":
    async def demo_sshfs():
        """Demonstrate SSHFS functionality."""
        print("🚀 SSHFS Kit Demo")
        print("=" * 50)
        
        # Configure SSHFS (update with your SSH details)
        config = {
            "host": "localhost",  # Update with your SSH server
            "username": "user",   # Update with your username
            "port": 22,
            "key_path": os.path.expanduser("~/.ssh/id_rsa"),  # or None for password
            "remote_base_path": "/tmp/ipfs_kit_sshfs_demo"
        }
        
        sshfs = create_sshfs_kit(config)
        
        try:
            # Connect
            print("🔌 Connecting to SSH server...")
            connect_result = await sshfs.connect()
            print(f"Connection: {'✅' if connect_result['success'] else '❌'}")
            
            if connect_result["success"]:
                # Create a test file
                test_file = "/tmp/sshfs_test.txt"
                with open(test_file, "w") as f:
                    f.write("Hello SSHFS!")
                
                # Store file
                print("📤 Storing test file...")
                store_result = await sshfs.store_file(
                    test_file, 
                    "test.txt", 
                    bucket="demo",
                    metadata={"test": True}
                )
                print(f"Store: {'✅' if store_result['success'] else '❌'}")
                
                if store_result["success"]:
                    storage_id = store_result["storage_id"]
                    
                    # List files
                    print("📋 Listing files...")
                    list_result = await sshfs.list_files()
                    print(f"Files: {list_result.get('total_files', 0)}")
                    
                    # Retrieve file
                    print("📥 Retrieving file...")
                    retrieve_result = await sshfs.retrieve_file(
                        storage_id, 
                        "/tmp/sshfs_retrieved.txt"
                    )
                    print(f"Retrieve: {'✅' if retrieve_result['success'] else '❌'}")
                    
                    # Get storage info
                    print("ℹ️ Getting storage info...")
                    info_result = await sshfs.get_storage_info()
                    if info_result["success"]:
                        info = info_result["storage_info"]
                        print(f"Backend: {info['backend_type']}")
                        print(f"Host: {info['host']}")
                        print(f"Files: {info['total_files']}")
                    
                    # Cleanup
                    os.unlink(test_file)
                    if os.path.exists("/tmp/sshfs_retrieved.txt"):
                        os.unlink("/tmp/sshfs_retrieved.txt")
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
        
        finally:
            # Disconnect
            await sshfs.disconnect()
            print("🔌 Disconnected")
    
    anyio.run(demo_sshfs())
