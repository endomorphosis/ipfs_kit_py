# Auto-Heal Context for Issue #379

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 27488833639
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27488833639
- **Branch:** main
- **Commit:** 17f82f3a5ef6ee0a63191f7fb12796c2272ed165

## Failed Jobs

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27488833639/job/81250028366

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27488833639/job/81250028420

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
