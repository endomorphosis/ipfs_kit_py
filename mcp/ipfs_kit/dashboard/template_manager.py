"""
Dashboard template manager for generating HTML templates.
"""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DashboardTemplateManager:
    """Manages dashboard HTML templates."""
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.templates_dir.mkdir(exist_ok=True)
        
    def create_dashboard_template(self) -> str:
        """Create the main dashboard template with comprehensive features."""
        
        template_path = self.templates_dir / "dashboard.html"
        
        template_content = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced IPFS Kit Backend Observatory</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px; background: #f5f5f5; line-height: 1.6;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;
        }
        .tabs { 
            background: white; border-radius: 8px; margin-bottom: 20px; overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .tab-buttons {
            display: flex; background: #f8f9fa; border-bottom: 1px solid #ddd;
        }
        .tab-button {
            flex: 1; padding: 15px; background: none; border: none; cursor: pointer;
            font-size: 14px; font-weight: 600; transition: all 0.3s;
        }
        .tab-button.active { background: white; color: #007bff; border-bottom: 2px solid #007bff; }
        .tab-button:hover { background: #e9ecef; }
        .tab-content { padding: 20px; display: none; }
        .tab-content.active { display: block; }
        .stats-grid { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px; margin-bottom: 20px;
        }
        .stat-card { 
            background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .backend-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px; margin-bottom: 20px;
        }
        .backend-card {
            background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-left: 4px solid #ddd; position: relative;
        }
        .backend-card.healthy { border-left-color: #4CAF50; }
        .backend-card.unhealthy { border-left-color: #f44336; }
        .backend-card.partial { border-left-color: #FF9800; }
        .backend-card.unknown { border-left-color: #9E9E9E; }
        .backend-header {
            display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;
        }
        .backend-actions {
            display: flex; gap: 10px;
        }
        .action-btn {
            padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer;
            font-size: 12px; font-weight: 500;
        }
        .action-btn.config { background: #17a2b8; color: white; }
        .action-btn.restart { background: #28a745; color: white; }
        .action-btn.logs { background: #6c757d; color: white; }
        .action-btn:hover { opacity: 0.8; }
        .status-badge {
            display: inline-block; padding: 4px 8px; border-radius: 4px;
            font-size: 12px; font-weight: bold; text-transform: uppercase; margin-right: 5px;
        }
        .status-healthy { background: #4CAF50; color: white; }
        .status-unhealthy { background: #f44336; color: white; }
        .status-partial { background: #FF9800; color: white; }
        .status-unknown { background: #9E9E9E; color: white; }
        
        .config-section {
            margin: 20px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        
        .config-section h4 {
            color: #495057;
            margin-bottom: 15px;
            border-bottom: 2px solid #007bff;
            padding-bottom: 5px;
        }
        
        .package-config-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .config-card {
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .config-card h5 {
            color: #007bff;
            margin-bottom: 15px;
            font-size: 1.1em;
        }
        
        .config-form {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .config-form label {
            font-weight: 500;
            color: #495057;
            margin-bottom: 5px;
        }
        
        .config-form input,
        .config-form select {
            padding: 8px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            font-size: 14px;
        }
        
        .config-form input:focus,
        .config-form select:focus {
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
        }
        
        .config-form input[type="checkbox"] {
            width: auto;
            margin-right: 5px;
        }
        
        .config-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background-color: #007bff;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #0056b3;
        }
        
        .btn-secondary {
            background-color: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #545b62;
        }
        
        .btn-success {
            background-color: #28a745;
            color: white;
        }
        
        .btn-success:hover {
            background-color: #218838;
        }
        .verbose-metrics {
            background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 15px 0;
            border: 1px solid #e9ecef;
        }
        .metrics-section {
            margin-bottom: 20px;
        }
        .metrics-section h4 {
            margin: 0 0 10px 0; color: #495057; font-size: 14px; font-weight: 600;
        }
        .metrics-table { 
            width: 100%; border-collapse: collapse; font-size: 13px;
        }
        .metrics-table th, .metrics-table td { 
            padding: 6px 8px; text-align: left; border-bottom: 1px solid #e9ecef;
        }
        .metrics-table th { background: #f8f9fa; font-weight: 600; }
        .metrics-table td.value {
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            background: #fff; color: #495057;
        }
        .refresh-btn {
            background: #007bff; color: white; border: none; padding: 10px 20px;
            border-radius: 4px; cursor: pointer; font-size: 14px; margin-right: 10px;
        }
        .refresh-btn:hover { background: #0056b3; }
        .auto-refresh { margin-left: 20px; }
        .error-log {
            background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px;
            border-radius: 4px; margin-top: 10px; max-height: 200px; overflow-y: auto;
            font-size: 12px;
        }
        .insights-card {
            background: #e8f5e8; border: 1px solid #c3e6c3; padding: 15px;
            border-radius: 8px; margin-top: 20px;
        }
        .modal {
            display: none; position: fixed; z-index: 1000; left: 0; top: 0;
            width: 100%; height: 100%; background: rgba(0,0,0,0.5);
        }
        .modal-content {
            background: white; margin: 5% auto; padding: 20px; width: 80%;
            max-width: 600px; border-radius: 8px; max-height: 80vh; overflow-y: auto;
        }
        .modal-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #e9ecef;
        }
        .close { 
            font-size: 28px; font-weight: bold; cursor: pointer; color: #aaa;
        }
        .close:hover { color: #000; }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block; margin-bottom: 5px; font-weight: 600; color: #495057;
        }
        .form-group input, .form-group textarea, .form-group select {
            width: 100%; padding: 8px 12px; border: 1px solid #ced4da;
            border-radius: 4px; font-size: 14px;
        }
        .form-group textarea {
            height: 80px; resize: vertical; font-family: monospace;
        }
        .form-row {
            display: grid; grid-template-columns: 1fr 1fr; gap: 15px;
        }
        .btn {
            padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;
            font-size: 14px; font-weight: 500; margin-right: 10px;
        }
        .btn-primary { background: #007bff; color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        .btn:hover { opacity: 0.8; }
        .connection-status {
            display: flex; align-items: center; gap: 10px; margin-bottom: 15px;
            padding: 10px; background: #f8f9fa; border-radius: 4px;
        }
        .connection-indicator {
            width: 12px; height: 12px; border-radius: 50%; background: #dc3545;
        }
        .connection-indicator.connected { background: #28a745; }
        .progress-bar {
            width: 100%; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;
            margin: 10px 0;
        }
        .progress-fill {
            height: 100%; background: #007bff; border-radius: 4px; transition: width 0.3s;
        }
        .expandable {
            border: 1px solid #e9ecef; border-radius: 4px; margin-bottom: 10px;
        }
        .expandable-header {
            padding: 10px 15px; background: #f8f9fa; cursor: pointer; display: flex;
            justify-content: space-between; align-items: center; font-weight: 600;
        }
        .expandable-content {
            padding: 15px; display: none;
        }
        .expandable.expanded .expandable-content { display: block; }
        .expandable.expanded .expandable-header::after { content: '▼'; }
        .expandable-header::after { content: '▶'; }
        .log-viewer {
            background: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 4px;
            font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto;
            white-space: pre-wrap;
        }
        
        /* Enhanced File Manager Styles with Drag & Drop */
        .file-manager-container {
            display: flex;
            gap: 20px;
            height: 700px;
        }
        
        .file-manager-sidebar {
            width: 280px;
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow-y: auto;
        }
        
        .file-manager-main {
            flex: 1;
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
            position: relative;
            display: flex;
            flex-direction: column;
        }
        
        /* Drag & Drop Styles */
        .drop-zone {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 123, 255, 0.1);
            border: 3px dashed #007bff;
            border-radius: 8px;
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 10;
            font-size: 18px;
            color: #007bff;
            font-weight: 600;
        }
        
        .drop-zone.active {
            display: flex;
        }
        
        .drop-zone.highlight {
            background: rgba(0, 123, 255, 0.2);
            border-color: #0056b3;
            transform: scale(1.02);
        }
        
        .dragging {
            opacity: 0.5;
            transform: scale(0.95);
            transition: all 0.2s;
        }
        
        .drag-ghost {
            background: #f8f9fa;
            border: 2px dashed #dee2e6;
            border-radius: 4px;
            opacity: 0.7;
        }
        
        .file-item.drag-over {
            background: #e3f2fd;
            border: 2px solid #2196f3;
        }
        
        /* File Upload Progress */
        .upload-progress {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            padding: 15px;
            min-width: 300px;
            z-index: 1000;
            transform: translateX(100%);
            transition: transform 0.3s;
        }
        
        .upload-progress.visible {
            transform: translateX(0);
        }
        
        .upload-item {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            padding: 8px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        
        .upload-item:last-child {
            margin-bottom: 0;
        }
        
        .upload-item .file-name {
            flex: 1;
            font-size: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .upload-item .progress-bar {
            width: 60px;
            height: 4px;
            background: #e9ecef;
            border-radius: 2px;
            overflow: hidden;
        }
        
        .upload-item .progress-fill {
            height: 100%;
            background: #28a745;
            transition: width 0.3s;
        }
        
        .upload-item .status {
            font-size: 10px;
            color: #6c757d;
        }
        
        /* Context Menu */
        .context-menu {
            position: fixed;
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            padding: 5px 0;
            min-width: 150px;
            z-index: 1000;
            display: none;
        }
        
        .context-menu-item {
            padding: 8px 15px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .context-menu-item:hover {
            background: #f8f9fa;
        }
        
        .context-menu-item.danger:hover {
            background: #f8d7da;
            color: #721c24;
        }
        
        .context-menu-separator {
            border-top: 1px solid #dee2e6;
            margin: 5px 0;
        }
        
        /* Enhanced File Viewer */
        .file-viewer {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.9);
            z-index: 2000;
            display: none;
            align-items: center;
            justify-content: center;
        }
        
        .file-viewer.visible {
            display: flex;
        }
        
        .file-viewer-content {
            background: white;
            border-radius: 8px;
            max-width: 90%;
            max-height: 90%;
            overflow: auto;
            position: relative;
        }
        
        .file-viewer-header {
            padding: 15px;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .file-viewer-close {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #6c757d;
        }
        
        .file-viewer-body {
            padding: 20px;
            max-height: 70vh;
            overflow: auto;
        }
        
        /* Real-time Updates */
        .real-time-indicator {
            position: absolute;
            top: 10px;
            right: 10px;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #28a745;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .disconnected .real-time-indicator {
            background: #dc3545;
            animation: none;
        }
        
        .search-container {
            margin-left: auto;
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .search-container input {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 200px;
        }
        
        .quick-access {
            margin-bottom: 20px;
        }
        
        .quick-access-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            cursor: pointer;
            border-radius: 4px;
            transition: background-color 0.2s;
        }
        
        .quick-access-item:hover {
            background-color: #f8f9fa;
        }
        
        .quick-access-item .icon {
            font-size: 16px;
            width: 20px;
        }
        
        .file-stats {
            border-top: 1px solid #eee;
            padding-top: 15px;
        }
        
        .stat-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 14px;
        }
        
        .stat-item .label {
            color: #666;
        }
        
        .stat-item .value {
            font-weight: 600;
        }
        
        .breadcrumb {
            display: flex;
            align-items: center;
            gap: 5px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        
        .breadcrumb-item {
            cursor: pointer;
            padding: 5px 10px;
            border-radius: 4px;
            transition: background-color 0.2s;
        }
        
        .breadcrumb-item:hover {
            background-color: #f8f9fa;
        }
        
        .file-list-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }
        
        .file-list-controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .btn-sm {
            padding: 5px 10px;
            font-size: 12px;
        }
        
        .btn-sm.active {
            background-color: #007bff;
            color: white;
        }
        
        .file-list {
            max-height: 400px;
            overflow-y: auto;
            flex-grow: 1;
        }
        
        .file-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s;
            border-bottom: 1px solid #f8f9fa;
        }
        
        .file-item:hover {
            background-color: #f8f9fa;
        }
        
        .file-item.selected {
            background-color: #e3f2fd;
        }
        
        .file-icon {
            font-size: 18px;
            width: 20px;
            text-align: center;
        }
        
        .file-info {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        
        .file-name {
            font-weight: 600;
            color: #333;
        }
        
        .file-meta {
            font-size: 12px;
            color: #666;
        }
        
        .file-actions {
            display: flex;
            gap: 5px;
            opacity: 0;
            transition: opacity 0.2s;
        }
        
        .file-item:hover .file-actions {
            opacity: 1;
        }
        
        .file-action-btn {
            padding: 2px 6px;
            background: #6c757d;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 10px;
        }
        
        .file-action-btn:hover {
            background: #545b62;
        }
        
        .file-action-btn.delete {
            background: #dc3545;
        }
        
        .file-action-btn.delete:hover {
            background: #c82333;
        }
        
        .grid-view .file-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
        }
        
        .grid-view .file-item {
            flex-direction: column;
            text-align: center;
            padding: 15px;
            border: 1px solid #eee;
            border-radius: 8px;
        }
        
        .grid-view .file-icon {
            font-size: 32px;
            margin-bottom: 10px;
        }
        
        .grid-view .file-info {
            align-items: center;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .empty-state .icon {
            font-size: 48px;
            margin-bottom: 10px;
        }
        
        /* Modal styles for file operations */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        
        .modal-content {
            background-color: white;
            margin: 15% auto;
            padding: 20px;
            border-radius: 8px;
            width: 80%;
            max-width: 500px;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .modal-title {
            font-size: 18px;
            font-weight: 600;
        }
        
        .modal-close {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #666;
        }
        
        .modal-close:hover {
            color: #333;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
        }
        
        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        
        .form-group textarea {
            height: 100px;
            resize: vertical;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔭 Enhanced IPFS Kit Backend Observatory</h1>
            <p>Comprehensive monitoring, observability and configuration for all filesystem backends</p>
        </div>
        
        <div class="tabs">
            <div class="tab-buttons">
                <button class="tab-button active" onclick="switchTab('overview', event)">📊 Overview</button>
                <button class="tab-button" onclick="switchTab('monitoring', event)">🔍 Monitoring</button>
                <button class="tab-button" onclick="switchTab('vfs', event)">💾 VFS Observatory</button>
                <button class="tab-button" onclick="switchTab('vector-kb', event)">🧠 Vector & KB</button>
                <button class="tab-button" onclick="switchTab('configuration', event)">⚙️ Configuration</button>
                <button class="tab-button" onclick="switchTab('filemanager', event)">📁 File Manager</button>
                <button class="tab-button" onclick="switchTab('logs', event)">📋 Logs</button>
            </div>
            
            <div id="overview" class="tab-content active">
                <div class="controls">
                    <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
                    <button class="refresh-btn" onclick="getInsights()">💡 Get Insights</button>
                    <button class="refresh-btn" onclick="exportConfig()">📤 Export Config</button>
                    <label class="auto-refresh">
                        <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()">
                        Auto-refresh (30s)
                    </label>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>System Status</h3>
                        <div id="systemStatus">Loading...</div>
                    </div>
                    <div class="stat-card">
                        <h3>Backend Summary</h3>
                        <div id="backendSummary">Loading...</div>
                    </div>
                    <div class="stat-card">
                        <h3>Performance</h3>
                        <div id="performanceMetrics">Loading...</div>
                    </div>
                </div>
                
                <div class="insights-card" id="insightsCard" style="display: none;">
                    <h3>🧠 Development Insights</h3>
                    <div id="insightsContent"></div>
                </div>
            </div>
            
            <div id="monitoring" class="tab-content">
                <div class="backend-grid" id="backendGrid">
                    <!-- Backend cards will be populated here -->
                </div>
            </div>
            
            <div id="vfs" class="tab-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>🧬 Cache Performance</h3>
                        <div id="cachePerformance">Loading cache metrics...</div>
                    </div>
                    <div class="stat-card">
                        <h3>🗂️ Filesystem Status</h3>
                        <div id="filesystemStatus">Loading filesystem metrics...</div>
                    </div>
                    <div class="stat-card">
                        <h3>📈 Access Patterns</h3>
                        <div id="accessPatterns">Loading access patterns...</div>
                    </div>
                    <div class="stat-card">
                        <h3>💻 Resource Usage</h3>
                        <div id="resourceUsage">Loading resource metrics...</div>
                    </div>
                </div>
                
                <div class="expandable">
                    <div class="expandable-header">Tiered Cache Details</div>
                    <div class="expandable-content">
                        <div id="tieredCacheDetails">Loading detailed cache information...</div>
                    </div>
                </div>
                
                <div class="expandable">
                    <div class="expandable-header">Hot Content Analysis</div>
                    <div class="expandable-content">
                        <div id="hotContentAnalysis">Loading hot content analysis...</div>
                    </div>
                </div>
            </div>
            
            <div id="vector-kb" class="tab-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>🔍 Vector Index Status</h3>
                        <div id="vectorIndexStatus">Loading vector index metrics...</div>
                    </div>
                    <div class="stat-card">
                        <h3>🕸️ Knowledge Graph</h3>
                        <div id="knowledgeGraphStatus">Loading knowledge graph metrics...</div>
                    </div>
                    <div class="stat-card">
                        <h3>🎯 Search Performance</h3>
                        <div id="searchPerformance">Loading search performance...</div>
                    </div>
                    <div class="stat-card">
                        <h3>📊 Content Distribution</h3>
                        <div id="contentDistribution">Loading content distribution...</div>
                    </div>
                </div>
                
                <div class="expandable">
                    <div class="expandable-header">Vector Index Details</div>
                    <div class="expandable-content">
                        <div id="vectorIndexDetails">Loading vector index details...</div>
                    </div>
                </div>
                
                <div class="expandable">
                    <div class="expandable-header">Knowledge Base Analytics</div>
                    <div class="expandable-content">
                        <div id="knowledgeBaseAnalytics">Loading knowledge base analytics...</div>
                    </div>
                </div>
                
                <div class="expandable">
                    <div class="expandable-header">Semantic Cache Performance</div>
                    <div class="expandable-content">
                        <div id="semanticCachePerformance">Loading semantic cache performance...</div>
                    </div>
                </div>
            </div>
            
            <div id="configuration" class="tab-content">
                <div id="configurationContent">
                    <h3>🔧 Configuration Management</h3>
                    
                    <!-- Package Configuration Section -->
                    <div class="config-section">
                        <h4>📦 Package Configuration</h4>
                        <div class="package-config-grid">
                            <div class="config-card">
                                <h5>System Settings</h5>
                                <div class="config-form">
                                    <label>Log Level:</label>
                                    <select id="system-log-level">
                                        <option value="DEBUG">DEBUG</option>
                                        <option value="INFO">INFO</option>
                                        <option value="WARNING">WARNING</option>
                                        <option value="ERROR">ERROR</option>
                                    </select>
                                    
                                    <label>Max Workers:</label>
                                    <input type="number" id="system-max-workers" min="1" max="16" value="4">
                                    
                                    <label>Cache Size:</label>
                                    <input type="text" id="system-cache-size" value="1000" placeholder="e.g., 1000, 10MB">
                                    
                                    <label>Data Directory:</label>
                                    <input type="text" id="system-data-dir" value="/tmp/ipfs_kit" placeholder="/path/to/data">
                                </div>
                            </div>
                            
                            <div class="config-card">
                                <h5>VFS Settings</h5>
                                <div class="config-form">
                                    <label>Cache Enabled:</label>
                                    <input type="checkbox" id="vfs-cache-enabled" checked>
                                    
                                    <label>Cache Max Size:</label>
                                    <input type="text" id="vfs-cache-max-size" value="10GB" placeholder="e.g., 10GB, 1000MB">
                                    
                                    <label>Vector Dimensions:</label>
                                    <input type="number" id="vfs-vector-dimensions" value="384" min="1" max="2048">
                                    
                                    <label>Knowledge Base Max Nodes:</label>
                                    <input type="number" id="vfs-kb-max-nodes" value="10000" min="100" max="1000000">
                                </div>
                            </div>
                            
                            <div class="config-card">
                                <h5>Observability Settings</h5>
                                <div class="config-form">
                                    <label>Metrics Enabled:</label>
                                    <input type="checkbox" id="obs-metrics-enabled" checked>
                                    
                                    <label>Prometheus Port:</label>
                                    <input type="number" id="obs-prometheus-port" value="9090" min="1000" max="65535">
                                    
                                    <label>Dashboard Enabled:</label>
                                    <input type="checkbox" id="obs-dashboard-enabled" checked>
                                    
                                    <label>Health Check Interval (seconds):</label>
                                    <input type="number" id="obs-health-check-interval" value="30" min="5" max="300">
                                </div>
                            </div>
                        </div>
                        
                        <div class="config-actions">
                            <button onclick="loadPackageConfig()" class="btn btn-secondary">🔄 Load Current Config</button>
                            <button onclick="savePackageConfig()" class="btn btn-primary">💾 Save Package Config</button>
                        </div>
                    </div>
                    
                    <!-- Backend Configuration Section -->
                    <div class="config-section">
                        <h4>🔌 Backend Configuration</h4>
                        <p>Select a backend to configure its settings:</p>
                        <div id="configBackendList"></div>
                    </div>
                </div>
            </div>
            
            <div id="filemanager" class="tab-content">
                <div class="file-manager-container">
                    <div class="file-manager-sidebar">
                        <h4>🗂️ Quick Access</h4>
                        <div class="quick-access">
                            <div class="quick-access-item" onclick="fileManager.navigateTo('/')">
                                <span class="icon">🏠</span>
                                <span>Root</span>
                            </div>
                        </div>
                        
                        <h4>📊 File Statistics</h4>
                        <div class="file-stats" id="fileManagerStats">
                            <div class="loading">Loading stats...</div>
                        </div>
                    </div>
                    
                    <div class="file-manager-main">
                        <div class="file-list-header">
                            <div class="breadcrumb" id="fileManagerBreadcrumb"></div>
                            <div class="file-list-controls">
                                <button class="btn btn-sm" onclick="fileManager.showCreateFolderModal()">📁 New Folder</button>
                                <button class="btn btn-sm" onclick="fileManager.triggerUpload()">📤 Upload</button>
                                <input type="file" id="fileInput" multiple style="display:none;" onchange="uploadSelectedFile()">
                                <input type="text" id="fileSearch" placeholder="Search..." onkeyup="filterFiles(this.value)">
                                <button class="btn btn-sm" onclick="fileManager.changeView('grid')" id="gridViewBtn">🔲</button>
                                <button class="btn btn-sm active" onclick="fileManager.changeView('list')" id="listViewBtn">📋</button>
                            </div>
                        </div>
                        
                        <div class="file-list" id="fileManagerList">
                            <div class="loading">Loading files...</div>
                        </div>
                        <div id="dropZone" class="drop-zone">Drop files here to upload</div>
                    </div>
                </div>
            </div>
            
            <div id="logs" class="tab-content">
                <div id="logsContent">
                    <h3>System Logs</h3>
                    <div class="log-viewer" id="logViewer">Loading logs...</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Configuration Modal -->
    <div id="configModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="configModalTitle">Configure Backend</h3>
                <span class="close" onclick="closeConfigModal()">&times;</span>
            </div>
            <div id="configModalContent">
                <!-- Configuration form will be populated here -->
            </div>
        </div>
    </div>

    <!-- Logs Modal -->
    <div id="logsModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="logsModalTitle">Backend Logs</h3>
                <span class="close" onclick="closeLogsModal()">&times;</span>
            </div>
            <div id="logsModalContent">
                <!-- Logs will be populated here -->
            </div>
        </div>
    </div>

    <!-- File Manager Modals -->
    <div id="createFolderModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">Create New Folder</h3>
                <button class="modal-close" onclick="fileManager.closeModal('createFolderModal')">&times;</button>
            </div>
            <div class="form-group">
                <label for="newFolderName">Folder Name</label>
                <input type="text" id="newFolderName" class="form-control">
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="fileManager.closeModal('createFolderModal')">Cancel</button>
                <button class="btn btn-primary" onclick="fileManager.createNewFolder()">Create</button>
            </div>
        </div>
    </div>

    <div id="renameModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">Rename Item</h3>
                <button class="modal-close" onclick="fileManager.closeModal('renameModal')">&times;</button>
            </div>
            <div class="form-group">
                <label for="newItemName">New Name</label>
                <input type="text" id="newItemName" class="form-control">
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="fileManager.closeModal('renameModal')">Cancel</button>
                <button class="btn btn-primary" onclick="fileManager.renameItem()">Rename</button>
            </div>
        </div>
    </div>

    <div id="moveModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">Move Item</h3>
                <button class="modal-close" onclick="fileManager.closeModal('moveModal')">&times;</button>
            </div>
            <div class="form-group">
                <label for="targetPath">Destination Path</label>
                <input type="text" id="targetPath" class="form-control">
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="fileManager.closeModal('moveModal')">Cancel</button>
                <button class="btn btn-primary" onclick="fileManager.moveItem()">Move</button>
            </div>
        </div>
    </div>

    <div id="uploadProgress" class="upload-progress">
        <h4>Uploads</h4>
        <div id="uploadProgressList"></div>
    </div>

    <ul id="contextMenu" class="context-menu">
        <li class="context-menu-item" data-action="open">Open</li>
        <li class="context-menu-item" data-action="download">Download</li>
        <li class="context-menu-separator"></li>
        <li class="context-menu-item" data-action="rename">Rename</li>
        <li class="context-menu-item" data-action="move">Move</li>
        <li class="context-menu-separator"></li>
        <li class="context-menu-item danger" data-action="delete">Delete</li>
    </ul>


    <script>
        let autoRefreshInterval = null;
        let currentBackendData = {};
        
        function switchTab(tabName, event) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tab buttons
            document.querySelectorAll('.tab-button').forEach(button => {
                button.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to the clicked button
            if (event && event.target) {
                event.target.classList.add('active');
            } else {
                // Fallback: find the button by tabName
                const buttons = document.querySelectorAll('.tab-button');
                buttons.forEach(button => {
                    if (button.textContent.toLowerCase().includes(tabName.toLowerCase())) {
                        button.classList.add('active');
                    }
                });
            }
            
            // Load content for specific tabs
            console.log('🔄 Switching to tab:', tabName);
            if (tabName === 'configuration') {
                console.log('⚙️ Loading configuration tab...');
                loadConfigurationTab();
            } else if (tabName === 'logs') {
                console.log('📋 Loading logs tab...');
                loadLogsTab();
            } else if (tabName === 'vfs') {
                console.log('📁 Loading VFS tab...');
                loadVFSTab();
            } else if (tabName === 'vector-kb') {
                console.log('🧠 Loading Vector/KB tab...');
                loadVectorKBTab();
            } else if (tabName === 'filemanager') {
                console.log('📂 Loading File Manager tab...');
                loadFileManagerTab();
            } else if (tabName === 'overview') {
                console.log('🏠 Loading overview tab...');
                refreshData();
            }
        }

        // Alias for backward compatibility
        function showTab(tabName, event) {
            switchTab(tabName, event);
        }
        
        async function refreshData() {
            try {
                console.log('🔄 Refreshing dashboard data...');
                const response = await fetch('/api/health');
                const responseData = await response.json();
                console.log('📊 Health API response:', responseData);
                
                // Handle both wrapped and direct response formats
                const data = responseData.success ? responseData.data : responseData;
                currentBackendData = data.backend_health || {};
                console.log('🔧 Backend data extracted:', currentBackendData);
                console.log('📈 Updating dashboard with data:', data);
                updateDashboard(data);
            } catch (error) {
                console.error('❌ Error refreshing data:', error);
            }
        }
        
        function updateDashboard(data) {
            console.log('🎨 Updating dashboard with data:', data);
            
            // Update system status
            const systemStatusEl = document.getElementById('systemStatus');
            if (systemStatusEl) {
                console.log('✅ Updating system status');
                systemStatusEl.innerHTML = `
                    <div class="connection-status">
                        <div class="connection-indicator ${data.status === 'running' ? 'connected' : ''}"></div>
                        <span>Status: ${data.status || 'unknown'}</span>
                    </div>
                    <p><strong>Uptime:</strong> ${data.uptime_seconds ? `${Math.floor(data.uptime_seconds / 3600)}h ${Math.floor((data.uptime_seconds % 3600) / 60)}m` : 'N/A'}</p>
                    <p><strong>Components:</strong> ${Object.values(data.components || {}).filter(Boolean).length}/${Object.keys(data.components || {}).length} active</p>
                `;
            } else {
                console.error('❌ systemStatus element not found');
            }
            
            // Update backend summary
            const backends = data.backend_health || {};
            const healthyCount = Object.values(backends).filter(b => b.health === 'healthy').length;
            const totalCount = Object.keys(backends).length;
            const progressPercent = totalCount > 0 ? (healthyCount / totalCount) * 100 : 0;
            
            const backendSummaryEl = document.getElementById('backendSummary');
            if (backendSummaryEl) {
                console.log('✅ Updating backend summary:', {healthyCount, totalCount, progressPercent});
                backendSummaryEl.innerHTML = `
                    <div style="font-size: 24px; font-weight: bold; color: ${healthyCount === totalCount ? '#4CAF50' : '#f44336'};">
                        ${healthyCount}/${totalCount}
                    </div>
                    <p>Backends Healthy</p>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progressPercent}%"></div>
                    </div>
                    <div style="font-size: 12px; color: #6c757d;">Health Score: ${progressPercent.toFixed(1)}%</div>
                `;
            } else {
                console.error('❌ backendSummary element not found');
            }
            
            // Update performance metrics
            const performanceMetricsEl = document.getElementById('performanceMetrics');
            if (performanceMetricsEl) {
                console.log('✅ Updating performance metrics');
                performanceMetricsEl.innerHTML = `
                    <div><strong>Memory:</strong> ${data.memory_usage_mb || 'N/A'}MB</div>
                    <div><strong>CPU:</strong> ${data.cpu_usage_percent || 'N/A'}%</div>
                    <div><strong>Active Backends:</strong> ${Object.values(backends).filter(b => b.status === 'running').length}</div>
                    <div><strong>Last Update:</strong> ${new Date().toLocaleTimeString()}</div>
                `;
            } else {
                console.error('❌ performanceMetrics element not found');
            }
            
            // Update backend grid
            console.log('🔧 Updating backend grid...');
            updateBackendGrid(backends);

            // Also update the VFS and Vector/KB tabs if they are active
            if (document.getElementById('vfs').classList.contains('active')) {
                loadVFSTab();
            }
            if (document.getElementById('vector-kb').classList.contains('active')) {
                loadVectorKBTab();
            }
        }
        
        function updateBackendGrid(backends) {
            const grid = document.getElementById('backendGrid');
            grid.innerHTML = '';
            
            for (const [name, backend] of Object.entries(backends)) {
                const card = document.createElement('div');
                card.className = `backend-card ${backend.health}`;
                
                // Create verbose metrics display
                let verboseMetricsHTML = createVerboseMetricsHTML(backend);
                
                let errorsHTML = '';
                if (backend.errors && backend.errors.length > 0) {
                    errorsHTML = `
                        <div class="expandable">
                            <div class="expandable-header">Recent Errors (${backend.errors.length})</div>
                            <div class="expandable-content">
                                <div class="error-log">
                                    ${backend.errors.slice(-5).map(error => 
                                        `<div><strong>${new Date(error.timestamp).toLocaleString()}:</strong> ${error.error}</div>`
                                    ).join('')}
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                card.innerHTML = `
                    <div class="backend-header">
                        <div>
                            <h3>${backend.name}</h3>
                            <div class="status-badge status-${backend.health}">${backend.health}</div>
                            <div class="status-badge status-${backend.status === 'running' ? 'healthy' : 'unknown'}">${backend.status}</div>
                        </div>
                        <div class="backend-actions">
                            <button class="action-btn config" onclick="openConfigModal('${name}')">⚙️ Config</button>
                            ${['ipfs', 'ipfs_cluster', 'ipfs_cluster_follow', 'lotus'].includes(name) ? 
                                `<button class="action-btn restart" onclick="restartBackend('${name}')">🔄 Restart</button>` : ''}
                            <button class="action-btn logs" onclick="openLogsModal('${name}')">📋 Logs</button>
                        </div>
                    </div>
                    <p><strong>Last Check:</strong> ${backend.last_check ? new Date(backend.last_check).toLocaleString() : 'Never'}</p>
                    ${verboseMetricsHTML}
                    ${errorsHTML}
                `;
                
                grid.appendChild(card);
            }
            
            // Add click handlers for expandable sections
            document.querySelectorAll('.expandable-header').forEach(header => {
                header.onclick = () => {
                    header.parentElement.classList.toggle('expanded');
                };
            });
        }
        
        function createVerboseMetricsHTML(backend) {
            if (!backend.metrics || Object.keys(backend.metrics).length === 0) {
                return '<div class="verbose-metrics"><em>No metrics available</em></div>';
            }
            
            let html = '<div class="verbose-metrics">';
            
            // Group metrics by category
            const groupedMetrics = groupMetricsByCategory(backend.metrics);
            
            for (const [category, metrics] of Object.entries(groupedMetrics)) {
                html += `
                    <div class="metrics-section">
                        <h4>${category}</h4>
                        <table class="metrics-table">
                `;
                
                for (const [key, value] of Object.entries(metrics)) {
                    const displayValue = formatMetricValue(value);
                    html += `
                        <tr>
                            <td>${formatMetricKey(key)}</td>
                            <td class="value">${displayValue}</td>
                        </tr>
                    `;
                }
                
                html += '</table></div>';
            }
            
            html += '</div>';
            return html;
        }
        
        function groupMetricsByCategory(metrics) {
            const groups = {
                'Connection': {},
                'Performance': {},
                'Storage': {},
                'Process': {},
                'Network': {},
                'Configuration': {},
                'Other': {}
            };
            
            for (const [key, value] of Object.entries(metrics)) {
                const lowerKey = key.toLowerCase();
                
                if (lowerKey.includes('version') || lowerKey.includes('commit') || lowerKey.includes('build')) {
                    groups['Configuration'][key] = value;
                } else if (lowerKey.includes('pid') || lowerKey.includes('process') || lowerKey.includes('daemon')) {
                    groups['Process'][key] = value;
                } else if (lowerKey.includes('size') || lowerKey.includes('storage') || lowerKey.includes('repo') || lowerKey.includes('objects')) {
                    groups['Storage'][key] = value;
                } else if (lowerKey.includes('peer') || lowerKey.includes('endpoint') || lowerKey.includes('connection')) {
                    groups['Network'][key] = value;
                } else if (lowerKey.includes('time') || lowerKey.includes('response') || lowerKey.includes('latency')) {
                    groups['Performance'][key] = value;
                } else if (lowerKey.includes('connected') || lowerKey.includes('running') || lowerKey.includes('available')) {
                    groups['Connection'][key] = value;
                } else {
                    groups['Other'][key] = value;
                }
            }
            
            // Remove empty groups
            return Object.fromEntries(Object.entries(groups).filter(([_, metrics]) => Object.keys(metrics).length > 0));
        }
        
        function formatMetricKey(key) {
            return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }
        
        function formatMetricValue(value) {
            if (typeof value === 'boolean') {
                return `<span style="color: ${value ? '#28a745' : '#dc3545'}">${value ? '✓' : '✗'}</span>`;
            } else if (typeof value === 'number') {
                if (value > 1000000) {
                    return `${(value / 1000000).toFixed(2)}M`;
                } else if (value > 1000) {
                    return `${(value / 1000).toFixed(2)}K`;
                }
                return value.toString();
            } else if (typeof value === 'string' && (value.startsWith('http') || value.startsWith('/'))) {
                return `<a href="${value}" target="_blank" style="color: #007bff;">${value.length > 50 ? value.substring(0, 47) + '...' : value}</a>`;
            } else if (typeof value === 'object') {
                return `<pre style="margin: 0; font-size: 11px;">${JSON.stringify(value, null, 2)}</pre>`;
            } else if (typeof value === 'string' && value.length > 50) {
                return `<span title="${value}">${value.substring(0, 47)}...</span>`;
            }
            return value.toString();
        }
        
        async function loadConfigurationTab() {
            // Load package configuration
            await loadPackageConfig();
            
            const configList = document.getElementById('configBackendList');
            configList.innerHTML = '<div style="text-align: center; padding: 20px;">Loading backend configurations...</div>';
            
            try {
                const response = await fetch('/api/backends');
                const backends = await response.json();
                currentBackendData = backends; // Update backend data
                configList.innerHTML = ''; // Clear loading message

                for (const [name, backend] of Object.entries(currentBackendData)) {
                    const configCard = document.createElement('div');
                    configCard.className = 'stat-card';
                    configCard.style.cursor = 'pointer';
                    configCard.onclick = () => openConfigModal(name);
                    
                    let configPreview = 'Click to configure';
                    if (backend.config) {
                        const keys = Object.keys(backend.config);
                        if (keys.length > 0) {
                            configPreview = `${keys.length} config sections: ${keys.slice(0, 3).join(', ')}...`;
                        } else {
                            configPreview = 'No configuration available';
                        }
                    }

                    configCard.innerHTML = `
                        <h4>${backend.name}</h4>
                        <div class="status-badge status-${backend.health}">${backend.health}</div>
                        <p style="font-size: 0.9em; color: #6c757d; margin: 8px 0;">${configPreview}</p>
                    `;
                    
                    configList.appendChild(configCard);
                }
            } catch (error) {
                configList.innerHTML = `<div style="color: red; padding: 20px;">Error loading configurations: ${error.message}</div>`;
            }
        }
        
        async function loadLogsTab() {
            try {
                const response = await fetch('/api/logs');
                const data = await response.json();
                const logs = data.logs.join('');
                document.getElementById('logViewer').textContent = logs;
            } catch (error) {
                document.getElementById('logViewer').textContent = 'Error loading logs: ' + error.message;
            }
        }
        
        async function loadVFSTab() {
            try {
                console.log('📁 Starting VFS tab load...');
                const statsResponse = await fetch('/api/vfs/statistics');
                console.log('📊 VFS statistics response status:', statsResponse.status);
                const responseData = await statsResponse.json();
                console.log('📊 VFS statistics data:', responseData);

                if (statsResponse.ok && responseData.success) {
                    const statsData = responseData.data;  // Extract the actual data
                    console.log('✅ Processing VFS statistics data:', statsData);
                    
                    const cacheEl = document.getElementById('cachePerformance');
                    const filesystemEl = document.getElementById('filesystemStatus');
                    const accessEl = document.getElementById('accessPatterns');
                    const resourceEl = document.getElementById('resourceUsage');
                    
                    console.log('🔍 Found elements:', {
                        cachePerformance: !!cacheEl,
                        filesystemStatus: !!filesystemEl,
                        accessPatterns: !!accessEl,
                        resourceUsage: !!resourceEl
                    });
                    
                    if (cacheEl) cacheEl.innerHTML = formatCachePerformance(statsData.cache_performance || {});
                    if (filesystemEl) filesystemEl.innerHTML = formatFilesystemStatus(statsData.filesystem_metrics || {});
                    if (accessEl) accessEl.innerHTML = formatAccessPatterns(statsData.access_patterns || {});
                    if (resourceEl) resourceEl.innerHTML = formatResourceUsage(statsData.resource_utilization || {});
                    
                    const tieredEl = document.getElementById('tieredCacheDetails');
                    const hotEl = document.getElementById('hotContentAnalysis');
                    if (tieredEl) tieredEl.innerHTML = formatTieredCacheDetails(statsData.cache_performance || {});
                    if (hotEl) hotEl.innerHTML = formatHotContentAnalysis(statsData.access_patterns || {});
                    
                    console.log('✅ VFS tab loaded successfully');
                } else {
                    throw new Error(responseData.error || 'Failed to load VFS statistics');
                }
            } catch (error) {
                console.error('❌ Error loading VFS data:', error);
                document.getElementById('vfs').querySelectorAll('.stat-card div, .expandable-content').forEach(el => {
                    el.innerHTML = `<span style="color: red;">Error: ${error.message}</span>`;
                });
            }
        }
        
        async function loadVectorKBTab() {
            try {
                const vectorResponse = await fetch('/api/vfs/vector-index');
                const vectorResponseData = await vectorResponse.json();
                if (!vectorResponse.ok || !vectorResponseData.success) throw new Error(vectorResponseData.error || 'Failed to load vector index status');
                const vectorData = vectorResponseData.data;

                const kbResponse = await fetch('/api/vfs/knowledge-base');
                const kbResponseData = await kbResponse.json();
                if (!kbResponse.ok || !kbResponseData.success) throw new Error(kbResponseData.error || 'Failed to load knowledge base status');
                const kbData = kbResponseData.data;

                const cacheResponse = await fetch('/api/vfs/cache');
                const cacheResponseData = await cacheResponse.json();
                if (!cacheResponse.ok || !cacheResponseData.success) throw new Error(cacheResponseData.error || 'Failed to load cache status');
                const cacheData = cacheResponseData.data;

                document.getElementById('vectorIndexStatus').innerHTML = formatVectorIndexStatus(vectorData || {});
                document.getElementById('knowledgeGraphStatus').innerHTML = formatKnowledgeGraphStatus(kbData || {});
                document.getElementById('searchPerformance').innerHTML = formatSearchPerformance(vectorData.search_performance || {});
                document.getElementById('contentDistribution').innerHTML = formatContentDistribution(vectorData.content_distribution || {});
                document.getElementById('vectorIndexDetails').innerHTML = formatVectorIndexDetails(vectorData || {});
                document.getElementById('knowledgeBaseAnalytics').innerHTML = formatKnowledgeBaseAnalytics(kbData || {});
                document.getElementById('semanticCachePerformance').innerHTML = formatSemanticCachePerformance(cacheData.semantic_cache || {});
                
            } catch (error) {
                console.error('Error loading Vector/KB data:', error);
                document.getElementById('vector-kb').querySelectorAll('.stat-card div, .expandable-content').forEach(el => {
                    el.innerHTML = `<span style="color: red;">Error: ${error.message}</span>`;
                });
            }
        }

        // Vector/KB Helper Functions
        function formatVectorIndexDetails(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            return `
                <div class="metrics-grid">
                    <div class="metric-item">
                        <strong>Total Vectors:</strong> ${data.total_vectors || 0}
                    </div>
                    <div class="metric-item">
                        <strong>Dimensions:</strong> ${data.dimensions || 'N/A'}
                    </div>
                    <div class="metric-item">
                        <strong>Index Type:</strong> ${data.index_type || 'N/A'}
                    </div>
                    <div class="metric-item">
                        <strong>Memory Usage:</strong> ${formatBytes(data.memory_usage || 0)}
                    </div>
                    <div class="metric-item">
                        <strong>Last Update:</strong> ${data.last_update ? new Date(data.last_update).toLocaleString() : 'N/A'}
                    </div>
                </div>
            `;
        }
        
        function formatKnowledgeBaseAnalytics(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            return `
                <div class="metrics-grid">
                    <div class="metric-item">
                        <strong>Documents:</strong> ${data.document_count || 0}
                    </div>
                    <div class="metric-item">
                        <strong>Entities:</strong> ${data.entity_count || 0}
                    </div>
                    <div class="metric-item">
                        <strong>Relationships:</strong> ${data.relationship_count || 0}
                    </div>
                    <div class="metric-item">
                        <strong>Avg Query Time:</strong> ${data.avg_query_time || 0}ms
                    </div>
                    <div class="metric-item">
                        <strong>Cache Hit Rate:</strong> ${data.cache_hit_rate || 0}%
                    </div>
                </div>
            `;
        }
        
        function formatBytes(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        // File Manager Helper Functions - Define these before loadFileManagerTab
        function setupFileManager() {
            // This function sets up the file manager UI
            console.log('Setting up file manager...');
        }
        
        function setupDragAndDrop() {
            const dropArea = document.getElementById('dropZone');
            if (!dropArea) return;
            
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, preventDefaults, false);
            });
            
            ['dragenter', 'dragover'].forEach(eventName => {
                dropArea.addEventListener(eventName, highlight, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, unhighlight, false);
            });
            
            dropArea.addEventListener('drop', handleDrop, false);
        }
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        function highlight(e) {
            document.getElementById('dropZone').classList.add('highlight');
        }
        
        function unhighlight(e) {
            document.getElementById('dropZone').classList.remove('highlight');
        }
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            handleFiles(files);
        }
        
        function handleFiles(files) {
            [...files].forEach(uploadFile);
        }
        
        function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            
            fetch('/api/files/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('File uploaded successfully');
                    refreshFileList();
                } else {
                    throw new Error(data.error || 'Upload failed');
                }
            })
            .catch(error => {
                console.error('Upload error:', error);
                alert('Upload failed: ' + error.message);
            });
        }
        
        function uploadSelectedFile() {
            const fileInput = document.getElementById('fileInput');
            if (fileInput.files.length > 0) {
                handleFiles(fileInput.files);
            }
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
                const response = await fetch(`/api/files/${filename}`);
                const blob = await response.blob();
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
        
        async function deleteFile(filename) {
            if (confirm(`Are you sure you want to delete ${filename}?`)) {
                try {
                    const response = await fetch(`/api/files/${filename}`, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        refreshFileList();
                    } else {
                        throw new Error(data.error || 'Delete failed');
                    }
                } catch (error) {
                    console.error('Delete error:', error);
                    alert('Delete failed: ' + error.message);
                }
            }
        }

        function createFolderPrompt() {
            const folderName = prompt('Enter folder name:');
            if (folderName) {
                createFolder(folderName);
            }
        }

        async function createFolder(folderName) {
            try {
                const response = await fetch('/api/files/create_folder', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ name: folderName })
                });
                const data = await response.json();
                
                if (data.success) {
                    refreshFileList();
                } else {
                    throw new Error(data.error || 'Create folder failed');
                }
            } catch (error) {
                console.error('Create folder error:', error);
                alert('Create folder failed: ' + error.message);
            }
        }

        async function loadFileManagerTab() {
            try {
                console.log('📂 Starting File Manager tab load...');
                
                // Initialize file manager UI if not already done
                if (!window.fileManagerInitialized) {
                    console.log('🔧 Initializing file manager UI...');
                    setupFileManager();
                    window.fileManagerInitialized = true;
                }
                
                // Load current directory contents
                console.log('📋 Loading file list...');
                await refreshFileList();
                
                // Setup drag and drop functionality
                console.log('🎯 Setting up drag and drop...');
                setupDragAndDrop();
                
                console.log('✅ File Manager tab loaded successfully');
            } catch (error) {
                console.error('❌ Error loading File Manager:', error);
                document.getElementById('filemanager').innerHTML = `<div style="color: red; padding: 20px;">Error loading File Manager: ${error.message}</div>`;
            }
        }
        
        async function refreshFileList() {
            try {
                console.log('📋 Fetching file list from /api/files/...');
                const response = await fetch('/api/files/');
                console.log('📊 File list response status:', response.status);
                const data = await response.json();
                console.log('📊 File list data:', data);
                
                if (data.success) {
                    console.log('✅ File list loaded, displaying files:', data.files);
                    displayFileList(data.files);
                } else {
                    throw new Error(data.error || 'Failed to load files');
                }
            } catch (error) {
                console.error('❌ Error loading file list:', error);
                const fileListEl = document.getElementById('fileList');
                if (fileListEl) {
                    fileListEl.innerHTML = `<div style="color: red;">Error: ${error.message}</div>`;
                } else {
                    console.error('❌ fileList element not found');
                }
            }
        }
        
        function displayFileList(files) {
            const fileList = document.getElementById('fileList');
            if (!fileList) return;
            
            fileList.innerHTML = files.map(file => `
                <div class="file-item ${file.type}" data-name="${file.name}">
                    <span class="file-icon">${file.type === 'directory' ? '📁' : '📄'}</span>
                    <span class="file-name">${file.name}</span>
                    <span class="file-size">${formatFileSize(file.size)}</span>
                    <span class="file-actions">
                        <button onclick="downloadFile('${file.name}')">📥</button>
                        <button onclick="deleteFile('${file.name}')">🗑️</button>
                    </span>
                </div>
            `).join('');
        }
        
        let backendConfigCache = {};

        async function openConfigModal(backendName) {
            const modal = document.getElementById('configModal');
            const title = document.getElementById('configModalTitle');
            const content = document.getElementById('configModalContent');
            
            title.textContent = `Configure ${backendName}`;
            content.innerHTML = '<div style="text-align: center; padding: 20px;">Loading configuration...</div>';
            modal.style.display = 'block';
            
            try {
                const response = await fetch(`/api/backends/${backendName}/config`);
                if (!response.ok) {
                    throw new Error(`Failed to load config for ${backendName}`);
                }
                const configData = await response.json();
                
                backendConfigCache[backendName] = configData.config || {};
                
                content.innerHTML = createConfigForm(backendName);

                // Add click handlers for expandable sections inside the modal
                content.querySelectorAll('.expandable-header').forEach(header => {
                    header.onclick = () => {
                        header.parentElement.classList.toggle('expanded');
                    };
                });

            } catch (error) {
                content.innerHTML = `<div style="color: red; padding: 20px;">Error loading configuration: ${error.message}</div>`;
            }
        }
        
        function closeConfigModal() {
            document.getElementById('configModal').style.display = 'none';
        }
        
        async function openLogsModal(backendName) {
            const modal = document.getElementById('logsModal');
            const title = document.getElementById('logsModalTitle');
            const content = document.getElementById('logsModalContent');
            
            title.textContent = `${backendName} Logs`;
            content.innerHTML = `<div class="log-viewer">Loading logs for ${backendName}...</div>`;
            modal.style.display = 'block';
            
            try {
                const response = await fetch(`/api/backends/${backendName}/logs`);
                const data = await response.json();
                content.innerHTML = `<div class="log-viewer">${data.logs.join('')}</div>`;
            } catch (error) {
                content.innerHTML = `<div class="log-viewer" style="color: red;">Error loading logs: ${error.message}</div>`;
            }
        }
        
        function closeLogsModal() {
            document.getElementById('logsModal').style.display = 'none';
        }
        
        function createConfigForm(backendName) {
            const configs = getBackendConfigOptions(backendName);
            
            let formHTML = `<form onsubmit="saveBackendConfig('${backendName}', event)">`;
            
            for (const [section, fields] of Object.entries(configs)) {
                formHTML += `
                    <div class="expandable expanded">
                        <div class="expandable-header">${section}</div>
                        <div class="expandable-content">
                `;
                
                for (const field of fields) {
                    formHTML += createFormField(field, backendName);
                }
                
                formHTML += '</div></div>';
            }
            
            const rawConfig = backendConfigCache[backendName] || {};
            formHTML += `
                <div class="expandable">
                    <div class="expandable-header">Raw Configuration (Advanced)</div>
                    <div class="expandable-content">
                        <div class="form-group">
                            <label>Complete Backend Configuration (JSON)</label>
                            <textarea name="raw_config" style="min-height: 200px; font-family: monospace; font-size: 12px;" readonly>${JSON.stringify(rawConfig, null, 2)}</textarea>
                            <small style="color: #6c757d;">This shows the complete backend configuration. Use the fields above to modify specific settings.</small>
                        </div>
                    </div>
                </div>
            `;
            
            formHTML += `
                <div style="margin-top: 20px; text-align: right;">
                    <button type="button" class="btn btn-secondary" onclick="closeConfigModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">Save Configuration</button>
                </div>
            </form>`;
            
            return formHTML;
        }

        function getBackendConfigOptions(backendName) {
            const configs = {
                'ipfs': {
                    'Connection': [
                        { name: 'Addresses.API', label: 'API Address', type: 'text', value: '/ip4/127.0.0.1/tcp/5001', description: 'IPFS API multiaddr' },
                        { name: 'Addresses.Gateway', label: 'Gateway Address', type: 'text', value: '/ip4/127.0.0.1/tcp/8080', description: 'IPFS Gateway multiaddr' },
                        { name: 'Identity.PeerID', label: 'Peer ID', type: 'text', value: '', description: 'IPFS node peer ID (read-only)', readonly: true }
                    ],
                    'Storage': [
                        { name: 'Datastore.StorageMax', label: 'Storage Max', type: 'text', value: '10GB', description: 'Maximum storage size' },
                        { name: 'Datastore.GCPeriod', label: 'GC Period', type: 'text', value: '1h', description: 'Garbage collection period' },
                        { name: 'Datastore.StorageGCWatermark', label: 'GC Watermark (%)', type: 'number', value: '90', description: 'Storage threshold for GC' }
                    ],
                    'Network': [
                        { name: 'Discovery.MDNS.Enabled', label: 'Enable mDNS', type: 'checkbox', value: 'true', description: 'Enable local network discovery' },
                        { name: 'Swarm.DisableBandwidthMetrics', label: 'Disable Bandwidth Metrics', type: 'checkbox', value: 'false', description: 'Disable bandwidth tracking' }
                    ]
                },
                'lotus': {
                    'Network': [
                        { name: 'network', label: 'Network', type: 'select', options: ['mainnet', 'calibnet', 'testnet'], value: 'calibnet', description: 'Filecoin network to connect to' },
                        { name: 'api_port', label: 'API Port', type: 'number', value: '1234', description: 'Lotus API port' },
                        { name: 'enable_splitstore', label: 'Enable Splitstore', type: 'checkbox', value: 'false', description: 'Enable splitstore for better performance' }
                    ],
                    'Authentication': [
                        { name: 'api_token', label: 'API Token', type: 'password', value: '', description: 'Lotus API authentication token' },
                        { name: 'jwt_secret', label: 'JWT Secret', type: 'password', value: '', description: 'JWT secret for API authentication' }
                    ],
                    'Performance': [
                        { name: 'max_peers', label: 'Max Peers', type: 'number', value: '100', description: 'Maximum number of peers' },
                        { name: 'bootstrap', label: 'Enable Bootstrap', type: 'checkbox', value: 'true', description: 'Enable bootstrap nodes' }
                    ]
                },
                'storacha': {
                    'Authentication': [
                        { name: 'api_token', label: 'API Token', type: 'password', value: '', description: 'Storacha API token' },
                        { name: 'space_did', label: 'Space DID', type: 'text', value: '', description: 'Storacha space identifier' },
                        { name: 'private_key', label: 'Private Key', type: 'password', value: '', description: 'Private key for signing' }
                    ],
                    'Endpoints': [
                        { name: 'primary_endpoint', label: 'Primary Endpoint', type: 'url', value: 'https://up.storacha.network/bridge', description: 'Primary Storacha endpoint' },
                        { name: 'backup_endpoints', label: 'Backup Endpoints', type: 'textarea', value: 'https://api.web3.storage\\nhttps://up.web3.storage/bridge', description: 'Backup endpoints (one per line)' }
                    ]
                },
                'synapse': {
                    'Authentication': [
                        { name: 'private_key', label: 'Private Key', type: 'password', value: '', description: 'Synapse private key for signing' },
                        { name: 'wallet_address', label: 'Wallet Address', type: 'text', value: '', description: 'Wallet address for transactions' }
                    ],
                    'Network': [
                        { name: 'network', label: 'Network', type: 'select', options: ['mainnet', 'calibration', 'testnet'], value: 'calibration', description: 'Filecoin network' },
                        { name: 'rpc_endpoint', label: 'RPC Endpoint', type: 'url', value: '', description: 'Custom RPC endpoint (optional)' }
                    ],
                    'Configuration': [
                        { name: 'max_file_size', label: 'Max File Size (MB)', type: 'number', value: '100', description: 'Maximum file size for uploads' },
                        { name: 'chunk_size', label: 'Chunk Size (MB)', type: 'number', value: '10', description: 'Chunk size for large files' }
                    ]
                },
                'huggingface': {
                    'Authentication': [
                        { name: 'token', label: 'HF Token', type: 'password', value: '', description: 'HuggingFace Hub token' },
                        { name: 'username', label: 'Username', type: 'text', value: '', description: 'HuggingFace username' }
                    ],
                    'Configuration': [
                        { name: 'cache_dir', label: 'Cache Directory', type: 'text', value: '~/.cache/huggingface', description: 'Local cache directory' },
                        { name: 'default_model', label: 'Default Model', type: 'text', value: 'sentence-transformers/all-MiniLM-L6-v2', description: 'Default embedding model' }
                    ]
                },
                's3': {
                    'Credentials': [
                        { name: 'access_key_id', label: 'Access Key ID', type: 'text', value: '', description: 'AWS Access Key ID' },
                        { name: 'secret_access_key', label: 'Secret Access Key', type: 'password', value: '', description: 'AWS Secret Access Key' },
                        { name: 'session_token', label: 'Session Token', type: 'password', value: '', description: 'AWS Session Token (optional)' }
                    ],
                    'Configuration': [
                        { name: 'region', label: 'Region', type: 'text', value: 'us-east-1', description: 'AWS region' },
                        { name: 'endpoint_url', label: 'Endpoint URL', type: 'url', value: '', description: 'Custom S3-compatible endpoint' },
                        { name: 'bucket', label: 'Default Bucket', type: 'text', value: '', description: 'Default S3 bucket' }
                    ]
                },
                'ipfs_cluster': {
                    'Connection': [
                        { name: 'api_endpoint', label: 'API Endpoint', type: 'url', value: 'http://127.0.0.1:9094', description: 'IPFS Cluster API endpoint' },
                        { name: 'proxy_endpoint', label: 'Proxy Endpoint', type: 'url', value: 'http://127.0.0.1:9095', description: 'IPFS Cluster proxy endpoint' }
                    ],
                    'Authentication': [
                        { name: 'basic_auth_user', label: 'Basic Auth User', type: 'text', value: '', description: 'Basic auth username' },
                        { name: 'basic_auth_pass', label: 'Basic Auth Password', type: 'password', value: '', description: 'Basic auth password' }
                    ],
                    'Configuration': [
                        { name: 'replication_factor', label: 'Replication Factor', type: 'number', value: '1', description: 'Number of replicas' },
                        { name: 'consensus', label: 'Consensus', type: 'select', options: ['raft', 'crdt'], value: 'raft', description: 'Consensus mechanism' }
                    ]
                }
            };
            
            return configs[backendName] || { 'General': [{ name: 'config', label: 'Configuration', type: 'textarea', value: '{}', description: 'Raw configuration (JSON)' }] };
        }

        function createFormField(field, backendName) {
            let input = '';
            const currentValue = getCurrentConfigValue(backendName, field.name) || field.value || '';
            const readonly = field.readonly ? 'readonly' : '';
            
            switch (field.type) {
                case 'select':
                    input = `<select name="${field.name}" ${readonly} class="form-control">`;
                    for (const option of field.options) {
                        input += `<option value="${option}" ${currentValue === option ? 'selected' : ''}>${option}</option>`;
                    }
                    input += '</select>';
                    break;
                case 'checkbox':
                    input = `<input type="checkbox" name="${field.name}" ${String(currentValue) === 'true' ? 'checked' : ''} ${readonly}>`;
                    break;
                case 'textarea':
                    input = `<textarea name="${field.name}" placeholder="${field.description || ''}" ${readonly} class="form-control">${currentValue}</textarea>`;
                    break;
                default:
                    input = `<input type="${field.type}" name="${field.name}" value="${currentValue}" placeholder="${field.description || ''}" ${readonly} class="form-control">`;
            }
            
            return `
                <div class="form-group">
                    <label>${field.label}</label>
                    ${input}
                    ${field.description ? `<small style="color: #6c757d;">${field.description}</small>` : ''}
                </div>
            `;
        }

        function getCurrentConfigValue(backendName, fieldName) {
            if (backendConfigCache[backendName]) {
                return getNestedValue(backendConfigCache[backendName], fieldName);
            }
            return '';
        }

        function getNestedValue(obj, path) {
            const keys = path.split('.');
            let value = obj;
            for (const key of keys) {
                if (value && typeof value === 'object' && key in value) {
                    value = value[key];
                } else {
                    return undefined;
                }
            }
            return value;
        }
        
        async function saveBackendConfig(backendName, event) {
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const newConfig = Object.fromEntries(formData.entries());
            
            try {
                const response = await fetch(`/api/backends/${backendName}/config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newConfig)
                });
                
                if (response.ok) {
                    alert('Configuration saved successfully!');
                    closeConfigModal();
                    refreshData();
                } else {
                    const errorData = await response.json();
                    alert(`Error saving configuration: ${errorData.error || response.statusText}`);
                }
            } catch (error) {
                alert(`Error saving configuration: ${error.message}`);
            }
        }
        
        async function restartBackend(backendName) {
            if (confirm(`Are you sure you want to restart ${backendName}?`)) {
                try {
                    const response = await fetch(`/api/backends/${backendName}/restart`, { method: 'POST' });
                    if (response.ok) {
                        alert(`${backendName} restart initiated.`);
                        setTimeout(refreshData, 2000); // Refresh after a delay
                    } else {
                        const errorData = await response.json();
                        alert(`Error restarting backend: ${errorData.error || response.statusText}`);
                    }
                } catch (error) {
                    alert(`Error restarting backend: ${error.message}`);
                }
            }
        }
        
        async function loadPackageConfig() {
            try {
                const response = await fetch('/api/config/package');
                const data = await response.json();
                
                if (data.success && data.config) {
                    const config = data.config;
                    
                    // System Settings
                    document.getElementById('system-log-level').value = config.system?.log_level || 'INFO';
                    document.getElementById('system-max-workers').value = config.system?.max_workers || 4;
                    document.getElementById('system-cache-size').value = config.system?.cache_size || 1000;
                    document.getElementById('system-data-dir').value = config.system?.data_directory || '/tmp/ipfs_kit';
                    
                    // VFS Settings
                    document.getElementById('vfs-cache-enabled').checked = config.vfs?.cache_enabled || true;
                    document.getElementById('vfs-cache-max-size').value = config.vfs?.cache_max_size || '10GB';
                    document.getElementById('vfs-vector-dimensions').value = config.vfs?.vector_dimensions || 384;
                    document.getElementById('vfs-kb-max-nodes').value = config.vfs?.knowledge_base_max_nodes || 10000;
                    
                    // Observability Settings
                    document.getElementById('obs-metrics-enabled').checked = config.observability?.metrics_enabled || true;
                    document.getElementById('obs-prometheus-port').value = config.observability?.prometheus_port || 9090;
                    document.getElementById('obs-dashboard-enabled').checked = config.observability?.dashboard_enabled || true;
                    document.getElementById('obs-health-check-interval').value = config.observability?.health_check_interval || 30;
                }
            } catch (error) {
                console.error('Error loading package configuration:', error);
            }
        }
        
        async function savePackageConfig() {
            const config = {
                system: {
                    log_level: document.getElementById('system-log-level').value,
                    max_workers: parseInt(document.getElementById('system-max-workers').value, 10),
                    cache_size: document.getElementById('system-cache-size').value,
                    data_directory: document.getElementById('system-data-dir').value
                },
                vfs: {
                    cache_enabled: document.getElementById('vfs-cache-enabled').checked,
                    cache_max_size: document.getElementById('vfs-cache-max-size').value,
                    vector_dimensions: parseInt(document.getElementById('vfs-vector-dimensions').value, 10),
                    knowledge_base_max_nodes: parseInt(document.getElementById('vfs-kb-max-nodes').value, 10)
                },
                observability: {
                    metrics_enabled: document.getElementById('obs-metrics-enabled').checked,
                    prometheus_port: parseInt(document.getElementById('obs-prometheus-port').value, 10),
                    dashboard_enabled: document.getElementById('obs-dashboard-enabled').checked,
                    health_check_interval: parseInt(document.getElementById('obs-health-check-interval').value, 10)
                }
            };
            
            try {
                const response = await fetch('/api/config/package', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                
                if (response.ok) {
                    alert('Package configuration saved successfully!');
                } else {
                    const errorData = await response.json();
                    alert(`Error saving configuration: ${errorData.error || response.statusText}`);
                }
            } catch (error) {
                alert(`Error saving configuration: ${error.message}`);
            }
        }
        
        async function getInsights() {
            const insightsCard = document.getElementById('insightsCard');
            const insightsContent = document.getElementById('insightsContent');
            
            try {
                const response = await fetch('/api/insights');
                const data = await response.json();
                if (data.success) {
                    insightsContent.innerHTML = formatInsights(data.insights);
                } else {
                    insightsContent.innerHTML = `<span style="color: red;">Error: ${data.error}</span>`;
                }
            } catch (error) {
                insightsContent.innerHTML = '<span style="color: red;">Error loading insights.</span>';
            }
            
            insightsCard.style.display = 'block';
        }
        
        async function exportConfig() {
            try {
                const response = await fetch('/api/config/export');
                const config = await response.json();
                
                const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `ipfs-kit-config-${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } catch (error) {
                alert('Error exporting configuration: ' + error.message);
            }
        }
        
        function toggleAutoRefresh() {
            const checkbox = document.getElementById('autoRefresh');
            if (checkbox.checked) {
                autoRefreshInterval = setInterval(refreshData, 30000);
            } else {
                clearInterval(autoRefreshInterval);
            }
        }
        
        function formatBytes(bytes, decimals = 2) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const dm = decimals < 0 ? 0 : decimals;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
        }
        
        function formatCachePerformance(data) {
            if (!data) return `No cache data available`;
            const tiered = data.tiered_cache || {};
            const semantic = data.semantic_cache || {};
            
            return `
                <div class="metrics-section">
                    <h4>Tiered Cache</h4>
                    <div><strong>Memory Hit Rate:</strong> ${((tiered.memory_tier?.hit_rate || 0) * 100).toFixed(1)}%</div>
                    <div><strong>Disk Hit Rate:</strong> ${((tiered.disk_tier?.hit_rate || 0) * 100).toFixed(1)}%</div>
                    <div><strong>Predictive Accuracy:</strong> ${((tiered.predictive_accuracy || 0) * 100).toFixed(1)}%</div>
                    <div><strong>Prefetch Efficiency:</strong> ${((tiered.prefetch_efficiency || 0) * 100).toFixed(1)}%</div>
                </div>
                <div class="metrics-section">
                    <h4>Semantic Cache</h4>
                    <div><strong>Similarity Threshold:</strong> ${semantic.similarity_threshold || 'N/A'}</div>
                    <div><strong>Cache Utilization:</strong> ${((semantic.cache_utilization || 0) * 100).toFixed(1)}%</div>
                    <div><strong>Embedding Model:</strong> ${semantic.embedding_model || 'N/A'}</div>
                </div>
            `;
        }
        
        function formatFilesystemStatus(data) {
            if (!data) return `No filesystem data available`;
            const metrics = data;
            return `
                <div class="metrics-section">
                    <h4>Disk Usage</h4>
                    <div><strong>Total:</strong> ${formatBytes(metrics.disk_usage.total_gb * 1024**3)}</div>
                    <div><strong>Used:</strong> ${formatBytes(metrics.disk_usage.used_gb * 1024**3)} (${metrics.disk_usage.usage_percent}%)</div>
                </div>
                <div class="metrics-section">
                    <h4>IPFS Kit Usage</h4>
                    <div><strong>Total Size:</strong> ${formatBytes(metrics.ipfs_kit_usage.total_size_mb * 1024**2)}</div>
                    <div><strong>Total Files:</strong> ${metrics.ipfs_kit_usage.total_files.toLocaleString()}</div>
                </div>
            `;
        }
        
        function formatAccessPatterns(data) {
            if (!data) return `No access pattern data available`;
            const patterns = data;
            return `
                <div class="metrics-section">
                    <h4>Hot Content (Top 3)</h4>
                    ${(patterns.hot_content || []).slice(0, 3).map(item => `
                        <div><strong>${item.path.split('/').pop()}:</strong> ${item.access_count} accesses</div>
                    `).join('')}
                </div>
                <div class="metrics-section">
                    <h4>Operation Distribution</h4>
                    ${Object.entries(patterns.operation_distribution || {}).map(([type, count]) => `
                        <div><strong>${type.replace('_', ' ')}:</strong> ${count.toLocaleString()}</div>
                    `).join('')}
                </div>
            `;
        }

        function formatResourceUsage(data) {
            if (!data) return `No resource usage data available`;
            const usage = data;
            return `
                <div class="metrics-section">
                    <h4>CPU Usage</h4>
                    <div><strong>System:</strong> ${usage.cpu_usage.system_percent}%</div>
                </div>
                <div class="metrics-section">
                    <h4>Memory Usage</h4>
                    <div><strong>System:</strong> ${usage.memory_usage.system_used_percent}% (${formatBytes(usage.memory_usage.system_total_mb * 1024**2 - usage.memory_usage.system_available_mb * 1024**2)} / ${formatBytes(usage.memory_usage.system_total_mb * 1024**2)})</div>
                    <div><strong>Cache:</strong> ${formatBytes(usage.memory_usage.cache_mb * 1024**2)}</div>
                    <div><strong>Index:</strong> ${formatBytes(usage.memory_usage.index_mb * 1024**2)}</div>
                </div>
            `;
        }

        function formatInsights(insights) {
            if (!insights || insights.length === 0) return 'No insights available.';
            return `<ul>${insights.map(i => `<li><strong>${i.title}:</strong> ${i.description} (Impact: ${i.impact})</li>`).join('')}</ul>`;
        }

        function formatVectorIndexStatus(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            return `
                <div class="metrics-section">
                    <h4>Index Status</h4>
                    <div><strong>Status:</strong> ${data.status || 'Unknown'}</div>
                    <div><strong>Total Vectors:</strong> ${data.total_vectors || 0}</div>
                    <div><strong>Dimensions:</strong> ${data.dimensions || 'N/A'}</div>
                    <div><strong>Index Size:</strong> ${data.index_size || 'N/A'}</div>
                </div>
            `;
        }
        
        function formatKnowledgeGraphStatus(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            return `
                <div class="metrics-section">
                    <h4>Knowledge Graph</h4>
                    <div><strong>Nodes:</strong> ${data.total_nodes || 0}</div>
                    <div><strong>Edges:</strong> ${data.total_edges || 0}</div>
                    <div><strong>Clusters:</strong> ${data.clusters || 0}</div>
                </div>
            `;
        }
        
        function formatSearchPerformance(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            return `
                <div class="metrics-section">
                    <h4>Search Performance</h4>
                    <div><strong>Avg Query Time:</strong> ${data.avg_query_time || 'N/A'}</div>
                    <div><strong>Throughput:</strong> ${data.throughput || 'N/A'}</div>
                    <div><strong>Success Rate:</strong> ${data.success_rate || 'N/A'}</div>
                </div>
            `;
        }
        
        function formatContentDistribution(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            return `
                <div class="metrics-section">
                    <h4>Content Distribution</h4>
                    <div><strong>Text Documents:</strong> ${data.text_documents || 0}</div>
                    <div><strong>Images:</strong> ${data.images || 0}</div>
                    <div><strong>Other:</strong> ${data.other || 0}</div>
                </div>
            `;
        }
        
        function formatSemanticCachePerformance(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            return `
                <div class="metrics-section">
                    <h4>Semantic Cache</h4>
                    <div><strong>Cache Hit Rate:</strong> ${((data.cache_hit_rate || 0) * 100).toFixed(1)}%</div>
                    <div><strong>Similarity Threshold:</strong> ${data.similarity_threshold || 'N/A'}</div>
                    <div><strong>Cache Size:</strong> ${data.cache_size || 'N/A'}</div>
                </div>
            `;
        }
        
        function formatTieredCacheDetails(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            const tiered = data.tiered_cache || {};
            const memory = tiered.memory_tier || {};
            const disk = tiered.disk_tier || {};
            
            return `
                <div class="metrics-section">
                    <h4>Memory Tier</h4>
                    <div><strong>Hit Rate:</strong> ${((memory.hit_rate || 0) * 100).toFixed(1)}%</div>
                    <div><strong>Size:</strong> ${memory.size_mb || 0}MB</div>
                    <div><strong>Items:</strong> ${memory.items || 0}</div>
                </div>
                <div class="metrics-section">
                    <h4>Disk Tier</h4>
                    <div><strong>Hit Rate:</strong> ${((disk.hit_rate || 0) * 100).toFixed(1)}%</div>
                    <div><strong>Read Latency:</strong> ${disk.read_latency_ms || 0}ms</div>
                    <div><strong>Write Latency:</strong> ${disk.write_latency_ms || 0}ms</div>
                </div>
            `;
        }
        
        function formatHotContentAnalysis(data) {
            if (!data || typeof data !== 'object') return '<div>No data available</div>';
            
            const hotContent = data.hot_content || [];
            
            return `
                <div class="metrics-section">
                    <h4>Most Accessed Content</h4>
                    ${hotContent.slice(0, 5).map(item => `
                        <div><strong>${item.path?.split('/').pop() || 'Unknown'}:</strong> ${item.access_count || 0} accesses</div>
                    `).join('')}
                </div>
            `;
        }

        // Enhanced File Manager Logic
        const fileManager = {
            currentPath: '/',
            files: [],
            view: 'list',
            sortBy: 'name',
            contextTarget: null,

            init() {
                this.setupEventListeners();
                this.refresh();
            },

            setupEventListeners() {
                const dropZone = document.getElementById('dropZone');
                const fileList = document.getElementById('fileManagerList');

                ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                    document.body.addEventListener(eventName, e => {
                        e.preventDefault();
                        e.stopPropagation();
                    });
                });

                document.body.addEventListener('dragenter', () => dropZone.style.display = 'flex');
                dropZone.addEventListener('dragleave', () => dropZone.style.display = 'none');
                dropZone.addEventListener('drop', e => {
                    dropZone.style.display = 'none';
                    this.handleFileUpload(e.dataTransfer.files);
                });

                fileList.addEventListener('contextmenu', e => {
                    e.preventDefault();
                    const target = e.target.closest('.file-item');
                    if (target) {
                        this.contextTarget = target;
                        this.showContextMenu(e.clientX, e.clientY);
                    }
                });

                document.addEventListener('click', () => this.hideContextMenu());
                document.getElementById('contextMenu').addEventListener('click', e => {
                    const action = e.target.closest('.context-menu-item').dataset.action;
                    this.handleContextMenuAction(action);
                });
            },

            async refresh() {
                this.renderLoading();
                try {
                    const response = await fetch(`/api/files/list?path=${encodeURIComponent(this.currentPath)}`);
                    const data = await response.json();
                    if (data.success && data.data) {
                        this.files = data.data.files || [];
                        this.sortFiles();
                        this.renderFiles();
                        this.renderBreadcrumb();
                        this.updateStats();
                    } else {
                        this.renderError(data.error || 'Failed to load files');
                    }
                } catch (error) {
                    this.renderError(error.message);
                }
            },

            renderFiles() {
                const fileList = document.getElementById('fileManagerList');
                fileList.innerHTML = '';
                fileList.className = `file-list ${this.view}-view`;

                if (this.files.length === 0) {
                    fileList.innerHTML = '<div class="empty-state">This folder is empty.</div>';
                    return;
                }

                this.files.forEach(file => {
                    const item = document.createElement('div');
                    item.className = 'file-item';
                    item.dataset.path = file.path;
                    item.dataset.isDir = file.is_dir;
                    item.innerHTML = this.view === 'list' ? this.renderListItem(file) : this.renderGridItem(file);
                    
                    item.addEventListener('dblclick', () => {
                        if (file.is_dir) {
                            this.navigateTo(file.path);
                        } else {
                            // Implement file preview
                        }
                    });
                    fileList.appendChild(item);
                });
            },

            renderListItem(file) {
                return `
                    <div class="file-icon">${file.is_dir ? '📁' : '📄'}</div>
                    <div class="file-info">
                        <div class="file-name">${file.name}</div>
                        <div class="file-meta">${formatBytes(file.size)} | ${new Date(file.modified * 1000).toLocaleString()}</div>
                    </div>
                `;
            },

            renderGridItem(file) {
                return `
                    <div class="file-icon">${file.is_dir ? '📁' : '📄'}</div>
                    <div class="file-info">
                        <div class="file-name">${file.name}</div>
                    </div>
                `;
            },

            renderBreadcrumb() {
                const breadcrumb = document.getElementById('fileManagerBreadcrumb');
                breadcrumb.innerHTML = '';
                let path = '';
                const parts = this.currentPath.split('/').filter(p => p);
                
                const root = document.createElement('span');
                root.className = 'breadcrumb-item';
                root.textContent = '🏠';
                root.onclick = () => this.navigateTo('/');
                breadcrumb.appendChild(root);

                parts.forEach(part => {
                    path += `/${part}`;
                    const item = document.createElement('span');
                    item.className = 'breadcrumb-item';
                    item.textContent = ` / ${part}`;
                    const currentPath = path;
                    item.onclick = () => this.navigateTo(currentPath);
                    breadcrumb.appendChild(item);
                });
            },

            updateStats() {
                const statsContainer = document.getElementById('fileManagerStats');
                const totalFiles = this.files.filter(f => !f.is_dir).length;
                const totalSize = this.files.reduce((acc, f) => acc + (f.is_dir ? 0 : f.size), 0);
                const lastModified = this.files.length > 0 ? Math.max(...this.files.map(f => f.modified)) : 0;

                statsContainer.innerHTML = `
                    <div class="stat-item"><span class="label">Files:</span><span class="value">${totalFiles}</span></div>
                    <div class="stat-item"><span class="label">Size:</span><span class="value">${formatBytes(totalSize)}</span></div>
                    <div class="stat-item"><span class="label">Modified:</span><span class="value">${lastModified ? new Date(lastModified * 1000).toLocaleDateString() : 'N/A'}</span></div>
                `;
            },

            navigateTo(path) {
                this.currentPath = path;
                this.refresh();
            },

            sortFiles(by = this.sortBy) {
                this.sortBy = by;
                this.files.sort((a, b) => {
                    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
                    if (by === 'name') return a.name.localeCompare(b.name);
                    if (by === 'size') return b.size - a.size;
                    if (by === 'modified') return b.modified - a.modified;
                    return 0;
                });
            },

            changeView(view) {
                this.view = view;
                document.getElementById('gridViewBtn').classList.toggle('active', view === 'grid');
                document.getElementById('listViewBtn').classList.toggle('active', view === 'list');
                this.renderFiles();
            },

            showContextMenu(x, y) {
                const menu = document.getElementById('contextMenu');
                menu.style.display = 'block';
                menu.style.left = `${x}px`;
                menu.style.top = `${y}px`;
            },

            hideContextMenu() {
                document.getElementById('contextMenu').style.display = 'none';
            },

            handleContextMenuAction(action) {
                if (!this.contextTarget) return;
                const path = this.contextTarget.dataset.path;
                switch (action) {
                    case 'rename': this.showRenameModal(path); break;
                    case 'delete': this.deleteItem(path); break;
                    case 'move': this.showMoveModal(path); break;
                    case 'download': this.downloadItem(path); break;
                }
            },

            showCreateFolderModal() {
                this.showModal('createFolderModal');
            },

            async createNewFolder() {
                const name = document.getElementById('newFolderName').value;
                if (!name) return;
                await this.apiCall('/api/files/create-folder', { path: this.currentPath, name });
                this.closeModal('createFolderModal');
                document.getElementById('newFolderName').value = '';
                this.refresh();
            },

            showRenameModal(path) {
                this.contextTarget.dataset.path = path; // Store path for rename
                document.getElementById('newItemName').value = path.split('/').pop();
                this.showModal('renameModal');
            },

            async renameItem() {
                const oldPath = this.contextTarget.dataset.path;
                const newName = document.getElementById('newItemName').value;
                if (!newName) return;
                const dir = oldPath.substring(0, oldPath.lastIndexOf('/'));
                const newPath = dir ? `${dir}/${newName}` : newName;
                await this.apiCall('/api/files/rename', { oldPath, newName: newPath });
                this.closeModal('renameModal');
                this.refresh();
            },

            showMoveModal(path) {
                this.contextTarget.dataset.path = path; // Store path for move
                document.getElementById('targetPath').value = this.currentPath;
                this.showModal('moveModal');
            },

            async moveItem() {
                const sourcePath = this.contextTarget.dataset.path;
                const targetPath = document.getElementById('targetPath').value;
                if (!targetPath) return;
                await this.apiCall('/api/files/move', { sourcePath, targetPath: `${targetPath}/${sourcePath.split('/').pop()}` });
                this.closeModal('moveModal');
                this.refresh();
            },

            async deleteItem(path) {
                if (confirm(`Are you sure you want to delete "${path}"?`)) {
                    await this.apiCall('/api/files/delete', { path });
                    this.refresh();
                }
            },

            async downloadItem(path) {
                window.location.href = `/api/files/download?path=${encodeURIComponent(path)}`;
            },

            triggerUpload() {
                document.getElementById('fileInput').click();
            },

            handleFileUpload(files) {
                const uploadProgress = document.getElementById('uploadProgress');
                const uploadList = document.getElementById('uploadProgressList');
                uploadProgress.classList.add('visible');

                Array.from(files).forEach(file => {
                    const uploadId = `upload-${Date.now()}-${Math.random()}`;
                    const item = document.createElement('div');
                    item.className = 'upload-item';
                    item.id = uploadId;
                    item.innerHTML = `
                        <div class="file-name">${file.name}</div>
                        <div class="progress-bar"><div class="progress-fill"></div></div>
                        <div class="status">Pending...</div>
                    `;
                    uploadList.appendChild(item);
                    this.uploadFile(file, uploadId);
                });
            },

            async uploadFile(file, uploadId) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('path', this.currentPath);

                const response = await fetch('/api/files/upload', {
                    method: 'POST',
                    body: formData,
                    // onUploadProgress can be handled with XMLHttpRequest if needed
                });
                
                const result = await response.json();
                const item = document.getElementById(uploadId);
                const statusEl = item.querySelector('.status');
                const progressFill = item.querySelector('.progress-fill');

                const isSuccess = result.success && (!result.data || result.data.success);
                if (isSuccess) {
                    statusEl.textContent = 'Done';
                    progressFill.style.width = '100%';
                    this.refresh();
                    setTimeout(() => item.remove(), 3000);
                } else {
                    const errorMsg = result.error || (result.data && result.data.error) || 'Upload failed';
                    statusEl.textContent = `Error: ${errorMsg}`;
                    statusEl.style.color = 'red';
                }
            },

            async apiCall(endpoint, body) {
                try {
                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body)
                    });
                    const data = await response.json();
                    if (!data.success || (data.data && !data.data.success)) {
                        const errorMsg = data.error || (data.data && data.data.error) || 'Unknown error';
                        alert(`Error: ${errorMsg}`);
                    }
                    return data;
                } catch (error) {
                    alert(`API Error: ${error.message}`);
                }
            },

            showModal(id) { document.getElementById(id).style.display = 'block'; },
            closeModal(id) { document.getElementById(id).style.display = 'none'; },
            renderLoading() { document.getElementById('fileManagerList').innerHTML = '<div class="loading">Loading...</div>'; },
            renderError(error) { document.getElementById('fileManagerList').innerHTML = `<div class="empty-state" style="color:red;">${error}</div>`; }
        };

        // Make functions globally accessible by assigning to window object
        window.switchTab = switchTab;
        window.setupDragAndDrop = setupDragAndDrop;
        window.uploadSelectedFile = uploadSelectedFile;
        window.createFolderPrompt = createFolderPrompt;
        window.loadFileManagerTab = loadFileManagerTab;
        window.downloadFile = downloadFile;
        window.deleteFile = deleteFile;
        window.refreshFileList = refreshFileList;
        window.refreshData = refreshData;
        window.closeConfigModal = closeConfigModal;
        window.openLogsModal = openLogsModal;
        window.closeLogsModal = closeLogsModal;

        // Initial load
        window.onload = () => {
            refreshData();
            fileManager.init();
        };
    </script>
</body>
</html>
        '''.strip()
        
        with open(template_path, "w") as f:
            f.write(template_content)
            
        logger.info(f"✓ Dashboard template created at {template_path}")
        return str(template_path)

    def create_error_template(self, error_details: dict) -> str:
        """Create a detailed error page template."""
        
        template_path = self.templates_dir / "error.html"
        
        template_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Server Error</title>
    <style>
        body {{ font-family: sans-serif; background: #f8f9fa; color: #343a40; padding: 20px; }}
        .container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #dc3545; }}
        pre {{ background: #e9ecef; padding: 15px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Server Error</h1>
        <p><strong>Type:</strong> {error_details.get("error_type", "Unknown")}</p>
        <p><strong>Message:</strong> {error_details.get("message", "No message")}</p>
        <p><strong>URL:</strong> {error_details.get("url", "N/A")}</p>
        <h3>Traceback</h3>
        <pre>{error_details.get("traceback", "No traceback available")}</pre>
    </div>
</body>
</html>
        '''.strip()
        
        with open(template_path, "w") as f:
            f.write(template_content)
            
        return str(template_path)
