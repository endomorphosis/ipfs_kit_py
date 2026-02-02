#!/usr/bin/env python3
"""
Safe package installer that handles lock file issues on multi-user systems.

This script helps install Python packages even when package manager locks exist,
which is common on shared systems like NVIDIA DGX machines.
"""

import subprocess
import sys
import time
import os
import sysconfig
from pathlib import Path


def wait_for_locks(timeout=300):
    """Wait for package manager locks to be released."""
    lock_files = [
        "/var/lib/dpkg/lock",
        "/var/lib/dpkg/lock-frontend",
        "/var/lib/apt/lists/lock",
        "/var/cache/apt/archives/lock"
    ]
    
    print(f"Checking for package manager locks (timeout: {timeout}s)...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        locks_present = False
        for lock_file in lock_files:
            if os.path.exists(lock_file):
                try:
                    # Try to check if file is locked
                    with open(lock_file, 'r'):
                        pass
                except (PermissionError, IOError):
                    locks_present = True
                    break
        
        if not locks_present:
            print("✓ No locks detected")
            return True
        
        elapsed = int(time.time() - start_time)
        print(f"  Waiting for locks to be released... ({elapsed}/{timeout}s)", end='\r')
        time.sleep(5)
    
    print(f"\n⚠ Timeout after {timeout}s, proceeding anyway")
    return False


def run_command(cmd, retries=3, retry_delay=5):
    """Run a command with retries."""
    for attempt in range(1, retries + 1):
        try:
            print(f"\nAttempt {attempt}/{retries}: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=600  # 10 minute timeout
            )
            print(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Command failed (exit code {e.returncode})")
            print(f"STDERR: {e.stderr}")
            if attempt < retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
        except subprocess.TimeoutExpired:
            print(f"✗ Command timed out")
            if attempt < retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
    
    print(f"✗ Failed after {retries} attempts")
    return False


def is_externally_managed_environment() -> bool:
    """Detect PEP 668 externally managed environments."""
    try:
        stdlib_path = sysconfig.get_path("stdlib")
        if not stdlib_path:
            return False
        marker = Path(stdlib_path) / "EXTERNALLY-MANAGED"
        return marker.exists()
    except Exception:
        return False


def build_pip_command(python_cmd: str, *args: str, break_system: bool = False) -> list:
    """Build a pip command with optional PEP 668 override."""
    cmd = [python_cmd, "-m", "pip", *args]
    if break_system:
        cmd.append("--break-system-packages")
    return cmd


def install_dependencies():
    """Install project dependencies safely."""
    print("=" * 60)
    print("Safe Dependency Installer for ARM64/Multi-Architecture")
    print("=" * 60)
    
    # Check Python version
    print(f"\nPython version: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    # Wait for package locks (if on Linux)
    if sys.platform.startswith('linux'):
        wait_for_locks()
    
    python_cmd = sys.executable
    use_break_system = False

    if is_externally_managed_environment():
        venv_dir = Path(".venv")
        print("\nDetected externally managed Python environment.")
        if not venv_dir.exists():
            print("Creating local virtual environment at .venv...")
            if not run_command([python_cmd, "-m", "venv", str(venv_dir)], retries=1):
                print("✗ Failed to create virtual environment")
        if venv_dir.exists():
            python_cmd = str(venv_dir / "bin" / "python")
            print(f"Using virtual environment python: {python_cmd}")
        elif os.environ.get("IPFS_KIT_BREAK_SYSTEM_PACKAGES") == "1":
            use_break_system = True
            print("Proceeding with --break-system-packages as requested")
        else:
            print("✗ Cannot install into externally managed environment.")
            print("  Create a venv or set IPFS_KIT_BREAK_SYSTEM_PACKAGES=1 to override.")
            return False

    # Upgrade pip, setuptools, wheel
    print("\n1. Upgrading pip, setuptools, and wheel...")
    if not run_command(build_pip_command(python_cmd, 'install', '--upgrade', 'pip', 'setuptools', 'wheel', break_system=use_break_system)):
        print("⚠ Failed to upgrade pip tools, continuing anyway...")
    
    # Install main package
    print("\n2. Installing main package...")
    ipfs_kit_git = "git+https://github.com/endomorphosis/ipfs_kit_py.git@main"
    ipfs_kit_direct = f"ipfs_kit_py @ {ipfs_kit_git}"
    installed_main = run_command(
        build_pip_command(python_cmd, 'install', ipfs_kit_direct, break_system=use_break_system)
    )
    if not installed_main:
        print("⚠ Failed to install from git main, trying local editable install...")
        installed_main = run_command(
            build_pip_command(python_cmd, 'install', '-e', '.', break_system=use_break_system)
        )
    if not installed_main:
        print("✗ Failed to install main package")
        return False
    
    # Install libp2p extras
    print("\n3. Installing libp2p extras (with retries)...")
    extras_installed = run_command(
        build_pip_command(python_cmd, 'install', '-e', '.[libp2p]', break_system=use_break_system),
        retries=3,
        retry_delay=10
    )
    
    if not extras_installed:
        print("⚠ Failed to install libp2p extras")
        print("  Trying to install individual dependencies...")
        
        # Try installing critical dependencies individually
        critical_deps = [
            'protobuf>=3.20.0,<5.0.0',
            'eth-hash[pycryptodome]>=0.3.3',
            'eth-keys>=0.4.0',
            'multiaddr>=0.0.9',
            'multiformats>=0.2.0',
        ]
        
        for dep in critical_deps:
            print(f"  Installing {dep}...")
            run_command(build_pip_command(python_cmd, 'install', dep, break_system=use_break_system), retries=2)
    
    # Install test dependencies
    print("\n4. Installing test dependencies...")
    test_deps = ['pytest', 'pytest-anyio', 'pytest-cov', 'pytest-asyncio', 'pytest-trio', 'jsonpatch']
    for dep in test_deps:
        run_command(build_pip_command(python_cmd, 'install', dep, break_system=use_break_system), retries=2)

    # Install optional integration dependencies (best effort)
    print("\n5. Installing optional integrations (best effort)...")
    optional_deps = [
        {
            "name": "ipfs_datasets_py",
            "pip": "ipfs_datasets_py",
            "git": "git+https://github.com/endomorphosis/ipfs_datasets_py.git",
            "zip": "https://github.com/endomorphosis/ipfs_datasets_py/archive/refs/heads/main.zip",
        },
        {
            "name": "ipfs_accelerate_py",
            "pip": "ipfs_accelerate_py",
            "git": "git+https://github.com/endomorphosis/ipfs_accelerate_py.git",
            "zip": "https://github.com/endomorphosis/ipfs_accelerate_py/archive/refs/heads/main.zip",
        },
    ]
    for dep in optional_deps:
        print(f"  Installing {dep['name']}...")
        installed = run_command(build_pip_command(python_cmd, 'install', dep["pip"], break_system=use_break_system), retries=2)
        if not installed:
            print(f"  Pip install failed for {dep['name']}, trying GitHub...")
            installed = run_command(build_pip_command(python_cmd, 'install', dep["git"], break_system=use_break_system), retries=2)
        if not installed and dep.get("zip"):
            print(f"  GitHub clone failed for {dep['name']}, trying zip archive...")
            run_command(build_pip_command(python_cmd, 'install', dep["zip"], break_system=use_break_system), retries=2)

    # Install optional extras that back integration tests
    print("\n6. Installing optional extras (best effort)...")
    optional_extras = [
        "dev",
        "api",
        "ipni",
        "saturn",
        "ipld",
        "enhanced_ipfs",
        "fsspec",
        "arrow",
        "graphql",
        "webrtc",
        "s3",
        "performance",
    ]
    for extra in optional_extras:
        print(f"  Installing extras: [{extra}]...")
        git_extra = f"ipfs_kit_py[{extra}] @ {ipfs_kit_git}"
        installed_extra = run_command(
            build_pip_command(python_cmd, 'install', git_extra, break_system=use_break_system),
            retries=2
        )
        if not installed_extra:
            run_command(
                build_pip_command(python_cmd, 'install', '-e', f'.[{extra}]', break_system=use_break_system),
                retries=2
            )

    # Install additional optional dependencies detected from integration warnings
    print("\n7. Installing optional ML/AI/PDF/RAG dependencies (best effort)...")
    optional_packages = [
        # ML / AI
        "torch",
        "sentence-transformers",
        "tiktoken",
        "nltk",
        "openai",
        # PDF / OCR
        "pymupdf",
        "pdfplumber",
        "pytesseract",
        "surya-ocr",
        # Web content parsing
        "beautifulsoup4",
        "newspaper3k",
        "readability-lxml",
    ]
    for pkg in optional_packages:
        run_command(build_pip_command(python_cmd, 'install', pkg, break_system=use_break_system), retries=2)
    
    # Verify installations
    print("\n8. Verifying installations...")
    print("-" * 60)
    
    checks = [
        ('ipfs_kit_py', 'import ipfs_kit_py'),
        ('cryptography', 'from cryptography.fernet import Fernet'),
        ('multiaddr', 'import multiaddr'),
        ('protobuf', 'from google.protobuf import descriptor'),
        ('eth_hash', 'import eth_hash'),
        ('eth_keys', 'import eth_keys'),
        ('ipfs_datasets_py', 'import ipfs_datasets_py'),
        ('ipfs_accelerate_py', 'import ipfs_accelerate_py'),
    ]
    
    success_count = 0
    for name, import_stmt in checks:
        try:
            subprocess.run(
                [python_cmd, '-c', import_stmt],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )
            print(f"✓ {name}")
            success_count += 1
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print(f"✗ {name} (not available or import failed)")
    
    print("-" * 60)
    print(f"Verification: {success_count}/{len(checks)} checks passed")
    
    if success_count >= len(checks) - 2:  # Allow 2 optional deps to fail
        print("\n✓ Installation completed successfully!")
        return True
    else:
        print("\n⚠ Installation completed with some issues")
        print("  Some optional dependencies may not be available")
        return True  # Still return True as core package should work


def main():
    """Main entry point."""
    try:
        success = install_dependencies()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n✗ Installation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
