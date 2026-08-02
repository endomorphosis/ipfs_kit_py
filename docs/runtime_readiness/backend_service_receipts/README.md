# Backend service certification receipts

The promoted S3-compatible, Kubo/IPFS, and Iroh adapters are inert on
construction.  A `passed` receipt is issued only after the declared operations
have contacted the configured service; missing or unreachable services issue a
`blocked` receipt and never select a local or mock fallback.

S3 aliases identify the shared S3-compatible protocol only.  They do not
certify provider-specific control-plane APIs or turn a provider token into an
S3 signing credential.  Iroh certification additionally performs local RPC
health and capability negotiation, while its receipt records namespace and
cross-namespace move limits.

`mcp_default_manager_status.json` is deliberately blocked.  The known default
MCP IPFS registration constructor mismatch is outside this task's authorized
adapter edit paths, so it must not be represented as a passing certification.
