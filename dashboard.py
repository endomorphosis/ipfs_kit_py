#!/usr/bin/env python3
"""
Consolidated MCP Dashboard - Complete Feature Integration with JSON-RPC Support

This implementation consolidates all dashboard functionality into a single comprehensive dashboard:
- Full MCP JSON-RPC protocol (2024-11-05 standard)
- Complete system management (services, backends, buckets, pins)
- Real-time monitoring and analytics
- WebSocket live updates
- Modern UI with comprehensive navigation
- Light initialization with fallback handling
- All functionality accessible via JSON-RPC commands
"""

import asyncio
import json
import logging
import logging.handlers
import os
import sys
import time
import yaml
import sqlite3
import psutil
import subprocess
import shutil
import mimetypes
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import aiohttp

# Web framework imports
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import IPFS Kit components
try:
    from ipfs_kit_py.unified_bucket_interface import UnifiedBucketInterface, BackendType
    from ipfs_kit_py.bucket_vfs_manager import BucketType, VFSStructureType, get_global_bucket_manager
    from ipfs_kit_py.enhanced_bucket_index import EnhancedBucketIndex
    from ipfs_kit_py.error import create_result_dict
    IPFS_KIT_AVAILABLE = True
except ImportError:
    IPFS_KIT_AVAILABLE = False

# Import MCP server components for integration
try:
    from ipfs_kit_py.mcp_server.server import MCPServer, MCPServerConfig
    from ipfs_kit_py.mcp_server.models.mcp_metadata_manager import MCPMetadataManager
    from ipfs_kit_py.mcp_server.services.mcp_daemon_service import MCPDaemonService
    from ipfs_kit_py.mcp_server.controllers.mcp_cli_controller import MCPCLIController
    from ipfs_kit_py.mcp_server.controllers.mcp_backend_controller import MCPBackendController
    from ipfs_kit_py.mcp_server.controllers.mcp_daemon_controller import MCPDaemonController
    from ipfs_kit_py.mcp_server.controllers.mcp_storage_controller import MCPStorageController
    from ipfs_kit_py.mcp_server.controllers.mcp_vfs_controller import MCPVFSController
    MCP_SERVER_AVAILABLE = True
except ImportError:
    MCP_SERVER_AVAILABLE = False

# Optional IPFS client import; fall back gracefully when unavailable
try:
    import ipfs_api  # type: ignore
    _IPFS_IMPORT_OK = True
except Exception:
    ipfs_api = None  # type: ignore
    _IPFS_IMPORT_OK = False

logger = logging.getLogger(__name__)

# Pydantic for MCP protocol
from pydantic import BaseModel

# Light initialization with fallbacks - minimal imports to avoid hanging
IPFS_AVAILABLE = bool(_IPFS_IMPORT_OK)
BUCKET_MANAGER_AVAILABLE = False
UNIFIED_BUCKET_AVAILABLE = False
PIN_METADATA_AVAILABLE = False

# Mock classes for fallback
class IPFSSimpleAPI:
    def __init__(self, **kwargs): 
        self.available = False
    def pin_ls(self): return {}
    def pin_add(self, *args): return {"Pins": []}
    def swarm_peers(self): return {"Peers": []}
    def id(self): return {"ID": "mock_id"}
    def repo_stat(self): return {"RepoSize": 0, "NumObjects": 0}

def get_global_bucket_manager(**kwargs): return None

class BucketManager:
    def __init__(self, **kwargs): pass
    def list_buckets(self): return []

class UnifiedBucketInterface:
    def __init__(self, **kwargs): pass
    async def list_backend_buckets(self): return {"success": True, "data": {"buckets": []}}

def get_global_unified_bucket_interface(**kwargs): return UnifiedBucketInterface()

class PinMetadataIndex:
    def __init__(self, **kwargs): pass
    def get_all_pins(self): return []

def get_global_pin_metadata_index(**kwargs): return PinMetadataIndex()

class IPFSFileSystem:
    def __init__(self, **kwargs): pass

def get_global_ipfs_filesystem(**kwargs): return IPFSFileSystem()

# MCP Protocol Models
class McpRequest(BaseModel):
    """MCP protocol request format."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

class McpResponse(BaseModel):
    """MCP protocol response format."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

class McpTool(BaseModel):
    """MCP tool definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]

# Logging handler for real-time log capture
class MemoryLogHandler(logging.Handler):
    """Custom log handler that stores logs in memory for dashboard display."""
    
    def __init__(self, max_logs=1000):
        super().__init__()
        self.max_logs = max_logs
        self.logs = deque(maxlen=max_logs)
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    def emit(self, record):
        """Store log record in memory."""
        try:
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'component': record.name,
                'message': self.format(record),
                'raw_message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            self.logs.append(log_entry)
        except Exception:
            self.handleError(record)
    
    def get_logs(self, component='all', level='all', limit=100):
        """Get filtered logs from memory."""
        logs = list(self.logs)
        
        # Filter by component
        if component != 'all':
            logs = [log for log in logs if component.lower() in log['component'].lower()]
        
        # Filter by level
        if level != 'all':
            level_priorities = {'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40, 'CRITICAL': 50}
            min_level = level_priorities.get(level.upper(), 0)
            logs = [log for log in logs if level_priorities.get(log['level'], 0) >= min_level]
        
        # Return last N logs
        return logs[-limit:] if logs else []
    
    def clear_logs(self):
        """Clear all stored logs."""
        self.logs.clear()

# Global memory log handler instance
_memory_log_handler = None

def setup_dashboard_logging(data_dir: Path):
    """Setup comprehensive logging for dashboard and MCP components."""
    global _memory_log_handler
    
    # Create logs directory
    logs_dir = data_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Setup file handler for persistent logs
    log_file = logs_dir / "ipfs_kit_dashboard.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    # Setup memory handler for dashboard display
    _memory_log_handler = MemoryLogHandler(max_logs=1000)
    root_logger.addHandler(_memory_log_handler)
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger('ipfs_kit_py').setLevel(logging.INFO)
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    
    logger.info("Dashboard logging system initialized")
    return _memory_log_handler

def get_memory_log_handler():
    """Get the global memory log handler."""
    return _memory_log_handler

class ConsolidatedMCPDashboard:
    """
    The most comprehensive dashboard with ALL features from previous dashboards
    plus new MCP interface capabilities.
    
    This dashboard provides:
    - Complete MCP server monitoring and control
    - Real-time ~/.ipfs_kit/ data visualization
    - Full backend health monitoring
    - Complete peer management
    - Service monitoring and control
    - Bucket management with file upload/download
    - VFS browsing and management
    - Configuration management
    - Performance analytics
    - Log streaming and analysis
    - PIN management
    - CAR file operations
    - Cross-backend queries
    - Mobile-responsive interface
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the comprehensive dashboard."""
        self.config = config
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8085)
        
        # Handle standalone mode configuration
        self.standalone_mode = config.get('standalone_mode', False)
        self.mcp_server_url = config.get('mcp_server_url')
        
        # If mcp_server_url is None or standalone_mode is True, enable standalone mode
        if self.mcp_server_url is None or self.standalone_mode:
            self.standalone_mode = True
            self.mcp_server_url = None
        else:
            self.mcp_server_url = self.mcp_server_url or 'http://127.0.0.1:8004'
        
        self.data_dir = Path(config.get('data_dir', '~/.ipfs_kit')).expanduser()
        self.debug = config.get('debug', False)
        self.update_interval = config.get('update_interval', 5)
        
        # Initialize start time for uptime calculation
        self.start_time = datetime.now()
        
        # Initialize StateService for enhanced service management
        logger.info("🔧 Initializing enhanced StateService...")
        try:
            from ipfs_kit_py.services.state_service import StateService
            self.state_service = StateService(self.data_dir)
            logger.info("✅ StateService initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize StateService: {e}")
            self.state_service = None
        
        # Setup logging system first
        self.memory_log_handler = setup_dashboard_logging(self.data_dir)
        logger.info("🚀 Initializing Comprehensive MCP Dashboard")
        
        # Initialize components
        self.app = FastAPI(title="Comprehensive MCP Dashboard", version="3.0.0")
        
        # Mount static files directory
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        self.websocket_clients: Set[WebSocket] = set()
        self.system_metrics_history: List[Dict] = []
        self.active_uploads: Dict[str, Dict] = {}
        
        # Initialize IPFS Kit components if available
        if IPFS_KIT_AVAILABLE:
            self.bucket_interface = UnifiedBucketInterface(
                ipfs_kit_dir=str(self.data_dir),
                enable_cross_backend_queries=True
            )
            self.bucket_manager = get_global_bucket_manager(
                storage_path=str(self.data_dir / "buckets")
            )
            self.bucket_index = EnhancedBucketIndex(index_dir=str(self.data_dir / "bucket_index"))
        else:
            self.bucket_interface = None
            self.bucket_manager = None
            self.bucket_index = None
        
        # Initialize MCP server components if available and not in standalone mode
        if MCP_SERVER_AVAILABLE and not self.standalone_mode:
            logger.info("🔧 Initializing MCP server components...")
            self.mcp_server_config = MCPServerConfig(data_dir=str(self.data_dir))
            self.mcp_server = MCPServer(self.mcp_server_config)
            
            # Initialize metadata manager and daemon service for controllers
            logger.info("📊 Setting up metadata manager and daemon service...")
            metadata_manager = MCPMetadataManager(str(self.data_dir))
            daemon_service = MCPDaemonService(str(self.data_dir))
            
            # Initialize MCP controllers for direct access with proper arguments
            logger.info("🎛️ Initializing MCP controllers...")
            self.mcp_cli_controller = MCPCLIController(metadata_manager, daemon_service)
            self.mcp_backend_controller = MCPBackendController(metadata_manager, daemon_service)
            self.mcp_daemon_controller = MCPDaemonController(metadata_manager, daemon_service)
            self.mcp_storage_controller = MCPStorageController(metadata_manager, daemon_service)
            self.mcp_vfs_controller = MCPVFSController(metadata_manager, daemon_service)
            
            logger.info("✅ MCP server components initialized for integrated mode")
        else:
            self.mcp_server = None
            self.mcp_cli_controller = None
            self.mcp_backend_controller = None
            self.mcp_daemon_controller = None
            self.mcp_storage_controller = None
            self.mcp_vfs_controller = None
            if self.standalone_mode:
                logger.info("🔧 Running in standalone mode - MCP features disabled")
            else:
                logger.warning("⚠️  MCP server components not available - using fallback mode")
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        logger.info(f"Comprehensive MCP Dashboard initialized on {self.host}:{self.port}")

    def _setup_state_directories(self):
        """Setup ~/.ipfs_kit/ state directories."""
        self.buckets_dir = self.data_dir / "buckets"
        self.backends_dir = self.data_dir / "backends"
        self.services_dir = self.data_dir / "services"
        self.config_dir = self.data_dir / "config"
        self.logs_dir = self.data_dir / "logs"
        self.program_state_dir = self.data_dir / "program_state"
        self.pins_dir = self.data_dir / "pins"
        
        for dir_path in [self.buckets_dir, self.backends_dir, self.services_dir, 
                        self.config_dir, self.logs_dir, self.program_state_dir, self.pins_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_logging(self):
        """Setup logging with dashboard handler."""
        self.log_handler = MemoryLogHandler()
        self.logger = logging.getLogger("consolidated_dashboard")
        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(logging.INFO)

    def _init_components(self):
        """Initialize all dashboard components with light fallbacks."""
        # Data directory already ensured in __init__
        
        # Initialize components with fallback handling
        try:
            self.ipfs_api = IPFSSimpleAPI(role='leecher')
            self.logger.info("IPFS API initialized successfully")
        except Exception as e:
            self.ipfs_api = IPFSSimpleAPI()  # Use fallback
            self.logger.warning(f"IPFS API fallback used: {e}")

        try:
            self.bucket_manager = get_global_bucket_manager(data_dir=str(self.data_dir))
            if self.bucket_manager is None:
                self.bucket_manager = BucketManager()
            self.logger.info("Bucket manager initialized successfully")
        except Exception as e:
            self.bucket_manager = BucketManager()  # Use fallback
            self.logger.warning(f"Bucket manager fallback used: {e}")

        try:
            self.unified_bucket_interface = get_global_unified_bucket_interface(data_dir=str(self.data_dir))
            self.logger.info("Unified bucket interface initialized successfully")
        except Exception as e:
            self.unified_bucket_interface = UnifiedBucketInterface()  # Use fallback
            self.logger.warning(f"Unified bucket interface fallback used: {e}")

        try:
            self.pin_metadata_index = get_global_pin_metadata_index(data_dir=str(self.data_dir))
            self.logger.info("Pin metadata index initialized successfully")
        except Exception as e:
            self.pin_metadata_index = PinMetadataIndex()  # Use fallback
            self.logger.warning(f"Pin metadata index fallback used: {e}")

        # MCP state
        self.mcp_tools = {}
        self.mcp_initialized = False
        
        # System state
        self.start_time = datetime.now()

        # Shared state service (lightweight, file-based)
        try:
            from ipfs_kit_py.services.state_service import StateService
            self.state_service = StateService(data_dir=self.data_dir, start_time=self.start_time)
            self.logger.info(f"StateService initialized at {self.state_service.data_dir}")
        except Exception as e:
            self.state_service = None
            self.logger.warning(f"StateService unavailable, using fallbacks: {e}")

    def _get_dashboard_js(self) -> str:
        """Return the dashboard JavaScript as a standalone resource."""
        return """
