#!/usr/bin/env python3
"""
Google Drive Kit for IPFS Kit.

This module provides comprehensive integration with Google Drive API
with robust authentication, file management, and introspection capabilities.
"""

import json
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import uuid
import socket
import io
import mimetypes
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
from pathlib import Path

# Configure logger
logger = logging.getLogger(__name__)

# Google Drive scopes and endpoints
GOOGLE_DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata'
]

GOOGLE_DRIVE_API_ENDPOINT = "https://www.googleapis.com/drive/v3"
GOOGLE_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"

class IPFSValidationError(Exception):
    """Error when input validation fails."""
    pass

class IPFSContentNotFoundError(Exception):
    """Content with specified CID not found."""
    pass

class IPFSConnectionError(Exception):
    """Error when connecting to services."""
    pass

class IPFSError(Exception):
    """Base class for all IPFS-related exceptions."""
    pass

class IPFSTimeoutError(Exception):
    """Timeout when communicating with services."""
    pass

class GDriveConnectionError(Exception):
    """Error when connecting to Google Drive services."""
    pass

class GDriveAuthenticationError(Exception):
    """Error with Google Drive authentication."""
    pass

class GDriveAPIError(Exception):
    """Error with Google Drive API."""
    pass

class GDriveQuotaError(Exception):
    """Error when Google Drive quota is exceeded."""
    pass

def create_result_dict(operation, correlation_id=None):
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id,
    }

def handle_error(result, error, message=None):
    """Handle errors in a standardized way."""
    result["success"] = False
    result["error"] = message or str(error)
    result["error_type"] = type(error).__name__
    return result

