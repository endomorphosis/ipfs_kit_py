"""CI helper script: fail if deprecated endpoints have passed their planned removal version.

Usage:
    python verify_deprecations.py [--version <current_version>]
Falls back to reading version from pyproject.toml if not supplied.

Exit codes:
    0 - OK
    1 - Violation detected
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

from consolidated_mcp_dashboard import ConsolidatedMCPDashboard

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

def parse_version(v: str):
    m = SEMVER_RE.match(v.strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups())

def current_version(cli_arg: str | None) -> str:
    if cli_arg:
        return cli_arg
    # Try pyproject
    pp = Path("pyproject.toml")
    if pp.exists():
        txt = pp.read_text(encoding="utf-8")
        with_version = re.search(r"^version\s*=\s*['\"]([^'\"]+)['\"]", txt, re.MULTILINE)
        if with_version:
            return with_version.group(1)
    return "0.0.0"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="Current package version")
    args = ap.parse_args()
    ver = current_version(args.version)
    parsed_now = parse_version(ver) or (0,0,0)

    dash = ConsolidatedMCPDashboard({})
    violations = []
    for ep, remove_in in dash.DEPRECATED_ENDPOINTS.items():
        parsed_remove = parse_version(remove_in)
        if parsed_remove and parsed_now >= parsed_remove:
            violations.append({"endpoint": ep, "remove_in": remove_in, "current": ver})
    if violations:
        print("Deprecated endpoints past removal version:")
        print(json.dumps(violations, indent=2))
        sys.exit(1)
    print("All deprecations within allowed window (current version:", ver, ")")

if __name__ == "__main__":
    main()
