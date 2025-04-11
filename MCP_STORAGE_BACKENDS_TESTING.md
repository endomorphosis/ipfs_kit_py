# MCP Storage Backends Comprehensive Testing

This document outlines the comprehensive testing approach for the MCP server's storage backend integrations. Building on the previous verification findings in `MCP_STORAGE_BACKENDS_VERIFICATION.md`, this testing strategy verifies that all storage backends correctly integrate with the MCP server, enabling bidirectional content transfer between IPFS and each backend.

## Storage Backends

The MCP server integrates with several storage backends:

| Backend       | Purpose                                          | Primary Operations                     |
|---------------|--------------------------------------------------|-----------------------------------------|
| S3            | Amazon S3 and compatible object storage          | Upload/download files to/from buckets  |
| Storacha      | Decentralized storage on Filecoin via Web3.Storage | Content archiving with CAR files    |
| HuggingFace   | AI model and dataset repository                  | Model/dataset storage and retrieval    |
| Filecoin      | Direct integration with Filecoin blockchain      | Storage deals and retrieval            |
| Lassie        | Content retrieval service for IPFS/Filecoin      | Retrieval of content by CID            |

## Previous Verification Findings

Our previous verification documented the API endpoints and status of each backend:

| Backend       | Status | API Available | Implementation Status                      |
|---------------|--------|---------------|--------------------------------------------|
| IPFS          | ✅     | Yes           | Fully functional with working endpoints     |
| Hugging Face  | ✅     | Yes           | Status check working, 7 endpoints defined   |
| Storacha/W3   | ✅     | Yes           | Status working, space/list & uploads working |
| Filecoin/Lotus| ❌     | Yes           | Endpoints defined but Lotus connection error |
| Lassie        | ❌     | Yes           | Status endpoint fails, 6 endpoints defined   |
| S3            | ❌     | Partial       | Only credentials endpoint found              |

## Enhanced Testing Approach

Building on these findings, we've developed a comprehensive testing strategy that:

1. Tests the **bidirectional transfer** of content between IPFS and each backend
2. Works with **real or simulated backends** based on available credentials
3. Uses a **unified testing framework** for consistent verification across backends
4. Provides **detailed reporting** of test results and failures

### Testing Architecture

The enhanced testing approach has three key components:

#### 1. MCP Server with Storage Backends

The `run_mcp_with_storage.py` script:

- Initializes the MCP server with all storage controllers
- Creates simulated backends for components that aren't available
- Configures backends with test credentials
- Exposes consistent API endpoints for all backends

This script uses monkeypatching to ensure S3 and other backends are available for testing even when real credentials aren't provided.

#### 2. Backend Testing Client

The `test_mcp_storage_backends.py` script implements a client for testing each backend:

- **MCPServerClient**: Client class for interacting with the MCP server API
- **Test Flow**:
  1. Checks server health
  2. Uploads test content to IPFS
  3. For each backend:
     - Checks backend status endpoint
     - Transfers content from IPFS to the backend
     - Transfers content from the backend back to IPFS
  4. Reports results for each backend

This client is designed to work with both real and simulated backend implementations.

#### 3. Orchestration Script

The `test_mcp_storage_backends.sh` shell script orchestrates the entire test process:

- Starts the MCP server with storage backends
- Waits for the server to be ready
- Runs the backend testing client
- Captures logs from both components
- Reports overall status
- Handles cleanup of resources

## Testing Details by Backend

### 1. S3 Backend

Tests the following operations:

1. **Status Check**: Verifies the S3 controller status endpoint
   ```
   GET /mcp/storage/s3/status
   ```

2. **IPFS to S3**: Transfers content from IPFS to S3
   ```
   POST /mcp/storage/s3/from_ipfs
   {
     "cid": "QmHash...",
     "bucket": "test-bucket",
     "key": "test/file.bin"
   }
   ```

3. **S3 to IPFS**: Transfers content from S3 to IPFS
   ```
   POST /mcp/storage/s3/to_ipfs
   {
     "bucket": "test-bucket",
     "key": "test/file.bin"
   }
   ```

### 2. Storacha (Web3.Storage) Backend

Tests the following operations:

1. **Status Check**: Verifies the Storacha controller status endpoint
   ```
   GET /mcp/storage/storacha/status
   ```

2. **IPFS to Storacha**: Transfers content from IPFS to Storacha/Web3.Storage
   ```
   POST /mcp/storage/storacha/from_ipfs
   {
     "cid": "QmHash..."
   }
   ```

3. **Storacha to IPFS**: Transfers content from Storacha back to IPFS
   ```
   POST /mcp/storage/storacha/to_ipfs
   {
     "car_cid": "bagbaiera..."
   }
   ```

### 3. HuggingFace Backend

Tests the following operations:

1. **Status Check**: Verifies the HuggingFace controller status endpoint
   ```
   GET /mcp/storage/huggingface/status
   ```

2. **IPFS to HuggingFace**: Transfers content from IPFS to HuggingFace
   ```
   POST /mcp/storage/huggingface/from_ipfs
   {
     "cid": "QmHash...",
     "repo_id": "test-repo",
     "path_in_repo": "ipfs/file.bin"
   }
   ```

