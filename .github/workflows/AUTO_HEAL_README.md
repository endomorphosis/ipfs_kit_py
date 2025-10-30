# Auto-Healing Workflows Documentation

## Overview

This repository has multiple auto-healing workflows designed to automatically detect, report, and fix failed GitHub Actions workflows. This document explains how they work and how to use them.

## Simple Auto-Heal Workflow (Recommended)

**File:** `simple-auto-heal.yml`

This is the **recommended** auto-healing workflow. It follows the VS Code Copilot pattern:

### How It Works

1. **Monitors Workflows:** Triggers when any monitored workflow completes with a failure
2. **Creates Issue:** Automatically creates a GitHub issue with:
   - Workflow failure details
   - Error logs from failed jobs
   - Run information and links
3. **Creates Draft PR:** Creates a draft pull request with:
   - Link to the issue
   - Auto-heal context file with failure analysis
   - Branch for Copilot to work on
4. **@mentions Copilot:** Includes @copilot mention in the PR description to trigger the GitHub Copilot agent

### What Happens Next

1. GitHub Copilot agent receives the @mention
2. Copilot analyzes the failure logs
3. Copilot implements a fix based on the error patterns
4. You review the fix and merge the PR

### Manual Intervention

If Copilot doesn't automatically provide a fix, you can:
- Review the PR and implement fixes manually
- Use GitHub Copilot in your IDE for assistance
- Open the PR in GitHub Copilot Workspace

## Other Auto-Healing Workflows

### copilot-agent-autofix.yml

**Purpose:** Advanced AI-powered fix generation using pattern matching
**Trigger:** When an issue is labeled with `auto-heal`, `workflow-failure`, and `copilot-agent`

This workflow:
- Parses issue details to extract failure information
- Analyzes error patterns (timeouts, missing dependencies, YAML errors, permissions)
- Generates fixes using AI-style pattern matching
- Creates a PR with the fixes

**Note:** This workflow is more complex and attempts to apply fixes automatically, which may not always be appropriate.

### workflow-failure-autofix.yml

**Purpose:** Create PRs with context for fixing workflow failures
**Trigger:** When any monitored workflow fails

This workflow:
- Creates workflow failure context files
- Creates a draft PR with context for Copilot Workspace
- Provides instructions for manual or Copilot-assisted fixing

**Note:** This workflow uses `peter-evans/create-pull-request` action which may behave differently than the simple approach.

### auto-heal-workflow.yml

**Purpose:** Generate fixes using Python scripts
**Trigger:** When an issue is labeled with `auto-heal` and `workflow-failure`

This workflow:
- Relies on Python scripts (`scripts/ci/generate_workflow_fix.py`)
- Attempts to generate fixes programmatically
- Creates PRs with applied fixes

**Note:** Depends on Python scripts which may need maintenance.

### copilot-auto-heal.yml

**Purpose:** Invoke GitHub Copilot for auto-healing
**Trigger:** When an issue is labeled with `auto-heal` and `workflow-failure` (but not `copilot-invoked`)

This workflow:
- Attempts to invoke Copilot via API/CLI
- Creates branches for Copilot Workspace
- Provides Copilot Workspace links

**Note:** More complex setup with multiple invocation methods.

### workflow-failure-monitor.yml

**Purpose:** Monitor all workflows and create issues
**Trigger:** When any workflow fails

This workflow:
- Monitors all workflows (using wildcard `["*"]`)
- Creates issues for failures
- Relies on Python script (`scripts/ci/analyze_workflow_failure.py`)

**Note:** May create duplicate issues if `simple-auto-heal.yml` is also running.

## Recommendations

### For Most Users

**Use:** `simple-auto-heal.yml`

This workflow provides the best balance of simplicity and automation. It follows the VS Code pattern that users are familiar with.

### Disable Conflicting Workflows

To avoid duplicate issues and PRs, consider disabling or removing:
- `workflow-failure-monitor.yml` (creates issues - redundant with simple-auto-heal)
- `workflow-failure-autofix.yml` (creates PRs - may conflict)

You can disable a workflow by:
1. Renaming it to `.yml.disabled`
2. Adding a condition: `if: false` to the jobs
3. Removing it entirely

### For Advanced Users

If you want more sophisticated fix generation, you can:
1. Keep `simple-auto-heal.yml` for issue/PR creation
2. Enhance it with the pattern matching from `copilot-agent-autofix.yml`
3. Use the Python scripts from `auto-heal-workflow.yml` for complex analysis

## Configuration

### Adding Workflows to Monitor

Edit `simple-auto-heal.yml` and add workflow names to the `workflow_run.workflows` list:

```yaml
on:
  workflow_run:
    workflows:
      - "Your Workflow Name"
      - "Another Workflow"
    types:
      - completed
```

### Customizing Issue Labels

Edit the labels in the "Create issue" step:

```yaml
labels: ['auto-heal', 'workflow-failure', 'needs-fix', 'your-custom-label']
```

### Customizing PR Labels

Edit the labels in the "Create draft PR" step:

```yaml
labels: ['auto-heal', 'workflow-fix', 'copilot-agent', 'your-custom-label']
```

## Troubleshooting

### Issue: Duplicate Issues Created

**Solution:** Make sure only one workflow is creating issues. Disable `workflow-failure-monitor.yml` if using `simple-auto-heal.yml`.

### Issue: Copilot Doesn't Respond

**Possible causes:**
1. Copilot agent integration not enabled in repository settings
2. @mention syntax not recognized
3. PR is not a draft (Copilot may only work on drafts in some cases)

**Solutions:**
1. Check repository settings for Copilot features
2. Ensure the @mention is in the PR description: `@copilot`
3. Verify the PR is created as a draft

### Issue: Python Scripts Not Found

If `auto-heal-workflow.yml` fails with "script not found":

**Solution:** Ensure the scripts exist at:
- `scripts/ci/generate_workflow_fix.py`
- `scripts/ci/analyze_workflow_failure.py`

### Issue: PRs Created on Wrong Branch

Check the `base` parameter in the "Create draft PR" step. It should match your default branch or the branch where the failure occurred.

## Best Practices

1. **Start Simple:** Use `simple-auto-heal.yml` first
2. **Monitor Issues:** Keep an eye on auto-created issues to ensure they're helpful
3. **Review PRs:** Always review auto-generated PRs before merging
4. **Iterate:** Adjust the workflow based on the types of failures you encounter
5. **Update Instructions:** Keep `.github/copilot-instructions.md` updated with guidance for Copilot

## Contributing

If you improve the auto-healing workflows, please:
1. Update this documentation
2. Test the changes on a few workflow failures
3. Share your improvements with the team

## Questions?

For questions or issues with auto-healing:
1. Check this documentation
2. Review the workflow run logs
3. Open an issue with label `auto-heal-meta`
