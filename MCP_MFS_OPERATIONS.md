# MFS Operations in MCP Server

This document provides details on the implementation of IPFS MFS (Mutable File System) operations in the MCP server.

## Overview

The Mutable File System (MFS) is an IPFS feature that provides a traditional file system interface on top of the immutable IPFS content-addressed storage. MFS allows users to add, modify, and remove files in a familiar way while leveraging IPFS's content addressing underneath.

All MFS operations have been implemented in the MCP server, providing a complete set of file system operations through the API.

## Implemented Operations

The following MFS operations have been implemented in the MCP server:

| Operation | Endpoint | Method | Description |
|-----------|----------|--------|-------------|
| List Files | `/ipfs/files/ls` | GET/POST | List contents of a directory in MFS |
| Make Directory | `/ipfs/files/mkdir` | POST | Create a directory in MFS |
| Get File Stats | `/ipfs/files/stat` | GET/POST | Get information about a file or directory in MFS |
| Read File | `/ipfs/files/read` | GET/POST | Read content from a file in MFS |
| Write File | `/ipfs/files/write` | POST | Write content to a file in MFS |
| Remove File | `/ipfs/files/rm` | POST/DELETE | Remove a file or directory from MFS |

## Implementation Details

### Model Implementation

The MFS operations are implemented as methods in the `IPFSModel` class:

```python
def files_mkdir(self, path: str, parents: bool = False, flush: bool = True) -> Dict[str, Any]:
    """Create a directory in the IPFS MFS (Mutable File System)."""
    # Implementation...

def files_ls(self, path: str = "/", long: bool = False) -> Dict[str, Any]:
    """List contents of a directory in the IPFS MFS."""
    # Implementation...

def files_stat(self, path: str) -> Dict[str, Any]:
    """Get status information about a file or directory in the IPFS MFS."""
    # Implementation...

def files_read(self, path: str, offset: int = 0, count: int = None) -> Dict[str, Any]:
    """Read content from a file in the IPFS MFS."""
    # Implementation...

def files_write(self, path: str, content: Union[str, bytes], create: bool = True, 
               truncate: bool = True, offset: int = 0, count: int = None,
               flush: bool = True) -> Dict[str, Any]:
    """Write content to a file in the IPFS MFS."""
    # Implementation...

def files_rm(self, path: str, recursive: bool = False, force: bool = False) -> Dict[str, Any]:
    """Remove a file or directory from the IPFS MFS."""
    # Implementation...
```

### Controller Implementation

The MFS operations are exposed through API endpoints in the `IPFSController` class:

```python
# Files API (MFS) endpoints
router.add_api_route(
    "/ipfs/files/ls",
    self.list_files,
    methods=["POST", "GET"],
    summary="List files",
    description="List files in the MFS (Mutable File System) directory"
)

router.add_api_route(
    "/ipfs/files/stat",
    self.stat_file,
    methods=["POST", "GET"],
    summary="Get file information",
    description="Get information about a file or directory in MFS"
)

router.add_api_route(
    "/ipfs/files/mkdir",
    self.make_directory,
    methods=["POST"],
    summary="Create directory",
    description="Create a directory in the MFS (Mutable File System)"
)

router.add_api_route(
    "/ipfs/files/read",
    self.read_file,
    methods=["POST", "GET"],
    summary="Read file content",
    description="Read content from a file in the MFS (Mutable File System)"
)

router.add_api_route(
    "/ipfs/files/write",
    self.write_file,
    methods=["POST"],
    summary="Write to file",
    description="Write content to a file in the MFS (Mutable File System)"
)

router.add_api_route(
    "/ipfs/files/rm",
    self.remove_file,
    methods=["POST", "DELETE"],
    summary="Remove file or directory",
    description="Remove a file or directory from the MFS (Mutable File System)"
)
```

## API Usage Examples

### List Files

**Request:**
```http
GET /ipfs/files/ls?path=/my_directory&long=true
```

**Response:**
```json
{
  "success": true,
  "operation_id": "files_ls_1635789123456",
  "duration_ms": 15.5,
  "path": "/my_directory",
  "Entries": [
    {
      "Name": "file1.txt",
      "Type": 0,
      "Size": 1024,
      "Hash": "QmXjkE12dQvKzkZzn2EVR8gPYq2kBvQxBKRE5hqZ5amrNH"
    },
    {
      "Name": "subdirectory",
      "Type": 1,
      "Size": 0,
      "Hash": "QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"
    }
  ]
}
```

