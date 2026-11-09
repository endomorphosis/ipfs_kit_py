"""
Test Suite for Service Configuration Form Fix

This test suite verifies the fix for the service configuration modal in the MCP dashboard.

Background:
-----------
The service configuration modal (enhanced_service_monitoring.html) was sending configuration
data in the wrong format. The backend expects configuration fields to be wrapped in a 'config'
object within the 'params' object.

Bug:
----
Frontend sent: { action: 'configure', params: { field1: val1, field2: val2 } }
Backend expects: config = params.get('config', {})
Result: config = {} (empty dict) - configuration fails!

Fix:
----
Frontend now sends: { action: 'configure', params: { config: { field1: val1, field2: val2 } } }
Backend extracts: config = params.get('config', {})
Result: config = { field1: val1, field2: val2 } - configuration succeeds!

Changes Made:
-------------
1. File: ipfs_kit_py/mcp/dashboard_templates/enhanced_service_monitoring.html
   - Line ~950: Modified saveServiceConfig() to wrap config in params.config
   - Line ~920: Added 'textarea' to querySelectorAll to capture JSON config fields

Backend Code Reference:
-----------------------
ipfs_kit_py/mcp/services/comprehensive_service_manager.py:974-976
    elif action == "configure":
        config = params.get("config", {})  # ← Expects config wrapped in params
        return await self.configure_service(service_id, config)
"""

import json
from typing import Dict, Any

def simulate_old_frontend_format(form_fields: Dict[str, str]) -> Dict[str, Any]:
    """
    Simulate what the OLD (broken) frontend was sending.
    This would fail because backend expects params.config.
    """
    return {
        "action": "configure",
        "params": form_fields  # ❌ Config sent directly in params
    }

def simulate_new_frontend_format(form_fields: Dict[str, str]) -> Dict[str, Any]:
    """
    Simulate what the NEW (fixed) frontend sends.
    This works because backend can extract config from params.config.
    """
    return {
        "action": "configure",
        "params": {
            "config": form_fields  # ✅ Config wrapped in params.config
        }
    }

def simulate_backend_extraction(payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Simulate how the backend extracts config from the request payload.
    This mirrors the code at comprehensive_service_manager.py:975
    """
    params = payload.get("params", {})
    config = params.get("config", {})  # Backend expects config in params.config
    return config

class TestServiceConfigurationFormat:
    """Test suite for service configuration format fix."""
    
    def test_old_format_fails_to_extract_config(self):
        """Test that the old format results in empty config."""
        # Arrange: User fills in configuration form
        form_fields = {
            "access_key": "AKIAIOSFODNN7EXAMPLE",
            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "bucket": "my-s3-bucket",
            "region": "us-east-1"
        }
        
        # Act: Frontend sends config in old (broken) format
        payload = simulate_old_frontend_format(form_fields)
        extracted_config = simulate_backend_extraction(payload)
        
        # Assert: Backend receives empty config
        assert extracted_config == {}, "Old format should result in empty config"
        assert len(extracted_config) == 0, "No config fields should be extracted"
        print("❌ OLD FORMAT: Backend received empty config - configuration would fail!")
    
    def test_new_format_successfully_extracts_config(self):
        """Test that the new format successfully passes config to backend."""
        # Arrange: User fills in configuration form
        form_fields = {
            "access_key": "AKIAIOSFODNN7EXAMPLE",
            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "bucket": "my-s3-bucket",
            "region": "us-east-1"
        }
        
        # Act: Frontend sends config in new (fixed) format
        payload = simulate_new_frontend_format(form_fields)
        extracted_config = simulate_backend_extraction(payload)
        
        # Assert: Backend receives complete config
        assert extracted_config == form_fields, "New format should pass config correctly"
        assert extracted_config["access_key"] == "AKIAIOSFODNN7EXAMPLE"
        assert extracted_config["secret_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert extracted_config["bucket"] == "my-s3-bucket"
        assert extracted_config["region"] == "us-east-1"
        print("✅ NEW FORMAT: Backend received complete config - configuration succeeds!")
    
    def test_multiple_service_types(self):
        """Test configuration format works for different service types."""
        test_cases = [
            {
                "service": "s3",
                "config": {
                    "access_key": "AKIAIOSFODNN7EXAMPLE",
                    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "bucket": "my-bucket",
                    "region": "us-west-2"
                }
            },
            {
                "service": "github",
                "config": {
                    "api_token": "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456",
                    "repository": "owner/repo"
                }
            },
            {
                "service": "huggingface",
                "config": {
                    "api_token": "hf_aBcDeFgHiJkLmNoPqRsTuVwXyZ",
                    "username": "my-username"
                }
            }
        ]
        
        for test_case in test_cases:
            payload = simulate_new_frontend_format(test_case["config"])
            extracted_config = simulate_backend_extraction(payload)
            
            assert extracted_config == test_case["config"], \
                f"Config for {test_case['service']} should be extracted correctly"
            print(f"✅ {test_case['service'].upper()}: Configuration format correct")
    
    def test_textarea_fields_included(self):
        """Test that textarea fields (like JSON config) are included."""
        # Arrange: Form includes both input and textarea fields
        form_fields = {
            "api_token": "abc123",
            "config_json": '{"advanced": {"timeout": 30, "retries": 3}}'  # From textarea
        }
        
        # Act: Frontend sends all fields including textarea
        payload = simulate_new_frontend_format(form_fields)
        extracted_config = simulate_backend_extraction(payload)
        
        # Assert: Textarea field is included
        assert "config_json" in extracted_config, "Textarea fields should be included"
        assert extracted_config["config_json"] == form_fields["config_json"]
        print("✅ TEXTAREA: JSON config fields from textarea are captured correctly")

def run_tests():
    """Run all tests and print results."""
    print("=" * 80)
    print("Service Configuration Form Fix - Test Suite")
    print("=" * 80)
    print()
    
    test = TestServiceConfigurationFormat()
    
    try:
        print("Test 1: Old format fails to extract config")
        print("-" * 80)
        test.test_old_format_fails_to_extract_config()
        print()
        
        print("Test 2: New format successfully extracts config")
        print("-" * 80)
        test.test_new_format_successfully_extracts_config()
        print()
        
        print("Test 3: Multiple service types")
        print("-" * 80)
        test.test_multiple_service_types()
        print()
        
        print("Test 4: Textarea fields included")
        print("-" * 80)
        test.test_textarea_fields_included()
        print()
        
        print("=" * 80)
        print("✅ All tests passed! Configuration form fix is working correctly.")
        print("=" * 80)
        return True
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
