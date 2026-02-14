import os
import shutil
import subprocess
import sys

from setuptools import find_packages, setup


def _truthy(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _auto_install_binaries_enabled() -> bool:
    return _truthy(os.environ.get("IPFS_KIT_AUTO_INSTALL_BINARIES"))


def _default_bin_dir() -> str:
    override = os.environ.get("IPFS_KIT_BIN_DIR")
    if override:
        return os.path.expanduser(override)
    return os.path.join(os.path.expanduser("~"), ".local", "share", "ipfs_kit_py", "bin")


def _try_install_binaries() -> None:
    if not _auto_install_binaries_enabled():
        return

    bin_dir = _default_bin_dir()
    os.makedirs(bin_dir, exist_ok=True)

    try:
        from ipfs_kit_py.install_ipfs import install_ipfs

        if shutil.which("ipfs") is None:
            install_ipfs(metadata={"bin_dir": bin_dir}).install_ipfs_daemon()
    except Exception as e:
        print(f"WARNING: IPFS auto-install during setup failed: {e}", file=sys.stderr)

    try:
        from ipfs_kit_py.install_lotus import install_lotus

        if shutil.which("lotus") is None:
            install_lotus(metadata={"bin_dir": bin_dir}).install_lotus_daemon()
    except Exception as e:
        print(f"WARNING: Lotus auto-install during setup failed: {e}", file=sys.stderr)


def _warn_missing_lotus_packages() -> None:
    """Emit a friendly warning if Lotus system dependencies are missing."""
    if os.environ.get("IPFS_KIT_SKIP_LOTUS_CHECK", "").lower() in {"1", "true", "yes"}:
        return

    if not sys.platform.startswith("linux"):
        return

    if not shutil.which("dpkg-query"):
        return

    required_packages = [
        "hwloc",
        "libhwloc-dev",
        "mesa-opencl-icd",
        "ocl-icd-opencl-dev",
    ]

    missing_packages = []
    for package in required_packages:
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Status}", package],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return

        if "install ok installed" not in result.stdout:
            missing_packages.append(package)

    if missing_packages:
        install_hint = (
            "sudo apt-get update && sudo apt-get install -y "
            + " ".join(required_packages)
        )
        print(
            "WARNING: Lotus prerequisites missing: "
            + ", ".join(missing_packages)
            + f". Install them with: {install_hint}",
            file=sys.stderr,
        )


_warn_missing_lotus_packages()

# This file is maintained for backwards compatibility
# Most configuration is now in pyproject.toml


def _load_pyproject_metadata() -> tuple[dict, list[str], dict[str, list[str]]]:
    """Load PEP 621 metadata from pyproject.toml.

    This keeps legacy setup.py installs aligned with the canonical configuration.
    """

    here = os.path.abspath(os.path.dirname(__file__))
    pyproject_path = os.path.join(here, "pyproject.toml")

    try:
        import tomllib  # Python 3.11+

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}, [], {}

    project = data.get("project", {})
    dependencies = list(project.get("dependencies", []) or [])
    optional_dependencies = dict(project.get("optional-dependencies", {}) or {})

    return project, dependencies, optional_dependencies


project, install_requires, extras_require = _load_pyproject_metadata()


cmdclass = {}
try:
    from setuptools.command.install import install as _install

    class install(_install):  # noqa: N801 - setuptools cmdclass name
        def run(self):
            super().run()
            _try_install_binaries()

    cmdclass["install"] = install
except Exception:
    pass

try:
    from setuptools.command.develop import develop as _develop

    class develop(_develop):  # noqa: N801 - setuptools cmdclass name
        def run(self):
            super().run()
            _try_install_binaries()

    cmdclass["develop"] = develop
except Exception:
    pass

setup(
    name='ipfs_kit_py',
    version='0.3.0',
    description='Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration',
    author='Benjamin Barber',
    author_email='starworks5@gmail.com',
    url='https://github.com/endomorphosis/ipfs_kit_py/',
    python_requires='>=3.12',
    packages=find_packages(include=["ipfs_kit_py*", "external*"]),
    include_package_data=True,
    install_requires=install_requires,
    extras_require=extras_require,
    cmdclass=cmdclass,
    # All other configurations come from pyproject.toml
)
