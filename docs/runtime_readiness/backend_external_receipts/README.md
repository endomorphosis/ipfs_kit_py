# Provider external receipts

This directory is the receipt authority for conditional or production provider
promotion.  It intentionally contains no active provider receipt: the backend
inventory must therefore remain configuration-only, unsupported, or
receipt-required in a fresh checkout.

A receipt is valid only when it conforms to `receipt.schema.json`, names a
declared backend type and its declared runtime factory, is currently within its
issued/expiry window, and records tests for storage operations plus rate,
timeout, retry, idempotency, and consistency semantics.  The code rejects
expired, malformed, mismatched, or credential-bearing records.

Receipts are evidence, not configuration.  They must not contain credentials,
secret-reference targets, endpoint account data, request bodies, or logs.
Credential references belong in authorized secret-management configuration and
are deliberately stripped before provider status, receipt, or runtime-promotion
records are created.

`index.json` is an explicit empty registry rather than evidence of a provider.
Adding an entry does not itself enable storage: a caller must load a current
receipt and separately register a repository-owned canonical runtime factory.
Standalone SDKs, MCP clients, and hermetic fixtures are never canonical
factories merely by being installed.
