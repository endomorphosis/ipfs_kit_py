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
        
        const services = data.services || [];
        const summary = data.summary || {};
        
        totalBadge.textContent = services.length;

        if (services.length > 0) {
            services.forEach(service => {
                let statusClass = 'bg-gray-500';
                let statusIcon = 'fa-question-circle';
                
                switch(service.status) {
                    case 'running':
                        statusClass = 'bg-green-500';
                        statusIcon = 'fa-check-circle';
                        break;
                    case 'stopped':
                        statusClass = 'bg-red-500';
                        statusIcon = 'fa-stop-circle';
                        break;
                    case 'not_enabled':
                        statusClass = 'bg-gray-500';
                        statusIcon = 'fa-power-off';
                        break;
                    case 'not_configured':
                        statusClass = 'bg-orange-500';
                        statusIcon = 'fa-cog';
                        break;
                    case 'configured':
                        statusClass = 'bg-blue-500';
                        statusIcon = 'fa-check';
                        break;
                    case 'error':
                        statusClass = 'bg-red-600';
                        statusIcon = 'fa-exclamation-triangle';
                        break;
                    default:
                        statusClass = 'bg-gray-500';
                        statusIcon = 'fa-question-circle';
                }

                const actions = service.actions || [];
                const actionsHtml = actions.map(action => {
                    let buttonClass = 'bg-blue-500 hover:bg-blue-600';
                    let buttonIcon = 'fa-play';
                    
                    switch(action) {
                        case 'start':
                            buttonClass = 'bg-green-500 hover:bg-green-600';
                            buttonIcon = 'fa-play';
                            break;
                        case 'stop':
                            buttonClass = 'bg-red-500 hover:bg-red-600';
                            buttonIcon = 'fa-stop';
                            break;
                        case 'restart':
                            buttonClass = 'bg-yellow-500 hover:bg-yellow-600';
                            buttonIcon = 'fa-redo';
                            break;
                        case 'configure':
                            buttonClass = 'bg-blue-500 hover:bg-blue-600';
                            buttonIcon = 'fa-cog';
                            break;
                        case 'enable':
                            buttonClass = 'bg-purple-500 hover:bg-purple-600';
                            buttonIcon = 'fa-power-off';
                            break;
                        case 'disable':
                            buttonClass = 'bg-gray-500 hover:bg-gray-600';
                            buttonIcon = 'fa-power-off';
                            break;
                        case 'health_check':
                            buttonClass = 'bg-cyan-500 hover:bg-cyan-600';
                            buttonIcon = 'fa-heart';
                            break;
                        case 'view_logs':
                            buttonClass = 'bg-indigo-500 hover:bg-indigo-600';
                            buttonIcon = 'fa-file-alt';
                            break;
                    }
                    
                    return `<button onclick="performServiceAction('${service.id}', '${action}')" class="px-3 py-1 rounded text-xs text-white font-medium ${buttonClass} transition-colors" title="${action.replace('_', ' ')}">
                        <i class="fas ${buttonIcon} mr-1"></i>${action.replace('_', ' ')}
                    </button>`;
                }).join(' ');

                const credentialsInfo = service.requires_credentials ? 
                    `<span class="text-xs text-orange-600"><i class="fas fa-key mr-1"></i>Requires credentials</span>` : '';

                const item = `
                    <div class="service-item p-6 rounded-xl border hover:shadow-lg transition-all">
                        <div class="flex items-center justify-between mb-4">
                            <div class="flex-grow">
                                <h4 class="text-lg font-semibold text-gray-800 mb-1">${service.name}</h4>
                                <p class="text-sm text-gray-600 mb-2">${service.description}</p>
                                <div class="flex items-center space-x-4 text-xs text-gray-500">
                                    <span class="px-2 py-1 bg-gray-100 rounded">${service.type}</span>
                                    ${service.port ? `<span>Port: ${service.port}</span>` : ''}
                                    ${credentialsInfo}
                                </div>
                            </div>
                            <div class="flex items-center space-x-3">
                                <div class="flex items-center px-3 py-2 rounded-full text-white text-sm font-medium ${statusClass}">
                                    <i class="fas ${statusIcon} mr-2"></i>
                                    <span>${service.status.replace('_', ' ')}</span>
                                </div>
                            </div>
                        </div>
                        <div class="flex items-center justify-between">
                            <div class="text-xs text-gray-500">
                                Last check: ${service.last_check ? new Date(service.last_check).toLocaleString() : 'N/A'}
                            </div>
                            <div class="flex space-x-2">
                                ${actionsHtml}
                            </div>
                        </div>
                    </div>
                `;
                servicesList.innerHTML += item;
            });
        } else {
            servicesList.innerHTML = '<p class="text-center text-gray-500">No services found.</p>';
        }
        
        // Update summary display if exists
        const summaryEl = document.getElementById('services-summary');
        if (summaryEl && summary) {
            summaryEl.innerHTML = `
                <div class="grid grid-cols-2 md:grid-cols-6 gap-4 mb-4">
                    <div class="text-center">
                        <div class="text-2xl font-bold text-green-600">${summary.running || 0}</div>
                        <div class="text-xs text-gray-600">Running</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-red-600">${summary.stopped || 0}</div>
                        <div class="text-xs text-gray-600">Stopped</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-gray-600">${summary.not_enabled || 0}</div>
                        <div class="text-xs text-gray-600">Not Enabled</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-orange-600">${summary.not_configured || 0}</div>
                        <div class="text-xs text-gray-600">Not Configured</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-blue-600">${summary.configured || 0}</div>
                        <div class="text-xs text-gray-600">Configured</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-red-700">${summary.error || 0}</div>
                        <div class="text-xs text-gray-600">Error</div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading services:', error);
        document.getElementById('services-list').innerHTML = '<p class="text-red-500">Failed to load services.</p>';
    }
}

/**
 * Perform an action on a service
 */
async function performServiceAction(serviceId, action) {
    try {
        let requestBody = {};
        
        // For configure action, prompt for configuration data
        if (action === 'configure') {
            const configData = await promptForServiceConfiguration(serviceId);
            if (!configData) return; // User cancelled
            
            requestBody = { config: configData };
            
            // Use the dedicated configure endpoint
            const response = await fetch(`/api/services/${serviceId}/configure`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            
            const result = await response.json();
            if (response.ok && result.success) {
                alert(`Service ${serviceId} configured successfully: ${result.message}`);
            } else {
                alert(`Failed to configure service ${serviceId}: ${result.error || 'Unknown error'}`);
            }
        } else {
            // For other actions, use the generic action endpoint
            const response = await fetch(`/api/services/${serviceId}/${action}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            
            const result = await response.json();
            if (response.ok && result.success) {
                alert(`Action '${action}' completed successfully: ${result.message}`);
            } else {
                alert(`Action '${action}' failed: ${result.error || 'Unknown error'}`);
            }
        }
        
        // Reload services to reflect changes
        await loadServices();
        
    } catch (error) {
        console.error(`Error performing action ${action} on service ${serviceId}:`, error);
        alert(`Failed to perform action: ${error.message}`);
    }
}

