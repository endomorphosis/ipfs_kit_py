#!/usr/bin/env python3
"""
IPFS-Kit CLI Entry Point with Fallback
"""

import sys

def main():
    """Main entry point with fallback for compatibility issues."""
    try:
        # Try the full CLI first
        from ipfs_kit_py.cli import sync_main
        return sync_main()
    except Exception as e:
        # Check if it's a known compatibility issue
        error_str = str(e)
        if any(keyword in error_str for keyword in ['multicodec', 'deprecated', 'Invalid multicodec status']):
            print(f"⚠️  Using fallback CLI due to compatibility issue: {e}")
            print("📋 Loading simplified CLI...")
            
            # Use the simple CLI as fallback
            try:
                import sys
                import os
                # Add the current directory to Python path
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                
                from simple_cli import simple_sync_main
                return simple_sync_main()
            except Exception as fallback_error:
                print(f"❌ Fallback CLI also failed: {fallback_error}")
                return 1
        else:
            # Re-raise other errors
            raise

if __name__ == '__main__':
    sys.exit(main())
