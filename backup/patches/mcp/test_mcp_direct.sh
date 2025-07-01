#!/bin/bash
# Direct MCP Server Test
# This script tests MCP server endpoints directly using curl

echo "=== MCP Server Direct Test ==="
echo "Testing on $(date)"

# Base URL for MCP server
MCP_URL="http://localhost:9994"

# Test 1: Health check
echo -e "\n1. Testing server health endpoint..."
curl -s $MCP_URL/health | jq

# Test 2: Initialize endpoint
echo -e "\n2. Testing initialize endpoint..."
curl -s $MCP_URL/initialize | jq

# Test 3: Try a specific tool with POST
echo -e "\n3. Testing ipfs_add tool..."
curl -s -X POST \
  $MCP_URL/mcp/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ipfs_add",
    "server": "ipfs-kit-mcp",
    "args": {
      "content": "Hello IPFS!",
      "filename": "test.txt",
      "pin": true
    }
  }' | jq

# Test 4: Try list_files tool
echo -e "\n4. Testing list_files tool..."
curl -s -X POST \
  $MCP_URL/mcp/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "list_files",
    "server": "ipfs-kit-mcp",
    "args": {
      "directory": ".",
      "recursive": false
    }
  }' | jq

# Test 5: Try read_file tool
echo -e "\n5. Testing read_file tool..."
curl -s -X POST \
  $MCP_URL/mcp/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "read_file",
    "server": "ipfs-kit-mcp",
    "args": {
      "path": "README.md"
    }
  }' | jq

echo -e "\n=== Test Complete ==="
echo "If you see any 404 errors, the MCP server API might have changed."
echo "Check the server logs for more details."
