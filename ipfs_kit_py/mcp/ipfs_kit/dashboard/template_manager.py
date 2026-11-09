"""
Dashboard template manager for generating HTML templates.
Provides modular templates with proper separation of concerns.
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DashboardTemplateManager:
    """Manages dashboard HTML templates with modular JavaScript architecture."""
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.templates_dir.mkdir(exist_ok=True)
        
    def create_dashboard_template(self) -> str:
        """Create the main dashboard template with modular JavaScript imports."""
        
        template_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced IPFS Kit Backend Observatory</title>
    <link rel="stylesheet" href="/static/css/dashboard.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Enhanced IPFS Kit Backend Observatory</h1>
            <div class="header-stats">
                <span id="status-indicator">🟡 Loading...</span>
                <span id="refresh-info">Last updated: Never</span>
                <button onclick="refreshData()">🔄 Refresh</button>
            </div>
        </div>

        <div class="tabs">
            <div class="tab-buttons">
                <button class="tab-button active" onclick="showTab('overview', event)">📊 Overview</button>
                <button class="tab-button" onclick="showTab('monitoring', event)">📈 Monitoring</button>
                <button class="tab-button" onclick="showTab('vfs', event)">🗂️ VFS Observatory</button>
                <button class="tab-button" onclick="showTab('vectorkb', event)">🧠 Vector/KB</button>
                <button class="tab-button" onclick="showTab('backends', event)">⚙️ Backends</button>
                <button class="tab-button" onclick="showTab('filemanager', event)">📁 File Manager</button>
                <button class="tab-button" onclick="showTab('configuration', event)">🔧 Configuration</button>
            </div>

            <!-- Tab Contents -->
            <div id="overview" class="tab-content active">
                <div id="overview-content">Loading overview...</div>
            </div>

            <div id="monitoring" class="tab-content">
                <div id="monitoring-content">Loading monitoring data...</div>
            </div>

            <div id="vfs" class="tab-content">
                <div id="vfs-content">Loading VFS data...</div>
            </div>

            <div id="vectorkb" class="tab-content">
                <div id="vectorkb-content">Loading Vector/KB data...</div>
            </div>

            <div id="backends" class="tab-content">
                <div id="backends-content">Loading backends...</div>
            </div>

            <div id="filemanager" class="tab-content">
                <div id="filemanager-content">Loading file manager...</div>
            </div>

            <div id="configuration" class="tab-content">
                <div id="configuration-content">Loading configuration...</div>
            </div>
        </div>
    </div>

    <!-- Modal for configuration -->
    <div id="configModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeConfigModal()">&times;</span>
            <h2 id="configModalTitle">Configuration</h2>
            <div id="configModalContent">Loading...</div>
        </div>
    </div>

    <!-- Modal for logs -->
    <div id="logsModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeLogsModal()">&times;</span>
            <h2 id="logsModalTitle">Logs</h2>
            <div id="logsModalContent">Loading...</div>
        </div>
    </div>

    <!-- Load modular JavaScript files in proper dependency order -->
    <script src="/static/js/api-client.js"></script>
    <script src="/static/js/file_manager.js"></script>
    <script src="/static/js/dashboard-core.js"></script>
    <script src="/static/js/overview-tab.js"></script>
    <script src="/static/js/other-tabs.js"></script>
    <script src="/static/js/vfs-observatory.js"></script>
    
    <!-- Initialize dashboard -->
    <script>
        // Create global API client instance
        window.api = new DashboardAPI();
        
        // Initialize dashboard when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeDashboard);
        } else {
            initializeDashboard();
        }
        
        function initializeDashboard() {
            console.log('Initializing modular dashboard...');
            if (typeof refreshData !== 'undefined') {
                refreshData();
            } else {
                console.error('refreshData function not found');
            }
        }
    </script>
</body>
</html>'''
        
        template_path = self.templates_dir / "index.html"
        template_path.write_text(template_content)
        logger.info(f"Created modular dashboard template at {template_path}")
        
        return template_content


def get_enhanced_dashboard_template():
    """
    Returns a comprehensive, modular HTML template for the enhanced dashboard.
    This replaces the previous monolithic approach with proper separation of concerns.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit Enhanced Dashboard</title>
    <link rel="stylesheet" href="/static/css/dashboard.css">
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>IPFS Kit Enhanced Dashboard</h1>
            <div class="header-stats">
                <span id="status-indicator">🔄 Loading...</span>
                <button onclick="dashboardCore.refreshAllData()">🔄 Refresh</button>
            </div>
        </div>
        
        <div class="tabs">
            <div class="tab-buttons">
                <button class="tab-button active" onclick="showTab('overview')">Overview</button>
                <button class="tab-button" onclick="showTab('monitoring')">Monitoring</button>
                <button class="tab-button" onclick="showTab('vfs')">VFS</button>
                <button class="tab-button" onclick="showTab('vector')">Vector</button>
                <button class="tab-button" onclick="showTab('kb')">Knowledge Base</button>
                <button class="tab-button" onclick="showTab('analytics')">Analytics</button>
                <button class="tab-button" onclick="showTab('files')">Files</button>
                <button class="tab-button" onclick="showTab('settings')">Settings</button>
            </div>
            
            <div id="overview" class="tab-content active">
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>System Status</h3>
                        <div class="stat-value" id="system-status">Checking...</div>
                        <div class="stat-label">Overall Health</div>
                    </div>
                    <div class="stat-card">
                        <h3>IPFS Peers</h3>
                        <div class="stat-value" id="peer-count">0</div>
                        <div class="stat-label">Connected Peers</div>
                    </div>
                    <div class="stat-card">
                        <h3>Data Storage</h3>
                        <div class="stat-value" id="storage-used">0 GB</div>
                        <div class="stat-label">Used Space</div>
                    </div>
                    <div class="stat-card">
                        <h3>Active Processes</h3>
                        <div class="stat-value" id="process-count">0</div>
                        <div class="stat-label">Running Services</div>
                    </div>
                </div>
            </div>
            
            <div id="monitoring" class="tab-content">
                <div id="monitoring-content">
                    <div class="loading">Loading monitoring data...</div>
                </div>
            </div>
            
            <div id="vfs" class="tab-content">
                <div id="vfs-content">
                    <div class="loading">Loading VFS data...</div>
                </div>
            </div>
            
            <div id="vector" class="tab-content">
                <div id="vector-content">
                    <div class="loading">Loading vector store data...</div>
                </div>
            </div>
            
            <div id="kb" class="tab-content">
                <div id="kb-content">
                    <div class="loading">Loading knowledge base data...</div>
                </div>
            </div>
            
            <div id="analytics" class="tab-content">
                <div id="analytics-content">
                    <div class="loading">Loading analytics data...</div>
                </div>
            </div>
            
            <div id="files" class="tab-content">
                <div id="files-content">
                    <div class="loading">Loading file management interface...</div>
                </div>
            </div>
            
            <div id="settings" class="tab-content">
                <div id="settings-content">
                    <div class="loading">Loading settings...</div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Load modular JavaScript files in proper order -->
    <script src="/static/js/api-client.js"></script>
    <script src="/static/js/file_manager.js"></script>
    <script src="/static/js/dashboard-core.js"></script>
    <script src="/static/js/overview-tab.js"></script>
    <script src="/static/js/other-tabs.js"></script>
    <script src="/static/js/vfs-observatory.js"></script>
    
    <script>
        // Initialize dashboard after all modules loaded
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM loaded, initializing dashboard...');
            if (typeof refreshData !== 'undefined') {
                refreshData();
            } else {
                console.error('refreshData function not found');
            }
        });
    </script>
</body>
</html>"""


def get_dashboard_template():
    """
    Returns the modular dashboard template (same as enhanced version).
    """
    return get_enhanced_dashboard_template()


def get_legacy_dashboard_template():
    """
    DEPRECATED: Legacy function that previously provided a comprehensive HTML template 
    for the IPFS Kit dashboard with embedded JavaScript. This has been replaced by 
    the modular approach using external JavaScript files for better separation of concerns.
    
    This function is maintained for backward compatibility but should not be used 
    for new implementations.
    """
    logger.warning("get_legacy_dashboard_template() is deprecated. Use get_enhanced_dashboard_template() instead.")
    return get_enhanced_dashboard_template()
