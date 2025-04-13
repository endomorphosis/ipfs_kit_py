#\!/usr/bin/env python3

"""Script to add a standardized error response formatter to MCP server."""

import re

def add_error_formatter():
    """Add a standardized error response formatter to the MCP server."""
    file_path = "ipfs_kit_py/mcp/server.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the _log_operation method
    log_op_pattern = re.compile(r'def _log_operation.*?self\.operation_log\.append\(operation\)', re.DOTALL)
    match = log_op_pattern.search(content)
    
    if not match:
        print("Could not find _log_operation method")
        return False
    
    log_op_code = match.group(0)
    
    # New code with error formatter
    new_code = log_op_code + '''
    
    def format_error_response(self, error: Exception, operation_id: str = None) -> Dict[str, Any]:
        """
        Create a standardized error response.
        
        Args:
            error: The exception that occurred
            operation_id: Optional operation ID to include in the response
            
        Returns:
            Standardized error response dictionary
        """
        # Generate operation ID if not provided
        if operation_id is None:
            operation_id = f"error_{int(time.time() * 1000)}"
            
        # Build standard error response
        response = {
            "success": False,
            "operation_id": operation_id,
            "timestamp": time.time(),
            "error": str(error),
            "error_type": type(error).__name__,
            "duration_ms": 0  # No duration for errors with no operation
        }
        
        # Log error details if debug mode is enabled
        if self.debug_mode:
            import traceback
            stack_trace = traceback.format_exc()
            if stack_trace \!= "NoneType: None\\n":  # Only include if there's a real trace
                response["debug_info"] = {
                    "stack_trace": stack_trace,
                    "error_args": getattr(error, "args", [])
                }
            
        # Log the error operation
        self._log_operation({
            "type": "error",
            "operation_id": operation_id,
            "timestamp": time.time(),
            "error": str(error),
            "error_type": type(error).__name__
        })
        
        return response'''
    
    # Replace the code
    updated_content = content.replace(log_op_code, new_code)
    
    with open(file_path, 'w') as f:
        f.write(updated_content)
    
    print("Successfully added format_error_response method to MCP server")
    return True

if __name__ == "__main__":
    add_error_formatter()
