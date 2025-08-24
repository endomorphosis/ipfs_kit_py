// Data Loading Functions
async function loadOverviewData() {
    try {
        const [overview, systemMetrics] = await Promise.all([
            window.ipfsKitAPI.getOverview(),
            window.ipfsKitAPI.getSystemMetrics()
        ]);
        
        const status = overview.data || overview;
        const counts = (status && status.counts) || {};
        const memory = systemMetrics.memory || {};
        const disk = systemMetrics.disk || {};
        const cpuPercent = typeof systemMetrics.cpu_percent === 'number' ? systemMetrics.cpu_percent : 0;

        document.getElementById('services-count').textContent = counts.services_active ?? '0';
        document.getElementById('backends-count').textContent = counts.backends ?? '0';
        document.getElementById('buckets-count').textContent = counts.buckets ?? '0';

        document.getElementById('cpu-percent').textContent = `${cpuPercent.toFixed(1)}%`;
        document.getElementById('cpu-bar').style.width = `${cpuPercent}%`;
        if (typeof memory.percent === 'number') {
            document.getElementById('memory-percent').textContent = `${memory.percent.toFixed(1)}%`;
            document.getElementById('memory-bar').style.width = `${memory.percent}%`;
        }
        if (typeof memory.used === 'number') document.getElementById('memory-used').textContent = formatBytes(memory.used);
        if (typeof memory.total === 'number') document.getElementById('memory-total').textContent = formatBytes(memory.total);
        if (typeof disk.percent === 'number') {
            document.getElementById('disk-percent').textContent = `${disk.percent.toFixed(1)}%`;
            document.getElementById('disk-bar').style.width = `${disk.percent}%`;
        }
        if (typeof disk.used === 'number') document.getElementById('disk-used').textContent = formatBytes(disk.used);
        if (typeof disk.total === 'number') document.getElementById('disk-total').textContent = formatBytes(disk.total);

        document.getElementById('sidebar-backends-count').textContent = counts.backends ?? '0';
        document.getElementById('sidebar-cpu-percent').textContent = `${Number(cpuPercent || 0).toFixed(0)}%`;
        document.getElementById('sidebar-cpu-bar').style.width = `${cpuPercent}%`;
        if (typeof memory.percent === 'number') {
            document.getElementById('sidebar-memory-percent').textContent = `${memory.percent.toFixed(0)}%`;
            document.getElementById('sidebar-memory-bar').style.width = `${memory.percent}%`;
        }

        loadIpfsDaemonStatus();
        loadNetworkActivity();
    } catch (error) {
        console.error('Error loading overview data:', error);
    }
}

async function loadIpfsDaemonStatus() {
    try {
        const data = await window.ipfsKitAPI.getServices();
        const services = data.services || {};
        const ipfs = services.ipfs || {};
        const isRunning = !!ipfs.api_port_open;
        const statusDiv = document.getElementById('ipfs-daemon-status');
        
        let statusHtml = '';
        if (isRunning) {
            statusHtml = `
                <div class="text-center p-4 bg-green-50 rounded-lg">
                    <div class="text-4xl text-green-500 mb-2"><i class="fas fa-check-circle"></i></div>
                    <p class="font-semibold text-green-800">Daemon Running</p>
                </div>
                <div class="p-4 bg-gray-50 rounded-lg col-span-2">
                    <p class="text-sm text-gray-600 break-all"><strong>Binary:</strong> ${ipfs.bin || 'N/A'}</p>
                    <p class="text-sm text-gray-600 mt-2"><strong>API Port:</strong> ${ipfs.api_port_open ? 'open' : 'closed'}</p>
                </div>
            `;
            document.getElementById('sidebar-ipfs-status').textContent = 'Running';
            document.getElementById('sidebar-ipfs-dot').className = 'status-dot running';
        } else {
            statusHtml = `
                <div class="text-center p-4 bg-red-50 rounded-lg col-span-3">
                    <div class="text-4xl text-red-500 mb-2"><i class="fas fa-times-circle"></i></div>
                    <p class="font-semibold text-red-800">Daemon Stopped</p>
                    <p class="text-sm text-gray-600 mt-2">${ipfs.bin ? 'API not reachable' : 'ipfs binary not found'}</p>
                </div>
            `;
            document.getElementById('sidebar-ipfs-status').textContent = 'Stopped';
            document.getElementById('sidebar-ipfs-dot').className = 'status-dot error';
        }
        statusDiv.innerHTML = statusHtml;
    } catch (error) {
        console.error('Error loading IPFS daemon status:', error);
        document.getElementById('ipfs-daemon-status').innerHTML = '<p class="text-red-500">Failed to load daemon status.</p>';
    }
}

