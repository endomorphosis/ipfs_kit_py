#!/usr/bin/env python3
"""
Comprehensive fix script for MCP API issues.
This script fixes multiple issues with the MCP server API including:
1. WebRTC dependency check method missing
2. IPFS cat endpoint parameter handling
3. Missing root, health, and versions endpoints
4. Endpoint routing issues
"""

import os
import sys
import logging
import time
import shutil
import traceback
import json
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix_mcp_api")

# Make backups before modification
def backup_file(file_path):
    """Make a backup of the file before modification."""
    if os.path.exists(file_path):
        backup_path = f"{file_path}.bak.{int(time.time())}"
        logger.info(f"Creating backup of {file_path} to {backup_path}")
        shutil.copy2(file_path, backup_path)
        return True
    else:
        logger.error(f"File not found: {file_path}")
        return False

# Fix WebRTC controller check_dependencies method
def fix_webrtc_dependency_check():
    """Fix the WebRTC controller's check_dependencies method to handle both method names."""
    controller_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/webrtc_controller.py"
    anyio_controller_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/webrtc_controller_anyio.py"
    
    # The anyio version has the correct implementation, but we'll check both for completeness
    for path in [controller_path, anyio_controller_path]:
        if not backup_file(path):
            continue
            
        try:
            with open(path, 'r') as f:
                content = f.read()
                
            # Check if the controller file has a check_dependencies method
            if "def check_dependencies" in content:
                logger.info(f"Found check_dependencies method in {path}")
                
                # Find the check_dependencies method
                dependency_method_pattern = re.compile(r"(\s+)async\s+def\s+check_dependencies.*?(\n\1\S|\Z)", re.DOTALL)
                match = dependency_method_pattern.search(content)
                
                if match:
                    old_method = match.group(0)
                    indentation = match.group(1)
                    
                    # Create improved implementation that handles both method names
                    new_method = f"""{indentation}async def check_dependencies(self) -> Dict[str, Any]:
{indentation}    \"\"\"
{indentation}    Check if WebRTC dependencies are available.
{indentation}    
{indentation}    Returns:
{indentation}        Dictionary with dependency status
{indentation}    \"\"\"
{indentation}    logger.debug("Checking WebRTC dependencies")
{indentation}    
{indentation}    # Run the dependency check in a background thread using anyio
{indentation}    try:
{indentation}        # Try to use the anyio-compatible version first
{indentation}        if hasattr(self.ipfs_model, 'check_webrtc_dependencies_anyio'):
{indentation}            return await self.ipfs_model.check_webrtc_dependencies_anyio()
{indentation}        
{indentation}        # Fall back to the sync version
{indentation}        elif hasattr(self.ipfs_model, 'check_webrtc_dependencies'):
{indentation}            return await anyio.to_thread.run_sync(self.ipfs_model.check_webrtc_dependencies)
{indentation}        
{indentation}        # Create a basic response if no method is available
{indentation}        else:
{indentation}            return {{
{indentation}                "success": False,
{indentation}                "webrtc_available": False,
{indentation}                "error": "No WebRTC dependency check method available",
{indentation}                "dependencies": {{
{indentation}                    "numpy": False,
{indentation}                    "opencv": False,
{indentation}                    "av": False,
{indentation}                    "aiortc": False,
{indentation}                    "websockets": False,
{indentation}                    "notifications": False
{indentation}                }}
{indentation}            }}
{indentation}    except Exception as e:
{indentation}        logger.error(f"Error checking WebRTC dependencies: {{e}}")
{indentation}        return {{
{indentation}            "success": False,
{indentation}            "webrtc_available": False,
{indentation}            "error": f"Error checking dependencies: {{str(e)}}",
{indentation}            "error_type": type(e).__name__
{indentation}        }}"""
                    
                    # Replace the method implementation
                    new_content = content.replace(old_method, new_method)
                    
                    if new_content != content:
                        with open(path, 'w') as f:
                            f.write(new_content)
                        logger.info(f"✅ Successfully updated check_dependencies method in {path}")
                        return True
                    else:
                        logger.warning(f"Failed to update check_dependencies method in {path} - content unchanged")
                else:
                    logger.warning(f"Could not find check_dependencies method pattern in {path}")
            else:
                logger.warning(f"Could not find check_dependencies method in {path}")
        except Exception as e:
            logger.error(f"Error fixing WebRTC controller {path}: {e}")
            logger.error(traceback.format_exc())
    
    logger.error("❌ Failed to fix WebRTC dependency check method")
    return False

