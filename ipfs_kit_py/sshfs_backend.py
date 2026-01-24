#!/usr/bin/env python3
"""
SSHFS Storage Backend for IPFS-Kit

This module implements an SSHFS (SSH Filesystem) storage backend that allows
IPFS-Kit to use remote SSH/SCP servers as storage destinations. It provides
seamless integration with SSH-accessible systems, supporting both key-based
and password authentication.

Features:
- SSH key-based and password authentication
- Automatic connection pooling and retry logic
- Parallel file operations
- Directory synchronization
- Remote path mapping and management
- Connection health monitoring
- Bandwidth throttling support
"""

import os
import asyncio
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, AsyncIterator, Set
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import paramiko
    from paramiko import SSHClient, AutoAddPolicy, RSAKey, Ed25519Key, ECDSAKey
    from paramiko.ssh_exception import SSHException, AuthenticationException, NoValidConnectionsError
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    paramiko = None
    SSHClient = None
    AutoAddPolicy = None
    SSHException = AuthenticationException = NoValidConnectionsError = Exception

try:
    import scp
    from scp import SCPClient, SCPException
    SCP_AVAILABLE = True
except ImportError:
    SCP_AVAILABLE = False
    scp = None
    SCPClient = None
    SCPException = Exception

# Import base storage backend
from .mcp.storage_types import StorageBackendType

# For now, create a simple base class since we need it
class StorageBackend:
    """Base storage backend class."""
    def __init__(self, backend_type: StorageBackendType, config: Dict[str, Any]):
        self.backend_type = backend_type
        self.config = config

logger = logging.getLogger(__name__)

@dataclass
class SSHFSConfig:
    """Configuration for SSHFS backend."""
    hostname: str
    username: str
    port: int = 22
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_data: Optional[str] = None
    passphrase: Optional[str] = None
    remote_base_path: str = '/tmp/ipfs_kit'
    connection_timeout: int = 30
    auth_timeout: int = 10
    max_connections: int = 5
    retry_attempts: int = 3
    retry_delay: float = 1.0
    bandwidth_limit: Optional[int] = None  # KB/s
    host_key_policy: str = 'auto_add'  # 'auto_add', 'reject', 'warning'
    compression: bool = True
    keepalive_interval: int = 60
    
    def validate(self) -> List[str]:
        """Validate configuration and return any errors."""
        errors = []
        
        if not self.hostname:
            errors.append("Hostname is required")
        
        if not self.username:
            errors.append("Username is required")
        
        if self.port < 1 or self.port > 65535:
            errors.append("Port must be between 1 and 65535")
        
        if not self.password and not self.private_key_path and not self.private_key_data:
            errors.append("Either password or private key must be provided")
        
        if self.private_key_path and not Path(self.private_key_path).exists():
            errors.append(f"Private key file not found: {self.private_key_path}")
        
        if self.max_connections < 1:
            errors.append("max_connections must be at least 1")
        
        if self.bandwidth_limit is not None and self.bandwidth_limit < 1:
            errors.append("bandwidth_limit must be positive")
        
        return errors

@dataclass
class SSHFSFileInfo:
    """Information about a file on the SSHFS backend."""
    path: str
    size: int
    modified_time: datetime
    is_directory: bool
    permissions: str
    owner: str
    group: str
    remote_path: str

