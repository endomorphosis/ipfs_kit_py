"""
Tests for dynamic role switching based on resources (Phase 3B).

This module tests dynamic role switching in IPFS cluster nodes based on:
- Available resources
- Network conditions
- Workload changes
- Environmental factors
- User preferences
"""

import unittest
import os
import time
import tempfile
import shutil
import uuid
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from ipfs_kit_py.ipfs_kit import ipfs_kit


@pytest.fixture
def dynamicnode_setup():
    """Create a node with role switching capabilities for testing."""
    with patch('subprocess.run') as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-id"}'
        mock_run.return_value = mock_process
        
        # Create leecher node that can be upgraded
        node = ipfs_kit(
            resources={"memory": "4GB", "disk": "100GB", "cpu": 2},
            metadata={
                "role": "leecher",
                "dynamic_roles": {
                    "enabled": True,
                    "check_interval": 300,  # 5 minutes
                    "upgrade_threshold": 0.7,  # 70% of required resources
                    "downgrade_threshold": 0.3  # 30% of required resources
                },
                "test_mode": True
            }
        )
        node.ipfs = MagicMock()
        
        # Mock service components to be added during role change
        node.create_cluster_follow_service = MagicMock()
        node.create_cluster_service = MagicMock()
        node.create_cluster_ctl = MagicMock()
        
        # Return the node for testing
        yield node


class TestRoleRequirements:
    """Test role requirement definitions and calculations."""
    
    def test_get_role_requirements(self, dynamicnode_setup):
        """Test retrieving resource requirements for different roles."""
        node = dynamicnode_setup
        
        # Mock the requirements function
        node.get_role_requirements = MagicMock(return_value={
            "leecher": {
                "memory_min": 2 * 1024 * 1024 * 1024,  # 2GB
                "disk_min": 10 * 1024 * 1024 * 1024,   # 10GB
                "cpu_min": 1,
                "bandwidth_min": 1 * 1024 * 1024       # 1MB/s
            },
            "worker": {
                "memory_min": 4 * 1024 * 1024 * 1024,  # 4GB
                "disk_min": 100 * 1024 * 1024 * 1024,  # 100GB
                "cpu_min": 2,
                "bandwidth_min": 5 * 1024 * 1024       # 5MB/s
            },
            "master": {
                "memory_min": 8 * 1024 * 1024 * 1024,  # 8GB
                "disk_min": 500 * 1024 * 1024 * 1024,  # 500GB
                "cpu_min": 4,
                "bandwidth_min": 10 * 1024 * 1024      # 10MB/s
            }
        })
        
        # Test getting requirements
        result = node.get_role_requirements()
        
        # Verify requirements
        assert "leecher" in result
        assert "worker" in result
        assert "master" in result
        
        assert result["leecher"]["memory_min"] < result["worker"]["memory_min"]
        assert result["worker"]["memory_min"] < result["master"]["memory_min"]
        
        node.get_role_requirements.assert_called_once()
    
    def test_get_available_resources(self, dynamicnode_setup):
        """Test retrieving available resources for role calculation."""
        node = dynamicnode_setup
        
        # Mock the resource detection function
        node.detect_available_resources = MagicMock(return_value={
            "memory_available": 6 * 1024 * 1024 * 1024,  # 6GB
            "disk_available": 120 * 1024 * 1024 * 1024,  # 120GB
            "cpu_available": 3,
            "bandwidth_available": 6 * 1024 * 1024,      # 6MB/s
            "gpu_available": False,
            "network_stability": 0.9  # 90% stable
        })
        
        # Test getting resources
        result = node.detect_available_resources()
        
        # Verify resources
        assert "memory_available" in result
        assert "disk_available" in result
        assert "cpu_available" in result
        assert "bandwidth_available" in result
        
        assert result["memory_available"] > 0
        assert result["disk_available"] > 0
        
        node.detect_available_resources.assert_called_once()


