"""
Example of integrating automatic error reporting in an IPFS Kit application.

This example demonstrates how to set up error reporting for:
1. Python runtime errors
2. MCP server errors
3. FastAPI application errors
4. Custom application errors
"""

import os
import logging
from ipfs_kit_py.init_error_reporting import setup_error_reporting, register_error_reporting_api

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main application entry point with error reporting."""
    
    # Initialize error reporting
    # This will:
    # - Create a GitHub issue reporter
    # - Install error interceptor for unhandled exceptions
    # - Install MCP error handler (if available)
    print("Setting up error reporting...")
    success = setup_error_reporting(
        # These can also be set via environment variables:
        # GITHUB_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME
        github_token=os.environ.get("GITHUB_TOKEN"),
        repo_owner=os.environ.get("GITHUB_REPO_OWNER", "endomorphosis"),
        repo_name=os.environ.get("GITHUB_REPO_NAME", "ipfs_kit_py"),
        enabled=True,
        context="IPFS Kit Example Application",
        install_interceptor=True,
        install_mcp_handler=True,
    )
    
    if success:
        print("✓ Error reporting configured successfully")
    else:
        print("! Error reporting disabled (no GitHub token)")
    
    # Example 1: Unhandled exception will be automatically reported
    print("\n--- Example 1: Automatic error reporting ---")
    try:
        # This error will be caught and reported automatically
        # Uncomment to test:
        # raise RuntimeError("Example runtime error - this will create a GitHub issue!")
        print("(Skipping automatic error example - uncomment to test)")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    
    # Example 2: Manual error reporting
    print("\n--- Example 2: Manual error reporting ---")
    from ipfs_kit_py.error_reporter import get_error_reporter
    
    reporter = get_error_reporter()
    if reporter and reporter.enabled:
        try:
            # Simulate an operation that might fail
            process_data(None)  # This will raise an error
        except Exception as e:
            # Manually report the error with context
            issue_url = reporter.report_error(
                error=e,
                context="Data Processing Module",
                additional_info={
                    "operation": "process_data",
                    "input_type": type(None).__name__,
                    "user_action": "data_upload",
                }
            )
            if issue_url:
                print(f"✓ Error reported: {issue_url}")
            else:
                print("! Error not reported (duplicate or rate limited)")
    
    # Example 3: FastAPI integration
    print("\n--- Example 3: FastAPI integration ---")
    try:
        from fastapi import FastAPI
        
        app = FastAPI(title="IPFS Kit Example with Error Reporting")
        
        # Register error reporting API endpoints
        register_error_reporting_api(app)
        print("✓ Error reporting API endpoints registered")
        print("  - POST /api/report-error")
        print("  - GET /api/error-reporting/status")
        
        # Example endpoint that might fail
        @app.get("/test-error")
        async def test_error():
            """Test endpoint that demonstrates error reporting."""
            # This error will be caught by FastAPI's error handler
            # and can be reported via the error reporting system
            raise ValueError("Test error from API endpoint")
        
        print("✓ FastAPI application configured")
        print("  Run with: uvicorn example_module:app --reload")
        
    except ImportError:
        print("! FastAPI not installed, skipping API example")
    
    # Example 4: MCP error reporting
    print("\n--- Example 4: MCP error reporting ---")
    try:
        from ipfs_kit_py.mcp.mcp_error_handling import MCPError, ErrorSeverity, ErrorCategory
        
        # MCP errors with severity "error" or "critical" are automatically reported
        try:
            raise MCPError(
                message="Storage backend connection failed",
                error_code="STORAGE_CONNECTION_FAILED",
                status_code=503,
                category=ErrorCategory.STORAGE,
                severity=ErrorSeverity.CRITICAL,
                details={
                    "backend": "s3",
                    "region": "us-east-1",
                    "retry_count": 3,
                },
                suggestion="Check network connectivity and AWS credentials"
            )
        except MCPError as e:
            print(f"MCP Error caught: {e.error_code}")
            print(f"  This error will be automatically reported to GitHub")
            
    except ImportError:
        print("! MCP error handling not available")
    
    # Example 5: Custom error reporting with error info dict
    print("\n--- Example 5: Custom error reporting (JavaScript-style) ---")
    if reporter and reporter.enabled:
        # This is useful for reporting errors from non-Python sources
        # like JavaScript errors from the dashboard
        error_info = {
            "error_type": "JavaScriptError",
            "error_message": "Uncaught TypeError: Cannot read property 'value' of null",
            "source_file": "dashboard.js",
            "line_number": 42,
            "column_number": 15,
            "stack": "at updateStatus (dashboard.js:42:15)\nat refresh (dashboard.js:100:5)",
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "url": "http://localhost:8080/dashboard",
        }
        
        issue_url = reporter.report_error_dict(
            error_info=error_info,
            context="MCP Dashboard (JavaScript)"
        )
        
        if issue_url:
            print(f"✓ JavaScript error reported: {issue_url}")
        else:
            print("! Error not reported (duplicate or rate limited)")
    
    print("\n--- Error Reporting Summary ---")
    print("The error reporting system provides:")
    print("1. Automatic reporting of unhandled Python exceptions")
    print("2. Automatic reporting of critical MCP errors")
    print("3. API endpoints for reporting errors from any source")
    print("4. JavaScript error handler for dashboard errors")
    print("5. Deduplication to prevent duplicate issues")
    print("6. Rate limiting to prevent spam")
    print("\nSee docs/error_reporting.md for full documentation")


def process_data(data):
    """Example function that might fail."""
    if data is None:
        raise ValueError("Data cannot be None")
    return data


if __name__ == "__main__":
    main()
