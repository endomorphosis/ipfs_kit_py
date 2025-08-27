/**
 * MCP Dashboard JavaScript Module
 * Handles UI interactions and real-time updates for the MCP server dashboard
 */
class MCPDashboard {
    constructor() {
        this.currentTab = 'overview';
        this.eventSource = null;
        this.refreshInterval = 5000; // 5 seconds
        this.autoRefreshEnabled = true;
        
        this.initializeEventListeners();
        this.setupRealTimeUpdates();
    }

    initializeEventListeners() {
        // Tab navigation
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-tab]')) {
                e.preventDefault();
                this.switchTab(e.target.dataset.tab);
            }
        });

        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                this.autoRefreshEnabled = e.target.checked;
                if (this.autoRefreshEnabled) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }
    }

    setupRealTimeUpdates() {
        try {
            this.eventSource = mcpClient.createEventSource();
            this.eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleRealtimeUpdate(data);
            };
            this.eventSource.onerror = (error) => {
                console.warn('EventSource error, falling back to polling:', error);
                this.startAutoRefresh();
            };
        } catch (error) {
            console.warn('EventSource not available, using polling:', error);
            this.startAutoRefresh();
        }
    }

    handleRealtimeUpdate(data) {
        switch (data.type) {
            case 'daemon_status':
                this.updateDaemonStatus(data.payload);
                break;
            case 'tool_execution':
                this.updateToolStatus(data.payload);
                break;
            case 'bucket_changed':
                this.refreshBucketsList();
                break;
            case 'config_changed':
                this.refreshConfig();
                break;
            default:
                console.log('Unknown event type:', data.type);
        }
    }

    switchTab(tabName) {
        // Update active tab
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // Show/hide tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.style.display = 'none';
        });
        
        const tabContent = document.getElementById(`${tabName}-tab`);
        if (tabContent) {
            tabContent.style.display = 'block';
        }

        this.currentTab = tabName;
        this.loadTabContent(tabName);
    }

    async loadTabContent(tabName) {
        switch (tabName) {
            case 'overview':
                await this.loadOverviewTab();
                break;
            case 'mcp-tools':
                await this.loadMCPToolsTab();
                break;
            case 'virtual-filesystem':
                await this.loadVirtualFilesystemTab();
                break;
            case 'program-state':
                await this.loadProgramStateTab();
                break;
            case 'backends':
                await this.loadBackendsTab();
                break;
            case 'services':
                await this.loadServicesTab();
                break;
            case 'metrics':
                await this.loadMetricsTab();
                break;
            case 'health':
                await this.loadHealthTab();
                break;
        }
    }

    async loadOverviewTab() {
        try {
            const serverInfo = await mcpClient.getServerInfo();
            const metrics = await mcpClient.getMetrics();
            
            document.getElementById('server-status').innerHTML = this.renderServerStatus(serverInfo);
            document.getElementById('system-metrics').innerHTML = this.renderSystemMetrics(metrics);
        } catch (error) {
            console.error('Error loading overview:', error);
            this.showError('overview-tab', 'Failed to load overview data');
        }
    }

    async loadMCPToolsTab() {
        try {
            const tools = await mcpClient.listTools();
            document.getElementById('mcp-tools-list').innerHTML = this.renderMCPTools(tools);
        } catch (error) {
            console.error('Error loading MCP tools:', error);
            this.showError('mcp-tools-list', 'Failed to load MCP tools');
        }
    }

    async loadVirtualFilesystemTab() {
        try {
            const buckets = await mcpClient.listBuckets();
            document.getElementById('buckets-list').innerHTML = this.renderBuckets(buckets);
        } catch (error) {
            console.error('Error loading virtual filesystem:', error);
            this.showError('buckets-list', 'Failed to load virtual filesystem data');
        }
    }

    async loadProgramStateTab() {
        try {
            const config = await mcpClient.getConfig();
            document.getElementById('config-editor').innerHTML = this.renderConfigEditor(config);
        } catch (error) {
            console.error('Error loading program state:', error);
            this.showError('config-editor', 'Failed to load program state');
        }
    }

    async loadBackendsTab() {
        try {
            const backends = await mcpClient.listStorageBackends();
            document.getElementById('backends-list').innerHTML = this.renderBackends(backends);
        } catch (error) {
            console.error('Error loading backends:', error);
            this.showError('backends-list', 'Failed to load storage backends');
        }
    }

    async loadServicesTab() {
        try {
            const daemonStatus = await mcpClient.getDaemonStatus();
            document.getElementById('services-list').innerHTML = this.renderServices(daemonStatus);
        } catch (error) {
            console.error('Error loading services:', error);
            this.showError('services-list', 'Failed to load services');
        }
    }

    async loadMetricsTab() {
        try {
            const metrics = await mcpClient.getMetrics();
            document.getElementById('metrics-dashboard').innerHTML = this.renderMetrics(metrics);
        } catch (error) {
            console.error('Error loading metrics:', error);
            this.showError('metrics-dashboard', 'Failed to load metrics');
        }
    }

    async loadHealthTab() {
        try {
            const health = await mcpClient.getServerInfo();
            document.getElementById('health-status').innerHTML = this.renderHealth(health);
        } catch (error) {
            console.error('Error loading health:', error);
            this.showError('health-status', 'Failed to load health data');
        }
    }

    // Rendering methods for different components
    renderMCPTools(tools) {
        return `
            <div class="tools-header">
                <h3>Available MCP Tools</h3>
                <button class="btn btn-primary" onclick="dashboard.refreshMCPTools()">Refresh Tools</button>
            </div>
            <div class="tools-grid">
                ${tools.map(tool => `
                    <div class="tool-card">
                        <h4>${tool.name}</h4>
                        <p>${tool.description || 'No description available'}</p>
                        <div class="tool-actions">
                            <button class="btn btn-sm btn-info" onclick="dashboard.showToolInfo('${tool.name}')">Info</button>
                            <button class="btn btn-sm btn-success" onclick="dashboard.executeTool('${tool.name}')">Execute</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderBuckets(buckets) {
        return `
            <div class="buckets-header">
                <h3>Virtual Filesystem Buckets</h3>
                <button class="btn btn-primary" onclick="dashboard.showCreateBucketModal()">Create Bucket</button>
            </div>
            <div class="buckets-grid">
                ${buckets.map(bucket => `
                    <div class="bucket-card">
                        <h4>${bucket.name}</h4>
                        <span class="bucket-type badge">${bucket.type}</span>
                        <p>Items: ${bucket.item_count || 0}</p>
                        <p>Size: ${this.formatBytes(bucket.size || 0)}</p>
                        <div class="bucket-actions">
                            <button class="btn btn-sm btn-info" onclick="dashboard.viewBucketContents('${bucket.name}')">View</button>
                            <button class="btn btn-sm btn-warning" onclick="dashboard.manageBucket('${bucket.name}')">Manage</button>
                            <button class="btn btn-sm btn-danger" onclick="dashboard.deleteBucket('${bucket.name}')">Delete</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderConfigEditor(config) {
        return `
            <div class="config-header">
                <h3>Program State Configuration</h3>
                <span class="config-path">~/.ipfs-kit/</span>
            </div>
            <div class="config-files">
                ${Object.entries(config.files || {}).map(([filename, content]) => `
                    <div class="config-file">
                        <h4>${filename}</h4>
                        <textarea class="config-content" data-file="${filename}">${JSON.stringify(content, null, 2)}</textarea>
                        <div class="config-actions">
                            <button class="btn btn-sm btn-success" onclick="dashboard.saveConfigFile('${filename}')">Save</button>
                            <button class="btn btn-sm btn-secondary" onclick="dashboard.resetConfigFile('${filename}')">Reset</button>
                        </div>
                    </div>
                `).join('')}
            </div>
            <div class="daemon-controls">
                <h4>Daemon Management</h4>
                <div class="daemon-grid">
                    <div class="daemon-card">
                        <h5>File Indexer</h5>
                        <button class="btn btn-sm btn-primary" onclick="dashboard.runFileIndexing()">Run Indexing</button>
                    </div>
                    <div class="daemon-card">
                        <h5>Pin Synchronizer</h5>
                        <button class="btn btn-sm btn-primary" onclick="dashboard.syncPins()">Sync Pins</button>
                    </div>
                    <div class="daemon-card">
                        <h5>Garbage Collector</h5>
                        <button class="btn btn-sm btn-warning" onclick="dashboard.runGarbageCollection()">Run GC</button>
                    </div>
                </div>
            </div>
        `;
    }

    // Action methods
    async executeTool(toolName) {
        try {
            const result = await mcpClient.executeTool(toolName, {});
            this.showNotification(`Tool ${toolName} executed successfully`, 'success');
            console.log('Tool execution result:', result);
        } catch (error) {
            this.showNotification(`Failed to execute tool ${toolName}: ${error.message}`, 'error');
        }
    }

    async createBucket(name, type) {
        try {
            await mcpClient.createBucket(name, type);
            this.showNotification(`Bucket ${name} created successfully`, 'success');
            this.loadVirtualFilesystemTab();
        } catch (error) {
            this.showNotification(`Failed to create bucket: ${error.message}`, 'error');
        }
    }

    async saveConfigFile(filename) {
        try {
            const content = document.querySelector(`[data-file="${filename}"]`).value;
            await mcpClient.updateConfigFile(filename, JSON.parse(content));
            this.showNotification(`Configuration file ${filename} saved`, 'success');
        } catch (error) {
            this.showNotification(`Failed to save config file: ${error.message}`, 'error');
        }
    }

    async runFileIndexing() {
        try {
            const result = await mcpClient.indexFiles();
            this.showNotification('File indexing completed', 'success');
        } catch (error) {
            this.showNotification(`File indexing failed: ${error.message}`, 'error');
        }
    }

    async syncPins() {
        try {
            const result = await mcpClient.syncPins();
            this.showNotification('Pin synchronization completed', 'success');
        } catch (error) {
            this.showNotification(`Pin sync failed: ${error.message}`, 'error');
        }
    }

    async runGarbageCollection() {
        try {
            const result = await mcpClient.runGarbageCollection();
            this.showNotification('Garbage collection completed', 'success');
        } catch (error) {
            this.showNotification(`Garbage collection failed: ${error.message}`, 'error');
        }
    }

    // Utility methods
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    showError(containerId, message) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `<div class="error-message">${message}</div>`;
        }
    }

    startAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        this.refreshTimer = setInterval(() => {
            if (this.autoRefreshEnabled) {
                this.loadTabContent(this.currentTab);
            }
        }, this.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new MCPDashboard();
});