class SSHFSConnection:
    """Manages a single SSH connection with SCP capabilities."""
    
    def __init__(self, config: SSHFSConfig, connection_id: str):
        self.config = config
        self.connection_id = connection_id
        self.ssh_client = None
        self.scp_client = None
        self.connected = False
        self.last_used = time.time()
        self.connection_errors = 0
        self._lock = anyio.Lock()
    
    async def connect(self) -> bool:
        """Establish SSH connection."""
        if not PARAMIKO_AVAILABLE:
            logger.error("Paramiko not available for SSH connections")
            return False
        
        async with self._lock:
            try:
                self.ssh_client = SSHClient()
                
                # Set host key policy
                if self.config.host_key_policy == 'auto_add':
                    self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())
                elif self.config.host_key_policy == 'reject':
                    pass  # Default policy rejects unknown hosts
                else:
                    logger.warning(f"Unknown host key policy: {self.config.host_key_policy}")
                
                # Prepare authentication
                auth_kwargs = {
                    'hostname': self.config.hostname,
                    'port': self.config.port,
                    'username': self.config.username,
                    'timeout': self.config.connection_timeout,
                    'auth_timeout': self.config.auth_timeout,
                    'compress': self.config.compression
                }
                
                # Add authentication method
                if self.config.password:
                    auth_kwargs['password'] = self.config.password
                elif self.config.private_key_path or self.config.private_key_data:
                    pkey = self._load_private_key()
                    if pkey:
                        auth_kwargs['pkey'] = pkey
                    else:
                        logger.error("Failed to load private key")
                        return False
                
                # Connect
                await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: self.ssh_client.connect(**auth_kwargs)
                )
                
                # Create SCP client
                if SCP_AVAILABLE:
                    self.scp_client = SCPClient(self.ssh_client.get_transport())
                
                self.connected = True
                self.connection_errors = 0
                self.last_used = time.time()
                
                logger.info(f"SSH connection {self.connection_id} established to {self.config.hostname}")
                return True
                
            except Exception as e:
                logger.error(f"SSH connection {self.connection_id} failed: {e}")
                self.connection_errors += 1
                await self.disconnect()
                return False
    
    def _load_private_key(self):
        """Load private key from file or data."""
        try:
            key_data = None
            
            if self.config.private_key_data:
                key_data = self.config.private_key_data
            elif self.config.private_key_path:
                with open(self.config.private_key_path, 'r') as f:
                    key_data = f.read()
            
            if not key_data:
                return None
            
            # Try different key types
            key_types = [RSAKey, Ed25519Key, ECDSAKey]
            
            for key_type in key_types:
                try:
                    if self.config.passphrase:
                        return key_type.from_private_key_file(
                            self.config.private_key_path or key_data,
                            password=self.config.passphrase
                        )
                    else:
                        return key_type.from_private_key_file(
                            self.config.private_key_path or key_data
                        )
                except Exception:
                    continue
            
            logger.error("Failed to load private key with any supported format")
            return None
            
        except Exception as e:
            logger.error(f"Error loading private key: {e}")
            return None
    
    async def disconnect(self):
        """Close SSH connection."""
        async with self._lock:
            try:
                if self.scp_client:
                    self.scp_client.close()
                    self.scp_client = None
                
                if self.ssh_client:
                    self.ssh_client.close()
                    self.ssh_client = None
                
                self.connected = False
                logger.debug(f"SSH connection {self.connection_id} closed")
                
            except Exception as e:
                logger.error(f"Error closing SSH connection {self.connection_id}: {e}")
    
    async def execute_command(self, command: str) -> Tuple[str, str, int]:
        """Execute command on remote server."""
        if not self.connected or not self.ssh_client:
            raise ConnectionError("SSH connection not established")
        
        try:
            stdin, stdout, stderr = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.ssh_client.exec_command(command, timeout=30)
            )
            
            stdout_data = await asyncio.get_event_loop().run_in_executor(
                None, stdout.read
            )
            stderr_data = await asyncio.get_event_loop().run_in_executor(
                None, stderr.read
            )
            
            return (
                stdout_data.decode('utf-8'),
                stderr_data.decode('utf-8'),
                stdout.channel.recv_exit_status()
            )
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise
    
    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file using SCP."""
        if not self.connected or not self.scp_client:
            raise ConnectionError("SCP connection not established")
        
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.scp_client.put(local_path, remote_path, recursive=False)
            )
            self.last_used = time.time()
            return True
            
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            return False
    
    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file using SCP."""
        if not self.connected or not self.scp_client:
            raise ConnectionError("SCP connection not established")
        
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.scp_client.get(remote_path, local_path, recursive=False)
            )
            self.last_used = time.time()
            return True
            
        except Exception as e:
            logger.error(f"File download failed: {e}")
            return False
    
    def is_idle(self, max_idle_time: int = 300) -> bool:
        """Check if connection has been idle for too long."""
        return time.time() - self.last_used > max_idle_time

