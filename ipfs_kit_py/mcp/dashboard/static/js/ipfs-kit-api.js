/**
 * IPFS Kit Unified API Library
 * 
 * This library provides a unified interface for all dashboard API calls,
 * replacing direct MCP tool access with a consistent JavaScript API.
 */

class IPFSKitAPI {
    constructor(baseUrl = '', options = {}) {
        this.baseUrl = baseUrl;
        this.options = {
            timeout: 30000,
            retries: 3,
            retryDelay: 1000,
            ...options
        };
        this.cache = new Map();
        this.eventListeners = new Map();
    }

    /**
     * Make an HTTP request with error handling and retries
     */
    async _request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...options.headers
            },
            ...options
        };

        for (let attempt = 1; attempt <= this.options.retries; attempt++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), this.options.timeout);

                const response = await fetch(url, {
                    ...config,
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                return data;

            } catch (error) {
                console.warn(`Request attempt ${attempt} failed:`, error);
                
                if (attempt === this.options.retries) {
                    throw new Error(`Request failed after ${attempt} attempts: ${error.message}`);
                }

                // Wait before retry
                await new Promise(resolve => setTimeout(resolve, this.options.retryDelay * attempt));
            }
        }
    }

    /**
     * Get data with caching
     */
    async _getCached(endpoint, cacheKey, ttl = 30000) {
        const cached = this.cache.get(cacheKey);
        if (cached && Date.now() - cached.timestamp < ttl) {
            return cached.data;
        }

        const data = await this._request(endpoint);
        this.cache.set(cacheKey, {
            data,
            timestamp: Date.now()
        });

        return data;
    }

    /**
     * Clear cache
     */
    clearCache(key = null) {
        if (key) {
            this.cache.delete(key);
        } else {
            this.cache.clear();
        }
    }

    /**
     * Event handling
     */
    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
    }

    off(event, callback) {
        const listeners = this.eventListeners.get(event);
        if (listeners) {
            const index = listeners.indexOf(callback);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
    }

    emit(event, data) {
        const listeners = this.eventListeners.get(event) || [];
        listeners.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error(`Error in event listener for ${event}:`, error);
            }
        });
    }

    // ===================
    // OVERVIEW API
    // ===================

    async getOverview() {
        return await this._getCached('/api/overview', 'overview', 10000);
    }

    async getSystemStatus() {
        return await this._getCached('/api/system/status', 'system_status', 5000);
    }

    // ===================
    // SERVICES API  
    // ===================

    async getServices() {
        return await this._getCached('/api/services', 'services', 5000);
    }

    async startService(serviceName) {
        const data = await this._request(`/api/services/${serviceName}/start`, {
            method: 'POST'
        });
        this.clearCache('services');
        this.emit('serviceStarted', { service: serviceName, data });
        return data;
    }

    async stopService(serviceName) {
        const data = await this._request(`/api/services/${serviceName}/stop`, {
            method: 'POST'
        });
        this.clearCache('services');
        this.emit('serviceStopped', { service: serviceName, data });
        return data;
    }

    async restartService(serviceName) {
        const data = await this._request(`/api/services/${serviceName}/restart`, {
            method: 'POST'
        });
        this.clearCache('services');
        this.emit('serviceRestarted', { service: serviceName, data });
        return data;
    }

    // ===================
    // BACKENDS API
    // ===================

    async getBackends() {
        return await this._getCached('/api/backends', 'backends', 15000);
    }

    async getBackendTypes() {
        return await this._getCached('/api/backends/types', 'backend_types', 60000);
    }

    async getBackend(backendId) {
        return await this._request(`/api/backends/${backendId}`);
    }

    async createBackend(backendConfig) {
        const data = await this._request('/api/backends', {
            method: 'POST',
            body: JSON.stringify(backendConfig)
        });
        this.clearCache('backends');
        this.emit('backendCreated', { config: backendConfig, data });
        return data;
    }

    async updateBackend(backendId, config) {
        const data = await this._request(`/api/backends/${backendId}`, {
            method: 'PUT',
            body: JSON.stringify(config)
        });
        this.clearCache('backends');
        this.clearCache(`backend_${backendId}`);
        this.emit('backendUpdated', { id: backendId, config, data });
        return data;
    }

    async deleteBackend(backendId) {
        const data = await this._request(`/api/backends/${backendId}`, {
            method: 'DELETE'
        });
        this.clearCache('backends');
        this.clearCache(`backend_${backendId}`);
        this.emit('backendDeleted', { id: backendId, data });
        return data;
    }

    async testBackend(backendId) {
        const data = await this._request(`/api/backends/${backendId}/test`, {
            method: 'POST'
        });
        this.emit('backendTested', { id: backendId, data });
        return data;
    }

    async getBackendStats(backendId) {
        return await this._getCached(`/api/backends/${backendId}/stats`, `backend_stats_${backendId}`, 10000);
    }

    async getBackendHealth(backendId) {
        return await this._request(`/api/backends/${backendId}/health`);
    }

    // ===================
    // CONFIGURATION API
    // ===================

    async getConfig() {
        return await this._getCached('/api/config', 'config', 30000);
    }

    async updateConfig(config) {
        const data = await this._request('/api/config', {
            method: 'PUT',
            body: JSON.stringify(config)
        });
        this.clearCache('config');
        this.emit('configUpdated', { config, data });
        return data;
    }

    async getBackendConfig(backendId) {
        return await this._request(`/api/config/backends/${backendId}`);
    }

    async updateBackendConfig(backendId, config) {
        const data = await this._request(`/api/config/backends/${backendId}`, {
            method: 'PUT',
            body: JSON.stringify(config)
        });
        this.clearCache('config');
        this.clearCache('backends');
        this.emit('backendConfigUpdated', { id: backendId, config, data });
        return data;
    }

    // ===================
    // METRICS API
    // ===================

    async getMetrics() {
        return await this._getCached('/api/metrics', 'metrics', 5000);
    }

    async getBackendMetrics(backendId) {
        return await this._getCached(`/api/metrics/backends/${backendId}`, `backend_metrics_${backendId}`, 10000);
    }

    async getSystemMetrics() {
        return await this._getCached('/api/metrics/system', 'system_metrics', 5000);
    }

    // ===================
    // PINS API
    // ===================

    async getPins() {
        return await this._getCached('/api/pins', 'pins', 10000);
    }

    async createPin(pinData) {
        const data = await this._request('/api/pins', {
            method: 'POST',
            body: JSON.stringify(pinData)
        });
        this.clearCache('pins');
        this.emit('pinCreated', { pinData, data });
        return data;
    }

    async deletePin(pinId) {
        const data = await this._request(`/api/pins/${pinId}`, {
            method: 'DELETE'
        });
        this.clearCache('pins');
        this.emit('pinDeleted', { id: pinId, data });
        return data;
    }

    async getPinStatus(pinId) {
        return await this._request(`/api/pins/${pinId}/status`);
    }

    // ===================
    // BUCKETS API
    // ===================
    // BUCKETS API
    // ===================

    async getBuckets() {
        return await this._getCached('/api/buckets', 'buckets', 15000);
    }

    async createBucket(bucketData) {
        const data = await this._request('/api/buckets', {
            method: 'POST',
            body: JSON.stringify(bucketData)
        });
        this.clearCache('buckets');
        this.emit('bucketCreated', { bucketData, data });
        return data;
    }

    async deleteBucket(bucketId) {
        const data = await this._request(`/api/buckets/${bucketId}`, {
            method: 'DELETE'
        });
        this.clearCache('buckets');
        this.emit('bucketDeleted', { id: bucketId, data });
        return data;
    }

    async getBucketDetails(bucketName) {
        return await this._getCached(`/api/buckets/${bucketName}`, `bucket_details_${bucketName}`, 10000);
    }

    async getBucketFiles(bucketName) {
        return await this._getCached(`/api/buckets/${bucketName}/files`, `bucket_files_${bucketName}`, 5000);
    }

    async getBucketContents(bucketId) {
        return await this._getCached(`/api/buckets/${bucketId}/contents`, `bucket_contents_${bucketId}`, 10000);
    }

    async uploadFileToBucket(bucketName, file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const data = await this._request(`/api/buckets/${bucketName}/upload`, {
            method: 'POST',
            body: formData,
            // Don't set Content-Type header for FormData
            headers: {}
        });
        this.clearCache(`bucket_files_${bucketName}`);
        this.emit('fileUploaded', { bucketName, file, data });
        return data;
    }

    async deleteFileFromBucket(bucketName, filename) {
        const data = await this._request(`/api/buckets/${bucketName}/files/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        this.clearCache(`bucket_files_${bucketName}`);
        this.emit('fileDeleted', { bucketName, filename, data });
        return data;
    }

    async renameFileInBucket(bucketName, oldName, newName) {
        const data = await this._request(`/api/buckets/${bucketName}/files/${encodeURIComponent(oldName)}/rename`, {
            method: 'POST',
            body: JSON.stringify({ new_name: newName })
        });
        this.clearCache(`bucket_files_${bucketName}`);
        this.emit('fileRenamed', { bucketName, oldName, newName, data });
        return data;
    }

    async updateBucketSettings(bucketName, settings) {
        const data = await this._request(`/api/buckets/${bucketName}/settings`, {
            method: 'PUT',
            body: JSON.stringify(settings)
        });
        this.clearCache('buckets');
        this.clearCache(`bucket_details_${bucketName}`);
        this.emit('bucketSettingsUpdated', { bucketName, settings, data });
        return data;
    }

    // ===================
    // LOGS API
    // ===================

    async getLogs(component = 'all', limit = 1000) {
        return await this._request(`/api/logs?component=${component}&limit=${limit}`);
    }

    async streamLogs(component, callback) {
        // WebSocket or EventSource implementation for real-time logs
        const eventSource = new EventSource(`/api/logs/stream?component=${component}`);
        
        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                callback(data);
            } catch (error) {
                console.error('Error parsing log data:', error);
            }
        };

        eventSource.onerror = (error) => {
            console.error('Log stream error:', error);
            eventSource.close();
        };

        return () => eventSource.close();
    }

    // ===================
    // UTILITIES
    // ===================

    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    }

    formatTimestamp(timestamp) {
        return new Date(timestamp).toLocaleString();
    }

    getStatusColor(status) {
        const colors = {
            'healthy': 'green',
            'online': 'green',
            'running': 'green',
            'degraded': 'yellow',
            'warning': 'yellow',
            'unhealthy': 'red',
            'offline': 'red',
            'stopped': 'red',
            'error': 'red',
            'unknown': 'gray'
        };
        return colors[status?.toLowerCase()] || 'gray';
    }
}

// Create global instance
window.ipfsKitAPI = new IPFSKitAPI();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = IPFSKitAPI;
}