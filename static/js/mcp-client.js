/**
 * MCP Server JavaScript Client
 * Provides interface to communicate with the MCP server using JSON-RPC
 */
class MCPClient {
    constructor(baseUrl = window.location.origin) {
        this.baseUrl = baseUrl;
        this.requestId = 1;
    }

    async jsonRpc(method, params = {}) {
        const response = await fetch(`${this.baseUrl}/dashboard/jsonrpc`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: method,
                params: params,
                id: this.requestId++
            })
        });
        
        const data = await response.json();
        if (data.error) {
            throw new Error(`MCP Error: ${data.error.message}`);
        }
        
        return data.result;
    }

    // MCP Server Tools Methods
    async listTools() {
        return await this.jsonRpc('tools.list');
    }

    async getToolInfo(toolName) {
        return await this.jsonRpc('tools.info', { tool: toolName });
    }

    async executeTool(toolName, args) {
        return await this.jsonRpc('tools.execute', { tool: toolName, args: args });
    }

    // Virtual Filesystem Methods
    async listBuckets() {
        return await this.jsonRpc('filesystem.buckets.list');
    }

    async createBucket(name, type = 'ipfs') {
        return await this.jsonRpc('filesystem.buckets.create', { name: name, type: type });
    }

    async deleteBucket(name) {
        return await this.jsonRpc('filesystem.buckets.delete', { name: name });
    }

    async listBucketContents(bucketName) {
        return await this.jsonRpc('filesystem.buckets.contents', { bucket: bucketName });
    }

    async addToBucket(bucketName, filePath, content) {
        return await this.jsonRpc('filesystem.buckets.add', { 
            bucket: bucketName, 
            path: filePath, 
            content: content 
        });
    }

    // Program State Methods (for ~/.ipfs-kit management)
    async getConfig() {
        return await this.jsonRpc('config.get');
    }

    async updateConfig(config) {
        return await this.jsonRpc('config.update', { config: config });
    }

    async getConfigFile(filename) {
        return await this.jsonRpc('config.file.get', { filename: filename });
    }

    async updateConfigFile(filename, content) {
        return await this.jsonRpc('config.file.update', { filename: filename, content: content });
    }

    // Daemon Management Methods
    async getDaemonStatus() {
        return await this.jsonRpc('daemon.status');
    }

    async startDaemon(daemonName) {
        return await this.jsonRpc('daemon.start', { daemon: daemonName });
    }

    async stopDaemon(daemonName) {
        return await this.jsonRpc('daemon.stop', { daemon: daemonName });
    }

    async restartDaemon(daemonName) {
        return await this.jsonRpc('daemon.restart', { daemon: daemonName });
    }

    // File Operations
    async indexFiles() {
        return await this.jsonRpc('files.index');
    }

    async syncPins() {
        return await this.jsonRpc('pins.sync');
    }

    async runGarbageCollection() {
        return await this.jsonRpc('gc.run');
    }

    // Storage Backend Methods
    async listStorageBackends() {
        return await this.jsonRpc('storage.backends.list');
    }

    async getBackendStatus(backendName) {
        return await this.jsonRpc('storage.backends.status', { backend: backendName });
    }

    async configureBackend(backendName, config) {
        return await this.jsonRpc('storage.backends.configure', { 
            backend: backendName, 
            config: config 
        });
    }

    // Real-time Updates
    createEventSource(endpoint = 'events') {
        return new EventSource(`${this.baseUrl}/dashboard/${endpoint}`);
    }

    // Utility Methods
    async getServerInfo() {
        return await this.jsonRpc('server.info');
    }

    async getMetrics() {
        return await this.jsonRpc('metrics.get');
    }
}

// Global MCP client instance
window.mcpClient = new MCPClient();