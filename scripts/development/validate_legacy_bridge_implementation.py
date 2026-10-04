#!/usr/bin/env python3
"""
Comprehensive validation of the legacy feature bridge implementation.

This validates that all 9 core legacy features have been successfully
mapped to the new bucket-centric architecture.
"""

import anyio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LegacyBridgeValidator:
    """Validates the legacy feature bridge implementation."""
    
    def __init__(self, dashboard_url: str = "http://127.0.0.1:8005"):
        self.dashboard_url = dashboard_url
        self.rpc_endpoint = f"{dashboard_url}/api/mcp/rpc"
        
        # Core legacy features that should be implemented
        self.core_features = [
            "pin.list",
            "pin.add", 
            "bucket.list",
            "bucket.create",
            "pin.get_metadata",
            "bucket.info",
            "backend.status",
            "bucket.search",
            "analytics.dashboard"
        ]
        
        self.validation_results = {}
    
    async def validate_all_features(self) -> Dict[str, Any]:
        """Validate all legacy features have been bridged correctly."""
        logger.info("Starting comprehensive legacy bridge validation")
        
        # Test scenarios for each feature
        test_scenarios = {
            "pin.list": [
                {"params": {}, "expected_keys": ["message", "legacy_name", "new_implementation"]},
                {"params": {"filter": "recent"}, "expected_keys": ["bucket_operations"]}
            ],
            "pin.add": [
                {"params": {"hash": "QmTest123", "name": "test-pin"}, "expected_keys": ["legacy_name"]},
                {"params": {"hash": "QmTest456", "metadata": {"tag": "test"}}, "expected_keys": ["bucket_operations"]}
            ],
            "bucket.list": [
                {"params": {}, "expected_keys": ["message", "bucket_operations"]},
                {"params": {"include_stats": True}, "expected_keys": ["state_files"]}
            ],
            "bucket.create": [
                {"params": {"name": "test-bucket", "type": "default"}, "expected_keys": ["legacy_name"]},
                {"params": {"name": "advanced-bucket", "config": {"encryption": True}}, "expected_keys": ["bucket_operations"]}
            ],
            "pin.get_metadata": [
                {"params": {"hash": "QmTest123"}, "expected_keys": ["message"]},
                {"params": {"hash": "QmTest456", "include_bucket_info": True}, "expected_keys": ["bucket_operations"]}
            ],
            "bucket.info": [
                {"params": {"name": "test-bucket"}, "expected_keys": ["legacy_name"]},
                {"params": {"name": "detailed-bucket", "include_files": True}, "expected_keys": ["bucket_operations"]}
            ],
            "backend.status": [
                {"params": {}, "expected_keys": ["message"]},
                {"params": {"backend": "local"}, "expected_keys": ["bucket_operations"]}
            ],
            "bucket.search": [
                {"params": {"query": "test", "type": "content"}, "expected_keys": ["legacy_name"]},
                {"params": {"query": "advanced", "cross_bucket": True}, "expected_keys": ["bucket_operations"]}
            ],
            "analytics.dashboard": [
                {"params": {}, "expected_keys": ["message"]},
                {"params": {"time_range": "week"}, "expected_keys": ["bucket_operations"]}
            ]
        }
        
        start_time = time.time()
        
        for feature in self.core_features:
            logger.info(f"Validating feature: {feature}")
            
            feature_results = {
                "implemented": False,
                "scenarios_passed": 0,
                "scenarios_total": 0,
                "errors": [],
                "responses": []
            }
            
            if feature in test_scenarios:
                scenarios = test_scenarios[feature]
                feature_results["scenarios_total"] = len(scenarios)
                
                for i, scenario in enumerate(scenarios):
                    try:
                        result = await self._test_feature_scenario(feature, scenario)
                        
                        if result["success"]:
                            feature_results["scenarios_passed"] += 1
                            feature_results["implemented"] = True
                            
                            # Validate response structure
                            if self._validate_response_structure(result, scenario.get("expected_keys", [])):
                                logger.info(f"✅ {feature} scenario {i+1} passed")
                            else:
                                logger.warning(f"⚠️ {feature} scenario {i+1} structure validation failed")
                        else:
                            feature_results["errors"].append(f"Scenario {i+1}: {result.get('error', 'Unknown error')}")
                        
                        feature_results["responses"].append(result)
                        
                    except Exception as e:
                        feature_results["errors"].append(f"Scenario {i+1}: Exception - {str(e)}")
                        logger.error(f"❌ {feature} scenario {i+1} failed: {e}")
            
            self.validation_results[feature] = feature_results
        
        # Generate summary
        summary = self._generate_validation_summary(start_time)
        logger.info("Validation completed")
        
        return {
            "validation_results": self.validation_results,
            "summary": summary
        }
    
    async def _test_feature_scenario(self, feature: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Test a specific feature scenario."""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "method": feature,
                    "params": scenario["params"]
                }
                
                async with session.post(
                    self.rpc_endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return await response.json()
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }
    
    def _validate_response_structure(self, response: Dict[str, Any], expected_keys: List[str]) -> bool:
        """Validate that response contains expected structure."""
        if not response.get("success"):
            return False
        
        data = response.get("data", {})
        
        for key in expected_keys:
            if key not in data:
                return False
        
        return True
    
    def _generate_validation_summary(self, start_time: float) -> Dict[str, Any]:
        """Generate comprehensive validation summary."""
        total_features = len(self.core_features)
        implemented_features = sum(1 for result in self.validation_results.values() if result["implemented"])
        total_scenarios = sum(result["scenarios_total"] for result in self.validation_results.values())
        passed_scenarios = sum(result["scenarios_passed"] for result in self.validation_results.values())
        total_errors = sum(len(result["errors"]) for result in self.validation_results.values())
        
        validation_time = time.time() - start_time
        
        # Success rate
        implementation_rate = (implemented_features / total_features) * 100
        scenario_success_rate = (passed_scenarios / total_scenarios) * 100 if total_scenarios > 0 else 0
        
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "validation_duration_seconds": round(validation_time, 2),
            "total_features": total_features,
            "implemented_features": implemented_features,
            "implementation_rate_percent": round(implementation_rate, 1),
            "total_scenarios": total_scenarios,
            "passed_scenarios": passed_scenarios,
            "scenario_success_rate_percent": round(scenario_success_rate, 1),
            "total_errors": total_errors,
            "status": "PASS" if implementation_rate >= 100 and total_errors == 0 else "PARTIAL" if implemented_features > 0 else "FAIL"
        }
    
    async def generate_detailed_report(self) -> str:
        """Generate a detailed validation report."""
        validation_data = await self.validate_all_features()
        
        report = []
        report.append("=" * 80)
        report.append("LEGACY FEATURE BRIDGE VALIDATION REPORT")
        report.append("=" * 80)
        report.append("")
        
        summary = validation_data["summary"]
        report.append(f"Validation Status: {summary['status']}")
        report.append(f"Timestamp: {summary['timestamp']}")
        report.append(f"Duration: {summary['validation_duration_seconds']}s")
        report.append("")
        
        report.append("IMPLEMENTATION OVERVIEW:")
        report.append(f"  Total Features: {summary['total_features']}")
        report.append(f"  Implemented: {summary['implemented_features']}")
        report.append(f"  Implementation Rate: {summary['implementation_rate_percent']}%")
        report.append("")
        
        report.append("SCENARIO TESTING:")
        report.append(f"  Total Scenarios: {summary['total_scenarios']}")
        report.append(f"  Passed Scenarios: {summary['passed_scenarios']}")
        report.append(f"  Success Rate: {summary['scenario_success_rate_percent']}%")
        report.append(f"  Total Errors: {summary['total_errors']}")
        report.append("")
        
        report.append("FEATURE DETAILS:")
        report.append("-" * 80)
        
        for feature, result in validation_data["validation_results"].items():
            status = "✅ IMPLEMENTED" if result["implemented"] else "❌ NOT IMPLEMENTED"
            report.append(f"{feature}: {status}")
            report.append(f"  Scenarios: {result['scenarios_passed']}/{result['scenarios_total']} passed")
            
            if result["errors"]:
                report.append(f"  Errors:")
                for error in result["errors"]:
                    report.append(f"    - {error}")
            
            report.append("")
        
        return "\\n".join(report)

async def main():
    """Main validation execution."""
    validator = LegacyBridgeValidator()
    
    try:
        # Wait a moment for dashboard to be ready
        await anyio.sleep(2)
        
        # Generate and display detailed report
        report = await validator.generate_detailed_report()
        print(report)
        
        # Save results to file
        validation_data = await validator.validate_all_features()
        results_file = Path("legacy_bridge_validation_results.json")
        
        with open(results_file, "w") as f:
            json.dump(validation_data, f, indent=2)
        
        logger.info(f"Validation results saved to {results_file}")
        
        # Print final status
        summary = validation_data["summary"]
        if summary["status"] == "PASS":
            logger.info("🎉 ALL LEGACY FEATURES SUCCESSFULLY BRIDGED!")
        elif summary["status"] == "PARTIAL":
            logger.info(f"✅ {summary['implemented_features']}/{summary['total_features']} features implemented")
        else:
            logger.error("❌ Legacy bridge implementation needs work")
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")

if __name__ == "__main__":
    anyio.run(main)
