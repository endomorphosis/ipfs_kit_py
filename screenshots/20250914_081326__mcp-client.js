
(function(global){
    // JSON-RPC helpers
    async function rpcList(){
        const r = await fetch('/mcp/tools/list', {method:'POST'});
        return await r.json();
    }
    async function rpcCall(name, args={}){
        const r = await fetch('/mcp/tools/call', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({name, args})});
        return await r.json();
    }
    async function status(){
        const r = await fetch('/api/mcp/status');
        const js = await r.json();
        // Normalize shape for clients/tests: expose initialized + tools at top level
        const data = (js && (js.data || js)) || {};
        const tools = Array.isArray(data.tools) ? data.tools : [];
        return { initialized: !!data, tools, ...data };
    }

    // Namespaced convenience wrappers
    const Services = {
        control: (service, action) => rpcCall('service_control', {service, action}),
        status: (service) => rpcCall('service_status', {service}),
    };

    const Backends = {
        list: () => rpcCall('list_backends', {}),
        get: (name) => rpcCall('get_backend', {name}),
        create: (name, config) => rpcCall('create_backend', {name, config}),
        update: (name, config) => rpcCall('update_backend', {name, config}),
        delete: (name) => rpcCall('delete_backend', {name}),
        test: (name) => rpcCall('test_backend', {name}),
    };

    const Buckets = {
        list: () => rpcCall('list_buckets', {}),
        get: (name) => rpcCall('get_bucket', {name}),
        create: (name, backend) => rpcCall('create_bucket', {name, backend}),
        update: (name, patch) => rpcCall('update_bucket', {name, patch}),
        delete: (name) => rpcCall('delete_bucket', {name}),
        getPolicy: (name) => rpcCall('get_bucket_policy', {name}),
        updatePolicy: (name, policy) => rpcCall('update_bucket_policy', {name, policy}),
        // Comprehensive bucket file management functions
        listFiles: (bucket, path, showMetadata) => rpcCall('bucket_list_files', {bucket, path: path || '.', show_metadata: !!showMetadata}),
        uploadFile: (bucket, path, content, mode, applyPolicy) => rpcCall('bucket_upload_file', {bucket, path, content, mode: mode || 'text', apply_policy: !!applyPolicy}),
        downloadFile: (bucket, path, format) => rpcCall('bucket_download_file', {bucket, path, format: format || 'text'}),
        deleteFile: (bucket, path, removeReplicas) => rpcCall('bucket_delete_file', {bucket, path, remove_replicas: !!removeReplicas}),
        renameFile: (bucket, src, dst, updateReplicas) => rpcCall('bucket_rename_file', {bucket, src, dst, update_replicas: !!updateReplicas}),
        mkdir: (bucket, path, createParents) => rpcCall('bucket_mkdir', {bucket, path, create_parents: !!createParents}),
        syncReplicas: (bucket, forceSync) => rpcCall('bucket_sync_replicas', {bucket, force_sync: !!forceSync}),
        getMetadata: (bucket, path, includeReplicas) => rpcCall('bucket_get_metadata', {bucket, path, include_replicas: !!includeReplicas}),
        getUsage: (name) => rpcCall('get_bucket_usage', {name}),
        generateShareLink: (bucket, accessType, expiration) => rpcCall('generate_bucket_share_link', {bucket, access_type: accessType || 'read_only', expiration: expiration || 'never'}),
        selectiveSync: (bucket, files, options) => rpcCall('bucket_selective_sync', {bucket, files, options: options || {}})
    };

    const Pins = {
        list: () => rpcCall('list_pins', {}),
        create: (cid, name) => rpcCall('create_pin', {cid, name}),
        delete: (cid) => rpcCall('delete_pin', {cid}),
        export: () => rpcCall('pins_export', {}),
        import: (items) => rpcCall('pins_import', {items}),
    };

    const Files = {
        list: (path='.') => rpcCall('files_list', {path}),
        read: (path) => rpcCall('files_read', {path}),
        write: (path, content, mode='text') => rpcCall('files_write', {path, content, mode}),
        mkdir: (path) => rpcCall('files_mkdir', {path}),
        rm: (path, recursive=false) => rpcCall('files_rm', {path, recursive}),
        mv: (src, dst) => rpcCall('files_mv', {src, dst}),
        stat: (path) => rpcCall('files_stat', {path}),
        copy: (src, dst, recursive=false) => rpcCall('files_copy', {src, dst, recursive}),
        touch: (path) => rpcCall('files_touch', {path}),
        tree: (path='.', depth=2) => rpcCall('files_tree', {path, depth}),
    };

    const IPFS = {
        version: () => rpcCall('ipfs_version', {}),
        add: (path) => rpcCall('ipfs_add', {path}),
        pin: (cid, name) => rpcCall('ipfs_pin', {cid, name}),
        cat: (cid) => rpcCall('ipfs_cat', {cid}),
        ls: (cid) => rpcCall('ipfs_ls', {cid}),
    };

    const CARs = {
        list: () => rpcCall('cars_list', {}),
        export: (path, car) => rpcCall('car_export', {path, car}),
        import: (car, dest) => rpcCall('car_import', {car, dest}),
    };

    const State = {
        snapshot: () => rpcCall('state_snapshot', {}),
        backup: () => rpcCall('state_backup', {}),
        reset: () => rpcCall('state_reset', {}),
    };

    const Logs = {
        get: (limit=200) => rpcCall('get_logs', {limit}),
        clear: () => rpcCall('clear_logs', {}),
    };

    const Server = {
        shutdown: () => rpcCall('server_shutdown', {}),
    };

    const Peers = {
        list: () => rpcCall('list_peers', {}),
        connect: (peer) => rpcCall('connect_peer', peer || {}),
        disconnect: (peer_id) => rpcCall('disconnect_peer', {peer_id}),
        info: (peer_id) => rpcCall('get_peer_info', {peer_id}),
    };

    // Schema helpers (beta; not used by wrappers yet)
    const Schema = {
        normalize(inputSchema){
            const s = inputSchema||{};
            if (s && s.properties) return s;
            const props = {}; Object.keys(s||{}).forEach(k => props[k] = { type: String(s[k]||'string') });
            return { type:'object', properties: props };
        },
        coerce(type, raw){
            if (type==='number') { const n = (raw===''||raw==null)?null:Number(raw); return isNaN(n)?null:n; }
            if (type==='boolean') return !!raw;
            if (type==='object' || type==='array') { try { return JSON.parse(String(raw||'')); } catch(e){ return { __error: String(e) }; } }
            return String(raw==null? '': raw);
        }
    };

    // Helper function used by dashboard UI
    function updateElement(selector, content) {
        const element = document.querySelector(selector);
        if (element) {
            if (typeof content === 'string') {
                element.textContent = content;
            } else if (typeof content === 'object' && content !== null) {
                element.textContent = JSON.stringify(content);
            } else {
                element.textContent = String(content || 'N/A');
            }
        }
    }

    const MCP = {
        // Core
        listTools: rpcList,
        callTool: rpcCall,
        status,
        // Namespaces
        Services, Backends, Buckets, Pins, Files, IPFS, CARs, State, Logs, Server, Peers,
        // Utils
        Schema,
    };

    // Comprehensive bucket file management helper functions
    async function refreshBucketFilesMCP(bucketName) {
        const fileList = document.getElementById('mcp-file-list');
        const pathInput = document.getElementById('current-path');
        const showMeta = document.getElementById('show-metadata');
        
        if (!fileList || !pathInput) return;
        
        const currentPath = pathInput.value || '.';
        const showMetadata = showMeta ? showMeta.checked : true;
        
        try {
            fileList.innerHTML = '<div style="text-align:center;padding:20px;color:#888;">Loading files via MCP...</div>';
            
            await waitForMCP();
            const result = await MCP.Buckets.listFiles(bucketName, currentPath, showMetadata);
            const files = (result && result.result && result.result.files) || [];
            
            if (files.length === 0) {
                fileList.innerHTML = '<div style="text-align:center;padding:20px;color:#888;">No files in this directory</div>';
                return;
            }
            
            // Create file table
            let tableHTML = `
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#222;border-bottom:1px solid #333;">
                            <th style="text-align:left;padding:6px;font-size:11px;width:40px;">Type</th>
                            <th style="text-align:left;padding:6px;font-size:11px;">Name</th>
                            <th style="text-align:right;padding:6px;font-size:11px;width:80px;">Size</th>
                            <th style="text-align:center;padding:6px;font-size:11px;width:100px;">Modified</th>
                            ${showMetadata ? '<th style="text-align:center;padding:6px;font-size:11px;width:80px;">Replicas</th>' : ''}
                            <th style="text-align:center;padding:6px;font-size:11px;width:120px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>`;
            
            files.forEach(file => {
                const isDir = file.is_dir;
                const icon = isDir ? '📁' : '📄';
                const size = isDir ? '—' : formatBytes(file.size || 0);
                const modified = file.modified ? new Date(file.modified).toLocaleDateString() : '—';
                const replicas = showMetadata && file.replicas ? file.replicas.length : 0;
                const cached = showMetadata && file.cached ? '💾' : '';
                
                tableHTML += `
                    <tr style="border-bottom:1px solid #222;cursor:pointer;" 
                        onclick="handleFileClick('${bucketName}', '${file.path}', ${isDir})"
                        onmouseover="this.style.backgroundColor='#1a1a1a'" 
                        onmouseout="this.style.backgroundColor='transparent'">
                        <td style="padding:4px;text-align:center;">${icon}</td>
                        <td style="padding:4px;${isDir ? 'color:#6b8cff;font-weight:bold;' : ''}">${file.name}</td>
                        <td style="padding:4px;text-align:right;font-family:monospace;font-size:10px;">${size}</td>
                        <td style="padding:4px;text-align:center;font-family:monospace;font-size:10px;">${modified}</td>
                        ${showMetadata ? `<td style="padding:4px;text-align:center;font-size:10px;">${replicas}${cached}</td>` : ''}
                        <td style="padding:4px;text-align:center;">
                            <div style="display:flex;gap:2px;justify-content:center;">
                                ${!isDir ? `
                                    <button onclick="event.stopPropagation(); downloadFileMCP('${bucketName}', '${file.path}')" 
                                            style="background:#2a5cb8;color:white;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">⬇</button>
                                    <button onclick="event.stopPropagation(); showRenameDialog('${bucketName}', '${file.path}')" 
                                            style="background:#555;color:white;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">✏️</button>
                                ` : ''}
                                <button onclick="event.stopPropagation(); deleteFileMCP('${bucketName}', '${file.path}')" 
                                        style="background:#b52a2a;color:white;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">🗑</button>
                                ${showMetadata ? `
                                    <button onclick="event.stopPropagation(); showFileMetadata('${bucketName}', '${file.path}')" 
                                            style="background:#666;color:white;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">ℹ️</button>
                                ` : ''}
                            </div>
                        </td>
                    </tr>`;
            });
            
            tableHTML += '</tbody></table>';
            fileList.innerHTML = tableHTML;
            
            // Update breadcrumbs
            updateBreadcrumbNav(bucketName, currentPath);
            
        } catch (e) {
            console.error('Error refreshing files:', e);
            fileList.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading files: ' + e.message + '</div>';
        }
    }

    // Handle file click (navigate to directory or show file details)
    function handleFileClick(bucketName, filePath, isDir) {
        if (isDir) {
            // Navigate to directory
            const pathInput = document.getElementById('current-path');
            if (pathInput) {
                const currentPath = pathInput.value || '.';
                const newPath = currentPath === '.' ? filePath : `${currentPath}/${filePath}`;
                pathInput.value = newPath;
                refreshBucketFilesMCP(bucketName);
            }
        } else {
            // Show file metadata
            showFileMetadata(bucketName, filePath);
        }
    }

    // Update breadcrumb navigation
    function updateBreadcrumbNav(bucketName, currentPath) {
        const breadcrumbNav = document.getElementById('breadcrumb-nav');
        if (!breadcrumbNav) return;
        
        const pathParts = currentPath === '.' ? [] : currentPath.split('/');
        const breadcrumbs = ['Root'];
        
        pathParts.forEach((part, index) => {
            breadcrumbs.push(part);
        });
        
        breadcrumbNav.innerHTML = breadcrumbs.map((crumb, index) => {
            const pathToHere = index === 0 ? '.' : pathParts.slice(0, index).join('/');
            return `<span onclick="navigateToBreadcrumb('${bucketName}', '${pathToHere}')" 
                          style="color:#6b8cff;cursor:pointer;text-decoration:underline;">${crumb}</span>`;
        }).join(' / ');
    }

    // Navigation and file operation functions
    window.navigateToBreadcrumb = function(bucketName, path) {
        const pathInput = document.getElementById('current-path');
        if (pathInput) {
            pathInput.value = path;
            refreshBucketFilesMCP(bucketName);
        }
    };

    window.navigateToPath = function(bucketName) {
        refreshBucketFilesMCP(bucketName);
    };

    window.goUpDirectory = function(bucketName) {
        const pathInput = document.getElementById('current-path');
        if (pathInput) {
            const currentPath = pathInput.value || '.';
            if (currentPath !== '.') {
                const pathParts = currentPath.split('/');
                pathParts.pop();
                pathInput.value = pathParts.length > 0 ? pathParts.join('/') : '.';
                refreshBucketFilesMCP(bucketName);
            }
        }
    };

    // File operation functions
    window.uploadFilesMCP = async function(bucketName, files) {
        if (!files || files.length === 0) return;
        
        const pathInput = document.getElementById('current-path');
        const currentPath = pathInput ? pathInput.value || '.' : '.';
        
        try {
            await waitForMCP();
            
            for (const file of files) {
                const reader = new FileReader();
                const fileContent = await new Promise((resolve, reject) => {
                    reader.onload = e => resolve(e.target.result);
                    reader.onerror = reject;
                    reader.readAsText(file);
                });
                
                const filePath = currentPath === '.' ? file.name : `${currentPath}/${file.name}`;
                await MCP.Buckets.uploadFile(bucketName, filePath, fileContent, 'text', true);
            }
            
            // Refresh file list
            await refreshBucketFilesMCP(bucketName);
            alert(`Successfully uploaded ${files.length} file(s)`);
            
        } catch (e) {
            console.error('Error uploading files:', e);
            alert('Error uploading files: ' + e.message);
        }
    };

    window.downloadFileMCP = async function(bucketName, filePath) {
        try {
            await waitForMCP();
            const result = await MCP.Buckets.downloadFile(bucketName, filePath, 'text');
            const content = (result && result.result && result.result.content) || '';
            
            // Create download link
            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filePath.split('/').pop();
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
        } catch (e) {
            console.error('Error downloading file:', e);
            alert('Error downloading file: ' + e.message);
        }
    };

    window.deleteFileMCP = async function(bucketName, filePath) {
        if (!confirm(`Delete ${filePath}?`)) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.deleteFile(bucketName, filePath, true);
            await refreshBucketFilesMCP(bucketName);
            
        } catch (e) {
            console.error('Error deleting file:', e);
            alert('Error deleting file: ' + e.message);
        }
    };

    window.showFileMetadata = async function(bucketName, filePath) {
        const detailsPanel = document.getElementById('file-details-panel');
        const metadataContent = document.getElementById('file-metadata-content');
        
        if (!detailsPanel || !metadataContent) return;
        
        try {
            await waitForMCP();
            const result = await MCP.Buckets.getMetadata(bucketName, filePath, true);
            const metadata = (result && result.result) || {};
            
            let metadataHTML = `<div style="font-size:10px;color:#aaa;margin-bottom:5px;">Path: ${filePath}</div>`;
            metadataHTML += `<div style="display:grid;grid-template-columns:auto 1fr;gap:5px;font-size:11px;">`;
            
            if (metadata.size) metadataHTML += `<span>Size:</span><span>${formatBytes(metadata.size)}</span>`;
            if (result.modified) metadataHTML += `<span>Modified:</span><span>${new Date(result.modified).toLocaleString()}</span>`;
            if (result.created) metadataHTML += `<span>Created:</span><span>${new Date(result.created).toLocaleString()}</span>`;
            if (result.replicas) metadataHTML += `<span>Replicas:</span><span>${result.replicas.length}</span>`;
            if (result.cached !== undefined) metadataHTML += `<span>Cached:</span><span>${result.cached ? 'Yes' : 'No'}</span>`;
            if (result.cache_type) metadataHTML += `<span>Cache Type:</span><span>${result.cache_type}</span>`;
            
            metadataHTML += '</div>';
            
            if (result.replicas && result.replicas.length > 0) {
                metadataHTML += '<div style="margin-top:8px;"><strong>Replicas:</strong></div>';
                metadataHTML += '<div style="font-size:10px;">';
                result.replicas.forEach(replica => {
                    metadataHTML += `<div style="margin:2px 0;">• ${replica.backend || 'Unknown'} (${replica.status || 'unknown'})</div>`;
                });
                metadataHTML += '</div>';
            }
            
            metadataContent.innerHTML = metadataHTML;
            detailsPanel.style.display = 'block';
            
        } catch (e) {
            console.error('Error loading file metadata:', e);
            metadataContent.innerHTML = '<div style="color:red;">Error loading metadata: ' + e.message + '</div>';
            detailsPanel.style.display = 'block';
        }
    };

    window.showCreateFolderDialog = function(bucketName) {
        const folderName = prompt('Enter folder name:');
        if (!folderName) return;
        
        const pathInput = document.getElementById('current-path');
        const currentPath = pathInput ? pathInput.value || '.' : '.';
        const folderPath = currentPath === '.' ? folderName : `${currentPath}/${folderName}`;
        
        createFolderMCP(bucketName, folderPath);
    };

    async function createFolderMCP(bucketName, folderPath) {
        try {
            await waitForMCP();
            await MCP.Buckets.mkdir(bucketName, folderPath, true);
            await refreshBucketFilesMCP(bucketName);
            
        } catch (e) {
            console.error('Error creating folder:', e);
            alert('Error creating folder: ' + e.message);
        }
    }

    window.showRenameDialog = function(bucketName, oldPath) {
        const fileName = oldPath.split('/').pop();
        const newName = prompt('Rename to:', fileName);
        if (!newName || newName === fileName) return;
        
        const pathParts = oldPath.split('/');
        pathParts.pop();
        const newPath = pathParts.length > 0 ? `${pathParts.join('/')}/${newName}` : newName;
        
        renameFileMCP(bucketName, oldPath, newPath);
    };

    async function renameFileMCP(bucketName, oldPath, newPath) {
        try {
            await waitForMCP();
            await MCP.Buckets.renameFile(bucketName, oldPath, newPath, true);
            await refreshBucketFilesMCP(bucketName);
            
        } catch (e) {
            console.error('Error renaming file:', e);
            alert('Error renaming file: ' + e.message);
        }
    }

    window.syncBucketReplicas = async function(bucketName) {
        const btn = document.getElementById('sync-replicas-btn');
        if (btn) {
            btn.disabled = true;
            btn.textContent = '🔄 Syncing...';
        }
        
        try {
            await waitForMCP();
            const result = await MCP.Buckets.syncReplicas(bucketName, false);
            const syncResult = (result && result.result) || {};
            alert(`Replica sync completed. ${syncResult.synced_files || 0} files synced.`);
            
        } catch (e) {
            console.error('Error syncing replicas:', e);
            alert('Error syncing replicas: ' + e.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = '🔄 Sync Replicas';
            }
        }
    };

    window.showBucketPolicySettings = async function(bucketName) {
        const modal = createModal('Bucket Policy: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = '<div style="text-align:center;padding:20px;">Loading policy...</div>';
            
            try {
                await waitForMCP();
                const policyResponse = await MCP.Buckets.getPolicy(bucketName);
                const policy = (policyResponse && policyResponse.result) || {};
                
                modalBody.innerHTML = `
                    <div style="display:grid;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:5px;font-size:12px;">
                                <strong>Replication Factor:</strong>
                            </label>
                            <input type="number" id="replication_factor" min="1" max="10" 
                                   value="${policy.replication_factor || 1}" 
                                   style="width:100px;background:#111;border:1px solid #333;color:white;padding:4px;">
                            <small style="color:#888;margin-left:10px;">Number of replica copies</small>
                        </div>
                        
                        <div>
                            <label style="display:block;margin-bottom:5px;font-size:12px;">
                                <strong>Cache Policy:</strong>
                            </label>
                            <select id="cache_policy" style="width:150px;background:#111;border:1px solid #333;color:white;padding:4px;">
                                <option value="none" ${(policy.cache_policy === 'none') ? 'selected' : ''}>None</option>
                                <option value="memory" ${(policy.cache_policy === 'memory') ? 'selected' : ''}>Memory</option>
                                <option value="disk" ${(policy.cache_policy === 'disk') ? 'selected' : ''}>Disk</option>
                            </select>
                            <small style="color:#888;margin-left:10px;">Caching strategy for files</small>
                        </div>
                        
                        <div>
                            <label style="display:block;margin-bottom:5px;font-size:12px;">
                                <strong>Retention Days:</strong>
                            </label>
                            <input type="number" id="retention_days" min="0" 
                                   value="${policy.retention_days || 0}" 
                                   style="width:100px;background:#111;border:1px solid #333;color:white;padding:4px;">
                            <small style="color:#888;margin-left:10px;">0 = no expiration</small>
                        </div>
                        
                        <div style="margin-top:20px;">
                            <button onclick="saveBucketPolicy('${bucketName}')" 
                                    style="background:#2a5cb8;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;">
                                💾 Save Policy
                            </button>
                        </div>
                    </div>
                `;
                
            } catch (e) {
                console.error('Error loading bucket policy:', e);
                modalBody.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading policy: ' + e.message + '</div>';
            }
        });
    };

    window.saveBucketPolicy = async function(bucketName) {
        const replicationFactor = document.getElementById('replication_factor');
        const cachePolicy = document.getElementById('cache_policy');
        const retentionDays = document.getElementById('retention_days');
        
        if (!replicationFactor || !cachePolicy || !retentionDays) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.updatePolicy(bucketName, {
                replication_factor: parseInt(replicationFactor.value),
                cache_policy: cachePolicy.value,
                retention_days: parseInt(retentionDays.value)
            });
            
            alert('Bucket policy updated successfully');
            
        } catch (e) {
            console.error('Error saving bucket policy:', e);
            alert('Error saving policy: ' + e.message);
        }
    };

    window.createNewBucket = function() {
        const bucketName = prompt('Enter bucket name:');
        if (!bucketName) return;
        
        createBucketMCP(bucketName);
    };

    async function createBucketMCP(bucketName) {
        try {
            await waitForMCP();
            await MCP.Buckets.create(bucketName);
            await loadBuckets(); // Refresh bucket list
            
        } catch (e) {
            console.error('Error creating bucket:', e);
            alert('Error creating bucket: ' + e.message);
        }
    }

    window.deleteBucketMCP = async function(bucketName) {
        if (!confirm(`Delete bucket "${bucketName}" and all its contents?`)) return;
        
        try {
            await waitForMCP();
            await MCP.Buckets.delete(bucketName);
            await loadBuckets(); // Refresh bucket list
            
        } catch (e) {
            console.error('Error deleting bucket:', e);
            alert('Error deleting bucket: ' + e.message);
        }
    };

    // Make functions globally available
    window.refreshBucketFilesMCP = refreshBucketFilesMCP;

    // Make updateElement globally available for dashboard UI
    if (typeof window !== 'undefined') {
        window.MCP = MCP;
        window.updateElement = updateElement;
    } else if (typeof globalThis !== 'undefined') {
        globalThis.MCP = MCP;
        globalThis.updateElement = updateElement;
    }
})(this);
