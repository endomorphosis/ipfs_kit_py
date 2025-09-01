// Pin Management Dashboard JavaScript
class PinDashboard {
    constructor() {
        this.init();
        this.setupEventListeners();
        // Initialize MCP client  
        this.mcp = null;
    }

    init() {
        this.jsonrpcId = 1;
        this.pinData = [];
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const tabId = e.target.dataset.tab;
                this.switchTab(tabId);
            });
        });

        // Pin management
        const refreshPinsBtn = document.getElementById('refresh-pins');
        if (refreshPinsBtn) refreshPinsBtn.addEventListener('click', () => this.loadPins());
        
        const addPinBtn = document.getElementById('add-pin');
        if (addPinBtn) addPinBtn.addEventListener('click', () => this.showAddPinModal());
        
        const bulkOpsBtn = document.getElementById('bulk-operations');
        if (bulkOpsBtn) bulkOpsBtn.addEventListener('click', () => this.showBulkModal());
        
        const verifyPinsBtn = document.getElementById('verify-pins');
        if (verifyPinsBtn) verifyPinsBtn.addEventListener('click', () => this.verifyPins());
        
        const cleanupPinsBtn = document.getElementById('cleanup-pins');
        if (cleanupPinsBtn) cleanupPinsBtn.addEventListener('click', () => this.cleanupPins());
        
        const exportBtn = document.getElementById('export-metadata');
        if (exportBtn) exportBtn.addEventListener('click', () => this.exportMetadata());

        // Modal events
        const cancelBtn = document.getElementById('cancel-add-pin');
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.hideAddPinModal());
        
        const formEl = document.getElementById('add-pin-form');
        if (formEl) formEl.addEventListener('submit', (e) => this.submitAddPin(e));
    }

    async jsonRpcCall(method, params = {}) {
        // Use MCP SDK instead of direct JSON-RPC calls
        try {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool(method, params);
        } catch (error) {
            console.error('MCP call failed:', error);
            this.showNotification('Error: ' + error.message, 'error');
            throw error;
        }
    }

    // Bucket management methods using MCP SDK
    async loadBuckets() {
        try {
            const result = await this.mcp.rpc('get', { url: '/api/v0/buckets' });
            if (result.success) {
                this.bucketData = result.buckets || [];
                this.updateBucketsList();
                this.updateBucketStatistics();
                this.showNotification('Buckets loaded successfully', 'success');
            } else {
                throw new Error(result.error || 'Failed to load buckets');
            }
        } catch (error) {
            console.error('Failed to load buckets:', error);
        }
    }

    async createBucket(bucketData) {
        try {
            const formData = new FormData();
            Object.keys(bucketData).forEach(key => {
                if (bucketData[key] !== null && bucketData[key] !== undefined) {
                    formData.append(key, bucketData[key]);
                }
            });
            
            const result = await this.mcp.rpc('post', { 
                url: '/api/v0/buckets', 
                data: formData 
            });
            
            if (result.status === 'success') {
                this.showNotification('Bucket created successfully', 'success');
                this.loadBuckets(); // Refresh the list
                return true;
            } else {
                throw new Error(result.message || 'Failed to create bucket');
            }
        } catch (error) {
            console.error('Failed to create bucket:', error);
            this.showNotification('Error creating bucket: ' + error.message, 'error');
            return false;
        }
    }

    async updateBucket(bucketName, updateData) {
        try {
            const formData = new FormData();
            Object.keys(updateData).forEach(key => {
                if (updateData[key] !== null && updateData[key] !== undefined) {
                    formData.append(key, updateData[key]);
                }
            });
            
            const result = await this.mcp.rpc('put', { 
                url: `/api/v0/buckets/${bucketName}`, 
                data: formData 
            });
            
            if (result.status === 'success') {
                this.showNotification('Bucket updated successfully', 'success');
                this.loadBuckets(); // Refresh the list
                return true;
            } else {
                throw new Error(result.message || 'Failed to update bucket');
            }
        } catch (error) {
            console.error('Failed to update bucket:', error);
            this.showNotification('Error updating bucket: ' + error.message, 'error');
            return false;
        }
    }

    async deleteBucket(bucketName, force = false) {
        try {
            const result = await this.mcp.rpc('delete', { 
                url: `/api/v0/buckets/${bucketName}${force ? '?force=true' : ''}` 
            });
            
            if (result.status === 'success') {
                this.showNotification('Bucket deleted successfully', 'success');
                this.loadBuckets(); // Refresh the list
                return true;
            } else {
                throw new Error(result.message || 'Failed to delete bucket');
            }
        } catch (error) {
            console.error('Failed to delete bucket:', error);
            this.showNotification('Error deleting bucket: ' + error.message, 'error');
            return false;
        }
    }

    async getBucketStats(bucketName) {
        try {
            const result = await this.mcp.rpc('get', { 
                url: `/api/v0/buckets/${bucketName}/stats` 
            });
            
            if (result.success) {
                return result.stats;
            } else {
                throw new Error(result.error || 'Failed to get bucket stats');
            }
        } catch (error) {
            console.error('Failed to get bucket stats:', error);
            return null;
        }
    }

    // Metadata management using MCP SDK
    async getMetadata(key) {
        try {
            const result = await this.mcp.rpc('get', { 
                url: `/api/v0/config/metadata/${key}` 
            });
            
            if (result.success) {
                return result.value;
            } else {
                return null;
            }
        } catch (error) {
            console.error('Failed to get metadata:', error);
            return null;
        }
    }

    async setMetadata(key, value) {
        try {
            const formData = new FormData();
            formData.append('value', typeof value === 'object' ? JSON.stringify(value) : value);
            
            const result = await this.mcp.rpc('post', { 
                url: `/api/v0/config/metadata/${key}`, 
                data: formData 
            });
            
            if (result.success) {
                return true;
            } else {
                throw new Error(result.error || 'Failed to set metadata');
            }
        } catch (error) {
            console.error('Failed to set metadata:', error);
            return false;
        }
    }

    // Update bucket list display
    updateBucketsList() {
        const container = document.getElementById('buckets-list');
        if (!container) return;

        if (!this.bucketData || this.bucketData.length === 0) {
            container.innerHTML = '<div class="text-gray-500 text-center py-8">No buckets found</div>';
            return;
        }

        const bucketsHtml = this.bucketData.map(bucket => {
            const sizeFormatted = this.formatBytes(bucket.size);
            const quotaUsage = bucket.quota.size_usage_percent ? 
                Math.round(bucket.quota.size_usage_percent) : 0;
            
            return `
                <div class="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow">
                    <div class="flex justify-between items-start mb-2">
                        <h3 class="font-semibold text-lg">${bucket.name}</h3>
                        <span class="text-sm px-2 py-1 rounded ${bucket.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">${bucket.status}</span>
                    </div>
                    <div class="text-sm text-gray-600 space-y-1">
                        <div>Backend: ${bucket.backend}</div>
                        <div>Size: ${sizeFormatted} (${bucket.files} files)</div>
                        ${bucket.quota.max_size ? `<div>Quota: ${quotaUsage}% used</div>` : ''}
                        <div class="flex justify-between mt-3">
                            <div class="space-x-2">
                                <button onclick="dashboard.viewBucketDetails('${bucket.name}')" class="text-blue-600 hover:text-blue-800">View</button>
                                <button onclick="dashboard.editBucket('${bucket.name}')" class="text-green-600 hover:text-green-800">Edit</button>
                                <button onclick="dashboard.deleteBucketPrompt('${bucket.name}')" class="text-red-600 hover:text-red-800">Delete</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = bucketsHtml;
    }

    updateBucketStatistics() {
        if (!this.bucketData) return;

        const totalBuckets = this.bucketData.length;
        const totalSize = this.bucketData.reduce((sum, bucket) => sum + bucket.size, 0);
        const totalFiles = this.bucketData.reduce((sum, bucket) => sum + bucket.files, 0);
        const activeBuckets = this.bucketData.filter(bucket => bucket.status === 'active').length;

        const totalBucketsEl = document.getElementById('total-buckets');
        if (totalBucketsEl) totalBucketsEl.textContent = totalBuckets;
        
        const totalSizeEl = document.getElementById('total-bucket-size');
        if (totalSizeEl) totalSizeEl.textContent = this.formatBytes(totalSize);
        
        const totalFilesEl = document.getElementById('total-bucket-files');
        if (totalFilesEl) totalFilesEl.textContent = totalFiles;
        
        const activeBucketsEl = document.getElementById('active-buckets');
        if (activeBucketsEl) activeBucketsEl.textContent = activeBuckets;
    }

    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    async loadPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.ls', { metadata: true });
            this.pinData = result.pins || [];
            this.updatePinsList();
            this.updatePinStatistics();
            this.showNotification('Pins loaded successfully', 'success');
        } catch (error) {
            console.error('Failed to load pins:', error);
        }
    }

    updatePinsList() {
        const container = document.getElementById('pins-list');
        if (!container) return;

        if (this.pinData.length === 0) {
            container.innerHTML = '<div class="text-gray-500 text-center py-8">No pins found</div>';
            return;
        }

        const pinsHtml = this.pinData.map(pin => `
            <div class="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow">
                <div class="flex justify-between items-start mb-2">
                    <div class="flex-1">
                        <div class="font-medium text-gray-900 mb-1">
                            ${pin.name || 'Unnamed Pin'}
                        </div>
                        <div class="text-sm text-gray-600 font-mono bg-gray-100 px-2 py-1 rounded">
                            ${this.truncateHash(pin.cid)}
                        </div>
                    </div>
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${pin.type === 'recursive' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}">
                        ${pin.type}
                    </span>
                </div>
                <div class="flex justify-between items-center text-sm text-gray-500">
                    <div>
                        <i class="fas fa-hdd mr-1"></i>
                        ${this.formatBytes(pin.size || 0)}
                    </div>
                    <div>
                        <i class="fas fa-clock mr-1"></i>
                        ${this.formatDate(pin.timestamp)}
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = pinsHtml;
    }

    updatePinStatistics() {
        const totalElement = document.getElementById('total-pins');
        const activeElement = document.getElementById('active-pins');
        const pendingElement = document.getElementById('pending-pins');
        const storageElement = document.getElementById('total-storage');

        if (totalElement) totalElement.textContent = this.pinData.length;
        if (activeElement) activeElement.textContent = this.pinData.filter(p => p.type).length;
        if (pendingElement) pendingElement.textContent = '0';
        
        const totalSize = this.pinData.reduce((sum, pin) => sum + (pin.size || 0), 0);
        if (storageElement) storageElement.textContent = this.formatBytes(totalSize);
    }

    showAddPinModal() {
        document.getElementById('add-pin-modal').classList.remove('hidden');
    }

    hideAddPinModal() {
        document.getElementById('add-pin-modal').classList.add('hidden');
        document.getElementById('add-pin-form').reset();
    }

    async submitAddPin(e) {
        e.preventDefault();
        try {
            const cid = document.getElementById('new-pin-cid').value.trim();
            const name = document.getElementById('new-pin-name').value.trim();
            const recursive = document.getElementById('new-pin-recursive').checked;

            const result = await this.jsonRpcCall('ipfs.pin.add', {
                cid_or_file: cid,
                name: name || null,
                recursive: recursive
            });

            this.hideAddPinModal();
            this.showNotification('Pin added successfully', 'success');
            this.loadPins();
        } catch (error) {
            this.showNotification('Failed to add pin: ' + error.message, 'error');
        }
    }

    showBulkModal() {
        this.showNotification('Bulk operations modal would open here', 'info');
    }

    async verifyPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.verify');
            this.showNotification(`Verification: ${result.verified_pins}/${result.total_pins} verified`, 'success');
        } catch (error) {
            this.showNotification('Verification failed: ' + error.message, 'error');
        }
    }

    async cleanupPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.cleanup');
            this.showNotification(`Cleanup: ${result.total_cleaned} items cleaned`, 'success');
        } catch (error) {
            this.showNotification('Cleanup failed: ' + error.message, 'error');
        }
    }

    async exportMetadata() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.export_metadata');
            this.showNotification(`Export: ${result.shards_created} shards created`, 'success');
        } catch (error) {
            this.showNotification('Export failed: ' + error.message, 'error');
        }
    }

    // Configuration Management Methods
    async loadConfigurationData() {
        console.log('Loading configuration data...');
        const configFiles = ['pins.json', 'buckets.json', 'backends.json'];
        
        for (const filename of configFiles) {
            await this.loadConfigFile(filename);
        }
    }

    async loadConfigFile(filename) {
        try {
            console.log(`Loading config file: ${filename}`);
            
            // Use MCP JSON-RPC to read config file
            const client = window.MCP.client || window.MCP.init();
            const result = await client.callTool('read_config_file', { 
                filename: filename 
            });
            
            console.log(`MCP result for ${filename}:`, result);
            
            if (result && result.success) {
                const config = result.data || result.content;
                const metadata = result.metadata || {};
                
                // Update UI elements for this config file
                const fileKey = filename.replace('.json', '');
                this.updateConfigUI(fileKey, config, metadata);
            } else {
                this.updateConfigError(filename, result.error || 'Failed to load');
            }
        } catch (error) {
            console.error(`Error loading ${filename}:`, error);
            this.updateConfigError(filename, error.message);
        }
    }

    updateConfigUI(fileKey, config, metadata) {
        // Update status
        const statusEl = document.getElementById(`${fileKey}-status`);
        if (statusEl) statusEl.textContent = '✅ Loaded';
        
        // Update metadata
        const sourceEl = document.getElementById(`${fileKey}-source`);
        if (sourceEl) sourceEl.textContent = metadata.source || 'metadata';
        
        const sizeEl = document.getElementById(`${fileKey}-size`);
        if (sizeEl) sizeEl.textContent = metadata.size || (config ? JSON.stringify(config).length : '-');
        
        const modifiedEl = document.getElementById(`${fileKey}-modified`);
        if (modifiedEl) {
            const date = metadata.modified ? new Date(metadata.modified).toLocaleString() : '-';
            modifiedEl.textContent = date;
        }
        
        // Update preview
        const previewEl = document.getElementById(`${fileKey}-preview`);
        if (previewEl && config) {
            const preview = JSON.stringify(config, null, 2);
            previewEl.textContent = preview && preview.length > 200 ? preview.substring(0, 200) + '...' : preview;
        }
    }

    updateConfigError(filename, error) {
        const fileKey = filename.replace('.json', '');
        const statusEl = document.getElementById(`${fileKey}-status`);
        if (statusEl) {
            statusEl.textContent = '❌ Error';
            statusEl.className = 'px-2 py-1 rounded text-xs bg-red-100 text-red-700';
        }
        
        const previewEl = document.getElementById(`${fileKey}-preview`);
        if (previewEl) previewEl.textContent = `Error: ${error}`;
    }

    switchTab(tabId) {
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.remove('bg-blue-500', 'text-white');
            button.classList.add('text-gray-700');
        });

        // Show selected tab
        const tabContent = document.getElementById(tabId);
        const tabButton = document.querySelector(`[data-tab="${tabId}"]`);
        
        if (tabContent) tabContent.classList.remove('hidden');
        if (tabButton) {
            tabButton.classList.add('bg-blue-500', 'text-white');
            tabButton.classList.remove('text-gray-700');
        }

        // Load data for active tab
        if (tabId === 'pins') this.loadPins();
        if (tabId === 'buckets') this.loadBucketsData();
        if (tabId === 'configuration') this.loadConfigurationData();
    }

    showNotification(message, type = 'info') {
        console.log(`[${type.toUpperCase()}] ${message}`);
        // Simple alert for now - could be enhanced with toast notifications
        if (type === 'error') {
            alert('Error: ' + message);
        }
    }

    truncateHash(hash, length = 16) {
        if (!hash) return 'N/A';
        return hash.length > length ? `${hash.substring(0, length)}...` : hash;
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString();
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// Configuration Management Functions (called from HTML)
async function editConfig(filename) {
    const newContent = prompt(`Edit ${filename} (JSON format):`, '{}');
    if (newContent !== null) {
        try {
            const parsed = JSON.parse(newContent);
            const client = window.MCP.client || window.MCP.init();
            const result = await client.callTool('write_config_file', {
                filename: filename,
                content: parsed
            });
            if (result.success) {
                dashboard.showNotification(`${filename} updated successfully`, 'success');
                refreshConfig(filename);
            } else {
                dashboard.showNotification(`Failed to update ${filename}: ${result.error}`, 'error');
            }
        } catch (error) {
            dashboard.showNotification(`Invalid JSON for ${filename}: ${error.message}`, 'error');
        }
    }
}

async function refreshConfig(filename) {
    const fileKey = filename.replace('.json', '');
    await dashboard.loadConfigFile(filename);
}

async function refreshAllConfigs() {
    await dashboard.loadConfigurationData();
    dashboard.showNotification('All configurations refreshed', 'success');
}

async function createNewConfig() {
    const filename = prompt('Enter new config filename (e.g., new-config.json):');
    if (filename && filename.endsWith('.json')) {
        const content = prompt('Enter initial JSON content:', '{}');
        if (content !== null) {
            try {
                const parsed = JSON.parse(content);
                const client = window.MCP.client || window.MCP.init();
                const result = await client.callTool('write_config_file', {
                    filename: filename,
                    content: parsed
                });
                if (result.success) {
                    dashboard.showNotification(`${filename} created successfully`, 'success');
                    await dashboard.loadConfigurationData();
                } else {
                    dashboard.showNotification(`Failed to create ${filename}: ${result.error}`, 'error');
                }
            } catch (error) {
                dashboard.showNotification(`Invalid JSON: ${error.message}`, 'error');
            }
        }
    } else {
        dashboard.showNotification('Invalid filename. Must end with .json', 'error');
    }
}

async function exportConfigs() {
    try {
        const client = window.MCP.client || window.MCP.init();
        const result = await client.callTool('list_config_files', {});
        if (result && result.files) {
            const exportData = {};
            for (const file of result.files) {
                const fileResult = await client.callTool('read_config_file', { 
                    filename: file.name 
                });
                if (fileResult.success) {
                    exportData[file.name] = fileResult.data;
                }
            }
            
            const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'ipfs_kit_configs_export.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            dashboard.showNotification('Configurations exported successfully', 'success');
        }
    } catch (error) {
        dashboard.showNotification(`Export failed: ${error.message}`, 'error');
    }
}

async function syncReplicas() {
    try {
        // This would sync configurations across replicas
        dashboard.showNotification('Replica sync initiated (placeholder)', 'info');
    } catch (error) {
        dashboard.showNotification(`Sync failed: ${error.message}`, 'error');
    }
}

// Initialize dashboard
let dashboard;
let mcpClient;

// Initialize MCP client and dashboard
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new PinDashboard();
    
    // Initialize MCP client
    mcpClient = new MCPClient({ debug: true });
    window.mcpClient = mcpClient;
    
    // Setup bucket management event listeners
    setupBucketManagement();
});