### Make Directory

**Request:**
```http
POST /ipfs/files/mkdir
Content-Type: application/json

{
  "path": "/my_directory/new_folder",
  "parents": true
}
```

**Response:**
```json
{
  "success": true,
  "operation_id": "files_mkdir_1635789123456",
  "duration_ms": 12.3,
  "path": "/my_directory/new_folder",
  "created": true
}
```

### Get File Stats

**Request:**
```http
GET /ipfs/files/stat?path=/my_directory/file1.txt
```

**Response:**
```json
{
  "success": true,
  "operation_id": "files_stat_1635789123456",
  "duration_ms": 8.7,
  "path": "/my_directory/file1.txt",
  "Size": 1024,
  "Type": 0,
  "Hash": "QmXjkE12dQvKzkZzn2EVR8gPYq2kBvQxBKRE5hqZ5amrNH",
  "Blocks": 1,
  "CumulativeSize": 1024
}
```

### Read File

**Request:**
```http
GET /ipfs/files/read?path=/my_directory/file1.txt&offset=0&count=100
```

**Response:**
```json
{
  "success": true,
  "operation_id": "files_read_1635789123456",
  "duration_ms": 10.2,
  "path": "/my_directory/file1.txt",
  "content": "VGhpcyBpcyB0aGUgY29udGVudCBvZiB0aGUgZmlsZS4=",
  "size": 30,
  "offset": 0,
  "count": 100
}
```

### Write File

**Request:**
```http
POST /ipfs/files/write
Content-Type: application/json

{
  "path": "/my_directory/file1.txt",
  "content": "This is the new content of the file.",
  "create": true,
  "truncate": true,
  "offset": 0,
  "flush": true
}
```

**Response:**
```json
{
  "success": true,
  "operation_id": "files_write_1635789123456",
  "duration_ms": 18.9,
  "path": "/my_directory/file1.txt",
  "bytes_written": 34,
  "size": 34,
  "create": true,
  "truncate": true,
  "offset": 0,
  "flush": true
}
```

### Remove File

**Request:**
```http
POST /ipfs/files/rm
Content-Type: application/json

{
  "path": "/my_directory/file1.txt",
  "recursive": false,
  "force": false
}
```

**Response:**
```json
{
  "success": true,
  "operation_id": "files_rm_1635789123456",
  "duration_ms": 9.5,
  "path": "/my_directory/file1.txt",
  "removed": true,
  "recursive": false,
  "force": false
}
```

## Error Handling

All MFS operations include comprehensive error handling:

1. **Operation Not Available**: When a client invokes an MFS operation on an IPFS instance that doesn't support it, the server provides simulated responses for testing.

2. **Path Not Found**: When a specified path doesn't exist, the server returns an appropriate error message.

3. **Permission Errors**: When a file operation fails due to permissions, the server provides a clear error message.

4. **Invalid Parameters**: When invalid parameters are provided, the server validates them and returns appropriate error messages.

5. **Unexpected Errors**: Any unexpected errors are caught and returned in a standardized format.

Example error response:
```json
{
  "success": false,
  "operation_id": "files_rm_1635789123456",
  "duration_ms": 5.2,
  "error": "No such file or directory: /nonexistent/path",
  "error_type": "FileNotFoundError",
  "path": "/nonexistent/path",
  "removed": false,
  "recursive": false,
  "force": false
}
```

## Testing

The MFS operations have been thoroughly tested in the `test_mcp_mfs_operations.py` test file, which includes:

1. Tests for normal operation with successful results
2. Tests for simulation mode when methods aren't available
3. Tests for error handling for exceptions

The test file contains detailed test cases for each MFS operation:

- `test_files_mkdir`
- `test_files_ls`
- `test_files_stat`
- `test_files_read`
- `test_files_write`
- `test_files_rm`
- `test_simulation_mode`
- `test_error_handling`

These tests ensure that all MFS operations work correctly and handle errors appropriately.

## Conclusion

The implementation of MFS operations in the MCP server provides a complete set of file system operations for IPFS content. These operations are now fully functional and available through the API, allowing users to interact with IPFS content using familiar file system operations.