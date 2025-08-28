
// Enhanced MCP SDK for JSON-RPC calls with comprehensive error handling
class MCPClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.requestId = 1;
        this.isConnected = false;
        this.retryCount = 0;
        this.maxRetries = 3;
        this.retryDelay = 1000;
        
        // Initialize connection testing
        this.testConnection();
    }
    
    async testConnection() {
        try {
            await this.callTool('health_check');
            this.isConnected = true;
            console.log('MCP connection established');
        } catch (error) {
            this.isConnected = false;
            console.warn('MCP connection failed, using fallback mode');
        }
    }
    
    async callTool(toolName, params = {}) {
        const requestId = this.requestId++;
        
        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                const payload = {
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: {
                        name: toolName,
                        arguments: params
                    },
                    id: requestId
                };
                
                console.log(`MCP call attempt ${attempt + 1}:`, toolName, params);
                
                const response = await fetch('/mcp/tools/call', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify(payload),
                    timeout: 10000  // 10 second timeout
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.error) {
                    throw new Error(`MCP Error: ${data.error.message || 'Unknown error'}`);
                }
                
                console.log(`MCP call successful:`, toolName, data.result);
                this.isConnected = true;
                this.retryCount = 0;
                
                return data.result;
                
            } catch (error) {
                console.warn(`MCP call attempt ${attempt + 1} failed:`, error.message);
                
                if (attempt < this.maxRetries) {
                    await new Promise(resolve => setTimeout(resolve, this.retryDelay * (attempt + 1)));
                } else {
                    this.isConnected = false;
                    this.retryCount++;
                    throw error;
                }
            }
        }
    }
    
    async callToolWithFallback(toolName, params = {}, fallbackApiEndpoint) {
        try {
            // Try MCP first
            return await this.callTool(toolName, params);
        } catch (mcpError) {
            console.warn(`MCP call failed for ${toolName}, falling back to API:`, mcpError.message);
            
            // Fallback to direct API call
            try {
                const response = await fetch(fallbackApiEndpoint);
                if (!response.ok) {
                    throw new Error(`API fallback failed: ${response.status}`);
                }
                return await response.json();
            } catch (apiError) {
                console.error(`Both MCP and API calls failed for ${toolName}:`, apiError.message);
                throw new Error(`Both MCP and API calls failed: ${mcpError.message} | ${apiError.message}`);
            }
        }
    }
    
    getConnectionStatus() {
        return {
            connected: this.isConnected,
            retryCount: this.retryCount,
            status: this.isConnected ? 'Connected via MCP JSON-RPC' : 'Using API Fallback'
        };
    }
}

// Export MCP client class and create global instances
window.MCP = {
    MCPClient: MCPClient
};

// Global MCP client instance
window.mcpClient = new MCPClient();

// Enhanced error handling and logging
window.mcpLogger = {
    log: (message, data) => console.log(`[MCP] ${message}`, data || ''),
    warn: (message, data) => console.warn(`[MCP] ${message}`, data || ''),
    error: (message, data) => console.error(`[MCP] ${message}`, data || '')
};

// Helper function that was missing from the enhanced dashboard template
function updateElement(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    } else {
        console.warn(`Element with id '${elementId}' not found`);
    }
}