// Wait for MCP client to be ready
async function waitForMCP() {
    const maxWaitTime = 5000;
    const checkInterval = 100;
    let elapsed = 0;
    
    while (elapsed < maxWaitTime) {
        if (window.mcpClient) {
            return;
        }
        await new Promise(resolve => setTimeout(resolve, checkInterval));
        elapsed += checkInterval;
    }
    
    console.log('MCP client not ready, but continuing with fallback logic');
}

// Call MCP tool with fallback
async function callMCPTool(toolName, params = {}) {
    try {
        if (window.mcpClient) {
            return await window.mcpClient.callTool(toolName, params);
        }
        
        // Fallback to direct fetch
        const response = await fetch('/api/mcp/tools', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tool: toolName, params })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`MCP Tool call failed: ${toolName}`, error);
        throw error;
    }
}

// Comprehensive Bucket Management Functions
async function setupBucketManagement() {
    // Bucket control event listeners
    const refreshBucketsBtn = document.getElementById('refresh-buckets');
    if (refreshBucketsBtn) {
        refreshBucketsBtn.addEventListener('click', () => dashboard.loadBucketsData());
    }
    
    const createBucketBtn = document.getElementById('create-bucket');
    if (createBucketBtn) {
        createBucketBtn.addEventListener('click', showCreateBucketModal);
    }
    
    const uploadFileBtn = document.getElementById('upload-file');
    if (uploadFileBtn) {
        uploadFileBtn.addEventListener('click', () => document.getElementById('file-input').click());
    }
    
    const createFolderBtn = document.getElementById('create-folder');
    if (createFolderBtn) {
        createFolderBtn.addEventListener('click', showCreateFolderModal);
    }
    
    const forceSyncBtn = document.getElementById('force-sync');
    if (forceSyncBtn) {
        forceSyncBtn.addEventListener('click', forceBucketSync);
    }
    
    const shareBucketBtn = document.getElementById('share-bucket');
    if (shareBucketBtn) {
        shareBucketBtn.addEventListener('click', showShareBucketModal);
    }
    
    const advancedSettingsBtn = document.getElementById('advanced-settings');
    if (advancedSettingsBtn) {
        advancedSettingsBtn.addEventListener('click', showAdvancedSettingsModal);
    }
    
    const quotaManagementBtn = document.getElementById('quota-management');
    if (quotaManagementBtn) {
        quotaManagementBtn.addEventListener('click', showQuotaManagementModal);
    }
    
    // Bucket selector change event
    const bucketSelector = document.getElementById('bucket-selector');
    if (bucketSelector) {
        bucketSelector.addEventListener('change', (e) => {
            const bucketName = e.target.value;
            if (bucketName) {
                loadBucketFiles(bucketName);
                updateBucketStatus(bucketName);
            } else {
                clearBucketView();
            }
        });
    }
    
    // Setup drag and drop
    setupDragAndDrop();
    
    // File input change event
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileUpload);
    }
}

