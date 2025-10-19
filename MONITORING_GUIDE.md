# GitHub Actions and Installation Monitoring Guide

This guide provides comprehensive documentation for monitoring GitHub Actions workflows and package installations in the `ipfs_kit_py` repository.

## Overview

The repository includes three complementary monitoring systems:

1. **GitHub Workflow Monitoring** - Trigger and monitor workflow runs in real-time
2. **Installation Monitoring** - Track first-time package installation and configuration
3. **ARM64 Dependency Monitoring** - Specialized monitoring for ARM64 builds

## Quick Start

### 1. Monitor GitHub Workflows

```bash
# List available workflows
python scripts/ci/trigger_and_monitor_workflow.py --list-workflows

# Trigger and monitor a workflow
python scripts/ci/trigger_and_monitor_workflow.py \
  --workflow daemon-config-tests.yml \
  --trigger --monitor

# Monitor an existing workflow run
python scripts/ci/trigger_and_monitor_workflow.py \
  --run-id 1234567890 --monitor
```

**Prerequisites:**
- GitHub CLI (`gh`) installed and authenticated
- Appropriate repository permissions

### 2. Monitor Package Installation

```bash
# Monitor a fresh installation
python scripts/ci/monitor_first_install.py \
  --command "pip install ipfs-kit-py"

# Verify existing installation
python scripts/ci/monitor_first_install.py --verify

# Check configuration only
python scripts/ci/monitor_first_install.py --config-only
```

### 3. Monitor ARM64 Dependencies

```bash
# Initialize ARM64 monitoring
python scripts/ci/monitor_arm64_installation.py

# Verify ARM64 dependencies
python scripts/ci/verify_arm64_dependencies.py

# Wrap installation with monitoring
./scripts/ci/installation_wrapper.sh system_deps \
  sudo apt-get install -y build-essential
```

## Demo Scripts

### Run Complete Demo

```bash
# Comprehensive demo of all monitoring tools
./scripts/ci/demo_workflow_monitoring.sh
```

This will demonstrate:
- Workflow listing and status checking
- Installation verification
- Configuration checking
- Artifact generation

### Run ARM64 Monitoring Demo

```bash
# ARM64-specific monitoring demo
./scripts/ci/demo_monitoring.sh
```

## Features

### Workflow Monitoring Features

- ✅ List all available workflows in the repository
- ✅ List recent workflow runs with status
- ✅ Trigger workflows on specific branches or refs
- ✅ Real-time monitoring of workflow execution
- ✅ Job-level status tracking
- ✅ Automatic log fetching for failed jobs
- ✅ Generate comprehensive summary reports
- ✅ Save detailed JSON metrics
- ✅ Export logs for troubleshooting

### Installation Monitoring Features

- ✅ Monitor pip installation with detailed progress
- ✅ Pre-installation system checks (Python, pip, build tools)
- ✅ Post-installation verification
- ✅ Configuration file detection and validation
- ✅ Binary availability checks (CLI tools, compilers)
- ✅ Package import verification
- ✅ Comprehensive reporting with metrics
- ✅ Error and warning tracking
- ✅ System information collection

### ARM64 Monitoring Features

- ✅ ARM64 architecture detection
- ✅ Build tool verification (gcc, go, make)
- ✅ Dependency installation tracking
- ✅ Real-time progress updates
- ✅ System metrics collection
- ✅ GitHub Actions integration
- ✅ Artifact generation for CI/CD

## GitHub Actions Integration

### Workflow Monitoring in CI

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
            --trigger --monitor \
            --poll-interval 15
      
      - name: Upload monitoring logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: workflow-monitoring-logs
          path: /tmp/workflow_monitor/
          retention-days: 7
```

### Installation Monitoring in CI

```yaml
jobs:
  test-installation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Monitor installation
        run: |
          python scripts/ci/monitor_first_install.py \
            --command "pip install -e .[dev,full]"
      
      - name: Upload installation logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: installation-monitoring-logs
          path: /tmp/install_monitor/
          retention-days: 7
```

### ARM64 Monitoring in CI

```yaml
jobs:
  test-arm64:
    runs-on: [self-hosted, arm64]
    steps:
      - uses: actions/checkout@v4
      
      - name: Initialize monitoring
        run: |
          mkdir -p /tmp/arm64_monitor /tmp/arm64_install_logs
          python scripts/ci/monitor_arm64_installation.py
      
      - name: Verify pre-installation
        run: python scripts/ci/verify_arm64_dependencies.py || true
      
      - name: Install with monitoring
        run: |
          ./scripts/ci/installation_wrapper.sh system_deps \
            sudo apt-get install -y build-essential golang-go
      
      - name: Verify post-installation
        run: python scripts/ci/verify_arm64_dependencies.py
      
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: arm64-monitoring-logs
          path: |
            /tmp/arm64_monitor/
            /tmp/arm64_install_logs/
          retention-days: 7
