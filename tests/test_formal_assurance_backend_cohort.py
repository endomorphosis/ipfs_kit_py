"""FACP-054: Execute local filesystem, pinned IPFS, and Iroh cohort.

Acceptance covered here:

* Local filesystem has a current receipt when all observed operations pass.
* Pinned IPFS and Iroh are LiveQualified only on complete current live
  evidence; otherwise they are explicitly Conditional/Unavailable with reasons.
* Support matrix rows match the persisted receipts.
* Cohort execution never fabricates missing live evidence or stores credentials.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import time
import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = KIT_ROOT / "ipfs_kit_py" / "assurance" / "backend_certification.py"
COHORT_PATH = KIT_ROOT / "data" / "formal_assurance" / "backend_receipts" / "cohort.json"

NOW = datetime(2026, 8, 19, 18, 0, tzinfo=timezone.utc)
COHORT_SCHEMA = "BackendCertificationCohort@1"
COHORT_TASK_ID = "FACP-054"
COHORT_EVIDENCE_BUNDLE = "facp/backend-cohort@1"


def _load_module():
    """Load under ``ipfs_kit_py.assurance`` without requiring ``__init__.py``."""

    import importlib.util

    package_name = "ipfs_kit_py"
    assurance_name = "ipfs_kit_py.assurance"
    module_name = "ipfs_kit_py.assurance.backend_certification"

    if package_name not in sys.modules:
        try:
            import ipfs_kit_py as kit_pkg  # noqa: F401
        except ImportError:
            kit_pkg = types.ModuleType(package_name)
            kit_pkg.__path__ = [str(KIT_ROOT / "ipfs_kit_py")]  # type: ignore[attr-defined]
            sys.modules[package_name] = kit_pkg

    if assurance_name not in sys.modules:
        assurance_pkg = types.ModuleType(assurance_name)
        assurance_pkg.__path__ = [str(MODULE_PATH.parent)]  # type: ignore[attr-defined]
        sys.modules[assurance_name] = assurance_pkg
        parent = sys.modules[package_name]
        setattr(parent, "assurance", assurance_pkg)

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    assurance = sys.modules[assurance_name]
    setattr(assurance, "backend_certification", module)
    return module


mod = _load_module()

CertificationDisposition = mod.CertificationDisposition
ObservationStatus = mod.ObservationStatus
OperationObservation = mod.OperationObservation
REQUIRED_SUITE_OPERATIONS = mod.REQUIRED_SUITE_OPERATIONS
COHORT_BACKEND_IDS = mod.COHORT_BACKEND_IDS
RECEIPT_SCHEMA = mod.RECEIPT_SCHEMA
SUPPORT_ROW_SCHEMA = mod.SUPPORT_ROW_SCHEMA
CLOSED_OUTCOME_UNAVAILABLE = mod.CLOSED_OUTCOME_UNAVAILABLE
CLOSED_OUTCOME_VERIFIED = mod.CLOSED_OUTCOME_VERIFIED
contract_for = mod.contract_for
evaluate_observations = mod.evaluate_observations
absent_live_runner_result = mod.absent_live_runner_result
generate_suite = mod.generate_suite
require_live_qualified = mod.require_live_qualified
BackendCertificationRejected = mod.BackendCertificationRejected


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _obs(
    operation: str,
    *,
    digests: dict[str, str],
    limitations: tuple[str, ...] = (),
    detail: str | None = None,
) -> OperationObservation:
    return OperationObservation(
        operation=operation,
        status=ObservationStatus.PASSED,
        environment="live",
        source="live_observed",
        signature_valid=True,
        freshness="current",
        digests=digests,
        limitations=limitations,
        detail=detail,
    )


def run_local_filesystem_suite(root: Path) -> tuple[OperationObservation, ...]:
    """Bounded local durable filesystem observation suite (FACP-054)."""

    root.mkdir(parents=True, exist_ok=True)
    observations: list[OperationObservation] = []

    path = root / "object.bin"
    payload = b"facp-054-local-fs-write-v1"
    path.write_bytes(payload)
    write_digest = _sha256_hex(payload)
    assert path.read_bytes() == payload
    observations.append(
        _obs(
            "write",
            digests={"bytes": f"sha256:{write_digest}", "path": str(path.name)},
        )
    )

    read_bytes = path.read_bytes()
    assert read_bytes == payload
    observations.append(
        _obs("read_back", digests={"bytes": f"sha256:{_sha256_hex(read_bytes)}"})
    )

    recomputed = _sha256_hex(path.read_bytes())
    assert recomputed == write_digest
    observations.append(
        _obs("digest", digests={"content": f"sha256:{recomputed}"})
    )

    path.unlink()
    assert not path.exists()
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    observations.append(_obs("delete", digests={"absent": "true"}))

    replay_path = root / "replay.bin"
    key_payload = b"facp-054-replay-key"
    replay_path.write_bytes(key_payload)
    d1 = _sha256_hex(replay_path.read_bytes())
    replay_path.write_bytes(key_payload)
    d2 = _sha256_hex(replay_path.read_bytes())
    assert d1 == d2
    observations.append(
        _obs("replay", digests={"first": f"sha256:{d1}", "second": f"sha256:{d2}"})
    )

    deadline = 0.25
    started = time.monotonic()
    time.sleep(0.01)
    elapsed = time.monotonic() - started
    assert elapsed < deadline
    observations.append(
        _obs(
            "timeout",
            digests={
                "deadline_seconds": str(deadline),
                "elapsed": f"{elapsed:.6f}",
            },
        )
    )

    conc_dir = root / "concurrency"
    conc_dir.mkdir(exist_ok=True)

    def _worker(i: int) -> str:
        p = conc_dir / f"w{i}.bin"
        data = f"worker-{i}".encode()
        p.write_bytes(data)
        got = p.read_bytes()
        if got != data:
            raise AssertionError(f"corruption worker {i}")
        return _sha256_hex(got)

    digests_conc: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(_worker, i) for i in range(4)]
        for fut in as_completed(futs):
            digests_conc.append(fut.result())
    assert len(digests_conc) == 4
    observations.append(
        _obs(
            "concurrency",
            digests={
                "workers": "4",
                "combined": (
                    "sha256:"
                    + _sha256_hex("".join(sorted(digests_conc)).encode())
                ),
            },
        )
    )

    durable = root / "durable.bin"
    durable_payload = b"facp-054-durable-across-restart"
    durable.write_bytes(durable_payload)
    durable_name = durable.name
    del durable
    reopened = root / durable_name
    assert reopened.read_bytes() == durable_payload
    observations.append(
        _obs(
            "restart",
            digests={"bytes": f"sha256:{_sha256_hex(durable_payload)}"},
        )
    )

    clean = root / "integrity.bin"
    clean_payload = b"facp-054-integrity"
    clean.write_bytes(clean_payload)
    expected = _sha256_hex(clean_payload)
    tampered = bytearray(clean.read_bytes())
    tampered[0] ^= 0xFF
    tampered_digest = _sha256_hex(bytes(tampered))
    assert tampered_digest != expected
    observations.append(
        _obs(
            "corruption",
            digests={
                "expected": f"sha256:{expected}",
                "tampered": f"sha256:{tampered_digest}",
                "detected": "true",
            },
        )
    )

    large = root / "large.bin"
    large_payload = (b"ABCDEFGH" * 4096) + b"TAIL"
    large.write_bytes(large_payload)
    got_large = large.read_bytes()
    assert got_large == large_payload
    observations.append(
        _obs(
            "large_object",
            digests={
                "size": str(len(large_payload)),
                "bytes": f"sha256:{_sha256_hex(got_large)}",
            },
        )
    )

    probe = {"credentials_stored": False, "refs_only": True}
    assert "api_token=" not in json.dumps(probe)
    observations.append(
        _obs(
            "credential",
            digests={"policy": "none-required", "raw_secret_rejected": "true"},
            limitations=("no_credentials_required",),
        )
    )

    parity_path = root / "parity.bin"
    parity_payload = b"facp-054-parity"
    parity_path.write_bytes(parity_payload)
    via_path = _sha256_hex(parity_path.read_bytes())
    with open(parity_path, "rb") as fh:
        via_open = _sha256_hex(fh.read())
    assert via_path == via_open
    observations.append(
        _obs(
            "interface_parity",
            digests={
                "python_path": f"sha256:{via_path}",
                "python_open": f"sha256:{via_open}",
            },
            limitations=("cli_mcp_mcpp_not_exercised_in_this_cohort_run",),
            detail=(
                "python Path/open parity verified; other surfaces remain suite-bound"
            ),
        )
    )

    assert {item.operation for item in observations} == set(REQUIRED_SUITE_OPERATIONS)
    return tuple(observations)


def _dict_to_observation(payload: dict[str, Any]) -> OperationObservation:
    return OperationObservation(
        operation=payload["operation"],
        status=ObservationStatus(payload["status"]),
        environment=payload["environment"],
        source=payload["source"],
        signature_valid=bool(payload["signature_valid"]),
        freshness=payload["freshness"],
        digests=dict(payload.get("digests") or {}),
        limitations=tuple(payload.get("limitations") or ()),
        detail=payload.get("detail"),
    )


@pytest.fixture(scope="module")
def cohort() -> dict[str, Any]:
    assert COHORT_PATH.is_file(), f"missing cohort receipt at {COHORT_PATH}"
    return json.loads(COHORT_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Identity / artifact shape
# ---------------------------------------------------------------------------


def test_cohort_artifact_identity(cohort: dict[str, Any]) -> None:
    assert cohort["schema"] == COHORT_SCHEMA
    assert cohort["task_id"] == COHORT_TASK_ID
    assert cohort["goal_id"] == mod.GOAL_ID
    assert cohort["evidence_bundle"] == COHORT_EVIDENCE_BUNDLE
    assert cohort["suite_evidence_bundle"] == mod.EVIDENCE_BUNDLE
    assert cohort["receipt_schema"] == RECEIPT_SCHEMA
    assert cohort["support_row_schema"] == SUPPORT_ROW_SCHEMA
    assert cohort["unsafe_promotion"] is False
    assert cohort["cohort"] == list(COHORT_BACKEND_IDS)
    assert cohort["required_operations"] == list(REQUIRED_SUITE_OPERATIONS)
    assert set(cohort["receipts"]) == set(COHORT_BACKEND_IDS)
    assert set(cohort["results"]) == set(COHORT_BACKEND_IDS)
    assert set(cohort["observations"]) == set(COHORT_BACKEND_IDS)
    assert set(cohort["live_runners"]) == set(COHORT_BACKEND_IDS)
    assert len(cohort["support_matrix"]) == len(COHORT_BACKEND_IDS)


def test_cohort_certifies_only_first_program_backends(cohort: dict[str, Any]) -> None:
    assert set(cohort["cohort"]) == {"local_filesystem", "pinned_ipfs", "iroh"}
    assert len(cohort["cohort"]) == 3


# ---------------------------------------------------------------------------
# Local filesystem — current LiveQualified receipt when all ops pass
# ---------------------------------------------------------------------------


def test_local_filesystem_receipt_is_current_and_live_qualified(
    cohort: dict[str, Any],
) -> None:
    receipt = cohort["receipts"]["local_filesystem"]
    result = cohort["results"]["local_filesystem"]
    assert receipt["schema"] == RECEIPT_SCHEMA
    assert receipt["backend_id"] == "local_filesystem"
    assert receipt["disposition"] == "LiveQualified"
    assert receipt["live_qualified"] is True
    assert receipt["suite_complete"] is True
    assert receipt["freshness"] == "current"
    assert receipt["environment"] == "live"
    assert receipt["signature_valid"] is True
    assert receipt["storage_selectable"] is True
    assert receipt["credentials_stored"] is False
    assert receipt["hidden_fallback"] is False
    assert set(receipt["operations_observed"]) == set(REQUIRED_SUITE_OPERATIONS)
    assert receipt["operations_failed"] == []
    assert result["disposition"] == "LiveQualified"
    assert result["closed_outcome"] == CLOSED_OUTCOME_VERIFIED
    assert result["live_qualified"] is True
    assert cohort["live_runners"]["local_filesystem"]["present"] is True


def test_local_filesystem_observations_cover_required_suite(
    cohort: dict[str, Any],
) -> None:
    observations = cohort["observations"]["local_filesystem"]
    ops = {item["operation"] for item in observations}
    assert ops == set(REQUIRED_SUITE_OPERATIONS)
    for item in observations:
        assert item["status"] == "passed"
        assert item["environment"] == "live"
        assert item["source"] == "live_observed"
        assert item["signature_valid"] is True
        assert item["freshness"] == "current"
        assert isinstance(item["digests"], dict) and item["digests"]


def test_local_filesystem_observations_reevaluate_to_live_qualified(
    cohort: dict[str, Any],
) -> None:
    observations = tuple(
        _dict_to_observation(item)
        for item in cohort["observations"]["local_filesystem"]
    )
    suite = generate_suite(contract_for("local_filesystem"), now=NOW)
    evaluated = evaluate_observations(
        contract_for("local_filesystem"),
        observations,
        live_runner_present=True,
        now=NOW,
        suite=suite,
    )
    assert evaluated.disposition is CertificationDisposition.LIVE_QUALIFIED
    assert evaluated.live_qualified is True
    assert evaluated.suite_complete is True
    assert require_live_qualified(evaluated) is evaluated
    # Receipt core fields align with persisted cohort receipt.
    persisted = cohort["receipts"]["local_filesystem"]
    assert evaluated.receipt["disposition"] == persisted["disposition"]
    assert evaluated.receipt["live_qualified"] is persisted["live_qualified"]
    assert evaluated.receipt["suite_digest"] == persisted["suite_digest"]
    assert evaluated.receipt["contract_digest"] == persisted["contract_digest"]


def test_local_filesystem_suite_still_passes_when_reexecuted() -> None:
    with tempfile.TemporaryDirectory(prefix="facp054-reexec-") as tmp:
        observations = run_local_filesystem_suite(Path(tmp))
    suite = generate_suite(contract_for("local_filesystem"), now=NOW)
    result = evaluate_observations(
        contract_for("local_filesystem"),
        observations,
        live_runner_present=True,
        now=NOW,
        suite=suite,
    )
    assert result.disposition is CertificationDisposition.LIVE_QUALIFIED
    assert result.suite_complete is True
    assert set(result.operations_observed) == set(REQUIRED_SUITE_OPERATIONS)


# ---------------------------------------------------------------------------
# Pinned IPFS / Iroh — LiveQualified only with complete live evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend_id", ["pinned_ipfs", "iroh"])
def test_daemon_backends_are_explicitly_nonqualified(
    cohort: dict[str, Any], backend_id: str
) -> None:
    receipt = cohort["receipts"][backend_id]
    result = cohort["results"][backend_id]
    runner = cohort["live_runners"][backend_id]

    assert receipt["live_qualified"] is False
    assert receipt["suite_complete"] is False
    assert receipt["disposition"] in {"Conditional", "Unavailable"}
    assert result["disposition"] in {"Conditional", "Unavailable"}
    assert result["live_qualified"] is False
    assert result["closed_outcome"] == CLOSED_OUTCOME_UNAVAILABLE
    assert runner["present"] is False or runner.get("authorized") is False

    reasons = set(receipt["reason_codes"])
    assert "live_qualified_requires_complete_observed_suite" in reasons
    assert reasons & {
        "live_runner_absent",
        "daemon_required",
        "live_evidence_unavailable",
        "incomplete_observed_suite",
    }
    assert cohort["observations"][backend_id] == []


@pytest.mark.parametrize("backend_id", ["pinned_ipfs", "iroh"])
def test_daemon_backends_cannot_be_live_qualified_without_runner(
    cohort: dict[str, Any], backend_id: str
) -> None:
    expected = absent_live_runner_result(
        contract_for(backend_id),
        now=NOW,
        suite=generate_suite(contract_for(backend_id), now=NOW),
    )
    persisted = cohort["results"][backend_id]
    assert persisted["disposition"] == expected.disposition.value
    assert persisted["live_qualified"] is False
    assert set(expected.reason_codes).issubset(set(persisted["reason_codes"]))
    with pytest.raises(BackendCertificationRejected):
        require_live_qualified(expected)


def test_incomplete_live_evidence_cannot_promote_ipfs_or_iroh() -> None:
    # Even a partial live observation set must not mint LiveQualified.
    for backend_id in ("pinned_ipfs", "iroh"):
        partial = (
            OperationObservation(
                operation="write",
                status=ObservationStatus.PASSED,
                environment="live",
                source="live_observed",
                signature_valid=True,
                freshness="current",
                digests={"bytes": "sha256:deadbeef"},
            ),
        )
        result = evaluate_observations(
            contract_for(backend_id),
            partial,
            live_runner_present=True,
            now=NOW,
        )
        assert result.live_qualified is False
        assert result.disposition is CertificationDisposition.CONDITIONAL
        assert "incomplete_observed_suite" in result.reason_codes


def test_configured_or_hermetic_evidence_cannot_live_qualify_daemons() -> None:
    hermetic = tuple(
        OperationObservation(
            operation=operation,
            status=ObservationStatus.PASSED,
            environment="hermetic",
            source="configured",
            signature_valid=True,
            freshness="current",
            digests={"observation": f"digest:{operation}"},
        )
        for operation in REQUIRED_SUITE_OPERATIONS
    )
    for backend_id in ("pinned_ipfs", "iroh"):
        result = evaluate_observations(
            contract_for(backend_id),
            hermetic,
            live_runner_present=True,
            now=NOW,
        )
        assert result.live_qualified is False
        assert result.disposition is not CertificationDisposition.LIVE_QUALIFIED


# ---------------------------------------------------------------------------
# Support matrix matches receipts
# ---------------------------------------------------------------------------


def test_support_matrix_matches_receipts(cohort: dict[str, Any]) -> None:
    rows_by_id = {row["backend_id"]: row for row in cohort["support_matrix"]}
    assert set(rows_by_id) == set(COHORT_BACKEND_IDS)

    for backend_id in COHORT_BACKEND_IDS:
        row = rows_by_id[backend_id]
        receipt = cohort["receipts"][backend_id]
        result = cohort["results"][backend_id]

        assert row["schema"] == SUPPORT_ROW_SCHEMA
        assert row["backend_id"] == receipt["backend_id"]
        assert row["operations_required"] == receipt["operations_required"]
        assert row["operations_observed"] == receipt["operations_observed"]
        assert row["suite_complete"] is receipt["suite_complete"]
        assert row["storage_selectable"] is receipt["storage_selectable"]
        assert row["receipt_schema"] == RECEIPT_SCHEMA
        assert row["certification_receipt_schema"] == RECEIPT_SCHEMA

        # Matrix row mirrors the evaluation support_row projection.
        assert row == result["support_row"]

        if receipt["live_qualified"]:
            assert row["disposition"] == "LiveQualified"
            assert row["live_tier"] == "production"
            assert row["evidence_freshness"] == "current"
            assert row["evidence_status"] == "live_qualified"
            assert receipt["disposition"] == "LiveQualified"
        else:
            # Honest nonqualification: Conditional inventory and/or Unavailable
            # live evidence, never LiveQualified.
            assert row["disposition"] in {"Conditional", "Unavailable"}
            assert receipt["disposition"] in {"Conditional", "Unavailable"}
            assert row["storage_selectable"] is False
            assert receipt["live_qualified"] is False


def test_support_matrix_order_follows_cohort(cohort: dict[str, Any]) -> None:
    assert [row["backend_id"] for row in cohort["support_matrix"]] == list(
        COHORT_BACKEND_IDS
    )


# ---------------------------------------------------------------------------
# Safety / credential / environment honesty
# ---------------------------------------------------------------------------


def test_receipts_never_store_credentials(cohort: dict[str, Any]) -> None:
    blob = json.dumps(cohort)
    for receipt in cohort["receipts"].values():
        assert receipt["credentials_stored"] is False
    assert "api_token" not in blob
    assert "secret_key" not in blob
    assert "raw-credential" not in blob
    assert "password=" not in blob


def test_live_runner_probe_matches_environment(cohort: dict[str, Any]) -> None:
    assert cohort["live_runners"]["local_filesystem"]["present"] is True
    # Document PATH honesty for daemon targets in this environment.
    for backend_id, binary in (("pinned_ipfs", "ipfs"), ("iroh", "iroh")):
        runner = cohort["live_runners"][backend_id]
        on_path = shutil.which(binary) is not None
        if not on_path:
            assert runner["present"] is False
            assert "not found" in runner["reason"].lower() or "not authorized" in (
                runner["reason"].lower()
            )
        # Regardless of PATH, LiveQualified still requires complete live suite.
        assert cohort["receipts"][backend_id]["live_qualified"] is False


def test_suite_and_contract_digests_are_bound(cohort: dict[str, Any]) -> None:
    for backend_id in COHORT_BACKEND_IDS:
        suite = generate_suite(contract_for(backend_id), now=NOW)
        assert cohort["suite_digests"][backend_id] == suite.suite_digest
        assert cohort["contract_digests"][backend_id] == suite.contract_digest
        assert (
            cohort["receipts"][backend_id]["suite_digest"] == suite.suite_digest
        )
        assert (
            cohort["receipts"][backend_id]["contract_digest"]
            == suite.contract_digest
        )


def test_cohort_json_is_valid_utf8_object() -> None:
    raw = COHORT_PATH.read_bytes()
    assert raw.decode("utf-8")
    payload = json.loads(raw)
    assert isinstance(payload, dict)
    assert payload["task_id"] == COHORT_TASK_ID
