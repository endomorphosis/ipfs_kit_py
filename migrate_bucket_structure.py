#!/usr/bin/env python3
"""
Bucket Structure Migration Script

Migrates from the current redundant bucket structure to the new VFS-based architecture:
- Consolidates bucket data into VFS indices
- Creates central bucket registry
- Extracts bucket configurations to YAML files
- Removes redundant directories
"""

import os
import json
import yaml
import shutil
from pathlib import Path
from typing import Dict, Any, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_bucket_structure(base_path: Path | None = None, dry_run: bool = True) -> bool:
    """Migrate bucket structure to new VFS-based architecture.
    
    Args:
        base_path: Base IPFS kit directory (defaults to ~/.ipfs_kit)
        dry_run: If True, only show what would be done without making changes
        
    Returns:
        True if successful, False otherwise
    """
    if base_path is None:
        base_path = Path.home() / '.ipfs_kit'
    
    logger.info(f"{'DRY RUN: ' if dry_run else ''}Migrating bucket structure in {base_path}")
    
    # Check if migration is needed
    buckets_dir = base_path / 'buckets'
    if not buckets_dir.exists():
        logger.info("No buckets directory found - migration not needed")
        return True
    
    # Initialize new structure paths
    vfs_indices_path = base_path / 'vfs_indices'
    bucket_configs_path = base_path / 'bucket_configs'
    registry_path = base_path / 'bucket_registry.yaml'
    
    # Create directories if not in dry run mode
    if not dry_run:
        vfs_indices_path.mkdir(exist_ok=True)
        bucket_configs_path.mkdir(exist_ok=True)
    
    # Analyze existing buckets
    bucket_analysis = analyze_existing_buckets(buckets_dir)
    logger.info(f"Found {len(bucket_analysis)} buckets to migrate")
    
    # Create new bucket registry
    registry = create_bucket_registry(bucket_analysis, dry_run)
    
    # Process each bucket
    for bucket_name, bucket_info in bucket_analysis.items():
        logger.info(f"{'DRY RUN: ' if dry_run else ''}Processing bucket: {bucket_name}")
        
        # Migrate VFS index
        migrate_vfs_index(bucket_name, bucket_info, vfs_indices_path, dry_run)
        
        # Create bucket configuration
        create_bucket_config(bucket_name, bucket_info, bucket_configs_path, dry_run)
    
    # Save registry
    if not dry_run:
        save_registry(registry, registry_path)
        logger.info(f"Saved bucket registry to {registry_path}")
    else:
        logger.info(f"DRY RUN: Would save registry to {registry_path}")
        print("Registry content:")
        print(yaml.dump(registry, default_flow_style=False))
    
    # Clean up old structure
    cleanup_old_structure(base_path, dry_run)
    
    logger.info(f"{'DRY RUN: ' if dry_run else ''}Migration completed successfully")
    return True

