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

// Tab switching function (needs to be available immediately)
function showTab(tabName, event) {
    console.log('showTab: Switching to tab:', tabName);
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-btn, .tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab
    const selectedTab = document.getElementById(tabName);
    const selectedButton = event ? event.target : document.querySelector(`[onclick*="${tabName}"]`);
    
    if (selectedTab) {
        selectedTab.classList.add('active');
        currentTab = tabName;
        
        // Load tab-specific content
        switch(tabName) {
            case 'overview':
                refreshData();
                break;
            case 'monitoring':
                if (typeof loadBackendsTab === 'function') loadBackendsTab();
                break;
            case 'vfs':
                if (typeof loadVFSTab === 'function') loadVFSTab();
                break;
            case 'vfs-journal':
                if (typeof loadVFSJournal === 'function') loadVFSJournal();
                break;
            case 'vector-kb':
                if (typeof loadVectorKBTab === 'function') loadVectorKBTab();
                break;
            case 'configuration':
                if (typeof loadConfigurationTab === 'function') loadConfigurationTab();
                break;
            case 'filemanager':
                if (typeof loadFileManagerTab === 'function') loadFileManagerTab();
                break;
            case 'backends':
                if (typeof loadBackendsTab === 'function') loadBackendsTab();
                break;
            case 'logs':
                if (typeof loadLogsTab === 'function') loadLogsTab();
                break;
        }
    }
    
    if (selectedButton) {
        selectedButton.classList.add('active');
    }
    
    // Prevent default button behavior
    if (event) {
        event.preventDefault();
    }
}

// Make switchTab available globally immediately
window.switchTab = showTab;
window.showTab = showTab;

// Initialize dashboard
async function populateBackendFilter() {
    const backendFilter = document.getElementById('journalBackendFilter');
    if (!backendFilter) return;

    try {
        const data = await dashboardAPI.fetch('/api/v0/storage/backends');
        if (data.success) {
            for (const backendName of Object.keys(data.backends)) {
                const option = document.createElement('option');
                option.value = backendName;
                option.textContent = backendName;
                backendFilter.appendChild(option);
            }
        }
    } catch (error) {
        console.error('Error populating backend filter:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded: Initializing dashboard...');
    initializeExpandables();
    refreshData();
    populateBackendFilter();
    // Initialize file manager if available
    if (typeof fileManager !== 'undefined' && fileManager.init) {
        fileManager.init();
    }
});

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
    // Update system status with comprehensive information
    const systemStatusElement = document.getElementById('systemStatus');
    if (systemStatusElement) {
        console.log('updateDashboard: #systemStatus element found. Current innerHTML:', systemStatusElement.innerHTML);
        systemStatusElement.innerHTML = `
            <div class="connection-status">
                <div class="connection-indicator ${data.status === 'healthy' || data.status === 'running' ? 'connected' : ''}"></div>
                <span>Status: ${data.status || 'unknown'}</span>
            </div>
            <p><strong>Uptime:</strong> ${data.uptime_seconds ? formatUptime(data.uptime_seconds) : 'N/A'}</p>
            <p><strong>Memory Usage:</strong> ${data.memory_usage_mb ? `${data.memory_usage_mb.toFixed(1)} MB` : 'N/A'}</p>
            <p><strong>CPU Usage:</strong> ${data.cpu_usage_percent !== undefined ? `${data.cpu_usage_percent}%` : 'N/A'}</p>
            <p><strong>Python Version:</strong> ${data.system?.python_version || 'N/A'}</p>
            <p><strong>Platform:</strong> ${data.system?.platform || 'N/A'}</p>
        `;
        console.log('updateDashboard: systemStatusElement updated. New innerHTML:', systemStatusElement.innerHTML);
    } else {
        console.error('updateDashboard: #systemStatus element not found.');
    }
    
    // Update backend summary with detailed health information
    const backendSummaryElement = document.getElementById('backendSummary');
    if (backendSummaryElement) {
        console.log('updateDashboard: #backendSummary element found. Current innerHTML:', backendSummaryElement.innerHTML);
        const backends = data.backend_health?.backends || {}; // Access backends from backend_health.backends
        const healthyCount = Object.values(backends).filter(b => b.health === 'healthy').length;
        const runningCount = Object.values(backends).filter(b => b.status === 'running').length;
        const totalCount = Object.keys(backends).length;
        const progressPercent = totalCount > 0 ? (healthyCount / totalCount) * 100 : 0;
        
        // Get status breakdown
        const statusCounts = {};
        Object.values(backends).forEach(backend => {
            statusCounts[backend.status] = (statusCounts[backend.status] || 0) + 1;
        });
        
        const statusBreakdown = Object.entries(statusCounts)
            .map(([status, count]) => `${status}: ${count}`)
            .join(', ');
        
        backendSummaryElement.innerHTML = `
            <div style="font-size: 24px; font-weight: bold; color: ${healthyCount === totalCount ? '#4CAF50' : '#f44336'};">
                ${healthyCount}/${totalCount}
            </div>
            <p>Backends Healthy</p>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progressPercent}%"></div>
            </div>
            <div style="font-size: 12px; color: #6c757d;">Health Score: ${progressPercent.toFixed(1)}%</div>
            <div style="font-size: 11px; margin-top: 5px; color: #888;">
                Running: ${runningCount} | ${statusBreakdown}
            </div>
        `;
        console.log('updateDashboard: backendSummaryElement updated. New innerHTML:', backendSummaryElement.innerHTML);
    } else {
        console.error('updateDashboard: #backendSummary element not found.');
    }
    
    // Update performance metrics with detailed information
    const performanceMetricsElement = document.getElementById('performanceMetrics');
    if (performanceMetricsElement) {
        console.log('updateDashboard: #performanceMetrics element found. Current innerHTML:', performanceMetricsElement.innerHTML);
        const backends = data.backend_health?.backends || {};
        const activeBackends = Object.values(backends).filter(b => b.status === 'running').length;
        const authenticatedBackends = Object.values(backends).filter(b => b.status === 'authenticated').length;
        const availableBackends = Object.values(backends).filter(b => b.status === 'available').length;
        
        performanceMetricsElement.innerHTML = `
            <div><strong>Memory:</strong> ${data.memory_usage_mb ? `${data.memory_usage_mb.toFixed(1)} MB` : 'N/A'}</div>
            <div><strong>CPU:</strong> ${data.cpu_usage_percent !== undefined ? `${data.cpu_usage_percent}%` : 'N/A'}</div>
            <div><strong>Active Backends:</strong> ${activeBackends}</div>
            <div><strong>Ready Backends:</strong> ${authenticatedBackends + availableBackends}</div>
            <div><strong>Last Update:</strong> ${new Date().toLocaleTimeString()}</div>
        `;
        console.log('updateDashboard: performanceMetricsElement updated. New innerHTML:', performanceMetricsElement.innerHTML);
    } else {
        console.error('updateDashboard: #performanceMetrics element not found.');
    }
    
    // Update backend grid
    updateBackendGrid(data.backend_health?.backends || {});

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
        
        let metricsHTML = '';
        if (backend.metrics && Object.keys(backend.metrics).length > 0) {
            metricsHTML = `
                <div class="metrics-grid">
                    <div><strong>Version:</strong> ${backend.metrics.version || 'N/A'}</div>
                    <div><strong>Repo Size:</strong> ${formatBytes(backend.metrics.repo_size || 0)}</div>
                    <div><strong>Storage Max:</strong> ${formatBytes(backend.metrics.storage_max || 0)}</div>
                    <div><strong>Objects:</strong> ${backend.metrics.num_objects || 0}</div>
                    <div><strong>Peers:</strong> ${backend.metrics.peer_count || 0}</div>
                    <div><strong>Pins:</strong> ${backend.metrics.pin_count || 0}</div>
                    <div><strong>Bandwidth In:</strong> ${formatBytes(backend.metrics.bandwidth_rate_in || 0)}/s</div>
                    <div><strong>Bandwidth Out:</strong> ${formatBytes(backend.metrics.bandwidth_rate_out || 0)}/s</div>
                    <div><strong>Total In:</strong> ${formatBytes(backend.metrics.bandwidth_total_in || 0)}</div>
                    <div><strong>Total Out:</strong> ${formatBytes(backend.metrics.bandwidth_total_out || 0)}</div>
                </div>
            `;
        }

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
            ${metricsHTML}
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
        
        if (response && response.success && response.backends) {
            const backends = response.backends;
            currentBackendData = backends; // Update backend data
            configList.innerHTML = ''; // Clear loading message

            for (const [backendKey, backend] of Object.entries(backends)) {
                const configCard = document.createElement('div');
                configCard.className = 'stat-card';
                configCard.style.cursor = 'pointer';
                configCard.onclick = () => openConfigModal(backendKey);
                
                let configPreview = 'Click to configure';
                if (backend.detailed_info) {
                    const configKeys = Object.keys(backend.detailed_info);
                    if (configKeys.length > 0) {
                        configPreview = `${configKeys.length} config options available`;
                    } else {
                        configPreview = 'No configuration available';
                    }
                }

                configCard.innerHTML = `
                    <h4>${backend.name || backendKey}</h4>
                    <div class="status-badge status-${backend.health || 'unknown'}">${backend.health || 'unknown'}</div>
                    <div class="status-badge status-${backend.status || 'unknown'}">${backend.status || 'unknown'}</div>
                    <p style="font-size: 0.9em; color: #6c757d; margin: 8px 0;">${configPreview}</p>
                `;
                
                configList.appendChild(configCard);
            }
            console.log('loadConfigurationTab: Backend configurations loaded.');
        } else {
            configList.innerHTML = '<div style="color: red; padding: 20px;">No backend data available</div>';
        }
    } catch (error) {
        console.error('loadConfigurationTab: Error loading configurations:', error);
        configList.innerHTML = `<div style="color: red; padding: 20px;">Error loading configurations: ${error.message}</div>`;
    }
}

