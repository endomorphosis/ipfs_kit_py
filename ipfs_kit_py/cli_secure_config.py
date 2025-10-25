#!/usr/bin/env python3
"""
CLI commands for secure configuration management.

Provides command-line interface for:
- Enabling/disabling encryption
- Migrating plain configs to encrypted format
- Key rotation
- Encryption status checking
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

from ipfs_kit_py.secure_config import SecureConfigManager


def cmd_status(args) -> int:
    """Show encryption status."""
    manager = SecureConfigManager(
        data_dir=args.data_dir,
        enable_encryption=True
    )
    
    status = manager.get_encryption_status()
    
    print("Encryption Status:")
    print("=" * 50)
    print(f"Encryption Enabled: {status['encryption_enabled']}")
    print(f"Cryptography Library: {'✅ Available' if status['cryptography_available'] else '❌ Not installed'}")
    print(f"Encryption Key: {'✅ Exists' if status['key_exists'] else '❌ Not found'}")
    if status['key_file']:
        print(f"Key Location: {status['key_file']}")
    print(f"Config Directory: {status['data_dir']}")
    print(f"Keyring Directory: {status['keyring_dir']}")
    
    return 0


def cmd_migrate(args) -> int:
    """Migrate config file to encrypted format."""
    manager = SecureConfigManager(
        data_dir=args.data_dir,
        enable_encryption=True,
        master_password=args.password
    )
    
    if not manager.enable_encryption:
        print("❌ Encryption not available. Install cryptography: pip install cryptography")
        return 1
    
    print(f"Migrating {args.filename} to encrypted format...")
    
    success = manager.migrate_to_encrypted(args.filename)
    
    if success:
        print(f"✅ Successfully migrated {args.filename}")
        print(f"   Backup created with .backup suffix")
        return 0
    else:
        print(f"❌ Migration failed for {args.filename}")
        return 1


def cmd_migrate_all(args) -> int:
    """Migrate all config files to encrypted format."""
    manager = SecureConfigManager(
        data_dir=args.data_dir,
        enable_encryption=True,
        master_password=args.password
    )
    
    if not manager.enable_encryption:
        print("❌ Encryption not available. Install cryptography: pip install cryptography")
        return 1
    
    data_dir = Path(args.data_dir or Path.home() / ".ipfs_kit").expanduser()
    config_files = [f.name for f in data_dir.glob("*.json") if not f.name.startswith('.')]
    
    if not config_files:
        print("No config files found to migrate")
        return 0
    
    print(f"Found {len(config_files)} config files to migrate:")
    for filename in config_files:
        print(f"  - {filename}")
    
    if not args.yes:
        response = input("\nProceed with migration? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled")
            return 0
    
    print("\nMigrating files...")
    success_count = 0
    failed_count = 0
    
    for filename in config_files:
        print(f"  Migrating {filename}...", end=" ")
        if manager.migrate_to_encrypted(filename):
            print("✅")
            success_count += 1
        else:
            print("❌")
            failed_count += 1
    
    print(f"\nMigration complete:")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    
    return 0 if failed_count == 0 else 1


def cmd_rotate_key(args) -> int:
    """Rotate encryption key."""
    manager = SecureConfigManager(
        data_dir=args.data_dir,
        enable_encryption=True
    )
    
    if not manager.enable_encryption:
        print("❌ Encryption not available. Install cryptography: pip install cryptography")
        return 1
    
    if not args.yes:
        print("⚠️  Warning: This will generate a new encryption key and re-encrypt all config files.")
        print("    Backups will be created automatically.")
        response = input("\nProceed with key rotation? (y/N): ")
        if response.lower() != 'y':
            print("Key rotation cancelled")
            return 0
    
    print("Rotating encryption key...")
    
    success = manager.rotate_key()
    
    if success:
        print("✅ Successfully rotated encryption key")
        print("   All config files have been re-encrypted")
        print("   Old key backed up with .backup suffix")
        return 0
    else:
        print("❌ Key rotation failed")
        return 1


def cmd_encrypt(args) -> int:
    """Encrypt a specific config file."""
    manager = SecureConfigManager(
        data_dir=args.data_dir,
        enable_encryption=True,
        master_password=args.password
    )
    
    if not manager.enable_encryption:
        print("❌ Encryption not available. Install cryptography: pip install cryptography")
        return 1
    
    # Load config
    data = manager.load_config(args.filename, decrypt=False)
    if data is None:
        print(f"❌ Config file {args.filename} not found")
        return 1
    
    # Save encrypted
    print(f"Encrypting {args.filename}...")
    success = manager.save_config(args.filename, data, encrypt=True)
    
    if success:
        print(f"✅ Successfully encrypted {args.filename}")
        return 0
    else:
        print(f"❌ Encryption failed for {args.filename}")
        return 1


def cmd_decrypt(args) -> int:
    """Decrypt and display a config file."""
    manager = SecureConfigManager(
        data_dir=args.data_dir,
        enable_encryption=True,
        master_password=args.password
    )
    
    data = manager.load_config(args.filename, decrypt=True)
    
    if data is None:
        print(f"❌ Config file {args.filename} not found")
        return 1
    
    print(json.dumps(data, indent=2))
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="IPFS Kit Secure Configuration Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--data-dir',
        type=str,
        default=None,
        help='Config directory (default: ~/.ipfs_kit)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show encryption status')
    status_parser.set_defaults(func=cmd_status)
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Migrate config file to encrypted format')
    migrate_parser.add_argument('filename', help='Config filename to migrate')
    migrate_parser.add_argument('--password', help='Master password (optional)')
    migrate_parser.set_defaults(func=cmd_migrate)
    
    # Migrate all command
    migrate_all_parser = subparsers.add_parser('migrate-all', help='Migrate all config files')
    migrate_all_parser.add_argument('--password', help='Master password (optional)')
    migrate_all_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    migrate_all_parser.set_defaults(func=cmd_migrate_all)
    
    # Rotate key command
    rotate_parser = subparsers.add_parser('rotate-key', help='Rotate encryption key')
    rotate_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    rotate_parser.set_defaults(func=cmd_rotate_key)
    
    # Encrypt command
    encrypt_parser = subparsers.add_parser('encrypt', help='Encrypt a config file')
    encrypt_parser.add_argument('filename', help='Config filename to encrypt')
    encrypt_parser.add_argument('--password', help='Master password (optional)')
    encrypt_parser.set_defaults(func=cmd_encrypt)
    
    # Decrypt command
    decrypt_parser = subparsers.add_parser('decrypt', help='Decrypt and display config')
    decrypt_parser.add_argument('filename', help='Config filename to decrypt')
    decrypt_parser.add_argument('--password', help='Master password (optional)')
    decrypt_parser.set_defaults(func=cmd_decrypt)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