/**
 * Prompt user for service configuration data
 */
async function promptForServiceConfiguration(serviceId) {
    // Get service info first to know what configuration is needed
    try {
        const response = await fetch('/api/services');
        const data = await response.json();
        const service = data.services.find(s => s.id === serviceId);
        
        if (!service) {
            alert(`Service ${serviceId} not found`);
            return null;
        }
        
        const configKeys = service.config_keys || [];
        const configData = {};
        
        if (configKeys.length === 0) {
            // No specific configuration needed
            return {};
        }
        
        // Prompt for each required configuration key
        for (const key of configKeys) {
            const value = prompt(`Enter ${key.replace('_', ' ')} for ${service.name}:`);
            if (value === null) {
                return null; // User cancelled
            }
            configData[key] = value;
        }
        
        return configData;
        
    } catch (error) {
        console.error('Error getting service configuration requirements:', error);
        // Fallback to simple configuration prompt
        const config = prompt(`Enter configuration data for ${serviceId} (JSON format):`);
        if (config === null) return null;
        
        try {
            return JSON.parse(config);
        } catch (e) {
            alert('Invalid JSON format');
            return null;
        }
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
        // Wait for MCP SDK to be available
        if (typeof window.MCP === 'undefined' || !window.MCP.Buckets) {
            throw new Error('MCP SDK not loaded or Buckets namespace not available');
        }
        
        // Use MCP SDK to list buckets (reads from ~/.ipfs_kit/ first)
        const data = await window.MCP.Buckets.list();
        const bucketsList = document.getElementById('buckets-list');
        bucketsList.innerHTML = '';

        const items = (data.items || data.buckets || []);
        if (items.length > 0) {
            // Enhanced bucket display with comprehensive management features
            for (const bucket of items) {
                // Get detailed bucket information including file counts and settings
                let bucketDetails = {};
                try {
                    bucketDetails = await window.MCP.Buckets.get(bucket.name);
                } catch (e) {
                    console.warn(`Could not load details for bucket ${bucket.name}:`, e);
                    bucketDetails = bucket;
                }

                const fileCount = bucketDetails.file_count || 0;
                const folderCount = bucketDetails.folder_count || 0;
                const totalSize = bucketDetails.total_size || 0;
                const settings = bucketDetails.settings || {};
                
                const vectorSearch = settings.vector_search ? '✓' : '✗';
                const knowledgeGraph = settings.knowledge_graph ? '✓' : '✗';
                
                const item = `
                    <div class="card p-6 mb-4 border rounded-lg hover:shadow-lg transition-shadow">
                        <div class="flex justify-between items-start mb-4">
                            <div class="flex-grow">
                                <h4 class="text-lg font-semibold text-gray-800 mb-2">${bucket.name}</h4>
                                <p class="text-sm text-gray-600 mb-2">Backend: ${bucket.backend || 'default'}</p>
                                <p class="text-sm text-gray-600">
                                    Files: ${fileCount} | Folders: ${folderCount} | Size: ${formatBytes(totalSize)} | 
                                    Vector Search: ${vectorSearch} | Knowledge Graph: ${knowledgeGraph}
                                </p>
                            </div>
                            <div class="flex space-x-2 ml-4">
                                <button onclick="viewBucketFiles('${bucket.name}')" class="btn-sm bg-blue-500 text-white px-3 py-1 rounded text-xs hover:bg-blue-600 transition-colors" title="View Files">
                                    📁 View Files
                                </button>
                                <button onclick="showBucketSettings('${bucket.name}')" class="btn-sm bg-gray-500 text-white px-3 py-1 rounded text-xs hover:bg-gray-600 transition-colors" title="Settings">
                                    ⚙️ Settings
                                </button>
                                <button onclick="toggleBucketDetails('${bucket.name}')" class="btn-sm bg-green-500 text-white px-3 py-1 rounded text-xs hover:bg-green-600 transition-colors" title="Toggle Details">
                                    ${document.getElementById('bucket-details-' + bucket.name.replace(/[^a-zA-Z0-9]/g, '_')) ? '▲' : '▼'}
                                </button>
                                <button onclick="deleteBucket('${bucket.name}')" class="btn-sm bg-red-500 text-white px-3 py-1 rounded text-xs hover:bg-red-600 transition-colors" title="Delete">
                                    🗑️ Delete
                                </button>
                            </div>
                        </div>
                        <div id="bucket-details-${bucket.name.replace(/[^a-zA-Z0-9]/g, '_')}" class="hidden mt-4 p-4 bg-gray-50 rounded-lg">
                            <h5 class="font-medium text-gray-700 mb-2">Advanced Settings</h5>
                            <div class="grid grid-cols-2 gap-4 text-sm text-gray-600">
                                <div>
                                    <strong>Storage Quota:</strong> ${settings.storage_quota ? formatBytes(settings.storage_quota) : 'Unlimited'}
                                </div>
                                <div>
                                    <strong>Max Files:</strong> ${settings.max_files || 'Unlimited'}
                                </div>
                                <div>
                                    <strong>Public Access:</strong> ${settings.public_access ? 'Yes' : 'No'}
                                </div>
                                <div>
                                    <strong>Cache TTL:</strong> ${settings.cache_ttl || 'Default'}
                                </div>
                            </div>
                            <div class="mt-3">
                                <strong class="text-gray-700">Policies:</strong>
                                <div class="text-sm text-gray-600">
                                    Replication: ${settings.replication_factor || 1} | 
                                    Cache: ${settings.cache_policy || 'default'} | 
                                    Retention: ${settings.retention_period || 'permanent'}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                bucketsList.innerHTML += item;
            }
        } else {
            bucketsList.innerHTML = '<p class="text-center text-gray-500">No buckets found.</p>';
        }
    } catch (error) {
        console.error('Error loading buckets via MCP SDK:', error);
        // Fallback to direct API call if MCP SDK fails
        try {
            console.log('Falling back to direct API call...');
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
                            <p class="text-xs text-red-500 mt-2">⚠️ Loaded via fallback API (MCP SDK unavailable)</p>
                        </div>
                    `;
                    bucketsList.innerHTML += item;
                });
            } else {
                bucketsList.innerHTML = '<p class="text-center text-gray-500">No buckets found.</p>';
            }
        } catch (fallbackError) {
            console.error('Fallback API call also failed:', fallbackError);
            document.getElementById('buckets-list').innerHTML = '<p class="text-red-500">Failed to load buckets via both MCP SDK and direct API.</p>';
        }
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

