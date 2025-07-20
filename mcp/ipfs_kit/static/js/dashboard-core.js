/**
 * Core Dashboard Functionality
 */

// Define dashboardAPI object for centralized API calls
const dashboardAPI = {
    fetch: async (url, options = {}) => {
        try {
            console.log(`dashboardAPI: Fetching ${url} with options:`, options);
            const response = await fetch(url, options);
            console.log(`dashboardAPI: Received response for ${url}. Status: ${response.status}, OK: ${response.ok}`);
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`dashboardAPI: HTTP error for ${url}! Status: ${response.status}, Message: ${errorText}`);
                throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
            }
            const jsonData = await response.json();
            console.log(`dashboardAPI: Received JSON data for ${url}:`, jsonData);
            return jsonData;
        } catch (error) {
            console.error(`dashboardAPI: API call to ${url} failed:`, error);
            throw error;
        }
    }
};

// Global variables
let currentTab = 'overview';
let autoRefreshInterval = null;
let currentBackendData = {};
let backendConfigCache = {};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded: Initializing dashboard...');
    initializeExpandables();
    refreshData();
    // Initialize file manager if available
    if (typeof fileManager !== 'undefined' && fileManager.init) {
        fileManager.init();
    }
});

// Tab switching
function showTab(tabName, event) {
    console.log('showTab: Switching to tab:', tabName);
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab
    const selectedTab = document.getElementById(tabName);
    const selectedButton = event ? event.target : document.querySelector(`[onclick*="${tabName}"]`);
    
    if (selectedTab) {
        selectedTab.classList.add('active');
        currentTab = tabName;
    }
    
    if (selectedButton) {
        selectedButton.classList.add('active');
    }
    
    // Load tab-specific data
    switch(tabName) {
        case 'overview':
            refreshData();
            break;
        case 'monitoring':
            if (typeof refreshMonitoring === 'function') refreshMonitoring();
            break;
        case 'vfs':
        case 'vfs-observatory':
            if (typeof loadVFSTab === 'function') loadVFSTab();
            break;
        case 'vector-kb':
            if (typeof loadVectorKBTab === 'function') loadVectorKBTab();
            break;
        case 'file-manager':
            if (typeof fileManager !== 'undefined' && fileManager.refresh) {
                fileManager.refresh();
            } else if (typeof loadFileManagerTab === 'function') {
                loadFileManagerTab();
            }
            break;
        case 'backends':
            if (typeof loadBackendsTab === 'function') loadBackendsTab();
            break;
        case 'configuration':
            if (typeof loadConfigurationTab === 'function') loadConfigurationTab();
            break;
    }
}

// Auto-refresh functionality
function startAutoRefresh() {
    console.log('startAutoRefresh: Starting auto-refresh...');
    if (autoRefreshInterval) clearInterval(autoRefreshInterval);
    autoRefreshInterval = setInterval(() => {
        if (currentTab === 'overview') {
            refreshData();
        } else if (currentTab === 'monitoring') {
            if (typeof refreshMonitoring === 'function') refreshMonitoring();
        }
    }, 30000); // Refresh every 30 seconds
}

