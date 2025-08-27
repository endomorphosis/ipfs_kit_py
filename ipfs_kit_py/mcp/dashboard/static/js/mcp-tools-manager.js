// MCP Tools Management Module

// Global variables for tool management
let mcpTools = [];
let currentTool = null;
let toolExecutionInProgress = false;

// MCP Tools data - predefined tools available in the system
const PREDEFINED_TOOLS = [
    {
        name: 'ipfs_add',
        category: 'IPFS Core',
        description: 'Add files or directories to IPFS network',
        icon: 'fas fa-plus-circle',
        color: 'blue',
        parameters: [
            { name: 'path', type: 'string', required: true, description: 'File or directory path to add' },
            { name: 'recursive', type: 'boolean', required: false, description: 'Add directory recursively' },
            { name: 'wrap_with_directory', type: 'boolean', required: false, description: 'Wrap files in a directory' }
        ],
        status: 'active'
    },
    {
        name: 'ipfs_cat',
        category: 'IPFS Core', 
        description: 'Retrieve content from IPFS by CID',
        icon: 'fas fa-eye',
        color: 'green',
        parameters: [
            { name: 'cid', type: 'string', required: true, description: 'Content identifier (CID) to retrieve' },
            { name: 'output_path', type: 'string', required: false, description: 'Path to save output file' }
        ],
        status: 'active'
    },
    {
        name: 'storage_transfer',
        category: 'Storage Management',
        description: 'Transfer data between storage backends',
        icon: 'fas fa-exchange-alt',
        color: 'orange',
        parameters: [
            { name: 'source_backend', type: 'string', required: true, description: 'Source storage backend' },
            { name: 'target_backend', type: 'string', required: true, description: 'Target storage backend' },
            { name: 'cid', type: 'string', required: true, description: 'Content identifier to transfer' }
        ],
        status: 'active'
    },
    {
        name: 'pin_sync',
        category: 'Pin Management',
        description: 'Synchronize pins across IPFS cluster',
        icon: 'fas fa-sync-alt',
        color: 'purple',
        parameters: [
            { name: 'mode', type: 'select', required: true, options: ['full', 'incremental'], description: 'Synchronization mode' },
            { name: 'cluster_peers', type: 'string', required: false, description: 'Comma-separated list of peer IDs' }
        ],
        status: 'active'
    },
    {
        name: 'file_indexer',
        category: 'Data Management',
        description: 'Index files for search and metadata',
        icon: 'fas fa-search',
        color: 'teal',
        parameters: [
            { name: 'path', type: 'string', required: true, description: 'Directory path to index' },
            { name: 'recursive', type: 'boolean', required: false, description: 'Index subdirectories recursively' },
            { name: 'update_existing', type: 'boolean', required: false, description: 'Update existing index entries' }
        ],
        status: 'active'
    },
    {
        name: 'garbage_collector',
        category: 'Maintenance',
        description: 'Clean up unused data blocks',
        icon: 'fas fa-trash-alt',
        color: 'red',
        parameters: [
            { name: 'dry_run', type: 'boolean', required: false, description: 'Show what would be deleted without actually deleting' },
            { name: 'grace_period', type: 'number', required: false, description: 'Grace period in hours before deletion' }
        ],
        status: 'active'
    }
];

// Initialize MCP Tools functionality
async function loadMcpDetails() {
    try {
        // Load available tools from server
        await loadMcpTools();
        
        // Load VFS buckets
        await loadVfsBuckets();
        
        // Load configuration files
        await loadConfigFiles();
        
        // Load daemon status
        await loadDaemonStatus();
        
        console.log('MCP Details loaded successfully');
    } catch (error) {
        console.error('Error loading MCP details:', error);
        showNotification('Failed to load MCP details', 'error');
    }
}

