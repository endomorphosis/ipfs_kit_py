# Advanced Cluster Authentication

Securing communication and operations within an `ipfs-kit-py` cluster is crucial. The `ClusterAuthManager` class in `cluster_authentication.py` provides mechanisms for authenticating nodes and authorizing actions.

## Overview

Cluster authentication ensures that only trusted nodes can join the cluster, participate in state synchronization, execute tasks, and access sensitive information. It employs several strategies:

**Key Concepts:**

*   **Mutual TLS (mTLS)**: Nodes use X.509 certificates to authenticate each other during connection establishment. Each node needs a private key and a certificate signed by a trusted Cluster Certificate Authority (CA). This verifies the identity of both the connecting node and the node being connected to.
*   **UCANs (User-Controlled Authorization Networks)**: A decentralized authorization scheme based on signed capabilities. Nodes can generate UCAN tokens granting specific permissions (e.g., "pin content", "execute task type X") to other nodes or clients. These tokens are verifiable without a central authority.
*   **Cluster Auth Tokens**: Potentially simpler, internally generated tokens (possibly JWTs or opaque tokens) used for authorizing specific RPC calls or operations within the cluster after initial authentication (e.g., via mTLS).
*   **Access Control Lists (ACLs) / Capability Checks**: Logic within the cluster coordinator or manager verifies if the authenticated peer (identified via its certificate or token claims) has the necessary permissions to perform a requested operation.

## Implementation (`ClusterAuthManager`)

The `ClusterAuthManager` centralizes authentication and authorization logic:

*   **Initialization**: Loads or generates necessary cryptographic materials (CA certificate, node certificate/key, UCAN keys, auth tokens) based on the node's role (Master, Worker, Leecher) and configuration.
*   **Certificate Management**: Handles generation of CA and node certificates, saving/loading them, and verifying peer certificates against the trusted CA.
*   **UCAN Management**: Generates the node's DID (Decentralized Identifier) from its key pair, issues UCAN tokens with specific capabilities and audiences, and verifies received UCANs.
*   **Token Management**: Issues, verifies, and potentially revokes cluster-specific authentication tokens.
*   **Secure Connection Establishment**: Integrates with the underlying networking layer (e.g., libp2p) to enforce mTLS during peer connections.
*   **RPC Security**: Provides methods to wrap or verify RPC calls, ensuring the caller is authenticated and authorized.
*   **Capability Enforcement**: Contains logic or hooks to check if a peer is authorized for a specific operation based on its role, certificate identity, or token claims.

## Configuration

Authentication settings are configured under the `cluster.authentication` key:

```python
# Example configuration snippet
config = {
    'cluster': {
        'authentication': {
            'enabled': True,
            'mode': 'mtls_ucan', # e.g., 'mtls', 'ucan', 'mtls_ucan'
            'ca_cert_path': '~/.ipfs_kit/cluster/ca.crt',
            'node_cert_path': '~/.ipfs_kit/cluster/node.crt',
            'node_key_path': '~/.ipfs_kit/cluster/node.key',
            'ucan_key_path': '~/.ipfs_kit/cluster/ucan.key',
            'generate_certs_if_missing': True, # Auto-generate certs on first run
            'token_secret': 'LOAD_FROM_ENV_OR_SECURE_STORE', # For cluster auth tokens if used
            'required_capabilities': { # Example access control
                 'pin_content': ['Master', 'Worker'],
                 'execute_gpu_task': ['Worker[gpu=true]'] # Role/capability check
            }
        }
        # ... other cluster config
    }
    # ... other ipfs-kit-py config
}
```

**Security Notes:**

*   Protect private keys (`node_key_path`, `ucan_key_path`) and token secrets diligently. Use appropriate file permissions and consider loading secrets from environment variables or secure vaults.
*   Securely distribute the CA certificate (`ca_cert_path`) to all legitimate cluster nodes.

## Workflow Examples

*   **Node Joining (mTLS)**:
    1.  New node attempts to connect to an existing cluster node.
    2.  Both nodes exchange certificates during the TLS handshake.
    3.  Each node verifies the other's certificate against its trusted CA certificate (`ca_cert_path`).
    4.  If verification succeeds on both sides, the secure connection is established.
*   **Task Execution (UCAN)**:
    1.  Master node wants Worker node B to execute a task.
    2.  Master generates a UCAN token granting Worker B the capability to execute that specific task type, setting Worker B's DID as the audience.
    3.  Master sends the task request along with the UCAN token to Worker B (over the mTLS connection).
    4.  Worker B verifies the UCAN token (checks signature, audience, capabilities, expiry).
    5.  If valid, Worker B executes the task.
*   **RPC Call (Cluster Token)**:
    1.  Worker node A needs to report status to the Master node via an RPC call.
    2.  Worker A includes its pre-issued cluster auth token in the RPC request header.
    3.  Master node receives the request, extracts the token, and verifies it (checks signature, expiry, claims).
    4.  If valid, the Master processes the RPC call.

## Benefits

*   **Strong Identity Verification**: mTLS ensures nodes are who they claim to be.
*   **Decentralized Authorization**: UCANs allow fine-grained permission delegation without a central authority.
*   **Defense in Depth**: Combining multiple methods (e.g., mTLS + UCANs) provides layered security.

## Considerations

*   **Complexity**: Managing certificates (generation, distribution, revocation) and UCANs adds operational overhead compared to simpler authentication methods.
*   **Key Management**: Secure storage and handling of private keys are critical.
*   **Clock Skew**: Systems relying on time-based tokens (JWTs, UCANs with expiry) require reasonably synchronized clocks across nodes.
