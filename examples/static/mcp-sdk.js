
// Simple MCP SDK for JSON-RPC calls
class MCPClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }
    
    async callTool(toolName, params = {}) {
        try {
            const response = await fetch('/mcp/tools/call', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'tools/call',
                    params: {
                        name: toolName,
                        arguments: params
                    },
                    id: Date.now()
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error.message || 'MCP call failed');
            }
            
            return data.result;
        } catch (error) {
            console.error('MCP tool call failed:', error);
            throw error;
        }
    }
}

// Global MCP client instance
window.mcpClient = new MCPClient();
