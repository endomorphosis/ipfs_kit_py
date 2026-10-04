#!/usr/bin/env python3
"""Validate and optionally materialize the packaged Iroh sign-off artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Direct script execution puts scripts/ci, rather than the checkout root, on
# sys.path. Prefer the checkout under validation over any globally installed
# ipfs_kit_py package.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ipfs_kit_py.iroh.release import (  # noqa: E402 - checkout path bootstrap
    load_release_readiness,
    load_release_receipts,
    promotion_blockers,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-stage", choices=("disabled", "experimental", "canary", "supported"), default="disabled")
    parser.add_argument("--output", type=Path, help="write a CI summary without changing packaged evidence")
    args = parser.parse_args()

    report = load_release_readiness()
    receipts = load_release_receipts()
    blockers = promotion_blockers(args.target_stage, report=report, receipts=receipts)
    summary = {
        "schema_version": 1,
        "kind": "ipfs-kit-iroh-release-verification",
        "release_bundle": report["release_bundle"],
        "target_stage": args.target_stage,
        "approved_stage": report["release_decision"]["approved_stage"],
        "decision": "go" if not blockers else "no_go",
        "blockers": blockers,
        "receipt_ids": [item["id"] for item in receipts["receipts"]],
        "unresolved_critical": receipts["security_findings"]["unresolved_critical"],
        "unresolved_high": receipts["security_findings"]["unresolved_high"]
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
