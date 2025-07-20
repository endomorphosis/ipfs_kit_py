/**
 * Dashboard Core Functionality
 * Clean implementation focused on tab management and auto-refresh
 */

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded: Initializing dashboard...');
    
    // Initialize expandable sections
    initializeExpandables();
    
    // Load overview tab by default
    showTab('overview');
    
    // Start auto-refresh
    startAutoRefresh();
});

// Tab management
function showTab(tabName, event) {
    console.log('showTab: Switching to tab:', tabName);
    
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab
    const selectedTab = document.getElementById(tabName);
    if (selectedTab) {
        selectedTab.classList.add('active');
        console.log('showTab: Activated tab:', tabName);
        
        // Mark button as active
        if (event && event.target) {
            event.target.classList.add('active');
        }
        
        // Load tab-specific content
        switch(tabName) {
            case 'overview':
                if (typeof refreshData === 'function') {
                    refreshData();
                    updatePerformanceMetrics();
                }
                break;
            case 'vfs':
                if (typeof loadVFSTab === 'function') {
                    loadVFSTab();
                }
                break;
            case 'monitoring':
                if (typeof refreshMonitoring === 'function') {
                    refreshMonitoring();
                }
                break;
            case 'vectorkb':
                if (typeof loadVectorKBTab === 'function') {
                    loadVectorKBTab();
                }
                break;
            case 'backends':
                if (typeof loadBackendsTab === 'function') {
                    loadBackendsTab();
                }
                break;
            case 'filemanager':
                if (typeof loadFileManagerTab === 'function') {
                    loadFileManagerTab();
                }
                break;
            case 'configuration':
                if (typeof loadConfigurationTab === 'function') {
                    loadConfigurationTab();
                }
                break;
        }
    } else {
        console.error('showTab: Tab not found:', tabName);
    }
}

// Auto-refresh system
function startAutoRefresh() {
    console.log('startAutoRefresh: Starting auto-refresh...');
    
    setInterval(() => {
        // Only refresh data for the currently active tab
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab) {
            const tabId = activeTab.id;
            
            // Call the appropriate refresh function based on active tab
            if (tabId === 'overview' && typeof refreshData === 'function') {
                refreshData();
                updatePerformanceMetrics();
            } else if (tabId === 'vfs' && typeof loadVFSTab === 'function') {
                loadVFSTab();
            } else if (tabId === 'monitoring' && typeof refreshMonitoring === 'function') {
                refreshMonitoring();
            }
        }
    }, 15000); // Refresh every 15 seconds
    
    console.log('startAutoRefresh: Auto-refresh configured');
}

// Performance metrics display
async function updatePerformanceMetrics() {
    console.log('updatePerformanceMetrics: Fetching performance data...');
    
    try {
        // Get fresh health data
        const data = await dashboardAPI.getHealth();
        
        const performanceElement = document.getElementById('performanceMetrics');
        if (!performanceElement) {
            console.warn('updatePerformanceMetrics: performanceMetrics element not found');
            return;
        }
        
        // Create performance metrics display
        const metricsHtml = `
            <div class="performance-metrics-card">
                <h4>📊 Performance Metrics</h4>
                <div class="metrics-grid">
                    <div class="metric">
                        <span class="metric-label">Memory Usage:</span>
                        <span class="metric-value">${data.memory_usage_mb ? data.memory_usage_mb.toFixed(1) + ' MB' : 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">CPU Usage:</span>
                        <span class="metric-value">${data.cpu_usage_percent !== undefined ? data.cpu_usage_percent.toFixed(1) + '%' : 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Uptime:</span>
                        <span class="metric-value">${data.uptime_seconds ? formatUptime(data.uptime_seconds) : 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Active Backends:</span>
                        <span class="metric-value">${data.backend_health && data.backend_health.backends ? Object.keys(data.backend_health.backends).length : 0}</span>
                    </div>
                </div>
            </div>
        `;
        
        performanceElement.innerHTML = metricsHtml;
        console.log('updatePerformanceMetrics: Performance metrics updated');
        
    } catch (error) {
        console.error('updatePerformanceMetrics: Error updating performance metrics:', error);
    }
}

