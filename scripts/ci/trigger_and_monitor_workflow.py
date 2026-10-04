#!/usr/bin/env python3
"""
GitHub Workflow Trigger and Monitor

This script triggers GitHub workflows and monitors their execution in real-time.
It provides status updates, log streaming, and failure analysis.

Usage:
    # Trigger a specific workflow
    python trigger_and_monitor_workflow.py --workflow daemon-config-tests.yml
    
    # Trigger with specific branch
    python trigger_and_monitor_workflow.py --workflow daemon-config-tests.yml --ref main
    
    # Monitor an existing workflow run
    python trigger_and_monitor_workflow.py --run-id 1234567890
    
    # List recent workflow runs
    python trigger_and_monitor_workflow.py --list --workflow daemon-config-tests.yml
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class WorkflowMonitor:
    """Monitor GitHub workflow execution."""
    
    def __init__(self, repo: str = "endomorphosis/ipfs_kit_py", log_dir: str = "/tmp/workflow_monitor"):
        self.repo = repo
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.start_time = time.time()
        
    def _run_gh_command(self, args: List[str], capture: bool = True) -> tuple[int, str, str]:
        """Run a GitHub CLI command."""
        cmd = ["gh"] + args
        try:
            if capture:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return result.returncode, result.stdout, result.stderr
            else:
                result = subprocess.run(cmd, timeout=60)
                return result.returncode, "", ""
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)
    
    def list_workflows(self) -> List[Dict]:
        """List available workflows."""
        print("📋 Listing workflows...")
        returncode, stdout, stderr = self._run_gh_command([
            "workflow", "list",
            "--repo", self.repo,
            "--json", "name,path,state,id"
        ])
        
        if returncode != 0:
            print(f"❌ Failed to list workflows: {stderr}")
            return []
        
        workflows = json.loads(stdout)
        for wf in workflows:
            status = "✅" if wf.get("state") == "active" else "⚠️"
            print(f"{status} {wf['name']} ({wf['path']})")
        
        return workflows
    
    def list_runs(self, workflow: str, limit: int = 10) -> List[Dict]:
        """List recent workflow runs."""
        print(f"📋 Listing recent runs for {workflow}...")
        
        returncode, stdout, stderr = self._run_gh_command([
            "run", "list",
            "--repo", self.repo,
            "--workflow", workflow,
            "--limit", str(limit),
            "--json", "databaseId,name,status,conclusion,createdAt,updatedAt,headBranch,event"
        ])
        
        if returncode != 0:
            print(f"❌ Failed to list runs: {stderr}")
            return []
        
        runs = json.loads(stdout)
        for run in runs:
            status_icon = {
                "completed": "✅" if run.get("conclusion") == "success" else "❌",
                "in_progress": "🔄",
                "queued": "⏳",
                "waiting": "⏸️"
            }.get(run.get("status"), "•")
            
            conclusion = run.get("conclusion", run.get("status"))
            print(f"{status_icon} Run {run['databaseId']}: {conclusion} - {run['headBranch']} ({run['event']})")
        
        return runs
    
    def trigger_workflow(self, workflow: str, ref: str = "main", inputs: Optional[Dict] = None) -> Optional[int]:
        """Trigger a workflow run."""
        print(f"🚀 Triggering workflow {workflow} on {ref}...")
        
        cmd_args = [
            "workflow", "run", workflow,
            "--repo", self.repo,
            "--ref", ref
        ]
        
        if inputs:
            for key, value in inputs.items():
                cmd_args.extend(["-f", f"{key}={value}"])
        
        returncode, stdout, stderr = self._run_gh_command(cmd_args)
        
        if returncode != 0:
            print(f"❌ Failed to trigger workflow: {stderr}")
            return None
        
        print(f"✅ Workflow triggered successfully")
        
        # Wait a moment for the run to appear
        print("⏳ Waiting for run to start...")
        time.sleep(5)
        
        # Get the most recent run
        runs = self.list_runs(workflow, limit=1)
        if runs:
            run_id = runs[0]["databaseId"]
            print(f"📍 Run ID: {run_id}")
            return run_id
        
        return None
    
    def get_run_status(self, run_id: int) -> Optional[Dict]:
        """Get status of a workflow run."""
        returncode, stdout, stderr = self._run_gh_command([
            "run", "view", str(run_id),
            "--repo", self.repo,
            "--json", "databaseId,name,status,conclusion,createdAt,updatedAt,headBranch,event,jobs,url"
        ])
        
        if returncode != 0:
            print(f"❌ Failed to get run status: {stderr}")
            return None
        
        return json.loads(stdout)
    
    def monitor_run(self, run_id: int, poll_interval: int = 10, show_logs: bool = True):
        """Monitor a workflow run until completion."""
        print(f"👀 Monitoring run {run_id}...")
        print(f"🔗 View in browser: https://github.com/{self.repo}/actions/runs/{run_id}")
        print("")
        
        previous_status = None
        job_statuses = {}
        
        while True:
            run_info = self.get_run_status(run_id)
            if not run_info:
                print("❌ Failed to get run status")
                break
            
            status = run_info["status"]
            conclusion = run_info.get("conclusion")
            
            # Print status change
            if status != previous_status:
                timestamp = datetime.now().strftime("%H:%M:%S")
                if status == "completed":
                    icon = "✅" if conclusion == "success" else "❌"
                    print(f"[{timestamp}] {icon} Run {status}: {conclusion}")
                else:
                    icon = {"in_progress": "🔄", "queued": "⏳", "waiting": "⏸️"}.get(status, "•")
                    print(f"[{timestamp}] {icon} Run {status}")
                previous_status = status
            
            # Monitor jobs
            for job in run_info.get("jobs", []):
                job_id = job["databaseId"]
                job_status = job["status"]
                job_conclusion = job.get("conclusion")
                job_name = job["name"]
                
                previous_job_status = job_statuses.get(job_id)
                current_job_status = f"{job_status}:{job_conclusion}"
                
                if current_job_status != previous_job_status:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    if job_status == "completed":
                        icon = "✅" if job_conclusion == "success" else "❌"
                        print(f"[{timestamp}]   {icon} Job '{job_name}': {job_conclusion}")
                        
                        # Show logs for failed jobs
                        if show_logs and job_conclusion == "failure":
                            print(f"      📄 Fetching logs for failed job...")
                            self._show_job_logs(run_id, job_id, tail_lines=50)
                    else:
                        icon = {"in_progress": "🔄", "queued": "⏳"}.get(job_status, "•")
                        print(f"[{timestamp}]   {icon} Job '{job_name}': {job_status}")
                    
                    job_statuses[job_id] = current_job_status
            
            # Check if completed
            if status == "completed":
                print("")
                print("=" * 60)
                if conclusion == "success":
                    print("✅ Workflow completed successfully!")
                else:
                    print(f"❌ Workflow failed with conclusion: {conclusion}")
                print("=" * 60)
                
                # Generate summary
                self._generate_summary(run_info)
                break
            
            # Wait before next poll
            time.sleep(poll_interval)
    
    def _show_job_logs(self, run_id: int, job_id: int, tail_lines: int = 50):
        """Show logs for a specific job."""
        log_file = self.log_dir / f"job_{job_id}_logs.txt"
        
        # Download logs
        returncode, stdout, stderr = self._run_gh_command([
            "run", "view", str(run_id),
            "--repo", self.repo,
            "--log",
            "--job", str(job_id)
        ])
        
        if returncode == 0:
            log_file.write_text(stdout)
            
            # Show tail of logs
            lines = stdout.split('\n')
            tail = lines[-tail_lines:] if len(lines) > tail_lines else lines
            print("      " + "─" * 50)
            for line in tail:
                if line.strip():
                    print(f"      {line}")
            print("      " + "─" * 50)
            print(f"      💾 Full logs saved to: {log_file}")
        else:
            print(f"      ⚠️ Could not fetch logs: {stderr}")
    
    def _generate_summary(self, run_info: Dict):
        """Generate a summary report of the workflow run."""
        report_file = self.log_dir / f"run_{run_info['databaseId']}_summary.md"
        
        with open(report_file, "w") as f:
            f.write(f"# Workflow Run Summary\n\n")
            f.write(f"**Run ID**: {run_info['databaseId']}\n")
            f.write(f"**Workflow**: {run_info['name']}\n")
            f.write(f"**Status**: {run_info['status']}\n")
            f.write(f"**Conclusion**: {run_info.get('conclusion', 'N/A')}\n")
            f.write(f"**Branch**: {run_info['headBranch']}\n")
            f.write(f"**Event**: {run_info['event']}\n")
            f.write(f"**URL**: {run_info['url']}\n")
            f.write(f"**Created**: {run_info['createdAt']}\n")
            f.write(f"**Updated**: {run_info['updatedAt']}\n\n")
            
            f.write(f"## Jobs\n\n")
            for job in run_info.get("jobs", []):
                icon = "✅" if job.get("conclusion") == "success" else "❌"
                f.write(f"- {icon} **{job['name']}**: {job.get('conclusion', job['status'])}\n")
            
            f.write(f"\n## Monitoring Metrics\n\n")
            duration = time.time() - self.start_time
            f.write(f"- **Monitoring Duration**: {duration:.1f}s\n")
            f.write(f"- **Report Generated**: {datetime.now().isoformat()}\n")
        
        print(f"\n📊 Summary report saved to: {report_file}")
        
        # Also save JSON
        json_file = self.log_dir / f"run_{run_info['databaseId']}_data.json"
        with open(json_file, "w") as f:
            json.dump(run_info, f, indent=2)
        print(f"📊 Full data saved to: {json_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Trigger and monitor GitHub workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available workflows
  python trigger_and_monitor_workflow.py --list-workflows
  
  # List recent runs for a workflow
  python trigger_and_monitor_workflow.py --list --workflow daemon-config-tests.yml
  
  # Trigger a workflow and monitor it
  python trigger_and_monitor_workflow.py --workflow daemon-config-tests.yml --trigger --monitor
  
  # Monitor an existing run
  python trigger_and_monitor_workflow.py --run-id 1234567890 --monitor
  
  # Trigger with specific branch
  python trigger_and_monitor_workflow.py --workflow daemon-config-tests.yml --ref develop --trigger --monitor
        """
    )
    
    parser.add_argument("--repo", default="endomorphosis/ipfs_kit_py",
                       help="GitHub repository (default: endomorphosis/ipfs_kit_py)")
    parser.add_argument("--workflow", help="Workflow file name (e.g., daemon-config-tests.yml)")
    parser.add_argument("--ref", default="main", help="Git ref (branch/tag) to trigger on")
    parser.add_argument("--run-id", type=int, help="Workflow run ID to monitor")
    parser.add_argument("--list-workflows", action="store_true", help="List available workflows")
    parser.add_argument("--list", action="store_true", help="List recent workflow runs")
    parser.add_argument("--trigger", action="store_true", help="Trigger the workflow")
    parser.add_argument("--monitor", action="store_true", help="Monitor the workflow run")
    parser.add_argument("--poll-interval", type=int, default=10,
                       help="Polling interval in seconds (default: 10)")
    parser.add_argument("--no-logs", action="store_true", help="Don't show job logs")
    parser.add_argument("--log-dir", default="/tmp/workflow_monitor",
                       help="Directory for logs and reports")
    
    args = parser.parse_args()
    
    # Check if gh CLI is available
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ GitHub CLI (gh) is not installed or not in PATH")
        print("   Install from: https://cli.github.com/")
        sys.exit(1)
    
    monitor = WorkflowMonitor(repo=args.repo, log_dir=args.log_dir)
    
    # Handle commands
    if args.list_workflows:
        monitor.list_workflows()
        return
    
    if args.list:
        if not args.workflow:
            print("❌ --workflow is required with --list")
            sys.exit(1)
        monitor.list_runs(args.workflow)
        return
    
    run_id = args.run_id
    
    # Trigger workflow if requested
    if args.trigger:
        if not args.workflow:
            print("❌ --workflow is required with --trigger")
            sys.exit(1)
        run_id = monitor.trigger_workflow(args.workflow, args.ref)
        if not run_id:
            sys.exit(1)
    
    # Monitor workflow if requested
    if args.monitor:
        if not run_id:
            print("❌ Either --run-id or --trigger is required with --monitor")
            sys.exit(1)
        monitor.monitor_run(run_id, poll_interval=args.poll_interval, show_logs=not args.no_logs)
        return
    
    # If no action specified, show help
    if not (args.list_workflows or args.list or args.trigger or args.monitor):
        parser.print_help()


if __name__ == "__main__":
    main()
