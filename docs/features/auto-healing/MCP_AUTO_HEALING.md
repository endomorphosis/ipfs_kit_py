# MCP Tool and JavaScript SDK Auto-Healing

## Overview

The auto-healing system has been extended to cover:
1. **MCP Server Tools** - All tools provided by the MCP server
2. **JavaScript SDK** - Client-side errors from the MCP SDK

Both error sources now automatically create GitHub issues and trigger the auto-healing workflow.

## MCP Server Tool Auto-Healing

### How It Works

When any MCP tool encounters an error:
1. The error is captured with full context (tool name, arguments, stack trace)
2. A GitHub issue is automatically created
3. The auto-heal workflow analyzes the error
4. A draft PR is created with a fix (or Copilot is invoked)

### Configuration

MCP tool auto-healing is enabled via environment variable:

```bash
export IPFS_KIT_AUTO_HEAL=true
export GITHUB_TOKEN=your_github_token
export GITHUB_REPOSITORY=endomorphosis/ipfs_kit_py
```

### Error Context Captured

For MCP tool errors, the following information is captured:
- **Tool name**: Which MCP tool failed
- **Arguments**: Parameters passed to the tool
- **Error type**: Exception class name
- **Error message**: Exception message
- **Stack trace**: Full Python stack trace
- **Timestamp**: When the error occurred

### Example

```python
# User calls MCP tool via dashboard
await mcpClient.callTool('ipfs_add', {content: 'test'})

# Tool fails internally
# Error is automatically captured and reported

# GitHub issue created:
# Title: [Auto-Heal] RuntimeError: IPFS daemon not running
# Labels: auto-heal, cli-error, mcp-tool
# Body: Full diagnostics including stack trace
```

## JavaScript SDK Auto-Healing

### How It Works

When the JavaScript SDK encounters an error:
1. The error is captured with browser context
2. Sent to backend via `/api/auto-heal/report-client-error`
3. Backend processes and creates GitHub issue
4. Auto-heal workflow is triggered

### Auto-Reporting

The SDK automatically reports errors in these scenarios:

1. **Tool Call Failures**: When `callTool()` fails after all retries
2. **Uncaught Errors**: Global JavaScript errors
3. **Unhandled Promises**: Promise rejection handling

### Error Context Captured

For client-side errors:
- **Error type**: JavaScript error type
- **Error message**: Error description
- **Stack trace**: JavaScript stack trace
- **Tool name**: MCP tool that was being called
- **Operation**: Type of operation (tool_call, fetch, etc.)
- **Parameters**: Tool parameters
- **Browser info**: Browser name and version
- **Platform**: Operating system
- **URL**: Page where error occurred
- **User agent**: Full user agent string

### Example

```javascript
// User calls MCP tool
await window.mcpClient.callTool('ipfs_cat', {hash: 'invalid_hash'})

// SDK tries with retries
// All attempts fail

// Error automatically reported:
POST /api/auto-heal/report-client-error
{
  error_type: 'Error',
  error_message: 'MCP Error: Invalid IPFS hash',
  stack_trace: 'Error\n  at MCPClient.callTool...',
  tool_name: 'ipfs_cat',
  operation: 'tool_call',
  params: {hash: 'invalid_hash'},
  browser: 'Chrome',
  platform: 'Linux',
  url: 'http://localhost:8004/',
  ...
}

// GitHub issue created automatically
```

### Disabling Auto-Reporting

To disable client-side error reporting:

```javascript
window.mcpClient.autoHealEnabled = false;
```

## API Endpoint

### POST /api/auto-heal/report-client-error

Receives client-side error reports.

**Request Body:**
```json
{
  "error_type": "string",
  "error_message": "string",
  "stack_trace": "string",
  "tool_name": "string",
  "operation": "string",
  "params": {},
  "browser": "string",
  "platform": "string",
  "user_agent": "string",
  "url": "string",
  "timestamp": "ISO8601"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Error reported successfully",
  "timestamp": "ISO8601"
}
```

## GitHub Issue Format

### MCP Tool Error Issue

```markdown
## CLI Error Auto-Report

### Error Information
- **Type:** `RuntimeError`
- **Message:** IPFS daemon not running
- **Timestamp:** 2026-01-31T12:00:00Z
- **Working Directory:** `MCP Server`
- **Python Version:** Server-side execution

### Command Executed
```bash
MCP Tool: ipfs_add
```

### Arguments
```json
{
  "content": "test data",
  "name": "file.txt"
}
```

### Stack Trace
```python
Traceback (most recent call last):
  File "ipfs_kit_py/mcp/ipfs_kit/mcp_tools/tool_manager.py", line 415, in _execute_tool
    return await self._handle_ipfs_add(content, name)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: IPFS daemon not running