# Fix IPFS controller to handle both cat endpoint styles
def fix_ipfs_cat_endpoint():
    """Fix the IPFS controller's cat endpoint to support both path and query parameters."""
    controller_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py"
    
    if not backup_file(controller_path):
        return False
        
    try:
        with open(controller_path, 'r') as f:
            content = f.read()
            
        # Find where cat endpoint is registered
        if "router.add_api_route" in content and "cat" in content:
            # Look for the line registering the cat endpoint
            cat_pattern = re.compile(r'(\s+)(router\.add_api_route.*?"(?:/ipfs/)?cat.*?",.*?\))', re.MULTILINE)
            match = cat_pattern.search(content)
            
            if match:
                indentation = match.group(1)
                original_route = match.group(2)
                
                # Find the method being registered
                method_name_match = re.search(r'(self\.[\w_]+)', original_route)
                if method_name_match:
                    method_name = method_name_match.group(1)
                    logger.info(f"Found cat endpoint registration: {method_name}")
                    
                    # Add a second registration for the other style
                    # If original has path parameter, add query parameter version
                    # If original has query parameter, add path parameter version
                    if "{cid}" in original_route:
                        # Original uses path parameter, add query parameter version
                        new_route = f'{indentation}router.add_api_route("/ipfs/cat", {method_name}, methods=["GET"])'
                    else:
                        # Original uses query parameter, add path parameter version
                        new_route = f'{indentation}router.add_api_route("/ipfs/cat/{{cid}}", {method_name}, methods=["GET"])'
                    
                    # Add the new route after the original
                    new_content = content.replace(original_route, f"{original_route}\n{new_route}")
                    
                    if new_content != content:
                        with open(controller_path, 'w') as f:
                            f.write(new_content)
                        logger.info(f"✅ Successfully added alternative cat endpoint registration")
                        
                        # Now we need to make sure the method can handle both parameter styles
                        # Look for the cat method implementation
                        cat_method_pattern = re.compile(r'(\s+)(?:async\s+)?def\s+([\w_]+).*?cid:.*?(?:\n\1\S|\Z)', re.DOTALL)
                        method_matches = cat_method_pattern.finditer(content)
                        
                        # Find the method that matches the name in the route registration
                        for method_match in method_matches:
                            if f"self.{method_match.group(2)}" == method_name:
                                method_indentation = method_match.group(1)
                                method_code = method_match.group(0)
                                
                                # Check if the method needs to be updated to handle both parameter styles
                                if "request:" in method_code and "cid:" in method_code:
                                    # Method already has parameters for both styles
                                    logger.info("Cat method already has parameters for both styles")
                                    return True
                                
                                # Method needs updating to handle both parameter styles
                                logger.info("Updating cat method to handle both parameter styles")
                                
                                # Determine if method uses path or query parameter
                                if "cid: str = Path" in method_code:
                                    # Uses path parameter, add support for query parameter
                                    method_code_lines = method_code.splitlines()
                                    param_line_index = None
                                    
                                    # Find the line with the cid parameter
                                    for i, line in enumerate(method_code_lines):
                                        if "cid: str = Path" in line:
                                            param_line_index = i
                                            break
                                    
                                    if param_line_index is not None:
                                        # Add query parameter support
                                        query_param_line = method_code_lines[param_line_index].replace("Path", "Query(None)")
                                        method_code_lines.insert(param_line_index + 1, query_param_line)
                                        
                                        # Add logic to use either parameter
                                        for i, line in enumerate(method_code_lines):
                                            if "logger.debug" in line and "cid" in line:
                                                logic_index = i + 1
                                                method_code_lines.insert(logic_index, f"{method_indentation}    # Use query parameter if path parameter is None")
                                                method_code_lines.insert(logic_index + 1, f"{method_indentation}    if cid is None and 'arg' in locals():")
                                                method_code_lines.insert(logic_index + 2, f"{method_indentation}        cid = arg")
                                                break
                                        
                                        # Reassemble method code
                                        updated_method_code = "\n".join(method_code_lines)
                                        
                                        # Replace the method in the content
                                        new_content = new_content.replace(method_code, updated_method_code)
                                        
                                        with open(controller_path, 'w') as f:
                                            f.write(new_content)
                                        logger.info("✅ Successfully updated cat method to handle both parameter styles")
                                        return True
                                    else:
                                        logger.warning("Could not find cid parameter line in cat method")
                                elif "cid: str = Query" in method_code:
                                    # Uses query parameter, add support for path parameter
                                    method_code_lines = method_code.splitlines()
                                    param_line_index = None
                                    
                                    # Find the line with the cid parameter
                                    for i, line in enumerate(method_code_lines):
                                        if "cid: str = Query" in line:
                                            param_line_index = i
                                            break
                                    
                                    if param_line_index is not None:
                                        # Add path parameter support
                                        path_param_line = method_code_lines[param_line_index].replace("Query", "Path(None)")
                                        method_code_lines.insert(param_line_index + 1, path_param_line)
                                        
                                        # Add logic to use either parameter
                                        for i, line in enumerate(method_code_lines):
                                            if "logger.debug" in line and "cid" in line:
                                                logic_index = i + 1
                                                method_code_lines.insert(logic_index, f"{method_indentation}    # Use path parameter if query parameter is None")
                                                method_code_lines.insert(logic_index + 1, f"{method_indentation}    if cid is None and 'path_cid' in locals():")
                                                method_code_lines.insert(logic_index + 2, f"{method_indentation}        cid = path_cid")
                                                break
                                        
                                        # Reassemble method code
                                        updated_method_code = "\n".join(method_code_lines)
                                        
                                        # Replace the method in the content
                                        new_content = new_content.replace(method_code, updated_method_code)
                                        
                                        with open(controller_path, 'w') as f:
                                            f.write(new_content)
                                        logger.info("✅ Successfully updated cat method to handle both parameter styles")
                                        return True
                                    else:
                                        logger.warning("Could not find cid parameter line in cat method")
                                else:
                                    logger.warning("Cat method parameter style not recognized")
                        
                        logger.warning("Could not find cat method implementation matching the route registration")
                else:
                    logger.warning("Could not find method name in cat endpoint registration")
            else:
                logger.warning("Could not find cat endpoint registration pattern")
        else:
            logger.warning("Could not find router.add_api_route for cat endpoint")
    except Exception as e:
        logger.error(f"Error fixing IPFS cat endpoint: {e}")
        logger.error(traceback.format_exc())
    
    logger.error("❌ Failed to fix IPFS cat endpoint")
    return False

