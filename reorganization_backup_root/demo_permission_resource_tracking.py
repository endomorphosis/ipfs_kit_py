#!/usr/bin/env python3
"""
Demo: Permission-Aware Resource Tracking CLI

This demo showcases the enhanced CLI resource tracking system that monitors 
permissioned storage backends based on their storage consumption and traffic patterns.

Features demonstrated:
1. Backend status with permission context
2. Resource usage with permission limits
3. Permission management and compliance
4. Traffic monitoring across backends
5. Export with permission data
"""

import os
import sys
import subprocess
import time

def run_cli_command(cmd, description):
    """Run a CLI command and display results."""
    print(f"\n{'='*60}")
    print(f"🔸 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}")
    print("-" * 40)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd="/home/devel/ipfs_kit_py")
        print(result.stdout)
        if result.stderr:
            print(f"⚠️  Stderr: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():    
    print("🚀 Permission-Aware Resource Tracking CLI Demo")
    print("=" * 60)
    print("This demo shows how to track permissioned storage backends")
    print("based on their storage consumption and traffic patterns.")
    
    # 1. Show current backend status with permission information
    run_cli_command(
        "python -m ipfs_kit_py.cli resource status",
        "Backend Status with Permission Context"
    )
    
    # 2. List all backend permissions
    run_cli_command(
        "python -m ipfs_kit_py.cli resource permissions --action list",
        "Storage Backend Permissions Summary"
    )
    
    # 3. Show resource usage with permission context
    run_cli_command(
        "python -m ipfs_kit_py.cli resource usage --period day",
        "Daily Resource Usage - All Permissioned Backends"
    )
    
    # 4. Show only backends with permission constraints (if any had limits)
    run_cli_command(
        "python -m ipfs_kit_py.cli resource usage --permissions-only",
        "Resource Usage - Only Permission-Controlled Backends"
    )
    
    # 5. Set resource limits for demonstration
    run_cli_command(
        "python -m ipfs_kit_py.cli resource permissions --action set-limits --backend s3_primary --storage-quota 100 --bandwidth-quota 20",
        "Setting Resource Limits for s3_primary Backend"
    )
    
    # 6. Check permission compliance
    run_cli_command(
        "python -m ipfs_kit_py.cli resource permissions --action check --backend s3_primary",
        "Permission Compliance Check for s3_primary"
    )
    
    # 7. Show traffic patterns
    run_cli_command(
        "python -m ipfs_kit_py.cli resource traffic --backend s3_primary",
        "Traffic Patterns for s3_primary Backend"
    )
    
    # 8. Show detailed resource usage with permission context
    run_cli_command(
        "python -m ipfs_kit_py.cli resource details --backend s3_primary --hours 24 --show-permissions",
        "Detailed Resource Usage with Permission Context"
    )
    
    # 9. Backend status with permission checks
    run_cli_command(
        "python -m ipfs_kit_py.cli resource status --permission-check",
        "Backend Status with Permission Compliance Check"
    )
    
    # 10. Export resource data with permission information
    export_file = "/tmp/resource_export_with_permissions.json"
    run_cli_command(
        f"python -m ipfs_kit_py.cli resource export --hours 24 --output {export_file} --include-permissions",
        "Export Resource Data with Permission Information"
    )
    
    if os.path.exists(export_file):
        print(f"\n📁 Export file created: {export_file}")
        # Show a sample of the exported data
        try:
            with open(export_file, 'r') as f:
                import json
                data = json.load(f)
                if data:
                    print(f"📊 Sample exported record:")
                    sample = data[0]
                    for key, value in sample.items():
                        print(f"  {key}: {value}")
        except Exception as e:
            print(f"⚠️  Could not read export file: {e}")
    
    print(f"\n{'='*60}")
    print("✅ Demo completed!")
    print("=" * 60)
    print("Key Features Demonstrated:")
    print("• 🔐 Permission-aware backend status")
    print("• 📊 Resource usage with permission limits")
    print("• 🔧 Permission management and limit setting")
    print("• 🚦 Permission compliance checking")
    print("• 📡 Traffic monitoring across backends")
    print("• 📤 Data export with permission context")
    print("• 🎯 Filtering for permission-controlled backends only")
    print("\nAll storage backends are monitored for:")
    print("• Storage consumption vs. quotas")
    print("• Bandwidth usage vs. limits")
    print("• Permission compliance status")
    print("• Traffic patterns and trends")

if __name__ == "__main__":
    main()
