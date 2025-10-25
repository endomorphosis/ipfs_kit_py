#!/usr/bin/env python3
"""
Verify that the enhanced_service_monitoring.html template has all the configuration field handlers.

Run this script to confirm the template changes are present.
"""

import os
import sys
from pathlib import Path

def check_template():
    # Find the template file
    script_dir = Path(__file__).parent
    template_path = script_dir / "ipfs_kit_py" / "mcp" / "dashboard_templates" / "enhanced_service_monitoring.html"
    
    if not template_path.exists():
        print(f"❌ Template not found at: {template_path}")
        return False
    
    print(f"✅ Template found at: {template_path}")
    print(f"   Size: {template_path.stat().st_size} bytes")
    print(f"   Modified: {template_path.stat().st_mtime}")
    
    # Read template content
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for key field handlers
    checks = [
        ("password field", "configKeys.includes('password')"),
        ("endpoint field", "configKeys.includes('endpoint')"),
        ("space field", "configKeys.includes('space')"),
        ("path field", "configKeys.includes('path')"),
        ("node_url field", "configKeys.includes('node_url')"),
        ("client_id field", "configKeys.includes('client_id')"),
        ("compression field", "configKeys.includes('compression')"),
        ("config hints helper", "const getHint = (fieldName)"),
        ("config hints usage", "${getHint"),
    ]
    
    print("\n🔍 Checking for field handlers...")
    all_found = True
    for name, pattern in checks:
        if pattern in content:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} MISSING!")
            all_found = False
    
    # Count field handlers
    field_count = content.count("configKeys.includes(")
    print(f"\n📊 Total field handlers: {field_count}")
    print(f"   Expected: 26+ (was 11 before fix)")
    
    if field_count < 20:
        print(f"   ⚠️  WARNING: Expected more field handlers!")
        all_found = False
    
    # Check for dashboard loading
    dashboard_path = script_dir / "ipfs_kit_py" / "mcp" / "dashboard" / "consolidated_mcp_dashboard.py"
    if dashboard_path.exists():
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            dashboard_content = f.read()
        
        print(f"\n🔍 Verifying dashboard loads this template...")
        if 'enhanced_service_monitoring.html' in dashboard_content:
            print(f"  ✅ Dashboard references enhanced_service_monitoring.html")
            
            # Find the line number
            for i, line in enumerate(dashboard_content.split('\n'), 1):
                if 'enhanced_service_monitoring.html' in line:
                    print(f"     Line {i}: {line.strip()}")
        else:
            print(f"  ❌ Dashboard doesn't reference template!")
            all_found = False
    
    print("\n" + "="*60)
    if all_found and field_count >= 20:
        print("✅ ALL CHECKS PASSED!")
        print("\nThe template has all the required field handlers.")
        print("\nIf you're not seeing them in the browser:")
        print("  1. Restart the dashboard: pkill -f consolidated_mcp_dashboard && ipfs-kit mcp start")
        print("  2. Clear browser cache: Ctrl+Shift+R or open incognito window")
        print("  3. Navigate to: http://localhost:8004/services")
        print("  4. Click Configure on FTP service")
        print("  5. Should see: Host, Port, Username, Password, Path fields")
        return True
    else:
        print("❌ SOME CHECKS FAILED!")
        print("\nThe template may not have all the required changes.")
        return False

if __name__ == "__main__":
    success = check_template()
    sys.exit(0 if success else 1)
