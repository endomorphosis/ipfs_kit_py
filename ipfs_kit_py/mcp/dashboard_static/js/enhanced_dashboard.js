// Enhanced Dashboard JavaScript
class EnhancedDashboard {
    constructor() {
        this.socket = null;
        this.charts = {};
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.initializeCharts();
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
        };
        
        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        this.socket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
        };
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connectionStatus');
        if (statusElement) {
            statusElement.textContent = connected ? 'Connected' : 'Disconnected';
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'initial_data':
            case 'update':
                this.updateDashboardData(data.data);
                break;
        }
    }
    
    updateDashboardData(data) {
        // Update metric cards and charts
        console.log('Updating dashboard with:', data);
    }
    
    initializeCharts() {
        // Initialize Chart.js charts
        const systemCtx = document.getElementById('systemMetricsChart');
        if (systemCtx) {
            this.charts.systemMetrics = new Chart(systemCtx, {
                type: 'line',
                data: { labels: [], datasets: [] },
                options: { responsive: true }
            });
        }
    }
}

function initializeDashboard(initialData) {
    const dashboard = new EnhancedDashboard();
    window.dashboard = dashboard;
    
    if (initialData) {
        dashboard.updateDashboardData(initialData);
    }
}