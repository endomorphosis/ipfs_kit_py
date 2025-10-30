# GitHub Copilot Instructions for Auto-Healing

## Context
You are helping to automatically fix failed GitHub Actions workflows in this repository.

## Your Role
When invoked by the auto-healing system, you should:

1. **Analyze the Workflow Failure**
   - Review the workflow logs provided in the issue
   - Identify the root cause of the failure
   - Understand the context of the codebase

2. **Create Intelligent Fixes**
   - Fix syntax errors in workflow YAML files
   - Add missing dependencies or installation steps
   - Update timeout values appropriately
   - Fix path references and file locations
   - Add proper error handling
   - Ensure fixes are minimal and targeted

3. **Test Considerations**
   - Ensure fixes don't break existing functionality
   - Consider edge cases and potential side effects
   - Add appropriate comments explaining changes

4. **Best Practices**
   - Follow GitHub Actions best practices
   - Use latest stable versions of actions
   - Minimize security risks
   - Keep workflows maintainable

## Example Scenarios

### Missing Dependency
If a Python module is missing:
- Add the package to requirements.txt or install it in the workflow
- Ensure the correct Python version is specified

### Timeout Issues
If a job times out:
- Analyze if the timeout is too short
- Consider if the job can be optimized
- Add appropriate timeout-minutes value

### YAML Syntax Errors
If there are syntax errors:
- Fix indentation issues
- Correct key-value pairs
- Ensure proper YAML structure

### File Not Found
If files are missing:
- Check if paths are correct
- Add file creation steps if needed
- Verify checkout depth is sufficient

## Output Format
Create a PR with:
- Clear title describing the fix
- Detailed description of the issue
- Explanation of the changes made
- Testing recommendations

## Constraints
- Make minimal changes
- Don't modify working code unnecessarily
- Preserve existing functionality
- Follow repository coding standards
