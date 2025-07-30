#!/usr/bin/env python3
"""
Bucket Architecture Migration Tool

Migrates existing bucket structure to the new simplified architecture:
- Converts nested bucket directories to flat VFS indices  
- Extracts metadata to YAML configuration files
- Creates central registry with IPFS CID references
- Maintains backward compatibility during transition
"""

import asyncio
import json
import logging
import os
import yaml
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import pandas as pd
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False

# Import with proper path handling
import sys
sys.path.append(str(Path(__file__).parent.parent))

try:
    from ipfs_kit_py.simplified_bucket_manager import SimplifiedBucketManager, BucketConfig
except ImportError:
    # Fallback for development
    SimplifiedBucketManager = None
    BucketConfig = None

logger = logging.getLogger(__name__)


class BucketMigrationTool:
    """Tool for migrating from old bucket structure to new simplified architecture."""
    
    def __init__(self, base_path: Optional[str] = None, backup: bool = True):
        """
        Initialize migration tool.
        
        Args:
            base_path: Base path for IPFS Kit (defaults to ~/.ipfs_kit)
            backup: Whether to create backups before migration
        """
        self.base_path = Path(base_path or os.path.expanduser("~/.ipfs_kit"))
        self.backup = backup
        
        # Old structure paths
        self.old_buckets_dir = self.base_path / "buckets"
        
        # New structure paths
        self.vfs_indices_dir = self.base_path / "vfs_indices"
        self.bucket_configs_dir = self.base_path / "bucket_configs"
        self.registry_file = self.base_path / "bucket_registry.parquet"
        
        # Backup path
        self.backup_dir = self.base_path / "migration_backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not PARQUET_AVAILABLE:
            raise ImportError("Parquet support required for migration. Install: pip install pyarrow")
    
    def _create_backup(self):
        """Create backup of existing bucket structure."""
        if not self.backup:
            return
            
        if not self.old_buckets_dir.exists():
            logger.info("No existing buckets directory to backup")
            return
        
        logger.info(f"Creating backup at {self.backup_dir}")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy buckets directory
        backup_buckets = self.backup_dir / "buckets"
        shutil.copytree(self.old_buckets_dir, backup_buckets)
        
        # Copy any existing registry files
        for file_name in ["bucket_registry.json", "bucket_registry.parquet"]:
            old_file = self.base_path / file_name
            if old_file.exists():
                shutil.copy2(old_file, self.backup_dir / file_name)
        
        logger.info(f"Backup completed at {self.backup_dir}")
    
    def _discover_old_buckets(self) -> List[Dict[str, Any]]:
        """Discover buckets in old structure."""
        discovered_buckets = []
        
        if not self.old_buckets_dir.exists():
            logger.info("No old buckets directory found")
            return discovered_buckets
        
        for bucket_path in self.old_buckets_dir.iterdir():
            if not bucket_path.is_dir():
                continue
                
            bucket_name = bucket_path.name
            bucket_info = {
                "name": bucket_name,
                "path": bucket_path,
                "metadata": {},
                "registry": {},
                "files": []
            }
            
            # Look for bucket registry
            registry_file = bucket_path / "bucket_registry.json"
            if registry_file.exists():
                try:
                    with open(registry_file, 'r') as f:
                        bucket_info["registry"] = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not read registry for {bucket_name}: {e}")
            
            # Look for nested bucket directory
            nested_bucket = bucket_path / bucket_name
            if nested_bucket.exists():
                # Look for metadata
                metadata_file = nested_bucket / "metadata" / "bucket_metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            bucket_info["metadata"] = json.load(f)
                    except Exception as e:
                        logger.warning(f"Could not read metadata for {bucket_name}: {e}")
                
                # Discover files in the bucket
                bucket_info["files"] = self._discover_bucket_files(nested_bucket)
            
            discovered_buckets.append(bucket_info)
            logger.info(f"Discovered bucket: {bucket_name} with {len(bucket_info['files'])} files")
        
        return discovered_buckets
    
    def _discover_bucket_files(self, bucket_path: Path) -> List[Dict[str, Any]]:
        """Discover files in an old bucket structure."""
        files = []
        
        # Look in common directories
        file_dirs = ["files", "car", "parquet", "vectors", "knowledge"]
        
        for dir_name in file_dirs:
            dir_path = bucket_path / dir_name
            if dir_path.exists():
                files.extend(self._scan_directory_for_files(dir_path, f"/{dir_name}"))
        
        return files
    
    def _scan_directory_for_files(self, dir_path: Path, vfs_prefix: str) -> List[Dict[str, Any]]:
        """Recursively scan directory for files."""
        files = []
        
        try:
            for item in dir_path.rglob("*"):
                if item.is_file() and not item.name.startswith('.'):
                    # Calculate virtual path
                    rel_path = item.relative_to(dir_path)
                    vfs_path = f"{vfs_prefix}/{rel_path}".replace("\\", "/")
                    
                    # Get file info
                    file_info = {
                        "vfs_path": vfs_path,
                        "physical_path": str(item),
                        "size": item.stat().st_size,
                        "modified_at": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                        "cid": ""  # Will need to be calculated/looked up
                    }
                    
                    # Try to determine MIME type
                    suffix = item.suffix.lower()
                    mime_map = {
                        '.txt': 'text/plain',
                        '.json': 'application/json',
                        '.yaml': 'application/x-yaml',
                        '.yml': 'application/x-yaml',
                        '.parquet': 'application/x-parquet',
                        '.car': 'application/car',
                        '.csv': 'text/csv'
                    }
                    file_info["mime_type"] = mime_map.get(suffix, "application/octet-stream")
                    
                    files.append(file_info)
        
        except Exception as e:
            logger.warning(f"Error scanning directory {dir_path}: {e}")
        
        return files
    
    def _create_bucket_config_from_old(self, bucket_info: Dict[str, Any]) -> Any:
        """Create new bucket config from old bucket information."""
        name = bucket_info["name"]
        metadata = bucket_info.get("metadata", {})
        registry = bucket_info.get("registry", {})
        
        # Extract type and vfs_structure from old metadata
        bucket_type = metadata.get("bucket_type", "general")
        vfs_structure = metadata.get("vfs_structure", "hybrid")
        
        # Create config with preserved metadata
        config = BucketConfig(
            name=name,
            type=bucket_type,
            vfs_structure=vfs_structure
        )
        
        # Update metadata with preserved values
        if metadata:
            config.metadata.update({
                "description": metadata.get("description", f"Migrated bucket {name}"),
                "created_at": metadata.get("created_at", datetime.now().isoformat()),
                "created_via": metadata.get("created_via", "migration"),
                "root_cid": metadata.get("root_cid", ""),
                "backend": metadata.get("backend", ""),
                "backend_config": metadata.get("backend_config", {}),
                "migrated_from": "legacy_structure",
                "migration_date": datetime.now().isoformat()
            })
        
        return config
    
    def _create_vfs_index_from_files(self, files: List[Dict[str, Any]]) -> pd.DataFrame:
        """Create VFS index DataFrame from file list."""
        vfs_data = {
            "path": [],
            "cid": [],
            "size": [],
            "mime_type": [],
            "created_at": [],
            "modified_at": [],
            "attributes": []
        }
        
        for file_info in files:
            vfs_data["path"].append(file_info["vfs_path"])
            vfs_data["cid"].append(file_info.get("cid", ""))  # Empty CID for now
            vfs_data["size"].append(file_info["size"])
            vfs_data["mime_type"].append(file_info.get("mime_type", ""))
            vfs_data["created_at"].append(file_info.get("modified_at", datetime.now().isoformat()))
            vfs_data["modified_at"].append(file_info.get("modified_at", datetime.now().isoformat()))
            
            # Store physical path in attributes for reference
            attributes = {
                "physical_path": file_info["physical_path"],
                "migrated": True
            }
            vfs_data["attributes"].append(json.dumps(attributes))
        
        return pd.DataFrame(vfs_data)
    
    async def analyze_migration(self) -> Dict[str, Any]:
        """Analyze what would be migrated without making changes."""
        logger.info("Analyzing bucket structure for migration...")
        
        buckets = self._discover_old_buckets()
        
        analysis = {
            "total_buckets": len(buckets),
            "total_files": sum(len(b["files"]) for b in buckets),
            "buckets": [],
            "migration_plan": {
                "create_directories": [
                    str(self.vfs_indices_dir),
                    str(self.bucket_configs_dir)
                ],
                "migrate_buckets": len(buckets) > 0,
                "backup_required": self.backup and self.old_buckets_dir.exists()
            }
        }
        
        for bucket in buckets:
            bucket_analysis = {
                "name": bucket["name"],
                "file_count": len(bucket["files"]),
                "total_size": sum(f["size"] for f in bucket["files"]),
                "has_metadata": bool(bucket["metadata"]),
                "has_registry": bool(bucket["registry"]),
                "config_file": str(self.bucket_configs_dir / f"{bucket['name']}.yaml"),
                "vfs_index_file": str(self.vfs_indices_dir / f"{bucket['name']}.parquet")
            }
            analysis["buckets"].append(bucket_analysis)
        
        return analysis
    
    async def migrate_buckets(self, dry_run: bool = False) -> Dict[str, Any]:
        """Migrate buckets from old structure to new architecture."""
        logger.info(f"Starting bucket migration (dry_run={dry_run})")
        
        if not dry_run:
            # Create backup
            self._create_backup()
            
            # Create new directories
            self.vfs_indices_dir.mkdir(parents=True, exist_ok=True)
            self.bucket_configs_dir.mkdir(parents=True, exist_ok=True)
        
        buckets = self._discover_old_buckets()
        
        # Initialize simplified bucket manager for new structure
        if not dry_run:
            manager = SimplifiedBucketManager(str(self.base_path))
        
        migration_results = {
            "migrated_buckets": [],
            "failed_buckets": [],
            "total_files_migrated": 0,
            "dry_run": dry_run
        }
        
        for bucket_info in buckets:
            bucket_name = bucket_info["name"]
            logger.info(f"Migrating bucket: {bucket_name}")
            
            try:
                if not dry_run:
                    # Create bucket config
                    config = self._create_bucket_config_from_old(bucket_info)
                    config_file = self.bucket_configs_dir / f"{bucket_name}.yaml"
                    
                    with open(config_file, 'w') as f:
                        yaml.dump(config.__dict__, f, default_flow_style=False, indent=2)
                    
                    # Create VFS index
                    vfs_df = self._create_vfs_index_from_files(bucket_info["files"])
                    vfs_index_file = self.vfs_indices_dir / f"{bucket_name}.parquet"
                    vfs_df.to_parquet(vfs_index_file, index=False)
                    
                    # Add to manager registry
                    manager.registry["buckets"][bucket_name] = {
                        "vfs_index": str(vfs_index_file),
                        "vfs_index_cid": "",  # Will be set when uploaded to IPFS
                        "config_file": str(config_file),
                        "type": config.type,
                        "vfs_structure": config.vfs_structure,
                        "created_at": config.metadata["created_at"],
                        "root_cid": config.metadata.get("root_cid", "")
                    }
                
                migration_result = {
                    "bucket_name": bucket_name,
                    "file_count": len(bucket_info["files"]),
                    "total_size": sum(f["size"] for f in bucket_info["files"]),
                    "config_created": not dry_run,
                    "vfs_index_created": not dry_run
                }
                
                migration_results["migrated_buckets"].append(migration_result)
                migration_results["total_files_migrated"] += len(bucket_info["files"])
                
                logger.info(f"Successfully migrated bucket {bucket_name} with {len(bucket_info['files'])} files")
                
            except Exception as e:
                logger.error(f"Failed to migrate bucket {bucket_name}: {e}")
                migration_results["failed_buckets"].append({
                    "bucket_name": bucket_name,
                    "error": str(e)
                })
        
        if not dry_run and hasattr(manager, 'registry'):
            # Save the registry
            manager._save_registry()
            logger.info("Saved new bucket registry")
        
        logger.info(f"Migration completed: {len(migration_results['migrated_buckets'])} succeeded, {len(migration_results['failed_buckets'])} failed")
        
        return migration_results
    
    async def validate_migration(self) -> Dict[str, Any]:
        """Validate that migration was successful."""
        logger.info("Validating migration results...")
        
        validation = {
            "new_structure_exists": {
                "vfs_indices_dir": self.vfs_indices_dir.exists(),
                "bucket_configs_dir": self.bucket_configs_dir.exists(),
                "registry_file": self.registry_file.exists()
            },
            "buckets_migrated": [],
            "validation_errors": []
        }
        
        if not self.registry_file.exists():
            validation["validation_errors"].append("Registry file not found")
            return validation
        
        try:
            # Load registry and validate
            df = pd.read_parquet(self.registry_file)
            
            for _, row in df.iterrows():
                bucket_name = row['bucket_name']
                vfs_index_path = Path(row['vfs_index_path'])
                config_file_path = Path(row['config_file_path'])
                
                bucket_validation = {
                    "bucket_name": bucket_name,
                    "vfs_index_exists": vfs_index_path.exists(),
                    "config_file_exists": config_file_path.exists(),
                    "file_count": 0
                }
                
                # Count files in VFS index
                if vfs_index_path.exists():
                    try:
                        vfs_df = pd.read_parquet(vfs_index_path)
                        bucket_validation["file_count"] = len(vfs_df)
                    except Exception as e:
                        validation["validation_errors"].append(f"Could not read VFS index for {bucket_name}: {e}")
                
                validation["buckets_migrated"].append(bucket_validation)
        
        except Exception as e:
            validation["validation_errors"].append(f"Could not validate registry: {e}")
        
        return validation


async def main():
    """Main function for running migration tool."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate IPFS Kit buckets to simplified architecture")
    parser.add_argument("--base-path", help="Base path for IPFS Kit (default: ~/.ipfs_kit)")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backup")
    parser.add_argument("--dry-run", action="store_true", help="Analyze migration without making changes")
    parser.add_argument("--validate", action="store_true", help="Validate migration results")
    parser.add_argument("--analyze", action="store_true", help="Analyze current structure")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    migration_tool = BucketMigrationTool(
        base_path=args.base_path,
        backup=not args.no_backup
    )
    
    if args.analyze:
        print("=== Migration Analysis ===")
        analysis = await migration_tool.analyze_migration()
        print(json.dumps(analysis, indent=2))
    
    elif args.validate:
        print("=== Migration Validation ===")
        validation = await migration_tool.validate_migration()
        print(json.dumps(validation, indent=2))
    
    else:
        print("=== Bucket Migration ===")
        results = await migration_tool.migrate_buckets(dry_run=args.dry_run)
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
