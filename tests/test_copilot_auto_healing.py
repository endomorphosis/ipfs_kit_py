#!/usr/bin/env python3
"""
Test suite for GitHub Copilot Auto-Healing System

This script validates the Copilot-enhanced auto-healing system configuration.
"""

import os
import sys
import yaml
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{Colors.RESET}\n")

def print_test(name, passed, details=""):
    icon = f"{Colors.GREEN}✅" if passed else f"{Colors.RED}❌"
    print(f"{icon} {name}{Colors.RESET}")
    if details:
        print(f"   {details}")

def test_workflow_yaml_validity():
    """Test that all workflow files are valid YAML"""
    print_header("Testing Workflow YAML Validity")
    
    workflows = [
        '.github/workflows/workflow-failure-monitor.yml',
        '.github/workflows/copilot-auto-heal.yml',
        '.github/workflows/copilot-agent-autofix.yml',
        '.github/workflows/auto-heal-workflow.yml'
    ]
    
    all_valid = True
    for workflow in workflows:
        try:
            with open(workflow, 'r') as f:
                yaml.safe_load(f)
            print_test(f"{workflow} is valid YAML", True)
        except FileNotFoundError:
            print_test(f"{workflow} exists", False, f"File not found")
            all_valid = False
        except yaml.YAMLError as e:
            print_test(f"{workflow} is valid YAML", False, f"YAML error: {e}")
            all_valid = False
    
    assert all_valid

def test_copilot_instructions_exist():
    """Test that Copilot instructions file exists"""
    print_header("Testing Copilot Instructions")
    
    instructions_file = '.github/copilot-instructions.md'
    
    if os.path.exists(instructions_file):
        with open(instructions_file, 'r') as f:
            content = f.read()
        
        # Check for key sections
        checks = {
            'Context section': '## Context' in content or '# Context' in content,
            'Role section': '## Your Role' in content or 'Role' in content,
            'Example scenarios': 'Example' in content or 'Scenario' in content,
            'Sufficient length': len(content) > 500
        }
        
        all_passed = all(checks.values())
        print_test("Copilot instructions file exists", True)
        for check, passed in checks.items():
            print_test(f"  - {check}", passed)
        
        assert all_passed
    else:
        print_test("Copilot instructions file exists", False)
        assert False

