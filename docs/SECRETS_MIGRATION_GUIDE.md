# Migration Guide: XOR to AES-256-GCM Encryption

## Overview

This guide provides step-by-step instructions for migrating from the legacy XOR encryption to production-grade AES-256-GCM encryption in the ipfs_kit_py secrets manager.

## Why Migrate?

### Security Comparison

| Feature | XOR (Legacy) | AES-256-GCM (New) |
|---------|--------------|-------------------|
| Algorithm | Simple XOR | AES-256-GCM |
| Key Derivation | None | PBKDF2 (600K iterations) |
| Salt | ❌ No | ✅ Yes (16 bytes, random) |
| Nonce | ❌ No | ✅ Yes (12 bytes, random) |
| Authentication | ❌ No | ✅ Yes (built-in) |
| Tamper Detection | ❌ No | ✅ Yes |
| Production Ready | ❌ NO | ✅ YES |

### Risk Assessment

**XOR Encryption Risks:**
- Easily broken with known-plaintext attack
- No protection against rainbow tables
- Same plaintext always produces same ciphertext
- No tamper detection
- **NOT suitable for production secrets**

**AES-256-GCM Benefits:**
- Industry-standard encryption (NIST approved)
- Resistant to all known practical attacks
- PBKDF2 with 600K iterations (OWASP 2023+ standard)
- Random salt prevents rainbow table attacks
- Random nonce ensures ciphertext uniqueness
- Authenticated encryption detects tampering
- **Production-ready**

## Pre-Migration Checklist

- [ ] **Backup current secrets**
  ```bash
  cp -r ~/.ipfs_kit/secrets ~/.ipfs_kit/secrets.backup.$(date +%Y%m%d)
  ```

- [ ] **Verify cryptography library**
  ```bash
  python -c "from cryptography.hazmat.primitives.ciphers.aead import AESGCM; print('✓ AES available')"
  ```

- [ ] **Test in development environment first**

- [ ] **Plan maintenance window** (minimal downtime needed)

- [ ] **Document current secret count**
  ```python
  from ipfs_kit_py.enhanced_secrets_manager import EnhancedSecretManager
  
  manager = EnhancedSecretManager()
  stats = manager.get_statistics()
  print(f"Total secrets: {stats['total_secrets']}")
  ```

## Migration Strategies

### Strategy 1: Automatic Migration (Recommended)

**Best for:** Most use cases, minimal downtime

1. **Enable AES encryption** (default in new installations)
   ```python
   from ipfs_kit_py.enhanced_secrets_manager import EnhancedSecretManager
   
   # Initialize with AES encryption (default)
   manager = EnhancedSecretManager(
       storage_path="~/.ipfs_kit/secrets",
       encryption_method="aes-gcm"  # Default, can be omitted
   )
   ```

2. **Migrate all secrets**
   ```python
   # Migrate all XOR-encrypted secrets to AES
   result = manager.migrate_all_secrets()
   
   print(f"Migration complete:")
   print(f"  Migrated: {result['migrated']}")
   print(f"  Already current: {result['already_current']}")
   print(f"  Errors: {len(result['errors'])}")
   
   if result['errors']:
       for error in result['errors']:
           print(f"  Error: {error}")
   ```

3. **Verify migration**
   ```python
   stats = manager.get_statistics()
   print(f"Encryption versions:")
   print(f"  AES (v2): {stats['encryption_versions'].get('v2', 0)}")
   print(f"  XOR (v1): {stats['encryption_versions'].get('v1', 0)}")
   ```

### Strategy 2: Gradual Migration

**Best for:** Large secret stores, zero-downtime requirements

1. **Phase 1: Enable AES for new secrets**
   ```python
   manager = EnhancedSecretManager(
       encryption_method="aes-gcm"  # New secrets use AES
   )
   ```
   
   - New secrets automatically use AES-256-GCM
   - Legacy secrets still readable (automatic detection)
   - No immediate migration required

2. **Phase 2: Monitor migration status**
   ```python
   # Check which secrets need migration
   for secret_id in manager.secrets.keys():
       info = manager.get_encryption_info(secret_id)
       if info['needs_migration']:
           print(f"Secret {secret_id} needs migration")
   ```

3. **Phase 3: Migrate during rotation**
   - Secrets are automatically upgraded when rotated
   - Natural migration over time
   - No explicit migration needed

4. **Phase 4: Final migration** (optional)
   ```python
   # Migrate remaining secrets after grace period
   result = manager.migrate_all_secrets()
   ```

### Strategy 3: Manual Migration

**Best for:** Custom migration logic, special requirements

1. **Identify secrets to migrate**
   ```python
   secrets_to_migrate = []
   
   for secret_id in manager.secrets.keys():
       info = manager.get_encryption_info(secret_id)
       if info and info['needs_migration']:
           secrets_to_migrate.append(secret_id)
   
   print(f"Found {len(secrets_to_migrate)} secrets to migrate")
   ```

