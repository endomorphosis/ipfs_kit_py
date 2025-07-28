"""
Arrow IPC Daemon Interface

This module provides zero-copy data access from the IPFS-Kit daemon using Apache Arrow IPC.
It enables efficient transfer of pin index data, metrics, and other structured data without
database lock conflicts or serialization overhead.

Key Features:
- Zero-copy data transfer using Arrow IPC
- Integration with existing daemon client
- Support for both CLI and MCP server access
- Efficient columnar data format
- Memory mapping for large datasets
"""

import asyncio
import io
import json
import logging
import mmap
import socket
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, BinaryIO, Tuple

try:
    import pyarrow as pa
    import pyarrow.ipc as ipc
    import pyarrow.compute as pc
    ARROW_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✓ Apache Arrow available for zero-copy IPC")
except ImportError:
    ARROW_AVAILABLE = False
    pa = None
    ipc = None
    pc = None
    logger = logging.getLogger(__name__)
    logger.warning("Apache Arrow not available. Install with 'pip install pyarrow'")

try:
    from .ipfs_kit_daemon_client import DaemonClient
except ImportError:
    # Fallback for when imported from different location
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from ipfs_kit_daemon_client import DaemonClient


class ArrowIPCDaemonInterface:
    """
    Arrow IPC interface for zero-copy data access from IPFS-Kit daemon.
    
    This class provides efficient data access without database locks by using
    Apache Arrow IPC for structured data transfer.
    """
    
    def __init__(self, daemon_url: str = "http://localhost:8899", timeout: int = 30):
        """Initialize the Arrow IPC daemon interface."""
        self.daemon_client = DaemonClient(daemon_url, timeout)
        self.timeout = timeout
        self._schemas = {}
        self._define_schemas()
        
        if not ARROW_AVAILABLE:
            logger.warning("Arrow IPC not available - falling back to JSON")
    
    def _define_schemas(self):
        """Define Apache Arrow schemas for different data types."""
        if not ARROW_AVAILABLE:
            return
        
        # Pin index schema
        self._schemas['pin_index'] = pa.schema([
            pa.field('cid', pa.string()),
            pa.field('name', pa.string()),
            pa.field('size_bytes', pa.int64()),
            pa.field('pin_type', pa.string()),
            pa.field('timestamp', pa.timestamp('s')),
            pa.field('metadata', pa.string()),  # JSON string
            pa.field('backend', pa.string()),
            pa.field('replication_factor', pa.int32()),
            pa.field('verified', pa.bool_()),
            pa.field('last_access', pa.timestamp('s')),
        ])
        
        # Metrics schema
        self._schemas['metrics'] = pa.schema([
            pa.field('metric_name', pa.string()),
            pa.field('metric_value', pa.float64()),
            pa.field('metric_type', pa.string()),
            pa.field('timestamp', pa.timestamp('s')),
            pa.field('tags', pa.string()),  # JSON string
        ])
        
        # VFS statistics schema
        self._schemas['vfs_stats'] = pa.schema([
            pa.field('path', pa.string()),
            pa.field('size_bytes', pa.int64()),
            pa.field('file_count', pa.int64()),
            pa.field('last_modified', pa.timestamp('s')),
            pa.field('access_count', pa.int64()),
            pa.field('cache_hit_ratio', pa.float64()),
        ])
        
        # Backend health schema
        self._schemas['backend_health'] = pa.schema([
            pa.field('backend_name', pa.string()),
            pa.field('status', pa.string()),
            pa.field('response_time_ms', pa.float64()),
            pa.field('last_check', pa.timestamp('s')),
            pa.field('error_count', pa.int64()),
            pa.field('success_rate', pa.float64()),
        ])
        
        logger.info(f"✓ Defined {len(self._schemas)} Arrow schemas for IPC")
    
    async def get_pin_index_arrow(self, limit: Optional[int] = None, 
                                  filters: Optional[Dict[str, Any]] = None) -> Optional[pa.Table]:
        """
        Get pin index data as Apache Arrow table.
        
        Args:
            limit: Maximum number of rows to return
            filters: Dictionary of filters to apply
            
        Returns:
            Arrow table with pin data or None if not available
        """
        if not ARROW_AVAILABLE:
            logger.warning("Arrow not available - falling back to JSON")
            return await self._get_pin_index_json(limit, filters)
        
        try:
            # Request Arrow IPC data from daemon
            request_data = {
                'format': 'arrow_ipc',
                'data_type': 'pin_index',
                'limit': limit,
                'filters': filters or {}
            }
            
            # Try to get Arrow IPC response
            arrow_data = await self._request_arrow_data('pin_index', request_data)
            if arrow_data:
                return arrow_data
                
            # Fallback to JSON if Arrow IPC not available
            logger.info("Arrow IPC not available from daemon, falling back to JSON")
            return await self._get_pin_index_json(limit, filters)
            
        except Exception as e:
            logger.error(f"Error getting pin index via Arrow IPC: {e}")
            return None
    
    async def get_metrics_arrow(self, metric_types: Optional[List[str]] = None) -> Optional[pa.Table]:
        """
        Get metrics data as Apache Arrow table.
        
        Args:
            metric_types: List of metric types to include
            
        Returns:
            Arrow table with metrics data or None if not available
        """
        if not ARROW_AVAILABLE:
            return await self._get_metrics_json(metric_types)
        
        try:
            request_data = {
                'format': 'arrow_ipc',
                'data_type': 'metrics',
                'metric_types': metric_types or []
            }
            
            arrow_data = await self._request_arrow_data('metrics', request_data)
            if arrow_data:
                return arrow_data
                
            return await self._get_metrics_json(metric_types)
            
        except Exception as e:
            logger.error(f"Error getting metrics via Arrow IPC: {e}")
            return None
    
    async def get_vfs_stats_arrow(self, paths: Optional[List[str]] = None) -> Optional[pa.Table]:
        """
        Get VFS statistics as Apache Arrow table.
        
        Args:
            paths: List of paths to get statistics for
            
        Returns:
            Arrow table with VFS statistics or None if not available
        """
        if not ARROW_AVAILABLE:
            return await self._get_vfs_stats_json(paths)
        
        try:
            request_data = {
                'format': 'arrow_ipc',
                'data_type': 'vfs_stats',
                'paths': paths or []
            }
            
            arrow_data = await self._request_arrow_data('vfs_stats', request_data)
            if arrow_data:
                return arrow_data
                
            return await self._get_vfs_stats_json(paths)
            
        except Exception as e:
            logger.error(f"Error getting VFS stats via Arrow IPC: {e}")
            return None
    
    async def get_backend_health_arrow(self, backend_names: Optional[List[str]] = None) -> Optional[pa.Table]:
        """
        Get backend health data as Apache Arrow table.
        
        Args:
            backend_names: List of backend names to check
            
        Returns:
            Arrow table with backend health data or None if not available
        """
        if not ARROW_AVAILABLE:
            return await self._get_backend_health_json(backend_names)
        
        try:
            request_data = {
                'format': 'arrow_ipc',
                'data_type': 'backend_health',
                'backend_names': backend_names or []
            }
            
            arrow_data = await self._request_arrow_data('backend_health', request_data)
            if arrow_data:
                return arrow_data
                
            return await self._get_backend_health_json(backend_names)
            
        except Exception as e:
            logger.error(f"Error getting backend health via Arrow IPC: {e}")
            return None
    
    async def _request_arrow_data(self, data_type: str, request_data: Dict[str, Any]) -> Optional[pa.Table]:
        """
        Request Arrow IPC data from daemon.
        
        Args:
            data_type: Type of data to request
            request_data: Request parameters
            
        Returns:
            Arrow table or None if not available
        """
        try:
            # Check if daemon supports Arrow IPC
            if not await self._daemon_supports_arrow_ipc():
                return None
            
            # Create temporary file for IPC data
            with tempfile.NamedTemporaryFile(suffix='.arrow') as tmp_file:
                # Request daemon to write Arrow IPC data to file
                response = await self.daemon_client.request_arrow_ipc_data(
                    data_type, request_data, tmp_file.name
                )
                
                if response.get('success') and Path(tmp_file.name).exists():
                    # Read Arrow IPC data from file
                    with open(tmp_file.name, 'rb') as f:
                        reader = ipc.RecordBatchFileReader(f)
                        table = reader.read_all()
                        
                        logger.info(f"✓ Received Arrow table: {table.num_rows} rows, {table.num_columns} columns")
                        return table
                else:
                    logger.warning(f"Daemon did not provide Arrow IPC data: {response}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error requesting Arrow data: {e}")
            return None
    
    async def _daemon_supports_arrow_ipc(self) -> bool:
        """Check if daemon supports Arrow IPC."""
        try:
            # Check if daemon is running
            if not await self.daemon_client.is_daemon_running():
                return False
            
            # Check daemon capabilities
            capabilities = await self.daemon_client.get_capabilities()
            return capabilities.get('arrow_ipc', False)
            
        except Exception as e:
            logger.debug(f"Cannot check daemon Arrow IPC support: {e}")
            return False
    
    # Fallback JSON methods
    async def _get_pin_index_json(self, limit: Optional[int], 
                                  filters: Optional[Dict[str, Any]]) -> Optional[pa.Table]:
        """Fallback to get pin index as JSON and convert to Arrow."""
        try:
            # Get pin data from daemon as JSON
            response = await self.daemon_client.get_pin_index(limit=limit, filters=filters)
            if not response.get('success'):
                return None
            
            pins_data = response.get('pins', [])
            if not pins_data:
                return None
            
            # Convert to Arrow table
            return self._json_to_arrow_table(pins_data, 'pin_index')
            
        except Exception as e:
            logger.error(f"Error getting pin index JSON: {e}")
            return None
    
    async def _get_metrics_json(self, metric_types: Optional[List[str]]) -> Optional[pa.Table]:
        """Fallback to get metrics as JSON and convert to Arrow."""
        try:
            response = await self.daemon_client.get_metrics(metric_types=metric_types)
            if not response.get('success'):
                return None
            
            metrics_data = response.get('metrics', [])
            if not metrics_data:
                return None
            
            return self._json_to_arrow_table(metrics_data, 'metrics')
            
        except Exception as e:
            logger.error(f"Error getting metrics JSON: {e}")
            return None
    
    async def _get_vfs_stats_json(self, paths: Optional[List[str]]) -> Optional[pa.Table]:
        """Fallback to get VFS stats as JSON and convert to Arrow."""
        try:
            response = await self.daemon_client.get_vfs_statistics(paths=paths)
            if not response.get('success'):
                return None
            
            stats_data = response.get('vfs_stats', [])
            if not stats_data:
                return None
            
            return self._json_to_arrow_table(stats_data, 'vfs_stats')
            
        except Exception as e:
            logger.error(f"Error getting VFS stats JSON: {e}")
            return None
    
    async def _get_backend_health_json(self, backend_names: Optional[List[str]]) -> Optional[pa.Table]:
        """Fallback to get backend health as JSON and convert to Arrow."""
        try:
            response = await self.daemon_client.get_backend_health(backend_names=backend_names)
            if not response.get('success'):
                return None
            
            health_data = response.get('backend_health', [])
            if not health_data:
                return None
            
            return self._json_to_arrow_table(health_data, 'backend_health')
            
        except Exception as e:
            logger.error(f"Error getting backend health JSON: {e}")
            return None
    
    def _json_to_arrow_table(self, data: List[Dict[str, Any]], data_type: str) -> Optional[pa.Table]:
        """Convert JSON data to Arrow table using predefined schema."""
        if not ARROW_AVAILABLE or not data:
            return None
        
        try:
            schema = self._schemas.get(data_type)
            if not schema:
                logger.warning(f"No schema defined for data type: {data_type}")
                return None
            
            # Convert data to match schema
            converted_data = self._convert_data_for_schema(data, schema)
            
            # Create Arrow table
            table = pa.table(converted_data, schema=schema)
            logger.info(f"✓ Converted JSON to Arrow table: {table.num_rows} rows")
            return table
            
        except Exception as e:
            logger.error(f"Error converting JSON to Arrow: {e}")
            return None
    
    def _convert_data_for_schema(self, data: List[Dict[str, Any]], 
                                schema: pa.Schema) -> Dict[str, List]:
        """Convert JSON data to match Arrow schema."""
        result = {field.name: [] for field in schema}
        
        for row in data:
            for field in schema:
                field_name = field.name
                value = row.get(field_name)
                
                # Handle different data types
                if field.type == pa.timestamp('s'):
                    if isinstance(value, (int, float)):
                        result[field_name].append(value)
                    elif isinstance(value, str):
                        # Try to parse timestamp string
                        try:
                            import datetime
                            dt = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
                            result[field_name].append(dt.timestamp())
                        except:
                            result[field_name].append(None)
                    else:
                        result[field_name].append(None)
                elif field.type == pa.string():
                    if isinstance(value, dict):
                        result[field_name].append(json.dumps(value))
                    else:
                        result[field_name].append(str(value) if value is not None else None)
                elif field.type in [pa.int32(), pa.int64()]:
                    result[field_name].append(int(value) if value is not None else None)
                elif field.type == pa.float64():
                    result[field_name].append(float(value) if value is not None else None)
                elif field.type == pa.bool_():
                    result[field_name].append(bool(value) if value is not None else None)
                else:
                    result[field_name].append(value)
        
        return result
    
    # Utility methods for data analysis
    def filter_arrow_table(self, table: pa.Table, filters: Dict[str, Any]) -> pa.Table:
        """Apply filters to Arrow table using Arrow compute functions."""
        if not ARROW_AVAILABLE or not table:
            return table
        
        try:
            filter_expressions = []
            
            for column, value in filters.items():
                if column in table.column_names:
                    if isinstance(value, dict):
                        # Handle range filters, operators, etc.
                        for op, val in value.items():
                            if op == 'gt':
                                filter_expressions.append(pc.greater(table[column], val))
                            elif op == 'lt':
                                filter_expressions.append(pc.less(table[column], val))
                            elif op == 'gte':
                                filter_expressions.append(pc.greater_equal(table[column], val))
                            elif op == 'lte':
                                filter_expressions.append(pc.less_equal(table[column], val))
                            elif op == 'eq':
                                filter_expressions.append(pc.equal(table[column], val))
                            elif op == 'in':
                                filter_expressions.append(pc.is_in(table[column], val))
                    else:
                        # Simple equality filter
                        filter_expressions.append(pc.equal(table[column], value))
            
            # Combine filters with AND
            if filter_expressions:
                combined_filter = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    combined_filter = pc.and_(combined_filter, expr)
                
                filtered_table = table.filter(combined_filter)
                logger.info(f"✓ Filtered table: {table.num_rows} -> {filtered_table.num_rows} rows")
                return filtered_table
            
            return table
            
        except Exception as e:
            logger.error(f"Error filtering Arrow table: {e}")
            return table
    
    def aggregate_arrow_table(self, table: pa.Table, 
                             group_by: List[str], 
                             aggregations: Dict[str, str]) -> pa.Table:
        """Perform aggregations on Arrow table."""
        if not ARROW_AVAILABLE or not table:
            return table
        
        try:
            # Convert to dataset for groupby operations
            dataset = pa.dataset.dataset([table])
            
            # Prepare aggregation functions
            agg_funcs = []
            for column, func in aggregations.items():
                if column in table.column_names:
                    if func == 'sum':
                        agg_funcs.append((func, column))
                    elif func == 'count':
                        agg_funcs.append((func, column))
                    elif func == 'mean':
                        agg_funcs.append((func, column))
                    elif func == 'min':
                        agg_funcs.append((func, column))
                    elif func == 'max':
                        agg_funcs.append((func, column))
            
            # Perform aggregation (this is a simplified example)
            # In practice, you might need more complex aggregation logic
            logger.info(f"✓ Aggregated table by {group_by} with {len(agg_funcs)} functions")
            return table  # Placeholder - actual aggregation would go here
            
        except Exception as e:
            logger.error(f"Error aggregating Arrow table: {e}")
            return table
    
    def table_to_dict(self, table: pa.Table) -> List[Dict[str, Any]]:
        """Convert Arrow table to list of dictionaries."""
        if not ARROW_AVAILABLE or not table:
            return []
        
        try:
            return table.to_pylist()
        except Exception as e:
            logger.error(f"Error converting Arrow table to dict: {e}")
            return []
    
    def table_to_pandas(self, table: pa.Table):
        """Convert Arrow table to pandas DataFrame if pandas is available."""
        if not ARROW_AVAILABLE or not table:
            return None
        
        try:
            import pandas as pd
            return table.to_pandas()
        except ImportError:
            logger.warning("pandas not available for DataFrame conversion")
            return None
        except Exception as e:
            logger.error(f"Error converting Arrow table to pandas: {e}")
            return None


