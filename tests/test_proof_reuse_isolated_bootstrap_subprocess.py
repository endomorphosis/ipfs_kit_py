"""Black-box startup coverage for the kit-owned proof-reuse bridge."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


KIT_ROOT = Path(__file__).resolve().parents[1]
PYTEST_SITE = Path(pytest.__file__).resolve().parents[1]
ACCELERATOR_PLUGIN = "ipfs_accelerate_py.testing.proof_reuse.plugin"
TRANSITIVE_MISSING = "ptr_kit_missing_transitive_dependency"
_PYTEST_RUNTIME_PACKAGES = (
    "pytest",
    "_pytest",
    "pluggy",
    "iniconfig",
    "packaging",
    "pygments",
    "py",
)


@pytest.fixture(scope="module")
def isolated_pytest_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Expose pytest to ``/usr/bin/python3`` without ambient entry points.

    The supervisor's interpreter can obtain pytest from a user site which also
    contains unrelated ``pytest11`` metadata.  Symlinking pytest's import-time
    packages out of that site keeps the child capable of running pytest while
    ensuring the wheel under test is the only kit plugin distribution visible.
    """

    runtime = tmp_path_factory.mktemp("kit-pytest-runtime")
    for package_name in _PYTEST_RUNTIME_PACKAGES:
        spec = importlib.util.find_spec(package_name)
        assert spec is not None, f"pytest runtime package is missing: {package_name}"
        if spec.submodule_search_locations:
            source = Path(next(iter(spec.submodule_search_locations))).resolve()
            target = runtime / package_name
            target.symlink_to(source, target_is_directory=True)
        else:
            assert spec.origin is not None
            source = Path(spec.origin).resolve()
            (runtime / source.name).symlink_to(source)
    return runtime


def _pip_environment(home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        path
        for path in (str(PYTEST_SITE), existing_pythonpath)
        if path
    )
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["HOME"] = str(home)
    environment["XDG_CACHE_HOME"] = str(home / ".cache")
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    return environment


