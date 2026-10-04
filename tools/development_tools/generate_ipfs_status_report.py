#!/usr/bin/env python3
"""
IPFS Tools Registration Status Report
"""

import sys
import json
from datetime import datetime

def generate_report():
    """Generate a comprehensive report on IPFS tools registration status"""
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "ipfs_tools_registry": {},
        "tool_categories": {},
        "registration_status": "VERIFIED",
        "issues_found": [],
        "recommendations": []
    }
    
    try:
        # Check IPFS tools registry
        from ipfs_tools_registry import IPFS_TOOLS
        
        report["ipfs_tools_registry"] = {
            "status": "AVAILABLE",
            "total_tools": len(IPFS_TOOLS),
            "tools_list": [tool["name"] for tool in IPFS_TOOLS[:10]]  # First 10 for brevity
        }
        
        # Categorize tools
        categories = {}
        for tool in IPFS_TOOLS:
            name = tool["name"]
            if "_" in name:
                category = name.split("_")[1]
                categories[category] = categories.get(category, 0) + 1
        
        report["tool_categories"] = categories
        
        # Check for common IPFS operations
        essential_tools = ["ipfs_add", "ipfs_cat", "ipfs_pin_add", "ipfs_pin_rm", "ipfs_files_ls"]
        available_essential = []
        missing_essential = []
        
        tool_names = [tool["name"] for tool in IPFS_TOOLS]
        for essential in essential_tools:
            if essential in tool_names:
                available_essential.append(essential)
            else:
                missing_essential.append(essential)
        
        report["essential_tools"] = {
            "available": available_essential,
            "missing": missing_essential
        }
        
        if missing_essential:
            report["issues_found"].append(f"Missing essential tools: {missing_essential}")
        
        # Check unified_ipfs_tools status
        try:
            import unified_ipfs_tools
            report["unified_ipfs_tools"] = {
                "status": "IMPORTABLE",
                "has_register_function": hasattr(unified_ipfs_tools, 'register_all_ipfs_tools')
            }
        except Exception as e:
            report["unified_ipfs_tools"] = {
                "status": "ERROR",
                "error": str(e)
            }
            report["issues_found"].append(f"unified_ipfs_tools import error: {e}")
        
        # Add recommendations
        if not report["issues_found"]:
            report["recommendations"].append("IPFS tools registry is fully functional")
            report["recommendations"].append("Ready for MCP server integration")
        else:
            report["recommendations"].append("Fix identified issues before deployment")
        
    except Exception as e:
        report["ipfs_tools_registry"] = {
            "status": "ERROR",
            "error": str(e)
        }
        report["registration_status"] = "FAILED"
        report["issues_found"].append(f"Registry import error: {e}")
    
    return report

def print_report(report):
    """Print the report in a readable format"""
    print("=" * 60)
    print("IPFS TOOLS REGISTRATION STATUS REPORT")
    print("=" * 60)
    print(f"Generated: {report['timestamp']}")
    print(f"Status: {report['registration_status']}")
    print()
    
    # Registry status
    if "ipfs_tools_registry" in report:
        registry = report["ipfs_tools_registry"]
        print(f"IPFS Tools Registry: {registry.get('status', 'UNKNOWN')}")
        if registry.get("status") == "AVAILABLE":
            print(f"Total Tools: {registry['total_tools']}")
            print("Sample Tools:")
            for tool in registry.get("tools_list", []):
                print(f"  - {tool}")
        print()
    
    # Categories
    if "tool_categories" in report and report["tool_categories"]:
        print("Tool Categories:")
        for category, count in sorted(report["tool_categories"].items()):
            print(f"  {category}: {count} tools")
        print()
    
    # Essential tools
    if "essential_tools" in report:
        essential = report["essential_tools"]
        print(f"Essential Tools Available: {len(essential['available'])}/{len(essential['available']) + len(essential['missing'])}")
        if essential["available"]:
            print("✅ Available:", ", ".join(essential["available"]))
        if essential["missing"]:
            print("❌ Missing:", ", ".join(essential["missing"]))
        print()
    
    # unified_ipfs_tools status
    if "unified_ipfs_tools" in report:
        unified = report["unified_ipfs_tools"]
        print(f"unified_ipfs_tools: {unified['status']}")
        if unified.get("has_register_function"):
            print("✅ Has register_all_ipfs_tools function")
        print()
    
    # Issues
    if report["issues_found"]:
        print("❌ ISSUES FOUND:")
        for issue in report["issues_found"]:
            print(f"  - {issue}")
        print()
    
    # Recommendations
    if report["recommendations"]:
        print("📋 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")
    
    print("=" * 60)

def main():
    print("Generating IPFS tools registration status report...")
    
    report = generate_report()
    print_report(report)
    
    # Also save as JSON
    with open("ipfs_tools_status_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: ipfs_tools_status_report.json")
    
    # Return appropriate exit code
    if report["registration_status"] == "VERIFIED" and not report["issues_found"]:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