```
```

### JavaScript SDK Error Issue

```markdown
## CLI Error Auto-Report

### Error Information
- **Type:** `Error`
- **Message:** MCP Error: Invalid IPFS hash
- **Timestamp:** 2026-01-31T12:00:00Z
- **Working Directory:** `Client-side (Browser)`
- **Python Version:** JavaScript SDK

### Command Executed
```bash
MCP SDK: ipfs_cat (tool_call)
```

### Arguments
```json
{
  "tool_name": "ipfs_cat",
  "operation": "tool_call",
  "params": {"hash": "invalid_hash"},
  "browser": "Chrome",
  "url": "http://localhost:8004/"
}
```

### Stack Trace
```javascript
Error
    at MCPClient.callTool (mcp-sdk.js:155:15)
    at async window.MCP.IPFS.cat (mcp-sdk.js:420:12)
```

### Environment
```
USER_AGENT=Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0
BROWSER=Chrome
PLATFORM=Linux
CLIENT_VERSION=1.0.0
```
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server Tools                          │
│  (Backend Python code)                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼ Error occurs
          ┌──────────────────────┐
          │ MCPToolErrorCapture  │
          │ - Captures context   │
          │ - Creates issue      │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  GitHub Issue        │
          │  + Auto-Heal         │
          │    Workflow          │
          └──────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│              JavaScript SDK (Browser)                        │
│  window.mcpClient.callTool(...)                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼ Error occurs
          ┌──────────────────────┐
          │ MCPClient            │
          │ - reportError()      │
          └──────────┬───────────┘
                     │
                     ▼ POST
          ┌──────────────────────────────┐
          │ /api/auto-heal/              │
          │   report-client-error        │
          └──────────┬───────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ ClientErrorReporter  │
          │ - Processes error    │
          │ - Creates issue      │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  GitHub Issue        │
          │  + Auto-Heal         │
          │    Workflow          │
          └──────────────────────┘
```

## Testing

### MCP Tool Error Testing

```python
# Enable auto-healing
export IPFS_KIT_AUTO_HEAL=true

# Start MCP server
ipfs-kit mcp start

# Trigger a tool error (e.g., with IPFS daemon stopped)
curl -X POST http://localhost:8004/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "ipfs_add",
      "arguments": {"content": "test"}
    },
    "id": 1
  }'

# Check GitHub issues - should see new auto-heal issue
```

### JavaScript SDK Error Testing

```javascript
// Open browser console at http://localhost:8004
// Try to call a tool that will fail
await window.mcpClient.callTool('ipfs_cat', {hash: 'invalid_hash'})

// Check network tab - should see POST to /api/auto-heal/report-client-error
// Check GitHub issues - should see new auto-heal issue
```

## Troubleshooting

### MCP Tool Errors Not Creating Issues

1. Check auto-healing is enabled:
   ```bash
   echo $IPFS_KIT_AUTO_HEAL
   # Should be: true
   ```

2. Check configuration:
   ```bash
   ipfs-kit autoheal status
   ```

3. Check server logs for auto-heal messages:
   ```bash
   tail -f ~/.ipfs_kit/mcp_8004.log | grep -i "auto-heal"
   ```

### Client Errors Not Being Reported

1. Check SDK is loaded:
   ```javascript
   console.log(window.mcpClient.autoHealEnabled)
   // Should be: true
   ```

2. Check network requests:
   - Open browser DevTools → Network tab
   - Look for POST to `/api/auto-heal/report-client-error`

3. Check backend endpoint:
   ```bash
   curl -X POST http://localhost:8004/api/auto-heal/report-client-error \
     -H "Content-Type: application/json" \
     -d '{"error_type": "test"}'
   ```

## Security Considerations

- Client-side error reports are rate-limited (server-side)
- Sensitive data in error contexts is filtered
- GitHub tokens are never exposed to client
- All error data is sanitized before GitHub issue creation

## Future Enhancements

1. **Error Aggregation**: Group similar errors into single issues
2. **Smart Rate Limiting**: Prevent duplicate issues for same error
3. **Error Analytics**: Dashboard showing error trends
4. **Auto-Fix Success Tracking**: Monitor which fixes work
5. **Client-Side Filtering**: Don't report known benign errors
