/**
 * Peer Discovery and Management Tab
 * 
 * Provides comprehensive peer discovery, management, and content visualization
 * for libp2p networks, IPFS, and IPFS Cluster peers.
 */

class PeerManager {
    constructor() {
        this.peers = new Map();
        this.discoveryActive = false;
        this.refreshInterval = null;
        this.currentView = 'list'; // list, details, content
        this.selectedPeer = null;
        this.filters = {
            protocol: null,
            connected: null,
            search: ''
        };
        this.pagination = {
            limit: 50,
            offset: 0,
            total: 0
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.startAutoRefresh();
    }
    
    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('peer-search');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(() => {
                this.filters.search = searchInput.value;
                this.refreshPeersList();
            }, 300));
        }
        
        // Filter buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('.filter-protocol')) {
                this.filters.protocol = e.target.dataset.protocol;
                this.updateFilterButtons();
                this.refreshPeersList();
            }
            
            if (e.target.matches('.filter-connection')) {
                this.filters.connected = e.target.dataset.connected === 'true' ? true : 
                                       e.target.dataset.connected === 'false' ? false : null;
                this.updateFilterButtons();
                this.refreshPeersList();
            }
            
            // Peer action buttons
            if (e.target.matches('.peer-connect-btn')) {
                const peerId = e.target.dataset.peerId;
                this.connectToPeer(peerId);
            }
            
            if (e.target.matches('.peer-disconnect-btn')) {
                const peerId = e.target.dataset.peerId;
                this.disconnectFromPeer(peerId);
            }
            
            if (e.target.matches('.peer-details-btn')) {
                const peerId = e.target.dataset.peerId;
                this.showPeerDetails(peerId);
            }
            
            // Discovery control buttons
            if (e.target.matches('#start-discovery-btn')) {
                this.startDiscovery();
            }
            
            if (e.target.matches('#stop-discovery-btn')) {
                this.stopDiscovery();
            }
        });
        
        // Pagination
        document.addEventListener('click', (e) => {
            if (e.target.matches('.pagination-prev')) {
                if (this.pagination.offset > 0) {
                    this.pagination.offset -= this.pagination.limit;
                    this.refreshPeersList();
                }
            }
            
            if (e.target.matches('.pagination-next')) {
                if (this.pagination.offset + this.pagination.limit < this.pagination.total) {
                    this.pagination.offset += this.pagination.limit;
                    this.refreshPeersList();
                }
            }
        });
    }
    
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            if (this.currentView === 'list') {
                this.refreshPeersList();
            }
            this.refreshSummary();
        }, 10000); // Refresh every 10 seconds
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    async refreshSummary() {
        try {
            const response = await fetch('/api/peers/summary');
            const result = await response.json();
            
            if (result.success) {
                this.updateSummaryDisplay(result.data);
                this.discoveryActive = result.data.discovery_active;
                this.updateDiscoveryControls();
            }
        } catch (error) {
            console.error('Error refreshing peer summary:', error);
        }
    }
    
    async refreshPeersList() {
        try {
            const params = new URLSearchParams({
                limit: this.pagination.limit.toString(),
                offset: this.pagination.offset.toString()
            });
            
            if (this.filters.protocol) {
                params.append('filter_protocol', this.filters.protocol);
            }
            
            if (this.filters.connected !== null) {
                params.append('filter_connected', this.filters.connected.toString());
            }
            
            const response = await fetch(`/api/peers/list?${params}`);
            const result = await response.json();
            
            if (result.success) {
                this.peers.clear();
                result.data.peers.forEach(peer => {
                    this.peers.set(peer.peer_id || peer.id, peer);
                });
                
                this.pagination.total = result.data.pagination.total;
                this.updatePeersDisplay();
                this.updatePagination();
            }
        } catch (error) {
            console.error('Error refreshing peers list:', error);
        }
    }
    
    updateSummaryDisplay(summary) {
        // Update summary cards
        this.updateElement('total-peers-count', summary.total_peers || 0);
        this.updateElement('connected-peers-count', summary.connected_peers || 0);
        this.updateElement('discovery-status', summary.discovery_active ? 'Active' : 'Inactive');
        this.updateElement('bootstrap-peers-count', summary.bootstrap_peers || 0);
        
        // Update protocol distribution
        this.updateProtocolChart(summary.protocols || {});
        
        // Update recent events
        this.updateRecentEvents(summary.recent_events || []);
    }
    
    updatePeersDisplay() {
        const container = document.getElementById('peers-list-container');
        if (!container) return;
        
        container.innerHTML = Array.from(this.peers.values()).map(peer => 
            this.createPeerCard(peer)
        ).join('');
    }
    
    createPeerCard(peer) {
        const isConnected = peer.connected || peer.connection_status === 'connected';
        const lastSeen = peer.last_seen ? new Date(peer.last_seen * 1000).toLocaleString() : 'Unknown';
        const protocols = (peer.protocols || []).join(', ') || 'None';
        const multiaddrs = (peer.multiaddrs || []).slice(0, 2); // Show first 2 addresses
        
        return `
            <div class="peer-card ${isConnected ? 'connected' : 'disconnected'}">
                <div class="peer-header">
                    <div class="peer-id">
                        <strong>ID:</strong> <code>${this.truncateText(peer.peer_id || peer.id, 20)}</code>
                        <span class="status-badge ${isConnected ? 'connected' : 'disconnected'}">
                            ${isConnected ? '🟢' : '🔴'} ${isConnected ? 'Connected' : 'Disconnected'}
                        </span>
                    </div>
                    <div class="peer-actions">
                        ${isConnected ? 
                            `<button class="btn btn-sm btn-warning peer-disconnect-btn" data-peer-id="${peer.peer_id || peer.id}">Disconnect</button>` :
                            `<button class="btn btn-sm btn-primary peer-connect-btn" data-peer-id="${peer.peer_id || peer.id}">Connect</button>`
                        }
                        <button class="btn btn-sm btn-info peer-details-btn" data-peer-id="${peer.peer_id || peer.id}">Details</button>
                    </div>
                </div>
                
                <div class="peer-info">
                    <div class="peer-detail"><strong>Protocols:</strong> ${protocols}</div>
                    <div class="peer-detail"><strong>Last Seen:</strong> ${lastSeen}</div>
                    ${peer.latency_ms ? `<div class="peer-detail"><strong>Latency:</strong> ${peer.latency_ms}ms</div>` : ''}
                    ${peer.agent_version !== 'unknown' ? `<div class="peer-detail"><strong>Agent:</strong> ${peer.agent_version}</div>` : ''}
                    ${peer.cluster_peer ? '<div class="peer-detail"><span class="badge badge-cluster">🏘️ Cluster Peer</span></div>' : ''}
                </div>
                
                ${multiaddrs.length > 0 ? `
                    <div class="peer-addresses">
                        <strong>Addresses:</strong>
                        ${multiaddrs.map(addr => `<div class="multiaddr"><code>${this.truncateText(addr, 60)}</code></div>`).join('')}
                        ${peer.multiaddrs && peer.multiaddrs.length > 2 ? `<div class="more-addresses">... and ${peer.multiaddrs.length - 2} more</div>` : ''}
                    </div>
                ` : ''}
                
                ${peer.shared_pins && peer.shared_pins.length > 0 ? `
                    <div class="peer-content">
                        <strong>Shared Content:</strong> ${peer.shared_pins.length} items
                        <button class="btn btn-sm btn-secondary view-content-btn" data-peer-id="${peer.peer_id || peer.id}">View Content</button>
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    updateProtocolChart(protocols) {
        const chartContainer = document.getElementById('protocol-chart');
        if (!chartContainer) return;
        
        const total = Object.values(protocols).reduce((sum, count) => sum + count, 0);
        
        chartContainer.innerHTML = Object.entries(protocols).map(([protocol, count]) => {
            const percentage = total > 0 ? (count / total * 100).toFixed(1) : 0;
            return `
                <div class="protocol-bar">
                    <div class="protocol-label">${protocol}</div>
                    <div class="protocol-progress">
                        <div class="progress-bar" style="width: ${percentage}%"></div>
                        <span class="protocol-count">${count} (${percentage}%)</span>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    updateRecentEvents(events) {
        const container = document.getElementById('recent-events-list');
        if (!container) return;
        
        container.innerHTML = events.slice(0, 10).map(event => {
            const timestamp = new Date(event.timestamp * 1000).toLocaleTimeString();
            const eventIcon = this.getEventIcon(event.event);
            
            return `
                <div class="event-item">
                    <span class="event-time">${timestamp}</span>
                    <span class="event-icon">${eventIcon}</span>
                    <span class="event-description">${this.formatEventDescription(event)}</span>
                </div>
            `;
        }).join('');
    }
    
    getEventIcon(eventType) {
        const icons = {
            'peer_discovered': '🔍',
            'peer_connected': '🔗',
            'peer_disconnected': '🔌',
            'peer_removed': '🗑️',
            'content_discovered': '📄'
        };
        return icons[eventType] || '📡';
    }
    
    formatEventDescription(event) {
        const peerId = this.truncateText(event.peer_id || 'Unknown', 12);
        
        switch (event.event) {
            case 'peer_discovered':
                return `Discovered peer ${peerId} with protocols: ${(event.protocols || []).join(', ')}`;
            case 'peer_connected':
                return `Connected to peer ${peerId}`;
            case 'peer_disconnected':
                return `Disconnected from peer ${peerId}`;
            case 'peer_removed':
                return `Removed stale peer ${peerId}`;
            case 'content_discovered':
                return `Found content on peer ${peerId}`;
            default:
                return `${event.event} for peer ${peerId}`;
        }
    }
    
    updateDiscoveryControls() {
        const startBtn = document.getElementById('start-discovery-btn');
        const stopBtn = document.getElementById('stop-discovery-btn');
        
        if (startBtn && stopBtn) {
            if (this.discoveryActive) {
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-block';
            } else {
                startBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
            }
        }
    }
    
    updatePagination() {
        const container = document.getElementById('pagination-container');
        if (!container) return;
        
        const currentPage = Math.floor(this.pagination.offset / this.pagination.limit) + 1;
        const totalPages = Math.ceil(this.pagination.total / this.pagination.limit);
        
        container.innerHTML = `
            <div class="pagination">
                <button class="btn btn-sm pagination-prev" ${this.pagination.offset === 0 ? 'disabled' : ''}>
                    Previous
                </button>
                <span class="pagination-info">
                    Page ${currentPage} of ${totalPages} (${this.pagination.total} total peers)
                </span>
                <button class="btn btn-sm pagination-next" ${this.pagination.offset + this.pagination.limit >= this.pagination.total ? 'disabled' : ''}>
                    Next
                </button>
            </div>
        `;
    }
    
    async connectToPeer(peerId) {
        try {
            const response = await fetch(`/api/peers/${peerId}/connect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('success', `Connected to peer ${this.truncateText(peerId, 12)}`);
                this.refreshPeersList();
            } else {
                this.showNotification('error', `Failed to connect: ${result.error}`);
            }
        } catch (error) {
            this.showNotification('error', 'Connection failed');
            console.error('Connect error:', error);
        }
    }
    
    async disconnectFromPeer(peerId) {
        try {
            const response = await fetch(`/api/peers/${peerId}/disconnect`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('success', `Disconnected from peer ${this.truncateText(peerId, 12)}`);
                this.refreshPeersList();
            } else {
                this.showNotification('error', `Failed to disconnect: ${result.error}`);
            }
        } catch (error) {
            this.showNotification('error', 'Disconnection failed');
            console.error('Disconnect error:', error);
        }
    }
    
    async showPeerDetails(peerId) {
        try {
            const response = await fetch(`/api/peers/${peerId}`);
            const result = await response.json();
            
            if (result.success) {
                this.displayPeerDetails(result.data);
                this.currentView = 'details';
                this.selectedPeer = peerId;
            } else {
                this.showNotification('error', 'Failed to load peer details');
            }
        } catch (error) {
            this.showNotification('error', 'Failed to load peer details');
            console.error('Peer details error:', error);
        }
    }
    
    displayPeerDetails(peerData) {
        const container = document.getElementById('peer-details-container');
        if (!container) return;
        
        const peer = peerData.peer;
        const metadata = peerData.metadata || {};
        const content = peerData.shared_content || { pins: [], files: [] };
        
        container.innerHTML = `
            <div class="peer-details-view">
                <div class="peer-details-header">
                    <h3>Peer Details</h3>
                    <button class="btn btn-secondary back-to-list-btn" onclick="peerManager.backToList()">← Back to List</button>
                </div>
                
                <div class="peer-info-detailed">
                    <div class="info-section">
                        <h4>Basic Information</h4>
                        <table class="table">
                            <tr><td><strong>Peer ID:</strong></td><td><code>${peer.peer_id || peer.id}</code></td></tr>
                            <tr><td><strong>Status:</strong></td><td><span class="status-badge ${peer.connected ? 'connected' : 'disconnected'}">${peer.connected ? 'Connected' : 'Disconnected'}</span></td></tr>
                            <tr><td><strong>Agent Version:</strong></td><td>${peer.agent_version || 'Unknown'}</td></tr>
                            <tr><td><strong>Protocol Version:</strong></td><td>${peer.protocol_version || 'Unknown'}</td></tr>
                            <tr><td><strong>Last Seen:</strong></td><td>${peer.last_seen ? new Date(peer.last_seen * 1000).toLocaleString() : 'Unknown'}</td></tr>
                            ${peer.latency_ms ? `<tr><td><strong>Latency:</strong></td><td>${peer.latency_ms}ms</td></tr>` : ''}
                        </table>
                    </div>
                    
                    ${peer.multiaddrs && peer.multiaddrs.length > 0 ? `
                        <div class="info-section">
                            <h4>Addresses</h4>
                            <ul class="address-list">
                                ${peer.multiaddrs.map(addr => `<li><code>${addr}</code></li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    
                    ${peer.protocols && peer.protocols.length > 0 ? `
                        <div class="info-section">
                            <h4>Supported Protocols</h4>
                            <div class="protocol-tags">
                                ${peer.protocols.map(protocol => `<span class="badge badge-protocol">${protocol}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    ${content.pins.length > 0 || content.files.length > 0 ? `
                        <div class="info-section">
                            <h4>Shared Content</h4>
                            <div class="content-tabs">
                                <button class="tab-btn active" onclick="peerManager.switchContentTab('pins')">Pins (${content.pins.length})</button>
                                <button class="tab-btn" onclick="peerManager.switchContentTab('files')">Files (${content.files.length})</button>
                            </div>
                            <div class="content-display" id="peer-content-display">
                                ${this.renderPeerContent(content, 'pins')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        // Show details view
        document.getElementById('peers-list-view').style.display = 'none';
        document.getElementById('peer-details-view').style.display = 'block';
    }
    
    renderPeerContent(content, type) {
        if (type === 'pins') {
            return content.pins.map(pin => `
                <div class="content-item">
                    <code class="content-hash">${pin.cid || pin}</code>
                    ${pin.name ? `<span class="content-name">${pin.name}</span>` : ''}
                    ${pin.size ? `<span class="content-size">${this.formatFileSize(pin.size)}</span>` : ''}
                </div>
            `).join('');
        } else {
            return content.files.map(file => `
                <div class="content-item">
                    <span class="file-icon">${file.type === 'directory' ? '📁' : '📄'}</span>
                    <span class="content-name">${file.name}</span>
                    ${file.hash ? `<code class="content-hash">${file.hash}</code>` : ''}
                    ${file.size ? `<span class="content-size">${this.formatFileSize(file.size)}</span>` : ''}
                </div>
            `).join('');
        }
    }
    
    switchContentTab(type) {
        const tabs = document.querySelectorAll('.content-tabs .tab-btn');
        tabs.forEach(tab => tab.classList.remove('active'));
        event.target.classList.add('active');
        
        if (this.selectedPeer) {
            // Re-render content display for the selected type
            // This would typically refetch the data
            console.log(`Switching to ${type} content for peer ${this.selectedPeer}`);
        }
    }
    
    backToList() {
        document.getElementById('peers-list-view').style.display = 'block';
        document.getElementById('peer-details-view').style.display = 'none';
        this.currentView = 'list';
        this.selectedPeer = null;
    }
    
    async startDiscovery() {
        try {
            const response = await fetch('/api/peers/discovery/start', { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('success', 'Peer discovery started');
                this.discoveryActive = true;
                this.updateDiscoveryControls();
            } else {
                this.showNotification('error', 'Failed to start discovery');
            }
        } catch (error) {
            this.showNotification('error', 'Failed to start discovery');
            console.error('Start discovery error:', error);
        }
    }
    
    async stopDiscovery() {
        try {
            const response = await fetch('/api/peers/discovery/stop', { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('success', 'Peer discovery stopped');
                this.discoveryActive = false;
                this.updateDiscoveryControls();
            } else {
                this.showNotification('error', 'Failed to stop discovery');
            }
        } catch (error) {
            this.showNotification('error', 'Failed to stop discovery');
            console.error('Stop discovery error:', error);
        }
    }
    
    // Utility methods
    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
    
    showNotification(type, message) {
        // Create a simple notification (you can enhance this)
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    updateFilterButtons() {
        // Update visual state of filter buttons
        document.querySelectorAll('.filter-protocol').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.protocol === this.filters.protocol);
        });
        
        document.querySelectorAll('.filter-connection').forEach(btn => {
            const btnValue = btn.dataset.connected === 'true' ? true : 
                           btn.dataset.connected === 'false' ? false : null;
            btn.classList.toggle('active', btnValue === this.filters.connected);
        });
    }
}

// Initialize peer manager when the peers tab is shown
let peerManager = null;

function initializePeerManager() {
    if (!peerManager) {
        peerManager = new PeerManager();
        console.log('Peer manager initialized');
    }
    
    // Refresh data when tab becomes active
    peerManager.refreshSummary();
    peerManager.refreshPeersList();
}

// Cleanup when leaving the tab
function cleanupPeerManager() {
    if (peerManager) {
        peerManager.stopAutoRefresh();
    }
}
