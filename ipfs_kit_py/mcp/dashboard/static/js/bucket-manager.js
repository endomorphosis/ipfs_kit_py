/**
 * Bucket Management Functions for MCP Dashboard
 * Handles file operations, bucket settings, and advanced features
 */

// File Management Functions
function handleFileDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    
    const uploadArea = document.getElementById('file-upload-area');
    uploadArea.classList.remove('border-blue-400', 'bg-blue-50');
    
    const files = event.dataTransfer.files;
    if (files.length > 0 && selectedBucket) {
        uploadFiles(Array.from(files));
    }
}

function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    
    const uploadArea = document.getElementById('file-upload-area');
    uploadArea.classList.add('border-blue-400', 'bg-blue-50');
}

function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    
    const uploadArea = document.getElementById('file-upload-area');
    uploadArea.classList.remove('border-blue-400', 'bg-blue-50');
}

function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    if (files.length > 0 && selectedBucket) {
        uploadFiles(files);
    }
}

async function uploadFiles(files) {
    if (!selectedBucket) {
        showNotification('Please select a bucket first', 'error');
        return;
    }
    
    const uploadArea = document.getElementById('file-upload-area');
    const originalContent = uploadArea.innerHTML;
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        try {
            // Show progress
            uploadArea.innerHTML = `
                <div class="text-center">
                    <i class="fas fa-upload text-4xl text-blue-500 mb-4"></i>
                    <p class="text-lg font-medium mb-2">Uploading ${file.name}</p>
                    <div class="w-full bg-gray-200 rounded-full h-2 mb-4">
                        <div class="bg-blue-600 h-2 rounded-full" style="width: ${((i + 1) / files.length) * 100}%"></div>
                    </div>
                    <p class="text-sm text-gray-500">${i + 1} of ${files.length} files</p>
                </div>
            `;
            
            // Upload file
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch(`/api/buckets/${selectedBucket.name}/upload`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`);
            }
            
            const result = await response.json();
            console.log(`Uploaded ${file.name}:`, result);
            
        } catch (error) {
            console.error(`Error uploading ${file.name}:`, error);
            showNotification(`Failed to upload ${file.name}: ${error.message}`, 'error');
        }
    }
    
    // Restore original content
    uploadArea.innerHTML = originalContent;
    
    // Refresh file list
    await loadBucketFiles(selectedBucket.name);
    showNotification(`Uploaded ${files.length} file(s) successfully`, 'success');
}

async function downloadFile(filename) {
    if (!selectedBucket) return;
    
    try {
        const response = await fetch(`/api/buckets/${selectedBucket.name}/download/${encodeURIComponent(filename)}`);
        
        if (!response.ok) {
            throw new Error(`Download failed: ${response.statusText}`);
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showNotification(`Downloaded ${filename}`, 'success');
    } catch (error) {
        console.error('Error downloading file:', error);
        showNotification(`Failed to download ${filename}: ${error.message}`, 'error');
    }
}

async function deleteFile(filename) {
    if (!selectedBucket || !confirm(`Are you sure you want to delete "${filename}"?`)) return;
    
    try {
        const response = await fetch(`/api/buckets/${selectedBucket.name}/files/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`Delete failed: ${response.statusText}`);
        }
        
        await loadBucketFiles(selectedBucket.name);
        showNotification(`Deleted ${filename}`, 'success');
    } catch (error) {
        console.error('Error deleting file:', error);
        showNotification(`Failed to delete ${filename}: ${error.message}`, 'error');
    }
}

function showFileMenu(filename, event) {
    event.stopPropagation();
    
    // Remove any existing menus
    document.querySelectorAll('.file-menu').forEach(menu => menu.remove());
    
    const menu = document.createElement('div');
    menu.className = 'file-menu absolute bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 py-1';
    menu.style.left = event.pageX + 'px';
    menu.style.top = event.pageY + 'px';
    
    menu.innerHTML = `
        <button onclick="downloadFile('${escapeHtml(filename)}')" class="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
            <i class="fas fa-download mr-2"></i> Download
        </button>
        <button onclick="renameFile('${escapeHtml(filename)}')" class="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
            <i class="fas fa-edit mr-2"></i> Rename
        </button>
        <button onclick="copyFile('${escapeHtml(filename)}')" class="block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
            <i class="fas fa-copy mr-2"></i> Copy
        </button>
        <hr class="border-gray-200 dark:border-gray-700 my-1">
        <button onclick="deleteFile('${escapeHtml(filename)}')" class="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900">
            <i class="fas fa-trash mr-2"></i> Delete
        </button>
    `;
    
    document.body.appendChild(menu);
    
    // Close menu when clicking elsewhere
    setTimeout(() => {
        document.addEventListener('click', function closeMenu() {
            menu.remove();
            document.removeEventListener('click', closeMenu);
        });
    }, 100);
}

