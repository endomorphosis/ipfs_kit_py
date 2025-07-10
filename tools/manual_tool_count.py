#!/usr/bin/env python3
"""
Manual MCP Server Tool Count Test
"""

# Count tools from the file directly
import re
import os

def count_tools_from_file():
    """Count tools by parsing the file directly"""
    file_path = "/home/barberb/ipfs_kit_py/mcp/enhanced_mcp_server_with_daemon_mgmt.py"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find all tool definitions
    tool_pattern = r'"([a-z_]+)": \{\s*"name": "\1"'
    tools = re.findall(tool_pattern, content)
    
    print(f"Tools found in {file_path}:")
    print(f"Total: {len(tools)} tools")
    
    # Categorize
    categories = {
        "IPFS Core": [],
        "IPFS Advanced": [],
        "IPFS MFS": [],
        "VFS": [],
        "System": []
    }
    
    for tool in tools:
        if tool.startswith("ipfs_"):
            if any(x in tool for x in ["dht_", "name_", "pubsub_"]):
                categories["IPFS Advanced"].append(tool)
            elif "files_" in tool:
                categories["IPFS MFS"].append(tool)
            else:
                categories["IPFS Core"].append(tool)
        elif tool.startswith("vfs_"):
            categories["VFS"].append(tool)
        else:
            categories["System"].append(tool)
    
    print("\nBreakdown by category:")
    total_check = 0
    for category, tool_list in categories.items():
        if tool_list:  # Only show categories with tools
            print(f"  {category}: {len(tool_list)} tools")
            for tool in sorted(tool_list):
                print(f"    - {tool}")
            total_check += len(tool_list)
    
    print(f"\nVerification: {total_check} tools total")
    
    # Expected counts
    expected = {
        "IPFS Core": 18,
        "IPFS Advanced": 8, 
        "IPFS MFS": 10,
        "VFS": 12,
        "System": 1
    }
    
    print(f"\nExpected vs Actual:")
    all_good = True
    for category, expected_count in expected.items():
        actual_count = len(categories[category])
        status = "✓" if actual_count == expected_count else "✗"
        print(f"  {status} {category}: {actual_count}/{expected_count}")
        if actual_count != expected_count:
            all_good = False
    
    total_expected = sum(expected.values())
    print(f"\nOverall: {total_check}/{total_expected} tools {'✓' if all_good else '✗'}")
    
    return all_good

if __name__ == "__main__":
    success = count_tools_from_file()
    if success:
        print("\n🎉 All expected tools are present!")
    else:
        print("\n⚠️  Some tools may be missing or miscategorized.")
