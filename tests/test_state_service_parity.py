#!/usr/bin/env python3
import json
from pathlib import Path
from ipfs_kit_py.services.state_service import StateService


def test_state_service_bucket_persistence(tmp_path: Path):
    svc = StateService(data_dir=tmp_path)
    assert (tmp_path / 'buckets.json').exists()

    # Initially empty
    assert svc.list_buckets() == []

    # Create and persist
    b = svc.create_bucket('demo', 'local')
    assert b['name'] == 'demo'
    assert b['backend'] == 'local'

    # Read back
    buckets = svc.list_buckets()
    assert any(x.get('name') == 'demo' for x in buckets)


def test_state_service_pin_persistence(tmp_path: Path):
    svc = StateService(data_dir=tmp_path)
    assert (tmp_path / 'pins.json').exists()

    # Initially empty
    assert svc.list_pins() == []

    # Create and persist
    p = svc.create_pin('bafy...cid', 'test')
    assert p['cid'].startswith('bafy')

    # Read back
    pins = svc.list_pins()
    assert any(x.get('cid') == 'bafy...cid' for x in pins)
