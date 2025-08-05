"""
Additional Dashboard Templates

This file contains the remaining dashboard templates for complete functionality.
"""

# Backend Management Template
BACKEND_MANAGEMENT_TEMPLATE = '''{% extends "base.html" %}

{% block content %}
<div class="backend-management">
    <h1>Backend Management</h1>
    
    <div class="backend-overview">
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Backends</h3>
                <div class="stat-value">{{ backends_data.total or 0 }}</div>
            </div>
            <div class="stat-card">
                <h3>Healthy</h3>
                <div class="stat-value healthy">{{ backends_data.healthy_count or 0 }}</div>
            </div>
            <div class="stat-card">
                <h3>Unhealthy</h3>
                <div class="stat-value error">{{ backends_data.unhealthy_count or 0 }}</div>
            </div>
            <div class="stat-card">
                <h3>Configured</h3>
                <div class="stat-value">{{ backends_data.configured_count or 0 }}</div>
            </div>
        </div>
    </div>
    
    <div class="backend-controls">
        <button class="btn btn-primary" onclick="refreshBackends()">Refresh All</button>
        <button class="btn btn-success" onclick="testAllBackends()">Test All</button>
        <button class="btn btn-info" onclick="showAddBackendModal()">Add Backend</button>
    </div>
    
    <div class="backends-table">
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Enabled</th>
                    <th>Last Check</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="backends-tbody">
                {% for backend in backends_data.backends %}
                <tr data-backend="{{ backend.name }}">
                    <td class="backend-name">{{ backend.name }}</td>
                    <td class="backend-type">
                        <span class="type-badge {{ backend.type }}">{{ backend.type }}</span>
                    </td>
                    <td class="backend-status">
                        <span class="status-indicator {{ backend.status }}">
                            {{ backend.status.title() }}
                        </span>
                    </td>
                    <td class="backend-enabled">
                        <input type="checkbox" {{ 'checked' if backend.enabled else '' }} 
                               onchange="toggleBackend('{{ backend.name }}', this.checked)">
                    </td>
                    <td class="last-check">{{ backend.last_check or 'Never' }}</td>
                    <td class="backend-actions">
                        <button class="btn btn-sm btn-info" onclick="testBackend('{{ backend.name }}')">Test</button>
                        <button class="btn btn-sm btn-warning" onclick="configureBackend('{{ backend.name }}')">Configure</button>
                        <button class="btn btn-sm btn-danger" onclick="removeBackend('{{ backend.name }}')">Remove</button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div class="backend-details" id="backend-details" style="display: none;">
        <h2>Backend Details</h2>
        <div class="details-content">
            <pre id="details-json"></pre>
        </div>
        <button class="btn btn-secondary" onclick="hideBackendDetails()">Close</button>
    </div>
</div>

<script>
async function refreshBackends() {
    try {
        const response = await fetch('/api/backends');
        const data = await response.json();
        updateBackendsTable(data);
        showNotification('Backends refreshed', 'success');
    } catch (error) {
        showNotification(`Error refreshing backends: ${error.message}`, 'error');
    }
}

async function testBackend(backendName) {
    try {
        const response = await fetch(`/api/backends/${backendName}/test`, { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            showNotification(`Backend ${backendName} test successful`, 'success');
        } else {
            showNotification(`Backend ${backendName} test failed: ${result.error}`, 'error');
        }
        
        refreshBackends();
    } catch (error) {
        showNotification(`Error testing backend: ${error.message}`, 'error');
    }
}

async function testAllBackends() {
    const backends = document.querySelectorAll('[data-backend]');
    for (const backend of backends) {
        const backendName = backend.dataset.backend;
        await testBackend(backendName);
        await new Promise(resolve => setTimeout(resolve, 1000)); // Rate limit
    }
}

function updateBackendsTable(data) {
    // Update table content with new data
    location.reload(); // Simple approach for now
}

function showBackendDetails(backendName, details) {
    document.getElementById('details-json').textContent = JSON.stringify(details, null, 2);
    document.getElementById('backend-details').style.display = 'block';
}

function hideBackendDetails() {
    document.getElementById('backend-details').style.display = 'none';
}
</script>
{% endblock %}'''

