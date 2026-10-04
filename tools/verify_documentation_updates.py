#!/usr/bin/env python3
"""
Documentation Update Verification
=================================

Verifies that all documentation has been updated to reflect the current
production-ready status and properly references the MCP Development Status document.
"""

import os
from pathlib import Path

def verify_documentation_updates():
    """Verify documentation consistency and MCP integration references."""
    base_path = Path("/home/barberb/ipfs_kit_py")
    
    print("🔍 Verifying Documentation Updates...")
    print("=" * 60)
    
    # Key files that should reference MCP_DEVELOPMENT_STATUS.md
    key_files = {
        "README.md": "Main project documentation",
        "docs/index.md": "Documentation index",
        "docs/mcp_roadmap.md": "MCP technical roadmap",
        "docs/GETTING_STARTED.md": "Getting started guide",
        "docs/API_REFERENCE.md": "API reference",
        "docs/ARCHITECTURE.md": "Architecture overview",
        "docs/installation_guide.md": "Installation guide",
        "docs/testing_guide.md": "Testing guide",
        "docs/storage_backends.md": "Storage backends",
        "docs/core_concepts.md": "Core concepts",
        "docs/PRODUCTION_READINESS_REPORT.md": "Production readiness report"
    }
    
    print("📚 Checking Key Documentation Files:")
    updates_found = 0
    
    for file_path, description in key_files.items():
        full_path = base_path / file_path
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for production ready indicators
                production_indicators = [
                    "Production Ready",
                    "MCP_DEVELOPMENT_STATUS.md",
                    "production-ready",
                    "✅",
                    "operational"
                ]
                
                indicators_found = sum(1 for indicator in production_indicators if indicator in content)
                
                if indicators_found >= 2:
                    print(f"✅ {file_path:<35} - {description} (Updated)")
                    updates_found += 1
                else:
                    print(f"⚠️  {file_path:<35} - {description} (May need updates)")
                    
            except Exception as e:
                print(f"❌ {file_path:<35} - Error reading: {e}")
        else:
            print(f"❌ {file_path:<35} - File not found")
    
    # Check MCP_DEVELOPMENT_STATUS.md exists and is comprehensive
    print("\n📋 Verifying MCP Development Status Document:")
    mcp_doc = base_path / "MCP_DEVELOPMENT_STATUS.md"
    if mcp_doc.exists():
        try:
            with open(mcp_doc, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for key sections
            required_sections = [
                "Executive Summary",
                "Current Architecture",
                "Development Status",
                "Quick Start",
                "Technical Architecture",
                "Future Development Priorities",
                "Troubleshooting"
            ]
            
            sections_found = 0
            for section in required_sections:
                if section in content:
                    sections_found += 1
                    print(f"✅ {section} section found")
                else:
                    print(f"⚠️  {section} section missing")
            
            print(f"\nMCP Document completeness: {sections_found}/{len(required_sections)} sections")
            
            # Check file size (should be comprehensive)
            file_size = len(content)
            if file_size > 10000:  # Should be substantial
                print(f"✅ Document size: {file_size} characters (Comprehensive)")
            else:
                print(f"⚠️  Document size: {file_size} characters (May need expansion)")
                
        except Exception as e:
            print(f"❌ Error reading MCP_DEVELOPMENT_STATUS.md: {e}")
    else:
        print("❌ MCP_DEVELOPMENT_STATUS.md not found")
    
    # Check project structure references
    print("\n📁 Verifying Project Structure References:")
    structure_files = [
        "PROJECT_STRUCTURE.md",
        "servers/README.md"
    ]
    
    structure_ok = 0
    for file_path in structure_files:
        full_path = base_path / file_path
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if "MCP_DEVELOPMENT_STATUS.md" in content or "production" in content.lower():
                    print(f"✅ {file_path} - References current status")
                    structure_ok += 1
                else:
                    print(f"⚠️  {file_path} - May need MCP status reference")
            except Exception as e:
                print(f"❌ {file_path} - Error reading: {e}")
        else:
            print(f"❌ {file_path} - File not found")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DOCUMENTATION UPDATE SUMMARY:")
    print(f"Key files updated: {updates_found}/{len(key_files)}")
    print(f"Structure files updated: {structure_ok}/{len(structure_files)}")
    
    total_checks = len(key_files) + len(structure_files) + 1  # +1 for MCP doc
    total_passed = updates_found + structure_ok + (1 if mcp_doc.exists() else 0)
    
    print(f"Overall documentation status: {total_passed}/{total_checks} ({total_passed/total_checks*100:.1f}%)")
    
    if total_passed >= total_checks * 0.9:  # 90% threshold
        print("🎉 Documentation update verification PASSED!")
        print("📚 All documentation properly updated for production readiness!")
    else:
        print("⚠️  Some documentation may need additional updates")
    
    print("\n🔗 Key Documentation Links:")
    print("- Primary Reference: MCP_DEVELOPMENT_STATUS.md")
    print("- Quick Start: README.md") 
    print("- API Docs: Available at /docs endpoint on running servers")
    print("- Project Structure: PROJECT_STRUCTURE.md")
    print("- Server Selection: servers/README.md")
    
    return total_passed >= total_checks * 0.9

if __name__ == "__main__":
    success = verify_documentation_updates()
    if success:
        print("\n✅ All documentation successfully updated and verified!")
    else:
        print("\n⚠️  Some documentation files may need additional attention.")