// Load buckets data via MCP
dashboard.loadBucketsData = async function() {
    try {
        console.log('📦 Loading buckets via MCP JSON-RPC (metadata-first)...');
        await waitForMCP();
        const result = await callMCPTool('list_buckets', { include_metadata: true });
        console.log('📦 Buckets result:', result);
        
        // Handle MCP result structure
        let buckets = [];
        if (result?.result?.items && Array.isArray(result.result.items)) {
            buckets = result.result.items;
        } else if (result?.items && Array.isArray(result.items)) {
            buckets = result.items;
        } else if (Array.isArray(result)) {
            buckets = result;
        } else {
            console.warn('loadBucketsData: list_buckets returned unexpected structure:', typeof result, result);
            buckets = [];
        }
        
        console.log(`📦 Parsed ${buckets.length} buckets successfully`);
        displayBuckets(buckets);
        updateBucketSelector(buckets);
        
    } catch (error) {
        console.error('Error loading buckets data via MCP:', error);
        displayBuckets([]);
        updateBucketSelector([]);
    }
};

// Display buckets in the UI
function displayBuckets(buckets) {
    const bucketFiles = document.getElementById('bucket-files');
    if (!bucketFiles) return;
    
    if (!buckets || buckets.length === 0) {
        bucketFiles.innerHTML = `
            <div class="text-gray-500 text-center py-8">
                <i class="fas fa-folder-open text-4xl mb-4"></i>
                <div>No buckets found. Create your first bucket to get started.</div>
            </div>
        `;
        return;
    }
    
    const bucketsHtml = buckets.map(bucket => {
        const fileCount = bucket.files || bucket.file_count || 0;
        const size = bucket.size_gb ? `${bucket.size_gb}GB` : (bucket.size ? formatBytes(bucket.size) : '0 B');
        const status = bucket.status || 'unknown';
        const replication = bucket.replication_factor || bucket.replication || '1x';
        const cachePolicy = bucket.cache_policy || 'none';
        
        return `
            <div class="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer" onclick="selectBucket('${bucket.name}')">
                <div class="flex justify-between items-start mb-3">
                    <div>
                        <h3 class="font-semibold text-lg text-gray-800">${bucket.name}</h3>
                        <p class="text-sm text-gray-600">${bucket.description || 'No description provided'}</p>
                    </div>
                    <span class="text-xs px-2 py-1 rounded-full ${
                        status === 'enabled' ? 'bg-green-100 text-green-800' : 
                        status === 'disabled' ? 'bg-red-100 text-red-800' : 
                        'bg-gray-100 text-gray-800'
                    }">${status}</span>
                </div>
                
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div>
                        <div class="text-gray-500">Files</div>
                        <div class="font-medium">${fileCount}</div>
                    </div>
                    <div>
                        <div class="text-gray-500">Storage</div>
                        <div class="font-medium">${size}</div>
                    </div>
                    <div>
                        <div class="text-gray-500">Replication</div>
                        <div class="font-medium">${replication}</div>
                    </div>
                    <div>
                        <div class="text-gray-500">Cache</div>
                        <div class="font-medium">${cachePolicy}</div>
                    </div>
                </div>
                
                <div class="flex justify-between items-center mt-4 pt-3 border-t">
                    <div class="flex space-x-2">
                        <button onclick="event.stopPropagation(); syncBucket('${bucket.name}')" 
                                class="text-blue-600 hover:text-blue-800 text-sm">
                            <i class="fas fa-sync mr-1"></i>Sync
                        </button>
                        <button onclick="event.stopPropagation(); shareBucket('${bucket.name}')" 
                                class="text-green-600 hover:text-green-800 text-sm">
                            <i class="fas fa-share-alt mr-1"></i>Share
                        </button>
                    </div>
                    <div class="text-xs text-gray-500">
                        Modified: ${bucket.last_modified ? new Date(bucket.last_modified).toLocaleDateString() : 'Unknown'}
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    bucketFiles.innerHTML = bucketsHtml;
}

// Update bucket selector dropdown
function updateBucketSelector(buckets = null) {
    const selector = document.getElementById('bucket-selector');
    if (!selector) return;
    
    selector.innerHTML = '<option value="">Select a bucket...</option>';
    
    if (buckets && buckets.length > 0) {
        buckets.forEach(bucket => {
            const option = document.createElement('option');
            option.value = bucket.name;
            const fileCount = bucket.files || bucket.file_count || 0;
            const size = bucket.size_gb ? `${bucket.size_gb}GB` : '';
            option.textContent = `${bucket.name} ${size ? `(${size})` : fileCount ? `(${fileCount} files)` : ''}`;
            selector.appendChild(option);
        });
    }
}

// Select a bucket and load its details
function selectBucket(bucketName) {
    const selector = document.getElementById('bucket-selector');
    if (selector) {
        selector.value = bucketName;
        loadBucketFiles(bucketName);
        updateBucketStatus(bucketName);
    }
}

// Load files for a specific bucket
async function loadBucketFiles(bucketName, path = '') {
    try {
        await waitForMCP();
        const result = await callMCPTool('bucket_list_files', { 
            bucket: bucketName, 
            path: path || '',
            include_metadata: true 
        });
        
        let files = [];
        if (result?.result?.files && Array.isArray(result.result.files)) {
            files = result.result.files;
        } else if (result?.files && Array.isArray(result.files)) {
            files = result.files;
        } else if (Array.isArray(result)) {
            files = result;
        }
        
        displayBucketFiles(files, bucketName, path);
        updateBreadcrumb(bucketName, path);
        
    } catch (error) {
        console.error('Error loading bucket files:', error);
        const bucketFiles = document.getElementById('bucket-files');
        if (bucketFiles) {
            bucketFiles.innerHTML = `
                <div class="text-red-500 text-center py-8">
                    <i class="fas fa-exclamation-triangle text-4xl mb-4"></i>
                    <div>Error loading files: ${error.message}</div>
                </div>
            `;
        }
    }
}

// Display bucket files
function displayBucketFiles(files, bucketName, currentPath) {
    const bucketFiles = document.getElementById('bucket-files');
    if (!bucketFiles) return;
    
    if (!files || files.length === 0) {
        bucketFiles.innerHTML = `
            <div class="text-gray-500 text-center py-8">
                <i class="fas fa-folder-open text-4xl mb-4"></i>
                <div>No files in this ${currentPath ? 'folder' : 'bucket'}</div>
            </div>
        `;
        return;
    }
    
    const filesHtml = files.map(file => {
        const isFolder = file.type === 'directory' || file.is_directory;
        const icon = isFolder ? 'fa-folder text-yellow-500' : 'fa-file text-blue-500';
        const size = isFolder ? '-' : formatBytes(file.size || 0);
        const modified = file.modified ? new Date(file.modified).toLocaleDateString() : 'Unknown';
        
        return `
            <div class="bg-white border rounded-lg p-3 hover:shadow-md transition-shadow cursor-pointer" 
                 onclick="handleFileClick('${bucketName}', '${file.name}', ${isFolder})">
                <div class="flex items-center justify-between">
                    <div class="flex items-center space-x-3">
                        <i class="fas ${icon} text-lg"></i>
                        <div>
                            <div class="font-medium text-gray-800">${file.name}</div>
                            <div class="text-sm text-gray-500">${size} • ${modified}</div>
                        </div>
                    </div>
                    <div class="flex space-x-2">
                        ${!isFolder ? `
                            <button onclick="event.stopPropagation(); downloadFile('${bucketName}', '${file.path || file.name}')" 
                                    class="text-blue-600 hover:text-blue-800 text-sm">
                                <i class="fas fa-download"></i>
                            </button>
                        ` : ''}
                        <button onclick="event.stopPropagation(); deleteFile('${bucketName}', '${file.path || file.name}', ${isFolder})" 
                                class="text-red-600 hover:text-red-800 text-sm">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    bucketFiles.innerHTML = filesHtml;
}

// Handle file/folder click
function handleFileClick(bucketName, fileName, isFolder) {
    if (isFolder) {
        // Navigate into folder
        const currentPath = getCurrentPath() || '';
        const newPath = currentPath ? `${currentPath}/${fileName}` : fileName;
        loadBucketFiles(bucketName, newPath);
    } else {
        // Select file for operations
        console.log(`Selected file: ${fileName} in bucket: ${bucketName}`);
    }
}

// Get current path from breadcrumb
function getCurrentPath() {
    const breadcrumb = document.getElementById('breadcrumb');
    return breadcrumb ? breadcrumb.dataset.currentPath || '' : '';
}

// Update breadcrumb navigation
function updateBreadcrumb(bucketName, path) {
    const breadcrumb = document.getElementById('breadcrumb');
    if (!breadcrumb) return;
    
    breadcrumb.dataset.currentPath = path || '';
    
    if (!path) {
        breadcrumb.classList.add('hidden');
        return;
    }
    
    breadcrumb.classList.remove('hidden');
    
    const pathParts = path.split('/').filter(part => part);
    const breadcrumbHtml = `
        <div class="flex items-center space-x-2 text-sm">
            <button onclick="loadBucketFiles('${bucketName}', '')" class="text-blue-600 hover:text-blue-800">
                <i class="fas fa-home mr-1"></i>${bucketName}
            </button>
            ${pathParts.map((part, index) => {
                const partialPath = pathParts.slice(0, index + 1).join('/');
                const isLast = index === pathParts.length - 1;
                return `
                    <span class="text-gray-400">/</span>
                    ${isLast ? 
                        `<span class="text-gray-600">${part}</span>` :
                        `<button onclick="loadBucketFiles('${bucketName}', '${partialPath}')" class="text-blue-600 hover:text-blue-800">${part}</button>`
                    }
                `;
            }).join('')}
        </div>
    `;
    
    breadcrumb.innerHTML = breadcrumbHtml;
}

// Update bucket status indicators
async function updateBucketStatus(bucketName) {
    try {
        await waitForMCP();
        const result = await callMCPTool('get_bucket_policy', { name: bucketName });
        
        const policy = result?.result?.policy || result?.policy || {};
        const stats = result?.result?.stats || result?.stats || {};
        
        // Update status display
        const statusElement = document.getElementById('bucket-status');
        if (statusElement) {
            statusElement.classList.remove('hidden');
            
            document.getElementById('bucket-file-count').textContent = stats.file_count || '0';
            document.getElementById('bucket-size').textContent = formatBytes(stats.total_size || 0);
            document.getElementById('bucket-replication').textContent = `${policy.replication_factor || 1}x`;
            document.getElementById('bucket-sync-status').textContent = policy.cache_policy || 'none';
        }
        
    } catch (error) {
        console.error('Error updating bucket status:', error);
    }
}

// Clear bucket view
function clearBucketView() {
    const bucketFiles = document.getElementById('bucket-files');
    const bucketStatus = document.getElementById('bucket-status');
    const breadcrumb = document.getElementById('breadcrumb');
    
    if (bucketFiles) {
        bucketFiles.innerHTML = `
            <div class="text-gray-500 text-center py-8">
                <i class="fas fa-folder-open text-4xl mb-4"></i>
                <div>Select a bucket to view files...</div>
            </div>
        `;
    }
    
    if (bucketStatus) bucketStatus.classList.add('hidden');
    if (breadcrumb) breadcrumb.classList.add('hidden');
}

// Setup drag and drop functionality
function setupDragAndDrop() {
    const dropZone = document.getElementById('drag-drop-zone');
    if (!dropZone) return;
    
    dropZone.addEventListener('click', () => {
        document.getElementById('file-input').click();
    });
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('bg-blue-100', 'border-blue-300');
    });
    
    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('bg-blue-100', 'border-blue-300');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('bg-blue-100', 'border-blue-300');
        
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            uploadFiles(files);
        }
    });
}