# Add root, health, and versions endpoints to MCP server
def add_basic_endpoints():
    """Add root, health, and versions endpoints to MCP server."""
    server_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/server.py"
    
    if not backup_file(server_path):
        return False
        
    try:
        with open(server_path, 'r') as f:
            content = f.read()
            
        # Check if we need to add basic endpoints
        if "def _create_router" in content:
            logger.info("Found _create_router method in server.py")
            
            # Find the method implementation
            router_method_pattern = re.compile(r'(\s+)def _create_router.*?(\n\1\S|\Z)', re.DOTALL)
            match = router_method_pattern.search(content)
            
            if match:
                router_method = match.group(0)
                indentation = match.group(1)
                
                # Check if basic endpoints are already added
                if "router.add_api_route(\"/\", self.root" in router_method:
                    logger.info("Root endpoint already exists")
                else:
                    # Add root endpoint
                    insert_point = router_method.find("return router")
                    if insert_point != -1:
                        # Find proper indentation
                        indentation_match = re.search(r'(\s+)return router', router_method)
                        if indentation_match:
                            endpoint_indentation = indentation_match.group(1)
                            
                            # Build new endpoints code
                            new_endpoints = f"""
{endpoint_indentation}# Add root endpoint for basic information
{endpoint_indentation}router.add_api_route("/", self.root_endpoint, methods=["GET"], tags=["Root"])
{endpoint_indentation}
{endpoint_indentation}# Add health check endpoint
{endpoint_indentation}router.add_api_route("/health", self.health_check, methods=["GET"], tags=["Health"])
{endpoint_indentation}
{endpoint_indentation}# Add versions endpoint
{endpoint_indentation}router.add_api_route("/versions", self.get_versions, methods=["GET"], tags=["Versions"])
"""
                            
                            # Insert the new endpoints
                            new_router_method = router_method[:insert_point] + new_endpoints + router_method[insert_point:]
                            
                            # Replace in content
                            new_content = content.replace(router_method, new_router_method)
                            
                            # Now check if we need to add the endpoint methods
                            endpoint_methods_to_add = []
                            
                            # Check for root endpoint method
                            if "def root_endpoint" not in content:
                                endpoint_methods_to_add.append(f"""
    def root_endpoint(self):
        \"\"\"
        Root endpoint providing basic server information.
        
        Returns:
            Dictionary with server information
        \"\"\"
        return {{
            "name": "IPFS Kit MCP Server",
            "version": "1.0.0",
            "instance_id": self.instance_id,
            "debug_mode": self.debug_mode,
            "isolation_mode": self.isolation_mode,
            "timestamp": time.time(),
            "endpoints": ["/", "/health", "/versions"]
        }}
""")
                            
                            # Check for health check method
                            if "def health_check" not in content:
                                endpoint_methods_to_add.append(f"""
    def health_check(self):
        \"\"\"
        Health check endpoint.
        
        Returns:
            Dictionary with health status
        \"\"\"
        # Query IPFS model for daemon status if available
        daemon_status = {{"status": "unknown"}}
        if "ipfs" in self.models:
            try:
                daemon_status = self.models["ipfs"].check_daemon_status()
            except Exception as e:
                logger.warning(f"Failed to check daemon status: {{e}}")
        
        return {{
            "status": "ok",
            "timestamp": time.time(),
            "instance_id": self.instance_id,
            "daemon_status": daemon_status
        }}
""")
                            
                            # Check for versions method
                            if "def get_versions" not in content:
                                endpoint_methods_to_add.append(f"""
    def get_versions(self):
        \"\"\"
        Get version information for server components.
        
        Returns:
            Dictionary with version information
        \"\"\"
        versions = {{
            "mcp_server": "1.0.0",
            "timestamp": time.time()
        }}
        
        # Get IPFS version if available
        if "ipfs" in self.models:
            try:
                ipfs_version = self.models["ipfs"].get_version()
                if isinstance(ipfs_version, dict) and ipfs_version.get("success"):
                    versions["ipfs"] = ipfs_version.get("version", "unknown")
            except Exception as e:
                logger.warning(f"Failed to get IPFS version: {{e}}")
                versions["ipfs"] = "error"
        
        # Get other component versions
        for component in ["storage_manager", "webrtc", "libp2p"]:
            if component in self.models:
                try:
                    model = self.models[component]
                    if hasattr(model, "get_version"):
                        version_info = model.get_version()
                        if isinstance(version_info, dict) and version_info.get("success"):
                            versions[component] = version_info.get("version", "unknown")
                except Exception as e:
                    logger.warning(f"Failed to get {{component}} version: {{e}}")
                    versions[component] = "error"
        
        return versions
""")
                            
                            # Add the endpoint methods if needed
                            if endpoint_methods_to_add:
                                # Find a good insertion point for methods (after class definition but before existing methods)
                                class_def_match = re.search(r'class MCPServer:.*?\n\n', content, re.DOTALL)
                                if class_def_match:
                                    insert_point = class_def_match.end()
                                    new_content = new_content[:insert_point] + "".join(endpoint_methods_to_add) + new_content[insert_point:]
                            
                            # Write the updated content
                            with open(server_path, 'w') as f:
                                f.write(new_content)
                            logger.info("✅ Successfully added basic endpoints to MCP server")
                            return True
                        else:
                            logger.warning("Could not find indentation for return router")
                    else:
                        logger.warning("Could not find return router in _create_router method")
                
            else:
                logger.warning("Could not find _create_router method implementation")
        else:
            logger.warning("Could not find _create_router method in server.py")
    except Exception as e:
        logger.error(f"Error adding basic endpoints: {e}")
        logger.error(traceback.format_exc())
    
    logger.error("❌ Failed to add basic endpoints to MCP server")
    return False

