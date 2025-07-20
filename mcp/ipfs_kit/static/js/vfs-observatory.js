/**
 * VFS Observatory Tab Functionality
 */

async function loadVFSTab() {
    console.log('Loading VFS Observatory tab...');
    try {
        // Load VFS health data
        const healthResponse = await dashboardAPI.getVFSHealth();
        const healthData = healthResponse.success ? healthResponse : null;
        
        // Load VFS statistics
        const statsResponse = await dashboardAPI.getVFSStatistics();
        const statsData = statsResponse.success ? statsResponse : null;
        
        // Load recommendations
        const recommendationsResponse = await dashboardAPI.getVFSRecommendations();
        const recommendationsData = recommendationsResponse.success ? recommendationsResponse : null;

        // Update VFS health overview
        updateVFSHealth(healthData);
        
        // Update cache performance with comprehensive data
        const cacheElement = document.getElementById('cachePerformance');
        if (cacheElement && healthData?.detailed_metrics?.cache_performance) {
            cacheElement.innerHTML = formatComprehensiveCacheDetails(healthData.detailed_metrics.cache_performance);
        }
        
        // Update filesystem status with comprehensive metrics
        const fsElement = document.getElementById('filesystemStatus');
        if (fsElement && healthData?.detailed_metrics?.filesystem_metrics) {
            fsElement.innerHTML = formatComprehensiveFilesystemMetrics(healthData.detailed_metrics.filesystem_metrics);
        }
        
        // Update access patterns with comprehensive data
        const accessElement = document.getElementById('accessPatterns');
        if (accessElement && healthData?.detailed_metrics?.access_patterns) {
            accessElement.innerHTML = formatComprehensiveAccessPatterns(healthData.detailed_metrics.access_patterns);
        }
        
        // Update resource utilization
        const resourceElement = document.getElementById('resourceUtilization');
        if (resourceElement && healthData?.detailed_metrics?.resource_utilization) {
            resourceElement.innerHTML = formatResourceUtilization(healthData.detailed_metrics.resource_utilization);
        }
        
        // Update VFS recommendations
        const recommendationsElement = document.getElementById('vfsRecommendations');
        if (recommendationsElement && recommendationsData) {
            recommendationsElement.innerHTML = formatVFSRecommendations(recommendationsData);
        }
        
    } catch (error) {
        console.error('Error loading VFS Observatory data:', error);
        const cacheElement = document.getElementById('cachePerformance');
        if (cacheElement) {
            cacheElement.innerHTML = '<div style="color: red; padding: 20px;">Error loading VFS Observatory data</div>';
        }
    }
}

function updateVFSHealth(healthData) {
    if (!healthData?.success) return;
    
    const healthElement = document.getElementById('vfsHealthOverview');
    if (!healthElement) return;
    
    healthElement.innerHTML = `
        <div class="stat-card">
            <h3>🏥 VFS Health Overview</h3>
            <div class="metric">
                <span class="metric-label">Overall Health Score</span>
                <span class="metric-value">${Math.round((healthData.overall_health_score || 0) * 100)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Cache Performance</span>
                <span class="metric-value">${Math.round((healthData.health_factors?.cache_performance || 0) * 100)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Index Health</span>
                <span class="metric-value">${Math.round((healthData.health_factors?.index_health || 0) * 100)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Resource Health</span>
                <span class="metric-value">${Math.round((healthData.health_factors?.resource_health || 0) * 100)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Filesystem Health</span>
                <span class="metric-value">${Math.round((healthData.health_factors?.filesystem_health || 0) * 100)}%</span>
            </div>
            ${healthData.alerts && healthData.alerts.length > 0 ? `
                <div class="metric">
                    <span class="metric-label">Active Alerts</span>
                    <span class="metric-value">${healthData.alerts.length}</span>
                </div>
            ` : ''}
        </div>
    `;
}