function formatUptime(seconds) {
    if (!seconds || seconds < 0) return 'N/A';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

function initializeExpandables() {
    console.log('initializeExpandables: Initializing expandable sections...');
    
    // Find all expandable headers and add click handlers
    document.querySelectorAll('.expandable-header').forEach(header => {
        header.addEventListener('click', () => {
            const expandable = header.parentElement;
            expandable.classList.toggle('expanded');
        });
    });
}

// Placeholder functions for modal management
function openConfigModal(backendName) {
    console.log('openConfigModal: Opening config for', backendName);
    // Implementation would go here
}

function closeConfigModal() {
    console.log('closeConfigModal: Closing config modal');
    // Implementation would go here
}

function openLogsModal(backendName) {
    console.log('openLogsModal: Opening logs for', backendName);
    // Implementation would go here
}

function closeLogsModal() {
    console.log('closeLogsModal: Closing logs modal');
    // Implementation would go here
}

function restartBackend(backendName) {
    console.log('restartBackend: Restarting', backendName);
    // Implementation would go here
}

// Control functions
function toggleAutoRefresh() {
    console.log('toggleAutoRefresh: Toggle requested');
    // Implementation would go here
}

function exportConfig() {
    console.log('exportConfig: Export requested');
    // Implementation would go here
}

function getInsights() {
    console.log('getInsights: Insights requested');
    // Implementation would go here
}

// File Manager related functions
function loadFileManagerTab() {
    console.log('loadFileManagerTab: Loading file manager tab...');
    const fileManagerContainer = document.getElementById('filemanager');
    if (!fileManagerContainer) {
        console.error('loadFileManagerTab: #filemanager element not found.');
        return;
    }
    // Check if fileManager exists from file_manager.js
    if (typeof fileManager !== 'undefined' && fileManager.refresh) {
        fileManager.refresh();
        console.log('loadFileManagerTab: fileManager refreshed.');
    } else {
        console.warn('loadFileManagerTab: fileManager object not found or refresh method missing.');
    }
}

// Modal functions
function createFolderPrompt() {
    const folderName = prompt("Enter folder name:");
    if (folderName) {
        if (typeof fileManager !== 'undefined' && fileManager.createNewFolder) {
            fileManager.createNewFolder(folderName);
        } else {
            console.warn('createFolderPrompt: fileManager not available');
        }
    }
}

function uploadSelectedFile() {
    const fileInput = document.getElementById('fileUploadInput');
    if (fileInput) {
        fileInput.click();
    } else {
        console.warn('uploadSelectedFile: fileUploadInput not found');
    }
}

function setupDragAndDrop() {
    const dropZone = document.getElementById('dropZone');
    const fileManagerList = document.getElementById('fileManagerList');

    if (!dropZone || !fileManagerList) {
        console.warn('setupDragAndDrop: Drop zone or file manager list not found. Skipping drag and drop setup.');
        return;
    }

    dropZone.addEventListener('dragover', (event) => {
        event.preventDefault();
        dropZone.classList.add('active');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('active');
    });

    dropZone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropZone.classList.remove('active');
        const files = event.dataTransfer.files;
        if (typeof fileManager !== 'undefined' && fileManager.handleFileUpload) {
            fileManager.handleFileUpload(files);
        } else {
            console.warn('setupDragAndDrop: fileManager not available for file upload');
        }
    });
    console.log('setupDragAndDrop: Drag and drop setup complete.');
}

// Expose functions globally for HTML compatibility
window.showTab = showTab;
window.refreshData = refreshData;
window.updatePerformanceMetrics = updatePerformanceMetrics;
window.getInsights = getInsights;
window.exportConfig = exportConfig;
window.toggleAutoRefresh = toggleAutoRefresh;
window.openConfigModal = openConfigModal;
window.closeConfigModal = closeConfigModal;
window.openLogsModal = openLogsModal;
window.closeLogsModal = closeLogsModal;
window.restartBackend = restartBackend;
window.loadFileManagerTab = loadFileManagerTab;
window.createFolderPrompt = createFolderPrompt;
window.uploadSelectedFile = uploadSelectedFile;
window.setupDragAndDrop = setupDragAndDrop;