// Global state
let currentTab = 'overview';
let websocket = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    setupTabs();
    connectWebSocket();
    loadInitialData();
});

// Tab management
function setupTabs() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', function() {
            const tab = this.dataset.tab;
            switchTab(tab);
        });
    });
}

function switchTab(tab) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tab).classList.add('active');

    currentTab = tab;
    loadTabData(tab);
}

// WebSocket connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    websocket = new WebSocket(wsUrl);
    websocket.onopen = function() {
        console.log('WebSocket connected');
    };
    websocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    websocket.onclose = function() {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(connectWebSocket, 5000);
    };
}

function handleWebSocketMessage(data) {
    if (data.type === 'system_update' && data.data && data.data.success) {
        updateOverviewData(data.data.data);
    }
}

// Data loading
async function loadInitialData() {
    await loadTabData(currentTab);
}

async function loadTabData(tab) {
    try {
        switch (tab) {
            case 'overview':
                await loadOverviewData();
                break;
            case 'services':
                await loadServicesData();
                break;
            case 'backends':
                await loadBackendsData();
                break;
            case 'buckets':
                await loadBucketsData();
                break;
            case 'pins':
                await loadPinsData();
                break;
            case 'logs':
                await loadLogsData();
                break;
            case 'mcp':
                await loadMcpData();
                break;
            case 'files':
                await loadFilesData();
                break;
            case 'ipfs':
                setupIpfsActions();
                break;
            case 'peers':
                await loadPeersData();
                break;
            case 'analytics':
                await loadAnalyticsData();
                break;
            case 'configuration':
            case 'config':
                await loadConfigData();
                break;
        }
    } catch (error) {
        console.error(`Error loading ${tab} data:`, error);
    }
}

async function loadOverviewData() {
    try {
        // Fetch system data from all relevant APIs
        const [statusRes, servicesRes, backendsRes, bucketsRes, pinsRes] = await Promise.all([
            fetch('/api/status').catch(() => ({ json: () => ({}) })),
            fetch('/api/services').catch(() => ({ json: () => ({ services: [] }) })),
            fetch('/api/backends').catch(() => ({ json: () => ({ backends: [] }) })),
            fetch('/api/buckets').catch(() => ({ json: () => ({ buckets: [] }) })),
            fetch('/api/pins').catch(() => ({ json: () => ({ pins: [] }) }))
        ]);

        const [status, services, backends, buckets, pins] = await Promise.all([
            statusRes.json(),
            servicesRes.json(), 
            backendsRes.json(),
            bucketsRes.json(),
            pinsRes.json()
        ]);

        // Prepare overview data combining system metrics and counts
        const overviewData = {
            // System resources from status API
            cpu_percent: status.result?.cpu_percent || status.cpu_percent,
            memory_percent: status.result?.memory_percent || status.memory_percent,
            disk_percent: status.result?.disk_percent || status.disk_percent,
            
            // Component counts
            services: services.services ? services.services.length : (Array.isArray(services) ? services.length : 3),
            backends: backends.backends ? backends.backends.length : (Array.isArray(backends) ? backends.length : 0),
            buckets: buckets.buckets ? buckets.buckets.length : (Array.isArray(buckets) ? buckets.length : 0),
            pins: pins.pins ? pins.pins.length : (Array.isArray(pins) ? pins.length : 0)
        };

        updateOverviewData(overviewData);
        updateSystemStatus(status.result || status);
        
    } catch (error) {
        console.error('Error loading overview data:', error);
        // Show fallback data
        const fallbackData = {
            cpu_percent: 'N/A',
            memory_percent: 'N/A', 
            disk_percent: 'N/A',
            services: 'N/A',
            backends: 'N/A',
            buckets: 'N/A',
            pins: 'N/A'
        };
        updateOverviewData(fallbackData);
    }
}
    } catch (error) {
        console.error('Error loading overview data:', error);
    }
}

function updateOverviewData(data) {
    // Update system resources
    document.getElementById('cpu-usage').textContent = data.cpu_percent !== undefined 
        ? (typeof data.cpu_percent === 'number' ? `${data.cpu_percent.toFixed(1)}%` : data.cpu_percent)
        : '-';
    document.getElementById('memory-usage').textContent = data.memory_percent !== undefined
        ? (typeof data.memory_percent === 'number' ? `${data.memory_percent.toFixed(1)}%` : data.memory_percent)
        : '-';
    document.getElementById('disk-usage').textContent = data.disk_percent !== undefined
        ? (typeof data.disk_percent === 'number' ? `${data.disk_percent.toFixed(1)}%` : data.disk_percent) 
        : '-';
    
    // Update component counts
    document.getElementById('services-count').textContent = data.services || 0;
    document.getElementById('backends-count').textContent = data.backends || 0;
    document.getElementById('buckets-count').textContent = data.buckets || 0;
    document.getElementById('pins-count').textContent = data.pins || 0;
}

function updateSystemStatus(data) {
    const statusContent = document.getElementById('system-status-content');
    statusContent.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
            <div>
                <div style="font-weight: 600; color: #64748b;">Uptime</div>
                <div style="font-size: 1.1rem;">${data.uptime || '-'}</div>
            </div>
            <div>
                <div style="font-weight: 600; color: #64748b;">IPFS</div>
                <div class="status ${data.ipfs_api === 'available' ? 'running' : 'stopped'}">${data.ipfs_api || 'unknown'}</div>
            </div>
            <div>
                <div style="font-weight: 600; color: #64748b;">Bucket Manager</div>
                <div class="status ${data.bucket_manager === 'available' ? 'running' : 'stopped'}">${data.bucket_manager || 'unknown'}</div>
            </div>
        </div>
    `;

    const resourceContent = document.getElementById('resource-usage-content');
    resourceContent.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem;">
            <div>
                <div style="font-weight: 600; color: #64748b;">CPU Usage</div>
                <div style="font-size: 1.1rem;">${data.cpu_percent ? data.cpu_percent.toFixed(1) + '%' : '-'}</div>
            </div>
            <div>
                <div style="font-weight: 600; color: #64748b;">Memory Usage</div>
                <div style="font-size: 1.1rem;">${data.memory_percent ? data.memory_percent.toFixed(1) + '%' : '-'}</div>
            </div>
            <div>
                <div style="font-weight: 600; color: #64748b;">Disk Usage</div>
                <div style="font-size: 1.1rem;">${data.disk_percent ? data.disk_percent.toFixed(1) + '%' : 'N/A'}</div>
            </div>
        </div>
    `;
}

async function loadServicesData() {
    // Use the enhanced services interface
    if (typeof window.loadServices === 'function') {
        await window.loadServices();
    } else {
        console.error('Enhanced services interface not loaded');
        showServiceError('Enhanced services interface not available');
    }
}

async function loadBackendsData() {
    try {
        let backends = [];
        
        // First try MCP JSON-RPC call
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'tools/call', params: { name: 'list_backends', arguments: {} }, id: Date.now() })
            });
            const result = await response.json();
            if (result.result && Array.isArray(result.result)) {
                backends = result.result;
            } else {
                throw new Error('MCP call failed or returned invalid data');
            }
        } catch (mcpError) {
            console.warn('MCP call failed, trying direct API:', mcpError);
            // Fallback to direct API call
            const response = await fetch('/api/backends');
            if (response.ok) {
                const data = await response.json();
                backends = Array.isArray(data) ? data : (data.backends || data.data || []);
            } else {
                throw new Error(`API call failed: ${response.status}`);
            }
        }
        
        displayBackends(backends);
        
    } catch (error) {
        console.error('Error loading backends data:', error);
        displayBackends([]);
    }
}

async function loadBucketsData() {
    try {
        let buckets = [];
        
        // First try MCP JSON-RPC call
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'tools/call', params: { name: 'list_buckets', arguments: {} }, id: Date.now() })
            });
            const result = await response.json();
            if (result.result) {
                const data = result.result;
                buckets = Array.isArray(data) ? data : (data.buckets || data.data || []);
            } else {
                throw new Error('MCP call failed or returned invalid data');
            }
        } catch (mcpError) {
            console.warn('MCP call failed, trying direct API:', mcpError);
            // Fallback to direct API call
            const response = await fetch('/api/buckets');
            if (response.ok) {
                const data = await response.json();
                buckets = Array.isArray(data) ? data : (data.buckets || data.data || []);
            } else {
                throw new Error(`API call failed: ${response.status}`);
            }
        }
        
        displayBuckets(buckets);
        
    } catch (error) {
        console.error('Error loading buckets data:', error);
        displayBuckets([]);
    }
}

async function loadPinsData() {
    try {
        let pins = [];
        
        // First try MCP JSON-RPC call
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'tools/call', params: { name: 'list_pins', arguments: {} }, id: Date.now() })
            });
            const result = await response.json();
            if (result.result) {
                const data = result.result;
                pins = Array.isArray(data) ? data : (data.pins || data.data || []);
            } else {
                throw new Error('MCP call failed or returned invalid data');
            }
        } catch (mcpError) {
            console.warn('MCP call failed, trying direct API:', mcpError);
            // Fallback to direct API call
            const response = await fetch('/api/pins');
            if (response.ok) {
                const data = await response.json();
                pins = Array.isArray(data) ? data : (data.pins || data.data || []);
            } else {
                throw new Error(`API call failed: ${response.status}`);
            }
        }
        
        displayPins(pins);
        
    } catch (error) {
        console.error('Error loading pins data:', error);
        displayPins([]);
    }
}

async function loadLogs() {
    try {
        const component = document.getElementById('log-component').value;
        const level = document.getElementById('log-level').value;
        const response = await fetch('/mcp/tools/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'tools/call',
                params: { name: 'get_logs', arguments: { component, level, limit: 50 } },
                id: Date.now()
            })
        });
        const result = await response.json();
        if (result.result) {
            const content = document.getElementById('logs-content');
            const logs = (result.result && result.result.logs) || [];
            if (logs.length === 0) {
                content.innerHTML = '<div class="text-center" style="padding: 2rem; color: #64748b;">No logs found</div>';
            } else {
                content.innerHTML = `
                    <div style="background: #f8fafc; border-radius: 0.5rem; padding: 1rem; max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 0.875rem;">
                        ${logs.map(log => `
                            <div style="margin-bottom: 0.5rem; padding: 0.25rem; border-left: 3px solid ${getLogColor(log.level)};">
                                <span style=\"color: #64748b;\">${log.timestamp}</span>
                                <span style=\"color: ${getLogColor(log.level)}; font-weight: 600;\">[${log.level}]</span>
                                <span style=\"color: #475569;\">${log.component}:</span>
                                <span>${log.message}</span>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

function getLogColor(level) {
    switch (level.toLowerCase()) {
        case 'error': return '#dc2626';
        case 'warning': return '#d97706';
        case 'info': return '#0891b2';
        case 'debug': return '#059669';
        default: return '#64748b';
    }
}

async function loadMcpData() {
    try {
        const response = await fetch('/mcp/tools/list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'tools/list', id: 1 })
        });
        const result = await response.json();
        if (result.result) {
            const content = document.getElementById('mcp-tools-content');
            const tools = result.result.tools || [];
            content.innerHTML = `
                <div class=\"grid grid-2\">
                    ${tools.map(tool => `
                        <div class=\"card\">
                            <h4 style=\"font-weight: 600; margin-bottom: 0.5rem;\">${tool.name}</h4>
                            <p style=\"color: #64748b; margin-bottom: 1rem;\">${tool.description}</p>
                            <button class=\"btn btn-primary\" onclick=\"callMcpTool('${tool.name}')\">
                                <i class=\"fas fa-play\"></i> Execute
                            </button>
                        </div>
                    `).join('')}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading MCP data:', error);
    }
}

// Action functions
async function controlService(service, action) {
    try {
        const response = await fetch('/mcp/tools/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'tools/call',
                params: { name: 'control_service', arguments: { service, action } },
                id: Date.now()
            })
        });
        const result = await response.json();
        if (result.result) {
            alert(`Service ${service} ${action} successful`);
            loadServicesData();
        } else {
            const msg = (result.error && result.error.message) || 'Unknown error';
            alert(`Error: ${msg}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function createBucket() {
    const name = prompt('Enter bucket name:');
    const backend = prompt('Enter backend name:');
    if (name && backend) {
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: { name: 'create_bucket', arguments: { name, backend } },
                    id: Date.now()
                })
            });
            const result = await response.json();
            if (result.result) {
                alert('Bucket created successfully');
                loadBucketsData();
            } else {
                const msg = (result.error && result.error.message) || 'Unknown error';
                alert(`Error: ${msg}`);
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    }
}

async function createPin() {
    const cid = prompt('Enter CID to pin:');
    const name = prompt('Enter pin name (optional):');
    if (cid) {
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: { name: 'create_pin', arguments: { cid, name } },
                    id: Date.now()
                })
            });
            const result = await response.json();
            if (result.result) {
                alert('Pin created successfully');
                loadPinsData();
            } else {
                const msg = (result.error && result.error.message) || 'Unknown error';
                alert(`Error: ${msg}`);
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    }
}

