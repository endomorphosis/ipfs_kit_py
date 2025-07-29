#!/usr/bin/env python3
"""
FTP Kit for IPFS-Kit Virtual Filesystem

This module provides FTP/FTPS-based storage backend for IPFS-Kit VFS,
enabling remote file storage and retrieval via FTP protocol with optional TLS encryption.

Key Features:
- FTP and FTPS (FTP over TLS) support
- Passive and active FTP modes
- Directory creation and management
- Bucket-based file organization
- Connection pooling and retry logic
- VFS integration for content-addressed storage
"""

import os
import ftplib
import ssl
import time
import uuid
import logging
import json
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import tempfile
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional dependency handling
try:
    import io
    HAS_IO = True
except ImportError:
    HAS_IO = False
    logger.warning("io module not available")
    import io  # io is actually a built-in module, this should not fail

def log_operation(operation: str, details: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
    """Log FTP operation with structured details."""
    return {
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "details": details or {}
    }


class FTPKit:
    """
    FTP storage backend for IPFS-Kit virtual filesystem.
    
    Provides FTP/FTPS-based file storage with VFS integration.
    """
    
    def __init__(self, 
                 host: str,
                 username: str,
                 password: str,
                 port: int = 21,
                 use_tls: bool = False,
                 passive_mode: bool = True,
                 remote_base_path: str = "/ipfs_kit_ftp",
                 connection_timeout: int = 30,
                 retry_attempts: int = 3,
                 verify_ssl: bool = True):
        """
        Initialize FTP Kit.
        
        Args:
            host: FTP server hostname/IP
            username: FTP username
            password: FTP password
            port: FTP port (default 21)
            use_tls: Enable FTPS (FTP over TLS)
            passive_mode: Use passive FTP mode
            remote_base_path: Base directory on FTP server
            connection_timeout: Connection timeout in seconds
            retry_attempts: Number of retry attempts for failed operations
            verify_ssl: Verify SSL certificates for FTPS
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_tls = use_tls
        self.passive_mode = passive_mode
        self.remote_base_path = remote_base_path.rstrip('/')
        self.connection_timeout = connection_timeout
        self.retry_attempts = retry_attempts
        self.verify_ssl = verify_ssl
        
        # Connection management
        self.connection: Optional[Union[ftplib.FTP, ftplib.FTP_TLS]] = None
        self.connected = False
        self.last_activity = None
        
        # Operation tracking
        self.operations_log = []
        
        logger.info(f"FTPKit initialized for {username}@{host}:{port} (TLS: {use_tls})")

    def connect(self) -> bool:
        """
        Establish FTP connection with retry logic.
        
        Returns:
            bool: True if connection successful
        """
        correlation_id = str(uuid.uuid4())
        
        for attempt in range(self.retry_attempts):
            try:
                # Create FTP connection
                if self.use_tls:
                    # FTPS connection
                    context = ssl.create_default_context()
                    if not self.verify_ssl:
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                    
                    self.connection = ftplib.FTP_TLS(context=context, timeout=self.connection_timeout)
                    self.connection.connect(self.host, self.port)
                    self.connection.login(self.username, self.password)
                    self.connection.prot_p()  # Enable data encryption
                else:
                    # Regular FTP connection
                    self.connection = ftplib.FTP(timeout=self.connection_timeout)
                    self.connection.connect(self.host, self.port)
                    self.connection.login(self.username, self.password)
                
                # Set passive mode
                self.connection.set_pasv(self.passive_mode)
                
                # Ensure base directory exists
                self._ensure_remote_directory(self.remote_base_path)
                
                self.connected = True
                self.last_activity = time.time()
                
                self.operations_log.append(log_operation(
                    "connect_success",
                    {"host": self.host, "port": self.port, "tls": self.use_tls, "attempt": attempt + 1},
                    correlation_id
                ))
                
                logger.info(f"FTP connection established to {self.host}:{self.port}")
                return True
                
            except Exception as e:
                logger.warning(f"FTP connection attempt {attempt + 1} failed: {e}")
                if attempt == self.retry_attempts - 1:
                    self.operations_log.append(log_operation(
                        "connect_failed",
                        {"host": self.host, "error": str(e), "attempts": self.retry_attempts},
                        correlation_id
                    ))
                    logger.error(f"Failed to connect to FTP server after {self.retry_attempts} attempts")
                    return False
                
                time.sleep(1 * (attempt + 1))  # Exponential backoff
        
        return False

    def disconnect(self):
        """Close FTP connection."""
        if self.connection and self.connected:
            try:
                self.connection.quit()
                logger.info("FTP connection closed gracefully")
            except Exception as e:
                logger.warning(f"Error closing FTP connection: {e}")
                try:
                    self.connection.close()
                except:
                    pass
            finally:
                self.connection = None
                self.connected = False
                self.last_activity = None

    def _ensure_connection(self) -> bool:
        """Ensure FTP connection is active, reconnect if needed."""
        if not self.connected or not self.connection:
            return self.connect()
        
        # Test connection with a simple command
        try:
            if self.connection:
                self.connection.pwd()
                self.last_activity = time.time()
                return True
        except Exception as e:
            logger.warning(f"FTP connection test failed: {e}, reconnecting...")
            self.connected = False
            return self.connect()
        
        return False

    def _ensure_remote_directory(self, remote_path: str) -> bool:
        """
        Ensure remote directory exists, create if necessary.
        
        Args:
            remote_path: Remote directory path
            
        Returns:
            bool: True if directory exists or created successfully
        """
        if not self._ensure_connection() or not self.connection:
            return False
        
        try:
            # Try to change to the directory
            current_dir = self.connection.pwd()
            self.connection.cwd(remote_path)
            self.connection.cwd(current_dir)  # Change back
            return True
        except ftplib.error_perm:
            # Directory doesn't exist, create it
            try:
                parts = remote_path.strip('/').split('/')
                current_path = '/'
                
                for part in parts:
                    if part:  # Skip empty parts
                        current_path = f"{current_path.rstrip('/')}/{part}"
                        try:
                            self.connection.mkd(current_path)
                            logger.debug(f"Created FTP directory: {current_path}")
                        except ftplib.error_perm as e:
                            # Directory might already exist
                            if "exists" not in str(e).lower():
                                logger.debug(f"Directory {current_path} might already exist: {e}")
                
                return True
            except Exception as e:
                logger.error(f"Failed to create FTP directory {remote_path}: {e}")
                return False

    def _get_remote_path(self, bucket_name: str, file_hash: str) -> str:
        """
        Generate remote file path for bucket organization.
        
        Args:
            bucket_name: VFS bucket name
            file_hash: File content hash
            
        Returns:
            str: Full remote file path
        """
        # Create bucket-based hierarchy: /base_path/bucket_name/hash_prefix/file_hash
        hash_prefix = file_hash[:2] if len(file_hash) >= 2 else "00"
        return f"{self.remote_base_path}/{bucket_name}/{hash_prefix}/{file_hash}"

    def store_file(self, bucket_name: str, file_hash: str, file_data: bytes, 
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store file via FTP.
        
        Args:
            bucket_name: VFS bucket name
            file_hash: Content-addressed file hash
            file_data: File data to store
            metadata: Optional file metadata
            
        Returns:
            bool: True if storage successful
        """
        correlation_id = str(uuid.uuid4())
        
        if not self._ensure_connection() or not self.connection:
            self.operations_log.append(log_operation(
                "store_failed",
                {"bucket": bucket_name, "hash": file_hash, "error": "connection_failed"},
                correlation_id
            ))
            return False
        
        try:
            remote_path = self._get_remote_path(bucket_name, file_hash)
            remote_dir = os.path.dirname(remote_path)
            
            # Ensure remote directory exists
            if not self._ensure_remote_directory(remote_dir):
                logger.error(f"Failed to create remote directory: {remote_dir}")
                return False
            
            # Store file using binary mode
            with io.BytesIO(file_data) as file_obj:
                self.connection.storbinary(f'STOR {remote_path}', file_obj)
            
            # Store metadata if provided
            if metadata:
                metadata_path = f"{remote_path}.meta"
                metadata_json = json.dumps(metadata, indent=2).encode('utf-8')
                with io.BytesIO(metadata_json) as meta_obj:
                    self.connection.storbinary(f'STOR {metadata_path}', meta_obj)
            
            self.operations_log.append(log_operation(
                "store_success",
                {"bucket": bucket_name, "hash": file_hash, "size": len(file_data), "path": remote_path},
                correlation_id
            ))
            
            logger.info(f"File stored via FTP: {remote_path} ({len(file_data)} bytes)")
            return True
            
        except Exception as e:
            self.operations_log.append(log_operation(
                "store_failed",
                {"bucket": bucket_name, "hash": file_hash, "error": str(e)},
                correlation_id
            ))
            logger.error(f"Failed to store file via FTP: {e}")
            return False

    def retrieve_file(self, bucket_name: str, file_hash: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """
        Retrieve file via FTP.
        
        Args:
            bucket_name: VFS bucket name
            file_hash: Content-addressed file hash
            
        Returns:
            Tuple of (file_data, metadata) or None if not found
        """
        correlation_id = str(uuid.uuid4())
        
        if not self._ensure_connection() or not self.connection:
            self.operations_log.append(log_operation(
                "retrieve_failed",
                {"bucket": bucket_name, "hash": file_hash, "error": "connection_failed"},
                correlation_id
            ))
            return None
        
        try:
            remote_path = self._get_remote_path(bucket_name, file_hash)
            
            # Retrieve file data
            file_data = io.BytesIO()
            self.connection.retrbinary(f'RETR {remote_path}', file_data.write)
            file_bytes = file_data.getvalue()
            
            # Try to retrieve metadata
            metadata = {}
            metadata_path = f"{remote_path}.meta"
            try:
                meta_data = io.BytesIO()
                self.connection.retrbinary(f'RETR {metadata_path}', meta_data.write)
                metadata = json.loads(meta_data.getvalue().decode('utf-8'))
            except Exception:
                # Metadata file might not exist
                pass
            
            self.operations_log.append(log_operation(
                "retrieve_success",
                {"bucket": bucket_name, "hash": file_hash, "size": len(file_bytes), "path": remote_path},
                correlation_id
            ))
            
            logger.info(f"File retrieved via FTP: {remote_path} ({len(file_bytes)} bytes)")
            return file_bytes, metadata
            
        except ftplib.error_perm as e:
            remote_path = self._get_remote_path(bucket_name, file_hash)
            if "550" in str(e):  # File not found
                self.operations_log.append(log_operation(
                    "retrieve_not_found",
                    {"bucket": bucket_name, "hash": file_hash, "path": remote_path},
                    correlation_id
                ))
                logger.debug(f"File not found via FTP: {remote_path}")
            else:
                self.operations_log.append(log_operation(
                    "retrieve_failed",
                    {"bucket": bucket_name, "hash": file_hash, "error": str(e)},
                    correlation_id
                ))
                logger.error(f"Failed to retrieve file via FTP: {e}")
            return None
        except Exception as e:
            self.operations_log.append(log_operation(
                "retrieve_failed",
                {"bucket": bucket_name, "hash": file_hash, "error": str(e)},
                correlation_id
            ))
            logger.error(f"Failed to retrieve file via FTP: {e}")
            return None

    def delete_file(self, bucket_name: str, file_hash: str) -> bool:
        """
        Delete file via FTP.
        
        Args:
            bucket_name: VFS bucket name
            file_hash: Content-addressed file hash
            
        Returns:
            bool: True if deletion successful
        """
        correlation_id = str(uuid.uuid4())
        
        if not self._ensure_connection() or not self.connection:
            self.operations_log.append(log_operation(
                "delete_failed",
                {"bucket": bucket_name, "hash": file_hash, "error": "connection_failed"},
                correlation_id
            ))
            return False
        
        try:
            remote_path = self._get_remote_path(bucket_name, file_hash)
            
            # Delete main file
            self.connection.delete(remote_path)
            
            # Try to delete metadata file
            try:
                metadata_path = f"{remote_path}.meta"
                self.connection.delete(metadata_path)
            except Exception:
                # Metadata file might not exist
                pass
            
            self.operations_log.append(log_operation(
                "delete_success",
                {"bucket": bucket_name, "hash": file_hash, "path": remote_path},
                correlation_id
            ))
            
            logger.info(f"File deleted via FTP: {remote_path}")
            return True
            
        except ftplib.error_perm as e:
            remote_path = self._get_remote_path(bucket_name, file_hash)
            if "550" in str(e):  # File not found
                self.operations_log.append(log_operation(
                    "delete_not_found",
                    {"bucket": bucket_name, "hash": file_hash, "path": remote_path},
                    correlation_id
                ))
                logger.debug(f"File not found for deletion via FTP: {remote_path}")
                return True  # Consider it successful if file doesn't exist
            else:
                self.operations_log.append(log_operation(
                    "delete_failed",
                    {"bucket": bucket_name, "hash": file_hash, "error": str(e)},
                    correlation_id
                ))
                logger.error(f"Failed to delete file via FTP: {e}")
                return False
        except Exception as e:
            self.operations_log.append(log_operation(
                "delete_failed",
                {"bucket": bucket_name, "hash": file_hash, "error": str(e)},
                correlation_id
            ))
            logger.error(f"Failed to delete file via FTP: {e}")
            return False

    def list_files(self, bucket_name: str, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List files in bucket via FTP.
        
        Args:
            bucket_name: VFS bucket name
            prefix: Optional file prefix filter
            
        Returns:
            List of file information dictionaries
        """
        correlation_id = str(uuid.uuid4())
        
        if not self._ensure_connection() or not self.connection:
            self.operations_log.append(log_operation(
                "list_failed",
                {"bucket": bucket_name, "error": "connection_failed"},
                correlation_id
            ))
            return []
        
        try:
            bucket_path = f"{self.remote_base_path}/{bucket_name}"
            files = []
            
            # Try to list the bucket directory
            try:
                self.connection.cwd(bucket_path)
            except ftplib.error_perm:
                # Bucket directory doesn't exist
                return []
            
            # List files recursively
            def list_recursive(path: str):
                try:
                    items = []
                    if self.connection:
                        self.connection.retrlines('LIST', items.append)
                    
                    for item in items:
                        # Parse FTP LIST output (simplified)
                        parts = item.split()
                        if len(parts) >= 9:
                            permissions = parts[0]
                            size = parts[4]
                            name = ' '.join(parts[8:])
                            
                            if not permissions.startswith('d'):  # Not a directory
                                if not name.endswith('.meta'):  # Skip metadata files
                                    if not prefix or name.startswith(prefix):
                                        file_info = {
                                            'name': name,
                                            'size': int(size) if size.isdigit() else 0,
                                            'path': f"{path}/{name}",
                                            'bucket': bucket_name
                                        }
                                        files.append(file_info)
                            else:
                                # Recursively list subdirectories
                                if name not in ['.', '..'] and self.connection:
                                    old_dir = self.connection.pwd()
                                    try:
                                        self.connection.cwd(name)
                                        list_recursive(f"{path}/{name}")
                                        self.connection.cwd(old_dir)
                                    except Exception:
                                        pass
                except Exception as e:
                    logger.warning(f"Error listing FTP directory {path}: {e}")
            
            list_recursive(bucket_path)
            
            self.operations_log.append(log_operation(
                "list_success",
                {"bucket": bucket_name, "file_count": len(files)},
                correlation_id
            ))
            
            logger.info(f"Listed {len(files)} files in FTP bucket: {bucket_name}")
            return files
            
        except Exception as e:
            self.operations_log.append(log_operation(
                "list_failed",
                {"bucket": bucket_name, "error": str(e)},
                correlation_id
            ))
            logger.error(f"Failed to list files via FTP: {e}")
            return []

    def get_server_info(self) -> Dict[str, Any]:
        """
        Get FTP server information.
        
        Returns:
            Dict containing server information
        """
        if not self._ensure_connection() or not self.connection:
            return {"connected": False, "error": "connection_failed"}
        
        try:
            # Get current working directory
            pwd = self.connection.pwd()
            
            # Get system information
            system_info = ""
            try:
                system_info = self.connection.sendcmd('SYST')
            except Exception:
                pass
            
            # Get feature list
            features = []
            try:
                features = self.connection.sendcmd('FEAT').split('\n')[1:-1]
            except Exception:
                pass
            
            return {
                "connected": True,
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "tls": self.use_tls,
                "passive_mode": self.passive_mode,
                "current_directory": pwd,
                "system": system_info,
                "features": features,
                "remote_base_path": self.remote_base_path,
                "operations_count": len(self.operations_log)
            }
            
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "host": self.host,
                "port": self.port
            }

    def get_operations_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent FTP operations log.
        
        Args:
            limit: Maximum number of operations to return
            
        Returns:
            List of recent operations
        """
        return self.operations_log[-limit:] if limit > 0 else self.operations_log

    def cleanup_old_operations(self, max_age_hours: int = 24):
        """
        Clean up old operation logs.
        
        Args:
            max_age_hours: Maximum age of operations to keep in hours
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        self.operations_log = [
            op for op in self.operations_log 
            if op.get('timestamp', 0) > cutoff_time
        ]

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.disconnect()
        except Exception:
            pass


# Utility functions for FTP operations
def validate_ftp_config(config: Dict[str, Any]) -> bool:
    """
    Validate FTP configuration.
    
    Args:
        config: FTP configuration dictionary
        
    Returns:
        bool: True if configuration is valid
    """
    required_fields = ['host', 'username', 'password']
    
    for field in required_fields:
        if field not in config or not config[field]:
            logger.error(f"Missing required FTP config field: {field}")
            return False
    
    # Validate port
    port = config.get('port', 21)
    if not isinstance(port, int) or port <= 0 or port > 65535:
        logger.error(f"Invalid FTP port: {port}")
        return False
    
    return True


def test_ftp_connection(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test FTP connection with given configuration.
    
    Args:
        config: FTP configuration dictionary
        
    Returns:
        Dict containing test results
    """
    if not validate_ftp_config(config):
        return {"success": False, "error": "invalid_config"}
    
    try:
        ftp = FTPKit(
            host=config['host'],
            username=config['username'],
            password=config['password'],
            port=config.get('port', 21),
            use_tls=config.get('use_tls', False),
            passive_mode=config.get('passive_mode', True),
            remote_base_path=config.get('remote_base_path', '/ipfs_kit_ftp')
        )
        
        success = ftp.connect()
        if success:
            server_info = ftp.get_server_info()
            ftp.disconnect()
            return {
                "success": True,
                "server_info": server_info,
                "message": "FTP connection test successful"
            }
        else:
            return {
                "success": False,
                "error": "connection_failed",
                "message": "Failed to connect to FTP server"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"FTP connection test failed: {e}"
        }


# Integration with VFS
async def store_vfs_file_ftp(ftp_kit: FTPKit, bucket_name: str, file_path: str, 
                            metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Store VFS file via FTP with content-addressed naming.
    
    Args:
        ftp_kit: Initialized FTPKit instance
        bucket_name: VFS bucket name
        file_path: Local file path to store
        metadata: Optional file metadata
        
    Returns:
        Content hash if successful, None otherwise
    """
    try:
        # Read file and calculate content hash
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Calculate content-addressed hash
        content_hash = hashlib.sha256(file_data).hexdigest()
        
        # Add file metadata
        file_metadata = metadata or {}
        file_metadata.update({
            'original_path': file_path,
            'size': len(file_data),
            'stored_at': datetime.utcnow().isoformat(),
            'content_hash': content_hash
        })
        
        # Store via FTP
        success = ftp_kit.store_file(bucket_name, content_hash, file_data, file_metadata)
        
        if success:
            logger.info(f"VFS file stored via FTP: {file_path} → {content_hash}")
            return content_hash
        else:
            logger.error(f"Failed to store VFS file via FTP: {file_path}")
            return None
            
    except Exception as e:
        logger.error(f"Error storing VFS file via FTP: {e}")
        return None


if __name__ == "__main__":
    # Example usage
    import json
    
    # Example configuration
    config = {
        "host": "ftp.example.com",
        "username": "testuser",
        "password": "testpass",
        "port": 21,
        "use_tls": False,
        "passive_mode": True,
        "remote_base_path": "/ipfs_kit_storage"
    }
    
    print("FTP Kit Example Usage:")
    print("=" * 40)
    
    # Test configuration validation
    print(f"Config validation: {validate_ftp_config(config)}")
    
    # Example FTP operations (would require real FTP server)
    print("\nExample FTP operations:")
    print("- ftp = FTPKit(**config)")
    print("- ftp.connect()")
    print("- ftp.store_file('bucket1', 'hash123', b'file_data')")
    print("- data, meta = ftp.retrieve_file('bucket1', 'hash123')")
    print("- ftp.list_files('bucket1')")
    print("- ftp.disconnect()")
