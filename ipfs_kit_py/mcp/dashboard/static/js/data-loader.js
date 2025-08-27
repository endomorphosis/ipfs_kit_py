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

// Global variables for bucket management
let selectedBucket = null;
let currentFileView = 'list';
let bucketFiles = [];
let filteredFiles = [];

async function loadBuckets() {
    try {
        const data = await window.ipfsKitAPI.getBuckets();
        const bucketsList = document.getElementById('buckets-list');
        bucketsList.innerHTML = '';

        const buckets = data.buckets || data.items || [];
        if (buckets.length > 0) {
            buckets.forEach(bucket => {
                const isActive = selectedBucket && selectedBucket.name === bucket.name ? 'ring-2 ring-blue-500' : '';
                const storageInfo = bucket.storage_used ? `${formatBytes(bucket.storage_used)} used` : 'Size unknown';
                
                const item = `
                    <div class="bucket-item p-3 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${isActive}" 
                         onclick="selectBucket('${bucket.name}')" data-bucket="${bucket.name}">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center">
                                <div class="p-2 rounded-lg bg-gradient-to-r from-blue-400 to-blue-600 mr-3">
                                    <i class="fas fa-folder text-white text-xs"></i>
                                </div>
                                <div>
                                    <h4 class="font-semibold text-sm text-gray-900 dark:text-white">${escapeHtml(bucket.name)}</h4>
                                    <p class="text-xs text-gray-500 dark:text-gray-400">${bucket.backend || 'Unknown'}</p>
                                </div>
                            </div>
                            <div class="text-right">
                                <div class="text-xs text-gray-500 dark:text-gray-400">${storageInfo}</div>
                                <div class="flex items-center mt-1">
                                    ${bucket.vector_search ? '<i class="fas fa-search text-green-500 text-xs mr-1" title="Vector search enabled"></i>' : ''}
                                    ${bucket.knowledge_graph ? '<i class="fas fa-project-diagram text-purple-500 text-xs mr-1" title="Knowledge graph enabled"></i>' : ''}
                                    ${bucket.cache_enabled ? '<i class="fas fa-bolt text-yellow-500 text-xs" title="Cache enabled"></i>' : ''}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                bucketsList.innerHTML += item;
            });
        } else {
            bucketsList.innerHTML = `
                <div class="text-center py-8 text-gray-500 dark:text-gray-400">
                    <i class="fas fa-folder-open text-3xl mb-2"></i>
                    <p class="text-sm">No buckets found</p>
                    <button onclick="showCreateBucketModal()" class="btn-primary text-white px-3 py-1 rounded-lg text-xs mt-2">
                        Create First Bucket
                    </button>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading buckets:', error);
        document.getElementById('buckets-list').innerHTML = '<div class="text-red-500 text-sm p-4 text-center">Failed to load buckets</div>';
    }
}

async function selectBucket(bucketName) {
    try {
        // Update UI to show selected bucket
        document.querySelectorAll('.bucket-item').forEach(item => {
            item.classList.remove('ring-2', 'ring-blue-500');
        });
        document.querySelector(`[data-bucket="${bucketName}"]`)?.classList.add('ring-2', 'ring-blue-500');
        
        // Get bucket details
        const bucketDetails = await window.ipfsKitAPI.getBucketDetails(bucketName);
        selectedBucket = { name: bucketName, ...bucketDetails.bucket };
        
        // Show bucket details panel
        document.getElementById('no-bucket-selected').classList.add('hidden');
        document.getElementById('bucket-details-panel').classList.remove('hidden');
        
        // Update header info
        document.getElementById('selected-bucket-name').textContent = bucketName;
        document.getElementById('selected-bucket-info').textContent = 
            `${selectedBucket.backend || 'Unknown backend'} • ${formatBytes(selectedBucket.storage_used || 0)} used`;
        
        // Load files
        await loadBucketFiles(bucketName);
        
    } catch (error) {
        console.error('Error selecting bucket:', error);
        showNotification('Failed to load bucket details', 'error');
    }
}

async function loadBucketFiles(bucketName) {
    try {
        const response = await window.ipfsKitAPI.getBucketFiles(bucketName);
        bucketFiles = response.files || [];
        filteredFiles = [...bucketFiles];
        
        renderFileList();
    } catch (error) {
        console.error('Error loading bucket files:', error);
        document.getElementById('file-browser').innerHTML = 
            '<div class="p-8 text-center text-red-500"><i class="fas fa-exclamation-triangle text-2xl mb-2"></i><p>Failed to load files</p></div>';
    }
}

function renderFileList() {
    const fileBrowser = document.getElementById('file-browser');
    
    if (filteredFiles.length === 0) {
        fileBrowser.innerHTML = `
            <div class="p-8 text-center text-gray-500 dark:text-gray-400">
                <i class="fas fa-folder-open text-4xl mb-4"></i>
                <p>No files in this bucket</p>
                <p class="text-sm mt-2">Drop files above or click Browse Files to upload</p>
            </div>
        `;
        return;
    }
    
    if (currentFileView === 'list') {
        renderFileListView();
    } else {
        renderFileGridView();
    }
}

function renderFileListView() {
    const fileBrowser = document.getElementById('file-browser');
    const filesHtml = filteredFiles.map(file => {
        const fileIcon = getFileIcon(file.name);
        const fileSize = formatBytes(file.size || 0);
        const lastModified = formatDate(file.last_modified);
        
        return `
            <div class="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 group">
                <div class="flex items-center flex-1">
                    <i class="${fileIcon} text-gray-400 mr-3"></i>
                    <div class="flex-1 min-w-0">
                        <p class="text-sm font-medium text-gray-900 dark:text-white truncate">${escapeHtml(file.name)}</p>
                        <p class="text-xs text-gray-500 dark:text-gray-400">${fileSize} • ${lastModified}</p>
                    </div>
                </div>
                <div class="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onclick="downloadFile('${escapeHtml(file.name)}')" class="p-1 text-gray-400 hover:text-blue-600" title="Download">
                        <i class="fas fa-download text-xs"></i>
                    </button>
                    <button onclick="showFileMenu('${escapeHtml(file.name)}', event)" class="p-1 text-gray-400 hover:text-gray-600" title="More options">
                        <i class="fas fa-ellipsis-v text-xs"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    fileBrowser.innerHTML = `<div class="max-h-96 overflow-y-auto">${filesHtml}</div>`;
}

function renderFileGridView() {
    const fileBrowser = document.getElementById('file-browser');
    const filesHtml = filteredFiles.map(file => {
        const fileIcon = getFileIcon(file.name);
        const fileSize = formatBytes(file.size || 0);
        
        return `
            <div class="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:shadow-md transition-shadow group">
                <div class="text-center">
                    <i class="${fileIcon} text-3xl text-gray-400 mb-2"></i>
                    <p class="text-sm font-medium text-gray-900 dark:text-white truncate" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</p>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">${fileSize}</p>
                </div>
                <div class="flex justify-center space-x-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onclick="downloadFile('${escapeHtml(file.name)}')" class="p-1 text-gray-400 hover:text-blue-600" title="Download">
                        <i class="fas fa-download text-xs"></i>
                    </button>
                    <button onclick="showFileMenu('${escapeHtml(file.name)}', event)" class="p-1 text-gray-400 hover:text-gray-600" title="More options">
                        <i class="fas fa-ellipsis-v text-xs"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    fileBrowser.innerHTML = `<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 p-4">${filesHtml}</div>`;
}

// Helper functions
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    try {
        return new Date(dateString).toLocaleDateString();
    } catch (e) {
        return 'Unknown';
    }
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'pdf': 'fas fa-file-pdf text-red-500',
        'doc': 'fas fa-file-word text-blue-500',
        'docx': 'fas fa-file-word text-blue-500',
        'xls': 'fas fa-file-excel text-green-500',
        'xlsx': 'fas fa-file-excel text-green-500',
        'ppt': 'fas fa-file-powerpoint text-orange-500',
        'pptx': 'fas fa-file-powerpoint text-orange-500',
        'txt': 'fas fa-file-alt',
        'md': 'fas fa-file-alt',
        'json': 'fas fa-file-code text-yellow-500',
        'xml': 'fas fa-file-code text-yellow-500',
        'html': 'fas fa-file-code text-orange-500',
        'css': 'fas fa-file-code text-blue-500',
        'js': 'fas fa-file-code text-yellow-500',
        'py': 'fas fa-file-code text-green-500',
        'zip': 'fas fa-file-archive text-gray-500',
        'tar': 'fas fa-file-archive text-gray-500',
        'gz': 'fas fa-file-archive text-gray-500',
        'jpg': 'fas fa-file-image text-purple-500',
        'jpeg': 'fas fa-file-image text-purple-500',
        'png': 'fas fa-file-image text-purple-500',
        'gif': 'fas fa-file-image text-purple-500',
        'svg': 'fas fa-file-image text-purple-500',
        'mp4': 'fas fa-file-video text-red-500',
        'avi': 'fas fa-file-video text-red-500',
        'mov': 'fas fa-file-video text-red-500',
        'mp3': 'fas fa-file-audio text-green-500',
        'wav': 'fas fa-file-audio text-green-500',
    };
    return iconMap[ext] || 'fas fa-file';
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

async function loadMetrics() {
    // Placeholder for metrics loading logic
    document.getElementById('metrics-content').innerHTML = '<p class="text-center text-gray-500">Detailed metrics coming soon.</p>';
}

async function loadMcpDetails() {
    // Load comprehensive MCP details using the new MCP tools manager
    if (typeof window.loadMcpDetails === 'function') {
        await window.loadMcpDetails();
    } else {
        // Fallback if MCP tools manager isn't loaded
        console.warn('MCP tools manager not loaded, using fallback');
        const mcpContent = document.getElementById('mcp-content');
        if (mcpContent) {
            mcpContent.innerHTML = '<p class="text-center text-gray-500">Loading MCP server details...</p>';
        }
    }
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
