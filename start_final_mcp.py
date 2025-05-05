#!/usr/bin/env python3
"""
MCP Server Launcher

This Python launcher handles compatibility issues, applies necessary patches,
ensures proper module imports, and runs the best available server implementation.
"""

import os
import sys
import signal
import logging
import argparse
import importlib.util
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mcp_launcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mcp-launcher")

# Server implementations in order of preference
SERVER_IMPLEMENTATIONS = [
    "fixed_final_mcp_server.py",
    "final_mcp_server.py",
    "enhanced_mcp_server_fixed.py",
    "direct_mcp_server.py",
]

# Required modules
REQUIRED_MODULES = [
    "starlette",
    "uvicorn",
    "fastapi", 
    "jsonrpc",
    "asyncio",
    "aiohttp"
]

class MCPServerLauncher:
    """Launches the MCP server with proper environment setup and patches."""
    
    def __init__(self, 
                 host: str = "0.0.0.0", 
                 port: int = 3000, 
                 log_file: str = "mcp_server.log"):
        self.host = host
        self.port = port
        self.log_file = log_file
        self.current_dir = os.getcwd()
        self.python_path_additions = []
        self.server_process = None
        self.exit_requested = False
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
    
    def setup_python_path(self) -> None:
        """Set up the Python path to ensure proper module imports."""
        # Add current directory
        sys.path.insert(0, self.current_dir)
        self.python_path_additions.append(self.current_dir)
        
        # Add potential module directories
        potential_module_dirs = [
            os.path.join(self.current_dir, "ipfs_kit_py"),
            os.path.join(self.current_dir, "vfs"),
        ]
        
        for module_dir in potential_module_dirs:
            if os.path.isdir(module_dir) and module_dir not in sys.path:
                sys.path.insert(0, module_dir)
                self.python_path_additions.append(module_dir)
                logger.info(f"Added {module_dir} to Python path")
    
    def check_required_modules(self) -> List[str]:
        """Check if required modules are available and return missing ones."""
        missing_modules = []
        
        for module_name in REQUIRED_MODULES:
            try:
                importlib.import_module(module_name)
                logger.info(f"Module {module_name} is available")
            except ImportError:
                missing_modules.append(module_name)
                logger.warning(f"Module {module_name} is missing")
        
        return missing_modules
    
    def find_best_server_implementation(self) -> Optional[str]:
        """Find the best available server implementation."""
        for server_script in SERVER_IMPLEMENTATIONS:
            server_path = os.path.join(self.current_dir, server_script)
            if os.path.isfile(server_path):
                logger.info(f"Found server implementation: {server_script}")
                return server_path
        
        logger.error("No server implementation found")
        return None
    
    def apply_compatibility_patches(self) -> None:
        """Apply compatibility patches to ensure proper operation."""
        logger.info("Applying compatibility patches")
        
        # Check for Python version
        python_version = sys.version_info
        if python_version.major == 3 and python_version.minor < 7:
            logger.warning(f"Python version {python_version.major}.{python_version.minor} may have limited compatibility")
            self._patch_asyncio_for_old_python()
        
        # Apply module compatibility patches
        if os.path.exists(os.path.join(self.current_dir, "mcp_module_patch.py")):
            logger.info("Applying module compatibility patch")
            try:
                # Dynamic import and execute
                spec = importlib.util.spec_from_file_location(
                    "mcp_module_patch", 
                    os.path.join(self.current_dir, "mcp_module_patch.py")
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    logger.info("Successfully applied module compatibility patch")
            except Exception as e:
                logger.error(f"Error applying module compatibility patch: {e}")
    
    def _patch_asyncio_for_old_python(self) -> None:
        """Patch asyncio for older Python versions."""
        try:
            # Create a simple patch for asyncio
            patch_file = os.path.join(self.current_dir, "asyncio_patch.py")
            if not os.path.exists(patch_file):
                with open(patch_file, "w") as f:
                    f.write("""
# Asyncio compatibility patch for older Python versions
import asyncio
import sys

if sys.version_info < (3, 7):
    # Add missing methods or monkey patch existing ones
    def _patch_loop():
        loop = asyncio.get_event_loop()
        if not hasattr(loop, 'create_future'):
            loop.create_future = lambda: asyncio.Future(loop=loop)
        return loop
    
    asyncio.get_event_loop = _patch_loop
    """)
                
            # Import the patch
            spec = importlib.util.spec_from_file_location("asyncio_patch", patch_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                logger.info("Applied asyncio patch for older Python versions")
        except Exception as e:
            logger.error(f"Error applying asyncio patch: {e}")
    
    def handle_signal(self, signum: int, frame: Any) -> None:
        """Handle signals (SIGINT, SIGTERM) to gracefully shutdown."""
        if self.exit_requested:
            logger.warning("Forced exit requested")
            sys.exit(1)
            
        logger.info(f"Received signal {signum}, shutting down...")
        self.exit_requested = True
        self.stop_server()
    
    def start_server(self) -> int:
        """Start the MCP server and return the exit code."""
        # Set up Python path
        self.setup_python_path()
        
        # Check for required modules
        missing_modules = self.check_required_modules()
        if missing_modules:
            logger.warning(f"Missing required modules: {', '.join(missing_modules)}")
            logger.warning("The server may not function correctly")
        
        # Apply compatibility patches
        self.apply_compatibility_patches()
        
        # Find the best server implementation
        server_script = self.find_best_server_implementation()
        if not server_script:
            logger.error("No server implementation found")
            return 1
        
        # Build command
        cmd = [
            sys.executable,
            server_script,
            "--host", self.host,
            "--port", str(self.port),
            "--log", self.log_file
        ]
        
        # Set environment variables
        env = os.environ.copy()
        if self.python_path_additions:
            python_path = os.pathsep.join(self.python_path_additions)
            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = python_path + os.pathsep + env["PYTHONPATH"]
            else:
                env["PYTHONPATH"] = python_path
        
        # Start the server
        logger.info(f"Starting server: {' '.join(cmd)}")
        try:
            self.server_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Monitor the server process
            while self.server_process.poll() is None and not self.exit_requested:
                # Process stdout
                if self.server_process.stdout:
                    line = self.server_process.stdout.readline()
                    if line:
                        logger.info(line.rstrip())
                
                time.sleep(0.1)
            
            # Check exit status
            if self.server_process.returncode is not None:
                if self.server_process.returncode != 0:
                    logger.error(f"Server exited with code {self.server_process.returncode}")
                else:
                    logger.info("Server exited normally")
                return self.server_process.returncode
            else:
                # We requested exit but process is still running
                self.stop_server()
                return 0
                
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            return 1
    
    def stop_server(self) -> None:
        """Stop the server process."""
        if self.server_process and self.server_process.poll() is None:
            logger.info("Stopping server process...")
            self.server_process.terminate()
            
            # Wait for the process to terminate
            for _ in range(10):
                if self.server_process.poll() is not None:
                    logger.info("Server process terminated")
                    break
                time.sleep(0.5)
            
            # If the process is still running, force kill
            if self.server_process.poll() is None:
                logger.warning("Server process did not terminate, forcing kill")
                self.server_process.kill()
                self.server_process.wait()

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='MCP Server Launcher')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=3000, help='Port to run the server on')
    parser.add_argument('--log', default='mcp_server.log', help='Log file to write output to')
    return parser.parse_args()

def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    launcher = MCPServerLauncher(
        host=args.host,
        port=args.port,
        log_file=args.log
    )
    
    return launcher.start_server()

if __name__ == "__main__":
    sys.exit(main())