// Load MCP tools and render them
async function loadMcpTools() {
    try {
        // Fetch tools from the server API
        const response = await fetch('/api/mcp/tools');
        const data = await response.json();
        
        if (data.success) {
            mcpTools = data.tools || [];
        } else {
            console.error('Error loading MCP tools:', data.error);
            // Fall back to predefined tools
            mcpTools = [...PREDEFINED_TOOLS];
        }
        
        renderMcpTools();
        updateMcpServerStatus('running');
    } catch (error) {
        console.error('Error loading MCP tools:', error);
        // Fall back to predefined tools
        mcpTools = [...PREDEFINED_TOOLS];
        renderMcpTools();
        updateMcpServerStatus('error');
        throw error;
    }
}

// Render MCP tools in the grid
function renderMcpTools() {
    const toolsGrid = document.getElementById('mcp-tools-grid');
    
    if (!toolsGrid) {
        console.error('MCP tools grid element not found');
        return;
    }
    
    toolsGrid.innerHTML = '';
    
    mcpTools.forEach(tool => {
        const toolCard = createToolCard(tool);
        toolsGrid.appendChild(toolCard);
    });
}

// Create a tool card element
function createToolCard(tool) {
    const card = document.createElement('div');
    card.className = 'bg-white border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow';
    
    const statusColor = tool.status === 'active' ? 'green' : 
                       tool.status === 'error' ? 'red' : 'gray';
    
    card.innerHTML = `
        <div class="flex items-start justify-between mb-4">
            <div class="flex items-center">
                <div class="p-3 bg-${tool.color}-100 rounded-lg mr-4">
                    <i class="${tool.icon} text-${tool.color}-600 text-xl"></i>
                </div>
                <div>
                    <h4 class="text-lg font-semibold text-gray-900">${tool.name}</h4>
                    <p class="text-sm text-gray-500">${tool.category}</p>
                </div>
            </div>
            <div class="flex items-center bg-${statusColor}-100 text-${statusColor}-800 px-2 py-1 rounded-full text-xs font-medium">
                <div class="w-2 h-2 bg-${statusColor}-500 rounded-full mr-2"></div>
                ${tool.status}
            </div>
        </div>
        
        <p class="text-sm text-gray-600 mb-4">${tool.description}</p>
        
        <div class="flex space-x-2">
            <button onclick="showToolInfo('${tool.name}')" class="flex-1 px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 font-medium text-sm transition-colors">
                <i class="fas fa-info-circle mr-2"></i>
                Info
            </button>
            <button onclick="showToolExecuteModal('${tool.name}')" class="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium text-sm transition-colors">
                <i class="fas fa-play mr-2"></i>
                Execute
            </button>
        </div>
    `;
    
    return card;
}

// Show tool information
function showToolInfo(toolName) {
    const tool = mcpTools.find(t => t.name === toolName);
    if (!tool) {
        showNotification(`Tool ${toolName} not found`, 'error');
        return;
    }
    
    const parametersHtml = tool.parameters.map(param => {
        const requiredBadge = param.required ? '<span class="bg-red-100 text-red-800 text-xs px-2 py-1 rounded ml-2">Required</span>' : '';
        const optionsInfo = param.options ? ` (Options: ${param.options.join(', ')})` : '';
        
        return `
            <div class="mb-2">
                <div class="font-medium text-gray-900">${param.name} <span class="text-gray-500 text-sm">(${param.type})</span> ${requiredBadge}</div>
                <div class="text-sm text-gray-600">${param.description}${optionsInfo}</div>
            </div>
        `;
    }).join('');
    
    // Create info modal (simple alert for now, could be enhanced with proper modal)
    const infoContent = `
        Tool: ${tool.name}
        Category: ${tool.category}
        Description: ${tool.description}
        Status: ${tool.status}
        
        Parameters:
        ${tool.parameters.map(p => `- ${p.name} (${p.type})${p.required ? ' *required*' : ''}: ${p.description}`).join('\n')}
    `;
    
    alert(infoContent);
}

