# GitHub Actions Workflow and Installation Monitoring Scripts

This directory contains scripts for monitoring GitHub Actions workflows and first-time package installations.

## Scripts Overview

### 1. `trigger_and_monitor_workflow.py`

Trigger and monitor GitHub Actions workflows in real-time.

**Features:**
- List available workflows
- List recent workflow runs
- Trigger workflows on specific branches
- Monitor workflow execution with real-time updates
- Display job statuses and logs for failed jobs
- Generate summary reports with metrics
- Save logs and detailed JSON data

**Requirements:**
- GitHub CLI (`gh`) must be installed and authenticated
- Requires appropriate repository permissions

**Usage Examples:**

```bash
# List all available workflows
python trigger_and_monitor_workflow.py --list-workflows

# List recent runs for a specific workflow
python trigger_and_monitor_workflow.py --list --workflow daemon-config-tests.yml

# Trigger a workflow and monitor its execution
python trigger_and_monitor_workflow.py --workflow daemon-config-tests.yml --trigger --monitor

# Monitor an existing workflow run
python trigger_and_monitor_workflow.py --run-id 1234567890 --monitor

# Trigger on a specific branch
python trigger_and_monitor_workflow.py --workflow arm64-ci.yml --ref develop --trigger --monitor

# Monitor without showing logs (faster)
python trigger_and_monitor_workflow.py --run-id 1234567890 --monitor --no-logs
```

**Output:**
- Real-time console updates with emoji indicators
- Logs saved to `/tmp/workflow_monitor/` by default
- Summary markdown reports
- Full workflow data in JSON format
- Job logs for failed jobs

**Status Indicators:**
- 🚀 Workflow triggered
- 🔄 In progress
- ⏳ Queued
- ⏸️ Waiting
- ✅ Success
- ❌ Failed
- ⚠️ Warning

### 2. `monitor_first_install.py`

Monitor the installation and configuration process when the package is installed for the first time.

**Features:**
- Monitor pip installation with detailed progress
- Pre-installation system checks (Python, pip, build tools)
- Post-installation verification
- Configuration file detection
- Binary availability checks
- Package import verification
- Comprehensive reporting with metrics
- Error and warning tracking

**Usage Examples:**

```bash
# Monitor a fresh installation
python monitor_first_install.py --command "pip install ipfs-kit-py"

# Monitor local development installation
python monitor_first_install.py --command "pip install -e ."

# Monitor with specific Python version
python monitor_first_install.py --command "pip install ipfs-kit-py" --python python3.11

# Only verify an existing installation
python monitor_first_install.py --verify

# Only check configuration files
python monitor_first_install.py --config-only
```

**Output:**
- Real-time installation progress with emoji indicators
- System information (CPU, memory, disk, architecture)
- Pre/post installation checks
- Configuration file detection
- Binary and package verification
- Detailed markdown report
- Metrics JSON file
- Installation output logs

**Checks Performed:**
- Python version and location
- pip availability
- Build tools (gcc, git, make)
- Package importability
- CLI tool availability
- Configuration directories
- Configuration files
- Daemon configs

### 3. Integration with Existing Scripts

These scripts complement the existing monitoring infrastructure:

- `monitor_arm64_installation.py` - ARM64-specific dependency monitoring
- `verify_arm64_dependencies.py` - ARM64 dependency verification
- `installation_wrapper.sh` - Bash wrapper for installation commands
- `demo_monitoring.sh` - Demonstration of monitoring tools

## GitHub Actions Integration

### Workflow Monitoring in CI

Add to your GitHub Actions workflow:

```yaml
jobs:
  trigger-and-monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Trigger workflow
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          python scripts/ci/trigger_and_monitor_workflow.py \
            --workflow daemon-config-tests.yml \
            --trigger \
            --monitor
      
      - name: Upload monitoring logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: workflow-monitoring-logs
          path: /tmp/workflow_monitor/
```

### Installation Monitoring in CI

Add to your GitHub Actions workflow:

