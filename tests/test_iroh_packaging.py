"""IROH-026 CI policy and built-distribution smoke tests."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "scripts" / "ci" / "verify_iroh_distributions.py"
SMOKE_PATH = ROOT / "scripts" / "ci" / "iroh_install_smoke.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "iroh-ci.yml"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_iroh_distributions", VERIFY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built_distributions(tmp_path_factory: pytest.TempPathFactory):
    """Build from a clean staging tree while planting forbidden local state."""

    build = pytest.importorskip("build")
    del build
    staging = tmp_path_factory.mktemp("iroh-package-source")
    for filename in ("pyproject.toml", "setup.py", "MANIFEST.in", "README.md", "LICENSE"):
        shutil.copy2(ROOT / filename, staging / filename)

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name == "__pycache__" or name.endswith((".pyc", ".pyo"))}
        if Path(directory).name == "bin":
            ignored.update(names)
        return ignored

    shutil.copytree(ROOT / "ipfs_kit_py", staging / "ipfs_kit_py", ignore=ignore)

    # These simulate developer-local runtime state. Both wheel and sdist must
    # exclude them even though the broad legacy package-data rule sees them.
    local_bin = staging / "ipfs_kit_py" / "bin"
    local_bin.mkdir(exist_ok=True)
    (local_bin / "ipfs-kit-iroh-sidecar").write_bytes(b"must-not-ship")
    (local_bin / "install.receipt.json").write_text("{}", encoding="utf-8")
    cache = staging / "ipfs_kit_py" / "iroh" / "__pycache__"
    cache.mkdir()
    (cache / "client.cpython-312.pyc").write_bytes(b"must-not-ship")

    out = staging / "artifacts"
    env = os.environ.copy()
    env["IPFS_KIT_AUTO_INSTALL_BINARIES"] = "0"
    env["SOURCE_DATE_EPOCH"] = "1783929600"
    result = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(out)],
        cwd=staging,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    artifacts = sorted([*out.glob("*.whl"), *out.glob("*.tar.gz")])
    assert len(artifacts) == 2
    return artifacts


def test_metadata_freezes_optional_dependencies_entry_points_and_python_versions() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]

    assert project["requires-python"] == ">=3.12"
    classifiers = set(project["classifiers"])
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.13" in classifiers
    assert {dependency.split(">=")[0] for dependency in project["optional-dependencies"]["iroh"]} == {
        "blake3",
        "duckdb",
    }
    assert project["entry-points"]["fsspec.specs"] == {
        "iroh": "ipfs_kit_py.iroh_fsspec:IrohFileSystem",
        "iroh+blob": "ipfs_kit_py.iroh_fsspec:IrohFileSystem",
    }
    assert project["scripts"]["ipfs-kit-iroh-interop"] == "ipfs_kit_py.iroh.multinode:main"


def test_package_configuration_excludes_runtime_binaries_credentials_and_caches() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        setuptools = tomllib.load(handle)["tool"]["setuptools"]
    exclusions = set(setuptools["exclude-package-data"]["ipfs_kit_py"])
    assert {"bin/*", "bin/**/*", "**/*.receipt.json", "**/*.key", "**/*.pem"} <= exclusions
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-exclude ipfs_kit_py/bin *" in manifest
    assert "__pycache__" in manifest


def test_workflow_has_strict_required_lanes_and_supported_matrix() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    for lane in (
        "unit",
        "fsspec-conformance",
        "async",
        "service",
        "installer",
        "security",
        "build-distributions",
        "distribution-smoke",
        "coverage",
        "multi-node",
    ):
        assert lane in workflow
    for version in ('python: "3.12"', 'python: "3.13"'):
        assert version in workflow
    for operating_system in ("ubuntu-latest", "macos-latest", "windows-latest"):
        assert operating_system in workflow
    assert "linux/amd64" in workflow and "linux/arm64" in workflow
    assert "--cov-fail-under=70" in workflow
    assert "inputs.run_multinode" in workflow
    assert "IPFS_KIT_IROH_INTEROP: \"1\"" in workflow
    assert "continue-on-error" not in workflow


def test_wheel_and_sdist_are_source_only_complete_and_metadata_valid(built_distributions) -> None:
    verifier = _load_verifier()
    reports = [verifier.audit_distribution(path) for path in built_distributions]
    assert {report["kind"] for report in reports} == {"wheel", "sdist"}
    assert all(report["bytes"] > 0 and report["files"] > 0 for report in reports)
    assert all(len(report["normalized_sha256"]) == 64 for report in reports)


def test_distribution_auditor_emits_machine_readable_report(built_distributions, tmp_path: Path) -> None:
    report_path = tmp_path / "packaging-report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY_PATH),
            *(str(path) for path in built_distributions),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["task_id"] == "IROH-026"
    assert report["status"] == "passed"
    assert {item["kind"] for item in report["artifacts"]} == {"wheel", "sdist"}


def test_minimal_wheel_imports_with_vendored_fsspec_and_no_iroh_binary(
    built_distributions, tmp_path: Path
) -> None:
    wheel = next(path for path in built_distributions if path.suffix == ".whl")
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    smoke = subprocess.run(
        [
            str(python),
            str(SMOKE_PATH),
            "--fsspec",
            "vendored",
            "--iroh-extra",
            "absent",
            "--bin-dir",
            str(tmp_path / "managed-bin"),
        ],
        cwd=tmp_path,
        env={**os.environ, "IPFS_KIT_AUTO_INSTALL_BINARIES": "0"},
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert json.loads(smoke.stdout)["iroh_binary"] == "absent"
