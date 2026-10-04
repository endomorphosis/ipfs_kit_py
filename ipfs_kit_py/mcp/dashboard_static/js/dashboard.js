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
        const [statusRes, metricsRes] = await Promise.all([
            fetch(`${API_BASE_URL}/mcp/status`),
            fetch(`${API_BASE_URL}/metrics/system`)
        ]);
        const statusJson = await statusRes.json();
        const metricsJson = await metricsRes.json();
        const status = statusJson && (statusJson.data || statusJson);
        const counts = (status && status.counts) || {};
        const memory = metricsJson.memory || {};
        const disk = metricsJson.disk || {};
        const cpuPercent = typeof metricsJson.cpu_percent === 'number' ? metricsJson.cpu_percent : 0;

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
        const servicesResponse = await fetch(`${API_BASE_URL}/services`);
        const servicesData = await servicesResponse.json();
        const services = servicesData.services || {};
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
                    <p class="text-sm text-gray-600"><strong>Binary:</strong> ${ipfs.bin || 'N/A'}</p>
                    <p class="text-sm text-gray-600"><strong>API Port:</strong> ${ipfs.api_port_open ? 'open' : 'closed'}</p>
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
        const response = await fetch(`${API_BASE_URL}/metrics/network`);
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
        // Try to load from comprehensive service manager first
        let response;
        let data;
        
        try {
            response = await fetch('/api/services/comprehensive');
            data = await response.json();
        } catch (error) {
            // Fallback to basic services API
            console.warn('Comprehensive services API not available, using fallback');
            response = await fetch('/api/services');
            data = await response.json();
            data = convertLegacyServicesData(data);
        }
        
        const servicesList = document.getElementById('services-list');
        servicesList.innerHTML = '';
        
        const services = data.services || {};
        updateServicesStatusCounts(services);
        
        if (Object.keys(services).length > 0) {
            renderComprehensiveServices(services);
        } else {
            servicesList.innerHTML = `
                <div class="text-center py-12 col-span-full">
                    <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full mb-4">
                        <i class="fas fa-exclamation-triangle text-2xl text-gray-500"></i>
                    </div>
                    <p class="text-gray-500 font-medium">No services available</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Error loading services:', error);
        document.getElementById('services-list').innerHTML = `
            <div class="text-center py-12 col-span-full">
                <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-red-100 to-red-200 rounded-full mb-4">
                    <i class="fas fa-exclamation-triangle text-2xl text-red-500"></i>
                </div>
                <p class="text-red-500 font-medium">Error loading services</p>
                <p class="text-gray-500 text-sm mt-2">${error.message}</p>
            </div>
        `;
    }
}

function convertLegacyServicesData(legacyData) {
    // Convert legacy services data to comprehensive format
    const services = legacyData.services || {};
    const converted = {};
    
    for (const [name, service] of Object.entries(services)) {
        converted[name] = {
            name: name.charAt(0).toUpperCase() + name.slice(1),
            type: 'daemon',
            description: `${name.charAt(0).toUpperCase() + name.slice(1)} service`,
            status: service.status || 'unknown',
            enabled: service.status === 'running',
            requires_credentials: false,
            actions: ['start', 'stop', 'configure']
        };
    }
    
    return { services: converted };
}

function updateServicesStatusCounts(services) {
    const counts = {
        running: 0,
        stopped: 0,
        not_enabled: 0,
        not_configured: 0,
        configured: 0,
        error: 0
    };
    
    for (const service of Object.values(services)) {
        const status = service.status || 'unknown';
        if (counts.hasOwnProperty(status)) {
            counts[status]++;
        } else if (status === 'running') {
            counts.running++;
        } else if (status === 'stopped') {
            counts.stopped++;
        } else {
            counts.error++;
        }
    }
    
    document.getElementById('services-running-count').textContent = counts.running;
    document.getElementById('services-stopped-count').textContent = counts.stopped;
    document.getElementById('services-not-enabled-count').textContent = counts.not_enabled;
    document.getElementById('services-not-configured-count').textContent = counts.not_configured;
    document.getElementById('services-configured-count').textContent = counts.configured;
    document.getElementById('services-error-count').textContent = counts.error;
}

function renderComprehensiveServices(services) {
    const servicesList = document.getElementById('services-list');
    servicesList.innerHTML = '';
    
    for (const [serviceId, service] of Object.entries(services)) {
        const serviceCard = createServiceCard(serviceId, service);
        servicesList.appendChild(serviceCard);
    }
}

function createServiceCard(serviceId, service) {
    const card = document.createElement('div');
    card.className = `service-card bg-white rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 p-6 border-l-4 ${getServiceBorderColor(service.status)} service-type-${service.type}`;
    
    const statusInfo = getServiceStatusInfo(service.status);
    const typeIcon = getServiceTypeIcon(service.type);
    
    card.innerHTML = `
        <div class="flex items-start justify-between mb-4">
            <div class="flex items-center">
                <div class="p-2 rounded-lg ${getServiceIconBg(service.type)} mr-3">
                    <i class="fas ${typeIcon} text-white"></i>
                </div>
                <div>
                    <h4 class="text-lg font-bold text-gray-800">${service.name}</h4>
                    <p class="text-sm text-gray-500">${getServiceCategoryLabel(service.type)}</p>
                </div>
            </div>
            <div class="flex items-center px-3 py-1 rounded-full text-xs font-semibold ${statusInfo.class}">
                ${statusInfo.icon} ${statusInfo.label}
            </div>
        </div>
        
        <p class="text-gray-600 text-sm mb-4">${service.description}</p>
        
        <div class="flex flex-wrap gap-2">
            ${createServiceActionButtons(serviceId, service)}
        </div>
        
        ${service.requires_credentials ? '<div class="mt-3 text-xs text-amber-600 flex items-center"><i class="fas fa-key mr-1"></i> Requires credentials</div>' : ''}
    `;
    
    return card;
}

function getServiceStatusInfo(status) {
    const statusMap = {
        'running': { icon: '🟢', label: 'Running', class: 'bg-green-100 text-green-800' },
        'stopped': { icon: '🔴', label: 'Stopped', class: 'bg-red-100 text-red-800' },
        'not_enabled': { icon: '⚫', label: 'Not Enabled', class: 'bg-gray-100 text-gray-800' },
        'not_configured': { icon: '🟡', label: 'Not Configured', class: 'bg-yellow-100 text-yellow-800' },
        'configured': { icon: '🔵', label: 'Configured', class: 'bg-blue-100 text-blue-800' },
        'error': { icon: '🟣', label: 'Error', class: 'bg-purple-100 text-purple-800' }
    };
    
    return statusMap[status] || { icon: '❓', label: 'Unknown', class: 'bg-gray-100 text-gray-600' };
}

function getServiceTypeIcon(type) {
    const typeIcons = {
        'daemon': 'fa-cogs',
        'storage': 'fa-database',
        'network': 'fa-network-wired',
        'index': 'fa-search',
        'credential': 'fa-key'
    };
    return typeIcons[type] || 'fa-question-circle';
}

function getServiceIconBg(type) {
    const bgColors = {
        'daemon': 'bg-gradient-to-r from-blue-500 to-blue-600',
        'storage': 'bg-gradient-to-r from-green-500 to-green-600',
        'network': 'bg-gradient-to-r from-purple-500 to-purple-600',
        'index': 'bg-gradient-to-r from-yellow-500 to-yellow-600',
        'credential': 'bg-gradient-to-r from-red-500 to-red-600'
    };
    return bgColors[type] || 'bg-gradient-to-r from-gray-500 to-gray-600';
}

function getServiceBorderColor(status) {
    const borderColors = {
        'running': 'border-green-500',
        'stopped': 'border-red-500',
        'not_enabled': 'border-gray-400',
        'not_configured': 'border-yellow-500',
        'configured': 'border-blue-500',
        'error': 'border-purple-500'
    };
    return borderColors[status] || 'border-gray-300';
}

function getServiceCategoryLabel(type) {
    const labels = {
        'daemon': '🛠️ Daemon Service',
        'storage': '📦 Storage Backend',
        'network': '🌐 Network Service',
        'index': '🔍 Index Service',
        'credential': '🔑 Credential Service'
    };
    return labels[type] || '❓ Unknown Service';
}

function createServiceActionButtons(serviceId, service) {
    const status = service.status || 'unknown';
    const actions = service.actions || [];
    let buttons = '';
    
    // Determine available actions based on status
    if (status === 'running') {
        if (actions.includes('stop')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'stop')" class="px-3 py-1 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg text-xs font-medium transition">Stop</button>`;
        }
        if (actions.includes('restart')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'restart')" class="px-3 py-1 bg-yellow-100 hover:bg-yellow-200 text-yellow-700 rounded-lg text-xs font-medium transition">Restart</button>`;
        }
        if (actions.includes('health_check')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'health_check')" class="px-3 py-1 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg text-xs font-medium transition">Health Check</button>`;
        }
        if (actions.includes('view_logs')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'view_logs')" class="px-3 py-1 bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg text-xs font-medium transition">View Logs</button>`;
        }
        if (actions.includes('disable')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'disable')" class="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-xs font-medium transition">Disable</button>`;
        }
    } else if (status === 'stopped') {
        if (actions.includes('start')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'start')" class="px-3 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg text-xs font-medium transition">Start</button>`;
        }
        if (actions.includes('disable')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'disable')" class="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-xs font-medium transition">Disable</button>`;
        }
        if (actions.includes('configure')) {
            buttons += `<button onclick="configureService('${serviceId}')" class="px-3 py-1 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg text-xs font-medium transition">Configure</button>`;
        }
    } else if (status === 'not_enabled') {
        if (actions.includes('enable')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'enable')" class="px-3 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg text-xs font-medium transition">Enable</button>`;
        }
    } else if (status === 'not_configured') {
        if (actions.includes('configure')) {
            buttons += `<button onclick="configureService('${serviceId}')" class="px-3 py-1 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg text-xs font-medium transition">Configure</button>`;
        }
        if (actions.includes('enable')) {
            buttons += `<button onclick="performServiceAction('${serviceId}', 'enable')" class="px-3 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg text-xs font-medium transition">Enable</button>`;
        }
    }
    
    return buttons;
}

