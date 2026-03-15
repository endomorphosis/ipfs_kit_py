# Auto-Heal Context for Issue #278

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 23076364705
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/23076364705
- **Branch:** main
- **Commit:** a83d2c5af7d815990b50905898b83ab189a9c0c2

## Failed Jobs

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/23076364705/job/67037379008

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/23076364705/job/67037379017

**Failed Steps:**
- Check formatting with black



## Task

Please fix the workflow failure by:
1. Analyzing the error logs above
2. Identifying the root cause
3. Making minimal, targeted changes to fix the issue
4. Ensuring the fix doesn't break existing functionality

## Files to Review

- `.github/workflows/` directory for workflow YAML files
- Related source code if the failure is in application tests
- Dependencies and configuration files

Follow the guidelines in `.github/copilot-instructions.md`
