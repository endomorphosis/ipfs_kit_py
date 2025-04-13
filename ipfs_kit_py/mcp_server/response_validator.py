"""
MCP Server Response Validator

This module provides response validation functionality for the MCP Server
blue/green deployment, enabling automatic comparison of responses from
blue and green implementations.
"""

import json
import logging
import difflib
import time
from typing import Dict, Any, Optional, List, Union, Tuple, Set, Callable

# Configure logging
logger = logging.getLogger(__name__)

class ResponseValidator:
    """
    Response validator for comparing blue and green server responses.
    
    This validator helps ensure compatibility between implementations by:
    1. Comparing response structure and content
    2. Calculating similarity scores
    3. Identifying critical differences
    4. Providing recommendations for rollout decisions
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the response validator with the given configuration.
        
        Args:
            config: Dictionary containing configuration options
        """
        self.config = config or {}
        
        # Fields to ignore during comparison (e.g., timestamps, response_id)
        self.ignored_fields = set(self.config.get("ignored_fields", [
            "timestamp", 
            "response_id", 
            "request_time",
            "server_id"
        ]))
        
        # Fields that must be identical for responses to be considered compatible
        self.critical_fields = set(self.config.get("critical_fields", [
            "success",
            "cid",
            "data_size",
            "error_code"
        ]))
        
        # Acceptable threshold for non-critical differences (as a percentage)
        self.similarity_threshold = self.config.get("similarity_threshold", 90.0)
        
        # History of validations performed
        self.validation_history = []
        
        # Statistics
        self.stats = {
            "total_validations": 0,
            "identical_responses": 0,
            "compatible_responses": 0,  # Different but acceptable
            "incompatible_responses": 0,
            "critical_differences": 0
        }
        
        logger.info("Response validator initialized")
    
    def validate(
        self, 
        blue_response: Dict[str, Any], 
        green_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate and compare responses from blue and green servers.
        
        Args:
            blue_response: Response from the blue server
            green_response: Response from the green server
            
        Returns:
            Dict containing validation results, including:
            - identical: Whether responses are exactly identical
            - compatible: Whether responses are functionally equivalent
            - similarity: Similarity score as a percentage
            - differences: List of differences found
            - critical_difference: Whether any critical fields differ
        """
        self.stats["total_validations"] += 1
        
        # Convert to strings for basic identity check
        try:
            blue_str = json.dumps(blue_response, sort_keys=True)
            green_str = json.dumps(green_response, sort_keys=True)
            
            # Check if responses are identical
            identical = (blue_str == green_str)
            if identical:
                self.stats["identical_responses"] += 1
                result = {
                    "identical": True,
                    "compatible": True,
                    "similarity": 100.0,
                    "differences": [],
                    "critical_difference": False
                }
                self._add_to_history(blue_response, green_response, result)
                return result
        except Exception as e:
            logger.error(f"Error during basic comparison: {e}")
            # Fall back to detailed comparison if JSON conversion fails
        
        # Perform detailed comparison
        try:
            # Find differences
            differences = self._find_differences(blue_response, green_response)
            
            # Calculate similarity score
            similarity = self._calculate_similarity(blue_response, green_response, differences)
            
            # Check for critical differences
            critical_fields_diff = self._check_critical_differences(differences)
            
            # Determine compatibility
            compatible = (
                similarity >= self.similarity_threshold and 
                not critical_fields_diff
            )
            
            if compatible and not critical_fields_diff:
                self.stats["compatible_responses"] += 1
            else:
                self.stats["incompatible_responses"] += 1
                
            if critical_fields_diff:
                self.stats["critical_differences"] += 1
            
            result = {
                "identical": False,
                "compatible": compatible,
                "similarity": similarity,
                "differences": differences,
                "critical_difference": critical_fields_diff,
                "critical_fields": list(critical_fields_diff) if critical_fields_diff else []
            }
            
            self._add_to_history(blue_response, green_response, result)
            return result
            
        except Exception as e:
            logger.error(f"Error during detailed validation: {e}")
            
            # Return error result
            result = {
                "identical": False,
                "compatible": False,
                "similarity": 0.0,
                "differences": [f"Validation error: {str(e)}"],
                "critical_difference": True,
                "error": str(e)
            }
            
            self._add_to_history(blue_response, green_response, result, error=str(e))
            return result
    
    def _find_differences(
        self, 
        blue_obj: Any, 
        green_obj: Any, 
        path: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Recursively find differences between two objects.
        
        Args:
            blue_obj: Object from blue response
            green_obj: Object from green response
            path: Current path in the object structure
            
        Returns:
            List of differences, each with path and values
        """
        differences = []
        
        # If path refers to an ignored field, skip comparison
        if path in self.ignored_fields:
            return differences
        
        # Handle different types
        if type(blue_obj) != type(green_obj):
            differences.append({
                "path": path,
                "blue_type": type(blue_obj).__name__,
                "green_type": type(green_obj).__name__,
                "blue_value": blue_obj,
                "green_value": green_obj
            })
            return differences
        
        # Handle dictionaries
        if isinstance(blue_obj, dict):
            # Find keys in blue but not in green
            for key in blue_obj:
                if key not in green_obj:
                    differences.append({
                        "path": f"{path}.{key}" if path else key,
                        "difference_type": "missing_in_green",
                        "blue_value": blue_obj[key]
                    })
                else:
                    # Recurse for common keys
                    nested_path = f"{path}.{key}" if path else key
                    if nested_path not in self.ignored_fields:
                        differences.extend(
                            self._find_differences(blue_obj[key], green_obj[key], nested_path)
                        )
            
            # Find keys in green but not in blue
            for key in green_obj:
                if key not in blue_obj:
                    differences.append({
                        "path": f"{path}.{key}" if path else key,
                        "difference_type": "missing_in_blue",
                        "green_value": green_obj[key]
                    })
        
        # Handle lists
        elif isinstance(blue_obj, list):
            if len(blue_obj) != len(green_obj):
                differences.append({
                    "path": path,
                    "difference_type": "list_length",
                    "blue_length": len(blue_obj),
                    "green_length": len(green_obj)
                })
            
            # Compare elements up to common length
            for i in range(min(len(blue_obj), len(green_obj))):
                nested_path = f"{path}[{i}]"
                differences.extend(
                    self._find_differences(blue_obj[i], green_obj[i], nested_path)
                )
        
        # Handle other types (strings, numbers, etc.)
        elif blue_obj != green_obj:
            differences.append({
                "path": path,
                "difference_type": "value",
                "blue_value": blue_obj,
                "green_value": green_obj
            })
        
        return differences
    
    def _calculate_similarity(
        self, 
        blue_obj: Any, 
        green_obj: Any, 
        differences: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate similarity score between two objects.
        
        Args:
            blue_obj: Object from blue response
            green_obj: Object from green response
            differences: List of differences found
            
        Returns:
            Similarity score as a percentage (0-100)
        """
        # Convert to strings for sequence comparison
        try:
            blue_str = json.dumps(blue_obj, sort_keys=True)
            green_str = json.dumps(green_obj, sort_keys=True)
            
            # Use difflib's SequenceMatcher for similarity ratio
            import difflib
            matcher = difflib.SequenceMatcher(None, blue_str, green_str)
            return matcher.ratio() * 100
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            
            # If string comparison fails, use difference count as a fallback
            if not differences:
                return 100.0
            
            # Count total fields in blue_obj
            def count_fields(obj, ignored_paths=None):
                ignored_paths = ignored_paths or set()
                if isinstance(obj, dict):
                    count = 0
                    for k, v in obj.items():
                        if k not in ignored_paths:
                            count += 1
                            count += count_fields(v)
                    return count
                elif isinstance(obj, list):
                    return sum(count_fields(item) for item in obj)
                else:
                    return 0
            
            total_fields = max(1, count_fields(blue_obj, self.ignored_fields))
            difference_ratio = len(differences) / total_fields
            return max(0, (1 - difference_ratio) * 100)
    
    def _check_critical_differences(
        self, 
        differences: List[Dict[str, Any]]
    ) -> Set[str]:
        """
        Check if any critical fields have differences.
        
        Args:
            differences: List of differences found
            
        Returns:
            Set of critical fields that differ, empty if none
        """
        critical_diffs = set()
        
        for diff in differences:
            path = diff.get("path", "")
            
            # Check if the path itself is a critical field
            if path in self.critical_fields:
                critical_diffs.add(path)
                continue
            
            # Check if the path contains a critical field
            for field in self.critical_fields:
                # Check for exact path match
                if path == field:
                    critical_diffs.add(field)
                # Check for field as part of a path (e.g., "data.success")
                elif f".{field}" in path or path.startswith(f"{field}."):
                    critical_diffs.add(field)
        
        return critical_diffs
    
    def _add_to_history(
        self, 
        blue_response: Dict[str, Any], 
        green_response: Dict[str, Any],
        result: Dict[str, Any],
        error: str = None
    ) -> None:
        """
        Add validation result to history.
        
        Args:
            blue_response: Response from blue server
            green_response: Response from green server
            result: Validation result
            error: Error message if validation failed
        """
        # Limit history size to avoid memory growth
        if len(self.validation_history) >= 100:
            self.validation_history.pop(0)
        
        # Add to history with timestamp
        self.validation_history.append({
            "timestamp": time.time(),
            "blue_response_summary": self._summarize_response(blue_response),
            "green_response_summary": self._summarize_response(green_response),
            "result": result,
            "error": error
        })
    
    def _summarize_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summarized version of a response for history storage."""
        if not isinstance(response, dict):
            return {"value": str(response)}
        
        # Extract key fields, but limit large values
        summary = {}
        for key, value in response.items():
            if key in self.critical_fields:
                summary[key] = value
            elif isinstance(value, dict) and len(value) > 0:
                summary[key] = "{...}" 
            elif isinstance(value, list) and len(value) > 0:
                summary[key] = f"[{len(value)} items]"
            elif isinstance(value, str) and len(value) > 100:
                summary[key] = value[:97] + "..."
            else:
                summary[key] = value
        
        return summary
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get validation statistics.
        
        Returns:
            Dict containing validation statistics
        """
        total = max(1, self.stats["total_validations"])
        
        return {
            "total_validations": self.stats["total_validations"],
            "identical_rate": (self.stats["identical_responses"] / total) * 100,
            "compatible_rate": (
                (self.stats["identical_responses"] + self.stats["compatible_responses"]) / total
            ) * 100,
            "incompatible_rate": (self.stats["incompatible_responses"] / total) * 100,
            "critical_difference_rate": (self.stats["critical_differences"] / total) * 100,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> Dict[str, Any]:
        """Generate recommendations based on validation statistics."""
        total = max(1, self.stats["total_validations"])
        identical_rate = (self.stats["identical_responses"] / total) * 100
        compatible_rate = (
            (self.stats["identical_responses"] + self.stats["compatible_responses"]) / total
        ) * 100
        critical_diff_rate = (self.stats["critical_differences"] / total) * 100
        
        if total < 10:
            return {
                "action": "gather_more_data",
                "confidence": "low",
                "message": "Not enough validations to make a recommendation."
            }
        
        if identical_rate > 99:
            return {
                "action": "green_safe",
                "confidence": "high",
                "message": "Responses are identical. Safe to switch to green."
            }
        
        if compatible_rate > 99 and critical_diff_rate == 0:
            return {
                "action": "green_safe",
                "confidence": "medium",
                "message": "Responses are functionally equivalent. Safe to switch to green."
            }
        
        if compatible_rate > 95 and critical_diff_rate < 1:
            return {
                "action": "increase_green_traffic",
                "confidence": "medium",
                "message": "Responses are mostly compatible. Can gradually increase green traffic."
            }
        
        if compatible_rate > 90 and critical_diff_rate < 5:
            return {
                "action": "monitor",
                "confidence": "medium",
                "message": "Some differences exist. Keep traffic split and monitor."
            }
        
        if critical_diff_rate > 10:
            return {
                "action": "rollback",
                "confidence": "high",
                "message": "Too many critical differences. Recommend rolling back to blue."
            }
        
        return {
            "action": "investigate",
            "confidence": "medium",
            "message": "Significant differences detected. Investigate before proceeding."
        }
    
    def get_recent_validations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent validation results.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of recent validation results
        """
        return self.validation_history[-limit:][::-1]