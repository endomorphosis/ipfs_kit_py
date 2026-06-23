/**
 * Vector Knowledge Base Tab Functionality
 */

async function loadVectorKBTab() {
    console.log('Loading Vector/KB tab...');
    
    const container = document.getElementById('vectorIndexStatus') || 
                     document.querySelector('#vector-kb .stats-grid');
    
    if (!container) {
        console.error('Vector/KB tab container not found');
        return;
    }
    
    try {
        const [indexStatus, protocols, walrus] = await Promise.all([
            dashboardAPI.getVFSGraphRAGStatus(),
            dashboardAPI.listFSSpecProtocols(),
            dashboardAPI.getWalrusStatus()
        ]);
        const statusData = indexStatus?.result || indexStatus?.data || indexStatus;
        const protocolData = protocols?.result || protocols?.data || protocols;
        const walrusData = walrus?.result || walrus?.data || walrus;
        const counts = statusData?.status?.counts || {};
        const protocolList = protocolData?.protocols || [];

        container.innerHTML = `
            <div class="stat-card">
                <h3>VFS GraphRAG Index</h3>
                <div class="metric"><span class="metric-label">Objects</span><span class="metric-value">${counts.objects || 0}</span></div>
                <div class="metric"><span class="metric-label">Chunks</span><span class="metric-value">${counts.chunks || 0}</span></div>
                <div class="metric"><span class="metric-label">Entities</span><span class="metric-value">${counts.entities || 0}</span></div>
                <div class="metric"><span class="metric-label">Relationships</span><span class="metric-value">${counts.relationships || 0}</span></div>
            </div>
            <div class="stat-card">
                <h3>Search</h3>
                <div class="form-group">
                    <input id="vfsGraphRAGQuery" class="form-control" type="text" placeholder="Search indexed VFS records">
                </div>
                <button class="btn btn-primary" onclick="runVFSGraphRAGSearch()">Search</button>
                <div id="vfsGraphRAGResults" class="expandable-content"></div>
            </div>
            <div class="stat-card">
                <h3>fsspec Protocols</h3>
                <div class="metric"><span class="metric-label">Protocols</span><span class="metric-value">${protocolList.join(', ') || 'Unavailable'}</span></div>
                <div class="metric"><span class="metric-label">Walrus</span><span class="metric-value">${walrusData?.configured ? 'Configured' : 'Needs Config'}</span></div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading Vector/KB data:', error);
        container.innerHTML = `
            <div class="stat-card">
                <h3>VFS GraphRAG</h3>
                <div class="metric"><span class="metric-label">Status</span><span class="metric-value">Unavailable</span></div>
            </div>
        `;
    }
}

async function runVFSGraphRAGSearch() {
    const input = document.getElementById('vfsGraphRAGQuery');
    const results = document.getElementById('vfsGraphRAGResults');
    if (!input || !results) return;
    results.innerHTML = 'Searching...';
    try {
        const response = await dashboardAPI.searchVFSGraphRAG(input.value || '', { top_k: 10 });
        const data = response?.result || response?.data || response;
        const items = data?.results || [];
        results.innerHTML = items.length ? items.map(item => `
            <div class="metric">
                <span class="metric-label">${item.path || item.record_id || 'record'}</span>
                <span class="metric-value">${Number(item.score || 0).toFixed(3)}</span>
            </div>
        `).join('') : '<div class="metric"><span class="metric-label">Results</span><span class="metric-value">0</span></div>';
    } catch (error) {
        console.error('VFS GraphRAG search failed:', error);
        results.innerHTML = 'Search failed';
    }
}

async function refreshMonitoring() {
    console.log('Refreshing monitoring data...');
    
    try {
        // Try to get monitoring data from API
        const [metricsData, alertsData, comprehensiveData] = await Promise.all([
            dashboardAPI.getMonitoringMetrics(),
            dashboardAPI.getMonitoringAlerts(),
            dashboardAPI.getComprehensiveMonitoring()
        ]);
        
        updateMonitoringDisplay(metricsData, alertsData, comprehensiveData);
        
    } catch (error) {
        console.error('Error refreshing monitoring data:', error);
        displayMonitoringError();
    }
}

function updateMonitoringDisplay(metrics, alerts, comprehensive) {
    const container = document.getElementById('monitoringContent') ||
                     document.querySelector('#monitoring .stats-grid');
    
    if (!container) return;
    
    container.innerHTML = `
        <div class="stat-card">
            <h3>📊 System Monitoring</h3>
            <p>Advanced monitoring features are being implemented.</p>
            <div class="metric">
                <span class="metric-label">Metrics Available</span>
                <span class="metric-value">${metrics?.success ? 'Yes' : 'No'}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Alerts Available</span>
                <span class="metric-value">${alerts?.success ? 'Yes' : 'No'}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Comprehensive Data</span>
                <span class="metric-value">${comprehensive?.success ? 'Yes' : 'No'}</span>
            </div>
        </div>
    `;
}

function displayMonitoringError() {
    const container = document.getElementById('monitoringContent') ||
                     document.querySelector('#monitoring .stats-grid');
    
    if (container) {
        container.innerHTML = `
            <div class="stat-card">
                <h3>📊 System Monitoring</h3>
                <p style="color: orange;">Monitoring endpoints are not yet implemented on the server.</p>
                <p>This feature will be available in a future update.</p>
            </div>
        `;
    }
}

async function loadConfigurationTab() {
    console.log('Loading Configuration tab...');
    
    const container = document.getElementById('configurationContent') ||
                     document.querySelector('#configuration .stats-grid');
    
    if (!container) {
        console.error('Configuration tab container not found');
        return;
    }
    
    container.innerHTML = `
        <div class="stat-card">
            <h3>⚙️ Configuration</h3>
            <p>Configuration management interface is being developed.</p>
            <div class="metric">
                <span class="metric-label">Backend Configs</span>
                <span class="metric-value">${Object.keys(currentBackendData?.backends || {}).length}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Editable</span>
                <span class="metric-value">Coming Soon</span>
            </div>
        </div>
    `;
}

async function loadBackendsTab() {
    console.log('Loading Backends tab...');
    
    const container = document.getElementById('backendsGrid') || 
                     document.querySelector('#backends .backend-grid');
    
    if (!container) {
        console.error('Backends tab container not found');
        return;
    }
    
    try {
        // Load backend data
        const backendsData = await dashboardAPI.getBackends();
        
        if (backendsData.success) {
            displayBackendsData(container, backendsData);
        } else {
            displayBackendsError(container, backendsData.error);
        }
    } catch (error) {
        console.error('Error loading backends data:', error);
        displayBackendsError(container, error.message);
    }
}

function displayBackendsData(container, data) {
    const backends = data.backends || {};
    const backendNames = Object.keys(backends);
    
    container.innerHTML = `
        <div class="stat-card">
            <h3>🔧 Backend Services</h3>
            <div class="backends-grid">
                ${backendNames.map(name => {
                    const backend = backends[name];
                    const statusColor = backend.healthy ? '#4CAF50' : '#FF5722';
                    const statusText = backend.healthy ? 'Healthy' : 'Unhealthy';
                    
                    return `
                        <div class="backend-item">
                            <div class="backend-header">
                                <h4>${name}</h4>
                                <span class="status" style="color: ${statusColor};">${statusText}</span>
                            </div>
                            <div class="backend-details">
                                <div class="metric">
                                    <span class="metric-label">Type</span>
                                    <span class="metric-value">${backend.type || 'Unknown'}</span>
                                </div>
                                <div class="metric">
                                    <span class="metric-label">Status</span>
                                    <span class="metric-value">${backend.status || 'Unknown'}</span>
                                </div>
                                ${backend.url ? `
                                <div class="metric">
                                    <span class="metric-label">URL</span>
                                    <span class="metric-value">${backend.url}</span>
                                </div>
                                ` : ''}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
            ${backendNames.length === 0 ? '<p>No backends configured.</p>' : ''}
        </div>
    `;
}

function displayBackendsError(container, error) {
    container.innerHTML = `
        <div class="stat-card">
            <h3>🔧 Backend Services</h3>
            <p style="color: orange;">Error loading backend data: ${error}</p>
            <p>Please check the server configuration.</p>
        </div>
    `;
}

// Expose functions globally for HTML compatibility
window.loadVectorKBTab = loadVectorKBTab;
window.runVFSGraphRAGSearch = runVFSGraphRAGSearch;
window.refreshMonitoring = refreshMonitoring;
window.loadConfigurationTab = loadConfigurationTab;
window.loadBackendsTab = loadBackendsTab;
