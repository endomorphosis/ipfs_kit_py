#!/usr/bin/env python3
"""
Analyze GitHub Actions workflows to determine which ones can run and which are blocked.
"""

import yaml
import os
from pathlib import Path
from collections import defaultdict

def analyze_workflows():
    workflows_dir = Path(".github/workflows")
    
    if not workflows_dir.exists():
        print("❌ No .github/workflows directory found")
        return
    
    results = {
        'github_hosted': [],
        'self_hosted': [],
        'mixed': [],
        'disabled': [],
        'errors': []
    }
    
    for workflow_file in sorted(workflows_dir.glob("*.yml")):
        try:
            with open(workflow_file, 'r') as f:
                content = yaml.safe_load(f)
            
            if not content:
                continue
                
            workflow_name = content.get('name', workflow_file.stem)
            
            # Check if workflow is disabled (check both 'on' and 'true' for YAML boolean true)
            on_config = content.get('on') or content.get(True)
            if on_config is None:
                results['disabled'].append({
                    'file': workflow_file.name,
                    'name': workflow_name,
                    'reason': 'No triggers defined'
                })
                continue
            
            # Analyze jobs
            jobs = content.get('jobs', {})
            if not jobs:
                results['disabled'].append({
                    'file': workflow_file.name,
                    'name': workflow_name,
                    'reason': 'No jobs defined'
                })
                continue
            
            runner_types = set()
            job_details = []
            
            for job_name, job_config in jobs.items():
                runs_on = job_config.get('runs-on', '')
                
                if isinstance(runs_on, str):
                    runner_str = runs_on
                elif isinstance(runs_on, list):
                    runner_str = ', '.join(runs_on)
                else:
                    runner_str = str(runs_on)
                
                job_details.append({
                    'job': job_name,
                    'runs_on': runner_str
                })
                
                # Categorize runner type
                if 'self-hosted' in runner_str.lower():
                    runner_types.add('self-hosted')
                elif 'ubuntu' in runner_str.lower() or 'macos' in runner_str.lower() or 'windows' in runner_str.lower():
                    runner_types.add('github-hosted')
                elif '${{' in runner_str:
                    runner_types.add('matrix')
            
            # Determine triggers
            if isinstance(on_config, dict):
                triggers = list(on_config.keys())
            elif isinstance(on_config, list):
                triggers = on_config
            else:
                triggers = [str(on_config)]
            
            workflow_info = {
                'file': workflow_file.name,
                'name': workflow_name,
                'triggers': triggers,
                'jobs': job_details
            }
            
            # Categorize workflow
            if len(runner_types) == 1:
                if 'self-hosted' in runner_types:
                    results['self_hosted'].append(workflow_info)
                elif 'github-hosted' in runner_types:
                    results['github_hosted'].append(workflow_info)
                elif 'matrix' in runner_types:
                    results['mixed'].append(workflow_info)
            elif len(runner_types) > 1:
                results['mixed'].append(workflow_info)
            
        except Exception as e:
            results['errors'].append({
                'file': workflow_file.name,
                'error': str(e)
            })
    
    return results

def print_results(results):
    print("=" * 80)
    print("🔍 GITHUB ACTIONS WORKFLOWS ANALYSIS")
    print("=" * 80)
    print()
    
    # GitHub-hosted workflows (WILL RUN)
    print("✅ WORKFLOWS THAT WILL RUN (GitHub-hosted runners)")
    print("-" * 80)
    if results['github_hosted']:
        for wf in results['github_hosted']:
            print(f"\n📄 {wf['name']}")
            print(f"   File: {wf['file']}")
            print(f"   Triggers: {', '.join(wf['triggers'])}")
            print(f"   Jobs ({len(wf['jobs'])}):")
            for job in wf['jobs']:
                print(f"     - {job['job']}: {job['runs_on']}")
    else:
        print("   (none)")
    
    print()
    print()
    
    # Self-hosted workflows (WON'T RUN)
    print("❌ WORKFLOWS THAT WON'T RUN (requires self-hosted runners)")
    print("-" * 80)
    if results['self_hosted']:
        for wf in results['self_hosted']:
            print(f"\n📄 {wf['name']}")
            print(f"   File: {wf['file']}")
            print(f"   Triggers: {', '.join(wf['triggers'])}")
            print(f"   Jobs ({len(wf['jobs'])}):")
            for job in wf['jobs']:
                print(f"     - {job['job']}: {job['runs_on']}")
            print(f"   ⚠️  STATUS: Will be queued indefinitely (no runners available)")
    else:
        print("   (none)")
    
    print()
    print()
    
    # Mixed workflows (PARTIALLY RUN)
    print("⚠️  WORKFLOWS WITH MIXED RUNNERS")
    print("-" * 80)
    if results['mixed']:
        for wf in results['mixed']:
            print(f"\n📄 {wf['name']}")
            print(f"   File: {wf['file']}")
            print(f"   Triggers: {', '.join(wf['triggers'])}")
            print(f"   Jobs ({len(wf['jobs'])}):")
            for job in wf['jobs']:
                if 'self-hosted' in job['runs_on'].lower():
                    status = "❌ Won't run"
                else:
                    status = "✅ Will run"
                print(f"     {status} - {job['job']}: {job['runs_on']}")
    else:
        print("   (none)")
    
    print()
    print()
    
    # Disabled workflows
    if results['disabled']:
        print("🚫 DISABLED WORKFLOWS")
        print("-" * 80)
        for wf in results['disabled']:
            print(f"   - {wf['name']} ({wf['file']}): {wf['reason']}")
        print()
        print()
    
    # Errors
    if results['errors']:
        print("⚠️  ERRORS")
        print("-" * 80)
        for err in results['errors']:
            print(f"   - {err['file']}: {err['error']}")
        print()
        print()
    
    # Summary
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    total_workflows = len(results['github_hosted']) + len(results['self_hosted']) + len(results['mixed'])
    print(f"Total workflows: {total_workflows}")
    print(f"  ✅ Fully functional (GitHub-hosted): {len(results['github_hosted'])}")
    print(f"  ❌ Blocked (self-hosted only): {len(results['self_hosted'])}")
    print(f"  ⚠️  Partially working (mixed): {len(results['mixed'])}")
    print(f"  🚫 Disabled: {len(results['disabled'])}")
    if results['errors']:
        print(f"  ⚠️  Parse errors: {len(results['errors'])}")
    
    print()
    print("💡 RECOMMENDATION:")
    if results['self_hosted'] or results['mixed']:
        print("   You have workflows configured for self-hosted runners that won't run.")
        print("   Options:")
        print("   1. Set up self-hosted runners (use ./scripts/setup-github-runner.sh)")
        print("   2. Convert workflows to use GitHub-hosted runners (ubuntu-latest)")
        print("   3. Disable/delete workflows you don't need")
    else:
        print("   All workflows are using GitHub-hosted runners. Everything should work!")
    print("=" * 80)

if __name__ == "__main__":
    results = analyze_workflows()
    print_results(results)