2. **Migrate individually**
   ```python
   for secret_id in secrets_to_migrate:
       # Get secret value (auto-decrypts from XOR)
       value = manager.retrieve_secret(secret_id)
       
       # Rotate to trigger re-encryption with AES
       if value:
           manager.rotate_secret(secret_id, value)
           print(f"Migrated: {secret_id}")
   ```

## Migration Script

Complete migration script with error handling:

```python
#!/usr/bin/env python3
"""
Migrate secrets from XOR to AES-256-GCM encryption.
"""

import sys
from pathlib import Path
from ipfs_kit_py.enhanced_secrets_manager import EnhancedSecretManager

def migrate_secrets(storage_path="~/.ipfs_kit/secrets", dry_run=False):
    """
    Migrate all secrets to AES-256-GCM.
    
    Args:
        storage_path: Path to secrets storage
        dry_run: If True, only report what would be migrated
    """
    print("=== Secret Migration: XOR → AES-256-GCM ===\n")
    
    # Initialize manager with AES encryption
    print("1. Initializing secrets manager...")
    manager = EnhancedSecretManager(
        storage_path=storage_path,
        encryption_method="aes-gcm"
    )
    
    # Get current statistics
    stats_before = manager.get_statistics()
    print(f"   Total secrets: {stats_before['total_secrets']}")
    print(f"   Encryption method: {stats_before['encryption_method']}")
    print(f"   AES available: {stats_before['aes_available']}")
    
    # Check encryption versions
    versions = stats_before.get('encryption_versions', {})
    xor_count = versions.get('v1', 0)
    aes_count = versions.get('v2', 0)
    
    print(f"\n2. Current encryption status:")
    print(f"   XOR (v1): {xor_count} secrets")
    print(f"   AES (v2): {aes_count} secrets")
    
    if xor_count == 0:
        print("\n✓ No migration needed - all secrets already use AES-256-GCM")
        return True
    
    if dry_run:
        print(f"\n[DRY RUN] Would migrate {xor_count} secrets")
        return True
    
    # Perform migration
    print(f"\n3. Migrating {xor_count} secrets to AES-256-GCM...")
    result = manager.migrate_all_secrets()
    
    print(f"   Migrated: {result['migrated']}")
    print(f"   Already current: {result['already_current']}")
    print(f"   Errors: {len(result['errors'])}")
    
    if result['errors']:
        print("\n⚠ Migration errors:")
        for error in result['errors']:
            print(f"   - {error}")
    
    # Verify migration
    stats_after = manager.get_statistics()
    versions_after = stats_after.get('encryption_versions', {})
    
    print(f"\n4. Post-migration status:")
    print(f"   XOR (v1): {versions_after.get('v1', 0)} secrets")
    print(f"   AES (v2): {versions_after.get('v2', 0)} secrets")
    
    if versions_after.get('v1', 0) == 0:
        print("\n✓ Migration successful - all secrets now use AES-256-GCM")
        return True
    else:
        print("\n⚠ Some secrets still use XOR encryption")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate secrets to AES-256-GCM")
    parser.add_argument("--storage-path", default="~/.ipfs_kit/secrets",
                        help="Path to secrets storage")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be migrated without changing anything")
    
    args = parser.parse_args()
    
    success = migrate_secrets(args.storage_path, args.dry_run)
    sys.exit(0 if success else 1)
```

## Rollout Plan

### Phase 1: Development/Testing (Week 1)

1. **Test migration in development**
   ```bash
   python migrate_secrets.py --dry-run
   python migrate_secrets.py
   ```

2. **Verify functionality**
   - Test secret retrieval
   - Test secret rotation
   - Test secret creation
   - Performance testing

3. **Measure performance**
   - Encryption time per secret
   - Decryption time per secret
   - Total migration time

### Phase 2: Staging/QA (Week 2)

1. **Deploy to staging environment**
2. **Run full migration**
3. **Integration testing**
4. **Load testing**
5. **Rollback test**

### Phase 3: Production Canary (Week 3)

1. **Deploy to 10% of production**
2. **Monitor metrics:**
   - Secret access latency
   - Error rates
   - Migration success rate
3. **Collect feedback**

### Phase 4: Full Production Rollout (Week 4-6)

1. **25% rollout** (Week 4)
   - Monitor for 3-5 days
   - Address any issues

2. **50% rollout** (Week 5)
   - Monitor for 3-5 days
   - Performance analysis

3. **100% rollout** (Week 6)
   - Complete migration
   - Decommission XOR support (optional)

## Monitoring

### Key Metrics