class gdrive_kit:
    def __init__(self, resources=None, metadata=None):
        """Initialize gdrive_kit with resources and metadata.
        
        Args:
            resources: Optional resources like file handles or connections
            metadata: Optional metadata dictionary with configuration
        """
        # Store resources
        self.resources = resources or {}

        # Store metadata
        self.metadata = metadata or {}

        # Generate correlation ID for tracking operations
        self.correlation_id = str(uuid.uuid4())

        # Set up state variables
        self.api_endpoint = GOOGLE_DRIVE_API_ENDPOINT
        self.oauth_endpoint = GOOGLE_OAUTH_ENDPOINT
        self.scopes = GOOGLE_DRIVE_SCOPES
        
        # Initialize authentication state
        self.authenticated = False
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        
        # Service and health monitoring
        self.service_status = "stopped"
        self.health_status = "unknown"
        self.last_health_check = None
        self.health_check_interval = 60  # seconds
        
        # Configuration paths
        self.config_dir = os.path.expanduser("~/.ipfs_kit/gdrive")
        self.credentials_file = os.path.join(self.config_dir, "credentials.json")
        self.token_file = os.path.join(self.config_dir, "token.json")
        
        # Mock mode for testing
        self.mock_mode = metadata.get("mock_mode", False) if metadata else False
        
        # In mock mode, automatically authenticate
        if self.mock_mode:
            self.authenticated = True
            self.access_token = "mock_access_token"
        
        # Setup directories
        self._setup_directories()
        
        # Initialize Google Drive service
        self._initialize_service()
        
        logger.info(f"Google Drive kit initialized")

    def _setup_directories(self):
        """Set up necessary directories for Google Drive kit."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            
            # Create mock storage directories for testing
            if self.mock_mode:
                mock_base = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_gdrive")
                mock_files = os.path.join(mock_base, "files")
                mock_folders = os.path.join(mock_base, "folders")
                
                os.makedirs(mock_files, exist_ok=True)
                os.makedirs(mock_folders, exist_ok=True)
                
                logger.info(f"Google Drive mock storage initialized at: {mock_base}")
        except Exception as e:
            logger.error(f"Error setting up directories: {e}")

    def _check_dns_resolution(self, host):
        """Check if a hostname can be resolved."""
        try:
            socket.gethostbyname(host)
            return True
        except socket.gaierror:
            return False

    def _initialize_service(self):
        """Initialize Google Drive service with authentication."""
        try:
            # Check for existing authentication
            if os.path.exists(self.token_file):
                self._load_existing_token()
            
            # Check DNS connectivity
            if not self.mock_mode and not self._check_dns_resolution("www.googleapis.com"):
                logger.warning("DNS resolution failed for googleapis.com")
                self.service_status = "disconnected"
                return
            
            # Initialize service status
            if self.authenticated:
                self.service_status = "running"
                self.health_status = "healthy"
            else:
                self.service_status = "stopped"
                self.health_status = "unhealthy"
                
        except Exception as e:
            logger.error(f"Error initializing Google Drive service: {e}")
            self.service_status = "error"
            self.health_status = "unhealthy"

    def _load_existing_token(self):
        """Load existing authentication token from file."""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                self.token_expiry = token_data.get('expires_at')
                
                # Check if token is still valid
                if self.token_expiry and time.time() < self.token_expiry:
                    self.authenticated = True
                    logger.info("Loaded valid Google Drive authentication token")
                else:
                    logger.info("Google Drive token expired, will need re-authentication")
                
                return token_data
                    
        except Exception as e:
            logger.error(f"Error loading Google Drive token: {e}")
            return None

    def _save_token(self):
        """Save authentication token to file."""
        try:
            token_data = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_at': self.token_expiry
            }
            
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            # Set secure permissions
            os.chmod(self.token_file, 0o600)
            logger.info("Google Drive authentication token saved")
            
        except Exception as e:
            logger.error(f"Error saving Google Drive token: {e}")

    def _make_api_request(self, method, endpoint_path, data=None, headers=None, timeout=30, params=None):
        """Make an API request to Google Drive with robust error handling."""
        if self.mock_mode:
            return self._mock_api_request(method, endpoint_path, data, params)
        
        try:
            import requests
        except ImportError:
            raise GDriveConnectionError("requests library not installed")

        # Ensure we have a valid token
        if not self.authenticated or not self.access_token:
            raise GDriveAuthenticationError("Not authenticated with Google Drive")
        
        # Check token expiry and refresh if needed
        if self.token_expiry and time.time() > self.token_expiry - 300:  # Refresh 5 minutes before expiry
            self._refresh_access_token()

        url = f"{self.api_endpoint}{endpoint_path}"
        request_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "ipfs-kit-gdrive/1.0"
        }
        
        if headers:
            request_headers.update(headers)

        try:
            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=request_headers,
                params=params,
                timeout=timeout
            )
            
            if response.status_code == 401:
                # Try to refresh token and retry once
                if self._refresh_access_token():
                    request_headers["Authorization"] = f"Bearer {self.access_token}"
                    response = requests.request(
                        method=method,
                        url=url,
                        json=data,
                        headers=request_headers,
                        params=params,
                        timeout=timeout
                    )
                else:
                    raise GDriveAuthenticationError("Authentication failed and token refresh failed")
            
            response.raise_for_status()
            
            # Handle JSON response
            if response.headers.get('content-type', '').startswith('application/json'):
                return response.json()
            else:
                return {"content": response.content, "status_code": response.status_code}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Drive API request failed: {e}")
            raise GDriveConnectionError(f"API request failed: {e}")

    def _mock_api_request(self, method, endpoint_path, data=None, params=None):
        """Mock API request for testing purposes."""
        logger.debug(f"Mock Google Drive API request: {method} {endpoint_path}")
        
        # Mock responses for different endpoints
        if '/files' in endpoint_path and method.upper() == 'GET':
            return {
                "files": [
                    {
                        "id": "1mock_file_id_123",
                        "name": "test_file.txt",
                        "size": "1024",
                        "mimeType": "text/plain",
                        "createdTime": "2024-01-01T00:00:00.000Z",
                        "modifiedTime": "2024-01-01T00:00:00.000Z"
                    }
                ],
                "nextPageToken": None
            }
        elif '/about' in endpoint_path:
            return {
                "storageQuota": {
                    "limit": "17179869184",  # 16 GB
                    "usage": "1073741824",   # 1 GB
                    "usageInDrive": "536870912"  # 512 MB
                },
                "user": {
                    "displayName": "Test User",
                    "emailAddress": "test@example.com"
                }
            }
        elif '/files' in endpoint_path and method.upper() == 'POST':
            # Mock file/folder creation
            mock_id = f"mock_{uuid.uuid4().hex[:8]}"
            result = {
                "id": mock_id,
                "success": True,
                "mock": True
            }
            if data and isinstance(data, dict):
                result["name"] = data.get("name", "unnamed")
                result["mimeType"] = data.get("mimeType", "application/octet-stream")
            return result
        else:
            return {"success": True, "mock": True}

    def _refresh_access_token(self):
        """Refresh the access token using refresh token."""
        if not self.refresh_token:
            return {"success": False, "error": "No refresh token available"}
        
        try:
            import requests
            
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
                'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET')
            }
            
            response = requests.post(self.oauth_endpoint, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)
            self.token_expiry = time.time() + expires_in
            
            # Save updated token
            self._save_token()
            
            logger.info("Google Drive access token refreshed successfully")
            return {"success": True, "access_token": self.access_token}
            
        except Exception as e:
            logger.error(f"Failed to refresh Google Drive token: {e}")
            self.authenticated = False
            return {"success": False, "error": str(e)}

    # Installation and Configuration Methods
    def install(self, **kwargs):
        """Install Google Drive dependencies and setup."""
        operation = "install"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            logger.info("Installing Google Drive kit dependencies...")
            
            # Check if required packages are installed
            missing_packages = self._check_and_install_dependencies()
            
            if missing_packages:
                result["missing_packages"] = missing_packages
                result["message"] = "Some dependencies could not be installed automatically"
            
            # Create configuration directories
            self._setup_directories()
            
            # Check for credentials
            if not os.path.exists(self.credentials_file):
                result["warning"] = "Google Drive credentials not found. Please run config() method to set up authentication."
            
            result["success"] = True
            result["message"] = "Google Drive kit installation completed"
            result["config_dir"] = self.config_dir
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def _check_and_install_dependencies(self):
        """Check and install required Python packages."""
        required_packages = [
            "google-auth",
            "google-auth-oauthlib", 
            "google-auth-httplib2",
            "google-api-python-client",
            "requests"
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                logger.debug(f"Package {package} is available")
            except ImportError:
                missing_packages.append(package)
                logger.warning(f"Package {package} is not installed")
                
                # Try to install automatically
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", package
                    ], capture_output=True)
                    logger.info(f"Successfully installed {package}")
                    missing_packages.remove(package)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to install {package}: {e}")
        
        return missing_packages

    def config(self, **kwargs):
        """Configure Google Drive authentication."""
        operation = "config"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Handle different configuration methods
            if "credentials_file" in kwargs:
                # Use provided credentials file
                creds_file = kwargs["credentials_file"]
                if os.path.exists(creds_file):
                    import shutil
                    shutil.copy2(creds_file, self.credentials_file)
                    result["message"] = "Credentials file copied successfully"
                else:
                    raise IPFSValidationError(f"Credentials file not found: {creds_file}")
            
            elif "client_id" in kwargs and "client_secret" in kwargs:
                # Use provided client credentials
                credentials = {
                    "installed": {
                        "client_id": kwargs["client_id"],
                        "client_secret": kwargs["client_secret"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"]
                    }
                }
                
                with open(self.credentials_file, 'w') as f:
                    json.dump(credentials, f, indent=2)
                
                result["message"] = "Client credentials configured successfully"
            
            else:
                result["message"] = "Please provide either 'credentials_file' or 'client_id' and 'client_secret'"
                result["instructions"] = {
                    "step1": "Go to https://console.developers.google.com/",
                    "step2": "Create a new project or select existing one",
                    "step3": "Enable Google Drive API",
                    "step4": "Create OAuth 2.0 credentials",
                    "step5": "Download credentials JSON file",
                    "step6": "Use config(credentials_file='path/to/credentials.json')"
                }
            
            result["success"] = True
            result["config_dir"] = self.config_dir
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def init(self, **kwargs):
        """Initialize Google Drive service and authenticate."""
        operation = "init"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            if self.mock_mode:
                self.authenticated = True
                self.service_status = "running"
                self.health_status = "healthy"
                result["success"] = True
                result["message"] = "Google Drive kit initialized in mock mode"
                return result
            
            # Check for credentials
            if not os.path.exists(self.credentials_file):
                raise GDriveAuthenticationError("Credentials not found. Please run config() first.")
            
            # Load credentials and authenticate
            try:
                from google.auth.transport.requests import Request
                from google.oauth2.credentials import Credentials
                from google_auth_oauthlib.flow import InstalledAppFlow
                
                creds = None
                
                # Load existing token
                if os.path.exists(self.token_file):
                    creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
                
                # If there are no valid credentials, run OAuth flow
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_file, self.scopes
                        )
                        creds = flow.run_local_server(port=0)
                    
                    # Save credentials
                    with open(self.token_file, 'w') as token:
                        token.write(creds.to_json())
                
                # Store authentication details
                self.access_token = creds.token
                self.refresh_token = creds.refresh_token
                self.token_expiry = creds.expiry.timestamp() if creds.expiry else None
                self.authenticated = True
                
                # Update service status
                self.service_status = "running"
                self.health_status = "healthy"
                
                result["success"] = True
                result["message"] = "Google Drive authentication successful"
                result["authenticated"] = True
                
            except ImportError as e:
                raise GDriveAuthenticationError(f"Required Google API libraries not installed: {e}")
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def start(self, **kwargs):
        """Start Google Drive service."""
        operation = "start"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            if self.service_status == "running" and self.authenticated:
                result["success"] = True
                result["message"] = "Google Drive service is already running"
                result["status"] = "already_running"
                return result
            
            # Initialize service if not authenticated
            if not self.authenticated:
                init_result = self.init(**kwargs)
                if not init_result["success"]:
                    return init_result
            
            # Perform health check to ensure service is responsive
            health_result = self.get_health(**kwargs)
            
            if health_result["success"] and health_result["health"] == "healthy":
                self.service_status = "running"
                result["success"] = True
                result["message"] = "Google Drive service started successfully"
                result["health"] = health_result["health"]
            else:
                result["success"] = False
                result["message"] = "Google Drive service failed health check"
                result["health_result"] = health_result
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def stop(self, **kwargs):
        """Stop Google Drive service."""
        operation = "stop"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Clear authentication
            self.authenticated = False
            self.access_token = None
            self.service_status = "stopped"
            self.health_status = "unknown"
            
            # Optionally remove token file
            if kwargs.get("clear_auth", False) and os.path.exists(self.token_file):
                os.remove(self.token_file)
                result["auth_cleared"] = True
            
            result["success"] = True
            result["message"] = "Google Drive service stopped"
            result["status"] = "stopped"
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    # Health Monitoring and Introspection Methods
    def get_health(self, **kwargs):
        """Get comprehensive health status of Google Drive service."""
        operation = "get_health"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            health_data = {
                "status": self.service_status,
                "health": "unknown",
                "authenticated": self.authenticated,
                "last_check": time.time(),
                "connectivity": False,
                "quota_info": {},
                "api_responsive": False,
                "errors": []
            }
            
            if self.mock_mode:
                health_data["health"] = "healthy"
                health_data["connectivity"] = True
                health_data["api_responsive"] = True
                health_data["quota_info"] = {
                    "total": "17179869184",  # 16 GB
                    "used": "1073741824",    # 1 GB
                    "available": "16106127360"  # 15 GB
                }
            else:
                # Check DNS connectivity
                if self._check_dns_resolution("www.googleapis.com"):
                    health_data["connectivity"] = True
                    
                    # Check API responsiveness if authenticated
                    if self.authenticated:
                        try:
                            about_info = self._make_api_request("GET", "/about", params={
                                "fields": "storageQuota,user"
                            })
                            
                            health_data["api_responsive"] = True
                            health_data["quota_info"] = about_info.get("storageQuota", {})
                            health_data["user_info"] = about_info.get("user", {})
                            
                        except Exception as e:
                            health_data["errors"].append(f"API test failed: {str(e)}")
                            health_data["api_responsive"] = False
                else:
                    health_data["errors"].append("DNS resolution failed for googleapis.com")
            
            # Determine overall health
            if health_data["connectivity"] and health_data["authenticated"] and health_data["api_responsive"]:
                health_data["health"] = "healthy"
            elif health_data["connectivity"] and health_data["authenticated"]:
                health_data["health"] = "degraded" 
            elif health_data["connectivity"]:
                health_data["health"] = "unhealthy"
            else:
                health_data["health"] = "disconnected"
            
            # Update internal state
            self.health_status = health_data["health"]
            self.last_health_check = health_data["last_check"]
            
            result["success"] = True
            result.update(health_data)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def get_status(self, **kwargs):
        """Get detailed status information about Google Drive service."""
        operation = "get_status" 
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            status_info = {
                "service_status": self.service_status,
                "health_status": self.health_status,
                "authenticated": self.authenticated,
                "token_expiry": self.token_expiry,
                "config_dir": self.config_dir,
                "credentials_present": os.path.exists(self.credentials_file),
                "token_present": os.path.exists(self.token_file),
                "mock_mode": self.mock_mode,
                "api_endpoint": self.api_endpoint,
                "last_health_check": self.last_health_check
            }
            
            # Add detailed file system info if authenticated
            if self.authenticated:
                try:
                    files_info = self.list_files(max_results=1, **kwargs)
                    if files_info["success"]:
                        status_info["files_accessible"] = True
                        status_info["sample_file_count"] = len(files_info.get("files", []))
                    else:
                        # If listing files failed, propagate the error
                        if "error" in files_info:
                            raise Exception(files_info["error"])
                    
                except Exception as e:
                    status_info["files_accessible"] = False
                    status_info["file_access_error"] = str(e)
                    # Re-raise to fail the whole operation if it's a critical error
                    raise
            
            result["success"] = True
            result["status"] = status_info
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def get_config(self, **kwargs):
        """Get current configuration."""
        operation = "get_config"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            config_info = {
                "config_dir": self.config_dir,
                "credentials_file": self.credentials_file,
                "token_file": self.token_file,
                "api_endpoint": self.api_endpoint,
                "scopes": self.scopes,
                "mock_mode": self.mock_mode,
                "health_check_interval": self.health_check_interval
            }
            
            # Add credentials info without sensitive data
            if os.path.exists(self.credentials_file):
                try:
                    with open(self.credentials_file, 'r') as f:
                        creds_data = json.load(f)
                    
                    config_info["credentials_configured"] = True
                    if "installed" in creds_data:
                        config_info["client_id_configured"] = bool(creds_data["installed"].get("client_id"))
                except Exception:
                    config_info["credentials_configured"] = False
            
            result["success"] = True
            result["config"] = config_info
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def set_config(self, config_data, **kwargs):
        """Set configuration parameters."""
        operation = "set_config"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            updated_fields = []
            
            # Update configurable parameters
            if "health_check_interval" in config_data:
                self.health_check_interval = int(config_data["health_check_interval"])
                updated_fields.append("health_check_interval")
            
            if "mock_mode" in config_data:
                self.mock_mode = bool(config_data["mock_mode"])
                updated_fields.append("mock_mode")
            
            if "api_endpoint" in config_data:
                self.api_endpoint = str(config_data["api_endpoint"])
                updated_fields.append("api_endpoint")
            
            result["success"] = True
            result["updated_fields"] = updated_fields
            result["message"] = f"Updated {len(updated_fields)} configuration fields"
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    # File Management Methods
    def list_files(self, **kwargs):
        """List files in Google Drive."""
        operation = "list_files"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not self.authenticated:
                raise GDriveAuthenticationError("Not authenticated with Google Drive")
            
            # Build query parameters
            params = {
                "fields": "files(id,name,size,mimeType,createdTime,modifiedTime,parents)",
                "pageSize": kwargs.get("max_results", 100)
            }
            
            if "query" in kwargs:
                params["q"] = kwargs["query"]
            
            if "parent_folder" in kwargs:
                folder_query = f"'{kwargs['parent_folder']}' in parents"
                if "q" in params:
                    params["q"] = f"{params['q']} and {folder_query}"
                else:
                    params["q"] = folder_query
            
            # Make API request
            files_data = self._make_api_request("GET", "/files", params=params)
            
            result["success"] = True
            result["files"] = files_data.get("files", [])
            result["file_count"] = len(result["files"])
            result["next_page_token"] = files_data.get("nextPageToken")
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def get_file_info(self, file_id, **kwargs):
        """Get detailed information about a specific file."""
        operation = "get_file_info"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not self.authenticated:
                raise GDriveAuthenticationError("Not authenticated with Google Drive")
            
            # Get file metadata
            params = {
                "fields": "id,name,size,mimeType,createdTime,modifiedTime,parents,permissions,webViewLink,webContentLink"
            }
            
            file_data = self._make_api_request("GET", f"/files/{file_id}", params=params)
            
            result["success"] = True
            result["file"] = file_data
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def upload_file(self, file_path, **kwargs):
        """Upload a file to Google Drive."""
        operation = "upload_file"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not self.authenticated:
                raise GDriveAuthenticationError("Not authenticated with Google Drive")
            
            if not os.path.exists(file_path):
                raise IPFSValidationError(f"File not found: {file_path}")
            
            # Prepare file metadata
            file_name = kwargs.get("name", os.path.basename(file_path))
            parent_folder = kwargs.get("parent_folder")
            
            metadata = {
                "name": file_name,
                "description": kwargs.get("description", "")
            }
            
            if parent_folder:
                metadata["parents"] = [parent_folder]
            
            # For mock mode, simulate upload
            if self.mock_mode:
                mock_file_id = f"mock_file_{uuid.uuid4().hex[:8]}"
                result["success"] = True
                result["file_id"] = mock_file_id
                result["file_name"] = file_name
                result["file_size"] = os.path.getsize(file_path)
                result["mock"] = True
                return result
            
            # Real upload implementation would require multipart upload
            # This is a simplified version
            import requests
            
            # Get file mime type
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            # Upload metadata first
            metadata_response = self._make_api_request("POST", "/files", data=metadata)
            
            result["success"] = True
            result["file_id"] = metadata_response["id"]
            result["file_name"] = metadata_response["name"]
            result["upload_method"] = "metadata_only"  # Simplified for demo
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def download_file(self, file_id, output_path, **kwargs):
        """Download a file from Google Drive."""
        operation = "download_file"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not self.authenticated:
                raise GDriveAuthenticationError("Not authenticated with Google Drive")
            
            # For mock mode, create a dummy file
            if self.mock_mode:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w') as f:
                    f.write(f"Mock file content for {file_id}")
                
                result["success"] = True
                result["file_id"] = file_id
                result["output_path"] = output_path
                result["file_size"] = os.path.getsize(output_path)
                result["mock"] = True
                return result
            
            # Get file info first
            file_info = self.get_file_info(file_id, **kwargs)
            if not file_info["success"]:
                return file_info
            
            # Download file content
            download_response = self._make_api_request("GET", f"/files/{file_id}", params={"alt": "media"})
            
            # Save to file
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(download_response["content"])
            
            result["success"] = True
            result["file_id"] = file_id
            result["output_path"] = output_path
            result["file_size"] = os.path.getsize(output_path)
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def delete_file(self, file_id, **kwargs):
        """Delete a file from Google Drive."""
        operation = "delete_file"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not self.authenticated:
                raise GDriveAuthenticationError("Not authenticated with Google Drive")
            
            # For mock mode, simulate deletion
            if self.mock_mode:
                result["success"] = True
                result["file_id"] = file_id
                result["message"] = "File deleted (mock mode)"
                result["mock"] = True
                return result
            
            # Delete file
            self._make_api_request("DELETE", f"/files/{file_id}")
            
            result["success"] = True
            result["file_id"] = file_id
            result["message"] = "File deleted successfully"
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    # Additional utility methods for health monitoring integration
    def get_quota_info(self, **kwargs):
        """Get Google Drive quota information for health monitoring."""
        operation = "get_quota_info"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            if not self.authenticated:
                result["quota"] = {"available": False, "reason": "not_authenticated"}
                result["success"] = True
                return result
            
            about_info = self._make_api_request("GET", "/about", params={
                "fields": "storageQuota"
            })
            
            quota = about_info.get("storageQuota", {})
            
            result["success"] = True
            result["quota"] = {
                "limit": int(quota.get("limit", 0)),
                "usage": int(quota.get("usage", 0)),
                "usage_in_drive": int(quota.get("usageInDrive", 0)),
                "available": int(quota.get("limit", 0)) - int(quota.get("usage", 0)),
                "usage_percentage": (int(quota.get("usage", 0)) / int(quota.get("limit", 1))) * 100
            }
            
            return result
            
        except Exception as e:
            return handle_error(result, e)

    def test_connectivity(self, **kwargs):
        """Test connectivity to Google Drive for health monitoring."""
        operation = "test_connectivity"
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict(operation, correlation_id)
        
        try:
            connectivity_tests = {
                "dns_resolution": self._check_dns_resolution("www.googleapis.com"),
                "api_endpoint_reachable": False,
                "authentication_valid": False
            }
            
            # If DNS fails, this is a critical failure
            if not connectivity_tests["dns_resolution"]:
                result["success"] = False
                result["connectivity"] = connectivity_tests
                result["overall_connectivity"] = False
                result["error"] = "DNS resolution failed"
                return result
            
            # Test API endpoint
            if connectivity_tests["dns_resolution"]:
                try:
                    import requests
                    response = requests.head("https://www.googleapis.com/drive/v3/about", timeout=10)
                    connectivity_tests["api_endpoint_reachable"] = response.status_code < 500
                except Exception:
                    connectivity_tests["api_endpoint_reachable"] = False
            
            # Test authentication
            if self.authenticated:
                try:
                    self._make_api_request("GET", "/about", params={"fields": "user"})
                    connectivity_tests["authentication_valid"] = True
                except Exception as e:
                    connectivity_tests["authentication_valid"] = False
                    # If it's a critical error, fail the whole test
                    if isinstance(e, (GDriveConnectionError, socket.timeout)):
                        raise
            
            result["success"] = True
            result["connectivity"] = connectivity_tests
            result["overall_connectivity"] = all(connectivity_tests.values()) if self.authenticated else connectivity_tests["dns_resolution"] and connectivity_tests["api_endpoint_reachable"]
            
            return result
            
        except Exception as e:
            return handle_error(result, e)
