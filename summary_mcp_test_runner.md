
================================================================================
                     MCP TEST RESULTS SUMMARY                       
================================================================================
Timestamp:      2025-05-12T20:32:46.558162
Server File:    final_mcp_server.py
Port:           9997
Total tests:    17
Passed:         13
Failed:         3
Skipped:        1
Success rate:   81.25% (excluding skipped tests)
================================================================================

Initial Probe Results:
  - list_tools: PASSED 
  - ipfs_version: PASSED {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found", "data": "ipfs_version"}, "id": 1747107166573}
  - vfs_ls_root: PASSED {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found", "data": "vfs_ls"}, "id": 1747107166579}

SOME TESTS FAILED. See mcp_test_results.json and mcp_test_runner.log for details.

Failed tools/operations:
  - Name: ipfs_cat, Category: ipfs, Details: {"jsonrpc": "2.0", "result": "{\"jsonrpc\": \"2.0\", \"error\": {\"code\": -32601, \"message\": \"Method not found\", \"data\": \"ipfs_cat\"}, \"id\": 1747107166630}", "id": 1747107166630}
  - Name: vfs_read, Category: vfs, Details: {"jsonrpc": "2.0", "result": "{\"jsonrpc\": \"2.0\", \"error\": {\"code\": -32601, \"message\": \"Method not found\", \"data\": \"vfs_read\"}, \"id\": 1747107166652}", "id": 1747107166652}
  - Name: vfs_ls, Category: vfs, Details: {"jsonrpc": "2.0", "result": "{\"jsonrpc\": \"2.0\", \"error\": {\"code\": -32601, \"message\": \"Method not found\", \"data\": \"vfs_ls\"}, \"id\": 1747107166658}", "id": 1747107166658}

Tool counts by category (from last successful list_tools):
- CORE: 0
- IPFS: 21
- VFS: 0
- OTHER: 32
================================================================================
