"""Regression coverage for the package's runtime-readiness import contract."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _project_metadata() -> dict[str, object]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
        return tomllib.load(project_file)["project"]


def _requirement_lines() -> list[str]:
    return [
        line.strip()
        for line in (PROJECT_ROOT / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _fresh_python(
    source: str, *, home: Path | None = None
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT)
    environment["PYTHONNOUSERSITE"] = "1"
    if home is not None:
        environment.update(
            {
                "HOME": str(home),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_DATA_HOME": str(home / ".local" / "share"),
                "XDG_STATE_HOME": str(home / ".local" / "state"),
            }
        )
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        text=True,
        capture_output=True,
    )


def test_runtime_version_matches_wheel_metadata_and_legacy_setup() -> None:
    project = _project_metadata()
    expected_version = str(project["version"])
    result = _fresh_python(
        f"""
        import ipfs_kit_py
        assert ipfs_kit_py.__version__ == {expected_version!r}
        """
    )
    assert result.returncode == 0, result.stderr

    setup_source = (PROJECT_ROOT / "setup.py").read_text()
    for host_probe in ("dpkg", "subprocess", "platform", "shutil", "os."):
        assert host_probe not in setup_source.lower()

    setup_result = subprocess.run(
        [sys.executable, "setup.py", "--name", "--version"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert setup_result.returncode == 0, setup_result.stderr
    assert str(project["name"]) in setup_result.stdout
    assert str(project["version"]) in setup_result.stdout


def test_core_requirements_are_exactly_the_project_dependencies() -> None:
    project = _project_metadata()
    assert _requirement_lines() == project["dependencies"]


def test_graphrag_and_mcp_extras_are_dedicated_and_complete() -> None:
    extras = _project_metadata()["optional-dependencies"]
    assert extras["graphrag"] == [
        "networkx>=3.0",
        "numpy>=1.20.0",
        "faiss-cpu>=1.8.0",
        "ipfs_datasets_py",
    ]
    assert extras["mcp"] == [
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "jinja2>=3.1.0",
        "mcp>=1.0.0",
    ]


def test_cold_root_core_and_mcp_imports_do_not_load_optional_stacks(
    tmp_path: Path,
) -> None:
    home = tmp_path / "fresh-home"
    home.mkdir()
    result = _fresh_python(
        """
        import os
        import sys
        from pathlib import Path
        import ipfs_kit_py
        import ipfs_kit_py.core
        import ipfs_kit_py.mcp_server

        forbidden = {
            "ipfs_kit_py.jit_imports",
            "ipfs_kit_py.install_ipfs",
            "ipfs_kit_py.install_lotus",
            "ipfs_kit_py.install_lassie",
            "ipfs_kit_py.install_storacha",
            "ipfs_kit_py.tool_registry",
            "ipfs_kit_py.service_manager",
            "torch",
            "transformers",
            "fastapi",
            "uvicorn",
            "mcp",
            "ipfs_datasets_py",
            "ipfs_accelerate_py",
        }
        assert not forbidden.intersection(sys.modules), sorted(forbidden.intersection(sys.modules))
        assert not tuple(Path(os.environ["HOME"]).iterdir())
        """,
        home=home,
    )
    assert result.returncode == 0, result.stderr
    assert not tuple(home.iterdir())


def test_canonical_exports_and_jit_singleton_are_explicit_use_only() -> None:
    result = _fresh_python(
        """
        import sys
        import ipfs_kit_py
        from ipfs_kit_py import (
            CanonicalStorageService,
            OperationDefinition,
            OperationRegistry,
            OperationRequest,
            ServiceRouter,
        )
        import ipfs_kit_py.core as core

        assert OperationDefinition is not None
        assert OperationRegistry is not None
        assert OperationRequest is not None
        assert ServiceRouter is not None
        assert CanonicalStorageService is not None
        assert {
            "OperationDefinition",
            "OperationRegistry",
            "OperationRequest",
            "ServiceRouter",
            "CanonicalStorageService",
        } <= set(ipfs_kit_py.__all__)
        assert {
            "OperationDefinition",
            "OperationRegistry",
            "OperationRequest",
            "ServiceRouter",
            "CanonicalStorageService",
        } <= set(core.__all__)
        assert "ipfs_kit_py.jit_imports" not in sys.modules
        first = core.get_jit_imports()
        second = core.get_jit_imports()
        assert first is second
        """
    )
    assert result.returncode == 0, result.stderr


def test_missing_optional_mcp_dependency_fails_only_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ipfs_kit_py
    import ipfs_kit_py.mcp_server as mcp_server

    def missing_module(*_args: object, **_kwargs: object) -> object:
        raise ModuleNotFoundError("No module named 'mcp'", name="mcp")

    mcp_server.__dict__.pop("HierarchicalToolManager", None)
    monkeypatch.setattr(mcp_server, "import_module", missing_module)

    with pytest.raises(ipfs_kit_py.OptionalDependencyError, match=r"ipfs_kit_py\[mcp\]"):
        _ = mcp_server.HierarchicalToolManager