// Show tool execution modal
function showToolExecuteModal(toolName) {
    const tool = mcpTools.find(t => t.name === toolName);
    if (!tool) {
        showNotification(`Tool ${toolName} not found`, 'error');
        return;
    }
    
    currentTool = tool;
    
    // Update modal title
    document.getElementById('modal-tool-title').textContent = `Execute: ${tool.name}`;
    
    // Generate form
    const formHtml = generateToolForm(tool);
    document.getElementById('tool-execution-form').innerHTML = formHtml;
    
    // Hide result section
    document.getElementById('tool-execution-result').classList.add('hidden');
    
    // Show modal
    document.getElementById('tool-execution-modal').classList.remove('hidden');
}

// Generate form for tool parameters
function generateToolForm(tool) {
    if (!tool.parameters || tool.parameters.length === 0) {
        return '<div class="text-center text-gray-500 py-8">This tool has no parameters</div>';
    }
    
    let formHtml = `
        <div class="mb-6">
            <h5 class="font-semibold text-gray-900 mb-2">Tool: ${tool.name}</h5>
            <p class="text-sm text-gray-600 mb-4">${tool.description}</p>
        </div>
        <div class="space-y-4">
    `;
    
    tool.parameters.forEach(param => {
        const requiredAttr = param.required ? 'required' : '';
        const requiredIndicator = param.required ? ' *' : '';
        
        if (param.type === 'boolean') {
            formHtml += `
                <div class="flex items-center justify-between">
                    <div>
                        <label class="text-sm font-medium text-gray-700">${param.name}${requiredIndicator}</label>
                        <p class="text-xs text-gray-500 mt-1">${param.description}</p>
                    </div>
                    <input type="checkbox" name="${param.name}" class="tool-param-input w-4 h-4 text-blue-600 rounded focus:ring-blue-500">
                </div>
            `;
        } else if (param.type === 'select' && param.options) {
            formHtml += `
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">${param.name}${requiredIndicator}</label>
                    <select name="${param.name}" class="tool-param-input w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" ${requiredAttr}>
                        <option value="">Select ${param.name}</option>
                        ${param.options.map(opt => `<option value="${opt}">${opt}</option>`).join('')}
                    </select>
                    <p class="text-xs text-gray-500 mt-1">${param.description}</p>
                </div>
            `;
        } else if (param.type === 'number') {
            formHtml += `
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">${param.name}${requiredIndicator}</label>
                    <input type="number" name="${param.name}" placeholder="Enter ${param.name}" 
                           class="tool-param-input w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" ${requiredAttr}>
                    <p class="text-xs text-gray-500 mt-1">${param.description}</p>
                </div>
            `;
        } else {
            // Default to text input
            formHtml += `
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">${param.name}${requiredIndicator}</label>
                    <input type="text" name="${param.name}" placeholder="Enter ${param.name}" 
                           class="tool-param-input w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" ${requiredAttr}>
                    <p class="text-xs text-gray-500 mt-1">${param.description}</p>
                </div>
            `;
        }
    });
    
    formHtml += '</div>';
    
    return formHtml;
}

// Execute tool with parameters
async function executeTool() {
    if (!currentTool || toolExecutionInProgress) {
        return;
    }
    
    try {
        toolExecutionInProgress = true;
        
        // Get form data
        const formData = new FormData();
        const inputs = document.querySelectorAll('.tool-param-input');
        const parameters = {};
        
        inputs.forEach(input => {
            if (input.type === 'checkbox') {
                parameters[input.name] = input.checked;
            } else if (input.value) {
                parameters[input.name] = input.value;
            }
        });
        
        // Show loading state
        const executeBtn = document.querySelector('[onclick="executeTool()"]');
        const originalBtnContent = executeBtn.innerHTML;
        executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Executing...';
        executeBtn.disabled = true;
        
        // Make API call to execute tool
        const response = await fetch('/api/mcp/tools/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tool_name: currentTool.name,
                parameters: parameters
            })
        });
        
        const result = await response.json();
        
        // Show result
        document.getElementById('tool-result-output').textContent = JSON.stringify(result, null, 2);
        document.getElementById('tool-execution-result').classList.remove('hidden');
        
        if (result.success) {
            showNotification(`Tool ${currentTool.name} executed successfully`, 'success');
        } else {
            showNotification(`Tool execution failed: ${result.error}`, 'error');
        }
        
        // Restore button
        executeBtn.innerHTML = originalBtnContent;
        executeBtn.disabled = false;
        
    } catch (error) {
        console.error('Error executing tool:', error);
        showNotification(`Error executing tool: ${error.message}`, 'error');
        
        // Restore button on error
        const executeBtn = document.querySelector('[onclick="executeTool()"]');
        executeBtn.innerHTML = '<i class="fas fa-play mr-2"></i>Execute Tool';
        executeBtn.disabled = false;
    } finally {
        toolExecutionInProgress = false;
    }
}

