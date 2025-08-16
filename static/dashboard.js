// Pin Management Dashboard JavaScript
class PinDashboard {
    constructor() {
        this.init();
        this.setupEventListeners();
        // Initialize MCP client
        this.mcp = new window.MCP.MCPClient({ baseUrl: '' });
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
        document.getElementById('refresh-pins')?.addEventListener('click', () => this.loadPins());
        document.getElementById('add-pin')?.addEventListener('click', () => this.showAddPinModal());
        document.getElementById('bulk-operations')?.addEventListener('click', () => this.showBulkModal());
        document.getElementById('verify-pins')?.addEventListener('click', () => this.verifyPins());
        document.getElementById('cleanup-pins')?.addEventListener('click', () => this.cleanupPins());
        document.getElementById('export-metadata')?.addEventListener('click', () => this.exportMetadata());

        // Modal events
        document.getElementById('cancel-add-pin')?.addEventListener('click', () => this.hideAddPinModal());
        document.getElementById('add-pin-form')?.addEventListener('submit', (e) => this.submitAddPin(e));
    }

    async jsonRpcCall(method, params = {}) {
        // Use MCP SDK instead of direct JSON-RPC calls
        try {
            return await this.mcp.rpc(method, params);
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

        document.getElementById('total-buckets')?.textContent = totalBuckets;
        document.getElementById('total-bucket-size')?.textContent = this.formatBytes(totalSize);
        document.getElementById('total-bucket-files')?.textContent = totalFiles;
        document.getElementById('active-buckets')?.textContent = activeBuckets;
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

// Initialize dashboard
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new PinDashboard();
});