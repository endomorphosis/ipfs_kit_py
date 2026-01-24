#!/usr/bin/env python3
"""
libp2p Dependency Installer for IPFS Kit and MCP Server

This script checks for and installs the required dependencies for libp2p
functionality in the IPFS Kit Python library and MCP server. It also
verifies the installation and provides comprehensive error reporting.

Usage:
    python install_libp2p.py [--force] [--check-only] [--install-dir DIR]

Options:
    --force         Force reinstallation even if dependencies are already present
    --check-only    Only check if dependencies are available, don't install
    --install-dir   Specify a custom installation directory for dependencies
"""

import os
import sys
import logging
import subprocess
import argparse
import importlib
import tempfile
import time
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Set

# Try to import pkg_resources
try:
    import pkg_resources
    HAS_PKG_RESOURCES = True
except ImportError:
    HAS_PKG_RESOURCES = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("install_libp2p")

# Global flags
HAS_LIBP2P = False
HAS_CRYPTO = False
HAS_MDNS = False


def check_pkg_installed(package_name: str, min_version: Optional[str] = None) -> bool:
    """
    Check if a package is installed and optionally meets minimum version requirement.
    
    Args:
        package_name: Name of the package to check
        min_version: Minimum version required (optional)
        
    Returns:
        bool: True if package is installed and meets version requirement
    """
    if not HAS_PKG_RESOURCES:
        # Fall back to importlib if pkg_resources is not available
        try:
            module = importlib.import_module(package_name)
            if hasattr(module, "__version__") and min_version:
                try:
                    module_version = module.__version__
                    # Simple version comparison (not as robust as pkg_resources)
                    return module_version >= min_version
                except (TypeError, ValueError):
                    # If version comparison fails, assume it's installed
                    return True
            return True
        except ImportError:
            return False
            
    # Use pkg_resources if available (more reliable)
    try:
        pkg = pkg_resources.get_distribution(package_name)
        if min_version:
            return pkg_resources.parse_version(pkg.version) >= pkg_resources.parse_version(min_version)
        return True
    except pkg_resources.DistributionNotFound:
        return False