# Service Monitoring Template
SERVICE_MONITORING_TEMPLATE = '''{% extends "base.html" %}

{% block content %}
<div class="service-monitoring">
    <h1>Service Monitoring</h1>
    
    <div class="services-grid">
        {% for service_name, service_data in services_data.items() %}
        <div class="service-card" data-service="{{ service_name }}">
            <div class="service-header">
                <h3>{{ service_name.title() }}</h3>
                <div class="service-status {{ service_data.status or 'unknown' }}">
                    {{ (service_data.status or 'unknown').title() }}
                </div>
            </div>
            
            <div class="service-details">
                {% if service_data.version %}
                <p><strong>Version:</strong> {{ service_data.version }}</p>
                {% endif %}
                {% if service_data.uptime %}
                <p><strong>Uptime:</strong> {{ service_data.uptime }}</p>
                {% endif %}
                {% if service_data.endpoints %}
                <p><strong>Endpoints:</strong> {{ service_data.endpoints | length }}</p>
                {% endif %}
                {% if service_data.error %}
                <p class="error-text"><strong>Error:</strong> {{ service_data.error }}</p>
                {% endif %}
            </div>
            
            <div class="service-actions">
                <button class="btn btn-sm btn-info" onclick="checkService('{{ service_name }}')">Check</button>
                <button class="btn btn-sm btn-primary" onclick="showServiceDetails('{{ service_name }}')">Details</button>
                {% if service_data.status == 'stopped' %}
                <button class="btn btn-sm btn-success" onclick="startService('{{ service_name }}')">Start</button>
                {% elif service_data.status == 'running' %}
                <button class="btn btn-sm btn-danger" onclick="stopService('{{ service_name }}')">Stop</button>
                <button class="btn btn-sm btn-warning" onclick="restartService('{{ service_name }}')">Restart</button>
                {% endif %}
            </div>
            
            {% if service_data.metrics %}
            <div class="service-metrics">
                <h4>Metrics</h4>
                {% for metric, value in service_data.metrics.items() %}
                <div class="metric-item">
                    <span class="metric-name">{{ metric }}:</span>
                    <span class="metric-value">{{ value }}</span>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    
    <div class="service-logs">
        <h2>Recent Service Logs</h2>
        <div class="log-controls">
            <select id="service-filter">
                <option value="all">All Services</option>
                {% for service_name in services_data.keys() %}
                <option value="{{ service_name }}">{{ service_name.title() }}</option>
                {% endfor %}
            </select>
            <button class="btn btn-sm btn-primary" onclick="refreshServiceLogs()">Refresh</button>
        </div>
        <div class="log-display" id="service-logs-display">
            <p>Loading service logs...</p>
        </div>
    </div>
</div>

<script>
async function checkService(serviceName) {
    try {
        const response = await fetch(`/api/services/${serviceName}/status`);
        const result = await response.json();
        
        showNotification(`Service ${serviceName} check completed`, 'info');
        
        // Update service card status
        const serviceCard = document.querySelector(`[data-service="${serviceName}"]`);
        if (serviceCard) {
            const statusElement = serviceCard.querySelector('.service-status');
            statusElement.className = `service-status ${result.status || 'unknown'}`;
            statusElement.textContent = (result.status || 'unknown').title();
        }
    } catch (error) {
        showNotification(`Error checking service: ${error.message}`, 'error');
    }
}

function showServiceDetails(serviceName) {
    // Would open a modal or navigate to detailed service page
    alert(`Service details for ${serviceName} would be shown here`);
}

async function refreshServiceLogs() {
    const filter = document.getElementById('service-filter').value;
    const logsDisplay = document.getElementById('service-logs-display');
    
    try {
        const response = await fetch(`/api/logs?component=${filter}&limit=20`);
        const result = await response.json();
        
        if (result.success && result.result.logs) {
            const logs = result.result.logs;
            logsDisplay.innerHTML = logs.map(log => 
                `<div class="log-entry ${log.level.toLowerCase()}">
                    <span class="log-time">${log.timestamp}</span>
                    <span class="log-level">${log.level}</span>
                    <span class="log-message">${log.message}</span>
                </div>`
            ).join('');
        } else {
            logsDisplay.innerHTML = '<p>No logs available</p>';
        }
    } catch (error) {
        logsDisplay.innerHTML = `<p class="error">Error loading logs: ${error.message}</p>`;
    }
}

// Auto-refresh service status
setInterval(() => {
    const serviceCards = document.querySelectorAll('[data-service]');
    serviceCards.forEach(card => {
        const serviceName = card.dataset.service;
        checkService(serviceName);
    });
}, 30000); // Check every 30 seconds
</script>
{% endblock %}'''

