# Named Iroh backends

Iroh is registered as the `iroh` named storage backend. Registry discovery is
side-effect free: it does not resolve credentials, connect to the RPC endpoint,
create Iroh state, or start a managed service.

Use [`config/iroh-backend.example.yaml`](../../config/iroh-backend.example.yaml)
as the version-1 shape. The persisted document is closed and validated before
every create, update, adapter construction, or migration. Unknown settings,
inline credentials, non-local RPC endpoints, malformed namespace IDs, and
impossible policy combinations are rejected.

```python
import yaml
from ipfs_kit_py.backend_manager import BackendManager

manager = BackendManager()
document = yaml.safe_load(open("config/iroh-backend.example.yaml"))
manager.create_backend(document.pop("name"), document.pop("type"), config=document)

info = manager.get_backend_info("team_archive")
print(info["capabilities"], info["health"])
```

`show_backend`, `list_backends`, create/update results, health probes, and
backend info redact credential-reference identifiers. Internal consumers may
request `get_backend_config(name, redact=False)` to resolve an opaque reference
at the last responsible moment. Resolved values must never be written back.

## Migrating legacy YAML

The migration accepts the historical flat Iroh fields and converts them to the
version-1 nested schema. For example:

```yaml
name: team_archive
type: iroh
namespace_id: a4d26868017c0ccffe2efe50944ef42125f9b8692f2a8f46f5f7d6c483ad127a
rpc_endpoint: unix:///run/user/1000/ipfs-kit-iroh.sock
instance: primary
node_key_ref: secretref:environment:IROH_NODE_KEY
write_capability_ref: secretref:environment:IROH_WRITE_CAPABILITY
```

Preview it by calling `validate_backend_config(document, migrate=True)`. To
rewrite persisted configuration atomically, keeping an owner-only backup:

```console
ipfs-kit-backend-migrate team_archive
```

Omit the name to migrate every backend. Existing non-Iroh backend documents
remain valid and unchanged. Migration rejects inline secrets and unknown fields
rather than guessing or silently dropping them. A second migration is
idempotent and reports `Backend already current`.