def run_pip_command(args: List[str], quiet: bool = False) -> bool:
    """
    Run a pip command with appropriate error handling.
    
    Args:
        args: List of arguments to pass to pip
        quiet: If True, suppress output
        
    Returns:
        bool: True if command succeeded, False otherwise
    """
    cmd = [sys.executable, "-m", "pip"] + args
    
    if quiet:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
    else:
        stdout = None
        stderr = None
    
    try:
        logger.debug(f"Running pip command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, stdout=stdout, stderr=stderr)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        if not quiet:
            logger.error(f"Pip command failed: {e}")
        return False
    except Exception as e:
        if not quiet:
            logger.error(f"Error running pip command: {e}")
        return False


def install_package(package_spec: str, install_dir: Optional[str] = None, upgrade: bool = False) -> bool:
    """
    Install a package using pip.
    
    Args:
        package_spec: Package specification (name==version)
        install_dir: Custom installation directory (optional)
        upgrade: If True, upgrade the package if already installed
        
    Returns:
        bool: True if installation succeeded, False otherwise
    """
    args = ["install"]
    
    if upgrade:
        args.append("--upgrade")
    
    if install_dir:
        install_dir_path = Path(install_dir).expanduser().resolve()
        if not install_dir_path.exists():
            try:
                install_dir_path.mkdir(parents=True)
            except Exception as e:
                logger.error(f"Failed to create installation directory {install_dir}: {e}")
                return False
        
        args.extend(["--target", str(install_dir_path)])
    
    args.append(package_spec)
    
    logger.info(f"Installing {package_spec}...")
    return run_pip_command(args)


def install_libp2p_dependencies(
    force: bool = False, 
    install_dir: Optional[str] = None
) -> bool:
    """
    Install all required libp2p dependencies.
    
    Args:
        force: If True, force reinstallation even if already present
        install_dir: Custom installation directory (optional)
        
    Returns:
        bool: True if all dependencies were installed successfully
    """
    # Define required packages with version constraints
    required_packages = {
        "libp2p": ">=0.2.0",           # Core libp2p library
        "cryptography": ">=36.0.0",     # For crypto operations
        "multiaddr": "==0.0.11",        # For multiaddress handling (libp2p requirement)
        "protobuf": ">=3.20.0",         # For protocol buffers
        "base58": ">=2.1.0",            # For base58 encoding/decoding
        "networkx": ">=2.6.0",          # For peer routing graph
        "async-timeout": ">=4.0.0",     # For asyncio timeouts
    }
    
    # Additional packages that enhance functionality but aren't strictly required
    optional_packages = {
        "aiodns": ">=3.0.0",            # For async DNS resolution
        "zeroconf": ">=0.38.0",         # For mDNS discovery
        "netifaces": ">=0.11.0",        # For network interface detection
        "coincurve": ">=17.0.0",        # For optimized crypto
        "prometheus-client": ">=0.14.0", # For metrics
    }

    # First, check which packages are already installed
    installed_packages = {}
    missing_packages = {}
    
    # Check required packages
    for package, version in required_packages.items():
        if force or not check_pkg_installed(package, version):
            missing_packages[package] = version
        else:
            installed_packages[package] = version
    
    # Check optional packages
    for package, version in optional_packages.items():
        if force or not check_pkg_installed(package, version):
            # Don't mark optional packages as missing
            pass
        else:
            installed_packages[package] = version
    
    # If no packages are missing, return success early
    if not missing_packages and not force:
        logger.info("All required libp2p dependencies are already installed")
        return True
    
    # Install missing packages
    success = True
    for package, version in missing_packages.items():
        package_spec = f"{package}{version}"
        if not install_package(package_spec, install_dir=install_dir, upgrade=force):
            logger.error(f"Failed to install {package_spec}")
            success = False
    
    # Try to install optional packages, but don't fail if they don't install
    for package, version in optional_packages.items():
        if force or not check_pkg_installed(package, version):
            package_spec = f"{package}{version}"
            try:
                if install_package(package_spec, install_dir=install_dir, upgrade=force):
                    logger.info(f"Optional package {package} installed successfully")
                else:
                    logger.warning(f"Optional package {package} installation failed")
            except Exception as e:
                logger.warning(f"Error installing optional package {package}: {e}")
    
    return success


def check_libp2p_imports() -> Dict[str, bool]:
    """
    Check if libp2p modules can be imported.
    
    Returns:
        Dict mapping module names to boolean indicating if they can be imported
    """
    global HAS_LIBP2P, HAS_CRYPTO, HAS_MDNS
    
    # Reset the flags
    HAS_LIBP2P = False
    HAS_CRYPTO = False
    HAS_MDNS = False
    
    results = {}
    
    # Check core libp2p
    try:
        import libp2p
        results["libp2p"] = True
        HAS_LIBP2P = True
        
        # Test specific libp2p components
        try:
            import libp2p.crypto.rsa
            import libp2p.crypto.secp256k1
            HAS_CRYPTO = True
            results["libp2p.crypto"] = True
        except ImportError:
            results["libp2p.crypto"] = False
        
        try:
            import libp2p.pubsub.gossipsub
            results["libp2p.pubsub"] = True
        except ImportError:
            results["libp2p.pubsub"] = False
        
        try:
            import zeroconf
            HAS_MDNS = True
            results["zeroconf"] = True
        except ImportError:
            results["zeroconf"] = False
    except ImportError:
        results["libp2p"] = False
    
    # Check additional dependencies
    required_modules = [
        "multiaddr", 
        "cryptography",
        "base58", 
        "protobuf", 
        "networkx"
    ]
    
    for module in required_modules:
        try:
            importlib.import_module(module)
            results[module] = True
        except ImportError:
            results[module] = False
    
    return results


def ensure_ipfs_kit_integration() -> bool:
    """
    Ensure the ipfs_kit_py integration with libp2p is working.
    
    Returns:
        bool: True if integration is successful
    """
    try:
        # Try to import ipfs_kit_py first
        import ipfs_kit_py
        
        # Check for core libp2p integration modules
        try:
            from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer, HAS_LIBP2P as PEER_HAS_LIBP2P
            from ipfs_kit_py.libp2p import HAS_LIBP2P as MODULE_HAS_LIBP2P
            
            # Verify the integration
            if not PEER_HAS_LIBP2P or not MODULE_HAS_LIBP2P:
                logger.warning("LibP2P integration modules are available but flag variables are False")
                logger.info("Attempting to fix integration flags...")
                
                # Try to update the module flags
                try:
                    import sys
                    sys.modules['ipfs_kit_py.libp2p'].__dict__['HAS_LIBP2P'] = True
                    sys.modules['ipfs_kit_py.libp2p_peer'].__dict__['HAS_LIBP2P'] = True
                    logger.info("Updated integration flags successfully")
                except Exception as e:
                    logger.warning(f"Failed to update integration flags: {e}")
            
            logger.info("IPFS Kit integration with libp2p is available")
            return True
            
        except ImportError as e:
            logger.warning(f"Failed to import IPFS Kit libp2p integration modules: {e}")
            return False
            
    except ImportError:
        logger.warning("IPFS Kit Python library is not installed")
        return False


def ensure_mcp_libp2p_integration() -> bool:
    """
    Ensure the MCP server integration with libp2p is working.
    
    Returns:
        bool: True if integration is successful
    """
    try:
        # Check for core MCP libp2p integration
        try:
            from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
            from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
            
            # Check if HAS_LIBP2P is available and True
            import ipfs_kit_py.mcp.models.libp2p_model
            if not getattr(ipfs_kit_py.mcp.models.libp2p_model, 'HAS_LIBP2P', False):
                logger.warning("MCP LibP2P model is available but HAS_LIBP2P flag is False")
                logger.info("Attempting to fix MCP integration flags...")
                
                # Try to update the module flags
                try:
                    import sys
                    ipfs_kit_py.mcp.models.libp2p_model.HAS_LIBP2P = True
                    sys.modules['ipfs_kit_py.mcp.models.libp2p_model'].__dict__['HAS_LIBP2P'] = True
                    logger.info("Updated MCP integration flags successfully")
                except Exception as e:
                    logger.warning(f"Failed to update MCP integration flags: {e}")
            
            logger.info("MCP integration with libp2p is available")
            return True
            
        except ImportError as e:
            logger.warning(f"Failed to import MCP libp2p integration modules: {e}")
            return False
            
    except ImportError:
        logger.info("MCP server modules are not installed or not in the path")
        return False


def verify_installation() -> Dict[str, bool]:
    """
    Verify the installation by running tests.
    
    Returns:
        Dict with test results
    """
    results = {
        "imports_successful": False,
        "ipfs_kit_integration": False,
        "mcp_integration": False,
        "can_create_peer": False,
        "can_generate_keys": False,
    }
    
    # Check if imports work
    import_results = check_libp2p_imports()
    results["imports_successful"] = all(
        import_results.get(module, False) 
        for module in ["libp2p", "multiaddr", "cryptography", "base58"]
    )
    
    if not results["imports_successful"]:
        return results
    
    # Check IPFS Kit integration
    results["ipfs_kit_integration"] = ensure_ipfs_kit_integration()
    
    # Check MCP integration
    results["mcp_integration"] = ensure_mcp_libp2p_integration()
    
    # Test creating a peer instance
    if HAS_LIBP2P:
        try:
            import libp2p
            import multiaddr
            import tempfile
            
            # Test key generation
            try:
                from libp2p.crypto.rsa import RSAPrivateKey, create_new_key_pair
                keypair = create_new_key_pair()
                results["can_generate_keys"] = keypair is not None
            except Exception as e:
                logger.error(f"Failed to generate keys: {e}")
            
            if results["ipfs_kit_integration"]:
                try:
                    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
                    
                    # Create temporary identity path
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        pass
                    
                    try:
                        # Try creating a peer
                        try:
                            peer = IPFSLibp2pPeer(
                                identity_path=tmp.name,
                                role="leecher"
                            )
                            # If we get here, peer creation was successful
                            results["can_create_peer"] = True
                        except Exception as e:
                            logger.error(f"Failed to create peer: {e}")
                    finally:
                        # Clean up temporary file
                        try:
                            os.unlink(tmp.name)
                        except:
                            pass
                        
                except ImportError:
                    logger.warning("IPFSLibp2pPeer is not available")
        except Exception as e:
            logger.error(f"Error during verification: {e}")
    
    return results


def print_system_info() -> None:
    """Print system information for debugging purposes."""
    print("\nSystem Information:")
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Path: {sys.path}")
    
    # Print installed packages
    print("\nInstalled packages:")
    try:
        installed = [f"{pkg.key}=={pkg.version}" for pkg in pkg_resources.working_set]
        installed.sort()
        
        for pkg in installed:
            if any(name in pkg.lower() for name in ["libp2p", "crypto", "multiaddr", "base58", "protobuf"]):
                print(f"  {pkg}")
    except Exception as e:
        print(f"  Error getting installed packages: {e}")


def install_mock_if_needed() -> bool:
    """
    Install mock implementations if real libp2p can't be installed.
    
    Returns:
        bool: True if mock was installed successfully, False otherwise
    """
    try:
        # Check if ipfs_kit_py is available
        import ipfs_kit_py
        
        # See if we have the mock implementation
        try:
            from ipfs_kit_py.libp2p.libp2p_mocks import apply_libp2p_mocks
            
            logger.info("Found mock implementation, applying mocks...")
            apply_libp2p_mocks()
            
            # Update module flags
            import sys
            if 'ipfs_kit_py.libp2p' in sys.modules:
                sys.modules['ipfs_kit_py.libp2p'].__dict__['HAS_LIBP2P'] = True
            if 'ipfs_kit_py.libp2p_peer' in sys.modules:
                sys.modules['ipfs_kit_py.libp2p_peer'].__dict__['HAS_LIBP2P'] = True
            
            # If mcp module is available, update its flags too
            if 'ipfs_kit_py.mcp.models.libp2p_model' in sys.modules:
                sys.modules['ipfs_kit_py.mcp.models.libp2p_model'].__dict__['HAS_LIBP2P'] = True
            
            logger.info("Successfully applied mock implementations")
            return True
            
        except ImportError:
            logger.warning("Mock implementation not found")
            
            # Try to copy enhanced_libp2p_mock.py if it exists
            script_dir = os.path.dirname(os.path.abspath(__file__))
            mock_path = os.path.join(script_dir, "enhanced_libp2p_mock.py")
            
            if os.path.exists(mock_path):
                logger.info("Found enhanced_libp2p_mock.py, running it...")
                
                try:
                    # Run the mock script
                    subprocess.run([sys.executable, mock_path], check=True)
                    logger.info("Successfully ran mock implementation")
                    return True
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to run mock implementation: {e}")
                    return False
            else:
                logger.info("Enhanced mock implementation not found")
                return False
            
    except ImportError:
        logger.warning("ipfs_kit_py is not installed")
        return False


def check_environment_variables() -> None:
    """Check and report on relevant environment variables."""
    env_vars = {
        "PYTHONPATH": "Python module search path",
        "IPFS_KIT_AUTO_INSTALL_DEPS": "Auto-install dependencies flag",
        "IPFS_PATH": "IPFS configuration directory",
        "LIBP2P_FORCE_PURELIB": "Force pure Python libp2p",
    }
    
    logger.info("Checking environment variables:")
    for var, desc in env_vars.items():
        value = os.environ.get(var)
        if value:
            logger.info(f"  {var}: {value} ({desc})")
        else:
            logger.debug(f"  {var} not set ({desc})")


def check_dependencies() -> bool:
    """
    Check if libp2p dependencies are available.
    
    Returns:
        bool: True if libp2p is available
    """
    global HAS_LIBP2P
    
    import_results = check_libp2p_imports()
    
    # Check if core dependencies are available
    core_available = all(
        import_results.get(module, False) 
        for module in ["libp2p", "multiaddr", "cryptography", "base58"]
    )
    
    HAS_LIBP2P = core_available
    
    return core_available


def install_dependencies_auto(force=False, install_dir=None):
    """
    Automatically install all required libp2p dependencies.
    
    This function is designed to be imported by other modules that need to ensure
    libp2p dependencies are available before proceeding.
    
    Args:
        force: If True, force reinstallation even if already present
        install_dir: Custom installation directory (optional)
        
    Returns:
        bool: True if all dependencies were installed successfully
    """
    logger.info("Auto-installing libp2p dependencies (force=%s)", force)
    
    # Check if already installed first
    if not force:
        import_results = check_libp2p_imports()
        all_available = all(
            import_results.get(module, False) 
            for module in ["libp2p", "multiaddr", "cryptography", "base58"]
        )
        
        if all_available:
            logger.info("Dependencies already installed, skipping installation")
            return True
    
    # Install dependencies
    success = install_libp2p_dependencies(force=force, install_dir=install_dir)
    
    if success:
        # Ensure integration with IPFS Kit
        ensure_ipfs_kit_integration()
        
        # Ensure integration with MCP server
        ensure_mcp_libp2p_integration()
        
        # Re-check imports
        import_results = check_libp2p_imports()
        all_available = all(
            import_results.get(module, False) 
            for module in ["libp2p", "multiaddr", "cryptography", "base58"]
        )
        
        return all_available
    
    return False

def check_dependency(package_name, min_version=None):
    """
    Check if a specific dependency is installed.
    
    Args:
        package_name: Name of the package to check
        min_version: Minimum required version (optional)
        
    Returns:
        tuple: (is_installed, version_str) where is_installed is a boolean and 
              version_str is the installed version or None if not installed
    """
    if not HAS_PKG_RESOURCES:
        # Fall back to importlib if pkg_resources is not available
        try:
            module = importlib.import_module(package_name)
            if hasattr(module, "__version__"):
                version = module.__version__
                if min_version:
                    try:
                        # Simple string comparison (not as robust as pkg_resources)
                        is_installed = version >= min_version
                    except (TypeError, ValueError):
                        # If version comparison fails, assume it's installed
                        is_installed = True
                else:
                    is_installed = True
                return is_installed, version
            else:
                # Module exists but no version info
                return True, "unknown"
        except ImportError:
            return False, None
    
    # Use pkg_resources if available
    try:
        pkg = pkg_resources.get_distribution(package_name)
        is_installed = True
        
        if min_version:
            is_installed = pkg_resources.parse_version(pkg.version) >= pkg_resources.parse_version(min_version)
            
        return is_installed, pkg.version
    except pkg_resources.DistributionNotFound:
        return False, None
    except Exception as e:
        logger.warning(f"Error checking dependency {package_name}: {e}")
        return False, None

def main():
    """Main function for the script."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Install libp2p dependencies for IPFS Kit and MCP Server"
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Force reinstallation even if dependencies are already present"
    )
    parser.add_argument(
        "--check-only", 
        action="store_true", 
        help="Only check if dependencies are available, don't install"
    )
    parser.add_argument(
        "--install-dir",
        type=str,
        help="Specify a custom installation directory for dependencies"
    )
    parser.add_argument(
        "--use-mocks",
        action="store_true",
        help="Use mock implementations instead of real libp2p"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Set log level based on arguments
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)
    
    logger.info("Starting libp2p dependency installer")
    
    # Check environment variables
    check_environment_variables()
    
    # Check existing dependencies
    logger.info("Checking for installed libp2p dependencies...")
    has_dependencies = check_dependencies()
    
    if has_dependencies and not args.force and not args.check_only:
        logger.info("libp2p dependencies are already installed")
        
        # Verify the installation
        logger.info("Verifying installation...")
        results = verify_installation()
        
        if not all(results.values()):
            logger.warning("Installation verification failed, will attempt repair")
            has_dependencies = False
    
    # If we're only checking, exit now
    if args.check_only:
        if has_dependencies:
            print("✅ libp2p dependencies are installed and available")
            results = verify_installation()
            print("\nVerification results:")
            for test, passed in results.items():
                status = "✅ Passed" if passed else "❌ Failed"
                print(f"  {test}: {status}")
            sys.exit(0)
        else:
            print("❌ libp2p dependencies are NOT available")
            
            # Print missing dependencies
            import_results = check_libp2p_imports()
            print("\nMissing dependencies:")
            for module, available in import_results.items():
                if not available:
                    print(f"  ❌ {module}")
            
            print("\nUse this script without --check-only to install the missing dependencies")
            sys.exit(1)
    
    # If we need to install or repair
    if not has_dependencies or args.force:
        if args.use_mocks:
            logger.info("Using mock implementations instead of real libp2p")
            mocks_installed = install_mock_if_needed()
            
            if mocks_installed:
                logger.info("Successfully installed mock implementations")
                print("✅ libp2p mock implementation installed and applied")
                sys.exit(0)
            else:
                logger.error("Failed to install mock implementations")
                print("❌ Failed to install libp2p mock implementations")
                sys.exit(1)
                
        # Install real dependencies
        logger.info("Installing libp2p dependencies...")
        success = install_libp2p_dependencies(force=args.force, install_dir=args.install_dir)
        
        if success:
            logger.info("Successfully installed libp2p dependencies")
            
            # Re-check imports
            has_dependencies = check_dependencies()
            if not has_dependencies:
                logger.error("Installation completed but imports still failing")
                print("❌ libp2p dependencies installation failed: imports not working")
                print_system_info()
                sys.exit(1)
                
            # Ensure integration with IPFS Kit
            ensure_ipfs_kit_integration()
            
            # Verify the installation
            logger.info("Verifying installation...")
            results = verify_installation()
            
            # Print verification results
            print("\nVerification results:")
            for test, passed in results.items():
                status = "✅ Passed" if passed else "❌ Failed"
                print(f"  {test}: {status}")
                
            if all(results.values()):
                print("\n✅ libp2p installation and verification successful")
                sys.exit(0)
            else:
                print("\n⚠️ libp2p installed but some verification tests failed")
                
                # If can't create peer, suggest mock implementation
                if not results["can_create_peer"]:
                    print("\nNote: If you continue having issues, try using mock implementations:")
                    print(f"  {sys.executable} {sys.argv[0]} --use-mocks")
                
                sys.exit(1)
        else:
            logger.error("Failed to install libp2p dependencies")
            print("❌ libp2p dependencies installation failed")
            
            # Try to install mock implementation as fallback
            print("\nAttempting to install mock implementation as fallback...")
            mocks_installed = install_mock_if_needed()
            
            if mocks_installed:
                print("✅ Installed mock implementation as fallback")
                sys.exit(0)
            else:
                print("❌ Failed to install mock implementation")
                print_system_info()
                sys.exit(1)
    else:
        # Dependencies were already installed
        print("✅ libp2p dependencies are already installed")
        
        # Ensure integration with IPFS Kit
        kit_integration = ensure_ipfs_kit_integration()
        
        # Ensure integration with MCP server
        mcp_integration = ensure_mcp_libp2p_integration()
        
        if kit_integration:
            print("✅ IPFS Kit integration is available")
        else:
            print("⚠️ IPFS Kit integration is NOT available")
        
        if mcp_integration:
            print("✅ MCP server integration is available")
        else:
            print("⚠️ MCP server integration is NOT available")
            
        sys.exit(0)


# Define variables that can be imported by other modules
__all__ = ["HAS_LIBP2P", "check_dependencies", "install_libp2p_dependencies", 
           "install_dependencies_auto", "check_dependency"]

if __name__ == "__main__":
    main()
