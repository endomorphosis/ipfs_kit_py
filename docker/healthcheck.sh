#!/bin/bash
set -e

# Function to log with timestamp
log() {
  echo "[$(date --rfc-3339=seconds)] $1"
}

# Check the IPFS HTTP API
check_ipfs_api() {
  if ! curl -s -f -m 5 "http://localhost:5001/api/v0/id" > /dev/null; then
    log "IPFS API check failed"
    return 1
  fi
  return 0
}

# Check the IPFS Gateway
check_ipfs_gateway() {
  if ! curl -s -f -m 5 "http://localhost:8080/ipfs/QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn" > /dev/null; then
    log "IPFS Gateway check failed"
    return 1
  fi
  return 0
}

# Check IPFS Cluster API (for master and worker roles)
check_ipfs_cluster() {
  # Only check cluster if we're in master or worker role
  if [[ "$ROLE" == "master" || "$ROLE" == "worker" ]]; then
    if ! curl -s -f -m 5 "http://localhost:9094/id" > /dev/null; then
      log "IPFS Cluster API check failed"
      return 1
    fi
  fi
  return 0
}

# Check for running Python server process
check_python_process() {
  if ! pgrep -f "uvicorn ipfs_kit_py.daemon:app" > /dev/null; then
    log "Python server process check failed"
    return 1
  fi
  return 0
}

# Main check function
main() {
  # Check Python process first (most fundamental)
  if ! check_python_process; then
    return 1
  fi
  
  # Check IPFS API
  if ! check_ipfs_api; then
    return 1
  fi
  
  # Check IPFS Gateway
  if ! check_ipfs_gateway; then
    return 1
  fi
  
  # Check IPFS Cluster if applicable
  if ! check_ipfs_cluster; then
    return 1
  fi
  
  # All checks passed
  return 0
}

# Run the checks
main
exit $?