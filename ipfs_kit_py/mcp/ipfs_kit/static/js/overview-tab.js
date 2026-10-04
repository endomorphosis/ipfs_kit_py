/**
 * Overview Tab Functionality
 * Handles system health and backend status display
 */

async function refreshData() {
    console.log('refreshData: Starting overview data refresh...');
    
    // Check if dashboardAPI is available
    if (typeof dashboardAPI === 'undefined') {
        console.warn('refreshData: dashboardAPI not yet loaded, skipping refresh');
        return;
    }
    
    try {
        // Get health data
        const healthData = await dashboardAPI.getHealth();
        console.log('refreshData: Received health data:', healthData);
        
        if (healthData) {
            updateSystemHealth(healthData);
            
            // Update backend data if available
            if (healthData.backend_health && healthData.backend_health.backends) {
                updateBackendStatus(healthData.backend_health);
            }
            
            // Update last refresh time
            updateLastRefreshTime();
        }
        
    } catch (error) {
        console.error('refreshData: Error refreshing overview data:', error);
        showErrorMessage('Failed to load overview data: ' + error.message);
    }
}

function updateSystemHealth(data) {
    console.log('updateSystemHealth: Processing data:', data);
    
    if (!data) {
        console.warn('updateSystemHealth: No data provided');
        return;
    }
    
    // Find the system status container
    const systemStatusElement = document.getElementById('systemStatus');
    if (!systemStatusElement) {
        console.warn('updateSystemHealth: systemStatus element not found');
        return;
    }
    
    // Create system status HTML
    const statusClass = data.status === 'running' ? 'healthy' : 'unhealthy';
    const statusIcon = data.status === 'running' ? '🟢' : '🔴';
    
    systemStatusElement.innerHTML = `
        <div class="system-health-card">
            <h4>${statusIcon} System Status</h4>
            <div class="health-metrics">
                <div class="metric">
                    <span class="metric-label">Status:</span>
                    <span class="metric-value status-${statusClass}">${data.status || 'unknown'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Uptime:</span>
                    <span class="metric-value">${formatUptime(data.uptime_seconds || 0)}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Memory:</span>
                    <span class="metric-value">${data.memory_usage_mb ? data.memory_usage_mb.toFixed(1) + ' MB' : 'N/A'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">CPU:</span>
                    <span class="metric-value">${data.cpu_usage_percent !== undefined ? data.cpu_usage_percent.toFixed(1) + '%' : 'N/A'}</span>
                </div>
            </div>
        </div>
    `;
    
    console.log('updateSystemHealth: System status updated');
}

function updateBackendStatus(backendHealthData) {
    console.log('updateBackendStatus: Processing backend data:', backendHealthData);
    
    if (!backendHealthData || !backendHealthData.success || !backendHealthData.backends) {
        console.warn('updateBackendStatus: Invalid backend data structure');
        return;
    }
    
    const container = document.getElementById('backendSummary');
    if (!container) {
        console.warn('updateBackendStatus: backendSummary element not found');
        return;
    }
    
    const backends = backendHealthData.backends;
    const backendKeys = Object.keys(backends);
    
    let healthyCount = 0;
    let totalCount = backendKeys.length;
    
    // Count healthy backends
    backendKeys.forEach(key => {
        const backend = backends[key];
        if (backend.health === 'healthy') {
            healthyCount++;
        }
    });
    
    // Create backend summary HTML
    const summaryHtml = `
        <div class="backend-summary-card">
            <h4>🔧 Backend Summary</h4>
            <div class="backend-overview">
                <div class="metric">
                    <span class="metric-label">Total Backends:</span>
                    <span class="metric-value">${totalCount}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Healthy:</span>
                    <span class="metric-value status-healthy">${healthyCount}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Unhealthy:</span>
                    <span class="metric-value status-unhealthy">${totalCount - healthyCount}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Health Rate:</span>
                    <span class="metric-value">${totalCount > 0 ? ((healthyCount / totalCount) * 100).toFixed(1) : 0}%</span>
                </div>
            </div>
        </div>
    `;
    
    container.innerHTML = summaryHtml;
    
    // Update detailed backend grid
    updateBackendGrid(backends);
    
    console.log('updateBackendStatus: Backend summary updated');
}

function updateBackendGrid(backends) {
    const grid = document.getElementById('backendGrid');
    if (!grid) {
        console.warn('updateBackendGrid: backendGrid element not found');
        return;
    }
    
    const backendKeys = Object.keys(backends);
    
    const backendHTML = backendKeys.map(key => {
        const backend = backends[key];
        const isHealthy = backend.health === 'healthy';
        const statusIcon = isHealthy ? '🟢' : '🔴';
        const healthClass = isHealthy ? 'healthy' : 'unhealthy';
        
        return `
            <div class="backend-item ${healthClass}">
                <div class="backend-header">
                    <h4>${statusIcon} ${backend.name}</h4>
                    <span class="status-badge status-${backend.status}">${backend.status}</span>
                </div>
                <div class="backend-details">
                    <div class="metric">
                        <span class="metric-label">Health:</span>
                        <span class="metric-value status-${healthClass}">${backend.health}</span>
                    </div>
                    ${backend.last_check ? `
                        <div class="metric">
                            <span class="metric-label">Last Check:</span>
                            <span class="metric-value">${formatTimestamp(backend.last_check)}</span>
                        </div>
                    ` : ''}
                    ${backend.port ? `
                        <div class="metric">
                            <span class="metric-label">Port:</span>
                            <span class="metric-value">${backend.port}</span>
                        </div>
                    ` : ''}
                    ${backend.errors && backend.errors.length > 0 ? `
                        <div class="backend-errors">
                            <strong>Errors:</strong> ${backend.errors.join(', ')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    grid.innerHTML = backendHTML;
    
    console.log('updateBackendGrid: Backend grid updated with', backendKeys.length, 'backends');
}

function updateLastRefreshTime() {
    const refreshInfo = document.getElementById('refresh-info');
    if (refreshInfo) {
        const now = new Date();
        refreshInfo.textContent = `Last updated: ${now.toLocaleTimeString()}`;
    }
    
    // Update status indicator
    const statusIndicator = document.getElementById('status-indicator');
    if (statusIndicator) {
        statusIndicator.textContent = '🟢 Connected';
    }
}

function formatUptime(seconds) {
    if (!seconds || seconds < 0) return 'N/A';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'N/A';
    
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    } catch (error) {
        console.warn('formatTimestamp: Invalid timestamp:', timestamp);
        return 'Invalid';
    }
}

function showErrorMessage(message) {
    console.error('Error:', message);
    
    // Try to update status indicator
    const statusIndicator = document.getElementById('status-indicator');
    if (statusIndicator) {
        statusIndicator.textContent = '🔴 Error';
    }
    
    // Create or update error container
    let errorContainer = document.getElementById('error-messages');
    if (!errorContainer) {
        errorContainer = createErrorContainer();
    }
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    
    errorContainer.appendChild(errorDiv);
    
    // Auto-remove after 8 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.parentNode.removeChild(errorDiv);
        }
    }, 8000);
}

function createErrorContainer() {
    const container = document.createElement('div');
    container.id = 'error-messages';
    container.className = 'error-container';
    container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        max-width: 400px;
    `;
    document.body.appendChild(container);
    return container;
}

// Export functions globally
window.refreshData = refreshData;
window.updateSystemHealth = updateSystemHealth;
window.updateBackendStatus = updateBackendStatus;