# Fix register_with_app method to ensure endpoints are properly registered
def fix_register_with_app():
    """Fix the register_with_app method to properly register endpoints at both prefixes."""
    server_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/server.py"
    
    if not backup_file(server_path):
        return False
        
    try:
        with open(server_path, 'r') as f:
            content = f.read()
            
        # Check if register_with_app needs fixing
        if "def register_with_app" in content:
            logger.info("Found register_with_app method in server.py")
            
            # Find the method implementation
            register_method_pattern = re.compile(r'(\s+)def register_with_app.*?(\n\1\S|\Z)', re.DOTALL)
            match = register_method_pattern.search(content)
            
            if match:
                register_method = match.group(0)
                indentation = match.group(1)
                
                # Check if the method already includes API compatibility for /api/v0/mcp
                if "/api/v0/mcp" in register_method:
                    logger.info("API v0 compatibility already exists")
                else:
                    # Add API v0 compatibility
                    # Find good insertion point (after normal mounting)
                    include_router_match = re.search(r'app\.include_router\(self\.router, prefix=prefix\)', register_method)
                    if include_router_match:
                        insert_point = include_router_match.end()
                        
                        # Build compatibility router code
                        compat_code = f"""
                        
{indentation}    # Also register endpoints at /api/v0/mcp for compatibility with tests
{indentation}    if not prefix.startswith("/api/v0/mcp"):
{indentation}        try:
{indentation}            # Create compatibility router for /api/v0/mcp endpoints
{indentation}            api_v0_mcp_router = APIRouter(prefix="/api/v0/mcp", tags=["mcp-api-v0"])
{indentation}            
{indentation}            # Register the same routes to this router
{indentation}            for route in self.router.routes:
{indentation}                # Add route to compatibility router
{indentation}                api_v0_mcp_router.routes.append(route)
{indentation}            
{indentation}            # Include compatibility router in the app
{indentation}            app.include_router(api_v0_mcp_router)
{indentation}            logger.info(f"MCP Server also registered at /api/v0/mcp for test compatibility")
{indentation}        except Exception as e:
{indentation}            error_msg = f"Failed to register compatibility router at /api/v0/mcp: {{e}}"
{indentation}            logger.warning(error_msg)
{indentation}            errors.append(error_msg)"""
                        
                        # Insert compatibility code
                        new_register_method = register_method[:insert_point] + compat_code + register_method[insert_point:]
                        
                        # Replace in content
                        new_content = content.replace(register_method, new_register_method)
                        
                        # Write the updated content
                        with open(server_path, 'w') as f:
                            f.write(new_content)
                        logger.info("✅ Successfully added API v0 compatibility to register_with_app")
                        return True
                    else:
                        logger.warning("Could not find app.include_router in register_with_app method")
            else:
                logger.warning("Could not find register_with_app method implementation")
        else:
            logger.warning("Could not find register_with_app method in server.py")
    except Exception as e:
        logger.error(f"Error fixing register_with_app method: {e}")
        logger.error(traceback.format_exc())
    
    logger.error("❌ Failed to fix register_with_app method")
    return False