async function loadNetworkActivity() {
    try {
        const data = await window.ipfsKitAPI.getSystemMetrics();
        const networkData = data.network || {};
        const points = Array.isArray(networkData.points) ? networkData.points : [];
        const last = points.length ? points[points.length - 1] : {};
        const tx = last.tx_bps || 0;
        const rx = last.rx_bps || 0;
        const contentDiv = document.getElementById('network-activity-content');
        function formatBps(v){
            const kb = v/1024; const mb = kb/1024;
            if (mb >= 1) return `${mb.toFixed(2)} MiB/s`;
            if (kb >= 1) return `${kb.toFixed(1)} KiB/s`;
            return `${v.toFixed(0)} B/s`;
        }
        contentDiv.innerHTML = `
            <div class="flex items-center">
                <div class="p-3 rounded-lg bg-gradient-to-r from-blue-400 to-cyan-500 mr-4">
                    <i class="fas fa-arrow-up text-white"></i>
                </div>
                <div>
                    <p class="text-gray-600 text-sm">TX Rate</p>
                    <p class="font-bold text-xl">${formatBps(tx)}</p>
                </div>
            </div>
            <div class="flex items-center">
                <div class="p-3 rounded-lg bg-gradient-to-r from-green-400 to-emerald-500 mr-4">
                    <i class="fas fa-arrow-down text-white"></i>
                </div>
                <div>
                    <p class="text-gray-600 text-sm">RX Rate</p>
                    <p class="font-bold text-xl">${formatBps(rx)}</p>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading network activity:', error);
        document.getElementById('network-activity-content').innerHTML = '<p class="text-red-500">Failed to load network data.</p>';
    }
}

async function loadServices() {
    try {
        const response = await fetch('/api/services');
        const data = await response.json();
        const servicesList = document.getElementById('services-list');
        const totalBadge = document.getElementById('services-total-badge');
        
        // Update summary counts
        const summary = data.summary || {};
        document.getElementById('services-running-count').textContent = summary.running || 0;
        document.getElementById('services-stopped-count').textContent = summary.stopped || 0;
        document.getElementById('services-configured-count').textContent = summary.configured || 0;
        document.getElementById('services-error-count').textContent = summary.error || 0;
        
        const services = data.services || [];
        totalBadge.textContent = services.length;
        servicesList.innerHTML = '';

        if (services.length > 0) {
            services.forEach(service => {
                const statusConfig = getServiceStatusConfig(service.status);
                const actions = service.actions || [];
                
                // Create action buttons
                const actionButtons = actions.map(action => {
                    const actionConfig = getActionConfig(action);
                    return `
                        <button onclick="performServiceAction('${service.id}', '${action}')" 
                                class="px-3 py-1 text-sm font-medium rounded-lg ${actionConfig.class} hover:opacity-80 transition-opacity"
                                title="${actionConfig.title}">
                            <i class="fas ${actionConfig.icon} mr-1"></i>
                            ${actionConfig.label}
                        </button>
                    `;
                }).join(' ');

                const serviceCard = `
                    <div class="service-card bg-white border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
                        <div class="flex items-start justify-between">
                            <div class="flex-grow">
                                <div class="flex items-center mb-2">
                                    <div class="p-2 rounded-lg ${statusConfig.bgClass} mr-3">
                                        <i class="fas ${getServiceTypeIcon(service.type)} text-white"></i>
                                    </div>
                                    <div>
                                        <h4 class="text-lg font-semibold text-gray-800">${service.name}</h4>
                                        <p class="text-sm text-gray-500">${service.type}</p>
                                    </div>
                                </div>
                                <p class="text-sm text-gray-600 mb-3">${service.description}</p>
                                
                                <!-- Service Details -->
                                <div class="grid grid-cols-2 gap-4 text-sm text-gray-600 mb-4">
                                    ${service.port ? `<div><span class="font-medium">Port:</span> ${service.port}</div>` : ''}
                                    ${service.last_check ? `<div><span class="font-medium">Last Check:</span> ${formatTimestamp(service.last_check)}</div>` : ''}
                                    ${service.requires_credentials ? `<div><span class="font-medium">Credentials:</span> Required</div>` : ''}
                                </div>
                            </div>
                            
                            <!-- Status and Actions -->
                            <div class="flex flex-col items-end space-y-3">
                                <div class="flex items-center px-3 py-2 rounded-full text-white text-sm font-medium ${statusConfig.badgeClass}">
                                    <i class="fas ${statusConfig.icon} mr-2"></i>
                                    <span>${service.status}</span>
                                </div>
                                
                                ${actionButtons.length > 0 ? `
                                    <div class="flex flex-wrap gap-2 justify-end">
                                        ${actionButtons}
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                        
                        <!-- Service Details Toggle -->
                        ${service.details && Object.keys(service.details).length > 0 ? `
                            <div class="mt-4 pt-4 border-t border-gray-200">
                                <button onclick="toggleServiceDetails('${service.id}')" class="text-sm text-blue-600 hover:text-blue-800">
                                    <i class="fas fa-chevron-down mr-1" id="details-icon-${service.id}"></i>
                                    View Details
                                </button>
                                <div id="service-details-${service.id}" class="hidden mt-3 p-3 bg-gray-50 rounded-lg">
                                    <pre class="text-xs text-gray-700">${JSON.stringify(service.details, null, 2)}</pre>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                `;
                servicesList.innerHTML += serviceCard;
            });
        } else {
            servicesList.innerHTML = `
                <div class="text-center py-12">
                    <div class="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
                        <i class="fas fa-cogs text-2xl text-gray-400"></i>
                    </div>
                    <p class="text-gray-500 font-medium">No services available</p>
                    <p class="text-gray-400 text-sm mt-2">Enable services in configuration to get started</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading services:', error);
        document.getElementById('services-list').innerHTML = `
            <div class="text-center py-12">
                <div class="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
                    <i class="fas fa-exclamation-triangle text-2xl text-red-500"></i>
                </div>
                <p class="text-red-500 font-medium">Failed to load services</p>
                <p class="text-gray-500 text-sm mt-2">${error.message}</p>
            </div>
        `;
    }
}

function getServiceStatusConfig(status) {
    switch (status) {
        case 'running':
            return { bgClass: 'bg-green-500', badgeClass: 'bg-green-500', icon: 'fa-check-circle' };
        case 'stopped':
            return { bgClass: 'bg-red-500', badgeClass: 'bg-red-500', icon: 'fa-stop-circle' };
        case 'configured':
            return { bgClass: 'bg-blue-500', badgeClass: 'bg-blue-500', icon: 'fa-cog' };
        case 'error':
            return { bgClass: 'bg-red-600', badgeClass: 'bg-red-600', icon: 'fa-exclamation-triangle' };
        case 'starting':
            return { bgClass: 'bg-yellow-500', badgeClass: 'bg-yellow-500', icon: 'fa-spinner fa-spin' };
        case 'stopping':
            return { bgClass: 'bg-orange-500', badgeClass: 'bg-orange-500', icon: 'fa-spinner fa-spin' };
        default:
            return { bgClass: 'bg-gray-500', badgeClass: 'bg-gray-500', icon: 'fa-question-circle' };
    }
}

function getServiceTypeIcon(type) {
    switch (type) {
        case 'daemon':
            return 'fa-server';
        case 'storage':
            return 'fa-database';
        case 'network':
            return 'fa-network-wired';
        case 'credential':
            return 'fa-key';
        default:
            return 'fa-cog';
    }
}

function getActionConfig(action) {
    switch (action) {
        case 'start':
            return { class: 'bg-green-500 text-white', icon: 'fa-play', label: 'Start', title: 'Start service' };
        case 'stop':
            return { class: 'bg-red-500 text-white', icon: 'fa-stop', label: 'Stop', title: 'Stop service' };
        case 'restart':
            return { class: 'bg-orange-500 text-white', icon: 'fa-redo', label: 'Restart', title: 'Restart service' };
        case 'configure':
            return { class: 'bg-blue-500 text-white', icon: 'fa-cog', label: 'Configure', title: 'Configure service' };
        case 'health_check':
            return { class: 'bg-purple-500 text-white', icon: 'fa-heartbeat', label: 'Health', title: 'Check health' };
        case 'view_logs':
            return { class: 'bg-gray-500 text-white', icon: 'fa-file-alt', label: 'Logs', title: 'View logs' };
        default:
            return { class: 'bg-gray-400 text-white', icon: 'fa-question', label: action, title: action };
    }
}

async function performServiceAction(serviceId, action) {
    try {
        // Show loading state
        const actionButtons = document.querySelectorAll(`[onclick*="${serviceId}"]`);
        actionButtons.forEach(btn => {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Working...';
        });

        const response = await fetch(`/api/services/${serviceId}/action`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ action: action })
        });

        const result = await response.json();

        if (result.success) {
            showNotification(`${action} completed successfully`, 'success');
            // Reload services to show updated status
            setTimeout(() => loadServices(), 1000);
        } else {
            showNotification(`Failed to ${action}: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('Error performing service action:', error);
        showNotification(`Error performing ${action}: ${error.message}`, 'error');
    } finally {
        // Restore button states
        setTimeout(() => loadServices(), 500);
    }
}

function toggleServiceDetails(serviceId) {
    const detailsDiv = document.getElementById(`service-details-${serviceId}`);
    const icon = document.getElementById(`details-icon-${serviceId}`);
    
    if (detailsDiv.classList.contains('hidden')) {
        detailsDiv.classList.remove('hidden');
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    } else {
        detailsDiv.classList.add('hidden');
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg transition-all duration-300 ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    notification.innerHTML = `
        <div class="flex items-center">
            <i class="fas ${
                type === 'success' ? 'fa-check-circle' :
                type === 'error' ? 'fa-exclamation-triangle' :
                'fa-info-circle'
            } mr-2"></i>
            ${message}
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Remove notification after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => document.body.removeChild(notification), 300);
    }, 3000);
}