// ============ Comprehensive Bucket Management Functions (using MCP SDK) ============

/**
 * View files in a bucket using MCP SDK
 */
async function viewBucketFiles(bucketName) {
    try {
        if (typeof window.MCP === 'undefined' || !window.MCP.Files) {
            throw new Error('MCP SDK Files namespace not available');
        }

        // Use MCP SDK to list files in the bucket (reads from ~/.ipfs_kit/ first)
        const files = await window.MCP.Files.list(`${bucketName}/`);
        
        // Create a modal or redirect to show file browser
        const fileList = files.files || files.items || [];
        let filesHtml = '<h3>Files in ' + bucketName + ':</h3><ul>';
        
        if (fileList.length > 0) {
            fileList.forEach(file => {
                filesHtml += `<li>${file.name || file.path} (${formatBytes(file.size || 0)})</li>`;
            });
        } else {
            filesHtml += '<li>No files found</li>';
        }
        filesHtml += '</ul>';
        
        // Simple alert for now, could be enhanced with a proper modal
        alert(filesHtml.replace(/<[^>]*>/g, ''));
        
    } catch (error) {
        console.error('Error viewing bucket files:', error);
        alert('Failed to load bucket files via MCP SDK: ' + error.message);
    }
}

/**
 * Show bucket settings using MCP SDK
 */
