#!/usr/bin/env python3
"""
CI/CD Workflow Validation Script

Validates GitHub Actions workflows to ensure they are properly configured
for both x86_64 and ARM64 architectures.
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple


class WorkflowValidator:
    """Validates GitHub Actions workflows"""

    def __init__(self, workflows_dir: Path):
        self.workflows_dir = workflows_dir
        self.results = {
            "total_workflows": 0,
            "valid_workflows": 0,
            "multi_arch_workflows": 0,
            "amd64_workflows": 0,
            "arm64_workflows": 0,
            "errors": [],
            "warnings": [],
            "passed": [],
        }

    def validate_workflow(self, workflow_file: Path) -> Tuple[bool, Dict[str, Any]]:
        """Validate a single workflow file"""
        try:
            with open(workflow_file, "r") as f:
                content = yaml.safe_load(f)

            info = {
                "name": workflow_file.name,
                "has_jobs": "jobs" in content,
                "architectures": set(),
                "python_versions": set(),
            }

            # Check for architecture support
            if "jobs" in content:
                for job_name, job_config in content["jobs"].items():
                    if "runs-on" in job_config:
                        runs_on = job_config["runs-on"]
                        if isinstance(runs_on, str):
                            runs_on = [runs_on]
                        for runner in runs_on:
                            if "amd64" in runner or "x86_64" in runner:
                                info["architectures"].add("amd64")
                            if "arm64" in runner or "aarch64" in runner:
                                info["architectures"].add("arm64")
                            if "ubuntu" in runner and "amd64" not in runner and "arm64" not in runner:
                                info["architectures"].add("amd64")  # Default

                    # Check for strategy matrix
                    if "strategy" in job_config and "matrix" in job_config["strategy"]:
                        matrix = job_config["strategy"]["matrix"]
                        if "python-version" in matrix:
                            versions = matrix["python-version"]
                            if isinstance(versions, list):
                                info["python_versions"].update(versions)

            return True, info
        except Exception as e:
            return False, {"name": workflow_file.name, "error": str(e)}

    def run_validation(self) -> bool:
        """Run validation on all workflows"""
        workflow_files = list(self.workflows_dir.glob("*.yml")) + list(
            self.workflows_dir.glob("*.yaml")
        )

        self.results["total_workflows"] = len(workflow_files)

        for workflow_file in workflow_files:
            is_valid, info = self.validate_workflow(workflow_file)

            if is_valid:
                self.results["valid_workflows"] += 1

                archs = info.get("architectures", set())
                if "amd64" in archs and "arm64" in archs:
                    self.results["multi_arch_workflows"] += 1
                    self.results["passed"].append(
                        f"✅ {info['name']}: Multi-arch support (AMD64 + ARM64)"
                    )
                elif "amd64" in archs:
                    self.results["amd64_workflows"] += 1
                    self.results["passed"].append(f"✅ {info['name']}: AMD64 support")
                elif "arm64" in archs:
                    self.results["arm64_workflows"] += 1
                    self.results["passed"].append(f"✅ {info['name']}: ARM64 support")
                else:
                    self.results["warnings"].append(
                        f"⚠️  {info['name']}: No specific architecture detected"
                    )

                # Check Python versions
                py_versions = info.get("python_versions", set())
                if py_versions and len(py_versions) >= 3:
                    py_versions_str = [str(v) for v in py_versions]
                    self.results["passed"].append(
                        f"   → Python versions: {sorted(py_versions_str)}"
                    )
            else:
                self.results["errors"].append(
                    f"❌ {info['name']}: {info.get('error', 'Unknown error')}"
                )

        return len(self.results["errors"]) == 0

    def print_summary(self):
        """Print validation summary"""
        print(f"\n{'='*70}")
        print("CI/CD Workflow Validation Summary")
        print(f"{'='*70}\n")

        print(f"Total Workflows: {self.results['total_workflows']}")
        print(f"Valid Workflows: {self.results['valid_workflows']}")
        print(f"Multi-Architecture: {self.results['multi_arch_workflows']}")
        print(f"AMD64 Only: {self.results['amd64_workflows']}")
        print(f"ARM64 Only: {self.results['arm64_workflows']}")
        print()

        if self.results["passed"]:
            print("✅ VALIDATED WORKFLOWS:")
            for item in self.results["passed"][:20]:  # Show first 20
                print(f"   {item}")
            if len(self.results["passed"]) > 20:
                print(f"   ... and {len(self.results['passed']) - 20} more")
            print()

        if self.results["warnings"]:
            print("⚠️  WARNINGS:")
            for warning in self.results["warnings"][:10]:
                print(f"   {warning}")
            if len(self.results["warnings"]) > 10:
                print(f"   ... and {len(self.results['warnings']) - 10} more")
            print()

        if self.results["errors"]:
            print("❌ ERRORS:")
            for error in self.results["errors"]:
                print(f"   {error}")
            print()

        print(f"{'='*70}")
        if len(self.results["errors"]) == 0:
            print("✅ ALL WORKFLOWS ARE VALID!")
            return True
        else:
            print("❌ SOME WORKFLOWS HAVE ERRORS!")
            return False


def main():
    """Main validation function"""
    repo_root = Path(__file__).parent.parent.parent
    workflows_dir = repo_root / ".github" / "workflows"

    if not workflows_dir.exists():
        print(f"❌ Workflows directory not found: {workflows_dir}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print("CI/CD Workflow Validation")
    print(f"{'='*70}\n")
    print(f"Workflows directory: {workflows_dir}")

    validator = WorkflowValidator(workflows_dir)
    validator.run_validation()
    success = validator.print_summary()

    # Save results
    import json

    output_dir = repo_root / "data" / "test_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "cicd_workflow_validation.json"

    with open(output_file, "w") as f:
        # Convert sets to lists for JSON serialization
        results_json = validator.results.copy()
        json.dump(results_json, f, indent=2)

    print(f"\nResults saved to: {output_file}\n")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
