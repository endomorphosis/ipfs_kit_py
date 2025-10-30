#!/usr/bin/env python3
"""
Generate workflow fixes based on failure analysis.

This script:
1. Analyzes the workflow failure
2. Determines potential fixes based on error patterns
3. Generates modified workflow files with fixes
4. Creates a fix report for the PR
"""

import os
import sys
import json
import re
import yaml
from github import Github
import requests


def generate_workflow_fix():
    """Main function to generate workflow fix."""
    
    # Get environment variables
    github_token = os.environ.get('GITHUB_TOKEN')
    workflow_run_id = os.environ.get('WORKFLOW_RUN_ID')
    workflow_name = os.environ.get('WORKFLOW_NAME')
    issue_number = os.environ.get('ISSUE_NUMBER')
    repository = os.environ.get('REPOSITORY')
    
    if not all([github_token, repository]):
        print("Missing required environment variables")
        sys.exit(1)
    
    # Initialize GitHub client
    g = Github(github_token)
    repo = g.get_repo(repository)
    
    try:
        # Load failure analysis if available
        analysis = {}
        if os.path.exists('/tmp/failure_analysis.json'):
            with open('/tmp/failure_analysis.json', 'r') as f:
                analysis = json.load(f)
        elif workflow_run_id:
            # Fetch fresh analysis
            workflow_run = repo.get_workflow_run(int(workflow_run_id))
            analysis = analyze_from_workflow_run(workflow_run, github_token, repository)
        
        # Generate fix based on error patterns
        fix = {
            'workflow_name': workflow_name or analysis.get('workflow_name', 'Unknown'),
            'analysis': '',
            'changes': [],
            'files': [],
            'error_summary': '',
            'suggested_fix': '',
            'testing_notes': '',
            'reason': ''
        }
        
        # Extract error patterns
        error_patterns = analysis.get('error_patterns', [])
        
        if not error_patterns and 'error_details' in analysis:
            # Try to identify patterns from error details
            error_patterns = identify_patterns_from_text(analysis['error_details'])
        
        # Generate fixes based on patterns
        has_fix = False
        workflow_path = None
        
        for pattern in error_patterns:
            if pattern.get('fixable'):
                fix_result = generate_fix_for_pattern(pattern, workflow_name, repo)
                if fix_result:
                    fix['changes'].append(fix_result['change'])
                    if 'file' in fix_result:
                        fix['files'].append(fix_result['file'])
                        has_fix = True
                        workflow_path = fix_result['file']['path']
        
        # If no specific pattern-based fix, try to create a general improvement
        if not has_fix and workflow_name:
            general_fix = generate_general_workflow_fix(workflow_name, analysis, repo)
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
        fix['error_summary'] = analysis.get('error_details', 'No error details available')[:1000]  # Limit size
        
        # Suggested fix description
        if fix['changes']:
            fix['suggested_fix'] = '\n'.join([f"- {change}" for change in fix['changes']])
        else:
            fix['suggested_fix'] = "No automatic fix could be generated. Please review the error logs manually."
            fix['reason'] = "Error patterns did not match any known fixable issues"
        
        # Testing notes
        fix['testing_notes'] = f"Test by triggering the '{workflow_name}' workflow after merging this PR."
        
        # Save fix to file
        with open('/tmp/workflow_fix.json', 'w') as f:
            json.dump(fix, f, indent=2)
        
        # Set GitHub Actions output (using environment file)
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write(f"has_fix={str(has_fix).lower()}\n")
        else:
            # Fallback for older GitHub Actions runners
            print(f"::set-output name=has_fix::{str(has_fix).lower()}")
        
        print(f"Fix generation complete. Has fix: {has_fix}")
        return fix
        
    except Exception as e:
        print(f"Error generating workflow fix: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def analyze_from_workflow_run(workflow_run, github_token, repository):
    """Analyze workflow run to extract failure info."""
    analysis = {
        'workflow_name': workflow_run.name,
        'error_details': '',
        'error_patterns': []
    }
    
    # Get failed jobs
    jobs = workflow_run.jobs()
    for job in jobs:
        if job.conclusion == 'failure':
            try:
                logs_url = f"https://api.github.com/repos/{repository}/actions/jobs/{job.id}/logs"
                headers = {
                    'Authorization': f'token {github_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }
                response = requests.get(logs_url, headers=headers, allow_redirects=True)
                
                if response.status_code == 200:
                    logs = response.text
                    analysis['error_details'] += f"\n### Job: {job.name}\n{logs[:2000]}"
                    patterns = identify_patterns_from_text(logs)
                    analysis['error_patterns'].extend(patterns)
            except Exception as e:
                print(f"Could not fetch logs for job {job.id}: {e}")
    
    return analysis


def identify_patterns_from_text(text):
    """Identify error patterns from text."""
    patterns = []
    
    pattern_checks = [
        {
            'pattern': r'command not found:\s*(\S+)',
            'type': 'missing_command',
            'fixable': True,
            'suggestion': 'Install missing command'
        },
        {
            'pattern': r'No such file or directory.*?([^\s]+)',
            'type': 'missing_file',
            'fixable': True,
            'suggestion': 'Check file paths'
        },
        {
            'pattern': r'ModuleNotFoundError.*?[\'"]([^\'"]+)[\'"]',
            'type': 'missing_dependency',
            'fixable': True,
            'suggestion': 'Install missing dependency'
        },
        {
            'pattern': r'timeout|timed out',
            'type': 'timeout',
            'fixable': True,
            'suggestion': 'Increase timeout'
        }
    ]
    
    for check in pattern_checks:
        match = re.search(check['pattern'], text, re.IGNORECASE)
        if match:
            pattern_dict = check.copy()
            if match.groups():
                pattern_dict['matched_value'] = match.group(1)
            patterns.append(pattern_dict)
    
    return patterns


def generate_fix_for_pattern(pattern, workflow_name, repo):
    """Generate a fix for a specific error pattern."""
    pattern_type = pattern['type']
    
    if pattern_type == 'missing_dependency':
        return generate_dependency_fix(pattern, workflow_name, repo)
    elif pattern_type == 'timeout':
        return generate_timeout_fix(pattern, workflow_name, repo)
    elif pattern_type == 'missing_command':
        return generate_command_fix(pattern, workflow_name, repo)
    elif pattern_type == 'missing_file':
        return generate_file_check_fix(pattern, workflow_name, repo)
    
    return None


def generate_dependency_fix(pattern, workflow_name, repo):
    """Generate fix for missing dependencies."""
    missing_dep = pattern.get('matched_value', 'unknown')
    
    return {
        'change': f"Add missing dependency: {missing_dep}",
        'description': f"Install {missing_dep} in the workflow"
    }


def generate_timeout_fix(pattern, workflow_name, repo):
    """Generate fix for timeout issues."""
    return {
        'change': "Increase job timeout",
        'description': "Add or increase timeout-minutes for the job"
    }


def generate_command_fix(pattern, workflow_name, repo):
    """Generate fix for missing commands."""
    missing_cmd = pattern.get('matched_value', 'unknown')
    
    return {
        'change': f"Add missing command: {missing_cmd}",
        'description': f"Install or add {missing_cmd} to PATH"
    }


def generate_file_check_fix(pattern, workflow_name, repo):
    """Generate fix for missing files."""
    return {
        'change': "Add file existence check",
        'description': "Add conditional checks before accessing files"
    }


def generate_general_workflow_fix(workflow_name, analysis, repo):
    """Generate a general workflow improvement when no specific fix is found."""
    
    # Try to find the workflow file
    workflow_files = []
    try:
        contents = repo.get_contents(".github/workflows")
        for content in contents:
            if content.type == "file" and (content.name.endswith('.yml') or content.name.endswith('.yaml')):
                workflow_files.append(content)
    except Exception as e:
        print(f"Could not list workflow files: {e}")
        return None
    
    # Find the matching workflow file
    target_workflow = None
    for wf_file in workflow_files:
        if workflow_name.lower().replace(' ', '-') in wf_file.name.lower():
            target_workflow = wf_file
            break
    
    if not target_workflow:
        return None
    
    # Read the workflow content
    try:
        workflow_content = target_workflow.decoded_content.decode('utf-8')
        workflow_data = yaml.safe_load(workflow_content)
        
        # Add continue-on-error to failed jobs if not present
        changes = []
        modified = False
        
        if 'jobs' in workflow_data:
            for job_name, job_config in workflow_data['jobs'].items():
                # Add continue-on-error for optional jobs
                if 'continue-on-error' not in job_config:
                    # Check if this is a job that often fails (like ARM64, optional tests, etc.)
                    if any(keyword in job_name.lower() for keyword in ['arm64', 'optional', 'experimental']):
                        job_config['continue-on-error'] = True
                        changes.append(f"Added continue-on-error to optional job: {job_name}")
                        modified = True
                
                # Add timeout if not present
                if 'timeout-minutes' not in job_config:
                    job_config['timeout-minutes'] = 60
                    changes.append(f"Added 60-minute timeout to job: {job_name}")
                    modified = True
        
        if modified:
            # Write modified workflow
            new_content = yaml.dump(workflow_data, default_flow_style=False, sort_keys=False)
            
            return {
                'changes': changes,
                'files': [{
                    'path': target_workflow.path,
                    'content': new_content
                }],
                'suggested_fix': '\n'.join([f"- {change}" for change in changes])
            }
    
    except Exception as e:
        print(f"Error processing workflow file: {e}")
    
    return None


if __name__ == '__main__':
    generate_workflow_fix()
