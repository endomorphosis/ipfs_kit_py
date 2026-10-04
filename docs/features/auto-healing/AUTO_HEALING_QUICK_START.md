# Auto-Healing Workflows - Quick Start Guide

This guide will help you get started with the auto-healing workflow system in 5 minutes.

## What is Auto-Healing?

When a GitHub Actions workflow fails, the system:
1. 🔍 Automatically detects the failure
2. 📊 Analyzes the logs to find the cause
3. 🔧 Creates a PR with a potential fix
4. 🤖 Triggers GitHub Copilot to review and enhance the fix

## Setup (One-Time)

### 1. Enable Workflow Permissions

Go to your repository settings:
- **Settings** → **Actions** → **General**
- Under "Workflow permissions", select: **Read and write permissions**
- Check: ✅ **Allow GitHub Actions to create and approve pull requests**
- Click **Save**

### 2. (Optional) Enable GitHub Copilot

If you have GitHub Copilot:
- The auto-healing PRs will automatically trigger Copilot review
- Copilot will suggest improvements to the automated fixes
- No additional configuration needed

## How to Use

### Automatic Mode (Default)

The system runs automatically - **no action needed**!

When a workflow fails:
1. Wait 1-2 minutes
2. Check the **Issues** tab for a new issue labeled `auto-heal`
3. Wait another 1-2 minutes
4. Check the **Pull Requests** tab for the auto-generated fix
5. Review and merge the PR

### Manual Trigger

To manually trigger auto-healing for a specific workflow failure:

1. Find the failed workflow run in the **Actions** tab
2. Note the workflow name and run ID
3. Create a new issue with:
   - Title: `[Auto-Heal] Workflow Failure: <workflow-name>`
   - Labels: `auto-heal`, `workflow-failure`
   - Body: Include the workflow run URL
4. The auto-heal workflow will trigger automatically

## Example Workflow

Let's say your "Python Tests" workflow fails:

```
Timeline:
0:00 - Workflow "Python Tests" fails
0:30 - Issue #42 created: "[Auto-Heal] Workflow Failure: Python Tests"
1:00 - PR #43 opened: "[Auto-Heal] Fix workflow: Python Tests"
1:30 - GitHub Copilot reviews the PR (if enabled)
2:00 - You review and merge the PR
2:30 - Workflow is fixed! ✅
```

## What Gets Fixed Automatically?

The system can fix:

✅ Missing Python dependencies  
✅ Timeout issues  
✅ Missing system commands  
✅ File not found errors  
✅ YAML syntax errors  
✅ Permission issues  
✅ Optional job failures  

❌ Cannot fix:
- Complex logic errors
- External service failures
- Missing credentials/secrets
- Infrastructure issues

## Check System Status

### Verify Setup

```bash
# Run the test script
python3 test_auto_healing_system.py

# Should show: "🎉 All tests passed!"
```

### View Auto-Healing Activity

```bash
# List all auto-heal issues
gh issue list --label auto-heal

# List all auto-heal PRs
gh pr list --label auto-heal

# View recent workflow failures
gh run list --status failure --limit 10
```

## Common Scenarios

### Scenario 1: PR Doesn't Auto-Fix the Issue

**What to do:**
1. Comment on the PR explaining what's still wrong
2. The comment helps improve the system
3. Manually fix the issue
4. Merge both fixes

### Scenario 2: No PR Was Created

**Check:**
1. Issue exists with `auto-heal` label? → System is working
2. Check issue comments for "manual intervention required"
3. Error might not be auto-fixable
4. Fix manually and close the issue

### Scenario 3: Too Many Auto-Heal Issues

**Fix:**
1. These might be from a single root cause
2. Find and fix the root issue manually
3. Close duplicate auto-heal issues:
   ```bash
   gh issue list --label auto-heal | xargs -n1 gh issue close
   ```

## Customization

### Disable for Specific Workflows

Add to your workflow file:
```yaml
# At the workflow level
on:
  push:
    branches: [main]
  # Workflow will still fail but won't trigger auto-heal
```

Then add a comment in the workflow:
```yaml
# auto-heal: disabled
# This workflow is excluded from auto-healing
```

### Adjust Fix Patterns

Edit the scripts:
- `scripts/ci/analyze_workflow_failure.py` - Add new error patterns
- `scripts/ci/generate_workflow_fix.py` - Add new fix generators

## Troubleshooting

### Issue: Workflows fail but no issue is created

**Solution:**
1. Check workflow permissions (Step 1 in Setup)
2. Check if workflow-failure-monitor.yml is enabled
3. View workflow logs for errors

### Issue: Issue created but no PR

**Solution:**
1. Check that auto-heal-workflow.yml is enabled
2. Check issue has both labels: `auto-heal` and `workflow-failure`
3. View auto-heal workflow logs

### Issue: PR created but workflow still fails

**Solution:**
1. The fix might be incomplete
2. Review the PR and add additional fixes
3. Test the workflow after merging
4. System learns from feedback

## Get Help

- 📖 Full documentation: [AUTO_HEALING_WORKFLOWS.md](AUTO_HEALING_WORKFLOWS.md)
- 🐛 Report issues: Label with `auto-heal-system`
- 💡 Suggest improvements: Open a discussion

## Next Steps

1. ✅ Complete the one-time setup above
2. ✅ Run `python3 test_auto_healing_system.py` to verify
3. ✅ Let it run automatically
4. ✅ Review and merge auto-heal PRs
5. 🎉 Enjoy self-healing workflows!

---

**Pro Tips:**
- Review auto-heal PRs before merging (always!)
- Comment on PRs to provide feedback
- The system learns from patterns over time
- Keep your workflows simple for better auto-healing
- Use descriptive error messages in your workflows

**Questions?** Check [AUTO_HEALING_WORKFLOWS.md](AUTO_HEALING_WORKFLOWS.md) for detailed documentation.
