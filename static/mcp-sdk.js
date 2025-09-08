
// Enhanced MCP SDK for comprehensive JSON-RPC service management with comprehensive error handling
class MCPClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.requestId = 1;
        this.isConnected = false;
        this.retryCount = 0;
        this.maxRetries = 3;
        this.retryDelay = 1000;
    // Cache of available MCP tools (optional)
    this._toolList = null;
    this._lastToolListAt = 0;
        
        // Initialize connection testing
        this.testConnection();
    }
    
    async testConnection() {
        try {
            console.log('Testing MCP connection...');
            await this.callTool('health_check');
            this.isConnected = true;
            console.log('MCP connection established successfully');
        } catch (error) {
            this.isConnected = false;
            console.warn('MCP connection failed, using fallback mode:', error.message);
            
            // Don't throw the error - just log and continue with fallback
            return false;
        }
    }
    
    async callTool(toolName, params = {}) {
        const requestId = this.requestId++;
        
        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                // Use the JSON-RPC format that our MCP server expects
                const payload = {
                    jsonrpc: "2.0",
                    method: "tools/call",
                    params: {
                        name: toolName,
                        arguments: params
                    },
                    id: requestId
                };
                
                console.log(`MCP call attempt ${attempt + 1}:`, toolName, JSON.stringify(params));
                
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
                
                let data;
                let text = '';
                try {
                    text = await response.text();
                    console.log(`Raw response (${text.length} chars):`, text.substring(0, 200) + (text.length > 200 ? '...' : ''));
                    
                    if (!text || text.trim() === '') {
                        throw new Error('Empty response from server');
                    }
                    
                    // Validate JSON structure before parsing
                    const trimmedText = text.trim();
                    if (!trimmedText.startsWith('{') && !trimmedText.startsWith('[')) {
                        throw new Error(`Invalid JSON response format: starts with '${trimmedText.substring(0, 10)}'`);
                    }
                    
                    if (trimmedText.startsWith('{') && !trimmedText.endsWith('}')) {
                        throw new Error('Incomplete JSON object: missing closing brace');
                    }
                    
                    if (trimmedText.startsWith('[') && !trimmedText.endsWith(']')) {
                        throw new Error('Incomplete JSON array: missing closing bracket');
                    }
                    
                    data = JSON.parse(text);
        } catch (jsonError) {
                    console.error('JSON parsing error details:', {
                        error: jsonError.message,
                        responseStatus: response.status,
                        responseHeaders: Object.fromEntries(response.headers.entries()),
            bodyPreview: (text || '').substring(0, 500)
                    });
                    throw new Error(`Invalid JSON response: ${jsonError.message}`);
                }
                
                if (data.error) {
                    // Handle different error formats
                    let errorMessage = "Unknown error";
                    if (typeof data.error === 'string') {
                        errorMessage = data.error;
                    } else if (data.error.message) {
                        errorMessage = data.error.message;
                    } else if (data.error.code) {
                        errorMessage = `Error ${data.error.code}: ${data.error.message || 'Unknown error'}`;
                    } else {
                        errorMessage = JSON.stringify(data.error);
                    }
                    throw new Error(`MCP Error: ${errorMessage}`);
                }
                
                console.log(`MCP call successful:`, toolName, JSON.stringify(data.result || data).substring(0, 200) + '...');
                this.isConnected = true;
                this.retryCount = 0;
                
                return data.result || data;
                
            } catch (error) {
                console.error(`MCP call attempt ${attempt + 1} failed:`, {
                    toolName: toolName,
                    params: params,
                    error: error.message,
                    stack: error.stack
                });

                // On unknown tool, try alias mapping and REST fallbacks (peer ops)
                if (String(error.message || '').includes('Unknown tool')) {
                    try {
                        const alt = await this._tryAliasesAndFallbacks(toolName, params);
                        if (alt !== undefined) {
                            // Success via alias/fallback
                            this.isConnected = true;
                            this.retryCount = 0;
                            return alt;
                        }
                    } catch (aliasErr) {
                        console.warn(`Alias/REST fallback failed for ${toolName}:`, aliasErr.message);
                    }
                }
                
                if (attempt < this.maxRetries) {
                    await new Promise(resolve => setTimeout(resolve, this.retryDelay * (attempt + 1)));
                } else {
                    this.isConnected = false;
                    this.retryCount++;
                    console.error(`All MCP call attempts failed for ${toolName}:`, error.message);
                    throw error;
                }
            }
        }
    }

    // Attempt alias names and REST peer fallbacks when the server doesn't expose the exact tool
    async _tryAliasesAndFallbacks(toolName, params) {
        const candidates = this._aliasCandidates(toolName);
        // Try alias names over MCP
        for (const name of candidates) {
            try {
                const res = await this._callOnce(name, params);
                console.log(`Alias '${name}' succeeded for '${toolName}'`);
                return res;
            } catch (e) {
                // continue to next alias
            }
        }
        // Try REST fallbacks for peer operations
        if (this._isPeerTool(toolName)) {
            const rest = await this._peerRestFallback(toolName, params);
            return rest;
        }
        return undefined;
    }

    _isPeerTool(name) {
        const n = String(name || '').toLowerCase();
        return ['list_peers','discover_peers','connect_peer','disconnect_peer','get_peer_stats','get_peer_info','bootstrap_peers']
            .includes(n);
    }

    _aliasCandidates(toolName) {
        const name = String(toolName || '');
        const base = name.replace(/[-\s]+/g, '_').toLowerCase();
        const map = {
            // peer discovery
            'discover_peers': ['peer_discover', 'discover_network_peers', 'find_peers', 'peers_discover', 'dht_discover_peers'],
            // peer list
            'list_peers': ['peers_list', 'get_peers', 'peer_list'],
            // peer connect/disconnect
            'connect_peer': ['peer_connect', 'connect_to_peer'],
            'disconnect_peer': ['peer_disconnect', 'disconnect_from_peer'],
            // peer stats/info
            'get_peer_stats': ['peer_stats', 'peers_stats'],
            'get_peer_info': ['peer_info', 'peers_info']
        };
        const built = map[base] || [];
        // add a hyphen variant and camel-case variant as last resort
        const hyphen = base.replace(/_/g, '-');
        const nosep = base.replace(/_/g, '');
        return [...new Set([base, ...built, hyphen, nosep])].filter(n => n !== name);
    }

    async _callOnce(toolName, params) {
        const payload = {
            jsonrpc: '2.0',
            method: 'tools/call',
            params: { name: toolName, arguments: params || {} },
            id: this.requestId++
        };
        const resp = await fetch('/mcp/tools/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data && data.error) throw new Error(data.error.message || 'MCP error');
        return data.result || data;
    }

    async _peerRestFallback(toolName, params) {
        // Try REST endpoints if available; return undefined if none succeed
        const n = String(toolName || '').toLowerCase();
        try {
            if (n === 'list_peers') {
                const r = await fetch('/api/peers');
                if (r.ok) return await r.json();
            } else if (n === 'discover_peers') {
                const r = await fetch('/api/peers/discover', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params || {}) });
                if (r.ok) return await r.json();
            } else if (n === 'connect_peer') {
                const r = await fetch('/api/peers/connect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params || {}) });
                if (r.ok) return await r.json();
            } else if (n === 'disconnect_peer') {
                const r = await fetch('/api/peers/disconnect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params || {}) });
                if (r.ok) return await r.json();
            } else if (n === 'get_peer_stats') {
                const r = await fetch('/api/peers/stats');
                if (r.ok) return await r.json();
            } else if (n === 'get_peer_info') {
                const pid = encodeURIComponent(params?.peer_id || '');
                if (pid) {
                    const r = await fetch(`/api/peers/${pid}`);
                    if (r.ok) return await r.json();
                }
            } else if (n === 'bootstrap_peers') {
                const r = await fetch('/api/peers/bootstrap', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params || {}) });
                if (r.ok) return await r.json();
            }
        } catch (e) {
            // network or endpoint not found; swallow to allow normal error path
        }
        return undefined;
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

