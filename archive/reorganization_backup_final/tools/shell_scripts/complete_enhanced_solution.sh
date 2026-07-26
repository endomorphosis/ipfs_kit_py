#!/bin/bash
# Complete IPFS MCP Solution
# This script runs the complete enhanced IPFS MCP solution

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="solution_results_${TIMESTAMP}"
LOG_FILE="${RESULTS_DIR}/solution.log"

# Create results directory
mkdir -p "${RESULTS_DIR}"

# Function to log messages
log() {
    local level="$1"
    local message="$2"
    local color="${NC}"
    
    case "${level}" in
        "INFO") color="${BLUE}" ;;
        "SUCCESS") color="${GREEN}" ;;
        "WARNING") color="${YELLOW}" ;;
        "ERROR") color="${RED}" ;;
    esac
    
    echo -e "${color}[$(date +%Y-%m-%d\ %H:%M:%S)] [${level}] ${message}${NC}" | tee -a "${LOG_FILE}"
}

# Print header
echo -e "${BOLD}${GREEN}"
echo "====================================================================="
echo "          IPFS MCP SERVER COMPLETE ENHANCED SOLUTION"
echo "====================================================================="
echo -e "${NC}"

log "INFO" "Starting solution at $(date)"
log "INFO" "Results will be stored in: ${RESULTS_DIR}"

# Step 1: Check environment
log "INFO" "Step 1: Checking environment"

# Verify that Python is installed
if ! command -v python3 &>/dev/null; then
    log "ERROR" "Python 3 is not installed or not in PATH"
    exit 1
fi

log "INFO" "Using Python: $(python3 --version)"

# Check for required files
REQUIRED_FILES=(
    "final_mcp_server.py"
    "unified_ipfs_tools.py"
    "fixed_ipfs_param_handling.py"
    "enhance_mock_implementations.py"
    "launch_enhanced_server.py"
    "enhanced_diagnostics.py"
    "test_parameter_handling.py"
)

missing_files=0
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "${file}" ]; then
        log "ERROR" "Required file not found: ${file}"
        missing_files=$((missing_files + 1))
    fi
done

if [ ${missing_files} -gt 0 ]; then
    log "ERROR" "${missing_files} required files are missing"
    exit 1
fi

log "SUCCESS" "All required files are present"

# Step 2: Run diagnostics
log "INFO" "Step 2: Running enhanced diagnostics"

python3 enhanced_diagnostics.py | tee -a "${LOG_FILE}"
diag_status=$?

if [ ${diag_status} -eq 0 ]; then
    log "SUCCESS" "Diagnostics completed successfully"
else
    log "WARNING" "Diagnostics reported issues, but continuing"
fi