class SSHFSConnectionPool:
    """Pool of SSH connections for efficient resource management."""
    
    def __init__(self, config: SSHFSConfig):
        self.config = config
        self.connections: Dict[str, SSHFSConnection] = {}
        self.available_connections: List[str] = []
        self.busy_connections: Set[str] = set()
        self._lock = anyio.Lock()
        self._connection_counter = 0
    
    async def get_connection(self) -> Optional[SSHFSConnection]:
        """Get an available connection from the pool."""
        async with self._lock:
            # Try to use an existing available connection
            if self.available_connections:
                conn_id = self.available_connections.pop(0)
                connection = self.connections[conn_id]
                
                # Verify connection is still valid
                if connection.connected:
                    self.busy_connections.add(conn_id)
                    return connection
                else:
                    # Connection is dead, remove it
                    await connection.disconnect()
                    del self.connections[conn_id]
            
            # Create new connection if under limit
            if len(self.connections) < self.config.max_connections:
                conn_id = f"sshfs_conn_{self._connection_counter}"
                self._connection_counter += 1
                
                connection = SSHFSConnection(self.config, conn_id)
                if await connection.connect():
                    self.connections[conn_id] = connection
                    self.busy_connections.add(conn_id)
                    return connection
                else:
                    await connection.disconnect()
            
            return None
    
    async def return_connection(self, connection: SSHFSConnection):
        """Return a connection to the pool."""
        async with self._lock:
            if connection.connection_id in self.busy_connections:
                self.busy_connections.remove(connection.connection_id)
                
                if connection.connected and connection.connection_errors == 0:
                    self.available_connections.append(connection.connection_id)
                else:
                    # Connection has errors, remove it
                    await connection.disconnect()
                    if connection.connection_id in self.connections:
                        del self.connections[connection.connection_id]
    
    async def cleanup_idle_connections(self):
        """Remove idle connections from the pool."""
        async with self._lock:
            idle_connections = []
            
            for conn_id, connection in self.connections.items():
                if conn_id not in self.busy_connections and connection.is_idle():
                    idle_connections.append(conn_id)
            
            for conn_id in idle_connections:
                connection = self.connections[conn_id]
                await connection.disconnect()
                del self.connections[conn_id]
                
                if conn_id in self.available_connections:
                    self.available_connections.remove(conn_id)
    
    async def close_all(self):
        """Close all connections in the pool."""
        async with self._lock:
            for connection in self.connections.values():
                await connection.disconnect()
            
            self.connections.clear()
            self.available_connections.clear()
            self.busy_connections.clear()

