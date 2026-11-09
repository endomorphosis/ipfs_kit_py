"""Readiness report assembly for VFS release evidence."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "pass", "passed", "success"}


def build_vfs_readiness_report(
    *,
    benchmark_path: str,
    output_path: str,
    contract_suites: Optional[Dict[str, Any]] = None,
    contract_gate_passed: Any = True,
    release_sha: Optional[str] = None,
) -> Dict[str, Any]:
    benchmark_file = Path(benchmark_path)
    benchmark = json.loads(benchmark_file.read_text(encoding="utf-8"))

    suites = contract_suites or {}
    normalized_suites = {
        str(name): _as_bool(result)
        for name, result in suites.items()
    }
    contracts_passed = all(normalized_suites.values()) if normalized_suites else _as_bool(contract_gate_passed)
    benchmark_passed = _as_bool(benchmark.get("success"))
    go_no_go = bool(contracts_passed and benchmark_passed)

    report = {
        "schema_version": "1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "release_sha": release_sha,
        "go_no_go": go_no_go,
        "contracts": {
            "passed": contracts_passed,
            "suites": normalized_suites,
        },
        "benchmark": benchmark,
        "summary": {
            "benchmark_passed": benchmark_passed,
            "contract_gate_passed": contracts_passed,
            "benchmark_output": str(benchmark_file),
        },
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