// File filtering and view functions
function filterFiles() {
    const searchTerm = document.getElementById('file-search').value.toLowerCase();
    filteredFiles = bucketFiles.filter(file => 
        file.name.toLowerCase().includes(searchTerm)
    );
    renderFileList();
}

function setFileView(view) {
    currentFileView = view;
    
    // Update button styles
    const listBtn = document.getElementById('list-view-btn');
    const gridBtn = document.getElementById('grid-view-btn');
    
    if (view === 'list') {
        listBtn.classList.add('bg-blue-500', 'text-white');
        listBtn.classList.remove('bg-gray-200', 'text-gray-700');
        gridBtn.classList.add('bg-gray-200', 'text-gray-700');
        gridBtn.classList.remove('bg-blue-500', 'text-white');
    } else {
        gridBtn.classList.add('bg-blue-500', 'text-white');
        gridBtn.classList.remove('bg-gray-200', 'text-gray-700');
        listBtn.classList.add('bg-gray-200', 'text-gray-700');
        listBtn.classList.remove('bg-blue-500', 'text-white');
    }
    
    renderFileList();
}

function refreshBucketFiles() {
    if (selectedBucket) {
        loadBucketFiles(selectedBucket.name);
        showNotification('Files refreshed', 'success');
    }
}

// Bucket Management Functions
function showCreateBucketModal() {
    document.getElementById('create-bucket-modal').classList.remove('hidden');
}

function hideCreateBucketModal() {
    document.getElementById('create-bucket-modal').classList.add('hidden');
    document.getElementById('create-bucket-form').reset();
}

async function createBucket(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const bucketData = {
        name: formData.get('name') || document.getElementById('new-bucket-name').value,
        backend: formData.get('backend') || document.getElementById('new-bucket-backend').value,
        description: formData.get('description') || document.getElementById('new-bucket-description').value,
        bucket_type: 'general'
    };
    
    if (!bucketData.name.trim()) {
        showNotification('Bucket name is required', 'error');
        return;
    }
    
    try {
        const response = await window.ipfsKitAPI.createBucket(bucketData);
        hideCreateBucketModal();
        await loadBuckets();
        showNotification(`Bucket "${bucketData.name}" created successfully`, 'success');
    } catch (error) {
        console.error('Error creating bucket:', error);
        showNotification(`Failed to create bucket: ${error.message}`, 'error');
    }
}

function showBucketSettingsModal() {
    if (!selectedBucket) return;
    
    // Populate form with current bucket data
    document.getElementById('settings-bucket-name').value = selectedBucket.name;
    document.getElementById('settings-bucket-backend').value = selectedBucket.backend || '';
    document.getElementById('settings-bucket-description').value = selectedBucket.description || '';
    
    // Populate settings based on bucket configuration
    if (selectedBucket.settings) {
        document.getElementById('settings-storage-quota').value = selectedBucket.settings.storage_quota || '';
        document.getElementById('settings-max-files').value = selectedBucket.settings.max_files || '';
        document.getElementById('settings-max-file-size').value = selectedBucket.settings.max_file_size || '';
        document.getElementById('settings-retention-days').value = selectedBucket.settings.retention_days || '';
        document.getElementById('settings-enable-cache').checked = selectedBucket.settings.cache_enabled || false;
        document.getElementById('settings-cache-ttl').value = selectedBucket.settings.cache_ttl || '';
        document.getElementById('settings-cache-size').value = selectedBucket.settings.cache_size || '';
        document.getElementById('settings-enable-vector-search').checked = selectedBucket.settings.vector_search || false;
        document.getElementById('settings-vector-index-type').value = selectedBucket.settings.vector_index_type || 'hnsw';
        document.getElementById('settings-enable-knowledge-graph').checked = selectedBucket.settings.knowledge_graph || false;
        document.getElementById('settings-search-index-location').value = selectedBucket.settings.search_index_location || 'Auto-generated';
        document.getElementById('settings-public-access').checked = selectedBucket.settings.public_access || false;
    }
    
    document.getElementById('bucket-settings-modal').classList.remove('hidden');
    showSettingsTab('general'); // Default to general tab
}