async function loadLogsTab() {
    console.log('loadLogsTab: Loading logs tab...');
    const logViewer = document.getElementById('logViewer');
    const searchInput = document.getElementById('logSearch');
    const levelFilter = document.getElementById('logLevelFilter');
    const sourceFilter = document.getElementById('logSourceFilter');
    
    if (!logViewer) {
        console.error('loadLogsTab: #logViewer element not found.');
        return;
    }

    const searchQuery = searchInput ? searchInput.value : '';
    const levelFilter_value = levelFilter ? levelFilter.value : '';
    const sourceFilter_value = sourceFilter ? sourceFilter.value : '';
    
    logViewer.innerHTML = '<div class="loading">Loading system logs...</div>';

    try {
        // Get logs from the working endpoint
        const logData = await dashboardAPI.fetch('/api/logs?limit=100');
        
        if (logData && logData.logs) {
            // Convert structured log data to formatted log strings
            let logs = [];
            
            // Process each backend's logs
            for (const [backend, backendLogs] of Object.entries(logData.logs)) {
                if (Array.isArray(backendLogs)) {
                    for (const logEntry of backendLogs) {
                        // Format: timestamp - backend - level - message
                        const formattedLog = `${logEntry.formatted_time} - ${logEntry.backend} - ${logEntry.level} - ${logEntry.message}`;
                        logs.push(formattedLog);
                    }
                }
            }
            
            // Apply client-side filtering
            if (searchQuery) {
                logs = logs.filter(log => 
                    log.toLowerCase().includes(searchQuery.toLowerCase())
                );
            }
            
            if (levelFilter_value) {
                logs = logs.filter(log => 
                    log.includes(` - ${levelFilter_value} - `)
                );
            }

            if (sourceFilter_value) {
                logs = logs.filter(log => 
                    log.includes(sourceFilter_value)
                );
            }

            // Always use renderLogEntries for proper layout (logs first, stats at bottom)
            renderLogEntries(logs, logViewer, false);
        } else {
            // Generate sample log data for demonstration
            const sampleLogs = generateSampleLogData(levelFilter_value, sourceFilter_value, searchQuery);
            renderLogEntries(sampleLogs, logViewer, true);
        }
    } catch (error) {
        console.error('loadLogsTab: Error loading logs:', error);
        // Generate sample data on error
        const sampleLogs = generateSampleLogData(levelFilter_value, sourceFilter_value, searchQuery);
        renderLogEntries(sampleLogs, logViewer, true);
    }
}

function filterLogs() {
    loadLogsTab();
}

function clearLogFilters() {
    const searchInput = document.getElementById('logSearch');
    const levelFilter = document.getElementById('logLevelFilter');
    const sourceFilter = document.getElementById('logSourceFilter');
    
    if (searchInput) searchInput.value = '';
    if (levelFilter) levelFilter.value = '';
    if (sourceFilter) sourceFilter.value = '';
    
    loadLogsTab();
}

function toggleAutoRefresh() {
    const btn = document.getElementById('autoRefreshBtn');
    
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        btn.textContent = '▶️ Auto-Refresh';
        btn.classList.remove('paused');
    } else {
        autoRefreshInterval = setInterval(() => {
            if (document.getElementById('logs').classList.contains('active')) {
                loadLogsTab();
            }
        }, 5000); // Refresh every 5 seconds
        btn.textContent = '⏸️ Auto-Refresh';
        btn.classList.add('paused');
    }
}

function renderLogEntries(logs, container, isSample = false) {
    // Clean and sort logs
    let cleanedLogs = logs
        .filter(log => log && log.trim().length > 0) // Remove empty lines
        .map(log => log.trim()) // Remove leading/trailing whitespace
        .sort((a, b) => {
            // Extract timestamps and sort by most recent first
            const timestampA = extractTimestamp(a);
            const timestampB = extractTimestamp(b);
            return timestampB - timestampA; // Most recent first
        });
    
    const logStats = calculateLogStats(cleanedLogs);
    
    // Put the log entries first, then stats at the bottom
    let logHTML = `<div class="log-entries">`;
    
    if (cleanedLogs.length === 0) {
        logHTML += `<div class="log-entry INFO">No log entries found matching current filters.</div>`;
    } else {
        for (const logEntry of cleanedLogs) {
            const level = extractLogLevel(logEntry);
            const formattedEntry = formatLogEntry(logEntry);
            
            logHTML += `<div class="log-entry ${level}">${formattedEntry}</div>`;
        }
    }
    
    logHTML += '</div>';
    
    // Add colored statistics indicators below the logs
    logHTML += `
        <div class="log-stats-indicators">
            <div class="stat-indicator total">
                <div class="stat-number">${cleanedLogs.length}</div>
                <div class="stat-label">Total</div>
            </div>
            <div class="stat-indicator errors">
                <div class="stat-number">${logStats.errors}</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat-indicator warnings">
                <div class="stat-number">${logStats.warnings}</div>
                <div class="stat-label">Warnings</div>
            </div>
            <div class="stat-indicator info">
                <div class="stat-number">${logStats.info}</div>
                <div class="stat-label">Info</div>
            </div>
        </div>
    `;
    
    if (isSample) {
        logHTML += `
            <div class="sample-notice">
                <p><em>📊 This is sample log data showing typical system activity.</em></p>
                <p><em>🔌 Connect to a running server with active backends to see real log entries.</em></p>
            </div>
        `;
    }
    
    container.innerHTML = logHTML;
}

function calculateLogStats(logs) {
    const stats = { errors: 0, warnings: 0, info: 0, debug: 0, critical: 0 };
    
    for (const log of logs) {
        if (log.includes(' - ERROR - ')) stats.errors++;
        else if (log.includes(' - WARNING - ')) stats.warnings++;
        else if (log.includes(' - INFO - ')) stats.info++;
        else if (log.includes(' - DEBUG - ')) stats.debug++;
        else if (log.includes(' - CRITICAL - ')) stats.critical++;
    }
    
    return stats;
}

function extractLogLevel(logEntry) {
    if (logEntry.includes(' - ERROR - ')) return 'ERROR';
    if (logEntry.includes(' - WARNING - ')) return 'WARNING';
    if (logEntry.includes(' - INFO - ')) return 'INFO';
    if (logEntry.includes(' - DEBUG - ')) return 'DEBUG';
    if (logEntry.includes(' - CRITICAL - ')) return 'CRITICAL';
    return 'INFO';
}

function extractTimestamp(logEntry) {
    // Extract timestamp from log entry
    // New format: "HH:MM:SS - backend - LEVEL - message"
    const timeMatch = logEntry.match(/^(\d{2}:\d{2}:\d{2})\s*-/);
    if (timeMatch) {
        const timeStr = timeMatch[1];
        // Create a date object with today's date and the extracted time
        const today = new Date();
        const [hours, minutes, seconds] = timeStr.split(':');
        const timestamp = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 
                                 parseInt(hours), parseInt(minutes), parseInt(seconds));
        return timestamp.getTime();
    }
    
    // Fallback: try full timestamp format "YYYY-MM-DD HH:MM:SS,mmm - ..."
    const timestampMatch = logEntry.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[,\.]?\d*\s*-/);
    if (timestampMatch) {
        const timestampStr = timestampMatch[1];
        const timestamp = new Date(timestampStr);
        return timestamp.getTime();
    }
    
    // Fallback: try ISO format
    const isoMatch = logEntry.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})/);
    if (isoMatch) {
        return new Date(isoMatch[1]).getTime();
    }
    
    // If no timestamp found, return 0 (will be sorted to end)
    return 0;
}

function formatLogEntry(logEntry) {
    // Remove excessive newlines, tabs, and extra spaces while preserving single spaces
    return logEntry
        .replace(/\n+/g, ' ')  // Replace newlines with single space
        .replace(/\t+/g, ' ')  // Replace tabs with single space
        .replace(/\s{2,}/g, ' ')  // Replace multiple spaces with single space
        .trim();  // Remove leading/trailing whitespace
}

function generateSampleLogData(levelFilter = '', sourceFilter = '', searchQuery = '') {
    const now = new Date();
    const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
    const sources = ['backend.ipfs', 'backend.lotus', 'backend.storacha', 'api.server', 'mcp.server'];
    const operations = [
        'Health check completed',
        'Backend status updated',
        'VFS operation: read',
        'VFS operation: write', 
        'API request processed',
        'Configuration updated',
        'Cache miss, loading from storage',
        'Cache hit, serving cached data',
        'Peer connection established',
        'File upload completed',
        'Index update finished',
        'Search operation completed',
        'Backup operation started',
        'Cleanup task executed'
    ];
    
    const logs = [];
    
    for (let i = 50; i >= 0; i--) {
        const timestamp = new Date(now.getTime() - i * 10000); // Every 10 seconds
        const level = levels[Math.floor(Math.random() * levels.length)];
        const source = sources[Math.floor(Math.random() * sources.length)];
        const operation = operations[Math.floor(Math.random() * operations.length)];
        
        // Apply filters if specified
        if (levelFilter && level !== levelFilter) continue;
        if (sourceFilter && !source.includes(sourceFilter)) continue;
        if (searchQuery && !operation.toLowerCase().includes(searchQuery.toLowerCase())) continue;
        
        const logEntry = `${timestamp.toISOString().replace('T', ' ').slice(0, 19)} - ${source} - ${level} - ${operation}`;
        logs.push(logEntry);
    }
    
    return logs;
}

