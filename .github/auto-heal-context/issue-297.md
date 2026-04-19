# Auto-Heal Context for Issue #297

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 24599002796
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/24599002796
- **Branch:** main
- **Commit:** 4067324d41a548ce639168caccdd31da8683be6a

## Failed Jobs

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/24599002796/job/71934345498

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/24599002796/job/71934345518

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