# Copy diagnostic results to solution results directory
cp -r diagnostic_results/* "${RESULTS_DIR}/" 2>/dev/null || true

# Step 3: Apply mock implementation enhancements
log "INFO" "Step 3: Applying mock implementation enhancements"

python3 enhance_mock_implementations.py | tee -a "${LOG_FILE}"
enhance_status=$?

if [ ${enhance_status} -eq 0 ]; then
    log "SUCCESS" "Mock implementation enhancements applied successfully"
else
    log "ERROR" "Failed to apply mock implementation enhancements"
    exit 1
fi

# Step 4: Start the enhanced server
log "INFO" "Step 4: Starting enhanced server"

python3 launch_enhanced_server.py | tee -a "${LOG_FILE}" &
server_pid=$!

# Wait for server to start
log "INFO" "Waiting for server to start..."
sleep 5

# Check if server is running
if ! curl -s http://localhost:9998/health >/dev/null; then
    log "ERROR" "Server failed to start"
    exit 1
fi

log "SUCCESS" "Server started successfully"

# Step 5: Run parameter handling tests
log "INFO" "Step 5: Running parameter handling tests"

python3 test_parameter_handling.py | tee -a "${LOG_FILE}"
param_test_status=$?

if [ ${param_test_status} -eq 0 ]; then
    log "SUCCESS" "Parameter handling tests passed"
else
    log "ERROR" "Parameter handling tests failed"
    # Continue anyway to collect all results
fi

# Copy test results to solution results directory
cp -r test_results/* "${RESULTS_DIR}/" 2>/dev/null || true

# Step 6: Run verification
log "INFO" "Step 6: Running solution verification"

python3 verify_solution.py | tee -a "${LOG_FILE}"
verify_status=$?

if [ ${verify_status} -eq 0 ]; then
    log "SUCCESS" "Solution verification passed"
else
    log "WARNING" "Solution verification reported issues"
    # Continue anyway
fi

# Copy verification results to solution results directory
cp -r verification_results/* "${RESULTS_DIR}/" 2>/dev/null || true

# Step 7: Generate solution report
log "INFO" "Step 7: Generating solution report"

cat > "${RESULTS_DIR}/solution_report.md" << EOF
# IPFS MCP Server Enhanced Solution Report

Generated: $(date)

## Summary

| Component | Status |
|-----------|--------|
| Diagnostics | $([ ${diag_status} -eq 0 ] && echo "✅ Passed" || echo "❌ Failed") |
| Mock Enhancements | $([ ${enhance_status} -eq 0 ] && echo "✅ Passed" || echo "❌ Failed") |
| Parameter Tests | $([ ${param_test_status} -eq 0 ] && echo "✅ Passed" || echo "❌ Failed") |
| Solution Verification | $([ ${verify_status} -eq 0 ] && echo "✅ Passed" || echo "❌ Failed") |

## Overall Status

$([ ${diag_status} -eq 0 ] && [ ${enhance_status} -eq 0 ] && [ ${param_test_status} -eq 0 ] && echo "✅ SUCCESS: All components working properly" || echo "❌ ISSUES DETECTED: Some components reported problems")

## Details

- See individual component reports in this directory
- For detailed logs, see \`${LOG_FILE}\`
- For detailed documentation, see \`README_ENHANCED_SOLUTION.md\`

## Server Status

The enhanced server is currently running.
- URL: http://localhost:9998
- Health: http://localhost:9998/health
- JSON-RPC: http://localhost:9998/jsonrpc

## Next Steps

1. Review any failed components
2. Check specific logs for more details
3. Apply any additional fixes as needed
4. For production use, ensure all tests pass

EOF

log "SUCCESS" "Solution report generated: ${RESULTS_DIR}/solution_report.md"

# Step 8: Finalize
log "INFO" "Step 8: Finalizing solution"

# Copy log files and READMEs to results directory
cp README_ENHANCED_SOLUTION.md "${RESULTS_DIR}/"
cp ENHANCED_SOLUTION.md "${RESULTS_DIR}/" 2>/dev/null || true
cp *.log "${RESULTS_DIR}/" 2>/dev/null || true

# Determine overall status
if [ ${diag_status} -eq 0 ] && [ ${enhance_status} -eq 0 ] && [ ${param_test_status} -eq 0 ] && [ ${verify_status} -eq 0 ]; then
    overall_status=0
    log "SUCCESS" "Complete solution executed successfully!"
    log "SUCCESS" "The enhanced IPFS MCP server is running and fully operational"
else
    overall_status=1
    log "WARNING" "Complete solution executed with some issues"
    log "WARNING" "See ${RESULTS_DIR}/solution_report.md for details"
fi

log "INFO" "Server is running at http://localhost:9998"
log "INFO" "To stop the server: kill -15 $(cat enhanced_server.pid)"
log "INFO" "Solution results are available in: ${RESULTS_DIR}"

# Print final message
echo
echo -e "${BOLD}${GREEN}Solution completed.${NC}"
echo -e "Results directory: ${RESULTS_DIR}"
echo -e "Solution report: ${RESULTS_DIR}/solution_report.md"
echo

exit ${overall_status}
