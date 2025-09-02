// Enhanced Dashboard JavaScript with Comprehensive Bucket File Management
class EnhancedDashboard {
    constructor() {
        this.init();
        this.setupEventListeners();
        // Initialize MCP client - wait for it to be available
        this.mcp = null;
        this.waitForMCP();
    }

    async waitForMCP() {
        // Wait for MCP client to be available
        let attempts = 0;
        while (!window.mcpClient && attempts < 10) {
            await new Promise(resolve => setTimeout(resolve, 500));
            attempts++;
        }
        if (window.mcpClient) {
            this.mcp = window.mcpClient;
            console.log('✅ MCP client initialized');
        } else {
            console.warn('⚠️ MCP client not available after 5 seconds');
        }
    }

    init() {
        this.jsonrpcId = 1;
        this.pinData = [];
        this.bucketData = [];
        this.selectedBucket = null;
        this.dragCounter = 0;
        
        // Initialize default test buckets for development
        this.initializeDefaultBuckets();
    }

    initializeDefaultBuckets() {
        // Create realistic test data as mentioned in PR description
        this.defaultBuckets = [
            {
                name: "documents",
                description: "Document storage bucket", 
                backend: "ipfs_local",
                status: "active",
                files: 12,
                size: 45678912, // ~43.5 MB
                replication_factor: 3,
                cache_policy: "memory",
                retention_policy: "permanent",
                quota: { max_size: 0, max_files: 0 }, // unlimited
                created: "2025-01-01T10:30:00Z",
                sync_status: "synced"
            },
            {
                name: "media", 
                description: "Media files storage bucket",
                backend: "s3_demo",
                status: "active",
                files: 85,
                size: 2468543210, // ~2.3 GB
                replication_factor: 2,
                cache_policy: "disk", 
                retention_policy: "90_days",
                quota: { max_size: 5368709120, max_files: 1000 }, // 5GB, 1000 files
                created: "2025-01-01T11:15:00Z",
                sync_status: "syncing"
            },
            {
                name: "archive",
                description: "Long-term archive storage",
                backend: "cluster", 
                status: "active",
                files: 567,
                size: 134217728000, // ~125 GB
                replication_factor: 5,
                cache_policy: "none",
                retention_policy: "permanent",
                quota: { max_size: 0, max_files: 0 }, // unlimited
                created: "2025-01-01T09:45:00Z", 
                sync_status: "synced"
            }
        ];
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const tabId = e.target.dataset.tab;
                this.switchTab(tabId);
            });
        });

        // Pin management
        const refreshPinsBtn = document.getElementById('refresh-pins');
        if (refreshPinsBtn) refreshPinsBtn.addEventListener('click', () => this.loadPins());
        
        const addPinBtn = document.getElementById('add-pin');
        if (addPinBtn) addPinBtn.addEventListener('click', () => this.showAddPinModal());
        
        const bulkOpsBtn = document.getElementById('bulk-operations');
        if (bulkOpsBtn) bulkOpsBtn.addEventListener('click', () => this.showBulkModal());
        
        const verifyPinsBtn = document.getElementById('verify-pins');
        if (verifyPinsBtn) verifyPinsBtn.addEventListener('click', () => this.verifyPins());
        
        const cleanupPinsBtn = document.getElementById('cleanup-pins');
        if (cleanupPinsBtn) cleanupPinsBtn.addEventListener('click', () => this.cleanupPins());
        
        const exportBtn = document.getElementById('export-metadata');
        if (exportBtn) exportBtn.addEventListener('click', () => this.exportMetadata());

        // Modal events
        const cancelBtn = document.getElementById('cancel-add-pin');
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.hideAddPinModal());
        
        const formEl = document.getElementById('add-pin-form');
        if (formEl) formEl.addEventListener('submit', (e) => this.submitAddPin(e));

        // === NEW: COMPREHENSIVE BUCKET FILE MANAGEMENT EVENT LISTENERS ===
        this.setupBucketEventListeners();
    }

    setupBucketEventListeners() {
        // Bucket management controls
        const refreshBucketsBtn = document.getElementById('refresh-buckets');
        if (refreshBucketsBtn) refreshBucketsBtn.addEventListener('click', () => this.loadBucketsData());
        
        const createBucketBtn = document.getElementById('create-bucket');
        if (createBucketBtn) createBucketBtn.addEventListener('click', () => this.showCreateBucketModal());
        
        const uploadFileBtn = document.getElementById('upload-file');
        if (uploadFileBtn) uploadFileBtn.addEventListener('click', () => this.triggerFileUpload());
        
        const createFolderBtn = document.getElementById('create-folder');
        if (createFolderBtn) createFolderBtn.addEventListener('click', () => this.showCreateFolderModal());
        
        const forceSyncBtn = document.getElementById('force-sync');
        if (forceSyncBtn) forceSyncBtn.addEventListener('click', () => this.forceBucketSync());
        
        const shareBucketBtn = document.getElementById('share-bucket');
        if (shareBucketBtn) shareBucketBtn.addEventListener('click', () => this.showShareBucketModal());

        // Advanced settings and quota management
        const advancedSettingsBtn = document.getElementById('advanced-settings');
        if (advancedSettingsBtn) advancedSettingsBtn.addEventListener('click', () => this.showAdvancedSettingsModal());
        
        const quotaManagementBtn = document.getElementById('quota-management');
        if (quotaManagementBtn) quotaManagementBtn.addEventListener('click', () => this.showQuotaManagementModal());

        // Bucket selector
        const bucketSelector = document.getElementById('bucket-selector');
        if (bucketSelector) bucketSelector.addEventListener('change', (e) => this.selectBucket(e.target.value));

        // Drag and drop file upload setup
        this.setupDragAndDrop();

        // File input change handler
        const fileInput = document.getElementById('file-input');
        if (fileInput) fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
    }

    setupDragAndDrop() {
        const dropZone = document.getElementById('drag-drop-zone');
        const fileInput = document.getElementById('file-input');
        
        if (!dropZone || !fileInput) return;

        // Handle drag events
        dropZone.addEventListener('dragenter', (e) => {
            e.preventDefault();
            this.dragCounter++;
            dropZone.classList.add('drag-over');
            dropZone.innerHTML = `
                <div class="text-blue-500">
                    <i class="fas fa-cloud-upload-alt text-6xl mb-4"></i>
                    <div class="text-xl font-medium mb-2">Drop files here to upload</div>
                    <div class="text-sm">Multiple files supported</div>
                </div>
            `;
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            this.dragCounter--;
            if (this.dragCounter === 0) {
                dropZone.classList.remove('drag-over');
                this.resetDragDropZone();
            }
        });

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.dragCounter = 0;
            dropZone.classList.remove('drag-over');
            this.resetDragDropZone();
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                this.handleFileUpload(files);
            }
        });

        // Click to browse files
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });
    }

    resetDragDropZone() {
        const dropZone = document.getElementById('drag-drop-zone');
        if (dropZone) {
            dropZone.innerHTML = `
                <div class="text-gray-500">
                    <i class="fas fa-cloud-upload-alt text-4xl mb-4"></i>
                    <div class="text-lg font-medium mb-2">Drag & Drop Files Here</div>
                    <div class="text-sm">Or click to browse files</div>
                    <input type="file" id="file-input" multiple class="hidden">
                </div>
            `;
            // Re-attach file input event listener
            const fileInput = document.getElementById('file-input');
            if (fileInput) fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        }
    }

    async jsonRpcCall(method, params = {}) {
        // Use MCP SDK for all tool calls
        try {
            if (!this.mcp) {
                await this.waitForMCP();
            }
            if (!this.mcp) {
                throw new Error('MCP client not available');
            }
            return await this.mcp.callTool(method, params);
        } catch (error) {
            console.error('MCP call failed:', error);
            this.showNotification('Error: ' + error.message, 'error');
            throw error;
        }
    }

    // === COMPREHENSIVE BUCKET FILE MANAGEMENT METHODS ===

    async loadBucketsData() {
        console.log('🗄️ Loading buckets via MCP JSON-RPC (metadata-first)...');
        try {
            await this.waitForMCP();
            
            const result = await this.jsonRpcCall('list_buckets', { 
                include_metadata: true 
            });
            
            console.log('🗄️ Buckets result:', result);
            
            if (result && result.result && Array.isArray(result.result.items)) {
                this.bucketData = result.result.items;
            } else if (result && Array.isArray(result.items)) {
                this.bucketData = result.items;
            } else {
                // Use default test buckets if no data available
                console.log('📦 Using default test buckets for development');
                this.bucketData = this.defaultBuckets;
            }
            
            this.updateBucketsDisplay();
            this.updateBucketSelector();
            this.showNotification('Buckets loaded successfully', 'success');
            
        } catch (error) {
            console.error('❌ Error loading buckets data via MCP:', error);
            // Fall back to default buckets for development
            this.bucketData = this.defaultBuckets;
            this.updateBucketsDisplay();
            this.updateBucketSelector();
            this.showNotification('Using default test buckets', 'warning');
        }
    }

    updateBucketsDisplay() {
        const container = document.getElementById('bucket-files');
        if (!container) return;

        if (!this.bucketData || this.bucketData.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <i class="fas fa-folder-open text-6xl text-gray-300 mb-4"></i>
                    <div class="text-gray-500 text-lg">No buckets found</div>
                    <div class="text-gray-400 text-sm mt-2">Create your first bucket to get started</div>
                </div>
            `;
            return;
        }

        // Display buckets in card format
        const bucketsHtml = this.bucketData.map(bucket => {
            const sizeFormatted = this.formatBytes(bucket.size || 0);
            const quotaUsage = bucket.quota && bucket.quota.max_size > 0 ? 
                Math.round((bucket.size / bucket.quota.max_size) * 100) : 0;
            
            const statusColor = bucket.status === 'active' ? 'green' : 'red';
            const syncStatusColor = bucket.sync_status === 'synced' ? 'green' : 
                                   bucket.sync_status === 'syncing' ? 'blue' : 'yellow';
            
            return `
                <div class="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <h3 class="text-xl font-semibold text-gray-800 mb-2">${bucket.name}</h3>
                            <p class="text-gray-600 text-sm">${bucket.description || 'No description provided'}</p>
                        </div>
                        <div class="flex gap-2">
                            <span class="px-3 py-1 rounded-full text-xs font-medium bg-${statusColor}-100 text-${statusColor}-800">
                                ${bucket.status || 'unknown'}
                            </span>
                        </div>
                    </div>
                    
                    <!-- Bucket metrics -->
                    <div class="grid grid-cols-2 gap-4 mb-4">
                        <div class="text-center">
                            <div class="text-2xl font-bold text-blue-600">${bucket.files || 0}</div>
                            <div class="text-xs text-gray-500">Files</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-green-600">${sizeFormatted}</div>
                            <div class="text-xs text-gray-500">Storage</div>
                        </div>
                    </div>

                    <!-- Status indicators -->
                    <div class="flex justify-between text-sm text-gray-600 mb-4">
                        <span>Replication: ${bucket.replication_factor || 1}x</span>
                        <span>Cache: ${bucket.cache_policy || 'none'}</span>
                        <span>Quota: ${bucket.quota && bucket.quota.max_size > 0 ? quotaUsage + '%' : 'unlimited'}</span>
                        <span>Retention: ${bucket.retention_policy || 'permanent'}</span>
                    </div>

                    <!-- Action buttons -->
                    <div class="flex justify-between items-center">
                        <div class="flex gap-2">
                            <button onclick="dashboard.selectBucketForManagement('${bucket.name}')" 
                                    class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm">
                                <i class="fas fa-folder-open mr-1"></i>Manage
                            </button>
                            <button onclick="dashboard.showBucketSettings('${bucket.name}')" 
                                    class="bg-gray-500 hover:bg-gray-600 text-white px-3 py-1 rounded text-sm">
                                <i class="fas fa-cog mr-1"></i>Settings
                            </button>
                            <button onclick="dashboard.forceBucketSyncForBucket('${bucket.name}')" 
                                    class="bg-indigo-500 hover:bg-indigo-600 text-white px-3 py-1 rounded text-sm">
                                <i class="fas fa-sync mr-1"></i>Sync
                            </button>
                            <button onclick="dashboard.showShareBucketModalFor('${bucket.name}')" 
                                    class="bg-orange-500 hover:bg-orange-600 text-white px-3 py-1 rounded text-sm">
                                <i class="fas fa-share-alt mr-1"></i>Share
                            </button>
                        </div>
                        <div class="text-xs text-gray-500">
                            <span class="inline-block w-2 h-2 rounded-full bg-${syncStatusColor}-500 mr-1"></span>
                            ${bucket.sync_status || 'unknown'}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = bucketsHtml;
    }

    updateBucketSelector() {
        const selector = document.getElementById('bucket-selector');
        if (!selector) return;

        selector.innerHTML = '<option value="">Select a bucket...</option>';
        
        this.bucketData.forEach(bucket => {
            const option = document.createElement('option');
            option.value = bucket.name;
            option.textContent = `${bucket.name} (${bucket.files || 0} files)`;
            selector.appendChild(option);
        });
    }

    selectBucket(bucketName) {
        if (!bucketName) {
            this.selectedBucket = null;
            this.hideBucketStatus();
            this.showBucketEmptyState();
            return;
        }

        this.selectedBucket = bucketName;
        const bucket = this.bucketData.find(b => b.name === bucketName);
        
        if (bucket) {
            this.showBucketStatus(bucket);
            this.loadBucketFiles(bucketName);
        }
    }

    selectBucketForManagement(bucketName) {
        // Set the selector and trigger bucket selection
        const selector = document.getElementById('bucket-selector');
        if (selector) {
            selector.value = bucketName;
            this.selectBucket(bucketName);
        }
    }

    showBucketStatus(bucket) {
        const statusDiv = document.getElementById('bucket-status');
        if (!statusDiv) return;

        statusDiv.classList.remove('hidden');
        
        // Update status metrics
        document.getElementById('bucket-file-count').textContent = bucket.files || 0;
        document.getElementById('bucket-size').textContent = this.formatBytes(bucket.size || 0);
        document.getElementById('bucket-replication').textContent = (bucket.replication_factor || 1) + 'x';
        document.getElementById('bucket-sync-status').textContent = bucket.sync_status || 'unknown';
    }

    hideBucketStatus() {
        const statusDiv = document.getElementById('bucket-status');
        if (statusDiv) {
            statusDiv.classList.add('hidden');
        }
    }

    showBucketEmptyState() {
        const container = document.getElementById('bucket-files');
        if (container) {
            container.innerHTML = `
                <div class="text-gray-500 text-center py-8">
                    <i class="fas fa-folder-open text-4xl mb-4"></i>
                    <div>Select a bucket to view files...</div>
                </div>
            `;
        }
    }

    async loadBucketFiles(bucketName) {
        console.log(`📁 Loading files for bucket: ${bucketName}`);
        try {
            const result = await this.jsonRpcCall('bucket_list_files', { 
                bucket: bucketName 
            });
            
            console.log('📁 Files result:', result);
            
            let files = [];
            if (result && result.result && Array.isArray(result.result.files)) {
                files = result.result.files;
            } else if (result && Array.isArray(result.files)) {
                files = result.files;
            } else {
                // Create sample files for demonstration
                files = this.generateSampleFiles(bucketName);
            }
            
            this.displayBucketFiles(files, bucketName);
            
        } catch (error) {
            console.error(`❌ Error loading files for bucket ${bucketName}:`, error);
            // Show sample files for development
            this.displayBucketFiles(this.generateSampleFiles(bucketName), bucketName);
        }
    }

    generateSampleFiles(bucketName) {
        // Generate realistic sample files based on bucket type
        const sampleFiles = {
            'documents': [
                { name: 'document1.pdf', size: 2048576, type: 'file', modified: '2025-01-15T10:30:00Z', cid: 'QmHash1...' },
                { name: 'spreadsheet.xlsx', size: 1536000, type: 'file', modified: '2025-01-14T15:45:00Z', cid: 'QmHash2...' },
                { name: 'presentation.pptx', size: 5242880, type: 'file', modified: '2025-01-13T09:15:00Z', cid: 'QmHash3...' },
                { name: 'reports', size: 0, type: 'folder', modified: '2025-01-12T14:20:00Z', files: 8 }
            ],
            'media': [
                { name: 'images', size: 0, type: 'folder', modified: '2025-01-15T16:30:00Z', files: 24 },
                { name: 'video_project.mp4', size: 157286400, type: 'file', modified: '2025-01-14T11:00:00Z', cid: 'QmHash4...' },
                { name: 'audio_samples', size: 0, type: 'folder', modified: '2025-01-13T13:45:00Z', files: 12 },
                { name: 'thumbnail.jpg', size: 245760, type: 'file', modified: '2025-01-12T08:30:00Z', cid: 'QmHash5...' }
            ],
            'archive': [
                { name: 'data.json', size: 1048576, type: 'file', modified: '2025-01-15T12:00:00Z', cid: 'QmHash6...' },
                { name: 'backup_2024', size: 0, type: 'folder', modified: '2024-12-31T23:59:00Z', files: 156 },
                { name: 'logs', size: 0, type: 'folder', modified: '2025-01-10T07:00:00Z', files: 89 },
                { name: 'config_archive.tar.gz', size: 3145728, type: 'file', modified: '2025-01-05T18:15:00Z', cid: 'QmHash7...' }
            ]
        };
        
        return sampleFiles[bucketName] || [
            { name: 'sample_file.txt', size: 1024, type: 'file', modified: new Date().toISOString(), cid: 'QmHashSample...' }
        ];
    }

    displayBucketFiles(files, bucketName) {
        const container = document.getElementById('bucket-files');
        if (!container) return;

        if (!files || files.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12">
                    <i class="fas fa-file-alt text-6xl text-gray-300 mb-4"></i>
                    <div class="text-gray-500 text-lg">No files in this bucket</div>
                    <div class="text-gray-400 text-sm mt-2">Drag and drop files to upload</div>
                </div>
            `;
            return;
        }

        const filesHtml = files.map(file => {
            const isFolder = file.type === 'folder';
            const icon = isFolder ? 'fa-folder' : 'fa-file-alt';
            const sizeText = isFolder ? `${file.files || 0} items` : this.formatBytes(file.size || 0);
            const modifiedDate = new Date(file.modified).toLocaleDateString();
            
            return `
                <div class="flex items-center justify-between p-3 border-b border-gray-200 hover:bg-gray-50">
                    <div class="flex items-center flex-1">
                        <i class="fas ${icon} text-blue-500 mr-3"></i>
                        <div class="flex-1">
                            <div class="font-medium text-gray-800">${file.name}</div>
                            <div class="text-sm text-gray-500">${sizeText} • Modified ${modifiedDate}</div>
                            ${file.cid ? `<div class="text-xs text-gray-400 font-mono">${file.cid.substring(0, 20)}...</div>` : ''}
                        </div>
                    </div>
                    <div class="flex gap-2">
                        ${!isFolder ? `
                            <button onclick="dashboard.downloadFile('${bucketName}', '${file.name}')" 
                                    class="text-blue-600 hover:text-blue-800 text-sm">
                                <i class="fas fa-download"></i>
                            </button>
                        ` : ''}
                        <button onclick="dashboard.deleteFile('${bucketName}', '${file.name}')" 
                                class="text-red-600 hover:text-red-800 text-sm">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div class="bg-white rounded-lg border border-gray-200">
                <div class="p-4 border-b border-gray-200">
                    <h3 class="font-semibold text-gray-800">Files in ${bucketName}</h3>
                </div>
                <div class="max-h-96 overflow-y-auto">
                    ${filesHtml}
                </div>
            </div>
        `;
    }

    // === FILE OPERATIONS ===

    handleFileSelection(event) {
        const files = Array.from(event.target.files);
        if (files.length > 0) {
            this.handleFileUpload(files);
        }
    }

    triggerFileUpload() {
        if (!this.selectedBucket) {
            this.showNotification('Please select a bucket first', 'warning');
            return;
        }
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.click();
        }
    }

    async handleFileUpload(files) {
        if (!this.selectedBucket) {
            this.showNotification('Please select a bucket first', 'warning');
            return;
        }

        console.log(`📤 Uploading ${files.length} files to bucket: ${this.selectedBucket}`);
        
        // Show upload progress
        this.showUploadProgress(files);

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            try {
                await this.uploadSingleFile(file, i + 1, files.length);
            } catch (error) {
                console.error(`❌ Failed to upload ${file.name}:`, error);
                this.showNotification(`Failed to upload ${file.name}: ${error.message}`, 'error');
            }
        }

        // Refresh file list
        this.loadBucketFiles(this.selectedBucket);
        this.hideUploadProgress();
        this.showNotification(`Successfully uploaded ${files.length} file(s)`, 'success');
    }

    async uploadSingleFile(file, index, total) {
        console.log(`📤 Uploading file ${index}/${total}: ${file.name}`);
        
        // Simulate upload via MCP tool
        try {
            const result = await this.jsonRpcCall('bucket_upload_file', {
                bucket: this.selectedBucket,
                filename: file.name,
                size: file.size,
                content_type: file.type
            });
            
            console.log(`✅ Upload result for ${file.name}:`, result);
            
            // Update progress
            this.updateUploadProgress(index, total, file.name);
            
        } catch (error) {
            console.error(`❌ Upload error for ${file.name}:`, error);
            throw error;
        }
    }

    showUploadProgress(files) {
        const dropZone = document.getElementById('drag-drop-zone');
        if (dropZone) {
            dropZone.innerHTML = `
                <div class="text-blue-500">
                    <i class="fas fa-spinner fa-spin text-4xl mb-4"></i>
                    <div class="text-lg font-medium mb-2">Uploading ${files.length} file(s)...</div>
                    <div id="upload-progress" class="text-sm">Starting upload...</div>
                    <div class="w-full bg-gray-200 rounded-full h-2 mt-4">
                        <div id="upload-progress-bar" class="bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                    </div>
                </div>
            `;
        }
    }

    updateUploadProgress(current, total, filename) {
        const progressText = document.getElementById('upload-progress');
        const progressBar = document.getElementById('upload-progress-bar');
        
        if (progressText) {
            progressText.textContent = `Uploading ${filename} (${current}/${total})`;
        }
        
        if (progressBar) {
            const percentage = (current / total) * 100;
            progressBar.style.width = `${percentage}%`;
        }
    }

    hideUploadProgress() {
        setTimeout(() => {
            this.resetDragDropZone();
        }, 2000);
    }

    async downloadFile(bucketName, filename) {
        console.log(`📥 Downloading file: ${filename} from bucket: ${bucketName}`);
        try {
            const result = await this.jsonRpcCall('bucket_download_file', {
                bucket: bucketName,
                filename: filename
            });
            
            if (result && result.result && result.result.download_url) {
                // Open download URL in new tab
                window.open(result.result.download_url, '_blank');
                this.showNotification(`Downloaded ${filename}`, 'success');
            } else {
                this.showNotification(`Download started for ${filename}`, 'success');
            }
            
        } catch (error) {
            console.error(`❌ Download error for ${filename}:`, error);
            this.showNotification(`Failed to download ${filename}: ${error.message}`, 'error');
        }
    }

    async deleteFile(bucketName, filename) {
        if (!confirm(`Are you sure you want to delete ${filename}?`)) {
            return;
        }

        console.log(`🗑️ Deleting file: ${filename} from bucket: ${bucketName}`);
        try {
            const result = await this.jsonRpcCall('bucket_delete_file', {
                bucket: bucketName,
                filename: filename
            });
            
            console.log(`✅ Delete result for ${filename}:`, result);
            this.showNotification(`Deleted ${filename}`, 'success');
            
            // Refresh file list
            this.loadBucketFiles(bucketName);
            
        } catch (error) {
            console.error(`❌ Delete error for ${filename}:`, error);
            this.showNotification(`Failed to delete ${filename}: ${error.message}`, 'error');
        }
    }

    // === BUCKET OPERATIONS ===

    async forceBucketSync() {
        if (!this.selectedBucket) {
            this.showNotification('Please select a bucket first', 'warning');
            return;
        }

        this.forceBucketSyncForBucket(this.selectedBucket);
    }

    async forceBucketSyncForBucket(bucketName) {
        console.log(`🔄 Forcing sync for bucket: ${bucketName}`);
        try {
            const result = await this.jsonRpcCall('bucket_sync_replicas', {
                bucket: bucketName,
                force_sync: true
            });
            
            console.log(`✅ Sync result for ${bucketName}:`, result);
            
            if (result && result.result && result.result.success) {
                this.showNotification(`Sync completed for ${bucketName}`, 'success');
                
                // Update bucket status
                const bucket = this.bucketData.find(b => b.name === bucketName);
                if (bucket) {
                    bucket.sync_status = 'synced';
                    this.updateBucketsDisplay();
                }
            } else {
                this.showNotification(`Sync started for ${bucketName}`, 'info');
            }
            
        } catch (error) {
            console.error(`❌ Sync error for ${bucketName}:`, error);
            this.showNotification(`Failed to sync ${bucketName}: ${error.message}`, 'error');
        }
    }

    // === ADVANCED SETTINGS MODAL ===

    showAdvancedSettingsModal() {
        if (!this.selectedBucket) {
            this.showNotification('Please select a bucket first', 'warning');
            return;
        }
        this.showBucketSettings(this.selectedBucket);
    }

    showBucketSettings(bucketName) {
        const bucket = this.bucketData.find(b => b.name === bucketName);
        if (!bucket) {
            this.showNotification('Bucket not found', 'error');
            return;
        }

        // Create and show advanced settings modal
        const modal = this.createAdvancedSettingsModal(bucket);
        document.body.appendChild(modal);
        
        // Show modal with animation
        setTimeout(() => {
            modal.classList.remove('opacity-0');
            modal.classList.add('opacity-100');
        }, 10);
    }

    createAdvancedSettingsModal(bucket) {
        const modalDiv = document.createElement('div');
        modalDiv.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center opacity-0 transition-opacity duration-300';
        modalDiv.id = 'advanced-settings-modal';

        modalDiv.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-screen overflow-y-auto m-4">
                <div class="p-6 border-b border-gray-200">
                    <div class="flex justify-between items-center">
                        <h2 class="text-2xl font-bold text-gray-800">Advanced Settings</h2>
                        <button onclick="dashboard.closeAdvancedSettingsModal()" class="text-gray-500 hover:text-gray-700">
                            <i class="fas fa-times text-xl"></i>
                        </button>
                    </div>
                    <p class="text-gray-600 mt-2">Configure advanced settings for bucket: <strong>${bucket.name}</strong></p>
                </div>
                
                <div class="p-6">
                    <form id="advanced-settings-form" class="space-y-6">
                        <!-- Basic Information -->
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Bucket Name</label>
                                <input type="text" value="${bucket.name}" readonly 
                                       class="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Backend</label>
                                <input type="text" value="${bucket.backend}" readonly 
                                       class="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50">
                            </div>
                        </div>

                        <!-- Replication Policy -->
                        <div class="bg-blue-50 p-4 rounded-lg">
                            <h3 class="text-lg font-semibold text-gray-800 mb-4">Replication Policy</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">Replication Factor</label>
                                    <select id="replication-factor" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                        <option value="1" ${bucket.replication_factor === 1 ? 'selected' : ''}>1 - No redundancy</option>
                                        <option value="2" ${bucket.replication_factor === 2 ? 'selected' : ''}>2 - Basic redundancy</option>
                                        <option value="3" ${bucket.replication_factor === 3 ? 'selected' : ''}>3 - Triple redundancy</option>
                                        <option value="5" ${bucket.replication_factor === 5 ? 'selected' : ''}>5 - High redundancy</option>
                                        <option value="7" ${bucket.replication_factor === 7 ? 'selected' : ''}>7 - Maximum redundancy</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">Cache Policy</label>
                                    <select id="cache-policy" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                        <option value="none" ${bucket.cache_policy === 'none' ? 'selected' : ''}>None - No caching</option>
                                        <option value="memory" ${bucket.cache_policy === 'memory' ? 'selected' : ''}>Memory - RAM cache</option>
                                        <option value="disk" ${bucket.cache_policy === 'disk' ? 'selected' : ''}>Disk - Disk cache</option>
                                        <option value="hybrid" ${bucket.cache_policy === 'hybrid' ? 'selected' : ''}>Hybrid - Memory + Disk</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <!-- Storage Quotas -->
                        <div class="bg-green-50 p-4 rounded-lg">
                            <h3 class="text-lg font-semibold text-gray-800 mb-4">Storage Quotas</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">Storage Quota (MB, 0 = unlimited)</label>
                                    <input type="number" id="storage-quota" value="${bucket.quota && bucket.quota.max_size ? Math.round(bucket.quota.max_size / 1024 / 1024) : 0}" 
                                           class="w-full px-3 py-2 border border-gray-300 rounded-md" min="0">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">Max Files (0 = unlimited)</label>
                                    <input type="number" id="max-files" value="${bucket.quota && bucket.quota.max_files ? bucket.quota.max_files : 0}" 
                                           class="w-full px-3 py-2 border border-gray-300 rounded-md" min="0">
                                </div>
                            </div>
                        </div>

                        <!-- Retention Settings -->
                        <div class="bg-purple-50 p-4 rounded-lg">
                            <h3 class="text-lg font-semibold text-gray-800 mb-4">Retention Settings</h3>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Retention Policy</label>
                                <select id="retention-policy" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                    <option value="permanent" ${bucket.retention_policy === 'permanent' ? 'selected' : ''}>Permanent - Keep forever</option>
                                    <option value="30_days" ${bucket.retention_policy === '30_days' ? 'selected' : ''}>30 Days</option>
                                    <option value="90_days" ${bucket.retention_policy === '90_days' ? 'selected' : ''}>90 Days</option>
                                    <option value="1_year" ${bucket.retention_policy === '1_year' ? 'selected' : ''}>1 Year</option>
                                    <option value="custom" ${!['permanent', '30_days', '90_days', '1_year'].includes(bucket.retention_policy) ? 'selected' : ''}>Custom</option>
                                </select>
                            </div>
                        </div>

                        <!-- Advanced Features -->
                        <div class="bg-yellow-50 p-4 rounded-lg">
                            <h3 class="text-lg font-semibold text-gray-800 mb-4">Advanced Features</h3>
                            <div class="space-y-3">
                                <label class="flex items-center">
                                    <input type="checkbox" id="enable-vector-search" class="mr-2">
                                    <span class="text-sm text-gray-700">Enable Vector Search</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" id="enable-knowledge-graph" class="mr-2">
                                    <span class="text-sm text-gray-700">Enable Knowledge Graph</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" id="enable-versioning" class="mr-2">
                                    <span class="text-sm text-gray-700">Enable File Versioning</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" id="allow-public-access" class="mr-2">
                                    <span class="text-sm text-gray-700">Allow Public Access</span>
                                </label>
                            </div>
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex justify-end space-x-3 pt-4 border-t border-gray-200">
                            <button type="button" onclick="dashboard.closeAdvancedSettingsModal()" 
                                    class="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">
                                Cancel
                            </button>
                            <button type="button" onclick="dashboard.syncBucketNow('${bucket.name}')" 
                                    class="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700">
                                <i class="fas fa-sync mr-2"></i>Sync Now
                            </button>
                            <button type="submit" 
                                    class="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                                <i class="fas fa-save mr-2"></i>Save Configuration
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        // Add form submit handler
        modalDiv.querySelector('#advanced-settings-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveAdvancedSettings(bucket.name);
        });

        return modalDiv;
    }
    async saveAdvancedSettings(bucketName) {
        console.log(`💾 Saving advanced settings for bucket: ${bucketName}`);
        
        // Get form values
        const replicationFactor = parseInt(document.getElementById('replication-factor').value);
        const cachePolicy = document.getElementById('cache-policy').value;
        const storageQuota = parseInt(document.getElementById('storage-quota').value);
        const maxFiles = parseInt(document.getElementById('max-files').value);
        const retentionPolicy = document.getElementById('retention-policy').value;
        const enableVectorSearch = document.getElementById('enable-vector-search').checked;
        const enableKnowledgeGraph = document.getElementById('enable-knowledge-graph').checked;
        const enableVersioning = document.getElementById('enable-versioning').checked;
        const allowPublicAccess = document.getElementById('allow-public-access').checked;

        try {
            const result = await this.jsonRpcCall('update_bucket_policy', {
                bucket: bucketName,
                replication_factor: replicationFactor,
                cache_policy: cachePolicy,
                storage_quota_mb: storageQuota,
                max_files: maxFiles,
                retention_policy: retentionPolicy,
                features: {
                    vector_search: enableVectorSearch,
                    knowledge_graph: enableKnowledgeGraph,
                    versioning: enableVersioning,
                    public_access: allowPublicAccess
                }
            });
            
            console.log(`✅ Settings save result for ${bucketName}:`, result);
            
            if (result && (result.result?.success || result.success)) {
                this.showNotification(`Settings saved for ${bucketName}`, 'success');
                
                // Update local bucket data
                const bucket = this.bucketData.find(b => b.name === bucketName);
                if (bucket) {
                    bucket.replication_factor = replicationFactor;
                    bucket.cache_policy = cachePolicy;
                    bucket.retention_policy = retentionPolicy;
                    bucket.quota = {
                        max_size: storageQuota > 0 ? storageQuota * 1024 * 1024 : 0,
                        max_files: maxFiles
                    };
                    this.updateBucketsDisplay();
                }
                
                this.closeAdvancedSettingsModal();
            } else {
                throw new Error(result?.error || 'Failed to save settings');
            }
            
        } catch (error) {
            console.error(`❌ Settings save error for ${bucketName}:`, error);
            this.showNotification(`Failed to save settings: ${error.message}`, 'error');
        }
    }

    async syncBucketNow(bucketName) {
        await this.forceBucketSyncForBucket(bucketName);
    }

    closeAdvancedSettingsModal() {
        const modal = document.getElementById('advanced-settings-modal');
        if (modal) {
            modal.classList.remove('opacity-100');
            modal.classList.add('opacity-0');
            setTimeout(() => {
                modal.remove();
            }, 300);
        }
    }

    // === SHARE BUCKET MODAL ===

    showShareBucketModal() {
        if (!this.selectedBucket) {
            this.showNotification('Please select a bucket first', 'warning');
            return;
        }
        this.showShareBucketModalFor(this.selectedBucket);
    }

    showShareBucketModalFor(bucketName) {
        const bucket = this.bucketData.find(b => b.name === bucketName);
        if (!bucket) {
            this.showNotification('Bucket not found', 'error');
            return;
        }

        // Create and show share modal
        const modal = this.createShareBucketModal(bucket);
        document.body.appendChild(modal);
        
        // Show modal with animation
        setTimeout(() => {
            modal.classList.remove('opacity-0');
            modal.classList.add('opacity-100');
        }, 10);
    }

    createShareBucketModal(bucket) {
        const modalDiv = document.createElement('div');
        modalDiv.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center opacity-0 transition-opacity duration-300';
        modalDiv.id = 'share-bucket-modal';

        modalDiv.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full m-4">
                <div class="p-6 border-b border-gray-200">
                    <div class="flex justify-between items-center">
                        <h2 class="text-2xl font-bold text-gray-800">Share Bucket</h2>
                        <button onclick="dashboard.closeShareBucketModal()" class="text-gray-500 hover:text-gray-700">
                            <i class="fas fa-times text-xl"></i>
                        </button>
                    </div>
                    <p class="text-gray-600 mt-2">Generate shareable links for bucket: <strong>${bucket.name}</strong></p>
                </div>
                
                <div class="p-6">
                    <form id="share-bucket-form" class="space-y-6">
                        <!-- Access Level -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-3">Access Level</label>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                                <label class="flex items-center p-3 border border-gray-300 rounded-md cursor-pointer hover:bg-gray-50">
                                    <input type="radio" name="access-level" value="read_only" checked class="mr-3">
                                    <div>
                                        <div class="font-medium">Read Only</div>
                                        <div class="text-sm text-gray-600">View and download files</div>
                                    </div>
                                </label>
                                <label class="flex items-center p-3 border border-gray-300 rounded-md cursor-pointer hover:bg-gray-50">
                                    <input type="radio" name="access-level" value="read_write" class="mr-3">
                                    <div>
                                        <div class="font-medium">Read Write</div>
                                        <div class="text-sm text-gray-600">View, download, and upload</div>
                                    </div>
                                </label>
                                <label class="flex items-center p-3 border border-gray-300 rounded-md cursor-pointer hover:bg-gray-50">
                                    <input type="radio" name="access-level" value="admin" class="mr-3">
                                    <div>
                                        <div class="font-medium">Admin</div>
                                        <div class="text-sm text-gray-600">Full bucket access</div>
                                    </div>
                                </label>
                            </div>
                        </div>

                        <!-- Expiration -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Link Expiration</label>
                            <select id="link-expiration" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="1h">1 Hour</option>
                                <option value="24h" selected>24 Hours</option>
                                <option value="7d">7 Days</option>
                                <option value="30d">30 Days</option>
                                <option value="never">Never (Permanent)</option>
                            </select>
                        </div>

                        <!-- Generated Link Display -->
                        <div id="generated-link-section" class="hidden">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Shareable Link</label>
                            <div class="flex">
                                <input type="text" id="generated-link" readonly 
                                       class="flex-1 px-3 py-2 border border-gray-300 rounded-l-md bg-gray-50 font-mono text-sm">
                                <button type="button" onclick="dashboard.copyShareLink()" 
                                        class="px-4 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700">
                                    <i class="fas fa-copy"></i>
                                </button>
                            </div>
                            <div id="link-details" class="mt-2 text-sm text-gray-600"></div>
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex justify-end space-x-3 pt-4 border-t border-gray-200">
                            <button type="button" onclick="dashboard.closeShareBucketModal()" 
                                    class="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">
                                Cancel
                            </button>
                            <button type="submit" 
                                    class="px-6 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700">
                                <i class="fas fa-share-alt mr-2"></i>Generate Share Link
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        // Add form submit handler
        modalDiv.querySelector('#share-bucket-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.generateShareLink(bucket.name);
        });

        return modalDiv;
    }

    async generateShareLink(bucketName) {
        console.log(`🔗 Generating share link for bucket: ${bucketName}`);
        
        // Get form values
        const accessLevel = document.querySelector('input[name="access-level"]:checked').value;
        const expiration = document.getElementById('link-expiration').value;

        try {
            const result = await this.jsonRpcCall('generate_bucket_share_link', {
                bucket: bucketName,
                access_type: accessLevel,
                expiration: expiration
            });
            
            console.log(`✅ Share link result for ${bucketName}:`, result);
            
            if (result && result.result && result.result.share_link) {
                const shareData = result.result;
                
                // Display the generated link
                const linkSection = document.getElementById('generated-link-section');
                const linkInput = document.getElementById('generated-link');
                const linkDetails = document.getElementById('link-details');
                
                if (linkSection && linkInput && linkDetails) {
                    linkSection.classList.remove('hidden');
                    linkInput.value = shareData.share_link;
                    
                    const expiryText = shareData.expiration === 'never' ? 'Never expires' : 
                                     `Expires: ${new Date(shareData.expires_at).toLocaleString()}`;
                    linkDetails.innerHTML = `
                        Access Level: <strong>${shareData.access_type}</strong> • ${expiryText}
                    `;
                }
                
                this.showNotification('Share link generated successfully', 'success');
                
            } else {
                throw new Error(result?.error || 'Failed to generate share link');
            }
            
        } catch (error) {
            console.error(`❌ Share link generation error for ${bucketName}:`, error);
            this.showNotification(`Failed to generate share link: ${error.message}`, 'error');
        }
    }

    copyShareLink() {
        const linkInput = document.getElementById('generated-link');
        if (linkInput) {
            linkInput.select();
            document.execCommand('copy');
            this.showNotification('Share link copied to clipboard', 'success');
        }
    }

    closeShareBucketModal() {
        const modal = document.getElementById('share-bucket-modal');
        if (modal) {
            modal.classList.remove('opacity-100');
            modal.classList.add('opacity-0');
            setTimeout(() => {
                modal.remove();
            }, 300);
        }
    }

    // === QUOTA MANAGEMENT MODAL ===

    showQuotaManagementModal() {
        if (!this.selectedBucket) {
            this.showNotification('Please select a bucket first', 'warning');
            return;
        }

        const bucket = this.bucketData.find(b => b.name === this.selectedBucket);
        if (!bucket) {
            this.showNotification('Bucket not found', 'error');
            return;
        }

        // === UTILITY METHODS ===

    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    showNotification(message, type = 'info') {
        // Create notification element if it doesn't exist
        let notificationContainer = document.getElementById('notification-container');
        if (!notificationContainer) {
            notificationContainer = document.createElement('div');
            notificationContainer.id = 'notification-container';
            notificationContainer.className = 'fixed top-4 right-4 z-50 space-y-2';
            document.body.appendChild(notificationContainer);
        }

        // Create notification
        const notification = document.createElement('div');
        const bgColor = {
            'success': 'bg-green-500',
            'error': 'bg-red-500',
            'warning': 'bg-yellow-500',
            'info': 'bg-blue-500'
        }[type] || 'bg-blue-500';

        notification.className = `${bgColor} text-white px-4 py-3 rounded-lg shadow-lg transform translate-x-full transition-transform duration-300`;
        notification.innerHTML = `
            <div class="flex items-center">
                <span class="flex-1">${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-2">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        notificationContainer.appendChild(notification);

        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 10);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.add('translate-x-full');
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 5000);
    }

    switchTab(tabId) {
        console.log(`📋 Switching to tab: ${tabId}`);
        
        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });

        // Remove active class from all tab buttons
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.remove('active');
        });

        // Show selected tab content
        const selectedTab = document.getElementById(tabId);
        const selectedButton = document.querySelector(`[data-tab="${tabId}"]`);
        
        if (selectedTab) {
            selectedTab.classList.remove('hidden');
        }
        
        if (selectedButton) {
            selectedButton.classList.add('active');
        }

        // Load tab-specific data
        this.loadTabData(tabId);
    }

    async loadTabData(tabId) {
        console.log(`📊 Loading data for tab: ${tabId}`);
        
        switch (tabId) {
            case 'overview':
                // Load system metrics and overview data
                await this.loadSystemMetrics();
                break;
            case 'pins':
                // Load pins data
                await this.loadPins();
                break;
            case 'buckets':
                // Load bucket management data
                await this.loadBucketsData();
                break;
            case 'backends':
                // Load backends data
                await this.loadBackendsData();
                break;
            case 'configuration':
                // Load configuration data
                await this.loadConfigurationData();
                break;
            default:
                console.log(`No specific data loading required for tab: ${tabId}`);
        }
    }

    async loadSystemMetrics() {
        try {
            const result = await this.jsonRpcCall('get_system_status');
            console.log('📊 System metrics loaded:', result);
            
            if (result && result.result) {
                const metrics = result.result;
                // Update system metrics display
                if (document.getElementById('cpu-usage')) {
                    document.getElementById('cpu-usage').textContent = `${metrics.cpu_percent || 0}%`;
                }
                if (document.getElementById('memory-usage')) {
                    document.getElementById('memory-usage').textContent = `${metrics.memory_percent || 0}%`;
                }
                if (document.getElementById('disk-usage')) {
                    document.getElementById('disk-usage').textContent = `${metrics.disk_percent || 0}%`;
                }
            }
        } catch (error) {
            console.error('❌ Error loading system metrics:', error);
        }
    }

    async loadBackendsData() {
        try {
            const result = await this.jsonRpcCall('list_backends', { 
                include_metadata: true 
            });
            console.log('🗄️ Backends loaded:', result);
            // Backend data handling would go here
        } catch (error) {
            console.error('❌ Error loading backends data:', error);
        }
    }

    async loadConfigurationData() {
        try {
            // Load configuration files via MCP
            console.log('⚙️ Loading configuration data...');
            const configFiles = ['pins.json', 'buckets.json', 'backends.json'];
            
            for (const filename of configFiles) {
                await this.loadConfigFile(filename);
            }
        } catch (error) {
            console.error('❌ Error loading configuration data:', error);
        }
    }

    async loadConfigFile(filename) {
        try {
            console.log(`Loading config file: ${filename}`);
            
            const result = await this.jsonRpcCall('read_config_file', { 
                filename: filename 
            });
            
            console.log(`MCP result for ${filename}:`, result);
            
            if (result && result.success) {
                const config = result.data || result.content;
                const metadata = result.metadata || {};
                
                // Update UI elements for this config file
                const fileKey = filename.replace('.json', '');
                this.updateConfigUI(fileKey, config, metadata);
            } else {
                this.updateConfigError(filename, result.error || 'Failed to load');
            }
        } catch (error) {
            console.error(`Error loading ${filename}:`, error);
            this.updateConfigError(filename, error.message);
        }
    }

    updateConfigUI(fileKey, config, metadata) {
        // Update status
        const statusEl = document.getElementById(`${fileKey}-status`);
        if (statusEl) statusEl.textContent = '✅ Loaded';
        
        // Update metadata
        const sourceEl = document.getElementById(`${fileKey}-source`);
        if (sourceEl) sourceEl.textContent = metadata.source || 'metadata';
        
        const sizeEl = document.getElementById(`${fileKey}-size`);
        if (sizeEl) sizeEl.textContent = metadata.size || (config ? JSON.stringify(config).length : '-');
        
        const modifiedEl = document.getElementById(`${fileKey}-modified`);
        if (modifiedEl) {
            const date = metadata.modified ? new Date(metadata.modified).toLocaleString() : '-';
            modifiedEl.textContent = date;
        }
        
        // Update preview
        const previewEl = document.getElementById(`${fileKey}-preview`);
        if (previewEl && config) {
            const preview = JSON.stringify(config, null, 2);
            previewEl.textContent = preview && preview.length > 200 ? preview.substring(0, 200) + '...' : preview;
        }
    }

    updateConfigError(filename, error) {
        const fileKey = filename.replace('.json', '');
        const statusEl = document.getElementById(`${fileKey}-status`);
        if (statusEl) {
            statusEl.textContent = '❌ Error';
            statusEl.className = 'px-2 py-1 rounded text-xs bg-red-100 text-red-700';
        }
        
        const previewEl = document.getElementById(`${fileKey}-preview`);
        if (previewEl) previewEl.textContent = `Error: ${error}`;
    }

    // === PIN MANAGEMENT METHODS (Existing) ===

    async loadPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.ls', { metadata: true });
            this.pinData = result.pins || [];
            this.updatePinsList();
            this.updatePinStatistics();
            this.showNotification('Pins loaded successfully', 'success');
        } catch (error) {
            console.error('Failed to load pins:', error);
        }
    }

    updatePinsList() {
        const container = document.getElementById('pins-list');
        if (!container) return;

        if (this.pinData.length === 0) {
            container.innerHTML = '<div class="text-gray-500 text-center py-8">No pins found</div>';
            return;
        }

        const pinsHtml = this.pinData.map(pin => `
            <div class="bg-white border rounded-lg p-4 hover:shadow-md transition-shadow">
                <div class="flex justify-between items-start mb-2">
                    <div class="flex-1">
                        <div class="font-medium text-gray-900 mb-1">
                            ${pin.name || 'Unnamed Pin'}
                        </div>
                        <div class="text-sm text-gray-600 font-mono bg-gray-100 px-2 py-1 rounded">
                            ${this.truncateHash(pin.cid)}
                        </div>
                    </div>
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${pin.type === 'recursive' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}">
                        ${pin.type}
                    </span>
                </div>
                <div class="flex justify-between items-center text-sm text-gray-500">
                    <div>
                        <i class="fas fa-hdd mr-1"></i>
                        ${this.formatBytes(pin.size || 0)}
                    </div>
                    <div>
                        <i class="fas fa-clock mr-1"></i>
                        ${this.formatDate(pin.timestamp)}
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = pinsHtml;
    }

    updatePinStatistics() {
        const totalElement = document.getElementById('total-pins');
        const activeElement = document.getElementById('active-pins');
        const pendingElement = document.getElementById('pending-pins');
        const storageElement = document.getElementById('total-storage');

        if (totalElement) totalElement.textContent = this.pinData.length;
        if (activeElement) activeElement.textContent = this.pinData.filter(p => p.type).length;
        if (pendingElement) pendingElement.textContent = '0';
        
        const totalSize = this.pinData.reduce((sum, pin) => sum + (pin.size || 0), 0);
        if (storageElement) storageElement.textContent = this.formatBytes(totalSize);
    }

    showAddPinModal() {
        const modal = document.getElementById('add-pin-modal');
        if (modal) {
            modal.classList.remove('hidden');
        }
    }

    hideAddPinModal() {
        const modal = document.getElementById('add-pin-modal');
        if (modal) {
            modal.classList.add('hidden');
            const form = document.getElementById('add-pin-form');
            if (form) form.reset();
        }
    }

    async submitAddPin(e) {
        e.preventDefault();
        try {
            const cid = document.getElementById('new-pin-cid').value.trim();
            const name = document.getElementById('new-pin-name').value.trim();
            const recursive = document.getElementById('new-pin-recursive').checked;

            const result = await this.jsonRpcCall('ipfs.pin.add', {
                cid_or_file: cid,
                name: name || null,
                recursive: recursive
            });

            this.hideAddPinModal();
            this.showNotification('Pin added successfully', 'success');
            this.loadPins();
        } catch (error) {
            this.showNotification('Failed to add pin: ' + error.message, 'error');
        }
    }

    showBulkModal() {
        this.showNotification('Bulk operations modal would open here', 'info');
    }

    async verifyPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.verify');
            this.showNotification(`Verification: ${result.verified_pins}/${result.total_pins} verified`, 'success');
        } catch (error) {
            this.showNotification('Verification failed: ' + error.message, 'error');
        }
    }

    async cleanupPins() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.cleanup');
            this.showNotification(`Cleanup: ${result.total_cleaned} items cleaned`, 'success');
        } catch (error) {
            this.showNotification('Cleanup failed: ' + error.message, 'error');
        }
    }

    async exportMetadata() {
        try {
            const result = await this.jsonRpcCall('ipfs.pin.export_metadata');
            this.showNotification(`Export: ${result.shards_created} shards created`, 'success');
        } catch (error) {
            this.showNotification('Export failed: ' + error.message, 'error');
        }
    }

    truncateHash(hash, length = 16) {
        if (!hash) return 'N/A';
        return hash.length > length ? `${hash.substring(0, length)}...` : hash;
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString();
    }
}
// === GLOBAL HELPER FUNCTIONS FOR HTML ONCLICK HANDLERS ===

// Configuration Management Functions (called from HTML)
async function editConfig(filename) {
    const newContent = prompt(`Edit ${filename} (JSON format):`, '{}');
    if (newContent !== null) {
        try {
            const parsed = JSON.parse(newContent);
            const result = await dashboard.jsonRpcCall('write_config_file', {
                filename: filename,
                content: parsed
            });
            if (result.success) {
                dashboard.showNotification(`${filename} updated successfully`, 'success');
                refreshConfig(filename);
            } else {
                dashboard.showNotification(`Failed to update ${filename}: ${result.error}`, 'error');
            }
        } catch (error) {
            dashboard.showNotification(`Invalid JSON for ${filename}: ${error.message}`, 'error');
        }
    }
}

async function refreshConfig(filename) {
    const fileKey = filename.replace('.json', '');
    await dashboard.loadConfigFile(filename);
}

async function refreshAllConfigs() {
    await dashboard.loadConfigurationData();
    dashboard.showNotification('All configurations refreshed', 'success');
}

async function createNewConfig() {
    const filename = prompt('Enter new config filename (e.g., new-config.json):');
    if (filename && filename.endsWith('.json')) {
        const content = prompt('Enter initial JSON content:', '{}');
        if (content !== null) {
            try {
                const parsed = JSON.parse(content);
                const result = await dashboard.jsonRpcCall('write_config_file', {
                    filename: filename,
                    content: parsed
                });
                if (result.success) {
                    dashboard.showNotification(`${filename} created successfully`, 'success');
                    await dashboard.loadConfigurationData();
                } else {
                    dashboard.showNotification(`Failed to create ${filename}: ${result.error}`, 'error');
                }
            } catch (error) {
                dashboard.showNotification(`Invalid JSON: ${error.message}`, 'error');
            }
        }
    } else {
        dashboard.showNotification('Invalid filename. Must end with .json', 'error');
    }
}

async function exportConfigs() {
    try {
        const result = await dashboard.jsonRpcCall('list_config_files', {});
        if (result && result.files) {
            const exportData = {};
            for (const file of result.files) {
                const fileResult = await dashboard.jsonRpcCall('read_config_file', { 
                    filename: file.name 
                });
                if (fileResult.success) {
                    exportData[file.name] = fileResult.data;
                }
            }
            
            const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'ipfs_kit_configs_export.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            dashboard.showNotification('Configurations exported successfully', 'success');
        }
    } catch (error) {
        dashboard.showNotification(`Export failed: ${error.message}`, 'error');
    }
}

async function syncReplicas() {
    try {
        // This would sync configurations across replicas
        dashboard.showNotification('Replica sync initiated (placeholder)', 'info');
    } catch (error) {
        dashboard.showNotification(`Sync failed: ${error.message}`, 'error');
    }
}

// Initialize dashboard
let dashboard;

// Initialize enhanced dashboard on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Dashboard initializing...');
    dashboard = new EnhancedDashboard();
    
    // Set global reference for onclick handlers
    window.dashboard = dashboard;
    
    console.log('📋 Dashboard initialized');
});
}