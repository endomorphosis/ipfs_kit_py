# Auto-Heal Context for Issue #427

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 28496813839
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/28496813839
- **Branch:** main
- **Commit:** c4f68f0156823853ac7f92c240eeab406ea930e2

## Failed Jobs

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/28496813839/job/84464710968

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/28496813839/job/84464710993

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