# Create a script for starting fixed MCP server
def create_fixed_server_script():
    """Create a script for starting the fixed MCP server."""
    fixed_script_path = "/home/barberb/ipfs_kit_py/run_fixed_mcp_server.py"
    
    try:
        # Content for the fixed server script
        script_content = """#!/usr/bin/env python3
\"\"\"
Run MCP server with all fixes applied.
This script starts the MCP server with proper configuration to address known issues.
\"\"\"

import logging
import uvicorn
from fastapi import FastAPI
from ipfs_kit_py.mcp.server import MCPServer

# Configure logging
logging.basicConfig(level=logging.INFO,
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("run_fixed_mcp_server")

# Create FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Model-Controller-Persistence Server for IPFS Kit",
    version="1.0.0"
)

# Root endpoint
@app.get("/")
def read_root():
    """Root endpoint for the server."""
    return {
        "name": "IPFS Kit MCP Server",
        "version": "1.0.0",
        "description": "API server for IPFS Kit operations",
        "endpoints": ["/", "/health", "/docs", "/api/v0/mcp/"]
    }

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint."""
    import time
    return {
        "status": "ok",
        "timestamp": time.time()
    }

# Create MCP server with debug mode for better logging
mcp_server = MCPServer(debug_mode=True)

# Register MCP server with FastAPI app with double routing
# This will register endpoints at both /mcp and /api/v0/mcp for compatibility
mcp_server.register_with_app(app, prefix="/mcp")

