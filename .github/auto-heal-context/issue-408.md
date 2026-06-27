# Auto-Heal Context for Issue #408

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 28248080831
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/28248080831
- **Branch:** main
- **Commit:** f96fd828014e4a846d1deb35a05c23c44f0bccb3

## Failed Jobs

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/28248080831/job/83692218952

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/28248080831/job/83692218968

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
