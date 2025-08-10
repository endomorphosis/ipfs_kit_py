#!/usr/bin/env python3
"""
Enhanced MCP Data Loader - Properly reads ~/.ipfs_kit/ directory structure

This module provides improved data loading methods that read the actual
configuration files and data structures from ~/.ipfs_kit/ directory.
"""

import os
import json
import yaml
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class EnhancedMCPDataLoader:
    """Enhanced data loader for MCP dashboard that reads real ~/.ipfs_kit/ data."""
    
    def __init__(self, data_dir: str = "~/.ipfs_kit"):
        """Initialize with data directory."""
        self.data_dir = Path(data_dir).expanduser()
        
    async def get_backend_configs(self) -> Dict[str, Any]:
        """Load backend configurations from backend_configs directory."""
        backends = []
        backend_configs_dir = self.data_dir / "backend_configs"
        
        if backend_configs_dir.exists():
            for config_file in backend_configs_dir.glob("*.yaml"):
                try:
                    with open(config_file, 'r') as f:
                        config_data = yaml.safe_load(f)
                    
                    backend_name = config_file.stem
                    backend_info = {
                        "name": backend_name,
                        "file": str(config_file),
                        "type": self._determine_backend_type(config_data),
                        "enabled": config_data.get("enabled", True),
                        "config": config_data.get("config", {}),
                        "metadata": config_data.get("metadata", {}),
                        "created_at": config_data.get("created_at", ""),
                        "status": "configured",
                        "last_modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat()
                    }
                    backends.append(backend_info)
                    
                except Exception as e:
                    logger.error(f"Error loading backend config {config_file}: {e}")
                    
        return {"backends": backends}
    
    async def get_bucket_configs(self) -> Dict[str, Any]:
        """Load bucket configurations from bucket_configs directory."""
        buckets = []
        bucket_configs_dir = self.data_dir / "bucket_configs"
        
        if bucket_configs_dir.exists():
            for config_file in bucket_configs_dir.glob("*.yaml"):
                try:
                    with open(config_file, 'r') as f:
                        config_data = yaml.safe_load(f)
                    
                    bucket_name = config_data.get("bucket_name", config_file.stem)
                    bucket_info = {
                        "name": bucket_name,
                        "file": str(config_file),
                        "type": config_data.get("type", "general"),
                        "access": config_data.get("access", {}),
                        "backend_bindings": config_data.get("backend_bindings", []),
                        "backup": config_data.get("backup", {}),
                        "cache": config_data.get("cache", {}),
                        "compression": config_data.get("compression", {}),
                        "encryption": config_data.get("encryption", {}),
                        "features": config_data.get("features", {}),
                        "monitoring": config_data.get("monitoring", {}),
                        "network": config_data.get("network", {}),
                        "performance": config_data.get("performance", {}),
                        "storage": config_data.get("storage", {}),
                        "vfs": config_data.get("vfs", {}),
                        "created_at": config_data.get("created_at", ""),
                        "status": "configured",
                        "last_modified": datetime.fromtimestamp(config_file.stat().st_mtime).isoformat()
                    }
                    buckets.append(bucket_info)
                    
                except Exception as e:
                    logger.error(f"Error loading bucket config {config_file}: {e}")
                    
        return {"buckets": buckets}
    
    async def get_bucket_index_data(self) -> Dict[str, Any]:
        """Load bucket index data from bucket_index directory."""
        index_data = {}
        bucket_index_dir = self.data_dir / "bucket_index"
        
        if bucket_index_dir.exists():
            for index_file in bucket_index_dir.glob("*.json"):
                try:
                    with open(index_file, 'r') as f:
                        data = json.load(f)
                    
                    bucket_name = index_file.stem
                    index_data[bucket_name] = {
                        "name": bucket_name,
                        "file": str(index_file),
                        "index_data": data,
                        "last_modified": datetime.fromtimestamp(index_file.stat().st_mtime).isoformat()
                    }
                    
                except Exception as e:
                    logger.error(f"Error loading bucket index {index_file}: {e}")
                    
        return {"bucket_indices": index_data}
    
    async def get_pins_data(self) -> Dict[str, Any]:
        """Load pins data from pins directory."""
        pins = []
        pins_dir = self.data_dir / "pins"
        
        if pins_dir.exists():
            for pin_file in pins_dir.glob("*.json"):
                try:
                    with open(pin_file, 'r') as f:
                        pin_data = json.load(f)
                    
                    pin_info = {
                        "file": str(pin_file),
                        "data": pin_data,
                        "last_modified": datetime.fromtimestamp(pin_file.stat().st_mtime).isoformat()
                    }
                    pins.append(pin_info)
                    
                except Exception as e:
                    logger.error(f"Error loading pin data {pin_file}: {e}")
        
        # Also check pin_metadata directory
        pin_metadata_dir = self.data_dir / "pin_metadata"
        metadata_pins = []
        
        if pin_metadata_dir.exists():
            for metadata_file in pin_metadata_dir.glob("*.json"):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    metadata_info = {
                        "file": str(metadata_file),
                        "metadata": metadata,
                        "last_modified": datetime.fromtimestamp(metadata_file.stat().st_mtime).isoformat()
                    }
                    metadata_pins.append(metadata_info)
                    
                except Exception as e:
                    logger.error(f"Error loading pin metadata {metadata_file}: {e}")
                    
        return {"pins": pins, "pin_metadata": metadata_pins}
    
    async def get_service_configs(self) -> Dict[str, Any]:
        """Load service configurations from services directory."""
        services = []
        services_dir = self.data_dir / "services"
        
        if services_dir.exists():
            for service_file in services_dir.glob("*.json"):
                try:
                    with open(service_file, 'r') as f:
                        service_data = json.load(f)
                    
                    service_info = {
                        "name": service_file.stem,
                        "file": str(service_file),
                        "config": service_data,
                        "last_modified": datetime.fromtimestamp(service_file.stat().st_mtime).isoformat()
                    }
                    services.append(service_info)
                    
                except Exception as e:
                    logger.error(f"Error loading service config {service_file}: {e}")
                    
        return {"services": services}
    
    async def get_mcp_config(self) -> Dict[str, Any]:
        """Load MCP configuration."""
        mcp_config_file = self.data_dir / "mcp_config.json"
        
        if mcp_config_file.exists():
            try:
                with open(mcp_config_file, 'r') as f:
                    config_data = json.load(f)
                
                return {
                    "config": config_data,
                    "file": str(mcp_config_file),
                    "last_modified": datetime.fromtimestamp(mcp_config_file.stat().st_mtime).isoformat()
                }
            except Exception as e:
                logger.error(f"Error loading MCP config: {e}")
                
        return {"config": {}, "file": "", "last_modified": ""}
    
    async def get_vfs_data(self) -> Dict[str, Any]:
        """Load VFS data from unified_vfs.duckdb."""
        vfs_db_file = self.data_dir / "unified_vfs.duckdb"
        vfs_data = {"tables": [], "stats": {}}
        
        if vfs_db_file.exists():
            try:
                # Note: This would require duckdb, but for now we'll just return file info
                vfs_data = {
                    "file": str(vfs_db_file),
                    "size": vfs_db_file.stat().st_size,
                    "last_modified": datetime.fromtimestamp(vfs_db_file.stat().st_mtime).isoformat()
                }
            except Exception as e:
                logger.error(f"Error reading VFS database: {e}")
                
        return {"vfs_database": vfs_data}
    
    async def get_logs_data(self) -> Dict[str, Any]:
        """Load recent log data from logs directory."""
        logs = []
        logs_dir = self.data_dir / "logs"
        
        if logs_dir.exists():
            for log_file in sorted(logs_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                try:
                    # Read last 20 lines of each log file
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        recent_lines = lines[-20:] if len(lines) > 20 else lines
                    
                    log_info = {
                        "name": log_file.name,
                        "file": str(log_file),
                        "size": log_file.stat().st_size,
                        "recent_lines": [line.strip() for line in recent_lines],
                        "last_modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                    }
                    logs.append(log_info)
                    
                except Exception as e:
                    logger.error(f"Error reading log file {log_file}: {e}")
                    
        return {"logs": logs}
    
    def _determine_backend_type(self, config_data: Dict[str, Any]) -> str:
        """Determine backend type from configuration data."""
        config = config_data.get("config", {})
        
        if "bucket_name" in config and "region" in config:
            return "s3"
        elif "username" in config and "hostname" in config:
            return "sshfs"
        elif "repo_url" in config:
            return "github"
        elif "api_endpoint" in config and "storacha" in str(config.get("api_endpoint", "")):
            return "storacha"
        elif "base_url" in config:
            return "ftp"
        else:
            return "unknown"