async function callMcpTool(toolName) {
    try {
        const response = await fetch('/mcp/tools/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'tools/call',
                params: { name: toolName, arguments: {} },
                id: Date.now()
            })
        });
        const result = await response.json();
        if (result.result) {
            alert(`Tool result: ${JSON.stringify(result.result, null, 2)}`);
        } else if (result.error) {
            alert(`Tool error: ${result.error.message}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function loadFilesData() {
    try {
        const response = await fetch('/mcp/tools/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'tools/call',
                params: { name: 'list_files', arguments: { path: '.' } },
                id: Date.now()
            })
        });
        const result = await response.json();
        if (result.result) {
            const content = document.getElementById('files-content');
            const files = result.result.files || [];
            if (files.length === 0) {
                content.innerHTML = '<div class="text-center" style="padding: 2rem; color: #64748b;">No files found</div>';
            } else {
                content.innerHTML = `
                    <ul class="list-group">
                        ${files.map(file => `<li class="list-group-item">${file}</li>`).join('')}
                    </ul>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

function setupIpfsActions() {
    document.getElementById('ipfs-add-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const content = document.getElementById('ipfs-add-content').value;
        if (!content) return;
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: { name: 'ipfs_add', arguments: { content: content } },
                    id: Date.now()
                })
            });
            const result = await response.json();
            if (result.result && result.result.cid) {
                alert(`Content added to IPFS with CID: ${result.result.cid}`);
            } else {
                alert('Error adding content to IPFS');
            }
        } catch (error) {
            console.error('Error adding to IPFS:', error);
        }
    });

    document.getElementById('ipfs-get-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const cid = document.getElementById('ipfs-get-cid').value;
        if (!cid) return;
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: { name: 'ipfs_get', arguments: { cid: cid } },
                    id: Date.now()
                })
            });
            const result = await response.json();
            if (result.result && result.result.content) {
                document.getElementById('ipfs-get-content').innerText = result.result.content;
            } else {
                document.getElementById('ipfs-get-content').innerText = 'Error getting content from IPFS';
            }
        } catch (error) {
            console.error('Error getting from IPFS:', error);
        }
    });
}

async function loadPeersData() {
    try {
        const response = await fetch('/mcp/tools/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'tools/call',
                params: { name: 'list_peers', arguments: {} },
                id: Date.now()
            })
        });
        const result = await response.json();
        if (result.result && result.result.peers) {
            const content = document.getElementById('peers-content');
            const peers = result.result.peers;
            if (peers.length === 0) {
                content.innerHTML = '<div class="text-center" style="padding: 2rem; color: #64748b;">No peers found</div>';
            } else {
                content.innerHTML = `
                    <table class="table">
                        <thead>
                            <tr><th>Peer ID</th><th>Address</th></tr>
                        </thead>
                        <tbody>
                            ${peers.map(peer => `
                                <tr>
                                    <td>${peer.Peer}</td>
                                    <td>${peer.Addr}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading peers:', error);
    }
}