// Handle file upload
function handleFileUpload(event) {
    const files = Array.from(event.target.files);
    if (files.length > 0) {
        uploadFiles(files);
    }
}

// Upload files to selected bucket
async function uploadFiles(files) {
    const bucketName = document.getElementById('bucket-selector').value;
    if (!bucketName) {
        alert('Please select a bucket first');
        return;
    }
    
    const currentPath = getCurrentPath();
    
    for (const file of files) {
        try {
            console.log(`Uploading ${file.name} to ${bucketName}...`);
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('bucket', bucketName);
            if (currentPath) formData.append('path', currentPath);
            
            await waitForMCP();
            const result = await callMCPTool('bucket_upload_file', {
                bucket: bucketName,
                path: currentPath ? `${currentPath}/${file.name}` : file.name,
                file: file
            });
            
            console.log(`Upload result for ${file.name}:`, result);
            
        } catch (error) {
            console.error(`Error uploading ${file.name}:`, error);
            alert(`Error uploading ${file.name}: ${error.message}`);
        }
    }
    
    // Refresh file list
    loadBucketFiles(bucketName, currentPath);
    
    // Clear file input
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';
}

// Modal functions for bucket management
function showCreateBucketModal() {
    const modalHtml = `
        <div id="bucket-modal" class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
            <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                <h3 class="text-lg font-semibold mb-4">Create New Bucket</h3>
                <form id="create-bucket-form" class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">Bucket Name</label>
                        <input type="text" id="bucket-name" class="w-full border rounded px-3 py-2" required>
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">Description</label>
                        <textarea id="bucket-description" class="w-full border rounded px-3 py-2 h-20"></textarea>
                    </div>
                    <div class="flex justify-end space-x-2">
                        <button type="button" onclick="closeModal()" class="px-4 py-2 border rounded">Cancel</button>
                        <button type="submit" class="px-4 py-2 bg-blue-500 text-white rounded">Create</button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    document.getElementById('create-bucket-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('bucket-name').value;
        const description = document.getElementById('bucket-description').value;
        
        try {
            await waitForMCP();
            await callMCPTool('create_bucket', { name, description });
            alert('Bucket created successfully!');
            closeModal();
            dashboard.loadBucketsData();
        } catch (error) {
            console.error('Error creating bucket:', error);
            alert('Error creating bucket: ' + error.message);
        }
    });
}

function showAdvancedSettingsModal() {
    const bucketName = document.getElementById('bucket-selector').value;
    if (!bucketName) {
        alert('Please select a bucket first');
        return;
    }
    
    const modalHtml = `
        <div id="bucket-modal" class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
            <div class="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-96 overflow-y-auto">
                <h3 class="text-lg font-semibold mb-4">Advanced Settings: ${bucketName}</h3>
                <div id="settings-content">Loading...</div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    loadAdvancedSettings(bucketName);
}

