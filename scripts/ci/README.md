# ARM64 Dependency Installation Monitoring

This directory contains monitoring and verification scripts for ARM64 dependency installation in GitHub Actions workflows.

## Overview

The monitoring system provides:

1. **Real-time progress tracking** - Monitor installation steps as they execute
2. **Detailed logging** - Capture stdout, stderr, and combined logs for all operations
3. **System metrics** - Collect CPU, memory, disk, and architecture information
4. **Error detection** - Identify and report installation failures
5. **GitHub Actions integration** - Automatically add results to workflow summaries
6. **Artifact generation** - Create downloadable reports and logs

## Scripts

### monitor_arm64_installation.py

Main monitoring script that tracks ARM64 dependency installation.

**Features:**
- Collects system information (architecture, CPU, memory)
- Monitors command execution with timeouts
- Checks binary and Python package installations
- Generates detailed Markdown reports
- Integrates with GitHub Actions summary

**Usage:**
```bash
python scripts/ci/monitor_arm64_installation.py
```

**Output:**
- `/tmp/arm64_monitor/arm64_monitor_report.md` - Detailed report
- `/tmp/arm64_monitor/arm64_monitor_metrics.json` - Machine-readable metrics
- GitHub Actions step summary (if running in Actions)

### verify_arm64_dependencies.py

Verification script that checks for required and optional dependencies.

**Features:**
- Verifies required build tools (gcc, g++, make, git)
- Checks optional tools (go, ipfs, lotus, lassie)
- Validates Python packages
- Reports missing dependencies
- Generates summary statistics

**Usage:**
```bash
python scripts/ci/verify_arm64_dependencies.py
```

**Exit Codes:**
- `0` - All required dependencies found
- `1` - Some required dependencies missing

### installation_wrapper.sh

Bash wrapper script that adds monitoring to any installation command.

**Features:**
- Captures stdout and stderr separately
- Creates timestamped logs
- Collects system metrics before and after execution
- Adds results to GitHub Actions summary
- Supports any command or script

**Usage:**
```bash
./scripts/ci/installation_wrapper.sh <script_name> <command> [args...]
```

**Example:**
```bash
./scripts/ci/installation_wrapper.sh ipfs_install pip install ipfs-kit-py
```

**Output Files:**
- `/tmp/arm64_install_logs/<script>_<timestamp>_stdout.log`
- `/tmp/arm64_install_logs/<script>_<timestamp>_stderr.log`
- `/tmp/arm64_install_logs/<script>_<timestamp>_combined.log`
- `/tmp/arm64_install_logs/<script>_<timestamp>_metrics.json`

## GitHub Actions Integration

### Workflow Setup

Add the monitoring scripts to your ARM64 CI workflow:

```yaml
- name: Initialize ARM64 monitoring
  run: |
    mkdir -p /tmp/arm64_monitor
    mkdir -p /tmp/arm64_install_logs
    python scripts/ci/monitor_arm64_installation.py

- name: Verify pre-installation dependencies
  run: |
    python scripts/ci/verify_arm64_dependencies.py || echo "Verification completed with warnings"

- name: Install dependencies with monitoring
  run: |
    ./scripts/ci/installation_wrapper.sh system_deps \
      sudo apt-get install -y build-essential

- name: Upload monitoring logs
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: arm64-monitoring-logs
    path: |
      /tmp/arm64_monitor/
      /tmp/arm64_install_logs/
```

### Viewing Results

**During Workflow Execution:**
- Check the workflow logs for real-time monitoring output
- Look for colored status indicators (✅, ❌, ⚠️)

**After Workflow Completion:**
- View the GitHub Actions Summary for high-level results
- Download artifacts for detailed logs and metrics
- Review JSON metrics files for programmatic analysis

## Log Files

### Standard Logs

Each monitored installation creates multiple log files:

- `*_stdout.log` - Standard output from the command
- `*_stderr.log` - Error output from the command
- `*_combined.log` - Combined stdout/stderr with timestamps
- `*_metrics.json` - System metrics and execution metadata

### Report Files

- `arm64_monitor_report.md` - Human-readable monitoring report
- `arm64_monitor_metrics.json` - Machine-readable metrics
- `dependency_verification.json` - Dependency check results

## Troubleshooting

### Missing Dependencies

If the verification script reports missing dependencies:

1. Check the verification output for specific missing tools
2. Install required dependencies before running main installation
3. Use the installation wrapper to monitor the dependency installation

### Installation Failures

If an installation fails:

1. Check the `*_stderr.log` for error messages
2. Review the `*_combined.log` for full context
3. Examine the `*_metrics.json` for system state
4. Look at the GitHub Actions summary for quick diagnostics

### Log Access

If logs are not generated:

1. Ensure log directories exist: `/tmp/arm64_monitor`, `/tmp/arm64_install_logs`
2. Check file permissions
3. Verify the scripts are executable (`chmod +x`)
4. Review workflow permissions for artifact uploads

## Best Practices

1. **Run verification before and after installation** - Catch dependency issues early
2. **Use the installation wrapper for critical steps** - Get detailed logs for debugging
3. **Upload artifacts with retention** - Keep logs available for troubleshooting
4. **Check GitHub Actions summaries** - Quick overview of installation status
5. **Monitor disk space** - ARM64 builds can consume significant space
6. **Set appropriate timeouts** - Some installations take longer on ARM64

## Environment Variables

- `LOG_DIR` - Override default log directory (default: `/tmp/arm64_install_logs`)
- `GITHUB_STEP_SUMMARY` - Path to GitHub Actions summary file (set by Actions)
- `GITHUB_ACTIONS` - Indicates running in GitHub Actions (set by Actions)

## Example Workflow

Complete example of monitoring ARM64 installation:

```yaml
jobs:
  test-arm64:
    runs-on: [self-hosted, arm64]
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up monitoring
      run: |
        mkdir -p /tmp/arm64_monitor /tmp/arm64_install_logs
        python scripts/ci/monitor_arm64_installation.py
    
    - name: Verify initial state
      run: python scripts/ci/verify_arm64_dependencies.py || true
    
    - name: Install system dependencies
      run: |
        ./scripts/ci/installation_wrapper.sh system_deps \
          sudo apt-get install -y build-essential golang-go
    
    - name: Install Python packages
      run: |
        ./scripts/ci/installation_wrapper.sh python_deps \
          pip install -r requirements.txt
    
    - name: Verify final state
      run: python scripts/ci/verify_arm64_dependencies.py
    
    - name: Upload logs
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: monitoring-logs
        path: |
          /tmp/arm64_monitor/
          /tmp/arm64_install_logs/
```

## Contributing

When adding new monitoring features:

1. Follow the existing logging format (timestamp, status, details)
2. Use consistent status indicators (✅, ❌, ⚠️, ℹ️)
3. Update this README with new functionality
4. Add error handling for all external commands
5. Test on actual ARM64 hardware when possible

## License

See the main repository LICENSE file.
