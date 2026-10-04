#!/usr/bin/env python3
"""Generate a single VFS readiness evidence report from benchmark output and contract status."""

from __future__ import annotations

import argparse
import json
import os
import sys

from ipfs_kit_py.vfs_readiness_report import build_vfs_readiness_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate VFS readiness release evidence")
    parser.add_argument("--benchmark", default=os.environ.get("IPFS_KIT_VFS_BENCHMARK_OUT", "build/vfs_readiness_benchmark.json"))
    parser.add_argument("--output", default=os.environ.get("IPFS_KIT_VFS_READINESS_REPORT_OUT", "build/vfs_readiness_report.json"))
    parser.add_argument("--release-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--contracts-passed", default=os.environ.get("IPFS_KIT_VFS_CONTRACTS_PASSED", "1"))
    parser.add_argument(
        "--suites",
        default=os.environ.get(
            "IPFS_KIT_VFS_CONTRACT_SUITES",
            json.dumps(
                {
                    "test_vfs_contract_hardening.py": True,
                    "test_datasets_metadata_index_contract.py": True,
                    "test_mcp_vfs_adapter_contract.py": True,
                    "test_vfs_mcp_integration.py": True,
                    "test_vfs_readiness_benchmark_contract.py": True,
                }
            ),
        ),
    )
    args = parser.parse_args()

    suites = json.loads(args.suites) if args.suites else {}
    report = build_vfs_readiness_report(
        benchmark_path=args.benchmark,
        output_path=args.output,
        contract_suites=suites,
        contract_gate_passed=args.contracts_passed,
        release_sha=args.release_sha,
    )

    print(json.dumps(report, indent=2, sort_keys=True))
    if not report.get("go_no_go", False):
        print("VFS readiness report indicates not ready for release", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
