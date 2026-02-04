# Auto-Heal Context for Issue #180

## Workflow Failure Information

- **Workflow:** Enhanced Docker Build and Test
- **Run ID:** 21657927955
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21657927955
- **Branch:** main
- **Commit:** 2119a63fa8adcb8553e4276e4a9dbf9e94637353

## Failed Jobs

### Job: Build AMD64 Docker Image

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21657927955/job/62436516974

**Failed Steps:**
- Build Docker image (AMD64)

### Job: Build ARM64 Docker Image

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21657927955/job/62436516996

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
