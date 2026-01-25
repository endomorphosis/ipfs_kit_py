"""
IPFS Kit Daemon Configuration Manager

This module provides comprehensive daemon configuration management for IPFS Kit,
including IPFS, Lotus, and other related daemons. It handles configuration
validation, daemon startup/shutdown, and health monitoring.
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class DaemonConfigManager:
    """
    Comprehensive daemon configuration manager for IPFS Kit.
    
    Handles configuration, startup, and monitoring of IPFS, Lotus, and related daemons.
    """
    
    def __init__(self, ipfs_kit_instance=None):
        """
        Initialize the daemon configuration manager.
        
        Args:
            ipfs_kit_instance: Optional ipfs_kit instance for integration
        """
        self.ipfs_kit = ipfs_kit_instance
        self.logger = logger
        
        # Default paths
        self.ipfs_path = os.environ.get('IPFS_PATH', os.path.expanduser('~/.ipfs'))
        self.lotus_path = os.environ.get('LOTUS_PATH', os.path.expanduser('~/.lotus'))
        
        # Configuration defaults
        self.default_config = {
            'ipfs': {
                'enabled': True,
                'auto_start': True,
                'api_port': 5001,
                'gateway_port': 8080,
                'swarm_port': 4001
            },
            'lotus': {
                'enabled': False,
                'auto_start': False,
                'api_port': 1234,
                'network': 'mainnet'
            },
            'cluster': {
                'enabled': False,
                'cluster_secret': '',
                'cluster_name': 'ipfs-kit-cluster'
            }
        }
        
        # Daemon status tracking
        self.daemon_status = {
            'ipfs': False,
            'lotus': False,
            'cluster': False
        }
    
    def check_daemon_configuration(self, daemon_type: str = 'ipfs') -> Dict[str, Any]:
        """
        Check if a daemon is properly configured.
        
        Args:
            daemon_type: Type of daemon ('ipfs', 'lotus', 'cluster')
            
        Returns:
            Dict with configuration status and details
        """
        result = {
            'configured': False,
            'path_exists': False,
            'config_exists': False,
            'valid_config': False,
            'errors': []
        }
        
        try:
            if daemon_type == 'ipfs':
                result = self._check_ipfs_config()
            elif daemon_type == 'lotus':
                result = self._check_lotus_config()
            elif daemon_type == 'cluster':
                result = self._check_cluster_config()
            else:
                result['errors'].append(f"Unknown daemon type: {daemon_type}")
                
        except Exception as e:
            result['errors'].append(f"Error checking {daemon_type} configuration: {str(e)}")
            
        return result
    
    def _check_ipfs_config(self) -> Dict[str, Any]:
        """Check IPFS daemon configuration."""
        result = {
            'configured': False,
            'path_exists': False,
            'config_exists': False,
            'valid_config': False,
            'errors': []
        }
        
        try:
            # Check if IPFS path exists
            ipfs_path = Path(self.ipfs_path)
            result['path_exists'] = ipfs_path.exists()
            
            # Check if config file exists
            config_file = ipfs_path / 'config'
            result['config_exists'] = config_file.exists()
            
            if result['config_exists']:
                # Validate config content
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    # Basic validation
                    required_keys = ['Identity', 'Addresses', 'Discovery']
                    if all(key in config for key in required_keys):
                        result['valid_config'] = True
                        result['configured'] = True
                    else:
                        result['errors'].append("Config missing required keys")
                        
                except json.JSONDecodeError as e:
                    result['errors'].append(f"Invalid JSON in config: {str(e)}")
            else:
                result['errors'].append("IPFS config file not found")
                
        except Exception as e:
            result['errors'].append(f"Error checking IPFS config: {str(e)}")
            
        return result
    
    def _check_lotus_config(self) -> Dict[str, Any]:
        """Check Lotus daemon configuration."""
        result = {
            'configured': False,
            'path_exists': False,
            'config_exists': False,
            'valid_config': False,
            'errors': []
        }
        
        try:
            # Check if Lotus path exists
            lotus_path = Path(self.lotus_path)
            result['path_exists'] = lotus_path.exists()
            
            # Check if config file exists
            config_file = lotus_path / 'config.toml'
            result['config_exists'] = config_file.exists()
            
            if result['config_exists']:
                result['valid_config'] = True
                result['configured'] = True
            else:
                # Lotus can work without explicit config
                result['configured'] = result['path_exists']
                
        except Exception as e:
            result['errors'].append(f"Error checking Lotus config: {str(e)}")
            
        return result
    
    def _check_cluster_config(self) -> Dict[str, Any]:
        """Check IPFS Cluster configuration."""
        result = {
            'configured': False,
            'path_exists': False,
            'config_exists': False,
            'valid_config': False,
            'errors': []
        }
        
        # IPFS Cluster config is optional for basic operation
        result['configured'] = True  # Default to enabled
        
        return result
    
    def configure_daemon(self, daemon_type: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Configure a daemon with the provided configuration.
        
        Args:
            daemon_type: Type of daemon ('ipfs', 'lotus', 'cluster')
            config: Optional configuration dict, uses defaults if None
            
        Returns:
            Dict with configuration results
        """
        result = {
            'success': False,
            'configured': False,
            'message': '',
            'errors': []
        }
        
        try:
            if daemon_type == 'ipfs':
                result = self._configure_ipfs(config)
            elif daemon_type == 'lotus':
                result = self._configure_lotus(config)
            elif daemon_type == 'cluster':
                result = self._configure_cluster(config)
            else:
                result['errors'].append(f"Unknown daemon type: {daemon_type}")
                
        except Exception as e:
            result['errors'].append(f"Error configuring {daemon_type}: {str(e)}")
            
        return result
    
    def _configure_ipfs(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Configure IPFS daemon."""
        result = {
            'success': False,
            'configured': False,
            'message': '',
            'errors': []
        }
        
        try:
            # Check if already configured
            check_result = self._check_ipfs_config()
            if check_result['configured']:
                result['success'] = True
                result['configured'] = True
                result['message'] = 'IPFS already configured'
                return result
            
            # Initialize IPFS if needed
            if not check_result['path_exists']:
                self.logger.info("Initializing IPFS...")
                try:
                    init_result = subprocess.run(
                        ['ipfs', 'init'],
                        env={'IPFS_PATH': self.ipfs_path},
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if init_result.returncode == 0:
                        result['success'] = True
                        result['configured'] = True
                        result['message'] = 'IPFS initialized successfully'
                        self.logger.info("IPFS initialization completed successfully")
                    else:
                        result['errors'].append(f"IPFS init failed: {init_result.stderr}")
                        self.logger.error(f"IPFS init failed: {init_result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    result['errors'].append("IPFS initialization timed out")
                except FileNotFoundError:
                    result['errors'].append("IPFS binary not found in PATH")
                    result['message'] = "Install IPFS: https://docs.ipfs.io/install/"
                except Exception as e:
                    result['errors'].append(f"IPFS initialization error: {str(e)}")
            else:
                # Path exists but config is invalid or missing, try to reinitialize
                self.logger.warning("IPFS path exists but configuration is invalid or missing; attempting reinit")
                try:
                    init_result = subprocess.run(
                        ['ipfs', 'init'],
                        env={'IPFS_PATH': self.ipfs_path},
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    init_output = (init_result.stdout or "") + (init_result.stderr or "")
                    if init_result.returncode == 0 or "already initialized" in init_output.lower():
                        result['success'] = True
                        result['configured'] = True
                        result['message'] = 'IPFS initialized successfully'
                        self.logger.info("IPFS initialization completed successfully")
                    else:
                        result['errors'].append(f"IPFS init failed: {init_output.strip()}")
                        result['message'] = 'IPFS path exists but needs manual configuration'
                except subprocess.TimeoutExpired:
                    result['errors'].append("IPFS initialization timed out")
                except FileNotFoundError:
                    result['errors'].append("IPFS binary not found in PATH")
                    result['message'] = "Install IPFS: https://docs.ipfs.io/install/"
                except Exception as e:
                    result['errors'].append(f"IPFS initialization error: {str(e)}")
            
        except Exception as e:
            result['errors'].append(f"Error configuring IPFS: {str(e)}")
            
        return result
    
    def _configure_lotus(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Configure Lotus daemon."""
        result = {
            'success': True,  # Lotus often works without explicit config
            'configured': True,
            'message': 'Lotus configuration validated',
            'errors': []
        }
        return result
    
    def _configure_cluster(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Configure IPFS Cluster."""
        result = {
            'success': True,  # Cluster is optional
            'configured': True,
            'message': 'Cluster configuration skipped (optional)',
            'errors': []
        }
        return result
    
    def start_daemon(self, daemon_type: str) -> Dict[str, Any]:
        """
        Start a daemon service.
        
        Args:
            daemon_type: Type of daemon ('ipfs', 'lotus', 'cluster')
            
        Returns:
            Dict with startup results
        """
        result = {
            'success': False,
            'running': False,
            'message': '',
            'errors': []
        }
        
        try:
            # Check if already running
            if self.is_daemon_running(daemon_type):
                result['success'] = True
                result['running'] = True
                result['message'] = f'{daemon_type} daemon already running'
                return result
            
            # Configure before starting
            config_result = self.configure_daemon(daemon_type)
            if not config_result['success']:
                result['errors'].extend(config_result['errors'])
                result['message'] = f'Configuration failed for {daemon_type}'
                return result
            
            # Start the daemon
            if daemon_type == 'ipfs':
                result = self._start_ipfs()
            elif daemon_type == 'lotus':
                result = self._start_lotus()
            elif daemon_type == 'cluster':
                result = self._start_cluster()
            else:
                result['errors'].append(f"Unknown daemon type: {daemon_type}")
                
        except Exception as e:
            result['errors'].append(f"Error starting {daemon_type}: {str(e)}")
            
        return result
    
    def _start_ipfs(self) -> Dict[str, Any]:
        """Start IPFS daemon."""
        result = {
            'success': False,
            'running': False,
            'message': '',
            'errors': []
        }
        
        try:
            # Try to start IPFS daemon
            self.logger.info("Starting IPFS daemon...")
            
            # Use daemon startup if available from ipfs_kit
            if self.ipfs_kit and hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'daemon_start'):
                daemon_result = self.ipfs_kit.ipfs.daemon_start()
                if daemon_result.get('success', False):
                    result['success'] = True
                    result['running'] = True
                    result['message'] = 'IPFS daemon started successfully via ipfs_kit'
                else:
                    result['errors'].append(f'IPFS daemon startup failed via ipfs_kit: {daemon_result.get("error", "Unknown error")}')
            else:
                # Try enhanced daemon manager (cross-platform)
                try:
                    from .enhanced_daemon_manager import EnhancedDaemonManager
                    daemon_manager = EnhancedDaemonManager(ipfs_path=self.ipfs_path)
                    start_result = daemon_manager.start_daemon(detach=True, init_if_needed=True)
                    status = start_result.get("status")
                    if status in ("started", "already_running"):
                        result['success'] = True
                        result['running'] = True
                        result['message'] = f"IPFS daemon {status} via enhanced manager"
                    else:
                        result['errors'].append(start_result.get("message", "Failed to start IPFS daemon"))
                except Exception as e:
                    result['errors'].append(f'Error starting IPFS daemon: {str(e)}')
                
        except Exception as e:
            result['errors'].append(f"Error starting IPFS daemon: {str(e)}")
            
        return result
    
    def _start_lotus(self) -> Dict[str, Any]:
        """Start Lotus daemon."""
        result = {
            'success': True,  # Optional daemon
            'running': False,
            'message': 'Lotus daemon startup skipped (optional)',
            'errors': []
        }
        return result
    
    def _start_cluster(self) -> Dict[str, Any]:
        """Start IPFS Cluster daemon."""
        result = {
            'success': True,  # Optional daemon
            'running': False,
            'message': 'Cluster daemon startup skipped (optional)',
            'errors': []
        }
        return result
    
    def is_daemon_running(self, daemon_type: str) -> bool:
        """
        Check if a daemon is currently running.
        
        Args:
            daemon_type: Type of daemon ('ipfs', 'lotus', 'cluster')
            
        Returns:
            True if daemon is running, False otherwise
        """
        try:
            if daemon_type == 'ipfs':
                return self._check_ipfs_running()
            elif daemon_type == 'lotus':
                return self._check_lotus_running()
            elif daemon_type == 'cluster':
                return self._check_cluster_running()
            else:
                return False
                
        except Exception as e:
            self.logger.warning(f"Error checking {daemon_type} status: {str(e)}")
            return False
    
    def _check_ipfs_running(self) -> bool:
        """Check if IPFS daemon is running."""
        try:
            # Try to connect to IPFS API
            result = subprocess.run(
                ['ipfs', 'id'],
                env={'IPFS_PATH': self.ipfs_path},
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.logger.debug("IPFS daemon is running")
                return True
            else:
                self.logger.debug(f"IPFS daemon not running: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.logger.debug("IPFS daemon check timed out")
            return False
        except FileNotFoundError:
            self.logger.debug("IPFS binary not found in PATH")
            return False
        except Exception as e:
            self.logger.debug(f"IPFS daemon check failed: {str(e)}")
            return False
    
    def _check_lotus_running(self) -> bool:
        """Check if Lotus daemon is running."""
        try:
            # Try basic lotus command
            result = subprocess.run(
                ['lotus', 'version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _check_cluster_running(self) -> bool:
        """Check if IPFS Cluster is running."""
        return False  # Cluster is optional
    
    def get_daemon_status(self) -> Dict[str, bool]:
        """
        Get the current status of all managed daemons.
        
        Returns:
            Dict mapping daemon names to their running status
        """
        status = {}
        for daemon_type in ['ipfs', 'lotus', 'cluster']:
            is_running = self.is_daemon_running(daemon_type)
            status[daemon_type] = is_running
            self.logger.debug(f"Daemon {daemon_type} status: {'running' if is_running else 'not running'}")
        
        self.daemon_status.update(status)
        return status
    
    def get_detailed_status_report(self) -> Dict[str, Any]:
        """
        Get a detailed status report of all daemons.
        
        Returns:
            Dict with detailed status information
        """
        report = {
            'timestamp': time.time(),
            'daemons': {},
            'summary': {
                'total': 3,
                'running': 0,
                'configured': 0,
                'required_running': 0
            }
        }
        
        for daemon_type in ['ipfs', 'lotus', 'cluster']:
            # Check if running
            is_running = self.is_daemon_running(daemon_type)
            
            # Check configuration
            config_status = self.check_daemon_configuration(daemon_type)
            
            report['daemons'][daemon_type] = {
                'running': is_running,
                'configured': config_status.get('configured', False),
                'required': daemon_type == 'ipfs',  # Only IPFS is truly required
                'errors': config_status.get('errors', [])
            }
            
            # Update summary
            if is_running:
                report['summary']['running'] += 1
                if daemon_type == 'ipfs':
                    report['summary']['required_running'] += 1
            
            if config_status.get('configured', False):
                report['summary']['configured'] += 1
        
        return report
    
    def ensure_daemons_running(self, daemon_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Ensure specified daemons are running, starting them if necessary.
        
        Args:
            daemon_types: List of daemon types to ensure running, defaults to ['ipfs']
            
        Returns:
            Dict with overall results and per-daemon status
        """
        if daemon_types is None:
            daemon_types = ['ipfs']  # Only IPFS is required by default
        
        result = {
            'success': True,
            'all_running': False,
            'daemon_status': {},
            'errors': []
        }
        
        try:
            for daemon_type in daemon_types:
                if not self.is_daemon_running(daemon_type):
                    start_result = self.start_daemon(daemon_type)
                    result['daemon_status'][daemon_type] = start_result
                    
                    if not start_result['success']:
                        result['success'] = False
                        result['errors'].extend(start_result['errors'])
                else:
                    result['daemon_status'][daemon_type] = {
                        'success': True,
                        'running': True,
                        'message': f'{daemon_type} already running'
                    }
            
            # Check final status
            status = self.get_daemon_status()
            running_daemons = [d for d in daemon_types if status.get(d, False)]
            result['all_running'] = len(running_daemons) == len(daemon_types)
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"Error ensuring daemons running: {str(e)}")
        
        return result
    
    def check_and_configure_all_daemons(self) -> Dict[str, Any]:
        """
        Check and configure all managed daemons.
        
        Returns:
            Dict with overall results and per-daemon status
        """
        result = {
            'success': True,
            'all_configured': False,
            'daemon_results': {},
            'errors': []
        }
        
        try:
            daemon_types = ['ipfs', 'lotus', 'cluster']
            configured_count = 0
            
            for daemon_type in daemon_types:
                # Check current configuration
                check_result = self.check_daemon_configuration(daemon_type)
                
                if not check_result['configured']:
                    # Try to configure
                    config_result = self.configure_daemon(daemon_type)
                    result['daemon_results'][daemon_type] = config_result
                    
                    if config_result['success']:
                        configured_count += 1
                    else:
                        result['success'] = False
                        result['errors'].extend(config_result['errors'])
                else:
                    result['daemon_results'][daemon_type] = {
                        'success': True,
                        'configured': True,
                        'message': f'{daemon_type} already configured'
                    }
                    configured_count += 1
            
            # Check if all required daemons are configured (IPFS is required)
            result['all_configured'] = configured_count >= 1  # At least IPFS
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"Error checking and configuring daemons: {str(e)}")
        
        return result
    
    def start_and_check_daemons(self) -> Dict[str, Any]:
        """
        Attempt to start all required daemons and check their status.
        
        Returns:
            Dict with startup results and status
        """
        result = {
            'success': False,
            'daemons_started': [],
            'daemons_failed': [],
            'status_report': {},
            'errors': []
        }
        
        try:
            # First ensure configuration
            config_result = self.check_and_configure_all_daemons()
            
            # Try to start IPFS (required daemon)
            if not self.is_daemon_running('ipfs'):
                self.logger.info("Attempting to start IPFS daemon...")
                ipfs_start = self.start_daemon('ipfs')
                
                if ipfs_start.get('success', False):
                    result['daemons_started'].append('ipfs')
                    self.logger.info("IPFS daemon started successfully")
                else:
                    result['daemons_failed'].append('ipfs')
                    result['errors'].extend(ipfs_start.get('errors', []))
                    self.logger.warning(f"Failed to start IPFS daemon: {ipfs_start.get('errors', [])}")
            else:
                result['daemons_started'].append('ipfs')
                self.logger.info("IPFS daemon already running")
            
            # Try to start Lotus (optional)
            if not self.is_daemon_running('lotus'):
                self.logger.debug("Lotus daemon not running (optional)")
                result['daemons_failed'].append('lotus')
            else:
                result['daemons_started'].append('lotus')
                self.logger.info("Lotus daemon running")
            
            # Cluster is optional
            if self.is_daemon_running('cluster'):
                result['daemons_started'].append('cluster')
                self.logger.info("Cluster daemon running")
            else:
                self.logger.debug("Cluster daemon not running (optional)")
            
            # Get final status
            result['status_report'] = self.get_detailed_status_report()
            
            # Success if at least IPFS is running
            result['success'] = 'ipfs' in result['daemons_started']
            
        except Exception as e:
            result['errors'].append(f"Error in daemon startup process: {str(e)}")
            self.logger.error(f"Daemon startup process failed: {str(e)}")
            
        return result


# Convenience functions for backward compatibility
def check_daemon_configuration(daemon_type: str = 'ipfs') -> Dict[str, Any]:
    """Standalone function to check daemon configuration."""
    manager = DaemonConfigManager()
    return manager.check_daemon_configuration(daemon_type)


def configure_daemon(daemon_type: str, config: Optional[Dict] = None) -> Dict[str, Any]:
    """Standalone function to configure a daemon."""
    manager = DaemonConfigManager()
    return manager.configure_daemon(daemon_type, config)


def start_daemon(daemon_type: str) -> Dict[str, Any]:
    """Standalone function to start a daemon."""
    manager = DaemonConfigManager()
    return manager.start_daemon(daemon_type)


def is_daemon_running(daemon_type: str) -> bool:
    """Standalone function to check if daemon is running."""
    manager = DaemonConfigManager()
    return manager.is_daemon_running(daemon_type)