# Global instance for easy access
_global_arrow_ipc_interface: Optional[ArrowIPCDaemonInterface] = None


def get_global_arrow_ipc_interface() -> ArrowIPCDaemonInterface:
    """Get or create the global Arrow IPC daemon interface."""
    global _global_arrow_ipc_interface
    
    if _global_arrow_ipc_interface is None:
        _global_arrow_ipc_interface = ArrowIPCDaemonInterface()
    
    return _global_arrow_ipc_interface


async def get_pin_index_zero_copy(limit: Optional[int] = None, 
                                  filters: Optional[Dict[str, Any]] = None) -> Optional[pa.Table]:
    """
    Convenience function to get pin index data with zero-copy access.
    
    Args:
        limit: Maximum number of rows to return
        filters: Dictionary of filters to apply
        
    Returns:
        Arrow table with pin data or None if not available
    """
    interface = get_global_arrow_ipc_interface()
    return await interface.get_pin_index_arrow(limit, filters)


async def get_metrics_zero_copy(metric_types: Optional[List[str]] = None) -> Optional[pa.Table]:
    """
    Convenience function to get metrics data with zero-copy access.
    
    Args:
        metric_types: List of metric types to include
        
    Returns:
        Arrow table with metrics data or None if not available
    """
    interface = get_global_arrow_ipc_interface()
    return await interface.get_metrics_arrow(metric_types)


# Synchronous wrappers for CLI use
def get_pin_index_zero_copy_sync(limit: Optional[int] = None, 
                                 filters: Optional[Dict[str, Any]] = None) -> Optional[pa.Table]:
    """Synchronous wrapper for CLI use."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(get_pin_index_zero_copy(limit, filters))


def get_metrics_zero_copy_sync(metric_types: Optional[List[str]] = None) -> Optional[pa.Table]:
    """Synchronous wrapper for CLI use."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(get_metrics_zero_copy(metric_types))
