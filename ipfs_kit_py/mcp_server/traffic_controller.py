"""
MCP Server Traffic Controller

This module provides traffic management functionality for the MCP Server
blue/green deployment, enabling dynamic adjustment of traffic distribution
based on performance metrics and response validation.
"""

import logging
import time
import random
import math
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Tuple, Callable

# Configure logging
logger = logging.getLogger(__name__)

class TrafficAction(Enum):
    """Actions that can be taken by the traffic controller."""
    MAINTAIN = "maintain"  # Keep current traffic distribution
    INCREASE_GREEN = "increase_green"  # Increase traffic to green
    DECREASE_GREEN = "decrease_green"  # Decrease traffic to green
    ALL_BLUE = "all_blue"  # Route all traffic to blue (rollback)
    ALL_GREEN = "all_green"  # Route all traffic to green (complete migration)

class TrafficController:
    """
    Traffic controller for managing blue/green traffic distribution.
    
    This controller dynamically adjusts the traffic split between blue and green
    servers based on performance metrics, health checks, and response validation.
    It implements various strategies for gradual rollout and automatic rollback.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the traffic controller with the given configuration.
        
        Args:
            config: Dictionary containing configuration options
        """
        self.config = config or {}
        
        # Traffic distribution (percentage to green)
        self.green_percentage = self.config.get("initial_green_percentage", 0)
        
        # Traffic step size for adjustments
        self.step_size = self.config.get("step_size", 5)
        
        # Safety thresholds
        self.safety_thresholds = self.config.get("safety_thresholds", {
            "min_success_rate": 99.0,  # Minimum success rate to maintain/increase green
            "max_error_rate_increase": 1.0,  # Max acceptable increase in error rate
            "max_latency_increase": 20.0,  # Max acceptable latency increase (%)
            "critical_error_threshold": 5.0  # Error rate that triggers rollback
        })
        
        # Automatic configuration
        self.auto_config = self.config.get("auto", {
            "enabled": True,
            "evaluation_interval": 300,  # Seconds between automatic adjustments
            "promotion_delay": 1800,  # Seconds to wait before increasing traffic
            "rollback_delay": 0,  # Seconds to wait before decreasing traffic
            "max_green_percentage": 100,  # Maximum green percentage in auto mode
            "gradual_rampup": True  # Whether to use gradual or aggressive ramp-up
        })
        
        # Validation requirements
        self.validation_config = self.config.get("validation", {
            "enabled": True,
            "min_validation_count": 50,  # Minimum validations before using results
            "min_compatible_rate": 99.0,  # Minimum compatible rate to increase green
            "max_critical_diff_rate": 0.1  # Maximum critical difference rate allowed
        })
        
        # State tracking
        self.state = {
            "last_evaluation_time": time.time(),
            "last_adjustment_time": time.time(),
            "adjustment_history": [],
            "steady_state_time": time.time(),
            "error_detected": False,
            "error_detection_time": None,
            "promotion_eligible": False,
            "promotion_eligibility_time": None
        }
        
        # Initialize control limits based on current traffic level
        self._update_control_limits()
        
        logger.info(f"Traffic controller initialized with {self.green_percentage}% green traffic")
    
    def _update_control_limits(self) -> None:
        """Update control limits based on current traffic level."""
        # Traffic levels control adjustment size - lower step size at higher green percentages
        if self.green_percentage < 20:
            self.step_size = self.config.get("step_size", 5)
        elif self.green_percentage < 50:
            self.step_size = self.config.get("step_size", 5) * 0.8
        elif self.green_percentage < 80:
            self.step_size = self.config.get("step_size", 5) * 0.6
        else:
            self.step_size = self.config.get("step_size", 5) * 0.4
        
        # Ensure step size is at least 1%
        self.step_size = max(1.0, self.step_size)
    
    def evaluate(
        self, 
        metrics: Dict[str, Any], 
        validation_stats: Optional[Dict[str, Any]] = None
    ) -> TrafficAction:
        """
        Evaluate metrics and determine the appropriate traffic action.
        
        Args:
            metrics: Metrics from the metrics collector
            validation_stats: Statistics from the response validator (optional)
            
        Returns:
            TrafficAction indicating what adjustment to make
        """
        # Update last evaluation time
        self.state["last_evaluation_time"] = time.time()
        
        # If auto mode is disabled, always maintain current traffic distribution
        if not self.auto_config.get("enabled", True):
            return TrafficAction.MAINTAIN
        
        # Check if green server is healthy
        if not metrics.get("green", {}).get("health", {}).get("status", False):
            logger.warning("Green server is unhealthy, routing traffic to blue")
            self.state["error_detected"] = True
            self.state["error_detection_time"] = time.time()
            return TrafficAction.ALL_BLUE
        
        # Check for critical error rate
        green_error_rate = 100 - metrics.get("green", {}).get("success_rate", 100)
        if green_error_rate > self.safety_thresholds.get("critical_error_threshold", 5.0):
            logger.warning(f"Green error rate {green_error_rate}% exceeds critical threshold, reducing traffic")
            self.state["error_detected"] = True
            self.state["error_detection_time"] = time.time()
            return TrafficAction.DECREASE_GREEN
        
        # Check validation stats if validation is enabled and stats are provided
        if (self.validation_config.get("enabled", True) and 
            validation_stats and 
            validation_stats.get("total_validations", 0) >= self.validation_config.get("min_validation_count", 50)):
            
            compatible_rate = validation_stats.get("compatible_rate", 100)
            critical_diff_rate = validation_stats.get("critical_difference_rate", 0)
            
            # Check if validation results are acceptable
            if (compatible_rate < self.validation_config.get("min_compatible_rate", 99.0) or
                critical_diff_rate > self.validation_config.get("max_critical_diff_rate", 0.1)):
                
                logger.warning(
                    f"Validation results unacceptable: compatible_rate={compatible_rate}%, "
                    f"critical_diff_rate={critical_diff_rate}%"
                )
                self.state["error_detected"] = True
                self.state["error_detection_time"] = time.time()
                return TrafficAction.DECREASE_GREEN
        
        # Check performance comparison
        blue_perf = metrics.get("blue", {})
        green_perf = metrics.get("green", {})
        
        if blue_perf and green_perf:
            blue_success_rate = blue_perf.get("success_rate", 100)
            green_success_rate = green_perf.get("success_rate", 100)
            
            blue_resp_time = blue_perf.get("avg_response_time", 0)
            green_resp_time = green_perf.get("avg_response_time", 0)
            
            # Calculate performance differences
            success_rate_diff = green_success_rate - blue_success_rate
            
            # Latency difference as a percentage
            if blue_resp_time > 0:
                latency_diff_pct = ((green_resp_time - blue_resp_time) / blue_resp_time) * 100
            else:
                latency_diff_pct = 0
            
            # Check if green performance is acceptable
            if (green_success_rate < self.safety_thresholds.get("min_success_rate", 99.0) or
                success_rate_diff < -self.safety_thresholds.get("max_error_rate_increase", 1.0) or
                latency_diff_pct > self.safety_thresholds.get("max_latency_increase", 20.0)):
                
                logger.warning(
                    f"Green performance below threshold: success_rate={green_success_rate}%, "
                    f"success_diff={success_rate_diff}%, latency_diff={latency_diff_pct}%"
                )
                self.state["error_detected"] = True
                self.state["error_detection_time"] = time.time()
                return TrafficAction.DECREASE_GREEN
        
        # If we get here, no issues have been detected
        if self.state["error_detected"]:
            # Reset error state as we've detected recovery
            logger.info("Green server has recovered from previous errors")
            self.state["error_detected"] = False
            self.state["error_detection_time"] = None
            self.state["steady_state_time"] = time.time()
            return TrafficAction.MAINTAIN
        
        # Check if we should promote (increase green traffic)
        if not self.state["promotion_eligible"]:
            # Check if we've been in steady state long enough to be eligible for promotion
            steady_state_duration = time.time() - self.state["steady_state_time"]
            promotion_delay = self.auto_config.get("promotion_delay", 1800)
            
            if steady_state_duration >= promotion_delay:
                logger.info(f"Green server has been stable for {steady_state_duration:.0f} seconds, eligible for promotion")
                self.state["promotion_eligible"] = True
                self.state["promotion_eligibility_time"] = time.time()
        
        # If green traffic is already at max, maintain or promote to all green
        if self.green_percentage >= self.auto_config.get("max_green_percentage", 100):
            if (self.green_percentage >= 100 or
                self.auto_config.get("max_green_percentage", 100) <= self.green_percentage):
                return TrafficAction.ALL_GREEN
            else:
                return TrafficAction.MAINTAIN
        
        # If eligible for promotion, increase green traffic
        if self.state["promotion_eligible"]:
            logger.info(f"Increasing green traffic from {self.green_percentage}%")
            return TrafficAction.INCREASE_GREEN
        
        # Otherwise maintain current distribution
        return TrafficAction.MAINTAIN
    
    def adjust_traffic(self, action: TrafficAction) -> Dict[str, Any]:
        """
        Adjust traffic distribution based on the given action.
        
        Args:
            action: TrafficAction to perform
            
        Returns:
            Dict containing the new traffic distribution
        """
        old_percentage = self.green_percentage
        
        if action == TrafficAction.MAINTAIN:
            # No change
            pass
        
        elif action == TrafficAction.INCREASE_GREEN:
            # Increase green traffic by step size
            self.green_percentage = min(100, self.green_percentage + self.step_size)
            self.state["last_adjustment_time"] = time.time()
            
            # If we're at 100%, consider migration complete
            if self.green_percentage >= 100:
                logger.info("Green traffic at 100%, migration complete")
                self.green_percentage = 100
        
        elif action == TrafficAction.DECREASE_GREEN:
            # Decrease green traffic by step size
            self.green_percentage = max(0, self.green_percentage - self.step_size)
            self.state["last_adjustment_time"] = time.time()
            self.state["promotion_eligible"] = False
            
            # If we're back to 0%, migration has been rolled back
            if self.green_percentage <= 0:
                logger.info("Green traffic at 0%, migration rolled back")
                self.green_percentage = 0
        
        elif action == TrafficAction.ALL_BLUE:
            # Route all traffic to blue
            self.green_percentage = 0
            self.state["last_adjustment_time"] = time.time()
            self.state["promotion_eligible"] = False
            logger.info("Routing all traffic to blue (rollback)")
        
        elif action == TrafficAction.ALL_GREEN:
            # Route all traffic to green
            self.green_percentage = 100
            self.state["last_adjustment_time"] = time.time()
            logger.info("Routing all traffic to green (migration complete)")
        
        # Record adjustment in history
        if self.green_percentage != old_percentage:
            self.state["adjustment_history"].append({
                "timestamp": time.time(),
                "action": action.value,
                "old_percentage": old_percentage,
                "new_percentage": self.green_percentage
            })
            
            # Limit history size
            if len(self.state["adjustment_history"]) > 100:
                self.state["adjustment_history"].pop(0)
            
            # Update control limits based on new traffic level
            self._update_control_limits()
        
        return {
            "green_percentage": self.green_percentage,
            "action": action.value,
            "changed": self.green_percentage != old_percentage
        }
    
    def get_traffic_split(self) -> Dict[str, float]:
        """
        Get the current traffic split between blue and green.
        
        Returns:
            Dict with blue_percentage and green_percentage
        """
        return {
            "blue_percentage": 100 - self.green_percentage,
            "green_percentage": self.green_percentage
        }
    
    def should_route_to_green(self) -> bool:
        """
        Determine if a specific request should be routed to green.
        
        Returns:
            True if request should go to green, False for blue
        """
        if self.green_percentage <= 0:
            return False
        if self.green_percentage >= 100:
            return True
        
        # Generate a random number between 0-100 and compare to green percentage
        return random.random() * 100 < self.green_percentage
    
    def get_adjustment_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of traffic adjustments.
        
        Returns:
            List of adjustment events
        """
        return self.state["adjustment_history"]
    
    def reset(self, green_percentage: float = 0) -> None:
        """
        Reset the traffic controller to a specific green percentage.
        
        Args:
            green_percentage: Initial green traffic percentage
        """
        self.green_percentage = max(0, min(100, green_percentage))
        
        self.state = {
            "last_evaluation_time": time.time(),
            "last_adjustment_time": time.time(),
            "adjustment_history": [],
            "steady_state_time": time.time(),
            "error_detected": False,
            "error_detection_time": None,
            "promotion_eligible": False,
            "promotion_eligibility_time": None
        }
        
        self._update_control_limits()
        logger.info(f"Traffic controller reset to {self.green_percentage}% green traffic")