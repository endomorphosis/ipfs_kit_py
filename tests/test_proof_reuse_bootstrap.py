"""Integration tests for ipfs_kit's optional proof-reuse bootstrap."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
ACCELERATE_ROOT = KIT_ROOT.parent / "ipfs_accelerate"
BOOTSTRAP = KIT_ROOT / "conftest.py"
PLUGIN_MODULE = "ipfs_accelerate_py.testing.proof_reuse.plugin"
PLUGIN_ENTRY_POINT = "ipfs-proof-reuse"
PYTEST_SITE = Path(pytest.__file__).resolve().parents[1]


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")


def _copy_bootstrap(project: Path) -> None:
    shutil.copy2(BOOTSTRAP, project / "conftest.py")


def _environment(
    tmp_path: Path,
    *,
    mode: str,
    autoload: bool,
    first_paths: tuple[Path, ...] = (),
) -> dict[str, str]:
    environment = dict(os.environ)
    python_paths = (
        *(str(path) for path in first_paths),
        str(ACCELERATE_ROOT),
        str(KIT_ROOT),
        str(PYTEST_SITE),
        environment.get("PYTHONPATH", ""),
    )
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in python_paths if part
    )
    environment["IPFS_TEST_PROOF_REUSE_MODE"] = mode
    environment["HOME"] = str(tmp_path / "user-home")
    environment["IPFS_PATH"] = str(tmp_path / "user-home" / ".ipfs")
    environment["COVERAGE_FILE"] = str(tmp_path / ".coverage")
    environment.pop("PYTEST_ADDOPTS", None)
    if autoload:
        environment.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
    else:
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def _run_pytest(
    project: Path,
    environment: dict[str, str],
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *arguments],
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _assert_success(
    completed: subprocess.CompletedProcess[str],
    expected: str,
) -> None:
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert expected in output, output


def _install_test_entry_point(metadata_root: Path) -> None:
    distribution = metadata_root / "ipfs_kit_ptr_bootstrap-0.dist-info"
    _write(
        distribution / "METADATA",
        """
        Metadata-Version: 2.1
        Name: ipfs-kit-ptr-bootstrap
        Version: 0
        """,
    )
    _write(
        distribution / "entry_points.txt",
        f"""
        [pytest11]
        {PLUGIN_ENTRY_POINT} = {PLUGIN_MODULE}
        """,
    )


def test_pyproject_declares_shared_pytest_entry_point() -> None:
    project = tomllib.loads(
        (KIT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert (
        project["project"]["entry-points"]["pytest11"][PLUGIN_ENTRY_POINT]
        == PLUGIN_MODULE
    )


@pytest.mark.parametrize("autoload", [False, True], ids=["root-fallback", "entry-point"])
def test_direct_node_pickup_with_entry_point_autoload_modes(
    tmp_path: Path,
    autoload: bool,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _copy_bootstrap(project)
    _write(
        project / "test_direct_node.py",
        f"""
        import pytest

        from {PLUGIN_MODULE} import get_item_metadata

        @pytest.mark.proof_reuse_effects("filesystem")
        def test_direct_node(request, pytestconfig):
            metadata = get_item_metadata(request.node)
            assert metadata is not None
            assert metadata.nodeid.endswith("test_direct_node.py::test_direct_node")
            assert metadata.effect_adapters == ("filesystem",)
            assert pytestconfig.pluginmanager.hasplugin("{PLUGIN_ENTRY_POINT}") is {
                autoload!r
            }
        """,
    )
    metadata_root = tmp_path / "metadata"
    first_paths: tuple[Path, ...] = ()
    if autoload:
        _install_test_entry_point(metadata_root)
        first_paths = (metadata_root,)
    environment = _environment(
        tmp_path,
        mode="shadow",
        autoload=autoload,
        first_paths=first_paths,
    )

    completed = _run_pytest(
        project,
        environment,
        "test_direct_node.py::test_direct_node",
        "-q",
    )

    _assert_success(completed, "1 passed")


def test_verified_hit_skips_before_fixtures_without_ipfs_or_daemon_touch(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    tests = project / "tests"
    tests.mkdir(parents=True)
    _copy_bootstrap(project)
    daemon_sentinel = tmp_path / "daemon-started"
    body_sentinel = tmp_path / "test-body-ran"
    _write(
        tests / "conftest.py",
        f"""
        from pathlib import Path

        import pytest

        from ipfs_accelerate_py.agent_supervisor.proof.test_execution_contracts import (
            reuse_skip,
        )
        from ipfs_accelerate_py.testing.proof_reuse.lookup import ProofReuseLookup
        from ipfs_accelerate_py.testing.proof_reuse.plugin import (
            set_proof_reuse_services,
        )

        class VerifiedHitLookup(ProofReuseLookup):
            def lookup(self, locator, execution_key, **kwargs):
                return reuse_skip(
                    certificate_cid="bafy-test-certificate",
                    receipt_cid="bafy-test-receipt",
                )

        def pytest_configure(config):
            set_proof_reuse_services(config, lookup=VerifiedHitLookup())

        @pytest.hookimpl(tryfirst=True)
        def pytest_collection_modifyitems(items):
            for item in items:
                item._ipfs_proof_reuse_locator = object()
                item._ipfs_proof_reuse_execution_key = object()

        @pytest.fixture(autouse=True)
        def would_start_daemon():
            Path({str(daemon_sentinel)!r}).write_text("started", encoding="utf-8")
        """,
    )
    _write(
        tests / "test_hit.py",
        f"""
        from pathlib import Path

        def test_cached_pass():
            Path({str(body_sentinel)!r}).write_text("ran", encoding="utf-8")
        """,
    )
    environment = _environment(tmp_path, mode="read", autoload=False)
    user_ipfs_path = Path(environment["IPFS_PATH"])

    completed = _run_pytest(
        project,
        environment,
        "tests/test_hit.py::test_cached_pass",
        "-q",
        "-rs",
    )

    _assert_success(completed, "1 skipped")
    assert "proof-cache-hit:bafy-test-certificate" in completed.stdout
    assert not daemon_sentinel.exists()
    assert not body_sentinel.exists()
    assert not user_ipfs_path.exists()


def test_missing_shared_plugin_executes_normally(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _copy_bootstrap(project)
    _write(project / "test_normal.py", "def test_normal():\n    assert True\n")
    blockers = tmp_path / "blockers"
    _write(
        blockers / "sitecustomize.py",
        """
        import importlib.abc
        import sys

        class BlockProofReuse(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "ipfs_accelerate_py" or fullname.startswith(
                    "ipfs_accelerate_py."
                ):
                    raise ModuleNotFoundError(
                        "optional proof-reuse plugin unavailable",
                        name=fullname,
                    )
                return None

        sys.meta_path.insert(0, BlockProofReuse())
        """,
    )
    environment = _environment(
        tmp_path,
        mode="read",
        autoload=False,
        first_paths=(blockers,),
    )

    completed = _run_pytest(project, environment, "test_normal.py", "-q")

    _assert_success(completed, "1 passed")


def test_missing_store_and_multiformats_execute_normally(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _copy_bootstrap(project)
    _write(project / "test_normal.py", "def test_normal():\n    assert True\n")
    blockers = tmp_path / "blockers"
    _write(
        blockers / "sitecustomize.py",
        """
        import importlib.abc
        import sys

        BLOCKED = ("ipfs_kit_py.proof_certificate_store", "multiformats")

        class BlockOptionalProviders(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if any(
                    fullname == name or fullname.startswith(name + ".")
                    for name in BLOCKED
                ):
                    raise AssertionError("optional provider imported: " + fullname)
                return None

        sys.meta_path.insert(0, BlockOptionalProviders())
        """,
    )
    environment = _environment(
        tmp_path,
        mode="shadow",
        autoload=False,
        first_paths=(blockers,),
    )

    completed = _run_pytest(project, environment, "test_normal.py", "-q")

    _assert_success(completed, "1 passed")


def test_explicit_off_mode_executes_normally(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _copy_bootstrap(project)
    _write(
        project / "test_off.py",
        f"""
        from {PLUGIN_MODULE} import ProofReuseMode, get_proof_reuse_config

        def test_off(pytestconfig):
            assert get_proof_reuse_config(pytestconfig).mode is ProofReuseMode.OFF
        """,
    )
    environment = _environment(tmp_path, mode="off", autoload=False)

    completed = _run_pytest(project, environment, "test_off.py", "-q")

    _assert_success(completed, "1 passed")


def test_coverage_execution_remains_available(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _copy_bootstrap(project)
    _write(
        project / "test_coverage_target.py",
        """
        def covered_value():
            return 42

        def test_covered_value():
            assert covered_value() == 42
        """,
    )
    environment = _environment(tmp_path, mode="off", autoload=False)

    completed = _run_pytest(
        project,
        environment,
        "-p",
        "pytest_cov.plugin",
        "--cov=test_coverage_target",
        "--cov-report=term",
        "test_coverage_target.py",
        "-q",
    )

    _assert_success(completed, "1 passed")
    assert "TOTAL" in completed.stdout