async function showBucketSettings(bucketName) {
    try {
        if (typeof window.MCP === 'undefined' || !window.MCP.Buckets) {
            throw new Error('MCP SDK Buckets namespace not available');
        }

        // Get bucket policy/settings via MCP SDK
        const settings = await window.MCP.Buckets.getPolicy(bucketName);
        
        // Create settings form
        const settingsForm = `
            Settings for ${bucketName}:
            
            Vector Search: ${settings.vector_search ? 'Enabled' : 'Disabled'}
            Knowledge Graph: ${settings.knowledge_graph ? 'Enabled' : 'Disabled'}
            Storage Quota: ${settings.storage_quota ? formatBytes(settings.storage_quota) : 'Unlimited'}
            Max Files: ${settings.max_files || 'Unlimited'}
            Public Access: ${settings.public_access ? 'Yes' : 'No'}
            Cache TTL: ${settings.cache_ttl || 'Default'}
            
            Policies:
            - Replication Factor: ${settings.replication_factor || 1}
            - Cache Policy: ${settings.cache_policy || 'default'}
            - Retention Period: ${settings.retention_period || 'permanent'}
        `;
        
        // For now, just show in alert. Could be enhanced with proper modal.
        alert(settingsForm);
        
    } catch (error) {
        console.error('Error loading bucket settings:', error);
        alert('Failed to load bucket settings via MCP SDK: ' + error.message);
    }
}