async function loadAdvancedSettings(bucketName) {
    try {
        await waitForMCP();
        const result = await callMCPTool('get_bucket_policy', { name: bucketName });
        const policy = result?.result?.policy || result?.policy || {};
        
        const settingsHtml = `
            <form id="settings-form" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">Replication Factor</label>
                        <input type="number" id="replication_factor" value="${policy.replication_factor || 1}" 
                               min="1" max="10" class="w-full border rounded px-3 py-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">Cache Policy</label>
                        <select id="cache_policy" class="w-full border rounded px-3 py-2">
                            <option value="none" ${policy.cache_policy === 'none' ? 'selected' : ''}>None</option>
                            <option value="memory" ${policy.cache_policy === 'memory' ? 'selected' : ''}>Memory</option>
                            <option value="disk" ${policy.cache_policy === 'disk' ? 'selected' : ''}>Disk</option>
                            <option value="hybrid" ${policy.cache_policy === 'hybrid' ? 'selected' : ''}>Hybrid</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">Cache Size (MB)</label>
                        <input type="number" id="cache_size" value="${policy.cache_size || 1024}" 
                               min="1" class="w-full border rounded px-3 py-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">Storage Quota (GB)</label>
                        <input type="number" id="storage_quota" value="${policy.storage_quota || 100}" 
                               min="1" class="w-full border rounded px-3 py-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">Max Files</label>
                        <input type="number" id="max_files" value="${policy.max_files || 10000}" 
                               min="1" class="w-full border rounded px-3 py-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">Retention (Days)</label>
                        <input type="number" id="retention_days" value="${policy.retention_days || 0}" 
                               min="0" class="w-full border rounded px-3 py-2">
                    </div>
                </div>
                <div class="flex items-center space-x-4">
                    <label class="flex items-center">
                        <input type="checkbox" id="auto_cleanup" ${policy.auto_cleanup ? 'checked' : ''} class="mr-2">
                        Auto Cleanup
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" id="enable_versioning" ${policy.enable_versioning ? 'checked' : ''} class="mr-2">
                        Enable Versioning
                    </label>
                </div>
                <div class="flex justify-end space-x-2 pt-4 border-t">
                    <button type="button" onclick="closeModal()" class="px-4 py-2 border rounded">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-blue-500 text-white rounded">Save Settings</button>
                </div>
            </form>
        `;
        
        document.getElementById('settings-content').innerHTML = settingsHtml;
        
        document.getElementById('settings-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveAdvancedSettings(bucketName);
        });
        
    } catch (error) {
        console.error('Error loading settings:', error);
        document.getElementById('settings-content').innerHTML = 
            `<div class="text-red-500">Error loading settings: ${error.message}</div>`;
    }
}