function stopAutoRefresh() {
    console.log('stopAutoRefresh: Stopping auto-refresh...');
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// Initialize expandable sections
function initializeExpandables() {
    console.log('initializeExpandables: Initializing expandable sections...');
    document.querySelectorAll('.expandable').forEach(item => {
        const header = item.querySelector('.expandable-header');
        if (header) {
            header.addEventListener('click', () => {
                item.classList.toggle('expanded');
            });
        }
    });
}

// Utility functions
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

function formatTimestamp(timestamp) {
    return new Date(timestamp).toLocaleString();
}

// Start auto-refresh on load
startAutoRefresh();

async function refreshData() {
    console.log('refreshData: Fetching /api/health...');
    try {
        const responseData = await dashboardAPI.fetch('/api/health');
        console.log('refreshData: Received responseData:', responseData);
        updateDashboard(responseData); // Pass the entire responseData
    } catch (error) {
        console.error('refreshData: Error refreshing data:', error);
    }
}

function updateDashboard(data) {
    console.log('updateDashboard: Updating dashboard with data:', data);
    // Update system status
    const systemStatusElement = document.getElementById('systemStatus');
    if (systemStatusElement) {
        console.log('updateDashboard: #systemStatus element found. Current innerHTML:', systemStatusElement.innerHTML);
        systemStatusElement.innerHTML = `
            <div class="connection-status">
                <div class="connection-indicator ${data.status === 'running' ? 'connected' : ''}"></div>
                <span>Status: ${data.status || 'unknown'}</span>
            </div>
            <p><strong>Uptime:</strong> ${data.uptime_seconds ? `${Math.floor(data.uptime_seconds / 3600)}h ${Math.floor((data.uptime_seconds % 3600) / 60)}m` : 'N/A'}</p>
            <p><strong>Components:</strong> ${Object.values(data.components || {}).filter(Boolean).length}/${Object.keys(data.components || {}).length} active</p>
        `;
        console.log('updateDashboard: systemStatusElement updated. New innerHTML:', systemStatusElement.innerHTML);
    } else {
        console.error('updateDashboard: #systemStatus element not found.');
    }
    
    // Update backend summary
    const backendSummaryElement = document.getElementById('backendSummary');
    if (backendSummaryElement) {
        console.log('updateDashboard: #backendSummary element found. Current innerHTML:', backendSummaryElement.innerHTML);
        const backends = data.backend_health.backends || {}; // Access backends from backend_health.backends
        const healthyCount = Object.values(backends).filter(b => b.health === 'healthy').length;
        const totalCount = Object.keys(backends).length;
        const progressPercent = totalCount > 0 ? (healthyCount / totalCount) * 100 : 0;
        
        backendSummaryElement.innerHTML = `
            <div style="font-size: 24px; font-weight: bold; color: ${healthyCount === totalCount ? '#4CAF50' : '#f44336'};
">
                ${healthyCount}/${totalCount}
            </div>
            <p>Backends Healthy</p>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progressPercent}%"></div>
            </div>
            <div style="font-size: 12px; color: #6c757d;">Health Score: ${progressPercent.toFixed(1)}%</div>
        `;
        console.log('updateDashboard: backendSummaryElement updated. New innerHTML:', backendSummaryElement.innerHTML);
    } else {
        console.error('updateDashboard: #backendSummary element not found.');
    }
    
    // Update performance metrics
    const performanceMetricsElement = document.getElementById('performanceMetrics');
    if (performanceMetricsElement) {
        console.log('updateDashboard: #performanceMetrics element found. Current innerHTML:', performanceMetricsElement.innerHTML);
        performanceMetricsElement.innerHTML = `
            <div><strong>Memory:</strong> ${data.memory_usage_mb || 'N/A'}MB</div>
            <div><strong>CPU:</strong> ${data.cpu_usage_percent || 'N/A'}%</div>
            <div><strong>Active Backends:</strong> ${Object.values(data.backend_health.backends || {}).filter(b => b.status === 'running').length}</div>
            <div><strong>Last Update:</strong> ${new Date().toLocaleTimeString()}</div>
        `;
        console.log('updateDashboard: performanceMetricsElement updated. New innerHTML:', performanceMetricsElement.innerHTML);
    } else {
        console.error('updateDashboard: #performanceMetrics element not found.');
    }
    
    // Update backend grid
    updateBackendGrid(data.backend_health.backends || {});

    // Also update the VFS and Vector/KB tabs if they are active
    if (document.getElementById('vfs').classList.contains('active')) {
        loadVFSTab();
    }
    if (document.getElementById('vector-kb').classList.contains('active')) {
        loadVectorKBTab();
    }
}

function updateBackendGrid(backends) {
    console.log('updateBackendGrid: Updating backend grid with backends:', backends);
    const grid = document.getElementById('backendGrid');
    if (!grid) {
        console.error('updateBackendGrid: #backendGrid element not found.');
        return;
    }
    grid.innerHTML = '';
    
    for (const [name, backend] of Object.entries(backends)) {
        const card = document.createElement('div');
        card.className = `backend-card ${backend.health}`;
        
        // Create verbose metrics display
        let verboseMetricsHTML = createVerboseMetricsHTML(backend);
        
        let errorsHTML = '';
        if (backend.errors && backend.errors.length > 0) {
            errorsHTML = `
                <div class="expandable">
                    <div class="expandable-header">Recent Errors (${backend.errors.length})</div>
                    <div class="expandable-content">
                        <div class="error-log">
                            ${backend.errors.slice(-5).map(error => 
                                `<div><strong>${new Date(error.timestamp).toLocaleString()}:</strong> ${error.error}</div>`
                            ).join('')}
                        </div>
                    </div>
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="backend-header">
                <div>
                    <h3>${backend.name}</h3>
                    <div class="status-badge status-${backend.health}">${backend.health}</div>
                    <div class="status-badge status-${backend.status === 'running' ? 'healthy' : 'unknown'}">${backend.status}</div>
                </div>
                <div class="backend-actions">
                    <button class="action-btn config" onclick="openConfigModal('${name}')">⚙️ Config</button>
                    ${['ipfs', 'ipfs_cluster', 'ipfs_cluster_follow', 'lotus'].includes(name) ? 
                                `<button class="action-btn restart" onclick="restartBackend('${name}')">🔄 Restart</button>` : ''}
                    <button class="action-btn logs" onclick="openLogsModal('${name}')">📋 Logs</button>
                </div>
            </div>
            <p><strong>Last Check:</strong> ${backend.last_check ? new Date(backend.last_check).toLocaleString() : 'Never'}</p>
            ${verboseMetricsHTML}
            ${errorsHTML}
        `;
        
        grid.appendChild(card);
    }
    
    // Add click handlers for expandable sections
    document.querySelectorAll('.expandable-header').forEach(header => {
        header.onclick = () => {
            header.parentElement.classList.toggle('expanded');
        };
    });
    console.log('updateBackendGrid: Backend grid updated.');
}

function createVerboseMetricsHTML(backend) {
    if (!backend.metrics || Object.keys(backend.metrics).length === 0) {
        return '<div class="verbose-metrics"><em>No metrics available</em></div>';
    }
    
    let html = '<div class="verbose-metrics">';
    
    // Group metrics by category
    const groupedMetrics = groupMetricsByCategory(backend.metrics);
    
    for (const [category, metrics] of Object.entries(groupedMetrics)) {
        html += `
            <div class="metrics-section">
                <h4>${category}</h4>
                <table class="metrics-table">
        `;
        
        for (const [key, value] of Object.entries(metrics)) {
            const displayValue = formatMetricValue(value);
            html += `
                <tr>
                    <td>${formatMetricKey(key)}</td>
                    <td class="value">${displayValue}</td>
                </tr>
            `;
        }
        
        html += '</table></div>';
    }
    
    html += '</div>';
    return html;
}

function groupMetricsByCategory(metrics) {
    const groups = {
        'Connection': {},
        'Performance': {},
        'Storage': {},
        'Process': {},
        'Network': {},
        'Configuration': {},
        'Other': {}
    };
    
    for (const [key, value] of Object.entries(metrics)) {
        const lowerKey = key.toLowerCase();
        
        if (lowerKey.includes('version') || lowerKey.includes('commit') || lowerKey.includes('build')) {
            groups['Configuration'][key] = value;
        } else if (lowerKey.includes('pid') || lowerKey.includes('process') || lowerKey.includes('daemon')) {
            groups['Process'][key] = value;
        } else if (lowerKey.includes('size') || lowerKey.includes('storage') || lowerKey.includes('repo') || lowerKey.includes('objects')) {
            groups['Storage'][key] = value;
        } else if (lowerKey.includes('peer') || lowerKey.includes('endpoint') || lowerKey.includes('connection')) {
            groups['Network'][key] = value;
        } else if (lowerKey.includes('time') || lowerKey.includes('response') || lowerKey.includes('latency')) {
            groups['Performance'][key] = value;
        } else if (lowerKey.includes('connected') || lowerKey.includes('running') || lowerKey.includes('available')) {
            groups['Connection'][key] = value;
        } else {
            groups['Other'][key] = value;
        }
    }
    
    // Remove empty groups
    return Object.fromEntries(Object.entries(groups).filter(([_, metrics]) => Object.keys(metrics).length > 0));
}

function formatMetricKey(key) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function formatMetricValue(value) {
    if (typeof value === 'boolean') {
        return `<span style="color: ${value ? '#28a745' : '#dc3545'}">${value ? '✓' : '✗'}</span>`;
    } else if (typeof value === 'number') {
        if (value > 1000000) {
            return `${(value / 1000000).toFixed(2)}M`;
        } else if (value > 1000) {
            return `${(value / 1000).toFixed(2)}K`;
        }
        return value.toString();
    } else if (typeof value === 'string' && (value.startsWith('http') || value.startsWith('/'))) {
        return `<a href="${value}" target="_blank" style="color: #007bff;">${value.length > 50 ? value.substring(0, 47) + '...' : value}</a>`;
    } else if (typeof value === 'object') {
        return `<pre style="margin: 0; font-size: 11px;">${JSON.stringify(value, null, 2)}</pre>`;
    } else if (typeof value === 'string' && value.length > 50) {
        return `<span title="${value}">${value.substring(0, 47)}...</span>`;
    }
    return value.toString();
}

async function loadConfigurationTab() {
    console.log('loadConfigurationTab: Loading configuration tab...');
    // Load package configuration
    await loadPackageConfig();
    
    const configList = document.getElementById('configBackendList');
    if (!configList) {
        console.error('loadConfigurationTab: #configBackendList element not found.');
        return;
    }
    configList.innerHTML = '<div style="text-align: center; padding: 20px;">Loading backend configurations...</div>';
    
    try {
        const response = await dashboardAPI.fetch('/api/backends');
        const backends = response; // Assuming response is directly the backends object
        currentBackendData = backends; // Update backend data
        configList.innerHTML = ''; // Clear loading message

        for (const [name, backend] of Object.entries(currentBackendData)) {
            const configCard = document.createElement('div');
            configCard.className = 'stat-card';
            configCard.style.cursor = 'pointer';
            configCard.onclick = () => openConfigModal(name);
            
            let configPreview = 'Click to configure';
            if (backend.config) {
                const keys = Object.keys(backend.config);
                if (keys.length > 0) {
                    configPreview = `${keys.length} config sections: ${keys.slice(0, 3).join(', ')}...`;
                } else {
                    configPreview = 'No configuration available';
                }
            }

            configCard.innerHTML = `
                <h4>${backend.name}</h4>
                <div class="status-badge status-${backend.health}">${backend.health}</div>
                <p style="font-size: 0.9em; color: #6c757d; margin: 8px 0;">${configPreview}</p>
            `;
            
            configList.appendChild(configCard);
        }
        console.log('loadConfigurationTab: Backend configurations loaded.');
    } catch (error) {
        console.error('loadConfigurationTab: Error loading configurations:', error);
        configList.innerHTML = `<div style="color: red; padding: 20px;">Error loading configurations: ${error.message}</div>`;
    }
}

async function loadLogsTab() {
    console.log('loadLogsTab: Loading logs tab...');
    try {
        const data = await dashboardAPI.fetch('/api/logs');
        console.log('loadLogsTab: Received logs data:', data);
        const logs = data.logs.join('');
        const logViewerElement = document.getElementById('logViewer');
        if (logViewerElement) {
            logViewerElement.textContent = logs;
            console.log('loadLogsTab: Log viewer updated.');
        } else {
            console.error('loadLogsTab: #logViewer element not found.');
        }
    } catch (error) {
        console.error('loadLogsTab: Error loading logs:', error);
        const logViewerElement = document.getElementById('logViewer');
        if (logViewerElement) {
            logViewerElement.textContent = `Error loading logs: ${error.message}`;
        }
    }
}

async function loadVFSTab() {
    console.log('loadVFSTab: Loading VFS tab...');
    try {
        const responseData = await dashboardAPI.fetch('/api/vfs/statistics');
        console.log('loadVFSTab: Received VFS statistics responseData:', responseData);

        if (responseData.success) {
            const statsData = responseData.data;  // Extract the actual data
            document.getElementById('cachePerformance').innerHTML = formatCachePerformance(statsData.cache_performance || {});
            document.getElementById('filesystemStatus').innerHTML = formatFilesystemStatus(statsData.filesystem_metrics || {});
            document.getElementById('accessPatterns').innerHTML = formatAccessPatterns(statsData.access_patterns || {});
            document.getElementById('resourceUsage').innerHTML = formatResourceUsage(statsData.resource_utilization || {});
            document.getElementById('tieredCacheDetails').innerHTML = formatTieredCacheDetails(statsData.cache_performance || {});
            document.getElementById('hotContentAnalysis').innerHTML = formatHotContentAnalysis(statsData.access_patterns || {});
            console.log('loadVFSTab: VFS tab updated.');
        } else {
            throw new Error(responseData.error || 'Failed to load VFS statistics');
        }
    } catch (error) {
        console.error('loadVFSTab: Error loading VFS data:', error);
        document.getElementById('vfs').querySelectorAll('.stat-card div, .expandable-content').forEach(el => {
            el.innerHTML = `<span style="color: red;">Error: ${error.message}</span>`;
        });
    }
}

async function loadVectorKBTab() {
    console.log('loadVectorKBTab: Loading Vector/KB tab...');
    try {
        const vectorResponseData = await dashboardAPI.fetch('/api/vfs/vector-index');
        if (!vectorResponseData.success) throw new Error(vectorResponseData.error || 'Failed to load vector index status');
        const vectorData = vectorResponseData.data;
        console.log('loadVectorKBTab: Received vector index data:', vectorData);

        const kbResponseData = await dashboardAPI.fetch('/api/vfs/knowledge-base');
        if (!kbResponseData.success) throw new Error(kbResponseData.error || 'Failed to load knowledge base status');
        const kbData = kbResponseData.data;
        console.log('loadVectorKBTab: Received knowledge base data:', kbData);

        const cacheResponseData = await dashboardAPI.fetch('/api/vfs/cache');
        if (!cacheResponseData.success) throw new Error(cacheResponseData.error || 'Failed to load cache status');
        const cacheData = cacheResponseData.data;
        console.log('loadVectorKBTab: Received cache data:', cacheData);

        document.getElementById('vectorIndexStatus').innerHTML = formatVectorIndexStatus(vectorData || {});
        document.getElementById('knowledgeGraphStatus').innerHTML = formatKnowledgeGraphStatus(kbData || {});
        document.getElementById('searchPerformance').innerHTML = formatSearchPerformance(vectorData.search_performance || {});
        document.getElementById('contentDistribution').innerHTML = formatContentDistribution(vectorData.content_distribution || {});
        document.getElementById('vectorIndexDetails').innerHTML = formatVectorIndexDetails(vectorData || {});
        document.getElementById('knowledgeBaseAnalytics').innerHTML = formatKnowledgeBaseAnalytics(kbData || {});
        document.getElementById('semanticCachePerformance').innerHTML = formatSemanticCachePerformance(cacheData.semantic_cache || {});
        console.log('loadVectorKBTab: Vector/KB tab updated.');
        
    } catch (error) {
        console.error('loadVectorKBTab: Error loading Vector/KB data:', error);
        document.getElementById('vector-kb').querySelectorAll('.stat-card div, .expandable-content').forEach(el => {
            el.innerHTML = `<span style="color: red;">Error: ${error.message}</span>`;
        });
    }
}

async function openConfigModal(backendName) {
    console.log('openConfigModal: Opening config modal for backend:', backendName);
    const modal = document.getElementById('configModal');
    const title = document.getElementById('configModalTitle');
    const content = document.getElementById('configModalContent');
    
    title.textContent = `Configure ${backendName}`;
    content.innerHTML = '<div style="text-align: center; padding: 20px;">Loading configuration...</div>';
    modal.style.display = 'block';
    
    try {
        const configData = await dashboardAPI.fetch(`/api/backends/${backendName}/config`);
        console.log('openConfigModal: Received config data:', configData);
        
        backendConfigCache[backendName] = configData.config || {};
        
        content.innerHTML = createConfigForm(backendName);

        // Add click handlers for expandable sections inside the modal
        content.querySelectorAll('.expandable-header').forEach(header => {
            header.onclick = () => {
                header.parentElement.classList.toggle('expanded');
            };
        });
        console.log('openConfigModal: Config modal content updated.');

    } catch (error) {
        console.error('openConfigModal: Error loading configuration:', error);
        content.innerHTML = `<div style="color: red; padding: 20px;">Error loading configuration: ${error.message}</div>`;
    }
}

function closeConfigModal() {
    console.log('closeConfigModal: Closing config modal.');
    document.getElementById('configModal').style.display = 'none';
}

async function openLogsModal(backendName) {
    console.log('openLogsModal: Opening logs modal for backend:', backendName);
    const modal = document.getElementById('logsModal');
    const title = document.getElementById('logsModalTitle');
    const content = document.getElementById('logsModalContent');
    
    title.textContent = `${backendName} Logs`;
    content.innerHTML = `<div class="log-viewer">Loading logs for ${backendName}...</div>`;
    modal.style.display = 'block';
    
    try {
        const data = await dashboardAPI.fetch(`/api/backends/${backendName}/logs`);
        console.log('openLogsModal: Received logs data:', data);
        const logViewerElement = content.querySelector('.log-viewer');
        if (logViewerElement) {
            logViewerElement.textContent = data.logs.join('');
            console.log('openLogsModal: Logs modal content updated.');
        } else {
            console.error('openLogsModal: Log viewer element not found in modal.');
        }
    } catch (error) {
        console.error('openLogsModal: Error loading logs:', error);
        const logViewerElement = content.querySelector('.log-viewer');
        if (logViewerElement) {
            logViewerElement.textContent = `Error loading logs: ${error.message}`;
        }
    }
}

function closeLogsModal() {
    console.log('closeLogsModal: Closing logs modal.');
    document.getElementById('logsModal').style.display = 'none';
}

function createConfigForm(backendName) {
    console.log('createConfigForm: Creating config form for backend:', backendName);
    const configs = getBackendConfigOptions(backendName);
    
    let formHTML = `<form onsubmit="saveBackendConfig('${backendName}', event)">`;
    
    for (const [section, fields] of Object.entries(configs)) {
        formHTML += `
            <div class="expandable expanded">
                <div class="expandable-header">${section}</div>
                <div class="expandable-content">
        `;
        
        for (const field of fields) {
            formHTML += createFormField(field, backendName);
        }
        
        formHTML += '</div></div>';
    }
    
    const rawConfig = backendConfigCache[backendName] || {};
    formHTML += `
        <div class="expandable">
            <div class="expandable-header">Raw Configuration (Advanced)</div>
            <div class="expandable-content">
                <div class="form-group">
                    <label>Complete Backend Configuration (JSON)</label>
                    <textarea name="raw_config" style="min-height: 200px; font-family: monospace; font-size: 12px;" readonly>${JSON.stringify(rawConfig, null, 2)}</textarea>
                    <small style="color: #6c757d;">This shows the complete backend configuration. Use the fields above to modify specific settings.</small>
                </div>
            </div>
        </div>
    `;
    
    formHTML += `
        <div style="margin-top: 20px; text-align: right;">
            <button type="button" class="btn btn-secondary" onclick="closeConfigModal()">Cancel</button>
            <button type="submit" class="btn btn-primary">Save Configuration</button>
        </div>
    </form>`;
    
    console.log('createConfigForm: Config form HTML generated.');
    return formHTML;
}

function getBackendConfigOptions(backendName) {
    const configs = {
        'ipfs': {
            'Connection': [
                { name: 'Addresses.API', label: 'API Address', type: 'text', value: '/ip4/127.0.0.1/tcp/5001', description: 'IPFS API multiaddr' },
                { name: 'Addresses.Gateway', label: 'Gateway Address', type: 'text', value: '/ip4/127.0.0.1/tcp/8080', description: 'IPFS Gateway multiaddr' },
                { name: 'Identity.PeerID', label: 'Peer ID', type: 'text', value: '', description: 'IPFS node peer ID (read-only)', readonly: true }
            ],
            'Storage': [
                { name: 'Datastore.StorageMax', label: 'Storage Max', type: 'text', value: '10GB', description: 'Maximum storage size' },
                { name: 'Datastore.GCPeriod', label: 'GC Period', type: 'text', value: '1h', description: 'Garbage collection period' },
                { name: 'Datastore.StorageGCWatermark', label: 'GC Watermark (%)', type: 'number', value: '90', description: 'Storage threshold for GC' }
            ],
            'Network': [
                { name: 'Discovery.MDNS.Enabled', label: 'Enable mDNS', type: 'checkbox', value: 'true', description: 'Enable local network discovery' },
                { name: 'Swarm.DisableBandwidthMetrics', label: 'Disable Bandwidth Metrics', type: 'checkbox', value: 'false', description: 'Disable bandwidth tracking' }
            ]
        },
        'lotus': {
            'Network': [
                { name: 'network', label: 'Network', type: 'select', options: ['mainnet', 'calibnet', 'testnet'], value: 'calibnet', description: 'Filecoin network to connect to' },
                { name: 'api_port', label: 'API Port', type: 'number', value: '1234', description: 'Lotus API port' },
                { name: 'enable_splitstore', label: 'Enable Splitstore', type: 'checkbox', value: 'false', description: 'Enable splitstore for better performance' }
            ],
            'Authentication': [
                { name: 'api_token', label: 'API Token', type: 'password', value: '', description: 'Lotus API authentication token' },
                { name: 'jwt_secret', label: 'JWT Secret', type: 'password', value: '', description: 'JWT secret for API authentication' }
            ],
            'Performance': [
                { name: 'max_peers', label: 'Max Peers', type: 'number', value: '100', description: 'Maximum number of peers' },
                { name: 'bootstrap', label: 'Enable Bootstrap', type: 'checkbox', value: 'true', description: 'Enable bootstrap nodes' }
            ]
        },
        'storacha': {
            'Authentication': [
                { name: 'api_token', label: 'API Token', type: 'password', value: '', description: 'Storacha API token' },
                { name: 'space_did', label: 'Space DID', type: 'text', value: '', description: 'Storacha space identifier' },
                { name: 'private_key', label: 'Private Key', type: 'password', value: '', description: 'Private key for signing' }
            ],
            'Endpoints': [
                { name: 'primary_endpoint', label: 'Primary Endpoint', type: 'url', value: 'https://up.storacha.network/bridge', description: 'Primary Storacha endpoint' },
                { name: 'backup_endpoints', label: 'Backup Endpoints', type: 'textarea', value: 'https://api.web3.storage\nhttps://up.web3.storage/bridge', description: 'Backup endpoints (one per line)' }
            ]
        },
        'synapse': {
            'Authentication': [
                { name: 'private_key', label: 'Private Key', type: 'password', value: '', description: 'Synapse private key for signing' },
                { name: 'wallet_address', label: 'Wallet Address', type: 'text', value: '', description: 'Wallet address for transactions' }
            ],
            'Network': [
                { name: 'network', label: 'Network', type: 'select', options: ['mainnet', 'calibration', 'testnet'], value: 'calibration', description: 'Filecoin network' },
                { name: 'rpc_endpoint', label: 'RPC Endpoint', type: 'url', value: '', description: 'Custom RPC endpoint (optional)' }
            ],
            'Configuration': [
                { name: 'max_file_size', label: 'Max File Size (MB)', type: 'number', value: '100', description: 'Maximum file size for uploads' },
                { name: 'chunk_size', label: 'Chunk Size (MB)', type: 'number', value: '10', description: 'Chunk size for large files' }
            ]
        },
        'huggingface': {
            'Authentication': [
                { name: 'token', label: 'HF Token', type: 'password', value: '', description: 'HuggingFace Hub token' },
                { name: 'username', label: 'Username', type: 'text', value: '', description: 'HuggingFace username' }
            ],
            'Configuration': [
                { name: 'cache_dir', label: 'Cache Directory', type: 'text', value: '~/.cache/huggingface', description: 'Local cache directory' },
                { name: 'default_model', label: 'Default Model', type: 'text', value: 'sentence-transformers/all-MiniLM-L6-v2', description: 'Default embedding model' }
            ]
        },
        's3': {
            'Credentials': [
                { name: 'access_key_id', label: 'Access Key ID', type: 'text', value: '', description: 'AWS Access Key ID' },
                { name: 'secret_access_key', label: 'Secret Access Key', type: 'password', value: '', description: 'AWS Secret Access Key' },
                { name: 'session_token', label: 'Session Token', type: 'password', value: '', description: 'AWS Session Token (optional)' }
            ],
            'Configuration': [
                { name: 'region', label: 'Region', type: 'text', value: 'us-east-1', description: 'AWS region' },
                { name: 'endpoint_url', label: 'Endpoint URL', type: 'url', value: '', description: 'Custom S3-compatible endpoint' },
                { name: 'bucket', label: 'Default Bucket', type: 'text', value: '', description: 'Default S3 bucket' }
            ]
        },
        'ipfs_cluster': {
            'Connection': [
                { name: 'api_endpoint', label: 'API Endpoint', type: 'url', value: 'http://127.0.0.1:9094', description: 'IPFS Cluster API endpoint' },
                { name: 'proxy_endpoint', label: 'Proxy Endpoint', type: 'url', value: 'http://127.0.0.1:9095', description: 'IPFS Cluster proxy endpoint' }
            ],
            'Authentication': [
                { name: 'basic_auth_user', label: 'Basic Auth User', type: 'text', value: '', description: 'Basic auth username' },
                { name: 'basic_auth_pass', label: 'Basic Auth Password', type: 'password', value: '', description: 'Basic auth password' }
            ],
            'Configuration': [
                { name: 'replication_factor', label: 'Replication Factor', type: 'number', value: '1', description: 'Number of replicas' },
                { name: 'consensus', label: 'Consensus', type: 'select', options: ['raft', 'crdt'], value: 'raft', description: 'Consensus mechanism' }
            ]
        }
    };
    
    return configs[backendName] || { 'General': [{ name: 'config', label: 'Configuration', type: 'textarea', value: '{}', description: 'Raw configuration (JSON)' }] };
}

function createFormField(field, backendName) {
    let input = '';
    const currentValue = getCurrentConfigValue(backendName, field.name) || field.value || '';
    const readonly = field.readonly ? 'readonly' : '';
    
    switch (field.type) {
        case 'select':
            input = `<select name="${field.name}" ${readonly} class="form-control">`;
            for (const option of field.options) {
                input += `<option value="${option}" ${currentValue === option ? 'selected' : ''}>${option}</option>`;
            }
            input += '</select>';
            break;
        case 'checkbox':
            input = `<input type="checkbox" name="${field.name}" ${String(currentValue) === 'true' ? 'checked' : ''} ${readonly}>`;
            break;
        case 'textarea':
            input = `<textarea name="${field.name}" placeholder="${field.description || ''}" ${readonly} class="form-control">${currentValue}</textarea>`;
            break;
        default:
            input = `<input type="${field.type}" name="${field.name}" value="${currentValue}" placeholder="${field.description || ''}" ${readonly} class="form-control">`;
    }
    
    return `
        <div class="form-group">
            <label>${field.label}</label>
            ${input}
            ${field.description ? `<small style="color: #6c757d;">${field.description}</small>` : ''}
        </div>
    `;
}

function getCurrentConfigValue(backendName, fieldName) {
    if (backendConfigCache[backendName]) {
        return getNestedValue(backendConfigCache[backendName], fieldName);
    }
    return '';
}

function getNestedValue(obj, path) {
    const keys = path.split('.');
    let value = obj;
    for (const key of keys) {
        if (value && typeof value === 'object' && key in value) {
            value = value[key];
        } else {
            return undefined;
        }
    }
    return value;
}

async function saveBackendConfig(backendName, event) {
    event.preventDefault();
    console.log('saveBackendConfig: Saving config for backend:', backendName);
    const form = event.target;
    const formData = new FormData(form);
    const newConfig = Object.fromEntries(formData.entries());
    
    try {
        const response = await dashboardAPI.fetch(`/api/backends/${backendName}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newConfig)
        });
        
        if (response.ok) {
            alert('Configuration saved successfully!');
            closeConfigModal();
            refreshData();
            console.log('saveBackendConfig: Configuration saved successfully.');
        } else {
            const errorData = await response.json();
            alert(`Error saving configuration: ${errorData.error || response.statusText}`);
            console.error('saveBackendConfig: Error saving configuration:', errorData);
        }
    } catch (error) {
        alert(`Error saving configuration: ${error.message}`);
        console.error('saveBackendConfig: Error saving configuration (fetch failed):', error);
    }
}

async function restartBackend(backendName) {
    console.log('restartBackend: Restarting backend:', backendName);
    if (confirm(`Are you sure you want to restart ${backendName}?`)) {
        try {
            const response = await dashboardAPI.fetch(`/api/backends/${backendName}/restart`, { method: 'POST' });
            if (response.ok) {
                alert(`${backendName} restart initiated.`);
                setTimeout(refreshData, 2000); // Refresh after a delay
                console.log('restartBackend: Restart initiated successfully.');
            } else {
                const errorData = await response.json();
                alert(`Error restarting backend: ${errorData.error || response.statusText}`);
                console.error('restartBackend: Error restarting backend:', errorData);
            }
        } catch (error) {
            alert(`Error restarting backend: ${error.message}`);
            console.error('restartBackend: Error restarting backend (fetch failed):', error);
        }
    }
}

async function loadPackageConfig() {
    console.log('loadPackageConfig: Loading package configuration...');
    try {
        const data = await dashboardAPI.fetch('/api/config/package');
        console.log('loadPackageConfig: Received package config data:', data);
        
        if (data.success && data.config) {
            const config = data.config;
            
            // System Settings
            document.getElementById('system-log-level').value = config.system?.log_level || 'INFO';
            document.getElementById('system-max-workers').value = config.system?.max_workers || 4;
            document.getElementById('system-cache-size').value = config.system?.cache_size || 1000;
            document.getElementById('system-data-dir').value = config.system?.data_directory || '/tmp/ipfs_kit';
            
            // VFS Settings
            document.getElementById('vfs-cache-enabled').checked = config.vfs?.cache_enabled || true;
            document.getElementById('vfs-cache-max-size').value = config.vfs?.cache_max_size || '10GB';
            document.getElementById('vfs-vector-dimensions').value = config.vfs?.vector_dimensions || 384;
            document.getElementById('vfs-kb-max-nodes').value = config.vfs?.knowledge_base_max_nodes || 10000;
            
            // Observability Settings
            document.getElementById('obs-metrics-enabled').checked = config.observability?.metrics_enabled || true;
            document.getElementById('obs-prometheus-port').value = config.observability?.prometheus_port || 9090;
            document.getElementById('obs-dashboard-enabled').checked = config.observability?.dashboard_enabled || true;
            document.getElementById('obs-health-check-interval').value = config.observability?.health_check_interval || 30;
            console.log('loadPackageConfig: Package configuration updated in form.');
        }
    } catch (error) {
        console.error('loadPackageConfig: Error loading package configuration:', error);
    }
}

async function savePackageConfig() {
    console.log('savePackageConfig: Saving package configuration...');
    const config = {
        system: {
            log_level: document.getElementById('system-log-level').value,
            max_workers: parseInt(document.getElementById('system-max-workers').value, 10),
            cache_size: document.getElementById('system-cache-size').value,
            data_directory: document.getElementById('system-data-dir').value
        },
        vfs: {
            cache_enabled: document.getElementById('vfs-cache-enabled').checked,
            cache_max_size: document.getElementById('vfs-cache-max-size').value,
            vector_dimensions: parseInt(document.getElementById('vfs-vector-dimensions').value, 10),
            knowledge_base_max_nodes: parseInt(document.getElementById('vfs-kb-max-nodes').value, 10)
        },
        observability: {
            metrics_enabled: document.getElementById('obs-metrics-enabled').checked,
            prometheus_port: parseInt(document.getElementById('obs-prometheus-port').value, 10),
            dashboard_enabled: document.getElementById('obs-dashboard-enabled').checked,
            health_check_interval: parseInt(document.getElementById('obs-health-check-interval').value, 10)
        }
    };
    
    try {
        const response = await dashboardAPI.fetch('/api/config/package', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            alert('Configuration saved successfully!');
            console.log('savePackageConfig: Package configuration saved successfully.');
        } else {
            const errorData = await response.json();
            alert(`Error saving configuration: ${errorData.error || response.statusText}`);
            console.error('savePackageConfig: Error saving configuration:', errorData);
        }
    } catch (error) {
        alert(`Error saving configuration: ${error.message}`);
        console.error('savePackageConfig: Error saving configuration (fetch failed):', error);
    }
}

async function getInsights() {
    console.log('getInsights: Fetching insights...');
    const insightsCard = document.getElementById('insightsCard');
    const insightsContent = document.getElementById('insightsContent');
    
    try {
        const data = await dashboardAPI.fetch('/api/insights');
        console.log('getInsights: Received insights data:', data);
        if (data.success) {
            insightsContent.innerHTML = formatInsights(data.insights);
            console.log('getInsights: Insights content updated.');
        } else {
            insightsContent.innerHTML = `<span style="color: red;">Error: ${data.error}</span>`;
            console.error('getInsights: Error in insights data:', data.error);
        }
    } catch (error) {
        console.error('getInsights: Error loading insights:', error);
        insightsContent.innerHTML = '<span style="color: red;">Error loading insights.</span>';
    }
    
    insightsCard.style.display = 'block';
}

async function exportConfig() {
    console.log('exportConfig: Exporting configuration...');
    try {
        const config = await dashboardAPI.fetch('/api/config/export');
        console.log('exportConfig: Received config for export:', config);
        
        const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ipfs-kit-config-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        console.log('exportConfig: Configuration exported.');
    } catch (error) {
        alert('Error exporting configuration: ' + error.message);
        console.error('exportConfig: Error exporting configuration:', error);
    }
}

function toggleAutoRefresh() {
    const checkbox = document.getElementById('autoRefresh');
    if (checkbox.checked) {
        console.log('toggleAutoRefresh: Auto-refresh enabled.');
        autoRefreshInterval = setInterval(refreshData, 30000);
    } else {
        console.log('toggleAutoRefresh: Auto-refresh disabled.');
        clearInterval(autoRefreshInterval);
    }
}

async function loadBackendsTab() {
    console.log('loadBackendsTab: Loading backends tab...');
    const grid = document.getElementById('backend-details-grid');
    if (!grid) {
        console.error('loadBackendsTab: #backend-details-grid element not found.');
        return;
    }
    grid.innerHTML = '';

    try {
        const data = await dashboardAPI.fetch('/api/v0/storage/backends');
        console.log('loadBackendsTab: Received backends data:', data);

        for (const backendName in data.backends) {
            const backendData = await dashboardAPI.fetch(`/api/v0/storage/backends/${backendName}`);
            const backend = backendData.backend;

            const card = document.createElement('div');
            card.className = `backend-card ${backend.status}`;

            card.innerHTML = `
                <div class="backend-header">
                    <h3>${backend.name}</h3>
                    <div class="status-badge status-${backend.status}">${backend.status}</div>
                </div>
            `;
            grid.appendChild(card);
        }
        console.log('loadBackendsTab: Backends tab updated.');
    } catch (error) {
        console.error('loadBackendsTab: Error loading backends tab:', error);
        grid.innerHTML = `<div style="color: red; padding: 20px;">Error loading backends: ${error.message}</div>`;
    }
}

// Placeholder functions for VFS and Vector/KB formatting (if not already defined)
function formatCachePerformance(data) {
    return `<p>Cache Hits: ${data.hits || 0}</p><p>Cache Misses: ${data.misses || 0}</p>`;
}
function formatFilesystemStatus(data) {
    return `<p>Total Space: ${formatBytes(data.total_space || 0)}</p><p>Used Space: ${formatBytes(data.used_space || 0)}</p>`;
}
function formatAccessPatterns(data) {
    return `<p>Reads: ${data.reads || 0}</p><p>Writes: ${data.writes || 0}</p>`;
}
function formatResourceUsage(data) {
    return `<p>CPU: ${data.cpu_percent || 0}%</p><p>Memory: ${formatBytes(data.memory_usage || 0)}</p>`;
}
function formatTieredCacheDetails(data) {
    return `<p>Tier 1 Size: ${formatBytes(data.tier1_size || 0)}</p><p>Tier 2 Size: ${formatBytes(data.tier2_size || 0)}</p>`;
}
function formatHotContentAnalysis(data) {
    return `<p>Hot Files: ${data.hot_files || 0}</p><p>Cold Files: ${data.cold_files || 0}</p>`;
}
function formatVectorIndexStatus(data) {
    return `<p>Indexed Vectors: ${data.indexed_vectors || 0}</p><p>Index Size: ${formatBytes(data.index_size || 0)}</p>`;
}
function formatKnowledgeGraphStatus(data) {
    return `<p>Nodes: ${data.nodes || 0}</p><p>Edges: ${data.edges || 0}</p>`;
}
function formatSearchPerformance(data) {
    return `<p>Query Latency: ${data.query_latency_ms || 0}ms</p><p>Queries Per Second: ${data.qps || 0}</p>`;
}
function formatContentDistribution(data) {
    return `<p>Text: ${data.text_count || 0}</p><p>Images: ${data.image_count || 0}</p>`;
}
function formatVectorIndexDetails(data) {
    return `<p>Dimensions: ${data.dimensions || 0}</p><p>Metric: ${data.metric || 'N/A'}</p>`;
}
function formatKnowledgeBaseAnalytics(data) {
    return `<p>Concepts: ${data.concepts || 0}</p><p>Relations: ${data.relations || 0}</p>`;
}
function formatSemanticCachePerformance(data) {
    return `<p>Semantic Cache Hits: ${data.hits || 0}</p><p>Semantic Cache Misses: ${data.misses || 0}</p>`;
}
function formatInsights(insights) {
    return insights;
}

// File Manager related functions (placeholders, actual implementation is in file_manager.js)
function loadFileManagerTab() {
    console.log('loadFileManagerTab: Loading file manager tab...');
    const fileManagerContainer = document.getElementById('filemanager');
    if (!fileManagerContainer) {
        console.error('loadFileManagerTab: #filemanager element not found.');
        return;
    }
    // Assuming file_manager.js content is loaded and fileManager object is available
    // If it's dynamically loaded, you'd need a fetch here.
    // For now, just ensure the fileManager object is initialized if it exists.
    if (typeof fileManager !== 'undefined' && fileManager.refresh) {
        fileManager.refresh();
        console.log('loadFileManagerTab: fileManager refreshed.');
    } else {
        console.warn('loadFileManagerTab: fileManager object not found or refresh method missing.');
    }
}

// Modal functions (from dashboard.html, ensuring they are defined)
function createFolderPrompt() {
    const folderName = prompt("Enter folder name:");
    if (folderName) {
        fileManager.createNewFolder(folderName);
    }
}

function uploadSelectedFile() {
    const fileInput = document.getElementById('fileUploadInput');
    fileInput.click();
}

function setupDragAndDrop() {
    const dropZone = document.getElementById('dropZone');
    const fileManagerList = document.getElementById('fileManagerList');

    if (!dropZone || !fileManagerList) {
        console.warn('setupDragAndDrop: Drop zone or file manager list not found. Skipping drag and drop setup.');
        return;
    }

    dropZone.addEventListener('dragover', (event) => {
        event.preventDefault();
        dropZone.classList.add('active');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('active');
    });

    dropZone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropZone.classList.remove('active');
        const files = event.dataTransfer.files;
        fileManager.handleFileUpload(files);
    });
    console.log('setupDragAndDrop: Drag and drop setup complete.');
}

// Start auto-refresh on load (already called at the top, but keeping this for clarity)
// startAutoRefresh();

// Ensure switchTab is globally accessible
window.switchTab = showTab;
window.showTab = showTab;  // Also expose as showTab for HTML compatibility
window.refreshData = refreshData;
window.getInsights = getInsights;
window.exportConfig = exportConfig;
window.toggleAutoRefresh = toggleAutoRefresh;
window.openConfigModal = openConfigModal;
window.closeConfigModal = closeConfigModal;
window.openLogsModal = openLogsModal;
window.closeLogsModal = closeLogsModal;
window.loadPackageConfig = loadPackageConfig;
window.savePackageConfig = savePackageConfig;
window.restartBackend = restartBackend;
window.loadFileManagerTab = loadFileManagerTab;
window.createFolderPrompt = createFolderPrompt;
window.uploadSelectedFile = uploadSelectedFile;
window.setupDragAndDrop = setupDragAndDrop;
window.loadVFSTab = loadVFSTab;
window.loadVectorKBTab = loadVectorKBTab;
window.loadBackendsTab = loadBackendsTab;
window.loadConfigurationTab = loadConfigurationTab;