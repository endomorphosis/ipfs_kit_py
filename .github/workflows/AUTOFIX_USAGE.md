# Workflow Auto-Fix System Usage Guide

This document explains how to use and test the workflow auto-fix and auto-heal system.

## Overview

The auto-fix system automatically:
1. Detects when a workflow fails on the main branch
2. Creates an issue documenting the failure
3. Creates a draft PR with context files for fixing
4. **Automatically @mentions Copilot on the PR to trigger analysis**
5. Waits for you to review and approve Copilot's proposed fixes

## How It Works

### Automatic Triggering

The `workflow-failure-autofix.yml` workflow uses the `workflow_run` trigger to monitor other workflows:

```yaml
on:
  workflow_run:
    workflows:
      - "Python package"
      - "Python Package"
      # ... other workflows
    types:
      - completed
```

**Important**: The `workflow_run` trigger only fires when:
- The monitored workflow runs on the **default branch** (main/master)
- The workflow file with the trigger exists on the default branch
- The monitored workflow completes (with any conclusion)

This means:
- ✅ Workflow failures on main branch WILL trigger autofix
- ❌ Workflow failures on feature branches will NOT trigger autofix
- ❌ Pull request workflow failures will NOT trigger autofix (unless merged to main)

### What Happens Automatically

When a monitored workflow fails on main:

1. **Issue Created**: A new issue is opened with:
   - Full failure details
   - Links to failed jobs and logs
   - Labels: `workflow-failure`, `auto-fix-eligible`, `ci/cd`

2. **Draft PR Created**: A draft pull request is opened with:
   - Context files in `.github/workflow-failures/`
   - Copilot instructions in `.github/copilot-fix-instructions.md`
   - Labels: `auto-fix`, `workflow-failure`, `ci/cd`

3. **Copilot Auto-Invoked**: A comment is automatically posted on the PR:
   - @mentions Copilot
   - Asks Copilot to analyze the failure
   - Requests minimal, targeted fixes
   - **This triggers Copilot to start working on the fix**

4. **Your Action Required**: 
   - Review the draft PR
   - Check Copilot's proposed changes
   - Approve and merge if satisfied
   - Or manually edit if needed

### Manual Triggering (for Testing)

You can manually trigger the autofix workflow for testing:

#### Option 1: Test with a Real Failed Workflow

1. Go to Actions tab in GitHub
2. Find a failed workflow run and note its Run ID (from the URL)
3. Go to "Workflow Failure Auto-Fix" workflow
4. Click "Run workflow"
5. Enter the Run ID
6. Click "Run workflow"

#### Option 2: Test with Dummy Data

1. Go to Actions tab in GitHub
2. Go to "Workflow Failure Auto-Fix" workflow
3. Click "Run workflow"
4. Leave Run ID empty (or enter a workflow name)
5. Click "Run workflow"

This will create a test issue and PR to verify the system works.

## Testing the Complete System

### Step 1: Verify Auto-Fix Triggers on Main Branch

1. **Cause a deliberate failure on main branch**:
   - Option A: Manually trigger the "Test Workflow Auto-Fix System" workflow
   - Option B: Push a commit that will fail tests to main branch
   
2. **Check that auto-fix workflow runs**:
   - Go to Actions → "Workflow Failure Auto-Fix"
   - Verify it ran after the failed workflow
   
3. **Check that issue was created**:
   - Go to Issues
   - Look for an issue with label `workflow-failure`
   
4. **Check that PR was created**:
   - Go to Pull Requests
   - Look for a draft PR with label `auto-fix`

### Step 2: Test GitHub Copilot Integration

Once an auto-fix PR is created:

#### Method A: Via GitHub Copilot Workspace

1. Open the draft PR in GitHub
2. Click "Open in Copilot Workspace" (if available)
3. Copilot will read the context files in `.github/workflow-failures/`
4. Ask Copilot: "Please analyze the workflow failure and implement a fix"
5. Review and apply the suggested changes
6. Push to the PR branch

#### Method B: Via Issue Comment

1. Go to the auto-created issue
2. Comment: `@copilot /fix-workflow`
3. The `copilot-auto-fix.yml` workflow will trigger
4. Follow the instructions in the automated response

### Step 3: Verify the Fix

1. Once fixes are implemented, mark the PR as ready for review
2. Verify CI passes on the PR
3. Merge the PR
4. The auto-created issue should auto-close

## Troubleshooting

### Auto-Fix Workflow Doesn't Trigger

**Symptom**: Workflow fails on main but no issue/PR is created

**Possible Causes**:

1. **Workflow not on main branch**
   - Solution: Ensure the `workflow-failure-autofix.yml` file exists on main
   
2. **Monitored workflow not in the list**
   - Solution: Add the workflow name to the `workflows:` list in `workflow-failure-autofix.yml`
   
3. **Permissions issue**
   - Solution: Verify the workflow has `issues: write` and `pull-requests: write` permissions
   
