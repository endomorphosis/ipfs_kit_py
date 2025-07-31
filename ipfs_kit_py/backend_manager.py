#!/usr/bin/env python3
"""
Backend Configuration Manager for IPFS Kit.

This manages backend configurations stored in ~/.ipfs_kit/backend_configs/
and pin mappings stored in ~/.ipfs_kit/backends/ for tracking which pins
are stored on which remote backends and their CAR file locations.
"""

import asyncio
import json
import logging
import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# Import config manager
try:
    from .config_manager import get_config_manager
    CONFIG_AVAILABLE = True
    _config_manager = get_config_manager
except ImportError:
    CONFIG_AVAILABLE = False
    _config_manager = None


class BackendManager:
    """Manages backend configurations and pin mappings."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize backend manager."""
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # Try to get from config manager if available
            if CONFIG_AVAILABLE and _config_manager:
                try:
                    config_manager = _config_manager()
                    self.data_dir = Path(config_manager.get_config_value('data_dir', '~/.ipfs_kit')).expanduser()
                except Exception:
                    self.data_dir = Path('~/.ipfs_kit').expanduser()
            else:
                self.data_dir = Path('~/.ipfs_kit').expanduser()
        
        # Backend directory structure
        self.backend_configs_dir = self.data_dir / 'backend_configs'
        self.backends_dir = self.data_dir / 'backends'
        
        # Ensure directories exist
        self.backend_configs_dir.mkdir(parents=True, exist_ok=True)
        self.backends_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"BackendManager initialized with data_dir: {self.data_dir}")
        logger.info(f"Backend configs dir: {self.backend_configs_dir}")
        logger.info(f"Backend indexes dir: {self.backends_dir}")
    
    async def create_backend_config(
        self,
        backend_name: str,
        backend_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a backend configuration.
        
        Args:
            backend_name: Name of the backend (e.g., 'my-s3-bucket')
            backend_type: Type of backend (e.g., 's3', 'huggingface', 'storacha')
            config: Backend-specific configuration
            
        Returns:
            Result dictionary
        """
        try:
            # Create configuration
            backend_config = {
                'name': backend_name,
                'type': backend_type,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'enabled': True,
                'config': config,
                'metadata': {
                    'version': '1.0',
                    'description': f'{backend_type} backend configuration'
                }
            }
            
            # Save configuration as YAML
            config_file = self.backend_configs_dir / f'{backend_name}.yaml'
            with open(config_file, 'w') as f:
                yaml.dump(backend_config, f, default_flow_style=False, indent=2)
            
            # Create backend index directory
            backend_index_dir = self.backends_dir / backend_name
            backend_index_dir.mkdir(exist_ok=True)
            
            # Create initial pin mapping index
            await self._create_initial_pin_mapping(backend_name)
            
            logger.info(f"Created backend configuration: {backend_name}")
            
            return {
                'success': True,
                'data': {
                    'backend_name': backend_name,
                    'backend_type': backend_type,
                    'config_file': str(config_file),
                    'index_dir': str(backend_index_dir)
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating backend config: {e}")
            return {
                'success': False,
                'error': f"Failed to create backend config: {str(e)}"
            }
    
    async def update_backend_config(
        self,
        backend_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing backend configuration."""
        try:
            config_file = self.backend_configs_dir / f'{backend_name}.yaml'
            
            if not config_file.exists():
                return {
                    'success': False,
                    'error': f"Backend '{backend_name}' not found"
                }
            
            # Load existing config
            with open(config_file, 'r') as f:
                backend_config = yaml.safe_load(f)
            
            # Update configuration
            backend_config['updated_at'] = datetime.utcnow().isoformat()
            
            # Merge updates
            for key, value in updates.items():
                if key == 'config':
                    # Merge config dictionaries
                    backend_config['config'].update(value)
                else:
                    backend_config[key] = value
            
            # Save updated configuration
            with open(config_file, 'w') as f:
                yaml.dump(backend_config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Updated backend configuration: {backend_name}")
            
            return {
                'success': True,
                'data': {
                    'backend_name': backend_name,
                    'updated_at': backend_config['updated_at']
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating backend config: {e}")
            return {
                'success': False,
                'error': f"Failed to update backend config: {str(e)}"
            }
    
    async def list_backend_configs(self) -> Dict[str, Any]:
        """List all backend configurations."""
        try:
            backends = []
            
            for config_file in self.backend_configs_dir.glob('*.yaml'):
                try:
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    backend_info = {
                        'name': config.get('name', config_file.stem),
                        'type': config.get('type', 'unknown'),
                        'enabled': config.get('enabled', True),
                        'created_at': config.get('created_at'),
                        'updated_at': config.get('updated_at'),
                        'config_file': str(config_file)
                    }
                    
                    # Check if backend index exists
                    backend_index_dir = self.backends_dir / backend_info['name']
                    backend_info['has_index'] = backend_index_dir.exists()
                    
                    backends.append(backend_info)
                    
                except Exception as e:
                    logger.warning(f"Error reading config file {config_file}: {e}")
                    continue
            
            # Sort by name
            backends.sort(key=lambda x: x['name'])
            
            return {
                'success': True,
                'data': {
                    'backends': backends,
                    'total_backends': len(backends)
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing backend configs: {e}")
            return {
                'success': False,
                'error': f"Failed to list backend configs: {str(e)}"
            }
    
    async def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get a specific backend configuration."""
        try:
            config_file = self.backend_configs_dir / f'{backend_name}.yaml'
            
            if not config_file.exists():
                return {
                    'success': False,
                    'error': f"Backend '{backend_name}' not found"
                }
            
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            return {
                'success': True,
                'data': {
                    'backend_config': config,
                    'config_file': str(config_file)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting backend config: {e}")
            return {
                'success': False,
                'error': f"Failed to get backend config: {str(e)}"
            }
    
    async def remove_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Remove a backend configuration."""
        try:
            config_file = self.backend_configs_dir / f'{backend_name}.yaml'
            backend_index_dir = self.backends_dir / backend_name
            
            if not config_file.exists():
                return {
                    'success': False,
                    'error': f"Backend '{backend_name}' not found"
                }
            
            # Remove configuration file
            config_file.unlink()
            
            # Remove backend index directory if it exists
            if backend_index_dir.exists():
                import shutil
                shutil.rmtree(backend_index_dir)
            
            logger.info(f"Removed backend configuration: {backend_name}")
            
            return {
                'success': True,
                'data': {
                    'backend_name': backend_name,
                    'removed_at': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error removing backend config: {e}")
            return {
                'success': False,
                'error': f"Failed to remove backend config: {str(e)}"
            }
    
    async def add_pin_mapping(
        self,
        backend_name: str,
        cid: str,
        car_file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a pin mapping to a backend index.
        
        Args:
            backend_name: Name of the backend
            cid: Content identifier
            car_file_path: Path to the CAR file on the remote backend
            metadata: Optional metadata about the pin
            
        Returns:
            Result dictionary
        """
        try:
            backend_index_dir = self.backends_dir / backend_name
            
            if not backend_index_dir.exists():
                return {
                    'success': False,
                    'error': f"Backend '{backend_name}' index not found"
                }
            
            # Pin mapping file
            pin_mapping_file = backend_index_dir / 'pin_mappings.parquet'
            
            # Create new mapping entry
            new_mapping = {
                'cid': cid,
                'car_file_path': car_file_path,
                'backend_name': backend_name,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'stored',
                'metadata': json.dumps(metadata or {})
            }
            
            if pin_mapping_file.exists():
                # Read existing mappings
                df_existing = pd.read_parquet(pin_mapping_file)
                
                # Check if mapping already exists
                if df_existing['cid'].eq(cid).any():
                    # Update existing mapping
                    df_existing.loc[df_existing['cid'] == cid, 'car_file_path'] = car_file_path
                    df_existing.loc[df_existing['cid'] == cid, 'updated_at'] = datetime.utcnow().isoformat()
                    df_existing.loc[df_existing['cid'] == cid, 'metadata'] = json.dumps(metadata or {})
                    df_combined = df_existing
                else:
                    # Add new mapping
                    df_new = pd.DataFrame([new_mapping])
                    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                # Create new mappings file
                df_combined = pd.DataFrame([new_mapping])
            
            # Save updated mappings
            df_combined.to_parquet(pin_mapping_file, index=False)
            
            logger.info(f"Added pin mapping: {cid} -> {car_file_path} on {backend_name}")
            
            return {
                'success': True,
                'data': {
                    'cid': cid,
                    'car_file_path': car_file_path,
                    'backend_name': backend_name
                }
            }
            
        except Exception as e:
            logger.error(f"Error adding pin mapping: {e}")
            return {
                'success': False,
                'error': f"Failed to add pin mapping: {str(e)}"
            }
    
    async def list_pin_mappings(
        self,
        backend_name: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """List pin mappings for a backend."""
        try:
            backend_index_dir = self.backends_dir / backend_name
            pin_mapping_file = backend_index_dir / 'pin_mappings.parquet'
            
            if not pin_mapping_file.exists():
                return {
                    'success': True,
                    'data': {
                        'mappings': [],
                        'total_mappings': 0
                    }
                }
            
            # Read pin mappings
            df = pd.read_parquet(pin_mapping_file)
            
            if limit:
                df = df.head(limit)
            
            mappings = []
            for _, row in df.iterrows():
                mapping_info = {
                    'cid': row['cid'],
                    'car_file_path': row['car_file_path'],
                    'backend_name': row['backend_name'],
                    'created_at': row['created_at'],
                    'status': row.get('status', 'unknown'),
                    'metadata': json.loads(row.get('metadata', '{}'))
                }
                mappings.append(mapping_info)
            
            return {
                'success': True,
                'data': {
                    'mappings': mappings,
                    'total_mappings': len(mappings)
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing pin mappings: {e}")
            return {
                'success': False,
                'error': f"Failed to list pin mappings: {str(e)}"
            }
    
    async def find_pin_on_backends(self, cid: str) -> Dict[str, Any]:
        """Find which backends have a specific pin."""
        try:
            backend_locations = []
            
            # Search all backend indexes
            for backend_dir in self.backends_dir.iterdir():
                if not backend_dir.is_dir():
                    continue
                
                pin_mapping_file = backend_dir / 'pin_mappings.parquet'
                if not pin_mapping_file.exists():
                    continue
                
                try:
                    df = pd.read_parquet(pin_mapping_file)
                    matching_pins = df[df['cid'] == cid]
                    
                    for _, row in matching_pins.iterrows():
                        backend_locations.append({
                            'backend_name': row['backend_name'],
                            'car_file_path': row['car_file_path'],
                            'created_at': row['created_at'],
                            'status': row.get('status', 'unknown'),
                            'metadata': json.loads(row.get('metadata', '{}'))
                        })
                        
                except Exception as e:
                    logger.warning(f"Error reading mappings from {backend_dir.name}: {e}")
                    continue
            
            return {
                'success': True,
                'data': {
                    'cid': cid,
                    'backend_locations': backend_locations,
                    'total_locations': len(backend_locations)
                }
            }
            
        except Exception as e:
            logger.error(f"Error finding pin on backends: {e}")
            return {
                'success': False,
                'error': f"Failed to find pin on backends: {str(e)}"
            }
    
    async def _create_initial_pin_mapping(self, backend_name: str):
        """Create initial pin mapping index for a backend."""
        try:
            backend_index_dir = self.backends_dir / backend_name
            pin_mapping_file = backend_index_dir / 'pin_mappings.parquet'
            
            # Create empty DataFrame with required columns
            empty_df = pd.DataFrame(columns=[
                'cid', 'car_file_path', 'backend_name', 'created_at', 
                'status', 'metadata'
            ])
            
            # Save as empty parquet file
            empty_df.to_parquet(pin_mapping_file, index=False)
            
            logger.info(f"Created initial pin mapping index for backend: {backend_name}")
            
        except Exception as e:
            logger.error(f"Error creating initial pin mapping: {e}")
            raise


# Global instance
_global_backend_manager = None

def get_backend_manager(data_dir: Optional[str] = None) -> BackendManager:
    """Get global backend manager instance."""
    global _global_backend_manager
    
    if _global_backend_manager is None:
        _global_backend_manager = BackendManager(data_dir)
    
    return _global_backend_manager