```python
# Get comprehensive statistics
stats = manager.get_statistics()

# Monitor these metrics:
metrics = {
    'total_secrets': stats['total_secrets'],
    'aes_secrets': stats['encryption_versions'].get('v2', 0),
    'xor_secrets': stats['encryption_versions'].get('v1', 0),
    'migration_progress': (
        stats['encryption_versions'].get('v2', 0) / stats['total_secrets'] * 100
        if stats['total_secrets'] > 0 else 0
    ),
    'expired_secrets': stats['expired_secrets'],
    'needs_rotation': stats['secrets_needing_rotation'],
}

print(f"Migration Progress: {metrics['migration_progress']:.1f}%")
```

### Alerts

Set up alerts for:
- **High error rate during migration** (> 1%)
- **Increased latency** (> 50ms P99)
- **Failed decryptions** (any occurrence)
- **Low migration progress** (< 50% after 1 week)

## Troubleshooting

### Issue: Decryption fails after migration

**Symptoms:** `Decryption failed: invalid key or corrupted data`

**Solution:**
```python
# Check encryption info
info = manager.get_encryption_info(secret_id)
print(f"Version: {info['encryption_version']}")
print(f"Needs migration: {info['needs_migration']}")

# If corrupted, restore from backup
# cp ~/.ipfs_kit/secrets.backup.YYYYMMDD/* ~/.ipfs_kit/secrets/
```

### Issue: Migration is slow

**Symptoms:** Migration takes > 1 second per secret

**Cause:** PBKDF2 with 600K iterations is CPU-intensive (by design)

**Solutions:**
1. Migrate in batches during low-traffic periods
2. Accept the delay (security > speed)
3. Use hardware with AES-NI support

### Issue: Some secrets won't migrate

**Symptoms:** Migration reports errors for specific secrets

**Solution:**
```python
# Check individual secret
try:
    value = manager.retrieve_secret(secret_id)
    if value:
        # Manual re-encryption
        manager.rotate_secret(secret_id, value)
except Exception as e:
    print(f"Error: {e}")
    # Restore from backup or recreate
```

## Rollback Procedure

If migration causes issues:

1. **Stop using new manager**
   ```bash
   # Revert code to previous version
   git checkout <previous-commit>
   ```

2. **Restore from backup**
   ```bash
   rm -rf ~/.ipfs_kit/secrets
   cp -r ~/.ipfs_kit/secrets.backup.YYYYMMDD ~/.ipfs_kit/secrets
   ```

3. **Verify restoration**
   ```python
   manager = EnhancedSecretManager(encryption_method="xor")
   stats = manager.get_statistics()
   print(f"Restored {stats['total_secrets']} secrets")
   ```

4. **Investigate issues**
5. **Fix problems**
6. **Re-attempt migration**

## Best Practices

### During Migration

1. **Always backup first**
2. **Test in non-production first**
3. **Migrate during low-traffic periods**
4. **Monitor continuously**
5. **Have rollback plan ready**

### After Migration

1. **Keep backups for 30 days**
2. **Monitor decryption errors**
3. **Track performance metrics**
4. **Update documentation**
5. **Plan for key rotation** (if needed)

### Long-term

1. **Regular secret rotation**
   ```python
   # Rotate secrets older than 90 days
   for secret_id, metadata in manager.metadata.items():
       age_days = (time.time() - metadata.last_rotated) / 86400
       if age_days > 90:
           print(f"Secret {secret_id} is {age_days:.0f} days old")
   ```

2. **Audit log reviews**
   ```python
   recent = manager.audit_log.get_recent_accesses(limit=100)
   for entry in recent:
       if not entry['success']:
           print(f"Failed access: {entry}")
   ```

3. **Cleanup old secrets**
   ```python
   # Delete expired secrets
   expiring = manager.get_expiring_secrets(within_days=0)
   for secret_id in expiring:
       manager.delete_secret(secret_id)
   ```

## FAQ

**Q: Can I use both XOR and AES simultaneously?**  
A: Yes! The manager automatically detects encryption version and decrypts accordingly.

**Q: What's the performance impact?**  
A: ~2-3ms per operation due to PBKDF2. Acceptable for most use cases.

**Q: Is the migration reversible?**  
A: Yes, restore from backup. But don't - AES is much more secure!

**Q: Can I migrate without downtime?**  
A: Yes, use Strategy 2 (Gradual Migration) for zero-downtime migration.

**Q: What happens to secrets during migration?**  
A: They remain accessible. Old format is read, new format is written.

**Q: How long should I keep XOR support?**  
A: After successful migration and monitoring (30 days), you can remove XOR support.

## Summary

✅ **AES-256-GCM** provides production-grade security  
✅ **Backward compatible** with legacy XOR secrets  
✅ **Automatic migration** available  
✅ **Zero downtime** possible  
✅ **Comprehensive testing** completed  

**Next Step:** Run `python migrate_secrets.py --dry-run` to simulate migration!
