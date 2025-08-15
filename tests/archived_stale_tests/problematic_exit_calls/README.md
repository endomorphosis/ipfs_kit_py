# Archived Tests with Problematic exit() Calls

These test files were archived because they contain `sys.exit(1)` or `exit(1)` calls
that prevent pytest from collecting tests properly. These are likely script files
rather than proper pytest test files.

## Issues
- Module-level exit() calls that terminate pytest collection
- Not structured as proper unit tests
- May be diagnostic or utility scripts rather than tests

These files should be reviewed and either:
1. Fixed to remove exit() calls and converted to proper tests
2. Moved to a scripts/ or utilities/ directory if they're not actually tests
3. Deleted if they're obsolete
