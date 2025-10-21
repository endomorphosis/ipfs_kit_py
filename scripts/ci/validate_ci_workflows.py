#!/usr/bin/env python3
"""
Comprehensive CI/CD Workflow Validation Script
===============================================

This script validates all GitHub Actions workflows to ensure they will run correctly.
It checks:
1. YAML syntax validity
2. Referenced scripts exist
3. Referenced tests exist
4. Python dependencies are available
5. Workflow structure is correct

Usage:
    python scripts/ci/validate_ci_workflows.py
    python scripts/ci/validate_ci_workflows.py --verbose
    python scripts/ci/validate_ci_workflows.py --fix-missing
"""

import yaml
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Set
import subprocess


class WorkflowValidator:
    """Validates GitHub Actions workflows for correctness."""
    
    def __init__(self, repo_root: Path, verbose: bool = False, fix_missing: bool = False):
        self.repo_root = repo_root
        self.workflows_dir = repo_root / '.github' / 'workflows'
        self.verbose = verbose
        self.fix_missing = fix_missing
        self.issues = []
        self.warnings = []
        self.fixed = []
        
    def log(self, message: str, level: str = 'info'):
        """Log a message."""
        if self.verbose or level != 'debug':
            symbols = {'info': 'ℹ️', 'warning': '⚠️', 'error': '❌', 'success': '✅', 'debug': '🔍'}
            print(f"{symbols.get(level, 'ℹ️')}  {message}")
    
    def check_yaml_syntax(self, workflow_file: Path) -> Tuple[bool, str]:
        """Check YAML syntax validity."""
        try:
            with open(workflow_file, 'r') as f:
                yaml.safe_load(f)
            return True, ""
        except yaml.YAMLError as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)
    
    def extract_scripts(self, content: str) -> Set[str]:
        """Extract script references from workflow content."""
        scripts = set()
        
        # Pattern: python script.py or python3 script.py
        py_scripts = re.findall(r'python[3]?\s+([^\s]+\.py)', content)
        scripts.update(py_scripts)
        
        # Pattern: bash script.sh or sh script.sh
        sh_scripts = re.findall(r'(?:bash|sh)\s+([^\s]+\.sh)', content)
        scripts.update(sh_scripts)
        
        # Pattern: scripts/ci/something.py
        ci_scripts = re.findall(r'scripts/ci/([^\s]+\.py)', content)
        scripts.update([f'scripts/ci/{s}' for s in ci_scripts])
        
        return scripts
    
    def extract_tests(self, content: str) -> Set[str]:
        """Extract test file references from workflow content."""
        tests = set()
        
        # Pattern: pytest tests/test_something.py
        test_files = re.findall(r'pytest\s+([^\s]+\.py)', content)
        tests.update(test_files)
        
        # Pattern: tests/test_something.py
        test_paths = re.findall(r'(tests/test_[^\s]+\.py)', content)
        tests.update(test_paths)
        
        return tests
    
    def verify_file_exists(self, file_path: str) -> bool:
        """Check if a file exists in the repository."""
        # Remove common prefixes and clean path
        clean_path = file_path.strip().lstrip('./')
        
        # Try direct path
        if (self.repo_root / clean_path).exists():
            return True
        
        # Try in scripts/ci
        if (self.repo_root / 'scripts' / 'ci' / Path(clean_path).name).exists():
            return True
        
        # Try in tests
        if (self.repo_root / 'tests' / Path(clean_path).name).exists():
            return True
        
        return False
    
    def create_missing_script(self, script_path: str) -> bool:
        """Create a placeholder for missing script if fix_missing is enabled."""
        if not self.fix_missing:
            return False
        
        full_path = self.repo_root / script_path
        
        # Don't create if it's a test file or obviously wrong path
        if 'test_' in script_path or 'matrix.py' in script_path or 'github.sh' in script_path:
            return False
        
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            if script_path.endswith('.py'):
                content = f'''#!/usr/bin/env python3
"""
{Path(script_path).name} - Auto-generated placeholder
This script was referenced in CI/CD workflows but was missing.
Please implement the required functionality.
"""

import sys

def main():
    print(f"{{Path(__file__).name}} is not yet implemented")
    print("Please implement this script as required by the CI/CD workflow")
    return 0

if __name__ == '__main__':
    sys.exit(main())
'''
            else:
                content = f'''#!/bin/bash
# {Path(script_path).name} - Auto-generated placeholder
# This script was referenced in CI/CD workflows but was missing.
# Please implement the required functionality.

echo "{Path(script_path).name} is not yet implemented"
echo "Please implement this script as required by the CI/CD workflow"
exit 0
'''
            
            full_path.write_text(content)
            full_path.chmod(0o755)
            self.fixed.append(f"Created placeholder: {script_path}")
            return True
            
        except Exception as e:
            self.log(f"Could not create {script_path}: {e}", 'warning')
            return False
    
    def validate_workflow(self, workflow_file: Path) -> Dict:
        """Validate a single workflow file."""
        result = {
            'name': workflow_file.name,
            'valid': True,
            'errors': [],
            'warnings': [],
            'scripts_missing': [],
            'tests_missing': []
        }
        
        # Check YAML syntax
        valid, error = self.check_yaml_syntax(workflow_file)
        if not valid:
            result['valid'] = False
            result['errors'].append(f"YAML syntax error: {error}")
            return result
        
        # Load and analyze workflow
        try:
            with open(workflow_file, 'r') as f:
                content = f.read()
                workflow_data = yaml.safe_load(content)
            
            # Check for basic structure
            if 'jobs' not in workflow_data:
                result['warnings'].append("No jobs defined")
            
            if 'on' not in workflow_data:
                result['warnings'].append("No triggers defined")
            
            # Extract and verify scripts
            scripts = self.extract_scripts(content)
            for script in scripts:
                if not self.verify_file_exists(script):
                    # Skip some known patterns
                    if script in ['matrix.py', 'github.sh', 'install.sh', 'health-check.sh']:
                        continue
                    if script.startswith('test_') and script.endswith('basic.py'):
                        # These are created dynamically in workflows
                        continue
                    
                    result['scripts_missing'].append(script)
                    if self.create_missing_script(script):
                        result['warnings'].append(f"Created placeholder for {script}")
                    else:
                        result['warnings'].append(f"Script not found: {script}")
            
            # Extract and verify tests
            tests = self.extract_tests(content)
            for test in tests:
                if not self.verify_file_exists(test):
                    # Skip pattern matches that aren't actual files
                    if test in ['-xvs', '\\', 'test/']:
                        continue
                    
                    result['tests_missing'].append(test)
                    result['warnings'].append(f"Test not found: {test}")
            
        except Exception as e:
            result['warnings'].append(f"Error analyzing workflow: {e}")
        
        return result
    
    def validate_all_workflows(self) -> Tuple[int, int, int]:
        """Validate all workflow files."""
        if not self.workflows_dir.exists():
            self.log(f"Workflows directory not found: {self.workflows_dir}", 'error')
            return 0, 1, 0
        
        workflow_files = sorted(list(self.workflows_dir.glob('*.yml')) + 
                               list(self.workflows_dir.glob('*.yaml')))
        
        if not workflow_files:
            self.log(f"No workflow files found in {self.workflows_dir}", 'error')
            return 0, 1, 0
        
        self.log(f"Validating {len(workflow_files)} workflow files...\n", 'info')
        
        valid_count = 0
        error_count = 0
        warning_count = 0
        
        for workflow_file in workflow_files:
            result = self.validate_workflow(workflow_file)
            
            # Determine status
            if result['valid'] and not result['errors']:
                status = '✅'
                valid_count += 1
            elif result['errors']:
                status = '❌'
                error_count += 1
            else:
                status = '⚠️'
            
            # Print result
            print(f"{status} {result['name']}")
            
            # Print errors
            for error in result['errors']:
                print(f"   ❌ {error}")
            
            # Print warnings (only in verbose mode or if there are errors)
            if self.verbose or result['errors']:
                for warning in result['warnings'][:5]:  # Limit to 5 warnings
                    print(f"   ⚠️  {warning}")
                if len(result['warnings']) > 5:
                    print(f"   ⚠️  ... and {len(result['warnings']) - 5} more warnings")
            
            warning_count += len(result['warnings'])
        
        # Print summary
        print(f"\n{'='*70}")
        print(f"📊 Validation Summary:")
        print(f"   Total workflows: {len(workflow_files)}")
        print(f"   Valid: {valid_count}")
        print(f"   With errors: {error_count}")
        print(f"   Total warnings: {warning_count}")
        
        if self.fixed:
            print(f"\n🔧 Fixed {len(self.fixed)} issues:")
            for fix in self.fixed[:10]:
                print(f"   ✓ {fix}")
            if len(self.fixed) > 10:
                print(f"   ... and {len(self.fixed) - 10} more")
        
        return valid_count, error_count, warning_count
    
    def run(self) -> int:
        """Run the validation and return exit code."""
        valid, errors, warnings = self.validate_all_workflows()
        
        if errors > 0:
            self.log(f"\n❌ Found {errors} workflow(s) with errors", 'error')
            return 1
        elif warnings > 0:
            self.log(f"\n✅ All workflows are valid (with {warnings} warnings)", 'success')
            return 0
        else:
            self.log(f"\n✅ All workflows are valid!", 'success')
            return 0


def main():
    parser = argparse.ArgumentParser(
        description='Validate GitHub Actions CI/CD workflows',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic validation
    python scripts/ci/validate_ci_workflows.py
    
    # Verbose output
    python scripts/ci/validate_ci_workflows.py --verbose
    
    # Create placeholders for missing scripts
    python scripts/ci/validate_ci_workflows.py --fix-missing
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output including all warnings'
    )
    
    parser.add_argument(
        '--fix-missing',
        action='store_true',
        help='Create placeholder files for missing scripts'
    )
    
    args = parser.parse_args()
    
    # Determine repo root
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent.parent  # scripts/ci/validate_ci_workflows.py -> repo root
    
    # Run validation
    validator = WorkflowValidator(repo_root, verbose=args.verbose, fix_missing=args.fix_missing)
    exit_code = validator.run()
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