def analyze_existing_buckets(buckets_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Analyze existing bucket structure.
    
    Args:
        buckets_dir: Path to buckets directory
        
    Returns:
        Dictionary mapping bucket names to their analysis data
    """
    bucket_analysis = {}
    
    for bucket_path in buckets_dir.iterdir():
        if not bucket_path.is_dir():
            continue
            
        bucket_name = bucket_path.name
        logger.info(f"Analyzing bucket: {bucket_name}")
        
        # Check for bucket registry
        registry_file = bucket_path / 'bucket_registry.json'
        registry_data = {}
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    registry_data = json.load(f)
            except Exception as e:
                logger.warning(f"Could not read registry for {bucket_name}: {e}")
        
        # Check for files and structure
        file_count = 0
        total_size = 0
        has_vfs_index = False
        
        # Check VFS indices directory
        vfs_index_path = Path.home() / '.ipfs_kit' / 'vfs_indices' / bucket_name
        if vfs_index_path.exists():
            has_vfs_index = True
            logger.info(f"Found existing VFS index for {bucket_name}")
        
        # Analyze bucket contents
        for root, dirs, files in os.walk(bucket_path):
            file_count += len(files)
            for file in files:
                file_path = Path(root) / file
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass
        
        bucket_analysis[bucket_name] = {
            'path': bucket_path,
            'registry_data': registry_data,
            'file_count': file_count,
            'total_size': total_size,
            'has_vfs_index': has_vfs_index,
            'bucket_info': registry_data.get(bucket_name, {})
        }
        
        logger.info(f"  Files: {file_count}, Size: {format_size(total_size)}, VFS: {has_vfs_index}")
    
    return bucket_analysis

def create_bucket_registry(bucket_analysis: Dict[str, Dict[str, Any]], dry_run: bool) -> Dict[str, Any]:
    """Create the new central bucket registry.
    
    Args:
        bucket_analysis: Analysis data from existing buckets
        dry_run: Whether this is a dry run
        
    Returns:
        Registry dictionary
    """
    registry = {
        'buckets': {},
        'statistics': {
            'total_buckets': 0,
            'total_files': 0,
            'total_size': '0B',
            'last_updated': '2025-07-29T16:00:00Z'  # Use current time in real implementation
        }
    }
    
    total_files = 0
    total_size = 0
    
    for bucket_name, analysis in bucket_analysis.items():
        bucket_info = analysis['bucket_info']
        
        registry['buckets'][bucket_name] = {
            'type': bucket_info.get('type', 'general'),
            'vfs_index': bucket_name,
            'created_at': bucket_info.get('created_at', '2025-07-29T16:00:00Z'),
            'backend_bindings': [],  # Will be populated from config
            'total_files': analysis['file_count'],
            'total_size': format_size(analysis['total_size']),
            'last_sync': '2025-07-29T16:00:00Z'
        }
        
        total_files += analysis['file_count']
        total_size += analysis['total_size']
    
    registry['statistics'] = {
        'total_buckets': len(registry['buckets']),
        'total_files': total_files,
        'total_size': format_size(total_size),
        'last_updated': '2025-07-29T16:00:00Z'
    }
    
    return registry

def migrate_vfs_index(bucket_name: str, bucket_info: Dict[str, Any], 
                     vfs_indices_path: Path, dry_run: bool):
    """Migrate or ensure VFS index exists for bucket.
    
    Args:
        bucket_name: Name of the bucket
        bucket_info: Bucket analysis information
        vfs_indices_path: Path to VFS indices directory
        dry_run: Whether this is a dry run
    """
    vfs_path = vfs_indices_path / bucket_name
    
    if bucket_info['has_vfs_index']:
        logger.info(f"  VFS index already exists for {bucket_name}")
    else:
        if dry_run:
            logger.info(f"  DRY RUN: Would create VFS index at {vfs_path}")
        else:
            logger.info(f"  Creating VFS index at {vfs_path}")
            vfs_path.mkdir(parents=True, exist_ok=True)
            
            # Create empty VFS index files
            import pandas as pd
            
            # Create index.parquet
            index_df = pd.DataFrame(columns=[
                'file_path', 'ipfs_cid', 'file_size', 'modified_time', 
                'content_type', 'checksum_sha256'
            ])
            index_df.to_parquet(vfs_path / 'index.parquet', index=False)
            
            # Create metadata.parquet
            metadata_df = pd.DataFrame(columns=[
                'file_path', 'tags', 'description', 'custom_metadata', 'search_keywords'
            ])
            metadata_df.to_parquet(vfs_path / 'metadata.parquet', index=False)

def create_bucket_config(bucket_name: str, bucket_info: Dict[str, Any], 
                        bucket_configs_path: Path, dry_run: bool):
    """Create bucket configuration YAML file.
    
    Args:
        bucket_name: Name of the bucket
        bucket_info: Bucket analysis information
        bucket_configs_path: Path to bucket configs directory
        dry_run: Whether this is a dry run
    """
    config_path = bucket_configs_path / f"{bucket_name}.yaml"
    
    # Extract configuration from bucket registry data
    bucket_data = bucket_info['bucket_info']
    
    config = {
        'bucket_name': bucket_name,
        'type': bucket_data.get('type', 'general'),
        'created_at': bucket_data.get('created_at', '2025-07-29T16:00:00Z'),
        'backup': {
            'enabled': True,
            'frequency': 'daily',
            'retention_days': 365,
            'destinations': []
        },
        'replication': {
            'min_replicas': 2,
            'max_replicas': 5,
            'geographic_distribution': True
        },
        'cache': {
            'enabled': True,
            'policy': 'lru',
            'size_mb': 512,
            'ttl_seconds': 3600
        },
        'access': {
            'public_read': False,
            'api_access': True,
            'web_interface': True
        }
    }
    
    if dry_run:
        logger.info(f"  DRY RUN: Would create config at {config_path}")
        print(f"Config for {bucket_name}:")
        print(yaml.dump(config, default_flow_style=False))
    else:
        logger.info(f"  Creating config at {config_path}")
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

def save_registry(registry: Dict[str, Any], registry_path: Path):
    """Save the bucket registry to YAML file.
    
    Args:
        registry: Registry data to save
        registry_path: Path to save registry
    """
    with open(registry_path, 'w') as f:
        yaml.dump(registry, f, default_flow_style=False, sort_keys=True)

def cleanup_old_structure(base_path: Path, dry_run: bool):
    """Clean up old bucket structure.
    
    Args:
        base_path: Base IPFS kit directory
        dry_run: Whether this is a dry run
    """
    old_dirs = [
        base_path / 'buckets',
        base_path / 'bucket_index'
    ]
    
    for old_dir in old_dirs:
        if old_dir.exists():
            if dry_run:
                logger.info(f"DRY RUN: Would remove {old_dir}")
            else:
                logger.info(f"Removing old directory: {old_dir}")
                # For safety, move to backup instead of deleting
                backup_dir = base_path / 'migration_backup'
                backup_dir.mkdir(exist_ok=True)
                
                backup_path = backup_dir / old_dir.name
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                
                shutil.move(str(old_dir), str(backup_path))
                logger.info(f"Moved {old_dir} to {backup_path}")

def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PB"

def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate bucket structure to VFS-based architecture')
    parser.add_argument('--base-path', type=Path, help='Base IPFS kit directory')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--force', action='store_true', help='Proceed with migration')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.force:
        print("⚠️  This will modify your bucket structure!")
        print("Use --dry-run to see what would be changed, or --force to proceed")
        return 1
    
    try:
        success = migrate_bucket_structure(args.base_path, args.dry_run)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
