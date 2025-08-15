// Data Loading Functions
async function loadOverviewData() {
    try {
        // Fetch new sources in parallel
        const [statusRes, metricsRes] = await Promise.all([
            fetch('/api/mcp/status'),
            fetch('/api/metrics/system')
        ]);
        const statusJson = await statusRes.json();
        const metricsJson = await metricsRes.json();
        const status = statusJson && (statusJson.data || statusJson);
        const counts = (status && status.counts) || {};
        const memory = metricsJson.memory || {};
        const disk = metricsJson.disk || {};
        const cpuPercent = typeof metricsJson.cpu_percent === 'number' ? metricsJson.cpu_percent : 0;

        // Update main metrics
        document.getElementById('services-count').textContent = counts.services_active ?? '0';
        document.getElementById('backends-count').textContent = counts.backends ?? '0';
        document.getElementById('buckets-count').textContent = counts.buckets ?? '0';

        // Update system performance
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

        // Update sidebar stats
        document.getElementById('sidebar-backends-count').textContent = counts.backends ?? '0';
        document.getElementById('sidebar-cpu-percent').textContent = `${Number(cpuPercent || 0).toFixed(0)}%`;
        document.getElementById('sidebar-cpu-bar').style.width = `${cpuPercent}%`;
        if (typeof memory.percent === 'number') {
            document.getElementById('sidebar-memory-percent').textContent = `${memory.percent.toFixed(0)}%`;
            document.getElementById('sidebar-memory-bar').style.width = `${memory.percent}%`;
        }

        // Load IPFS daemon status and network
        loadIpfsDaemonStatus();
        loadNetworkActivity();

    } catch (error) {
        console.error('Error loading overview data:', error);
    }
}

async function loadIpfsDaemonStatus() {
    try {
        const response = await fetch('/api/services');
        const data = await response.json();
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
        const response = await fetch('/api/metrics/network');
        const data = await response.json();
        const points = Array.isArray(data.points) ? data.points : [];
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
        const response = await fetch('/api/state/backends');
        const data = await response.json();
        const backendsList = document.getElementById('backends-list');
        backendsList.innerHTML = '';

        const items = (data.items || []);
        if (items.length > 0) {
            items.forEach(backend => {
                const item = `
                    <div class="card p-6 mb-4">
                        <h4 class="text-lg font-semibold">${backend.name}</h4>
                        <pre class="text-xs bg-gray-900 text-gray-100 p-2 rounded">${JSON.stringify(backend.config || {}, null, 2)}</pre>
                    </div>
                `;
                backendsList.innerHTML += item;
            });
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
        const response = await fetch('/api/state/buckets');
        const data = await response.json();
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
