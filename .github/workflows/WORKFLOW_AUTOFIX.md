# Workflow Failure Auto-Fix System

This system automatically detects GitHub Actions workflow failures and creates infrastructure for GitHub Copilot to implement fixes.

## Overview

When a GitHub Actions workflow fails, this system automatically:

1. **Creates an Issue** - Documents the failure with details, logs, and context
2. **Creates a Draft PR** - Sets up a branch with failure context for implementing fixes
3. **Enables Copilot Integration** - Provides context files that GitHub Copilot can use to understand and fix the failure
4. **Supports Manual Fixes** - Allows developers to manually implement fixes if preferred

## How It Works

### Automatic Failure Detection

The `workflow-failure-autofix.yml` workflow monitors all other workflows using the `workflow_run` trigger:

```yaml
on:
  workflow_run:
    workflows: ["*"]  # Monitor all workflows
    types:
      - completed
```

When a workflow fails:
1. The system captures failure details (failed jobs, steps, logs)
2. Creates an issue tagged with `workflow-failure` and `auto-fix-eligible`
3. Creates a new branch named `auto-fix/workflow-{run_id}`
4. Adds context files to `.github/workflow-failures/`
5. Creates a draft PR with instructions for fixing

### Context Files

The system creates context files that help both humans and AI understand the failure:

- `.github/workflow-failures/failure-{run_id}.md` - Detailed failure information
- `.github/copilot-fix-instructions.md` - Instructions for implementing the fix

These files contain:
- Workflow name and run ID
- Failed jobs and steps
- Common failure patterns and solutions
- Step-by-step fix instructions

### GitHub Copilot Integration

There are two ways to use GitHub Copilot to fix workflow failures:

#### Method 1: Via GitHub Copilot Workspace (Recommended)

1. Open the auto-created draft PR in GitHub Copilot Workspace
2. Copilot will automatically read the context files
3. Use the prompt: 
   ```
   Please analyze the workflow failure context in .github/workflow-failures/ 
   and implement a fix for the failed workflow. Make minimal, targeted changes 
   to address the specific failure.
   ```
4. Review the suggested changes
5. Commit the fixes to the PR branch
6. Mark the PR as ready for review

#### Method 2: Via Issue Comment

1. Find the auto-created issue for the workflow failure
2. Comment: `@copilot /fix-workflow`
3. This triggers the `copilot-auto-fix.yml` workflow
4. Follow the instructions provided in the automated response

### Manual Fixes

If you prefer to fix the workflow manually:

1. Navigate to the auto-created draft PR
2. Check out the PR branch locally
3. Review the failure context in `.github/workflow-failures/`
4. Implement your fix
5. Push changes to the PR branch
6. Mark the PR as ready for review

## Workflow Files

### workflow-failure-autofix.yml

The main workflow that detects and responds to failures:

- **Trigger**: `workflow_run` on completion
- **Condition**: Only runs when conclusion is 'failure'
- **Actions**:
  - Analyzes workflow failure
  - Creates an issue
  - Creates a draft PR with context
  - Sets up for Copilot integration

### copilot-auto-fix.yml

Helper workflow for triggering Copilot fixes:

- **Trigger**: Issue comments or manual dispatch
- **Condition**: Comment contains `@copilot /fix-workflow`
- **Actions**:
  - Links issue to PR
  - Adds helpful labels
  - Provides instructions for using Copilot

## Configuration

### Required Permissions

The workflows require these permissions:

```yaml
permissions:
  contents: write      # To create branches and commits
  issues: write        # To create and comment on issues
  pull-requests: write # To create PRs
  actions: read        # To read workflow run details
```

### Secrets

The workflows use the default `GITHUB_TOKEN` which is automatically provided by GitHub Actions.

### Customization

You can customize the behavior by modifying:

- **Workflow monitoring**: Edit the `workflows` list in the `workflow_run` trigger
- **Issue labels**: Modify the `labels` field in the issue creation step
- **PR template**: Customize the PR body in the `create-pull-request` step
- **Context format**: Edit the format of files in `.github/workflow-failures/`