function formatComprehensiveCacheDetails(cacheData) {
    if (!cacheData) return 'Cache performance data not available';
    
    return `
        <div class="stat-card">
            <h4>🚀 Tiered Cache Performance</h4>
            <div class="metric">
                <span class="metric-label">Memory Tier Hit Rate</span>
                <span class="metric-value">${Math.round((cacheData.tiered_cache?.memory_tier?.hit_rate || 0) * 100)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Memory Tier Size</span>
                <span class="metric-value">${cacheData.tiered_cache?.memory_tier?.size_mb || 0}MB (${cacheData.tiered_cache?.memory_tier?.items || 0} items)</span>
            </div>
            <div class="metric">
                <span class="metric-label">Disk Tier Hit Rate</span>
                <span class="metric-value">${Math.round((cacheData.tiered_cache?.disk_tier?.hit_rate || 0) * 100)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Disk Tier Size</span>
                <span class="metric-value">${cacheData.tiered_cache?.disk_tier?.size_gb || 0}GB (${cacheData.tiered_cache?.disk_tier?.items || 0} items)</span>
            </div>
        </div>
        <div class="stat-card">
            <h4>🧠 Semantic Cache</h4>
            <div class="metric">
                <span class="metric-label">Similarity Threshold</span>
                <span class="metric-value">${cacheData.semantic_cache?.similarity_threshold || 'N/A'}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Cache Utilization</span>
                <span class="metric-value">${Math.round((cacheData.semantic_cache?.cache_utilization || 0) * 100)}%</span>
            </div>
        </div>
    `;
}

function formatComprehensiveFilesystemMetrics(fsData) {
    if (!fsData) return 'Filesystem metrics not available';
    
    return `
        <div class="stat-card">
            <h4>💽 Filesystem Status</h4>
            <div class="metric">
                <span class="metric-label">Total Space</span>
                <span class="metric-value">${formatBytes(fsData.storage?.total_space || 0)}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Used Space</span>
                <span class="metric-value">${formatBytes(fsData.storage?.used_space || 0)}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Available Space</span>
                <span class="metric-value">${formatBytes(fsData.storage?.available_space || 0)}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Usage</span>
                <span class="metric-value">${Math.round((fsData.storage?.usage_percent || 0) * 100)}%</span>
            </div>
        </div>
    `;
}

function formatComprehensiveAccessPatterns(accessData) {
    if (!accessData) return 'Access patterns not available';
    
    return `
        <div class="stat-card">
            <h4>📈 Access Patterns</h4>
            <div class="metric">
                <span class="metric-label">Read Operations</span>
                <span class="metric-value">${accessData.operations?.reads || 0}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Write Operations</span>
                <span class="metric-value">${accessData.operations?.writes || 0}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Average Response Time</span>
                <span class="metric-value">${Math.round(accessData.performance?.avg_response_time || 0)}ms</span>
            </div>
        </div>
    `;
}

function formatResourceUtilization(resourceData) {
    if (!resourceData) return 'Resource utilization not available';
    
    return `
        <div class="stat-card">
            <h4>⚡ Resource Utilization</h4>
            <div class="metric">
                <span class="metric-label">CPU Usage</span>
                <span class="metric-value">${Math.round(resourceData.cpu_percent || 0)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Memory Usage</span>
                <span class="metric-value">${Math.round(resourceData.memory_percent || 0)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">I/O Operations</span>
                <span class="metric-value">${resourceData.io_operations || 0}</span>
            </div>
        </div>
    `;
}

function formatVFSRecommendations(recommendationsData) {
    if (!recommendationsData?.recommendations) return 'No recommendations available';
    
    const recommendations = recommendationsData.recommendations;
    const recommendationHTML = recommendations.map(rec => `
        <div class="recommendation-item ${rec.priority || 'low'}">
            <div class="recommendation-title">${rec.title || 'Recommendation'}</div>
            <div class="recommendation-description">${rec.description || ''}</div>
            ${rec.action ? `<div class="recommendation-action">${rec.action}</div>` : ''}
        </div>
    `).join('');
    
    return `
        <div class="vfs-section">
            <h4>💡 VFS Recommendations</h4>
            ${recommendationHTML || '<div>No specific recommendations at this time.</div>'}
        </div>
    `;
}

// Expose functions globally for HTML compatibility
window.loadVFSTab = loadVFSTab;