```yaml
jobs:
  test-installation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Monitor installation
        run: |
          python scripts/ci/monitor_first_install.py \
            --command "pip install -e .[dev,full]"
      
      - name: Upload installation logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: installation-logs
          path: /tmp/install_monitor/
```

## Local Testing

### Test Workflow Monitor (requires GitHub authentication)

```bash
# Set up GitHub CLI authentication first
gh auth login

# List workflows
python scripts/ci/trigger_and_monitor_workflow.py --list-workflows

# List recent runs
python scripts/ci/trigger_and_monitor_workflow.py --list --workflow daemon-config-tests.yml
```

### Test Installation Monitor

```bash
# Check configuration only (no installation)
python scripts/ci/monitor_first_install.py --config-only

# Verify existing installation
python scripts/ci/monitor_first_install.py --verify

# Monitor a real installation (in a clean environment)
python scripts/ci/monitor_first_install.py --command "pip install ipfs-kit-py"
```

## Output Locations

### Workflow Monitor
- **Default directory**: `/tmp/workflow_monitor/`
- **Files generated**:
  - `job_<ID>_logs.txt` - Individual job logs
  - `run_<ID>_summary.md` - Workflow run summary
  - `run_<ID>_data.json` - Complete workflow data

### Installation Monitor
- **Default directory**: `/tmp/install_monitor/`
- **Files generated**:
  - `installation_output.log` - Raw installation output
  - `installation_report.md` - Human-readable report
  - `installation_metrics.json` - Structured metrics data

## Troubleshooting

### Workflow Monitor Issues

**Problem**: "gh: To use GitHub CLI in a GitHub Actions workflow..."
**Solution**: Set the `GH_TOKEN` environment variable:
```bash
export GH_TOKEN="your_github_token"
# or in GitHub Actions:
env:
  GH_TOKEN: ${{ github.token }}
```

**Problem**: "Failed to list workflows"
**Solution**: Ensure `gh` CLI is installed and authenticated:
```bash
gh auth login
gh auth status
```

### Installation Monitor Issues

**Problem**: "Command timed out"
**Solution**: Increase timeout in the script or run with better network connection

**Problem**: Package not found after installation
**Solution**: Check if the package was installed in a different Python environment

## Advanced Usage

### Custom Log Directories

```bash
# Workflow monitor
python trigger_and_monitor_workflow.py \
  --workflow daemon-config-tests.yml \
  --trigger --monitor \
  --log-dir /custom/path

# Installation monitor
python monitor_first_install.py \
  --command "pip install ipfs-kit-py" \
  --log-dir /custom/path
```

### Scripting and Automation

```bash
#!/bin/bash
# Automated workflow trigger and monitor
WORKFLOW="daemon-config-tests.yml"
REPO="endomorphosis/ipfs_kit_py"

# Trigger and monitor
python scripts/ci/trigger_and_monitor_workflow.py \
  --repo "$REPO" \
  --workflow "$WORKFLOW" \
  --trigger \
  --monitor \
  --poll-interval 15

# Check if successful
if [ $? -eq 0 ]; then
  echo "✅ Workflow completed successfully"
else
  echo "❌ Workflow failed"
  exit 1
fi
```

## Best Practices

1. **Always authenticate** before using workflow monitor
2. **Use appropriate poll intervals** (default: 10s) to avoid rate limits
3. **Save artifacts** in GitHub Actions for post-mortem analysis
4. **Review logs** for failed workflows to identify issues quickly
5. **Test locally first** before integrating into CI/CD
6. **Use custom log directories** in production to organize outputs
7. **Monitor regularly** to catch issues early in development cycle

## Related Documentation

- [ARM64 Monitoring Guide](../../ARM64_MONITORING_GUIDE.md)
- [ARM64 Monitoring Implementation](../../ARM64_MONITORING_IMPLEMENTATION.md)
- [GitHub Actions Workflows](../../.github/workflows/README.md)
- [CI/CD Documentation](../README.md)
