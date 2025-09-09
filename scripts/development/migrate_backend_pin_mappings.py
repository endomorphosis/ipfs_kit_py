#!/usr/bin/env python3
"""
Backend Pin Mappings Migration Tool

This tool standardizes all backends in ~/.ipfs_kit/backends/ to ensure they contain:
- pin_mappings.parquet: Maps IPFS CID hashes to remote backend locations
- pin_mappings.car: CAR file containing the pin mapping data

Migrates from legacy pins.json format to the new standardized format.
"""

import os
import json
import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PinMappingsMigrator:
    """Handles migration of backend pin storage to standardized format."""
    
    def __init__(self, ipfs_kit_path: str = None):
        """Initialize the migrator with the IPFS Kit data directory."""
        self.ipfs_kit_path = Path(ipfs_kit_path or os.path.expanduser("~/.ipfs_kit"))
        self.backends_path = self.ipfs_kit_path / "backends"
        
        # Standard schema for pin_mappings.parquet
        self.pin_mappings_schema = {
            'cid': 'string',               # IPFS CID hash
            'car_file_path': 'string',     # Path to CAR file on remote backend
            'backend_name': 'string',      # Name of the backend
            'created_at': 'string',        # ISO timestamp when pin was created
            'status': 'string',            # Pin status: 'stored', 'pending', 'failed'
            'metadata': 'string'           # JSON string with additional metadata
        }
        
    def discover_backends(self) -> List[Path]:
        """Discover all backend directories."""
        if not self.backends_path.exists():
            logger.warning(f"Backends directory not found: {self.backends_path}")
            return []
        
        backends = []
        for item in self.backends_path.iterdir():
            if item.is_dir():
                backends.append(item)
        
        logger.info(f"Discovered {len(backends)} backend directories")
        return backends
    
    def analyze_backend(self, backend_path: Path) -> Dict:
        """Analyze a backend directory and determine migration needs."""
        backend_name = backend_path.name
        
        analysis = {
            'backend_name': backend_name,
            'backend_path': backend_path,
            'has_pins_json': False,
            'has_pin_mappings_parquet': False,
            'has_pin_mappings_car': False,
            'pins_json_data': [],
            'needs_migration': False,
            'errors': []
        }
        
        # Check for existing files
        pins_json_path = backend_path / "pins.json"
        pin_mappings_parquet_path = backend_path / "pin_mappings.parquet"
        pin_mappings_car_path = backend_path / "pin_mappings.car"
        
        analysis['has_pins_json'] = pins_json_path.exists()
        analysis['has_pin_mappings_parquet'] = pin_mappings_parquet_path.exists()
        analysis['has_pin_mappings_car'] = pin_mappings_car_path.exists()
        
        # Read pins.json if it exists
        if analysis['has_pins_json']:
            try:
                with open(pins_json_path, 'r') as f:
                    analysis['pins_json_data'] = json.load(f)
                logger.debug(f"Read {len(analysis['pins_json_data'])} pins from {pins_json_path}")
            except Exception as e:
                analysis['errors'].append(f"Error reading pins.json: {e}")
                logger.error(f"Error reading {pins_json_path}: {e}")
        
        # Determine if migration is needed
        analysis['needs_migration'] = (
            not analysis['has_pin_mappings_parquet'] or 
            not analysis['has_pin_mappings_car'] or
            (analysis['has_pins_json'] and analysis['pins_json_data'])
        )
        
        return analysis
    
    def convert_pins_json_to_mappings(self, pins_data: List, backend_name: str) -> pd.DataFrame:
        """Convert pins.json data to pin_mappings format."""
        if not pins_data:
            # Create empty DataFrame with correct schema
            return pd.DataFrame(columns=list(self.pin_mappings_schema.keys()))
        
        mappings = []
        current_time = datetime.now().isoformat()
        
        for pin_entry in pins_data:
            # Handle different pin.json formats
            if isinstance(pin_entry, str):
                # Simple CID string format
                cid = pin_entry
                metadata = {}
            elif isinstance(pin_entry, dict):
                # Structured pin entry
                cid = pin_entry.get('cid', pin_entry.get('hash', ''))
                metadata = {k: v for k, v in pin_entry.items() if k not in ['cid', 'hash']}
            else:
                logger.warning(f"Unknown pin entry format: {pin_entry}")
                continue
            
            if not cid:
                logger.warning(f"No CID found in pin entry: {pin_entry}")
                continue
            
            # Generate CAR file path based on backend type and CID
            car_file_path = self._generate_car_file_path(backend_name, cid)
            
            mapping = {
                'cid': cid,
                'car_file_path': car_file_path,
                'backend_name': backend_name,
                'created_at': metadata.get('created_at', current_time),
                'status': metadata.get('status', 'stored'),
                'metadata': json.dumps(metadata)
            }
            mappings.append(mapping)
        
        return pd.DataFrame(mappings)
    
    def _generate_car_file_path(self, backend_name: str, cid: str) -> str:
        """Generate appropriate CAR file path based on backend type."""
        # Common patterns for different backend types
        if 's3' in backend_name.lower():
            return f"/s3-bucket/cars/{cid}.car"
        elif 'github' in backend_name.lower():
            return f"/github-repo/cars/{cid}.car"
        elif 'storacha' in backend_name.lower():
            return f"/storacha/{cid}.car"
        elif 'huggingface' in backend_name.lower() or 'hf' in backend_name.lower():
            return f"/hf-repo/cars/{cid}.car"
        elif 'ftp' in backend_name.lower():
            return f"/ftp-storage/cars/{cid}.car"
        elif 'sshfs' in backend_name.lower():
            return f"/sshfs-mount/cars/{cid}.car"
        else:
            # Generic path for unknown backends
            return f"/{backend_name}/cars/{cid}.car"
    
    def create_pin_mappings_car(self, pin_mappings_df: pd.DataFrame, car_file_path: Path) -> bool:
        """Create a CAR file containing the pin mappings data."""
        try:
            # Convert DataFrame to JSON for CAR file content
            mappings_json = pin_mappings_df.to_json(orient='records', indent=2)
            
            # For now, we'll create a simple text-based CAR file
            # In a full implementation, this would be a proper IPLD CAR file
            car_content = {
                "format": "pin_mappings_car",
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "pin_mappings": json.loads(mappings_json)
            }
            
            with open(car_file_path, 'w') as f:
                json.dump(car_content, f, indent=2)
            
            logger.info(f"Created pin_mappings.car: {car_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating CAR file {car_file_path}: {e}")
            return False
    
    def merge_existing_mappings(self, existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """Merge existing pin mappings with new data, avoiding duplicates."""
        if existing_df.empty:
            return new_df
        
        if new_df.empty:
            return existing_df
        
        # Combine and remove duplicates based on CID
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # Keep the most recent entry for each CID
        combined_df['created_at_dt'] = pd.to_datetime(combined_df['created_at'])
        combined_df = combined_df.sort_values('created_at_dt').drop_duplicates(
            subset=['cid'], keep='last'
        ).drop('created_at_dt', axis=1)
        
        return combined_df
    
    def migrate_backend(self, analysis: Dict, dry_run: bool = False) -> bool:
        """Migrate a single backend to the new format."""
        backend_path = analysis['backend_path']
        backend_name = analysis['backend_name']
        
        logger.info(f"Migrating backend: {backend_name}")
        
        if not analysis['needs_migration']:
            logger.info(f"Backend {backend_name} already up to date")
            return True
        
        try:
            # Load existing pin_mappings.parquet if it exists
            existing_df = pd.DataFrame()
            pin_mappings_parquet_path = backend_path / "pin_mappings.parquet"
            
            if analysis['has_pin_mappings_parquet']:
                try:
                    existing_df = pd.read_parquet(pin_mappings_parquet_path)
                    logger.debug(f"Loaded existing pin mappings: {len(existing_df)} records")
                except Exception as e:
                    logger.warning(f"Error reading existing pin_mappings.parquet: {e}")
            
            # Convert pins.json data to DataFrame
            new_df = self.convert_pins_json_to_mappings(
                analysis['pins_json_data'], backend_name
            )
            
            # Merge with existing data
            final_df = self.merge_existing_mappings(existing_df, new_df)
            
            if dry_run:
                logger.info(f"[DRY RUN] Would migrate {len(final_df)} pin mappings for {backend_name}")
                return True
            
            # Save pin_mappings.parquet
            final_df.to_parquet(pin_mappings_parquet_path, index=False)
            logger.info(f"Saved pin_mappings.parquet: {len(final_df)} records")
            
            # Create pin_mappings.car
            pin_mappings_car_path = backend_path / "pin_mappings.car"
            if not self.create_pin_mappings_car(final_df, pin_mappings_car_path):
                return False
            
            # Backup original pins.json if it exists and has data
            if analysis['has_pins_json'] and analysis['pins_json_data']:
                backup_path = backend_path / f"pins.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                pins_json_path = backend_path / "pins.json"
                pins_json_path.rename(backup_path)
                logger.info(f"Backed up original pins.json to: {backup_path}")
            
            logger.info(f"Successfully migrated backend: {backend_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating backend {backend_name}: {e}")
            return False
    
    def run_migration(self, dry_run: bool = False, backend_filter: str = None) -> Dict:
        """Run the complete migration process."""
        logger.info("Starting backend pin mappings migration")
        
        backends = self.discover_backends()
        if not backends:
            logger.warning("No backends found to migrate")
            return {'success': False, 'message': 'No backends found'}
        
        # Filter backends if specified
        if backend_filter:
            backends = [b for b in backends if backend_filter.lower() in b.name.lower()]
            logger.info(f"Filtering to backends matching '{backend_filter}': {len(backends)} backends")
        
        results = {
            'total_backends': len(backends),
            'analyzed': 0,
            'migrated': 0,
            'errors': 0,
            'up_to_date': 0,
            'backend_results': []
        }
        
        for backend_path in backends:
            try:
                # Analyze backend
                analysis = self.analyze_backend(backend_path)
                results['analyzed'] += 1
                
                logger.info(f"\n📊 Backend Analysis: {analysis['backend_name']}")
                logger.info(f"  pins.json: {'✅' if analysis['has_pins_json'] else '❌'} ({len(analysis['pins_json_data'])} pins)")
                logger.info(f"  pin_mappings.parquet: {'✅' if analysis['has_pin_mappings_parquet'] else '❌'}")
                logger.info(f"  pin_mappings.car: {'✅' if analysis['has_pin_mappings_car'] else '❌'}")
                logger.info(f"  Migration needed: {'✅' if analysis['needs_migration'] else '❌'}")
                
                if analysis['errors']:
                    for error in analysis['errors']:
                        logger.warning(f"  ⚠️  {error}")
                
                # Migrate if needed
                if analysis['needs_migration']:
                    success = self.migrate_backend(analysis, dry_run=dry_run)
                    if success:
                        results['migrated'] += 1
                    else:
                        results['errors'] += 1
                else:
                    results['up_to_date'] += 1
                
                results['backend_results'].append({
                    'backend_name': analysis['backend_name'],
                    'needs_migration': analysis['needs_migration'],
                    'success': not analysis['needs_migration'] or 
                              (analysis['needs_migration'] and self.migrate_backend(analysis, dry_run=True)),
                    'errors': analysis['errors']
                })
                
            except Exception as e:
                logger.error(f"Error processing backend {backend_path.name}: {e}")
                results['errors'] += 1
        
        # Summary
        logger.info(f"\n🎯 Migration Summary:")
        logger.info(f"  Total backends: {results['total_backends']}")
        logger.info(f"  Analyzed: {results['analyzed']}")
        logger.info(f"  Migrated: {results['migrated']}")
        logger.info(f"  Already up-to-date: {results['up_to_date']}")
        logger.info(f"  Errors: {results['errors']}")
        
        if dry_run:
            logger.info(f"\n🔍 This was a dry run - no files were modified")
        
        results['success'] = results['errors'] == 0
        return results

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate backend pin storage to standardized pin_mappings format"
    )
    parser.add_argument(
        '--ipfs-kit-path',
        default=None,
        help='Path to IPFS Kit data directory (default: ~/.ipfs_kit)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without making changes'
    )
    parser.add_argument(
        '--backend-filter',
        default=None,
        help='Only migrate backends whose names contain this string'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create migrator and run
    migrator = PinMappingsMigrator(args.ipfs_kit_path)
    results = migrator.run_migration(
        dry_run=args.dry_run,
        backend_filter=args.backend_filter
    )
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)

if __name__ == '__main__':
    main()
