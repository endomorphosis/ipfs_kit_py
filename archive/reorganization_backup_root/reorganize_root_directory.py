#!/usr/bin/env python3
"""
IPFS Kit Root Directory Reorganization Tool

This script implements the reorganization recommendations from the analysis.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List
import json

class RootDirectoryReorganizer:
    """Reorganize the root directory based on analysis recommendations"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.backup_path = self.root_path / "reorganization_backup_root"
        
        # Files to keep in root directory
        self.keep_in_root = {
            'README.md', 'README_ENHANCED.md', 'CHANGELOG.md', 'LICENSE',
            'pyproject.toml', 'setup.py', 'requirements.txt', 'requirements_enhanced.txt',
            'main.py', 'ipfs_kit_cli.py', 'ipfs-kit', 'ipfs-kit.py',
            'Makefile', 'package.json', 'package-lock.json',
            # Keep a few key documentation files
            'CLI_OVERVIEW.md', 'POLICY_SYSTEM_DOCUMENTATION.md', 'DOCUMENTATION.md',
            'PROJECT_STRUCTURE.md', 'DEPLOYMENT_GUIDE.md', 'QUICK_REFERENCE.md'
        }
        
        # Directory structure to create
        self.target_structure = {
            'docs/': 'Documentation files',
            'docs/implementation/': 'Implementation documentation',
            'docs/guides/': 'User guides',
            'docs/summaries/': 'Summary documents',
            'docs/test_reports/': 'Test result reports',
            'examples/': 'Demo and example scripts',
            'examples/demos/': 'Demonstration scripts',
            'examples/integration/': 'Integration examples',
            'tests/': 'Test files',
            'tests/unit/': 'Unit tests',
            'tests/integration/': 'Integration tests',
            'tests/performance/': 'Performance tests',
            'tests/comprehensive/': 'Comprehensive test suites',
            'tools/': 'Utility and maintenance scripts',
            'tools/analysis/': 'Analysis tools',
            'tools/debugging/': 'Debugging tools',
            'tools/setup/': 'Setup and installation tools',
            'tools/maintenance/': 'Maintenance utilities',
            'cli/': 'CLI tool variants',
            'data/': 'Data and configuration files',
            'data/configs/': 'Configuration files',
            'data/results/': 'Test and analysis results',
            'data/samples/': 'Sample data files',
            'deprecated/': 'Deprecated files for reference',
            'logs/': 'Log files'
        }
        
    def create_backup(self):
        """Create backup of current state"""
        print("📦 Creating backup of current root directory...")
        
        if self.backup_path.exists():
            shutil.rmtree(self.backup_path)
        
        self.backup_path.mkdir(exist_ok=True)
        
        # Copy all files to backup
        root_files = [f for f in self.root_path.iterdir() 
                     if f.is_file() and not f.name.startswith('.')]
        
        for file_path in root_files:
            shutil.copy2(file_path, self.backup_path / file_path.name)
        
        print(f"✅ Backed up {len(root_files)} files to {self.backup_path}")
        
    def create_directory_structure(self):
        """Create the target directory structure"""
        print("📁 Creating directory structure...")
        
        for dir_path, description in self.target_structure.items():
            full_path = self.root_path / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            
            # Create README in each directory
            readme_path = full_path / "README.md"
            if not readme_path.exists():
                readme_content = f"# {dir_path.rstrip('/')}\n\n{description}\n"
                readme_path.write_text(readme_content)
        
        print(f"✅ Created {len(self.target_structure)} directories")
        
    def reorganize_files(self):
        """Move files to their appropriate locations"""
        print("📄 Reorganizing files...")
        
        moved_count = 0
        deleted_count = 0
        
        # Get all files in root
        root_files = [f for f in self.root_path.iterdir() 
                     if f.is_file() and not f.name.startswith('.')]
        
        for file_path in root_files:
            filename = file_path.name
            
            # Skip files to keep in root
            if filename in self.keep_in_root:
                continue
                
            # Skip the backup directory and our own scripts
            if filename in ['analyze_root_organization.py', 'reorganize_root_directory.py']:
                continue
            
            # Delete empty files and obvious artifacts
            if self._should_delete(file_path):
                file_path.unlink()
                deleted_count += 1
                print(f"🗑️  Deleted: {filename}")
                continue
            
            # Move file to appropriate location
            target_dir = self._get_target_directory(filename, file_path)
            if target_dir:
                target_path = self.root_path / target_dir / filename
                
                # Handle naming conflicts
                if target_path.exists():
                    base_name = target_path.stem
                    extension = target_path.suffix
                    counter = 1
                    while target_path.exists():
                        target_path = target_path.parent / f"{base_name}_{counter}{extension}"
                        counter += 1
                
                shutil.move(str(file_path), str(target_path))
                moved_count += 1
                print(f"📄 Moved: {filename} → {target_dir}")
        
        print(f"✅ Moved {moved_count} files, deleted {deleted_count} files")
        
    def _should_delete(self, file_path: Path) -> bool:
        """Check if file should be deleted"""
        filename = file_path.name
        
        # Delete empty files
        if file_path.stat().st_size == 0:
            return True
        
        # Delete obvious build artifacts
        if filename.startswith('=') or filename.endswith('.pyc'):
            return True
        
        # Delete some deprecated files
        deprecated_files = {
            'simple_mcp_server.py',
            'simple_ipfs_car.py', 
            'simple_vfs_demo.py',
            'standalone_jit.py',
            'standalone_program_state.py'
        }
        
        return filename in deprecated_files
        
    def _get_target_directory(self, filename: str, file_path: Path) -> str:
        """Get the target directory for a file"""
        
        # Documentation files
        if filename.endswith('.md') and filename not in self.keep_in_root:
            if 'COMPLETE' in filename or 'IMPLEMENTATION' in filename:
                return 'docs/implementation'
            elif 'GUIDE' in filename:
                return 'docs/guides'
            elif 'SUMMARY' in filename:
                return 'docs/summaries'
            elif 'TEST' in filename and 'RESULTS' in filename:
                return 'docs/test_reports'
            else:
                return 'docs'
        
        # Demo files
        if filename.startswith('demo_'):
            if 'integration' in filename:
                return 'examples/integration'
            else:
                return 'examples/demos'
        
        # Complete integration demos
        if 'integration_demo' in filename:
            return 'examples/integration'
        
        # Show/display utilities
        if filename.startswith('show_') or filename.startswith('comprehensive_'):
            return 'examples'
        
        # Test files
        if filename.startswith('test_'):
            if 'integration' in filename or 'comprehensive' in filename:
                return 'tests/integration'
            elif 'performance' in filename or 'multi_processing' in filename:
                return 'tests/performance'
            elif 'comprehensive' in filename:
                return 'tests/comprehensive'
            else:
                return 'tests/unit'
        
        # CLI tools (except main one)
        if filename.endswith('_cli.py') and filename != 'ipfs_kit_cli.py':
            return 'cli'
        
        # CLI variants
        if filename.startswith('ipfs_kit_cli_') and filename.endswith('.py'):
            return 'cli'
        
        # Utility scripts
        if any(filename.startswith(prefix) for prefix in [
            'analyze_', 'check_', 'clean_', 'create_', 'debug_', 
            'fix_', 'setup_', 'verify_', 'install_', 'migrate_',
            'deprecate_', 'trace_'
        ]):
            if filename.startswith('analyze_') or filename.startswith('trace_'):
                return 'tools/analysis'
            elif filename.startswith('debug_'):
                return 'tools/debugging'
            elif filename.startswith('setup_') or filename.startswith('install_'):
                return 'tools/setup'
            else:
                return 'tools/maintenance'
        
        # Data files
        if filename.endswith(('.json', '.yaml', '.yml')):
            if 'config' in filename:
                return 'data/configs'
            elif 'result' in filename or 'report' in filename:
                return 'data/results'
            else:
                return 'data/samples'
        
        # Log files
        if filename.endswith('.log'):
            return 'logs'
        
        # Image files
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            return 'docs'  # Images likely for documentation
        
        # Archive files
        if filename.endswith(('.tar.gz', '.zip')):
            return 'deprecated'
        
        # Enhanced/multiprocessing files
        if filename.startswith('enhanced_') and filename.endswith('.py'):
            if 'mcp' in filename:
                return 'examples'
            elif 'cli' in filename:
                return 'cli'
            else:
                return 'tools'
        
        # Server files
        if 'server' in filename and filename.endswith('.py'):
            return 'examples'
        
        # Dashboard files
        if 'dashboard' in filename:
            return 'examples'
        
        # Default for Python files
        if filename.endswith('.py'):
            return 'tools'
        
        return None
    
    def create_organization_summary(self):
        """Create a summary of the reorganization"""
        summary = {
            'timestamp': str(Path().cwd()),
            'root_files_remaining': [],
            'directories_created': list(self.target_structure.keys()),
            'organization_rules': {
                'keep_in_root': list(self.keep_in_root),
                'directory_purposes': self.target_structure
            }
        }
        
        # List remaining root files
        root_files = [f.name for f in self.root_path.iterdir() 
                     if f.is_file() and not f.name.startswith('.')]
        summary['root_files_remaining'] = sorted(root_files)
        
        # Save summary
        summary_path = self.root_path / 'REORGANIZATION_SUMMARY.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📊 Created reorganization summary: {summary_path}")
        
    def create_root_readme_update(self):
        """Update the root README with the new organization"""
        readme_addition = """

## Repository Organization

This repository has been organized into a clear directory structure:

### Root Directory
Contains only essential project files:
- `README.md` - Main project documentation
- `pyproject.toml` / `setup.py` - Python package configuration
- `requirements.txt` - Python dependencies
- `main.py` - Main entry point
- `ipfs_kit_cli.py` - Primary CLI tool
- Key documentation files

### Directory Structure
- `docs/` - All documentation (guides, implementation docs, summaries)
- `examples/` - Demo scripts and integration examples
- `tests/` - Comprehensive test suite (unit, integration, performance)
- `tools/` - Utility scripts and maintenance tools
- `cli/` - Alternative CLI implementations
- `data/` - Configuration files, sample data, and results
- `logs/` - Log files
- `deprecated/` - Archived files for reference

### Finding Files
- **Documentation**: Check `docs/` and its subdirectories
- **Examples**: Look in `examples/demos/` or `examples/integration/`
- **Tests**: All test files are in `tests/` with appropriate subdirectories
- **Utilities**: Maintenance and analysis tools are in `tools/`

"""
        
        readme_path = self.root_path / 'README.md'
        if readme_path.exists():
            content = readme_path.read_text()
            if 'Repository Organization' not in content:
                content += readme_addition
                readme_path.write_text(content)
                print("📝 Updated README.md with organization information")
    
    def reorganize(self):
        """Execute the full reorganization"""
        print("🚀 Starting Root Directory Reorganization")
        print("=" * 60)
        
        self.create_backup()
        self.create_directory_structure()
        self.reorganize_files()
        self.create_organization_summary()
        self.create_root_readme_update()
        
        print("\n✅ REORGANIZATION COMPLETE!")
        print("=" * 60)
        print("📁 Root directory is now organized with:")
        print(f"   • {len(self.keep_in_root)} essential files in root")  
        print(f"   • {len(self.target_structure)} organized directories")
        print(f"   • Backup available in: {self.backup_path}")
        print("\n📖 Next steps:")
        print("   1. Review the organized structure")
        print("   2. Test that imports and scripts still work")
        print("   3. Update any hard-coded paths if needed")
        print("   4. Commit the organized structure")

def main():
    """Main execution function"""
    reorganizer = RootDirectoryReorganizer("/home/devel/ipfs_kit_py")
    
    # Confirm before proceeding
    print("⚠️  This will reorganize the root directory by moving files to subdirectories.")
    print("A backup will be created before any changes are made.")
    response = input("Continue? (y/N): ")
    
    if response.lower() in ['y', 'yes']:
        reorganizer.reorganize()
    else:
        print("❌ Reorganization cancelled")

if __name__ == "__main__":
    main()
