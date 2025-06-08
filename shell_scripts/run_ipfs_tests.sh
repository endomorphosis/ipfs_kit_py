#!/bin/bash
# Run IPFS MCP Tests with full output
echo "Starting IPFS MCP Tools Tests..."
python3 test_ipfs_mcp_tools.py --verbose 2>&1 | tee ipfs_mcp_tests.log
exit_code=${PIPESTATUS[0]}
echo "Test completed with exit code: $exit_code"