# Log Viewer Template
LOG_VIEWER_TEMPLATE = '''{% extends "base.html" %}

{% block content %}
<div class="log-viewer">
    <h1>Log Viewer</h1>
    
    <div class="log-controls">
        <div class="filter-group">
            <label>Component:</label>
            <select id="component-filter">
                <option value="all">All</option>
                <option value="daemon">Daemon</option>
                <option value="pin">Pin Manager</option>
                <option value="backend">Backend</option>
                <option value="service">Service</option>
                <option value="mcp">MCP Server</option>
            </select>
        </div>
        
        <div class="filter-group">
            <label>Level:</label>
            <select id="level-filter">
                <option value="DEBUG">Debug</option>
                <option value="INFO" selected>Info</option>
                <option value="WARNING">Warning</option>
                <option value="ERROR">Error</option>
                <option value="CRITICAL">Critical</option>
            </select>
        </div>
        
        <div class="filter-group">
            <label>Limit:</label>
            <select id="limit-filter">
                <option value="50">50</option>
                <option value="100" selected>100</option>
                <option value="200">200</option>
                <option value="500">500</option>
            </select>
        </div>
        
        <div class="action-group">
            <button class="btn btn-primary" onclick="refreshLogs()">Refresh</button>
            <button class="btn btn-success" onclick="toggleAutoRefresh()">
                <span id="auto-refresh-text">Enable Auto-Refresh</span>
            </button>
            <button class="btn btn-info" onclick="exportLogs()">Export</button>
            <button class="btn btn-warning" onclick="clearLogs()">Clear</button>
        </div>
    </div>
    
    <div class="log-stats">
        <div class="stat">
            <span class="stat-label">Total Entries:</span>
            <span class="stat-value" id="total-entries">0</span>
        </div>
        <div class="stat">
            <span class="stat-label">Errors:</span>
            <span class="stat-value error" id="error-entries">0</span>
        </div>
        <div class="stat">
            <span class="stat-label">Warnings:</span>
            <span class="stat-value warning" id="warning-entries">0</span>
        </div>
    </div>
    
    <div class="log-display" id="log-display">
        <div class="log-loading">Loading logs...</div>
    </div>
    
    <div class="log-pagination">
        <button class="btn btn-sm btn-secondary" onclick="loadMoreLogs()">Load More</button>
    </div>
</div>

<style>
.log-viewer {
    max-width: 100%;
}

.log-controls {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
    align-items: end;
}

.filter-group, .action-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.action-group {
    flex-direction: row;
    align-items: center;
}

.log-stats {
    display: flex;
    gap: 2rem;
    margin-bottom: 1rem;
    padding: 1rem;
    background: #f8f9fa;
    border-radius: 4px;
}

.stat-value.error { color: #e74c3c; }
.stat-value.warning { color: #f39c12; }

.log-display {
    background: #2c3e50;
    color: #ecf0f1;
    padding: 1rem;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 0.875rem;
    max-height: 600px;
    overflow-y: auto;
}

.log-entry {
    margin-bottom: 0.25rem;
    padding: 0.25rem;
    border-left: 3px solid transparent;
}

.log-entry.debug { border-left-color: #95a5a6; }
.log-entry.info { border-left-color: #3498db; }
.log-entry.warning { border-left-color: #f39c12; }
.log-entry.error { border-left-color: #e74c3c; }
.log-entry.critical { border-left-color: #8e44ad; }

.log-timestamp {
    color: #95a5a6;
    margin-right: 1rem;
}

.log-level {
    font-weight: bold;
    margin-right: 1rem;
    min-width: 60px;
    display: inline-block;
}

.log-component {
    color: #3498db;
    margin-right: 1rem;
    min-width: 80px;
    display: inline-block;
}

.log-message {
    white-space: pre-wrap;
}
</style>

<script>
let autoRefreshInterval = null;
let currentOffset = 0;

async function refreshLogs() {
    const component = document.getElementById('component-filter').value;
    const level = document.getElementById('level-filter').value;
    const limit = document.getElementById('limit-filter').value;
    
    try {
        const response = await fetch(`/api/logs?component=${component}&level=${level}&limit=${limit}`);
        const result = await response.json();
        
        if (result.success && result.result.logs) {
            displayLogs(result.result.logs);
            updateLogStats(result.result.logs);
            currentOffset = result.result.logs.length;
        } else {
            document.getElementById('log-display').innerHTML = '<div class="log-error">No logs available</div>';
        }
    } catch (error) {
        document.getElementById('log-display').innerHTML = `<div class="log-error">Error loading logs: ${error.message}</div>`;
    }
}

function displayLogs(logs) {
    const logDisplay = document.getElementById('log-display');
    
    if (logs.length === 0) {
        logDisplay.innerHTML = '<div class="log-empty">No logs found</div>';
        return;
    }
    
    const logHTML = logs.map(log => `
        <div class="log-entry ${log.level.toLowerCase()}">
            <span class="log-timestamp">${log.timestamp}</span>
            <span class="log-level">${log.level}</span>
            <span class="log-component">${log.component || 'unknown'}</span>
            <span class="log-message">${log.message}</span>
        </div>
    `).join('');
    
    logDisplay.innerHTML = logHTML;
    logDisplay.scrollTop = logDisplay.scrollHeight; // Scroll to bottom
}

function updateLogStats(logs) {
    const totalEntries = logs.length;
    const errorEntries = logs.filter(log => log.level === 'ERROR' || log.level === 'CRITICAL').length;
    const warningEntries = logs.filter(log => log.level === 'WARNING').length;
    
    document.getElementById('total-entries').textContent = totalEntries;
    document.getElementById('error-entries').textContent = errorEntries;
    document.getElementById('warning-entries').textContent = warningEntries;
}

function toggleAutoRefresh() {
    const button = document.getElementById('auto-refresh-text');
    
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        button.textContent = 'Enable Auto-Refresh';
    } else {
        autoRefreshInterval = setInterval(refreshLogs, 5000);
        button.textContent = 'Disable Auto-Refresh';
    }
}

async function exportLogs() {
    const component = document.getElementById('component-filter').value;
    const level = document.getElementById('level-filter').value;
    
    try {
        const response = await fetch(`/api/logs/export?component=${component}&level=${level}&format=json`);
        const blob = await response.blob();
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `logs-${component}-${level}-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        
        window.URL.revokeObjectURL(url);
    } catch (error) {
        showNotification(`Error exporting logs: ${error.message}`, 'error');
    }
}

async function clearLogs() {
    if (!confirm('Are you sure you want to clear all logs?')) return;
    
    try {
        const response = await fetch('/api/logs/clear', { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            showNotification('Logs cleared successfully', 'success');
            refreshLogs();
        } else {
            showNotification(`Error clearing logs: ${result.error}`, 'error');
        }
    } catch (error) {
        showNotification(`Error clearing logs: ${error.message}`, 'error');
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    refreshLogs();
    
    // Bind filter changes
    document.getElementById('component-filter').addEventListener('change', refreshLogs);
    document.getElementById('level-filter').addEventListener('change', refreshLogs);
    document.getElementById('limit-filter').addEventListener('change', refreshLogs);
});
</script>
{% endblock %}'''