4. **GitHub Actions Settings**
   - Solution: Check that workflows can create PRs in Settings → Actions → General

### Issue Created but No PR

**Symptom**: Issue is created but draft PR is missing

**Possible Causes**:

1. **peter-evans/create-pull-request failed**
   - Solution: Check the workflow logs for errors in the "Create Pull Request" step
   
2. **No changes to commit**
   - Solution: Verify context files are being created in `.github/workflow-failures/`

### Copilot Doesn't Respond

**Symptom**: Commenting `@copilot /fix-workflow` doesn't trigger anything

**Possible Causes**:

1. **GitHub Copilot not enabled**
   - Solution: Enable GitHub Copilot for your repository
   
2. **Workflow not triggered**
   - Solution: Check Actions → "Copilot Auto-Fix Implementation" to see if it ran
   
3. **No linked PR**
   - Solution: The workflow needs a linked PR to work with

## Monitoring and Debugging

### View Auto-Fix Workflow Runs

```bash
gh run list --workflow="workflow-failure-autofix.yml"
```

### View Auto-Fix Workflow Logs

```bash
gh run view <run-id> --log
```

### List Auto-Fix Issues

```bash
gh issue list --label "workflow-failure"
```

### List Auto-Fix PRs

```bash
gh pr list --label "auto-fix"
```

## Configuration

### Adding More Workflows to Monitor

Edit `.github/workflows/workflow-failure-autofix.yml`:

```yaml
on:
  workflow_run:
    workflows:
      - "Python package"
      - "Your New Workflow Name"  # Add here
    types:
      - completed
```

**Important**: The workflow name must EXACTLY match the `name:` field in the workflow file.

### Customizing Issue/PR Content

Edit the issue body template in the "Create issue for workflow failure" step.

Edit the PR body template in the "Create Pull Request for auto-fix" step.

### Changing Labels

Modify the `labels:` arrays in:
- "Create issue for workflow failure" step
- "Create Pull Request for auto-fix" step

## Best Practices

1. **Test on Feature Branch First**
   - Use manual trigger to test changes to autofix workflows
   - Don't rely on main branch failures for testing

2. **Review Auto-Created PRs**
   - Even with Copilot fixes, always review before merging
   - Auto-fixes may not catch complex issues

3. **Keep Context Files Updated**
   - The quality of Copilot fixes depends on good context
   - Update templates if you find patterns that help

4. **Monitor Autofix Success Rate**
   - Track which types of failures get fixed automatically
   - Improve templates for failure types that don't get fixed well

5. **Don't Disable Autofix Permanently**
   - If autofix creates noise, refine the conditions rather than disabling
   - Use the `if:` condition to filter out certain failure types

## Security Considerations

1. **Token Permissions**
   - The autofix workflow uses `GITHUB_TOKEN`
   - It has `issues: write` and `pull-requests: write` permissions
   - This is necessary for creating issues and PRs

2. **Untrusted Input**
   - The workflow reads data from failed workflows
   - This data is sanitized before use in issues/PRs
   - Don't add unvalidated data to workflow files

3. **Pull Request Reviews**
   - Auto-created PRs are marked as drafts
   - Always require human review before merging
   - Consider requiring approvals even for autofix PRs

## Advanced Usage

### Custom Failure Patterns

You can add custom logic to detect specific failure patterns:

```javascript
// In the "Get workflow run details" step
if (failureDetails.includes('ModuleNotFoundError')) {
  // Add specific guidance for missing module errors
  failureDetails += '\n**Suggested Fix**: Add missing dependency to requirements.txt\n';
}
```

### Automatic PR Approval (Use with Caution)

If you want to auto-approve certain types of fixes:

```yaml
- name: Auto-approve simple fixes
  if: contains(steps.workflow-details.outputs.failure_details, 'simple pattern')
  run: gh pr review ${{ steps.create-pr.outputs.pull-request-number }} --approve
```

**Warning**: This reduces human oversight. Use only for well-understood, low-risk fixes.

### Integration with Other Tools

The autofix system can integrate with:
- Slack notifications (add step to post to Slack)
- Email alerts (use GitHub Actions email action)
- Custom dashboards (export metrics to external system)

## FAQ

**Q: Can I use this system on a private repository?**
A: Yes, but ensure GitHub Copilot is enabled for private repositories in your organization.

**Q: Does this work with self-hosted runners?**
A: Yes, but ensure self-hosted runners have necessary permissions to create issues/PRs.

**Q: Can I customize which failures trigger autofix?**
A: Yes, add conditions in the job's `if:` statement to filter by workflow name, failure type, etc.

**Q: What happens if multiple workflows fail at once?**
A: Each failure creates a separate issue and PR. Consider adding logic to batch related failures.

**Q: Can I use this in a monorepo?**
A: Yes, but you may want to customize the failure detection to filter by changed files.

## Support

For issues with the autofix system:
1. Check this documentation
2. Review workflow run logs in Actions tab
3. Create an issue with label `autofix-system` for help