function renderLogsInterface(logData, container) {
    console.log('renderLogsInterface: This function is deprecated, using renderLogEntries instead');
    // Redirect to use the proper log display with sample data
    const sampleLogs = generateSampleLogData();
    renderLogEntries(sampleLogs, container, true);
}

function loadLogOverview() {
    // Stub function - could load overview statistics
    console.log('loadLogOverview: Loading log overview');
}

function loadRecentLogs() {
    // Stub function - could load recent logs
    console.log('loadRecentLogs: Loading recent logs');
}

function loadErrorLogs() {
    // Stub function - could load error logs
    console.log('loadErrorLogs: Loading error logs');
}

function populateBackendSelects() {
    // Stub function - could populate backend dropdowns
    console.log('populateBackendSelects: Populating backend selects');
}

function filterRecentLogs() {
    // Stub function - could filter recent logs
    console.log('filterRecentLogs: Filtering recent logs');
}

function filterErrorLogs() {
    // Stub function - could filter error logs
    console.log('filterErrorLogs: Filtering error logs');
}

function loadBackendLogs() {
    // Stub function - could load backend-specific logs
    console.log('loadBackendLogs: Loading backend logs');
}

function loadAllBackendLogs() {
    // Stub function - could load all backend logs
    console.log('loadAllBackendLogs: Loading all backend logs');
}

function renderLogsWithStats(statsData, container) {
    console.log('renderLogsWithStats: This function is deprecated, using renderLogEntries instead');
    // Redirect to use the proper log display with sample data
    const sampleLogs = generateSampleLogData();
    renderLogEntries(sampleLogs, container, true);
}

function renderSampleLogs(container) {
    const sampleLogs = generateSampleSystemLogs();
    container.innerHTML = `
        <div class="logs-interface">
            <div class="log-info-banner">
                <p><strong>Demo Mode:</strong> These are sample logs. Connect to a running server for real system logs.</p>
            </div>
            <div class="logs-tabs">
                <button class="log-tab-btn active" onclick="showLogSection('overview')">📊 Sample Overview</button>
            </div>
            <div class="log-sections">
                <div id="overview-logs" class="log-section active">
                    <div class="log-content-area">
                        <pre class="log-display">${sampleLogs}</pre>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function generateSampleSystemLogs() {
    const now = new Date();
    const logs = [];
    
    // Generate realistic system activity logs
    for (let i = 20; i >= 0; i--) {
        const timestamp = new Date(now.getTime() - i * 60000).toISOString();
        
        const activities = [
            `${timestamp} - INFO - Backend health check completed for IPFS`,
            `${timestamp} - INFO - VFS operation: read /vectors/embeddings_cache.bin (245ms)`,
            `${timestamp} - DEBUG - Memory usage: 629.18MB, CPU: 12.3%`,
            `${timestamp} - INFO - WebSocket connection established from 127.0.0.1`,
            `${timestamp} - WARNING - IPFS cluster connection timeout, retrying...`,
            `${timestamp} - INFO - Semantic search query processed: 'document classification' (34ms)`,
            `${timestamp} - INFO - Cache hit for vector similarity search`,
            `${timestamp} - DEBUG - Processing file upload to storage backend`,
            `${timestamp} - INFO - Knowledge graph updated: 5 new entities added`,
            `${timestamp} - ERROR - Failed to connect to Lotus daemon: connection refused`,
            `${timestamp} - INFO - Dashboard page accessed from 127.0.0.1`,
            `${timestamp} - INFO - Backend status updated: Storacha (healthy)`,
            `${timestamp} - DEBUG - Garbage collection: freed 45.2MB`,
            `${timestamp} - INFO - VFS journal entry: write operation completed`,
            `${timestamp} - WARNING - High memory usage detected: 85% threshold exceeded`
        ];
        
        // Add random activity
        if (Math.random() > 0.3) {
            logs.push(activities[Math.floor(Math.random() * activities.length)]);
        }
    }
    
    return logs.join('\n');
}

function highlightLogLevels(element) {
    const content = element.innerHTML;
    const highlighted = content
        .replace(/(ERROR|CRITICAL)/g, '<span style="color: #f44336; font-weight: bold;">$1</span>')
        .replace(/(WARNING)/g, '<span style="color: #ff9800; font-weight: bold;">$1</span>')
        .replace(/(INFO)/g, '<span style="color: #4CAF50;">$1</span>')
        .replace(/(DEBUG)/g, '<span style="color: #2196F3;">$1</span>');
    
    element.innerHTML = highlighted;
}

function showLogSection(sectionName) {
    console.log('showLogSection: Switching to section:', sectionName);
    
    // Hide all sections
    document.querySelectorAll('.log-section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.log-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected section
    const targetSection = document.getElementById(`${sectionName}-logs`);
    if (targetSection) {
        targetSection.classList.add('active');
    }
    
    // Activate selected tab
    const activeTab = document.querySelector(`[onclick*="showLogSection('${sectionName}')"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }
}

