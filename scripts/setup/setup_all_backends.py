#!/usr/bin/env python3
"""
Unified script to install and configure all filesystem backends.

This script runs all install_ and config_ scripts for filesystem backends
including IPFS, Lotus, Storacha, and Synapse SDK.

Usage:
    python setup_all_backends.py [--backend=BACKEND] [--verbose]

Backends:
    all (default) - Setup all backends
    ipfs         - Setup IPFS only
    lotus        - Setup Lotus only  
    storacha     - Setup Storacha only
    synapse      - Setup Synapse SDK only
"""

import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BackendSetupManager:
    """Manager for setting up all filesystem backends."""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.project_root = project_root
        self.ipfs_kit_dir = os.path.join(project_root, "ipfs_kit_py")
        
        # Define backend configurations
        self.backends = {
            'ipfs': {
                'name': 'IPFS',
                'install_module': 'install_ipfs',
                'config_module': None,  # IPFS config is handled in the main module
                'description': 'InterPlanetary File System'
            },
            'lotus': {
                'name': 'Lotus',
                'install_module': 'install_lotus',
                'config_module': None,  # Lotus config is handled in lotus_kit
                'description': 'Filecoin Lotus client'
            },
            'storacha': {
                'name': 'Storacha',
                'install_module': 'install_storacha',
                'config_module': None,  # Storacha config is handled in storacha_kit
                'description': 'Storacha Web3 storage'
            },
            'synapse': {
                'name': 'Synapse SDK',
                'install_module': 'install_synapse_sdk',
                'config_module': 'config_synapse_sdk',
                'description': 'Synapse SDK with Filecoin PDP'
            }
        }
    
    def setup_backend(self, backend_name):
        """Setup a specific backend."""
        if backend_name not in self.backends:
            logger.error(f"Unknown backend: {backend_name}")
            return False
        
        backend_config = self.backends[backend_name]
        logger.info(f"\n{'='*60}")
        logger.info(f"Setting up {backend_config['name']} ({backend_config['description']})")
        logger.info(f"{'='*60}")
        
        # Step 1: Install the backend
        success = self._run_install(backend_name, backend_config)
        if not success:
            logger.error(f"❌ Failed to install {backend_config['name']}")
            return False
        
        # Step 2: Configure the backend (if applicable)
        if backend_config['config_module']:
            success = self._run_config(backend_name, backend_config)
            if not success:
                logger.warning(f"⚠ Failed to configure {backend_config['name']} (non-critical)")
        
        logger.info(f"✅ {backend_config['name']} setup completed successfully!")
        return True
    
    def _run_install(self, backend_name, backend_config):
        """Run installation for a backend."""
        logger.info(f"📦 Installing {backend_config['name']}...")
        
        try:
            # Import the install module
            install_module = backend_config['install_module']
            module = __import__(f"ipfs_kit_py.{install_module}", fromlist=[install_module])
            
            # Get the install class (should have same name as module)
            install_class = getattr(module, install_module)
            
            # Create installer instance
            metadata = {'verbose': self.verbose}
            installer = install_class(metadata=metadata)
            
            # For Synapse SDK, check if methods exist
            if backend_name == 'synapse':
                # Handle Synapse SDK installation
                return self._install_synapse_sdk(installer)
            elif backend_name == 'ipfs':
                if hasattr(installer, 'install_ipfs_daemon'):
                    return bool(installer.install_ipfs_daemon())
            elif backend_name == 'lotus':
                if hasattr(installer, 'install_lotus_daemon'):
                    return bool(installer.install_lotus_daemon())
            elif backend_name == 'storacha':
                success = True
                if hasattr(installer, 'install_storacha_dependencies'):
                    success = bool(installer.install_storacha_dependencies()) and success
                if hasattr(installer, 'install_w3_cli'):
                    w3_success = bool(installer.install_w3_cli())
                    if not w3_success:
                        logger.warning("W3 CLI installation skipped or failed; continuing without it")
                return success
            else:
                # Handle other backends - try different method names
                for method_name in ['install', 'run', 'setup']:
                    if hasattr(installer, method_name):
                        method = getattr(installer, method_name)
                        result = method()
                        if isinstance(result, bool):
                            return result
                        elif isinstance(result, dict):
                            return result.get('success', False)
                        else:
                            return True  # Assume success if no clear return
                
                logger.warning(f"⚠ No known install method found for {backend_config['name']}")
                return True  # Don't fail on missing methods
                
        except Exception as e:
            logger.error(f"❌ Installation failed: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def _install_synapse_sdk(self, installer):
        """Special handling for Synapse SDK installation."""
        try:
            # Check available methods
            methods = [attr for attr in dir(installer) if not attr.startswith('_')]
            logger.info(f"Available installer methods: {methods}")
            
            # Try to create JS wrapper files (this should work)
            if hasattr(installer, 'create_js_wrapper_files'):
                success = installer.create_js_wrapper_files()
                if success:
                    logger.info("✓ JavaScript wrapper files created")
                else:
                    logger.warning("⚠ Failed to create JavaScript wrapper files")
            
            # Try to install Node.js if needed
            if hasattr(installer, 'install_nodejs'):
                try:
                    success = installer.install_nodejs()
                    if success:
                        logger.info("✓ Node.js installation completed")
                    else:
                        logger.warning("⚠ Node.js installation failed or not needed")
                except Exception as e:
                    logger.warning(f"⚠ Node.js installation error: {e}")
            
            # Try to install NPM packages
            if hasattr(installer, 'install_npm_dependencies'):
                try:
                    success = installer.install_npm_dependencies()
                    if success:
                        logger.info("✓ NPM packages installed")
                    else:
                        logger.warning("⚠ NPM package installation failed")
                except Exception as e:
                    logger.warning(f"⚠ NPM package installation error: {e}")
            
            logger.info("✓ Synapse SDK installation steps completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Synapse SDK installation error: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def _run_config(self, backend_name, backend_config):
        """Run configuration for a backend."""
        logger.info(f"⚙️  Configuring {backend_config['name']}...")
        
        try:
            # Import the config module
            config_module = backend_config['config_module']
            module = __import__(f"ipfs_kit_py.{config_module}", fromlist=[config_module])
            
            # Get the config class
            config_class = getattr(module, config_module)
            
            # Create config instance
            config_manager = config_class()
            
            # For Synapse SDK configuration
            if backend_name == 'synapse':
                # Try to setup basic configuration
                if hasattr(config_manager, 'create_default_config'):
                    config_manager.create_default_config()
                    logger.info("✓ Default Synapse configuration created")
                elif hasattr(config_manager, 'setup_config'):
                    config_manager.setup_config()
                    logger.info("✓ Synapse configuration setup completed")
                else:
                    logger.info("✓ Synapse configuration manager initialized")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Configuration failed: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def setup_all_backends(self):
        """Setup all backends."""
        logger.info("🚀 Setting up all filesystem backends...")
        
        results = {}
        for backend_name in self.backends.keys():
            results[backend_name] = self.setup_backend(backend_name)
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("BACKEND SETUP SUMMARY")
        logger.info(f"{'='*60}")
        
        success_count = 0
        for backend_name, success in results.items():
            backend_config = self.backends[backend_name]
            status = "✅ SUCCESS" if success else "❌ FAILED"
            logger.info(f"{backend_config['name']:<15} {status}")
            if success:
                success_count += 1
        
        logger.info(f"\nCompleted: {success_count}/{len(self.backends)} backends")
        
        if success_count == len(self.backends):
            logger.info("🎉 All backends setup successfully!")
        else:
            logger.warning("⚠ Some backends failed to setup. Check logs above.")
        
        return success_count == len(self.backends)
    
    def test_integrations(self):
        """Test backend integrations."""
        logger.info("\n🧪 Testing backend integrations...")
        
        # Test IPFS Kit integration
        try:
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            kit = ipfs_kit(metadata={"role": "leecher"})
            
            backends_available = []
            if hasattr(kit, 'ipfs'):
                backends_available.append('IPFS')
            if hasattr(kit, 'lotus_kit') and kit.lotus_kit:
                backends_available.append('Lotus')
            if hasattr(kit, 'storacha_kit') and kit.storacha_kit:
                backends_available.append('Storacha')
            if hasattr(kit, 'synapse_storage') and kit.synapse_storage:
                backends_available.append('Synapse')
            
            logger.info(f"✓ IPFS Kit integration: {len(backends_available)} backends available")
            logger.info(f"  Available backends: {', '.join(backends_available)}")
            
        except Exception as e:
            logger.error(f"❌ IPFS Kit integration test failed: {e}")
        
        # Test FSSpec integration
        try:
            from ipfs_kit_py.enhanced_fsspec import IPFSFileSystem
            import fsspec
            
            protocols = ['ipfs', 'filecoin', 'storacha', 'synapse']
            available_protocols = []
            
            for protocol in protocols:
                try:
                    fs = IPFSFileSystem(backend=protocol)
                    available_protocols.append(protocol)
                except Exception:
                    pass
            
            logger.info(f"✓ FSSpec integration: {len(available_protocols)} protocols available")
            logger.info(f"  Available protocols: {', '.join(available_protocols)}")
            
        except Exception as e:
            logger.error(f"❌ FSSpec integration test failed: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Setup filesystem backends for IPFS Kit')
    parser.add_argument('--backend', default='all', 
                       choices=['all', 'ipfs', 'lotus', 'storacha', 'synapse'],
                       help='Backend to setup (default: all)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--test', action='store_true',
                       help='Run integration tests after setup')
    
    args = parser.parse_args()
    
    # Create setup manager
    manager = BackendSetupManager(verbose=args.verbose)
    
    # Setup backends
    if args.backend == 'all':
        success = manager.setup_all_backends()
    else:
        success = manager.setup_backend(args.backend)
    
    # Run tests if requested
    if args.test:
        manager.test_integrations()
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