// Service filtering
function filterServices(category) {
    const cards = document.querySelectorAll('.service-card');
    const buttons = document.querySelectorAll('.service-filter-btn');
    
    // Update active button
    buttons.forEach(btn => btn.classList.remove('active', 'bg-blue-500', 'text-white'));
    buttons.forEach(btn => btn.classList.add('bg-gray-200', 'text-gray-700'));
    
    const activeBtn = document.querySelector(`button[onclick="filterServices('${category}')"]`);
    activeBtn.classList.remove('bg-gray-200', 'text-gray-700');
    activeBtn.classList.add('active', 'bg-blue-500', 'text-white');
    
    // Filter cards
    cards.forEach(card => {
        if (category === 'all') {
            card.style.display = 'block';
        } else {
            const hasCategory = card.classList.contains(`service-type-${category}`);
            card.style.display = hasCategory ? 'block' : 'none';
        }
    });
}

// Service actions
async function performServiceAction(serviceId, action) {
    try {
        const response = await fetch(`/api/services/${serviceId}/${action}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(`Service ${action} completed successfully`, 'success');
            // Reload services to update status
            setTimeout(() => loadServices(), 1000);
        } else {
            showNotification(`Failed to ${action} service: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error(`Error performing ${action} on ${serviceId}:`, error);
        showNotification(`Error performing ${action}: ${error.message}`, 'error');
    }
}

function configureService(serviceId) {
    // Open configuration modal
    const modal = document.getElementById('service-config-modal');
    const title = document.getElementById('modal-title');
    const content = document.getElementById('modal-content');
    
    // Find the service data
    // This would typically come from the loaded services data
    title.textContent = `Configure ${serviceId.charAt(0).toUpperCase() + serviceId.slice(1)}`;
    
    // Generate configuration form based on service type
    content.innerHTML = generateServiceConfigForm(serviceId);
    
    // Show modal
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modal.querySelector('.transform').classList.remove('scale-95');
    }, 10);
}

