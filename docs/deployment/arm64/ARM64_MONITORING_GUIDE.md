# ARM64 GitHub Actions Monitoring Implementation Guide

## Overview

This implementation adds comprehensive monitoring and logging for ARM64 dependency installation and configuration in GitHub Actions workflows. The solution addresses the lack of visibility into installation processes that was hampering ARM64 CI/CD reliability.

## Problem Statement

The original issue identified:
- No monitoring software for GitHub Actions ARM64 workflows
- Difficult to debug dependency installation failures
- No visibility into installation/configuration script execution
- Hard to diagnose ARM64-specific build issues

## Solution Components

### 1. Monitoring Scripts

#### `monitor_arm64_installation.py`
- **Purpose**: Real-time monitoring of ARM64 installation processes
- **Features**:
  - System information collection (CPU, memory, architecture)
  - Binary availability checking (gcc, go, make, git, etc.)
  - Python package verification
  - Execution time tracking
  - Error detection and reporting
  - GitHub Actions summary integration
- **Output**: Markdown reports and JSON metrics

#### `verify_arm64_dependencies.py`
- **Purpose**: Pre/post-installation dependency verification
- **Features**:
  - Required vs. optional dependency classification
  - Build tool verification
  - Python package checking
  - Pass/fail/warning status reporting
  - GitHub Actions integration
- **Output**: Console summary and JSON results

#### `installation_wrapper.sh`
- **Purpose**: Bash wrapper for monitoring any installation command
- **Features**:
  - Separate stdout/stderr capture
  - Timestamped logging
  - System metrics collection
  - GitHub Actions summary integration
  - Execution time tracking
- **Output**: Multiple log files and metrics JSON

### 2. Workflow Integration

#### Enhanced `arm64-ci.yml`
Added monitoring steps:
1. **Initialize ARM64 monitoring** - Set up log directories
2. **Verify pre-installation dependencies** - Check initial state
3. **Monitored system dependency installation** - Track apt-get operations
4. **Monitored Python dependency installation** - Log pip operations
5. **Verify post-installation dependencies** - Confirm successful installation
6. **Upload monitoring logs** - Preserve artifacts
7. **Generate final monitoring report** - Summary with error detection

#### Enhanced `daemon-config-tests.yml`
Added monitoring steps:
1. **Monitored dependency installation** - Track pip operations
2. **Environment verification** - Confirm module imports
3. **Monitoring summary** - GitHub Actions summary report

## Usage

### In GitHub Actions Workflows

```yaml
jobs:
  build-arm64:
    runs-on: [self-hosted, arm64]
    steps:
      # 1. Initialize monitoring
      - name: Initialize ARM64 monitoring
        run: |
          mkdir -p /tmp/arm64_monitor /tmp/arm64_install_logs
          python scripts/ci/monitor_arm64_installation.py

      # 2. Pre-installation verification
      - name: Verify pre-installation dependencies
        run: |
          python scripts/ci/verify_arm64_dependencies.py || true

      # 3. Monitored installation
      - name: Install system dependencies
        run: |
          ./scripts/ci/installation_wrapper.sh system_deps \
            sudo apt-get install -y build-essential golang-go

      # 4. Post-installation verification
      - name: Verify post-installation dependencies
        run: |
          python scripts/ci/verify_arm64_dependencies.py

      # 5. Upload artifacts
      - name: Upload monitoring logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: arm64-monitoring-logs
          path: |
            /tmp/arm64_monitor/
            /tmp/arm64_install_logs/
          retention-days: 7
```

### Standalone Usage

```bash
# Run dependency verification
python scripts/ci/verify_arm64_dependencies.py

# Run installation monitor
python scripts/ci/monitor_arm64_installation.py

# Wrap any installation command
./scripts/ci/installation_wrapper.sh my_install pip install ipfs-kit-py

# Run full demo
./scripts/ci/demo_monitoring.sh
```

## Monitoring Output

### Console Output
Real-time status indicators:
- ✅ Success
- ❌ Failure
- ⚠️ Warning
- 🔄 In progress
- ℹ️ Information

### Log Files

#### Standard Logs (per installation)
- `*_stdout.log` - Standard output
- `*_stderr.log` - Error output
- `*_combined.log` - Combined with timestamps
- `*_metrics.json` - Execution metadata

#### Report Files
- `arm64_monitor_report.md` - Human-readable report
- `arm64_monitor_metrics.json` - Machine-readable metrics
- `dependency_verification.json` - Dependency check results

### GitHub Actions Integration

Monitoring results appear in:
1. **Workflow logs** - Real-time console output
2. **Step summaries** - $GITHUB_STEP_SUMMARY
3. **Artifacts** - Downloadable logs and reports
4. **Job annotations** - Error/warning markers

## Example Monitoring Report

