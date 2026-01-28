# Auto-Heal Context for Issue #119

## Workflow Failure Information

- **Workflow:** Enhanced Docker Build and Test
- **Run ID:** 21428003778
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21428003778
- **Branch:** main
- **Commit:** 33b3fda9132a239b8ac3cd00d470d70eba63700c

## Failed Jobs

### Job: Build AMD64 Docker Image

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21428003778/job/61700947818

**Failed Steps:**
- Build Docker image (AMD64)

### Job: Build ARM64 Docker Image

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21428003778/job/61700947829

**Failed Steps:**
- Build Docker image (ARM64)



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