function generateServiceConfigForm(serviceId) {
    // Service-specific configuration forms
    const configForms = {
        's3': `
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Access Key</label>
                    <input type="text" id="s3-access-key" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="AWS Access Key">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Secret Key</label>
                    <input type="password" id="s3-secret-key" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="AWS Secret Key">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Region</label>
                    <input type="text" id="s3-region" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="us-east-1">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Bucket Name</label>
                    <input type="text" id="s3-bucket" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="your-bucket-name">
                </div>
            </div>
        `,
        'huggingface': `
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">API Token</label>
                    <input type="password" id="hf-api-token" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="hf_your_token_here">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Username</label>
                    <input type="text" id="hf-username" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="your-username">
                </div>
            </div>
        `,
        'github': `
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Access Token</label>
                    <input type="password" id="github-token" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="github_pat_your_token">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Username</label>
                    <input type="text" id="github-username" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="your-username">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Repository</label>
                    <input type="text" id="github-repo" class="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="repository-name">
                </div>
            </div>
        `
    };
    
    return configForms[serviceId] || `
        <div class="space-y-4">
            <div class="text-center py-8">
                <i class="fas fa-cog text-4xl text-gray-400 mb-4"></i>
                <p class="text-gray-600">Configuration form for ${serviceId} will be available soon.</p>
            </div>
        </div>
    `;
}

function closeServiceModal() {
    const modal = document.getElementById('service-config-modal');
    modal.classList.add('opacity-0');
    modal.querySelector('.transform').classList.add('scale-95');
    setTimeout(() => {
        modal.classList.add('hidden');
    }, 300);
}

function saveServiceConfig() {
    // This would save the configuration
    showNotification('Service configuration saved successfully', 'success');
    closeServiceModal();
    // Reload services
    setTimeout(() => loadServices(), 500);
}

function showNotification(message, type = 'info') {
    // Simple notification system
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-6 py-4 rounded-lg shadow-lg z-50 ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    notification.innerHTML = `
        <div class="flex items-center">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-triangle' : 'fa-info-circle'} mr-2"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}
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