function hideBucketSettingsModal() {
    document.getElementById('bucket-settings-modal').classList.add('hidden');
}

function showSettingsTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.settings-tab-content').forEach(tab => tab.classList.add('hidden'));
    
    // Show selected tab content
    document.getElementById(`settings-${tabName}`).classList.remove('hidden');
    
    // Update tab button styles
    document.querySelectorAll('.settings-tab-btn').forEach(btn => {
        btn.classList.remove('border-blue-500', 'text-blue-600', 'active');
        btn.classList.add('border-transparent', 'text-gray-500');
    });
    
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('border-blue-500', 'text-blue-600', 'active');
    document.querySelector(`[data-tab="${tabName}"]`).classList.remove('border-transparent', 'text-gray-500');
}

async function saveBucketSettings() {
    if (!selectedBucket) return;
    
    const settings = {
        description: document.getElementById('settings-bucket-description').value,
        storage_quota: parseInt(document.getElementById('settings-storage-quota').value) || null,
        max_files: parseInt(document.getElementById('settings-max-files').value) || null,
        max_file_size: parseInt(document.getElementById('settings-max-file-size').value) || null,
        retention_days: parseInt(document.getElementById('settings-retention-days').value) || null,
        cache_enabled: document.getElementById('settings-enable-cache').checked,
        cache_ttl: parseInt(document.getElementById('settings-cache-ttl').value) || 3600,
        cache_size: parseInt(document.getElementById('settings-cache-size').value) || null,
        vector_search: document.getElementById('settings-enable-vector-search').checked,
        vector_index_type: document.getElementById('settings-vector-index-type').value,
        knowledge_graph: document.getElementById('settings-enable-knowledge-graph').checked,
        public_access: document.getElementById('settings-public-access').checked
    };
    
    try {
        const response = await fetch(`/api/buckets/${selectedBucket.name}/settings`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        if (!response.ok) {
            throw new Error(`Settings update failed: ${response.statusText}`);
        }
        
        hideBucketSettingsModal();
        await loadBuckets();
        showNotification('Bucket settings updated successfully', 'success');
    } catch (error) {
        console.error('Error updating bucket settings:', error);
        showNotification(`Failed to update settings: ${error.message}`, 'error');
    }
}

async function deleteBucket() {
    if (!selectedBucket) return;
    
    const bucketName = selectedBucket.name;
    const confirmText = prompt(`To delete this bucket, type its name: ${bucketName}`);
    
    if (confirmText !== bucketName) {
        showNotification('Bucket name mismatch. Deletion cancelled.', 'error');
        return;
    }
    
    try {
        const response = await window.ipfsKitAPI.deleteBucket(bucketName);
        hideBucketSettingsModal();
        selectedBucket = null;
        document.getElementById('bucket-details-panel').classList.add('hidden');
        document.getElementById('no-bucket-selected').classList.remove('hidden');
        await loadBuckets();
        showNotification(`Bucket "${bucketName}" deleted successfully`, 'success');
    } catch (error) {
        console.error('Error deleting bucket:', error);
        showNotification(`Failed to delete bucket: ${error.message}`, 'error');
    }
}

// Utility function for notifications
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        type === 'warning' ? 'bg-yellow-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    
    notification.innerHTML = `
        <div class="flex items-center">
            <i class="fas ${
                type === 'success' ? 'fa-check-circle' :
                type === 'error' ? 'fa-exclamation-circle' :
                type === 'warning' ? 'fa-exclamation-triangle' :
                'fa-info-circle'
            } mr-2"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Additional file operations
async function renameFile(oldName) {
    if (!selectedBucket) return;
    
    const newName = prompt('Enter new filename:', oldName);
    if (!newName || newName === oldName) return;
    
    try {
        const response = await fetch(`/api/buckets/${selectedBucket.name}/files/${encodeURIComponent(oldName)}/rename`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_name: newName })
        });
        
        if (!response.ok) {
            throw new Error(`Rename failed: ${response.statusText}`);
        }
        
        await loadBucketFiles(selectedBucket.name);
        showNotification(`Renamed "${oldName}" to "${newName}"`, 'success');
    } catch (error) {
        console.error('Error renaming file:', error);
        showNotification(`Failed to rename file: ${error.message}`, 'error');
    }
}

async function copyFile(filename) {
    if (!selectedBucket) return;
    
    // TODO: Implement file copy functionality
    showNotification('Copy functionality coming soon', 'info');
}