async function loadLogOverview() {
    try {
        const statsData = await dashboardAPI.fetch('/api/logs/statistics');
        const overviewContent = document.getElementById('overviewContent');
        
        if (statsData && statsData.success) {
            const stats = statsData.data;
            overviewContent.innerHTML = `
                <div class="overview-sections">
                    <div class="recent-activity">
                        <h4>Recent Activity</h4>
                        <div class="activity-stats">
                            <span>Last Hour: ${stats.recent_activity?.last_hour || 0}</span>
                            <span>Last 24h: ${stats.recent_activity?.last_24h || 0}</span>
                            <span>Last Week: ${stats.recent_activity?.last_week || 0}</span>
                        </div>
                    </div>
                    <div class="backend-overview">
                        <h4>Backend Status</h4>
                        <div class="backend-overview-grid">
                            ${Object.entries(stats.backends || {}).map(([name, data]) => `
                                <div class="backend-overview-card">
                                    <div class="backend-name">${name}</div>
                                    <div class="backend-info">
                                        <span>${data.total_entries} entries</span>
                                        <span>Last: ${data.last_entry ? new Date(data.last_entry).toLocaleString() : 'Never'}</span>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `;
        } else {
            overviewContent.innerHTML = '<div class="info-message">No overview data available</div>';
        }
    } catch (error) {
        console.error('Error loading log overview:', error);
        const overviewContent = document.getElementById('overviewContent');
        if (overviewContent) {
            overviewContent.innerHTML = '<div class="error-message">Error loading overview</div>';
        }
    }
}

async function loadRecentLogs() {
    try {
        const recentData = await dashboardAPI.fetch('/api/logs/recent?minutes=30');
        const recentContent = document.getElementById('recentLogsContent');
        
        if (recentData && recentData.success && recentData.data) {
            const logs = Array.isArray(recentData.data) ? recentData.data : [recentData.data];
            recentContent.innerHTML = `
                <div class="log-table-container">
                    <table class="log-table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Backend</th>
                                <th>Level</th>
                                <th>Message</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${logs.map(log => `
                                <tr class="log-row log-${log.level?.toLowerCase() || 'info'}">
                                    <td class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</td>
                                    <td class="log-backend">${log.backend || 'system'}</td>
                                    <td class="log-level">${log.level || 'INFO'}</td>
                                    <td class="log-message">${log.message || ''}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } else {
            recentContent.innerHTML = '<div class="info-message">No recent logs available</div>';
        }
    } catch (error) {
        console.error('Error loading recent logs:', error);
        const recentContent = document.getElementById('recentLogsContent');
        if (recentContent) {
            recentContent.innerHTML = '<div class="error-message">Error loading recent logs</div>';
        }
    }
}

async function loadErrorLogs() {
    try {
        const errorData = await dashboardAPI.fetch('/api/logs/errors');
        const errorContent = document.getElementById('errorLogsContent');
        
        if (errorData && errorData.success && errorData.data) {
            const errors = Array.isArray(errorData.data) ? errorData.data : [errorData.data];
            errorContent.innerHTML = `
                <div class="log-table-container">
                    <table class="log-table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Backend</th>
                                <th>Level</th>
                                <th>Message</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${errors.map(error => `
                                <tr class="log-row log-${error.level?.toLowerCase() || 'error'}">
                                    <td class="log-time">${new Date(error.timestamp).toLocaleTimeString()}</td>
                                    <td class="log-backend">${error.backend || 'system'}</td>
                                    <td class="log-level">${error.level || 'ERROR'}</td>
                                    <td class="log-message">${error.message || ''}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } else {
            errorContent.innerHTML = '<div class="info-message">No error logs found</div>';
        }
    } catch (error) {
        console.error('Error loading error logs:', error);
        const errorContent = document.getElementById('errorLogsContent');
        if (errorContent) {
            errorContent.innerHTML = '<div class="error-message">Error loading error logs</div>';
        }
    }
}

async function populateBackendSelects() {
    try {
        const backendData = await dashboardAPI.fetch('/api/backends/status');
        if (backendData && backendData.success) {
            const backends = Object.keys(backendData.backends || {});
            
            // Populate backend selectors
            const selectors = ['errorLogBackend', 'backendLogSelect'];
            selectors.forEach(selectorId => {
                const selector = document.getElementById(selectorId);
                if (selector) {
                    backends.forEach(backend => {
                        const option = document.createElement('option');
                        option.value = backend;
                        option.textContent = backend;
                        selector.appendChild(option);
                    });
                }
            });
        }
    } catch (error) {
        console.error('Error populating backend selects:', error);
    }
}

async function loadVFSJournal() {
    console.log('loadVFSJournal: Loading VFS journal...');
    const journalContent = document.getElementById('vfsJournalContent');
    const searchInput = document.getElementById('journalSearch');
    const backendFilter = document.getElementById('journalBackendFilter');
    const operationFilter = document.getElementById('journalOperationFilter');

    if (!journalContent) {
        console.error('loadVFSJournal: #vfsJournalContent element not found.');
        return;
    }

    const query = searchInput ? searchInput.value : '';
    const backend = backendFilter ? backendFilter.value : '';
    const operation = operationFilter ? operationFilter.value : '';

    journalContent.innerHTML = '<div class="loading">Loading VFS journal...</div>';

    try {
        // Try to get real VFS data first
        let journalData = null;
        let vfsStats = null;
        let backendHealth = null;
        
        try {
            // Get VFS statistics for real content access patterns
            vfsStats = await dashboardAPI.fetch('/api/vfs/statistics');
            backendHealth = await dashboardAPI.fetch('/api/health');
            
            // Try VFS journal endpoint
            const journalResponse = await dashboardAPI.fetch(`/api/vfs/journal?query=${encodeURIComponent(query)}&backend=${backend}&operation=${operation}`);
            if (journalResponse && journalResponse.success) {
                journalData = journalResponse;
            }
        } catch (e) {
            console.log('loadVFSJournal: API endpoints not fully available, using enhanced sample data');
        }

        if (journalData && journalData.journal && journalData.journal.length > 0) {
            // Use real journal data
            renderJournalTable(journalData.journal, journalContent, false);
        } else {
            // Generate enhanced journal data based on real backend and VFS statistics
            const enhancedJournal = generateEnhancedVFSJournal(backend, operation, query, vfsStats, backendHealth);
            renderJournalTable(enhancedJournal, journalContent, true);
        }
    } catch (error) {
        console.error('loadVFSJournal: Error loading VFS journal:', error);
        journalContent.innerHTML = `
            <div class="error-state">
                <h3>Error Loading VFS Journal</h3>
                <p>${error.message}</p>
                <button onclick="loadVFSJournal()">Retry</button>
            </div>
        `;
    }
}

function generateEnhancedVFSJournal(backendFilter = '', operationFilter = '', searchQuery = '', vfsStats = null, backendHealth = null) {
    const now = new Date();
    const journal = [];
    
    // Get real backend statuses if available
    let activeBackends = ['ipfs', 'lotus', 'storacha', 's3', 'local'];
    let hotContent = [];
    let operationCounts = {};
    
    if (backendHealth && backendHealth.backend_health && backendHealth.backend_health.backends) {
        const backends = backendHealth.backend_health.backends;
        activeBackends = Object.keys(backends).filter(name => 
            backends[name].status === 'running' || 
            backends[name].status === 'authenticated' || 
            backends[name].status === 'available'
        );
    }
    
    if (vfsStats && vfsStats.success && vfsStats.data.access_patterns) {
        hotContent = vfsStats.data.access_patterns.hot_content || [];
        operationCounts = vfsStats.data.access_patterns.operation_distribution || {};
    }
    
    // Generate realistic journal entries based on real VFS activity
    const operations = ['read', 'write', 'upload', 'download', 'delete', 'list', 'index', 'search'];
    const baseOperations = Object.keys(operationCounts).length > 0 ? 
        Object.keys(operationCounts).map(op => op.replace('_operations', '')) : operations;
    
    // Use hot content paths if available, otherwise use default paths
    const paths = hotContent.length > 0 ? 
        hotContent.map(item => item.path) : [
            '/vectors/embeddings_cache.bin',
            '/documents/research_papers/ai_trends_2024.pdf',
            '/knowledge_base/entities.json',
            '/cache/semantic_search.cache',
            '/index/document_vectors.idx',
            '/graphs/relationship_map.graph',
            '/datasets/training_data.parquet',
            '/models/transformer_weights.bin'
        ];
    
    // Generate entries based on real access patterns
    const totalEntries = Math.min(100, Math.max(20, Object.values(operationCounts).reduce((a, b) => a + b, 0) / 100));
    
    for (let i = totalEntries; i >= 0; i--) {
        const timestamp = new Date(now.getTime() - i * 15000).toISOString(); // Every 15 seconds
        
        // Weight backend selection towards active backends
        const backend = activeBackends.length > 0 ? 
            activeBackends[Math.floor(Math.random() * activeBackends.length)] :
            ['ipfs', 'storacha', 'local'][Math.floor(Math.random() * 3)];
            
        // Weight operation selection based on real operation distribution
        const operation = baseOperations[Math.floor(Math.random() * baseOperations.length)];
        
        // Weight path selection towards hot content
        const pathIndex = hotContent.length > 0 && Math.random() < 0.7 ? 
            Math.floor(Math.random() * Math.min(hotContent.length, 5)) : 
            Math.floor(Math.random() * paths.length);
        const path = paths[pathIndex];
        
        // Apply filters if specified
        if (backendFilter && backend !== backendFilter) continue;
        if (operationFilter && operation !== operationFilter) continue;
        if (searchQuery && !path.toLowerCase().includes(searchQuery.toLowerCase())) continue;
        
        // Use real file sizes if available from hot content
        let size_bytes = Math.floor(Math.random() * 10000000); // Default random size
        if (hotContent.length > 0 && pathIndex < hotContent.length) {
            size_bytes = hotContent[pathIndex].size_kb * 1024;
        }
        
        const entry = {
            timestamp: timestamp,
            backend: backend,
            operation: operation,
            path: path,
            size_bytes: size_bytes,
            duration_ms: Math.random() * 1000 + 10, // 10ms to 1s
            success: Math.random() > 0.1, // 90% success rate for active backends
            details: generateRealisticOperationDetails(operation, backend, path, vfsStats)
        };
        
        journal.push(entry);
    }
    
    // Sort by timestamp (newest first)
    return journal.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}

function generateRealisticOperationDetails(operation, backend, path, vfsStats = null) {
    // Generate more realistic details based on actual VFS statistics
    const cacheHitRate = vfsStats?.data?.cache_performance?.tiered_cache?.memory_tier?.hit_rate || 0.85;
    const avgQueryTime = vfsStats?.data?.vector_index_status?.search_performance?.average_query_time_ms || 25;
    
    const detailsMap = {
        read: [
            `Cache hit (${(cacheHitRate * 100).toFixed(1)}% hit rate)`,
            'Cache miss, loaded from disk',
            'Network retrieval from peer',
            'Index lookup completed',
            `Retrieved from ${backend} storage`
        ],
        write: [
            'Data committed to storage',
            'Index updated successfully',
            'Backup created automatically',
            'Metadata synchronized',
            `Written to ${backend} backend`
        ],
        upload: [
            'File uploaded successfully',
            'Checksum verified',
            'Distributed to cluster nodes',
            'Pinned to IPFS network',
            `Stored via ${backend} backend`
        ],
        download: [
            'Retrieved from cache',
            'Downloaded from peer network',
            'Fetched from gateway',
            'Streamed from storage',
            `Downloaded via ${backend}`
        ],
        search: [
            `Vector similarity search (${avgQueryTime.toFixed(1)}ms)`,
            'Full-text search completed',
            'Metadata query processed',
            'Graph traversal executed',
            'Semantic search performed'
        ],
        index: [
            'Vector index updated',
            'Document indexed successfully',
            'Embeddings generated',
            'Knowledge graph updated',
            'Search index rebuilt'
        ]
    };
    
    const operationDetails = detailsMap[operation] || ['Operation completed'];
    return operationDetails[Math.floor(Math.random() * operationDetails.length)];
}

function renderJournalTable(journal, container, isSample = false) {
    let journalHTML = `
        <div class="journal-stats">
            <div class="stat">
                <strong>Total Entries:</strong> ${journal.length}
            </div>
            <div class="stat">
                <strong>Time Range:</strong> ${getTimeRange(journal)}
            </div>
            <div class="stat">
                <strong>Backends Active:</strong> ${getUniqueBackends(journal).length}
            </div>
            ${isSample ? '<div class="stat sample-indicator"><strong>Mode:</strong> Sample Data</div>' : ''}
        </div>
        <div class="journal-table-container">
            <table class="journal-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Backend</th>
                        <th>Operation</th>
                        <th>Path</th>
                        <th>Size</th>
                        <th>Duration</th>
                        <th>Status</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    for (const entry of journal) {
        const statusClass = entry.success ? 'success' : 'error';
        const statusIcon = entry.success ? '✓' : '✗';
        const sizeFormatted = entry.size_bytes ? formatBytes(entry.size_bytes) : '-';
        const durationFormatted = entry.duration_ms ? `${entry.duration_ms.toFixed(2)}ms` : '-';
        
        journalHTML += `
            <tr class="journal-entry ${statusClass}">
                <td class="timestamp">${new Date(entry.timestamp).toLocaleString()}</td>
                <td class="backend">
                    <span class="backend-badge backend-${entry.backend}">${entry.backend}</span>
                </td>
                <td class="operation">
                    <span class="operation-badge operation-${entry.operation}">${entry.operation}</span>
                </td>
                <td class="path" title="${entry.path}">
                    ${truncatePath(entry.path, 40)}
                </td>
                <td class="size">${sizeFormatted}</td>
                <td class="duration">${durationFormatted}</td>
                <td class="status">
                    <span class="status-indicator ${statusClass}">
                        ${statusIcon} ${entry.success ? 'Success' : 'Failed'}
                    </span>
                </td>
                <td class="details" title="${entry.details || ''}">${truncateText(entry.details || '-', 30)}</td>
            </tr>
        `;
    }
    
    journalHTML += `
                </tbody>
            </table>
        </div>
    `;
    
    if (isSample) {
        journalHTML += `
            <div class="sample-notice">
                <p><em>📊 This is sample VFS journal data showing typical filesystem operations across different backends.</em></p>
                <p><em>🔌 Connect to a running server with active backends to see real journal entries.</em></p>
            </div>
        `;
    }
    
    container.innerHTML = journalHTML;
}

function generateSampleVFSJournal(backendFilter = '', operationFilter = '', searchQuery = '') {
    const now = new Date();
    const backends = ['ipfs', 'ipfs_cluster', 'lotus', 'storacha', 's3', 'local'];
    const operations = ['read', 'write', 'delete', 'list', 'upload', 'download', 'index', 'search'];
    const paths = [
        '/vectors/embeddings_cache.bin',
        '/documents/research_papers/ai_trends_2024.pdf',
        '/knowledge_base/entities.json',
        '/cache/semantic_search.cache',
        '/index/document_vectors.idx',
        '/graphs/relationship_map.graph',
        '/datasets/training_data.parquet',
        '/models/transformer_weights.bin',
        '/logs/system_activity.log',
        '/config/backend_settings.yaml',
        '/uploads/user_document.txt',
        '/temp/processing_queue.json'
    ];
    
    const journal = [];
    
    for (let i = 100; i >= 0; i--) {
        const timestamp = new Date(now.getTime() - i * 30000).toISOString(); // Every 30 seconds
        
        const backend = backends[Math.floor(Math.random() * backends.length)];
        const operation = operations[Math.floor(Math.random() * operations.length)];
        const path = paths[Math.floor(Math.random() * paths.length)];
        
        // Apply filters if specified
        if (backendFilter && backend !== backendFilter) continue;
        if (operationFilter && operation !== operationFilter) continue;
        if (searchQuery && !path.toLowerCase().includes(searchQuery.toLowerCase())) continue;
        
        const entry = {
            timestamp: timestamp,
            backend: backend,
            operation: operation,
            path: path,
            size_bytes: Math.floor(Math.random() * 10000000), // Random size up to 10MB
            duration_ms: Math.random() * 1000 + 10, // 10ms to 1s
            success: Math.random() > 0.15, // 85% success rate
            details: generateOperationDetails(operation, backend, path)
        };
        
        journal.push(entry);
    }
    
    // Sort by timestamp (newest first)
    return journal.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}

function generateOperationDetails(operation, backend, path) {
    const details = {
        read: [
            'Cache hit',
            'Cache miss, loaded from disk',
            'Network retrieval',
            'Index lookup'
        ],
        write: [
            'Data committed to storage',
            'Index updated',
            'Backup created',
            'Metadata synchronized'
        ],
        upload: [
            'File uploaded successfully',
            'Checksum verified',
            'Distributed to cluster',
            'Pinned to IPFS'
        ],
        download: [
            'Retrieved from cache',
            'Downloaded from peer',
            'Fetched from gateway',
            'Streamed from storage'
        ],
        delete: [
            'File removed',
            'Index cleaned up',
            'References updated',
            'Garbage collected'
        ],
        search: [
            'Vector similarity search',
            'Full-text search',
            'Metadata query',
            'Graph traversal'
        ]
    };
    
    const operationDetails = details[operation] || ['Operation completed'];
    return operationDetails[Math.floor(Math.random() * operationDetails.length)];
}

function getTimeRange(journal) {
    if (journal.length === 0) return 'No entries';
    
    const timestamps = journal.map(entry => new Date(entry.timestamp));
    const earliest = new Date(Math.min(...timestamps));
    const latest = new Date(Math.max(...timestamps));
    
    const timeDiff = latest - earliest;
    const hours = Math.floor(timeDiff / (1000 * 60 * 60));
    const minutes = Math.floor((timeDiff % (1000 * 60 * 60)) / (1000 * 60));
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else {
        return `${minutes}m`;
    }
}

function getUniqueBackends(journal) {
    return [...new Set(journal.map(entry => entry.backend))];
}

function truncatePath(path, maxLength) {
    if (path.length <= maxLength) return path;
    
    const parts = path.split('/');
    if (parts.length <= 2) {
        return path.substring(0, maxLength - 3) + '...';
    }
    
    return parts[0] + '/.../' + parts[parts.length - 1];
}

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
}

function filterVFSJournal() {
    loadVFSJournal();
}

function clearVFSJournalFilters() {
    const searchInput = document.getElementById('journalSearch');
    const backendFilter = document.getElementById('journalBackendFilter');
    const operationFilter = document.getElementById('journalOperationFilter');
    
    if (searchInput) searchInput.value = '';
    if (backendFilter) backendFilter.value = '';
    if (operationFilter) operationFilter.value = '';
    
    loadVFSJournal();
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
        'lassie': {
            'Binary': [
                { name: 'binary_path', label: 'Lassie Binary Path', type: 'text', value: 'lassie', description: 'Path to lassie binary executable' },
                { name: 'binary_available', label: 'Binary Available', type: 'checkbox', value: 'false', description: 'Whether lassie binary is available', readonly: true }
            ],
            'Retrieval': [
                { name: 'concurrent_downloads', label: 'Concurrent Downloads', type: 'number', value: '10', description: 'Number of concurrent downloads' },
                { name: 'timeout', label: 'Timeout', type: 'text', value: '30s', description: 'Timeout for retrieval operations' },
                { name: 'temp_directory', label: 'Temp Directory', type: 'text', value: '', description: 'Temporary directory for downloads' }
            ],
            'Providers': [
                { name: 'provider_endpoints', label: 'Provider Endpoints', type: 'textarea', value: '', description: 'Provider endpoints (one per line)' },
                { name: 'enable_bitswap', label: 'Enable Bitswap', type: 'checkbox', value: 'true', description: 'Enable Bitswap protocol' },
                { name: 'enable_graphsync', label: 'Enable GraphSync', type: 'checkbox', value: 'true', description: 'Enable GraphSync protocol' }
            ],
            'Integration': [
                { name: 'integration_mode', label: 'Integration Mode', type: 'select', options: ['standalone', 'lotus-integrated'], value: 'standalone', description: 'How lassie integrates with the system' },
                { name: 'lotus_endpoint', label: 'Lotus Endpoint', type: 'url', value: 'http://127.0.0.1:1234/rpc/v0', description: 'Lotus API endpoint for integration' }
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
        const value = getNestedValue(backendConfigCache[backendName], fieldName);
        // Return empty string instead of undefined to prevent "undefined" text
        return value !== undefined ? value : '';
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
            return undefined; // Return undefined but handle it in getCurrentConfigValue
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
    grid.innerHTML = '<div class="loading">Loading backend details...</div>';

    try {
        const data = await dashboardAPI.fetch('/api/v0/storage/backends');
        console.log('loadBackendsTab: Received backends data:', data);
        grid.innerHTML = ''; // Clear loading message

        if (!data.backends || Object.keys(data.backends).length === 0) {
            grid.innerHTML = '<div class="empty-state">No backends found.</div>';
            return;
        }

        for (const [backendName, backendInfo] of Object.entries(data.backends)) {
            const card = document.createElement('div');
            card.className = `backend-card ${backendInfo.status || 'unknown'}`;

            let storageInfoHTML = '<p><strong>Storage:</strong> N/A</p>';
            if (backendInfo.storage_info) {
                const { type, used_bytes, available_bytes, total_bytes } = backendInfo.storage_info;
                const used = formatBytes(used_bytes || 0);
                const total = formatBytes(total_bytes || 0);
                const progress = total_bytes > 0 ? ((used_bytes || 0) / total_bytes) * 100 : 0;

                storageInfoHTML = `
                    <div class="storage-details">
                        <p><strong>Storage Type:</strong> ${type || 'N/A'}</p>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${progress.toFixed(2)}%;"></div>
                        </div>
                        <div class="storage-stats">
                            <span>${used} / ${total}</span>
                            <span>${progress.toFixed(1)}%</span>
                        </div>
                    </div>
                `;
            }

            let capabilitiesHTML = '';
            if (backendInfo.capabilities && backendInfo.capabilities.length > 0) {
                capabilitiesHTML = `
                    <div class="capabilities">
                        <strong>Capabilities:</strong>
                        <div class="capability-tags">
                            ${backendInfo.capabilities.map(cap => `<span class="tag">${cap}</span>`).join('')}
                        </div>
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="backend-header">
                    <h3>${backendInfo.name || backendName}</h3>
                    <div class="status-badge status-${backendInfo.status || 'unknown'}">${backendInfo.status || 'unknown'}</div>
                </div>
                <div class="backend-details">
                    <p><strong>Backend Type:</strong> ${backendInfo.backend_type || backendName}</p>
                    <p><strong>Priority:</strong> ${backendInfo.priority || 'N/A'}</p>
                    <p><strong>Last Check:</strong> ${backendInfo.last_check ? new Date(backendInfo.last_check).toLocaleString() : 'Never'}</p>
                    ${storageInfoHTML}
                    ${capabilitiesHTML}
                </div>
            `;
            grid.appendChild(card);
        }
        console.log('loadBackendsTab: Backends tab updated.');
    } catch (error) {
        console.error('loadBackendsTab: Error loading backends tab:', error);
        grid.innerHTML = `<div class="error-state">Error loading backends: ${error.message}</div>`;
    }
}

// Placeholder functions for VFS and Vector/KB formatting (if not already defined)
function formatCachePerformance(data) {
    if (!data.tiered_cache && !data.semantic_cache) {
        return `<p>No cache data available</p>`;
    }
    
    let html = '';
    
    if (data.tiered_cache) {
        const tc = data.tiered_cache;
        html += `
            <div class="cache-section">
                <h4>Tiered Cache</h4>
                <div class="cache-tier">
                    <strong>Memory Tier:</strong>
                    <p>Hit Rate: ${(tc.memory_tier?.hit_rate * 100 || 0).toFixed(1)}%</p>
                    <p>Size: ${formatBytes((tc.memory_tier?.size_mb || 0) * 1024 * 1024)}</p>
                    <p>Items: ${tc.memory_tier?.items || 0}</p>
                    <p>Avg Item Size: ${tc.memory_tier?.average_item_size || 'N/A'}</p>
                    <p>Evictions/hr: ${tc.memory_tier?.evictions_per_hour || 0}</p>
                </div>
                <div class="cache-tier">
                    <strong>Disk Tier:</strong>
                    <p>Hit Rate: ${(tc.disk_tier?.hit_rate * 100 || 0).toFixed(1)}%</p>
                    <p>Size: ${formatBytes((tc.disk_tier?.size_gb || 0) * 1024 * 1024 * 1024)}</p>
                    <p>Items: ${tc.disk_tier?.items || 0}</p>
                    <p>Read Latency: ${tc.disk_tier?.read_latency_ms || 0}ms</p>
                    <p>Write Latency: ${tc.disk_tier?.write_latency_ms || 0}ms</p>
                </div>
                <p><strong>Predictive Accuracy:</strong> ${(tc.predictive_accuracy * 100 || 0).toFixed(1)}%</p>
                <p><strong>Prefetch Efficiency:</strong> ${(tc.prefetch_efficiency * 100 || 0).toFixed(1)}%</p>
            </div>
        `;
    }
    
    if (data.semantic_cache) {
        const sc = data.semantic_cache;
        html += `
            <div class="cache-section">
                <h4>Semantic Cache</h4>
                <p><strong>Model:</strong> ${sc.embedding_model || 'N/A'}</p>
                <p><strong>Similarity Threshold:</strong> ${sc.similarity_threshold || 0}</p>
                <p><strong>Cache Entries:</strong> ${sc.cache_entries || 0}</p>
                <p><strong>Exact Matches:</strong> ${sc.exact_matches || 0}</p>
                <p><strong>Similarity Matches:</strong> ${sc.similarity_matches || 0}</p>
                <p><strong>Utilization:</strong> ${(sc.cache_utilization * 100 || 0).toFixed(1)}%</p>
                <p><strong>Avg Similarity:</strong> ${(sc.average_similarity * 100 || 0).toFixed(1)}%</p>
            </div>
        `;
    }
    
    return html;
}
function formatFilesystemStatus(data) {
    if (!data.disk_usage && !data.ipfs_kit_usage && !data.io_stats) {
        return `<p>No filesystem data available</p>`;
    }
    
    let html = '';
    
    if (data.disk_usage) {
        const du = data.disk_usage;
        html += `
            <div class="filesystem-section">
                <h4>Disk Usage</h4>
                <p><strong>Total:</strong> ${formatBytes(du.total_gb * 1024 * 1024 * 1024)}</p>
                <p><strong>Used:</strong> ${formatBytes(du.used_gb * 1024 * 1024 * 1024)} (${du.usage_percent?.toFixed(1)}%)</p>
                <p><strong>Free:</strong> ${formatBytes(du.free_gb * 1024 * 1024 * 1024)}</p>
                <div class="progress-bar" style="margin: 5px 0;">
                    <div class="progress-fill" style="width: ${du.usage_percent || 0}%; background-color: ${du.usage_percent > 80 ? '#f44336' : '#4CAF50'};"></div>
                </div>
            </div>
        `;
    }
    
    if (data.ipfs_kit_usage) {
        const iku = data.ipfs_kit_usage;
        html += `
            <div class="filesystem-section">
                <h4>IPFS Kit Usage</h4>
                <p><strong>Size:</strong> ${formatBytes(iku.total_size_mb * 1024 * 1024)}</p>
                <p><strong>Files:</strong> ${iku.total_files || 0}</p>
                <p><strong>Avg File Size:</strong> ${formatBytes((iku.average_file_size_kb || 0) * 1024)}</p>
            </div>
        `;
    }
    
    if (data.io_stats) {
        const io = data.io_stats;
        html += `
            <div class="filesystem-section">
                <h4>I/O Statistics</h4>
                <p><strong>Read Ops/sec:</strong> ${io.read_ops_per_sec?.toFixed(1) || 0}</p>
                <p><strong>Write Ops/sec:</strong> ${io.write_ops_per_sec?.toFixed(1) || 0}</p>
                <p><strong>Read Bandwidth:</strong> ${io.read_bandwidth_mbps?.toFixed(1) || 0} MB/s</p>
                <p><strong>Write Bandwidth:</strong> ${io.write_bandwidth_mbps?.toFixed(1) || 0} MB/s</p>
                <p><strong>I/O Utilization:</strong> ${io.io_utilization_percent?.toFixed(1) || 0}%</p>
            </div>
        `;
    }
    
    return html;
}
function formatAccessPatterns(data) {
    if (!data.hot_content && !data.operation_distribution && !data.temporal_patterns) {
        return `<p>No access pattern data available</p>`;
    }
    
    let html = '';
    
    if (data.hot_content && data.hot_content.length > 0) {
        html += `
            <div class="access-section">
                <h4>Hot Content</h4>
                ${data.hot_content.slice(0, 5).map(item => `
                    <div class="hot-item">
                        <p><strong>${item.path}</strong></p>
                        <p>Accesses: ${item.access_count} | Size: ${formatBytes(item.size_kb * 1024)}</p>
                        <p>Last: ${new Date(item.last_accessed).toLocaleString()}</p>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    if (data.operation_distribution) {
        const od = data.operation_distribution;
        html += `
            <div class="access-section">
                <h4>Operation Distribution</h4>
                <p><strong>Read Operations:</strong> ${od.read_operations || 0}</p>
                <p><strong>Write Operations:</strong> ${od.write_operations || 0}</p>
                <p><strong>Search Operations:</strong> ${od.search_operations || 0}</p>
                <p><strong>Cache Operations:</strong> ${od.cache_operations || 0}</p>
            </div>
        `;
    }
    
    if (data.temporal_patterns && data.temporal_patterns.peak_hours) {
        const tp = data.temporal_patterns;
        html += `
            <div class="access-section">
                <h4>Temporal Patterns</h4>
                <p><strong>Peak Hours:</strong> ${tp.peak_hours.join(', ')}</p>
                <p><strong>Low Activity:</strong> ${tp.low_activity_hours.join(', ')}</p>
            </div>
        `;
    }
    
    if (data.access_frequency) {
        const af = data.access_frequency;
        html += `
            <div class="access-section">
                <h4>Access Frequency</h4>
                <p><strong>Very Frequent:</strong> ${af.very_frequent || 0}</p>
                <p><strong>Frequent:</strong> ${af.frequent || 0}</p>
                <p><strong>Moderate:</strong> ${af.moderate || 0}</p>
                <p><strong>Infrequent:</strong> ${af.infrequent || 0}</p>
            </div>
        `;
    }
    
    return html;
}
function formatResourceUsage(data) {
    if (!data.memory_usage && !data.disk_usage && !data.cpu_usage && !data.network_usage) {
        return `<p>No resource usage data available</p>`;
    }
    
    let html = '';
    
    if (data.memory_usage) {
        const mu = data.memory_usage;
        html += `
            <div class="resource-section">
                <h4>Memory Usage</h4>
                <p><strong>Cache:</strong> ${formatBytes((mu.cache_mb || 0) * 1024 * 1024)}</p>
                <p><strong>Index:</strong> ${formatBytes((mu.index_mb || 0) * 1024 * 1024)}</p>
                <p><strong>System Total:</strong> ${formatBytes((mu.system_total_mb || 0) * 1024 * 1024)}</p>
                <p><strong>System Available:</strong> ${formatBytes((mu.system_available_mb || 0) * 1024 * 1024)}</p>
                <p><strong>System Used:</strong> ${mu.system_used_percent?.toFixed(1) || 0}%</p>
            </div>
        `;
    }
    
    if (data.disk_usage) {
        const du = data.disk_usage;
        html += `
            <div class="resource-section">
                <h4>Disk Usage</h4>
                <p><strong>Cache:</strong> ${formatBytes((du.cache_gb || 0) * 1024 * 1024 * 1024)}</p>
                <p><strong>Index:</strong> ${formatBytes((du.index_gb || 0) * 1024 * 1024 * 1024)}</p>
                <p><strong>Total Used:</strong> ${formatBytes((du.total_used_gb || 0) * 1024 * 1024 * 1024)}</p>
            </div>
        `;
    }
    
    if (data.cpu_usage) {
        const cu = data.cpu_usage;
        html += `
            <div class="resource-section">
                <h4>CPU Usage</h4>
                <p><strong>System:</strong> ${cu.system_percent?.toFixed(1) || 0}%</p>
                <p><strong>Indexing (est):</strong> ${cu.indexing_estimated?.toFixed(1) || 0}%</p>
                <p><strong>Search (est):</strong> ${cu.search_estimated?.toFixed(1) || 0}%</p>
                <p><strong>Cache Mgmt (est):</strong> ${cu.cache_management_estimated?.toFixed(1) || 0}%</p>
            </div>
        `;
    }
    
    if (data.network_usage) {
        const nu = data.network_usage;
        html += `
            <div class="resource-section">
                <h4>Network Usage</h4>
                <p><strong>Connections:</strong> ${nu.estimated_connections || 0}</p>
                <p><strong>Bandwidth Utilization:</strong> ${(nu.bandwidth_utilization * 100 || 0).toFixed(1)}%</p>
            </div>
        `;
    }
    
    return html;
}
function formatTieredCacheDetails(data) {
    // This is redundant with formatCachePerformance, but keeping for compatibility
    if (!data.tiered_cache) {
        return `<p>No tiered cache data available</p>`;
    }
    
    const tc = data.tiered_cache;
    return `
        <div class="tiered-cache-details">
            <p><strong>Memory Tier Hit Rate:</strong> ${(tc.memory_tier?.hit_rate * 100 || 0).toFixed(1)}%</p>
            <p><strong>Disk Tier Hit Rate:</strong> ${(tc.disk_tier?.hit_rate * 100 || 0).toFixed(1)}%</p>
            <p><strong>Predictive Accuracy:</strong> ${(tc.predictive_accuracy * 100 || 0).toFixed(1)}%</p>
            <p><strong>Prefetch Efficiency:</strong> ${(tc.prefetch_efficiency * 100 || 0).toFixed(1)}%</p>
        </div>
    `;
}

function formatHotContentAnalysis(data) {
    if (!data.hot_content || data.hot_content.length === 0) {
        return `<p>No hot content data available</p>`;
    }
    
    const topFiles = data.hot_content.slice(0, 3);
    return `
        <div class="hot-content-analysis">
            <h4>Most Accessed Files</h4>
            ${topFiles.map(file => `
                <div class="hot-file">
                    <p><strong>${file.path.split('/').pop()}</strong></p>
                    <p>${file.access_count} accesses • ${formatBytes(file.size_kb * 1024)}</p>
                </div>
            `).join('')}
            <p><strong>Total Hot Files:</strong> ${data.hot_content.length}</p>
        </div>
    `;
}
function formatVectorIndexStatus(data) {
    if (!data.index_health && !data.total_vectors) {
        return `<p>No vector index data available</p>`;
    }
    
    return `
        <div class="vector-index-status">
            <p><strong>Health:</strong> <span style="color: ${data.index_health === 'healthy' ? 'green' : data.index_health === 'initializing' ? 'orange' : 'red'}">${data.index_health || 'unknown'}</span></p>
            <p><strong>Total Vectors:</strong> ${(data.total_vectors || 0).toLocaleString()}</p>
            <p><strong>Index Type:</strong> ${(data.index_type || 'unknown').toUpperCase()}</p>
            <p><strong>Dimensions:</strong> ${data.dimension || 0}</p>
            <p><strong>Clusters:</strong> ${data.clusters || 0}</p>
            <p><strong>Index Size:</strong> ${formatBytes((data.index_size_mb || 0) * 1024 * 1024)}</p>
            <p><strong>Last Updated:</strong> ${data.last_updated ? new Date(data.last_updated).toLocaleString() : 'Never'}</p>
            <p><strong>Update Frequency:</strong> ${data.update_frequency || 'unknown'}</p>
            ${data.search_performance ? `
                <div class="search-performance">
                    <h5>Search Performance</h5>
                    <p>Avg Query Time: ${data.search_performance.average_query_time_ms || 0}ms</p>
                    <p>Queries/Second: ${data.search_performance.queries_per_second || 0}</p>
                    <p>Recall@10: ${(data.search_performance.recall_at_10 * 100 || 0).toFixed(1)}%</p>
                    <p>Precision@10: ${(data.search_performance.precision_at_10 * 100 || 0).toFixed(1)}%</p>
                    <p>Total Searches: ${(data.search_performance.total_searches || 0).toLocaleString()}</p>
                </div>
            ` : ''}
            ${data.content_distribution ? `
                <div class="content-distribution">
                    <h5>Content Distribution</h5>
                    <p>Text Documents: ${(data.content_distribution.text_documents || 0).toLocaleString()}</p>
                    <p>Code Files: ${(data.content_distribution.code_files || 0).toLocaleString()}</p>
                    <p>Markdown Files: ${(data.content_distribution.markdown_files || 0).toLocaleString()}</p>
                    <p>JSON Objects: ${(data.content_distribution.json_objects || 0).toLocaleString()}</p>
                </div>
            ` : ''}
        </div>
    `;
}

function formatKnowledgeGraphStatus(data) {
    if (!data.graph_health && !data.nodes && !data.edges) {
        return `<p>No knowledge graph data available</p>`;
    }
    
    return `
        <div class="knowledge-graph-status">
            <p><strong>Graph Health:</strong> <span style="color: ${data.graph_health === 'healthy' ? 'green' : data.graph_health === 'empty' ? 'orange' : 'red'}">${data.graph_health || 'unknown'}</span></p>
            ${data.nodes ? `
                <div class="graph-nodes">
                    <h5>Nodes</h5>
                    <p>Total: ${(data.nodes.total || 0).toLocaleString()}</p>
                    <p>Documents: ${(data.nodes.documents || 0).toLocaleString()}</p>
                    <p>Entities: ${(data.nodes.entities || 0).toLocaleString()}</p>
                    <p>Concepts: ${(data.nodes.concepts || 0).toLocaleString()}</p>
                    <p>Relations: ${(data.nodes.relations || 0).toLocaleString()}</p>
                </div>
            ` : ''}
            ${data.edges ? `
                <div class="graph-edges">
                    <h5>Edges</h5>
                    <p>Total: ${(data.edges.total || 0).toLocaleString()}</p>
                    <p>Semantic Links: ${(data.edges.semantic_links || 0).toLocaleString()}</p>
                    <p>Reference Links: ${(data.edges.reference_links || 0).toLocaleString()}</p>
                    <p>Temporal Links: ${(data.edges.temporal_links || 0).toLocaleString()}</p>
                </div>
            ` : ''}
            ${data.graph_metrics ? `
                <div class="graph-metrics">
                    <h5>Graph Metrics</h5>
                    <p>Density: ${data.graph_metrics.density || 0}</p>
                    <p>Clustering Coefficient: ${data.graph_metrics.clustering_coefficient?.toFixed(2) || 0}</p>
                    <p>Avg Path Length: ${data.graph_metrics.average_path_length?.toFixed(1) || 0}</p>
                    <p>Modularity: ${data.graph_metrics.modularity?.toFixed(2) || 0}</p>
                    <p>Connected Components: ${data.graph_metrics.connected_components || 0}</p>
                </div>
            ` : ''}
            ${data.content_analysis ? `
                <div class="content-analysis">
                    <h5>Content Analysis</h5>
                    <p>Languages: ${data.content_analysis.languages_detected?.join(', ') || 'none'}</p>
                    <p>Topics Identified: ${data.content_analysis.topics_identified || 0}</p>
                    ${data.content_analysis.sentiment_distribution ? `
                        <div class="sentiment">
                            <p>Sentiment - Positive: ${(data.content_analysis.sentiment_distribution.positive * 100 || 0).toFixed(1)}%</p>
                            <p>Neutral: ${(data.content_analysis.sentiment_distribution.neutral * 100 || 0).toFixed(1)}%</p>
                            <p>Negative: ${(data.content_analysis.sentiment_distribution.negative * 100 || 0).toFixed(1)}%</p>
                        </div>
                    ` : ''}
                    ${data.content_analysis.complexity_scores ? `
                        <div class="complexity">
                            <p>Complexity - Low: ${(data.content_analysis.complexity_scores.low * 100 || 0).toFixed(1)}%</p>
                            <p>Medium: ${(data.content_analysis.complexity_scores.medium * 100 || 0).toFixed(1)}%</p>
                            <p>High: ${(data.content_analysis.complexity_scores.high * 100 || 0).toFixed(1)}%</p>
                        </div>
                    ` : ''}
                </div>
            ` : ''}
            <p><strong>Last Updated:</strong> ${data.last_updated ? new Date(data.last_updated).toLocaleString() : 'Never'}</p>
        </div>
    `;
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
// Vector & KB Search Functions
async function performVectorSearch() {
    console.log('performVectorSearch: Starting vector search');
    const query = document.getElementById('vectorSearch').value.trim();
    if (!query) {
        alert('Please enter a search query');
        return;
    }
    
    const resultsContainer = document.getElementById('searchResults');
    const resultsContent = document.getElementById('searchResultsContent');
    
    resultsContainer.style.display = 'block';
    resultsContent.innerHTML = '<div style="text-align: center; padding: 20px;">🔍 Searching vector database...</div>';
    
    try {
        const response = await dashboardAPI.fetch(`/api/vector/search?query=${encodeURIComponent(query)}&limit=10`);
        
        if (response.success && response.results) {
            resultsContent.innerHTML = formatVectorSearchResults(response);
        } else {
            resultsContent.innerHTML = `<div style="color: red;">Vector search failed: ${response.error || 'Unknown error'}</div>`;
        }
        
    } catch (error) {
        console.error('performVectorSearch: Error:', error);
        resultsContent.innerHTML = `<div style="color: red;">Error performing vector search: ${error.message}</div>`;
    }
}

async function performEntitySearch() {
    console.log('performEntitySearch: Starting entity search');
    const entityId = document.getElementById('entitySearch').value.trim();
    if (!entityId) {
        alert('Please enter an entity ID');
        return;
    }
    
    const resultsContainer = document.getElementById('searchResults');
    const resultsContent = document.getElementById('searchResultsContent');
    
    resultsContainer.style.display = 'block';
    resultsContent.innerHTML = '<div style="text-align: center; padding: 20px;">🕸️ Exploring knowledge graph...</div>';
    
    try {
        const response = await dashboardAPI.fetch(`/api/kg/search?entity_id=${encodeURIComponent(entityId)}`);
        
        if (response.success && response.entity) {
            resultsContent.innerHTML = formatEntitySearchResults(response);
        } else {
            resultsContent.innerHTML = `<div style="color: red;">Entity search failed: ${response.error || 'Unknown error'}</div>`;
        }
        
    } catch (error) {
        console.error('performEntitySearch: Error:', error);
        resultsContent.innerHTML = `<div style="color: red;">Error exploring entity: ${error.message}</div>`;
    }
}

async function listVectorCollections() {
    console.log('listVectorCollections: Starting collection listing');
    const resultsContainer = document.getElementById('searchResults');
    const resultsContent = document.getElementById('searchResultsContent');
    
    resultsContainer.style.display = 'block';
    resultsContent.innerHTML = '<div style="text-align: center; padding: 20px;">📋 Loading vector collections...</div>';
    
    try {
        const response = await dashboardAPI.fetch('/api/vector/collections');
        
        if (response.success && response.collections) {
            resultsContent.innerHTML = formatVectorCollections(response);
        } else {
            resultsContent.innerHTML = `<div style="color: red;">Failed to load collections: ${response.error || 'Unknown error'}</div>`;
        }
        
    } catch (error) {
        console.error('listVectorCollections: Error:', error);
        resultsContent.innerHTML = `<div style="color: red;">Error loading collections: ${error.message}</div>`;
    }
}

function formatVectorSearchResults(response) {
    const { query, results, total_found, search_time_ms } = response;
    
    if (!results || results.length === 0) {
        return `
            <div style="text-align: center; color: #666;">
                <h4>No Results Found</h4>
                <p>No vectors found matching "${query}"</p>
            </div>
        `;
    }
    
    let html = `
        <div style="margin-bottom: 15px;">
            <h4>🔍 Vector Search Results for "${query}"</h4>
            <p style="color: #666;">Found ${total_found} results in ${search_time_ms}ms</p>
        </div>
        <div style="max-height: 400px; overflow-y: auto;">
    `;
    
    results.forEach((result, index) => {
        const similarity = (result.score * 100).toFixed(1);
        html += `
            <div style="border: 1px solid #ddd; border-radius: 4px; padding: 15px; margin-bottom: 10px; background: ${index % 2 === 0 ? '#f9f9f9' : 'white'};">
                <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 10px;">
                    <strong style="color: #007bff;">${result.cid || result.id || 'Unknown'}</strong>
                    <span style="background: #e3f2fd; color: #1976d2; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                        ${similarity}% match
                    </span>
                </div>
                ${result.title ? `<h5 style="margin: 5px 0; color: #333;">${result.title}</h5>` : ''}
                ${result.content ? `<p style="margin: 5px 0; color: #666; font-size: 14px;">${result.content.substring(0, 200)}${result.content.length > 200 ? '...' : ''}</p>` : ''}
                <div style="display: flex; gap: 10px; margin-top: 10px; font-size: 12px; color: #888;">
                    ${result.content_type ? `<span>Type: ${result.content_type}</span>` : ''}
                    ${result.created_at ? `<span>Created: ${new Date(result.created_at).toLocaleDateString()}</span>` : ''}
                    ${result.size ? `<span>Size: ${formatBytes(result.size)}</span>` : ''}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
}

function formatEntitySearchResults(response) {
    const { entity_id, entity, related_entities } = response;
    
    let html = `
        <div style="margin-bottom: 15px;">
            <h4>🕸️ Entity Details for "${entity_id}"</h4>
        </div>
    `;
    
    if (entity) {
        html += `
            <div style="border: 1px solid #ddd; border-radius: 4px; padding: 15px; margin-bottom: 15px; background: #f9f9f9;">
                <h5 style="color: #333; margin-bottom: 10px;">Entity Information</h5>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div><strong>ID:</strong> ${entity.id || entity_id}</div>
                    <div><strong>Type:</strong> ${entity.type || 'Unknown'}</div>
                    ${entity.created_at ? `<div><strong>Created:</strong> ${new Date(entity.created_at * 1000).toLocaleString()}</div>` : ''}
                    ${entity.updated_at ? `<div><strong>Updated:</strong> ${new Date(entity.updated_at * 1000).toLocaleString()}</div>` : ''}
                </div>
                ${entity.properties ? `
                    <div style="margin-top: 10px;">
                        <strong>Properties:</strong>
                        <pre style="background: white; padding: 10px; border-radius: 4px; margin-top: 5px; font-size: 12px; overflow-x: auto;">${JSON.stringify(entity.properties, null, 2)}</pre>
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    if (related_entities && related_entities.length > 0) {
        html += `
            <div style="border: 1px solid #ddd; border-radius: 4px; padding: 15px; background: white;">
                <h5 style="color: #333; margin-bottom: 10px;">Related Entities (${related_entities.length})</h5>
                <div style="max-height: 300px; overflow-y: auto;">
        `;
        
        related_entities.forEach((rel, index) => {
            html += `
                <div style="border-bottom: 1px solid #eee; padding: 10px 0; ${index === related_entities.length - 1 ? 'border-bottom: none;' : ''}">
                    <div style="display: flex; justify-content: between; align-items: center;">
                        <strong style="color: #007bff;">${rel.entity_id || rel.id}</strong>
                        <span style="background: #e8f5e8; color: #2e7d32; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                            ${rel.relationship_type || 'connected'}
                        </span>
                    </div>
                    ${rel.type ? `<div style="font-size: 12px; color: #666; margin-top: 2px;">Type: ${rel.type}</div>` : ''}
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    } else {
        html += `
            <div style="text-align: center; color: #666; padding: 20px; border: 1px solid #ddd; border-radius: 4px;">
                No related entities found
            </div>
        `;
    }
    
    return html;
}

function formatVectorCollections(response) {
    const { collections, total_collections } = response;
    
    if (!collections || collections.length === 0) {
        return `
            <div style="text-align: center; color: #666;">
                <h4>No Collections Found</h4>
                <p>No vector collections are currently available</p>
            </div>
        `;
    }
    
    let html = `
        <div style="margin-bottom: 15px;">
            <h4>📋 Vector Collections (${total_collections})</h4>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
    `;
    
    collections.forEach(collection => {
        html += `
            <div style="border: 1px solid #ddd; border-radius: 4px; padding: 15px; background: white;">
                <h5 style="color: #333; margin-bottom: 10px;">${collection.name}</h5>
                <div style="font-size: 14px; color: #666;">
                    <div><strong>Type:</strong> ${collection.type}</div>
                    <div><strong>Documents:</strong> ${collection.document_count}</div>
                    <div><strong>Vectors:</strong> ${collection.vector_count}</div>
                </div>
                <button onclick="searchInCollection('${collection.name}')" 
                        style="margin-top: 10px; padding: 5px 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                    Search in Collection
                </button>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
}

function searchInCollection(collectionName) {
    const query = prompt(`Enter search query for collection "${collectionName}":`);
    if (query) {
        document.getElementById('vectorSearch').value = `collection:${collectionName} ${query}`;
        performVectorSearch();
    }
}

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
window.loadLogsTab = loadLogsTab;
window.filterLogs = filterLogs;
window.clearLogFilters = clearLogFilters;
window.filterVFSJournal = filterVFSJournal;
window.clearVFSJournalFilters = clearVFSJournalFilters;
window.showLogSection = showLogSection;
window.loadVFSJournal = loadVFSJournal;

// Vector & KB Search Functions
window.performVectorSearch = performVectorSearch;
window.performEntitySearch = performEntitySearch;
window.listVectorCollections = listVectorCollections;
window.searchInCollection = searchInCollection;