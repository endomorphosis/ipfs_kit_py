// Type definitions for MCP SDK UMD
// Minimal declarations to aid autocomplete and documentation.

export interface McpToolDef {
  name: string;
  description: string;
  inputSchema?: any;
}

export interface HookContext {
  name: string;
  args: Record<string, any>;
  client: MCPClient;
  result?: any;
  error?: any;
}

export type Unsubscribe = () => void;

export interface ConnectWsHandlers {
  onOpen?: (ev: any) => void;
  onClose?: (ev: any) => void;
  onError?: (ev: any) => void;
  onMessage?: (data: any) => void;
}

export interface MCPClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
  headers?: Record<string, string>;
}

export class MCPClient {
  constructor(options?: MCPClientOptions);
  baseUrl: string;
  timeoutMs: number;
  headers: Record<string, string>;

  // Core RPC
  rpc(method: string, params?: any, id?: number): Promise<any>;

  // Tools
  toolsList(): Promise<{ tools: McpToolDef[] } | any>;
  toolsCall(name: string, args?: Record<string, any>): Promise<any>;
  discoverTools(force?: boolean): Promise<McpToolDef[]>;
  bindToolStubs(opts?: { overwrite?: boolean }): Promise<Record<string, (args?: Record<string, any>) => Promise<any>>>;

  // Introspection
  getToolNames(): string[];
  hasTool(name: string): boolean;
  getToolSchema(name: string): any;
  describeTools(): Array<{ name: string; description: string; inputSchema: any }>;

  // Hooks
  addBeforeHook(fn: (ctx: HookContext) => any | Promise<any>): Unsubscribe;
  addAfterHook(fn: (ctx: HookContext) => any | Promise<any>): Unsubscribe;
  addErrorHook(fn: (ctx: HookContext) => any | Promise<any>): Unsubscribe;
  on(event: 'toolsUpdated', fn: (tools: McpToolDef[]) => any): Unsubscribe;

  // Helpers
  systemStatus(): Promise<any>;
  systemHealth(): Promise<any>;
  streamLogs(onMessage: (msg: any) => void, onError?: (err: any) => void): Unsubscribe;
  connectWebSocket(path?: string, handlers?: ConnectWsHandlers): WebSocket;
}

export function createClient(options?: MCPClientOptions): MCPClient;

declare global {
  interface Window {
    MCP: { MCPClient: typeof MCPClient; createClient: typeof createClient };
    mcpClient?: MCPClient;
  }
}