# Also direct registration for test compatibility
mcp_server.register_with_app(app, prefix="/api/v0/mcp")

if __name__ == "__main__":
    logger.info("Starting fixed MCP server on port 9991")
    uvicorn.run(app, host="127.0.0.1", port=9991)
"""
        
        # Write the script file
        with open(fixed_script_path, 'w') as f:
            f.write(script_content)
        
        # Make it executable
        os.chmod(fixed_script_path, 0o755)
        
        logger.info(f"✅ Successfully created fixed server script at {fixed_script_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating fixed server script: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function to fix all MCP API issues."""
    logger.info("Starting comprehensive MCP API fixes...")
    
    # Fix WebRTC dependency check
    webrtc_fixed = fix_webrtc_dependency_check()
    if webrtc_fixed:
        logger.info("✅ WebRTC dependency check fixed successfully")
    else:
        logger.error("❌ Failed to fix WebRTC dependency check")
        
    # Fix IPFS cat endpoint
    cat_fixed = fix_ipfs_cat_endpoint()
    if cat_fixed:
        logger.info("✅ IPFS cat endpoint fixed successfully")
    else:
        logger.error("❌ Failed to fix IPFS cat endpoint")
        
    # Add basic endpoints
    endpoints_added = add_basic_endpoints()
    if endpoints_added:
        logger.info("✅ Basic endpoints added successfully")
    else:
        logger.error("❌ Failed to add basic endpoints")
        
    # Fix register_with_app method
    register_fixed = fix_register_with_app()
    if register_fixed:
        logger.info("✅ register_with_app method fixed successfully")
    else:
        logger.error("❌ Failed to fix register_with_app method")
        
    # Create fixed server script
    script_created = create_fixed_server_script()
    if script_created:
        logger.info("✅ Fixed server script created successfully")
    else:
        logger.error("❌ Failed to create fixed server script")
    
    # Report overall status
    success = all([webrtc_fixed, cat_fixed, endpoints_added, register_fixed, script_created])
    logger.info("\n" + "="*50)
    logger.info("MCP API FIX SUMMARY")
    logger.info("="*50)
    logger.info(f"WebRTC dependency check: {'✅ Fixed' if webrtc_fixed else '❌ Failed'}")
    logger.info(f"IPFS cat endpoint: {'✅ Fixed' if cat_fixed else '❌ Failed'}")
    logger.info(f"Basic endpoints: {'✅ Added' if endpoints_added else '❌ Failed'}")
    logger.info(f"register_with_app method: {'✅ Fixed' if register_fixed else '❌ Failed'}")
    logger.info(f"Fixed server script: {'✅ Created' if script_created else '❌ Failed'}")
    logger.info("="*50)
    logger.info(f"Overall status: {'✅ Success' if success else '❌ Partial success, some fixes failed'}")
    logger.info("="*50)
    
    if script_created:
        logger.info("\nTo run the fixed MCP server:")
        logger.info("  python run_fixed_mcp_server.py")
        logger.info("  (This will start the server on port 9991)")
        
    logger.info("\nTo test MCP API endpoints:")
    logger.info("  python test_mcp_api.py --url http://localhost:9991")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())