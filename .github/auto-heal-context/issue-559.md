# Auto-Heal Context for Issue #559

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 31739141096
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/31739141096
- **Branch:** main
- **Commit:** 6196017ca3df016c7159dce43af60f2a0d96a9ae

## Failed Jobs

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/31739141096/job/94577923991

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/31739141096/job/94577924220

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
