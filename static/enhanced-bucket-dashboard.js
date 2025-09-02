// Enhanced Professional Bucket Management Dashboard
class EnhancedBucketDashboard {
    constructor() {
        this.mcp = window.mcpClient;
        this.buckets = [];
        this.selectedBucket = null;
        this.currentView = 'grid'; // grid or list
        this.currentSort = { field: 'name', direction: 'asc' };
        this.filters = { status: '', tier: '' };
        this.searchQuery = '';
        this.selectedFiles = new Set();
        this.currentPath = '';
        
        this.init();
        this.setupEventListeners();
        this.loadBuckets();
    }

    init() {
        this.initializeDefaultBuckets();
        this.setupDragAndDrop();
        this.setupKeyboardShortcuts();
    }

    setupEventListeners() {
        // Search functionality
        document.getElementById('bucket-search')?.addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.filterAndRenderBuckets();
        });

        // View toggles
        document.getElementById('view-grid')?.addEventListener('click', () => this.setView('grid'));
        document.getElementById('view-list')?.addEventListener('click', () => this.setView('list'));

        // Filters
        document.getElementById('bucket-filter-status')?.addEventListener('change', (e) => {
            this.filters.status = e.target.value;
            this.filterAndRenderBuckets();
        });

        document.getElementById('bucket-filter-tier')?.addEventListener('change', (e) => {
            this.filters.tier = e.target.value;
            this.filterAndRenderBuckets();
        });

        document.getElementById('clear-filters')?.addEventListener('click', () => {
            this.clearFilters();
        });

        // Sort
        document.getElementById('bucket-sort')?.addEventListener('change', (e) => {
            this.currentSort.field = e.target.value;
            this.sortAndRenderBuckets();
        });

        document.getElementById('sort-direction')?.addEventListener('click', () => {
            this.toggleSortDirection();
        });

        // Main actions
        document.getElementById('bulk-actions-btn')?.addEventListener('click', () => {
            this.openCreateBucketModal();
        });

        document.getElementById('create-first-bucket')?.addEventListener('click', () => {
            this.openCreateBucketModal();
        });

        // Bucket detail tabs
        document.getElementById('tab-files')?.addEventListener('click', () => this.switchTab('files'));
        document.getElementById('tab-settings')?.addEventListener('click', () => this.switchTab('settings'));
        document.getElementById('tab-sharing')?.addEventListener('click', () => this.switchTab('sharing'));
        document.getElementById('tab-activity')?.addEventListener('click', () => this.switchTab('activity'));

        // File operations
        document.getElementById('upload-files-btn')?.addEventListener('click', () => this.openUploadModal());
        document.getElementById('create-folder-btn')?.addEventListener('click', () => this.createFolder());
        document.getElementById('download-selected-btn')?.addEventListener('click', () => this.downloadSelected());

        // Bucket actions
        document.getElementById('bucket-settings-btn')?.addEventListener('click', () => this.openBucketSettings());
        document.getElementById('bucket-share-btn')?.addEventListener('click', () => this.openShareModal());
        document.getElementById('bucket-sync-btn')?.addEventListener('click', () => this.syncBucket());

        // Modal handlers
        this.setupModalHandlers();

        // File search
        document.getElementById('file-search')?.addEventListener('input', (e) => {
            this.filterFiles(e.target.value);
        });

        // File view toggles
        document.getElementById('file-view-list')?.addEventListener('click', () => this.setFileView('list'));
        document.getElementById('file-view-grid')?.addEventListener('click', () => this.setFileView('grid'));
    }

    setupModalHandlers() {
        // Create bucket modal
        document.getElementById('create-bucket-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.createBucket();
        });

        document.getElementById('close-create-bucket')?.addEventListener('click', () => {
            this.closeModal('create-bucket-modal');
        });

        document.getElementById('cancel-create-bucket')?.addEventListener('click', () => {
            this.closeModal('create-bucket-modal');
        });

        // Settings modal
        document.getElementById('apply-settings')?.addEventListener('click', () => {
            this.applyBucketSettings();
        });

        document.getElementById('close-settings-modal')?.addEventListener('click', () => {
            this.closeModal('bucket-settings-modal');
        });

        document.getElementById('cancel-settings')?.addEventListener('click', () => {
            this.closeModal('bucket-settings-modal');
        });

        // Upload modal
        document.getElementById('upload-file-input')?.addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files);
        });

        document.getElementById('modal-drop-zone')?.addEventListener('click', () => {
            document.getElementById('upload-file-input').click();
        });

        document.getElementById('start-upload')?.addEventListener('click', () => {
            this.startUpload();
        });

        document.getElementById('clear-upload-queue')?.addEventListener('click', () => {
            this.clearUploadQueue();
        });

        document.getElementById('close-upload-modal')?.addEventListener('click', () => {
            this.closeModal('upload-files-modal');
        });

        // Share modal
        document.getElementById('generate-share-link')?.addEventListener('click', () => {
            this.generateShareLink();
        });

        document.getElementById('copy-share-link')?.addEventListener('click', () => {
            this.copyShareLink();
        });

        document.getElementById('close-share-modal')?.addEventListener('click', () => {
            this.closeModal('share-bucket-modal');
        });

        document.getElementById('cancel-share')?.addEventListener('click', () => {
            this.closeModal('share-bucket-modal');
        });
    }

    setupDragAndDrop() {
        const dropZone = document.getElementById('files-tab-content');
        if (!dropZone) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, this.showDropOverlay.bind(this), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, this.hideDropOverlay.bind(this), false);
        });

        dropZone.addEventListener('drop', this.handleDrop.bind(this), false);
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + N: New bucket
            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                this.openCreateBucketModal();
            }
            
            // Ctrl/Cmd + U: Upload files
            if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
                e.preventDefault();
                if (this.selectedBucket) {
                    this.openUploadModal();
                }
            }
            
            // Delete: Delete selected files
            if (e.key === 'Delete' && this.selectedFiles.size > 0) {
                e.preventDefault();
                this.deleteSelectedFiles();
            }
        });
    }

    async initializeDefaultBuckets() {
        try {
            await this.waitForMCP();
            
            // Check if buckets already exist
            const existingBuckets = await this.mcp.callTool('list_buckets', { include_metadata: true });
            
            if (!existingBuckets?.result?.items?.length) {
                // Create default test buckets
                const defaultBuckets = [
                    {
                        name: 'documents',
                        description: 'Document storage bucket',
                        tier: 'hot',
                        replication_factor: 3,
                        cache_policy: 'memory',
                        retention_policy: 'permanent'
                    },
                    {
                        name: 'media',
                        description: 'Media files storage bucket',
                        tier: 'warm', 
                        replication_factor: 2,
                        cache_policy: 'disk',
                        retention_policy: '1y'
                    },
                    {
                        name: 'archive',
                        description: 'Long-term archive storage',
                        tier: 'cold',
                        replication_factor: 5,
                        cache_policy: 'none',
                        retention_policy: 'permanent'
                    }
                ];

                for (const bucket of defaultBuckets) {
                    try {
                        await this.mcp.callTool('create_bucket', bucket);
                    } catch (error) {
                        console.warn(`Failed to create default bucket ${bucket.name}:`, error);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to initialize default buckets:', error);
        }
    }

    async loadBuckets() {
        try {
            await this.waitForMCP();
            
            this.showBucketLoading();
            
            const result = await this.mcp.callTool('list_buckets', { include_metadata: true });
            
            if (result?.result?.items) {
                this.buckets = result.result.items.map(bucket => ({
                    ...bucket,
                    status: bucket.status || 'active',
                    tier: bucket.tier || 'warm',
                    files: bucket.files || 0,
                    size: bucket.size || 0,
                    replication: bucket.replication_factor || 3,
                    lastSync: bucket.last_sync || new Date().toISOString(),
                    created: bucket.created || new Date().toISOString()
                }));
            } else {
                this.buckets = [];
            }
            
            this.updateBucketCount();
            this.filterAndRenderBuckets();
            this.hideBucketLoading();
            
        } catch (error) {
            console.error('Failed to load buckets:', error);
            this.showNotification('Failed to load buckets', 'error');
            this.buckets = [];
            this.hideBucketLoading();
            this.showBucketEmpty();
        }
    }

    filterAndRenderBuckets() {
        let filtered = [...this.buckets];

        // Apply search filter
        if (this.searchQuery) {
            filtered = filtered.filter(bucket => 
                bucket.name.toLowerCase().includes(this.searchQuery) ||
                (bucket.description && bucket.description.toLowerCase().includes(this.searchQuery))
            );
        }

        // Apply status filter
        if (this.filters.status) {
            filtered = filtered.filter(bucket => bucket.status === this.filters.status);
        }

        // Apply tier filter
        if (this.filters.tier) {
            filtered = filtered.filter(bucket => bucket.tier === this.filters.tier);
        }

        // Apply sorting
        filtered.sort((a, b) => {
            let valueA = a[this.currentSort.field];
            let valueB = b[this.currentSort.field];

            if (typeof valueA === 'string') {
                valueA = valueA.toLowerCase();
                valueB = valueB.toLowerCase();
            }

            let result = 0;
            if (valueA < valueB) result = -1;
            if (valueA > valueB) result = 1;

            return this.currentSort.direction === 'asc' ? result : -result;
        });

        this.renderBucketList(filtered);
    }

    renderBucketList(buckets) {
        const container = document.getElementById('bucket-list');
        if (!container) return;

        if (buckets.length === 0) {
            this.showBucketEmpty();
            return;
        }

        const bucketsHtml = buckets.map(bucket => this.renderBucketItem(bucket)).join('');
        container.innerHTML = bucketsHtml;

        // Add click handlers for bucket items
        container.querySelectorAll('.bucket-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const bucketName = e.currentTarget.dataset.bucketName;
                this.selectBucket(bucketName);
            });
        });
    }

    renderBucketItem(bucket) {
        const statusColor = this.getStatusColor(bucket.status);
        const tierBadge = this.getTierBadge(bucket.tier);
        const sizeFormatted = this.formatFileSize(bucket.size || 0);
        const timeAgo = this.getTimeAgo(bucket.lastSync);

        return `
            <div class="bucket-item p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors ${this.selectedBucket?.name === bucket.name ? 'ring-2 ring-blue-500 bg-blue-50' : ''}" 
                 data-bucket-name="${bucket.name}">
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center">
                        <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
                            <i class="fas fa-database text-blue-600"></i>
                        </div>
                        <div>
                            <h3 class="font-medium text-gray-900">${bucket.name}</h3>
                            <p class="text-sm text-gray-500">${bucket.description || 'No description'}</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-2">
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${statusColor}">
                            <div class="w-1.5 h-1.5 rounded-full mr-1.5 ${statusColor.includes('green') ? 'bg-green-400' : statusColor.includes('yellow') ? 'bg-yellow-400' : 'bg-red-400'}"></div>
                            ${bucket.status}
                        </span>
                        ${tierBadge}
                    </div>
                </div>
                <div class="grid grid-cols-3 gap-4 text-sm text-gray-600">
                    <div>
                        <span class="font-medium">${bucket.files || 0}</span>
                        <span class="text-gray-400 ml-1">files</span>
                    </div>
                    <div>
                        <span class="font-medium">${sizeFormatted}</span>
                        <span class="text-gray-400 ml-1">size</span>
                    </div>
                    <div>
                        <span class="font-medium">${timeAgo}</span>
                        <span class="text-gray-400 ml-1">sync</span>
                    </div>
                </div>
            </div>
        `;
    }

    selectBucket(bucketName) {
        this.selectedBucket = this.buckets.find(b => b.name === bucketName);
        if (!this.selectedBucket) return;

        // Update UI
        this.renderBucketList(this.buckets); // Re-render to update selection
        this.showBucketDetails();
        this.loadBucketFiles();
        this.updateBucketStats();
    }

    showBucketDetails() {
        document.getElementById('no-bucket-selected').classList.add('hidden');
        document.getElementById('bucket-details').classList.remove('hidden');

        // Update bucket header
        document.getElementById('bucket-name').textContent = this.selectedBucket.name;
        
        // Update status badge
        const statusBadge = document.getElementById('bucket-status-badge');
        const statusColor = this.getStatusColor(this.selectedBucket.status);
        statusBadge.className = `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColor}`;
        statusBadge.innerHTML = `
            <div class="w-1.5 h-1.5 rounded-full mr-1.5 ${statusColor.includes('green') ? 'bg-green-400' : statusColor.includes('yellow') ? 'bg-yellow-400' : 'bg-red-400'}"></div>
            ${this.selectedBucket.status}
        `;

        // Update tier badge
        const tierBadge = document.getElementById('bucket-tier-badge');
        tierBadge.textContent = this.getTierLabel(this.selectedBucket.tier);
        tierBadge.className = `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${this.getTierColor(this.selectedBucket.tier)}`;
    }

    updateBucketStats() {
        if (!this.selectedBucket) return;

        document.getElementById('stat-files').textContent = this.selectedBucket.files || 0;
        document.getElementById('stat-size').textContent = this.formatFileSize(this.selectedBucket.size || 0);
        document.getElementById('stat-replicas').textContent = `${this.selectedBucket.replication || 3}x`;
        document.getElementById('stat-sync-time').textContent = this.getTimeAgo(this.selectedBucket.lastSync);
    }

    async loadBucketFiles() {
        if (!this.selectedBucket) return;

        try {
            await this.waitForMCP();
            const result = await this.mcp.callTool('bucket_list_files', {
                bucket_name: this.selectedBucket.name,
                path: this.currentPath || ''
            });

            const files = result?.result?.files || this.generateSampleFiles();
            this.renderFileList(files);
            this.updateFileBreadcrumbs();
            
        } catch (error) {
            console.error('Failed to load bucket files:', error);
            this.renderFileList(this.generateSampleFiles());
        }
    }

    generateSampleFiles() {
        // Generate sample files for demonstration
        return [
            {
                name: 'document1.pdf',
                type: 'file',
                size: 2540000,
                modified: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
                mimetype: 'application/pdf'
            },
            {
                name: 'images',
                type: 'folder',
                size: 0,
                modified: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
                items: 24
            },
            {
                name: 'data.json',
                type: 'file',
                size: 156000,
                modified: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
                mimetype: 'application/json'
            },
            {
                name: 'presentations',
                type: 'folder',
                size: 0,
                modified: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
                items: 8
            }
        ];
    }

    renderFileList(files) {
        const container = document.getElementById('file-list-container');
        if (!container) return;

        if (files.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <i class="fas fa-folder-open text-gray-300 text-4xl mb-4"></i>
                    <p class="text-gray-500">No files in this folder</p>
                </div>
            `;
            return;
        }

        const filesHtml = files.map(file => this.renderFileItem(file)).join('');
        container.innerHTML = `<div class="divide-y divide-gray-200">${filesHtml}</div>`;

        // Add click handlers
        container.querySelectorAll('.file-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.type === 'checkbox') return;
                
                const fileName = item.dataset.fileName;
                const fileType = item.dataset.fileType;
                
                if (fileType === 'folder') {
                    this.navigateToFolder(fileName);
                } else {
                    this.selectFile(fileName);
                }
            });

            // Handle file selection
            const checkbox = item.querySelector('input[type="checkbox"]');
            if (checkbox) {
                checkbox.addEventListener('change', (e) => {
                    const fileName = item.dataset.fileName;
                    if (e.target.checked) {
                        this.selectedFiles.add(fileName);
                    } else {
                        this.selectedFiles.delete(fileName);
                    }
                    this.updateFileSelection();
                });
            }
        });
    }

    renderFileItem(file) {
        const isSelected = this.selectedFiles.has(file.name);
        const icon = this.getFileIcon(file);
        const size = file.type === 'folder' ? `${file.items || 0} items` : this.formatFileSize(file.size);
        const timeAgo = this.getTimeAgo(file.modified);

        return `
            <div class="file-item p-4 hover:bg-gray-50 cursor-pointer flex items-center" 
                 data-file-name="${file.name}" data-file-type="${file.type}">
                <div class="flex items-center flex-1">
                    <input type="checkbox" ${isSelected ? 'checked' : ''} 
                           class="mr-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                    <div class="flex items-center flex-1">
                        <div class="flex-shrink-0 mr-4">
                            <div class="w-10 h-10 rounded-lg flex items-center justify-center ${icon.bgColor}">
                                <i class="${icon.icon} ${icon.textColor}"></i>
                            </div>
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-medium text-gray-900 truncate">${file.name}</p>
                            <p class="text-sm text-gray-500">${size} • ${timeAgo}</p>
                        </div>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <button class="p-1 text-gray-400 hover:text-gray-600" onclick="event.stopPropagation(); this.downloadFile('${file.name}')">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="p-1 text-gray-400 hover:text-gray-600" onclick="event.stopPropagation(); this.moreActions('${file.name}')">
                        <i class="fas fa-ellipsis-h"></i>
                    </button>
                </div>
            </div>
        `;
    }

    // Utility methods
    async waitForMCP() {
        let attempts = 0;
        while (!this.mcp && attempts < 50) {
            this.mcp = window.mcpClient;
            if (!this.mcp) {
                await new Promise(resolve => setTimeout(resolve, 100));
                attempts++;
            }
        }
        if (!this.mcp) {
            throw new Error('MCP client not available after waiting');
        }
    }

    showBucketLoading() {
        document.getElementById('bucket-loading')?.classList.remove('hidden');
        document.getElementById('bucket-empty')?.classList.add('hidden');
        document.getElementById('bucket-list').innerHTML = '';
    }

    hideBucketLoading() {
        document.getElementById('bucket-loading')?.classList.add('hidden');
    }

    showBucketEmpty() {
        document.getElementById('bucket-empty')?.classList.remove('hidden');
        document.getElementById('bucket-list').innerHTML = '';
    }

    updateBucketCount() {
        document.getElementById('bucket-count').textContent = this.buckets.length;
    }

    setView(view) {
        this.currentView = view;
        document.getElementById('view-grid').classList.toggle('bg-white', view === 'grid');
        document.getElementById('view-grid').classList.toggle('shadow-sm', view === 'grid');
        document.getElementById('view-list').classList.toggle('bg-white', view === 'list');
        document.getElementById('view-list').classList.toggle('shadow-sm', view === 'list');
    }

    clearFilters() {
        this.filters = { status: '', tier: '' };
        this.searchQuery = '';
        document.getElementById('bucket-search').value = '';
        document.getElementById('bucket-filter-status').value = '';
        document.getElementById('bucket-filter-tier').value = '';
        this.filterAndRenderBuckets();
    }

    toggleSortDirection() {
        this.currentSort.direction = this.currentSort.direction === 'asc' ? 'desc' : 'asc';
        const icon = document.querySelector('#sort-direction i');
        icon.className = this.currentSort.direction === 'asc' ? 'fas fa-sort-amount-up text-sm' : 'fas fa-sort-amount-down text-sm';
        this.sortAndRenderBuckets();
    }

    sortAndRenderBuckets() {
        this.filterAndRenderBuckets();
    }

    getStatusColor(status) {
        const colors = {
            'active': 'bg-green-100 text-green-800',
            'syncing': 'bg-yellow-100 text-yellow-800',
            'error': 'bg-red-100 text-red-800',
            'offline': 'bg-gray-100 text-gray-800'
        };
        return colors[status] || colors['offline'];
    }

    getTierBadge(tier) {
        const badges = {
            'hot': '<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">Hot</span>',
            'warm': '<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">Warm</span>',
            'cold': '<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">Cold</span>',
            'archive': '<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">Archive</span>'
        };
        return badges[tier] || badges['warm'];
    }

    getTierColor(tier) {
        const colors = {
            'hot': 'bg-red-100 text-red-800',
            'warm': 'bg-yellow-100 text-yellow-800',
            'cold': 'bg-blue-100 text-blue-800',
            'archive': 'bg-purple-100 text-purple-800'
        };
        return colors[tier] || colors['warm'];
    }

    getTierLabel(tier) {
        const labels = {
            'hot': 'Hot Storage',
            'warm': 'Warm Storage', 
            'cold': 'Cold Storage',
            'archive': 'Archive'
        };
        return labels[tier] || 'Warm Storage';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    getTimeAgo(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return 'now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    }

    getFileIcon(file) {
        if (file.type === 'folder') {
            return { icon: 'fas fa-folder', bgColor: 'bg-blue-100', textColor: 'text-blue-600' };
        }

        const ext = file.name.split('.').pop().toLowerCase();
        const iconMap = {
            'pdf': { icon: 'fas fa-file-pdf', bgColor: 'bg-red-100', textColor: 'text-red-600' },
            'doc': { icon: 'fas fa-file-word', bgColor: 'bg-blue-100', textColor: 'text-blue-600' },
            'docx': { icon: 'fas fa-file-word', bgColor: 'bg-blue-100', textColor: 'text-blue-600' },
            'xls': { icon: 'fas fa-file-excel', bgColor: 'bg-green-100', textColor: 'text-green-600' },
            'xlsx': { icon: 'fas fa-file-excel', bgColor: 'bg-green-100', textColor: 'text-green-600' },
            'ppt': { icon: 'fas fa-file-powerpoint', bgColor: 'bg-orange-100', textColor: 'text-orange-600' },
            'pptx': { icon: 'fas fa-file-powerpoint', bgColor: 'bg-orange-100', textColor: 'text-orange-600' },
            'jpg': { icon: 'fas fa-file-image', bgColor: 'bg-purple-100', textColor: 'text-purple-600' },
            'jpeg': { icon: 'fas fa-file-image', bgColor: 'bg-purple-100', textColor: 'text-purple-600' },
            'png': { icon: 'fas fa-file-image', bgColor: 'bg-purple-100', textColor: 'text-purple-600' },
            'gif': { icon: 'fas fa-file-image', bgColor: 'bg-purple-100', textColor: 'text-purple-600' },
            'mp4': { icon: 'fas fa-file-video', bgColor: 'bg-indigo-100', textColor: 'text-indigo-600' },
            'mp3': { icon: 'fas fa-file-audio', bgColor: 'bg-yellow-100', textColor: 'text-yellow-600' },
            'json': { icon: 'fas fa-file-code', bgColor: 'bg-gray-100', textColor: 'text-gray-600' },
            'txt': { icon: 'fas fa-file-alt', bgColor: 'bg-gray-100', textColor: 'text-gray-600' }
        };

        return iconMap[ext] || { icon: 'fas fa-file', bgColor: 'bg-gray-100', textColor: 'text-gray-600' };
    }

    // Modal methods
    openCreateBucketModal() {
        this.showModal('create-bucket-modal');
        document.getElementById('new-bucket-name').focus();
    }

    openBucketSettings() {
        if (!this.selectedBucket) return;
        
        this.showModal('bucket-settings-modal');
        this.populateSettingsForm();
    }

    openUploadModal() {
        if (!this.selectedBucket) return;
        
        this.showModal('upload-files-modal');
        this.clearUploadQueue();
    }

    openShareModal() {
        if (!this.selectedBucket) return;
        
        this.showModal('share-bucket-modal');
        document.getElementById('share-link-container').classList.add('hidden');
    }

    showModal(modalId) {
        document.getElementById(modalId)?.classList.remove('hidden');
    }

    closeModal(modalId) {
        document.getElementById(modalId)?.classList.add('hidden');
    }

    showNotification(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const colors = {
            'success': 'bg-green-500 text-white',
            'error': 'bg-red-500 text-white',
            'warning': 'bg-yellow-500 text-white',
            'info': 'bg-blue-500 text-white'
        };

        const toast = document.createElement('div');
        toast.className = `px-4 py-2 rounded-lg shadow-lg ${colors[type]} flex items-center space-x-2 transform translate-x-full transition-transform`;
        toast.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
            <span>${message}</span>
            <button class="ml-2 text-white/80 hover:text-white" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;

        container.appendChild(toast);
        
        // Animate in
        setTimeout(() => toast.classList.remove('translate-x-full'), 100);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    // Placeholder methods for functionality
    async createBucket() {
        const name = document.getElementById('new-bucket-name').value;
        const description = document.getElementById('new-bucket-description').value;
        const tier = document.getElementById('new-bucket-tier').value;
        const replication = document.getElementById('new-bucket-replication').value;

        try {
            await this.mcp.callTool('create_bucket', {
                name,
                description,
                tier,
                replication_factor: parseInt(replication)
            });

            this.showNotification(`Bucket "${name}" created successfully`, 'success');
            this.closeModal('create-bucket-modal');
            this.loadBuckets();
        } catch (error) {
            console.error('Failed to create bucket:', error);
            this.showNotification('Failed to create bucket', 'error');
        }
    }

    async syncBucket() {
        if (!this.selectedBucket) return;

        try {
            await this.mcp.callTool('bucket_sync_replicas', {
                bucket_name: this.selectedBucket.name
            });
            this.showNotification(`Bucket "${this.selectedBucket.name}" sync started`, 'success');
        } catch (error) {
            console.error('Failed to sync bucket:', error);
            this.showNotification('Failed to start sync', 'error');
        }
    }

    async generateShareLink() {
        if (!this.selectedBucket) return;

        const accessLevel = document.getElementById('share-access-level').value;
        const expiration = document.getElementById('share-expiration').value;

        try {
            const result = await this.mcp.callTool('generate_bucket_share_link', {
                bucket_name: this.selectedBucket.name,
                access_level: accessLevel,
                expiration: expiration
            });

            const shareUrl = result?.result?.share_url || `http://127.0.0.1:8004/shared/${this.selectedBucket.name}/${Date.now()}`;
            
            document.getElementById('share-link-url').value = shareUrl;
            document.getElementById('share-link-container').classList.remove('hidden');
            
            this.showNotification('Share link generated successfully', 'success');
        } catch (error) {
            console.error('Failed to generate share link:', error);
            this.showNotification('Failed to generate share link', 'error');
        }
    }

    copyShareLink() {
        const linkInput = document.getElementById('share-link-url');
        linkInput.select();
        document.execCommand('copy');
        this.showNotification('Share link copied to clipboard', 'success');
    }

    // Drag and drop handlers
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    showDropOverlay() {
        if (!this.selectedBucket) return;
        document.getElementById('drag-drop-overlay')?.classList.remove('hidden');
    }

    hideDropOverlay() {
        document.getElementById('drag-drop-overlay')?.classList.add('hidden');
    }

    handleDrop(e) {
        const files = e.dataTransfer.files;
        this.handleFileSelect(files);
        this.openUploadModal();
    }

    handleFileSelect(files) {
        // Add files to upload queue
        Array.from(files).forEach(file => {
            this.addFileToUploadQueue(file);
        });
        this.updateUploadFileCount();
    }

    addFileToUploadQueue(file) {
        const queue = document.getElementById('upload-file-queue');
        const fileItem = document.createElement('div');
        fileItem.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-lg';
        fileItem.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-file text-gray-400 mr-3"></i>
                <div>
                    <div class="font-medium">${file.name}</div>
                    <div class="text-sm text-gray-500">${this.formatFileSize(file.size)}</div>
                </div>
            </div>
            <button class="text-red-500 hover:text-red-700" onclick="this.parentElement.remove(); this.updateUploadFileCount()">
                <i class="fas fa-times"></i>
            </button>
        `;
        queue.appendChild(fileItem);
    }

    updateUploadFileCount() {
        const count = document.getElementById('upload-file-queue').children.length;
        document.getElementById('upload-file-count').textContent = count;
        document.getElementById('start-upload').disabled = count === 0;
    }

    clearUploadQueue() {
        document.getElementById('upload-file-queue').innerHTML = '';
        this.updateUploadFileCount();
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('[id^="tab-"]').forEach(tab => {
            tab.className = 'py-4 px-1 border-b-2 border-transparent font-medium text-sm text-gray-500 hover:text-gray-700';
        });
        document.getElementById(`tab-${tabName}`).className = 'py-4 px-1 border-b-2 border-blue-600 font-medium text-sm text-blue-600';

        // Update tab content
        document.querySelectorAll('[id$="-tab-content"]').forEach(content => {
            content.classList.add('hidden');
        });
        document.getElementById(`${tabName}-tab-content`).classList.remove('hidden');

        // Load tab-specific content
        if (tabName === 'files') {
            this.loadBucketFiles();
        } else if (tabName === 'settings') {
            this.loadBucketSettings();
        } else if (tabName === 'sharing') {
            this.loadBucketSharing();
        } else if (tabName === 'activity') {
            this.loadBucketActivity();
        }
    }

    loadBucketSettings() {
        const content = document.getElementById('settings-tab-content');
        content.innerHTML = `
            <div class="p-6 space-y-6">
                <h3 class="text-lg font-semibold">Bucket Configuration</h3>
                <p class="text-gray-600">Settings will be loaded here...</p>
            </div>
        `;
    }

    loadBucketSharing() {
        const content = document.getElementById('sharing-tab-content');
        content.innerHTML = `
            <div class="p-6 space-y-6">
                <h3 class="text-lg font-semibold">Share Settings</h3>
                <p class="text-gray-600">Sharing options will be loaded here...</p>
            </div>
        `;
    }

    loadBucketActivity() {
        const content = document.getElementById('activity-tab-content');
        content.innerHTML = `
            <div class="p-6 space-y-6">
                <h3 class="text-lg font-semibold">Recent Activity</h3>
                <p class="text-gray-600">Activity log will be loaded here...</p>
            </div>
        `;
    }
}

// Initialize the enhanced bucket dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Wait for MCP client to be available
    const initDashboard = () => {
        if (window.mcpClient) {
            new EnhancedBucketDashboard();
        } else {
            setTimeout(initDashboard, 100);
        }
    };
    initDashboard();
});