function formatTimestamp(timestamp) {
    try {
        const date = new Date(timestamp);
        return date.toLocaleString();
    } catch (error) {
        return timestamp;
    }
}

async function loadBackends() {
    try {
        const [backendsData, backendStats] = await Promise.all([
            window.ipfsKitAPI.getBackends(),
            window.ipfsKitAPI.getBackendMetrics('all')
        ]);
        
        const backendsList = document.getElementById('backends-list');
        backendsList.innerHTML = '';

        const items = backendsData.items || [];
        if (items.length > 0) {
            for (const backend of items) {
                const stats = backendStats.backends ? backendStats.backends[backend.name] : {};
                const storage = stats.storage || {};
                const quota = stats.quota || {};
                const health = stats.health || {};
                
                const statusColor = window.ipfsKitAPI.getStatusColor(stats.status || 'unknown');
                
                const item = `
                    <div class="card p-6 mb-4">
                        <div class="flex justify-between items-start mb-4">
                            <div>
                                <h4 class="text-lg font-semibold">${backend.name}</h4>
                                <span class="text-sm px-2 py-1 bg-${statusColor}-100 text-${statusColor}-800 rounded">${stats.status || 'Unknown'}</span>
                            </div>
                            <div class="text-right">
                                <div class="text-sm text-gray-600">Type: ${backend.type || 'Unknown'}</div>
                                <div class="text-sm text-gray-600">Last Check: ${stats.last_health_check ? window.ipfsKitAPI.formatTimestamp(stats.last_health_check * 1000) : 'Never'}</div>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                            <div class="bg-blue-50 p-3 rounded">
                                <div class="text-sm font-medium text-blue-800">Storage Used</div>
                                <div class="text-xl font-bold text-blue-900">${window.ipfsKitAPI.formatBytes(storage.used_space || 0)}</div>
                                <div class="text-xs text-blue-600">${storage.files_count || 0} files</div>
                            </div>
                            <div class="bg-green-50 p-3 rounded">
                                <div class="text-sm font-medium text-green-800">Available Space</div>
                                <div class="text-xl font-bold text-green-900">${window.ipfsKitAPI.formatBytes(storage.available_space || 0)}</div>
                                <div class="text-xs text-green-600">${storage.usage_percent || 0}% used</div>
                            </div>
                            <div class="bg-purple-50 p-3 rounded">
                                <div class="text-sm font-medium text-purple-800">Quota Usage</div>
                                <div class="text-xl font-bold text-purple-900">${quota.usage_percent || 0}%</div>
                                <div class="text-xs text-purple-600">${window.ipfsKitAPI.formatBytes(quota.remaining || 0)} remaining</div>
                            </div>
                        </div>
                        
                        <div class="flex justify-between items-center">
                            <div class="text-sm text-gray-600">
                                Avg Response: ${health.avg_response_time ? (health.avg_response_time * 1000).toFixed(0) + 'ms' : 'N/A'}
                            </div>
                            <div class="space-x-2">
                                <button onclick="testBackend('${backend.name}')" class="px-3 py-1 bg-blue-500 text-white text-sm rounded hover:bg-blue-600">Test</button>
                                <button onclick="configureBackend('${backend.name}')" class="px-3 py-1 bg-green-500 text-white text-sm rounded hover:bg-green-600">Configure</button>
                                <button onclick="removeBackend('${backend.name}')" class="px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600">Remove</button>
                            </div>
                        </div>
                    </div>
                `;
                backendsList.innerHTML += item;
            }
        } else {
            backendsList.innerHTML = '<p class="text-center text-gray-500">No backends configured.</p>';
        }
    } catch (error) {
        console.error('Error loading backends:', error);
        document.getElementById('backends-list').innerHTML = '<p class="text-red-500">Failed to load backends.</p>';
    }
}

