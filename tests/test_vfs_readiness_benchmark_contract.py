#!/usr/bin/env python3
"""Contract test for VFS readiness benchmark helper."""

from ipfs_kit_py.vfs_readiness_benchmark import run_vfs_readiness_benchmark


def test_vfs_readiness_benchmark_small_sample_contract():
    result = run_vfs_readiness_benchmark(
        samples=5,
        queue_wait_timeout_sec=5.0,
        mutation_p95_threshold_ms=2000.0,
        queue_lag_p95_threshold_ms=5000.0,
    )

    assert isinstance(result, dict)
    assert "metrics" in result
    assert "thresholds" in result
    assert result["samples"] == 5
    assert result["metrics"]["mutation_ms"]["p95"] >= 0.0
    assert result["metrics"]["queue_lag_ms"]["p95"] >= 0.0
    assert result["success"] is True