def test_copilot_workflows_structure():
    """Test that Copilot workflows have correct structure"""
    print_header("Testing Copilot Workflow Structure")
    
    workflows_to_test = {
        '.github/workflows/copilot-agent-autofix.yml': {
            'trigger': 'issues',
            'label_check': 'copilot-agent',
            'required_steps': ['Checkout repository', 'Parse issue', 'Generate', 'Create PR']
        },
        '.github/workflows/copilot-auto-heal.yml': {
            'trigger': 'issues',
            'label_check': 'auto-heal',
            'required_steps': ['Checkout repository', 'Parse issue', 'Copilot', 'Create']
        }
    }
    
    all_valid = True
    for workflow_path, requirements in workflows_to_test.items():
        try:
            with open(workflow_path, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # Check trigger (check both in YAML and raw file)
            with open(workflow_path, 'r') as f:
                raw_content = f.read()
            has_correct_trigger = requirements['trigger'] in str(workflow.get('on', {})) or f"on:\n  {requirements['trigger']}" in raw_content
            print_test(f"{Path(workflow_path).name} has '{requirements['trigger']}' trigger", has_correct_trigger)
            
            # Check for label check in condition
            workflow_str = str(workflow)
            has_label_check = requirements['label_check'] in workflow_str
            print_test(f"{Path(workflow_path).name} checks for '{requirements['label_check']}' label", has_label_check)
            
            # Check for required steps
            jobs = workflow.get('jobs', {})
            steps_found = []
            for job_name, job_config in jobs.items():
                for step in job_config.get('steps', []):
                    step_name = step.get('name', '')
                    steps_found.append(step_name)
            
            steps_str = ' '.join(steps_found)
            has_required_steps = all(req in steps_str for req in requirements['required_steps'])
            print_test(f"{Path(workflow_path).name} has required steps", has_required_steps)
            
            if not all([has_correct_trigger, has_label_check, has_required_steps]):
                all_valid = False
        
        except Exception as e:
            print_test(f"{Path(workflow_path).name} structure test", False, str(e))
            all_valid = False
    
    assert all_valid

def test_workflow_failure_monitor_labels():
    """Test that workflow failure monitor adds copilot-agent label"""
    print_header("Testing Workflow Failure Monitor Configuration")
    
    try:
        with open('.github/workflows/workflow-failure-monitor.yml', 'r') as f:
            content = f.read()
        
        # Check if copilot-agent label is added
        has_copilot_label = 'copilot-agent' in content
        print_test("Monitor adds 'copilot-agent' label", has_copilot_label)
        
        # Check for auto-heal label
        has_autoheal_label = 'auto-heal' in content
        print_test("Monitor adds 'auto-heal' label", has_autoheal_label)
        
        # Check for workflow-failure label
        has_failure_label = 'workflow-failure' in content
        print_test("Monitor adds 'workflow-failure' label", has_failure_label)
        
        assert has_copilot_label and has_autoheal_label and has_failure_label
    
    except Exception as e:
        print_test("Workflow failure monitor test", False, str(e))
        assert False

def test_documentation():
    """Test that documentation exists and is comprehensive"""
    print_header("Testing Documentation")
    
    docs_to_check = {
        'COPILOT_AUTO_HEALING_GUIDE.md': 5000,  # Should be substantial
        'AUTO_HEALING_WORKFLOWS.md': 1000,
        'AUTO_HEALING_QUICK_START.md': 500
    }
    
    all_valid = True
    for doc, min_length in docs_to_check.items():
        if os.path.exists(doc):
            with open(doc, 'r') as f:
                content = f.read()
            
            is_long_enough = len(content) >= min_length
            print_test(f"{doc} exists and is comprehensive", is_long_enough, 
                      f"Length: {len(content)} chars (min: {min_length})")
            
            if not is_long_enough:
                all_valid = False
        else:
            print_test(f"{doc} exists", False)
            all_valid = False
    
    assert all_valid

def test_copilot_integration_features():
    """Test that key Copilot integration features are present"""
    print_header("Testing Copilot Integration Features")
    
    features_to_check = {
        '.github/workflows/copilot-agent-autofix.yml': [
            'copilot',
            'autofix',
            'pr',
            'fix'
        ],
        '.github/workflows/copilot-auto-heal.yml': [
            'workspace',
            'copilot',
            'task',
            'branch'
        ],
        'COPILOT_AUTO_HEALING_GUIDE.md': [
            'GitHub Copilot',
            'AI',
            'intelligent',
            'workspace',
            'agent'
        ]
    }
    
    all_valid = True
    for file_path, keywords in features_to_check.items():
        try:
            with open(file_path, 'r') as f:
                content = f.read().lower()
            
            keywords_found = [kw for kw in keywords if kw.lower() in content]
            all_found = len(keywords_found) == len(keywords)
            
            print_test(f"{file_path} has Copilot features", all_found,
                      f"Found: {', '.join(keywords_found)}")
            
            if not all_found:
                all_valid = False
                missing = [kw for kw in keywords if kw.lower() not in content]
                print(f"   {Colors.YELLOW}Missing: {', '.join(missing)}{Colors.RESET}")
        
        except FileNotFoundError:
            print_test(f"{file_path} exists", False)
            all_valid = False
    
    assert all_valid

def test_workflow_permissions():
    """Test that workflows have appropriate permissions"""
    print_header("Testing Workflow Permissions")
    
    workflows = [
        '.github/workflows/copilot-agent-autofix.yml',
        '.github/workflows/copilot-auto-heal.yml',
        '.github/workflows/workflow-failure-monitor.yml'
    ]
    
    required_permissions = {
        'copilot-agent-autofix.yml': ['contents', 'pull-requests', 'issues', 'actions'],
        'copilot-auto-heal.yml': ['contents', 'pull-requests', 'issues'],
        'workflow-failure-monitor.yml': ['contents', 'actions', 'issues']
    }
    
    all_valid = True
    for workflow_path in workflows:
        workflow_name = Path(workflow_path).name
        try:
            with open(workflow_path, 'r') as f:
                workflow = yaml.safe_load(f)
            
            permissions = workflow.get('permissions', {})
            has_permissions = len(permissions) > 0
            print_test(f"{workflow_name} has permissions defined", has_permissions)
            
            if workflow_name in required_permissions:
                required = required_permissions[workflow_name]
                has_all = all(perm in permissions for perm in required)
                print_test(f"{workflow_name} has required permissions", has_all,
                          f"Required: {', '.join(required)}")
                
                if not has_all:
                    all_valid = False
        
        except Exception as e:
            print_test(f"{workflow_name} permissions test", False, str(e))
            all_valid = False
    
    assert all_valid

def main():
    """Run all tests"""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("GitHub Copilot Auto-Healing System - Test Suite")
    print(f"{'='*60}{Colors.RESET}\n")
    
    tests = [
        ("Workflow YAML Validity", test_workflow_yaml_validity),
        ("Copilot Instructions", test_copilot_instructions_exist),
        ("Copilot Workflow Structure", test_copilot_workflows_structure),
        ("Workflow Failure Monitor Labels", test_workflow_failure_monitor_labels),
        ("Documentation", test_documentation),
        ("Copilot Integration Features", test_copilot_integration_features),
        ("Workflow Permissions", test_workflow_permissions)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"{Colors.RED}❌ Error running {test_name}: {e}{Colors.RESET}")
            results[test_name] = False
    
    # Print summary
    print_header("Test Summary")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        icon = f"{Colors.GREEN}✅ PASS" if result else f"{Colors.RED}❌ FAIL"
        print(f"{icon}: {test_name}{Colors.RESET}")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"Total: {passed}/{total} tests passed")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    if passed == total:
        print(f"{Colors.GREEN}🎉 All tests passed! Copilot auto-healing system is properly configured.{Colors.RESET}\n")
        return 0
    else:
        print(f"{Colors.RED}⚠️  Some tests failed. Please review the configuration.{Colors.RESET}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