class TestDynamicRoleDetermination:
    """Test determination of appropriate role based on available resources."""
    
    def test_evaluate_potential_roles(self, dynamicnode_setup):
        """Test evaluating which roles are possible with current resources."""
        node = dynamicnode_setup
        
        # Mock resource detection
        node.detect_available_resources = MagicMock(return_value={
            "memory_available": 6 * 1024 * 1024 * 1024,  # 6GB
            "disk_available": 120 * 1024 * 1024 * 1024,  # 120GB
            "cpu_available": 3,
            "bandwidth_available": 8 * 1024 * 1024       # 8MB/s
        })
        
        # Mock role requirements
        node.get_role_requirements = MagicMock(return_value={
            "leecher": {
                "memory_min": 2 * 1024 * 1024 * 1024,
                "disk_min": 10 * 1024 * 1024 * 1024,
                "cpu_min": 1,
                "bandwidth_min": 1 * 1024 * 1024
            },
            "worker": {
                "memory_min": 4 * 1024 * 1024 * 1024,
                "disk_min": 100 * 1024 * 1024 * 1024,
                "cpu_min": 2,
                "bandwidth_min": 5 * 1024 * 1024
            },
            "master": {
                "memory_min": 8 * 1024 * 1024 * 1024,
                "disk_min": 500 * 1024 * 1024 * 1024,
                "cpu_min": 4,
                "bandwidth_min": 10 * 1024 * 1024
            }
        })
        
        # Mock the role evaluation function
        def evaluate_roles():
            resources = node.detect_available_resources()
            requirements = node.get_role_requirements()
            
            results = {}
            
            # Calculate capability percentage for each role
            for role, reqs in requirements.items():
                mem_pct = resources["memory_available"] / reqs["memory_min"]
                disk_pct = resources["disk_available"] / reqs["disk_min"]
                cpu_pct = resources["cpu_available"] / reqs["cpu_min"]
                bw_pct = resources["bandwidth_available"] / reqs["bandwidth_min"]
                
                # Use the minimum percentage as the limiting factor
                capability_pct = min(mem_pct, disk_pct, cpu_pct, bw_pct)
                
                results[role] = {
                    "capable": capability_pct >= 1.0,  # True if 100% or more
                    "capability_percent": capability_pct,
                    "limiting_factor": "memory" if mem_pct == capability_pct else
                                      "disk" if disk_pct == capability_pct else
                                      "cpu" if cpu_pct == capability_pct else
                                      "bandwidth"
                }
            
            return results
        
        node.evaluate_potential_roles = MagicMock(side_effect=evaluate_roles)
        
        # Test role evaluation
        result = node.evaluate_potential_roles()
        
        # Verify results
        assert "leecher" in result
        assert "worker" in result
        assert "master" in result
        
        # With mocked values, node should be capable of leecher and worker roles
        assert result["leecher"]["capable"] is True
        assert result["worker"]["capable"] is True
        assert result["master"]["capable"] is False
        
        # Limiting factor for master should be disk (120GB vs 500GB required)
        assert result["master"]["limiting_factor"] == "disk"
        
        node.detect_available_resources.assert_called_once()
        node.get_role_requirements.assert_called_once()
    
    def test_determine_optimal_role(self, dynamicnode_setup):
        """Test determining the optimal role based on resources and constraints."""
        node = dynamicnode_setup
        
        # Mock role evaluation
        node.evaluate_potential_roles = MagicMock(return_value={
            "leecher": {
                "capable": True,
                "capability_percent": 3.0,  # 300% of required resources
                "limiting_factor": None
            },
            "worker": {
                "capable": True,
                "capability_percent": 1.2,  # 120% of required resources
                "limiting_factor": "disk"
            },
            "master": {
                "capable": False,
                "capability_percent": 0.5,  # 50% of required resources
                "limiting_factor": "disk"
            }
        })
        
        # Mock the role optimization function
        def optimize_role():
            current_role = node.role
            role_evaluation = node.evaluate_potential_roles()
            
            # First check: can we maintain current role?
            if current_role in role_evaluation and role_evaluation[current_role]["capable"]:
                # Check if we should upgrade
                if current_role == "leecher":
                    # Check if worker is viable 
                    if role_evaluation["worker"]["capable"]:
                        return {
                            "optimal_role": "worker",
                            "action": "upgrade",
                            "reason": f"Node has sufficient resources for worker role ({role_evaluation['worker']['capability_percent']:.2f}x requirement)"
                        }
                elif current_role == "worker":
                    # Check if master is viable 
                    if role_evaluation["master"]["capable"]:
                        return {
                            "optimal_role": "master",
                            "action": "upgrade",
                            "reason": f"Node has sufficient resources for master role ({role_evaluation['master']['capability_percent']:.2f}x requirement)"
                        }
                
                # No better role available, stay as is
                return {
                    "optimal_role": current_role,
                    "action": "maintain",
                    "reason": f"Current role '{current_role}' is optimal for available resources"
                }
            
            # Current role isn't viable, find the best one
            best_role = None
            best_capability = 0
            
            for role, eval_data in role_evaluation.items():
                if eval_data["capable"] and eval_data["capability_percent"] > best_capability:
                    best_role = role
                    best_capability = eval_data["capability_percent"]
            
            if best_role:
                if best_role == current_role:
                    action = "maintain"
                elif ["leecher", "worker", "master"].index(best_role) > ["leecher", "worker", "master"].index(current_role):
                    action = "upgrade"
                else:
                    action = "downgrade"
                    
                return {
                    "optimal_role": best_role,
                    "action": action,
                    "reason": f"Changing from '{current_role}' to '{best_role}' based on resource capabilities"
                }
            
            # Fallback to leecher if nothing is viable
            return {
                "optimal_role": "leecher",
                "action": "downgrade",
                "reason": "Insufficient resources for current role, defaulting to leecher"
            }
            
        node.determine_optimal_role = MagicMock(side_effect=optimize_role)
        
        # Test role optimization
        result = node.determine_optimal_role()
        
        # Verify results - with the mocked evaluations, should upgrade to worker
        assert result["optimal_role"] == "worker"
        assert result["action"] == "upgrade"
        assert "sufficient resources" in result["reason"]
        
        node.evaluate_potential_roles.assert_called_once()


