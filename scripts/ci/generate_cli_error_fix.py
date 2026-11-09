#!/usr/bin/env python3
"""
Generate CLI error fixes based on failure analysis.

This script:
1. Analyzes the CLI error from the GitHub issue
2. Determines potential fixes based on error patterns
3. Generates code fixes if possible
4. Creates a fix report for the PR
"""

import os
import sys
import json
import re
from github import Github


def generate_cli_error_fix():
    """Main function to generate CLI error fix."""
    
    # Get environment variables
    github_token = os.environ.get('GITHUB_TOKEN')
    issue_number = os.environ.get('ISSUE_NUMBER')
    repository = os.environ.get('REPOSITORY')
    
    if not all([github_token, repository, issue_number]):
        print("Missing required environment variables")
        sys.exit(1)
    
    # Initialize GitHub client
    g = Github(github_token)
    repo = g.get_repo(repository)
    
    try:
        # Get the issue
        issue = repo.get_issue(int(issue_number))
        
        # Parse error details from issue body
        analysis = parse_cli_error_from_issue(issue.body)
        
        # Generate fix based on error patterns
        fix = {
            'error_type': analysis.get('error_type', 'Unknown'),
            'analysis': '',
            'changes': [],
            'files': [],
            'error_summary': '',
            'suggested_fix': '',
            'testing_notes': '',
            'reason': ''
        }
        
        # Extract error patterns
        error_patterns = identify_cli_error_patterns(analysis)
        
        # Generate fixes based on patterns
        has_fix = False
        
        for pattern in error_patterns:
            if pattern.get('fixable'):
                fix_result = generate_fix_for_cli_pattern(pattern, analysis, repo)
                if fix_result:
                    fix['changes'].append(fix_result['change'])
                    if 'file' in fix_result:
                        fix['files'].append(fix_result['file'])
                        has_fix = True
        
        # If no specific pattern-based fix, provide general guidance
        if not has_fix:
            general_fix = generate_general_cli_fix(analysis, repo)
            if general_fix:
                fix.update(general_fix)
                has_fix = True
        
        # Prepare analysis summary
        if error_patterns:
            pattern_types = [p['type'] for p in error_patterns]
            fix['analysis'] = f"Identified {len(error_patterns)} potential issue(s): {', '.join(set(pattern_types))}"
        else:
            fix['analysis'] = "Unable to identify specific error patterns. Manual review recommended."
        
        # Error summary
        fix['error_summary'] = analysis.get('error_message', 'No error details available')[:1000]
        
        # Suggested fix description
        if fix['changes']:
            fix['suggested_fix'] = '\n'.join([f"- {change}" for change in fix['changes']])
        else:
            fix['suggested_fix'] = "No automatic fix could be generated. Invoking GitHub Copilot for assistance."
            fix['reason'] = "Error patterns did not match any known fixable issues. GitHub Copilot will be invoked."
        
        # Testing notes
        fix['testing_notes'] = f"Test by running the command that caused the error: {analysis.get('command', 'N/A')}"
        
        # Save fix to file
        with open('/tmp/cli_error_fix.json', 'w') as f:
            json.dump(fix, f, indent=2)
        
        # Set GitHub Actions output
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write(f"has_fix={str(has_fix).lower()}\n")
                f.write(f"error_type={fix['error_type']}\n")
                f.write(f"invoke_copilot={str(not has_fix).lower()}\n")
        
        print(f"CLI error fix generation complete. Has fix: {has_fix}")
        return fix
        
    except Exception as e:
        print(f"Error generating CLI error fix: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def parse_cli_error_from_issue(issue_body):
    """Parse CLI error details from issue body."""
    analysis = {
        'error_type': '',
        'error_message': '',
        'stack_trace': '',
        'command': '',
        'arguments': '',
        'log_context': '',
    }
    
    # Extract error type
    type_match = re.search(r'\*\*Type:\*\*\s+`([^`]+)`', issue_body)
    if type_match:
        analysis['error_type'] = type_match.group(1)
    
    # Extract error message
    msg_match = re.search(r'\*\*Message:\*\*\s+(.+?)(?:\n|$)', issue_body)
    if msg_match:
        analysis['error_message'] = msg_match.group(1).strip()
    
    # Extract command
    cmd_match = re.search(r'### Command Executed\s+```(?:bash)?\s+(.+?)\s+```', issue_body, re.DOTALL)
    if cmd_match:
        analysis['command'] = cmd_match.group(1).strip()
    
    # Extract stack trace
    stack_match = re.search(r'### Stack Trace\s+```(?:python)?\s+(.+?)\s+```', issue_body, re.DOTALL)
    if stack_match:
        analysis['stack_trace'] = stack_match.group(1).strip()
    
    # Extract log context
    log_match = re.search(r'### Log Context.*?\s+```\s+(.+?)\s+```', issue_body, re.DOTALL)
    if log_match:
        analysis['log_context'] = log_match.group(1).strip()
    
    return analysis


def identify_cli_error_patterns(analysis):
    """Identify error patterns from CLI error analysis."""
    patterns = []
    
    error_type = analysis.get('error_type', '')
    error_msg = analysis.get('error_message', '')
    stack_trace = analysis.get('stack_trace', '')
    combined_text = f"{error_type} {error_msg} {stack_trace}"
    
    pattern_checks = [
        {
            'pattern': r'ModuleNotFoundError.*?[\'"]([^\'"]+)[\'"]',
            'type': 'missing_dependency',
            'fixable': True,
            'suggestion': 'Install missing Python module'
        },
        {
            'pattern': r'ImportError.*?cannot import.*?[\'"]([^\'"]+)[\'"]',
            'type': 'import_error',
            'fixable': True,
            'suggestion': 'Fix import statement or add missing dependency'
        },
        {
            'pattern': r'FileNotFoundError.*?[\'"]([^\'"]+)[\'"]',
            'type': 'missing_file',
            'fixable': True,
            'suggestion': 'Create missing file or fix path'
        },
        {
            'pattern': r'PermissionError',
            'type': 'permission_error',
            'fixable': True,
            'suggestion': 'Fix file permissions'
        },
        {
            'pattern': r'ConnectionError|ConnectionRefusedError',
            'type': 'connection_error',
            'fixable': True,
            'suggestion': 'Check service is running or network connectivity'
        },
        {
            'pattern': r'AttributeError.*?object has no attribute\s+[\'"]([^\'"]+)[\'"]',
            'type': 'attribute_error',
            'fixable': False,
            'suggestion': 'Code logic error - needs manual review'
        },
        {
            'pattern': r'TypeError',
            'type': 'type_error',
            'fixable': False,
            'suggestion': 'Type mismatch - needs code review'
        },
        {
            'pattern': r'KeyError.*?[\'"]([^\'"]+)[\'"]',
            'type': 'key_error',
            'fixable': False,
            'suggestion': 'Missing dictionary key - needs code review'
        },
    ]
    
    for check in pattern_checks:
        match = re.search(check['pattern'], combined_text, re.IGNORECASE)
        if match:
            pattern_dict = check.copy()
            if match.groups():
                pattern_dict['matched_value'] = match.group(1)
            patterns.append(pattern_dict)
    
    return patterns


def generate_fix_for_cli_pattern(pattern, analysis, repo):
    """Generate a fix for a specific CLI error pattern."""
    pattern_type = pattern['type']
    
    if pattern_type == 'missing_dependency':
        return generate_dependency_fix(pattern, analysis)
    elif pattern_type == 'import_error':
        return generate_import_fix(pattern, analysis)
    elif pattern_type == 'missing_file':
        return generate_missing_file_fix(pattern, analysis)
    elif pattern_type == 'permission_error':
        return generate_permission_fix(pattern, analysis)
    elif pattern_type == 'connection_error':
        return generate_connection_fix(pattern, analysis)
    
    return None


def generate_dependency_fix(pattern, analysis):
    """Generate fix for missing dependencies."""
    missing_module = pattern.get('matched_value', 'unknown')
    
    return {
        'change': f"Add missing Python dependency: {missing_module}",
        'description': f"Add {missing_module} to requirements or dependencies"
    }


def generate_import_fix(pattern, analysis):
    """Generate fix for import errors."""
    missing_import = pattern.get('matched_value', 'unknown')
    
    return {
        'change': f"Fix import error for: {missing_import}",
        'description': f"Check if {missing_import} is installed or fix import path"
    }


def generate_missing_file_fix(pattern, analysis):
    """Generate fix for missing files."""
    missing_file = pattern.get('matched_value', 'unknown')
    
    return {
        'change': f"Handle missing file: {missing_file}",
        'description': f"Add file existence check or create {missing_file}"
    }


def generate_permission_fix(pattern, analysis):
    """Generate fix for permission errors."""
    return {
        'change': "Fix file/directory permissions",
        'description': "Add permission checks or fix file access rights"
    }


def generate_connection_fix(pattern, analysis):
    """Generate fix for connection errors."""
    return {
        'change': "Add connection error handling",
        'description': "Add retry logic or better error messages for connection failures"
    }


def generate_general_cli_fix(analysis, repo):
    """Generate general guidance when no specific fix is found."""
    
    error_type = analysis.get('error_type', 'Unknown')
    
    # This will signal to invoke GitHub Copilot
    return {
        'changes': [],
        'files': [],
        'suggested_fix': f"GitHub Copilot will be invoked to analyze and fix this {error_type} error.",
        'reason': "Complex error requiring AI-assisted code review and fix generation."
    }


if __name__ == '__main__':
    generate_cli_error_fix()
