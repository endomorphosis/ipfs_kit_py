#!/usr/bin/env python3
"""
CI/CD Scripts Test Runner
==========================

This script tests all CI/CD scripts to ensure they can run without errors.
It's designed to run in the GitHub Actions environment.

Usage:
    python scripts/ci/test_ci_scripts.py
    python scripts/ci/test_ci_scripts.py --verbose
    python scripts/ci/test_ci_scripts.py --script monitor_amd64_installation.py
"""

import subprocess
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict
import json


class CIScriptTester:
    """Tests CI/CD scripts for basic functionality."""
    
    def __init__(self, repo_root: Path, verbose: bool = False):
        self.repo_root = repo_root
        self.scripts_dir = repo_root / 'scripts' / 'ci'
        self.verbose = verbose
        self.results = []
        
    def log(self, message: str, level: str = 'info'):
        """Log a message."""
        if self.verbose or level != 'debug':
            symbols = {'info': 'ℹ️', 'warning': '⚠️', 'error': '❌', 'success': '✅'}
            print(f"{symbols.get(level, 'ℹ️')}  {message}")
    
    def run_script(self, script_path: Path, args: List[str] = None) -> Tuple[bool, str, str]:
        """Run a script and return success status, stdout, stderr."""
        if args is None:
            args = []
        
        try:
            # Try with --help first to see if script accepts it
            result = subprocess.run(
                [sys.executable, str(script_path)] + args,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", "Script timed out after 30 seconds"
        except Exception as e:
            return False, "", str(e)
    
    def test_script(self, script_path: Path) -> Dict:
        """Test a single script."""
        result = {
            'name': script_path.name,
            'path': str(script_path.relative_to(self.repo_root)),
            'executable': script_path.stat().st_mode & 0o111 != 0,
            'help_works': False,
            'runs': False,
            'exit_code': None,
            'stdout_lines': 0,
            'stderr_lines': 0,
            'error': None
        }
        
        # Test if script is executable
        if not result['executable']:
            self.log(f"Script {script_path.name} is not executable", 'warning')
        
        # Test with --help if it's likely to support it
        help_success, help_stdout, help_stderr = self.run_script(script_path, ['--help'])
        result['help_works'] = help_success
        
        # Test basic execution (no args or with safe args)
        # For monitoring scripts, they should run without errors even with no special args
        run_success, run_stdout, run_stderr = self.run_script(script_path)
        result['runs'] = run_success
        result['stdout_lines'] = len(run_stdout.splitlines()) if run_stdout else 0
        result['stderr_lines'] = len(run_stderr.splitlines()) if run_stderr else 0
        
        if not run_success:
            result['error'] = run_stderr[:200] if run_stderr else "Unknown error"
        
        return result
    
    def test_all_scripts(self, specific_script: str = None) -> List[Dict]:
        """Test all Python scripts in scripts/ci directory."""
        if not self.scripts_dir.exists():
            self.log(f"Scripts directory not found: {self.scripts_dir}", 'error')
            return []
        
        # Get all Python scripts
        if specific_script:
            scripts = [self.scripts_dir / specific_script]
            if not scripts[0].exists():
                self.log(f"Script not found: {specific_script}", 'error')
                return []
        else:
            scripts = sorted(self.scripts_dir.glob('*.py'))
        
        self.log(f"Testing {len(scripts)} CI/CD scripts...\n", 'info')
        
        results = []
        for script in scripts:
            self.log(f"Testing {script.name}...", 'debug')
            result = self.test_script(script)
            results.append(result)
            
            # Print result
            if result['runs']:
                print(f"✅ {result['name']}")
                if self.verbose:
                    print(f"   Output: {result['stdout_lines']} lines")
            elif result['help_works']:
                print(f"⚠️  {result['name']} (help works but execution may need arguments)")
            else:
                print(f"❌ {result['name']}")
                if result['error']:
                    print(f"   Error: {result['error'][:100]}")
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """Print test summary."""
        if not results:
            return
        
        total = len(results)
        runs = sum(1 for r in results if r['runs'])
        help_works = sum(1 for r in results if r['help_works'])
        executable = sum(1 for r in results if r['executable'])
        
        print(f"\n{'='*70}")
        print(f"📊 Test Summary:")
        print(f"   Total scripts: {total}")
        print(f"   Runs successfully: {runs}")
        print(f"   Help works: {help_works}")
        print(f"   Executable: {executable}")
        print(f"   Success rate: {runs/total*100:.1f}%")
        
        # Scripts that don't run
        failed = [r for r in results if not r['runs']]
        if failed:
            print(f"\n⚠️  Scripts that need attention ({len(failed)}):")
            for r in failed[:5]:
                print(f"   - {r['name']}")
                if r['error'] and self.verbose:
                    print(f"     {r['error'][:80]}")
            if len(failed) > 5:
                print(f"   ... and {len(failed) - 5} more")
    
    def save_results(self, results: List[Dict], output_file: Path):
        """Save test results to JSON file."""
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump({
                    'total': len(results),
                    'success': sum(1 for r in results if r['runs']),
                    'results': results
                }, f, indent=2)
            self.log(f"Results saved to {output_file}", 'success')
        except Exception as e:
            self.log(f"Could not save results: {e}", 'error')
    
    def run(self, specific_script: str = None) -> int:
        """Run tests and return exit code."""
        results = self.test_all_scripts(specific_script)
        self.print_summary(results)
        
        # Save results
        output_file = self.repo_root / 'data' / 'test_results' / 'ci_scripts_test_results.json'
        self.save_results(results, output_file)
        
        # Return 0 if most scripts work
        if results:
            success_rate = sum(1 for r in results if r['runs']) / len(results)
            if success_rate >= 0.7:  # 70% success rate
                self.log("\n✅ CI/CD scripts are functional", 'success')
                return 0
            else:
                self.log(f"\n⚠️  Only {success_rate*100:.1f}% of scripts work", 'warning')
                return 1
        else:
            self.log("\n❌ No scripts found to test", 'error')
            return 1


def main():
    parser = argparse.ArgumentParser(
        description='Test CI/CD scripts for basic functionality',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output'
    )
    
    parser.add_argument(
        '--script', '-s',
        help='Test a specific script by name'
    )
    
    args = parser.parse_args()
    
    # Determine repo root
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent.parent
    
    # Run tests
    tester = CIScriptTester(repo_root, verbose=args.verbose)
    exit_code = tester.run(specific_script=args.script)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