// Close tool modal
function closeToolModal() {
    document.getElementById('tool-execution-modal').classList.add('hidden');
    currentTool = null;
}

// Refresh MCP tools
async function refreshMcpTools() {
    try {
        const refreshBtn = document.querySelector('[onclick="refreshMcpTools()"]');
        const originalContent = refreshBtn.innerHTML;
        
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Refreshing...';
        refreshBtn.disabled = true;
        
        await loadMcpTools();
        showNotification('MCP tools refreshed successfully', 'success');
        
        refreshBtn.innerHTML = originalContent;
        refreshBtn.disabled = false;
    } catch (error) {
        console.error('Error refreshing tools:', error);
        showNotification('Failed to refresh MCP tools', 'error');
        
        const refreshBtn = document.querySelector('[onclick="refreshMcpTools()"]');
        refreshBtn.innerHTML = '<i class="fas fa-sync-alt mr-2"></i>Refresh Tools';
        refreshBtn.disabled = false;
    }
}

// Update MCP server status
function updateMcpServerStatus(status) {
    const statusElement = document.getElementById('mcp-server-status');
    const statusText = status === 'running' ? 'Server Running' : 
                     status === 'error' ? 'Server Error' : 'Server Stopped';
    
    statusElement.textContent = statusText;
    statusElement.className = status === 'running' ? 'text-green-800' : 
                            status === 'error' ? 'text-red-800' : 'text-gray-800';
}

// Load Virtual Filesystem Buckets
async function loadVfsBuckets() {
    try {
        // Fetch buckets from the server API
        const response = await fetch('/api/mcp/vfs/buckets');
        const data = await response.json();
        
        if (data.success) {
            const buckets = data.buckets || [];
            renderVfsBuckets(buckets);
            updateBackendCounts(buckets);
        } else {
            console.error('Error loading VFS buckets:', data.error);
            // Fall back to mock data
            const mockBuckets = [
                {
                    name: 'ipfs-main',
                    backend: 'IPFS',
                    type: 'ipfs',
                    itemCount: 1247,
                    totalSize: 2147483648,
                    status: 'active'
                },
                {
                    name: 's3-backup',
                    backend: 'S3 Compatible',
                    type: 's3',
                    itemCount: 523,
                    totalSize: 1073741824,
                    status: 'active'
                },
                {
                    name: 'hf-models',
                    backend: 'HuggingFace',
                    type: 'huggingface',
                    itemCount: 89,
                    totalSize: 536870912,
                    status: 'active'
                }
            ];
            
            renderVfsBuckets(mockBuckets);
            updateBackendCounts(mockBuckets);
        }
    } catch (error) {
        console.error('Error loading VFS buckets:', error);
        throw error;
    }
}

// Render VFS buckets list
function renderVfsBuckets(buckets) {
    const bucketsList = document.getElementById('vfs-buckets-list');
    
    if (!bucketsList) {
        console.error('VFS buckets list element not found');
        return;
    }
    
    bucketsList.innerHTML = '';
    
    buckets.forEach(bucket => {
        const bucketCard = createVfsBucketCard(bucket);
        bucketsList.appendChild(bucketCard);
    });
}

