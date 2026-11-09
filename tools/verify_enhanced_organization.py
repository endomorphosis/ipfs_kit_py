#!/usr/bin/env python3
"""
Enhanced Project Structure Verification
=======================================

Verifies the logical organization of the IPFS Kit project from a maintainer's perspective.
"""

import os
from pathlib import Path

def check_directory_structure():
    """Verify the main directory structure is logical and complete."""
    base_path = Path("/home/barberb/ipfs_kit_py")
    
    print("🔍 Verifying Enhanced Project Structure...")
    print("=" * 60)
    
    # Essential root level files (production ready only)
    print("\n📁 Root Level - Production Ready Files:")
    root_essentials = [
        "standalone_cluster_server.py",  # Primary production server
        "start_3_node_cluster.py",       # Production cluster launcher
        "main.py",                       # Main entry point
        "README.md",                     # Primary documentation
        "CHANGELOG.md",                  # Version history
        "PROJECT_STRUCTURE.md",          # Structure documentation
        "pyproject.toml",                # Python project config
        "setup.py",                      # Package setup
        "LICENSE",                       # License
        "Makefile"                       # Build commands
    ]
    
    root_ok = 0
    for file in root_essentials:
        path = base_path / file
        if path.exists():
            print(f"✅ {file}")
            root_ok += 1
        else:
            print(f"❌ {file} - MISSING")
    
    # Organized directories
    print("\n📁 Organized Directories:")
    directories = {
        "ipfs_kit_py/": "Core Python package",
        "cluster/": "Cluster management",
        "servers/": "Development servers",
        "tests/": "Testing & validation",
        "tools/": "Development tools",
        "bin/": "Demonstration scripts",
        "docs/": "Documentation",
        "examples/": "Code examples",
        "scripts/": "Utility scripts",
        "config/": "Configuration files",
        "deployment/": "Deployment resources",
        "logs/": "Log files",
        "archive/": "Archived content"
    }
    
    dir_ok = 0
    for dir_name, description in directories.items():
        path = base_path / dir_name
        if path.exists() and path.is_dir():
            print(f"✅ {dir_name:<15} - {description}")
            dir_ok += 1
        else:
            print(f"❌ {dir_name:<15} - MISSING")
    
    # Specialized documentation organization
    print("\n📁 Documentation Organization:")
    doc_structure = {
        "docs/summaries/": "Project summaries and status",
        "docs/integration/": "Integration documentation", 
        "docs/workflows/": "Workflow documentation"
    }
    
    doc_ok = 0
    for doc_dir, description in doc_structure.items():
        path = base_path / doc_dir
        if path.exists() and path.is_dir():
            print(f"✅ {doc_dir:<20} - {description}")
            doc_ok += 1
        else:
            print(f"❌ {doc_dir:<20} - MISSING")
    
    # Verify servers directory organization
    print("\n📁 Servers Directory Content:")
    servers_path = base_path / "servers"
    if servers_path.exists():
        server_files = list(servers_path.glob("*.py"))
        readme_exists = (servers_path / "README.md").exists()
        print(f"✅ Found {len(server_files)} development server files")
        print(f"{'✅' if readme_exists else '❌'} servers/README.md")
        
        server_ok = len(server_files) + (1 if readme_exists else 0)
    else:
        server_ok = 0
        print("❌ servers/ directory missing")
    
    # Check for clean root (no clutter)
    print("\n🧹 Root Level Cleanliness Check:")
    root_files = [f for f in base_path.iterdir() if f.is_file()]
    
    # Count by type
    py_files = [f for f in root_files if f.suffix == '.py']
    md_files = [f for f in root_files if f.suffix == '.md']
    config_files = [f for f in root_files if f.suffix in ['.toml', '.txt', '.json']]
    other_files = [f for f in root_files if f.suffix not in ['.py', '.md', '.toml', '.txt', '.json']]
    
    print(f"📊 Root file count: {len(root_files)} total")
    print(f"   - Python files: {len(py_files)} (should be ~3 for production servers)")
    print(f"   - Markdown files: {len(md_files)} (documentation)")
    print(f"   - Config files: {len(config_files)} (project config)")
    print(f"   - Other files: {len(other_files)} (should be minimal)")
    
    clean_root = len(root_files) < 15  # Reasonable threshold for clean root
    print(f"{'✅' if clean_root else '⚠️ '} Root directory {'clean' if clean_root else 'may have clutter'}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 ENHANCED ORGANIZATION SUMMARY:")
    print(f"Essential root files: {root_ok}/{len(root_essentials)}")
    print(f"Organized directories: {dir_ok}/{len(directories)}")
    print(f"Documentation structure: {doc_ok}/{len(doc_structure)}")
    print(f"Servers organization: {server_ok}/{'?' if not servers_path.exists() else len(server_files) + 1}")
    print(f"Root cleanliness: {'✅' if clean_root else '⚠️'}")
    
    total_checks = len(root_essentials) + len(directories) + len(doc_structure)
    total_passed = root_ok + dir_ok + doc_ok
    
    print(f"\nOverall organization: {total_passed}/{total_checks} ({total_passed/total_checks*100:.1f}%)")
    
    if total_passed >= total_checks * 0.9:  # 90% threshold
        print("🎉 Enhanced organization verification PASSED!")
        print("📁 Project structure is maintainer-friendly and production-ready!")
    else:
        print("⚠️  Some organizational improvements needed")
    
    return total_passed >= total_checks * 0.9

def verify_maintainer_workflow():
    """Verify that common maintainer workflows are supported."""
    base_path = Path("/home/barberb/ipfs_kit_py")
    
    print("\n🔧 Maintainer Workflow Verification:")
    
    workflows = {
        "Production deployment": base_path / "start_3_node_cluster.py",
        "Development server": base_path / "servers" / "enhanced_mcp_server_with_full_config.py", 
        "Running tests": base_path / "tests",
        "Development tools": base_path / "tools",
        "Documentation": base_path / "docs",
        "Configuration": base_path / "config",
        "Examples": base_path / "examples"
    }
    
    workflow_ok = 0
    for workflow, path in workflows.items():
        if path.exists():
            print(f"✅ {workflow}")
            workflow_ok += 1
        else:
            print(f"❌ {workflow} - path missing: {path}")
    
    print(f"\nWorkflow support: {workflow_ok}/{len(workflows)} ({workflow_ok/len(workflows)*100:.1f}%)")
    
    return workflow_ok == len(workflows)

if __name__ == "__main__":
    structure_ok = check_directory_structure()
    workflow_ok = verify_maintainer_workflow()
    
    print("\n" + "=" * 60)
    if structure_ok and workflow_ok:
        print("🎯 FINAL RESULT: Enhanced organization verification PASSED!")
        print("🚀 Project is optimally organized for maintainer success!")
    else:
        print("⚠️  FINAL RESULT: Some areas need attention for optimal organization")
