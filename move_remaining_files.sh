#!/bin/bash
# Script to move remaining files from root directory into appropriate subdirectories
# Based on file function and purpose

echo "Moving remaining files to appropriate subdirectories..."

# Documentation files to docs/
mv BINARY_INSTALLATION_FIX_REPORT.md docs/
mv DOCKER_CICD_STATUS.md docs/
mv FINAL_IMPLEMENTATION_COMPLETE.md docs/
mv FINAL_IMPLEMENTATION_SUMMARY.md docs/
mv FINAL_MCP_SERVER_COMPLETE.md docs/
mv FINAL_PRODUCTION_STATUS.md docs/
mv FINAL_PRODUCTION_STATUS_REPORT.md docs/
mv IPFS_KIT_MCP_INTEGRATION_PLAN.md docs/
mv IPFS_MCP_TOOLS_TEST_REPORT.md docs/
mv MCP_INTEGRATION_STATUS.md docs/
mv MCP_SERVER_PRODUCTION_MIGRATION.md docs/
mv PHASE1_TEST_RESULTS_SUMMARY.md docs/
mv PRODUCTION_READINESS_REPORT.md docs/
mv PROTOBUF_CONFLICT_RESOLUTION.md docs/
mv README_FINAL_MCP_PRODUCTION.md docs/
mv README_NEW.md docs/
mv REAL_IPFS_INTEGRATION_REPORT.md docs/
mv VSCODE_MCP_INTEGRATION_STATUS.md docs/
mv WORKSPACE_CLEANUP_PLAN.md docs/
mv WORKSPACE_REORGANIZATION_PLAN.md docs/

# Docker files to docker/
mv Dockerfile docker/
mv Dockerfile.final docker/
mv docker-compose.final.yml docker/
mv docker-compose.yml docker/

# Configuration files to config/
mv MANIFEST.in config/
mv setup.cfg config/
mv setup.py config/
mv pyproject.toml config/
mv pytest.ini config/
mv tox.ini config/
mv requirements.txt config/

# Test files to tests/
mv comprehensive_ipfs_test.py tests/
mv end_to_end_integration_test.py tests/
mv enhanced_test_diagnostics.py tests/
mv final_binary_detection_validation.py tests/
mv final_production_validation.py tests/
mv final_validation.py tests/
mv production_verification.py tests/
mv test_basic_ipfs_mcp.py tests/
mv test_binary_detection_fix.py tests/
mv test_binary_fix_simple.py tests/
mv test_detailed_tools.py tests/
mv test_direct_ipfs_server.py tests/
mv test_direct_mcp_tools.py tests/
mv test_edge_cases.py tests/
mv test_enhanced_mcp_phase1.py tests/
mv test_final_server_simple.py tests/
mv test_imports.py tests/
mv test_install_ipfs_final.py tests/
mv test_install_ipfs_standalone.py tests/
mv test_ipfs_direct.py tests/
mv test_ipfs_import.py tests/
mv test_ipfs_ls_fix.py tests/
mv test_ipfs_mcp_tools.py tests/
mv test_ipfs_tools.py tests/
mv test_mcp_basic.py tests/
mv test_mcp_comprehensive.py tests/
mv test_mcp_tools_comprehensive.py tests/
mv test_phase1.py tests/
mv test_phase2.py tests/
mv test_production_mcp_server.py tests/
mv test_reorganization_final.py tests/
mv test_resources_list.py tests/
mv test_resources_support.py tests/
mv test_unified_tools.py tests/
mv test_vscode_mcp_integration.py tests/

# Development and utility scripts to dev/
mv binary_detection_fix_summary.py dev/
mv debug_install_methods.py dev/
mv fix_mcp_dependencies.py dev/
mv fixed_direct_ipfs_tools.py dev/
mv fixed_ipfs_model.py dev/
mv ipfs_tools_fix.py dev/
mv ipfs_tools_minimal.py dev/
mv mcp_status_check.py dev/
mv organize_workspace.py dev/
mv complete_workspace_reorganization.py dev/
mv phase2_final_status.py dev/
mv reorganization_final_status.py dev/
mv reorganize_workspace.py dev/
mv simple_cleanup.py dev/
mv simple_reorganize.py dev/
mv simple_server_test.py dev/
mv quick_phase2_test.py dev/
mv validate_enhanced_server.py dev/
mv validate_reorganization.py dev/
mv verify_real_ipfs.py dev/
mv workspace_cleanup_automation.sh dev/

# Shell scripts to scripts/
mv final_validation.sh scripts/
mv final_verification.sh scripts/
mv improved_run_solution.sh scripts/
mv manual_test.sh scripts/
mv quick_test.sh scripts/
mv restart_enhanced_mcp_server.sh scripts/
mv restart_final_solution.sh scripts/
mv restart_vscode_mcp.sh scripts/
mv run_final_mcp.sh scripts/
mv run_final_solution.sh scripts/
mv run_fixed_final_solution.sh scripts/
mv setup_venv.sh scripts/
mv simple_cleanup.sh scripts/
mv start_vscode_mcp.sh scripts/
mv test_final_server.sh scripts/
mv verify_deployment_readiness.sh scripts/

# MCP servers to mcp/
mv enhanced_mcp_server_with_daemon_mgmt.py mcp/
mv vscode_mcp_server.py mcp/

# Legacy core files to mcp/ipfs_kit/
mv unified_ipfs_tools.py mcp/ipfs_kit/tools/

# Initialization scripts to scripts/
mv initialize_phase1.py scripts/
mv initialize_phase2.py scripts/

# Main entry point to root (keeping it there)
# mv main.py (keeping in root as primary entry point)

# Log files to logs/ (create if doesn't exist)
mkdir -p logs
mv ipfs_daemon.log logs/ 2>/dev/null || true
mv phase1_init.log logs/ 2>/dev/null || true
mv phase2_init.log logs/ 2>/dev/null || true

# Status files to dev/ (temporary status files)
mv phase1_status.json dev/ 2>/dev/null || true
mv phase2_status.json dev/ 2>/dev/null || true
mv tools_registry.json dev/ 2>/dev/null || true

# Test data files to tests/data/ (create if doesn't exist)
mkdir -p tests/data
mv test_file.txt tests/data/ 2>/dev/null || true

echo "File organization complete!"
echo "Summary of moves:"
echo "- Documentation files → docs/"
echo "- Docker files → docker/"
echo "- Configuration files → config/"
echo "- Test files → tests/"
echo "- Development utilities → dev/"
echo "- Shell scripts → scripts/"
echo "- MCP servers → mcp/"
echo "- Log files → logs/"
echo "- Status/registry files → dev/"
echo "- Test data → tests/data/"
echo ""
echo "Files kept in root:"
echo "- main.py (primary entry point)"
echo "- README.md (main readme)"
echo "- LICENSE (license file)"
echo "- Makefile (build automation)"
echo "- Standard directories (.git/, .vscode/, etc.)"
