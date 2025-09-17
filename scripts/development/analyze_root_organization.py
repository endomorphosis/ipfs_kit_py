#!/usr/bin/env python3
"""
IPFS Kit Root Directory Organization Analysis

This script analyzes all files in the root directory and provides
recommendations for better organization.
"""

import os
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple
from datetime import datetime

class RootDirectoryAnalyzer:
    """Analyze and categorize files in the root directory"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.analysis = {
            'core_files': [],           # Essential project files
            'documentation': [],        # Documentation and guides  
            'demos': [],               # Demo and example scripts
            'tests': [],               # Test files
            'cli_tools': [],           # CLI-related files
            'utilities': [],           # Utility scripts
            'data_files': [],          # Data/config files
            'deprecated': [],          # Deprecated/old files
            'build_artifacts': [],     # Build outputs
            'logs': [],                # Log files
            'empty_files': [],         # Empty files
            'unknown': []              # Unclassified files
        }
        
    def analyze(self) -> Dict:
        """Perform comprehensive analysis of root directory"""
        print("🔍 Analyzing Root Directory Organization")
        print("=" * 60)
        
        # Get all files in root directory (not subdirectories)
        root_files = [f for f in self.root_path.iterdir() 
                     if f.is_file() and not f.name.startswith('.')]
        
        print(f"Found {len(root_files)} files in root directory")
        print()
        
        # Analyze each file
        for file_path in root_files:
            self._categorize_file(file_path)
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        
        return {
            'analysis': self.analysis,
            'recommendations': recommendations,
            'file_count': len(root_files)
        }
    
    def _categorize_file(self, file_path: Path):
        """Categorize a single file"""
        filename = file_path.name
        file_size = file_path.stat().st_size
        
        # Check if file is empty
        if file_size == 0:
            self.analysis['empty_files'].append({
                'name': filename,
                'path': str(file_path),
                'reason': 'Empty file'
            })
            return
        
        # Core project files
        if self._is_core_file(filename):
            self.analysis['core_files'].append({
                'name': filename,
                'path': str(file_path),
                'type': self._get_core_file_type(filename)
            })
        
        # Documentation files
        elif self._is_documentation(filename, file_path):
            doc_type = self._get_documentation_type(filename)
            self.analysis['documentation'].append({
                'name': filename,
                'path': str(file_path),
                'type': doc_type,
                'size': file_size
            })
        
        # Demo files
        elif self._is_demo_file(filename):
            self.analysis['demos'].append({
                'name': filename,
                'path': str(file_path),
                'type': self._get_demo_type(filename)
            })
        
        # Test files
        elif self._is_test_file(filename):
            self.analysis['tests'].append({
                'name': filename,
                'path': str(file_path),
                'type': self._get_test_type(filename)
            })
        
        # CLI tools
        elif self._is_cli_tool(filename):
            self.analysis['cli_tools'].append({
                'name': filename,
                'path': str(file_path),
                'purpose': self._get_cli_purpose(filename)
            })
        
        # Utility scripts
        elif self._is_utility_script(filename):
            self.analysis['utilities'].append({
                'name': filename,
                'path': str(file_path),
                'purpose': self._get_utility_purpose(filename)
            })
        
        # Data files
        elif self._is_data_file(filename):
            self.analysis['data_files'].append({
                'name': filename,
                'path': str(file_path),
                'type': self._get_data_type(filename),
                'size': file_size
            })
        
        # Build artifacts
        elif self._is_build_artifact(filename):
            self.analysis['build_artifacts'].append({
                'name': filename,
                'path': str(file_path),
                'type': self._get_artifact_type(filename)
            })
        
        # Log files
        elif self._is_log_file(filename):
            self.analysis['logs'].append({
                'name': filename,
                'path': str(file_path),
                'size': file_size
            })
        
        # Deprecated files
        elif self._is_deprecated(filename, file_path):
            self.analysis['deprecated'].append({
                'name': filename,
                'path': str(file_path),
                'reason': self._get_deprecation_reason(filename)
            })
        
        # Unknown files
        else:
            self.analysis['unknown'].append({
                'name': filename,
                'path': str(file_path),
                'size': file_size
            })
    
    def _is_core_file(self, filename: str) -> bool:
        """Check if file is a core project file"""
        core_files = {
            'setup.py', 'pyproject.toml', 'requirements.txt', 'requirements_enhanced.txt',
            'LICENSE', 'README.md', 'README_ENHANCED.md', 'CHANGELOG.md',
            'Makefile', 'package.json', 'package-lock.json',
            'main.py', 'ipfs-kit', 'ipfs-kit.py'
        }
        return filename in core_files
    
    def _get_core_file_type(self, filename: str) -> str:
        """Get the type of core file"""
        if filename in ['setup.py', 'pyproject.toml']:
            return 'build_config'
        elif filename.startswith('requirements'):
            return 'dependencies'
        elif filename in ['README.md', 'README_ENHANCED.md', 'CHANGELOG.md']:
            return 'documentation'
        elif filename in ['LICENSE']:
            return 'legal'
        elif filename in ['main.py', 'ipfs-kit', 'ipfs-kit.py']:
            return 'entrypoint'
        elif filename in ['Makefile', 'package.json', 'package-lock.json']:
            return 'build_tool'
        return 'unknown'
    
    def _is_documentation(self, filename: str, file_path: Path) -> bool:
        """Check if file is documentation"""
        # Documentation patterns
        doc_patterns = [
            r'^[A-Z_]+\.md$',  # All caps MD files
            r'.*_GUIDE\.md$',   # Guide files
            r'.*_SUMMARY\.md$', # Summary files
            r'.*_COMPLETE\.md$', # Complete implementation docs
            r'DOCUMENTATION\.md$',
            r'DEPLOYMENT_GUIDE\.md$',
            r'PROJECT_STRUCTURE\.md$',
            r'QUICK_REFERENCE\.md$'
        ]
        
        for pattern in doc_patterns:
            if re.match(pattern, filename):
                return True
        
        # Check if it's a markdown file with substantial content
        if filename.endswith('.md') and file_path.stat().st_size > 1000:
            return True
            
        return False
    
    def _get_documentation_type(self, filename: str) -> str:
        """Get the type of documentation"""
        if 'GUIDE' in filename:
            return 'guide'
        elif 'SUMMARY' in filename:
            return 'summary'
        elif 'COMPLETE' in filename:
            return 'implementation_doc'
        elif 'TEST' in filename and 'RESULTS' in filename:
            return 'test_report'
        elif filename in ['DOCUMENTATION.md', 'PROJECT_STRUCTURE.md']:
            return 'main_doc'
        elif 'DEPLOYMENT' in filename:
            return 'deployment'
        else:
            return 'general'
    
    def _is_demo_file(self, filename: str) -> bool:
        """Check if file is a demo script"""
        demo_patterns = [
            r'^demo_.*\.py$',
            r'^complete_integration_demo\.py$',
            r'^comprehensive_.*_demo\.py$',
            r'^show_.*\.py$'
        ]
        
        for pattern in demo_patterns:
            if re.match(pattern, filename):
                return True
        return False
    
    def _get_demo_type(self, filename: str) -> str:
        """Get the type of demo"""
        if 'arrow' in filename or 'parquet' in filename:
            return 'data_processing'
        elif 'bucket' in filename or 'vfs' in filename:
            return 'filesystem'
        elif 'cluster' in filename:
            return 'cluster'
        elif 'dashboard' in filename:
            return 'dashboard'
        elif 'mcp' in filename:
            return 'mcp_server'
        elif 'integration' in filename:
            return 'integration'
        else:
            return 'general'
    
    def _is_test_file(self, filename: str) -> bool:
        """Check if file is a test file"""
        test_patterns = [
            r'^test_.*\.py$',
            r'^.*_test\.py$',
            r'^run_.*_test.*\.py$',
            r'^quick_.*_test\.py$',
            r'^minimal_.*_test\.py$'
        ]
        
        for pattern in test_patterns:
            if re.match(pattern, filename):
                return True
        return False
    
    def _get_test_type(self, filename: str) -> str:
        """Get the type of test"""
        if 'integration' in filename:
            return 'integration'
        elif 'comprehensive' in filename:
            return 'comprehensive'
        elif 'daemon' in filename:
            return 'daemon'
        elif 'cluster' in filename:
            return 'cluster'
        elif 'mcp' in filename:
            return 'mcp_server'
        elif 'performance' in filename or 'multi_processing' in filename:
            return 'performance'
        elif 'quick' in filename or 'minimal' in filename:
            return 'quick'
        else:
            return 'unit'
    
    def _is_cli_tool(self, filename: str) -> bool:
        """Check if file is a CLI tool"""
        cli_patterns = [
            r'^.*_cli\.py$',
            r'^bucket_cli\.py$',
            r'^ipfs_kit_cli.*\.py$',
            r'^enhanced_.*_cli\.py$'
        ]
        
        for pattern in cli_patterns:
            if re.match(pattern, filename):
                return True
        return False
    
    def _get_cli_purpose(self, filename: str) -> str:
        """Get the purpose of CLI tool"""
        if 'bucket' in filename:
            return 'bucket_management'
        elif 'wal' in filename:
            return 'wal_operations'
        elif 'fs_journal' in filename:
            return 'filesystem_journal'
        elif 'multiprocessing' in filename:
            return 'multiprocessing'
        elif 'enhanced' in filename:
            return 'enhanced_features'
        else:
            return 'general_cli'
    
    def _is_utility_script(self, filename: str) -> bool:
        """Check if file is a utility script"""
        utility_patterns = [
            r'^analyze_.*\.py$',
            r'^check_.*\.py$',
            r'^clean_.*\.py$',
            r'^create_.*\.py$',
            r'^debug_.*\.py$',
            r'^fix_.*\.py$',
            r'^setup_.*\.py$',
            r'^verify_.*\.py$',
            r'^trace_.*\.py$',
            r'^install_.*\.py$',
            r'^migrate_.*\.py$',
            r'^deprecate_.*\.py$'
        ]
        
        for pattern in utility_patterns:
            if re.match(pattern, filename):
                return True
        return False
    
    def _get_utility_purpose(self, filename: str) -> str:
        """Get the purpose of utility script"""
        if filename.startswith('analyze_'):
            return 'analysis'
        elif filename.startswith('check_'):
            return 'validation'
        elif filename.startswith('clean_'):
            return 'cleanup'
        elif filename.startswith('create_'):
            return 'generation'
        elif filename.startswith('debug_'):
            return 'debugging'
        elif filename.startswith('fix_'):
            return 'fixing'
        elif filename.startswith('setup_'):
            return 'setup'
        elif filename.startswith('verify_'):
            return 'verification'
        elif filename.startswith('install_'):
            return 'installation'
        elif filename.startswith('migrate_'):
            return 'migration'
        else:
            return 'general_utility'
    
    def _is_data_file(self, filename: str) -> bool:
        """Check if file is a data file"""
        data_extensions = {'.json', '.csv', '.parquet', '.yaml', '.yml', '.log', '.png'}
        return any(filename.endswith(ext) for ext in data_extensions)
    
    def _get_data_type(self, filename: str) -> str:
        """Get the type of data file"""
        if filename.endswith('.json'):
            return 'json_data'
        elif filename.endswith('.csv'):
            return 'csv_data'
        elif filename.endswith('.parquet'):
            return 'parquet_data'
        elif filename.endswith(('.yaml', '.yml')):
            return 'yaml_config'
        elif filename.endswith('.log'):
            return 'log_file'
        elif filename.endswith('.png'):
            return 'image'
        else:
            return 'unknown_data'
    
    def _is_build_artifact(self, filename: str) -> bool:
        """Check if file is a build artifact"""
        artifacts = {
            'ipfs_kit_config_backup_20250728_212506.tar.gz'
        }
        return filename in artifacts or filename.startswith('=')
    
    def _get_artifact_type(self, filename: str) -> str:
        """Get the type of build artifact"""
        if filename.endswith('.tar.gz'):
            return 'backup_archive'
        elif filename.startswith('='):
            return 'pip_output'
        else:
            return 'unknown_artifact'
    
    def _is_log_file(self, filename: str) -> bool:
        """Check if file is a log file"""
        return filename.endswith('.log')
    
    def _is_deprecated(self, filename: str, file_path: Path) -> bool:
        """Check if file is deprecated"""
        deprecated_patterns = [
            r'^.*_old\.py$',
            r'^.*_backup\.py$',
            r'^.*_deprecated\.py$',
            r'^simple_.*\.py$',  # Many simple_ files seem to be older versions
            r'^standalone_.*\.py$',  # Some standalone files might be deprecated
            r'^ipfs_kit_cli_.*\.py$'  # Multiple CLI versions suggest older ones are deprecated
        ]
        
        for pattern in deprecated_patterns:
            if re.match(pattern, filename):
                return True
        
        # Check for multiple versions of similar files
        base_name = filename.replace('_enhanced', '').replace('_optimized', '').replace('_fixed', '').replace('_super_fast', '').replace('_ultra_fast', '').replace('_jit_optimized', '')
        
        if 'ipfs_kit_cli' in filename and filename != 'ipfs_kit_cli.py':
            return True
            
        return False
    
    def _get_deprecation_reason(self, filename: str) -> str:
        """Get the reason for deprecation"""
        if 'old' in filename:
            return 'explicitly_marked_old'
        elif 'backup' in filename:
            return 'backup_version'
        elif 'deprecated' in filename:
            return 'explicitly_deprecated'
        elif 'simple' in filename:
            return 'simplified_version'
        elif any(suffix in filename for suffix in ['_enhanced', '_optimized', '_fixed', '_fast']):
            return 'superseded_by_newer_version'
        else:
            return 'potentially_obsolete'
    
    def _generate_recommendations(self) -> Dict:
        """Generate organization recommendations"""
        recommendations = {
            'move_to_folders': {},
            'delete_candidates': [],
            'consolidate': [],
            'prioritize': []
        }
        
        # Recommend moving files to appropriate folders
        if self.analysis['documentation']:
            recommendations['move_to_folders']['docs/'] = [
                f['name'] for f in self.analysis['documentation'] 
                if not f['name'] in ['README.md', 'README_ENHANCED.md', 'CHANGELOG.md']
            ]
        
        if self.analysis['demos']:
            recommendations['move_to_folders']['examples/'] = [
                f['name'] for f in self.analysis['demos']
            ]
        
        if self.analysis['tests']:
            recommendations['move_to_folders']['tests/'] = [
                f['name'] for f in self.analysis['tests']
            ]
        
        if self.analysis['utilities']:
            recommendations['move_to_folders']['tools/'] = [
                f['name'] for f in self.analysis['utilities']
            ]
        
        if self.analysis['cli_tools']:
            recommendations['move_to_folders']['cli/'] = [
                f['name'] for f in self.analysis['cli_tools']
                if f['name'] != 'ipfs_kit_cli.py'  # Keep main CLI in root
            ]
        
        if self.analysis['data_files']:
            recommendations['move_to_folders']['data/'] = [
                f['name'] for f in self.analysis['data_files']
                if not f['name'].endswith('.png')  # Images might stay in root for README
            ]
        
        # Recommend files for deletion
        recommendations['delete_candidates'] = (
            [f['name'] for f in self.analysis['empty_files']] +
            [f['name'] for f in self.analysis['deprecated']] +
            [f['name'] for f in self.analysis['build_artifacts'] if f['name'].startswith('=')]
        )
        
        # Recommend consolidation
        cli_files = [f['name'] for f in self.analysis['cli_tools']]
        if len(cli_files) > 1:
            recommendations['consolidate'].append({
                'type': 'cli_tools',
                'files': cli_files,
                'suggestion': 'Consolidate into single enhanced CLI'
            })
        
        # Prioritize important files to keep in root
        recommendations['prioritize'] = [
            'README.md',
            'pyproject.toml',
            'setup.py', 
            'requirements.txt',
            'main.py',
            'ipfs_kit_cli.py',
            'LICENSE',
            'CHANGELOG.md'
        ]
        
        return recommendations
    
    def print_analysis(self, analysis_result: Dict):
        """Print the analysis results"""
        analysis = analysis_result['analysis']
        recommendations = analysis_result['recommendations']
        
        print("\n📊 ANALYSIS RESULTS")
        print("=" * 60)
        
        # Print categories
        for category, files in analysis.items():
            if files:
                print(f"\n{category.upper().replace('_', ' ')} ({len(files)} files):")
                for file_info in files[:5]:  # Show first 5
                    name = file_info['name']
                    if len(name) > 50:
                        name = name[:47] + "..."
                    print(f"  • {name}")
                if len(files) > 5:
                    print(f"  ... and {len(files) - 5} more")
        
        print(f"\n📈 SUMMARY")
        print(f"Total files analyzed: {analysis_result['file_count']}")
        print(f"Categories with files: {len([k for k, v in analysis.items() if v])}")
        
        print(f"\n🎯 RECOMMENDATIONS")
        print("=" * 60)
        
        # Move recommendations
        if recommendations['move_to_folders']:
            print("\n📁 MOVE TO FOLDERS:")
            for folder, files in recommendations['move_to_folders'].items():
                if files:
                    print(f"  {folder} ({len(files)} files)")
                    for file in files[:3]:
                        print(f"    • {file}")
                    if len(files) > 3:
                        print(f"    ... and {len(files) - 3} more")
        
        # Delete recommendations  
        if recommendations['delete_candidates']:
            print(f"\n🗑️  DELETE CANDIDATES ({len(recommendations['delete_candidates'])} files):")
            for file in recommendations['delete_candidates'][:10]:
                print(f"  • {file}")
            if len(recommendations['delete_candidates']) > 10:
                print(f"  ... and {len(recommendations['delete_candidates']) - 10} more")
        
        # Consolidation recommendations
        if recommendations['consolidate']:
            print(f"\n🔄 CONSOLIDATION OPPORTUNITIES:")
            for item in recommendations['consolidate']:
                print(f"  • {item['type']}: {item['suggestion']}")
                print(f"    Files: {', '.join(item['files'][:3])}")
        
        # Priority files
        print(f"\n⭐ KEEP IN ROOT (Priority files):")
        for file in recommendations['prioritize']:
            if any(f['name'] == file for category_files in analysis.values() for f in category_files):
                print(f"  • {file}")

def main():
    """Main function"""
    analyzer = RootDirectoryAnalyzer("/home/devel/ipfs_kit_py")
    result = analyzer.analyze()
    analyzer.print_analysis(result)
    
    print(f"\n💡 NEXT STEPS:")
    print("1. Review the recommendations above")
    print("2. Create the suggested folder structure")
    print("3. Move files to appropriate locations")
    print("4. Delete deprecated and empty files")
    print("5. Update import statements as needed")
    print("6. Test that everything still works")

if __name__ == "__main__":
    main()
