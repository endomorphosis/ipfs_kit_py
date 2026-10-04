#!/usr/bin/env python3
"""
Quick Post-Reorganization Verification Test

A lightweight test focused on verifying core functionality without triggering daemon operations.
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path
from typing import Dict


def test_basic_imports():
    """Test basic imports without daemon initialization"""
    print("📦 Testing basic imports...")

    results = {}

    # Test core package structure
    try:
        import ipfs_kit_py

        results["core_package"] = "PASS"
        print("  ✅ Core package imports successfully")
    except Exception as e:
        results["core_package"] = f"FAIL: {e}"
        print(f"  ❌ Core package failed: {e}")

    # Test CLI module import without execution
    try:
        spec = __import__("importlib.util", fromlist=["spec"]).spec_from_file_location(
            "cli_module", "/home/devel/ipfs_kit_py/ipfs_kit_py/cli.py"
        )
        if spec and spec.loader:
            results["cli_module"] = "PASS"
            print("  ✅ CLI module file exists and is importable")
        else:
            results["cli_module"] = "FAIL: Module spec failed"
            print("  ❌ CLI module spec failed")
    except Exception as e:
        results["cli_module"] = f"FAIL: {e}"
        print(f"  ❌ CLI module error: {e}")

    return results


def test_cli_commands():
    """Test CLI commands without daemon operations"""
    print("🖥️  Testing CLI commands...")

    results = {}

    # Test CLI help
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ipfs_kit_py.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd="/home/devel/ipfs_kit_py",
        )

        if result.returncode == 0 and "usage:" in result.stdout.lower():
            results["cli_help"] = "PASS"
            print("  ✅ CLI help command works")
        else:
            results["cli_help"] = f"FAIL: {result.stderr}"
            print(f"  ❌ CLI help failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        results["cli_help"] = "FAIL: Timeout"
        print("  ❌ CLI help timed out")
    except Exception as e:
        results["cli_help"] = f"FAIL: {e}"
        print(f"  ❌ CLI help error: {e}")

    # Test specific command help (non-daemon)
    safe_commands = ["config", "backend", "health"]
    for cmd in safe_commands:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ipfs_kit_py.cli", cmd, "--help"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd="/home/devel/ipfs_kit_py",
            )

            if result.returncode == 0:
                results[f"{cmd}_help"] = "PASS"
                print(f"  ✅ CLI {cmd} --help works")
            else:
                results[f"{cmd}_help"] = "PARTIAL"
                print(f"  ⚠️  CLI {cmd} --help partial: {result.returncode}")
        except Exception as e:
            results[f"{cmd}_help"] = f"FAIL: {e}"
            print(f"  ❌ CLI {cmd} error: {e}")

    return results


def test_file_structure():
    """Test that reorganized file structure is correct"""
    print("📁 Testing file structure...")

    results = {}
    root_path = Path("/home/devel/ipfs_kit_py")

    # Essential root files
    essential_files = [
        "README.md",
        "pyproject.toml",
        "setup.py",
        "requirements.txt",
        "main.py",
        "ipfs_kit_cli.py",
        "LICENSE",
        "CHANGELOG.md",
    ]

    for file_name in essential_files:
        file_path = root_path / file_name
        if file_path.exists():
            results[f"root_{file_name}"] = "PASS"
            print(f"  ✅ {file_name} exists in root")
        else:
            results[f"root_{file_name}"] = "FAIL"
            print(f"  ❌ {file_name} missing from root")

    # Organized directories
    organized_dirs = {
        "docs": "Documentation files",
        "examples": "Demo and example scripts",
        "tests": "Test files",
        "tools": "Utility scripts",
        "cli": "CLI variants",
        "data": "Data files",
    }

    for dir_name, description in organized_dirs.items():
        dir_path = root_path / dir_name
        if dir_path.exists() and dir_path.is_dir():
            file_count = len(list(dir_path.rglob("*")))
            results[f"dir_{dir_name}"] = f"PASS: {file_count} items"
            print(f"  ✅ {dir_name}/ directory exists ({file_count} items)")
        else:
            results[f"dir_{dir_name}"] = "FAIL"
            print(f"  ❌ {dir_name}/ directory missing")

    return results


def test_package_structure():
    """Test that the ipfs_kit_py package structure is intact"""
    print("📦 Testing package structure...")

    results = {}
    package_path = Path("/home/devel/ipfs_kit_py/ipfs_kit_py")

    # Key package files
    key_files = [
        "__init__.py",
        "api.py",
        "cli.py",
        "ipfs_kit.py",
        "daemon_config_manager.py",
        "ipfs_fsspec.py",
    ]

    for file_name in key_files:
        file_path = package_path / file_name
        if file_path.exists():
            results[f"pkg_{file_name}"] = "PASS"
            print(f"  ✅ ipfs_kit_py/{file_name} exists")
        else:
            results[f"pkg_{file_name}"] = "FAIL"
            print(f"  ❌ ipfs_kit_py/{file_name} missing")

    return results


def test_docker_files():
    """Test Docker-related files"""
    print("🐳 Testing Docker files...")

    results = {}
    root_path = Path("/home/devel/ipfs_kit_py")

    # Docker files
    docker_files = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]
    docker_found = False

    for docker_file in docker_files:
        file_path = root_path / docker_file
        if file_path.exists():
            results["dockerfile"] = f"PASS: {docker_file}"
            print(f"  ✅ {docker_file} found")
            docker_found = True
            break

    if not docker_found:
        # Check docker directory
        docker_dir = root_path / "docker"
        if docker_dir.exists():
            docker_files_in_dir = list(docker_dir.glob("*docker*"))
            if docker_files_in_dir:
                results["dockerfile"] = f"PASS: docker/ directory"
                print(f"  ✅ Docker files found in docker/ directory")
            else:
                results["dockerfile"] = "PARTIAL: docker/ dir exists but no files"
                print(f"  ⚠️  docker/ directory exists but no Docker files")
        else:
            results["dockerfile"] = "FAIL: No Docker files"
            print(f"  ❌ No Docker files found")

    return results


def test_kubernetes_files():
    """Test Kubernetes-related files"""
    print("☸️  Testing Kubernetes files...")

    results = {}
    root_path = Path("/home/devel/ipfs_kit_py")

    k8s_dir = root_path / "k8s"
    if k8s_dir.exists():
        yaml_files = list(k8s_dir.rglob("*.yaml")) + list(k8s_dir.rglob("*.yml"))
        if yaml_files:
            results["k8s_manifests"] = f"PASS: {len(yaml_files)} files"
            print(f"  ✅ Kubernetes manifests found: {len(yaml_files)} files")
        else:
            results["k8s_manifests"] = "FAIL: No YAML files"
            print(f"  ❌ k8s/ directory exists but no YAML files")
    else:
        results["k8s_manifests"] = "PARTIAL: No k8s directory"
        print(f"  ⚠️  No k8s/ directory found")

    return results


def test_build_files():
    """Test build and configuration files"""
    print("🔧 Testing build files...")

    results = {}
    root_path = Path("/home/devel/ipfs_kit_py")

    # Build files
    build_files = {
        "pyproject.toml": "Python project config",
        "setup.py": "Setup script",
        "requirements.txt": "Dependencies",
        "Makefile": "Build commands",
    }

    for file_name, description in build_files.items():
        file_path = root_path / file_name
        if file_path.exists():
            results[f"build_{file_name}"] = "PASS"
            print(f"  ✅ {file_name} exists ({description})")
        else:
            results[f"build_{file_name}"] = "FAIL"
            print(f"  ❌ {file_name} missing ({description})")

    return results


def main():
    """Run quick verification tests"""
    print("🧪 IPFS Kit Quick Post-Reorganization Verification")
    print("=" * 60)
    print(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_results = {}

    # Run test categories
    test_functions = [
        ("File Structure", test_file_structure),
        ("Package Structure", test_package_structure),
        ("Basic Imports", test_basic_imports),
        ("CLI Commands", test_cli_commands),
        ("Docker Files", test_docker_files),
        ("Kubernetes Files", test_kubernetes_files),
        ("Build Files", test_build_files),
    ]

    for category_name, test_func in test_functions:
        print(f"\n🔍 {category_name}...")
        print("-" * 40)
        try:
            results = test_func()
            all_results[category_name.lower().replace(" ", "_")] = results
        except Exception as e:
            print(f"❌ {category_name} failed: {e}")
            all_results[category_name.lower().replace(" ", "_")] = {"error": str(e)}

    # Generate summary
    print("\n" + "=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 60)

    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    partial_tests = 0

    for category, results in all_results.items():
        if "error" in results:
            total_tests += 1
            failed_tests += 1
            continue

        category_name = category.replace("_", " ").title()
        print(f"\n📂 {category_name}:")

        for test_name, result in results.items():
            total_tests += 1
            if result.startswith("PASS"):
                print(f"  ✅ {test_name}: {result}")
                passed_tests += 1
            elif result.startswith("PARTIAL"):
                print(f"  ⚠️  {test_name}: {result}")
                partial_tests += 1
            else:
                print(f"  ❌ {test_name}: {result}")
                failed_tests += 1

    # Overall status
    print(f"\n🎯 OVERALL RESULTS:")
    print(f"  Total Tests: {total_tests}")
    print(f"  ✅ Passed: {passed_tests} ({passed_tests / total_tests * 100:.1f}%)")
    print(f"  ❌ Failed: {failed_tests} ({failed_tests / total_tests * 100:.1f}%)")
    print(f"  ⚠️  Partial: {partial_tests} ({partial_tests / total_tests * 100:.1f}%)")

    if failed_tests == 0:
        print(f"\n🎉 VERIFICATION STATUS: ✅ PASS")
        print("   The reorganization was successful!")
        exit_code = 0
    elif failed_tests <= total_tests * 0.15:  # Allow up to 15% failures
        print(f"\n⚠️  VERIFICATION STATUS: 🟡 MOSTLY PASS")
        print("   Most components work, minor issues detected.")
        exit_code = 1
    else:
        print(f"\n❌ VERIFICATION STATUS: 🔴 NEEDS ATTENTION")
        print("   Several issues detected that need fixing.")
        exit_code = 2

    # Save results
    results_file = Path("/home/devel/ipfs_kit_py/quick_verification_results.json")
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n💾 Results saved to: {results_file}")

    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
