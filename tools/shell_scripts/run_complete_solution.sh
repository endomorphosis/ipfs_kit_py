#!/bin/bash
# Complete Solution Runner
# This script runs the entire IPFS MCP solution with all enhancements

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BOLD}${GREEN}"
echo "====================================================================="
echo "                  IPFS MCP SERVER ENHANCED SOLUTION                   "
echo "====================================================================="
echo -e "${NC}"
echo "Starting comprehensive solution run at $(date)"
echo

# Create results directory
RESULTS_DIR="run_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"
LOGFILE="$RESULTS_DIR/run.log"

# Log both to file and console
log() {
    local level="$1"
    local message="$2"
    local color="$NC"
    
    case "$level" in
        "INFO") color="$BLUE";;
        "SUCCESS") color="$GREEN";;
        "ERROR") color="$RED";;
        "WARNING") color="$YELLOW";;
    esac
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}" | tee -a "$LOGFILE"
}

# Step 1: Run verification
log "INFO" "Step 1: Verifying solution components"
python3 verify_solution.py | tee -a "$LOGFILE"
VERIFY_STATUS=$?

if [ $VERIFY_STATUS -ne 0 ]; then
    log "WARNING" "Some verification checks failed, but continuing with solution run"
fi

# Step 2: Run enhanced diagnostics
log "INFO" "Step 2: Running enhanced diagnostics"
python3 enhanced_diagnostics.py | tee -a "$LOGFILE"
DIAG_STATUS=$?

if [ $DIAG_STATUS -ne 0 ]; then
    log "WARNING" "Some diagnostic checks failed, but continuing with solution run"
fi

# Step 3: Run the enhanced solution
log "INFO" "Step 3: Running enhanced solution"
./run_enhanced_solution.sh | tee -a "$LOGFILE"
SOLUTION_STATUS=$?

# Step 4: Run the comprehensive test suite
log "INFO" "Step 4: Running comprehensive test suite"
python3 mcp_test_suite.py | tee -a "$LOGFILE"
TEST_STATUS=$?

# Generate final report
log "INFO" "Generating final solution report"

cat > "$RESULTS_DIR/solution_summary.md" << EOF
# IPFS MCP Server Enhanced Solution Summary

Generated: $(date)

## Overview

This report summarizes the results of running the enhanced IPFS MCP server solution.

## Results

| Component | Status | Details |
|-----------|--------|---------|
| Verification | $(if [ $VERIFY_STATUS -eq 0 ]; then echo "✅ Passed"; else echo "❌ Failed"; fi) | See verification_results/ |
| Diagnostics | $(if [ $DIAG_STATUS -eq 0 ]; then echo "✅ Passed"; else echo "❌ Failed"; fi) | See diagnostic_results/ |
| Enhanced Solution | $(if [ $SOLUTION_STATUS -eq 0 ]; then echo "✅ Passed"; else echo "❌ Failed"; fi) | See run_enhanced_solution.sh |
| Test Suite | $(if [ $TEST_STATUS -eq 0 ]; then echo "✅ Passed"; else echo "❌ Failed"; fi) | See test_results/ |

## Overall Status

$(if [ $VERIFY_STATUS -eq 0 ] && [ $SOLUTION_STATUS -eq 0 ] && [ $TEST_STATUS -eq 0 ]; then echo "✅ SUCCESS: All components working properly"; else echo "❌ ISSUES DETECTED: Some components failed"; fi)

## Documentation

Full documentation for the enhanced solution can be found in ENHANCED_SOLUTION.md.

## Next Steps

1. Review any failed components
2. Check specific logs for more details
3. Apply any additional fixes as needed
4. For production use, ensure parameter handling is properly implemented

EOF

# Final status
log "INFO" "Complete solution run finished"

if [ $VERIFY_STATUS -eq 0 ] && [ $SOLUTION_STATUS -eq 0 ] && [ $TEST_STATUS -eq 0 ]; then
    log "SUCCESS" "All components are working successfully!"
    log "SUCCESS" "The enhanced MCP solution is ready for use"
else
    log "WARNING" "Some components have issues. Check $RESULTS_DIR/solution_summary.md for details"
fi

echo
echo -e "${BOLD}${GREEN}Solution run complete. Results available in: $RESULTS_DIR${NC}"
echo

# Copy important files to results directory for reference
cp enhanced_diagnostics.log "$RESULTS_DIR/"
cp verify_solution.py "$RESULTS_DIR/"
cp ENHANCED_SOLUTION.md "$RESULTS_DIR/"
cp mcp_test_suite.log "$RESULTS_DIR/" 2>/dev/null || true
cp solution_verification.log "$RESULTS_DIR/" 2>/dev/null || true
