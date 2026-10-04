#!/usr/bin/env python3
"""
Script to add ARM64 support to existing workflows

This script analyzes workflows and adds ARM64 testing support where appropriate.
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, List, Any


class WorkflowARM64Updater:
    """Updates workflows to add ARM64 support"""

    # Workflows that should NOT be modified (already have ARM64 or are AMD64-specific)
    SKIP_WORKFLOWS = {
        'arm64-ci.yml',  # Already ARM64-specific
        'multi-arch-ci.yml',  # Already multi-arch
        'multi-arch-test-parity.yml',  # New multi-arch workflow
        'amd64-ci.yml',  # AMD64-specific by design
        'amd64-release.yml',  # AMD64-specific by design
        'amd64-python-package.yml',  # AMD64-specific by design
        'pages.yml',  # GitHub Pages - no need for ARM64
        'docker-arch-tests.yml',  # Already tests architectures
    }

    # Workflows that are high priority for ARM64 support
    HIGH_PRIORITY = {
        'run-tests.yml',
        'daemon-tests.yml',
        'cluster-tests.yml',
        'python-package.yml',
        'lint.yml',
        'security.yml',
        'coverage.yml',
    }

    def __init__(self, workflows_dir: Path):
        self.workflows_dir = workflows_dir
        self.updates = []

    def should_update(self, workflow_name: str) -> bool:
        """Check if workflow should be updated"""
        if workflow_name in self.SKIP_WORKFLOWS:
            return False
        return True

    def analyze_workflow(self, workflow_file: Path) -> Dict[str, Any]:
        """Analyze a workflow file"""
        try:
            with open(workflow_file, 'r') as f:
                content = yaml.safe_load(f)

            info = {
                'name': workflow_file.name,
                'path': workflow_file,
                'has_matrix': False,
                'has_self_hosted': False,
                'has_ubuntu_runner': False,
                'priority': 'high' if workflow_file.name in self.HIGH_PRIORITY else 'medium',
            }

            # Check for matrix strategy
            if 'jobs' in content:
                for job_name, job_config in content['jobs'].items():
                    if 'runs-on' in job_config:
                        runs_on = job_config['runs-on']
                        if 'ubuntu' in str(runs_on):
                            info['has_ubuntu_runner'] = True
                        if 'self-hosted' in str(runs_on):
                            info['has_self_hosted'] = True

                    if 'strategy' in job_config and 'matrix' in job_config['strategy']:
                        info['has_matrix'] = True

            return info
        except Exception as e:
            print(f"Error analyzing {workflow_file.name}: {e}")
            return None

    def generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate recommendations for adding ARM64 support"""
        recommendations = []

        workflow_files = list(self.workflows_dir.glob('*.yml'))

        for workflow_file in workflow_files:
            if not self.should_update(workflow_file.name):
                continue

            info = self.analyze_workflow(workflow_file)
            if not info:
                continue

            if info['has_ubuntu_runner']:
                recommendations.append({
                    'workflow': workflow_file.name,
                    'priority': info['priority'],
                    'approach': 'matrix',
                    'description': f"Add architecture matrix to {workflow_file.name}",
                    'details': {
                        'has_matrix': info['has_matrix'],
                        'suggested_change': 'Add arch: [amd64, arm64] to strategy matrix and use conditional runners',
                    }
                })

        return recommendations

    def print_recommendations(self):
        """Print recommendations for adding ARM64 support"""
        recommendations = self.generate_recommendations()

        print(f"\n{'='*70}")
        print("ARM64 Support Recommendations")
        print(f"{'='*70}\n")

        high_priority = [r for r in recommendations if r['priority'] == 'high']
        medium_priority = [r for r in recommendations if r['priority'] == 'medium']

        if high_priority:
            print("🔴 HIGH PRIORITY WORKFLOWS:")
            for rec in high_priority:
                print(f"\n  📋 {rec['workflow']}")
                print(f"     Approach: {rec['approach']}")
                print(f"     {rec['description']}")
                print(f"     Suggestion: {rec['details']['suggested_change']}")

        if medium_priority:
            print("\n\n🟡 MEDIUM PRIORITY WORKFLOWS:")
            for rec in medium_priority:
                print(f"\n  📋 {rec['workflow']}")
                print(f"     Approach: {rec['approach']}")
                print(f"     Suggestion: {rec['details']['suggested_change']}")

        print(f"\n{'='*70}")
        print(f"Total workflows analyzed: {len(recommendations)}")
        print(f"High priority: {len(high_priority)}")
        print(f"Medium priority: {len(medium_priority)}")
        print(f"{'='*70}\n")

        # Save to file
        output_file = Path(__file__).parent.parent.parent / "data" / "test_results" / "arm64_recommendations.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write("ARM64 Support Recommendations\n")
            f.write("="*70 + "\n\n")
            for rec in recommendations:
                f.write(f"Workflow: {rec['workflow']}\n")
                f.write(f"Priority: {rec['priority']}\n")
                f.write(f"Approach: {rec['approach']}\n")
                f.write(f"Description: {rec['description']}\n")
                f.write(f"Suggestion: {rec['details']['suggested_change']}\n")
                f.write("\n")
        
        print(f"Recommendations saved to: {output_file}\n")


def main():
    """Main function"""
    repo_root = Path(__file__).parent.parent.parent
    workflows_dir = repo_root / ".github" / "workflows"

    if not workflows_dir.exists():
        print(f"❌ Workflows directory not found: {workflows_dir}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print("Analyzing Workflows for ARM64 Support")
    print(f"{'='*70}\n")
    print(f"Workflows directory: {workflows_dir}")

    updater = WorkflowARM64Updater(workflows_dir)
    updater.print_recommendations()


if __name__ == "__main__":
    main()
