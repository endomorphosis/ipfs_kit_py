// Pin Management Dashboard JavaScript
class PinDashboard {
    constructor() {
        this.init();
        this.setupEventListeners();
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
        try {
            const response = await fetch('/api/jsonrpc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: method,
                    params: params,
                    id: this.jsonrpcId++
                })
            });
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error.message || 'Unknown error');
            }
            return data.result;
        } catch (error) {
            console.error('JSON-RPC call failed:', error);
            this.showNotification('Error: ' + error.message, 'error');
            throw error;
        }
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