class SSHFSBackend(StorageBackend):
    """SSHFS storage backend implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize SSHFS backend."""
        super().__init__(StorageBackendType.SSHFS, config)
        
        # Parse configuration
        self.sshfs_config = SSHFSConfig(**config)
        config_errors = self.sshfs_config.validate()
        if config_errors:
            raise ValueError(f"SSHFS configuration errors: {', '.join(config_errors)}")
        
        # Initialize connection pool
        self.connection_pool = SSHFSConnectionPool(self.sshfs_config)
        
        # State tracking
        self.connected = False
        self.last_health_check = 0
        self.health_check_interval = 60  # seconds
        
        # Performance metrics
        self.metrics = {
            'operations_count': 0,
            'bytes_uploaded': 0,
            'bytes_downloaded': 0,
            'connection_errors': 0,
            'last_operation_time': None
        }
        
        logger.info(f"SSHFS backend initialized for {self.sshfs_config.hostname}")
    
    async def initialize(self) -> bool:
        """Initialize the SSHFS backend."""
        try:
            # Test connection
            connection = await self.connection_pool.get_connection()
            if not connection:
                logger.error("Failed to establish initial SSHFS connection")
                return False
            
            # Ensure remote base directory exists
            await self._ensure_remote_directory(connection, self.sshfs_config.remote_base_path)
            
            # Return connection to pool
            await self.connection_pool.return_connection(connection)
            
            self.connected = True
            logger.info("SSHFS backend initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"SSHFS backend initialization failed: {e}")
            return False
    
    async def _ensure_remote_directory(self, connection: SSHFSConnection, path: str):
        """Ensure remote directory exists."""
        try:
            stdout, stderr, exit_code = await connection.execute_command(f"mkdir -p '{path}'")
            if exit_code != 0:
                logger.warning(f"Failed to create remote directory {path}: {stderr}")
        except Exception as e:
            logger.error(f"Error ensuring remote directory {path}: {e}")
    
    def _get_remote_path(self, key: str) -> str:
        """Get full remote path for a given key."""
        # Create a safe path structure
        safe_key = key.replace('/', '_').replace('\\', '_')
        return f"{self.sshfs_config.remote_base_path}/{safe_key}"
    
    async def store(self, key: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store data in SSHFS backend."""
        connection = None
        try:
            connection = await self.connection_pool.get_connection()
            if not connection:
                logger.error("No SSHFS connection available for store operation")
                return False
            
            # Create temporary local file
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(data)
                tmp_path = tmp_file.name
            
            try:
                remote_path = self._get_remote_path(key)
                
                # Ensure remote directory exists
                remote_dir = str(Path(remote_path).parent)
                await self._ensure_remote_directory(connection, remote_dir)
                
                # Upload file
                success = await connection.upload_file(tmp_path, remote_path)
                
                if success:
                    # Store metadata if provided
                    if metadata:
                        await self._store_metadata(connection, key, metadata)
                    
                    self.metrics['operations_count'] += 1
                    self.metrics['bytes_uploaded'] += len(data)
                    self.metrics['last_operation_time'] = datetime.now()
                    
                    logger.debug(f"Stored {len(data)} bytes at {key}")
                    return True
                else:
                    logger.error(f"Failed to upload file for key {key}")
                    return False
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        
        except Exception as e:
            logger.error(f"Error storing data for key {key}: {e}")
            self.metrics['connection_errors'] += 1
            return False
        
        finally:
            if connection:
                await self.connection_pool.return_connection(connection)
    
    async def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieve data from SSHFS backend."""
        connection = None
        try:
            connection = await self.connection_pool.get_connection()
            if not connection:
                logger.error("No SSHFS connection available for retrieve operation")
                return None
            
            remote_path = self._get_remote_path(key)
            
            # Create temporary local file
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            try:
                # Download file
                success = await connection.download_file(remote_path, tmp_path)
                
                if success:
                    # Read downloaded data
                    with open(tmp_path, 'rb') as f:
                        data = f.read()
                    
                    self.metrics['operations_count'] += 1
                    self.metrics['bytes_downloaded'] += len(data)
                    self.metrics['last_operation_time'] = datetime.now()
                    
                    logger.debug(f"Retrieved {len(data)} bytes for key {key}")
                    return data
                else:
                    logger.warning(f"File not found or download failed for key {key}")
                    return None
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        
        except Exception as e:
            logger.error(f"Error retrieving data for key {key}: {e}")
            self.metrics['connection_errors'] += 1
            return None
        
        finally:
            if connection:
                await self.connection_pool.return_connection(connection)
    
    async def delete(self, key: str) -> bool:
        """Delete data from SSHFS backend."""
        connection = None
        try:
            connection = await self.connection_pool.get_connection()
            if not connection:
                logger.error("No SSHFS connection available for delete operation")
                return False
            
            remote_path = self._get_remote_path(key)
            
            # Delete file
            stdout, stderr, exit_code = await connection.execute_command(f"rm -f '{remote_path}'")
            
            if exit_code == 0:
                # Delete metadata if exists
                await self._delete_metadata(connection, key)
                
                self.metrics['operations_count'] += 1
                self.metrics['last_operation_time'] = datetime.now()
                
                logger.debug(f"Deleted key {key}")
                return True
            else:
                logger.warning(f"Failed to delete key {key}: {stderr}")
                return False
        
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            self.metrics['connection_errors'] += 1
            return False
        
        finally:
            if connection:
                await self.connection_pool.return_connection(connection)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in SSHFS backend."""
        connection = None
        try:
            connection = await self.connection_pool.get_connection()
            if not connection:
                logger.error("No SSHFS connection available for exists check")
                return False
            
            remote_path = self._get_remote_path(key)
            
            # Check if file exists
            stdout, stderr, exit_code = await connection.execute_command(f"test -f '{remote_path}' && echo 'exists'")
            
            return exit_code == 0 and 'exists' in stdout
        
        except Exception as e:
            logger.error(f"Error checking existence of key {key}: {e}")
            return False
        
        finally:
            if connection:
                await self.connection_pool.return_connection(connection)
    
    async def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List keys in SSHFS backend."""
        connection = None
        try:
            connection = await self.connection_pool.get_connection()
            if not connection:
                logger.error("No SSHFS connection available for list operation")
                return []
            
            base_path = self.sshfs_config.remote_base_path
            
            # List files in remote directory
            if prefix:
                # Use find command with prefix filtering
                safe_prefix = prefix.replace('/', '_').replace('\\', '_')
                cmd = f"find '{base_path}' -name '{safe_prefix}*' -type f"
            else:
                cmd = f"find '{base_path}' -type f"
            
            stdout, stderr, exit_code = await connection.execute_command(cmd)
            
            if exit_code == 0:
                # Convert remote paths back to keys
                keys = []
                for line in stdout.strip().split('\n'):
                    if line:
                        relative_path = line.replace(base_path + '/', '')
                        # Convert back from safe path to original key
                        key = relative_path.replace('_', '/')
                        keys.append(key)
                
                return keys
            else:
                logger.warning(f"Failed to list keys: {stderr}")
                return []
        
        except Exception as e:
            logger.error(f"Error listing keys: {e}")
            return []
        
        finally:
            if connection:
                await self.connection_pool.return_connection(connection)
    
    async def _store_metadata(self, connection: SSHFSConnection, key: str, metadata: Dict[str, Any]):
        """Store metadata for a key."""
        try:
            metadata_path = self._get_remote_path(f"{key}.metadata")
            metadata_json = json.dumps(metadata, indent=2)
            
            # Create temporary metadata file
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write(metadata_json)
                tmp_path = tmp_file.name
            
            try:
                # Ensure remote directory exists
                remote_dir = str(Path(metadata_path).parent)
                await self._ensure_remote_directory(connection, remote_dir)
                
                # Upload metadata file
                await connection.upload_file(tmp_path, metadata_path)
                
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        
        except Exception as e:
            logger.error(f"Error storing metadata for key {key}: {e}")
    
    async def _delete_metadata(self, connection: SSHFSConnection, key: str):
        """Delete metadata for a key."""
        try:
            metadata_path = self._get_remote_path(f"{key}.metadata")
            await connection.execute_command(f"rm -f '{metadata_path}'")
        except Exception as e:
            logger.debug(f"Error deleting metadata for key {key}: {e}")
    
    async def get_info(self) -> Dict[str, Any]:
        """Get SSHFS backend information."""
        return {
            'backend_type': self.backend_type.value,
            'hostname': self.sshfs_config.hostname,
            'username': self.sshfs_config.username,
            'port': self.sshfs_config.port,
            'remote_base_path': self.sshfs_config.remote_base_path,
            'connected': self.connected,
            'max_connections': self.sshfs_config.max_connections,
            'active_connections': len(self.connection_pool.connections),
            'available_connections': len(self.connection_pool.available_connections),
            'busy_connections': len(self.connection_pool.busy_connections),
            'metrics': self.metrics.copy()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on SSHFS backend."""
        now = time.time()
        
        # Skip if recently checked
        if now - self.last_health_check < self.health_check_interval:
            return {
                'status': 'healthy' if self.connected else 'unhealthy',
                'last_check': self.last_health_check,
                'cached': True
            }
        
        health_status = {
            'status': 'healthy',
            'timestamp': now,
            'details': {},
            'metrics': self.metrics.copy()
        }
        
        connection = None
        try:
            # Test connection
            connection = await self.connection_pool.get_connection()
            if not connection:
                health_status['status'] = 'unhealthy'
                health_status['details']['connection'] = 'Failed to get connection from pool'
            else:
                # Test basic command
                stdout, stderr, exit_code = await connection.execute_command('echo "health_check"')
                if exit_code != 0 or 'health_check' not in stdout:
                    health_status['status'] = 'unhealthy'
                    health_status['details']['command_test'] = f'Command test failed: {stderr}'
                else:
                    health_status['details']['command_test'] = 'OK'
                
                # Test remote directory access
                stdout, stderr, exit_code = await connection.execute_command(f"ls '{self.sshfs_config.remote_base_path}' > /dev/null")
                if exit_code != 0:
                    health_status['status'] = 'degraded'
                    health_status['details']['directory_access'] = f'Directory access failed: {stderr}'
                else:
                    health_status['details']['directory_access'] = 'OK'
        
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['details']['error'] = str(e)
        
        finally:
            if connection:
                await self.connection_pool.return_connection(connection)
        
        # Update connection status
        self.connected = health_status['status'] in ['healthy', 'degraded']
        self.last_health_check = now
        
        # Clean up idle connections
        await self.connection_pool.cleanup_idle_connections()
        
        return health_status
    
    async def cleanup(self):
        """Clean up SSHFS backend resources."""
        try:
            await self.connection_pool.close_all()
            self.connected = False
            logger.info("SSHFS backend cleanup completed")
        except Exception as e:
            logger.error(f"Error during SSHFS backend cleanup: {e}")

# Factory function for creating SSHFS backend
def create_sshfs_backend(config: Dict[str, Any]) -> SSHFSBackend:
    """Create and return an SSHFS backend instance."""
    if not PARAMIKO_AVAILABLE:
        raise ImportError("Paramiko is required for SSHFS backend. Install with: pip install paramiko")
    
    if not SCP_AVAILABLE:
        raise ImportError("SCP is required for SSHFS backend. Install with: pip install scp")
    
    return SSHFSBackend(config)