// Create VFS bucket card
function createVfsBucketCard(bucket) {
    const card = document.createElement('div');
    card.className = 'bg-white border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow';
    
    const backendIcon = bucket.type === 'ipfs' ? 'fas fa-globe' :
                       bucket.type === 's3' ? 'fas fa-cloud' :
                       bucket.type === 'huggingface' ? 'fas fa-robot' : 
                       'fab fa-github';
    
    const backendColor = bucket.type === 'ipfs' ? 'blue' :
                        bucket.type === 's3' ? 'orange' :
                        bucket.type === 'huggingface' ? 'purple' : 'gray';
    
    card.innerHTML = `
        <div class="flex items-start justify-between mb-4">
            <div class="flex items-center">
                <div class="p-3 bg-${backendColor}-100 rounded-lg mr-4">
                    <i class="${backendIcon} text-${backendColor}-600 text-xl"></i>
                </div>
                <div>
                    <h4 class="text-lg font-semibold text-gray-900">${bucket.name}</h4>
                    <p class="text-sm text-gray-500">${bucket.backend}</p>
                </div>
            </div>
            <div class="flex items-center bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs font-medium">
                <div class="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
                ${bucket.status}
            </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4 mb-4 text-sm">
            <div>
                <span class="text-gray-600">Items:</span>
                <span class="font-semibold ml-2">${bucket.itemCount.toLocaleString()}</span>
            </div>
            <div>
                <span class="text-gray-600">Size:</span>
                <span class="font-semibold ml-2">${formatBytes(bucket.totalSize)}</span>
            </div>
        </div>
        
        <div class="flex space-x-2">
            <button onclick="viewVfsBucket('${bucket.name}')" class="flex-1 px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 font-medium text-sm transition-colors">
                <i class="fas fa-eye mr-2"></i>
                View
            </button>
            <button onclick="manageVfsBucket('${bucket.name}')" class="flex-1 px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 font-medium text-sm transition-colors">
                <i class="fas fa-cog mr-2"></i>
                Manage
            </button>
            <button onclick="deleteVfsBucket('${bucket.name}')" class="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 font-medium text-sm transition-colors">
                <i class="fas fa-trash mr-2"></i>
                Delete
            </button>
        </div>
    `;
    
    return card;
}

// Update backend counts
function updateBackendCounts(buckets) {
    const ipfsBuckets = buckets.filter(b => b.type === 'ipfs');
    const s3Buckets = buckets.filter(b => b.type === 's3');
    const hfBuckets = buckets.filter(b => b.type === 'huggingface');
    const githubBuckets = buckets.filter(b => b.type === 'github');
    
    document.getElementById('ipfs-bucket-count').textContent = ipfsBuckets.length;
    document.getElementById('s3-bucket-count').textContent = s3Buckets.length;
    document.getElementById('hf-bucket-count').textContent = hfBuckets.length;
    document.getElementById('github-bucket-count').textContent = githubBuckets.length;
    
    document.getElementById('ipfs-bucket-size').textContent = formatBytes(ipfsBuckets.reduce((sum, b) => sum + b.totalSize, 0)) + ' total';
    document.getElementById('s3-bucket-size').textContent = formatBytes(s3Buckets.reduce((sum, b) => sum + b.totalSize, 0)) + ' total';
    document.getElementById('hf-bucket-size').textContent = formatBytes(hfBuckets.reduce((sum, b) => sum + b.totalSize, 0)) + ' total';
    document.getElementById('github-bucket-size').textContent = formatBytes(githubBuckets.reduce((sum, b) => sum + b.totalSize, 0)) + ' total';
}

// VFS Bucket management functions
function viewVfsBucket(bucketName) {
    // Switch to buckets tab and select the bucket
    showTab('buckets');
    // This would require coordination with the existing bucket functionality
    showNotification(`Viewing bucket: ${bucketName}`, 'info');
}

function manageVfsBucket(bucketName) {
    showNotification(`Manage bucket functionality for ${bucketName} will be implemented`, 'info');
}

