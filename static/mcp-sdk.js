
// Enhanced MCP SDK for comprehensive JSON-RPC service management with comprehensive error handling
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
                // Use the simplified format that our MCP server expects
                const payload = {
                    method: toolName,
                    params: params
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
                    throw new Error(`MCP Error: ${data.error}`);
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

// Export MCP client class and create global instances with comprehensive service management
window.MCP = {
    MCPClient: MCPClient,
    
    // Comprehensive Service Management namespace
    Services: {
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
    },
    
    // Comprehensive Backend Management namespace  
    Backends: {
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
    },
    
    // Comprehensive Bucket Management namespace
    Buckets: {
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
    },
    
    // System Health namespace
    System: {
        async healthCheck() {
            return await window.mcpClient.callTool('health_check');
        },
        
        async getStatus() {
            return await window.mcpClient.callTool('get_system_status');
        }
    }
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
