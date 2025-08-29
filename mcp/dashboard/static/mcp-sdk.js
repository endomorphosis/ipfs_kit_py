/**
 * MCP Client SDK for IPFS Kit Dashboard
 * Provides MCP JSON-RPC integration with fallback to direct API calls
 */

class MCPClient {
    constructor(options = {}) {
        this.baseUrl = options.baseUrl || '';
        this.timeout = options.timeout || 10000;
        this.retryCount = options.retryCount || 3;
        this.retryDelay = options.retryDelay || 1000;
        this.connected = false;
        this.requestId = 0;
        this.debug = options.debug || false;
        
        this.log('MCP Client initialized');
        this.testConnection();
    }
    
    log(message, data = null) {
        if (this.debug) {
            console.log(`[MCP Client] ${message}`, data || '');
        }
    }
    
    error(message, data = null) {
        console.error(`[MCP Client] ${message}`, data || '');
    }
    
    async testConnection() {
        try {
            const response = await fetch('/api/mcp/status');
            if (response.ok) {
                const data = await response.json();
                this.connected = data.success !== false;
                this.log('Connection test successful', {connected: this.connected});
            }
        } catch (error) {
            this.connected = false;
            this.log('Connection test failed', error);
        }
    }
    
    generateRequestId() {
        return ++this.requestId;
    }
    
    async callTool(toolName, params = {}) {
        this.log(`Calling tool: ${toolName}`, params);
        
        // Try MCP JSON-RPC first
        try {
            const mcpResponse = await this.callMCPJsonRPC(toolName, params);
            this.log(`✅ ${toolName} via MCP JSON-RPC`, mcpResponse);
            return mcpResponse;
        } catch (mcpError) {
            this.log(`MCP JSON-RPC failed for ${toolName}: ${mcpError.message}, falling back to API`, mcpError);
            
            // Fallback to direct API calls
            try {
                const apiResponse = await this.callAPIFallback(toolName, params);
                this.log(`📡 ${toolName} via API fallback`, apiResponse);
                return apiResponse;
            } catch (apiError) {
                this.error(`Both MCP and API failed for ${toolName}`, { mcpError: mcpError.message, apiError: apiError.message });
                throw apiError;
            }
        }
    }
    
    async callMCPJsonRPC(toolName, params) {
        const payload = {
            jsonrpc: '2.0',
            method: 'tools/call',
            params: { 
                name: toolName, 
                arguments: params 
            },
            id: this.generateRequestId()
        };
        
        const response = await this.makeRequest('/mcp/tools/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`MCP JSON-RPC error: ${response.status} ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.error) {
            throw new Error(`MCP tool error: ${result.error.message || result.error}`);
        }
        
        return result.result;
    }
    
    async callAPIFallback(toolName, params) {
        // Map tool names to API endpoints
        const apiMapping = {
            'get_system_status': '/api/metrics/system',
            'get_system_overview': '/api/mcp/status',
            'list_services': '/api/mcp/status',
            'list_backends': '/api/backends',
            'list_buckets': '/api/buckets',
            'get_peers': '/api/peers',
            'get_logs': '/api/logs'
        };
        
        const endpoint = apiMapping[toolName];
        if (!endpoint) {
            throw new Error(`No API fallback available for tool: ${toolName}`);
        }
        
        const response = await this.makeRequest(endpoint);
        if (!response.ok) {
            throw new Error(`API fallback error: ${response.status} ${response.statusText}`);
        }
        
        return await response.json();
    }
    
    async makeRequest(url, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);
        
        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            throw error;
        }
    }
}

// Create global MCP namespace with SDK components
window.MCP = {
    Client: MCPClient,
    client: null,
    
    // Initialize the MCP client
    init(options = {}) {
        this.client = new MCPClient(options);
        return this.client;
    },
    
    // Buckets namespace
    Buckets: {
        async list() {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('list_buckets');
        },
        
        async get(bucketName) {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('get_bucket_info', { bucket_name: bucketName });
        },
        
        async create(bucketName, config = {}) {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('create_bucket', { name: bucketName, config });
        },
        
        async delete(bucketName) {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('delete_bucket', { bucket_name: bucketName });
        }
    },
    
    // Backends namespace  
    Backends: {
        async list() {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('list_backends');
        },
        
        async get(backendName) {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('get_backend_info', { backend_name: backendName });
        }
    },
    
    // System namespace
    System: {
        async getStatus() {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('get_system_status');
        },
        
        async getOverview() {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('get_system_overview');
        },
        
        async getServices() {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('list_services');
        }
    },
    
    // Network namespace
    Network: {
        async getPeers() {
            const client = window.MCP.client || window.MCP.init();
            return await client.callTool('get_peers');
        }
    }
};

// Auto-initialize MCP client with debug mode in development
document.addEventListener('DOMContentLoaded', () => {
    try {
        const debug = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        window.MCP.init({ debug });
        console.log('🔗 MCP Client initialized successfully');
    } catch (error) {
        console.error('❌ MCP Client initialization failed:', error);
    }
});