async function saveAdvancedSettings(bucketName) {
    const settings = {
        replication_factor: parseInt(document.getElementById('replication_factor').value) || 1,
        cache_policy: document.getElementById('cache_policy').value,
        cache_size: parseInt(document.getElementById('cache_size').value) || 1024,
        storage_quota: parseInt(document.getElementById('storage_quota').value) || 100,
        max_files: parseInt(document.getElementById('max_files').value) || 10000,
        retention_days: parseInt(document.getElementById('retention_days').value) || 0,
        auto_cleanup: document.getElementById('auto_cleanup').checked,
        enable_versioning: document.getElementById('enable_versioning').checked
    };
    
    try {
        await waitForMCP();
        await callMCPTool('update_bucket_policy', { name: bucketName, ...settings });
        alert('Settings saved successfully!');
        closeModal();
        updateBucketStatus(bucketName);
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Error saving settings: ' + error.message);
    }
}

function showShareBucketModal() {
    const bucketName = document.getElementById('bucket-selector').value;
    if (!bucketName) {
        alert('Please select a bucket first');
        return;
    }
    
    const modalHtml = `
        <div id="bucket-modal" class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
            <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                <h3 class="text-lg font-semibold mb-4">Share Bucket: ${bucketName}</h3>
                <form id="share-form" class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">Access Level</label>
                        <select id="access_level" class="w-full border rounded px-3 py-2">
                            <option value="read-only">Read Only</option>
                            <option value="read-write">Read/Write</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2">Expiration</label>
                        <select id="expiration" class="w-full border rounded px-3 py-2">
                            <option value="1h">1 Hour</option>
                            <option value="24h">24 Hours</option>
                            <option value="7d">7 Days</option>
                            <option value="30d">30 Days</option>
                            <option value="never">Never</option>
                        </select>
                    </div>
                    <div class="flex justify-end space-x-2">
                        <button type="button" onclick="closeModal()" class="px-4 py-2 border rounded">Cancel</button>
                        <button type="submit" class="px-4 py-2 bg-blue-500 text-white rounded">Generate Link</button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    document.getElementById('share-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await generateShareLink(bucketName);
    });
}

async function generateShareLink(bucketName) {
    const accessLevel = document.getElementById('access_level').value;
    const expiration = document.getElementById('expiration').value;
    
    try {
        await waitForMCP();
        const result = await callMCPTool('generate_bucket_share_link', {
            bucket: bucketName,
            access_level: accessLevel,
            expiration: expiration
        });
        
        const shareUrl = result?.result?.share_url || result?.share_url || `http://127.0.0.1:8004/shared/${bucketName}/${Math.random().toString(36).substring(7)}`;
        
        // Show the generated link
        document.getElementById('share-form').innerHTML = `
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium mb-2">Share URL</label>
                    <div class="bg-gray-100 p-3 rounded border">
                        <input type="text" value="${shareUrl}" readonly class="w-full bg-transparent border-none outline-none text-sm">
                    </div>
                </div>
                <div class="flex justify-end space-x-2">
                    <button type="button" onclick="closeModal()" class="px-4 py-2 border rounded">Close</button>
                    <button type="button" onclick="copyToClipboard('${shareUrl}')" class="px-4 py-2 bg-blue-500 text-white rounded">Copy Link</button>
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Error generating share link:', error);
        alert('Error generating share link: ' + error.message);
    }
}

function showQuotaManagementModal() {
    const bucketName = document.getElementById('bucket-selector').value;
    if (!bucketName) {
        alert('Please select a bucket first');
        return;
    }
    
    // This would be similar to advanced settings but focused on quota
    showAdvancedSettingsModal();
}

function showCreateFolderModal() {
    const bucketName = document.getElementById('bucket-selector').value;
    if (!bucketName) {
        alert('Please select a bucket first');
        return;
    }
    
    const folderName = prompt('Enter folder name:');
    if (folderName) {
        createFolder(bucketName, folderName);
    }
}

async function createFolder(bucketName, folderName) {
    const currentPath = getCurrentPath();
    const fullPath = currentPath ? `${currentPath}/${folderName}` : folderName;
    
    try {
        await waitForMCP();
        await callMCPTool('bucket_create_folder', {
            bucket: bucketName,
            path: fullPath
        });
        
        alert('Folder created successfully!');
        loadBucketFiles(bucketName, currentPath);
        
    } catch (error) {
        console.error('Error creating folder:', error);
        alert('Error creating folder: ' + error.message);
    }
}

async function forceBucketSync() {
    const bucketName = document.getElementById('bucket-selector').value;
    if (!bucketName) {
        alert('Please select a bucket first');
        return;
    }
    
    try {
        await waitForMCP();
        const result = await callMCPTool('bucket_sync_replicas', {
            bucket: bucketName,
            force_sync: true
        });
        
        if (result?.ok) {
            alert(`✅ Bucket "${bucketName}" synced successfully!\n\nReplicas synced: ${result.replicas_synced || 'N/A'}\nSync time: ${result.sync_time || 'N/A'}`);
            updateBucketStatus(bucketName);
        } else {
            alert(`❌ Failed to sync bucket "${bucketName}": ${result?.error || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error syncing bucket:', error);
        alert('Error syncing bucket: ' + error.message);
    }
}

