// Data Loading Functions
async function loadOverviewData() {
    try {
        const response = await fetch('/api/system/overview');
        const data = await response.json();

        // Update main metrics
        document.getElementById('services-count').textContent = data.services;
        document.getElementById('backends-count').textContent = data.backends;
        document.getElementById('buckets-count').textContent = data.buckets;

        // Update system performance
        const system = data.system;
        document.getElementById('cpu-percent').textContent = `${system.cpu.usage.toFixed(1)}%`;
        document.getElementById('cpu-bar').style.width = `${system.cpu.usage}%`;
        document.getElementById('memory-percent').textContent = `${system.memory.percent.toFixed(1)}%`;
        document.getElementById('memory-bar').style.width = `${system.memory.percent}%`;
        document.getElementById('memory-used').textContent = formatBytes(system.memory.used);
        document.getElementById('memory-total').textContent = formatBytes(system.memory.total);
        document.getElementById('disk-percent').textContent = `${system.disk.percent.toFixed(1)}%`;
        document.getElementById('disk-bar').style.width = `${system.disk.percent}%`;
        document.getElementById('disk-used').textContent = formatBytes(system.disk.used);
        document.getElementById('disk-total').textContent = formatBytes(system.disk.total);

        // Update sidebar stats
        document.getElementById('sidebar-backends-count').textContent = data.backends;
        document.getElementById('sidebar-cpu-percent').textContent = `${system.cpu.usage.toFixed(0)}%`;
        document.getElementById('sidebar-cpu-bar').style.width = `${system.cpu.usage}%`;
        document.getElementById('sidebar-memory-percent').textContent = `${system.memory.percent.toFixed(0)}%`;
        document.getElementById('sidebar-memory-bar').style.width = `${system.memory.percent}%`;

        // Load IPFS daemon status
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
        const daemonStatus = services.ipfs || { status: 'stopped' };
        const statusDiv = document.getElementById('ipfs-daemon-status');
        
        let statusHtml = '';
        if (daemonStatus && daemonStatus.status === 'running') {
            statusHtml = `
                <div class="text-center p-4 bg-green-50 rounded-lg">
                    <div class="text-4xl text-green-500 mb-2"><i class="fas fa-check-circle"></i></div>
                    <p class="font-semibold text-green-800">Daemon Running</p>
                </div>
                <div class="p-4 bg-gray-50 rounded-lg col-span-2">
                    <p class="text-sm text-gray-600 break-all"><strong>Peer ID:</strong> ${daemonStatus.peer_id || 'N/A'}</p>
                    <p class="text-sm text-gray-600 mt-2"><strong>Addresses:</strong></p>
                    <ul class="text-xs list-disc list-inside pl-2 mt-1">
                        ${daemonStatus.addresses && daemonStatus.addresses.length > 0 ? daemonStatus.addresses.map(a => `<li class="break-all">${a}</li>`).join('') : '<li>No addresses found</li>'}
                    </ul>
                </div>
            `;
            document.getElementById('sidebar-ipfs-status').textContent = 'Running';
            document.getElementById('sidebar-ipfs-dot').className = 'status-dot running';
        } else {
            statusHtml = `
                <div class="text-center p-4 bg-red-50 rounded-lg col-span-3">
                    <div class="text-4xl text-red-500 mb-2"><i class="fas fa-times-circle"></i></div>
                    <p class="font-semibold text-red-800">Daemon Stopped</p>
                    <p class="text-sm text-gray-600 mt-2">${daemonStatus ? daemonStatus.error : 'Could not fetch status.'}</p>
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
        const response = await fetch('/api/system/metrics');
        const data = await response.json();
        const network = data.network;
        const contentDiv = document.getElementById('network-activity-content');
        contentDiv.innerHTML = `
            <div class="flex items-center">
                <div class="p-3 rounded-lg bg-gradient-to-r from-blue-400 to-cyan-500 mr-4">
                    <i class="fas fa-arrow-up text-white"></i>
                </div>
                <div>
                    <p class="text-gray-600 text-sm">Data Sent</p>
                    <p class="font-bold text-xl">${formatBytes(network.sent)}</p>
                </div>
            </div>
            <div class="flex items-center">
                <div class="p-3 rounded-lg bg-gradient-to-r from-green-400 to-emerald-500 mr-4">
                    <i class="fas fa-arrow-down text-white"></i>
                </div>
                <div>
                    <p class="text-gray-600 text-sm">Data Received</p>
                    <p class="font-bold text-xl">${formatBytes(network.recv)}</p>
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
        const response = await fetch('/api/backends');
        const data = await response.json();
        const backendsList = document.getElementById('backends-list');
        backendsList.innerHTML = '';

        if (data.backends && data.backends.length > 0) {
            data.backends.forEach(backend => {
                const item = `
                    <div class="card p-6 mb-4">
                        <h4 class="text-lg font-semibold">${backend.name}</h4>
                        <p>Type: ${backend.type}</p>
                        <p>Status: ${backend.status}</p>
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
        const response = await fetch('/api/buckets');
        const data = await response.json();
        const bucketsList = document.getElementById('buckets-list');
        bucketsList.innerHTML = '';

        if (data.buckets && data.buckets.length > 0) {
            data.buckets.forEach(bucket => {
                const item = `
                    <div class="card p-6 mb-4">
                        <h4 class="text-lg font-semibold">${bucket.name}</h4>
                        <p>Backend: ${bucket.backend}</p>
                        <p>Files: ${bucket.files_count}</p>
                        <p>Size: ${formatBytes(bucket.size_bytes)}</p>
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
