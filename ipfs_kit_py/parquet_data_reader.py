#!/usr/bin/env python3
"""
Parquet Data Access Layer for IPFS-Kit CLI

This module provides content-addressed, lock-free access to IPFS-Kit data
stored in Parquet format. Designed to avoid database lock conflicts while
providing real-time access to pins, WAL operations, and FS journal data.
"""

import pandas as pd
import glob
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json


class ParquetDataReader:
    """Lock-free data access using Parquet files as the source of truth."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / '.ipfs_kit'
        
    def read_pins(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Read pin data from Parquet files."""
        try:
            # Try multiple possible pin data locations
            pin_sources = [
                self.base_path / 'pin_metadata' / 'parquet_storage' / 'pins.parquet',
                self.base_path / 'enhanced_pin_index' / 'enhanced_pins.parquet',
                self.base_path / 'pin_metadata' / 'pins.parquet'
            ]
            
            for source in pin_sources:
                if source.exists():
                    try:
                        df = pd.read_parquet(source)
                        if len(df) > 0:
                            # Apply limit if specified
                            if limit:
                                df = df.head(limit)
                            
                            pins = []
                            for _, row in df.iterrows():
                                pin_data = {
                                    'cid': row.get('cid', ''),
                                    'name': row.get('name', ''),
                                    'pin_type': row.get('pin_type', row.get('type', 'recursive')),
                                    'timestamp': row.get('timestamp', row.get('last_updated', '')),
                                    'size_bytes': row.get('size_bytes', 0),
                                    'vfs_path': row.get('vfs_path', ''),
                                    'mount_point': row.get('mount_point', ''),
                                    'access_count': row.get('access_count', 0),
                                    'last_accessed': row.get('last_accessed', ''),
                                    'storage_tiers': row.get('storage_tiers', []),
                                    'primary_tier': row.get('primary_tier', ''),
                                    'replication_factor': row.get('replication_factor', 1),
                                    'content_hash': row.get('content_hash', ''),
                                    'integrity_status': row.get('integrity_status', 'unknown')
                                }
                                pins.append(pin_data)
                            
                            return {
                                'success': True,
                                'pins': pins,
                                'source': str(source),
                                'total_count': len(df),
                                'method': 'parquet_direct'
                            }
                    except Exception as e:
                        print(f"⚠️  Error reading {source}: {e}")
                        continue
            
            return {
                'success': False,
                'error': 'No readable pin Parquet files found',
                'pins': []
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Parquet read error: {e}',
                'pins': []
            }
    
    def read_wal_operations(self, limit: Optional[int] = None, 
                           status_filter: Optional[str] = None) -> Dict[str, Any]:
        """Read WAL operations from Parquet files."""
        try:
            wal_pattern = str(self.base_path / 'wal' / 'data' / '**' / '*.parquet')
            wal_files = glob.glob(wal_pattern, recursive=True)
            
            if not wal_files:
                return {
                    'success': False,
                    'error': 'No WAL Parquet files found',
                    'operations': []
                }
            
            # Read and combine all WAL files
            all_operations = []
            for file_path in wal_files:
                try:
                    df = pd.read_parquet(file_path)
                    
                    # Apply status filter if specified
                    if status_filter:
                        df = df[df['status'] == status_filter]
                    
                    for _, row in df.iterrows():
                        operation = {
                            'id': row.get('id', ''),
                            'operation_type': row.get('operation_type', ''),
                            'backend_type': row.get('backend_type', ''),
                            'status': row.get('status', ''),
                            'created_at': row.get('created_at', ''),
                            'updated_at': row.get('updated_at', ''),
                            'path': row.get('path', ''),
                            'size': row.get('size', 0),
                            'retry_count': row.get('retry_count', 0),
                            'error_message': row.get('error_message', ''),
                            'duration_ms': row.get('duration_ms', 0),
                            'metadata': self._parse_json_field(row.get('metadata_json', '{}'))
                        }
                        all_operations.append(operation)
                        
                except Exception as e:
                    print(f"⚠️  Error reading WAL file {file_path}: {e}")
                    continue
            
            # Sort by timestamp (most recent first)
            all_operations.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            # Apply limit if specified
            if limit:
                all_operations = all_operations[:limit]
            
            return {
                'success': True,
                'operations': all_operations,
                'sources': wal_files,
                'total_count': len(all_operations),
                'method': 'parquet_direct'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'WAL Parquet read error: {e}',
                'operations': []
            }
    
    def read_fs_journal_operations(self, limit: Optional[int] = None,
                                  success_filter: Optional[bool] = None) -> Dict[str, Any]:
        """Read filesystem journal operations from Parquet files."""
        try:
            fs_pattern = str(self.base_path / 'fs_journal' / 'data' / '**' / '*.parquet')
            fs_files = glob.glob(fs_pattern, recursive=True)
            
            if not fs_files:
                return {
                    'success': False,
                    'error': 'No FS Journal Parquet files found',
                    'operations': []
                }
            
            # Read and combine all FS journal files
            all_operations = []
            for file_path in fs_files:
                try:
                    df = pd.read_parquet(file_path)
                    
                    # Apply success filter if specified
                    if success_filter is not None:
                        df = df[df['success'] == success_filter]
                    
                    for _, row in df.iterrows():
                        operation = {
                            'id': row.get('id', ''),
                            'operation_type': row.get('operation_type', ''),
                            'path': row.get('path', ''),
                            'backend_name': row.get('backend_name', ''),
                            'success': row.get('success', False),
                            'timestamp': row.get('timestamp', ''),
                            'size': row.get('size', 0),
                            'error_message': row.get('error_message', ''),
                            'duration_ms': row.get('duration_ms', 0),
                            'metadata': self._parse_json_field(row.get('metadata_json', '{}'))
                        }
                        all_operations.append(operation)
                        
                except Exception as e:
                    print(f"⚠️  Error reading FS Journal file {file_path}: {e}")
                    continue
            
            # Sort by timestamp (most recent first)
            all_operations.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Apply limit if specified
            if limit:
                all_operations = all_operations[:limit]
            
            return {
                'success': True,
                'operations': all_operations,
                'sources': fs_files,
                'total_count': len(all_operations),
                'method': 'parquet_direct'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'FS Journal Parquet read error: {e}',
                'operations': []
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics from all Parquet data sources."""
        try:
            metrics = {
                'pins': self._get_pin_metrics(),
                'wal': self._get_wal_metrics(),
                'fs_journal': self._get_fs_journal_metrics(),
                'storage': self._get_storage_metrics()
            }
            
            return {
                'success': True,
                'metrics': metrics,
                'method': 'parquet_direct',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Metrics calculation error: {e}',
                'metrics': {}
            }
    
    def _get_pin_metrics(self) -> Dict[str, Any]:
        """Get pin-specific metrics from Parquet data."""
        pin_result = self.read_pins()
        if not pin_result['success']:
            return {'total_pins': 0, 'total_size': 0, 'error': pin_result['error']}
        
        pins = pin_result['pins']
        total_size = sum(pin.get('size_bytes', 0) for pin in pins)
        
        return {
            'total_pins': len(pins),
            'total_size_bytes': total_size,
            'total_size_formatted': self._format_size(total_size),
            'sources': [pin_result['source']] if pin_result.get('source') else []
        }
    
    def _get_wal_metrics(self) -> Dict[str, Any]:
        """Get WAL-specific metrics from Parquet data."""
        wal_result = self.read_wal_operations()
        if not wal_result['success']:
            return {'total_operations': 0, 'error': wal_result['error']}
        
        operations = wal_result['operations']
        status_counts = {}
        for op in operations:
            status = op.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'total_operations': len(operations),
            'status_breakdown': status_counts,
            'sources': wal_result.get('sources', [])
        }
    
    def _get_fs_journal_metrics(self) -> Dict[str, Any]:
        """Get FS Journal-specific metrics from Parquet data."""
        fs_result = self.read_fs_journal_operations()
        if not fs_result['success']:
            return {'total_operations': 0, 'error': fs_result['error']}
        
        operations = fs_result['operations']
        success_count = sum(1 for op in operations if op.get('success', False))
        failed_count = len(operations) - success_count
        
        return {
            'total_operations': len(operations),
            'successful_operations': success_count,
            'failed_operations': failed_count,
            'success_rate': (success_count / len(operations) * 100) if operations else 0,
            'sources': fs_result.get('sources', [])
        }
    
    def _get_storage_metrics(self) -> Dict[str, Any]:
        """Get storage usage metrics from the .ipfs_kit directory."""
        try:
            parquet_files = list(self.base_path.glob('**/*.parquet'))
            duckdb_files = list(self.base_path.glob('**/*.duckdb'))
            
            total_parquet_size = sum(f.stat().st_size for f in parquet_files if f.exists())
            total_duckdb_size = sum(f.stat().st_size for f in duckdb_files if f.exists())
            
            return {
                'parquet_files': len(parquet_files),
                'duckdb_files': len(duckdb_files),
                'total_parquet_size_bytes': total_parquet_size,
                'total_duckdb_size_bytes': total_duckdb_size,
                'total_size_formatted': self._format_size(total_parquet_size + total_duckdb_size),
                'base_path': str(self.base_path)
            }
            
        except Exception as e:
            return {'error': f'Storage metrics error: {e}'}
    
    def read_configuration(self) -> Dict[str, Any]:
        """Read configuration data from YAML/JSON files in ~/.ipfs_kit/."""
        try:
            config_data = {}
            
            # Define configuration files to read
            config_files = {
                'package': 'package_config.yaml',
                's3': 's3_config.yaml', 
                'lotus': 'lotus_config.yaml',
                'wal': 'wal/config.json',
                'fs_journal': 'fs_journal/config.json'
            }
            
            sources_found = []
            
            for config_key, config_file in config_files.items():
                config_path = self.base_path / config_file
                if config_path.exists():
                    try:
                        with open(config_path, 'r') as f:
                            if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                                import yaml
                                data = yaml.safe_load(f)
                            elif config_file.endswith('.json'):
                                data = json.load(f)
                            else:
                                continue
                        
                        if data:
                            config_data[config_key] = data
                            sources_found.append(str(config_path))
                            
                    except Exception as e:
                        print(f"⚠️  Error reading config file {config_path}: {e}")
                        continue
            
            # Add computed values
            if config_data:
                config_data['_meta'] = {
                    'base_path': str(self.base_path),
                    'sources': sources_found,
                    'timestamp': datetime.now().isoformat(),
                    'total_configs': len(config_data)
                }
            
            return {
                'success': True,
                'config': config_data,
                'sources': sources_found,
                'method': 'direct_file_access'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Configuration read error: {e}',
                'config': {}
            }
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value using dot notation (e.g., 's3.region')."""
        config_result = self.read_configuration()
        
        if not config_result['success']:
            return default
        
        config_data = config_result['config']
        
        # Handle dot notation (e.g., 's3.region' -> config_data['s3']['region'])
        parts = key.split('.')
        current = config_data
        
        try:
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current
        except (TypeError, KeyError):
            return default
    
    def read_program_state(self) -> Dict[str, Any]:
        """Read current program state from Parquet files."""
        try:
            state_dir = self.base_path / 'program_state' / 'parquet'
            
            if not state_dir.exists():
                return {
                    'success': False,
                    'error': 'Program state directory not found',
                    'state': {}
                }
            
            # Define state files to read
            state_files = {
                'system': 'system_state.parquet',
                'network': 'network_state.parquet', 
                'storage': 'storage_state.parquet',
                'files': 'files_state.parquet'
            }
            
            state_data = {}
            sources_found = []
            
            for state_key, state_file in state_files.items():
                state_path = state_dir / state_file
                if state_path.exists():
                    try:
                        df = pd.read_parquet(state_path)
                        
                        # Convert DataFrame to dictionary format
                        state_records = []
                        for _, row in df.iterrows():
                            record = {}
                            for column in df.columns:
                                value = row[column]
                                # Handle pandas NA/NaN values
                                if pd.isna(value):
                                    record[column] = None
                                # Handle nested dict/JSON data
                                elif isinstance(value, dict):
                                    record[column] = value
                                else:
                                    record[column] = value
                            state_records.append(record)
                        
                        state_data[state_key] = {
                            'records': state_records,
                            'count': len(state_records),
                            'columns': list(df.columns),
                            'last_updated': state_records[-1].get('updated_at') if state_records else None,
                            'latest_data': state_records[-1].get(f'{state_key}_state', {}) if state_records else {}
                        }
                        sources_found.append(str(state_path))
                        
                    except Exception as e:
                        print(f"⚠️  Error reading state file {state_path}: {e}")
                        continue
            
            # Add summary information
            if state_data:
                state_data['_meta'] = {
                    'base_path': str(state_dir),
                    'sources': sources_found,
                    'timestamp': datetime.now().isoformat(),
                    'total_states': len(state_data) - 1,  # -1 for _meta
                    'method': 'parquet_direct'
                }
            
            return {
                'success': True,
                'state': state_data,
                'sources': sources_found,
                'method': 'parquet_state_access'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Program state read error: {e}',
                'state': {}
            }
    
    def get_current_daemon_status(self) -> Dict[str, Any]:
        """Get current daemon status from program state without daemon locks."""
        state_result = self.read_program_state()
        
        if not state_result['success']:
            return {
                'running': False,
                'error': state_result.get('error', 'Unknown error'),
                'source': 'state_read_failed'
            }
        
        state_data = state_result['state']
        
        # Extract daemon status from system state
        system_state = state_data.get('system', {})
        network_state = state_data.get('network', {})
        storage_state = state_data.get('storage', {})
        files_state = state_data.get('files', {})
        
        # Build daemon status from state data
        daemon_status = {
            'running': False,
            'services': {},
            'performance': {},
            'network': {},
            'storage': {},
            'files': {},
            'source': 'parquet_state',
            'last_updated': state_data.get('_meta', {}).get('timestamp', 'unknown')
        }
        
        # Extract system state data
        if system_state.get('latest_data'):
            sys_data = system_state['latest_data']
            daemon_status['running'] = True  # If we have recent state data, daemon was running
            daemon_status['performance'] = {
                'bandwidth_in': self._format_size(sys_data.get('bandwidth_in', 0)) + '/s',
                'bandwidth_out': self._format_size(sys_data.get('bandwidth_out', 0)) + '/s',
                'repo_size': self._format_size(sys_data.get('repo_size', 0)),
                'ipfs_version': sys_data.get('ipfs_version', 'Unknown'),
                'last_updated': sys_data.get('last_updated', 'Unknown')
            }
            
            # Store sys_data for network fallback
            peer_count_fallback = sys_data.get('peer_count', 0)
        else:
            peer_count_fallback = 0
        
        # Extract network state data
        if network_state.get('latest_data'):
            net_data = network_state['latest_data']
            daemon_status['network'] = {
                'connected_peers': net_data.get('peer_count', peer_count_fallback),
                'listening_addresses': net_data.get('listening_addresses', []),
                'bandwidth_in': net_data.get('bandwidth_in_bps', 0),
                'bandwidth_out': net_data.get('bandwidth_out_bps', 0),
                'network_status': net_data.get('network_status', 'Unknown')
            }
        
        # Extract storage state data
        if storage_state.get('latest_data'):
            stor_data = storage_state['latest_data']
            daemon_status['storage'] = {
                'total_size': self._format_size(stor_data.get('total_size_bytes', 0)),
                'used_size': self._format_size(stor_data.get('used_size_bytes', 0)),
                'available_size': self._format_size(stor_data.get('available_size_bytes', 0)),
                'pin_count': stor_data.get('pin_count', 0),
                'repo_version': stor_data.get('repo_version', 'Unknown')
            }
        
        # Extract files state data
        if files_state.get('latest_data'):
            files_data = files_state['latest_data']
            daemon_status['files'] = {
                'total_files': files_data.get('total_files', 0),
                'pinned_files': files_data.get('pinned_files', 0),
                'cached_files': files_data.get('cached_files', 0),
                'file_operations': files_data.get('recent_operations', 0)
            }
        
        return daemon_status

    def _parse_json_field(self, json_str: Union[str, None]) -> Dict[str, Any]:
        """Safely parse JSON fields from Parquet data."""
        if not json_str or pd.isna(json_str):
            return {}
        
        try:
            if isinstance(json_str, str):
                return json.loads(json_str)
            return json_str if isinstance(json_str, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"


# Global instance for CLI usage
_parquet_reader = None

def get_parquet_reader() -> ParquetDataReader:
    """Get global Parquet data reader instance."""
    global _parquet_reader
    if _parquet_reader is None:
        _parquet_reader = ParquetDataReader()
    return _parquet_reader
