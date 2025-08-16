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
        servicesList.innerHTML = '';
        
        // Convert services object to array format
        const services = data.services || {};
        const servicesArray = Object.entries(services).map(([name, service]) => ({
            name: name.charAt(0).toUpperCase() + name.slice(1), // Capitalize first letter
            status: service.status || 'unknown',
            description: `${name.charAt(0).toUpperCase() + name.slice(1)} service`
        }));
        
        totalBadge.textContent = servicesArray.length;

        if (servicesArray.length > 0) {
            servicesArray.forEach(service => {
                let statusClass = 'bg-gray-500';
                let statusIcon = 'fa-question-circle';
                if (service.status === 'running') {
                    statusClass = 'bg-green-500';
                    statusIcon = 'fa-check-circle';
                } else if (service.status === 'stopped' || service.status === 'error') {
                    statusClass = 'bg-red-500';
                    statusIcon = 'fa-times-circle';
                } else if (service.status === 'configured' || service.status === 'available') {
                    statusClass = 'bg-blue-500';
                    statusIcon = 'fa-cog';
                }

                const item = `
                    <div class="service-item p-6 rounded-xl flex items-center justify-between">
                        <div>
                            <h4 class="text-lg font-semibold text-gray-800">${service.name}</h4>
                            <p class="text-sm text-gray-600">${service.description}</p>
                        </div>
                        <div class="flex items-center space-x-4">
                            <span class="text-sm font-medium text-gray-500">${service.type}</span>
                            <div class="flex items-center px-3 py-1 rounded-full text-white text-sm font-medium ${statusClass}">
                                <i class="fas ${statusIcon} mr-2"></i>
                                <span>${service.status}</span>
                            </div>
                        </div>
                    </div>
                `;
                servicesList.innerHTML += item;
            });
        } else {
            servicesList.innerHTML = '<p class="text-center text-gray-500">No services found.</p>';
        }
    } catch (error) {
        console.error('Error loading services:', error);
        document.getElementById('services-list').innerHTML = '<p class="text-red-500">Failed to load services.</p>';
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
