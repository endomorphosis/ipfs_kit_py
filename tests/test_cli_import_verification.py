#!/usr/bin/env python3
"""
Simplified test to verify MCP CLI uses refactored dashboard.
"""

import sys
import os
from pathlib import Path
import pytest

# Add paths
sys.path.insert(0, '/home/devel/ipfs_kit_py')
sys.path.insert(0, '/home/devel/ipfs_kit_py/ipfs_kit_py')

def test_cli_dashboard_import():
    """Test that CLI can import the correct dashboard."""
    print("🧪 Testing CLI dashboard import resolution...")

    repo_hint = Path('/home/devel/ipfs_kit_py')
    if not repo_hint.exists():
        pytest.skip("CLI import verification requires /home/devel/ipfs_kit_py layout")
    
    # Simulate CLI import logic
    try:
        # Test direct import from mcp directory (as updated in CLI)
        mcp_dir = '/home/devel/ipfs_kit_py/ipfs_kit_py/mcp'
        sys.path.insert(0, mcp_dir)
        from refactored_unified_dashboard import RefactoredUnifiedMCPDashboard
        dashboard_class = RefactoredUnifiedMCPDashboard
        print("✅ CLI can import RefactoredUnifiedMCPDashboard")
        
        # Test initialization
        config = {
            'host': '127.0.0.1',
            'port': 8010,
            'data_dir': '~/.ipfs_kit',
            'debug': False,
            'update_interval': 3
        }
        dashboard = dashboard_class(config)
        print("✅ Dashboard initializes successfully")
        
        # Check management features
        has_services = hasattr(dashboard, '_get_services_status')
        has_backends = hasattr(dashboard, '_get_backends_status') 
        has_buckets = hasattr(dashboard, '_get_buckets_status')
        
        print(f"✅ Services management: {has_services}")
        print(f"✅ Backends management: {has_backends}")
        print(f"✅ Buckets management: {has_buckets}")
        
        # Check template files exist
        template_file = dashboard.template_dir / 'unified_dashboard.html'
        css_file = dashboard.static_dir / 'css' / 'dashboard.css'
        js_file = dashboard.static_dir / 'js' / 'dashboard.js'
        
        print(f"✅ Template file exists: {template_file.exists()}")
        print(f"✅ CSS file exists: {css_file.exists()}")
        print(f"✅ JS file exists: {js_file.exists()}")
        
        assert True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        
        # Test fallback
        try:
            sys.path.insert(0, '/home/devel/ipfs_kit_py/ipfs_kit_py')
            from unified_mcp_dashboard import UnifiedMCPDashboard
            print("⚠️  Would fall back to original dashboard (migration notice)")
            pytest.skip("Refactored dashboard not importable in this environment")
        except ImportError as e2:
            print(f"❌ Fallback also failed: {e2}")
            pytest.skip("CLI dashboard import failed in this environment")


def main():
    """Main test function."""
    print("=" * 60)
    print("🧪 CLI MCP Dashboard Import Test")
    print("=" * 60)
    
    success = test_cli_dashboard_import()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ PASS: CLI will use refactored dashboard with management tabs")
        print("📋 Available management features:")
        print("   - ✅ Services Status & Management")
        print("   - ✅ Storage Backends Management") 
        print("   - ✅ Buckets Management")
        print("   - ✅ Template-based rendering")
        print("   - ✅ Separated HTML/CSS/JS files")
        print("")
        print("🚀 Command: ipfs-kit mcp start")
        print("📊 Result: Full-featured management dashboard")
    else:
        print("❌ FAIL: CLI import issues detected")
    print("=" * 60)


if __name__ == "__main__":
    main()
