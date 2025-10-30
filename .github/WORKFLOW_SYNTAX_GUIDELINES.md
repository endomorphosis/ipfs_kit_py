# GitHub Actions Workflow Syntax Guidelines

## Common Pitfalls and Best Practices

### Problem: Template Literals in github-script Actions

**Issue**: Using JavaScript template literals (backticks) in `actions/github-script@v7` steps can cause "Invalid or unexpected token" syntax errors when combined with YAML variable interpolation.

#### Why This Happens

When you write:
```yaml
- uses: actions/github-script@v7
  with:
    script: |
      const message = `Hello ${someVar}`;
      const issue = `Issue: ${{ steps.previous.outputs.value }}`;
```

The YAML parser and JavaScript interpreter conflict:
- YAML sees `${{ }}` and tries to interpolate it
- JavaScript sees `` `${}` `` and expects a template literal
- The result is malformed JavaScript that causes runtime errors

#### ✓ Correct Approach: Use String Concatenation

```yaml
- uses: actions/github-script@v7
  with:
    script: |
      const message = 'Hello ' + someVar;
      const issue = 'Issue: ${{ steps.previous.outputs.value }}';
      
      // For multiline strings
      const body = 'Line 1\n' +
                   'Line 2: ' + variable + '\n' +
                   'Line 3';
```

#### ✗ Avoid: Template Literals with YAML Variables

```yaml
# DON'T DO THIS
- uses: actions/github-script@v7
  with:
    script: |
      const issue = `
        # Title: ${title}
        Value: ${{ steps.output.value }}
      `;
```

### Examples from Fixes

#### Before (Broken)
```javascript
const issueBody = `# Workflow Failure: ${workflow_name}

A workflow has failed and requires attention.

## Failure Details

- **Workflow**: ${workflow_name}
- **Run ID**: ${workflow_run.id}
- **Branch**: ${branch}
- **Run URL**: ${workflow_url}
`;
```

#### After (Fixed)
```javascript
const issueBody = '# Workflow Failure: ' + workflow_name + '\n\n' +
  'A workflow has failed and requires attention.\n\n' +
  '## Failure Details\n\n' +
  '- **Workflow**: ' + workflow_name + '\n' +
  '- **Run ID**: ' + workflow_run.id + '\n' +
  '- **Branch**: ' + branch + '\n' +
  '- **Run URL**: ' + workflow_url + '\n';
```

### Other Best Practices

#### 1. YAML Validation
Always validate YAML syntax before committing:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/your-workflow.yml'))"
```

#### 2. Multi-line Strings
Use YAML's `|` or `>` operators correctly:
```yaml
# Literal block scalar (preserves newlines)
script: |
  line 1
  line 2

# Folded block scalar (joins lines)
description: >
  This is a long
  description that will
  be joined into one line
```

#### 3. Escaping
When you must use special characters:
```yaml
# Escape backticks in regular strings
message: 'Use `code` formatting'

# For actual backticks in JavaScript, use \`
script: |
  const cmd = 'echo \`date\`';
```

#### 4. Testing
- Test workflows with `act` locally before pushing
- Use workflow_dispatch for manual testing
- Start with small, simple scripts and build up

### Quick Reference

| Use Case | Recommended Syntax |
|----------|-------------------|
| Simple variable | `'text' + variable` |
| Multiple variables | `'a' + var1 + 'b' + var2` |
| Multiline | `'line1\n' + 'line2\n'` |
| YAML variable | `'value: ${{ steps.id.outputs.name }}'` |
| Backticks (code) | `'Use \`code\` here'` |

### Related Issues

- Fixed in PR #92: workflow-failure-autofix.yml had 3 locations with this issue
- Affected lines: 65-73, 129-165, 336-347
- Error message: "SyntaxError: Invalid or unexpected token"

### Further Reading

- [GitHub Actions Contexts](https://docs.github.com/en/actions/learn-github-actions/contexts)
- [YAML Multiline Strings](https://yaml-multiline.info/)
- [actions/github-script Documentation](https://github.com/actions/github-script)
