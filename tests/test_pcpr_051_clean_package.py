"""PCPR-051: build clean Kit package."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.clean_package import (
    CANONICAL_LICENSE_CLASSIFIER,
    CANONICAL_PYTHON_CLASSIFIER,
    CANONICAL_PYTHON_REQUIRES,
    CLOSED_RELEASE_OUTCOMES,
    CURRENT_HEAD_NON_PROMOTION_VERDICT_CID,
    FIND_PACKAGE_EXCLUDES,
    HERMETIC_CANDIDATE_SUITES,
    INTERFACE,
    MANIFEST_PRUNE_LINES,
    NAMED_GIT_EXTRAS,
    OutcomeProbe,
    PCPR_051_GOAL_ID,
    PCPR_051_TASK_ID,
    RECURSIVE_SUBMODULE_TREES,
    SCHEMA,
    SEALED_PATH,
    SEALED_PYTHON,
    SIBLING_TREES,
    CleanPackageError,
    clean_package_manifest,
    current_head_static_probes,
    parse_setup_wrapper,
    pcpr_051_receipt_promotion,
    qualify_clean_package,
    qualify_current_head_clean_package,
    scan_requirement_text,
)


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_closed_vocabularies_match_pcpr_051_requirements() -> None:
    assert PCPR_051_TASK_ID == "PCPR-051"
    assert PCPR_051_GOAL_ID == "PCPR-G600"
    assert INTERFACE == "KitCleanPackage@1"
    assert SCHEMA == "ipfs_kit_py/assurance/clean-package@1"
    assert CANONICAL_PYTHON_REQUIRES == ">=3.12"
    assert CANONICAL_PYTHON_CLASSIFIER == "Programming Language :: Python :: 3.12"
    assert SIBLING_TREES == ("ipfs_accelerate_py", "ipfs_datasets_py", ".tools")
    assert RECURSIVE_SUBMODULE_TREES == (
        "py-ipld-car",
        "py-ipld-dag-pb",
        "py-ipld-unixfs",
    )
    assert NAMED_GIT_EXTRAS == ("libp2p", "ipld-github")
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith("test_pcpr_051_clean_package.py")
    assert SEALED_PATH == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
    assert SEALED_PYTHON == "/usr/bin/python3.12"
    manifest = clean_package_manifest()
    assert manifest["requires_sibling_source_trees"] is False
    assert manifest["mutable_git_release_requires"] is False
    assert manifest["requires_recursive_submodules"] is False
    assert manifest["import_side_effects"] == "none"
    assert manifest["runtime_requires_authority"] == (
        "pyproject.toml:project.dependencies"
    )


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_clean_package()
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.sibling_source_required is False
    assert verdict.mutable_git_release_requires is False
    assert verdict.isolated_import_without_siblings is True
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.live_backend_qualified is False
    assert verdict.live_backend_evidence_kind == "unavailable"
    assert verdict.built_wheel_evidence_kind == "unavailable"
    assert verdict.built_sdist_evidence_kind == "unavailable"
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("baguqeera")
    assert verdict.verdict_cid == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID
    assert verdict.blockers == ()
    section = pcpr_051_receipt_promotion(verdict)
    assert section["promotion_status"] == "rnd_non_promoted"
    assert section["closed_release_outcome"] is None
    assert section["release_claim"] is False
    assert section["isolated_import_without_siblings"] is True
    assert section["live_backend_qualified"] is False
    assert section["verdict_cid"] == CURRENT_HEAD_NON_PROMOTION_VERDICT_CID


def test_static_probes_show_clean_package_constraints() -> None:
    probes = {item.probe_id: item for item in current_head_static_probes()}
    assert probes["release_requires_have_no_vcs"].present is True
    assert probes["release_requires_have_no_editable"].present is True
    assert probes["mutable_git_release_requires"].present is False
    assert probes["editable_local_release_requires"].present is False
    assert probes["pyproject_core_dependencies_are_pypi"].present is True
    assert probes["python_requires_agrees"].present is True
    assert probes["python_classifier_agrees"].present is True
    assert probes["pyproject_python_classifier_agrees"].present is True
    assert probes["sibling_packages_excluded"].present is True
    assert probes["sibling_submodules_pruned"].present is True
    assert probes["recursive_submodules_pruned"].present is True
    assert probes["pyproject_clean_package_table"].present is True
    assert probes["package_init_has_no_sys_path_injection"].present is True
    assert probes["git_extras_are_not_release_profile"].present is True
    assert probes["full_extra_has_no_vcs"].present is True
    assert probes["setup_defers_to_pyproject"].present is True
    assert probes["manifest_advertises_clean_package"].present is True
    assert probes["isolated_import_without_siblings"].present is True
    assert probes["isolated_import_without_siblings"].evidence_kind == (
        "measured_hermetic"
    )
    assert probes["sibling_source_imported"].present is False
    assert probes["sys_path_injection_observed"].present is False
    assert probes["simulated_results_represented_as_live"].present is False
    assert probes["built_wheel_represented_as_live"].present is False
    assert probes["built_sdist_represented_as_live"].present is False
    assert probes["published_release_represented_as_live"].present is False
    assert probes["live_backend_qualification"].evidence_kind == "unavailable"
    assert probes["live_backend_qualification"].present is None
    assert probes["built_wheel_metadata"].evidence_kind == "unavailable"
    assert probes["built_sdist_metadata"].evidence_kind == "unavailable"
    for probe in probes.values():
        assert probe.live is False
        assert probe.simulated_represented_as_live is False


def test_packaging_files_declare_clean_install_constraints() -> None:
    pyproject = (_PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    setup = (_PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")
    manifest = (_PACKAGE_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    wrapper = parse_setup_wrapper(setup)
    assert wrapper["metadata_source"] == "pyproject.toml"
    assert wrapper["has_install_requires_assignment"] is False
    assert wrapper["calls_bare_setup"] is True
    assert 'requires-python = ">=3.12"' in pyproject
    assert CANONICAL_PYTHON_CLASSIFIER in pyproject
    assert CANONICAL_LICENSE_CLASSIFIER in pyproject
    assert 'interface = "KitCleanPackage@1"' in pyproject
    assert "requires-sibling-source-trees = false" in pyproject
    assert 'include = ["ipfs_kit_py", "ipfs_kit_py.*"]' in pyproject
    assert '"external*"' in pyproject
    assert '"external" = ["**/*"]' not in pyproject
    assert 'include = ["ipfs_kit_py*", "external*"]' not in pyproject
    for line in MANIFEST_PRUNE_LINES:
        assert line in manifest
    for marker in FIND_PACKAGE_EXCLUDES:
        assert f'"{marker}"' in pyproject
    assert "libp2p @ git+" in pyproject
    assert 'libp2p @ git+https://github.com/libp2p/py-libp2p.git@main"' not in (
        pyproject.split("[project.optional-dependencies]", 1)[-1].split(
            "libp2p = [", 1
        )[0]
    )
    full_block = pyproject.split("full = [", 1)[1].split("\n]", 1)[0]
    assert "git+" not in full_block
    core_block = pyproject.split("dependencies = [", 1)[1].split("\n]", 1)[0]
    assert "git+" not in core_block
    requirements = (_PACKAGE_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert scan_requirement_text(requirements)["vcs"] == ()
    assert scan_requirement_text(core_block)["vcs"] == ()


def test_scan_requirement_text_rejects_git_and_editable() -> None:
    hits = scan_requirement_text(
        "libp2p @ git+https://github.com/libp2p/py-libp2p.git@main\n-e ../ipfs_datasets_py\n"
    )
    assert hits["vcs"]
    assert hits["editable"]
    clean = scan_requirement_text("requests>=2.28.0\n")
    assert clean["vcs"] == ()
    assert clean["editable"] == ()


def test_simulated_live_probe_is_rejected() -> None:
    with pytest.raises(CleanPackageError, match="simulated"):
        qualify_clean_package(
            (
                OutcomeProbe(
                    probe_id="bogus",
                    present=False,
                    evidence_kind="simulated",
                    live=False,
                    simulated_represented_as_live=True,
                    reason="must fail",
                ),
            )
        )


def test_live_claim_without_measured_live_evidence_is_rejected() -> None:
    with pytest.raises(CleanPackageError, match="measured_live"):
        qualify_clean_package(
            (
                OutcomeProbe(
                    probe_id="bogus",
                    present=True,
                    evidence_kind="measured",
                    live=True,
                    simulated_represented_as_live=False,
                    reason="must fail",
                ),
            )
        )


def test_receipt_promotion_rejects_closed_release() -> None:
    verdict = qualify_current_head_clean_package()
    with pytest.raises(CleanPackageError, match="closed release"):
        pcpr_051_receipt_promotion(
            replace(verdict, closed_release_outcome="release_candidate_qualified")
        )
    with pytest.raises(CleanPackageError, match="claim a PCPR release"):
        pcpr_051_receipt_promotion(replace(verdict, release_claim=True))
    with pytest.raises(CleanPackageError, match="DuckDB or Quack"):
        pcpr_051_receipt_promotion(
            replace(verdict, duckdb_or_quack_state_written=True)
        )