def create_additional_templates(templates_dir):
    """Create additional dashboard templates."""
    
    # Backend Management
    (templates_dir / "backend_management.html").write_text(BACKEND_MANAGEMENT_TEMPLATE)
    
    # Service Monitoring  
    (templates_dir / "service_monitoring.html").write_text(SERVICE_MONITORING_TEMPLATE)
    
    # Log Viewer
    (templates_dir / "log_viewer.html").write_text(LOG_VIEWER_TEMPLATE)
    
    # Configuration Template
    config_template = '''{% extends "base.html" %}

{% block content %}
<div class="configuration">
    <h1>Configuration Management</h1>
    
    <div class="config-sections">
        <div class="config-tree">
            <h2>Configuration Tree</h2>
            <div id="config-tree-display">
                <pre>{{ config_data | tojson(indent=2) if config_data else "No configuration data available" }}</pre>
            </div>
        </div>
        
        <div class="config-editor">
            <h2>Edit Configuration</h2>
            <form id="config-form">
                <div class="form-group">
                    <label>Configuration Key:</label>
                    <input type="text" id="config-key" placeholder="e.g., backends.s3.enabled">
                </div>
                <div class="form-group">
                    <label>Value:</label>
                    <textarea id="config-value" placeholder="Configuration value (JSON format)"></textarea>
                </div>
                <button type="submit" class="btn btn-primary">Update Configuration</button>
            </form>
        </div>
    </div>
    
    <div class="config-actions">
        <button class="btn btn-info" onclick="refreshConfig()">Refresh</button>
        <button class="btn btn-warning" onclick="backupConfig()">Backup</button>
        <button class="btn btn-success" onclick="restoreConfig()">Restore</button>
    </div>
</div>

<script>
document.getElementById('config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const key = document.getElementById('config-key').value;
    const value = document.getElementById('config-value').value;
    
    try {
        const response = await fetch('/api/config/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, value: JSON.parse(value) })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Configuration updated successfully', 'success');
            refreshConfig();
        } else {
            showNotification(`Error updating configuration: ${result.error}`, 'error');
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    }
});

async function refreshConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        
        document.getElementById('config-tree-display').innerHTML = 
            `<pre>${JSON.stringify(config, null, 2)}</pre>`;
    } catch (error) {
        showNotification(`Error refreshing config: ${error.message}`, 'error');
    }
}
</script>
{% endblock %}'''
    
    (templates_dir / "configuration.html").write_text(config_template)
    
    # Metrics Dashboard Template
    metrics_template = '''{% extends "base.html" %}

{% block content %}
<div class="metrics-dashboard">
    <h1>Metrics & Analytics</h1>
    
    <div class="metrics-grid">
        <div class="chart-container">
            <h2>System Performance</h2>
            <canvas id="system-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>Pin Operations</h2>
            <canvas id="pin-chart"></canvas>
        </div>
        
        <div class="chart-container">
            <h2>Backend Health</h2>
            <canvas id="backend-chart"></canvas>
        </div>
        
        <div class="metrics-table">
            <h2>Detailed Metrics</h2>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Current</th>
                        <th>Average</th>
                        <th>Peak</th>
                        <th>Trend</th>
                    </tr>
                </thead>
                <tbody id="metrics-tbody">
                    <!-- Metrics data will be populated here -->
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
// Chart.js would be used here for visualization
// This is a placeholder for the actual metrics dashboard implementation
</script>
{% endblock %}'''
    
    (templates_dir / "metrics_dashboard.html").write_text(metrics_template)

if __name__ == "__main__":
    from pathlib import Path
    templates_dir = Path("dashboard_templates")
    templates_dir.mkdir(exist_ok=True)
    create_additional_templates(templates_dir)
    print(f"Additional dashboard templates created in {templates_dir}")
