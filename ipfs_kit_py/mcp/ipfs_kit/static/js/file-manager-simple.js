/**
 * Simple File Manager Integration
 * Works with the existing file_manager.js
 */

/**
 * Simple File Manager Integration
 * Works with the existing file_manager.js
 */

async function loadFileManagerTab() {
    console.log('Loading File Manager tab...');
    
    // Wait for fileManager to be available from file_manager.js
    if (typeof fileManager !== 'undefined' && fileManager.refresh) {
        try {
            console.log('File Manager found, refreshing...');
            await fileManager.refresh();
            console.log('File Manager tab loaded successfully');
        } catch (error) {
            console.error('Error refreshing file manager:', error);
        }
    } else {
        // If fileManager is not available, provide basic functionality
        console.warn('Main fileManager not found, providing basic functionality');
        await loadBasicFileManager();
    }
}

async function loadBasicFileManager() {
    const container = document.getElementById('fileManagerList') || 
                     document.querySelector('#file-manager .file-list');
    
    if (!container) {
        console.error('File manager container not found');
        return;
    }
    
    try {
        // Load basic file list
        const response = await fetch('/api/files/');
        const data = await response.json();
        
        if (data.success) {
            displayBasicFileList(container, data.files);
        } else {
            throw new Error(data.error || 'Failed to load files');
        }
    } catch (error) {
        console.error('Error loading basic file manager:', error);
        container.innerHTML = `<div style="color: red;">Error: ${error.message}</div>`;
    }
}

function displayBasicFileList(container, files) {
    if (!files || files.length === 0) {
        container.innerHTML = '<div class="empty-state">No files found</div>';
        return;
    }
    
    container.innerHTML = files.map(file => `
        <div class="file-item">
            <span class="file-icon">${file.type === 'directory' ? '📁' : '📄'}</span>
            <span class="file-name">${file.name}</span>
            <span class="file-size">${formatFileSize(file.size || 0)}</span>
            <span class="file-actions">
                <button onclick="downloadFile('${file.name}')" title="Download">📥</button>
                <button onclick="deleteFile('${file.name}')" title="Delete">🗑️</button>
            </span>
        </div>
    `).join('');
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function downloadFile(filename) {
    try {
        const response = await fetch(`/api/files/download?path=${encodeURIComponent(filename)}`);
        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } else {
            throw new Error('Download failed');
        }
    } catch (error) {
        console.error('Download error:', error);
        alert('Download failed: ' + error.message);
    }
}

async function deleteFile(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    
    try {
        const response = await fetch('/api/files/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filename })
        });
        
        const data = await response.json();
        if (data.success) {
            console.log('File deleted successfully');
            // Refresh the file list
            await loadFileManagerTab();
        } else {
            throw new Error(data.error || 'Delete failed');
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('Delete failed: ' + error.message);
    }
}

// Export functions globally
window.loadFileManagerTab = loadFileManagerTab;

function displaySimpleFileList(files) {
    const fileList = document.getElementById('fileManagerList') || document.getElementById('fileList');
    if (!fileList) {
        console.error('File list element not found');
        return;
    }
    
    if (!files || files.length === 0) {
        fileList.innerHTML = '<div class="empty-state">No files found</div>';
        return;
    }
    
    fileList.innerHTML = files.map(file => `
        <div class="file-item ${file.type}" data-name="${file.name}" data-path="${file.path}">
            <span class="file-icon">${file.type === 'directory' ? '📁' : '📄'}</span>
            <span class="file-name">${file.name}</span>
            <span class="file-size">${formatBytes(file.size || 0)}</span>
            <span class="file-actions">
                ${file.type === 'file' ? `<button onclick="downloadFileSimple('${file.name}')">📥 Download</button>` : ''}
                <button onclick="deleteFileSimple('${file.name}')">🗑️ Delete</button>
            </span>
        </div>
    `).join('');
}

async function downloadFileSimple(filename) {
    try {
        const blob = await dashboardAPI.downloadFile(filename);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Download error:', error);
        alert('Download failed: ' + error.message);
    }
}

async function deleteFileSimple(filename) {
    if (confirm(`Are you sure you want to delete ${filename}?`)) {
        try {
            const response = await dashboardAPI.deleteFile(filename);
            if (response.success) {
                await loadFileManagerTab(); // Refresh file list
            } else {
                throw new Error(response.error || 'Delete failed');
            }
        } catch (error) {
            console.error('Delete error:', error);
            alert('Delete failed: ' + error.message);
        }
    }
}

async function uploadFileSimple() {
    const fileInput = document.getElementById('fileUploadInput');
    if (!fileInput || fileInput.files.length === 0) {
        alert('Please select a file to upload');
        return;
    }
    
    try {
        const response = await dashboardAPI.uploadFile(fileInput.files[0]);
        if (response.success) {
            await loadFileManagerTab(); // Refresh file list
            fileInput.value = ''; // Clear the input
        } else {
            throw new Error(response.error || 'Upload failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        alert('Upload failed: ' + error.message);
    }
}

function createFolderPrompt() {
    const folderName = prompt('Enter folder name:');
    if (folderName) {
        createFolderSimple(folderName);
    }
}

async function createFolderSimple(folderName) {
    try {
        const response = await dashboardAPI.createFolder(folderName);
        if (response.success) {
            await loadFileManagerTab(); // Refresh file list
        } else {
            throw new Error(response.error || 'Create folder failed');
        }
    } catch (error) {
        console.error('Create folder error:', error);
        alert('Create folder failed: ' + error.message);
    }
}