@pytest.fixture(scope="module")
def installed_wheel_target(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the real project wheel from a disposable copy and target-install it."""

    work = tmp_path_factory.mktemp("kit-wheel")
    source = work / "source"
    source.mkdir()
    for filename in ("pyproject.toml", "setup.py", "README.md"):
        shutil.copy2(KIT_ROOT / filename, source / filename)
    shutil.copytree(
        KIT_ROOT / "ipfs_kit_py",
        source / "ipfs_kit_py",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )

    wheelhouse = work / "wheelhouse"
    wheelhouse.mkdir()
    build_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--no-index",
            "--no-cache-dir",
            "--wheel-dir",
            str(wheelhouse),
            str(source),
        ],
        env=_pip_environment(work / "pip-home"),
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr
    wheels = sorted(wheelhouse.glob("ipfs_kit_py-*.whl"))
    assert len(wheels) == 1

    target = work / "target"
    install_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--no-compile",
            "--force-reinstall",
            "--target",
            str(target),
            str(wheels[0]),
        ],
        env=_pip_environment(work / "pip-home"),
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    entry_point_files = list(target.glob("ipfs_kit_py-*.dist-info/entry_points.txt"))
    assert len(entry_point_files) == 1
    assert (
        "ipfs-kit-proof-reuse = ipfs_kit_py.pytest_proof_reuse"
        in entry_point_files[0].read_text(encoding="utf-8")
    )
    return target


def _write_source_checkout(root: Path) -> Path:
    root.mkdir(parents=True)
    shutil.copy2(KIT_ROOT / "conftest.py", root / "conftest.py")
    (root / "ipfs_kit_py").symlink_to(
        KIT_ROOT / "ipfs_kit_py", target_is_directory=True
    )
    return root


def _write_accelerator_case(root: Path, case: str) -> Path:
    root.mkdir(parents=True)
    package = root / "ipfs_accelerate_py"
    package.mkdir()
    if case == "empty-namespace":
        return root

    (package / "__init__.py").write_text("# regular accelerator package\n")
    if case == "regular-missing-testing":
        return root

    testing = package / "testing"
    proof_reuse = testing / "proof_reuse"
    proof_reuse.mkdir(parents=True)
    plugin = proof_reuse / "plugin.py"
    if case == "namespace-plugin-internal-missing":
        # The root and its parents remain PEP 420 namespaces, but the target
        # plugin is discoverable.  Its chain-named import error is actionable.
        plugin.write_text("import ipfs_accelerate_py.testing.proof_reuse.runtime_dependency\n")
        return root
    (testing / "__init__.py").write_text("")
    (proof_reuse / "__init__.py").write_text("")
    if case == "transitive-missing":
        plugin.write_text(f"import {TRANSITIVE_MISSING}\n")
        return root

    assert case == "found-plugin"
    plugin.write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "def pytest_configure(config):\n"
        "    marker = Path(os.environ['PTR_ACCELERATOR_MARKER'])\n"
        "    count = int(marker.read_text()) if marker.exists() else 0\n"
        "    marker.write_text(str(count + 1))\n"
    )
    distribution = root / "ptr_fake_accelerator-1.0.dist-info"
    distribution.mkdir()
    (distribution / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: ptr-fake-accelerator\nVersion: 1.0\n"
    )
    (distribution / "entry_points.txt").write_text(
        "[pytest11]\n"
        f"ipfs-proof-reuse = {ACCELERATOR_PLUGIN}\n"
    )
    return root


def _write_direct_node(root: Path) -> Path:
    node = root / "test_real_body.py"
    node.write_text(
        f'''from pathlib import Path
import os


def test_real_body(pytestconfig):
    body_marker = Path(os.environ["PTR_BODY_MARKER"])
    count = int(body_marker.read_text()) if body_marker.exists() else 0
    body_marker.write_text(str(count + 1))

    manager = pytestconfig.pluginmanager
    bridge_plugins = [
        plugin for plugin in manager.get_plugins()
        if getattr(plugin, "__name__", None) == "ipfs_kit_py.pytest_proof_reuse"
    ]
    assert len(bridge_plugins) == 1
    bridge_names = [
        name for name, plugin in manager.list_name_plugin()
        if plugin is bridge_plugins[0]
    ]
    assert bridge_names == [os.environ["PTR_EXPECTED_BRIDGE_NAME"]]

    accelerator_plugins = [
        plugin for plugin in manager.get_plugins()
        if getattr(plugin, "__name__", None) == "{ACCELERATOR_PLUGIN}"
    ]
    if os.environ["PTR_EXPECT_ACCELERATOR"] == "1":
        assert len(accelerator_plugins) == 1
        assert manager.get_plugin("ipfs-proof-reuse") is accelerator_plugins[0]
        assert Path(os.environ["PTR_ACCELERATOR_MARKER"]).read_text() == "1"
    else:
        assert accelerator_plugins == []
        assert manager.get_plugin("ipfs-proof-reuse") is None
''',
        encoding="utf-8",
    )
    return node


def _subprocess_environment(
    paths: list[Path], sandbox: Path, *, source_checkout: bool, expect_plugin: bool
) -> dict[str, str]:
    home = sandbox / "home"
    temporary = sandbox / "tmp"
    home.mkdir(parents=True)
    temporary.mkdir()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in paths)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["HOME"] = str(home)
    environment["XDG_CACHE_HOME"] = str(home / ".cache")
    environment["XDG_CONFIG_HOME"] = str(home / ".config")
    environment["XDG_DATA_HOME"] = str(home / ".local" / "share")
    environment["IPFS_PATH"] = str(home / ".ipfs")
    environment["TMPDIR"] = str(temporary)
    environment["IPFS_KIT_AUTO_INSTALL_BINARIES"] = "1"
    environment["IPFS_TEST_PROOF_REUSE_MODE"] = "off"
    environment["PTR_BODY_MARKER"] = str(sandbox / "body-ran")
    environment["PTR_ACCELERATOR_MARKER"] = str(sandbox / "accelerator-ran")
    environment["PTR_EXPECT_ACCELERATOR"] = "1" if expect_plugin else "0"
    environment["PTR_EXPECTED_BRIDGE_NAME"] = (
        "ipfs_kit_py.pytest_proof_reuse"
        if source_checkout
        else "ipfs-kit-proof-reuse"
    )
    if source_checkout:
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    else:
        environment.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
    for variable in (
        "COVERAGE_PROCESS_START",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "PYTHONHOME",
    ):
        environment.pop(variable, None)
    return environment


_IMPORT_PROBE = r'''
import os
import sys
from pathlib import Path

home = Path(os.environ["HOME"])
before = sorted(str(path.relative_to(home)) for path in home.rglob("*"))

def reject_side_effect(event, args):
    if event == "subprocess.Popen" or event == "os.system" or event.startswith("socket."):
        raise AssertionError(f"forbidden import side effect: {event}")

sys.addaudithook(reject_side_effect)
import ipfs_kit_py
import ipfs_kit_py.pytest_proof_reuse as bridge

assert ipfs_kit_py.KUBO_BINARY is None
assert not any(name == "ipfs_accelerate_py" or name.startswith("ipfs_accelerate_py.") for name in sys.modules)
for forbidden in (
    "ipfs_kit_py.install_ipfs",
    "ipfs_kit_py.install_lotus",
    "ipfs_kit_py.install_lassie",
    "ipfs_kit_py.install_storacha",
    "ipfs_kit_py.kubo_runtime",
):
    assert forbidden not in sys.modules

missing = ""
plugin = None
try:
    plugin = bridge._optional_accelerator_plugin()
except ModuleNotFoundError as error:
    missing = error.name or ""

after = sorted(str(path.relative_to(home)) for path in home.rglob("*"))
assert after == before, (before, after)
if missing:
    print(f"MISSING:{missing}")
    raise SystemExit(86)
print("PLUGIN:none" if plugin is None else f"PLUGIN:{plugin.__name__}")
'''


@pytest.mark.parametrize("installation", ("source", "wheel"))
@pytest.mark.parametrize(
    ("accelerator_case", "expected_missing"),
    (
        ("empty-namespace", None),
        ("regular-missing-testing", "ipfs_accelerate_py.testing"),
        ("namespace-plugin-internal-missing", "ipfs_accelerate_py.testing.proof_reuse.runtime_dependency"),
        ("transitive-missing", TRANSITIVE_MISSING),
        ("found-plugin", None),
    ),
)
def test_isolated_bootstrap_matrix(
    tmp_path: Path,
    isolated_pytest_site: Path,
    installed_wheel_target: Path,
    installation: str,
    accelerator_case: str,
    expected_missing: str | None,
) -> None:
    scenario = _write_accelerator_case(tmp_path / "accelerator-site", accelerator_case)
    source_checkout = installation == "source"
    if source_checkout:
        run_root = _write_source_checkout(tmp_path / "source")
        kit_import_root = run_root
    else:
        run_root = tmp_path / "runner"
        run_root.mkdir()
        kit_import_root = installed_wheel_target

    node = _write_direct_node(run_root)
    environment = _subprocess_environment(
        [kit_import_root, scenario, isolated_pytest_site],
        tmp_path / "sandbox",
        source_checkout=source_checkout,
        expect_plugin=accelerator_case == "found-plugin",
    )

    import_result = subprocess.run(
        [sys.executable, "-c", _IMPORT_PROBE],
        cwd=run_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if expected_missing is None:
        assert import_result.returncode == 0, import_result.stdout + import_result.stderr
        expected_plugin = (
            f"PLUGIN:{ACCELERATOR_PLUGIN}"
            if accelerator_case == "found-plugin"
            else "PLUGIN:none"
        )
        assert expected_plugin in import_result.stdout
    else:
        assert import_result.returncode == 86, import_result.stdout + import_result.stderr
        assert f"MISSING:{expected_missing}" in import_result.stdout

    pytest_result = subprocess.run(
        [sys.executable, "-m", "pytest", str(node), "-q"],
        cwd=run_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    body_marker = Path(environment["PTR_BODY_MARKER"])
    accelerator_marker = Path(environment["PTR_ACCELERATOR_MARKER"])
    if expected_missing is None:
        assert pytest_result.returncode == 0, pytest_result.stdout + pytest_result.stderr
        assert body_marker.read_text() == "1"
        if accelerator_case == "found-plugin":
            assert accelerator_marker.read_text() == "1"
        else:
            assert not accelerator_marker.exists()
    else:
        assert pytest_result.returncode != 0
        assert expected_missing in pytest_result.stdout + pytest_result.stderr
        assert not body_marker.exists()
        assert not accelerator_marker.exists()
