# CI/CD Validation Tools - Quick Start

This directory contains tools for validating and testing GitHub Actions CI/CD workflows.

## 🚀 Quick Start

```bash
# Validate all workflow files
python scripts/ci/validate_ci_workflows.py

# Test all CI scripts
python scripts/ci/test_ci_scripts.py

# Run comprehensive validation
bash scripts/ci/run_all_validations.sh
```

## 📋 Tools Overview

### 1. validate_ci_workflows.py
Validates all GitHub Actions workflow YAML files.

**Features:**
- ✅ YAML syntax validation
- ✅ Check for referenced scripts
- ✅ Check for referenced tests
- ✅ Verify workflow structure

**Usage:**
```bash
# Basic validation
python scripts/ci/validate_ci_workflows.py

# Verbose mode (shows all warnings)
python scripts/ci/validate_ci_workflows.py --verbose

# Create placeholders for missing scripts
python scripts/ci/validate_ci_workflows.py --fix-missing
```

### 2. test_ci_scripts.py
Tests all CI/CD scripts for basic functionality.

**Features:**
- ✅ Test script execution
- ✅ Check for --help support
- ✅ Verify scripts are executable
- ✅ Generate test reports

**Usage:**
```bash
# Test all scripts
python scripts/ci/test_ci_scripts.py

# Verbose mode
python scripts/ci/test_ci_scripts.py --verbose

# Test specific script
python scripts/ci/test_ci_scripts.py --script monitor_amd64_installation.py
```

### 3. run_all_validations.sh
Runs all validation checks in one command.

**Features:**
- ✅ Validates workflows
- ✅ Tests CI scripts
- ✅ Checks dependencies
- ✅ Verifies documentation
- ✅ Generates summary report

**Usage:**
```bash
bash scripts/ci/run_all_validations.sh
```

### 4. check_monitoring_health.py
Verifies monitoring system health.

**Checks:**
- ✅ Python environment
- ✅ GitHub CLI setup
- ✅ Monitoring scripts
- ✅ Log directories
- ✅ Documentation

**Usage:**
```bash
python scripts/ci/check_monitoring_health.py
```

### 5. verify_amd64_dependencies.py / verify_arm64_dependencies.py
Verifies build environment for specific architectures.

**Checks:**
- ✅ Build tools (gcc, g++, make)
- ✅ Go compiler
- ✅ Python packages
- ✅ System binaries

**Usage:**
```bash
# AMD64
python scripts/ci/verify_amd64_dependencies.py

# ARM64
python scripts/ci/verify_arm64_dependencies.py
```

### 6. monitor_amd64_installation.py / monitor_arm64_installation.py
Monitors package installation process.

**Features:**
- ✅ Real-time monitoring
- ✅ Dependency tracking
- ✅ Report generation
- ✅ GitHub Actions integration

**Usage:**
```bash
# AMD64
python scripts/ci/monitor_amd64_installation.py

# ARM64
python scripts/ci/monitor_arm64_installation.py
```

## 🔄 GitHub Actions Integration

All validation tools are integrated into the CI/CD pipeline via the `ci-cd-validation.yml` workflow.

The workflow runs:
- ✅ On every push to main/develop
- ✅ On pull requests
- ✅ Daily at 00:00 UTC
- ✅ Manually via workflow_dispatch

## 📊 Output Examples

### Workflow Validation
```
✅ amd64-ci.yml
✅ arm64-ci.yml
✅ run-tests.yml
...
📊 Validation Summary:
   Total workflows: 36
   Valid: 36
   With errors: 0
   Total warnings: 53
```

### Script Testing
```
✅ monitor_amd64_installation.py
✅ verify_amd64_dependencies.py
⚠️  generate_performance_report.py (help works but execution may need arguments)
...
📊 Test Summary:
   Total scripts: 11
   Success rate: 54.5%
```

### Comprehensive Validation
```
✅ PASSED: Python 3 availability
✅ PASSED: Workflow YAML validation
✅ PASSED: CI scripts functionality
...
Success rate: 90%
✅ CI/CD validation PASSED
```

## 🐛 Troubleshooting

### Issue: Workflow validation fails

**Solution:**
1. Check YAML syntax: `python -c "import yaml; yaml.safe_load(open('.github/workflows/file.yml'))"`
2. Run verbose validation: `python scripts/ci/validate_ci_workflows.py --verbose`
3. Fix errors reported by the validator

### Issue: Script tests fail

**Solution:**
1. Check if script exists: `ls -la scripts/ci/script.py`
2. Verify it's executable: `chmod +x scripts/ci/script.py`
3. Test manually: `python scripts/ci/script.py --help`

### Issue: Dependencies not found

**Solution:**
1. Install system dependencies: `sudo apt-get install build-essential gcc g++ make git`
2. Install Python packages: `pip install pyyaml requests`
3. Re-run validation

## 📚 Documentation

For detailed information, see:
- [CI/CD Validation Guide](../../docs/ci-cd/CI_CD_VALIDATION_GUIDE.md) - Complete guide
- [Workflow Monitoring](WORKFLOW_MONITORING.md) - Monitoring details
- [AMD64 Workflows](../../docs/ci-cd/amd64/AMD64_WORKFLOWS_QUICK_REF.md) - AMD64 specific
- [ARM64 Monitoring](../../docs/deployment/arm64/ARM64_MONITORING_GUIDE.md) - ARM64 specific

## 🔧 Development

### Adding New Validation Checks

1. Create script in `scripts/ci/`
2. Make it executable: `chmod +x script.py`
3. Add to `run_all_validations.sh`
4. Update documentation
5. Test with `python scripts/ci/test_ci_scripts.py --script your_script.py`

### Updating Workflows

1. Make changes to `.github/workflows/`
2. Validate: `python scripts/ci/validate_ci_workflows.py`
3. Test on branch first
4. Monitor first run carefully

## 📈 Success Metrics

**Current Status:**
- ✅ 36 workflow files validated
- ✅ 11 CI/CD scripts
- ✅ 90%+ validation success rate
- ✅ Daily automated checks

## 🎯 Goals

- Maintain 100% workflow YAML validity
- Keep CI script success rate > 80%
- Automated daily validation
- Comprehensive documentation

## 🤝 Contributing

When contributing:
1. Run validation before committing
2. Update documentation
3. Test changes on a branch
4. Monitor workflow runs

## 📞 Support

For issues or questions:
1. Check workflow logs in GitHub Actions
2. Review validation output
3. Consult documentation
4. Create an issue with details
