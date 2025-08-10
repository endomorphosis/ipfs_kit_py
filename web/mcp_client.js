(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.McpClient = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  class McpClient {
    constructor({ baseUrl, jsonRpcUrl, fetchImpl } = {}) {
      this.baseUrl = baseUrl ? baseUrl.replace(/\/$/, '') : null;
      this.jsonRpcUrl = jsonRpcUrl || (this.baseUrl ? this.baseUrl + '/api/jsonrpc' : null);
      this.fetch = fetchImpl || (typeof fetch !== 'undefined' ? fetch.bind(window) : null);
      if (!this.fetch) throw new Error('No fetch implementation available');
    }

    // Resolve best available transport: HTTP tools first, fallback to JSON-RPC
    _hasHttpTools() { return !!this.baseUrl; }

    async _rpc(method, params) {
      if (!this.jsonRpcUrl) throw new Error('jsonRpcUrl not configured');
      const body = { jsonrpc: '2.0', id: Date.now(), method, params: params || {} };
      const r = await this.fetch(this.jsonRpcUrl, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      });
      if (!r.ok) throw new Error(`RPC ${method} failed: ${r.status}`);
      const j = await r.json();
      if (j.error) throw new Error(j.error.message || 'RPC error');
      return j.result;
    }

    // System
    async status() {
      if (this._hasHttpTools()) {
        const r = await this.fetch(`${this.baseUrl}/status`);
        if (r.ok) return r.json();
      }
      return this._rpc('system.status');
    }

    // Tools
    async listTools() {
      if (this._hasHttpTools()) {
        const r = await this.fetch(`${this.baseUrl}/api/tools`);
        if (r.ok) return r.json();
      }
      const res = await this._rpc('tools.list');
      return res.tools || res;
    }

    async callTool(name, args = {}) {
      if (this._hasHttpTools()) {
        const r = await this.fetch(`${this.baseUrl}/tools/${encodeURIComponent(name)}`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ arguments: args })
        });
        if (r.ok) return r.json();
      }
      return this._rpc('tools.call', { tool: name, args });
    }

    // Convenience wrappers aligned with dashboard usage
    async getSystemOverview() { return this.callTool('get_system_overview'); }
    async getSystemStatus() { return this.callTool('get_system_status'); }

    async listServices() { return this.callTool('list_services'); }
    async controlService(service, action) { return this.callTool('control_service', { service, action }); }
  async startService(service_name) { return this.callTool('start_service', { service_name }); }
  async stopService(service_name) { return this.callTool('stop_service', { service_name }); }
  async restartService(service_name) { return this.callTool('restart_service', { service_name }); }
  async getAdvServicesData() { return this.callTool('get_adv_services_data'); }

    async listBackends() { return this.callTool('list_backends'); }
  async getAdvBackendsData() { return this.callTool('get_adv_backends_data'); }
  async getBackendHealth(backend_name) { return this.callTool('get_backend_health', { backend_name }); }
  async getBackendStats(backend_name) { return this.callTool('get_backend_stats', { backend_name }); }

    async listBuckets() { return this.callTool('list_buckets'); }
    async createBucket(name, backend) { return this.callTool('create_bucket', { name, backend }); }

    async listPins() { return this.callTool('list_pins'); }
    async createPin(cid, name) { return this.callTool('create_pin', { cid, name }); }

    async getLogs({ component = 'all', level = 'all', limit = 100 } = {}) {
      return this.callTool('get_logs', { component, level, limit });
    }

    async listFiles(path, bucket) { return this.callTool('list_files', { path, bucket }); }
    async readFile(path, bucket) { return this.callTool('read_file', { path, bucket }); }
  async writeFile(path, content, bucket) { return this.callTool('write_file', { path, content, bucket }); }

  // IPFS helpers
  async ipfsAdd(content) { return this.callTool('ipfs_add', { content }); }
  async ipfsGet(cid) { return this.callTool('ipfs_get', { cid }); }

  // Peers and analytics
  async listPeers() { return this.callTool('list_peers'); }
  async getSystemAnalytics() { return this.callTool('get_system_analytics'); }
  async getVfsOverviewData() { return this.callTool('get_vfs_overview_data'); }
  async getAdvPeersData() { return this.callTool('get_adv_peers_data'); }
  async connectPeer(peer_addr) { return this.callTool('connect_peer', { peer_addr }); }
  async disconnectPeer(peer_id) { return this.callTool('disconnect_peer', { peer_id }); }
  async getAdvAnalyticsData() { return this.callTool('get_adv_analytics_data'); }

  // Config files
  async getConfigFiles() { return this.callTool('get_config_files'); }
  async getConfigFileContent(filename) { return this.callTool('get_config_file_content', { filename }); }
  async saveConfigFileContent(filename, content) { return this.callTool('save_config_file_content', { filename, content }); }
  }

  // Helper to derive baseUrl from JSON-RPC like dashboard logic
  McpClient.deriveBaseUrl = function (jsonRpcUrl) {
    if (!jsonRpcUrl || typeof jsonRpcUrl !== 'string') return null;
    const u = jsonRpcUrl.replace(/\/$/, '');
    if (u.endsWith('/api/jsonrpc')) return u.slice(0, -'/api/jsonrpc'.length);
    return null;
  };

  return McpClient;
}));