```markdown
# ARM64 Dependency Installation Monitor Report

**Generated**: 2025-10-19T05:48:40.636037
**Total Duration**: 0.04 seconds

## System Information
- **architecture**: aarch64
- **platform**: Linux-5.15.0-arm64
- **python_version**: 3.11.5
- **cpu_count**: 4
- **memory_total**: 8388608 KB

## Installation Steps
- ✅ **build_tool_gcc**: 0.00s
  - Command: `which gcc`
- ✅ **build_tool_go**: 0.00s
  - Command: `which go`
- ✅ **python_requests**: 0.00s
  - Command: `import requests`

## Installation Timeline
- [0.0s] 🔄 System Check
- [0.0s] ✅ System Check
  - Running on ARM64 (aarch64)
- [0.0s] 🔄 Check gcc
- [0.0s] ✅ Check gcc
  - Found: /usr/bin/gcc, Version: gcc 11.4.0
```

## Debugging Workflow Failures

### Step 1: Check GitHub Actions Summary
- Navigate to workflow run
- Review "ARM64 Dependency Verification" section
- Check for ❌ indicators

### Step 2: Download Artifacts
- Click "Artifacts" in workflow run
- Download `arm64-monitoring-logs`
- Extract and review logs

### Step 3: Analyze Logs
```bash
# Check for errors in combined log
grep -i "error\|failed" *_combined.log

# Review metrics for system state
cat *_metrics.json | jq .

# Check dependency verification
cat dependency_verification.json | jq '.summary'
```

### Step 4: Review Specific Installation
```bash
# Find logs for specific step
ls -1 /tmp/arm64_install_logs/ | grep system_deps

# Review stderr
cat system_deps_*_stderr.log

# Check exit code in metrics
cat system_deps_*_metrics.json | jq '.execution.exit_code'
```

## Metrics Collected

### System Metrics
- Architecture (x86_64, aarch64, arm64)
- CPU count and model
- Memory total and available
- Disk space
- Kernel version
- OS distribution

### Installation Metrics
- Command executed
- Start/end time
- Duration (seconds)
- Exit code
- Stdout/stderr output
- Environment variables

### Dependency Status
- Binary availability
- Version information
- Installation path
- Python package versions

## Best Practices

1. **Always verify before and after installation**
   ```bash
   python scripts/ci/verify_arm64_dependencies.py  # Before
   # ... installation steps ...
   python scripts/ci/verify_arm64_dependencies.py  # After
   ```

2. **Use installation wrapper for critical steps**
   ```bash
   ./scripts/ci/installation_wrapper.sh ipfs_install \
     pip install ipfs-kit-py
   ```

3. **Upload artifacts with retention**
   ```yaml
   - uses: actions/upload-artifact@v3
     with:
       retention-days: 7
   ```

4. **Check exit codes**
   ```bash
   python scripts/ci/verify_arm64_dependencies.py
   if [ $? -ne 0 ]; then
     echo "Verification failed"
     exit 1
   fi
   ```

5. **Review GitHub Actions summaries**
   - Check after every workflow run
   - Look for warning indicators
   - Download artifacts for failures

## Troubleshooting

### Monitoring scripts not found
```bash
# Ensure checkout includes scripts
- uses: actions/checkout@v4

# Make scripts executable
- run: |
    chmod +x scripts/ci/*.sh
    chmod +x scripts/ci/*.py
```

### Logs not generated
```bash
# Create directories first
- run: |
    mkdir -p /tmp/arm64_monitor
    mkdir -p /tmp/arm64_install_logs
    chmod 777 /tmp/arm64_monitor
    chmod 777 /tmp/arm64_install_logs
```

### Artifacts not uploaded
```yaml
# Use if: always() to ensure upload
- uses: actions/upload-artifact@v3
  if: always()
  with:
    name: monitoring-logs
    path: /tmp/arm64_*
```

### Python import errors
```bash
# Ensure Python environment is activated
- run: |
    source venv/bin/activate
    python scripts/ci/verify_arm64_dependencies.py
```

## Testing

### Local Testing
```bash
# Run monitoring demo
./scripts/ci/demo_monitoring.sh

# Test individual scripts
python scripts/ci/monitor_arm64_installation.py
python scripts/ci/verify_arm64_dependencies.py
./scripts/ci/installation_wrapper.sh test echo "test"
```

### Workflow Testing
1. Push to a test branch
2. Trigger workflow manually
3. Review workflow logs
4. Download and inspect artifacts
5. Verify GitHub Actions summaries

## Future Enhancements

Potential improvements:
- [ ] Add performance benchmarking
- [ ] Implement alert thresholds
- [ ] Add Slack/email notifications
- [ ] Create comparison reports between runs
- [ ] Add ARM64-specific binary detection
- [ ] Implement retry logic for failed installations
- [ ] Add visualization dashboards
- [ ] Integrate with external monitoring services

## Contributing

When adding monitoring features:
1. Follow existing log format conventions
2. Use consistent status indicators
3. Update documentation
4. Test on actual ARM64 hardware
5. Ensure GitHub Actions compatibility

## Related Documentation

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [ARM64 Build Summary](ARM64_BUILD_SUMMARY.md)
- [CI/CD Scripts README](./README.md)
- [Workflow Configuration](../../.github/workflows/README.md)

## Support

For issues or questions:
1. Check workflow logs first
2. Review downloaded artifacts
3. Search existing issues
4. Create new issue with:
   - Workflow run URL
   - Relevant log excerpts
   - System information
   - Steps to reproduce