async function loadBuckets() {
    try {
        const data = await window.ipfsKitAPI.getBuckets();
        const bucketsList = document.getElementById('buckets-list');
        bucketsList.innerHTML = '';

        const items = (data.items || []);
        if (items.length > 0) {
            items.forEach(bucket => {
                const item = `
                    <div class="card p-6 mb-4">
                        <h4 class="text-lg font-semibold">${bucket.name}</h4>
                        <p>Backend: ${bucket.backend || '-'}</p>
                        <p>Meta: <pre class="text-xs bg-gray-900 text-gray-100 p-2 rounded">${JSON.stringify(bucket.meta || {}, null, 2)}</pre></p>
                    </div>
                `;
                bucketsList.innerHTML += item;
            });
        } else {
            bucketsList.innerHTML = '<p class="text-center text-gray-500">No buckets found.</p>';
        }
    } catch (error) {
        console.error('Error loading buckets:', error);
        document.getElementById('buckets-list').innerHTML = '<p class="text-red-500">Failed to load buckets.</p>';
    }
}

async function loadMetrics() {
    // Placeholder for metrics loading logic
    document.getElementById('metrics-content').innerHTML = '<p class="text-center text-gray-500">Detailed metrics coming soon.</p>';
}

async function loadMcpDetails() {
    // Placeholder for MCP details loading logic
    document.getElementById('mcp-content').innerHTML = '<p class="text-center text-gray-500">MCP server details coming soon.</p>';
}

// Backend Management Functions
async function testBackend(backendId) {
    try {
        const result = await window.ipfsKitAPI.testBackend(backendId);
        if (result.success) {
            alert(`Backend ${backendId} test successful!`);
        } else {
            alert(`Backend ${backendId} test failed: ${result.error}`);
        }
    } catch (error) {
        console.error('Error testing backend:', error);
        alert('Failed to test backend');
    }
}

async function configureBackend(backendId) {
    // This could open a modal or redirect to config page
    showTab('config');
    // Focus on the specific backend configuration
    // This would require additional UI work
}

async function removeBackend(backendId) {
    if (!confirm(`Are you sure you want to remove backend "${backendId}"?`)) {
        return;
    }
    
    try {
        const result = await window.ipfsKitAPI.deleteBackend(backendId);
        if (result.success) {
            alert(`Backend ${backendId} removed successfully!`);
            loadBackends(); // Refresh the backends list
        } else {
            alert(`Failed to remove backend: ${result.error}`);
        }
    } catch (error) {
        console.error('Error removing backend:', error);
        alert('Failed to remove backend');
    }
}

async function addNewBackend() {
    // This would open a modal for adding new backends
    // For now, just show an alert
    alert('Add New Backend functionality will be implemented in a future version');
}
