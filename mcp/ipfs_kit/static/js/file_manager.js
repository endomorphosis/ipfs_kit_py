const fileManager = {
    currentPath: '/',
    viewMode: 'list', // 'list' or 'grid'
    selectedItems: new Set(),
    uploadQueue: [],
    uploading: false,

    init: function() {
        console.log('File Manager Initializing...');
        this.elements = {
            fileManagerList: document.getElementById('fileManagerList'),
            fileManagerBreadcrumb: document.getElementById('fileManagerBreadcrumb'),
            fileUploadInput: document.getElementById('fileUploadInput'),
            dropZone: document.getElementById('dropZone'),
            createFolderModal: document.getElementById('createFolderModal'),
            newFolderNameInput: document.getElementById('newFolderName'),
            renameModal: document.getElementById('renameModal'),
            newItemNameInput: document.getElementById('newItemName'),
            moveModal: document.getElementById('moveModal'),
            targetPathInput: document.getElementById('targetPath'),
            uploadProgressContainer: document.getElementById('uploadProgress'),
            uploadProgressList: document.getElementById('uploadProgressList'),
            gridViewBtn: document.getElementById('gridViewBtn'),
            listViewBtn: document.getElementById('listViewBtn'),
            fileSearchInput: document.getElementById('fileSearch')
        };

        this.addEventListeners();
        this.refresh();
    },

    addEventListeners: function() {
        if (this.elements.fileUploadInput) {
            this.elements.fileUploadInput.addEventListener('change', (e) => this.handleFileUpload(e.target.files));
        }

        if (this.elements.dropZone) {
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                this.elements.dropZone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                }, false);
            });

            this.elements.dropZone.addEventListener('dragenter', () => this.elements.dropZone.classList.add('active'));
            this.elements.dropZone.addEventListener('dragleave', () => this.elements.dropZone.classList.remove('active'));
            this.elements.dropZone.addEventListener('drop', (e) => {
                this.elements.dropZone.classList.remove('active');
                this.handleFileUpload(e.dataTransfer.files);
            });
        }

        if (this.elements.fileManagerList) {
            this.elements.fileManagerList.addEventListener('click', (e) => {
                const item = e.target.closest('.file-item');
                if (item) {
                    const path = item.dataset.path;
                    const type = item.dataset.type;
                    if (type === 'folder') {
                        this.navigateTo(path);
                    } else {
                        // Handle file click (e.g., open preview, download)
                        console.log('File clicked:', path);
                    }
                }
            });
            this.elements.fileManagerList.addEventListener('contextmenu', (e) => this.showContextMenu(e));
        }

        if (this.elements.gridViewBtn) {
            this.elements.gridViewBtn.addEventListener('click', () => this.changeView('grid'));
        }
        if (this.elements.listViewBtn) {
            this.elements.listViewBtn.addEventListener('click', () => this.changeView('list'));
        }
        if (this.elements.fileSearchInput) {
            this.elements.fileSearchInput.addEventListener('keyup', (e) => this.filterFiles(e.target.value));
        }

        // Global click listener to hide context menu
        document.addEventListener('click', () => {
            const contextMenu = document.getElementById('contextMenu');
            if (contextMenu) contextMenu.style.display = 'none';
        });
    },

    refresh: async function() {
        console.log('Refreshing file list for path:', this.currentPath);
        if (!this.elements.fileManagerList) {
            console.error('fileManagerList element not found.');
            return;
        }
        this.elements.fileManagerList.innerHTML = '<div class="loading">Loading files...</div>';
        this.updateBreadcrumb();
        this.updateFileManagerStats();

        try {
            const response = await fetch(`/api/files/list?path=${encodeURIComponent(this.currentPath)}`);
            const data = await response.json();

            if (data.success) {
                this.renderFiles(data.files);
            } else {
                this.elements.fileManagerList.innerHTML = `<div class="empty-state">Error: ${data.error || 'Failed to load files.'}</div>`;
                console.error('Error listing files:', data.error);
            }
        } catch (error) {
            this.elements.fileManagerList.innerHTML = `<div class="empty-state">Error: ${error.message || 'Network error.'}</div>`;
            console.error('Network error listing files:', error);
        }
    },

    renderFiles: function(files) {
        this.elements.fileManagerList.innerHTML = '';
        if (files.length === 0) {
            this.elements.fileManagerList.innerHTML = '<div class="empty-state"><span class="icon">📂</span><p>This folder is empty.</p></div>';
            return;
        }

        // Add '..' for navigating up
        if (this.currentPath !== '/') {
            const upFolder = document.createElement('div');
            upFolder.className = 'file-item';
            upFolder.dataset.path = this.getParentPath(this.currentPath);
            upFolder.dataset.type = 'folder';
            upFolder.innerHTML = `
                <span class="file-icon">⬆️</span>
                <div class="file-info">
                    <span class="file-name">..</span>
                    <span class="file-meta">Parent Directory</span>
                </div>
            `;
            this.elements.fileManagerList.appendChild(upFolder);
        }

        files.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.dataset.path = file.path;
            fileItem.dataset.type = file.type;
            fileItem.dataset.name = file.name;

            const icon = file.type === 'folder' ? '📁' : this.getFileIcon(file.name);
            const size = file.type === 'file' ? this.formatBytes(file.size) : '';
            const modified = file.modified_at ? new Date(file.modified_at).toLocaleString() : '';

            fileItem.innerHTML = `
                <span class="file-icon">${icon}</span>
                <div class="file-info">
                    <span class="file-name">${file.name}</span>
                    <span class="file-meta">${size} ${modified}</span>
                </div>
                <div class="file-actions">
                    ${file.type === 'file' ? `<button class="file-action-btn" onclick="fileManager.downloadFile('${file.path}')">⬇️</button>` : ''}
                    <button class="file-action-btn" onclick="fileManager.showRenameModal('${file.path}', '${file.name}')">✏️</button>
                    <button class="file-action-btn" onclick="fileManager.showMoveModal('${file.path}')">➡️</button>
                    <button class="file-action-btn delete" onclick="fileManager.deleteItem('${file.path}')">🗑️</button>
                </div>
            `;
            this.elements.fileManagerList.appendChild(fileItem);
        });

        this.changeView(this.viewMode); // Apply current view mode
    },

    navigateTo: function(path) {
        this.currentPath = path;
        this.refresh();
    },

    updateBreadcrumb: function() {
        if (!this.elements.fileManagerBreadcrumb) return;
        this.elements.fileManagerBreadcrumb.innerHTML = '';
        let pathParts = this.currentPath.split('/').filter(p => p);
        
        let current = '/';
        const rootCrumb = document.createElement('span');
        rootCrumb.className = 'breadcrumb-item';
        rootCrumb.textContent = 'Root';
        rootCrumb.onclick = () => this.navigateTo('/');
        this.elements.fileManagerBreadcrumb.appendChild(rootCrumb);

        pathParts.forEach(part => {
            current = (current === '/' ? '' : current) + '/' + part;
            const crumb = document.createElement('span');
            crumb.className = 'breadcrumb-item';
            crumb.textContent = part;
            crumb.dataset.path = current;
            crumb.onclick = () => this.navigateTo(crumb.dataset.path);
            this.elements.fileManagerBreadcrumb.appendChild(document.createTextNode(' / '));
            this.elements.fileManagerBreadcrumb.appendChild(crumb);
        });
    },

    getParentPath: function(path) {
        const parts = path.split('/').filter(p => p);
        if (parts.length <= 1) {
            return '/';
        }
        return '/' + parts.slice(0, -1).join('/');
    },

    getFileIcon: function(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        switch (ext) {
            case 'jpg': case 'jpeg': case 'png': case 'gif': case 'bmp': case 'svg':
                return '🖼️';
            case 'mp4': case 'mov': case 'avi':
                return '🎞️';
            case 'mp3': case 'wav': case 'ogg':
                return '🎵';
            case 'pdf':
                return '📄';
            case 'doc': case 'docx':
                return '📝';
            case 'xls': case 'xlsx':
                return '📊';
            case 'zip': case 'tar': case 'gz':
                return '📦';
            case 'js': case 'ts': case 'py': case 'html': case 'css': case 'json':
                return '💻';
            case 'txt': case 'md':
                return '📄';
            default:
                return '❓';
        }
    },

    formatBytes: function(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    updateFileManagerStats: async function() {
        if (!this.elements.fileManagerStats) return;
        this.elements.fileManagerStats.innerHTML = '<div class="loading">Loading stats...</div>';
        try {
            const response = await fetch('/api/analytics/files');
            const data = await response.json();
            if (data.success) {
                const stats = data.file_statistics;
                this.elements.fileManagerStats.innerHTML = `
                    <div class="stat-item"><span class="label">Total Files:</span><span class="value">${stats.total_files || 0}</span></div>
                    <div class="stat-item"><span class="label">Total Size:</span><span class="value">${this.formatBytes(stats.total_size || 0)}</span></div>
                    <div class="stat-item"><span class="label">Avg File Size:</span><span class="value">${this.formatBytes(stats.average_file_size || 0)}</span></div>
                    <div class="stat-item"><span class="label">Folders:</span><span class="value">${stats.total_folders || 0}</span></div>
                `;
            } else {
                this.elements.fileManagerStats.innerHTML = `<div class="empty-state">Error: ${data.error || 'Failed to load stats.'}</div>`;
            }
        } catch (error) {
            this.elements.fileManagerStats.innerHTML = `<div class="empty-state">Error: ${error.message || 'Network error.'}</div>`;
        }
    },

    triggerUpload: function() {
        if (this.elements.fileUploadInput) {
            this.elements.fileUploadInput.click();
        }
    },

    handleFileUpload: async function(files) {
        if (files.length === 0) return;

        for (let i = 0; i < files.length; i++) {
            this.uploadQueue.push(files[i]);
        }
        this.processUploadQueue();
    },

    processUploadQueue: async function() {
        if (this.uploading || this.uploadQueue.length === 0) return;

        this.uploading = true;
        this.elements.uploadProgressContainer.classList.add('visible');

        const file = this.uploadQueue.shift();
        const uploadItem = document.createElement('div');
        uploadItem.className = 'upload-item';
        uploadItem.innerHTML = `
            <span class="file-name">${file.name}</span>
            <div class="progress-bar"><div class="progress-fill" style="width: 0%;"></div></div>
            <span class="status">Uploading...</span>
        `;
        this.elements.uploadProgressList.appendChild(uploadItem);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('path', this.currentPath);

        try {
            const response = await fetch('/api/files/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            if (result.success) {
                uploadItem.querySelector('.progress-fill').style.width = '100%';
                uploadItem.querySelector('.status').textContent = 'Completed';
                uploadItem.querySelector('.status').style.color = '#28a745';
                this.refresh();
            } else {
                uploadItem.querySelector('.status').textContent = `Failed: ${result.error || 'Unknown error'}`;
                uploadItem.querySelector('.status').style.color = '#dc3545';
                console.error('Upload failed:', result.error);
            }
        } catch (error) {
            uploadItem.querySelector('.status').textContent = `Failed: ${error.message}`;
            uploadItem.querySelector('.status').style.color = '#dc3545';
            console.error('Upload error:', error);
        } finally {
            this.uploading = false;
            if (this.uploadQueue.length === 0) {
                setTimeout(() => this.elements.uploadProgressContainer.classList.remove('visible'), 2000);
                this.elements.uploadProgressList.innerHTML = ''; // Clear list after all uploads
            }
            this.processUploadQueue(); // Process next file
        }
    },

    showCreateFolderModal: function() {
        if (this.elements.createFolderModal) {
            this.elements.createFolderModal.style.display = 'block';
            if (this.elements.newFolderNameInput) {
                this.elements.newFolderNameInput.value = '';
                this.elements.newFolderNameInput.focus();
            }
        }
    },

    createNewFolder: async function() {
        const folderName = this.elements.newFolderNameInput ? this.elements.newFolderNameInput.value : '';
        if (!folderName) {
            alert('Folder name cannot be empty.');
            return;
        }

        try {
            const response = await fetch('/api/files/create-folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: this.currentPath, name: folderName })
            });
            const result = await response.json();
            if (result.success) {
                alert('Folder created successfully!');
                this.closeModal('createFolderModal');
                this.refresh();
            } else {
                alert(`Failed to create folder: ${result.error}`);
            }
        } catch (error) {
            alert(`Error creating folder: ${error.message}`);
        }
    },

    showRenameModal: function(oldPath, oldName) {
        this.itemToRename = { oldPath, oldName };
        if (this.elements.renameModal) {
            this.elements.renameModal.style.display = 'block';
            if (this.elements.newItemNameInput) {
                this.elements.newItemNameInput.value = oldName;
                this.elements.newItemNameInput.focus();
            }
        }
    },

    renameItem: async function() {
        const newName = this.elements.newItemNameInput ? this.elements.newItemNameInput.value : '';
        if (!newName) {
            alert('New name cannot be empty.');
            return;
        }
        if (!this.itemToRename) return;

        try {
            const response = await fetch('/api/files/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ oldPath: this.itemToRename.oldPath, newName: newName })
            });
            const result = await response.json();
            if (result.success) {
                alert('Item renamed successfully!');
                this.closeModal('renameModal');
                this.refresh();
            } else {
                alert(`Failed to rename item: ${result.error}`);
            }
        } catch (error) {
            alert(`Error renaming item: ${error.message}`);
        }
    },

    showMoveModal: function(sourcePath) {
        this.itemToMove = { sourcePath };
        if (this.elements.moveModal) {
            this.elements.moveModal.style.display = 'block';
            if (this.elements.targetPathInput) {
                this.elements.targetPathInput.value = this.currentPath; // Default to current path
                this.elements.targetPathInput.focus();
            }
        }
    },

    moveItem: async function() {
        const targetPath = this.elements.targetPathInput ? this.elements.targetPathInput.value : '';
        if (!targetPath) {
            alert('Target path cannot be empty.');
            return;
        }
        if (!this.itemToMove) return;

        try {
            const response = await fetch('/api/files/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sourcePath: this.itemToMove.sourcePath, targetPath: targetPath })
            });
            const result = await response.json();
            if (result.success) {
                alert('Item moved successfully!');
                this.closeModal('moveModal');
                this.refresh();
            } else {
                alert(`Failed to move item: ${result.error}`);
            }
        } catch (error) {
            alert(`Error moving item: ${error.message}`);
        }
    },

    deleteItem: async function(path) {
        if (!confirm(`Are you sure you want to delete ${path}? This cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch('/api/files/delete', {
                method: 'POST', // Using POST for delete with body
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });
            const result = await response.json();
            if (result.success) {
                alert('Item deleted successfully!');
                this.refresh();
            } else {
                alert(`Failed to delete item: ${result.error}`);
            }
        } catch (error) {
            alert(`Error deleting item: ${error.message}`);
        }
    },

    downloadFile: function(path) {
        const url = `/api/files/download?path=${encodeURIComponent(path)}`;
        window.open(url, '_blank');
    },

    changeView: function(mode) {
        this.viewMode = mode;
        if (this.elements.fileManagerList) {
            this.elements.fileManagerList.classList.remove('list-view', 'grid-view');
            this.elements.fileManagerList.classList.add(`${mode}-view`);
        }
        if (this.elements.listViewBtn) {
            this.elements.listViewBtn.classList.toggle('active', mode === 'list');
        }
        if (this.elements.gridViewBtn) {
            this.elements.gridViewBtn.classList.toggle('active', mode === 'grid');
        }
    },

    filterFiles: function(query) {
        const items = this.elements.fileManagerList.querySelectorAll('.file-item');
        items.forEach(item => {
            const name = item.dataset.name || '';
            if (name.toLowerCase().includes(query.toLowerCase())) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    },

    showContextMenu: function(e) {
        e.preventDefault();
        const contextMenu = document.getElementById('contextMenu');
        if (!contextMenu) return;

        const item = e.target.closest('.file-item');
        if (!item) {
            contextMenu.style.display = 'none';
            return;
        }

        const path = item.dataset.path;
        const type = item.dataset.type;
        const name = item.dataset.name;

        // Populate context menu actions
        contextMenu.innerHTML = `
            ${type === 'file' ? `<li class="context-menu-item" data-action="open">Open</li>` : ''}
            ${type === 'file' ? `<li class="context-menu-item" data-action="download">Download</li>` : ''}
            <li class="context-menu-separator"></li>
            <li class="context-menu-item" data-action="rename">Rename</li>
            <li class="context-menu-item" data-action="move">Move</li>
            <li class="context-menu-separator"></li>
            <li class="context-menu-item danger" data-action="delete">Delete</li>
        `;

        // Attach event listeners to context menu items
        contextMenu.querySelectorAll('.context-menu-item').forEach(menuItem => {
            menuItem.onclick = () => {
                contextMenu.style.display = 'none';
                const action = menuItem.dataset.action;
                switch (action) {
                    case 'open':
                        console.log('Open:', path);
                        // Implement file opening/preview
                        break;
                    case 'download':
                        this.downloadFile(path);
                        break;
                    case 'rename':
                        this.showRenameModal(path, name);
                        break;
                    case 'move':
                        this.showMoveModal(path);
                        break;
                    case 'delete':
                        this.deleteItem(path);
                        break;
                }
            };
        });

        // Position and display context menu
        contextMenu.style.top = `${e.clientY}px`;
        contextMenu.style.left = `${e.clientX}px`;
        contextMenu.style.display = 'block';
    },

    closeModal: function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    }
};

// Expose fileManager to global scope for direct calls from HTML
window.fileManager = fileManager;