// Export MCP client class and create/merge global namespace without clobbering
window.MCP = window.MCP || {};
window.MCP.MCPClient = MCPClient;

// Comprehensive Service Management namespace
window.MCP.Services = {
        async list(includeMetadata = true) {
            return await window.mcpClient.callTool('list_services', { include_metadata: includeMetadata });
        },
        
        async configure(serviceType, instanceName, config) {
            return await window.mcpClient.callTool('configure_service', {
                service_type: serviceType,
                instance_name: instanceName,
                config: config
            });
        },
        
        async getStatus() {
            return await window.mcpClient.callTool('get_system_status');
        }
};

// Comprehensive Backend Management namespace  
window.MCP.Backends = {
        async list(includeMetadata = true) {
            return await window.mcpClient.callTool('list_backends', { include_metadata: includeMetadata });
        },
        
        async configure(backendType, instanceName, config) {
            return await window.mcpClient.callTool('configure_service', {
                service_type: backendType,
                instance_name: instanceName,
                config: config
            });
        }
};

// Comprehensive Bucket Management namespace
window.MCP.Buckets = {
        async list(includeMetadata = true) {
            return await window.mcpClient.callTool('list_buckets', { include_metadata: includeMetadata });
        },
        
        async listFiles(bucket, path = '/', showMetadata = false) {
            return await window.mcpClient.callTool('bucket_list_files', {
                bucket: bucket,
                path: path,
                show_metadata: showMetadata
            });
        },
        
        async uploadFile(bucket, path, content, mode = 'create', applyPolicy = true) {
            return await window.mcpClient.callTool('bucket_upload_file', {
                bucket: bucket,
                path: path,
                content: content,
                mode: mode,
                apply_policy: applyPolicy
            });
        },
        
        async downloadFile(bucket, path, format = 'text') {
            return await window.mcpClient.callTool('bucket_download_file', {
                bucket: bucket,
                path: path,
                format: format
            });
        },
        
        async deleteFile(bucket, path, removeReplicas = false) {
            return await window.mcpClient.callTool('bucket_delete_file', {
                bucket: bucket,
                path: path,
                remove_replicas: removeReplicas
            });
        },
        
        async createFolder(bucket, path) {
            return await window.mcpClient.callTool('bucket_create_folder', {
                bucket: bucket,
                path: path
            });
        },
        
        async renameFile(bucket, oldPath, newPath) {
            return await window.mcpClient.callTool('bucket_rename_file', {
                bucket: bucket,
                old_path: oldPath,
                new_path: newPath
            });
        },
        
        async syncReplicas(bucket, forceSync = false) {
            return await window.mcpClient.callTool('bucket_sync_replicas', {
                bucket: bucket,
                force_sync: forceSync
            });
        },
        
        async configure(bucketName, config) {
            return await window.mcpClient.callTool('configure_service', {
                service_type: 'bucket',
                instance_name: bucketName,
                config: config
            });
        }
};