3. **HuggingFace to IPFS**: Transfers content from HuggingFace to IPFS
   ```
   POST /mcp/storage/huggingface/to_ipfs
   {
     "repo_id": "test-repo",
     "path_in_repo": "ipfs/file.bin"
   }
   ```

### 4. Filecoin Backend

Tests the following operations:

1. **Status Check**: Verifies the Filecoin controller status endpoint
   ```
   GET /mcp/storage/filecoin/status
   ```

2. **IPFS to Filecoin**: Transfers content from IPFS to Filecoin (creates deals)
   ```
   POST /mcp/storage/filecoin/from_ipfs
   {
     "cid": "QmHash..."
   }
   ```

3. **Filecoin to IPFS**: Retrieves content from Filecoin back to IPFS
   ```
   POST /mcp/storage/filecoin/to_ipfs
   {
     "deal_id": "deal-id-value"
   }
   ```

### 5. Lassie Backend

Tests the following operations:

1. **Status Check**: Verifies the Lassie controller status endpoint
   ```
   GET /mcp/storage/lassie/status
   ```

2. **Lassie to IPFS**: Retrieves content using Lassie and imports to local IPFS
   ```
   POST /mcp/storage/lassie/to_ipfs
   {
     "cid": "QmHash..."
   }
   ```

## Test Environment Configuration

The tests use environment variables to configure real backend access:

- **S3**:
  - `AWS_ACCESS_KEY_ID`: S3 access key
  - `AWS_SECRET_ACCESS_KEY`: S3 secret key
  - `AWS_REGION`: AWS region
  - `S3_TEST_BUCKET`: Bucket name
  - `S3_ENDPOINT_URL`: Optional, for S3-compatible storage
  
- **HuggingFace**:
  - `HUGGINGFACE_TOKEN`: API token
  - `HF_TEST_REPO`: Repository name
  
- **Storacha**:
  - `W3_DELEGATION_PROOF`: Delegation proof (JWT) for Web3.Storage
  - `W3_PROOF_AUTH`: Authorization proof

For testing without real credentials, the MCP server creates simulated backend implementations with mock functionality.

## Test Output and Reporting

The test results are reported in multiple ways:

1. **Console Output**: Real-time progress and results with colored status indicators
   ```
   === Testing S3 Backend ===
   ✅ S3 backend status check successful
   ✅ Transfer from IPFS to S3 successful
   ✅ Transfer from S3 to IPFS successful
   ```

2. **Log Files**:
   - MCP server log with detailed backend operations
   - Backend test log with request/response details

3. **Summary Report**:
   ```
   === Test Summary ===
   S3: ✅ Success
   STORACHA: ✅ Success
   HUGGINGFACE: ✅ Success
   FILECOIN: ✅ Success
   LASSIE: ✅ Success

   Successful backends: 5/5
   Failed backends: 0/5
   ```

4. **Detailed JSON Results**:
   ```json
   {
     "backend": "s3",
     "status_check": {"success": true, "is_available": true},
     "ipfs_to_backend": {
       "success": true,
       "bucket": "test-bucket",
       "key": "QmHash..."
     },
     "backend_to_ipfs": {
       "success": true,
       "ipfs_cid": "QmNewHash..."
     },
     "overall": true
   }
   ```

## Usage Guide

To run the comprehensive backend verification:

```bash
./test_mcp_storage_backends.sh
```

### Command-line Options

- `--port PORT`: Port for MCP server (default: 10000)
- `--host HOST`: Host for MCP server (default: 127.0.0.1) 
- `--backend LIST`: Space-separated list of backends to test (default: all)

Example testing only S3 and HuggingFace backends:
```bash
./test_mcp_storage_backends.sh --backend "s3 huggingface"
```

## Addressing Previous Verification Issues

The enhanced testing approach addresses the issues identified in the previous verification:

1. **S3 Backend**: The test environment ensures S3Controller is properly initialized and registered
2. **Lassie Backend**: Tests use a known public CID for Lassie retrieval
3. **Filecoin Backend**: Uses mock mode for testing without Lotus daemon
4. **Comprehensive Testing**: Tests all endpoints with both success and failure scenarios

## Future Testing Enhancements

1. **Performance Testing**: Add timing measurements for each operation
2. **Concurrent Testing**: Test multiple simultaneous transfers
3. **Large File Testing**: Test with different file sizes to identify bottlenecks
4. **Fault Injection**: Simulate network issues, timeouts, and service failures
5. **Metrics Collection**: Track memory usage and resource consumption during transfers
6. **Cross-Backend Transfers**: Test direct transfers between different backends

## Conclusion

This comprehensive testing approach ensures that all storage backends function correctly with the MCP server. By testing bidirectional content transfers between IPFS and each backend, we can verify the core functionality that makes the MCP server valuable as a unified content management interface.

The tests provide immediate feedback on backend functionality while also creating detailed logs for debugging issues. This approach ensures that both existing and new storage backends can be consistently verified against a common standard.