## Common Failure Patterns

The system includes guidance for common failure types:

### Dependency Issues
- Outdated package versions
- Missing dependencies
- Version conflicts

**Fix**: Update `requirements.txt` or `pyproject.toml` with correct versions

### Syntax Errors
- Invalid YAML in workflow files
- Malformed commands

**Fix**: Validate YAML syntax and correct formatting issues

### Permission Issues
- Insufficient workflow permissions
- Token access problems

**Fix**: Add required permissions to workflow file

### Resource Issues
- Out of memory
- Disk space issues
- Timeout errors

**Fix**: Adjust resource limits or optimize operations

### Test Failures
- Failed unit tests
- Integration test errors
- Linting failures

**Fix**: Address the specific test or linting issues

## Best Practices

1. **Review Before Merging**: Always review auto-generated fixes before merging
2. **Test Locally**: When possible, test fixes locally before pushing
3. **Minimal Changes**: Make the smallest change necessary to fix the issue
4. **Document Fixes**: Update the PR description with what was changed and why
5. **Close Loop**: Ensure the fix actually resolves the failure by monitoring subsequent runs

## Limitations

- **Log Size**: Very large workflow logs may be truncated
- **Concurrency**: Multiple simultaneous failures may create multiple issues/PRs
- **Complexity**: Some failures may be too complex for automated fixing
- **External Dependencies**: Failures due to external service issues may not be fixable

## Troubleshooting

### Issue/PR Not Created

Check that:
- The workflow has necessary permissions
- The `GITHUB_TOKEN` has appropriate scopes
- The repository settings allow workflow runs to create PRs

### Copilot Not Responding

Ensure:
- GitHub Copilot is enabled for your repository
- You're using the correct trigger phrase: `@copilot /fix-workflow`
- The PR has the context files in `.github/workflow-failures/`

### Fix Doesn't Resolve Failure

- Review the original failure logs more carefully
- Check if the issue requires changes outside the workflow file
- Consider if external factors (services, dependencies) are involved

## Examples

### Example 1: Dependency Update Failure

**Failure**: `pip install` fails due to missing package

**Context File Content**:
```markdown
Failed Step: Install dependencies
Error: Could not find a version that satisfies the requirement foo>=2.0.0
```

**Copilot Fix**:
- Updates `requirements.txt` or `pyproject.toml`
- Adjusts version constraints
- Commits with message: "Fix dependency version conflict"

### Example 2: Test Failure

**Failure**: Unit tests fail

**Context File Content**:
```markdown
Failed Step: Test with pytest
Error: test_foo.py::test_bar FAILED
AssertionError: expected 5, got 4
```

**Copilot Fix**:
- Reviews the test file
- Identifies the issue in the code
- Fixes the logic or test expectation
- Commits with message: "Fix failing unit test in test_foo.py"

### Example 3: Workflow Syntax Error

**Failure**: Workflow file has YAML syntax error

**Context File Content**:
```markdown
Failed Step: Workflow validation
Error: Invalid workflow file - unexpected character at line 45
```

**Copilot Fix**:
- Reviews the workflow YAML
- Corrects the syntax error
- Validates the YAML
- Commits with message: "Fix YAML syntax error in workflow"

## Future Enhancements

Potential improvements to this system:

1. **Automatic Retry**: Automatically retry after fix is merged
2. **Learning System**: Track which fixes work and improve suggestions
3. **Notification Integration**: Slack/email notifications for failures
4. **Dashboard**: Web dashboard showing failure trends
5. **Priority Scoring**: Automatically prioritize critical workflow failures
6. **Multi-Repository**: Extend to monitor workflows across multiple repositories

## Contributing

To improve this system:

1. Test the workflows in your environment
2. Report issues or suggest improvements
3. Contribute fixes or enhancements via PR
4. Share successful fix patterns

## Support

For questions or issues:

- Create an issue in the repository
- Tag with `workflow-failure` and `documentation`
- Provide details about your use case

---

**Note**: This system is designed to assist with workflow fixes, not replace human judgment. Always review automated fixes before merging them.
