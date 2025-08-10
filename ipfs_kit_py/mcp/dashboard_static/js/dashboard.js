const API_BASE_URL = 'http://127.0.0.1:8004/api';

// Utility Functions
const formatBytes = (bytes, decimals = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

// Tab Switching
function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    // Show the selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Update active link style
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`.nav-link[onclick="showTab('${tabName}')"]`).classList.add('active');

    // Load data for the selected tab
    if (tabName === 'overview') {
        loadOverviewData();
    } else if (tabName === 'services') {
        loadServices();
    } else if (tabName === 'backends') {
        loadBackends();
    } else if (tabName === 'buckets') {
        loadBuckets();
    } else if (tabName === 'metrics') {
        loadMetrics();
    } else if (tabName === 'config') {
        loadConfig();
    } else if (tabName === 'mcp') {
        loadMcpDetails();
    } else if (tabName === 'pins') {
        loadPins();
    }
    
    // Close mobile sidebar on tab selection
    const sidebar = document.getElementById('sidebar');
    if (sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
        document.getElementById('mobile-overlay').classList.add('hidden');
    }
}

// Data Loading Functions
async function loadOverviewData() {
    try {
        const response = await fetch(`${API_BASE_URL}/system/overview`);
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
        // Get services data for daemon status
        const servicesResponse = await fetch(`${API_BASE_URL}/services`);
        const servicesData = await servicesResponse.json();
        const services = servicesData.services || {};
        const daemonStatus = services.ipfs || { status: 'stopped' };
        
        // Get overview data for peer ID and addresses
        const overviewResponse = await fetch(`${API_BASE_URL}/system/overview`);
        const overviewData = await overviewResponse.json();
        
        const statusDiv = document.getElementById('ipfs-daemon-status');
        
        let statusHtml = '';
        if (daemonStatus && daemonStatus.status === 'running') {
            statusHtml = `
                <div class="text-center p-4 bg-green-50 rounded-lg">
                    <div class="text-4xl text-green-500 mb-2"><i class="fas fa-check-circle"></i></div>
                    <p class="font-semibold text-green-800">Daemon Running</p>
                </div>
                <div class="p-4 bg-gray-50 rounded-lg col-span-2">
                    <p class="text-sm text-gray-600"><strong>Peer ID:</strong> ${overviewData.peer_id || 'N/A'}</p>
                    <p class="text-sm text-gray-600"><strong>Addresses:</strong></p>
                    <ul class="text-xs list-disc list-inside pl-2 mt-1">
                        ${overviewData.addresses ? overviewData.addresses.map(a => `<li>${a}</li>`).join('') : '<li>No addresses found</li>'}
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
                const config = backend.config || {};
                const metadata = backend.metadata || {};
                
                const item = `
                    <div class="card p-6 mb-4 hover:shadow-lg transition-shadow">
                        <div class="flex justify-between items-start mb-4">
                            <div>
                                <h4 class="text-lg font-semibold text-gray-800">${backend.name}</h4>
                                <p class="text-sm text-gray-600">${metadata.description || 'No description'}</p>
                            </div>
                            <div class="flex space-x-2">
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${backend.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                    ${backend.enabled ? 'Enabled' : 'Disabled'}
                                </span>
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                    ${backend.type || 'unknown'}
                                </span>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div>
                                <h5 class="font-semibold text-gray-700 mb-2">Configuration</h5>
                                <div class="text-sm space-y-1">
                                    ${backend.type === 's3' ? `
                                        <div><span class="text-gray-600">Bucket:</span> <span class="font-mono">${config.bucket_name || 'N/A'}</span></div>
                                        <div><span class="text-gray-600">Region:</span> <span class="font-mono">${config.region || 'N/A'}</span></div>
                                        <div><span class="text-gray-600">Access Key:</span> <span class="font-mono">${config.access_key_id ? '***' + config.access_key_id.slice(-4) : 'N/A'}</span></div>
                                    ` : backend.type === 'sshfs' ? `
                                        <div><span class="text-gray-600">Host:</span> <span class="font-mono">${config.hostname || 'N/A'}</span></div>
                                        <div><span class="text-gray-600">User:</span> <span class="font-mono">${config.username || 'N/A'}</span></div>
                                        <div><span class="text-gray-600">Path:</span> <span class="font-mono">${config.remote_path || 'N/A'}</span></div>
                                    ` : backend.type === 'github' ? `
                                        <div><span class="text-gray-600">Repository:</span> <span class="font-mono">${config.repo_url || 'N/A'}</span></div>
                                        <div><span class="text-gray-600">Branch:</span> <span class="font-mono">${config.branch || 'main'}</span></div>
                                    ` : backend.type === 'ftp' ? `
                                        <div><span class="text-gray-600">Host:</span> <span class="font-mono">${config.hostname || 'N/A'}</span></div>
                                        <div><span class="text-gray-600">Port:</span> <span class="font-mono">${config.port || '21'}</span></div>
                                        <div><span class="text-gray-600">User:</span> <span class="font-mono">${config.username || 'N/A'}</span></div>
                                    ` : `
                                        <div class="text-gray-500">Configuration details available in config file</div>
                                    `}
                                </div>
                            </div>
                            <div>
                                <h5 class="font-semibold text-gray-700 mb-2">Status & Info</h5>
                                <div class="text-sm space-y-1">
                                    <div><span class="text-gray-600">Status:</span> <span class="font-medium">${backend.status || 'configured'}</span></div>
                                    <div><span class="text-gray-600">Version:</span> <span class="font-mono">${metadata.version || 'N/A'}</span></div>
                                    <div><span class="text-gray-600">Created:</span> <span class="text-gray-500">${backend.created_at ? new Date(backend.created_at).toLocaleDateString() : 'N/A'}</span></div>
                                    <div><span class="text-gray-600">Modified:</span> <span class="text-gray-500">${backend.last_modified ? new Date(backend.last_modified).toLocaleDateString() : 'N/A'}</span></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="border-t pt-4 flex justify-between items-center">
                            <div class="text-xs text-gray-500">
                                ${backend.file ? `Config: ${backend.file.split('/').pop()}` : 'No config file'}
                            </div>
                            <div class="flex space-x-2">
                                <button onclick="editBackend('${backend.name}')" class="text-blue-500 hover:text-blue-700 text-sm">
                                    <i class="fas fa-edit mr-1"></i> Edit
                                </button>
                                <button onclick="viewBackendDetails('${backend.name}')" class="text-green-500 hover:text-green-700 text-sm">
                                    <i class="fas fa-eye mr-1"></i> Details
                                </button>
                                <button onclick="testBackend('${backend.name}')" class="text-purple-500 hover:text-purple-700 text-sm">
                                    <i class="fas fa-plug mr-1"></i> Test
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                backendsList.innerHTML += item;
            });
        } else {
            backendsList.innerHTML = '<p class="text-center text-gray-500">No backends configured. Create a backend configuration to get started.</p>';
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
                const backendBindings = bucket.backend_bindings || [];
                const access = bucket.access || {};
                const features = bucket.features || {};
                
                const item = `
                    <div class="card p-6 mb-4 hover:shadow-lg transition-shadow">
                        <div class="flex justify-between items-start mb-4">
                            <div>
                                <h4 class="text-lg font-semibold text-gray-800">${bucket.name}</h4>
                                <p class="text-sm text-gray-600">${bucket.description || 'No description'}</p>
                            </div>
                            <div class="flex space-x-2">
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bucket.status === 'configured' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}">
                                    ${bucket.status || 'unknown'}
                                </span>
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                    ${bucket.type || 'general'}
                                </span>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                            <div class="text-center p-3 bg-gray-50 rounded-lg">
                                <div class="text-2xl font-bold text-blue-600">${bucket.files_count || 0}</div>
                                <div class="text-sm text-gray-600">Files</div>
                            </div>
                            <div class="text-center p-3 bg-gray-50 rounded-lg">
                                <div class="text-2xl font-bold text-green-600">${formatBytes(bucket.size_bytes || 0)}</div>
                                <div class="text-sm text-gray-600">Size</div>
                            </div>
                            <div class="text-center p-3 bg-gray-50 rounded-lg">
                                <div class="text-2xl font-bold text-purple-600">${backendBindings.length}</div>
                                <div class="text-sm text-gray-600">Backends</div>
                            </div>
                        </div>
                        
                        <div class="border-t pt-4">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                <div>
                                    <h5 class="font-semibold text-gray-700 mb-2">Access Settings</h5>
                                    <ul class="space-y-1 text-gray-600">
                                        <li><i class="fas fa-${access.public_read ? 'check text-green-500' : 'times text-red-500'} w-4"></i> Public Read</li>
                                        <li><i class="fas fa-${access.web_interface ? 'check text-green-500' : 'times text-red-500'} w-4"></i> Web Interface</li>
                                        <li><i class="fas fa-${access.api_access ? 'check text-green-500' : 'times text-red-500'} w-4"></i> API Access</li>
                                        <li><i class="fas fa-${access.encryption_at_rest ? 'check text-green-500' : 'times text-red-500'} w-4"></i> Encryption at Rest</li>
                                    </ul>
                                </div>
                                <div>
                                    <h5 class="font-semibold text-gray-700 mb-2">Features</h5>
                                    <ul class="space-y-1 text-gray-600">
                                        <li><i class="fas fa-${features.search_enabled ? 'check text-green-500' : 'times text-red-500'} w-4"></i> Search</li>
                                        <li><i class="fas fa-${features.versioning_enabled ? 'check text-green-500' : 'times text-red-500'} w-4"></i> Versioning</li>
                                        <li><i class="fas fa-${features.metadata_extraction ? 'check text-green-500' : 'times text-red-500'} w-4"></i> Metadata Extraction</li>
                                        <li><i class="fas fa-${features.auto_indexing ? 'check text-green-500' : 'times text-red-500'} w-4"></i> Auto Indexing</li>
                                    </ul>
                                </div>
                            </div>
                            
                            ${backendBindings.length > 0 ? `
                                <div class="mt-4">
                                    <h5 class="font-semibold text-gray-700 mb-2">Backend Bindings</h5>
                                    <div class="flex flex-wrap gap-2">
                                        ${backendBindings.map(binding => `
                                            <span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-purple-100 text-purple-800">
                                                ${binding}
                                            </span>
                                        `).join('')}
                                    </div>
                                </div>
                            ` : ''}
                            
                            <div class="mt-4 flex justify-between items-center">
                                <div class="text-xs text-gray-500">
                                    ${bucket.file ? `Config: ${bucket.file.split('/').pop()}` : `Backend: ${bucket.backend || 'Unknown'}`}
                                </div>
                                <div class="flex space-x-2">
                                    <button onclick="editBucket('${bucket.name}')" class="text-blue-500 hover:text-blue-700 text-sm">
                                        <i class="fas fa-edit mr-1"></i> Edit
                                    </button>
                                    <button onclick="viewBucketDetails('${bucket.name}')" class="text-green-500 hover:text-green-700 text-sm">
                                        <i class="fas fa-eye mr-1"></i> Details
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                bucketsList.innerHTML += item;
            });
        } else {
            bucketsList.innerHTML = '<p class="text-center text-gray-500">No buckets found. Create a bucket configuration to get started.</p>';
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

async function loadConfig() {
    // Placeholder for config loading logic
    document.getElementById('config-content').innerHTML = '<p class="text-center text-gray-500">Configuration management coming soon.</p>';
}

async function loadMcpDetails() {
    // Placeholder for MCP details loading logic
    document.getElementById('mcp-content').innerHTML = '<p class="text-center text-gray-500">MCP server details coming soon.</p>';
}

// Pins Tab
async function loadPins() {
    try {
        const response = await fetch('/api/pins');
        const data = await response.json();
        const pinsList = document.getElementById('pins-list');
        pinsList.innerHTML = ''; // Clear existing list

        if (data.pins && data.pins.length > 0) {
            data.pins.forEach(pin => {
                const row = `
                    <tr class="hover:bg-gray-50">
                        <td class="p-4 text-sm text-gray-800 font-mono">${pin.cid}</td>
                        <td class="p-4 text-sm text-gray-600">${pin.name || ''}</td>
                        <td class="p-4 text-right">
                            <button onclick="removePin('${pin.cid}')" class="text-red-500 hover:text-red-700 font-semibold">
                                <i class="fas fa-trash-alt mr-1"></i> Remove
                            </button>
                        </td>
                    </tr>
                `;
                pinsList.innerHTML += row;
            });
        } else {
            pinsList.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-gray-500">No pins found.</td></tr>';
        }
    } catch (error) {
        console.error('Error loading pins:', error);
        const pinsList = document.getElementById('pins-list');
        pinsList.innerHTML = '<tr><td colspan="3" class="p-8 text-center text-red-500">Failed to load pins.</td></tr>';
    }
}

async function addPin() {
    const cid = document.getElementById('pin-cid-input').value;
    const name = document.getElementById('pin-name-input').value;

    if (!cid) {
        alert('Please enter a CID.');
        return;
    }

    try {
        const response = await fetch('/api/pins', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cid, name }),
        });
        const result = await response.json();
        if (result.success) {
            document.getElementById('pin-cid-input').value = '';
            document.getElementById('pin-name-input').value = '';
            loadPins(); // Refresh the list
        } else {
            alert(`Error adding pin: ${result.error}`);
        }
    } catch (error) {
        console.error('Error adding pin:', error);
        alert('An unexpected error occurred while adding the pin.');
    }
}

async function removePin(cid) {
    if (!confirm(`Are you sure you want to remove pin ${cid}?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/pins/${cid}`, {
            method: 'DELETE',
        });
        const result = await response.json();
        if (result.success) {
            loadPins(); // Refresh the list
        } else {
            alert(`Error removing pin: ${result.error}`);
        }
    } catch (error) {
        console.error('Error removing pin:', error);
        alert('An unexpected error occurred while removing the pin.');
    }
}

// Global Refresh and Timers
function refreshData() {
    const activeTab = document.querySelector('.nav-link.active').getAttribute('onclick').replace("showTab('", "").replace("')", "");
    showTab(activeTab);
}

// Bucket Management Functions
function editBucket(bucketName) {
    alert(`Edit bucket functionality for "${bucketName}" coming soon!`);
    // TODO: Implement bucket editing modal/form
}

function viewBucketDetails(bucketName) {
    alert(`Detailed view for bucket "${bucketName}" coming soon!`);
    // TODO: Implement detailed bucket view modal
}

function createNewBucket() {
    alert("Create new bucket functionality coming soon!");
    // TODO: Implement bucket creation modal/form
}

// Backend Management Functions  
function editBackend(backendName) {
    alert(`Edit backend functionality for "${backendName}" coming soon!`);
    // TODO: Implement backend editing modal/form
}

function viewBackendDetails(backendName) {
    alert(`Detailed view for backend "${backendName}" coming soon!`);
    // TODO: Implement detailed backend view modal
}

function testBackend(backendName) {
    alert(`Test backend connection for "${backendName}" coming soon!`);
    // TODO: Implement backend connectivity test
}

function createNewBackend() {
    alert("Create new backend functionality coming soon!");
    // TODO: Implement backend creation modal/form
}

function updateTime() {
    const now = new Date();
    document.getElementById('current-time').textContent = now.toLocaleTimeString();
}

// Mobile Menu
document.getElementById('mobile-menu-btn').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('mobile-overlay').classList.toggle('hidden');
});
document.getElementById('mobile-overlay').addEventListener('click', () => {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('mobile-overlay').classList.add('hidden');
});

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    showTab('overview');
    setInterval(refreshData, 5000); // Auto-refresh data every 5 seconds
    setInterval(updateTime, 1000);
});
