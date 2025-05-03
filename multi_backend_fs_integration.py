#!/usr/bin/env python3
"""
Multi-Backend Filesystem Integration for IPFS Kit

This module integrates various storage backends (HuggingFace, S3, Filecoin, Storacha, etc.)
with the FS Journal virtual filesystem, providing a unified interface for working with
content across different storage systems.

Features:
- Backend-specific virtual path mappings
- Content prefetching
- Cross-backend search
- Data format conversions (Parquet, Arrow)
- Transparent caching and synchronization
"""

import os
import sys
import json
import logging
import asyncio
import importlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import FS Journal components
try:
    from fs_journal_tools import (
        FSJournal, FSOperation, FSOperationType, IPFSFSBridge,
        create_journal_and_bridge
    )
except ImportError as e:
    logger.error(f"Failed to import FS Journal components: {e}")
    raise

# Storage backend types
class StorageBackendType(Enum):
    """Types of storage backends supported by the multi-backend filesystem"""
    IPFS = auto()
    HUGGINGFACE = auto()
    S3 = auto()
    FILECOIN = auto()
    STORACHA = auto()
    LASSIE = auto()
    IPFS_CLUSTER = auto()
    LOCAL = auto()
    CUSTOM = auto()

@dataclass
class BackendConfig:
    """Configuration for a storage backend"""
    backend_type: StorageBackendType
    name: str
    root_path: str  # Virtual root path for this backend
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    prefetch_enabled: bool = False
    prefetch_depth: int = 1
    controller: Any = None  # Reference to the controller instance