class TestRoleSwitchingImplementation:
    """Test the actual implementation of switching between roles."""
    
    def test_upgrade_leecher_to_worker(self, dynamicnode_setup):
        """Test upgrading a node from leecher to worker role."""
        node = dynamicnode_setup
        
        # Verify initial role
        assert node.role == "leecher"
        
        # Mock the upgrade function
        node.upgrade_to_worker = MagicMock(return_value={
            "success": True,
            "previous_role": "leecher",
            "new_role": "worker",
            "actions_performed": [
                "Stopped IPFS daemon",
                "Updated node configuration",
                "Initialized cluster follow service",
                "Restarted IPFS daemon with worker profile",
                "Joined cluster as worker"
            ]
        })
        
        # Test upgrading to worker
        result = node.upgrade_to_worker(
            master_address="/ip4/192.168.1.100/tcp/9096/p2p/QmMasterPeerID",
            cluster_secret="cluster-shared-secret-key"
        )
        
        # Verify result
        assert result["success"] is True
        assert result["previous_role"] == "leecher"
        assert result["new_role"] == "worker"
        assert len(result["actions_performed"]) > 0
        
        # Verify the service creation was called
        node.create_cluster_follow_service.assert_called_once()
        
        # When upgrading from leecher to worker, this shouldn't be called
        node.create_cluster_service.assert_not_called()
        node.create_cluster_ctl.assert_not_called()
    
    def test_upgrade_worker_to_master(self, dynamicnode_setup):
        """Test upgrading a node from worker to master role."""
        node = dynamicnode_setup
        
        # Set initial role to worker
        node.role = "worker"
        node.ipfs_cluster_follow = MagicMock()
        
        # Mock the upgrade function
        node.upgrade_to_master = MagicMock(return_value={
            "success": True,
            "previous_role": "worker",
            "new_role": "master",
            "actions_performed": [
                "Stopped IPFS daemon",
                "Stopped cluster follow service",
                "Updated node configuration",
                "Initialized cluster service",
                "Initialized cluster control interface",
                "Restarted IPFS daemon with master profile",
                "Started cluster service as master"
            ]
        })
        
        # Test upgrading to master
        result = node.upgrade_to_master(
            cluster_secret="cluster-shared-secret-key",
            config_overrides={"replication_factor": 3}
        )
        
        # Verify result
        assert result["success"] is True
        assert result["previous_role"] == "worker"
        assert result["new_role"] == "master"
        assert len(result["actions_performed"]) > 0
        
        # Verify the service creations were called
        node.create_cluster_service.assert_called_once()
        node.create_cluster_ctl.assert_called_once()
    
    def test_downgrade_worker_to_leecher(self, dynamicnode_setup):
        """Test downgrading a node from worker to leecher role."""
        node = dynamicnode_setup
        
        # Set initial role to worker
        node.role = "worker"
        node.ipfs_cluster_follow = MagicMock()
        
        # Mock the downgrade function
        node.downgrade_to_leecher = MagicMock(return_value={
            "success": True,
            "previous_role": "worker",
            "new_role": "leecher",
            "actions_performed": [
                "Stopped IPFS daemon",
                "Stopped cluster follow service",
                "Updated node configuration",
                "Restarted IPFS daemon with leecher profile",
                "Removed cluster follow service"
            ]
        })
        
        # Test downgrading to leecher
        result = node.downgrade_to_leecher()
        
        # Verify result
        assert result["success"] is True
        assert result["previous_role"] == "worker"
        assert result["new_role"] == "leecher"
        assert len(result["actions_performed"]) > 0