// System Health namespace
window.MCP.System = {
        async healthCheck() {
            return await window.mcpClient.callTool('health_check');
        },
        
        async getStatus() {
            return await window.mcpClient.callTool('get_system_status');
        }
};

// Create global MCP client instance
window.mcpClient = new MCPClient();

// Provide a proxy so callers using window.MCP.callTool work
window.MCP.callTool = async function(toolName, params = {}) {
    if (!window.mcpClient || typeof window.mcpClient.callTool !== 'function') {
        throw new Error('MCP client not initialized');
    }
    return window.mcpClient.callTool(toolName, params);
};

// Enhanced error handling and logging
window.mcpLogger = {
    log: (message, data) => console.log(`[MCP] ${message}`, data || ''),
    warn: (message, data) => console.warn(`[MCP] ${message}`, data || ''),
    error: (message, data) => console.error(`[MCP] ${message}`, data || '')
};

// Global error handler to catch any uncaught JavaScript errors
window.addEventListener('error', function(event) {
    console.error('Uncaught JavaScript error:', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error ? event.error.toString() : 'No error object',
        stack: event.error ? event.error.stack : 'No stack trace available'
    });
});

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', {
        reason: typeof event.reason === 'object' ? JSON.stringify(event.reason) : event.reason,
        promise: event.promise
    });
});

// Helper function that was missing from the enhanced dashboard template
function updateElement(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    } else {
        console.warn(`Element with id '${elementId}' not found`);
    }
}
