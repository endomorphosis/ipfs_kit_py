"""PCPR-053: produce Kit dependency locks."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.assurance.dependency_locks import (
    CLOSED_RELEASE_OUTCOMES,
    CURRENT_HEAD_NON_PROMOTION_VERDICT_CID,
    HERMETIC_CANDIDATE_SUITES,
    INTERFACE,
    LOCK_KIND,
    NAMED_GIT_EXTRAS,
    OutcomeProbe,
    PCPR_053_GOAL_ID,
    PCPR_053_TASK_ID,
    SCHEMA,
    SEALED_PATH,
    SEALED_PYTHON,
    DependencyLockError,
    current_head_static_probes,
    pcpr_053_receipt_promotion,
    qualify_current_head_dependency_locks,
    qualify_dependency_locks,
    render_release_lock,
    scan_requirement_text,
    verify_lock_files,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_closed_vocabularies_match_pcpr_053_requirements() -> None:
    assert PCPR_053_TASK_ID == "PCPR-053"
    assert PCPR_053_GOAL_ID == "PCPR-G600"
    assert INTERFACE == "KitDependencyLocks@1"
    assert SCHEMA == "ipfs_kit_py/assurance/dependency-locks@1"
    assert LOCK_KIND == "declared_release_profile"
    assert NAMED_GIT_EXTRAS == ("libp2p", "ipld-github")
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith("test_pcpr_053_dependency_locks.py")
    assert SEALED_PATH == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
    assert SEALED_PYTHON == "/usr/bin/python3.12"
    document = render_release_lock()
    assert document["direct_requirement_count"] == 22
    assert document["mutable_git"] is False
    assert document["editable"] is False
    assert document["live"] is False
    assert document["release_claim"] is False
    assert document["closed_release_outcome"] is None
    assert document["hashes"]["invented"] is False
    assert document["requirements_authority"] == "pyproject.toml:project.dependencies"
    assert document["native_dependencies"]["libmagic"]["status"] == "unavailable"


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_dependency_locks()
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.sibling_source_required is False
    assert verdict.mutable_git_release_lock is False
    assert verdict.hashes_invented is False
    assert verdict.live_resolver_qualified is False
    assert verdict.live_resolver_evidence_kind == "unavailable"
    assert verdict.hash_lock_evidence_kind == "unavailable"
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("baguqeera")
    assert verdict.verdict_cid == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID
    assert verdict.blockers == ()
    section = pcpr_053_receipt_promotion(verdict)
    assert section["promotion_status"] == "rnd_non_promoted"
    assert section["closed_release_outcome"] is None
    assert section["release_claim"] is False
    assert section["verdict_cid"] == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID


def test_static_probes_show_declared_lock_constraints() -> None:
    probes = {item.probe_id: item for item in current_head_static_probes()}
    assert probes["release_lock_has_no_vcs"].present is True
    assert probes["release_lock_has_no_editable"].present is True
    assert probes["release_lock_has_no_path"].present is True
    assert probes["hashes_not_invented"].present is True
    assert probes["lock_files_match_generator"].present is True
    assert probes["pyproject_dependency_locks_table"].present is True
    assert probes["requirements_authority_agrees"].present is True
    assert probes["named_git_extras_are_not_release_lock"].present is True
    assert probes["mutable_git_in_release_lock"].present is False
    assert probes["live_resolver"].evidence_kind == "unavailable"
    for probe in probes.values():
        assert probe.live is False
        assert probe.simulated_represented_as_live is False


def test_committed_lock_files_match_generator() -> None:
    verified = verify_lock_files()
    assert verified["ok"] is True
    pyproject = (_PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'interface = "KitDependencyLocks@1"' in pyproject
    assert "libp2p @ git+" in pyproject
    core = pyproject.split("dependencies = [", 1)[1].split("\n]", 1)[0]
    assert "git+" not in core
    assert scan_requirement_text(core)["vcs"] == ()


def test_simulated_live_probe_is_rejected() -> None:
    with pytest.raises(DependencyLockError, match="simulated"):
        qualify_dependency_locks(
            (
                OutcomeProbe(
                    probe_id="bogus",
                    present=False,
                    evidence_kind="simulated",
                    live=False,
                    simulated_represented_as_live=True,
                    reason="must fail",
                ),
            ),
            lock_cid="baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
