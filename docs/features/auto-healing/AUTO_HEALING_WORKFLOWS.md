# Auto-Healing Workflow System

This document describes the automated workflow failure detection and repair system implemented in this repository.

## Overview

The auto-healing system automatically detects failed GitHub Actions workflows, analyzes the failures, and creates pull requests with potential fixes. This system eliminates the need for manual intervention in many common workflow failure scenarios.

## How It Works

### 1. Failure Detection

The **Workflow Failure Monitor** (`workflow-failure-monitor.yml`) runs automatically whenever any workflow in the repository completes with a failure status.

**Trigger:** `workflow_run` event with `conclusion: failure`

**Actions:**
- Detects the failed workflow
- Analyzes failure logs and error messages
- Creates a GitHub issue with failure details
- Labels the issue with `auto-heal` and `workflow-failure`

### 2. Automatic Fix Generation

The **Auto-Heal Workflow** (`auto-heal-workflow.yml`) triggers when an issue with the `auto-heal` label is created or labeled.

**Trigger:** `issues` event with `auto-heal` and `workflow-failure` labels

**Actions:**
- Parses the failure details from the issue
- Analyzes the workflow logs to identify error patterns
- Generates potential fixes for common issues
- Creates a new branch with fixes
- Opens a pull request with the proposed changes
- Links the PR back to the original issue

### 3. GitHub Copilot Integration

Once the auto-healing PR is created:
- GitHub Copilot agent is automatically invoked (if configured in repository settings)
- Copilot can review and enhance the automated fix
- The system learns from patterns and improves over time

## Components

### Workflows

#### `workflow-failure-monitor.yml`
- **Purpose:** Monitor all workflows for failures
- **Trigger:** On any workflow completion
- **Permissions:** `contents: read`, `actions: read`, `issues: write`
- **Output:** GitHub issue with failure analysis

#### `auto-heal-workflow.yml`
- **Purpose:** Generate and submit fixes for failed workflows
- **Trigger:** When issue is labeled with `auto-heal`
- **Permissions:** `contents: write`, `pull-requests: write`, `issues: write`, `actions: read`
- **Output:** Pull request with proposed fixes

### Scripts

#### `scripts/ci/analyze_workflow_failure.py`
Analyzes workflow failures by:
- Fetching workflow run details via GitHub API
- Downloading and parsing job logs
- Extracting error messages and patterns
- Categorizing errors by type (missing dependencies, timeouts, etc.)
- Generating structured failure analysis

#### `scripts/ci/generate_workflow_fix.py`
Generates fixes by:
- Loading failure analysis
- Identifying fixable error patterns
- Generating appropriate fixes for each pattern type
- Modifying workflow files with improvements
- Creating detailed fix reports for PRs

## Supported Fix Types

The auto-healing system can automatically fix:

1. **Missing Dependencies**
   - Adds missing Python packages to install steps
   - Updates requirements.txt references

2. **Timeout Issues**
   - Increases `timeout-minutes` for jobs
   - Adds timeout configurations where missing

3. **Missing Commands**
   - Adds installation steps for missing system commands
   - Updates PATH configuration

4. **File Not Found Errors**
   - Adds file existence checks
   - Updates file path references

5. **YAML Syntax Errors**
   - Fixes common YAML formatting issues
   - Corrects indentation problems

6. **Optional Job Failures**
   - Adds `continue-on-error: true` for optional jobs
   - Configures ARM64 or experimental features as non-blocking

7. **Rate Limiting**
   - Adds retry logic
   - Implements backoff strategies

## Usage

### Automatic Operation

The system works automatically - no manual intervention needed:

1. A workflow fails
2. Issue is created within minutes
3. Auto-heal PR is generated
4. Review and merge the PR

### Manual Trigger

To manually trigger the auto-healing system:

1. Create or find an issue about a workflow failure
2. Add the labels: `auto-heal` and `workflow-failure`
3. The auto-heal workflow will trigger automatically

### Disabling Auto-Healing

To disable auto-healing for a specific workflow failure:
1. Remove the `auto-heal` label from the issue
2. Add the `needs-manual-fix` label
3. The auto-healing system will skip this issue

## Configuration

### Repository Settings

Ensure the following are configured:

1. **GitHub Actions Permissions**
   - Settings → Actions → General
   - Set "Workflow permissions" to "Read and write permissions"
   - Enable "Allow GitHub Actions to create and approve pull requests"