/**
 * Toggle bucket details visibility
 */
function toggleBucketDetails(bucketName) {
    const detailsId = 'bucket-details-' + bucketName.replace(/[^a-zA-Z0-9]/g, '_');
    const detailsEl = document.getElementById(detailsId);
    
    if (detailsEl) {
        detailsEl.classList.toggle('hidden');
        
        // Update button text
        const button = document.querySelector(`button[onclick="toggleBucketDetails('${bucketName}')"]`);
        if (button) {
            button.innerHTML = detailsEl.classList.contains('hidden') ? 
                '▼' : '▲';
        }
    }
}

/**
 * Delete a bucket using MCP SDK
 */
async function deleteBucket(bucketName) {
    if (!confirm(`Are you sure you want to delete bucket "${bucketName}"? This action cannot be undone.`)) {
        return;
    }
    
    try {
        if (typeof window.MCP === 'undefined' || !window.MCP.Buckets) {
            throw new Error('MCP SDK Buckets namespace not available');
        }

        // Delete bucket via MCP SDK (manages ~/.ipfs_kit/ filesystem)
        await window.MCP.Buckets.delete(bucketName);
        
        // Reload buckets list
        await loadBuckets();
        
        alert(`Bucket "${bucketName}" deleted successfully.`);
        
    } catch (error) {
        console.error('Error deleting bucket:', error);
        alert('Failed to delete bucket via MCP SDK: ' + error.message);
    }
}

/**
 * Create a new bucket using MCP SDK
 */
async function createBucket() {
    const bucketName = prompt('Enter bucket name:');
    if (!bucketName) return;
    
    const backend = prompt('Enter backend name (or leave empty for default):') || 'default';
    
    try {
        if (typeof window.MCP === 'undefined' || !window.MCP.Buckets) {
            throw new Error('MCP SDK Buckets namespace not available');
        }

        // Create bucket via MCP SDK (creates in ~/.ipfs_kit/ filesystem)
        await window.MCP.Buckets.create(bucketName, backend);
        
        // Reload buckets list
        await loadBuckets();
        
        alert(`Bucket "${bucketName}" created successfully.`);
        
    } catch (error) {
        console.error('Error creating bucket:', error);
        alert('Failed to create bucket via MCP SDK: ' + error.message);
    }
}

/**
 * Upload files to bucket using MCP SDK
 */
async function uploadToBucket(bucketName) {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.multiple = true;
    
    fileInput.onchange = async function(event) {
        const files = event.target.files;
        if (!files || files.length === 0) return;
        
        try {
            if (typeof window.MCP === 'undefined' || !window.MCP.Files) {
                throw new Error('MCP SDK Files namespace not available');
            }

            for (const file of files) {
                const reader = new FileReader();
                reader.onload = async function(e) {
                    try {
                        const content = e.target.result;
                        const filePath = `${bucketName}/${file.name}`;
                        
                        // Write file via MCP SDK (writes to ~/.ipfs_kit/ filesystem first)
                        await window.MCP.Files.write(filePath, content, 'binary');
                        
                        console.log(`Uploaded ${file.name} to bucket ${bucketName}`);
                    } catch (error) {
                        console.error(`Failed to upload ${file.name}:`, error);
                        alert(`Failed to upload ${file.name}: ${error.message}`);
                    }
                };
                reader.readAsArrayBuffer(file);
            }
            
            // Reload buckets to show updated file counts
            setTimeout(() => loadBuckets(), 2000);
            alert(`Started uploading ${files.length} files to bucket "${bucketName}".`);
            
        } catch (error) {
            console.error('Error uploading files:', error);
            alert('Failed to upload files via MCP SDK: ' + error.message);
        }
    };
    
    fileInput.click();
}
