#!/usr/bin/env python3
"""
Analyze workflow failures and extract relevant information for auto-healing.

This script:
1. Fetches workflow run details from GitHub API
2. Downloads and analyzes job logs
3. Extracts error messages and failure patterns
4. Generates a structured analysis for the auto-healing system
"""

import os
import sys
import json
import re
from github import Github
import requests


def analyze_workflow_failure():
    """Main function to analyze workflow failure."""
    
    # Get environment variables
    github_token = os.environ.get('GITHUB_TOKEN')
    workflow_run_id = os.environ.get('WORKFLOW_RUN_ID')
    workflow_name = os.environ.get('WORKFLOW_NAME')
    repository = os.environ.get('REPOSITORY')
    
    if not all([github_token, workflow_run_id, repository]):
        print("Missing required environment variables")
        sys.exit(1)
    
    # Initialize GitHub client
    g = Github(github_token)
    repo = g.get_repo(repository)
    
    try:
        # Get workflow run details
        workflow_run = repo.get_workflow_run(int(workflow_run_id))
        
        analysis = {
            'workflow_name': workflow_name,
            'run_id': workflow_run_id,
            'run_url': workflow_run.html_url,
            'conclusion': workflow_run.conclusion,
            'created_at': workflow_run.created_at.isoformat(),
            'updated_at': workflow_run.updated_at.isoformat(),
            'head_branch': workflow_run.head_branch,
            'head_sha': workflow_run.head_sha,
            'failed_jobs': [],
            'error_details': '',
            'summary': '',
            'error_patterns': []
        }
        
        # Get jobs for this workflow run
        jobs = workflow_run.jobs()
        
        for job in jobs:
            if job.conclusion == 'failure':
                job_info = {
                    'name': job.name,
                    'conclusion': job.conclusion,
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'steps': []
                }
                
                # Analyze job steps
                for step in job.steps:
                    if step.conclusion == 'failure':
                        job_info['steps'].append({
                            'name': step.name,
                            'conclusion': step.conclusion,
                            'number': step.number
                        })
                
                analysis['failed_jobs'].append(job_info)
                
                # Try to get logs for failed job
                try:
                    logs_url = f"https://api.github.com/repos/{repository}/actions/jobs/{job.id}/logs"
                    headers = {
                        'Authorization': f'token {github_token}',
                        'Accept': 'application/vnd.github.v3+json'
                    }
                    response = requests.get(logs_url, headers=headers, allow_redirects=True)
                    
                    if response.status_code == 200:
                        logs = response.text
                        errors = extract_errors_from_logs(logs)
                        analysis['error_details'] += f"\n\n### Job: {job.name}\n"
                        analysis['error_details'] += '\n'.join(errors[:10])  # Limit to first 10 errors
                        
                        # Extract error patterns
                        patterns = identify_error_patterns(logs)
                        analysis['error_patterns'].extend(patterns)
                
                except Exception as e:
                    print(f"Could not fetch logs for job {job.id}: {e}")
        
        # Generate summary
        if analysis['failed_jobs']:
            job_names = [job['name'] for job in analysis['failed_jobs']]
            analysis['summary'] = f"Workflow '{workflow_name}' failed with {len(analysis['failed_jobs'])} failed job(s): {', '.join(job_names)}"
        else:
            analysis['summary'] = f"Workflow '{workflow_name}' failed but no specific job failures were identified."
        
        # Determine if we should create an issue
        should_create_issue = len(analysis['failed_jobs']) > 0
        
        # Save analysis to file
        with open('/tmp/failure_analysis.json', 'w') as f:
            json.dump(analysis, f, indent=2)
        
        # Set GitHub Actions output
        print(f"::set-output name=should_create_issue::{str(should_create_issue).lower()}")
        
        print(f"Analysis complete. Found {len(analysis['failed_jobs'])} failed jobs.")
        return analysis
        
    except Exception as e:
        print(f"Error analyzing workflow failure: {e}")
        sys.exit(1)


def extract_errors_from_logs(logs):
    """Extract error messages from job logs."""
    errors = []
    
    # Common error patterns
    error_patterns = [
        r'Error:\s*(.+)',
        r'ERROR:\s*(.+)',
        r'FAILED:\s*(.+)',
        r'Exception:\s*(.+)',
        r'❌\s*(.+)',
        r'\[error\]\s*(.+)',
        r'fatal:\s*(.+)',
        r'Traceback \(most recent call last\):',
    ]
    
    lines = logs.split('\n')
    for i, line in enumerate(lines):
        for pattern in error_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # Get context (current line + next few lines)
                context_lines = lines[i:min(i+5, len(lines))]
                errors.append('\n'.join(context_lines))
                break
    
    return errors


def identify_error_patterns(logs):
    """Identify common error patterns that can be auto-fixed."""
    patterns = []
    
    # Common fixable patterns
    pattern_checks = [
        {
            'pattern': r'command not found',
            'type': 'missing_command',
            'fixable': True,
            'suggestion': 'Install missing command or add to PATH'
        },
        {
            'pattern': r'No such file or directory',
            'type': 'missing_file',
            'fixable': True,
            'suggestion': 'Check file paths and ensure files exist'
        },
        {
            'pattern': r'Permission denied',
            'type': 'permission_error',
            'fixable': True,
            'suggestion': 'Add appropriate permissions or use sudo'
        },
        {
            'pattern': r'Module not found|ImportError',
            'type': 'missing_dependency',
            'fixable': True,
            'suggestion': 'Install missing Python dependencies'
        },
        {
            'pattern': r'YAML syntax error|invalid yaml',
            'type': 'yaml_syntax',
            'fixable': True,
            'suggestion': 'Fix YAML syntax errors'
        },
        {
            'pattern': r'timeout|timed out',
            'type': 'timeout',
            'fixable': True,
            'suggestion': 'Increase timeout or optimize slow operations'
        },
        {
            'pattern': r'rate limit|too many requests',
            'type': 'rate_limit',
            'fixable': True,
            'suggestion': 'Add rate limiting or retry logic'
        },
        {
            'pattern': r'connection refused|connection timeout',
            'type': 'connection_error',
            'fixable': False,
            'suggestion': 'Check network connectivity and service availability'
        }
    ]
    
    for check in pattern_checks:
        if re.search(check['pattern'], logs, re.IGNORECASE):
            patterns.append(check)
    
    return patterns


if __name__ == '__main__':
    analyze_workflow_failure()