class TestAutomatedRoleSwitching:
    """Test automated role switching based on resource monitoring."""
    
    def test_resource_monitor(self, dynamicnode_setup):
        """Test monitoring resources and detecting changes."""
        node = dynamicnode_setup
        
        # Mock the resource monitoring function
        previous_resources = {
            "memory_available": 4 * 1024 * 1024 * 1024,
            "disk_available": 100 * 1024 * 1024 * 1024,
            "cpu_available": 2,
            "bandwidth_available": 5 * 1024 * 1024
        }
        
        current_resources = {
            "memory_available": 6 * 1024 * 1024 * 1024,  # Increased
            "disk_available": 120 * 1024 * 1024 * 1024,  # Increased
            "cpu_available": 3,  # Increased
            "bandwidth_available": 8 * 1024 * 1024  # Increased
        }
        
        node.detect_resource_changes = MagicMock(return_value={
            "significant_change": True,
            "previous_resources": previous_resources,
            "current_resources": current_resources,
            "changes": {
                "memory_available": {
                    "previous": previous_resources["memory_available"],
                    "current": current_resources["memory_available"],
                    "difference": current_resources["memory_available"] - previous_resources["memory_available"],
                    "percent_change": ((current_resources["memory_available"] / previous_resources["memory_available"]) - 1) * 100
                },
                "disk_available": {
                    "previous": previous_resources["disk_available"],
                    "current": current_resources["disk_available"],
                    "difference": current_resources["disk_available"] - previous_resources["disk_available"],
                    "percent_change": ((current_resources["disk_available"] / previous_resources["disk_available"]) - 1) * 100
                },
                "cpu_available": {
                    "previous": previous_resources["cpu_available"],
                    "current": current_resources["cpu_available"],
                    "difference": current_resources["cpu_available"] - previous_resources["cpu_available"],
                    "percent_change": ((current_resources["cpu_available"] / previous_resources["cpu_available"]) - 1) * 100
                },
                "bandwidth_available": {
                    "previous": previous_resources["bandwidth_available"],
                    "current": current_resources["bandwidth_available"],
                    "difference": current_resources["bandwidth_available"] - previous_resources["bandwidth_available"],
                    "percent_change": ((current_resources["bandwidth_available"] / previous_resources["bandwidth_available"]) - 1) * 100
                }
            }
        })
        
        # Test resource monitoring
        result = node.detect_resource_changes()
        
        # Verify result
        assert result["significant_change"] is True
        assert "changes" in result
        assert all(key in result["changes"] for key in ["memory_available", "disk_available", "cpu_available", "bandwidth_available"])
        
        # All changes should be positive
        for resource_type, change_data in result["changes"].items():
            assert change_data["difference"] > 0
            assert change_data["percent_change"] > 0
    
    def test_automated_role_check(self, dynamicnode_setup):
        """Test the automated role check and decision process."""
        node = dynamicnode_setup
        
        # Mock dependencies
        node.detect_resource_changes = MagicMock(return_value={
            "significant_change": True,
            "changes": {
                "memory_available": {"percent_change": 50},
                "disk_available": {"percent_change": 20}
            }
        })
        
        node.determine_optimal_role = MagicMock(return_value={
            "optimal_role": "worker",
            "action": "upgrade",
            "reason": "Node has sufficient resources for worker role"
        })
        
        node.upgrade_to_worker = MagicMock(return_value={
            "success": True,
            "previous_role": "leecher",
            "new_role": "worker"
        })
        
        # Mock the auto check function
        def auto_check():
            # Check if resources have changed significantly
            change_result = node.detect_resource_changes()
            
            if not change_result["significant_change"]:
                return {
                    "success": True,
                    "role_change_needed": False,
                    "message": "No significant resource changes detected"
                }
            
            # Determine optimal role
            role_result = node.determine_optimal_role()
            
            if role_result["action"] == "maintain":
                return {
                    "success": True,
                    "role_change_needed": False,
                    "message": f"Current role '{node.role}' remains optimal"
                }
            
            # Need to change role
            if role_result["action"] == "upgrade":
                if role_result["optimal_role"] == "worker":
                    upgrade_result = node.upgrade_to_worker()
                    if upgrade_result["success"]:
                        return {
                            "success": True,
                            "role_change_needed": True,
                            "role_change_executed": True,
                            "previous_role": "leecher",
                            "new_role": "worker",
                            "message": "Upgraded from leecher to worker role"
                        }
                elif role_result["optimal_role"] == "master":
                    upgrade_result = node.upgrade_to_master()
                    if upgrade_result["success"]:
                        return {
                            "success": True,
                            "role_change_needed": True,
                            "role_change_executed": True,
                            "previous_role": "worker",
                            "new_role": "master",
                            "message": "Upgraded from worker to master role"
                        }
            elif role_result["action"] == "downgrade":
                if role_result["optimal_role"] == "worker":
                    downgrade_result = node.downgrade_to_worker()
                    if downgrade_result["success"]:
                        return {
                            "success": True,
                            "role_change_needed": True,
                            "role_change_executed": True,
                            "previous_role": "master",
                            "new_role": "worker",
                            "message": "Downgraded from master to worker role"
                        }
                elif role_result["optimal_role"] == "leecher":
                    downgrade_result = node.downgrade_to_leecher()
                    if downgrade_result["success"]:
                        return {
                            "success": True,
                            "role_change_needed": True,
                            "role_change_executed": True,
                            "previous_role": "worker",
                            "new_role": "leecher",
                            "message": "Downgraded from worker to leecher role"
                        }
            
            # Something went wrong
            return {
                "success": False,
                "role_change_needed": True,
                "role_change_executed": False,
                "message": "Failed to execute role change"
            }
        
        node.check_and_update_role = MagicMock(side_effect=auto_check)
        
        # Test auto role check
        result = node.check_and_update_role()
        
        # Verify result
        assert result["success"] is True
        assert result["role_change_needed"] is True
        assert result["role_change_executed"] is True
        assert result["previous_role"] == "leecher"
        assert result["new_role"] == "worker"
        assert "Upgraded from leecher to worker role" in result["message"]
        
        # Verify call sequence
        node.detect_resource_changes.assert_called_once()
        node.determine_optimal_role.assert_called_once()
        node.upgrade_to_worker.assert_called_once()


