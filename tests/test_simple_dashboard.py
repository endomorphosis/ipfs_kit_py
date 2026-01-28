#!/usr/bin/env python3
"""
Simple test dashboard to verify basic functionality
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import socketserver
import threading
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")
    
    def do_GET(self):
        """Handle GET requests"""
        path = self.path.split('?')[0]  # Remove query parameters
        
        if path == '/':
            self.serve_dashboard()
        elif path == '/api/buckets':
            self.serve_buckets_api()
        elif path.startswith('/api/buckets/') and path.endswith('/files'):
            bucket_name = path.split('/')[3]
            self.serve_bucket_files_api(bucket_name)
        elif path == '/api/system/overview':
            self.serve_overview_api()
        elif path == '/static/js/test-dashboard.js':
            self.serve_js()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests"""
        path = self.path.split('?')[0]
        
        if path == '/api/buckets':
            self.handle_create_bucket()
        elif path.startswith('/api/buckets/') and path.endswith('/upload'):
            bucket_name = path.split('/')[3]
            self.handle_upload_file(bucket_name)
        else:
            self.send_error(404, "Not Found")
    
    def serve_dashboard(self):
        """Serve the main dashboard HTML"""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit - Test Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1200px, margin: 0 auto; }
        .card { background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .btn { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
        .btn:hover { background: #0056b3; }
        .btn-success { background: #28a745; }
        .btn-success:hover { background: #1e7e34; }
        .error { color: #dc3545; background: #f8d7da; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .success { color: #155724; background: #d4edda; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .form-group { margin: 15px 0; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .file-list { margin: 20px 0; }
        .file-item { padding: 10px; border: 1px solid #ddd; margin: 5px 0; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
        .upload-area { border: 2px dashed #ddd; padding: 40px; text-align: center; border-radius: 8px; margin: 20px 0; }
        .upload-area.dragover { border-color: #007bff; background: #f8f9fa; }
        .hidden { display: none; }
        .bucket-selector { margin: 20px 0; }
        .bucket-selector select { padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        #console-log { background: #000; color: #0f0; padding: 15px; border-radius: 4px; font-family: monospace; height: 200px; overflow-y: auto; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="container">
        <h1>IPFS Kit - Test Dashboard</h1>
        
        <div class="card">
            <h2>Console Log</h2>
            <div id="console-log"></div>
            <button class="btn" onclick="clearConsole()">Clear Console</button>
        </div>
        
        <div class="card">
            <h2>Create Bucket</h2>
            <div class="form-group">
                <label for="bucket-name">Bucket Name:</label>
                <input type="text" id="bucket-name" placeholder="Enter bucket name">
            </div>
            <div class="form-group">
                <label for="bucket-description">Description:</label>
                <input type="text" id="bucket-description" placeholder="Enter description">
            </div>
            <button class="btn btn-success" onclick="createBucket()">Create Bucket</button>
        </div>
        
        <div class="card">
            <h2>Select Bucket</h2>
            <div class="bucket-selector">
                <select id="bucket-select" onchange="selectBucket()">
                    <option value="">Select a bucket...</option>
                </select>
                <button class="btn" onclick="loadBuckets()">Refresh Buckets</button>
            </div>
        </div>
        
        <div class="card">
            <h2>File Upload</h2>
            <div class="upload-area" id="upload-area" ondrop="handleDrop(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)">
                <p>Drag and drop files here or click to select</p>
                <input type="file" id="file-input" multiple style="display: none;" onchange="handleFileSelect(event)">
                <button class="btn" onclick="document.getElementById('file-input').click()">Select Files</button>
            </div>
        </div>
        
        <div class="card">
            <h2>Files in Selected Bucket</h2>
            <div id="file-list" class="file-list">
                <p>Select a bucket to view files</p>
            </div>
            <button class="btn" onclick="refreshFiles()">Refresh Files</button>
        </div>
        
        <div id="message-area"></div>
    </div>
    
    <script src="/static/js/test-dashboard.js"></script>
</body>
</html>
"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def serve_js(self):
        """Serve the dashboard JavaScript"""
        js = """
// Test Dashboard JavaScript with Verbose Logging

let selectedBucket = null;
let consoleElement = null;

// Logging function
function logToConsole(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] ${level}: ${message}`;
    console.log(logMessage);
    
    if (!consoleElement) {
        consoleElement = document.getElementById('console-log');
    }
    
    if (consoleElement) {
        consoleElement.textContent += logMessage + '\\n';
        consoleElement.scrollTop = consoleElement.scrollHeight;
    }
}

function clearConsole() {
    if (consoleElement) {
        consoleElement.textContent = '';
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    logToConsole('Dashboard initialized');
    loadBuckets();
});

// API helper function
async function apiCall(url, options = {}) {
    logToConsole(`Making API call to: ${url}`);
    logToConsole(`Options: ${JSON.stringify(options)}`);
    
    try {
        const response = await fetch(url, {
            headers: {
                'Accept': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        logToConsole(`Response status: ${response.status} ${response.statusText}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        logToConsole(`Response data: ${JSON.stringify(data, null, 2)}`);
        return data;
    } catch (error) {
        logToConsole(`API call failed: ${error.message}`, 'ERROR');
        throw error;
    }
}

// Load buckets
async function loadBuckets() {
    logToConsole('Loading buckets...');
    try {
        const data = await apiCall('/api/buckets');
        const bucketSelect = document.getElementById('bucket-select');
        
        // Clear existing options
        bucketSelect.innerHTML = '<option value="">Select a bucket...</option>';
        
        if (data.buckets && data.buckets.length > 0) {
            data.buckets.forEach(bucket => {
                const option = document.createElement('option');
                option.value = bucket.name;
                option.textContent = `${bucket.name} (${bucket.backend || 'local'})`;
                bucketSelect.appendChild(option);
            });
            showMessage(`Loaded ${data.buckets.length} buckets`, 'success');
        } else {
            showMessage('No buckets found', 'info');
        }
    } catch (error) {
        showMessage(`Failed to load buckets: ${error.message}`, 'error');
    }
}

// Create bucket
async function createBucket() {
    const name = document.getElementById('bucket-name').value.trim();
    const description = document.getElementById('bucket-description').value.trim();
    
    if (!name) {
        showMessage('Bucket name is required', 'error');
        return;
    }
    
    logToConsole(`Creating bucket: ${name}`);
    
    try {
        const data = await apiCall('/api/buckets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description,
                bucket_type: 'general'
            })
        });
        
        if (data.success) {
            showMessage(`Bucket "${name}" created successfully`, 'success');
            document.getElementById('bucket-name').value = '';
            document.getElementById('bucket-description').value = '';
            loadBuckets();
        } else {
            showMessage(`Failed to create bucket: ${data.error}`, 'error');
        }
    } catch (error) {
        showMessage(`Failed to create bucket: ${error.message}`, 'error');
    }
}

// Select bucket
function selectBucket() {
    const bucketSelect = document.getElementById('bucket-select');
    selectedBucket = bucketSelect.value;
    
    if (selectedBucket) {
        logToConsole(`Selected bucket: ${selectedBucket}`);
        showMessage(`Selected bucket: ${selectedBucket}`, 'info');
        loadBucketFiles();
    } else {
        logToConsole('No bucket selected');
        document.getElementById('file-list').innerHTML = '<p>Select a bucket to view files</p>';
    }
}

// Load bucket files
async function loadBucketFiles() {
    if (!selectedBucket) {
        showMessage('No bucket selected', 'error');
        return;
    }
    
    logToConsole(`Loading files for bucket: ${selectedBucket}`);
    
    try {
        const data = await apiCall(`/api/buckets/${selectedBucket}/files`);
        const fileList = document.getElementById('file-list');
        
        if (data.success && data.files && data.files.length > 0) {
            fileList.innerHTML = '';
            data.files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.innerHTML = `
                    <div>
                        <strong>${file.name}</strong> (${formatBytes(file.size || 0)})
                        <br><small>Modified: ${file.last_modified || 'Unknown'}</small>
                    </div>
                    <div>
                        <button class="btn" onclick="downloadFile('${file.name}')">Download</button>
                        <button class="btn" onclick="viewMetadata('${file.name}')">View Metadata</button>
                    </div>
                `;
                fileList.appendChild(fileItem);
            });
            showMessage(`Loaded ${data.files.length} files`, 'success');
        } else {
            fileList.innerHTML = '<p>No files in this bucket</p>';
            showMessage('No files found in bucket', 'info');
        }
    } catch (error) {
        showMessage(`Failed to load files: ${error.message}`, 'error');
    }
}

// File upload handling
function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    
    const uploadArea = document.getElementById('upload-area');
    uploadArea.classList.remove('dragover');
    
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
        logToConsole(`Files dropped: ${files.map(f => f.name).join(', ')}`);
        uploadFiles(files);
    }
}

function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('upload-area').classList.add('dragover');
}

function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('upload-area').classList.remove('dragover');
}

function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    if (files.length > 0) {
        logToConsole(`Files selected: ${files.map(f => f.name).join(', ')}`);
        uploadFiles(files);
    }
}

// Upload files
async function uploadFiles(files) {
    if (!selectedBucket) {
        showMessage('Please select a bucket first', 'error');
        return;
    }
    
    logToConsole(`Uploading ${files.length} files to bucket: ${selectedBucket}`);
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        logToConsole(`Uploading file ${i + 1}/${files.length}: ${file.name} (${formatBytes(file.size)})`);
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch(`/api/buckets/${selectedBucket}/upload`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            logToConsole(`Upload result for ${file.name}: ${JSON.stringify(result)}`);
            
            if (result.success) {
                showMessage(`Uploaded ${file.name} successfully`, 'success');
            } else {
                showMessage(`Failed to upload ${file.name}: ${result.error}`, 'error');
            }
        } catch (error) {
            logToConsole(`Upload error for ${file.name}: ${error.message}`, 'ERROR');
            showMessage(`Failed to upload ${file.name}: ${error.message}`, 'error');
        }
    }
    
    // Refresh file list after uploads
    loadBucketFiles();
}

// Refresh files
function refreshFiles() {
    if (selectedBucket) {
        loadBucketFiles();
    } else {
        showMessage('No bucket selected', 'error');
    }
}

// View file metadata
function viewMetadata(fileName) {
    logToConsole(`Viewing metadata for file: ${fileName}`);
    alert(`Metadata for: ${fileName}\\n\\nThis is a placeholder for full metadata functionality.\\nFile: ${fileName}\\nBucket: ${selectedBucket}\\nTimestamp: ${new Date().toISOString()}`);
}

// Download file
function downloadFile(fileName) {
    if (!selectedBucket) {
        showMessage('No bucket selected', 'error');
        return;
    }
    
    logToConsole(`Downloading file: ${fileName} from bucket: ${selectedBucket}`);
    const url = `/api/buckets/${selectedBucket}/download/${encodeURIComponent(fileName)}`;
    window.open(url, '_blank');
}

// Utility functions
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showMessage(message, type = 'info') {
    logToConsole(`Message (${type}): ${message}`);
    
    const messageArea = document.getElementById('message-area');
    const messageDiv = document.createElement('div');
    messageDiv.className = type === 'error' ? 'error' : (type === 'success' ? 'success' : 'info');
    messageDiv.textContent = message;
    messageArea.appendChild(messageDiv);
    
    // Remove message after 5 seconds
    setTimeout(() => {
        messageDiv.remove();
    }, 5000);
}
"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript')
        self.end_headers()
        self.wfile.write(js.encode('utf-8'))
    
    def serve_buckets_api(self):
        """Serve buckets API"""
        # Create sample data
        data_dir = Path.home() / ".ipfs_kit"
        buckets_dir = data_dir / "buckets"
        
        buckets = []
        if buckets_dir.exists():
            for bucket_path in buckets_dir.iterdir():
                if bucket_path.is_dir():
                    file_count = len(list(bucket_path.glob('*')))
                    buckets.append({
                        "name": bucket_path.name,
                        "backend": "local",
                        "description": f"Local bucket {bucket_path.name}",
                        "file_count": file_count,
                        "storage_used": 0,
                        "created_at": datetime.now().isoformat()
                    })
        
        # Add a sample bucket if none exist
        if not buckets:
            buckets = [{
                "name": "sample-bucket",
                "backend": "local", 
                "description": "Sample bucket for testing",
                "file_count": 0,
                "storage_used": 0,
                "created_at": datetime.now().isoformat()
            }]
        
        response_data = {"buckets": buckets}
        self.send_json_response(response_data)
    
    def serve_bucket_files_api(self, bucket_name):
        """Serve bucket files API"""
        data_dir = Path.home() / ".ipfs_kit"
        bucket_path = data_dir / "buckets" / bucket_name
        
        files = []
        if bucket_path.exists() and bucket_path.is_dir():
            for file_path in bucket_path.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        "name": file_path.name,
                        "size": stat.st_size,
                        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "path": file_path.name,
                        "type": "file"
                    })
        
        response_data = {"success": True, "files": files}
        self.send_json_response(response_data)
    
    def serve_overview_api(self):
        """Serve system overview API"""
        response_data = {
            "data": {
                "counts": {
                    "services_active": 1,
                    "backends": 1,
                    "buckets": 1
                }
            }
        }
        self.send_json_response(response_data)
    
    def handle_create_bucket(self):
        """Handle bucket creation"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            bucket_name = data.get('name')
            description = data.get('description', '')
            
            if not bucket_name:
                self.send_json_response({"success": False, "error": "Bucket name required"}, 400)
                return
            
            # Create bucket directory
            data_dir = Path.home() / ".ipfs_kit"
            bucket_path = data_dir / "buckets" / bucket_name
            bucket_path.mkdir(parents=True, exist_ok=True)
            
            # Create bucket config
            config_dir = data_dir / "bucket_configs"
            config_dir.mkdir(parents=True, exist_ok=True)
            
            bucket_config = {
                "name": bucket_name,
                "description": description,
                "backend": "local",
                "created_at": datetime.now().isoformat()
            }
            
            config_file = config_dir / f"{bucket_name}.json"
            with open(config_file, 'w') as f:
                json.dump(bucket_config, f, indent=2)
            
            logger.info(f"Created bucket: {bucket_name}")
            self.send_json_response({
                "success": True, 
                "message": f"Bucket '{bucket_name}' created successfully",
                "bucket": bucket_config
            })
            
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            self.send_json_response({"success": False, "error": str(e)}, 500)
    
    def handle_upload_file(self, bucket_name):
        """Handle file upload"""
        try:
            # Parse multipart form data (simplified)
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_json_response({"success": False, "error": "Multipart form data required"}, 400)
                return
            
            # This is a simplified multipart parser - in production use proper library
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # Extract boundary
            boundary = content_type.split('boundary=')[1].encode()
            parts = post_data.split(b'--' + boundary)
            
            for part in parts:
                if b'Content-Disposition: form-data' in part and b'filename=' in part:
                    # Extract filename
                    lines = part.split(b'\r\n')
                    filename = None
                    content_start = 0
                    
                    for i, line in enumerate(lines):
                        if b'filename=' in line:
                            filename_match = line.decode().split('filename="')[1].split('"')[0]
                            filename = filename_match
                        elif line == b'':
                            content_start = i + 1
                            break
                    
                    if filename and content_start > 0:
                        # Extract file content
                        file_content = b'\r\n'.join(lines[content_start:])
                        # Remove trailing boundary data
                        if file_content.endswith(b'\r\n'):
                            file_content = file_content[:-2]
                        
                        # Save file
                        data_dir = Path.home() / ".ipfs_kit"
                        bucket_path = data_dir / "buckets" / bucket_name
                        bucket_path.mkdir(parents=True, exist_ok=True)
                        
                        file_path = bucket_path / filename
                        with open(file_path, 'wb') as f:
                            f.write(file_content)
                        
                        logger.info(f"Uploaded file: {filename} to bucket: {bucket_name}")
                        self.send_json_response({
                            "success": True,
                            "message": f"File '{filename}' uploaded successfully",
                            "file": {
                                "name": filename,
                                "size": len(file_content),
                                "uploaded_at": datetime.now().isoformat()
                            }
                        })
                        return
            
            self.send_json_response({"success": False, "error": "No file found in upload"}, 400)
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            self.send_json_response({"success": False, "error": str(e)}, 500)
    
    def send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))


def run_dashboard(host='127.0.0.1', port=8004):
    """Run the test dashboard"""
    logger.info(f"Starting test dashboard on http://{host}:{port}")
    
    try:
        server = HTTPServer((host, port), DashboardHandler)
        logger.info(f"Dashboard running on http://{host}:{port}")
        logger.info("Press Ctrl+C to stop")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard stopped")
    except Exception as e:
        logger.error(f"Dashboard error: {e}")


if __name__ == "__main__":
    run_dashboard()