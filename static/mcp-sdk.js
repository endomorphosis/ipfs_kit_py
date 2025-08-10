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

    // Low-level GET
    async _get(path) {
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : undefined;
      const req = fetch(this.baseUrl + path, { method: 'GET', headers: this.headers, signal: controller && controller.signal });
      const res = await withTimeout(req, this.timeoutMs, controller);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }
  }

  function createClient(options) { return new MCPClient(options); }

  return { MCPClient, createClient };
}));
