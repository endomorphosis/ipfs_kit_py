#!/usr/bin/env python3
"""
Complete IPFS Kit Workspace Reorganization Script
==================================================

This script completes the reorganization of the IPFS Kit workspace 
for better maintainability while preserving all functionality.
"""

import os
import shutil
from pathlib import Path
import logging
import glob
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompleteWorkspaceReorganizer:
    """Completes the reorganization of the IPFS Kit workspace"""
    
    def __init__(self, root_path: Path):
        self.root = Path(root_path)
        self.backup_dir = self.root / "reorganization_backup_final"
        
    def create_backup(self):
        """Create backup before reorganization"""
        logger.info("Creating final backup before reorganization...")
        
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        
        self.backup_dir.mkdir()
        
        # Backup critical files and directories that will be moved
        critical_items = [
            "core/",
            "tools/", 
            "mcp/",
            "test_*.py",
            "*.py",
            ".vscode/",
            "scripts/",
            "requirements.txt",
            "pyproject.toml"
        ]
        
        for pattern in critical_items:
            if '*' in pattern:
                matches = glob.glob(str(self.root / pattern))
                for match in matches:
                    match_path = Path(match)
                    rel_path = match_path.relative_to(self.root)
                    backup_path = self.backup_dir / rel_path
                    
                    try:
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        if match_path.is_dir():
                            shutil.copytree(match_path, backup_path, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                        else:
                            shutil.copy2(match_path, backup_path)
                    except Exception as e:
                        logger.warning(f"Could not backup {match_path}: {e}")
            else:
                src = self.root / pattern
                if src.exists():
                    try:
                        if src.is_dir():
                            shutil.copytree(src, self.backup_dir / pattern, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                        else:
                            shutil.copy2(src, self.backup_dir / pattern)
                    except Exception as e:
                        logger.warning(f"Could not backup {src}: {e}")
        
        logger.info(f"Backup created at {self.backup_dir}")

    def ensure_directory_structure(self):
        """Ensure the new directory structure exists"""
        logger.info("Ensuring new directory structure exists...")
        
        directories = [
            "src/ipfs_kit/core",
            "src/ipfs_kit/tools", 
            "src/ipfs_kit/mcp",
            "src/ipfs_kit/utils",
            "tests/unit",
            "tests/integration",
            "tests/e2e",
            "tests/validation",
            "scripts",
            "config/vscode",
            "docs/reports",
            "docs/plans",
            "deployment/docker",
            "dev",
            "examples",
            "build/logs",
            "build/status",
            "build/cache"
        ]
        
        for directory in directories:
            dir_path = self.root / directory
            dir_path.mkdir(parents=True, exist_ok=True)

    def move_core_infrastructure(self):
        """Move core infrastructure to src/ipfs_kit/"""
        logger.info("Moving core infrastructure...")
        
        # Move core directory if it hasn't been moved yet
        if (self.root / "core").exists() and not (self.root / "src/ipfs_kit/core/__init__.py").exists():
            src_core = self.root / "core"
            dest_core = self.root / "src/ipfs_kit/core"
            
            # Remove destination if it exists
            if dest_core.exists():
                shutil.rmtree(dest_core)
            
            shutil.copytree(src_core, dest_core, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            logger.info(f"Copied core/ -> src/ipfs_kit/core/")

        # Move tools directory if it hasn't been moved yet
        if (self.root / "tools").exists() and not (self.root / "src/ipfs_kit/tools/__init__.py").exists():
            src_tools = self.root / "tools"
            dest_tools = self.root / "src/ipfs_kit/tools"
            
            # Remove destination if it exists
            if dest_tools.exists():
                shutil.rmtree(dest_tools)
            
            # Copy only the main tool files, not all the dev tools
            dest_tools.mkdir(parents=True, exist_ok=True)
            
            main_tool_files = [
                "ipfs_core_tools.py",
                "ipfs_core_tools_part2.py",
                "unified_ipfs_tools.py"
            ]
            
            for tool_file in main_tool_files:
                src_file = src_tools / tool_file
                if src_file.exists():
                    shutil.copy2(src_file, dest_tools / tool_file)
                    logger.info(f"Copied {tool_file} to src/ipfs_kit/tools/")

        # Move MCP directory if it hasn't been moved yet  
        if (self.root / "mcp").exists() and not (self.root / "src/ipfs_kit/mcp/__init__.py").exists():
            src_mcp = self.root / "mcp"
            dest_mcp = self.root / "src/ipfs_kit/mcp"
            
            # Remove destination if it exists
            if dest_mcp.exists():
                shutil.rmtree(dest_mcp)
            
            shutil.copytree(src_mcp, dest_mcp, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            logger.info(f"Copied mcp/ -> src/ipfs_kit/mcp/")

    def move_test_files(self):
        """Move test files to tests/ directory"""
        logger.info("Moving test files...")
        
        # Find all test files in root
        test_files = glob.glob(str(self.root / "test_*.py"))
        
        for test_file in test_files:
            test_path = Path(test_file)
            filename = test_path.name
            
            # Categorize tests
            if any(keyword in filename.lower() for keyword in ["integration", "comprehensive", "e2e", "end_to_end"]):
                dest_dir = self.root / "tests/integration"
            elif any(keyword in filename.lower() for keyword in ["validation", "final", "production"]):
                dest_dir = self.root / "tests/validation"
            elif any(keyword in filename.lower() for keyword in ["phase1", "phase2"]):
                dest_dir = self.root / "tests/unit"
            else:
                dest_dir = self.root / "tests"
            
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / filename
            
            if not dest_file.exists():
                shutil.copy2(test_path, dest_file)
                logger.info(f"Copied {filename} -> {dest_dir.relative_to(self.root)}/")

    def move_scripts(self):
        """Move script files to scripts/ directory"""
        logger.info("Moving script files...")
        
        script_patterns = [
            "initialize_*.py",
            "restart_*.sh", 
            "run_*.sh",
            "start_*.sh",
            "setup_*.sh",
            "*_validation.sh",
            "*_verification.sh",
            "manual_test.sh",
            "quick_test.sh"
        ]
        
        existing_scripts = (self.root / "scripts").exists()
        
        for pattern in script_patterns:
            matches = glob.glob(str(self.root / pattern))
            for match in matches:
                match_path = Path(match)
                filename = match_path.name
                dest_file = self.root / "scripts" / filename
                
                if not dest_file.exists():
                    shutil.copy2(match_path, dest_file)
                    logger.info(f"Copied {filename} -> scripts/")

    def move_dev_files(self):
        """Move development files to dev/ directory"""
        logger.info("Moving development files...")
        
        dev_files = [
            "phase2_final_status.py",
            "quick_phase2_test.py", 
            "organize_workspace.py",
            "mcp_status_check.py",
            "fix_mcp_dependencies.py",
            "debug_install_methods.py",
            "enhanced_test_diagnostics.py",
            "binary_detection_fix_summary.py",
            "validate_enhanced_server.py",
            "production_verification.py",
            "reorganize_workspace.py",
            "simple_reorganize.py"
        ]
        
        for dev_file in dev_files:
            src_file = self.root / dev_file
            if src_file.exists():
                dest_file = self.root / "dev" / dev_file
                if not dest_file.exists():
                    shutil.copy2(src_file, dest_file)
                    logger.info(f"Copied {dev_file} -> dev/")

    def move_config_files(self):
        """Move configuration files to config/ directory"""
        logger.info("Moving configuration files...")
        
        # Move VS Code config
        if (self.root / ".vscode").exists():
            vscode_dest = self.root / "config/vscode"
            if not vscode_dest.exists():
                shutil.copytree(self.root / ".vscode", vscode_dest)
                logger.info("Copied .vscode/ -> config/vscode/")

        # Copy important config files
        config_files = [
            "pyproject.toml",
            "requirements.txt", 
            "setup.cfg",
            "pytest.ini",
            "tox.ini"
        ]
        
        for config_file in config_files:
            src_file = self.root / config_file
            if src_file.exists():
                dest_file = self.root / "config" / config_file
                if not dest_file.exists():
                    shutil.copy2(src_file, dest_file)
                    logger.info(f"Copied {config_file} -> config/")

    def create_package_inits(self):
        """Create __init__.py files for the new package structure"""
        logger.info("Creating package __init__.py files...")
        
        init_files = {
            "src/__init__.py": "",
            "src/ipfs_kit/__init__.py": '''"""
IPFS Kit - Complete IPFS Integration for Python
===============================================

A comprehensive Python library for IPFS integration with MCP server support.
"""

__version__ = "2.2.0"
__author__ = "IPFS Kit Team"

from .core import *
from .tools import *
from .mcp import *
''',
            "src/ipfs_kit/core/__init__.py": '''"""
Core infrastructure components for IPFS Kit
"""

from .tool_registry import ToolRegistry, registry, tool, ToolCategory, ToolSchema
from .service_manager import ServiceManager, service_manager, ipfs_manager
from .error_handler import ErrorHandler, error_handler, create_success_response
from .test_framework import TestFramework, test_framework

__all__ = [
    'ToolRegistry', 'registry', 'tool', 'ToolCategory', 'ToolSchema',
    'ServiceManager', 'service_manager', 'ipfs_manager', 
    'ErrorHandler', 'error_handler', 'create_success_response',
    'TestFramework', 'test_framework'
]
''',
            "src/ipfs_kit/tools/__init__.py": '''"""
IPFS tools implementations
"""

# Import all IPFS tools when package is imported
try:
    from . import ipfs_core_tools
    from . import ipfs_core_tools_part2
    from . import unified_ipfs_tools
except ImportError:
    pass

__all__ = ['ipfs_core_tools', 'ipfs_core_tools_part2', 'unified_ipfs_tools']
''',
            "src/ipfs_kit/mcp/__init__.py": '''"""
MCP (Model Context Protocol) server implementations
"""

__all__ = ['enhanced_mcp_server_with_daemon_mgmt']
''',
            "src/ipfs_kit/utils/__init__.py": '''"""
Utility functions and helpers
"""

__all__ = []
''',
            "tests/__init__.py": "",
            "scripts/__init__.py": ""
        }
        
        for file_path, content in init_files.items():
            full_path = self.root / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            if not full_path.exists():
                full_path.write_text(content)
                logger.info(f"Created {file_path}")

    def update_import_paths(self):
        """Update import paths to match new structure"""
        logger.info("Updating import paths...")
        
        # Files that need import updates
        files_to_update = []
        
        # Find Python files that might need updates
        for pattern in ["scripts/*.py", "src/ipfs_kit/mcp/*.py", "tests/*.py", "tests/*/*.py", "dev/*.py"]:
            files_to_update.extend(glob.glob(str(self.root / pattern)))
        
        # Import path mappings
        import_updates = {
            r'from core\.': 'from src.ipfs_kit.core.',
            r'from tools\.': 'from src.ipfs_kit.tools.',
            r'from mcp\.': 'from src.ipfs_kit.mcp.',
            r'import core\.': 'import src.ipfs_kit.core.',
            r'import tools\.': 'import src.ipfs_kit.tools.',
            r'import mcp\.': 'import src.ipfs_kit.mcp.',
            r'sys\.path\.insert\(0, ["\']core["\']\)': 'sys.path.insert(0, "src/ipfs_kit")',
            r'sys\.path\.insert\(0, ["\']tools["\']\)': 'sys.path.insert(0, "src/ipfs_kit")',
            r'sys\.path\.insert\(0, ["\']mcp["\']\)': 'sys.path.insert(0, "src/ipfs_kit")',
        }
        
        for file_path in files_to_update:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                updated = False
                for old_pattern, new_replacement in import_updates.items():
                    new_content = re.sub(old_pattern, new_replacement, content)
                    if new_content != content:
                        content = new_content
                        updated = True
                
                if updated:
                    with open(file_path, 'w') as f:
                        f.write(content)
                    logger.info(f"Updated imports in {Path(file_path).relative_to(self.root)}")
                    
            except Exception as e:
                logger.warning(f"Could not update imports in {file_path}: {e}")

    def update_mcp_config(self):
        """Update MCP configuration to point to new server location"""
        logger.info("Updating MCP configuration...")
        
        mcp_config_path = self.root / "config/vscode/mcp.json"
        if mcp_config_path.exists():
            try:
                content = mcp_config_path.read_text()
                
                # Update the server path
                old_path = "/home/barberb/ipfs_kit_py/mcp/enhanced_mcp_server_with_daemon_mgmt.py"
                new_path = "/home/barberb/ipfs_kit_py/src/ipfs_kit/mcp/enhanced_mcp_server_with_daemon_mgmt.py"
                
                updated_content = content.replace(old_path, new_path)
                
                if updated_content != content:
                    mcp_config_path.write_text(updated_content)
                    logger.info("Updated MCP server path in config")
                    
                    # Also update the original .vscode location
                    original_config = self.root / ".vscode/mcp.json"
                    if original_config.exists():
                        original_config.write_text(updated_content)
                        logger.info("Updated original .vscode/mcp.json")
                        
            except Exception as e:
                logger.warning(f"Could not update MCP config: {e}")

    def create_main_script(self):
        """Create a main entry point script"""
        logger.info("Creating main entry point...")
        
        main_script = self.root / "main.py"
        main_content = '''#!/usr/bin/env python3
"""
IPFS Kit - Main Entry Point
============================

Quick access to common IPFS Kit functionality.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Main entry point with command menu"""
    print("\\n🚀 IPFS Kit - Complete IPFS Integration")
    print("=" * 40)
    print("1. Start MCP Server")
    print("2. Run Tests")
    print("3. Check IPFS Status")
    print("4. Initialize Environment")
    print("5. Exit")
    
    choice = input("\\nSelect option (1-5): ").strip()
    
    if choice == "1":
        print("\\n🔧 Starting MCP Server...")
        from src.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import main as mcp_main
        mcp_main()
    elif choice == "2":
        print("\\n🧪 Running Tests...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pytest", "tests/"], cwd=Path(__file__).parent)
    elif choice == "3":
        print("\\n📊 Checking IPFS Status...")
        from src.ipfs_kit.core.service_manager import service_manager
        status = service_manager.get_service_status("ipfs")
        print(f"IPFS Status: {status}")
    elif choice == "4":
        print("\\n⚙️ Initializing Environment...")
        import subprocess
        subprocess.run([sys.executable, "scripts/initialize_phase2.py"], cwd=Path(__file__).parent)
    elif choice == "5":
        print("\\n👋 Goodbye!")
        return
    else:
        print("\\n❌ Invalid choice. Please try again.")
        main()

if __name__ == "__main__":
    main()
'''
        
        if not main_script.exists():
            main_script.write_text(main_content)
            main_script.chmod(0o755)
            logger.info("Created main.py entry point")

    def reorganize(self):
        """Execute the complete reorganization"""
        logger.info("🚀 Starting complete workspace reorganization...")
        
        try:
            self.create_backup()
            self.ensure_directory_structure()
            self.move_core_infrastructure()
            self.move_test_files()
            self.move_scripts()
            self.move_dev_files()
            self.move_config_files()
            self.create_package_inits()
            self.update_import_paths()
            self.update_mcp_config()
            self.create_main_script()
            
            logger.info("✅ Complete workspace reorganization finished!")
            logger.info("📁 New structure:")
            logger.info("  src/ipfs_kit/     - Main package")
            logger.info("  tests/            - All tests")
            logger.info("  scripts/          - Setup and utility scripts")
            logger.info("  config/           - Configuration files")
            logger.info("  dev/              - Development tools")
            logger.info("  main.py           - Entry point script")
            
        except Exception as e:
            logger.error(f"❌ Reorganization failed: {e}")
            raise

def main():
    """Main function"""
    root_path = Path(__file__).parent
    reorganizer = CompleteWorkspaceReorganizer(root_path)
    reorganizer.reorganize()

if __name__ == "__main__":
    main()
