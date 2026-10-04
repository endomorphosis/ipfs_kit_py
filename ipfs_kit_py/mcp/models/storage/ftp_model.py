#!/usr/bin/env python3
"""
FTP Storage Backend Model for MCP Integration

This module defines the FTP storage backend model structure for Model Context Protocol (MCP) integration,
providing schema definitions and validation for FTP storage backend configurations.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, ConfigDict, Field, validator
from datetime import datetime
import json


class FTPConnectionConfig(BaseModel):
    """FTP connection configuration parameters"""
    
    host: str = Field(..., description="FTP server hostname or IP address")
    port: int = Field(21, description="FTP server port (default: 21)")
    username: str = Field(..., description="FTP username")
    password: str = Field(..., description="FTP password")
    use_tls: bool = Field(False, description="Use FTP over TLS (FTPS)")
    passive_mode: bool = Field(True, description="Use passive mode for data connections")
    timeout: int = Field(30, description="Connection timeout in seconds")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "host": "ftp.example.com",
                "port": 21,
                "username": "ftpuser",
                "password": "ftppassword",
                "use_tls": False,
                "passive_mode": True,
                "timeout": 30
            }
        }
    )


class FTPStorageMetadata(BaseModel):
    """FTP storage backend metadata structure for MCP"""
    
    # Basic storage information
    connection_config: FTPConnectionConfig = Field(..., description="FTP connection configuration")
    remote_base_path: str = Field("/", description="Base path on FTP server")
    local_cache_path: Optional[str] = Field(None, description="Local cache directory path")
    
    # Performance and behavior settings
    max_concurrent_transfers: int = Field(5, description="Maximum concurrent FTP transfers")
    chunk_size: int = Field(8192, description="Data transfer chunk size in bytes")
    retry_attempts: int = Field(3, description="Number of retry attempts for failed operations")
    connection_pool_size: int = Field(3, description="FTP connection pool size")
    
    # Health monitoring
    health_check_interval: int = Field(300, description="Health check interval in seconds")
    connection_keepalive: bool = Field(True, description="Keep FTP connections alive")
    last_health_check: Optional[datetime] = Field(None, description="Last health check timestamp")
    health_status: str = Field("unknown", description="Current health status")
    
    # Storage statistics
    total_files: int = Field(0, description="Total number of files stored")
    total_size_bytes: int = Field(0, description="Total storage size in bytes")
    last_sync_timestamp: Optional[datetime] = Field(None, description="Last synchronization timestamp")
    
    # VFS integration
    vfs_mount_points: List[str] = Field(default_factory=list, description="VFS mount points using this backend")
    content_addressing_enabled: bool = Field(True, description="Enable content-addressed storage")
    
    # Git VFS translation support
    git_vfs_enabled: bool = Field(False, description="Enable Git VFS translation layer")
    git_repositories: List[str] = Field(default_factory=list, description="Git repositories using VFS translation")
    vfs_snapshots: List[Dict[str, Any]] = Field(default_factory=list, description="VFS snapshots for Git integration")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        },
        json_schema_extra={
            "example": {
                "connection_config": {
                    "host": "ftp.example.com",
                    "port": 21,
                    "username": "ftpuser",
                    "password": "ftppassword",
                    "use_tls": False,
                    "passive_mode": True,
                    "timeout": 30
                },
                "remote_base_path": "/storage",
                "local_cache_path": "/tmp/ftp_cache",
                "max_concurrent_transfers": 5,
                "chunk_size": 8192,
                "retry_attempts": 3,
                "connection_pool_size": 3,
                "health_check_interval": 300,
                "connection_keepalive": True,
                "health_status": "healthy",
                "total_files": 150,
                "total_size_bytes": 52428800,
                "vfs_mount_points": ["/vfs/ftp"],
                "content_addressing_enabled": True,
                "git_vfs_enabled": False,
                "git_repositories": [],
                "vfs_snapshots": []
            }
        }
    )


class FTPOperationResult(BaseModel):
    """Result structure for FTP operations"""
    
    success: bool = Field(..., description="Operation success status")
    operation_type: str = Field(..., description="Type of operation performed")
    file_path: str = Field(..., description="File path involved in operation")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    duration_ms: Optional[int] = Field(None, description="Operation duration in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if operation failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional operation metadata")
    timestamp: datetime = Field(default_factory=datetime.now, description="Operation timestamp")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class FTPHealthStatus(BaseModel):
    """FTP backend health status information"""
    
    backend_type: str = Field("ftp", description="Storage backend type")
    is_healthy: bool = Field(False, description="Overall health status")
    last_check: datetime = Field(default_factory=datetime.now, description="Last health check timestamp")
    
    # Connection status
    connection_status: str = Field("unknown", description="FTP connection status")
    connection_latency_ms: Optional[int] = Field(None, description="Connection latency in milliseconds")
    active_connections: int = Field(0, description="Number of active FTP connections")
    
    # Performance metrics
    upload_speed_mbps: Optional[float] = Field(None, description="Upload speed in Mbps")
    download_speed_mbps: Optional[float] = Field(None, description="Download speed in Mbps")
    
    # Error tracking
    recent_errors: List[str] = Field(default_factory=list, description="Recent error messages")
    error_count_24h: int = Field(0, description="Error count in last 24 hours")
    
    # Storage information
    available_space_bytes: Optional[int] = Field(None, description="Available storage space")
    used_space_bytes: Optional[int] = Field(None, description="Used storage space")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class FTPModel(BaseModel):
    """Complete FTP storage backend model for MCP integration"""
    
    backend_id: str = Field(..., description="Unique backend identifier")
    backend_type: str = Field("ftp", description="Storage backend type")
    metadata: FTPStorageMetadata = Field(..., description="FTP storage metadata")
    health_status: FTPHealthStatus = Field(..., description="Health status information")
    
    # MCP integration fields
    mcp_server_info: Dict[str, Any] = Field(default_factory=dict, description="MCP server information")
    supported_operations: List[str] = Field(
        default_factory=lambda: ["upload", "download", "delete", "list", "health_check"],
        description="Supported operations"
    )
    
    # Configuration validation
    is_configured: bool = Field(False, description="Backend configuration status")
    configuration_errors: List[str] = Field(default_factory=list, description="Configuration validation errors")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        },
        json_schema_extra={
            "example": {
                "backend_id": "ftp_primary",
                "backend_type": "ftp",
                "metadata": {
                    "connection_config": {
                        "host": "ftp.example.com",
                        "port": 21,
                        "username": "ftpuser",
                        "password": "ftppassword"
                    },
                    "remote_base_path": "/storage",
                    "health_status": "healthy",
                    "total_files": 150,
                    "total_size_bytes": 52428800
                },
                "health_status": {
                    "backend_type": "ftp",
                    "is_healthy": True,
                    "connection_status": "connected",
                    "active_connections": 2
                },
                "supported_operations": ["upload", "download", "delete", "list", "health_check"],
                "is_configured": True,
                "configuration_errors": []
            }
        }
    )

    def to_parquet_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary suitable for Parquet storage"""
        return {
            "backend_id": self.backend_id,
            "backend_type": self.backend_type,
            "host": self.metadata.connection_config.host,
            "port": self.metadata.connection_config.port,
            "remote_base_path": self.metadata.remote_base_path,
            "use_tls": self.metadata.connection_config.use_tls,
            "passive_mode": self.metadata.connection_config.passive_mode,
            "max_concurrent_transfers": self.metadata.max_concurrent_transfers,
            "health_status": self.health_status.is_healthy,
            "connection_status": self.health_status.connection_status,
            "active_connections": self.health_status.active_connections,
            "total_files": self.metadata.total_files,
            "total_size_bytes": self.metadata.total_size_bytes,
            "git_vfs_enabled": self.metadata.git_vfs_enabled,
            "git_repositories_count": len(self.metadata.git_repositories),
            "vfs_snapshots_count": len(self.metadata.vfs_snapshots),
            "vfs_mount_points": json.dumps(self.metadata.vfs_mount_points),
            "last_health_check": self.metadata.last_health_check.isoformat() if self.metadata.last_health_check else None,
            "last_sync_timestamp": self.metadata.last_sync_timestamp.isoformat() if self.metadata.last_sync_timestamp else None,
            "is_configured": self.is_configured,
            "configuration_errors": json.dumps(self.configuration_errors),
            "supported_operations": json.dumps(self.supported_operations)
        }
