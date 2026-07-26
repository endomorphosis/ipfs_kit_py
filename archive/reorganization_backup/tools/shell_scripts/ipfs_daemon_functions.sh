# Function to ensure IPFS daemon is running
ensure_ipfs_daemon_running() {
  log "INFO" "Ensuring IPFS daemon is running..." "IPFS"
  
  # Check if IPFS is installed
  if ! command -v ipfs &> /dev/null; then
    log "ERROR" "IPFS is not installed. Please install it and try again." "IPFS"
    log "INFO" "You can install IPFS from https://docs.ipfs.tech/install/command-line/" "IPFS"
    return 1
  else
    local ipfs_version=$(ipfs --version)
    log "INFO" "IPFS is installed: $ipfs_version" "IPFS"
  fi
  
  # Check if IPFS daemon is running
  if ! pgrep -x "ipfs" > /dev/null; then
    log "WARNING" "IPFS daemon is not running. Attempting to start it..." "IPFS"
    
    # Start IPFS daemon in background and redirect output to log file
    mkdir -p "$(dirname "$IPFS_LOG_FILE")"
    ipfs daemon --init &> "$IPFS_LOG_FILE" &
    
    # Save IPFS daemon PID
    local ipfs_pid=$!
    log "INFO" "Started IPFS daemon with PID: $ipfs_pid" "IPFS"
    
    # Wait for IPFS daemon to initialize
    log "INFO" "Waiting for IPFS daemon to initialize..." "IPFS"
    local timeout=30
    local elapsed=0
    local interval=1
    
    while [ $elapsed -lt $timeout ]; do
      # Check if daemon is responsive
      if ipfs swarm peers &> /dev/null; then
        log "SUCCESS" "IPFS daemon is running and responsive" "IPFS"
        return 0
      fi
      
      # Check if daemon is still running
      if ! kill -0 $ipfs_pid 2> /dev/null; then
        log "ERROR" "IPFS daemon process terminated unexpectedly" "IPFS"
        log "ERROR" "Check the log file for details: $IPFS_LOG_FILE" "IPFS"
        return 1
      fi
      
      sleep $interval
      elapsed=$((elapsed + interval))
      if [ $((elapsed % 5)) -eq 0 ]; then
        log "INFO" "Still waiting for IPFS daemon to initialize... (${elapsed}s)" "IPFS"
      fi
    done
    
    log "ERROR" "Timed out waiting for IPFS daemon to initialize" "IPFS"
    return 1
  else
    # IPFS daemon is already running, check if it's responsive
    if ipfs swarm peers &> /dev/null; then
      log "SUCCESS" "IPFS daemon is already running and responsive" "IPFS"
      return 0
    else
      log "WARNING" "IPFS daemon is running but not responsive. Attempting to restart..." "IPFS"
      
      # Kill existing daemon
      pkill -x "ipfs"
      sleep 2
      
      # Start a new daemon
      ipfs daemon --init &> "$IPFS_LOG_FILE" &
      
      # Save IPFS daemon PID
      local ipfs_pid=$!
      log "INFO" "Restarted IPFS daemon with PID: $ipfs_pid" "IPFS"
      
      # Wait for daemon to initialize
      local timeout=30
      local elapsed=0
      local interval=1
      
      while [ $elapsed -lt $timeout ]; do
        if ipfs swarm peers &> /dev/null; then
          log "SUCCESS" "IPFS daemon is now running and responsive" "IPFS"
          return 0
        fi
        
        sleep $interval
        elapsed=$((elapsed + interval))
      done
      
      log "ERROR" "Timed out waiting for IPFS daemon to initialize after restart" "IPFS"
      return 1
    fi
  fi
}
