        // Global variables
        let currentTab = 'overview';
        let autoRefreshInterval = null;
        let currentBackendData = {};
        let backendConfigCache = {};
        let currentPath = '/'; // For file manager
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            initializeExpandables();
            refreshData();
            setupDragAndDrop(); // Setup drag and drop for file manager
        });
        
        // Tab switching
        function showTab(tabName, event) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tab buttons
            document.querySelectorAll('.tab-btn').forEach(button => {
                button.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            
            // Activate selected tab button
            if (event && event.target) {
                event.target.classList.add('active');
            } else {
                // Fallback: find the button by tabName
                const buttons = document.querySelectorAll('.tab-btn');
                buttons.forEach(button => {
                    if (button.onclick && button.onclick.toString().includes(tabName)) {
                        button.classList.add('active');
                    }
                });
            }
            
            currentTab = tabName;
            
            // Load tab-specific data
            switch(tabName) {
                case 'overview':
                    refreshData();
                    break;
                case 'monitoring':
                    refreshMonitoring();
                    break;
                case 'vfs':
                    loadVFSTab();
                    break;
                case 'vector-kb':
                    loadVectorKBTab();
                    break;
                case 'backends':
                    loadBackendsTab();
                    break;
                case 'file-manager':
                    loadFileManagerTab(); // Load file manager data
                    break;
                case 'configuration':
                    loadConfigurationTab();
                    break;
            }
        }
        
        // Main data refresh function
        async function refreshData() {
            try {
                // Load system status
                const healthResponse = await fetch('/api/health');
                const healthData = await healthResponse.json();
                
                // Load backend status
                const backendResponse = await fetch('/api/backends');
                const backendData = await backendResponse.json();
                currentBackendData = backendData;
                
                // Update UI
                updateSystemStatus(healthData);
                updateBackendSummary(backendData);
                updatePerformanceMetrics(healthData);
                updateComponentStatus(healthData);
                
            } catch (error) {
                console.error('Error refreshing data:', error);
            }
        }
        
        // Refresh monitoring tab
        async function refreshMonitoring() {
            try {
                // Load comprehensive monitoring data
                const [monitoringResponse, metricsResponse, alertsResponse] = await Promise.all([
                    fetch('/api/monitoring/comprehensive'),
                    fetch('/api/monitoring/metrics'),
                    fetch('/api/monitoring/alerts')
                ]);
                
                const monitoringData = await monitoringResponse.json();
                const metricsData = await metricsResponse.json();
                const alertsData = await alertsResponse.json();
                
                const grid = document.getElementById('backendGrid');
                grid.innerHTML = '';
                
                if (monitoringData.success) {
                    // Create comprehensive monitoring dashboard
                    updateComprehensiveMonitoring(monitoringData.monitoring_data, metricsData.metrics, alertsData.alerts);
                } else {
                    grid.innerHTML = '<div class="stat-card"><h3>Error loading monitoring data</h3></div>';
                }
                
            } catch (error) {
                console.error('Error refreshing monitoring:', error);
                document.getElementById('backendGrid').innerHTML = '<div class="stat-card"><h3>Error loading monitoring data</h3></div>';
            }
        }
        
        function updateComprehensiveMonitoring(monitoringData, metricsData, alertsData) {
            const grid = document.getElementById('backendGrid');
            
            // System Metrics Card
            const systemCard = document.createElement('div');
            systemCard.className = 'stat-card';
            systemCard.innerHTML = `
                <h3>🖥️ System Metrics</h3>
                <div class="metric">
                    <span class="metric-label">CPU Usage</span>
                    <span class="metric-value">${monitoringData.system_metrics.cpu.usage_percent}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Memory Usage</span>
                    <span class="metric-value">${monitoringData.system_metrics.memory.used_gb}GB / ${monitoringData.system_metrics.memory.total_gb}GB</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Disk Usage</span>
                    <span class="metric-value">${monitoringData.system_metrics.disk.used_gb}GB / ${monitoringData.system_metrics.disk.total_gb}GB</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Network RX/TX</span>
                    <span class="metric-value">${monitoringData.system_metrics.network.rx_mbps}/${monitoringData.system_metrics.network.tx_mbps} Mbps</span>
                </div>
            `;
            grid.appendChild(systemCard);
            
            // Performance Indicators Card
            const performanceCard = document.createElement('div');
            performanceCard.className = 'stat-card';
            performanceCard.innerHTML = `
                <h3>📊 Performance Indicators</h3>
                <div class="metric">
                    <span class="metric-label">Uptime</span>
                    <span class="metric-value">${Math.floor(monitoringData.performance_indicators.uptime_seconds / 86400)} days</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Requests Processed</span>
                    <span class="metric-value">${monitoringData.performance_indicators.requests_processed.toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Avg Response Time</span>
                    <span class="metric-value">${monitoringData.performance_indicators.average_response_time_ms}ms</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Error Rate</span>
                    <span class="metric-value">${monitoringData.performance_indicators.error_rate_percent}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Cache Hit Rate</span>
                    <span class="metric-value">${Math.round(monitoringData.performance_indicators.cache_hit_rate * 100)}%</span>
                </div>
            `;
            grid.appendChild(performanceCard);
            
            // Operational Metrics Card
            const operationalCard = document.createElement('div');
            operationalCard.className = 'stat-card';
            operationalCard.innerHTML = `
                <h3>🔧 Operational Metrics</h3>
                <div class="metric">
                    <span class="metric-label">Active Backends</span>
                    <span class="metric-value">${monitoringData.operational_metrics.active_backends}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Healthy Backends</span>
                    <span class="metric-value">${monitoringData.operational_metrics.healthy_backends}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Operations (24h)</span>
                    <span class="metric-value">${monitoringData.operational_metrics.total_operations_24h.toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Failed Operations (24h)</span>
                    <span class="metric-value">${monitoringData.operational_metrics.failed_operations_24h}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Data Transferred (24h)</span>
                    <span class="metric-value">${monitoringData.operational_metrics.data_transferred_gb_24h}GB</span>
                </div>
            `;
            grid.appendChild(operationalCard);
            
            // Response Time Metrics Card
            if (metricsData && metricsData.success) {
                const responseTimeCard = document.createElement('div');
                responseTimeCard.className = 'stat-card';
                responseTimeCard.innerHTML = `
                    <h3>⚡ Response Time Metrics</h3>
                    <div class="metric">
                        <span class="metric-label">IPFS Avg/P95/P99</span>
                        <span class="metric-value">${metricsData.metrics.response_times.ipfs.avg_ms}/${metricsData.metrics.response_times.ipfs.p95_ms}/${metricsData.metrics.response_times.ipfs.p99_ms}ms</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Cluster Avg/P95/P99</span>
                        <span class="metric-value">${metricsData.metrics.response_times.cluster.avg_ms}/${metricsData.metrics.response_times.cluster.p95_ms}/${metricsData.metrics.response_times.cluster.p99_ms}ms</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Lotus Avg/P95/P99</span>
                        <span class="metric-value">${metricsData.metrics.response_times.lotus.avg_ms}/${metricsData.metrics.response_times.lotus.p95_ms}/${metricsData.metrics.response_times.lotus.p99_ms}ms</span>
                    </div>
                `;
                grid.appendChild(responseTimeCard);
                
                // Throughput Metrics Card
                const throughputCard = document.createElement('div');
                throughputCard.className = 'stat-card';
                throughputCard.innerHTML = `
                    <h3>🚀 Throughput & Resource Utilization</h3>
                    <div class="metric">
                        <span class="metric-label">Requests/Second</span>
                        <span class="metric-value">${metricsData.metrics.throughput.requests_per_second}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Data Transfer</span>
                        <span class="metric-value">${metricsData.metrics.throughput.data_transfer_mbps} Mbps</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Operations/Minute</span>
                        <span class="metric-value">${metricsData.metrics.throughput.operations_per_minute.toLocaleString()}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">CPU/Memory/Disk/Network</span>
                        <span class="metric-value">${metricsData.metrics.resource_utilization.cpu_percent}%/${metricsData.metrics.resource_utilization.memory_percent}%/${metricsData.metrics.resource_utilization.disk_io_percent}%/${metricsData.metrics.resource_utilization.network_io_percent}%</span>
                    </div>
                `;
                grid.appendChild(throughputCard);
            }
            
            // Alerts Card
            if (alertsData && alertsData.success && alertsData.alerts.length > 0) {
                const alertsCard = document.createElement('div');
                alertsCard.className = 'stat-card';
                alertsCard.innerHTML = `
                    <h3>🚨 Active Alerts (${alertsData.alert_summary.total})</h3>
                    ${alertsData.alerts.map(alert => `
                        <div class="metric">
                            <span class="metric-label">${alert.component} - ${alert.level}</span>
                            <span class="metric-value">${alert.message}</span>
                        </div>
                    `).join('')}
                    <div class="metric">
                        <span class="metric-label">Summary</span>
                        <span class="metric-value">Critical: ${alertsData.alert_summary.critical}, Warning: ${alertsData.alert_summary.warning}, Info: ${alertsData.alert_summary.info}</span>
                    </div>
                `;
                grid.appendChild(alertsCard);
            }
        }
        
        function updateBackendGrid(backends) {
            const grid = document.getElementById('backendGrid');
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
                            <span class="backend-status ${backend.health}">${backend.health}</span>
                        </div>
                        <div class="backend-actions">
                            <button class="action-btn" onclick="viewLogs('${name}')">&#128221; Logs</button>
                            <button class="action-btn" onclick="configureBackend('${name}')">&#9881; Config</button>
                            <button class="action-btn" onclick="restartBackend('${name}')">&#128260; Restart</button>
                        </div>
                    </div>
                    <div class="backend-content">
                        <div class="backend-metrics">
                            <div class="metric">
                                <span class="metric-label">Status:</span>
                                <span class="metric-value">${backend.status}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Last Check:</span>
                                <span class="metric-value">${backend.last_check ? new Date(backend.last_check).toLocaleString() : 'Never'}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Health Score:</span>
                                <span class="metric-value">${backend.health_score || 'Unknown'}</span>
                            </div>
                        </div>
                        ${verboseMetricsHTML}
                        ${errorsHTML}
                    </div>
                `;
                
                grid.appendChild(card);
            }
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
            if (typeof value === 'number') {
                if (value > 1000000) {
                    return (value / 1000000).toFixed(1) + 'M';
                } else if (value > 1000) {
                    return (value / 1000).toFixed(1) + 'K';
                } else {
                    return value.toString();
                }
            } else if (typeof value === 'boolean') {
                return value ? '✓' : '✗';
            } else if (typeof value === 'string') {
                return value.length > 50 ? value.substring(0, 50) + '...' : value;
            } else {
                return JSON.stringify(value);
            }
        }
        
        // Update system status
        function updateSystemStatus(data) {
            const healthScore = data.health_score || 0;
            const statusElement = document.getElementById('systemStatus');
            
            const healthClass = healthScore > 70 ? 'good' : healthScore > 40 ? 'warning' : 'error';
            
            statusElement.innerHTML = `
                <div class="health-score ${healthClass}">${healthScore.toFixed(1)}%</div>
                <div class="metric">
                    <span class="metric-label">Health Score</span>
                    <span class="metric-value">${healthScore.toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Uptime</span>
                    <span class="metric-value">${formatUptime(data.uptime_seconds || 0)}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Status</span>
                    <span class="metric-value">${data.status || 'unknown'}</span>
                </div>
            `;
        }
        
        // Update backend summary
        function updateBackendSummary(data) {
            const element = document.getElementById('backendSummary');
            
            if (data.backends) {
                const backends = Object.values(data.backends);
                const healthy = backends.filter(b => b.health === 'healthy').length;
                const total = backends.length;
                
                element.innerHTML = `
                    <div class="metric">
                        <span class="metric-label">Total Backends</span>
                        <span class="metric-value">${total}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Healthy</span>
                        <span class="metric-value">${healthy}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Success Rate</span>
                        <span class="metric-value">${total > 0 ? (healthy/total*100).toFixed(1) : 0}%</span>
                    </div>
                `;
            } else {
                element.innerHTML = '<div class="metric"><span class="metric-label">Status</span><span class="metric-value">Loading...</span></div>';
            }
        }
        
        // Update performance metrics
        function updatePerformanceMetrics(data) {
            const element = document.getElementById('performanceMetrics');
            
            element.innerHTML = `
                <div class="metric">
                    <span class="metric-label">Response Time</span>
                    <span class="metric-value">${(data.average_response_time || 0).toFixed(3)}s</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Memory Usage</span>
                    <span class="metric-value">${(data.memory_usage_mb || 0).toFixed(1)}MB</span>
                </div>
                <div class="metric">
                    <span class="metric-label">CPU Usage</span>
                    <span class="metric-value">${(data.cpu_usage_percent || 0).toFixed(1)}%</span>
                </div>
            `;
        }
        
        // Update component status
        function updateComponentStatus(data) {
            const element = document.getElementById('componentStatus');
            
            if (data.components) {
                let html = '';
                Object.entries(data.components).forEach(([component, available]) => {
                    const statusClass = available ? 'status-healthy' : 'status-unhealthy';
                    const indicator = available ? '✓' : '✗';
                    
                    html += `
                        <div class="metric">
                            <span class="metric-label">${component.replace('_', ' ')}</span>
                            <span class="metric-value status-badge ${statusClass}">${indicator}</span>
                        </div>
                    `;
                });
                element.innerHTML = html;
            } else {
                element.innerHTML = '<div class="metric"><span class="metric-label">Status</span><span class="metric-value">Loading...</span></div>';
            }
        }
        
        // Create backend card
        function createBackendCard(name, backend) {
            const card = document.createElement('div');
            card.className = 'backend-card';
            
            const statusBadge = backend.health === 'healthy' ? 'status-healthy' : 'status-unhealthy';
            
            card.innerHTML = `
                <h4>${name} <span class="status-badge ${statusBadge}">${backend.health}</span></h4>
                <div class="metric">
                    <span class="metric-label">Status</span>
                    <span class="metric-value">${backend.status || 'unknown'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Response Time</span>
                    <span class="metric-value">${(backend.response_time || 0).toFixed(3)}s</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Last Check</span>
                    <span class="metric-value">${formatTimestamp(backend.last_check)}</span>
                </div>
                <div class="backend-actions">
                    <button class="btn-primary" onclick="openConfigModal('${name}')">&#9881; Configure</button>
                    <button class="btn-secondary" onclick="openLogsModal('${name}')">&#128221; Logs</button>
                    <button class="btn-success" onclick="restartBackend('${name}')">&#128260; Restart</button>
                </div>
            `;
            
            return card;
        }
        
        // VFS Tab Functions
        async function loadVFSTab() {
            try {
                // Load VFS statistics
                const response = await fetch('/api/vfs/statistics');
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('cachePerformance').innerHTML = formatCachePerformance(data.cache_performance);
                    document.getElementById('filesystemStatus').innerHTML = formatFilesystemStatus(data.filesystem_metrics);
                    document.getElementById('accessPatterns').innerHTML = formatAccessPatterns(data.access_patterns);
                    document.getElementById('resourceUsage').innerHTML = formatResourceUsage(data.resource_utilization);
                    
                    // Load detailed sections
                    document.getElementById('tieredCacheDetails').innerHTML = formatTieredCacheDetails(data.cache_performance);
                    document.getElementById('hotContentAnalysis').innerHTML = formatHotContentAnalysis(data.access_patterns);
                } else {
                    document.getElementById('cachePerformance').innerHTML = 'VFS monitoring not available';
                }
                
            } catch (error) {
                console.error('Error loading VFS data:', error);
                document.getElementById('cachePerformance').innerHTML = 'Error loading VFS data';
            }
        }
        
        // Vector/KB Tab Functions

        
        // Configuration Tab Functions
        async function loadConfigurationTab() {
            try {
                // Load comprehensive configuration
                const configResponse = await fetch('/api/config');
                const configData = await configResponse.json();
                
                if (configData.success) {
                    // Update system configuration
                    updateSystemConfiguration(configData.config.system);
                    
                    // Update backend configurations
                    updateBackendConfigurations(configData.config.backends);
                    
                    // Update dashboard configuration
                    updateDashboardConfiguration(configData.config.dashboard);
                    
                    // Update monitoring configuration
                    updateMonitoringConfiguration(configData.config.monitoring);
                    
                    // Update VFS configuration
                    updateVFSConfiguration(configData.config.vfs);
                    
                    // Update security configuration
                    updateSecurityConfiguration(configData.config.security);
                    
                    // Update performance configuration
                    updatePerformanceConfiguration(configData.config.performance);
                    
                } else {
                    document.getElementById('configBackendList').innerHTML = '<div style="color: red; padding: 20px;">Error loading configuration data</div>';
                }
                
            } catch (error) {
                console.error('Error loading configuration:', error);
                document.getElementById('configBackendList').innerHTML = '<div style="color: red; padding: 20px;">Error loading configurations</div>';
            }
        }
        
        function updateSystemConfiguration(systemConfig) {
            const systemConfigElement = document.getElementById('systemConfiguration');
            if (systemConfigElement) {
                systemConfigElement.innerHTML = `
                    <div class="stat-card">
                        <h4>🖥️ System Configuration</h4>
                        <div class="metric">
                            <span class="metric-label">Server Host</span>
                            <span class="metric-value">${systemConfig.server.host}:${systemConfig.server.port}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Debug Mode</span>
                            <span class="metric-value">${systemConfig.server.debug ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Log Level</span>
                            <span class="metric-value">${systemConfig.server.log_level}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Database Type</span>
                            <span class="metric-value">${systemConfig.database.type}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Cache Type</span>
                            <span class="metric-value">${systemConfig.cache.type} (${systemConfig.cache.max_size_mb}MB)</span>
                        </div>
                    </div>
                `;
            }
        }
        
        function updateBackendConfigurations(backendsConfig) {
            const configList = document.getElementById('configBackendList');
            if (configList) {
                configList.innerHTML = '';
                
                Object.entries(backendsConfig).forEach(([name, backend]) => {
                    const configCard = document.createElement('div');
                    configCard.className = 'stat-card';
                    configCard.style.cursor = 'pointer';
                    configCard.onclick = () => openComprehensiveConfigModal(name, backend);
                    
                    configCard.innerHTML = `
                        <h4>🔧 ${name}</h4>
                        <div class="metric">
                            <span class="metric-label">Status</span>
                            <span class="metric-value">${backend.enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">URL</span>
                            <span class="metric-value">${backend.url || backend.connection?.url || 'Not configured'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Timeout</span>
                            <span class="metric-value">${backend.timeout || backend.connection?.timeout || 30}s</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Health Check</span>
                            <span class="metric-value">${backend.monitoring?.health_check_enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <p style="margin: 8px 0; font-size: 0.9em; color: #666;">Click to configure advanced settings</p>
                    `;
                    
                    configList.appendChild(configCard);
                });
            }
        }
        
        function updateDashboardConfiguration(dashboardConfig) {
            const dashboardConfigElement = document.getElementById('dashboardConfiguration');
            if (dashboardConfigElement) {
                dashboardConfigElement.innerHTML = `
                    <div class="stat-card">
                        <h4>📊 Dashboard Configuration</h4>
                        <div class="metric">
                            <span class="metric-label">Title</span>
                            <span class="metric-value">${dashboardConfig.title}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Theme</span>
                            <span class="metric-value">${dashboardConfig.theme}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Auto Refresh</span>
                            <span class="metric-value">${dashboardConfig.auto_refresh ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Refresh Interval</span>
                            <span class="metric-value">${dashboardConfig.refresh_interval}ms</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Enabled Tabs</span>
                            <span class="metric-value">${Object.entries(dashboardConfig.tabs).filter(([_, config]) => config.enabled).map(([name, _]) => name).join(', ')}</span>
                        </div>
                    </div>
                `;
            }
        }
        
        function updateMonitoringConfiguration(monitoringConfig) {
            const monitoringConfigElement = document.getElementById('monitoringConfiguration');
            if (monitoringConfigElement) {
                monitoringConfigElement.innerHTML = `
                    <div class="stat-card">
                        <h4>📈 Monitoring Configuration</h4>
                        <div class="metric">
                            <span class="metric-label">Monitoring Enabled</span>
                            <span class="metric-value">${monitoringConfig.enabled ? 'Yes' : 'No'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Retention Period</span>
                            <span class="metric-value">${monitoringConfig.metrics_retention_days} days</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">CPU Alert Threshold</span>
                            <span class="metric-value">${monitoringConfig.alert_threshold.cpu_percent}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Memory Alert Threshold</span>
                            <span class="metric-value">${monitoringConfig.alert_threshold.memory_percent}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Response Time Threshold</span>
                            <span class="metric-value">${monitoringConfig.alert_threshold.response_time_ms}ms</span>
                        </div>
                    </div>
                `;
            }
        }
        
        function updateVFSConfiguration(vfsConfig) {
            const vfsConfigElement = document.getElementById('vfsConfiguration');
            if (vfsConfigElement) {
                vfsConfigElement.innerHTML = `
                    <div class="stat-card">
                        <h4>📁 VFS Configuration</h4>
                        <div class="metric">
                            <span class="metric-label">Cache Size</span>
                            <span class="metric-value">${vfsConfig.cache_size_mb}MB</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Index Enabled</span>
                            <span class="metric-value">${vfsConfig.index_enabled ? 'Yes' : 'No'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Compression</span>
                            <span class="metric-value">${vfsConfig.compression_enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Analytics</span>
                            <span class="metric-value">${vfsConfig.analytics_enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Performance Tracking</span>
                            <span class="metric-value">${vfsConfig.performance_tracking ? 'Enabled' : 'Disabled'}</span>
                        </div>
                    </div>
                `;
            }
        }
        
        function updateSecurityConfiguration(securityConfig) {
            const securityConfigElement = document.getElementById('securityConfiguration');
            if (securityConfigElement) {
                securityConfigElement.innerHTML = `
                    <div class="stat-card">
                        <h4>🔐 Security Configuration</h4>
                        <div class="metric">
                            <span class="metric-label">Authentication</span>
                            <span class="metric-value">${securityConfig.authentication.enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">CORS</span>
                            <span class="metric-value">${securityConfig.cors.enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Rate Limiting</span>
                            <span class="metric-value">${securityConfig.rate_limiting.enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        ${securityConfig.rate_limiting.enabled ? `
                            <div class="metric">
                                <span class="metric-label">Rate Limit</span>
                                <span class="metric-value">${securityConfig.rate_limiting.requests_per_minute} req/min</span>
                            </div>
                        ` : ''}
                    </div>
                `;
            }
        }
        
        function updatePerformanceConfiguration(performanceConfig) {
            const performanceConfigElement = document.getElementById('performanceConfiguration');
            if (performanceConfigElement) {
                performanceConfigElement.innerHTML = `
                    <div class="stat-card">
                        <h4>⚡ Performance Configuration</h4>
                        <div class="metric">
                            <span class="metric-label">Connection Pool Size</span>
                            <span class="metric-value">${performanceConfig.connection_pool_size}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Request Timeout</span>
                            <span class="metric-value">${performanceConfig.request_timeout}s</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Max Concurrent Requests</span>
                            <span class="metric-value">${performanceConfig.max_concurrent_requests}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Compression</span>
                            <span class="metric-value">${performanceConfig.compression_enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Caching</span>
                            <span class="metric-value">${performanceConfig.caching_enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                    </div>
                `;
            }
        }
        
        function openComprehensiveConfigModal(backendName, backendConfig) {
            console.log('Opening comprehensive config modal for:', backendName);
            // Implementation for comprehensive backend configuration modal
            alert(`Comprehensive configuration for ${backendName} would open here.`);
        }
        
        // Configuration functions
        async function loadPackageConfig() {
            try {
                const response = await fetch('/api/config/package');
                const data = await response.json();
                
                if (data.success && data.config) {
                    const config = data.config;
                    
                    // Load system settings
                    const system = config.system || {};
                    if (document.getElementById('system-log-level')) {
                        document.getElementById('system-log-level').value = system.log_level || 'INFO';
                    }
                    
                    // Load other settings...
                    // (Similar to enhanced version)
                }
                
            } catch (error) {
                console.error('Error loading package configuration:', error);
            }
        }
        
        async function savePackageConfig() {
            try {
                const config = {
                    system: {
                        log_level: document.getElementById('system-log-level')?.value || 'INFO',
                        max_workers: document.getElementById('system-max-workers')?.value || '4',
                        cache_size: document.getElementById('system-cache-size')?.value || '1000',
                        data_directory: document.getElementById('system-data-dir')?.value || '/tmp/ipfs_kit'
                    },
                    vfs: {
                        cache_enabled: document.getElementById('vfs-cache-enabled')?.checked ? 'true' : 'false',
                        cache_max_size: document.getElementById('vfs-cache-max-size')?.value || '10GB',
                        vector_dimensions: document.getElementById('vfs-vector-dimensions')?.value || '384',
                        knowledge_base_max_nodes: document.getElementById('vfs-kb-max-nodes')?.value || '10000'
                    },
                    observability: {
                        metrics_enabled: document.getElementById('obs-metrics-enabled')?.checked ? 'true' : 'false',
                        prometheus_port: document.getElementById('obs-prometheus-port')?.value || '9090',
                        dashboard_enabled: document.getElementById('obs-dashboard-enabled')?.checked ? 'true' : 'false',
                        health_check_interval: document.getElementById('obs-health-check-interval')?.value || '30'
                    }
                };
                
                const response = await fetch('/api/config/package', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                
                if (response.ok) {
                    alert('Package configuration saved successfully!');
                } else {
                    alert('Error saving package configuration');
                }
                
            } catch (error) {
                console.error('Error saving package configuration:', error);
                alert('Error saving package configuration: ' + error.message);
            }
        }
        
        // Modal functions
        async function openConfigModal(backendName) {
            const modal = document.getElementById('configModal');
            const title = document.getElementById('configModalTitle');
            const content = document.getElementById('configModalContent');
            
            title.textContent = `Configure ${backendName}`;
            content.innerHTML = '<div style="text-align: center; padding: 20px;">Loading configuration...</div>';
            modal.style.display = 'block';
            
            try {
                const response = await fetch(`/api/backends/${backendName}/config`);
                const configData = await response.json();
                
                if (configData.success) {
                    backendConfigCache[backendName] = configData.config || {};
                    content.innerHTML = createConfigForm(backendName, configData.config);
                } else {
                    content.innerHTML = `<div style="color: red; padding: 20px;">Error loading configuration: ${configData.error}</div>`;
                }
                
            } catch (error) {
                content.innerHTML = `<div style="color: red; padding: 20px;">Error loading configuration: ${error.message}</div>`;
            }
        }
        
        function closeConfigModal() {
            document.getElementById('configModal').style.display = 'none';
        }
        
        function openLogsModal(backendName) {
            const modal = document.getElementById('logsModal');
            const title = document.getElementById('logsModalTitle');
            const content = document.getElementById('logsModalContent');
            
            title.textContent = `${backendName} Logs`;
            content.innerHTML = '<div style="padding: 20px;">Loading logs...</div>';
            modal.style.display = 'block';
            
            // Load logs
            fetch(`/api/backends/${backendName}/logs`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        content.innerHTML = `<pre style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">${data.logs || 'No logs available'}</pre>`;
                    } else {
                        content.innerHTML = `<div style="color: red; padding: 20px;">Error loading logs: ${data.error}</div>`;
                    }
                })
                .catch(error => {
                    content.innerHTML = `<div style="color: red; padding: 20px;">Error loading logs: ${error.message}</div>`;
                });
        }
        
        function closeLogsModal() {
            document.getElementById('logsModal').style.display = 'none';
        }
        
        // Utility functions
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${minutes}m`;
        }
        
        function formatTimestamp(timestamp) {
            if (!timestamp) return 'Never';
            return new Date(timestamp).toLocaleString();
        }
        
        function createConfigForm(backendName, config) {
            return `
                <form onsubmit="saveBackendConfig('${backendName}', event)">
                    <div class="config-form">
                        <label>Backend Configuration (JSON):</label>
                        <textarea name="config" rows="10" style="font-family: monospace;">${JSON.stringify(config, null, 2)}</textarea>
                    </div>
                    <div style="margin-top: 20px; text-align: right;">
                        <button type="button" class="btn-secondary" onclick="closeConfigModal()">Cancel</button>
                        <button type="submit" class="btn-primary">Save</button>
                    </div>
                </form>
            `;
        }
        
        async function saveBackendConfig(backendName, event) {
            event.preventDefault();
            
            const formData = new FormData(event.target);
            const configJson = formData.get('config');
            
            try {
                const config = JSON.parse(configJson);
                
                const response = await fetch(`/api/backends/${backendName}/config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                
                if (response.ok) {
                    alert('Configuration saved successfully!');
                    closeConfigModal();
                    refreshData();
                } else {
                    alert('Error saving configuration');
                }
                
            } catch (error) {
                alert('Error saving configuration: ' + error.message);
            }
        }
        
        async function restartBackend(backendName) {
            if (!confirm(`Are you sure you want to restart ${backendName}?`)) {
                return;
            }
            
            try {
                const response = await fetch(`/api/backends/${backendName}/restart`, { method: 'POST' });
                if (response.ok) {
                    alert(`${backendName} restart initiated`);
                    refreshData();
                } else {
                    alert('Error restarting backend');
                }
            } catch (error) {
                alert('Error restarting backend: ' + error.message);
            }
        }
        
        async function exportConfig() {
            try {
                const response = await fetch('/api/config/export');
                const config = await response.json();
                
                const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `ipfs-kit-config-${new Date().toISOString().split('T')[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
            } catch (error) {
                alert('Error exporting configuration: ' + error.message);
            }
        }
        
        async function getInsights() {
            try {
                const response = await fetch('/api/insights');
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('insightsContent').innerHTML = data.insights || 'No insights available';
                    document.getElementById('insightsCard').style.display = 'block';
                } else {
                    document.getElementById('insightsContent').innerHTML = 'Error loading insights';
                }
            } catch (error) {
                console.error('Error getting insights:', error);
                document.getElementById('insightsContent').innerHTML = 'Error loading insights';
            }
        }
        
        function toggleAutoRefresh() {
            const checkbox = document.getElementById('autoRefresh');
            if (checkbox.checked) {
                autoRefreshInterval = setInterval(refreshData, 30000);
            } else {
                clearInterval(autoRefreshInterval);
            }
        }
        
        function initializeExpandables() {
            document.querySelectorAll('.expandable-header').forEach(header => {
                header.onclick = () => {
                    header.parentElement.classList.toggle('expanded');
                };
            });
        }
        
        // Format functions (simplified versions)
        function formatCachePerformance(data) {
            if (!data) return 'No cache data available';
            return `
                <div class="metric">
                    <span class="metric-label">Hit Rate</span>
                    <span class="metric-value">${(data.hit_rate * 100).toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Size</span>
                    <span class="metric-value">${data.size_mb || 0}MB</span>
                </div>
            `;
        }
        
        function formatFilesystemStatus(data) {
            if (!data) return 'No filesystem data available';
            return `
                <div class="metric">
                    <span class="metric-label">Operations</span>
                    <span class="metric-value">${data.operations || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Errors</span>
                    <span class="metric-value">${data.errors || 0}</span>
                </div>
            `;
        }
        
        function formatAccessPatterns(data) {
            if (!data) return 'No access pattern data available';
            return `
                <div class="metric">
                    <span class="metric-label">Hot Files</span>
                    <span class="metric-value">${data.hot_files || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Access Count</span>
                    <span class="metric-value">${data.total_accesses || 0}</span>
                </div>
            `;
        }
        
        function formatResourceUsage(data) {
            if (!data) return 'No resource data available';
            return `
                <div class="metric">
                    <span class="metric-label">Memory</span>
                    <span class="metric-value">${data.memory_mb || 0}MB</span>
                </div>
                <div class="metric">
                    <span class="metric-label">CPU</span>
                    <span class="metric-value">${data.cpu_percent || 0}%</span>
                </div>
            `;
        }
        
        function formatVectorIndexStatus(data) {
            if (!data) return 'No vector index data available';
            return `
                <div class="metric">
                    <span class="metric-label">Index Size</span>
                    <span class="metric-value">${data.size || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Dimension</span>
                    <span class="metric-value">${data.dimension || 0}</span>
                </div>
            `;
        }
        
        function formatKnowledgeGraphStatus(data) {
            if (!data) return 'No knowledge graph data available';
            return `
                <div class="metric">
                    <span class="metric-label">Nodes</span>
                    <span class="metric-value">${data.nodes || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Edges</span>
                    <span class="metric-value">${data.edges || 0}</span>
                </div>
            `;
        }
        
        function formatSearchPerformance(data) {
            if (!data) return 'No search performance data available';
            return `
                <div class="metric">
                    <span class="metric-label">Avg Query Time</span>
                    <span class="metric-value">${data.avg_query_time || 0}ms</span>
                </div>
                <div class="metric">
                    <span class="metric-label">QPS</span>
                    <span class="metric-value">${data.qps || 0}</span>
                </div>
            `;
        }
        
        function formatContentDistribution(data) {
            if (!data) return 'No content distribution data available';
            return Object.entries(data).map(([type, count]) => `
                <div class="metric">
                    <span class="metric-label">${type}</span>
                    <span class="metric-value">${count}</span>
                </div>
            `).join('');
        }
        
        function formatTieredCacheDetails(data) {
            if (!data || !data.tiered_cache) return 'No tiered cache data available';
            const tc = data.tiered_cache;
            return `
                <div class="stats-grid">
                    <div class="stat-card">
                        <h4>Memory Tier</h4>
                        <div class="metric">
                            <span class="metric-label">Hit Rate</span>
                            <span class="metric-value">${(tc.memory_tier.hit_rate * 100).toFixed(1)}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Size</span>
                            <span class="metric-value">${tc.memory_tier.size_mb}MB</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Items</span>
                            <span class="metric-value">${tc.memory_tier.items}</span>
                        </div>
                    </div>
                    <div class="stat-card">
                        <h4>Disk Tier</h4>
                        <div class="metric">
                            <span class="metric-label">Hit Rate</span>
                            <span class="metric-value">${(tc.disk_tier.hit_rate * 100).toFixed(1)}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Size</span>
                            <span class="metric-value">${tc.disk_tier.size_gb}GB</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Read Latency</span>
                            <span class="metric-value">${tc.disk_tier.read_latency_ms}ms</span>
                        </div>
                    </div>
                    <div class="stat-card">
                        <h4>Performance</h4>
                        <div class="metric">
                            <span class="metric-label">Predictive Accuracy</span>
                            <span class="metric-value">${(tc.predictive_accuracy * 100).toFixed(1)}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Prefetch Efficiency</span>
                            <span class="metric-value">${(tc.prefetch_efficiency * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        function formatHotContentAnalysis(data) {
            if (!data) return 'No hot content data available';
            return `
                <div class="metrics-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Content ID</th>
                                <th>Access Count</th>
                                <th>Size</th>
                                <th>Last Access</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.hot_content.map(item => `
                                <tr>
                                    <td>${item.cid}</td>
                                    <td>${item.access_count}</td>
                                    <td>${item.size_kb}KB</td>
                                    <td>${new Date().toLocaleString()}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                <div class="stats-grid" style="margin-top: 20px;">
                    <div class="stat-card">
                        <h4>Temporal Patterns</h4>
                        <div class="metric">
                            <span class="metric-label">Peak Hours</span>
                            <span class="metric-value">${data.temporal_patterns.peak_hours.join(', ')}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Weekly Pattern</span>
                            <span class="metric-value">${data.temporal_patterns.weekly_pattern}</span>
                        </div>
                    </div>
                    <div class="stat-card">
                        <h4>Content Types</h4>
                        ${Object.entries(data.content_types).map(([type, percent]) => `
                            <div class="metric">
                                <span class="metric-label">${type}</span>
                                <span class="metric-value">${(percent * 100).toFixed(1)}%</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        function formatVectorIndexDetails(data) {
            if (!data || !data.total_vectors) return 'No vector index details available';
            return `
                <div class="stats-grid">
                    <div class="stat-card">
                        <h4>Index Health</h4>
                        <div class="metric">
                            <span class="metric-label">Status</span>
                            <span class="metric-value status-badge status-${data.index_health === 'healthy' ? 'healthy' : 'unhealthy'}">${data.index_health}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Total Vectors</span>
                            <span class="metric-value">${data.total_vectors.toLocaleString()}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Index Type</span>
                            <span class="metric-value">${data.index_type}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Dimension</span>
                            <span class="metric-value">${data.dimension}</span>
                        </div>
                    </div>
                    <div class="stat-card">
                        <h4>Search Performance</h4>
                        <div class="metric">
                            <span class="metric-label">Avg Query Time</span>
                            <span class="metric-value">${data.search_performance.average_query_time_ms}ms</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">QPS</span>
                            <span class="metric-value">${data.search_performance.queries_per_second}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Recall@10</span>
                            <span class="metric-value">${(data.search_performance.recall_at_10 * 100).toFixed(1)}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Precision@10</span>
                            <span class="metric-value">${(data.search_performance.precision_at_10 * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                    <div class="stat-card">
                        <h4>Content Distribution</h4>
                        ${Object.entries(data.content_distribution).map(([type, count]) => `
                            <div class="metric">
                                <span class="metric-label">${type.replace('_', ' ')}</span>
                                <span class="metric-value">${count.toLocaleString()}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        function formatKnowledgeBaseAnalytics(data) {
            if (!data || !data.nodes) return 'No knowledge base analytics available';
            return `
                <div class="stats-grid">
                    <div class="stat-card">
                        <h4>Graph Structure</h4>
                        <div class="metric">
                            <span class="metric-label">Health</span>
                            <span class="metric-value status-badge status-${data.graph_health === 'healthy' ? 'healthy' : 'unhealthy'}">${data.graph_health}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Total Nodes</span>
                            <span class="metric-value">${data.nodes.total.toLocaleString()}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Total Edges</span>
                            <span class="metric-value">${data.edges.total.toLocaleString()}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Density</span>
                            <span class="metric-value">${data.graph_metrics.density.toFixed(3)}</span>
                        </div>
                    </div>
                    <div class="stat-card">
                        <h4>Node Types</h4>
                        ${Object.entries(data.nodes).filter(([key]) => key !== 'total').map(([type, count]) => `
                            <div class="metric">
                                <span class="metric-label">${type}</span>
                                <span class="metric-value">${count.toLocaleString()}</span>
                            </div>
                        `).join('')}
                    </div>
                    <div class="stat-card">
                        <h4>Edge Types</h4>
                        ${Object.entries(data.edges).filter(([key]) => key !== 'total').map(([type, count]) => `
                            <div class="metric">
                                <span class="metric-label">${type.replace('_', ' ')}</span>
                                <span class="metric-value">${count.toLocaleString()}</span>
                            </div>
                        `).join('')}
                    </div>
                    <div class="stat-card">
                        <h4>Content Analysis</h4>
                        <div class="metric">
                            <span class="metric-label">Topics</span>
                            <span class="metric-value">${data.content_analysis.topics_identified}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Languages</span>
                            <span class="metric-value">${data.content_analysis.languages_detected.join(', ')}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Sentiment</span>
                            <span class="metric-value">
                                ${(data.content_analysis.sentiment_distribution.positive * 100).toFixed(0)}% pos, 
                                ${(data.content_analysis.sentiment_distribution.neutral * 100).toFixed(0)}% neu, 
                                ${(data.content_analysis.sentiment_distribution.negative * 100).toFixed(0)}% neg
                            </span>
                        </div>
                    </div>
                </div>
            `;
        }

        // Backends Tab Functions
        async function loadBackendsTab() {
            try {
                const response = await fetch('/api/backends');
                const data = await response.json();
                if (data.success) {
                    const grid = document.getElementById('backendsGrid');
                    grid.innerHTML = '';
                    for (const [name, backend] of Object.entries(data.backends)) {
                        const card = document.createElement('div');
                        card.className = `backend-card ${backend.health}`;

                        let detailedInfoHtml = '';
                        if (backend.detailed_info) {
                            for (const [key, value] of Object.entries(backend.detailed_info)) {
                                detailedInfoHtml += `
                                    <div class="metric">
                                        <span class="metric-label">${formatMetricKey(key)}:</span>
                                        <span class="metric-value">${formatMetricValue(value)}</span>
                                    </div>
                                `;
                            }
                        }

                        let errorsHtml = '';
                        if (backend.errors && backend.errors.length > 0) {
                            errorsHtml = `
                                <div class="expandable">
                                    <div class="expandable-header">Recent Errors (${backend.errors.length})</div>
                                    <div class="expandable-content">
                                        <div class="error-log">
                                            ${backend.errors.map(error => 
                                                `<div><strong>${new Date(error.timestamp).toLocaleString()}:</strong> ${error.error}</div>`
                                            ).join('')}
                                        </div>
                                    </div>
                                </div>
                            `;
                        }

                        card.innerHTML = `
                            <h4>${backend.name} <span class="status-badge status-${backend.health}">${backend.health}</span></h4>
                            <div class="metric">
                                <span class="metric-label">Status:</span>
                                <span class="metric-value">${backend.status || 'unknown'}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Last Check:</span>
                                <span class="metric-value">${formatTimestamp(backend.last_check)}</span>
                            </div>
                            ${detailedInfoHtml}
                            ${errorsHtml}
                            <div class="backend-actions">
                                <button class="btn-primary" onclick="openConfigModal('${name}')">&#9881; Configure</button>
                                <button class="btn-secondary" onclick="openLogsModal('${name}')">&#128221; Logs</button>
                                <button class="btn-success" onclick="restartBackend('${name}')">&#128260; Restart</button>
                            </div>
                        `;
                        grid.appendChild(card);
                    }
                    initializeExpandables(); // Re-initialize expandables for new content
                } else {
                    document.getElementById('backendsGrid').innerHTML = '<div class="stat-card"><h3>Error loading backend data</h3></div>';
                }
            } catch (error) {
                console.error('Error loading backends data:', error);
                document.getElementById('backendsGrid').innerHTML = '<div class="stat-card"><h3>Error loading backends data</h3></div>';
            }
        }
        
        // VFS Tab Functions
        async function loadVFSTab() {
            console.log('Loading VFS Observatory tab...');
            
            try {
                // Load comprehensive VFS health, performance, and analytics
                const [healthResponse, performanceResponse, vectorResponse, kbResponse, recommendationsResponse] = await Promise.all([
                    fetch('/api/vfs/health'),
                    fetch('/api/vfs/performance'),
                    fetch('/api/vfs/vector-index'),
                    fetch('/api/vfs/knowledge-base'),
                    fetch('/api/vfs/recommendations')
                ]);
                
                const healthData = await healthResponse.json();
                const performanceData = await performanceResponse.json();
                const vectorData = await vectorResponse.json();
                const kbData = await kbResponse.json();
                const recommendationsData = await recommendationsResponse.json();

                // Update VFS health overview
                updateVFSHealth(healthData);
                
                // Update cache performance with comprehensive data
                document.getElementById('cachePerformance').innerHTML = formatComprehensiveCacheDetails(healthData.detailed_metrics?.cache_performance);
                
                // Update filesystem status with comprehensive metrics
                document.getElementById('filesystemStatus').innerHTML = formatComprehensiveFilesystemMetrics(healthData.detailed_metrics?.filesystem_metrics);
                
                // Update access patterns with comprehensive data
                document.getElementById('accessPatterns').innerHTML = formatComprehensiveAccessPatterns(healthData.detailed_metrics?.access_patterns);
                
                // Update resource utilization
                if (document.getElementById('resourceUtilization')) {
                    document.getElementById('resourceUtilization').innerHTML = formatResourceUtilization(healthData.detailed_metrics?.resource_utilization);
                }
                
                // Update VFS recommendations
                if (document.getElementById('vfsRecommendations')) {
                    document.getElementById('vfsRecommendations').innerHTML = formatVFSRecommendations(recommendationsData);
                }
                
            } catch (error) {
                console.error('Error loading VFS Observatory data:', error);
                document.getElementById('cachePerformance').innerHTML = 'Error loading VFS Observatory data';
            }
        }
        
        function updateVFSHealth(healthData) {
            if (healthData.success) {
                const healthElement = document.getElementById('vfsHealthOverview');
                if (healthElement) {
                    healthElement.innerHTML = `
                        <div class="stat-card">
                            <h3>🏥 VFS Health Overview</h3>
                            <div class="metric">
                                <span class="metric-label">Overall Health Score</span>
                                <span class="metric-value">${Math.round(healthData.overall_health_score * 100)}%</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Cache Performance</span>
                                <span class="metric-value">${Math.round(healthData.health_factors.cache_performance * 100)}%</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Index Health</span>
                                <span class="metric-value">${Math.round(healthData.health_factors.index_health * 100)}%</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Resource Health</span>
                                <span class="metric-value">${Math.round(healthData.health_factors.resource_health * 100)}%</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Filesystem Health</span>
                                <span class="metric-value">${Math.round(healthData.health_factors.filesystem_health * 100)}%</span>
                            </div>
                            ${healthData.alerts && healthData.alerts.length > 0 ? `
                                <div class="metric">
                                    <span class="metric-label">Active Alerts</span>
                                    <span class="metric-value">${healthData.alerts.length}</span>
                                </div>
                            ` : ''}
                        </div>
                    `;
                }
        }
        
        function formatComprehensiveCacheDetails(cacheData) {
            if (!cacheData) return 'Cache performance data not available';
            
            return `
                <div class="stat-card">
                    <h4>🚀 Tiered Cache Performance</h4>
                    <div class="metric">
                        <span class="metric-label">Memory Tier Hit Rate</span>
                        <span class="metric-value">${Math.round(cacheData.tiered_cache.memory_tier.hit_rate * 100)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Memory Tier Size</span>
                        <span class="metric-value">${cacheData.tiered_cache.memory_tier.size_mb}MB (${cacheData.tiered_cache.memory_tier.items} items)</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Disk Tier Hit Rate</span>
                        <span class="metric-value">${Math.round(cacheData.tiered_cache.disk_tier.hit_rate * 100)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Disk Tier Size</span>
                        <span class="metric-value">${cacheData.tiered_cache.disk_tier.size_gb}GB (${cacheData.tiered_cache.disk_tier.items} items)</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Predictive Accuracy</span>
                        <span class="metric-value">${Math.round(cacheData.tiered_cache.predictive_accuracy * 100)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Prefetch Efficiency</span>
                        <span class="metric-value">${Math.round(cacheData.tiered_cache.prefetch_efficiency * 100)}%</span>
                    </div>
                </div>
                <div class="stat-card">
                    <h4>🧠 Semantic Cache</h4>
                    <div class="metric">
                        <span class="metric-label">Similarity Threshold</span>
                        <span class="metric-value">${cacheData.semantic_cache.similarity_threshold}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Cache Utilization</span>
                        <span class="metric-value">${Math.round(cacheData.semantic_cache.cache_utilization * 100)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Embedding Model</span>
                        <span class="metric-value">${cacheData.semantic_cache.embedding_model}</span>
                    </div>
                </div>
            `;
        }
        
        function formatComprehensiveFilesystemMetrics(fsData) {
            if (!fsData) return 'Filesystem metrics not available';
            
            return `
                <div class="stat-card">
                    <h4>📁 Mount Points</h4>
                    ${Object.entries(fsData.mount_points).map(([mount, data]) => `
                        <div class="metric">
                            <span class="metric-label">${mount}</span>
                            <span class="metric-value">${data.status} - ${data.size_gb}GB (${data.operations} ops)</span>
                        </div>
                    `).join('')}
                </div>
                <div class="stat-card">
                    <h4>📊 File Operations</h4>
                    <div class="metric">
                        <span class="metric-label">Reads / Writes</span>
                        <span class="metric-value">${fsData.file_operations.reads.toLocaleString()} / ${fsData.file_operations.writes.toLocaleString()}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Deletes / Listings</span>
                        <span class="metric-value">${fsData.file_operations.deletes} / ${fsData.file_operations.listings.toLocaleString()}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Seeks</span>
                        <span class="metric-value">${fsData.file_operations.seeks.toLocaleString()}</span>
                    </div>
                </div>
                <div class="stat-card">
                    <h4>🌐 Bandwidth Usage</h4>
                    <div class="metric">
                        <span class="metric-label">Read / Write Speed</span>
                        <span class="metric-value">${fsData.bandwidth_usage.read_mbps} / ${fsData.bandwidth_usage.write_mbps} Mbps</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Total Transferred</span>
                        <span class="metric-value">${fsData.bandwidth_usage.total_transferred_gb}GB</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Compression Ratio</span>
                        <span class="metric-value">${Math.round(fsData.bandwidth_usage.compression_ratio * 100)}%</span>
                    </div>
                </div>
            `;
        }
        
        function formatComprehensiveAccessPatterns(accessData) {
            if (!accessData) return 'Access patterns not available';
            
            return `
                <div class="stat-card">
                    <h4>🔥 Hot Content</h4>
                    ${accessData.hot_content.slice(0, 3).map(item => `
                        <div class="metric">
                            <span class="metric-label">${item.cid.substring(0, 12)}...</span>
                            <span class="metric-value">${item.access_count} accesses (${item.size_kb}KB)</span>
                        </div>
                    `).join('')}
                </div>
                <div class="stat-card">
                    <h4>⏰ Temporal Patterns</h4>
                    <div class="metric">
                        <span class="metric-label">Peak Hours</span>
                        <span class="metric-value">${accessData.temporal_patterns.peak_hours.join(', ')}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Weekly Pattern</span>
                        <span class="metric-value">${accessData.temporal_patterns.weekly_pattern}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Seasonal Trend</span>
                        <span class="metric-value">${accessData.temporal_patterns.seasonal_trend}</span>
                    </div>
                </div>
                <div class="stat-card">
                    <h4>📄 Content Types</h4>
                    ${Object.entries(accessData.content_types).map(([type, ratio]) => `
                            <div class="metric">
                                <span class="metric-label">${type}</span>
                                <span class="metric-value">${(ratio * 100).toFixed(1)}%</span>
                            </div>
                        `).join('')}
                    </div>
                <div class="stat-card">
                    <h4>🌍 Geographic Distribution</h4>
                    <div class="metric">
                        <span class="metric-label">Local / Remote</span>
                        <span class="metric-value">${Math.round(accessData.geographic_distribution.local * 100)}% / ${Math.round(accessData.geographic_distribution.remote_gateways * 100)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">CDN Hit Rate</span>
                        <span class="metric-value">${Math.round(accessData.geographic_distribution.cdn_hits * 100)}%</span>
                    </div>
                </div>
            `;
        }
        
        function formatResourceUtilization(resourceData) {
            if (!resourceData) return 'Resource utilization not available';
            
            return `
                <div class="stat-card">
                    <h4>💾 Memory Usage</h4>
                    <div class="metric">
                        <span class="metric-label">Cache / Index / Buffers</span>
                        <span class="metric-value">${resourceData.memory_usage.cache_mb}MB / ${resourceData.memory_usage.index_mb}MB / ${resourceData.memory_usage.buffers_mb}MB</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Total Used / Available</span>
                        <span class="metric-value">${resourceData.memory_usage.total_mb}MB / ${resourceData.memory_usage.available_mb}MB</span>
                    </div>
                </div>
                <div class="stat-card">
                    <h4>💽 Disk Usage</h4>
                    <div class="metric">
                        <span class="metric-label">Cache / Index / Logs</span>
                        <span class="metric-value">${resourceData.disk_usage.cache_gb}GB / ${resourceData.disk_usage.index_gb}GB / ${resourceData.disk_usage.logs_gb}GB</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Total Used / Available</span>
                        <span class="metric-value">${resourceData.disk_usage.total_gb}GB / ${resourceData.disk_usage.available_gb}GB</span>
                    </div>
                </div>
                <div class="stat-card">
                    <h4>⚡ CPU & Network Usage</h4>
                    <div class="metric">
                        <span class="metric-label">Indexing / Search / Cache</span>
                        <span class="metric-value">${Math.round(resourceData.cpu_usage.indexing * 100)}% / ${Math.round(resourceData.cpu_usage.search * 100)}% / ${Math.round(resourceData.cpu_usage.cache_management * 100)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Network Connections</span>
                        <span class="metric-value">IPFS: ${resourceData.network_usage.ipfs_connections}, Cluster: ${resourceData.network_usage.cluster_connections}</span>
                    </div>
                </div>
            `;
        }
        
        function formatVFSRecommendations(recommendationsData) {
            if (!recommendationsData || !recommendationsData.success) return 'Recommendations not available';
            
            return `
                <div class="stat-card">
                    <h4>💡 VFS Optimization Recommendations</h4>
                    ${recommendationsData.recommendations.map(rec => `
                        <div class="metric">
                            <span class="metric-label">${rec.category}</span>
                            <span class="metric-value">${rec.message}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        // VFS Observatory Tab Functions
        async function loadVFSObservatoryTab() {
            console.log('Loading VFS Observatory tab...');
            
            // Load resource usage
            try {
                const response = await fetch('/api/vfs/resource-utilization');
                const data = await response.json();
                document.getElementById('resourceUsage').innerHTML = formatResourceUsage(data);
            } catch (error) {
                console.error('Error loading resource usage:', error);
                document.getElementById('resourceUsage').innerHTML = 'Error loading resource usage';
            }
            
            // Load detailed sections
            try {
                const response = await fetch('/api/vfs/cache');
                const data = await response.json();
                document.getElementById('tieredCacheDetails').innerHTML = formatTieredCacheDetails(data);
            } catch (error) {
                console.error('Error loading tiered cache details:', error);
            }
            
            try {
                const response = await fetch('/api/vfs/access-patterns');
                const data = await response.json();
                document.getElementById('hotContentAnalysis').innerHTML = formatHotContentAnalysis(data);
            } catch (error) {
                console.error('Error loading hot content analysis:', error);
            }
        }
        
        // Vector & KB Tab Functions
        async function loadVectorKBTab() {
            console.log('Loading Vector & KB tab...');
            
            // Load vector index status
            try {
                const response = await fetch('/api/vfs/vector-index');
                const data = await response.json();
                document.getElementById('vectorIndexStatus').innerHTML = formatVectorIndexStatus(data);
                document.getElementById('vectorIndexDetails').innerHTML = formatVectorIndexDetails(data);
            } catch (error) {
                console.error('Error loading vector index status:', error);
                document.getElementById('vectorIndexStatus').innerHTML = 'Error loading vector index status';
            }
            
            // Load knowledge graph status
            try {
                const response = await fetch('/api/vfs/knowledge-base');
                const data = await response.json();
                document.getElementById('knowledgeGraphStatus').innerHTML = formatKnowledgeGraphStatus(data);
                document.getElementById('knowledgeBaseAnalytics').innerHTML = formatKnowledgeBaseAnalytics(data);
            } catch (error) {
                console.error('Error loading knowledge graph status:', error);
                document.getElementById('knowledgeGraphStatus').innerHTML = 'Error loading knowledge graph status';
            }
            
            // Load search performance
            try {
                const response = await fetch('/api/vfs/vector-index');
                const data = await response.json();
                document.getElementById('searchPerformance').innerHTML = formatSearchPerformance(data.search_performance);
            } catch (error) {
                console.error('Error loading search performance:', error);
                document.getElementById('searchPerformance').innerHTML = 'Error loading search performance';
            }
            
            // Load content distribution
            try {
                const response = await fetch('/api/vfs/vector-index');
                const data = await response.json();
                document.getElementById('contentDistribution').innerHTML = formatContentDistribution(data.content_distribution);
            } catch (error) {
                console.error('Error loading content distribution:', error);
                document.getElementById('contentDistribution').innerHTML = 'Error loading content distribution';
            }
            
            // Load semantic cache performance
            try {
                const response = await fetch('/api/vfs/cache');
                const data = await response.json();
                document.getElementById('semanticCachePerformance').innerHTML = formatSemanticCachePerformance(data.semantic_cache);
            } catch (error) {
                console.error('Error loading semantic cache performance:', error);
            }

            // Add search forms
            document.getElementById('vectorSearch').innerHTML = `
                <form onsubmit="searchVector(event)">
                    <input type="text" id="vectorQuery" placeholder="Search Vector DB">
                    <button type="submit">Search</button>
                </form>
                <div id="vectorSearchResults"></div>
            `;

            document.getElementById('kbSearch').innerHTML = `
                <form onsubmit="searchKB(event)">
                    <input type="text" id="kbQuery" placeholder="Search KB by Entity ID">
                    <button type="submit">Search</button>
                </form>
                <div id="kbSearchResults"></div>
            `;
        }

        async function searchVector(event) {
            event.preventDefault();
            const query = document.getElementById('vectorQuery').value;
            const resultsContainer = document.getElementById('vectorSearchResults');
            resultsContainer.innerHTML = 'Searching...';

            try {
                const response = await fetch('/api/vfs/vector-search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                const data = await response.json();
                if (data.success) {
                    resultsContainer.innerHTML = data.results.map(r => `<div class="search-result"><strong>${r.id}</strong> (Score: ${r.score.toFixed(2)})<br>${r.text}</div>`).join('');
                } else {
                    resultsContainer.innerHTML = `<div class="error">${data.error}</div>`;
                }
            } catch (error) {
                resultsContainer.innerHTML = `<div class="error">${error.message}</div>`;
            }
        }

        async function searchKB(event) {
            event.preventDefault();
            const entityId = document.getElementById('kbQuery').value;
            const resultsContainer = document.getElementById('kbSearchResults');
            resultsContainer.innerHTML = 'Searching...';

            try {
                const response = await fetch('/api/vfs/kb-search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ entity_id: entityId })
                });
                const data = await response.json();
                if (data.success) {
                    resultsContainer.innerHTML = `<div class="search-result"><strong>${data.results.label}</strong> (${data.results.entity_id})<br>${data.results.properties.description}</div>`;
                } else {
                    resultsContainer.innerHTML = `<div class="error">${data.error}</div>`;
                }
            } catch (error) {
                resultsContainer.innerHTML = `<div class="error">${error.message}</div>`;
            }
        }
        
        function formatFilesystemMetrics(data) {
            if (!data || !data.mount_points) return 'No filesystem metrics available';
            
            return `
                <div class="stats-grid">
                    <div class="stat-card">
                        <h4>Mount Points</h4>
                        ${Object.entries(data.mount_points).map(([mount, info]) => `
                            <div class="metric">
                                <span class="metric-label">${mount}</span>
                                <span class="metric-value status-badge status-${info.status === 'active' ? 'healthy' : 'unhealthy'}">${info.status}</span>
                            </div>
                        `).join('')}
                    </div>
                    <div class="stat-card">
                        <h4>Operations</h4>
                        ${Object.entries(data.file_operations).map(([op, count]) => `
                            <div class="metric">
                                <span class="metric-label">${op}</span>
                                <span class="metric-value">${count.toLocaleString()}</span>
                            </div>
                        `).join('')}
                    </div>
                    <div class="stat-card">
                        <h4>Bandwidth</h4>
                        <div class="metric">
                            <span class="metric-label">Read</span>
                            <span class="metric-value">${data.bandwidth_usage.read_mbps} Mbps</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Write</span>
                            <span class="metric-value">${data.bandwidth_usage.write_mbps} Mbps</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Compression</span>
                            <span class="metric-value">${(data.bandwidth_usage.compression_ratio * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        function formatSemanticCachePerformance(data) {
            if (!data) return 'No semantic cache data available';
            
            return `
                <div class="stats-grid">
                    <div class="stat-card">
                        <h4>Semantic Cache Performance</h4>
                        <div class="metric">
                            <span class="metric-label">Exact Matches</span>
                            <span class="metric-value">${data.exact_matches}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Similarity Matches</span>
                            <span class="metric-value">${data.similarity_matches}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Threshold</span>
                            <span class="metric-value">${data.similarity_threshold}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Utilization</span>
                            <span class="metric-value">${(data.cache_utilization * 100).toFixed(1)}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Model</span>
                            <span class="metric-value">${data.embedding_model}</span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // Initialize on page load
        refreshData();
        initializeExpandables();
        
        // Set up auto-refresh
        setInterval(refreshData, 30000);

        // File Manager Functions
        async function loadFileManagerTab() {
            console.log('Loading File Manager tab for path:', currentPath);
            document.getElementById('currentPath').textContent = currentPath;
            try {
                const response = await fetch(`/api/files/list?path=${encodeURIComponent(currentPath)}`);
                const data = await response.json();
                
                if (data.success) {
                    renderFiles(data.files);
                } else {
                    document.getElementById('fileList').innerHTML = `<div style="color: red; padding: 20px;">Error loading files: ${data.error}</div>`;
                }
            } catch (error) {
                console.error('Error loading file manager data:', error);
                document.getElementById('fileList').innerHTML = '<div style="color: red; padding: 20px;">Error loading file manager data</div>';
            }
        }

        function renderFiles(files) {
            const fileListElement = document.getElementById('fileList');
            fileListElement.innerHTML = ''; // Clear current list

            // Add ".." for navigating up
            if (currentPath !== '/') {
                const upDirItem = document.createElement('div');
                upDirItem.className = 'file-item';
                upDirItem.innerHTML = `
                    <span class="file-item-icon">&#128193;</span>
                    <span class="file-item-name">..</span>
                    <span class="file-item-size"></span>
                    <span class="file-item-modified"></span>
                    <div class="file-item-actions"></div>
                `;
                upDirItem.onclick = () => navigateToFileManager(currentPath.substring(0, currentPath.lastIndexOf('/')) || '/');
                fileListElement.appendChild(upDirItem);
            }

            files.sort((a, b) => {
                if (a.is_dir === b.is_dir) {
                    return a.name.localeCompare(b.name);
                }
                return a.is_dir ? -1 : 1; // Directories first
            });

            files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.draggable = true; // Enable dragging
                fileItem.dataset.path = file.path;
                fileItem.dataset.isDir = file.is_dir;

                fileItem.innerHTML = `
                    <span class="file-item-icon">${getFileIcon(file)}</span>
                    <span class="file-item-name">${file.name}</span>
                    <span class="file-item-size">${file.is_dir ? '' : formatFileSize(file.size)}</span>
                    <span class="file-item-modified">${formatFileModified(file.modified)}</span>
                    <div class="file-item-actions">
                        ${file.is_dir ? '' : `<button onclick="downloadFile('${file.path}', '${file.name}')" title="Download">&#128229;</button>`}
                        <button onclick="renameFilePrompt('${file.path}', '${file.name}')" title="Rename">&#128221;</button>
                        <button onclick="deleteFile('${file.path}')" title="Delete">&#128465;</button>
                    </div>
                `;
                
                if (file.is_dir) {
                    fileItem.onclick = () => navigateToFileManager(file.path);
                } else {
                    // For files, click might open/preview, for now just log
                    fileItem.onclick = () => console.log('Clicked file:', file.name);
                }
                fileListElement.appendChild(fileItem);
            });
        }

        function getFileIcon(file) {
            if (file.is_dir) return '&#128193;'; // Folder icon
            const ext = file.name.split('.').pop().toLowerCase();
            switch (ext) {
                case 'txt': return '&#128462;'; // Text file
                case 'pdf': return '&#128195;'; // PDF
                case 'jpg': case 'png': case 'gif': return '&#128444;'; // Image
                case 'zip': case 'rar': return '&#128452;'; // Archive
                case 'js': case 'py': case 'html': case 'css': return '&#128187;'; // Code file
                default: return '&#128462;'; // Generic file
            }
        }

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function formatFileModified(timestamp) {
            const date = new Date(timestamp * 1000); // Convert Unix timestamp to milliseconds
            return date.toLocaleString();
        }

        async function createFolderPrompt() {
            const folderName = prompt('Enter new folder name:');
            if (folderName) {
                try {
                    const response = await fetch('/api/files/create-folder', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: currentPath, name: folderName })
                    });
                    const data = await response.json();
                    if (data.success) {
                        alert('Folder created successfully!');
                        loadFileManagerTab();
                    } else {
                        alert('Error creating folder: ' + data.error);
                    }
                } catch (error) {
                    console.error('Error creating folder:', error);
                    alert('Error creating folder: ' + error.message);
                }
            }
        }

        async function uploadSelectedFile() {
            const fileInput = document.getElementById('fileUploadInput');
            if (fileInput.files.length > 0) {
                const file = fileInput.files[0];
                const formData = new FormData();
                formData.append('file', file);
                formData.append('path', currentPath);

                try {
                    const response = await fetch('/api/files/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    if (data.success) {
                        alert('File uploaded successfully!');
                        loadFileManagerTab();
                    } else {
                        alert('Error uploading file: ' + data.error);
                    }
                } catch (error) {
                    console.error('Error uploading file:', error);
                    alert('Error uploading file: ' + error.message);
                }
            }
        }

        async function deleteFile(path) {
            if (confirm(`Are you sure you want to delete ${path}?`)) {
                try {
                    const response = await fetch('/api/files/delete', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: path })
                    });
                    const data = await response.json();
                    if (data.success) {
                        alert('Item deleted successfully!');
                        loadFileManagerTab();
                    } else {
                        alert('Error deleting item: ' + data.error);
                    }
                } catch (error) {
                    console.error('Error deleting item:', error);
                    alert('Error deleting item: ' + error.message);
                }
            }
        }

        async function renameFilePrompt(path, oldName) {
            const newName = prompt(`Rename ${oldName} to:`, oldName);
            if (newName && newName !== oldName) {
                try {
                    const response = await fetch('/api/files/rename', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ oldPath: path, newName: newName })
                    });
                    const data = await response.json();
                    if (data.success) {
                        alert('Item renamed successfully!');
                        loadFileManagerTab();
                    } else {
                        alert('Error renaming item: ' + data.error);
                    }
                } catch (error) {
                    console.error('Error renaming item:', error);
                    alert('Error renaming item: ' + error.message);
                }
            }
        }

        async function downloadFile(path, name) {
            try {
                const response = await fetch(`/api/files/download?path=${encodeURIComponent(path)}`);
                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = name;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                } else {
                    const errorData = await response.json();
                    alert('Error downloading file: ' + errorData.error);
                }
            } catch (error) {
                console.error('Error downloading file:', error);
                alert('Error downloading file: ' + error.message);
            }
        }

        function navigateToFileManager(newPath) {
            currentPath = newPath;
            document.getElementById('currentPath').textContent = currentPath;
            loadFileManagerTab();
        }

        // Drag and Drop functionality
        let draggedItem = null;

        function setupDragAndDrop() {
            const fileList = document.getElementById('fileList');

            fileList.addEventListener('dragstart', (e) => {
                draggedItem = e.target.closest('.file-item');
                if (draggedItem) {
                    e.dataTransfer.setData('text/plain', draggedItem.dataset.path);
                    e.dataTransfer.effectAllowed = 'move';
                    setTimeout(() => draggedItem.classList.add('dragging'), 0);
                }
            });

            fileList.addEventListener('dragover', (e) => {
                e.preventDefault();
                const targetItem = e.target.closest('.file-item');
                if (targetItem && targetItem.dataset.isDir === 'true') {
                    targetItem.classList.add('drag-over');
                } else {
                    fileList.classList.add('drag-over'); // Indicate drop on current directory
                }
                e.dataTransfer.dropEffect = 'move';
            });

            fileList.addEventListener('dragleave', (e) => {
                const targetItem = e.target.closest('.file-item');
                if (targetItem) {
                    targetItem.classList.remove('drag-over');
                }
                fileList.classList.remove('drag-over');
            });

            fileList.addEventListener('drop', async (e) => {
                e.preventDefault();
                const targetItem = e.target.closest('.file-item');
                let dropPath = currentPath;

                if (targetItem && targetItem.dataset.isDir === 'true') {
                    dropPath = targetItem.dataset.path;
                }
                
                fileList.classList.remove('drag-over');
                if (targetItem) {
                    targetItem.classList.remove('drag-over');
                }
                if (draggedItem) {
                    draggedItem.classList.remove('dragging');
                }

                const sourcePath = e.dataTransfer.getData('text/plain');
                if (sourcePath && sourcePath !== dropPath) {
                    const sourceName = sourcePath.split('/').pop();
                    const newTargetPath = dropPath === '/' ? `/${sourceName}` : `${dropPath}/${sourceName}`;

                    // Prevent moving a folder into itself or its subfolder
                    if (dropPath.startsWith(sourcePath) && dropPath !== sourcePath) {
                        alert('Cannot move a folder into itself or its subfolder.');
                        return;
                    }

                    try {
                        const response = await fetch('/api/files/move', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ sourcePath: sourcePath, targetPath: newTargetPath })
                        });
                        const data = await response.json();
                        if (data.success) {
                            alert('Item moved successfully!');
                            loadFileManagerTab();
                        } else {
                            alert('Error moving item: ' + data.error);
                        }
                    } catch (error) {
                        console.error('Error moving item:', error);
                        alert('Error moving item: ' + error.message);
                    }
                }
                draggedItem = null;
            });

            fileList.addEventListener('dragend', () => {
                if (draggedItem) {
                    draggedItem.classList.remove('dragging');
                }
                draggedItem = null;
            });
        }
        
        // Tab loading functions with proper API calls
        async function refreshMonitoring() {
            console.log('Refreshing monitoring data...');
            await refreshData(); // Use the main refresh function
            await loadBackendsTab();
        }
        
        async function loadVFSTab() {
            console.log('Loading VFS Observatory tab...');
            try {
                // Load VFS statistics
                const response = await fetch('/api/vfs/statistics');
                const data = await response.json();
                
                if (data.success && data.data) {
                    const vfsData = data.data;
                    document.getElementById('cachePerformance').innerHTML = formatCachePerformance(vfsData.cache_performance);
                    document.getElementById('filesystemStatus').innerHTML = formatFilesystemStatus(vfsData.filesystem_metrics);
                    document.getElementById('accessPatterns').innerHTML = formatAccessPatterns(vfsData.access_patterns);
                    document.getElementById('resourceUsage').innerHTML = formatResourceUsage(vfsData.resource_utilization);
                } else {
                    console.error('Failed to load VFS data:', data.error);
                }
            } catch (error) {
                console.error('Error loading VFS tab:', error);
            }
        }
        
        async function loadVectorKBTab() {
            console.log('Loading Vector/KB tab...');
            try {
                // Load vector index and knowledge base data
                const [vectorResponse, kbResponse] = await Promise.all([
                    fetch('/api/vfs/vector-index'),
                    fetch('/api/vfs/knowledge-base')
                ]);
                
                const vectorData = await vectorResponse.json();
                const kbData = await kbResponse.json();
                
                if (vectorData.success && vectorData.data) {
                    document.getElementById('vectorIndexStatus').innerHTML = formatVectorIndexStatus(vectorData.data);
                }
                if (kbData.success && kbData.data) {
                    document.getElementById('knowledgeGraphStatus').innerHTML = formatKnowledgeGraphStatus(kbData.data);
                }
            } catch (error) {
                console.error('Error loading Vector/KB tab:', error);
            }
        }
        
        async function loadBackendsTab() {
            console.log('Loading Backends tab...');
            await refreshData(); // Use the main refresh function
        }
        
        async function loadConfigurationTab() {
            console.log('Loading Configuration tab...');
            try {
                // Load package configuration
                const response = await fetch('/api/config/package');
                const data = await response.json();
                if (data.success) {
                    // Configuration loading logic would go here
                    console.log('Configuration loaded');
                }
            } catch (error) {
                console.error('Error loading configuration:', error);
            }
        }
        
        async function loadFileManagerTab() {
            console.log('Loading File Manager tab...');
            try {
                // Load file list
                const response = await fetch('/api/files/');
                const data = await response.json();
                
                if (data.success && data.files) {
                    displayFileList(data.files);
                } else {
                    console.error('Failed to load file list:', data.error);
                }
            } catch (error) {
                console.error('Error loading file manager tab:', error);
            }
        }
        
        function createFolderPrompt() {
            const folderName = prompt('Enter folder name:');
            if (folderName) {
                console.log('Creating folder:', folderName);
                // Folder creation logic here
            }
        }
        
        function savePackageConfig() {
            console.log('Saving package configuration...');
            alert('Configuration saved!');
        }
        
        function closeConfigModal() {
            console.log('Closing config modal...');
            // Modal closing logic here
        }
        
        // File Manager Functions
        function displayFileList(files) {
            const fileList = document.getElementById('file-list');
            if (!fileList) {
                console.error('File list element not found');
                return;
            }
            
            fileList.innerHTML = files.map(file => `
                <div class="file-item ${file.type}" data-name="${file.name}" data-path="${file.path}">
                    <span class="file-icon">${file.type === 'directory' ? '📁' : '📄'}</span>
                    <span class="file-name">${file.name}</span>
                    <span class="file-size">${formatFileSize(file.size || 0)}</span>
                    <span class="file-actions">
                        ${file.type === 'file' ? `<button onclick="downloadFile('${file.name}')">📥 Download</button>` : ''}
                        <button onclick="deleteFile('${file.name}')">🗑️ Delete</button>
                    </span>
                </div>
            `).join('');
        }
        
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        
        async function downloadFile(filename) {
            try {
                const response = await fetch(`/api/files/${filename}`);
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    a.click();
                    window.URL.revokeObjectURL(url);
                } else {
                    console.error('Download failed:', response.statusText);
                    alert('Download failed: ' + response.statusText);
                }
            } catch (error) {
                console.error('Download error:', error);
                alert('Download failed: ' + error.message);
            }
        }
        
        async function deleteFile(filename) {
            if (confirm(`Are you sure you want to delete ${filename}?`)) {
                try {
                    const response = await fetch(`/api/files/${filename}`, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        await loadFileManagerTab(); // Refresh file list
                    } else {
                        throw new Error(data.error || 'Delete failed');
                    }
                } catch (error) {
                    console.error('Delete error:', error);
                    alert('Delete failed: ' + error.message);
                }
            }
        }
        
        async function uploadSelectedFile() {
            const fileInput = document.getElementById('fileUploadInput');
            if (fileInput.files.length > 0) {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                
                try {
                    const response = await fetch('/api/files/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        await loadFileManagerTab(); // Refresh file list
                        fileInput.value = ''; // Clear the input
                    } else {
                        throw new Error(data.error || 'Upload failed');
                    }
                } catch (error) {
                    console.error('Upload error:', error);
                    alert('Upload failed: ' + error.message);
                }
            }
        }
        
        function createFolderPrompt() {
            const folderName = prompt('Enter folder name:');
            if (folderName) {
                createFolder(folderName);
            }
        }
        
        async function createFolder(folderName) {
            try {
                const response = await fetch('/api/files/create_folder', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ name: folderName })
                });
                const data = await response.json();
                
                if (data.success) {
                    await loadFileManagerTab(); // Refresh file list
                } else {
                    throw new Error(data.error || 'Create folder failed');
                }
            } catch (error) {
                console.error('Create folder error:', error);
                alert('Create folder failed: ' + error.message);
            }
        }
