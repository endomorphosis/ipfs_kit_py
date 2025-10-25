#!/bin/bash

# Installation Wrapper Script with Monitoring
# This script wraps any installation command with detailed logging and monitoring
# for use in GitHub Actions ARM64 workflows

set -euo pipefail

# Configuration
LOG_DIR="${LOG_DIR:-/tmp/arm64_install_logs}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SCRIPT_NAME="${1:-unknown}"
shift || true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create log directory
mkdir -p "$LOG_DIR"

# Log files
STDOUT_LOG="$LOG_DIR/${SCRIPT_NAME}_${TIMESTAMP}_stdout.log"
STDERR_LOG="$LOG_DIR/${SCRIPT_NAME}_${TIMESTAMP}_stderr.log"
COMBINED_LOG="$LOG_DIR/${SCRIPT_NAME}_${TIMESTAMP}_combined.log"
METRICS_LOG="$LOG_DIR/${SCRIPT_NAME}_${TIMESTAMP}_metrics.json"

# Function to log with timestamp
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)
            echo -e "${BLUE}[INFO]${NC} [$timestamp] $message" | tee -a "$COMBINED_LOG"
            ;;
        SUCCESS)
            echo -e "${GREEN}[SUCCESS]${NC} [$timestamp] $message" | tee -a "$COMBINED_LOG"
            ;;
        WARNING)
            echo -e "${YELLOW}[WARNING]${NC} [$timestamp] $message" | tee -a "$COMBINED_LOG"
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} [$timestamp] $message" | tee -a "$COMBINED_LOG"
            ;;
        *)
            echo "[$timestamp] $message" | tee -a "$COMBINED_LOG"
            ;;
    esac
}

# Function to collect system metrics
collect_system_metrics() {
    local metrics_file=$1
    
    cat > "$metrics_file" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "script": "$SCRIPT_NAME",
  "system": {
    "architecture": "$(uname -m)",
    "kernel": "$(uname -r)",
    "os": "$(lsb_release -ds 2>/dev/null || echo 'Unknown')",
    "cpu_count": "$(nproc)",
    "memory_total_kb": "$(grep MemTotal /proc/meminfo | awk '{print $2}')",
    "memory_available_kb": "$(grep MemAvailable /proc/meminfo | awk '{print $2}')",
    "disk_space": "$(df -h / | tail -1 | awk '{print $4}')"
  },
  "environment": {
    "PATH": "$PATH",
    "PYTHON_VERSION": "$(python3 --version 2>&1 || echo 'Not installed')",
    "GO_VERSION": "$(go version 2>&1 || echo 'Not installed')",
    "GCC_VERSION": "$(gcc --version 2>&1 | head -1 || echo 'Not installed')"
  }
}
EOF
}

# Function to add to GitHub Actions summary
add_to_github_summary() {
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        cat >> "$GITHUB_STEP_SUMMARY" <<EOF

## Installation Monitoring: $SCRIPT_NAME

**Timestamp**: $(date -Iseconds)  
**Duration**: ${ELAPSED_TIME}s  
**Status**: $1

### System Information
- **Architecture**: $(uname -m)
- **CPU Cores**: $(nproc)
- **Available Memory**: $(grep MemAvailable /proc/meminfo | awk '{print $2}') KB
- **Disk Space**: $(df -h / | tail -1 | awk '{print $4}')

### Logs
- Combined log: \`$COMBINED_LOG\`
- Stdout log: \`$STDOUT_LOG\`
- Stderr log: \`$STDERR_LOG\`
- Metrics: \`$METRICS_LOG\`

EOF
        if [ "$1" = "SUCCESS" ]; then
            echo "✅ Installation completed successfully" >> "$GITHUB_STEP_SUMMARY"
        else
            echo "❌ Installation failed" >> "$GITHUB_STEP_SUMMARY"
            echo "" >> "$GITHUB_STEP_SUMMARY"
            echo "### Error Log (last 20 lines)" >> "$GITHUB_STEP_SUMMARY"
            echo '```' >> "$GITHUB_STEP_SUMMARY"
            tail -20 "$STDERR_LOG" >> "$GITHUB_STEP_SUMMARY" 2>/dev/null || echo "No error log available"
            echo '```' >> "$GITHUB_STEP_SUMMARY"
        fi
    fi
}

# Main execution
main() {
    log INFO "==================================================================="
    log INFO "Installation Wrapper - Monitoring: $SCRIPT_NAME"
    log INFO "==================================================================="
    
    # Collect pre-execution metrics
    log INFO "Collecting system metrics..."
    collect_system_metrics "$METRICS_LOG"
    
    # Display system information
    log INFO "System Information:"
    log INFO "  Architecture: $(uname -m)"
    log INFO "  Kernel: $(uname -r)"
    log INFO "  CPU Cores: $(nproc)"
    log INFO "  Memory Available: $(grep MemAvailable /proc/meminfo | awk '{print $2}') KB"
    log INFO "  Disk Space: $(df -h / | tail -1 | awk '{print $4}')"
    
    if [ $# -eq 0 ]; then
        log ERROR "No command specified to monitor"
        exit 1
    fi
    
    log INFO "Executing command: $@"
    log INFO "Logs will be saved to:"
    log INFO "  - Combined: $COMBINED_LOG"
    log INFO "  - Stdout: $STDOUT_LOG"
    log INFO "  - Stderr: $STDERR_LOG"
    log INFO "  - Metrics: $METRICS_LOG"
    
    # Execute the command
    START_TIME=$(date +%s)
    
    set +e
    "$@" > >(tee -a "$STDOUT_LOG" "$COMBINED_LOG") 2> >(tee -a "$STDERR_LOG" "$COMBINED_LOG" >&2)
    EXIT_CODE=$?
    set -e
    
    END_TIME=$(date +%s)
    ELAPSED_TIME=$((END_TIME - START_TIME))
    
    log INFO "==================================================================="
    log INFO "Execution completed"
    log INFO "  Exit Code: $EXIT_CODE"
    log INFO "  Duration: ${ELAPSED_TIME}s"
    log INFO "==================================================================="
    
    # Add execution results to metrics
    cat >> "$METRICS_LOG" <<EOF
,
  "execution": {
    "command": "$@",
    "start_time": $START_TIME,
    "end_time": $END_TIME,
    "duration_seconds": $ELAPSED_TIME,
    "exit_code": $EXIT_CODE
  }
}
EOF
    
    # Add to GitHub Actions summary
    if [ $EXIT_CODE -eq 0 ]; then
        log SUCCESS "Command executed successfully"
        add_to_github_summary "SUCCESS"
    else
        log ERROR "Command failed with exit code $EXIT_CODE"
        add_to_github_summary "FAILED"
        
        # Show last lines of error log
        if [ -s "$STDERR_LOG" ]; then
            log ERROR "Last 10 lines of stderr:"
            tail -10 "$STDERR_LOG" | while IFS= read -r line; do
                log ERROR "  $line"
            done
        fi
    fi
    
    # Upload logs as artifacts if in GitHub Actions
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
        log INFO "GitHub Actions detected - logs available as artifacts"
    fi
    
    return $EXIT_CODE
}

# Run main function
main "$@"