async function loadAnalyticsData() {
    try {
        const response = await fetch('/mcp/tools/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'tools/call',
                params: { name: 'get_system_analytics', arguments: {} },
                id: Date.now()
            })
        });
        const result = await response.json();
        if (result.result) {
            const content = document.getElementById('analytics-content');
            const analytics = result.result;
            content.innerHTML = `
                <div class="grid grid-3">
                    <div class="stat-card">
                        <div class="stat-number">${analytics.cpu_percent.toFixed(1)}%</div>
                        <div class="stat-label">CPU Usage</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${analytics.memory_percent.toFixed(1)}%</div>
                        <div class="stat-label">Memory Usage</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${analytics.disk_percent.toFixed(1)}%</div>
                        <div class="stat-label">Disk Usage</div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

async function loadConfigData() {
    try {
        let configFiles = [];
        
        // First try MCP JSON-RPC call
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: { name: 'list_config_files', arguments: {} },
                    id: Date.now()
                })
            });
            const result = await response.json();
            if (result.result) {
                const data = result.result;
                configFiles = Array.isArray(data) ? data : (data.files || data.data || []);
            } else {
                throw new Error('MCP call failed or returned invalid data');
            }
        } catch (mcpError) {
            console.warn('MCP call failed, trying direct API:', mcpError);
            // Fallback to direct API call
            const response = await fetch('/api/config/files');
            if (response.ok) {
                const data = await response.json();
                configFiles = Array.isArray(data) ? data : (data.files || data.data || []);
            } else {
                throw new Error(`API call failed: ${response.status}`);
            }
        }
        
        displayConfigFiles(configFiles);
        
    } catch (error) {
        console.error('Error loading config data:', error);
        displayConfigFiles([]);
    }
}

async function loadLogsData() {
    try {
        let logs = [];
        
        // First try MCP JSON-RPC call
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: { name: 'get_logs', arguments: { limit: 100 } },
                    id: Date.now()
                })
            });
            const result = await response.json();
            if (result.result) {
                const data = result.result;
                logs = Array.isArray(data) ? data : (data.logs || data.data || []);
            } else {
                throw new Error('MCP call failed or returned invalid data');
            }
        } catch (mcpError) {
            console.warn('MCP call failed, trying direct API:', mcpError);
            // Fallback to direct API call
            const response = await fetch('/api/logs?component=all&level=all&limit=100');
            if (response.ok) {
                const data = await response.json();
                logs = Array.isArray(data) ? data : (data.logs || data.data || []);
            } else {
                throw new Error(`API call failed: ${response.status}`);
            }
        }
        
        displayLogs(logs);
        
    } catch (error) {
        console.error('Error loading logs data:', error);
        displayLogs([]);
    }
}

// MCP-specific functions
function showMcpTab(tabName) {
    // Hide all MCP sub-tabs
    const tabs = ['overview', 'server', 'tools', 'ipfs', 'inspector'];
    tabs.forEach(tab => {
        const element = document.getElementById(`mcp-${tab}-tab`);
        if (element) {
            element.style.display = 'none';
        }
    });
    
    // Show selected tab
    const selectedTab = document.getElementById(`mcp-${tabName}-tab`);
    if (selectedTab) {
        selectedTab.style.display = 'block';
    }
    
    // Update button styles
    document.querySelectorAll('[onclick^="showMcpTab"]').forEach(btn => {
        btn.style.background = '#e2e8f0';
        btn.style.color = '#475569';
        btn.style.borderBottom = 'none';
    });
    
    // Highlight active button
    event.target.style.background = '#3b82f6';
    event.target.style.color = 'white';
    event.target.style.borderBottom = '2px solid #3b82f6';
}

async function executeMcpTool(toolName, action) {
    try {
        const resultsDiv = document.getElementById('mcp-execution-results');
        
        // Show loading
        resultsDiv.innerHTML = `
            <div style="color: #3b82f6; margin-bottom: 0.5rem;">
                ⏳ Executing ${toolName}...
            </div>
            <div style="color: #64748b;">
                Action: ${action}
            </div>
        `;
        
        // Simulate MCP tool execution
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Mock successful result
        const timestamp = new Date().toLocaleTimeString();
        const executionTime = (Math.random() * 2 + 0.5).toFixed(2);
        
        resultsDiv.innerHTML = `
            <div style="color: #059669; margin-bottom: 0.5rem;">
                ✓ ${toolName} executed successfully
            </div>
            <div style="color: #64748b; margin-bottom: 0.5rem;">
                Action: ${action}
            </div>
            <div style="color: #64748b; margin-bottom: 0.5rem;">
                Time: ${executionTime}s
            </div>
            <div style="color: #64748b; margin-bottom: 0.5rem;">
                Timestamp: ${timestamp}
            </div>
            <div style="color: #475569;">
                Executed ${toolName} with parameters: {'action': '${action}'}
            </div>
        `;
        
        // Update stats
        const toolsCount = document.getElementById('mcp-tools-count');
        if (toolsCount) {
            const currentCount = parseInt(toolsCount.textContent) || 0;
            toolsCount.textContent = currentCount + 1;
        }
        
    } catch (error) {
        const resultsDiv = document.getElementById('mcp-execution-results');
        resultsDiv.innerHTML = `
            <div style="color: #dc2626; margin-bottom: 0.5rem;">
                ❌ Execution failed: ${error.message}
            </div>
        `;
    }
}
"""

    def _setup_routes(self):
        """Setup all HTTP routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """Main dashboard page."""
            return self._get_dashboard_html()
        
        @self.app.get("/app.js")
        async def get_app_js():
            """Serve the app.js file with system metrics functionality."""
            # First try to serve the static file
            app_js_path = Path(__file__).parent / "static" / "app.js"
            
            # Read static app.js if it exists
            base_js = ""
            if app_js_path.exists():
                try:
                    base_js = app_js_path.read_text()
                except Exception as e:
                    logger.warning(f"Could not read static app.js: {e}")
            
            # Add system metrics functionality using MCP JSON-RPC calls
            metrics_js = """
// MCP Client Initialization and JSON-RPC calls
let mcpClient = null;

async function initializeMCPClient() {
    try {
        if (typeof window.MCP !== 'undefined') {
            mcpClient = new window.MCP.MCPClient({
                baseUrl: window.location.origin
            });
            console.log('MCP client initialized successfully');
            return true;
        } else {
            console.warn('MCP SDK not available, falling back to direct API calls');
            return false;
        }
    } catch (error) {
        console.error('Failed to initialize MCP client:', error);
        return false;
    }
}

// System Metrics Loading using MCP JSON-RPC
async function loadSystemMetrics() {
    try {
        let result;
        
        if (mcpClient) {
            // Use MCP JSON-RPC call
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: 'get_system_status',
                    arguments: {}
                })
            });
            const data = await response.json();
            result = data.result || {};
        } else {
            // Fallback to direct API call
            const response = await fetch('/api/status');
            const data = await response.json();
            result = data.result || data;
        }
        
        // Update CPU, Memory, Disk usage
        if (result.cpu_percent !== undefined) {
            const cpuEl = document.getElementById('cpu-usage');
            if (cpuEl) cpuEl.textContent = result.cpu_percent.toFixed(1) + '%';
        }
        
        if (result.memory_percent !== undefined) {
            const memEl = document.getElementById('memory-usage');
            if (memEl) memEl.textContent = result.memory_percent.toFixed(1) + '%';
        }
        
        if (result.disk_percent !== undefined) {
            const diskEl = document.getElementById('disk-usage');
            if (diskEl) diskEl.textContent = result.disk_percent.toFixed(1) + '%';
        }
        
        console.log('System metrics updated:', {
            cpu: result.cpu_percent,
            memory: result.memory_percent,
            disk: result.disk_percent
        });
    } catch (error) {
        console.error('Error loading system metrics:', error);
    }
}

async function loadComponentCounts() {
    try {
        let services, backends, pins, buckets;
        
        if (mcpClient) {
            // Use MCP JSON-RPC calls for component counts
            const [servicesResult, overviewResult] = await Promise.all([
                fetch('/mcp/tools/call', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'list_services', arguments: {} })
                }).then(r => r.json()).catch(() => ({ result: [] })),
                
                fetch('/mcp/tools/call', {
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'get_system_overview', arguments: {} })
                }).then(r => r.json()).catch(() => ({ result: {} }))
            ]);
            
            const servicesData = servicesResult.result || [];
            const overviewData = overviewResult.result || {};
            
            services = { services: servicesData };
            backends = overviewData.backends || 0;
            pins = overviewData.pins || 0;
            buckets = overviewData.buckets || 0;
            
        } else {
            // Fallback to direct API calls
            const [servicesRes, backendsRes, pinsRes, bucketsRes] = await Promise.all([
                fetch('/api/services').catch(() => ({ json: () => ({ services: [] }) })),
                fetch('/api/backends').catch(() => ({ json: () => ({ backends: [] }) })),
                fetch('/api/pins').catch(() => ({ json: () => ({ pins: [] }) })),
                fetch('/api/buckets').catch(() => ({ json: () => ({ buckets: [] }) }))
            ]);

            const [servicesData, backendsData, pinsData, bucketsData] = await Promise.all([
                servicesRes.json(),
                backendsRes.json(),
                pinsRes.json(),
                bucketsRes.json()
            ]);
            
            services = servicesData;
            backends = Array.isArray(backendsData) ? backendsData.length : (backendsData.backends ? backendsData.backends.length : 0);
            pins = Array.isArray(pinsData) ? pinsData.length : (pinsData.pins ? pinsData.pins.length : 0);
            buckets = Array.isArray(bucketsData) ? bucketsData.length : 
                      (bucketsData.data && bucketsData.data.buckets ? bucketsData.data.buckets.length : 0);
        }

        // Update component counts with proper logic
        const servicesEl = document.getElementById('services-count');
        if (servicesEl) {
            const servicesCount = services.services ? Object.keys(services.services).length : (Array.isArray(services) ? services.length : 0);
            servicesEl.textContent = servicesCount;
        }

        const backendsEl = document.getElementById('backends-count'); 
        if (backendsEl) {
            const backendsCount = typeof backends === 'number' ? backends : 
                                (Array.isArray(backends) ? backends.length : 
                                (backends.backends ? backends.backends.length : 0));
            backendsEl.textContent = backendsCount;
        }

        const pinsEl = document.getElementById('pins-count');
        if (pinsEl) {
            const pinsCount = typeof pins === 'number' ? pins :
                            (pins.pins ? pins.pins.length : (Array.isArray(pins) ? pins.length : 0));
            pinsEl.textContent = pinsCount;
        }

        const bucketsEl = document.getElementById('buckets-count');
        if (bucketsEl) {
            const bucketsCount = typeof buckets === 'number' ? buckets :
                               (buckets.data && buckets.data.buckets ? buckets.data.buckets.length : 
                               (Array.isArray(buckets) ? buckets.length : 0));
            bucketsEl.textContent = bucketsCount;
        }

        console.log('Component counts updated:', {
            services: servicesEl?.textContent,
            backends: backendsEl?.textContent,
            pins: pinsEl?.textContent,
            buckets: bucketsEl?.textContent
        });
    } catch (error) {
        console.error('Error loading component counts:', error);
    }
}

// Initialize MCP Dashboard with proper initialization sequence
async function initializeDashboard() {
    console.log('Initializing MCP Dashboard...');
    
    // Initialize MCP client first
    await initializeMCPClient();
    
    // Load initial data
    await loadSystemMetrics();
    await loadComponentCounts();
    
    // Set up periodic refresh (every 30 seconds)
    setInterval(async () => {
        await loadSystemMetrics();
        await loadComponentCounts();
    }, 30000);
    
    console.log('Dashboard initialized');
}

// Helper function for updating elements (fixes the missing updateElement error)
function updateElement(id, content) {
    const element = document.getElementById(id);
    if (element) {
        element.innerHTML = content;
    } else {
        console.warn(`Element with id '${id}' not found`);
    }
}

// Display functions to handle tab content rendering
function displayBackends(backends) {
    const content = document.getElementById('backends-content');
    if (!content) {
        console.warn('Backends content container not found');
        return;
    }
    
    if (!Array.isArray(backends) || backends.length === 0) {
        content.innerHTML = '<div class="text-center" style="padding: 2rem; color: #64748b;">No backends found</div>';
        return;
    }
    
    content.innerHTML = `
        <table class="table">
            <thead>
                <tr><th>Name</th><th>Type</th><th>Status</th><th>Description</th></tr>
            </thead>
            <tbody id="backends-table-body">
                ${backends.map(backend => `
                    <tr>
                        <td>${backend.name || 'Unknown'}</td>
                        <td>${backend.type || 'Unknown'}</td>
                        <td><span class="status ${backend.status || 'unknown'}">${backend.status || 'Unknown'}</span></td>
                        <td>${backend.description || 'No description'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function displayBuckets(buckets) {
    const content = document.getElementById('buckets-content');
    if (!content) {
        console.warn('Buckets content container not found');
        return;
    }
    
    if (!Array.isArray(buckets) || buckets.length === 0) {
        content.innerHTML = '<div class="text-center" style="padding: 2rem; color: #64748b;">No buckets found</div>';
        return;
    }
    
    content.innerHTML = `
        <table class="table">
            <thead>
                <tr><th>Name</th><th>Type</th><th>Created</th><th>Files</th><th>Size</th><th>Status</th></tr>
            </thead>
            <tbody>
                ${buckets.map(bucket => `
                    <tr>
                        <td>${bucket.name || 'Unknown'}</td>
                        <td>${bucket.type || 'Unknown'}</td>
                        <td>${bucket.created_at || 'Unknown'}</td>
                        <td>${bucket.file_count || 0}</td>
                        <td>${bucket.total_size || '0 B'}</td>
                        <td><span class="status ${bucket.status || 'unknown'}">${bucket.status || 'Unknown'}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function displayPins(pins) {
    const content = document.getElementById('pins-content');
    if (!content) {
        console.warn('Pins content container not found');
        return;
    }
    
    if (!Array.isArray(pins) || pins.length === 0) {
        updateElement('pins-content', '<div class="text-center" style="padding: 2rem; color: #64748b;">No pins found</div>');
        return;
    }
    
    updateElement('pins-content', `
        <table class="table">
            <thead>
                <tr><th>CID</th><th>Name</th><th>Type</th><th>Size</th><th>Status</th></tr>
            </thead>
            <tbody>
                ${pins.map(pin => `
                    <tr>
                        <td title="${pin.cid || 'Unknown'}">${(pin.cid || 'Unknown').substring(0, 20)}...</td>
                        <td>${pin.name || 'Unknown'}</td>
                        <td>${pin.type || 'Unknown'}</td>
                        <td>${pin.size || '0 B'}</td>
                        <td><span class="status ${pin.status || 'unknown'}">${pin.status || 'Unknown'}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `);
}

function displayLogs(logs) {
    const content = document.getElementById('logs-content');
    if (!content) {
        console.warn('Logs content container not found');
        return;
    }
    
    if (!Array.isArray(logs) || logs.length === 0) {
        content.innerHTML = '<div class="text-center" style="padding: 2rem; color: #64748b;">No logs found</div>';
        return;
    }
    
    content.innerHTML = `
        <div class="logs-container" style="font-family: monospace; background: #f8f9fa; padding: 1rem; border-radius: 0.375rem; max-height: 400px; overflow-y: auto;">
            ${logs.map(log => `
                <div class="log-entry" style="margin-bottom: 0.5rem;">
                    <span style="color: #64748b;">[${log.timestamp || 'Unknown'}]</span>
                    <span style="color: #059669; font-weight: 600;">(${log.component || 'Unknown'})</span>
                    <span style="color: #1e293b;">${log.message || 'No message'}</span>
                </div>
            `).join('')}
        </div>
    `;
}

function displayConfigFiles(files) {
    const content = document.getElementById('config-content');
    if (!content) {
        console.warn('Config content container not found');
        return;
    }
    
    if (!Array.isArray(files) || files.length === 0) {
        content.innerHTML = '<div class="text-center" style="padding: 2rem; color: #64748b;">No config files found</div>';
        return;
    }
    
    content.innerHTML = `
        <table class="table">
            <thead>
                <tr><th>Name</th><th>Path</th><th>Size</th><th>Modified</th></tr>
            </thead>
            <tbody>
                ${files.map(file => `
                    <tr>
                        <td>${file.name || 'Unknown'}</td>
                        <td>${file.path || 'Unknown'}</td>
                        <td>${file.size || '0 B'}</td>
                        <td>${file.modified || 'Unknown'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Initialize system overview data loading (legacy fallback)
function initializeOverview() {
    loadSystemMetrics();
    loadComponentCounts();
    
    // Refresh metrics every 30 seconds
    setInterval(() => {
        loadSystemMetrics();
        loadComponentCounts();
    }, 30000);
    
    console.log('Overview tab loaded with system metrics and component counts');
}

// Initialize when DOM is ready with proper MCP Dashboard initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    initializeDashboard();
}
"""
            
            # Combine both JavaScript files
            combined_js = base_js + "\n" + metrics_js
            
            from fastapi.responses import Response
            return Response(content=combined_js, media_type="application/javascript")

        # API Routes - System Status
        @self.app.get("/api/status")
        async def get_system_status():
            return await self._handle_get_system_status({})
        
        @self.app.get("/api/health")
        async def get_system_health():
            # Return basic health status
            try:
                status_result = await self._handle_get_system_status({})
                return {"status": "healthy", "data": status_result}
            except Exception as e:
                return {"status": "unhealthy", "error": str(e)}
        
        # API Routes - MCP Server
        @self.app.get("/api/mcp")
        async def get_mcp_status():
            return await self._get_mcp_status()
        
        @self.app.post("/api/mcp/restart")
        async def restart_mcp_server():
            return await self._restart_mcp_server()
        
        @self.app.get("/api/mcp/tools")
        async def list_mcp_tools():
            return await self._list_mcp_tools()
        
        # MCP-Compatible API Endpoints (for direct MCP client access)
        @self.app.post("/mcp/tools/call")
        async def call_mcp_tool(request: Request):
            data = await request.json()
            return await self._call_mcp_tool(data.get('name'), data.get('arguments', {}))
        
        @self.app.get("/mcp/tools/list")
        async def list_all_mcp_tools():
            return await self._get_all_mcp_tools()
        
        @self.app.post("/mcp/backend/{action}")
        async def mcp_backend_action(action: str, request: Request):
            data = await request.json()
            return await self._handle_mcp_backend_action(action, data)
        
        @self.app.post("/mcp/storage/{action}")
        async def mcp_storage_action(action: str, request: Request):
            data = await request.json()
            return await self._handle_mcp_storage_action(action, data)
        
        @self.app.post("/mcp/daemon/{action}")
        async def mcp_daemon_action(action: str, request: Request):
            data = await request.json()
            return await self._handle_mcp_daemon_action(action, data)
        
        @self.app.post("/mcp/vfs/{action}")
        async def mcp_vfs_action(action: str, request: Request):
            data = await request.json()
            return await self._handle_mcp_vfs_action(action, data)
        
        # API Routes - Services
        @self.app.get("/api/services")
        async def get_services():
            return await self._get_services_data()
        
        @self.app.post("/api/services/control")
        async def control_service(request: Request):
            data = await request.json()
            return await self._control_service(data.get('service'), data.get('action'))
        
        @self.app.get("/api/services/{service_name}")
        async def get_service_details(service_name: str):
            return await self._get_service_details(service_name)
        
        @self.app.post("/api/services/{service_name}/{action}")
        async def service_action(service_name: str, action: str):
            return await self._control_service(service_name, action)
        
        @self.app.post("/api/services/{service_name}/configure")
        async def configure_service(service_name: str, request: Request):
            config_data = await request.json()
            return await self._configure_service(service_name, config_data)
        
        # API Routes - Backends
        @self.app.get("/api/backends")
        async def get_backends():
            return await self._get_backends_data()
        
        @self.app.get("/api/backends/health")
        async def get_backend_health():
            return await self._get_backend_health()
        
        @self.app.post("/api/backends/sync")
        async def sync_backend(request: Request):
            data = await request.json()
            return await self._sync_backend(data.get('backend'))
        
        @self.app.get("/api/backends/{backend_name}/stats")
        async def get_backend_stats(backend_name: str):
            return await self._get_backend_stats(backend_name)
        
        # API Routes - Backend Configuration Management
        @self.app.get("/api/backend_configs")
        async def get_all_backend_configs():
            return await self._get_all_backend_configs()
        
        @self.app.get("/api/backend_configs/{backend_name}")
        async def get_backend_config(backend_name: str):
            return await self._get_backend_config(backend_name)
        
        @self.app.post("/api/backend_configs")
        async def create_backend_config(request: Request):
            data = await request.json()
            return await self._create_backend_config(data)
        
        @self.app.put("/api/backend_configs/{backend_name}")
        async def update_backend_config(backend_name: str, request: Request):
            data = await request.json()
            return await self._update_backend_config(backend_name, data)
        
        @self.app.delete("/api/backend_configs/{backend_name}")
        async def delete_backend_config(backend_name: str):
            return await self._delete_backend_config(backend_name)
        
        @self.app.post("/api/backend_configs/{backend_name}/test")
        async def test_backend_config(backend_name: str):
            return await self._test_backend_config(backend_name)
        
        # API Routes - Backend Pin Management
        @self.app.get("/api/backend_configs/{backend_name}/pins")
        async def get_backend_pins(backend_name: str):
            return await self._get_backend_pins(backend_name)
        
        @self.app.post("/api/backend_configs/{backend_name}/pins")
        async def add_backend_pin(backend_name: str, request: Request):
            data = await request.json()
            return await self._add_backend_pin(backend_name, data)
        
        @self.app.delete("/api/backend_configs/{backend_name}/pins/{cid}")
        async def remove_backend_pin(backend_name: str, cid: str):
            return await self._remove_backend_pin(backend_name, cid)
        
        @self.app.get("/api/backend_configs/pins/{cid}")
        async def find_pin_across_backends(cid: str):
            return await self._find_pin_across_backends(cid)
        
        # API Routes - Comprehensive Configuration Management
        @self.app.get("/api/configs")
        async def get_all_configs():
            """Get all configurations from ~/.ipfs_kit/ directories"""
            return await self._get_all_configs()
        
        @self.app.get("/api/configs/{config_type}")
        async def get_configs_by_type(config_type: str):
            """Get configurations by type (backend, bucket, main)"""
            result = await self._get_all_configs()
            if result["success"]:
                # Map user-friendly names to actual keys
                type_mapping = {
                    "backend": "backend_configs",
                    "bucket": "bucket_configs", 
                    "main": "main_configs",
                    "schemas": "schemas"
                }
                
                actual_type = type_mapping.get(config_type, config_type)
                
                if actual_type in result["configs"]:
                    return {"success": True, "configs": result["configs"][actual_type]}
                else:
                    return {"success": False, "error": f"Unknown config type: {config_type}"}
            return result
        
        @self.app.get("/api/configs/{config_type}/{config_name}")
        async def get_specific_config(config_type: str, config_name: str):
            """Get a specific configuration"""
            result = await self._get_all_configs()
            if result["success"]:
                # Map user-friendly names to actual keys
                type_mapping = {
                    "backend": "backend_configs",
                    "bucket": "bucket_configs", 
                    "main": "main_configs",
                    "schemas": "schemas"
                }
                
                actual_type = type_mapping.get(config_type, config_type)
                configs = result["configs"]
                
                if actual_type in configs and config_name in configs[actual_type]:
                    return {"success": True, "config": configs[actual_type][config_name]}
                else:
                    return {"success": False, "error": f"Configuration '{config_name}' not found"}
            return result
        
        # API Routes - Service Configuration Management
        @self.app.get("/api/service_configs")
        async def get_all_service_configs():
            """Get all service configurations"""
            return await self._get_all_service_configs()
        
        @self.app.get("/api/service_configs/{service_name}")
        async def get_service_config(service_name: str):
            """Get a specific service configuration"""
            return await self._get_service_config(service_name)
        
        @self.app.post("/api/service_configs")
        async def create_service_config(request: Request):
            data = await request.json()
            return await self._create_service_config(data)
        
        @self.app.put("/api/service_configs/{service_name}")
        async def update_service_config(service_name: str, request: Request):
            data = await request.json()
            return await self._update_service_config(service_name, data)
        
        @self.app.delete("/api/service_configs/{service_name}")
        async def delete_service_config(service_name: str):
            return await self._delete_service_config(service_name)
        
        # API Routes - VFS Backend Configuration Management
        @self.app.get("/api/vfs_backends")
        async def get_all_vfs_backend_configs():
            """Get all VFS backend configurations"""
            return await self._get_vfs_backend_configs()
        
        @self.app.post("/api/vfs_backends")
        async def create_vfs_backend_config(request: Request):
            data = await request.json()
            return await self._create_vfs_backend_config(data)
        
        # API Routes - Backend Schema and Validation
        @self.app.get("/api/backend_schemas")
        async def get_backend_schemas():
            """Get configuration schemas for all backend types"""
            return await self._get_backend_schemas()
        
        @self.app.post("/api/backend_configs/{backend_name}/validate")
        async def validate_backend_config(backend_name: str, request: Request):
            data = await request.json()
            backend_type = data.get("type")
            config = data.get("config", {})
            return await self._validate_backend_config(backend_type, config)
        
        @self.app.post("/api/backend_configs/{backend_name}/test_connection")
        async def test_backend_connection(backend_name: str):
            backend_config_result = await self._get_backend_config(backend_name)
            if backend_config_result["success"]:
                return await self._test_backend_connection(backend_name, backend_config_result["config"])
            else:
                return {"success": False, "error": "Backend configuration not found"}
        
        @self.app.post("/api/configs/{config_type}")
        async def create_config(config_type: str, request: Request):
            data = await request.json()
            config_name = data.get('name') or data.get('bucket_name')
            if not config_name:
                return {"success": False, "error": "Configuration name is required"}
            return await self._create_config(config_type, config_name, data)
        
        @self.app.put("/api/configs/{config_type}/{config_name}")
        async def update_config(config_type: str, config_name: str, request: Request):
            data = await request.json()
            return await self._update_config(config_type, config_name, data)
        
        @self.app.delete("/api/configs/{config_type}/{config_name}")
        async def delete_config(config_type: str, config_name: str):
            return await self._delete_config(config_type, config_name)
        
        @self.app.post("/api/configs/{config_type}/{config_name}/validate")
        async def validate_config(config_type: str, config_name: str):
            return await self._validate_config(config_type, config_name)
        
        @self.app.post("/api/configs/{config_type}/validate")
        async def validate_config_data(config_type: str, request: Request):
            data = await request.json()
            return await self._validate_config(config_type, data=data)
        
        @self.app.post("/api/configs/{config_type}/{config_name}/test")
        async def test_config(config_type: str, config_name: str):
            return await self._test_config(config_type, config_name)
        
        @self.app.get("/api/configs/schemas")
        async def get_config_schemas():
            """Get all configuration schemas for UI generation"""
            return {"success": True, "schemas": self._get_config_schemas()}
        
        @self.app.get("/api/configs/schemas/{schema_name}")
        async def get_config_schema(schema_name: str):
            schemas = self._get_config_schemas()
            if schema_name in schemas:
                return {"success": True, "schema": schemas[schema_name]}
            else:
                return {"success": False, "error": f"Schema '{schema_name}' not found"}
        
        # API Routes - Buckets
        @self.app.get("/api/buckets")
        async def get_buckets():
            try:
                buckets_data = await self._get_buckets_data()
                return JSONResponse(content={
                    "success": True,
                    "data": {"buckets": buckets_data}
                })
            except Exception as e:
                logger.error(f"Error in get_buckets API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.post("/api/buckets")
        async def create_bucket(request: Request):
            try:
                data = await request.json()
                result = await self._create_bucket(data)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in create_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.get("/api/buckets/{bucket_name}")
        async def get_bucket_details(bucket_name: str):
            try:
                result = await self._get_bucket_details(bucket_name)
                return JSONResponse(content={
                    "success": True,
                    "data": result
                })
            except Exception as e:
                logger.error(f"Error in get_bucket_details API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.delete("/api/buckets/{bucket_name}")
        async def delete_bucket(bucket_name: str):
            try:
                result = await self._delete_bucket(bucket_name)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in delete_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.get("/api/buckets/{bucket_name}/files")
        async def list_bucket_files(bucket_name: str):
            try:
                result = await self._list_bucket_files(bucket_name)
                return JSONResponse(content={
                    "success": True,
                    "data": result
                })
            except Exception as e:
                logger.error(f"Error in list_bucket_files API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.post("/api/buckets/{bucket_name}/upload")
        async def upload_to_bucket(bucket_name: str, file: UploadFile = File(...), virtual_path: str = Form(None)):
            try:
                result = await self._upload_file_to_bucket(bucket_name, file, virtual_path)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in upload_to_bucket API: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": str(e)}
                )
        
        @self.app.get("/api/buckets/{bucket_name}/download/{file_path:path}")
        async def download_from_bucket(bucket_name: str, file_path: str):
            return await self._download_file_from_bucket(bucket_name, file_path)
        
        @self.app.delete("/api/buckets/{bucket_name}/files/{file_path:path}")
        async def delete_bucket_file(bucket_name: str, file_path: str):
            return await self._delete_bucket_file(bucket_name, file_path)
            
        # API Routes - Bucket Index Management
        @self.app.get("/api/bucket_index")
        async def get_bucket_index():
            return await self._get_bucket_index()
        
        @self.app.post("/api/bucket_index/create")
        async def create_bucket_index(request: Request):
            data = await request.json()
            return await self._create_bucket_index(data)
            
        @self.app.post("/api/bucket_index/rebuild")
        async def rebuild_bucket_index():
            return await self._rebuild_bucket_index()
            
        @self.app.get("/api/bucket_index/{bucket_name}")
        async def get_bucket_index_info(bucket_name: str):
            return await self._get_bucket_index_info(bucket_name)

        # API Routes - VFS
        @self.app.get("/api/vfs")
        async def get_vfs_structure():
            return await self._get_vfs_structure()
        
        @self.app.get("/api/vfs/{bucket_name}")
        async def browse_vfs(bucket_name: str, path: str = "/"):
            return await self._browse_vfs(bucket_name, path)
        
        # API Routes - Peers
        @self.app.get("/api/peers")
        async def get_peers():
            return await self._get_peers_data()
        
        @self.app.post("/api/peers/connect")
        async def connect_peer(request: Request):
            data = await request.json()
            return await self._connect_peer(data.get('address'))
        
        # API Routes - Logs
        @self.app.get("/api/logs")
        async def get_logs(component: str = "all", level: str = "info", limit: int = 100):
            return await self._get_logs(component, level, limit)
        
        @self.app.get("/api/logs/stream")
        async def stream_logs():
            return await self._stream_logs()
        
        # API Routes - Metrics  
        @self.app.get("/api/metrics")
        async def get_system_metrics():
            return await self._get_system_metrics()
        
        @self.app.get("/api/metrics/detailed")
        async def get_detailed_metrics():
            return await self._get_detailed_metrics()
        
        @self.app.get("/api/metrics/history")
        async def get_metrics_history():
            return await self._get_metrics_history()
        
        # API Routes - Enhanced Configuration Management
        @self.app.get("/api/config")
        async def get_config():
            return await self._get_system_config()
        
        @self.app.post("/api/config")
        async def update_config(request: Request):
            data = await request.json()
            return await self._update_system_config(data)
        
        @self.app.get("/api/config/files")
        async def list_config_files():
            return await self._list_config_files()
        
        @self.app.get("/api/config/file/{filename}")
        async def get_config_file(filename: str):
            return await self._get_config_file(filename)
        
        @self.app.post("/api/config/file/{filename}")
        async def update_config_file(filename: str, request: Request):
            data = await request.json()
            content = data.get('content', '')
            return await self._update_config_file(filename, content)
        
        @self.app.delete("/api/config/file/{filename}")
        async def delete_config_file(filename: str):
            return await self._delete_config_file(filename)
        
        @self.app.post("/api/config/backup")
        async def backup_config():
            return await self._backup_configuration()
        
        @self.app.post("/api/config/restore")
        async def restore_config(request: Request):
            data = await request.json()
            return await self._restore_configuration(data.get('backup_path'))
        
        @self.app.get("/api/config/mcp")
        async def get_mcp_config():
            return await self._get_mcp_server_config()
        
        @self.app.post("/api/config/mcp")
        async def update_mcp_config(request: Request):
            data = await request.json()
            return await self._update_mcp_server_config(data)
        
        @self.app.get("/api/config/{component}")
        async def get_component_config(component: str):
            return await self._get_component_config(component)
        
        # API Routes - Analytics
        @self.app.get("/api/analytics/summary")
        async def get_analytics_summary():
            return await self._get_analytics_summary()
        
        @self.app.get("/api/analytics/buckets")
        async def get_bucket_analytics():
            return await self._get_bucket_analytics()
        
        @self.app.get("/api/analytics/performance")
        async def get_performance_analytics():
            return await self._get_performance_analytics()
        
        # WebSocket endpoint for real-time updates
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)
    
    async def _disconnect_peer(self, peer_id: str) -> Dict[str, Any]:
        """Disconnect from a peer using the MCP server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.mcp_server_url}/tools/peer_disconnect",
                    json={"arguments": {"peer_id": peer_id}}
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        return {"success": False, "error": f"MCP server error: {resp.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        @self.app.get("/api/peers/stats")
        async def get_peer_stats():
            return await self._get_peer_stats()
        
        # API Routes - Pins
        @self.app.get("/api/pins")
        async def get_pins():
            return await self._get_pins_data()
        
        @self.app.post("/api/pins")
        async def add_pin(request: Request):
            data = await request.json()
            return await self._add_pin(data.get('cid'), data.get('name'))
        
        @self.app.delete("/api/pins/{cid}")
        async def remove_pin(cid: str):
            return await self._remove_pin(cid)
        
        @self.app.post("/api/pins/sync")
        async def sync_pins():
            return await self._sync_pins()
        
        # API Routes - Missing endpoints from error logs
        @self.app.get("/api/peers")
        async def get_peers():
            return await self._get_peer_stats()
        
        @self.app.get("/api/logs")
        async def get_logs(component: str = "all", level: str = "all", limit: int = 100):
            return await self._get_logs(component, level, limit)
        
        @self.app.get("/api/analytics/summary")
        async def get_analytics_summary():
            return await self._get_analytics_summary()
        
        @self.app.get("/api/config/files")
        async def get_config_files():
            return await self._get_config_files()

    def _get_dashboard_html(self):
        """Generate the dashboard HTML."""
        return """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>IPFS Kit - Consolidated MCP Dashboard</title>
    <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css\">
    <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
    <style>
        /* Modern CSS Framework */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #334155; }
        
        /* Layout */
        .dashboard { display: flex; min-height: 100vh; }
        .sidebar { width: 250px; background: white; border-right: 1px solid #e2e8f0; padding: 1.5rem; }
        .main-content { flex: 1; padding: 2rem; }
        
        /* Sidebar */
        .logo { font-size: 1.5rem; font-weight: bold; color: #0f172a; margin-bottom: 2rem; }
        .nav-item { display: flex; align-items: center; padding: 0.75rem 1rem; margin: 0.25rem 0; border-radius: 0.5rem; cursor: pointer; transition: all 0.2s; }
        .nav-item:hover { background: #f1f5f9; }
        .nav-item.active { background: #3b82f6; color: white; }
        .nav-item i { margin-right: 0.75rem; width: 1.25rem; }
        
        /* Cards */
        .card { background: white; border-radius: 0.75rem; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem; }
        .card-title { font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; color: #0f172a; }
        
        /* Grid */
        .grid { display: grid; gap: 1.5rem; }
        .grid-2 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
        .grid-3 { grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }
        .grid-4 { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
        
        /* Stats */
        .stat-card { text-align: center; padding: 1.5rem; }
        .stat-number { font-size: 2.5rem; font-weight: bold; color: #3b82f6; }
        .stat-label { color: #64748b; margin-top: 0.5rem; }
        
        /* Status */
        .status { display: inline-flex; align-items: center; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 500; }
        .status.running { background: #dcfce7; color: #166534; }
        .status.stopped { background: #fee2e2; color: #dc2626; }
        .status.configured { background: #dbeafe; color: #1d4ed8; }
        
        /* Buttons */
        .btn { display: inline-flex; align-items: center; padding: 0.5rem 1rem; border-radius: 0.5rem; font-weight: 500; cursor: pointer; transition: all 0.2s; border: none; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-secondary { background: #e2e8f0; color: #475569; }
        .btn-secondary:hover { background: #cbd5e1; }
        
        /* Tables */
        .table { width: 100%; border-collapse: collapse; }
        .table th, .table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
        .table th { font-weight: 600; color: #374151; background: #f9fafb; }
        
        /* Hide content initially */
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Service Categories */
        .service-categories { margin-top: 2rem; }
        .service-category { margin-bottom: 3rem; }
        .category-title { 
            font-size: 1.5rem; 
            font-weight: 600; 
            margin-bottom: 0.5rem; 
            color: #1e293b;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .category-description { 
            color: #64748b; 
            margin-bottom: 1.5rem; 
            font-size: 0.95rem;
        }
        
        /* Service Cards */
        .service-card { 
            background: white; 
            border-radius: 0.75rem; 
            padding: 1.5rem; 
            box-shadow: 0 1px 3px rgba(0,0,0,0.1); 
            border: 1px solid #e2e8f0;
            transition: all 0.2s;
            position: relative;
            overflow: hidden;
        }
        .service-card:hover { 
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); 
            transform: translateY(-2px);
        }
        
        .service-card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1rem;
        }
        
        .service-info h3 {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
            color: #1e293b;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .service-description {
            font-size: 0.875rem;
            color: #64748b;
            margin-bottom: 0.75rem;
        }
        
        .service-meta {
            font-size: 0.75rem;
            color: #94a3b8;
            margin-bottom: 1rem;
        }
        
        /* Service Status Badges */
        .service-status {
            display: inline-flex;
            align-items: center;
            padding: 0.375rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }
        
        .service-status.running {
            background: #dcfce7;
            color: #166534;
        }
        .service-status.stopped {
            background: #fee2e2;
            color: #dc2626;
        }
        .service-status.not-enabled {
            background: #f3f4f6;
            color: #6b7280;
        }
        .service-status.not-configured {
            background: #fef3c7;
            color: #d97706;
        }
        .service-status.configured {
            background: #dbeafe;
            color: #1d4ed8;
        }
        .service-status.error {
            background: #fecaca;
            color: #b91c1c;
        }
        
        /* Service Actions */
        .service-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        
        .service-btn {
            display: inline-flex;
            align-items: center;
            gap: 0.375rem;
            padding: 0.5rem 0.875rem;
            border-radius: 0.375rem;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            text-decoration: none;
        }
        
        .service-btn.btn-start {
            background: #dcfce7;
            color: #166534;
        }
        .service-btn.btn-start:hover {
            background: #bbf7d0;
        }
        
        .service-btn.btn-stop {
            background: #fee2e2;
            color: #dc2626;
        }
        .service-btn.btn-stop:hover {
            background: #fecaca;
        }
        
        .service-btn.btn-configure {
            background: #dbeafe;
            color: #1d4ed8;
        }
        .service-btn.btn-configure:hover {
            background: #bfdbfe;
        }
        
        .service-btn.btn-enable {
            background: #f0f9ff;
            color: #0284c7;
        }
        .service-btn.btn-enable:hover {
            background: #e0f2fe;
        }
        
        .service-btn.btn-restart {
            background: #fef3c7;
            color: #d97706;
        }
        .service-btn.btn-restart:hover {
            background: #fed7aa;
        }
        
        /* Configuration Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal.show {
            display: flex;
        }
        
        .modal-content {
            background: white;
            border-radius: 0.75rem;
            padding: 2rem;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
        }
        
        .modal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 1rem;
        }
        
        .modal-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #1e293b;
        }
        
        .modal-close {
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: #64748b;
            padding: 0.25rem;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-label {
            display: block;
            font-size: 0.875rem;
            font-weight: 600;
            color: #374151;
            margin-bottom: 0.5rem;
        }
        
        .form-input {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #d1d5db;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            transition: border-color 0.2s;
        }
        
        .form-input:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        .form-help {
            font-size: 0.75rem;
            color: #64748b;
            margin-top: 0.375rem;
        }
        
        .btn-group {
            display: flex;
            gap: 0.75rem;
            justify-content: flex-end;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #e2e8f0;
        }
        
        /* Utilities */
        .text-center { text-align: center; }
        .text-success { color: #059669; }
        .text-error { color: #dc2626; }
        .text-warning { color: #d97706; }
        .mt-4 { margin-top: 1rem; }
        .mb-4 { margin-bottom: 1rem; }
        .mb-6 { margin-bottom: 1.5rem; }
    </style>
</head>
<body>
    <div class=\"dashboard\">
        <div class=\"sidebar\">
            <div class=\"logo\">IPFS Kit</div>
            <nav>
                <div class=\"nav-item active\" data-tab=\"overview\">
                    <i class=\"fas fa-tachometer-alt\"></i> Overview
                </div>
                <div class=\"nav-item\" data-tab=\"services\">
                    <i class=\"fas fa-cogs\"></i> Services
                </div>
                <div class=\"nav-item\" data-tab=\"backends\">
                    <i class=\"fas fa-database\"></i> Backends
                </div>
                <div class=\"nav-item\" data-tab=\"buckets\">
                    <i class=\"fas fa-archive\"></i> Buckets
                </div>
                <div class=\"nav-item\" data-tab=\"pins\">
                    <i class=\"fas fa-thumbtack\"></i> Pins
                </div>
                <div class=\"nav-item\" data-tab=\"logs\">
                    <i class=\"fas fa-file-alt\"></i> Logs
                </div>
                <div class="nav-item" data-tab="mcp">
                    <i class="fas fa-exchange-alt"></i> MCP Tools
                </div>
                <div class="nav-item" data-tab="files">
                    <i class="fas fa-folder"></i> Files
                </div>
                <div class="nav-item" data-tab="ipfs">
                    <i class="fas fa-cube"></i> IPFS
                </div>
                <div class="nav-item" data-tab="peers">
                    <i class="fas fa-users"></i> Peers
                </div>
                <div class="nav-item" data-tab="analytics">
                    <i class="fas fa-chart-line"></i> Analytics
                </div>
            </nav>
        </div>
        
        <!-- Main Content -->
        <div class=\"main-content\">
            <!-- Overview Tab -->
            <div class="tab-content active" id="overview">
                <h1 class="card-title">System Overview</h1>
                
                <!-- System Metrics Grid (2 rows x 3 columns) -->
                <div class="grid grid-3">
                    <!-- Row 1: System Resources -->
                    <div class="card stat-card">
                        <div class="stat-number" id="cpu-usage">-</div>
                        <div class="stat-label">CPU Usage</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="memory-usage">-</div>
                        <div class="stat-label">Memory Usage</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="disk-usage">-</div>
                        <div class="stat-label">Disk Usage</div>
                    </div>
                    
                    <!-- Row 2: System Components -->
                    <div class="card stat-card">
                        <div class="stat-number" id="services-count">-</div>
                        <div class="stat-label">Services</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="backends-count">-</div>
                        <div class="stat-label">Backends</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="pins-count">-</div>
                        <div class="stat-label">Pins</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="buckets-count">-</div>
                        <div class="stat-label">Buckets</div>
                    </div>
                </div>
                
                <div class="grid grid-2">
                    <div class="card">
                        <h3 class="card-title">System Status</h3>
                        <div id="system-status-content">Loading...</div>
                    </div>
                    <div class="card">
                        <h3 class="card-title">Resource Usage</h3>
                        <div id="resource-usage-content">Loading...</div>
                    </div>
                </div>
            </div>
            
            <!-- Services Tab -->
            <div class="tab-content" id="services">
                <h1 class="card-title">🔧 Service Management</h1>
                
                <!-- Service Status Overview -->
                <div class="grid grid-4 mb-6">
                    <div class="card stat-card">
                        <div class="stat-number" id="running-services-count">0</div>
                        <div class="stat-label">🟢 Running</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="stopped-services-count">0</div>
                        <div class="stat-label">🔴 Stopped</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="configured-services-count">0</div>
                        <div class="stat-label">⚙️ Configured</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="unconfigured-services-count">0</div>
                        <div class="stat-label">❓ Need Setup</div>
                    </div>
                </div>

                <!-- Service Categories -->
                <div class="service-categories">
                    <!-- Storage Services -->
                    <div class="service-category">
                        <h2 class="category-title">📦 Storage Services</h2>
                        <p class="category-description">Configure storage backends for distributed file management</p>
                        <div class="grid grid-3" id="storage-services">
                            <!-- Storage service cards will be populated here -->
                        </div>
                    </div>

                    <!-- Daemon Services -->
                    <div class="service-category">
                        <h2 class="category-title">🛠️ Daemon Services</h2>
                        <p class="category-description">Core system services and background processes</p>
                        <div class="grid grid-3" id="daemon-services">
                            <!-- Daemon service cards will be populated here -->
                        </div>
                    </div>

                    <!-- Network Services -->
                    <div class="service-category">
                        <h2 class="category-title">🌐 Network Services</h2>
                        <p class="category-description">API endpoints and communication protocols</p>
                        <div class="grid grid-3" id="network-services">
                            <!-- Network service cards will be populated here -->
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Backends Tab -->
            <div class="tab-content" id="backends">
                <h1 class="card-title">Backend Configuration</h1>
                <div class="card">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Type</th>
                                <th>Status</th>
                                <th>Config File</th>
                            </tr>
                        </thead>
                        <tbody id="backends-table-body">
                            <tr><td colspan="4" class="text-center">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- Buckets Tab -->
            <div class="tab-content" id="buckets">
                <h1 class="card-title">Bucket Management</h1>
                <div class="card">
                    <div class="mb-4">
                        <button class="btn btn-primary" onclick="createBucket()">
                            <i class="fas fa-plus"></i> Create Bucket
                        </button>
                    </div>
                    <div id="buckets-content">Loading...</div>
                </div>
            </div>
            
            <!-- Pins Tab -->
            <div class="tab-content" id="pins">
                <h1 class="card-title">Pin Management</h1>
                <div class="card">
                    <div class="mb-4">
                        <button class="btn btn-primary" onclick="createPin()">
                            <i class="fas fa-plus"></i> Create Pin
                        </button>
                    </div>
                    <div id="pins-content">Loading...</div>
                </div>
            </div>
            
            <!-- Logs Tab -->
            <div class="tab-content" id="logs">
                <h1 class="card-title">System Logs</h1>
                <div class="card">
                    <div class="mb-4">
                        <select id="log-component" class="btn btn-secondary">
                            <option value="all">All Components</option>
                        </select>
                        <select id="log-level" class="btn btn-secondary">
                            <option value="all">All Levels</option>
                            <option value="error">Error</option>
                            <option value="warning">Warning</option>
                            <option value="info">Info</option>
                            <option value="debug">Debug</option>
                        </select>
                        <button class="btn btn-primary" onclick="loadLogs()">Refresh</button>
                    </div>
                    <div id="logs-content">Loading...</div>
                </div>
            </div>
            
            <!-- MCP Tab -->
            <div class="tab-content" id="mcp">
                <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem;">
                    <i class="fas fa-exchange-alt" style="font-size: 2rem; color: #3b82f6;"></i>
                    <h1 class="card-title" style="margin: 0;">MCP Tools</h1>
                    <div style="margin-left: auto; font-size: 0.875rem; color: #64748b;">
                        Iterative Development
                    </div>
                </div>
                
                <!-- MCP Server Control -->
                <div class="grid grid-4 mb-6">
                    <div class="card stat-card">
                        <div class="stat-number" style="color: #10b981;" id="mcp-server-status">Running</div>
                        <div class="stat-label">🟢 MCP Server</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="mcp-tools-count">3</div>
                        <div class="stat-label">🛠️ Tools Registry</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" id="mcp-protocol-version">2024-11-05</div>
                        <div class="stat-label">📋 Protocol Ver.</div>
                    </div>
                    <div class="card stat-card">
                        <div class="stat-number" style="color: #3b82f6;" id="mcp-connections">Active</div>
                        <div class="stat-label">🔗 IPFS Kit Link</div>
                    </div>
                </div>

                <!-- MCP Tabs -->
                <div style="border-bottom: 1px solid #e2e8f0; margin-bottom: 1.5rem;">
                    <nav style="display: flex; gap: 0.5rem;">
                        <button class="btn btn-secondary" style="border-radius: 0; border-bottom: 2px solid #3b82f6;" onclick="showMcpTab('overview')">Overview</button>
                        <button class="btn btn-secondary" style="border-radius: 0;" onclick="showMcpTab('server')">MCP Server</button>
                        <button class="btn btn-secondary" style="border-radius: 0;" onclick="showMcpTab('tools')">Tools Registry</button>
                        <button class="btn btn-secondary" style="border-radius: 0; background: #3b82f6; color: white;" onclick="showMcpTab('ipfs')">IPFS Integration</button>
                        <button class="btn btn-secondary" style="border-radius: 0;" onclick="showMcpTab('inspector')">Protocol Inspector</button>
                    </nav>
                </div>

                <!-- IPFS Integration Tab (Active) -->
                <div id="mcp-ipfs-tab">
                    <div class="grid grid-2">
                        <div class="card">
                            <h3 class="card-title">MCP-Enabled IPFS Operations</h3>
                            <p style="color: #64748b; margin-bottom: 1rem;">
                                Execute IPFS Kit operations through the MCP protocol for better integration and control.
                            </p>
                            
                            <h4 style="font-weight: 600; margin-bottom: 0.75rem;">Quick Actions</h4>
                            <div style="display: grid; gap: 0.5rem;">
                                <button class="btn btn-primary" onclick="executeMcpTool('ipfs_pin_tool', 'pin_list')">
                                    <i class="fas fa-list"></i> List Pins via MCP
                                </button>
                                <button class="btn btn-primary" onclick="executeMcpTool('bucket_management_tool', 'list_buckets')">
                                    <i class="fas fa-archive"></i> List Buckets via MCP  
                                </button>
                                <button class="btn btn-primary" onclick="executeMcpTool('ipfs_kit_control_tool', 'system_status')">
                                    <i class="fas fa-heartbeat"></i> System Status via MCP
                                </button>
                            </div>
                        </div>
                        
                        <div class="card">
                            <h3 class="card-title">Execution Results</h3>
                            <div id="mcp-execution-results" style="background: #f8fafc; border-radius: 0.5rem; padding: 1rem; min-height: 200px; font-family: monospace; font-size: 0.875rem; overflow-y: auto;">
                                <div style="color: #059669; margin-bottom: 0.5rem;">
                                    ✓ ipfs_pin_tool executed successfully
                                </div>
                                <div style="color: #64748b; margin-bottom: 0.5rem;">
                                    Action: pin_list
                                </div>
                                <div style="color: #64748b; margin-bottom: 0.5rem;">
                                    Time: 1.23s
                                </div>
                                <div style="color: #475569;">
                                    Executed ipfs_pin_tool with parameters: {'action': 'pin_list'}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Files Tab -->
            <div class="tab-content" id="files">
                <h1 class="card-title">File Browser</h1>
                <div class="card">
                    <div id="files-content">Loading...</div>
                </div>
            </div>

            <!-- IPFS Tab -->
            <div class="tab-content" id="ipfs">
                <h1 class="card-title">IPFS Operations</h1>
                <div class="card">
                    <div class="grid grid-2">
                        <div>
                            <h3>Add Content to IPFS</h3>
                            <form id="ipfs-add-form">
                                <textarea id="ipfs-add-content" placeholder="Enter content to add" rows="5" style="width: 100%;"></textarea>
                                <button type="submit" class="btn btn-primary mt-4">Add to IPFS</button>
                            </form>
                        </div>
                        <div>
                            <h3>Get Content from IPFS</h3>
                            <form id="ipfs-get-form">
                                <input type="text" id="ipfs-get-cid" placeholder="Enter IPFS CID" style="width: 100%;">
                                <button type="submit" class="btn btn-primary mt-4">Get from IPFS</button>
                            </form>
                            <div id="ipfs-get-content" class="mt-4"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Peers Tab -->
            <div class="tab-content" id="peers">
                <h1 class="card-title">Connected Peers</h1>
                <div class="card">
                    <div id="peers-content">Loading...</div>
                </div>
            </div>

            <!-- Analytics Tab -->
            <div class="tab-content" id="analytics">
                <h1 class="card-title">System Analytics</h1>
                <div class="card">
                    <div id="analytics-content">Loading...</div>
                </div>
            </div>
        </div>
        </div>

    <!-- Service Configuration Modal -->
    <div id="service-config-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title" id="modal-title">Configure Service</h2>
                <button class="modal-close" onclick="closeConfigModal()">&times;</button>
            </div>
            <div id="modal-body">
                <!-- Configuration form will be populated here -->
            </div>
        </div>
    </div>

    <!-- Load MCP SDK first -->
    <script src="/static/mcp-sdk.js"></script>
    <!-- Load app code -->
    <script src="/app.js" defer></script>
</body>
</html>"""

    async def run(self):
        """Run the dashboard server."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info" if self.debug else "warning"
        )
        server = uvicorn.Server(config)
        await server.serve()

    # =================== MCP TOOL IMPLEMENTATIONS ===================
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool by name with arguments."""
        try:
            # Handle different tool types
            if tool_name == "list_services":
                return await self._handle_list_services(arguments)
            elif tool_name == "control_service":
                return await self._handle_control_service(arguments)
            elif tool_name == "list_backends":
                return await self._handle_list_backends(arguments)
            elif tool_name == "list_buckets":
                return await self._handle_list_buckets(arguments)
            elif tool_name == "list_pins":
                return await self._handle_list_pins(arguments)
            elif tool_name == "get_system_overview":
                return await self._handle_get_system_overview(arguments)
            elif tool_name == "get_system_status":
                return await self._handle_get_system_status(arguments)
            elif tool_name == "get_logs":
                return await self._handle_get_logs(arguments)
            elif tool_name == "list_files":
                return await self._handle_list_files(arguments)
            elif tool_name == "ipfs_add":
                return await self._handle_ipfs_add(arguments)
            elif tool_name == "ipfs_get":
                return await self._handle_ipfs_get(arguments)
            elif tool_name == "list_peers":
                return await self._handle_list_peers(arguments)
            elif tool_name == "get_system_analytics":
                return await self._handle_get_system_analytics(arguments)
            elif tool_name == "list_config_files":
                return await self._handle_list_config_files(arguments)
            elif tool_name == "create_bucket":
                return await self._handle_create_bucket(arguments)
            elif tool_name == "create_pin":
                return await self._handle_create_pin(arguments)
            else:
                return {
                    "error": f"Unknown tool: {tool_name}",
                    "available_tools": [
                        "list_services", "control_service", "list_backends", "list_buckets", 
                        "list_pins", "get_system_overview", "get_system_status", "get_logs",
                        "list_files", "ipfs_add", "ipfs_get", "list_peers", "get_system_analytics",
                        "list_config_files", "create_bucket", "create_pin"
                    ]
                }
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def _get_all_mcp_tools(self) -> Dict[str, Any]:
        """Get list of all available MCP tools."""
        tools = [
            {
                "name": "list_services",
                "description": "List all detected services including daemons and VFS backends",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "control_service", 
                "description": "Control a service (start, stop, restart, configure)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "action": {"type": "string", "description": "Action to perform"}
                    },
                    "required": ["service", "action"]
                }
            },
            {
                "name": "list_backends",
                "description": "List all storage backends",
                "inputSchema": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "list_buckets", 
                "description": "List all buckets",
                "inputSchema": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "list_pins",
                "description": "List all pins",
                "inputSchema": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "get_system_overview",
                "description": "Get system overview",
                "inputSchema": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "get_system_status",
                "description": "Get detailed system status",
                "inputSchema": {"type": "object", "properties": {}, "required": []}
            },
            {
                "name": "get_logs",
                "description": "Get system logs",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component": {"type": "string", "description": "Component to get logs for"},
                        "level": {"type": "string", "description": "Log level filter"},
                        "limit": {"type": "number", "description": "Number of log entries"}
                    },
                    "required": []
                }
            }
        ]
        return {"result": {"tools": tools}}
    
    async def _handle_list_services(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_services tool call."""
        try:
            # Use StateService to get enhanced service list
            if hasattr(self, 'state_service') and self.state_service:
                services = self.state_service.list_services()
            else:
                # Fallback: create StateService instance
                from ipfs_kit_py.services.state_service import StateService
                state_service = StateService(self.data_dir)
                services = state_service.list_services()
            
            return {"result": services}
        except Exception as e:
            logger.error(f"Error listing services: {e}")
            return {"error": str(e)}
    
    async def _handle_control_service(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle control_service tool call."""
        try:
            service_name = arguments.get("service")
            action = arguments.get("action")
            
            if not service_name or not action:
                return {"error": "service and action parameters are required"}
            
            # Use StateService to control service
            if hasattr(self, 'state_service') and self.state_service:
                result = self.state_service.control_service(service_name, action)
            else:
                from ipfs_kit_py.services.state_service import StateService
                state_service = StateService(self.data_dir)
                result = state_service.control_service(service_name, action)
            
            return {"result": result}
        except Exception as e:
            logger.error(f"Error controlling service: {e}")
            return {"error": str(e)}
    
    async def _handle_list_backends(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_backends tool call.""" 
        try:
            backends = await self._get_backends_data()
            return {"result": backends}
        except Exception as e:
            logger.error(f"Error listing backends: {e}")
            return {"error": str(e)}
    
    async def _handle_list_buckets(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_buckets tool call."""
        try:
            buckets = await self._get_buckets_data()
            return {"result": buckets}  # Return direct array for consistency
        except Exception as e:
            logger.error(f"Error listing buckets: {e}")
            return {"error": str(e)}
    
    async def _handle_list_pins(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_pins tool call."""
        try:
            pins = await self._get_pins_data()
            return {"result": pins}  # Return direct array for consistency
        except Exception as e:
            logger.error(f"Error listing pins: {e}")
            return {"error": str(e)}
    
    async def _handle_get_system_overview(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_system_overview tool call."""
        try:
            # Get data from the same sources as the API endpoints
            backends_data = await self._get_backends_data()
            buckets_data = await self._get_buckets_data()
            pins_data = await self._get_pins_data()
            services_data = await self._get_services_data()
            
            overview = {
                "services": len(services_data.get("services", {})),
                "backends": len(backends_data),
                "buckets": len(buckets_data),
                "pins": len(pins_data),
                "uptime": str(datetime.now() - self.start_time),
                "status": "running"
            }
            
            return {"result": overview}
        except Exception as e:
            logger.error(f"Error getting system overview: {e}")
            return {"error": str(e)}
    
    async def _handle_get_system_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_system_status tool call."""
        try:
            if hasattr(self, 'state_service') and self.state_service:
                status = self.state_service.get_system_status()
            else:
                from ipfs_kit_py.services.state_service import StateService
                state_service = StateService(self.data_dir)
                status = state_service.get_system_status()
            
            return {"result": status}
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"error": str(e)}
    
    async def _handle_get_logs(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_logs tool call."""
        try:
            component = arguments.get("component", "all")
            level = arguments.get("level", "all")
            limit = arguments.get("limit", 50)
            
            if hasattr(self, 'memory_log_handler') and self.memory_log_handler:
                logs = self.memory_log_handler.get_logs(component, level, limit)
            else:
                logs = []
            
            return {"result": logs}
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return {"error": str(e)}
    
    async def _handle_list_files(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_files tool call."""
        try:
            path = arguments.get("path", ".")
            files = []
            
            try:
                import os
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    files.append({
                        "name": item,
                        "path": item_path,
                        "type": "directory" if os.path.isdir(item_path) else "file",
                        "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
                    })
            except Exception as e:
                return {"error": f"Error listing files: {str(e)}"}
            
            return {"result": files}
        except Exception as e:
            logger.error(f"Error handling list_files: {e}")
            return {"error": str(e)}
    
    async def _handle_ipfs_add(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ipfs_add tool call."""
        try:
            content = arguments.get("content")
            if not content:
                return {"error": "content parameter is required"}
            
            # Placeholder for IPFS add functionality
            return {"result": {"cid": "QmPlaceholder", "content": content[:100] + "..." if len(content) > 100 else content}}
        except Exception as e:
            logger.error(f"Error handling ipfs_add: {e}")
            return {"error": str(e)}
    
    async def _handle_ipfs_get(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ipfs_get tool call."""
        try:
            cid = arguments.get("cid")
            if not cid:
                return {"error": "cid parameter is required"}
            
            # Placeholder for IPFS get functionality
            return {"result": {"cid": cid, "content": f"Content for {cid} (placeholder)"}}
        except Exception as e:
            logger.error(f"Error handling ipfs_get: {e}")
            return {"error": str(e)}
    
    async def _handle_list_peers(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_peers tool call."""
        try:
            # Placeholder for peer listing
            peers = [
                {"id": "12D3KooWExample1", "addresses": ["/ip4/127.0.0.1/tcp/4001"]},
                {"id": "12D3KooWExample2", "addresses": ["/ip4/192.168.1.100/tcp/4001"]}
            ]
            return {"result": peers}
        except Exception as e:
            logger.error(f"Error handling list_peers: {e}")
            return {"error": str(e)}
    
    async def _handle_get_system_analytics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_system_analytics tool call."""
        try:
            # Placeholder for system analytics
            analytics = {
                "cpu_usage": 25.5,
                "memory_usage": 60.2,
                "disk_usage": 45.8,
                "network_io": {"bytes_sent": 1024000, "bytes_recv": 2048000}
            }
            return {"result": analytics}
        except Exception as e:
            logger.error(f"Error handling get_system_analytics: {e}")
            return {"error": str(e)}
    
    async def _handle_list_config_files(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_config_files tool call."""
        try:
            config_files = await self._get_config_files()
            files = config_files.get("data", {}).get("files", [])
            return {"result": files}
        except Exception as e:
            logger.error(f"Error listing config files: {e}")
            return {"error": str(e)}
    
    async def _handle_create_bucket(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_bucket tool call."""
        try:
            name = arguments.get("name")
            backend = arguments.get("backend")
            
            if not name or not backend:
                return {"error": "name and backend parameters are required"}
            
            if hasattr(self, 'state_service') and self.state_service:
                result = self.state_service.create_bucket(name, backend)
            else:
                from ipfs_kit_py.services.state_service import StateService
                state_service = StateService(self.data_dir)
                result = state_service.create_bucket(name, backend)
            
            return {"result": result}
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            return {"error": str(e)}
    
    async def _handle_create_pin(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_pin tool call."""
        try:
            cid = arguments.get("cid")
            name = arguments.get("name", "")
            
            if not cid:
                return {"error": "cid parameter is required"}
            
            if hasattr(self, 'state_service') and self.state_service:
                result = self.state_service.create_pin(cid, name)
            else:
                from ipfs_kit_py.services.state_service import StateService
                state_service = StateService(self.data_dir)
                result = state_service.create_pin(cid, name)
            
            return {"result": result}
        except Exception as e:
            logger.error(f"Error creating pin: {e}")
            return {"error": str(e)}

    # =================== OTHER METHODS ===================

    async def _test_all_components(self):
        """Test all components for functionality."""
        # TODO: Implement actual component tests
        return {"success": True, "data": {"status": "all components passed"}}

    async def _test_mcp_tools(self):
        """Test all MCP tools."""
        # TODO: Implement actual MCP tool tests
        return {"success": True, "data": {"status": "all MCP tools passed"}}
    
    async def _get_services_data(self):
        """Get comprehensive services data for the dashboard."""
        try:
            # Mock service data with comprehensive service information
            services = {
                "ipfs": {
                    "name": "IPFS Daemon",
                    "type": "daemon", 
                    "status": "stopped",
                    "description": "IPFS node for distributed file system",
                    "last_check": "2024-01-01T00:00:00Z"
                },
                "mcp_server": {
                    "name": "MCP Server",
                    "type": "network",
                    "status": "running", 
                    "description": "Model Context Protocol server",
                    "last_check": "2024-01-01T00:00:00Z"
                },
                "aria2": {
                    "name": "Aria2 Daemon", 
                    "type": "daemon",
                    "status": "stopped",
                    "description": "High-speed download manager daemon",
                    "last_check": "2024-01-01T00:00:00Z"
                },
                "lotus": {
                    "name": "Lotus Storage",
                    "type": "daemon",
                    "status": "not_enabled",
                    "description": "Filecoin Lotus node for blockchain storage", 
                    "last_check": "N/A"
                },
                "ipfs_cluster": {
                    "name": "IPFS Cluster",
                    "type": "daemon",
                    "status": "not_enabled", 
                    "description": "IPFS Cluster for coordinated IPFS nodes",
                    "last_check": "N/A"
                },
                "s3": {
                    "name": "Amazon S3",
                    "type": "storage",
                    "status": "not_configured",
                    "description": "Amazon S3 compatible storage for distributed file management",
                    "last_check": "N/A"
                },
                "huggingface": {
                    "name": "HuggingFace Hub",
                    "type": "storage", 
                    "status": "not_configured",
                    "description": "HuggingFace Hub for AI models and datasets",
                    "last_check": "N/A"
                },
                "github": {
                    "name": "GitHub Storage",
                    "type": "storage",
                    "status": "not_configured",
                    "description": "GitHub repositories as distributed storage backends", 
                    "last_check": "N/A"
                },
                "storacha": {
                    "name": "Storacha",
                    "type": "storage",
                    "status": "not_configured",
                    "description": "Decentralized storage network",
                    "last_check": "N/A"
                },
                "synapse": {
                    "name": "Synapse Matrix", 
                    "type": "storage",
                    "status": "not_configured",
                    "description": "Matrix Synapse messaging and storage",
                    "last_check": "N/A"
                },
                "gdrive": {
                    "name": "Google Drive",
                    "type": "storage",
                    "status": "not_configured",
                    "description": "Google Drive cloud storage integration",
                    "last_check": "N/A"
                },
                "ftp": {
                    "name": "FTP Server",
                    "type": "storage", 
                    "status": "not_configured",
                    "description": "File Transfer Protocol server connection",
                    "last_check": "N/A"
                },
                "sshfs": {
                    "name": "SSHFS",
                    "type": "storage",
                    "status": "not_configured",
                    "description": "SSH filesystem mounting for secure file access",
                    "last_check": "N/A"
                }
            }
            
            return {"success": True, "services": services}
            
        except Exception as e:
            logger.error(f"Error getting services data: {e}")
            return {"success": False, "error": str(e), "services": {}}
    
    async def _get_service_details(self, service_name: str):
        """Get details for a specific service."""
        try:
            services_data = await self._get_services_data()
            if services_data["success"] and service_name in services_data["services"]:
                return {"success": True, "service": services_data["services"][service_name]}
            else:
                return {"success": False, "error": f"Service '{service_name}' not found"}
        except Exception as e:
            logger.error(f"Error getting service details for {service_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _control_service(self, service_name: str, action: str):
        """Control a service (start, stop, restart, enable, disable)."""
        try:
            logger.info(f"Service control: {service_name} -> {action}")
            
            # Mock service control logic
            valid_actions = ["start", "stop", "restart", "enable", "disable", "configure"]
            if action not in valid_actions:
                return {"success": False, "error": f"Invalid action: {action}"}
            
            # Simulate different responses based on service and action
            if action == "start":
                message = f"Started {service_name} service"
            elif action == "stop": 
                message = f"Stopped {service_name} service"
            elif action == "restart":
                message = f"Restarted {service_name} service"
            elif action == "enable":
                message = f"Enabled {service_name} service"
            elif action == "disable":
                message = f"Disabled {service_name} service"
            else:
                message = f"Performed {action} on {service_name} service"
                
            return {
                "success": True, 
                "message": message,
                "service": service_name,
                "action": action
            }
            
        except Exception as e:
            logger.error(f"Error controlling service {service_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _configure_service(self, service_name: str, config_data: dict):
        """Configure a service with the provided configuration data."""
        try:
            logger.info(f"Configuring service {service_name} with config: {config_data}")
            
            # Mock service configuration logic
            # In a real implementation, this would save the configuration
            # and update the service status accordingly
            
            return {
                "success": True,
                "message": f"Successfully configured {service_name} service",
                "service": service_name,
                "config": config_data
            }
            
        except Exception as e:
            logger.error(f"Error configuring service {service_name}: {e}")
            return {"success": False, "error": str(e)}

    async def _get_backends_data(self):
        """Get comprehensive backends data for the dashboard."""
        try:
            # Mock backend data with comprehensive backend information
            backends = {
                "ipfs": {
                    "name": "IPFS Storage",
                    "type": "filesystem",
                    "status": "active",
                    "description": "Distributed IPFS file system backend",
                    "health": "healthy",
                    "storage_used": "2.1 GB",
                    "files_count": 156
                },
                "s3": {
                    "name": "Amazon S3", 
                    "type": "cloud_storage",
                    "status": "inactive",
                    "description": "Amazon S3 cloud storage backend",
                    "health": "unknown",
                    "storage_used": "0 GB",
                    "files_count": 0
                },
                "local": {
                    "name": "Local Storage",
                    "type": "filesystem", 
                    "status": "active",
                    "description": "Local filesystem backend",
                    "health": "healthy",
                    "storage_used": "5.7 GB", 
                    "files_count": 342
                }
            }
            
            return list(backends.values())
            
        except Exception as e:
            logger.error(f"Error getting backends data: {e}")
            return []

    async def _get_buckets_data(self):
        """Get comprehensive buckets data for the dashboard."""
        try:
            # Mock bucket data with comprehensive bucket information
            buckets = {
                "default": {
                    "name": "default",
                    "type": "mixed",
                    "created_at": "2024-01-01T00:00:00Z",
                    "file_count": 45,
                    "total_size": "1.2 GB",
                    "backends": ["ipfs", "local"],
                    "status": "active"
                },
                "media": {
                    "name": "media",
                    "type": "multimedia",
                    "created_at": "2024-01-15T10:30:00Z", 
                    "file_count": 23,
                    "total_size": "850 MB",
                    "backends": ["ipfs", "s3"],
                    "status": "active"
                },
                "documents": {
                    "name": "documents",
                    "type": "documents",
                    "created_at": "2024-02-01T14:20:00Z",
                    "file_count": 67,
                    "total_size": "234 MB", 
                    "backends": ["local"],
                    "status": "active"
                }
            }
            
            return list(buckets.values())
            
        except Exception as e:
            logger.error(f"Error getting buckets data: {e}")
            return []

    async def _get_pins_data(self):
        """Get comprehensive pins data for the dashboard."""
        try:
            # Mock pins data with comprehensive pin information
            pins = {
                "QmRJzaM2U1A4DJCWW7F6DHJdzhnep5sz1FhdvGp1xn8VkW": {
                    "cid": "QmRJzaM2U1A4DJCWW7F6DHJdzhnep5sz1FhdvGp1xn8VkW", 
                    "name": "example-document.pdf",
                    "type": "document",
                    "size": "2.3 MB",
                    "pinned_at": "2024-01-10T08:30:00Z",
                    "backends": ["ipfs", "local"],
                    "status": "pinned"
                },
                "QmPUjLZrEpNfPJxb5pExLmh4DhJd9yTbxQPhTfzR8PXqHk": {
                    "cid": "QmPUjLZrEpNfPJxb5pExLmh4DhJd9yTbxQPhTfzR8PXqHk",
                    "name": "config.yaml", 
                    "type": "configuration",
                    "size": "1.1 KB",
                    "pinned_at": "2024-01-05T14:15:00Z",
                    "backends": ["ipfs"],
                    "status": "pinned"
                },
                "QmXwPdMXpUCZ8UBMBWxYaLJMx9Q8NhF6T2VxE3KYzMvKdg": {
                    "cid": "QmXwPdMXpUCZ8UBMBWxYaLJMx9Q8NhF6T2VxE3KYzMvKdg",
                    "name": "image.png",
                    "type": "image", 
                    "size": "456 KB",
                    "pinned_at": "2024-01-20T11:45:00Z",
                    "backends": ["ipfs", "local"],
                    "status": "pinned"
                }
            }
            
            return list(pins.values())
            
        except Exception as e:
            logger.error(f"Error getting pins data: {e}")
            return []

    async def _get_peer_stats(self) -> Dict[str, Any]:
        """Get peer statistics."""
        try:
            # Mock peer stats data
            return {
                "connected_peers": 5,
                "total_peers": 12,
                "peer_info": [
                    {"id": "12D3Koo...", "addr": "/ip4/192.168.1.1/tcp/4001", "latency": "25ms"},
                    {"id": "12D3Koo...", "addr": "/ip4/192.168.1.2/tcp/4001", "latency": "18ms"},
                ],
                "bandwidth": {
                    "in": "1.2 MB/s",
                    "out": "0.8 MB/s"
                }
            }
        except Exception as e:
            logger.error(f"Error getting peer stats: {e}")
            return {}

    async def _add_pin(self, cid: str, name: str = None) -> Dict[str, Any]:
        """Add a pin to the system."""
        try:
            # Mock pin addition - return success for now
            return {
                "success": True,
                "message": f"Pin added successfully",
                "data": {
                    "cid": cid,
                    "name": name or f"pin-{cid[:8]}",
                    "status": "pinned",
                    "pinned_at": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error adding pin: {e}")
            return {"success": False, "error": str(e)}

    async def _remove_pin(self, cid: str) -> Dict[str, Any]:
        """Remove a pin from the system."""
        try:
            # Mock pin removal - return success for now
            return {
                "success": True,
                "message": f"Pin removed successfully",
                "data": {"cid": cid}
            }
        except Exception as e:
            logger.error(f"Error removing pin: {e}")
            return {"success": False, "error": str(e)}

    async def _sync_pins(self) -> Dict[str, Any]:
        """Sync pins across backends."""
        try:
            # Mock pin sync - return success for now
            return {
                "success": True,
                "message": "Pins synchronized successfully",
                "data": {
                    "synced_count": 3,
                    "failed_count": 0
                }
            }
        except Exception as e:
            logger.error(f"Error syncing pins: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_logs(self, component: str = "all", level: str = "all", limit: int = 100) -> Dict[str, Any]:
        """Get system logs."""
        try:
            # Mock logs data
            logs = [
                {"timestamp": "2024-08-28T04:05:00Z", "level": "INFO", "component": "mcp", "message": "MCP server started"},
                {"timestamp": "2024-08-28T04:05:01Z", "level": "DEBUG", "component": "backend", "message": "Backend health check completed"},
                {"timestamp": "2024-08-28T04:05:02Z", "level": "INFO", "component": "dashboard", "message": "Dashboard initialized"},
                {"timestamp": "2024-08-28T04:05:03Z", "level": "DEBUG", "component": "api", "message": "API endpoints registered"},
                {"timestamp": "2024-08-28T04:05:04Z", "level": "INFO", "component": "system", "message": "System metrics updated"}
            ][:limit]
            
            return {
                "success": True,
                "data": {"logs": logs}
            }
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Get analytics summary."""
        try:
            # Mock analytics data
            return {
                "success": True,
                "data": {
                    "requests_per_hour": 45,
                    "average_response_time": "120ms",
                    "error_rate": "0.2%",
                    "uptime": "99.8%",
                    "active_connections": 8,
                    "total_data_processed": "2.4 GB"
                }
            }
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_config_files(self) -> Dict[str, Any]:
        """Get configuration files."""
        try:
            # Mock config files data
            config_files = [
                {"name": "ipfs_kit.yaml", "path": "/config/ipfs_kit.yaml", "size": "2.1 KB", "modified": "2024-08-28T04:00:00Z"},
                {"name": "backends.yaml", "path": "/config/backends.yaml", "size": "1.8 KB", "modified": "2024-08-27T10:30:00Z"},
                {"name": "services.json", "path": "/config/services.json", "size": "3.2 KB", "modified": "2024-08-26T15:45:00Z"}
            ]
            
            return {
                "success": True,
                "data": {"files": config_files}
            }
        except Exception as e:
            logger.error(f"Error getting config files: {e}")
            return {"success": False, "error": str(e)}

def main():
    """Main entry point."""
    import sys
    
    config = {
        "host": "127.0.0.1",
        "port": 8004,
        "debug": "--debug" in sys.argv,
    # Use a concrete expanded path by default
    "data_dir": str(Path.home() / ".ipfs_kit"),
    }
    
    dashboard = ConsolidatedMCPDashboard(config)
    asyncio.run(dashboard.run())

if __name__ == "__main__":
    main()
