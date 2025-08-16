/*
MCP SDK (Browser/Node UMD)
Lightweight client for MCP JSON-RPC servers and dashboard helpers.
Attaches to window.MCP in browsers or exports module in Node.
*/
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.MCP = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DEFAULT_TIMEOUT_MS = 15000;

  function withTimeout(promise, ms, controller) {
    let to;
    const timeout = new Promise((_, reject) => {
      to = setTimeout(() => {
        if (controller) controller.abort();
        reject(new Error('Request timed out'));
      }, ms);
    });
    return Promise.race([promise, timeout]).finally(() => clearTimeout(to));
  }

  class MCPClient {
    constructor(options = {}) {
      this.baseUrl = (options.baseUrl || '').replace(/\/$/, '');
      this.timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;
      this.headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
  // Tool registry and dynamic API
  this._tools = null; // array of tool defs
  this._toolMap = {}; // name -> def
  this.tools = {};    // namespace of generated stubs (exact names)
  this.api = this.tools; // alias for clarity
  this.toolsCamel = {};  // camelCase aliases

  // Interceptors/hooks
  this._before = [];
  this._after = [];
  this._error = [];
  this._listeners = { toolsUpdated: [] };
    }

    async rpc(method, params = {}, id = Date.now()) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : undefined;
      const body = JSON.stringify({ jsonrpc: '2.0', method, params, id });
      const url = this.baseUrl + (method.startsWith('tools/') ? '/mcp/' + method : '/mcp/' + method);
      const req = fetch(url, { method: 'POST', headers: this.headers, body, signal: controller && controller.signal });
      const res = await withTimeout(req, this.timeoutMs, controller);
      const json = await res.json();
      if (!res.ok) throw new Error(json && json.error ? json.error.message || 'RPC error' : 'RPC HTTP error');
      if (json.error) throw new Error(json.error.message || 'RPC error');
      return json.result;
    }

    // Tools
    async toolsList() { return this.rpc('tools/list'); }
    async toolsCall(name, args = {}) { return this.rpc('tools/call', { name, arguments: args, }); }

    // Discover tools and build stubs
    async discoverTools(force = false) {
      if (this._tools && !force) return this._tools;
      const res = await this.toolsList();
      const tools = (res && res.tools) || [];
      this._tools = tools;
      this._toolMap = {};
      for (const t of tools) this._toolMap[t.name] = t;
      this._emit('toolsUpdated', tools);
      return tools;
    }

    // Create named functions under this.tools and camelCase aliases under this.toolsCamel
    async bindToolStubs({ overwrite = false } = {}) {
      const tools = await this.discoverTools();
      for (const t of tools) {
        const name = t.name;
        const camel = name.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
        if (!overwrite && this.tools[name]) continue;
        const fn = async (args = {}) => {
          this._validateArgs(name, t.inputSchema, args);
          return this._callWithInterceptors(name, args);
        };
        this.tools[name] = fn;
        this.toolsCamel[camel] = fn; // alias
        // Also attach convenience method on client instance if safe
        if (overwrite || typeof this[name] === 'undefined') {
          Object.defineProperty(this, name, { value: fn, enumerable: false });
        }
      }
      return this.tools;
    }

    // Centralized call with hooks
    async _callWithInterceptors(name, args) {
      const ctx = { name, args, client: this };
      for (const h of this._before) {
        try { await h(ctx); } catch (_) { /* ignore */ }
      }
      try {
        const result = await this.toolsCall(name, args);
        ctx.result = result;
        for (const h of this._after) {
          try { await h(ctx); } catch (_) { /* ignore */ }
        }
        return result;
      } catch (err) {
        ctx.error = err;
        for (const h of this._error) {
          try { await h(ctx); } catch (_) { /* ignore */ }
        }
        throw err;
      }
    }

    // Basic schema-based validation (checks required+types when provided)
    _validateArgs(name, schema, args) {
      if (!schema || typeof schema !== 'object') return;
      const req = Array.isArray(schema.required) ? schema.required : [];
      for (const k of req) {
        if (!(k in args)) throw new Error(`Missing required argument '${k}' for tool '${name}'`);
      }
      const props = schema.properties || {};
      for (const key of Object.keys(args || {})) {
        if (!props[key] || !props[key].type) continue;
        const t = props[key].type;
        const v = args[key];
        if (t === 'integer' && typeof v !== 'number') throw new Error(`Argument '${key}' must be integer`);
        if (t === 'number' && typeof v !== 'number') throw new Error(`Argument '${key}' must be number`);
        if (t === 'string' && typeof v !== 'string') throw new Error(`Argument '${key}' must be string`);
        if (t === 'boolean' && typeof v !== 'boolean') throw new Error(`Argument '${key}' must be boolean`);
        if (t === 'object' && (v === null || typeof v !== 'object' || Array.isArray(v))) throw new Error(`Argument '${key}' must be object`);
        if (t === 'array' && !Array.isArray(v)) throw new Error(`Argument '${key}' must be array`);
      }
    }

    // Introspection helpers
    getToolNames() { return this._tools ? this._tools.map(t => t.name) : []; }
    hasTool(name) { return !!this._toolMap[name]; }
    getToolSchema(name) { return this._toolMap[name] ? this._toolMap[name].inputSchema : undefined; }
    describeTools() { return this._tools ? this._tools.map(t => ({ name: t.name, description: t.description, inputSchema: t.inputSchema })) : []; }

    // Hooks API
    addBeforeHook(fn) { this._before.push(fn); return () => this._remove(this._before, fn); }
    addAfterHook(fn) { this._after.push(fn); return () => this._remove(this._after, fn); }
    addErrorHook(fn) { this._error.push(fn); return () => this._remove(this._error, fn); }
    on(event, fn) { (this._listeners[event] = this._listeners[event] || []).push(fn); return () => this._remove(this._listeners[event], fn); }
    _emit(event, data) { (this._listeners[event] || []).forEach(fn => { try { fn(data); } catch (_) {} }); }
    _remove(arr, fn) { const i = arr.indexOf(fn); if (i >= 0) arr.splice(i, 1); }

    // System helpers (dashboard adjunct endpoints)
    async systemStatus() { return this._get('/api/mcp/status'); }
    async systemHealth() { return this._get('/api/system/health'); }
    
    // Service management helpers
    async listServices() { return this._get('/api/services/list'); }
    async getServiceStatus(serviceName) { return this._get(`/api/services/${serviceName}/status`); }
    async startService(serviceName) { return this._post(`/api/services/${serviceName}/start`, {}); }
    async stopService(serviceName) { return this._post(`/api/services/${serviceName}/stop`, {}); }
    async addService(serviceName, config) { return this._post('/api/services/add', { name: serviceName, config }); }
    async removeService(serviceName) { return this._delete(`/api/services/${serviceName}`); }
    async updateServiceConfig(serviceName, config) { return this._put(`/api/services/${serviceName}/config`, config); }
    async getServiceConfig(serviceName) { return this._get(`/api/services/${serviceName}/config`); }
    async getServiceStats(serviceName) { return this._get(`/api/services/${serviceName}/stats`); }
    async getAllServicesStatus() { return this._get('/api/services/status'); }
    
    // Monitoring helpers
    async getMonitoringData(serviceName, metricType) { 
      let url = `/api/monitoring/${serviceName}`;
      if (metricType) url += `/${metricType}`;
      return this._get(url);
    }
    async getQuotaInfo(serviceName) { return this._get(`/api/services/${serviceName}/quota`); }
    async getStorageInfo(serviceName) { return this._get(`/api/services/${serviceName}/storage`); }
    async getBackendStats() { return this._get('/api/backends/stats'); }

    // Files/logs helpers
    streamLogs(onMessage, onError) {
      const url = this.baseUrl + '/api/logs/stream';
      if (typeof EventSource === 'undefined') {
        throw new Error('EventSource not supported in this environment');
      }
      const es = new EventSource(url);
      es.onmessage = (evt) => {
        try { onMessage && onMessage(JSON.parse(evt.data)); }
        catch (_) { /* ignore parse errors */ }
      };
      es.onerror = (err) => { onError && onError(err); };
      return () => { try { es.close(); } catch (_) {} };
    }

    // WebSocket helpers
    connectWebSocket(path = '/ws', handlers = {}) {
      const protocol = (typeof window !== 'undefined' && window.location && window.location.protocol === 'https:') ? 'wss:' : 'ws:';
      const host = (typeof window !== 'undefined' && window.location) ? window.location.host : '';
      const url = this.baseUrl ? this.baseUrl.replace(/^http/, 'ws') + path : `${protocol}//${host}${path}`;
      const ws = new (typeof WebSocket !== 'undefined' ? WebSocket : require('ws'))(url);
      if (handlers.onOpen) ws.onopen = handlers.onOpen;
      if (handlers.onClose) ws.onclose = handlers.onClose;
      if (handlers.onError) ws.onerror = handlers.onError;
      ws.onmessage = (evt) => {
        try { const data = JSON.parse(evt.data); handlers.onMessage && handlers.onMessage(data); }
        catch (_) { handlers.onMessage && handlers.onMessage(evt.data); }
      };
      return ws;
    }

    // Low-level HTTP methods
    async _get(path) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : undefined;
      const req = fetch(this.baseUrl + path, { method: 'GET', headers: this.headers, signal: controller && controller.signal });
      const res = await withTimeout(req, this.timeoutMs, controller);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }
    
    async _post(path, data) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : undefined;
      const req = fetch(this.baseUrl + path, { 
        method: 'POST', 
        headers: this.headers, 
        body: JSON.stringify(data),
        signal: controller && controller.signal 
      });
      const res = await withTimeout(req, this.timeoutMs, controller);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }
    
    async _put(path, data) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : undefined;
      const req = fetch(this.baseUrl + path, { 
        method: 'PUT', 
        headers: this.headers, 
        body: JSON.stringify(data),
        signal: controller && controller.signal 
      });
      const res = await withTimeout(req, this.timeoutMs, controller);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }
    
    async _delete(path) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : undefined;
      const req = fetch(this.baseUrl + path, { method: 'DELETE', headers: this.headers, signal: controller && controller.signal });
      const res = await withTimeout(req, this.timeoutMs, controller);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }
  }

  // Dashboard UI helper class for service management
  class ServiceDashboard {
    constructor(client, options = {}) {
      this.client = client;
      this.container = options.container || document.body;
      this.refreshInterval = options.refreshInterval || 5000;
      this.autoRefresh = options.autoRefresh !== false;
      this._intervalId = null;
      this._services = {};
    }

    async init() {
      await this.render();
      if (this.autoRefresh) {
        this.startAutoRefresh();
      }
    }

    async render() {
      const services = await this.client.getAllServicesStatus();
      this._services = services;
      
      const html = `
        <div class="service-dashboard">
          <div class="dashboard-header">
            <h2>Service Management</h2>
            <div class="dashboard-actions">
              <button id="refresh-btn" class="btn btn-primary">Refresh</button>
              <button id="add-service-btn" class="btn btn-success">Add Service</button>
            </div>
          </div>
          <div class="services-grid">
            ${Object.entries(services).map(([name, status]) => this.renderServiceCard(name, status)).join('')}
          </div>
        </div>
      `;
      
      this.container.innerHTML = html;
      this.bindEvents();
    }

    renderServiceCard(name, status) {
      const statusClass = status.status === 'running' ? 'success' : 
                         status.status === 'error' ? 'danger' : 'warning';
      
      return `
        <div class="service-card" data-service="${name}">
          <div class="card-header">
            <h3>${name}</h3>
            <span class="status-badge status-${statusClass}">${status.status}</span>
          </div>
          <div class="card-body">
            <div class="service-info">
              <div class="info-item">
                <label>Type:</label>
                <span>${status.type || 'unknown'}</span>
              </div>
              <div class="info-item">
                <label>Last Updated:</label>
                <span>${new Date(status.last_updated).toLocaleString()}</span>
              </div>
            </div>
            <div class="service-actions">
              <button class="btn btn-sm ${status.status === 'running' ? 'btn-warning' : 'btn-success'}" 
                      data-action="${status.status === 'running' ? 'stop' : 'start'}" 
                      data-service="${name}">
                ${status.status === 'running' ? 'Stop' : 'Start'}
              </button>
              <button class="btn btn-sm btn-info" data-action="config" data-service="${name}">Config</button>
              <button class="btn btn-sm btn-secondary" data-action="stats" data-service="${name}">Stats</button>
              <button class="btn btn-sm btn-danger" data-action="remove" data-service="${name}">Remove</button>
            </div>
          </div>
        </div>
      `;
    }

    bindEvents() {
      // Refresh button
      const refreshBtn = this.container.querySelector('#refresh-btn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => this.render());
      }

      // Add service button
      const addBtn = this.container.querySelector('#add-service-btn');
      if (addBtn) {
        addBtn.addEventListener('click', () => this.showAddServiceModal());
      }

      // Service action buttons
      this.container.addEventListener('click', async (e) => {
        const action = e.target.dataset.action;
        const serviceName = e.target.dataset.service;
        
        if (!action || !serviceName) return;
        
        try {
          switch (action) {
            case 'start':
              await this.client.startService(serviceName);
              break;
            case 'stop':
              await this.client.stopService(serviceName);
              break;
            case 'config':
              this.showConfigModal(serviceName);
              return;
            case 'stats':
              this.showStatsModal(serviceName);
              return;
            case 'remove':
              if (confirm(`Are you sure you want to remove service ${serviceName}?`)) {
                await this.client.removeService(serviceName);
              }
              break;
          }
          
          // Refresh the display
          setTimeout(() => this.render(), 1000);
        } catch (error) {
          alert(`Action failed: ${error.message}`);
        }
      });
    }

    showAddServiceModal() {
      const modal = document.createElement('div');
      modal.className = 'modal-overlay';
      modal.innerHTML = `
        <div class="modal">
          <div class="modal-header">
            <h3>Add Service</h3>
            <button class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <form id="add-service-form">
              <div class="form-group">
                <label>Service Type:</label>
                <select name="serviceType" required>
                  <option value="">Select service type...</option>
                  <option value="ipfs">IPFS</option>
                  <option value="ipfs_cluster">IPFS Cluster</option>
                  <option value="s3">S3</option>
                  <option value="storacha">Storacha</option>
                  <option value="huggingface">HuggingFace</option>
                  <option value="ftp">FTP</option>
                  <option value="sshfs">SSHFS</option>
                  <option value="lotus">Lotus</option>
                  <option value="synapse">Synapse</option>
                  <option value="parquet">Parquet</option>
                  <option value="arrow">Arrow</option>
                  <option value="github">GitHub</option>
                </select>
              </div>
              <div class="form-group">
                <label>Configuration (JSON):</label>
                <textarea name="config" rows="6" placeholder='{"key": "value"}'></textarea>
              </div>
              <div class="form-actions">
                <button type="submit" class="btn btn-primary">Add Service</button>
                <button type="button" class="btn btn-secondary modal-cancel">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      `;
      
      document.body.appendChild(modal);
      
      // Bind modal events
      modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
      modal.querySelector('.modal-cancel').addEventListener('click', () => modal.remove());
      modal.querySelector('#add-service-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const serviceType = formData.get('serviceType');
        const configText = formData.get('config');
        
        let config = {};
        if (configText) {
          try {
            config = JSON.parse(configText);
          } catch (error) {
            alert('Invalid JSON configuration');
            return;
          }
        }
        
        try {
          await this.client.addService(serviceType, config);
          modal.remove();
          setTimeout(() => this.render(), 1000);
        } catch (error) {
          alert(`Failed to add service: ${error.message}`);
        }
      });
    }

    async showConfigModal(serviceName) {
      const config = await this.client.getServiceConfig(serviceName);
      
      const modal = document.createElement('div');
      modal.className = 'modal-overlay';
      modal.innerHTML = `
        <div class="modal">
          <div class="modal-header">
            <h3>Configure ${serviceName}</h3>
            <button class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <form id="config-form">
              <div class="form-group">
                <label>Configuration (JSON):</label>
                <textarea name="config" rows="10">${JSON.stringify(config, null, 2)}</textarea>
              </div>
              <div class="form-actions">
                <button type="submit" class="btn btn-primary">Update Config</button>
                <button type="button" class="btn btn-secondary modal-cancel">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      `;
      
      document.body.appendChild(modal);
      
      // Bind modal events
      modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
      modal.querySelector('.modal-cancel').addEventListener('click', () => modal.remove());
      modal.querySelector('#config-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const configText = formData.get('config');
        
        try {
          const newConfig = JSON.parse(configText);
          await this.client.updateServiceConfig(serviceName, newConfig);
          modal.remove();
          setTimeout(() => this.render(), 1000);
        } catch (error) {
          alert(`Failed to update config: ${error.message}`);
        }
      });
    }

    async showStatsModal(serviceName) {
      const stats = await this.client.getServiceStats(serviceName);
      
      const modal = document.createElement('div');
      modal.className = 'modal-overlay';
      modal.innerHTML = `
        <div class="modal">
          <div class="modal-header">
            <h3>Statistics for ${serviceName}</h3>
            <button class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <pre>${JSON.stringify(stats, null, 2)}</pre>
          </div>
        </div>
      `;
      
      document.body.appendChild(modal);
      modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
    }

    startAutoRefresh() {
      if (this._intervalId) {
        clearInterval(this._intervalId);
      }
      this._intervalId = setInterval(() => this.render(), this.refreshInterval);
    }

    stopAutoRefresh() {
      if (this._intervalId) {
        clearInterval(this._intervalId);
        this._intervalId = null;
      }
    }

    destroy() {
      this.stopAutoRefresh();
      this.container.innerHTML = '';
    }
  }

  function createClient(options) { return new MCPClient(options); }
  function createServiceDashboard(client, options) { return new ServiceDashboard(client, options); }

  return { 
    MCPClient, 
    ServiceDashboard, 
    createClient, 
    createServiceDashboard 
  };
}));
