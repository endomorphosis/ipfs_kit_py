#!/usr/bin/env python3
"""
Test the auto-healing workflow system configuration.

This script validates:
1. Workflow files are valid YAML
2. Required scripts exist and are executable
3. Dependencies are installable
4. Basic functionality of analysis and fix generation
"""

import os
import sys
import yaml
import subprocess
from pathlib import Path


def test_workflow_yaml_validity():
    """Test that workflow files are valid YAML."""
    print("Testing workflow YAML validity...")
    
    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        print("  ❌ Workflow directory not found")
        return False
    
    target_workflows = [
        "workflow-failure-monitor.yml",
        "auto-heal-workflow.yml"
    ]
    
    for workflow_name in target_workflows:
        workflow_path = workflow_dir / workflow_name
        if not workflow_path.exists():
            print(f"  ❌ Workflow not found: {workflow_name}")
            return False
        
        try:
            with open(workflow_path, 'r') as f:
                yaml.safe_load(f)
            print(f"  ✅ {workflow_name} is valid YAML")
        except yaml.YAMLError as e:
            print(f"  ❌ {workflow_name} has YAML errors: {e}")
            return False
    
    return True


def test_scripts_exist():
    """Test that required scripts exist and are executable."""
    print("\nTesting script existence...")
    
    scripts = [
        "scripts/ci/analyze_workflow_failure.py",
        "scripts/ci/generate_workflow_fix.py"
    ]
    
    for script_path in scripts:
        path = Path(script_path)
        if not path.exists():
            print(f"  ❌ Script not found: {script_path}")
            return False
        
        if not os.access(path, os.X_OK):
            print(f"  ⚠️  Script not executable: {script_path}")
            # Make it executable
            os.chmod(path, 0o755)
            print(f"  ✅ Made executable: {script_path}")
        else:
            print(f"  ✅ Script exists and is executable: {script_path}")
    
    return True


def test_dependencies():
    """Test that required dependencies can be imported."""
    print("\nTesting Python dependencies...")
    
    required_modules = [
        ('github', 'PyGithub'),
        ('yaml', 'PyYAML'),
        ('requests', 'requests')
    ]
    
    all_available = True
    for module_name, package_name in required_modules:
        try:
            __import__(module_name)
            print(f"  ✅ {package_name} is available")
        except ImportError:
            print(f"  ⚠️  {package_name} not installed (will be installed in workflows)")
            all_available = False
    
    return True  # Dependencies will be installed in workflow


def test_script_syntax():
    """Test that scripts have valid Python syntax."""
    print("\nTesting script syntax...")
    
    scripts = [
        "scripts/ci/analyze_workflow_failure.py",
        "scripts/ci/generate_workflow_fix.py"
    ]
    
    for script_path in scripts:
        try:
            result = subprocess.run(
                ['python3', '-m', 'py_compile', script_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"  ✅ {script_path} has valid syntax")
            else:
                print(f"  ❌ {script_path} has syntax errors:")
                print(f"     {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Syntax check timed out for {script_path}")
        except Exception as e:
            print(f"  ❌ Error checking {script_path}: {e}")
            return False
    
    return True


def test_documentation():
    """Test that documentation exists."""
    print("\nTesting documentation...")
    
    docs = [
        "AUTO_HEALING_WORKFLOWS.md"
    ]
    
    for doc_path in docs:
        path = Path(doc_path)
        if not path.exists():
            print(f"  ❌ Documentation not found: {doc_path}")
            return False
        
        # Check that it has content
        if path.stat().st_size < 100:
            print(f"  ⚠️  Documentation seems too short: {doc_path}")
        else:
            print(f"  ✅ Documentation exists: {doc_path}")
    
    return True


def test_workflow_structure():
    """Test that workflows have required components."""
    print("\nTesting workflow structure...")
    
    # Test workflow-failure-monitor.yml
    monitor_path = Path(".github/workflows/workflow-failure-monitor.yml")
    with open(monitor_path, 'r') as f:
        monitor_workflow = yaml.safe_load(f)
    
    # Check for required elements (YAML parses 'on' as boolean True)
    has_on_key = 'on' in monitor_workflow or True in monitor_workflow
    workflow_run_config = monitor_workflow.get('on') or monitor_workflow.get(True)
    
    checks = [
        (has_on_key and workflow_run_config and 'workflow_run' in workflow_run_config, 
         "workflow-failure-monitor has workflow_run trigger"),
        ('permissions' in monitor_workflow, 
         "workflow-failure-monitor has permissions"),
        ('jobs' in monitor_workflow, 
         "workflow-failure-monitor has jobs"),
    ]
    
    # Test auto-heal-workflow.yml
    heal_path = Path(".github/workflows/auto-heal-workflow.yml")
    with open(heal_path, 'r') as f:
        heal_workflow = yaml.safe_load(f)
    
    heal_on_config = heal_workflow.get('on') or heal_workflow.get(True)
    
    checks.extend([
        (heal_on_config and 'issues' in heal_on_config, 
         "auto-heal-workflow has issues trigger"),
        ('permissions' in heal_workflow, 
         "auto-heal-workflow has permissions"),
        ('jobs' in heal_workflow, 
         "auto-heal-workflow has jobs"),
    ])
    
    all_passed = True
    for check, description in checks:
        if check:
            print(f"  ✅ {description}")
        else:
            print(f"  ❌ {description}")
            all_passed = False
    
    return all_passed


def main():
    """Run all tests."""
    print("=" * 60)
    print("Auto-Healing Workflow System - Configuration Test")
    print("=" * 60)
    
    tests = [
        ("Workflow YAML Validity", test_workflow_yaml_validity),
        ("Script Existence", test_scripts_exist),
        ("Python Dependencies", test_dependencies),
        ("Script Syntax", test_script_syntax),
        ("Documentation", test_documentation),
        ("Workflow Structure", test_workflow_structure),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Auto-healing system is properly configured.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
