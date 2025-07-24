#!/usr/bin/env python3
"""
Fix Lotus configuration to enable ChainIndexer when EthRPC is enabled.
"""

import os
import re

def fix_lotus_config():
    """Fix the Lotus configuration file to add EnableIndexer = true."""
    
    lotus_config_path = "/home/devel/.lotus/config.toml"
    
    if not os.path.exists(lotus_config_path):
        print(f"❌ Lotus config file not found at: {lotus_config_path}")
        return False
    
    try:
        # Read the current configuration
        with open(lotus_config_path, 'r') as f:
            config_content = f.read()
        
        print("📋 Current Lotus configuration:")
        print(config_content)
        print("\n" + "="*50 + "\n")
        
        # Check if ChainIndexer section already exists
        if '[ChainIndexer]' in config_content:
            print("⚠️  ChainIndexer section already exists")
            
            # Check if EnableIndexer is already set
            if 'EnableIndexer = true' in config_content:
                print("✅ EnableIndexer is already set to true")
                return True
            else:
                # Add EnableIndexer to existing ChainIndexer section
                config_content = re.sub(
                    r'(\[ChainIndexer\])',
                    r'\1\n  EnableIndexer = true',
                    config_content
                )
        else:
            # Add ChainIndexer section before Fevm section
            if '[Fevm]' in config_content:
                config_content = config_content.replace(
                    '[Fevm]',
                    '[ChainIndexer]\n  EnableIndexer = true\n  \n[Fevm]'
                )
            else:
                # Add at the end if no Fevm section
                config_content += '\n\n[ChainIndexer]\n  EnableIndexer = true\n'
        
        # Write the updated configuration
        with open(lotus_config_path, 'w') as f:
            f.write(config_content)
        
        print("✅ Updated Lotus configuration:")
        print(config_content)
        print("\n✅ Lotus configuration fixed successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing Lotus configuration: {e}")
        return False

if __name__ == "__main__":
    success = fix_lotus_config()
    if success:
        print("\n🚀 Lotus should now start correctly. Try starting it again.")
    else:
        print("\n❌ Failed to fix Lotus configuration.")