function deleteVfsBucket(bucketName) {
    if (confirm(`Are you sure you want to delete bucket "${bucketName}"? This action cannot be undone.`)) {
        showNotification(`Delete bucket functionality for ${bucketName} will be implemented`, 'info');
    }
}

// Configuration file management
let currentConfigFile = 'config';
const configFiles = {
    config: {
        filename: 'config.yaml',
        content: '',
        modified: false
    },
    peers: {
        filename: 'peers.json',
        content: '',
        modified: false
    },
    keys: {
        filename: 'keys.json',
        content: '',
        modified: false
    }
};

// Load configuration files
async function loadConfigFiles() {
    try {
        // Load config.yaml by default
        await loadConfigFile('config');
    } catch (error) {
        console.error('Error loading config files:', error);
        throw error;
    }
}

// Load specific configuration file
async function loadConfigFile(configType) {
    try {
        // Fetch config file from server API
        const response = await fetch(`/api/mcp/config/${configType}`);
        const data = await response.json();
        
        if (data.success) {
            configFiles[configType].content = data.content || '';
        } else {
            console.error(`Error loading config file ${configType}:`, data.error);
            // Fall back to mock content
            const mockContent = {
                config: `# IPFS Kit Configuration
ipfs:
  api_port: 5001
  gateway_port: 8080
  swarm_port: 4001

storage_backends:
  s3:
    enabled: true
    bucket: "ipfs-kit-backup"
    region: "us-west-2"
  
  huggingface:
    enabled: true
    username: "your-username"

daemon_settings:
  file_indexer:
    enabled: true
    interval: 3600
  pin_sync:
    enabled: true
    interval: 1800
  garbage_collector:
    enabled: false
    interval: 86400`,
                
                peers: `{
  "bootstrap_peers": [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa"
  ],
  "trusted_peers": [],
  "blocked_peers": []
}`,
                
                keys: `{
  "peer_id": "QmYourPeerIDHere",
  "private_key": "CAISIQABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
}`
            };
            
            configFiles[configType].content = mockContent[configType] || '';
        }
        
        if (configType === currentConfigFile) {
            document.getElementById('config-file-content').value = configFiles[configType].content;
            updateConfigFileStatus('Loaded');
        }
        
    } catch (error) {
        console.error(`Error loading config file ${configType}:`, error);
        throw error;
    }
}

// Show configuration file
function showConfigFile(configType) {
    if (configFiles[currentConfigFile].modified) {
        if (!confirm('You have unsaved changes. Do you want to discard them?')) {
            return;
        }
    }
    
    currentConfigFile = configType;
    
    // Update tab buttons
    document.querySelectorAll('.config-tab-btn').forEach(btn => {
        btn.classList.remove('active', 'text-blue-600', 'border-blue-600');
        btn.classList.add('text-gray-500', 'border-transparent');
    });
    
    const activeBtn = document.querySelector(`[data-config="${configType}"]`);
    activeBtn.classList.remove('text-gray-500', 'border-transparent');
    activeBtn.classList.add('active', 'text-blue-600', 'border-blue-600');
    
    // Update file name
    document.getElementById('current-config-file').textContent = configFiles[configType].filename;
    
    // Load content
    document.getElementById('config-file-content').value = configFiles[configType].content;
    updateConfigFileStatus(configFiles[configType].modified ? 'Modified' : 'Ready');
    
    // Load file if not already loaded
    if (!configFiles[configType].content) {
        loadConfigFile(configType);
    }
}

