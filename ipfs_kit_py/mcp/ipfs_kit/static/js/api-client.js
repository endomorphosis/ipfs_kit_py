/**
 * API Client for Dashboard
 */

class DashboardAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    async request(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`API Error: ${response.status} ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API request failed for ${endpoint}:`, error);
            throw error;
        }
    }

    // Health and status endpoints
    async getHealth() {
        return this.request('/api/health');
    }

    async getBackends() {
        return this.request('/api/backends');
    }

    // VFS endpoints
    async getVFSStatistics() {
        return this.request('/api/vfs/statistics');
    }

    async getVFSHealth() {
        return this.request('/api/vfs/health');
    }

    async getVFSRecommendations() {
        return this.request('/api/vfs/recommendations');
    }

    // File management endpoints
    async getFiles(path = '/') {
        return this.request(`/api/files/?path=${encodeURIComponent(path)}`);
    }

    async uploadFile(file, path = '/') {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('path', path);
        
        return this.request('/api/files/upload', {
            method: 'POST',
            body: formData,
            headers: {} // Don't set Content-Type for FormData
        });
    }

    async downloadFile(filename) {
        const response = await fetch(`${this.baseUrl}/api/files/${encodeURIComponent(filename)}`);
        if (!response.ok) {
            throw new Error(`Download failed: ${response.statusText}`);
        }
        return response.blob();
    }

    async deleteFile(filename) {
        return this.request(`/api/files/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
    }

    async createFolder(name, path = '/') {
        return this.request('/api/files/create_folder', {
            method: 'POST',
            body: JSON.stringify({ name, path })
        });
    }

    // Monitoring endpoints (if they exist)
    async getMonitoringMetrics() {
        try {
            return await this.request('/api/monitoring/metrics');
        } catch (error) {
            console.warn('Monitoring metrics endpoint not available:', error);
            return { success: false, error: 'Endpoint not available' };
        }
    }

    async getMonitoringAlerts() {
        try {
            return await this.request('/api/monitoring/alerts');
        } catch (error) {
            console.warn('Monitoring alerts endpoint not available:', error);
            return { success: false, error: 'Endpoint not available' };
        }
    }

    async getComprehensiveMonitoring() {
        try {
            return await this.request('/api/monitoring/comprehensive');
        } catch (error) {
            console.warn('Comprehensive monitoring endpoint not available:', error);
            return { success: false, error: 'Endpoint not available' };
        }
    }

    // System logs
    async getLogs() {
        try {
            return this.request('/api/logs');
        } catch (error) {
            console.warn('Logs endpoint not available:', error);
            return { success: false, error: 'Endpoint not available' };
        }
    }
}

// Create global API instance
window.dashboardAPI = new DashboardAPI();
