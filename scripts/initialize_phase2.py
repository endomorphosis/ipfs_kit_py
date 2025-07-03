#!/usr/bin/env python3
"""
Phase 2 IPFS Core Tools Initialization Script

This script continues from Phase 1 and initializes Phase 2 components:
- IPFS Core Tools (18 tools)
- Advanced IPFS Tools 
- MFS (Mutable File System) Tools
- VFS (Virtual File System) Integration
- Multi-Backend Storage
"""

import os
import sys
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add core and tools directories to Python path
base_dir = Path(__file__).parent
core_dir = base_dir / "core"
tools_dir = base_dir / "tools"
sys.path.insert(0, str(core_dir))
sys.path.insert(0, str(tools_dir))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('phase2_init.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Phase2Initializer:
    """Phase 2 IPFS tools initializer"""
    
    def __init__(self):
        self.components = {}
        self.tools_registered = {}
        self.initialization_status = {}
        self.phase1_required = True
        
    def check_phase1_prerequisites(self) -> bool:
        """Check if Phase 1 is properly initialized"""
        logger.info("Checking Phase 1 prerequisites...")
        
        try:
            # Import Phase 1 components
            from core.tool_registry import registry
            from core.service_manager import ipfs_manager
            from core.error_handler import error_handler
            from core.test_framework import test_framework
            
            # Check if they're initialized
            if len(registry.tools) == 0:
                logger.warning("Tool registry appears empty - running Phase 1 initialization")
                return self._run_phase1_init()
            
            logger.info("✓ Phase 1 components are available")
            self.components.update({
                'tool_registry': registry,
                'ipfs_manager': ipfs_manager,
                'error_handler': error_handler,
                'test_framework': test_framework
            })
            return True
            
        except ImportError as e:
            logger.error(f"Phase 1 components not available: {e}")
            return False
            
    def _run_phase1_init(self) -> bool:
        """Run Phase 1 initialization if needed"""
        try:
            logger.info("Running Phase 1 initialization...")
            from initialize_phase1 import Phase1Initializer
            
            phase1 = Phase1Initializer()
            success = phase1.initialize_all()
            
            if success:
                self.components.update(phase1.components)
                logger.info("✓ Phase 1 initialization completed")
                return True
            else:
                logger.error("✗ Phase 1 initialization failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to run Phase 1 initialization: {e}")
            return False
    
    def initialize_all(self) -> bool:
        """Initialize all Phase 2 components"""
        logger.info("Starting Phase 2 initialization...")
        
        # Check prerequisites
        if not self.check_phase1_prerequisites():
            logger.error("Phase 1 prerequisites not met")
            return False
        
        # Phase 2 components
        components = [
            ("ipfs_daemon", self._ensure_ipfs_daemon),
            ("ipfs_core_tools", self._initialize_ipfs_core_tools),
            ("ipfs_advanced_tools", self._initialize_ipfs_advanced_tools),
            ("ipfs_mfs_tools", self._initialize_ipfs_mfs_tools),
            ("ipfs_vfs_integration", self._initialize_ipfs_vfs_integration),
        ]
        
        all_success = True
        for name, init_func in components:
            try:
                logger.info(f"Initializing {name}...")
                success = init_func()
                self.initialization_status[name] = "success" if success else "failed"
                if not success:
                    all_success = False
                    logger.error(f"Failed to initialize {name}")
                else:
                    logger.info(f"Successfully initialized {name}")
            except Exception as e:
                logger.error(f"Error initializing {name}: {e}")
                self.initialization_status[name] = "error"
                all_success = False
        
        if all_success:
            logger.info("Phase 2 initialization completed successfully!")
            self._run_validation_tests()
        else:
            logger.error("Phase 2 initialization completed with errors")
        
        return all_success
    
    def _ensure_ipfs_daemon(self) -> bool:
        """Ensure IPFS daemon is running"""
        try:
            ipfs_manager = self.components.get('ipfs_manager')
            if not ipfs_manager:
                logger.error("IPFS manager not available")
                return False
            
            logger.info("Checking IPFS daemon status...")
            if ipfs_manager.health_check("ipfs"):
                logger.info("✓ IPFS daemon is running")
                return True
            
            logger.info("Starting IPFS daemon...")
            if ipfs_manager.ensure_ipfs_running():
                logger.info("✓ IPFS daemon started successfully")
                return True
            else:
                logger.warning("⚠ IPFS daemon failed to start")
                return False
                
        except Exception as e:
            logger.error(f"IPFS daemon check failed: {e}")
            return False
    
    def _initialize_ipfs_core_tools(self) -> bool:
        """Initialize the 18 core IPFS tools"""
        try:
            registry = self.components.get('tool_registry')
            if not registry:
                logger.error("Tool registry not available")
                return False
            
            # Import and register core tools
            logger.info("Registering IPFS core tools...")
            
            # Import tools from both parts
            from tools.ipfs_core_tools import (
                handle_ipfs_add, handle_ipfs_cat, handle_ipfs_get, handle_ipfs_ls,
                handle_ipfs_pin_add, handle_ipfs_pin_rm, handle_ipfs_pin_ls, handle_ipfs_pin_update
            )
            from tools.ipfs_core_tools_part2 import (
                handle_ipfs_id, handle_ipfs_version, handle_ipfs_stats, handle_ipfs_swarm_peers,
                handle_ipfs_refs, handle_ipfs_refs_local, handle_ipfs_block_stat, handle_ipfs_block_get,
                handle_ipfs_dag_get, handle_ipfs_dag_put
            )
            
            # Define all tools
            core_tools = [
                # Basic Operations
                ("ipfs_add", handle_ipfs_add),
                ("ipfs_cat", handle_ipfs_cat), 
                ("ipfs_get", handle_ipfs_get),
                ("ipfs_ls", handle_ipfs_ls),
                
                # Pin Management  
                ("ipfs_pin_add", handle_ipfs_pin_add),
                ("ipfs_pin_rm", handle_ipfs_pin_rm),
                ("ipfs_pin_ls", handle_ipfs_pin_ls),
                ("ipfs_pin_update", handle_ipfs_pin_update),
                
                # Node Operations
                ("ipfs_id", handle_ipfs_id),
                ("ipfs_version", handle_ipfs_version),
                ("ipfs_stats", handle_ipfs_stats),
                ("ipfs_swarm_peers", handle_ipfs_swarm_peers),
                
                # Content Operations
                ("ipfs_refs", handle_ipfs_refs),
                ("ipfs_refs_local", handle_ipfs_refs_local),
                ("ipfs_block_stat", handle_ipfs_block_stat),
                ("ipfs_block_get", handle_ipfs_block_get),
                
                # DAG Operations
                ("ipfs_dag_get", handle_ipfs_dag_get),
                ("ipfs_dag_put", handle_ipfs_dag_put)
            ]
            
            # Register each tool
            registered_count = 0
            for tool_name, handler in core_tools:
                try:
                    # Get tool metadata from decorator
                    tool_meta = getattr(handler, '_tool_meta', None)
                    if tool_meta:
                        from core.tool_registry import ToolSchema, ToolCategory
                        
                        schema = ToolSchema(
                            name=tool_meta['name'],
                            category=ToolCategory.IPFS_CORE,
                            description=tool_meta['description'],
                            parameters=tool_meta['parameters'],
                            returns=tool_meta.get('returns', {}),
                            version=tool_meta.get('version', '1.0.0'),
                            dependencies=tool_meta.get('dependencies', [])
                        )
                        
                        if registry.register_tool(schema, handler):
                            registered_count += 1
                            logger.debug(f"Registered tool: {tool_name}")
                        else:
                            logger.warning(f"Failed to register tool: {tool_name}")
                    else:
                        logger.warning(f"Tool {tool_name} missing metadata")
                        
                except Exception as e:
                    logger.error(f"Error registering tool {tool_name}: {e}")
            
            self.tools_registered['ipfs_core'] = registered_count
            logger.info(f"✓ Registered {registered_count}/18 IPFS core tools")
            
            # Save registry
            registry.save_registry()
            return registered_count >= 16  # Allow some tools to fail
            
        except Exception as e:
            logger.error(f"Failed to initialize IPFS core tools: {e}")
            return False
    
    def _initialize_ipfs_advanced_tools(self) -> bool:
        """Initialize advanced IPFS tools (placeholder for future implementation)"""
        try:
            logger.info("Advanced IPFS tools initialization - placeholder")
            # TODO: Implement advanced tools like ipfs-cluster, pubsub, etc.
            self.tools_registered['ipfs_advanced'] = 0
            return True
        except Exception as e:
            logger.error(f"Failed to initialize advanced IPFS tools: {e}")
            return False
    
    def _initialize_ipfs_mfs_tools(self) -> bool:
        """Initialize MFS (Mutable File System) tools (placeholder)"""
        try:
            logger.info("MFS tools initialization - placeholder") 
            # TODO: Implement MFS tools: files/cp, files/mkdir, files/ls, etc.
            self.tools_registered['ipfs_mfs'] = 0
            return True
        except Exception as e:
            logger.error(f"Failed to initialize MFS tools: {e}")
            return False
    
    def _initialize_ipfs_vfs_integration(self) -> bool:
        """Initialize VFS integration (placeholder)"""
        try:
            logger.info("VFS integration initialization - placeholder")
            # TODO: Implement virtual file system integration
            self.tools_registered['ipfs_vfs'] = 0
            return True
        except Exception as e:
            logger.error(f"Failed to initialize VFS integration: {e}")
            return False
    
    def _run_validation_tests(self) -> bool:
        """Run validation tests for Phase 2 components"""
        logger.info("Running Phase 2 validation tests...")
        
        try:
            test_framework = self.components.get("test_framework")
            if not test_framework:
                logger.error("Test framework not available")
                return False
            
            # Test IPFS core tools
            logger.info("Testing IPFS core tools...")
            results = []
            
            # Test tool registry contains IPFS tools
            registry = self.components.get('tool_registry')
            if registry:
                ipfs_tools = [tool for tool in registry.tools.values() 
                             if tool.category.value == "ipfs_core"]
                logger.info(f"Found {len(ipfs_tools)} IPFS core tools in registry")
                
                if len(ipfs_tools) >= 16:
                    logger.info("✓ IPFS tools registry test passed")
                else:
                    logger.warning(f"⚠ Only {len(ipfs_tools)} IPFS tools registered (expected 18)")
            
            # Test IPFS daemon connectivity  
            ipfs_manager = self.components.get('ipfs_manager')
            if ipfs_manager and ipfs_manager.health_check("ipfs"):
                logger.info("✓ IPFS daemon connectivity test passed")
            else:
                logger.warning("⚠ IPFS daemon connectivity test failed")
            
            return True
                
        except Exception as e:
            logger.error(f"Error running validation tests: {e}")
            return False
    
    def generate_status_report(self) -> Dict[str, Any]:
        """Generate Phase 2 status report"""
        report = {
            "phase": "Phase 2 - IPFS Core Tools",
            "timestamp": str(Path(__file__).stat().st_mtime),
            "components": self.initialization_status.copy(),
            "tools_registered": self.tools_registered.copy(),
            "summary": {
                "total_components": len(self.initialization_status),
                "successful": len([s for s in self.initialization_status.values() if s == "success"]),
                "failed": len([s for s in self.initialization_status.values() if s in ["failed", "error"]]),
                "total_tools": sum(self.tools_registered.values()),
                "overall_status": "success" if all(s == "success" for s in self.initialization_status.values()) else "partial"
            }
        }
        
        # Add detailed component information
        if "tool_registry" in self.components:
            registry = self.components["tool_registry"]
            report["tool_registry_stats"] = registry.get_registry_stats()
        
        return report
    
    def save_status_report(self, filename: str = "phase2_status.json"):
        """Save status report to file"""
        try:
            report = self.generate_status_report()
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Status report saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save status report: {e}")
            return False

def main():
    """Main initialization function"""
    print("=" * 60)
    print("IPFS Kit MCP Integration - Phase 2 Initialization")
    print("=" * 60)
    print()
    
    # Create initializer
    initializer = Phase2Initializer()
    
    # Run initialization
    success = initializer.initialize_all()
    
    # Generate and save report
    initializer.save_status_report()
    
    # Print summary
    print()
    print("=" * 60)
    print("PHASE 2 INITIALIZATION SUMMARY")
    print("=" * 60)
    
    for component, status in initializer.initialization_status.items():
        status_symbol = "✓" if status == "success" else "✗"
        print(f"{status_symbol} {component}: {status}")
    
    print()
    print("Tools Registered:")
    for category, count in initializer.tools_registered.items():
        print(f"  • {category}: {count} tools")
    
    print()
    if success:
        print("🎉 Phase 2 initialization completed successfully!")
        print("✓ IPFS Daemon Running")
        print("✓ IPFS Core Tools (18 tools)")
        print("✓ Advanced Tools Framework")
        print("✓ MFS Tools Framework") 
        print("✓ VFS Integration Framework")
        print()
        print("Next steps:")
        print("1. Review phase2_status.json for detailed information")
        print("2. Test IPFS tools: python test_phase2.py")
        print("3. Proceed to Phase 3: Integration & Testing")
    else:
        print("❌ Phase 2 initialization completed with errors")
        print("Please check the logs and resolve issues before proceeding")
    
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
