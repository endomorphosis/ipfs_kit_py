#!/usr/bin/env python3
"""
IPFS-VFS Dependency Manager and System Check

This script handles dependency installation, system compatibility checks, and environment setup
for the IPFS Virtual Filesystem MCP integration.
"""

import os
import sys
import subprocess
import platform
import logging
import argparse
import json
from pathlib import Path
from importlib import util as importlib_util
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("vfs_setup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("vfs-setup")

class DependencyManager:
    """Manages dependencies for IPFS Virtual Filesystem"""
    
    # Define required Python modules
    PYTHON_DEPENDENCIES = {
        "core": [
            {"name": "fastapi", "min_version": "0.68.0"},
            {"name": "uvicorn", "min_version": "0.15.0"},
            {"name": "aiohttp", "min_version": "3.8.0"},
            {"name": "requests", "min_version": "2.26.0"},
            {"name": "pydantic", "min_version": "1.8.0"},
        ],
        "ipfs": [
            {"name": "ipfshttpclient", "min_version": "0.8.0"},
            {"name": "multiaddr", "min_version": "0.0.9"},
        ],
        "storage": [
            {"name": "boto3", "min_version": "1.20.0"},
            {"name": "google-cloud-storage", "min_version": "2.0.0", "optional": True},
        ],
        "ui": [
            {"name": "rich", "min_version": "10.0.0", "optional": True},
            {"name": "tqdm", "min_version": "4.62.0", "optional": True},
        ]
    }
    
    # Define system dependencies
    SYSTEM_DEPENDENCIES = [
        {"name": "ipfs", "command": "ipfs --version", "optional": True},
        {"name": "git", "command": "git --version"},
        {"name": "curl", "command": "curl --version"},
    ]
    
    def __init__(self, install_dir: str = None, config_file: str = None):
        """Initialize dependency manager"""
        self.install_dir = install_dir or os.getcwd()
        self.config_file = config_file or os.path.join(self.install_dir, "vfs_config.json")
        self.config = self._load_config()
        
        # Path to virtual environment
        self.venv_path = os.path.join(self.install_dir, ".venv")
        self.venv_active = self._check_venv_active()
        
        logger.info(f"Dependency manager initialized in {self.install_dir}")
    
    def _load_config(self) -> Dict:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    return json.load(f)
            logger.warning(f"Configuration file not found at {self.config_file}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
        
        return {}
    
    def _check_venv_active(self) -> bool:
        """Check if a virtual environment is active"""
        return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    def check_python_version(self) -> Tuple[bool, str]:
        """Check Python version compatibility"""
        current_version = tuple(map(int, platform.python_version_tuple()))
        required_version = (3, 7, 0)
        
        if current_version >= required_version:
            logger.info(f"✅ Python version {platform.python_version()} meets requirements")
            return True, f"Python {platform.python_version()}"
        else:
            logger.warning(f"❌ Python version {platform.python_version()} is below required {'.'.join(map(str, required_version))}")
            return False, f"Python {platform.python_version()}"
    
    def check_python_module(self, module_info: Dict) -> Tuple[bool, str]:
        """Check if a Python module is installed and meets version requirements"""
        module_name = module_info["name"]
        min_version = module_info.get("min_version")
        optional = module_info.get("optional", False)
        
        try:
            # Check if module can be imported
            spec = importlib_util.find_spec(module_name)
            
            if spec is None:
                if optional:
                    logger.warning(f"⚠️ Optional module {module_name} not found")
                    return False, f"Not installed (optional)"
                else:
                    logger.warning(f"❌ Required module {module_name} not found")
                    return False, f"Not installed"
            
            # If module exists, try to get its version
            module = importlib_util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Try different attributes for version
            version_attr = None
            for attr in ["__version__", "version", "VERSION"]:
                if hasattr(module, attr):
                    version_attr = getattr(module, attr)
                    if isinstance(version_attr, str):
                        break
            
            if version_attr is not None and min_version is not None:
                # Convert version strings to tuples for comparison
                current = self._version_to_tuple(version_attr)
                required = self._version_to_tuple(min_version)
                
                if current >= required:
                    logger.info(f"✅ Module {module_name} version {version_attr} meets requirements")
                    return True, version_attr
                else:
                    if optional:
                        logger.warning(f"⚠️ Optional module {module_name} version {version_attr} is below required {min_version}")
                        return False, f"{version_attr} (update recommended)"
                    else:
                        logger.warning(f"❌ Module {module_name} version {version_attr} is below required {min_version}")
                        return False, f"{version_attr} (update required)"
            
            # If we can't determine version or no min version specified
            logger.info(f"✅ Module {module_name} is installed")
            return True, "Installed"
        
        except Exception as e:
            if optional:
                logger.warning(f"⚠️ Error checking optional module {module_name}: {e}")
                return False, f"Error: {str(e)[:30]}... (optional)"
            else:
                logger.error(f"❌ Error checking module {module_name}: {e}")
                return False, f"Error: {str(e)[:30]}..."
    
    def check_system_dependency(self, dependency: Dict) -> Tuple[bool, str]:
        """Check if a system dependency is installed"""
        name = dependency["name"]
        command = dependency["command"]
        optional = dependency.get("optional", False)
        
        try:
            # Run command to check if dependency is installed
            process = subprocess.run(
                command, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode == 0:
                version_info = process.stdout.strip().split("\n")[0]
                logger.info(f"✅ System dependency {name} is installed: {version_info}")
                return True, version_info
            else:
                if optional:
                    logger.warning(f"⚠️ Optional system dependency {name} not found")
                    return False, "Not installed (optional)"
                else:
                    logger.warning(f"❌ System dependency {name} not found")
                    return False, "Not installed"
        
        except Exception as e:
            if optional:
                logger.warning(f"⚠️ Error checking optional system dependency {name}: {e}")
                return False, f"Error (optional)"
            else:
                logger.error(f"❌ Error checking system dependency {name}: {e}")
                return False, "Error"
    
    def check_all_dependencies(self) -> Dict:
        """Check all dependencies and return status"""
        results = {
            "python_version": self.check_python_version(),
            "virtual_env": (self.venv_active, "Active" if self.venv_active else "Not active"),
            "python_modules": {},
            "system_dependencies": {}
        }
        
        # Check all Python modules
        for category, modules in self.PYTHON_DEPENDENCIES.items():
            results["python_modules"][category] = {}
            for module in modules:
                name = module["name"]
                results["python_modules"][category][name] = self.check_python_module(module)
        
        # Check system dependencies
        for dependency in self.SYSTEM_DEPENDENCIES:
            name = dependency["name"]
            results["system_dependencies"][name] = self.check_system_dependency(dependency)
        
        # Compute overall status
        all_required_modules_ok = all(
            info[0] for category, modules in results["python_modules"].items()
            for name, info in modules.items()
            if not self.PYTHON_DEPENDENCIES[category][next(
                i for i, m in enumerate(self.PYTHON_DEPENDENCIES[category]) 
                if m["name"] == name
            )].get("optional", False)
        )
        
        all_required_system_deps_ok = all(
            info[0] for name, info in results["system_dependencies"].items()
            if not next(
                dep for dep in self.SYSTEM_DEPENDENCIES 
                if dep["name"] == name
            ).get("optional", False)
        )
        
        results["overall_status"] = results["python_version"][0] and all_required_modules_ok and all_required_system_deps_ok
        
        return results
    
    def install_python_dependencies(self, upgrade: bool = False) -> bool:
        """Install required Python dependencies"""
        logger.info("Installing Python dependencies...")
        
        pip_args = ["install"]
        if upgrade:
            pip_args.append("--upgrade")
        
        # Collect all non-optional modules
        all_modules = []
        for category, modules in self.PYTHON_DEPENDENCIES.items():
            for module in modules:
                if not module.get("optional", False):
                    # Use exact version if specified
                    if "min_version" in module:
                        all_modules.append(f"{module['name']}>={module['min_version']}")
                    else:
                        all_modules.append(module["name"])
        
        # Install all modules at once
        try:
            cmd = [sys.executable, "-m", "pip"] + pip_args + all_modules
            logger.info(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            logger.info("✅ Successfully installed Python dependencies")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Error installing Python dependencies: {e}")
            return False
    
    def create_virtual_env(self) -> bool:
        """Create a virtual environment"""
        if self.venv_active:
            logger.info("Virtual environment is already active")
            return True
        
        logger.info(f"Creating virtual environment in {self.venv_path}")
        
        try:
            subprocess.run([sys.executable, "-m", "venv", self.venv_path], check=True)
            
            # Get path to activation script
            if platform.system() == "Windows":
                activate_script = os.path.join(self.venv_path, "Scripts", "activate.bat")
                activate_cmd = f"{activate_script}"
            else:
                activate_script = os.path.join(self.venv_path, "bin", "activate")
                activate_cmd = f"source {activate_script}"
            
            if os.path.exists(activate_script):
                logger.info(f"✅ Virtual environment created. Activate with: {activate_cmd}")
                return True
            else:
                logger.error(f"❌ Virtual environment created but activation script not found")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error creating virtual environment: {e}")
            return False
    
    def install_ipfs(self) -> bool:
        """Attempt to install IPFS"""
        logger.info("Attempting to install IPFS...")
        
        system = platform.system().lower()
        
        try:
            if system == "linux":
                # Try to install IPFS using package manager or direct download
                logger.info("Detected Linux system, installing IPFS...")
                
                # First check if apt is available (Debian/Ubuntu)
                try:
                    subprocess.run(["apt", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    logger.info("Using apt to install IPFS")
                    
                    # Add IPFS repository and install
                    commands = [
                        "sudo apt-get update",
                        "sudo apt-get install -y wget",
                        "wget -O ipfs.tar.gz https://dist.ipfs.io/go-ipfs/v0.14.0/go-ipfs_v0.14.0_linux-amd64.tar.gz",
                        "tar -xvzf ipfs.tar.gz",
                        "cd go-ipfs && sudo bash install.sh",
                        "ipfs --version"
                    ]
                    
                    for cmd in commands:
                        logger.info(f"Running: {cmd}")
                        result = subprocess.run(cmd, shell=True, check=False)
                        if result.returncode != 0:
                            logger.warning(f"Command failed with code {result.returncode}: {cmd}")
                
                    return self.check_system_dependency({"name": "ipfs", "command": "ipfs --version"})[0]
                
                except Exception:
                    logger.warning("apt not available, trying alternative installation method")
            
            elif system == "darwin":
                # macOS installation via Homebrew
                logger.info("Detected macOS, installing IPFS via Homebrew...")
                
                try:
                    # Check if Homebrew is installed
                    subprocess.run(["brew", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    
                    # Install IPFS
                    subprocess.run(["brew", "install", "ipfs"], check=True)
                    
                    return self.check_system_dependency({"name": "ipfs", "command": "ipfs --version"})[0]
                
                except Exception as e:
                    logger.warning(f"Error installing IPFS via Homebrew: {e}")
                    logger.info("Please install Homebrew first: https://brew.sh")
            
            elif system == "windows":
                # Windows installation instructions
                logger.info("Detected Windows, showing manual installation instructions...")
                logger.info("Please download and install IPFS Desktop from: https://github.com/ipfs/ipfs-desktop/releases")
                logger.info("After installation, restart this script.")
                return False
            
            # Fallback for all systems - show manual instructions
            logger.warning("Automatic IPFS installation not supported for this system")
            logger.info("Please install IPFS manually from: https://docs.ipfs.tech/install/ipfs-desktop/")
            return False
        
        except Exception as e:
            logger.error(f"Error installing IPFS: {e}")
            return False
    
    def initialize_ipfs(self) -> bool:
        """Initialize IPFS if needed"""
        # Check if IPFS is already initialized
        try:
            result = subprocess.run(
                "ipfs id", 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("✅ IPFS is already initialized")
                return True
            
            # Initialize IPFS
            logger.info("Initializing IPFS...")
            subprocess.run("ipfs init", shell=True, check=True)
            logger.info("✅ IPFS initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing IPFS: {e}")
            return False
    
    def setup_environment(self, force_recreate: bool = False) -> bool:
        """Set up the environment for VFS integration"""
        logger.info("Setting up environment for VFS integration...")
        
        # Create config directory
        config_dir = os.path.expanduser("~/.ipfs_kit")
        os.makedirs(config_dir, exist_ok=True)
        
        # Create virtual env if needed and not active
        if not self.venv_active and not os.path.exists(self.venv_path):
            if self.create_virtual_env():
                logger.info(f"Please activate the virtual environment and run this script again")
                if platform.system() == "Windows":
                    logger.info(f"{os.path.join(self.venv_path, 'Scripts', 'activate.bat')}")
                else:
                    logger.info(f"source {os.path.join(self.venv_path, 'bin', 'activate')}")
                return False
        
        # Create necessary directories
        directories = [
            os.path.join(config_dir, "vfs"),
            os.path.join(config_dir, "local_storage"),
            os.path.join(config_dir, "backups")
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        
        # Copy config file if it doesn't exist in the config dir
        config_dest = os.path.join(config_dir, "vfs_config.json")
        if not os.path.exists(config_dest) and os.path.exists(self.config_file):
            import shutil
            shutil.copy(self.config_file, config_dest)
            logger.info(f"Copied config file to {config_dest}")
        
        # Create helper scripts
        if platform.system() != "Windows":
            self._create_helper_scripts()
        
        return True
    
    def _create_helper_scripts(self):
        """Create helper scripts for environment setup"""
        # Create script to activate virtual env and set up environment
        activate_script = os.path.join(self.install_dir, "activate_vfs_env.sh")
        
        with open(activate_script, "w") as f:
            f.write(f"""#!/bin/bash
# Activate VFS environment
if [ -f "{os.path.join(self.venv_path, 'bin', 'activate')}" ]; then
    source "{os.path.join(self.venv_path, 'bin', 'activate')}"
    echo "Virtual environment activated"
else
    echo "Virtual environment not found"
fi

# Set up environment variables
export IPFS_KIT_CONFIG_DIR="{os.path.expanduser('~/.ipfs_kit')}"
export IPFS_KIT_VFS_ENABLED=1
export PYTHONPATH="{self.install_dir}:$PYTHONPATH"

echo "Environment set up for VFS integration"
""")
        
        # Make script executable
        os.chmod(activate_script, 0o755)
        logger.info(f"Created activation script: {activate_script}")
        
        # Create a simple health check script
        health_script = os.path.join(self.install_dir, "check_vfs_health.sh")
        
        with open(health_script, "w") as f:
            f.write(f"""#!/bin/bash
# Check VFS health
echo "Checking MCP server health..."
curl -s http://localhost:3000/health

echo -e "\\nChecking virtual filesystem tools..."
python -c "import requests; print(requests.post('http://localhost:3000/jsonrpc', json={'jsonrpc': '2.0', 'method': 'get_tools', 'params': {}, 'id': 1}).json())" | grep -i vfs
""")
        
        # Make script executable
        os.chmod(health_script, 0o755)
        logger.info(f"Created health check script: {health_script}")
    
    def _version_to_tuple(self, version_str: str) -> Tuple:
        """Convert version string to tuple for comparison"""
        # Remove any non-numeric prefix (e.g., 'v1.0.0' -> '1.0.0')
        version_str = ''.join(c for c in version_str if c.isdigit() or c == '.')
        
        # Split by dot and convert to integers
        parts = []
        for part in version_str.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        
        # Ensure at least three elements (major, minor, patch)
        while len(parts) < 3:
            parts.append(0)
        
        return tuple(parts)

def display_results(results: Dict):
    """Display dependency check results in a readable format"""
    try:
        # Try to use rich if available
        from rich.console import Console
        from rich.table import Table
        
        console = Console()
        
        console.print("\n[bold blue]===== IPFS Virtual Filesystem Setup Report =====")
        
        # Python version and environment
        python_status = "[green]✓" if results["python_version"][0] else "[red]✗"
        venv_status = "[green]✓" if results["virtual_env"][0] else "[yellow]!"
        
        console.print(f"\n[bold]System Environment:")
        console.print(f"  Python: {python_status} {results['python_version'][1]}")
        console.print(f"  Virtual Environment: {venv_status} {results['virtual_env'][1]}")
        
        # System dependencies
        console.print(f"\n[bold]System Dependencies:")
        for name, (ok, version) in results["system_dependencies"].items():
            status = "[green]✓" if ok else "[yellow]!" if "optional" in version else "[red]✗"
            console.print(f"  {name}: {status} {version}")
        
        # Python modules by category
        console.print(f"\n[bold]Python Dependencies:")
        
        for category, modules in results["python_modules"].items():
            console.print(f"\n  [bold]{category.capitalize()} Modules:")
            
            table = Table(show_header=True, header_style="bold")
            table.add_column("Module", style="dim")
            table.add_column("Status")
            table.add_column("Version/Info")
            
            for name, (ok, version) in modules.items():
                status = "✓" if ok else "!" if "optional" in version else "✗"
                color = "green" if ok else "yellow" if "optional" in version else "red"
                table.add_row(name, f"[{color}]{status}", version)
            
            console.print(table)
        
        # Overall status
        overall_status = "[green]READY" if results["overall_status"] else "[red]NOT READY"
        console.print(f"\n[bold]Overall Status: {overall_status}")
        
        if not results["overall_status"]:
            console.print("\n[yellow]To resolve issues, run this script with the --install flag")
        
    except ImportError:
        # Fallback to plain text
        print("\n===== IPFS Virtual Filesystem Setup Report =====\n")
        
        # Python version and environment
        python_status = "✓" if results["python_version"][0] else "✗"
        venv_status = "✓" if results["virtual_env"][0] else "!"
        
        print("System Environment:")
        print(f"  Python: {python_status} {results['python_version'][1]}")
        print(f"  Virtual Environment: {venv_status} {results['virtual_env'][1]}")
        
        # System dependencies
        print("\nSystem Dependencies:")
        for name, (ok, version) in results["system_dependencies"].items():
            status = "✓" if ok else "!" if "optional" in version else "✗"
            print(f"  {name}: {status} {version}")
        
        # Python modules
        print("\nPython Dependencies:")
        
        for category, modules in results["python_modules"].items():
            print(f"\n  {category.capitalize()} Modules:")
            
            # Calculate column widths
            name_width = max(len(name) for name in modules.keys()) + 2
            status_width = 4
            
            # Print header
            print(f"  {'Module':<{name_width}}{'Status':<{status_width}}Version/Info")
            print(f"  {'-' * name_width}{'-' * status_width}{'-' * 20}")
            
            # Print modules
            for name, (ok, version) in modules.items():
                status = "✓" if ok else "!" if "optional" in version else "✗"
                print(f"  {name:<{name_width}}{status:<{status_width}}{version}")
        
        # Overall status
        overall_status = "READY" if results["overall_status"] else "NOT READY"
        print(f"\nOverall Status: {overall_status}")
        
        if not results["overall_status"]:
            print("\nTo resolve issues, run this script with the --install flag")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="IPFS-VFS Dependency Manager and System Check")
    parser.add_argument("--install", action="store_true", help="Install missing dependencies")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade existing dependencies")
    parser.add_argument("--venv", action="store_true", help="Create virtual environment")
    parser.add_argument("--ipfs", action="store_true", help="Install IPFS")
    parser.add_argument("--setup", action="store_true", help="Set up environment")
    parser.add_argument("--dir", help="Installation directory")
    parser.add_argument("--config", help="Configuration file path")
    
    args = parser.parse_args()
    
    # Create dependency manager
    manager = DependencyManager(install_dir=args.dir, config_file=args.config)
    
    # Check dependencies
    results = manager.check_all_dependencies()
    
    # Install dependencies if requested
    if args.install:
        print("\nInstalling Python dependencies...")
        manager.install_python_dependencies(upgrade=args.upgrade)
    
    if args.venv:
        print("\nCreating virtual environment...")
        manager.create_virtual_env()
    
    if args.ipfs:
        print("\nInstalling IPFS...")
        manager.install_ipfs()
        manager.initialize_ipfs()
    
    if args.setup:
        print("\nSetting up environment...")
        manager.setup_environment()
    
    # Display results
    display_results(results)
    
    return 0 if results["overall_status"] else 1

if __name__ == "__main__":
    sys.exit(main())
