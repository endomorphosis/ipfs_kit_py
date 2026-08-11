# Auto-Heal Context for Issue #539

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 31437516787
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/31437516787
- **Branch:** main
- **Commit:** 5a7a2df8181cfdc33bc19be09989df7ff83f2d4e

## Failed Jobs

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/31437516787/job/93614844137

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/31437516787/job/93614844171

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