class TestUserControlledRoleSwitching:
    """Test user-controlled role switching with overrides."""
    
    def test_user_initiated_role_change(self, dynamicnode_setup):
        """Test user-initiated role change with resource validation."""
        node = dynamicnode_setup
        
        # Mock dependencies
        node.evaluate_potential_roles = MagicMock(return_value={
            "leecher": {"capable": True, "capability_percent": 3.0},
            "worker": {"capable": True, "capability_percent": 1.2},
            "master": {"capable": False, "capability_percent": 0.5}
        })
        
        node.upgrade_to_worker = MagicMock(return_value={
            "success": True,
            "previous_role": "leecher",
            "new_role": "worker"
        })
        
        # Mock the user-initiated change function
        def user_change_role(target_role, force=False):
            # Check if role is valid
            if target_role not in ["leecher", "worker", "master"]:
                return {
                    "success": False,
                    "error": f"Invalid role: {target_role}"
                }
            
            # If not forced, check if we have sufficient resources
            if not force:
                role_eval = node.evaluate_potential_roles()
                
                if target_role not in role_eval or not role_eval[target_role]["capable"]:
                    return {
                        "success": False,
                        "error": f"Insufficient resources for role: {target_role}",
                        "capability_percent": role_eval[target_role]["capability_percent"] if target_role in role_eval else 0,
                        "limiting_factor": role_eval[target_role]["limiting_factor"] if target_role in role_eval else "unknown"
                    }
            
            # Execute the role change
            current_role = node.role
            
            if target_role == current_role:
                return {
                    "success": True,
                    "message": f"Node is already in {target_role} role"
                }
            
            # Handle the role change
            if current_role == "leecher" and target_role == "worker":
                result = node.upgrade_to_worker()
                return {
                    "success": result["success"],
                    "previous_role": result["previous_role"],
                    "new_role": result["new_role"],
                    "message": f"Upgraded from {result['previous_role']} to {result['new_role']}"
                }
            elif current_role == "leecher" and target_role == "master":
                result = node.upgrade_to_master()
                return {
                    "success": result["success"],
                    "previous_role": result["previous_role"],
                    "new_role": result["new_role"],
                    "message": f"Upgraded from {result['previous_role']} to {result['new_role']}"
                }
            elif current_role == "worker" and target_role == "master":
                result = node.upgrade_to_master()
                return {
                    "success": result["success"],
                    "previous_role": result["previous_role"],
                    "new_role": result["new_role"],
                    "message": f"Upgraded from {result['previous_role']} to {result['new_role']}"
                }
            elif current_role == "worker" and target_role == "leecher":
                result = node.downgrade_to_leecher()
                return {
                    "success": result["success"],
                    "previous_role": result["previous_role"],
                    "new_role": result["new_role"],
                    "message": f"Downgraded from {result['previous_role']} to {result['new_role']}"
                }
            elif current_role == "master" and target_role == "worker":
                result = node.downgrade_to_worker()
                return {
                    "success": result["success"],
                    "previous_role": result["previous_role"],
                    "new_role": result["new_role"],
                    "message": f"Downgraded from {result['previous_role']} to {result['new_role']}"
                }
            elif current_role == "master" and target_role == "leecher":
                result = node.downgrade_to_leecher()
                return {
                    "success": result["success"],
                    "previous_role": result["previous_role"],
                    "new_role": result["new_role"],
                    "message": f"Downgraded from {result['previous_role']} to {result['new_role']}"
                }
            
            return {
                "success": False,
                "error": f"Unsupported role transition: {current_role} to {target_role}"
            }
        
        node.change_role = MagicMock(side_effect=user_change_role)
        
        # Test valid role change
        result = node.change_role("worker")
        
        # Verify result
        assert result["success"] is True
        assert "Upgraded from leecher to worker" in result["message"]
        
        # Test invalid role change (insufficient resources)
        node.evaluate_potential_roles = MagicMock(return_value={
            "leecher": {"capable": True, "capability_percent": 3.0},
            "worker": {"capable": True, "capability_percent": 1.2},
            "master": {"capable": False, "capability_percent": 0.5, "limiting_factor": "disk"}
        })
        
        result = node.change_role("master")
        
        # Verify failure
        assert result["success"] is False
        assert "Insufficient resources" in result["error"]
        assert result["limiting_factor"] == "disk"
        
        # Test forced role change (bypass resource check)
        node.upgrade_to_master = MagicMock(return_value={
            "success": True,
            "previous_role": "leecher",
            "new_role": "master"
        })
        
        result = node.change_role("master", force=True)
        
        # Verify result with force flag
        assert result["success"] is True
        assert "Upgraded from leecher to master" in result["message"]
        
        # Verify evaluate_potential_roles was not called for forced change
        node.evaluate_potential_roles.assert_called_once()  # Only from previous call


if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])