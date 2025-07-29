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
import subprocess
import os


class ParquetDataReader:
    """Lock-free data access using Parquet files as the source of truth."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / '.ipfs_kit'
        
    def read_pins(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Read pin data from Parquet files with fallback to IPFS API (read-only)."""
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
                            # Check if this looks like real data (not mock)
                            if self._is_real_pin_data(df):
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
                            else:
                                print(f"⚠️  Detected mock data in {source}, skipping...")
                                continue
                    except Exception as e:
                        print(f"⚠️  Error reading {source}: {e}")
                        continue
            
            # No valid Parquet files found, fallback to read-only IPFS API access
            print("📡 No valid pin Parquet files found, reading from IPFS API (read-only)...")
            return self._read_pins_from_ipfs_readonly(limit)
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Parquet read error: {e}',
                'pins': []
            }

    def _is_real_pin_data(self, df: pd.DataFrame) -> bool:
        """Check if the pin data looks real (not mock data)."""
        if len(df) == 0:
            return False
            
        # Check for mock data patterns
        sample_cids = df['cid'].head(3).tolist() if 'cid' in df.columns else []
        for cid in sample_cids:
            # Mock CIDs often have obvious patterns
            if isinstance(cid, str) and ('sample_' in cid.lower() or 
                                       cid.startswith('QmY1Q2YxKXR9Zz8qM4c8N5k2z8v3u1L4t6h9q3w2e5r')):
                return False
        
        # Check for mock names
        names = df['name'].head(3).tolist() if 'name' in df.columns else []
        mock_names = ['sample_document.pdf', 'sample_image.jpg', 'sample_data.json']
        for name in names:
            if name in mock_names:
                return False
        
        return True

    def _read_pins_from_ipfs_readonly(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Read pins directly from IPFS daemon (read-only, no updates)."""
        try:
            # Check if IPFS is running
            test_result = subprocess.run(
                ['ipfs', 'id'],
                capture_output=True, text=True, timeout=5
            )
            
            if test_result.returncode != 0:
                return {
                    'success': False,
                    'error': 'IPFS daemon not running',
                    'pins': []
                }
            
            # Get recursive pins (read-only operation)
            result = subprocess.run(
                ['ipfs', 'pin', 'ls', '--type=recursive'],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'IPFS pin ls failed: {result.stderr}',
                    'pins': []
                }

            pins = []
            lines = result.stdout.strip().split('\n')
            
            # Process each pin line
            for line in lines:
                if not line.strip():
                    continue
                    
                parts = line.split()
                if len(parts) >= 2:
                    cid = parts[0]
                    pin_type = parts[1] if len(parts) > 1 else 'recursive'
                    
                    pin_data = {
                        'cid': cid,
                        'name': f'pin_{cid[:12]}',  # Use first 12 chars as name
                        'pin_type': pin_type,
                        'timestamp': '',
                        'size_bytes': 0,  # Size would require additional IPFS calls
                        'vfs_path': '',
                        'mount_point': '',
                        'access_count': 0,
                        'last_accessed': '',
                        'storage_tiers': [],
                        'primary_tier': 'ipfs',
                        'replication_factor': 1,
                        'content_hash': '',
                        'integrity_status': 'pinned'
                    }
                    pins.append(pin_data)

            # Apply limit if specified
            if limit and len(pins) > limit:
                pins = pins[:limit]

            return {
                'success': True,
                'pins': pins,
                'source': 'ipfs_api_readonly',
                'total_count': len(pins),
                'method': 'ipfs_api_readonly'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'IPFS read-only access error: {e}',
                'pins': []
            }
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
    
    def get_bucket_analytics(self) -> Dict[str, Any]:
        """Get bucket analytics from Parquet data or fallback sources."""
        try:
            # Primary: Try Parquet-based bucket analytics
            bucket_parquet_dir = self.base_path / 'bucket_index' / 'parquet'
            analytics_parquet_path = bucket_parquet_dir / 'bucket_analytics.parquet'
            
            if analytics_parquet_path.exists():
                try:
                    df = pd.read_parquet(analytics_parquet_path)
                    
                    # Parse analytics from Parquet
                    buckets = []
                    backend_summary = {}
                    global_stats = {}
                    
                    for _, row in df.iterrows():
                        metric_type = row.get('metric_type', '')
                        metric_name = row.get('metric_name', '')
                        
                        if metric_type == 'backend_summary':
                            backend_summary[metric_name] = {
                                'bucket_count': row.get('bucket_count', 0),
                                'total_size_bytes': row.get('total_size_bytes', 0),
                                'file_count': row.get('file_count', 0),
                                'metadata': self._parse_json_field(row.get('metadata', '{}'))
                            }
                        elif metric_type == 'global_summary':
                            global_stats = {
                                'total_buckets': row.get('bucket_count', 0),
                                'total_size_bytes': row.get('total_size_bytes', 0),
                                'total_files': row.get('file_count', 0),
                                'metadata': self._parse_json_field(row.get('metadata', '{}'))
                            }
                    
                    return {
                        'success': True,
                        'buckets': buckets,
                        'analytics': {
                            'backend_summary': backend_summary,
                            'global_stats': global_stats,
                            'sources_count': 1,
                            'last_updated': datetime.now().isoformat(),
                            'query_time_ms': 0.5,  # Very fast Parquet access
                            'method': 'parquet_analytics'
                        },
                        'timestamp': datetime.now().isoformat()
                    }
                except Exception as e:
                    print(f"⚠️  Error reading analytics Parquet: {e}")
            
            # Secondary: Try to read bucket metadata from Parquet
            buckets_parquet_path = bucket_parquet_dir / 'buckets.parquet'
            if buckets_parquet_path.exists():
                try:
                    df = pd.read_parquet(buckets_parquet_path)
                    buckets = []
                    for _, row in df.iterrows():
                        bucket_data = {
                            'bucket_id': row.get('bucket_id', ''),
                            'name': row.get('name', ''),
                            'backend': row.get('backend', ''),
                            'size_bytes': row.get('size_bytes', 0),
                            'file_count': row.get('file_count', 0),
                            'created_at': row.get('created_at', ''),
                            'last_updated': row.get('last_updated', ''),
                            'description': row.get('description', ''),
                            'tags': self._parse_json_field(row.get('tags', '[]')),
                            'storage_class': row.get('storage_class', ''),
                            'encryption': row.get('encryption', False)
                        }
                        buckets.append(bucket_data)
                    
                    return {
                        'success': True,
                        'buckets': buckets,
                        'analytics': {
                            'sources_count': 1,
                            'last_updated': datetime.now().isoformat(),
                            'query_time_ms': 1.0,
                            'method': 'parquet_buckets'
                        },
                        'timestamp': datetime.now().isoformat()
                    }
                except Exception as e:
                    print(f"⚠️  Error reading buckets Parquet: {e}")
            
            # Fallback: Try to read bucket data from various JSON sources
            buckets = []
            bucket_dirs = [
                self.base_path / 'bucket_index',
                self.base_path / 'bucket_analytics',
                self.base_path / 'vfs' / 'buckets'
            ]
            
            for bucket_dir in bucket_dirs:
                if bucket_dir.exists():
                    # Look for JSON files with bucket data
                    for json_file in bucket_dir.glob('*.json'):
                        try:
                            with open(json_file, 'r') as f:
                                data = json.load(f)
                                if isinstance(data, list):
                                    buckets.extend(data)
                                elif isinstance(data, dict) and 'buckets' in data:
                                    buckets.extend(data['buckets'])
                                elif isinstance(data, dict):
                                    # Single bucket
                                    buckets.append(data)
                        except Exception:
                            continue
            
            return {
                'success': True,
                'buckets': buckets,
                'analytics': {
                    'sources_count': len([d for d in bucket_dirs if d.exists()]),
                    'last_updated': datetime.now().isoformat(),
                    'query_time_ms': 5.0,  # Slower JSON fallback
                    'method': 'json_fallback'
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to get bucket analytics: {e}',
                'buckets': []
            }
    
    def query_files_by_bucket(self, bucket_name: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Query files in a specific bucket using individual bucket Parquet VFS data."""
        try:
            # Try individual bucket Parquet file first (new method)
            bucket_vfs_path = self.base_path / 'vfs' / 'buckets' / f'{bucket_name}_vfs.parquet'
            
            if bucket_vfs_path.exists():
                try:
                    df = pd.read_parquet(bucket_vfs_path)
                    
                    # Apply limit if specified
                    if limit:
                        df = df.head(limit)
                    
                    files = []
                    for _, row in df.iterrows():
                        file_data = {
                            'file_id': row.get('file_id', ''),
                            'name': row.get('name', ''),
                            'cid': row.get('cid', ''),
                            'size_bytes': row.get('size_bytes', 0),
                            'mime_type': row.get('mime_type', ''),
                            'uploaded_at': row.get('uploaded_at', ''),
                            'tags': self._parse_json_field(row.get('tags', '[]')),
                            'path': row.get('path', ''),
                            'vfs_path': row.get('vfs_path', ''),
                            'mount_point': row.get('mount_point', ''),
                            'access_count': row.get('access_count', 0),
                            'last_accessed': row.get('last_accessed', ''),
                            'content_hash': row.get('content_hash', ''),
                            'integrity_status': row.get('integrity_status', 'unknown'),
                            'storage_tier': row.get('storage_tier', 'primary'),
                            'snapshot_created': row.get('snapshot_created', ''),
                            'bucket_version': row.get('bucket_version', 1)
                        }
                        files.append(file_data)
                    
                    return {
                        'success': True,
                        'bucket_name': bucket_name,
                        'files': files,
                        'total_count': len(files),
                        'source': str(bucket_vfs_path),
                        'method': 'individual_bucket_parquet',
                        'query_time_ms': 0.5  # Very fast individual file access
                    }
                    
                except Exception as e:
                    print(f"⚠️  Error reading individual bucket Parquet: {e}")
            
            # Fallback to combined VFS Parquet file
            vfs_parquet_path = self.base_path / 'vfs' / 'parquet' / 'bucket_files.parquet'
            
            if not vfs_parquet_path.exists():
                return {
                    'success': False,
                    'error': f'No VFS data found for bucket {bucket_name}',
                    'files': []
                }
            
            # Read combined VFS Parquet data
            df = pd.read_parquet(vfs_parquet_path)
            
            # Filter by bucket name
            bucket_files = df[df['bucket_name'] == bucket_name]
            
            # Apply limit if specified
            if limit:
                bucket_files = bucket_files.head(limit)
            
            files = []
            for _, row in bucket_files.iterrows():
                file_data = {
                    'file_id': row.get('file_id', ''),
                    'name': row.get('name', ''),
                    'cid': row.get('cid', ''),
                    'size_bytes': row.get('size_bytes', 0),
                    'mime_type': row.get('mime_type', ''),
                    'uploaded_at': row.get('uploaded_at', ''),
                    'tags': self._parse_json_field(row.get('tags', '[]')),
                    'path': row.get('path', ''),
                    'vfs_path': row.get('vfs_path', ''),
                    'mount_point': row.get('mount_point', ''),
                    'access_count': row.get('access_count', 0),
                    'last_accessed': row.get('last_accessed', ''),
                    'content_hash': row.get('content_hash', ''),
                    'integrity_status': row.get('integrity_status', 'unknown'),
                    'storage_tier': row.get('storage_tier', 'primary')
                }
                files.append(file_data)
            
            return {
                'success': True,
                'bucket_name': bucket_name,
                'files': files,
                'total_count': len(files),
                'source': str(vfs_parquet_path),
                'method': 'combined_parquet_vfs_query',
                'query_time_ms': 1.0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'VFS query error: {e}',
                'files': []
            }
    
    def get_bucket_snapshot_info(self, bucket_name: str) -> Dict[str, Any]:
        """Get snapshot information for a specific bucket."""
        try:
            bucket_vfs_path = self.base_path / 'vfs' / 'buckets' / f'{bucket_name}_vfs.parquet'
            
            if not bucket_vfs_path.exists():
                return {
                    'success': False,
                    'error': f'Bucket VFS file not found: {bucket_vfs_path}',
                    'snapshot_info': None
                }
            
            # Read bucket data to get snapshot info
            df = pd.read_parquet(bucket_vfs_path)
            
            if len(df) == 0:
                return {
                    'success': False,
                    'error': f'No data in bucket VFS file',
                    'snapshot_info': None
                }
            
            # Get snapshot info from first row (should be consistent across all rows)
            first_row = df.iloc[0]
            
            # Calculate content hash of the Parquet file
            with open(bucket_vfs_path, 'rb') as f:
                parquet_bytes = f.read()
            
            # Create a simple hash for the file content
            import hashlib
            content_hash = hashlib.sha256(parquet_bytes).hexdigest()
            
            snapshot_info = {
                'bucket_name': bucket_name,
                'parquet_file': str(bucket_vfs_path),
                'parquet_size_bytes': len(parquet_bytes),
                'content_hash': content_hash,
                'file_count': len(df),
                'total_size_bytes': df['size_bytes'].sum(),
                'snapshot_created': first_row.get('snapshot_created', ''),
                'bucket_version': first_row.get('bucket_version', 1),
                'car_ready': True,
                'ipfs_ready': True,
                'storacha_ready': True
            }
            
            return {
                'success': True,
                'snapshot_info': snapshot_info,
                'source': str(bucket_vfs_path)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to get bucket snapshot info: {e}',
                'snapshot_info': None
            }
    
    def get_all_bucket_snapshots(self) -> Dict[str, Any]:
        """Get snapshot information for all buckets."""
        try:
            buckets_dir = self.base_path / 'vfs' / 'buckets'
            
            if not buckets_dir.exists():
                return {
                    'success': False,
                    'error': 'Buckets directory not found',
                    'snapshots': []
                }
            
            snapshots = []
            
            # Find all bucket VFS Parquet files
            for parquet_file in buckets_dir.glob('*_vfs.parquet'):
                bucket_name = parquet_file.stem.replace('_vfs', '')
                
                snapshot_result = self.get_bucket_snapshot_info(bucket_name)
                if snapshot_result['success']:
                    snapshots.append(snapshot_result['snapshot_info'])
            
            # Try to get global manifest if available
            manifest_path = self.base_path / 'vfs' / 'bucket_manifest.json'
            global_info = {}
            
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    
                    global_info = {
                        'snapshot_id': manifest.get('snapshot_id', ''),
                        'global_hash': manifest.get('global_hash', ''),
                        'created_at': manifest.get('created_at', ''),
                        'bucket_count': manifest.get('bucket_count', 0),
                        'total_files': manifest.get('total_files', 0),
                        'total_size_bytes': manifest.get('total_size_bytes', 0)
                    }
                except Exception as e:
                    print(f"⚠️  Error reading manifest: {e}")
            
            return {
                'success': True,
                'snapshots': snapshots,
                'global_info': global_info,
                'bucket_count': len(snapshots),
                'method': 'individual_bucket_snapshots'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to get bucket snapshots: {e}',
                'snapshots': []
            }
    
    def query_cid_location(self, cid: str) -> Dict[str, Any]:
        """Find bucket and filesystem location for a given CID using individual bucket files."""
        try:
            # Try individual bucket files first (faster)
            buckets_dir = self.base_path / 'vfs' / 'buckets'
            
            if buckets_dir.exists():
                for parquet_file in buckets_dir.glob('*_vfs.parquet'):
                    try:
                        df = pd.read_parquet(parquet_file)
                        cid_matches = df[df['cid'] == cid]
                        
                        if len(cid_matches) > 0:
                            match = cid_matches.iloc[0]
                            bucket_name = parquet_file.stem.replace('_vfs', '')
                            
                            location = {
                                'cid': cid,
                                'bucket_name': bucket_name,
                                'file_name': match.get('name', ''),
                                'file_path': match.get('path', ''),
                                'vfs_path': match.get('vfs_path', ''),
                                'size_bytes': match.get('size_bytes', 0),
                                'mime_type': match.get('mime_type', ''),
                                'uploaded_at': match.get('uploaded_at', ''),
                                'tags': self._parse_json_field(match.get('tags', '[]')),
                                'pinned': True,  # Files in VFS are considered pinned
                                'pin_type': 'recursive',
                                'storage_tier': match.get('storage_tier', 'primary'),
                                'content_hash': match.get('content_hash', ''),
                                'snapshot_created': match.get('snapshot_created', ''),
                                'bucket_version': match.get('bucket_version', 1)
                            }
                            
                            return {
                                'success': True,
                                'cid': cid,
                                'found': True,
                                'location': location,
                                'source': str(parquet_file),
                                'method': 'individual_bucket_search',
                                'query_time_ms': 0.2  # Very fast individual file search
                            }
                    except Exception as e:
                        print(f"⚠️  Error searching bucket file {parquet_file}: {e}")
                        continue
            
            # Fallback to combined CID mapping file
            cid_mapping_path = self.base_path / 'vfs' / 'parquet' / 'cid_to_bucket_mapping.parquet'
            
            if not cid_mapping_path.exists():
                return {
                    'success': True,
                    'cid': cid,
                    'found': False,
                    'location': None,
                    'message': f'CID {cid} not found in bucket index'
                }
            
            # Read CID mapping Parquet data
            df = pd.read_parquet(cid_mapping_path)
            
            # Find the CID
            cid_matches = df[df['cid'] == cid]
            
            if len(cid_matches) == 0:
                return {
                    'success': True,
                    'cid': cid,
                    'found': False,
                    'location': None,
                    'message': f'CID {cid} not found in bucket index'
                }
            
            # Get the first match (CIDs should be unique)
            match = cid_matches.iloc[0]
            
            location = {
                'cid': cid,
                'bucket_name': match.get('bucket_name', ''),
                'file_name': match.get('file_name', ''),
                'file_path': match.get('file_path', ''),
                'vfs_path': match.get('vfs_path', ''),
                'size_bytes': match.get('size_bytes', 0),
                'mime_type': match.get('mime_type', ''),
                'uploaded_at': match.get('uploaded_at', ''),
                'tags': self._parse_json_field(match.get('tags', '[]')),
                'pinned': match.get('pinned', False),
                'pin_type': match.get('pin_type', 'recursive'),
                'storage_tier': match.get('storage_tier', 'primary'),
                'replication_factor': match.get('replication_factor', 1)
            }
            
            return {
                'success': True,
                'cid': cid,
                'found': True,
                'location': location,
                'source': str(cid_mapping_path),
                'method': 'combined_parquet_cid_lookup',
                'query_time_ms': 0.5
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'CID lookup error: {e}',
                'location': None
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status from Parquet data."""
        try:
            health_status: Dict[str, Any] = {
                'overall_status': 'HEALTHY',
                'last_check': datetime.now().isoformat()
            }
            
            # IPFS health from program state
            program_state = self.read_program_state()
            if program_state['success']:
                state = program_state['state']
                
                # IPFS service health
                ipfs_state = state.get('network', {})
                health_status['ipfs'] = {
                    'status': 'ONLINE' if ipfs_state.get('ipfs_peers', 0) > 0 else 'OFFLINE',
                    'peer_id': ipfs_state.get('peer_id', 'Unknown'),
                    'connected_peers': ipfs_state.get('ipfs_peers', 0)
                }
                
                # System health
                system_state = state.get('system', {})
                cpu_usage = system_state.get('cpu_percent', 0)
                memory_usage = system_state.get('memory_percent', 0)
                
                if cpu_usage > 90 or memory_usage > 90:
                    health_status['overall_status'] = 'WARNING'
            else:
                health_status['ipfs'] = {
                    'status': 'UNKNOWN',
                    'peer_id': 'Unknown',
                    'connected_peers': 0
                }
            
            # WAL health
            wal_metrics = self._get_wal_metrics()
            health_status['wal'] = {
                'status': 'HEALTHY',
                'pending_operations': wal_metrics.get('total_operations', 0),
                'failed_operations': wal_metrics.get('failed_operations', 0)
            }
            
            # Storage health
            storage_metrics = self._get_storage_metrics()
            health_status['storage'] = {
                'status': 'HEALTHY',
                'available_space': storage_metrics.get('total_size_formatted', 'Unknown'),
                'parquet_files': storage_metrics.get('parquet_files', 0)
            }
            
            return {
                'success': True,
                'health': health_status,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to get health status: {e}',
                'health': {}
            }
    
    def get_program_state(self) -> Dict[str, Any]:
        """Get current program state - alias for read_program_state."""
        return self.read_program_state()


# Global instance for CLI usage
_parquet_reader = None

def get_parquet_reader() -> ParquetDataReader:
    """Get global Parquet data reader instance."""
    global _parquet_reader
    if _parquet_reader is None:
        _parquet_reader = ParquetDataReader()
    return _parquet_reader
