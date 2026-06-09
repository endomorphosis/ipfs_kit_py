# Auto-Heal Context for Issue #354

## Workflow Failure Information

- **Workflow:** Python Package
- **Run ID:** 27139167313
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27139167313
- **Branch:** main
- **Commit:** 8d2183b0eff95411f30c7b6b196fec9e88657612

## Failed Jobs

### Job: Test Python 3.12 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27139167313/job/80099398802

**Failed Steps:**
- Check formatting with black

### Job: Test Python 3.13 on amd64

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/27139167313/job/80099398831

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