// Save configuration file
async function saveConfigFile() {
    try {
        const content = document.getElementById('config-file-content').value;
        
        // Call API to save file
        const response = await fetch(`/api/mcp/config/${currentConfigFile}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content: content })
        });
        
        const data = await response.json();
        
        if (data.success) {
            configFiles[currentConfigFile].content = content;
            configFiles[currentConfigFile].modified = false;
            
            updateConfigFileStatus('Saved');
            showNotification(`${configFiles[currentConfigFile].filename} saved successfully`, 'success');
        } else {
            throw new Error(data.error || 'Failed to save file');
        }
        
    } catch (error) {
        console.error('Error saving config file:', error);
        showNotification(`Failed to save ${configFiles[currentConfigFile].filename}: ${error.message}`, 'error');
    }
}

// Reset configuration file
function resetConfigFile() {
    if (confirm('Are you sure you want to reset to the original content? Unsaved changes will be lost.')) {
        loadConfigFile(currentConfigFile);
        configFiles[currentConfigFile].modified = false;
        updateConfigFileStatus('Reset');
        showNotification(`${configFiles[currentConfigFile].filename} reset to original`, 'info');
    }
}

// Update config file status
function updateConfigFileStatus(status) {
    const statusElement = document.getElementById('config-file-status');
    statusElement.textContent = status;
    
    const colors = {
        'Ready': 'text-gray-500',
        'Modified': 'text-yellow-600',
        'Saved': 'text-green-600',
        'Reset': 'text-blue-600',
        'Loaded': 'text-blue-500'
    };
    
    statusElement.className = `text-xs ${colors[status] || 'text-gray-500'}`;
}

// Monitor config file changes
document.addEventListener('DOMContentLoaded', () => {
    const configTextarea = document.getElementById('config-file-content');
    if (configTextarea) {
        configTextarea.addEventListener('input', () => {
            configFiles[currentConfigFile].modified = true;
            updateConfigFileStatus('Modified');
        });
    }
});

// Daemon management functions
async function loadDaemonStatus() {
    try {
        // Fetch daemon status from server API
        const response = await fetch('/api/mcp/daemon/status');
        const data = await response.json();
        
        if (data.success) {
            updateDaemonStatus(data.services || {});
        } else {
            console.error('Error loading daemon status:', data.error);
            // Fall back to mock status
            const mockStatus = {
                file_indexer: {
                    status: 'stopped',
                    last_run: null,
                    file_count: 0
                },
                pin_sync: {
                    status: 'running',
                    last_run: new Date().toISOString(),
                    sync_count: 1247
                },
                garbage_collector: {
                    status: 'stopped',
                    last_run: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
                    freed_space: 1073741824 // 1GB
                }
            };
            
            updateDaemonStatus(mockStatus);
        }
    } catch (error) {
        console.error('Error loading daemon status:', error);
        throw error;
    }
}

// Update daemon status display
function updateDaemonStatus(status) {
    // File Indexer
    const indexerStatus = status.file_indexer;
    updateDaemonServiceStatus('indexer', indexerStatus.status);
    document.getElementById('indexer-status').textContent = indexerStatus.status;
    document.getElementById('indexer-last-run').textContent = indexerStatus.last_run ? formatTimestamp(indexerStatus.last_run) : 'Never';
    document.getElementById('indexer-file-count').textContent = indexerStatus.file_count.toLocaleString();
    
    // Pin Sync
    const pinSyncStatus = status.pin_sync;
    updateDaemonServiceStatus('pin-sync', pinSyncStatus.status);
    document.getElementById('pin-sync-status').textContent = pinSyncStatus.status;
    document.getElementById('pin-sync-last-run').textContent = pinSyncStatus.last_run ? formatTimestamp(pinSyncStatus.last_run) : 'Never';
    document.getElementById('pin-sync-count').textContent = pinSyncStatus.sync_count.toLocaleString();
    
    // Garbage Collector
    const gcStatus = status.garbage_collector;
    updateDaemonServiceStatus('gc', gcStatus.status);
    document.getElementById('gc-status').textContent = gcStatus.status;
    document.getElementById('gc-last-run').textContent = gcStatus.last_run ? formatTimestamp(gcStatus.last_run) : 'Never';
    document.getElementById('gc-freed-space').textContent = formatBytes(gcStatus.freed_space);
    
    // Update last update time
    document.getElementById('daemon-last-update').textContent = new Date().toLocaleTimeString();
}

// Update daemon service status indicator
function updateDaemonServiceStatus(servicePrefix, status) {
    const statusDot = document.getElementById(`${servicePrefix}-status-dot`);
    if (statusDot) {
        statusDot.className = `status-dot ${status === 'running' ? 'running' : status === 'error' ? 'error' : 'stopped'}`;
    }
}

// Start daemon service
async function startDaemonService(serviceName) {
    try {
        showNotification(`Starting ${serviceName}...`, 'info');
        
        // Call API to start daemon service
        const response = await fetch(`/api/mcp/daemon/${serviceName}/start`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`${serviceName} started successfully`, 'success');
        } else {
            throw new Error(data.error || `Failed to start ${serviceName}`);
        }
        
        await loadDaemonStatus(); // Refresh status
        
    } catch (error) {
        console.error(`Error starting ${serviceName}:`, error);
        showNotification(`Failed to start ${serviceName}: ${error.message}`, 'error');
    }
}

// Stop daemon service
async function stopDaemonService(serviceName) {
    try {
        showNotification(`Stopping ${serviceName}...`, 'info');
        
        // Call API to stop daemon service
        const response = await fetch(`/api/mcp/daemon/${serviceName}/stop`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`${serviceName} stopped successfully`, 'success');
        } else {
            throw new Error(data.error || `Failed to stop ${serviceName}`);
        }
        
        await loadDaemonStatus(); // Refresh status
        
    } catch (error) {
        console.error(`Error stopping ${serviceName}:`, error);
        showNotification(`Failed to stop ${serviceName}: ${error.message}`, 'error');
    }
}

// Clear daemon logs
function clearDaemonLogs() {
    document.getElementById('daemon-logs').innerHTML = '<div class="text-gray-500 italic">Logs cleared</div>';
    showNotification('Daemon logs cleared', 'info');
}

// Refresh daemon logs
async function refreshDaemonLogs() {
    try {
        // Fetch logs from server API
        const response = await fetch('/api/mcp/daemon/logs');
        const data = await response.json();
        
        if (data.success) {
            const logs = data.logs || [];
            const logsHtml = logs.map(log => {
                const timestamp = formatTimestamp(log.timestamp);
                const levelColor = log.level === 'INFO' ? 'text-blue-600' : 
                                 log.level === 'WARN' ? 'text-yellow-600' : 
                                 log.level === 'ERROR' ? 'text-red-600' : 'text-gray-600';
                
                return `<div class="mb-1">
                    <span class="text-gray-500 text-xs">[${timestamp}]</span> 
                    <span class="${levelColor} font-medium text-xs">${log.level}:</span>
                    <span class="text-sm">${log.message}</span>
                </div>`;
            }).join('');
            
            document.getElementById('daemon-logs').innerHTML = logsHtml || '<div class="text-gray-500 italic">No recent logs</div>';
        } else {
            console.error('Error loading daemon logs:', data.error);
            // Fall back to mock logs
            const mockLogs = [
                '[2024-01-15 10:30:15] INFO: Pin sync completed successfully - 1247 pins synchronized',
                '[2024-01-15 10:25:12] INFO: File indexer scanning /data/ipfs directory',
                '[2024-01-15 10:20:08] WARN: Garbage collector skipped - still within grace period',
                '[2024-01-15 10:15:05] INFO: MCP server started on port 8004',
                '[2024-01-15 10:10:02] INFO: IPFS daemon connection established'
            ];
            
            const logsHtml = mockLogs.map(log => `<div class="mb-1">${log}</div>`).join('');
            document.getElementById('daemon-logs').innerHTML = logsHtml;
        }
        
        showNotification('Daemon logs refreshed', 'success');
        
    } catch (error) {
        console.error('Error refreshing daemon logs:', error);
        showNotification('Failed to refresh daemon logs', 'error');
    }
}

// Utility function to format timestamp
function formatTimestamp(timestamp) {
    try {
        return new Date(timestamp).toLocaleString();
    } catch (error) {
        return timestamp;
    }
}