# CI/CD Workflow Validation Guide

This document describes the tools and processes for validating GitHub Actions CI/CD workflows in this repository.

## Overview

This repository contains 35+ GitHub Actions workflows that handle:
- Multi-architecture builds (AMD64, ARM64)
- Testing across multiple Python versions (3.8-3.13)
- Docker image builds and tests
- Documentation generation
- Security scanning
- Release automation

## Validation Tools

### 1. Workflow YAML Validation

**Script:** `scripts/ci/validate_ci_workflows.py`

Validates all workflow files for:
- YAML syntax correctness
- Referenced scripts existence
- Referenced test files existence
- Workflow structure (jobs, triggers, etc.)

**Usage:**
```bash
# Basic validation
python scripts/ci/validate_ci_workflows.py

# Verbose output with all warnings
python scripts/ci/validate_ci_workflows.py --verbose

# Create placeholders for missing scripts
python scripts/ci/validate_ci_workflows.py --fix-missing
```

**Example Output:**
```
✅ amd64-ci.yml
✅ arm64-ci.yml
✅ run-tests.yml
...
📊 Validation Summary:
   Total workflows: 35
   Valid: 35
   With errors: 0
   Total warnings: 52
```

### 2. CI Script Testing

**Script:** `scripts/ci/test_ci_scripts.py`

Tests all CI/CD scripts in `scripts/ci/` to ensure they can run without errors.

**Usage:**
```bash
# Test all scripts
python scripts/ci/test_ci_scripts.py

# Test with verbose output
python scripts/ci/test_ci_scripts.py --verbose

# Test a specific script
python scripts/ci/test_ci_scripts.py --script monitor_amd64_installation.py
```

**Example Output:**
```
✅ monitor_amd64_installation.py
✅ verify_amd64_dependencies.py
⚠️  generate_performance_report.py (help works but execution may need arguments)
...
📊 Test Summary:
   Total scripts: 11
   Runs successfully: 6
   Success rate: 54.5%
```

### 3. Monitoring System Health Check

**Script:** `scripts/ci/check_monitoring_health.py`

Verifies that the monitoring system components are properly set up.

**Usage:**
```bash
python scripts/ci/check_monitoring_health.py
```

Checks:
- Python environment
- GitHub CLI authentication
- Monitoring scripts existence
- Log directories writable
- Documentation files

## Key CI/CD Scripts

### Installation Monitoring

- **`monitor_amd64_installation.py`** - Monitors AMD64 package installation
- **`monitor_arm64_installation.py`** - Monitors ARM64 package installation
- **`monitor_first_install.py`** - Tracks first-time installation metrics

### Dependency Verification

- **`verify_amd64_dependencies.py`** - Verifies AMD64 build environment
- **`verify_arm64_dependencies.py`** - Verifies ARM64 build environment

### Workflow Management

- **`trigger_and_monitor_workflow.py`** - Triggers and monitors workflow runs
- **`generate_performance_report.py`** - Generates performance reports

## Workflow Categories

### Architecture-Specific Workflows

| Workflow | Purpose | Runners |
|----------|---------|---------|
| `amd64-ci.yml` | AMD64 CI/CD pipeline | self-hosted, amd64 |
| `arm64-ci.yml` | ARM64 CI/CD pipeline | self-hosted, arm64, dgx |
| `multi-arch-ci.yml` | Multi-arch builds | self-hosted |

### Testing Workflows

| Workflow | Purpose | Python Versions |
|----------|---------|-----------------|
| `run-tests.yml` | Main test suite | 3.8-3.13 |
| `daemon-tests.yml` | Daemon functionality tests | 3.8-3.11 |
| `cluster-tests.yml` | Cluster service tests | 3.8-3.11 |

### Build & Release Workflows

| Workflow | Purpose |
|----------|---------|
| `docker-build.yml` | Docker image builds |
| `publish-package.yml` | PyPI package publishing |
| `release.yml` | Release automation |

### Quality & Security Workflows

