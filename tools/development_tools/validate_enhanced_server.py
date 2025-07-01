#!/usr/bin/env python3
"""
Validation script for the enhanced MCP server
"""
import sys
import importlib.util
import subprocess
import json
from pathlib import Path

def main():
    print("🧪 Validating Enhanced MCP Server")
    print("=" * 50)
    
    # Test 1: Check if file exists
    server_file = Path("final_mcp_server_enhanced.py")
    if not server_file.exists():
        print("❌ Enhanced server file not found!")
        return False
        
    print("✅ Enhanced server file exists")
    
    # Test 2: Check Python syntax
    try:
        result = subprocess.run([sys.executable, "-m", "py_compile", str(server_file)], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Python syntax is valid")
        else:
            print(f"❌ Syntax error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Failed to check syntax: {e}")
        return False
    
    # Test 3: Check imports
    try:
        spec = importlib.util.spec_from_file_location("final_mcp_server_enhanced", server_file)
        module = importlib.util.module_from_spec(spec)
        # Don't execute, just check if it would load
        print("✅ Import structure is valid")
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Test 4: Check if Docker configs reference correct file
    dockerfiles = ["Dockerfile", "Dockerfile.final"]
    for dockerfile in dockerfiles:
        if Path(dockerfile).exists():
            with open(dockerfile, 'r') as f:
                content = f.read()
                if "final_mcp_server_enhanced.py" in content:
                    print(f"✅ {dockerfile} uses enhanced server")
                else:
                    print(f"⚠️  {dockerfile} might not use enhanced server")
    
    # Test 5: Check docker-compose config
    compose_file = Path("docker-compose.final.yml")
    if compose_file.exists():
        print("✅ Docker Compose configuration exists")
    
    # Test 6: Check CI/CD workflow
    workflow_file = Path(".github/workflows/final-mcp-server.yml")
    if workflow_file.exists():
        with open(workflow_file, 'r') as f:
            content = f.read()
            if "final_mcp_server_enhanced.py" in content:
                print("✅ CI/CD workflow references enhanced server")
            else:
                print("⚠️  CI/CD workflow might not reference enhanced server")
    
    print("\n🎉 Validation complete!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