@dataclass
class DataFormat:
    """Data format information"""
    format_type: str  # e.g., 'parquet', 'arrow', 'json', 'csv', etc.
    schema: Optional[Dict[str, Any]] = None
    compression: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class MultiBackendFS:
    """
    Multi-Backend Filesystem that integrates various storage backends
    with the FS Journal virtual filesystem
    """
    
    def __init__(self, base_dir: str):
        """Initialize the multi-backend filesystem"""
        self.base_dir = os.path.abspath(base_dir)
        
        # Initialize FS Journal and IPFS-FS Bridge
        self.journal, self.ipfs_bridge = create_journal_and_bridge(base_dir)
        
        # Backend configurations
        self.backends: Dict[str, BackendConfig] = {}
        
        # Path mappings: backend_path -> local_path
        self.path_mappings: Dict[str, str] = {}
        
        # Format handlers: format_type -> (encoder, decoder)
        self.format_handlers: Dict[str, Tuple[Callable, Callable]] = {}
        
        # Search index
        self.search_index: Dict[str, List[str]] = {}  # keyword -> [paths]
        
        # Initialize default format handlers
        self._init_format_handlers()
        
        logger.info(f"Initialized Multi-Backend Filesystem with base directory: {base_dir}")
    
    def _init_format_handlers(self):
        """Initialize default format handlers"""
        # JSON format handler
        self.register_format_handler(
            'json',
            lambda data, **kwargs: json.dumps(data, **kwargs).encode('utf-8'),
            lambda data, **kwargs: json.loads(data.decode('utf-8'), **kwargs)
        )
        
        # Try to register Parquet and Arrow handlers if available
        try:
            import pandas as pd
            import pyarrow as pa
            import pyarrow.parquet as pq
            import io
            
            # Parquet format handler
            self.register_format_handler(
                'parquet',
                lambda data, **kwargs: pq.write_table(
                    pa.Table.from_pandas(pd.DataFrame(data)),
                    io.BytesIO()
                ).getvalue(),
                lambda data, **kwargs: pq.read_table(
                    io.BytesIO(data)
                ).to_pandas().to_dict('records')
            )
            
            # Arrow format handler
            self.register_format_handler(
                'arrow',
                lambda data, **kwargs: pa.serialize_pandas(
                    pd.DataFrame(data)
                ).to_buffer().to_pybytes(),
                lambda data, **kwargs: pa.deserialize_pandas(data).to_dict('records')
            )
            
            logger.info("Registered Parquet and Arrow format handlers")
        except ImportError:
            logger.warning("Pandas or PyArrow not available, Parquet and Arrow formats not supported")
    
    def register_backend(self, config: BackendConfig) -> bool:
        """Register a storage backend"""
        if config.name in self.backends:
            logger.warning(f"Backend '{config.name}' already registered")
            return False
        
        self.backends[config.name] = config
        logger.info(f"Registered backend: {config.name} ({config.backend_type.name}) at {config.root_path}")
        return True
    
    def get_backend_for_path(self, path: str) -> Optional[BackendConfig]:
        """Get the backend configuration for a path"""
        for name, config in self.backends.items():
            if path.startswith(config.root_path):
                return config
        return None
    
    def map_path(self, backend_path: str, local_path: str) -> Dict[str, Any]:
        """Map a backend path to a local filesystem path"""
        # Normalize paths
        norm_backend_path = backend_path.rstrip('/')
        norm_local_path = os.path.normpath(local_path)
        
        # Get the backend for this path
        backend = self.get_backend_for_path(norm_backend_path)
        if not backend:
            error_msg = f"No backend registered for path: {norm_backend_path}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Create mapping
        self.path_mappings[norm_backend_path] = norm_local_path
        
        # Ensure path is tracked
        self.journal.track_path(norm_local_path)
        
        # If this is an IPFS path, also map in the IPFS bridge
        if backend.backend_type == StorageBackendType.IPFS:
            # Extract the IPFS-specific part of the path
            ipfs_path = norm_backend_path[len(backend.root_path):]
            if not ipfs_path:
                ipfs_path = '/'
            
            self.ipfs_bridge.map_path(ipfs_path, norm_local_path)
        
        # If prefetching is enabled for this backend, trigger it
        if backend.prefetch_enabled:
            asyncio.create_task(self._prefetch_content(
                norm_backend_path, 
                norm_local_path, 
                backend,
                depth=backend.prefetch_depth
            ))
        
        logger.info(f"Mapped backend path {norm_backend_path} to local path {norm_local_path}")
        return {
            "success": True,
            "backend_path": norm_backend_path,
            "local_path": norm_local_path,
            "backend": backend.name
        }
    
    def unmap_path(self, backend_path: str) -> Dict[str, Any]:
        """Remove a mapping between backend and local filesystem"""
        norm_backend_path = backend_path.rstrip('/')
        
        if norm_backend_path in self.path_mappings:
            local_path = self.path_mappings[norm_backend_path]
            del self.path_mappings[norm_backend_path]
            
            # Get the backend for this path
            backend = self.get_backend_for_path(norm_backend_path)
            if backend and backend.backend_type == StorageBackendType.IPFS:
                # Extract the IPFS-specific part of the path
                ipfs_path = norm_backend_path[len(backend.root_path):]
                if not ipfs_path:
                    ipfs_path = '/'
                
                self.ipfs_bridge.unmap_path(ipfs_path)
            
            logger.info(f"Unmapped backend path {norm_backend_path} from local path {local_path}")
            return {
                "success": True,
                "backend_path": norm_backend_path,
                "local_path": local_path
            }
        else:
            logger.warning(f"Backend path {norm_backend_path} not found in mappings")
            return {
                "success": False,
                "error": f"Backend path {norm_backend_path} not found in mappings"
            }
    
    def list_mappings(self) -> Dict[str, Any]:
        """List all mappings between backends and local filesystem"""
        mappings = []
        for backend_path, local_path in self.path_mappings.items():
            backend = self.get_backend_for_path(backend_path)
            mappings.append({
                "backend_path": backend_path,
                "local_path": local_path,
                "backend": backend.name if backend else "unknown"
            })
        
        return {
            "success": True,
            "count": len(mappings),
            "mappings": mappings
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of the multi-backend filesystem"""
        return {
            "success": True,
            "backends_count": len(self.backends),
            "mappings_count": len(self.path_mappings),
            "tracked_paths_count": len(self.journal.tracked_paths),
            "format_handlers_count": len(self.format_handlers),
            "search_index_size": len(self.search_index)
        }
    
    async def _prefetch_content(
        self, 
        backend_path: str, 
        local_path: str, 
        backend: BackendConfig,
        depth: int = 1
    ) -> None:
        """Prefetch content from a backend path"""
        if depth <= 0:
            return
        
        logger.info(f"Prefetching content from {backend_path} (depth={depth})")
        
        try:
            # The actual prefetching implementation would depend on the backend type
            # Here we just create the directory structure
            os.makedirs(local_path, exist_ok=True)
            
            # For demonstration, create a metadata file
            metadata_path = os.path.join(local_path, '.metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump({
                    "backend": backend.name,
                    "backend_path": backend_path,
                    "prefetched_at": datetime.now(timezone.utc).isoformat(),
                    "prefetch_depth": depth
                }, f)
            
            # Record operation
            self.journal.record_operation(FSOperation(
                operation_type=FSOperationType.WRITE,
                path=metadata_path,
                metadata={"prefetch": True}
            ))
            
            logger.info(f"Prefetched content from {backend_path} to {local_path}")
        except Exception as e:
            logger.error(f"Error prefetching content from {backend_path}: {e}")
    
    def register_format_handler(
        self, 
        format_type: str, 
        encoder: Callable, 
        decoder: Callable
    ) -> None:
        """Register a format handler"""
        self.format_handlers[format_type] = (encoder, decoder)
        logger.info(f"Registered format handler for {format_type}")
    
    def convert_format(
        self, 
        data: Any, 
        source_format: str, 
        target_format: str,
        **kwargs
    ) -> Any:
        """Convert data from one format to another"""
        if source_format not in self.format_handlers:
            raise ValueError(f"Source format {source_format} not supported")
        
        if target_format not in self.format_handlers:
            raise ValueError(f"Target format {target_format} not supported")
        
        # If source and target are the same, do nothing
        if source_format == target_format:
            return data
        
        # Decode from source format
        _, source_decoder = self.format_handlers[source_format]
        decoded_data = source_decoder(data, **kwargs)
        
        # Encode to target format
        target_encoder, _ = self.format_handlers[target_format]
        encoded_data = target_encoder(decoded_data, **kwargs)
        
        return encoded_data
    
    def index_content(self, path: str, content: Union[str, bytes]) -> None:
        """Index content for search"""
        if isinstance(content, bytes):
            try:
                content = content.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning(f"Cannot index binary content at {path}")
                return
        
        # Simple tokenization for indexing
        words = content.lower().split()
        unique_words = set(words)
        
        # Add to index
        for word in unique_words:
            if word not in self.search_index:
                self.search_index[word] = []
            if path not in self.search_index[word]:
                self.search_index[word].append(path)
        
        logger.debug(f"Indexed {len(unique_words)} unique words from {path}")
    
    def search(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Search indexed content"""
        query_words = query.lower().split()
        results = {}
        
        for word in query_words:
            if word in self.search_index:
                for path in self.search_index[word]:
                    if path not in results:
                        results[path] = 0
                    results[path] += 1
        
        # Sort by relevance (number of query words matched)
        sorted_results = sorted(
            results.items(), 
            key=lambda item: item[1], 
            reverse=True
        )
        
        # Limit results
        limited_results = sorted_results[:limit]
        
        return {
            "success": True,
            "query": query,
            "total_results": len(sorted_results),
            "results": [
                {"path": path, "relevance": relevance}
                for path, relevance in limited_results
            ]
        }
    
    def sync_all(self) -> Dict[str, Any]:
        """Synchronize all mapped paths"""
        result = {
            "success": True,
            "synced": 0,
            "errors": []
        }
        
        for backend_path, local_path in self.path_mappings.items():
            try:
                # Get the backend for this path
                backend = self.get_backend_for_path(backend_path)
                if not backend:
                    error_msg = f"No backend registered for path: {backend_path}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
                    continue
                
                # Sync local path to disk
                sync_result = self.journal.sync_to_disk(local_path)
                result["synced"] += sync_result["synced_files"]
                
                if not sync_result["success"]:
                    result["errors"].extend(sync_result["errors"])
            except Exception as e:
                error_msg = f"Error syncing {backend_path}: {e}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        result["success"] = len(result["errors"]) == 0
        logger.info(f"Synced {result['synced']} files with {len(result['errors'])} errors")
        return result

# MCP integration functions

async def init_huggingface_backend(ctx, name: str = "huggingface", root_path: str = "/hf") -> Dict[str, Any]:
    """Initialize HuggingFace backend"""
    try:
        from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController
        
        # Create Multi-Backend FS instance if not already created
        if not hasattr(ctx.server, "multi_backend_fs"):
            ctx.server.multi_backend_fs = MultiBackendFS(os.getcwd())
        
        fs = ctx.server.multi_backend_fs
        
        # Create HuggingFace controller if not already available
        if not hasattr(ctx.server, "huggingface_controller"):
            # In a real implementation, this would properly initialize the controller
            # For now, we'll just create a dummy instance
            ctx.server.huggingface_controller = HuggingFaceController()
        
        # Register HuggingFace backend
        config = BackendConfig(
            backend_type=StorageBackendType.HUGGINGFACE,
            name=name,
            root_path=root_path,
            controller=ctx.server.huggingface_controller,
            prefetch_enabled=True,
            prefetch_depth=1
        )
        
        fs.register_backend(config)
        
        await ctx.info(f"Initialized HuggingFace backend: {name} at {root_path}")
        return {
            "success": True,
            "backend": name,
            "root_path": root_path
        }
    except Exception as e:
        error_msg = f"Error initializing HuggingFace backend: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def init_filecoin_backend(ctx, name: str = "filecoin", root_path: str = "/fil") -> Dict[str, Any]:
    """Initialize Filecoin backend"""
    try:
        from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
        
        # Create Multi-Backend FS instance if not already created
        if not hasattr(ctx.server, "multi_backend_fs"):
            ctx.server.multi_backend_fs = MultiBackendFS(os.getcwd())
        
        fs = ctx.server.multi_backend_fs
        
        # Create Filecoin controller if not already available
        if not hasattr(ctx.server, "filecoin_controller"):
            # In a real implementation, this would properly initialize the controller
            # For now, we'll just create a dummy instance
            ctx.server.filecoin_controller = FilecoinController()
        
        # Register Filecoin backend
        config = BackendConfig(
            backend_type=StorageBackendType.FILECOIN,
            name=name,
            root_path=root_path,
            controller=ctx.server.filecoin_controller,
            prefetch_enabled=False  # Typically don't prefetch from Filecoin due to cost
        )
        
        fs.register_backend(config)
        
        await ctx.info(f"Initialized Filecoin backend: {name} at {root_path}")
        return {
            "success": True,
            "backend": name,
            "root_path": root_path
        }
    except Exception as e:
        error_msg = f"Error initializing Filecoin backend: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def init_s3_backend(ctx, name: str = "s3", root_path: str = "/s3", bucket: str = None) -> Dict[str, Any]:
    """Initialize S3 backend"""
    try:
        from ipfs_kit_py.mcp.controllers.storage.s3_controller import S3Controller
        
        # Create Multi-Backend FS instance if not already created
        if not hasattr(ctx.server, "multi_backend_fs"):
            ctx.server.multi_backend_fs = MultiBackendFS(os.getcwd())
        
        fs = ctx.server.multi_backend_fs
        
        # Create S3 controller if not already available
        if not hasattr(ctx.server, "s3_controller"):
            # In a real implementation, this would properly initialize the controller
            # For now, we'll just create a dummy instance
            ctx.server.s3_controller = S3Controller()
        
        # Register S3 backend
        config = BackendConfig(
            backend_type=StorageBackendType.S3,
            name=name,
            root_path=root_path,
            controller=ctx.server.s3_controller,
            config={"bucket": bucket} if bucket else {},
            prefetch_enabled=True
        )
        
        fs.register_backend(config)
        
        await ctx.info(f"Initialized S3 backend: {name} at {root_path}")
        return {
            "success": True,
            "backend": name,
            "root_path": root_path
        }
    except Exception as e:
        error_msg = f"Error initializing S3 backend: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def init_storacha_backend(ctx, name: str = "storacha", root_path: str = "/storacha") -> Dict[str, Any]:
    """Initialize Storacha backend"""
    try:
        from ipfs_kit_py.mcp.controllers.storage.storacha_controller import StorachaController
        
        # Create Multi-Backend FS instance if not already created
        if not hasattr(ctx.server, "multi_backend_fs"):
            ctx.server.multi_backend_fs = MultiBackendFS(os.getcwd())
        
        fs = ctx.server.multi_backend_fs
        
        # Create Storacha controller if not already available
        if not hasattr(ctx.server, "storacha_controller"):
            # In a real implementation, this would properly initialize the controller
            # For now, we'll just create a dummy instance
            ctx.server.storacha_controller = StorachaController()
        
        # Register Storacha backend
        config = BackendConfig(
            backend_type=StorageBackendType.STORACHA,
            name=name,
            root_path=root_path,
            controller=ctx.server.storacha_controller,
            prefetch_enabled=True
        )
        
        fs.register_backend(config)
        
        await ctx.info(f"Initialized Storacha backend: {name} at {root_path}")
        return {
            "success": True,
            "backend": name,
            "root_path": root_path
        }
    except Exception as e:
        error_msg = f"Error initializing Storacha backend: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def init_ipfs_cluster_backend(ctx, name: str = "ipfs_cluster", root_path: str = "/ipfs_cluster") -> Dict[str, Any]:
    """Initialize IPFS Cluster backend"""
    # Note: This is a placeholder implementation since IPFS Cluster controller might not exist yet
    try:
        # Create Multi-Backend FS instance if not already created
        if not hasattr(ctx.server, "multi_backend_fs"):
            ctx.server.multi_backend_fs = MultiBackendFS(os.getcwd())
        
        fs = ctx.server.multi_backend_fs
        
        # Register IPFS Cluster backend (using a mock controller for now)
        config = BackendConfig(
            backend_type=StorageBackendType.IPFS_CLUSTER,
            name=name,
            root_path=root_path,
            controller=None,  # Would be replaced with actual controller
            prefetch_enabled=True
        )
        
        fs.register_backend(config)
        
        await ctx.info(f"Initialized IPFS Cluster backend: {name} at {root_path}")
        return {
            "success": True,
            "backend": name,
            "root_path": root_path
        }
    except Exception as e:
        error_msg = f"Error initializing IPFS Cluster backend: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

# Generic handlers for MCP tools

async def multi_backend_map_handler(
    ctx, 
    backend_path: str, 
    local_path: str
) -> Dict[str, Any]:
    """Handle mapping backend path to local path"""
    try:
        if not hasattr(ctx.server, "multi_backend_fs"):
            error_msg = "Multi-Backend FS not initialized"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        fs = ctx.server.multi_backend_fs
        result = fs.map_path(backend_path, local_path)
        
        if result["success"]:
            await ctx.info(f"Mapped {backend_path} to {local_path}")
        else:
            await ctx.error(f"Failed to map {backend_path}: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        error_msg = f"Error mapping path: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def multi_backend_unmap_handler(ctx, backend_path: str) -> Dict[str, Any]:
    """Handle unmapping backend path"""
    try:
        if not hasattr(ctx.server, "multi_backend_fs"):
            error_msg = "Multi-Backend FS not initialized"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        fs = ctx.server.multi_backend_fs
        result = fs.unmap_path(backend_path)
        
        if result["success"]:
            await ctx.info(f"Unmapped {backend_path}")
        else:
            await ctx.error(f"Failed to unmap {backend_path}: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        error_msg = f"Error unmapping path: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def multi_backend_list_mappings_handler(ctx) -> Dict[str, Any]:
    """Handle listing mappings"""
    try:
        if not hasattr(ctx.server, "multi_backend_fs"):
            error_msg = "Multi-Backend FS not initialized"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        fs = ctx.server.multi_backend_fs
        result = fs.list_mappings()
        
        await ctx.info(f"Listed {result['count']} mappings")
        return result
    except Exception as e:
        error_msg = f"Error listing mappings: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def multi_backend_status_handler(ctx) -> Dict[str, Any]:
    """Handle getting status"""
    try:
        if not hasattr(ctx.server, "multi_backend_fs"):
            error_msg = "Multi-Backend FS not initialized"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        fs = ctx.server.multi_backend_fs
        result = fs.get_status()
        
        await ctx.info(f"Got status: {result['backends_count']} backends, {result['mappings_count']} mappings")
        return result
    except Exception as e:
        error_msg = f"Error getting status: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def multi_backend_sync_handler(ctx) -> Dict[str, Any]:
    """Handle syncing all backends"""
    try:
        if not hasattr(ctx.server, "multi_backend_fs"):
            error_msg = "Multi-Backend FS not initialized"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        fs = ctx.server.multi_backend_fs
        result = fs.sync_all()
        
        await ctx.info(f"Synced {result['synced']} files with {len(result['errors'])} errors")
        return result
    except Exception as e:
        error_msg = f"Error syncing: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def multi_backend_search_handler(ctx, query: str, limit: int = 100) -> Dict[str, Any]:
    """Handle search"""
    try:
        if not hasattr(ctx.server, "multi_backend_fs"):
            error_msg = "Multi-Backend FS not initialized"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        fs = ctx.server.multi_backend_fs
        result = fs.search(query, limit)
        
        await ctx.info(f"Search for '{query}' found {result['total_results']} results")
        return result
    except Exception as e:
        error_msg = f"Error searching: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def multi_backend_convert_format_handler(
    ctx, 
    path: str, 
    source_format: str, 
    target_format: str
) -> Dict[str, Any]:
    """Handle format conversion"""
    try:
        if not hasattr(ctx.server, "multi_backend_fs"):
            error_msg = "Multi-Backend FS not initialized"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        fs = ctx.server.multi_backend_fs
        
        # Check if path exists
        if not os.path.exists(path):
            error_msg = f"Path does not exist: {path}"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Read the file
        with open(path, 'rb') as f:
            file_data = f.read()
        
        # Convert the format
        try:
            converted_data = fs.convert_format(file_data, source_format, target_format)
            
            # Create the output path (append the target format extension)
            base_path, _ = os.path.splitext(path)
            output_path = f"{base_path}.{target_format}"
            
            # Write the converted data
            with open(output_path, 'wb') as f:
                f.write(converted_data)
            
            await ctx.info(f"Converted {path} from {source_format} to {target_format} and saved to {output_path}")
            return {
                "success": True,
                "source_path": path,
                "source_format": source_format,
                "target_format": target_format,
                "output_path": output_path
            }
        except ValueError as ve:
            error_msg = f"Format conversion error: {str(ve)}"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Error converting format: {e}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

def register_multi_backend_tools(server) -> bool:
    """Register Multi-Backend FS tools with MCP server"""
    try:
        # Create Multi-Backend FS instance if not already created
        if not hasattr(server, "multi_backend_fs"):
            server.multi_backend_fs = MultiBackendFS(os.getcwd())
        
        # Register backend initialization tools
        server.tool(name="init_huggingface_backend", 
                   description="Initialize HuggingFace backend for the virtual filesystem")(init_huggingface_backend)
        
        server.tool(name="init_filecoin_backend",
                   description="Initialize Filecoin backend for the virtual filesystem")(init_filecoin_backend)
        
        server.tool(name="init_s3_backend",
                   description="Initialize S3 backend for the virtual filesystem")(init_s3_backend)
        
        server.tool(name="init_storacha_backend",
                   description="Initialize Storacha backend for the virtual filesystem")(init_storacha_backend)
        
        server.tool(name="init_ipfs_cluster_backend",
                   description="Initialize IPFS Cluster backend for the virtual filesystem")(init_ipfs_cluster_backend)
        
        # Register generic tools
        server.tool(name="multi_backend_map",
                   description="Map a backend path to a local filesystem path")(multi_backend_map_handler)
        
        server.tool(name="multi_backend_unmap",
                   description="Remove a mapping between backend and local filesystem")(multi_backend_unmap_handler)
        
        server.tool(name="multi_backend_list_mappings",
                   description="List all mappings between backends and local filesystem")(multi_backend_list_mappings_handler)
        
        server.tool(name="multi_backend_status",
                   description="Get status of the multi-backend filesystem")(multi_backend_status_handler)
        
        server.tool(name="multi_backend_sync",
                   description="Synchronize all mapped paths")(multi_backend_sync_handler)
        
        server.tool(name="multi_backend_search",
                   description="Search indexed content")(multi_backend_search_handler)
        
        server.tool(name="multi_backend_convert_format",
                   description="Convert a file from one format to another")(multi_backend_convert_format_handler)
        
        logger.info("✅ Successfully registered Multi-Backend FS tools with MCP server")
        return True
    except Exception as e:
        logger.error(f"Failed to register Multi-Backend FS tools: {e}")
        return False

if __name__ == "__main__":
    # For testing/demonstration
    fs = MultiBackendFS(os.getcwd())
    
    # Register some backends
    fs.register_backend(BackendConfig(
        backend_type=StorageBackendType.IPFS,
        name="ipfs_main",
        root_path="/ipfs"
    ))
    
    fs.register_backend(BackendConfig(
        backend_type=StorageBackendType.HUGGINGFACE,
        name="huggingface_models",
        root_path="/hf"
    ))
    
    fs.register_backend(BackendConfig(
        backend_type=StorageBackendType.S3,
        name="s3_storage",
        root_path="/s3",
        config={"bucket": "test-bucket"}
    ))
    
    # Print status
    print(json.dumps(fs.get_status(), indent=2))