2. **GitHub Copilot** (Optional but Recommended)
   - Enable GitHub Copilot for the repository
   - Configure Copilot to review PRs automatically
   - The auto-healing PRs will trigger Copilot review

### Environment Variables

The workflows use these environment variables (automatically provided by GitHub):
- `GITHUB_TOKEN`: Authentication token
- `WORKFLOW_RUN_ID`: ID of the failed workflow run
- `WORKFLOW_NAME`: Name of the failed workflow
- `REPOSITORY`: Repository name (owner/repo)

## Workflow Dependencies

Required Python packages (installed automatically in workflows):
```bash
pip install PyGithub requests pyyaml
```

## Limitations

### Cannot Auto-Fix

The system may not be able to automatically fix:
- Complex logic errors in code
- Infrastructure or external service failures
- Security vulnerabilities requiring manual review
- Failures due to missing secrets or credentials

In these cases, the system will:
- Create an issue with analysis
- Add the `needs-manual-fix` label
- Provide guidance for manual intervention

### Rate Limits

GitHub API rate limits may affect the system:
- Workflow monitoring: Limited by Actions concurrent jobs
- Issue creation: Subject to GitHub API rate limits
- Log downloads: May be throttled for very large logs

## Monitoring

### Check Auto-Healing Status

View auto-healing activity:
```bash
# List all auto-heal issues
gh issue list --label auto-heal

# List all auto-heal PRs
gh pr list --label auto-heal

# View specific workflow failure
gh run view <run-id> --log-failed
```

### Success Metrics

Track auto-healing effectiveness:
- Number of issues created
- Number of PRs generated
- PR merge rate
- Time to fix (issue creation to PR merge)

## Examples

### Example 1: Missing Dependency

**Failure:**
```
ModuleNotFoundError: No module named 'requests'
```

**Auto-Generated Fix:**
```yaml
- name: Install dependencies
  run: |
    pip install requests
    pip install -r requirements.txt
```

### Example 2: Timeout Issue

**Failure:**
```
Error: The operation was canceled.
Job timed out after 30 minutes
```

**Auto-Generated Fix:**
```yaml
jobs:
  test:
    timeout-minutes: 60  # Increased from default 30
```

### Example 3: Optional Job Failure

**Failure:**
```
Job 'test-arm64' failed on self-hosted runner
```

**Auto-Generated Fix:**
```yaml
jobs:
  test-arm64:
    continue-on-error: true  # Added to prevent pipeline failure
```

## Troubleshooting

### Issue: Auto-heal PR not created

**Possible causes:**
- Missing workflow permissions
- Rate limit exceeded
- No fixable error pattern detected

**Solution:**
- Check workflow logs for errors
- Verify repository permissions
- Review issue comments for details

### Issue: PR contains incorrect fix

**Solution:**
1. Comment on the PR with the issue
2. Close the PR
3. The system will learn from feedback
4. Manually fix the workflow
5. Update the auto-heal logic if needed

### Issue: System creates duplicate issues

**Prevention:** The system checks for existing issues created within 24 hours

**Manual cleanup:**
```bash
gh issue list --label auto-heal | xargs -n1 gh issue close
```

## Best Practices

1. **Review Auto-Generated PRs**
   - Always review the PR before merging
   - Verify the fix addresses the root cause
   - Test the fix if possible

2. **Provide Feedback**
   - Comment on PRs with issues or improvements
   - This helps improve the auto-healing logic

3. **Keep Workflows Updated**
   - Use latest action versions
   - Follow GitHub Actions best practices
   - Add appropriate error handling

4. **Monitor Patterns**
   - Review recurring failures
   - Update auto-healing logic for common issues
   - Document complex fixes

## Future Enhancements

Planned improvements:
- Machine learning-based fix generation
- Integration with external monitoring tools
- Automatic rollback on fix failure
- Multi-repository auto-healing
- Custom fix templates per workflow type

## Contributing

To improve the auto-healing system:

1. Add new error patterns in `analyze_workflow_failure.py`
2. Implement fix generators in `generate_workflow_fix.py`
3. Update workflow files as needed
4. Add tests for new fix types
5. Update this documentation

## Support

For issues with the auto-healing system:
1. Check existing issues labeled `auto-heal-system`
2. Review workflow logs
3. Create a new issue with:
   - Failed workflow details
   - Auto-healing behavior observed
   - Expected behavior
   - Relevant logs

## License

This auto-healing system is part of the ipfs_kit_py project and follows the same license.
