#!/usr/bin/env python3
"""
Targeted patch for ipfs_kit.py to add daemon configuration checks
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipfs_kit_patch")

def patch_ipfs_kit_start_daemons():
    """Patch the ipfs_kit module to include configuration checks in _start_required_daemons method."""
    
    # Read the current ipfs_kit.py file
    ipfs_kit_path = Path("ipfs_kit_py/ipfs_kit.py")
    
    if not ipfs_kit_path.exists():
        logger.error("ipfs_kit.py not found")
        return False
    
    # Read the current content
    with open(ipfs_kit_path, 'r') as f:
        content = f.read()
    
    # Check if patch is already applied
    if "daemon_config_manager" in content:
        logger.info("ipfs_kit.py already patched")
        return True
    
    # Find the line where we log "Starting required daemons for role"
    lines = content.split('\n')
    patched_lines = []
    patch_applied = False
    
    for i, line in enumerate(lines):
        patched_lines.append(line)
        
        # Look for the log line about starting required daemons
        if 'Starting required daemons for role' in line and not patch_applied:
            # Add configuration check after this line
            patched_lines.extend([
                "",
                "        # Ensure all daemons are properly configured before starting",
                "        try:",
                "            from .daemon_config_manager import DaemonConfigManager",
                "            config_manager = DaemonConfigManager(self)",
                "            config_result = config_manager.check_and_configure_all_daemons()",
                "            if not config_result.get('overall_success', False):",
                "                self.logger.warning('Some daemon configurations failed, but continuing...')",
                "                self.logger.warning(f'Config summary: {config_result.get(\"summary\", \"No summary\")}')",
                "            else:",
                "                self.logger.info('All daemon configurations validated successfully')",
                "        except Exception as config_error:",
                "            self.logger.warning(f'Daemon configuration check failed: {config_error}')",
                "            self.logger.warning('Continuing with daemon startup...')",
                ""
            ])
            patch_applied = True
    
    if not patch_applied:
        logger.warning("Target line not found in ipfs_kit.py")
        return False
    
    # Write the patched content
    with open(ipfs_kit_path, 'w') as f:
        f.write('\n'.join(patched_lines))
    
    logger.info("ipfs_kit.py patched successfully")
    return True

def main():
    """Main function to apply the patch."""
    print("🔧 Applying targeted daemon configuration patch to ipfs_kit.py...")
    
    result = patch_ipfs_kit_start_daemons()
    
    if result:
        print("✅ ipfs_kit.py patched successfully!")
        print("\n💡 The patch adds daemon configuration checks to the _start_required_daemons method.")
        print("💡 This ensures proper configuration before daemon startup.")
        return 0
    else:
        print("❌ ipfs_kit.py patch failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
