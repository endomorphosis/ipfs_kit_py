#!/usr/bin/env python3
"""
Migrate secrets from XOR to AES-256-GCM encryption.

This script migrates all secrets in the ipfs_kit_py secrets manager
from legacy XOR encryption to production-grade AES-256-GCM encryption.

Usage:
    python migrate_secrets.py [--storage-path PATH] [--dry-run]

Options:
    --storage-path PATH   Path to secrets storage (default: ~/.ipfs_kit/secrets)
    --dry-run            Show what would be migrated without changing anything
    --help               Show this help message
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ipfs_kit_py.enhanced_secrets_manager import EnhancedSecretManager, AES_ENCRYPTION_AVAILABLE


def print_banner():
    """Print banner."""
    print("=" * 60)
    print("  Secret Migration: XOR → AES-256-GCM")
    print("=" * 60)
    print()


def check_prerequisites():
    """Check if AES encryption is available."""
    if not AES_ENCRYPTION_AVAILABLE:
        print("✗ ERROR: AES encryption not available")
        print()
        print("Please install the cryptography library:")
        print("  pip install 'cryptography>=38.0.0'")
        print()
        return False
    
    print("✓ AES-256-GCM encryption available")
    return True


def migrate_secrets(storage_path="~/.ipfs_kit/secrets", dry_run=False):
    """
    Migrate all secrets to AES-256-GCM.
    
    Args:
        storage_path: Path to secrets storage
        dry_run: If True, only report what would be migrated
        
    Returns:
        True if successful, False otherwise
    """
    print_banner()
    
    # Check prerequisites
    if not check_prerequisites():
        return False
    
    # Expand path
    storage_path = Path(storage_path).expanduser()
    
    print(f"✓ Storage path: {storage_path}")
    print()
    
    # Initialize manager with AES encryption
    print("Step 1: Initializing secrets manager...")
    try:
        manager = EnhancedSecretManager(
            storage_path=str(storage_path),
            encryption_method="aes-gcm"
        )
        print("✓ Manager initialized")
    except Exception as e:
        print(f"✗ Failed to initialize manager: {e}")
        return False
    
    # Get current statistics
    print("\nStep 2: Analyzing current secrets...")
    stats_before = manager.get_statistics()
    print(f"   Total secrets: {stats_before['total_secrets']}")
    print(f"   Encryption method: {stats_before['encryption_method']}")
    
    # Check encryption versions
    versions = stats_before.get('encryption_versions', {})
    xor_count = versions.get('v1', 0)
    aes_count = versions.get('v2', 0)
    
    print(f"\n   Current encryption breakdown:")
    print(f"   • XOR (v1 - legacy):  {xor_count:3d} secrets")
    print(f"   • AES (v2 - current): {aes_count:3d} secrets")
    
    if xor_count == 0:
        print("\n✓ SUCCESS: All secrets already use AES-256-GCM")
        print("   No migration needed!")
        return True
    
    if dry_run:
        print(f"\n[DRY RUN MODE]")
        print(f"   Would migrate {xor_count} secrets from XOR to AES-256-GCM")
        print(f"   Run without --dry-run to perform actual migration")
        return True
    
    # Confirm migration
    print(f"\nStep 3: Ready to migrate {xor_count} secrets")
    print("   This will:")
    print("   • Keep all secrets accessible")
    print("   • Upgrade encryption from XOR to AES-256-GCM")
    print("   • Take approximately 2-3ms per secret")
    print()
    
    response = input("   Continue with migration? [y/N]: ")
    if response.lower() != 'y':
        print("\n✗ Migration cancelled by user")
        return False
    
    # Perform migration
    print(f"\nStep 4: Migrating secrets...")
    print("   This may take a few seconds...")
    
    try:
        result = manager.migrate_all_secrets()
        
        print(f"\n   Migration results:")
        print(f"   • Migrated:        {result['migrated']:3d} secrets")
        print(f"   • Already current: {result['already_current']:3d} secrets")
        print(f"   • Errors:          {len(result['errors']):3d}")
        
        if result['errors']:
            print("\n   ⚠ Migration errors:")
            for error in result['errors']:
                print(f"      - {error}")
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        return False
    
    # Verify migration
    print("\nStep 5: Verifying migration...")
    stats_after = manager.get_statistics()
    versions_after = stats_after.get('encryption_versions', {})
    
    xor_after = versions_after.get('v1', 0)
    aes_after = versions_after.get('v2', 0)
    
    print(f"   Post-migration encryption breakdown:")
    print(f"   • XOR (v1 - legacy):  {xor_after:3d} secrets")
    print(f"   • AES (v2 - current): {aes_after:3d} secrets")
    
    if xor_after == 0:
        print("\n✓ SUCCESS: All secrets migrated to AES-256-GCM")
        print("\n   Your secrets are now protected with:")
        print("   • AES-256-GCM authenticated encryption")
        print("   • PBKDF2 key derivation (600K iterations)")
        print("   • Random salt per secret (16 bytes)")
        print("   • Random nonce per encryption (12 bytes)")
        print("   • Built-in tamper detection")
        return True
    else:
        print(f"\n⚠ WARNING: {xor_after} secrets still use XOR encryption")
        print("   Some secrets may have failed to migrate")
        print("   Check error messages above")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate secrets from XOR to AES-256-GCM encryption",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration without making changes
  python migrate_secrets.py --dry-run
  
  # Migrate secrets in default location
  python migrate_secrets.py
  
  # Migrate secrets in custom location
  python migrate_secrets.py --storage-path /path/to/secrets

For more information, see: docs/SECRETS_MIGRATION_GUIDE.md
        """
    )
    
    parser.add_argument(
        "--storage-path",
        default="~/.ipfs_kit/secrets",
        help="Path to secrets storage (default: ~/.ipfs_kit/secrets)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes"
    )
    
    args = parser.parse_args()
    
    # Run migration
    success = migrate_secrets(args.storage_path, args.dry_run)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