| Workflow | Purpose |
|----------|---------|
| `lint.yml` | Code linting |
| `security.yml` | Security scanning |
| `coverage.yml` | Code coverage |

## Common Issues and Solutions

### Issue: Script Not Found in Workflow

**Symptom:** Workflow references a script that doesn't exist

**Solution:**
1. Run `python scripts/ci/validate_ci_workflows.py --verbose` to identify missing scripts
2. Either:
   - Create the missing script
   - Remove the reference from the workflow
   - Use `--fix-missing` to create a placeholder

### Issue: Tests Referenced but Missing

**Symptom:** Workflow tries to run tests that don't exist

**Solution:**
1. Check if test is dynamically created (like `test_arm64_basic.py`)
2. Create the test file if it should exist permanently
3. Update workflow to handle missing tests gracefully

### Issue: Self-Hosted Runner Requirements

**Symptom:** Workflow fails on self-hosted runners

**Solution:**
1. Verify runner labels match workflow requirements
2. Check system dependencies are installed on runners
3. Ensure Python versions are available on runners

## Best Practices

### 1. Always Validate Before Committing

```bash
# Run validation before committing workflow changes
python scripts/ci/validate_ci_workflows.py
```

### 2. Test Scripts Locally

```bash
# Test new CI scripts before using in workflows
python scripts/ci/test_ci_scripts.py --script your_new_script.py
```

### 3. Use Monitoring Scripts

All workflows should use the monitoring scripts for better observability:

```yaml
- name: Initialize monitoring
  run: |
    python scripts/ci/monitor_amd64_installation.py
```

### 4. Handle Failures Gracefully

Scripts should continue even if some steps fail:

```yaml
- name: Optional step
  run: |
    python script.py || echo "Step failed but continuing"
```

### 5. Add Verbose Logging

Use the monitoring and verification scripts to add detailed logging:

```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt | tee /tmp/install_logs/requirements.log
```

## Testing Workflows Locally

### Using act (GitHub Actions locally)

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run a workflow locally
act -W .github/workflows/run-tests.yml
```

### Manual Testing

```bash
# Test basic package installation
python -m venv test_env
source test_env/bin/activate
pip install -e .
pytest tests/

# Test monitoring scripts
python scripts/ci/monitor_amd64_installation.py
python scripts/ci/verify_amd64_dependencies.py
```

## Continuous Improvement

### Adding New Workflows

1. Create workflow file in `.github/workflows/`
2. Validate: `python scripts/ci/validate_ci_workflows.py`
3. Test referenced scripts: `python scripts/ci/test_ci_scripts.py`
4. Commit and monitor first run

### Updating Existing Workflows

1. Make changes
2. Validate: `python scripts/ci/validate_ci_workflows.py --verbose`
3. Check for new script dependencies
4. Test on a branch first
5. Monitor workflow run carefully

## Monitoring Workflow Runs

### View Workflow Status

```bash
# Using GitHub CLI
gh workflow list
gh run list --workflow=run-tests.yml
gh run view <run-id>
```

### Check Logs

```bash
# Download logs
gh run download <run-id>

# View specific job logs
gh run view <run-id> --log
```

### Monitoring Artifacts

Workflows generate monitoring artifacts:
- `amd64-monitoring-logs-*` - AMD64 installation logs
- `arm64-monitoring-logs-*` - ARM64 installation logs
- `test-results-*` - Test execution results

## Support and Troubleshooting

### Getting Help

1. Check workflow logs in GitHub Actions
2. Review monitoring artifacts
3. Run validation scripts locally
4. Check documentation in `scripts/ci/README.md`

### Reporting Issues

When reporting workflow issues, include:
- Workflow name and run ID
- Error messages from logs
- Output from validation scripts
- System information (arch, Python version, etc.)

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Monitoring Guide](../../.github/scripts/ci/WORKFLOW_MONITORING.md)
- [ARM64 Monitoring Guide](ARM64_MONITORING_GUIDE.md)
- [AMD64 Workflows Guide](amd64/AMD64_WORKFLOWS_QUICK_REF.md)