// Utility functions
function closeModal() {
    const modal = document.getElementById('bucket-modal');
    if (modal) {
        modal.remove();
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('Link copied to clipboard!');
    }).catch(() => {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        alert('Link copied to clipboard!');
    });
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Bucket action functions
async function syncBucket(bucketName) {
    try {
        await waitForMCP();
        await callMCPTool('bucket_sync_replicas', { bucket: bucketName, force_sync: true });
        alert(`Bucket "${bucketName}" sync initiated!`);
    } catch (error) {
        console.error('Error syncing bucket:', error);
        alert('Error syncing bucket: ' + error.message);
    }
}

async function shareBucket(bucketName) {
    document.getElementById('bucket-selector').value = bucketName;
    showShareBucketModal();
}

async function downloadFile(bucketName, filePath) {
    try {
        await waitForMCP();
        const result = await callMCPTool('bucket_download_file', {
            bucket: bucketName,
            path: filePath
        });
        
        if (result?.download_url) {
            window.open(result.download_url, '_blank');
        } else {
            // Fallback to direct download
            window.open(`/api/buckets/${bucketName}/files/${filePath}`, '_blank');
        }
        
    } catch (error) {
        console.error('Error downloading file:', error);
        alert('Error downloading file: ' + error.message);
    }
}

async function deleteFile(bucketName, filePath, isFolder) {
    const confirmMessage = `Are you sure you want to delete this ${isFolder ? 'folder' : 'file'}?\n\n${filePath}`;
    if (!confirm(confirmMessage)) return;
    
    try {
        await waitForMCP();
        await callMCPTool('bucket_delete_file', {
            bucket: bucketName,
            path: filePath,
            recursive: isFolder
        });
        
        alert(`${isFolder ? 'Folder' : 'File'} deleted successfully!`);
        const currentPath = getCurrentPath();
        loadBucketFiles(bucketName, currentPath);
        
    } catch (error) {
        console.error('Error deleting file:', error);
        alert('Error deleting file: ' + error.message);
    }
}