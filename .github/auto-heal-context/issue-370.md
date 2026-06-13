# Auto-Heal Context for Issue #370

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 27415519228
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27415519228
- **Branch:** main
- **Commit:** 1c33f2833489b111266af73328797821e92908b0

## Failed Jobs

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27415519228/job/81027227075

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27415519228/job/81027227095

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