```

## Output and Artifacts

### Workflow Monitor Output

**Location:** `/tmp/workflow_monitor/` (configurable with `--log-dir`)

**Files:**
- `job_<ID>_logs.txt` - Logs from individual jobs
- `run_<ID>_summary.md` - Human-readable workflow summary
- `run_<ID>_data.json` - Complete workflow data in JSON format

**Console Output:**
- Real-time status updates with emoji indicators
- Job progress tracking
- Failed job log excerpts
- Summary statistics

### Installation Monitor Output

**Location:** `/tmp/install_monitor/` (configurable with `--log-dir`)

**Files:**
- `installation_output.log` - Raw installation stdout/stderr
- `installation_report.md` - Human-readable report
- `installation_metrics.json` - Structured metrics data

**Report Contents:**
- System information (CPU, memory, disk, architecture)
- Installation steps with status and duration
- Configuration checks and results
- Errors and warnings
- Package verification results

### ARM64 Monitor Output

**Location:** `/tmp/arm64_monitor/` and `/tmp/arm64_install_logs/`

**Files:**
- `arm64_monitor_report.md` - Monitoring report
- `arm64_monitor_metrics.json` - System metrics
- `dependency_verification.json` - Dependency check results
- `<step>_<timestamp>_stdout.log` - Step output logs
- `<step>_<timestamp>_stderr.log` - Step error logs
- `<step>_<timestamp>_combined.log` - Combined logs with timestamps
- `<step>_<timestamp>_metrics.json` - Step execution metrics

## Status Indicators

All monitoring scripts use consistent emoji indicators:

- 🚀 **Triggered/Started** - Action initiated
- 🔄 **In Progress** - Currently running
- ⏳ **Queued** - Waiting to start
- ⏸️ **Waiting** - Paused or waiting for resources
- ✅ **Success** - Completed successfully
- ❌ **Failed/Error** - Failed or encountered error
- ⚠️ **Warning** - Completed with warnings
- ℹ️ **Info** - Informational message
- ⏭️ **Skipped** - Step skipped
- 📋 **List** - Listing items
- 📊 **Report** - Report generated
- 📄 **File** - File created/found
- 💾 **Saved** - Data saved
- 🔍 **Checking** - Verification in progress

## Troubleshooting

### Workflow Monitor Issues

**Problem:** "gh: To use GitHub CLI in a GitHub Actions workflow..."

**Solution:** Set the `GH_TOKEN` environment variable:
```bash
export GH_TOKEN="your_github_token"
# or in GitHub Actions:
env:
  GH_TOKEN: ${{ github.token }}
```

**Problem:** "Failed to list workflows"

**Solution:** Authenticate with GitHub CLI:
```bash
gh auth login
gh auth status
```

### Installation Monitor Issues

**Problem:** "Command timed out"

**Solution:** 
- Check network connectivity
- Increase timeout in script (default: 10 minutes)
- Run with better network connection

**Problem:** Package not found after installation

**Solution:**
- Check if installed in correct Python environment
- Verify installation path with `pip show ipfs-kit-py`
- Ensure Python path is correct

### ARM64 Monitor Issues

**Problem:** Scripts not executable

**Solution:**
```bash
chmod +x scripts/ci/*.sh
chmod +x scripts/ci/*.py
```

**Problem:** Logs not generated

**Solution:**
```bash
# Create directories first
mkdir -p /tmp/arm64_monitor /tmp/arm64_install_logs
chmod 777 /tmp/arm64_monitor /tmp/arm64_install_logs
```

## Documentation

### Detailed Guides

- [Workflow Monitoring Guide](./scripts/ci/WORKFLOW_MONITORING.md) - Complete workflow and installation monitoring documentation
- [ARM64 Monitoring Guide](./ARM64_MONITORING_GUIDE.md) - ARM64-specific monitoring guide
- [ARM64 Implementation Details](./ARM64_MONITORING_IMPLEMENTATION.md) - Technical implementation details
- [CI Scripts README](./scripts/ci/README.md) - Overview of all CI monitoring scripts

### Example Workflows

Browse the `.github/workflows/` directory for examples:
- `daemon-config-tests.yml` - Daemon configuration testing with monitoring
- `arm64-ci.yml` - ARM64 CI with comprehensive monitoring
- `multi-arch-ci.yml` - Multi-architecture builds with monitoring

## Best Practices

1. **Always authenticate** before using workflow monitor in local environments
2. **Use appropriate poll intervals** to avoid GitHub API rate limits (default: 10s, recommended: 10-30s)
3. **Save artifacts** in CI/CD for troubleshooting and auditing
4. **Review logs immediately** after failures to identify root causes
5. **Test locally first** before integrating into production CI/CD
6. **Use custom log directories** to organize outputs in multi-step workflows
7. **Monitor regularly** during development to catch issues early
8. **Set up notifications** for critical workflow failures
9. **Archive monitoring data** for long-term analysis and compliance

## Contributing

When adding or improving monitoring features:

1. Follow existing logging format conventions
2. Use consistent status indicators (emoji)
3. Update relevant documentation
4. Test on target platforms (x86_64, ARM64)
5. Ensure GitHub Actions compatibility
6. Add error handling for external dependencies
7. Include examples in documentation

## Support

For issues or questions:

1. Check workflow/installation logs first
2. Review downloaded artifacts from failed runs
3. Search existing GitHub issues
4. Create new issue with:
   - Workflow/installation command used
   - Relevant log excerpts
   - System information
   - Steps to reproduce

## License

See the main repository [LICENSE](./LICENSE) file.

## Changelog

### Version 1.0.0 (2025-10-19)

**Added:**
- Initial release of workflow trigger and monitoring script
- First-time installation monitoring script
- Comprehensive documentation
- Demo scripts for all monitoring tools
- GitHub Actions integration examples
- Troubleshooting guides

**Integration with existing tools:**
- ARM64 monitoring scripts (from PR #70)
- Installation wrapper scripts
- Dependency verification tools

## Related Resources

- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Python Packaging Guide](https://packaging.python.org/)
- [ARM64 Development Guide](./ARM64_BUILD_SUMMARY.md)
