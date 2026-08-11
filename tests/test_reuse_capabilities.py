from ipfs_kit_py.test_reuse_capabilities import TestReuseCapabilities


def test_capability_probe_is_lazy_and_not_proof_authority():
    calls = []
    capabilities = TestReuseCapabilities(which=lambda name: calls.append(name) or None)
    assert calls == []
    assert capabilities.can_authorize_proof() is False
    assert capabilities.probe("ipfs").available is False
    assert calls == ["ipfs"]

