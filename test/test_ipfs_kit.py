import tempfile
import os
import platform
import json
from ipfs_kit_py import storacha_kit
from ipfs_kit_py import ipfs_kit

class TestIpfsKit:
    def __init__(self, resources, metadata):
        self.metadata = metadata
        self.resources = resources
        self.ipfs_kit = ipfs_kit(resources, metadata)
        self.storacha_kit = storacha_kit(resources, metadata)
        return None
        
    def test(self):
        results = {}
        test_ipfs_kit_install = None
        test_ipfs_kit = None
        test_ipfs_kit_stop = None
        test_ipfs_kit_start = None
        test_ipfs_kit_ready = None
        test_ipfs_kit_get_config = None
        test_ipfs_kit_set_config = None
        test_ipfs_kit_get_config_value = None
        test_ipfs_kit_set_config_value = None
        test_ipfs_kit_get_pinset = None
        test_ipfs_kit_add_pin = None
        test_ipfs_kit_remove_pin = None
        test_ipfs_kit_upload_object = None
        test_ipfs_kit_download_object = None
        test_ipfs_kit_name_resolve = None
        test_ipfs_kit_name_publish = None
        test_ipfs_kit_add_path = None
        test_ipfs_kit_ls_path = None
        test_ipfs_kit_remove_path = None
        test_ipfs_kit_get = None
        test_ipfs_kit_get_pinset = None
        test_ipfs_kit_load_collection = None
        test_ipfs_kit_update_collection_ipfs = None
        test_ipfs_kit_check_collection = None
        test_ipfs_kit_ipfs_get_config = None
        test_ipfs_kit_ipfs_set_config = None
        test_ipfs_kit_ipfs_get_config_value = None
        test_ipfs_kit_ipfs_set_config_value = None
        test_ipfs_kit_storacha_kit = None
        try:
            results["test_install"] = self.test_install()
        except Exception as e:
            results["test_install"] = e
        try:
            results["test_ipfs_kit_stop"] = self.ipfs_kit_stop()
        except Exception as e:
            results["test_ipfs_kit_stop"] = e
        try:
            results["test_ipfs_kit_start"] = self.ipfs_kit_start()
        except Exception as e:
            results["test_ipfs_kit_start"] = e
        try:
            results["test_ipfs_kit_ready"] = self.ipfs_kit_ready()
        except Exception as e:
            results["test_ipfs_kit_ready"] = e
        try:
            results["test_ipfs_kit_get_config"] = self.ipfs_get_config()
        except Exception as e:
            results["test_ipfs_kit_get_config"] = e
        try:
            results["test_ipfs_kit_set_config"] = self.ipfs_set_config()
        except Exception as e:
            results["test_ipfs_kit_set_config"] = e
        try:
            results["test_ipfs_kit_get_config_value"] = self.ipfs_get_config_value()
        except Exception as e:
            results["test_ipfs_kit_get_config_value"] = e
        try:
            results["test_ipfs_kit_set_config_value"] = self.ipfs_set_config_value()
        except Exception as e:
            results["test_ipfs_kit_set_config_value"] = e
        try:    
            results["test_ipfs_kit_get_pinset"] = self.ipfs_get_pinset()
        except Exception as e:
            results["test_ipfs_kit_get_pinset"] = e
        try:
            results["test_ipfs_kit_add_pin"] = self.ipfs_add_pin()
        except Exception as e:
            results["test_ipfs_kit_add_pin"] = e
        try:
            results["test_ipfs_kit_remove_pin"] = self.ipfs_remove_pin()
        except Exception as e:
            results["test_ipfs_kit_remove_pin"] = e
        try:
            results["test_ipfs_kit_upload_object"] = self.ipfs_upload_object()
        except Exception as e:
            results["test_ipfs_kit_upload_object"] = e
        try:
            results["test_ipfs_kit_download_object"] = self.ipget_download_object()
        except Exception as e:
            results["test_ipfs_kit_download_object"] = e
        try:
            results["test_ipfs_kit_name_resolve"] = self.name_resolve()
        except Exception as e:
            results["test_ipfs_kit_name_resolve"] = e
        try:
            results["test_ipfs_kit_name_publish"] = self.name_publish()
        except Exception as e:
            results["test_ipfs_kit_name_publish"] = e
        try:
            results["test_ipfs_kit_add_path"] = self.ipfs_add_path()
        except Exception as e:
            results["test_ipfs_kit_add_path"] = e
        try:
            results["test_ipfs_kit_ls_path"] = self.ipfs_ls_path()
        except Exception as e:
            results["test_ipfs_kit_ls_path"] = e
        try:
            results["test_ipfs_kit_remove_path"] = self.ipfs_remove_path()
        except Exception as e:
            results["test_ipfs_kit_remove_path"] = e
        try:
            results["test_ipfs_kit_get"] = self.ipfs_get()
        except Exception as e:
            results["test_ipfs_kit_get"] = e
        try:
            results["test_ipfs_kit_storacha_kit"] = self.storacha_kit.test()
        except Exception as e:
            results["test_ipfs_kit_storacha_kit"] = e                
        try:
            results["test_ipfs_kit"] = self.test()
        except Exception as e:
            results["test_ipfs_kit"] = e
        return results
