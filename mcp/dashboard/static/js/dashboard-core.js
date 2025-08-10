// Utility Functions
const formatBytes = (bytes, decimals = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

// Tab Switching
function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    // Show the selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Update active link style
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`.nav-link[onclick="showTab('${tabName}')"]`).classList.add('active');

    // Load data for the selected tab
    if (tabName === 'overview') {
        loadOverviewData();
    } else if (tabName === 'services') {
        loadServices();
    } else if (tabName === 'backends') {
        loadBackends();
    } else if (tabName === 'buckets') {
        loadBuckets();
    } else if (tabName === 'metrics') {
        loadMetrics();
    } else if (tabName === 'config') {
        loadConfig();
    } else if (tabName === 'mcp') {
        loadMcpDetails();
    } else if (tabName === 'pins') {
        loadPins();
    }
    
    // Close mobile sidebar on tab selection
    const sidebar = document.getElementById('sidebar');
    if (sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
        document.getElementById('mobile-overlay').classList.add('hidden');
    }
}

// Global Refresh and Timers
function refreshData() {
    const activeTab = document.querySelector('.nav-link.active').getAttribute('onclick').replace("showTab('", "").replace("')", "");
    showTab(activeTab);
}

function updateTime() {
    const now = new Date();
    document.getElementById('current-time').textContent = now.toLocaleTimeString();
}

// Mobile Menu
document.addEventListener('DOMContentLoaded', () => {
    // Mobile menu initialization
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const mobileOverlay = document.getElementById('mobile-overlay');
    
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            mobileOverlay.classList.toggle('hidden');
        });
    }
    
    if (mobileOverlay) {
        mobileOverlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            mobileOverlay.classList.add('hidden');
        });
    }
    
    // Initial Load
    showTab('overview');
    setInterval(refreshData, 5000); // Auto-refresh data every 5 seconds
    setInterval(updateTime, 1000);
});
