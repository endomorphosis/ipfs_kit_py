# Test function to verify IPFS kit integration with MCP tools
test_ipfs_kit_integration() {
  log "INFO" "Testing comprehensive IPFS kit integration with MCP tools..." "IPFS-KIT"
  
  # Create test directory
  local test_dir="$RESULTS_DIR/ipfs_kit_integration_test"
  mkdir -p "$test_dir"
  
  # Create test file
  local test_file="$test_dir/test_content.txt"
  local test_content="This is a test file for IPFS kit integration with MCP tools $(date)"
  echo "$test_content" > "$test_file"
  
  # Test flow:
  # 1. Add file to IPFS via MCP tool
  # 2. Retrieve CID
  # 3. Import into VFS
  # 4. Modify via VFS
  # 5. Verify changes propagate to IPFS
  local ipfs_tools_working=true
  local vfs_tools_working=true
  local integration_working=true
  
  # Step 1: Add file to IPFS
  log "INFO" "Adding test file to IPFS via MCP tool..." "IPFS-KIT"
  local add_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"ipfs_add\",\"params\":{\"file_path\":\"$test_file\"},\"id\":1}")
  
  if [[ "$add_response" != *"cid"* ]] && [[ "$add_response" != *"Hash"* ]]; then
    log "ERROR" "Failed to add file to IPFS: $add_response" "IPFS-KIT"
    ipfs_tools_working=false
    return 1
  fi
  
  # Extract CID
  local cid=""
  if [[ "$add_response" == *"\"cid\""* ]]; then
    cid=$(echo "$add_response" | grep -o '"cid"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
  elif [[ "$add_response" == *"\"Hash\""* ]]; then
    cid=$(echo "$add_response" | grep -o '"Hash"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
  fi
  
  log "INFO" "Successfully added file to IPFS with CID: $cid" "IPFS-KIT"
  
  # Step 2: Verify retrieval from IPFS
  log "INFO" "Retrieving file from IPFS via MCP tool..." "IPFS-KIT"
  local cat_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"ipfs_cat\",\"params\":{\"cid\":\"$cid\"},\"id\":2}")
  
  if [[ "$cat_response" != *"$test_content"* ]]; then
    log "ERROR" "Failed to retrieve file from IPFS or content mismatch: $cat_response" "IPFS-KIT"
    ipfs_tools_working=false
  else
    log "SUCCESS" "Successfully retrieved file from IPFS with matching content" "IPFS-KIT"
  fi
  
  # Step 3: Test VFS import from IPFS
  local vfs_path="/ipfs-kit-test-$(date +%s)"
  local vfs_file="$vfs_path/imported.txt"
  
  log "INFO" "Creating VFS directory: $vfs_path" "IPFS-KIT"
  local mkdir_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_mkdir\",\"params\":{\"path\":\"$vfs_path\"},\"id\":3}")
  
  if [[ "$mkdir_response" != *"success"* ]] && [[ "$mkdir_response" != *"result"* ]]; then
    log "ERROR" "Failed to create VFS directory: $mkdir_response" "IPFS-KIT"
    vfs_tools_working=false
    return 1
  fi
  
  log "INFO" "Importing IPFS content to VFS: $vfs_file" "IPFS-KIT"
  local import_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_import\",\"params\":{\"path\":\"$vfs_file\",\"cid\":\"$cid\"},\"id\":4}")
  
  if [[ "$import_response" != *"result"* ]]; then
    log "ERROR" "Failed to import IPFS content to VFS: $import_response" "IPFS-KIT"
    integration_working=false
  else
    log "SUCCESS" "Successfully imported IPFS content to VFS" "IPFS-KIT"
    
    # Step 4: Verify VFS content
    log "INFO" "Verifying VFS file content..." "IPFS-KIT"
    local read_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_read\",\"params\":{\"path\":\"$vfs_file\"},\"id\":5}")
    
    if [[ "$read_response" != *"$test_content"* ]]; then
      log "ERROR" "VFS content doesn't match original: $read_response" "IPFS-KIT"
      vfs_tools_working=false
    else
      log "SUCCESS" "Successfully verified VFS content matches original" "IPFS-KIT"
      
      # Step 5: Modify VFS file and verify changes in IPFS
      local modified_content="$test_content\nModified via VFS on $(date)"
      log "INFO" "Modifying VFS file..." "IPFS-KIT"
      local write_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
        -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_write\",\"params\":{\"path\":\"$vfs_file\",\"content\":\"$modified_content\"},\"id\":6}")
      
      if [[ "$write_response" != *"result"* ]]; then
        log "ERROR" "Failed to modify VFS file: $write_response" "IPFS-KIT"
        vfs_tools_working=false
      else
        log "SUCCESS" "Successfully modified VFS file" "IPFS-KIT"
        
        # Get new CID
        log "INFO" "Getting CID of modified file..." "IPFS-KIT"
        local stat_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
          -H "Content-Type: application/json" \
          -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_stat\",\"params\":{\"path\":\"$vfs_file\"},\"id\":7}")
        
        local new_cid=""
        if [[ "$stat_response" == *"\"cid\""* ]]; then
          new_cid=$(echo "$stat_response" | grep -o '"cid"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
        elif [[ "$stat_response" == *"\"hash\""* ]]; then
          new_cid=$(echo "$stat_response" | grep -o '"hash"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
        fi
        
        if [ -z "$new_cid" ]; then
          log "ERROR" "Failed to get new CID for modified file" "IPFS-KIT"
          integration_working=false
        else
          log "INFO" "Got new CID after modification: $new_cid" "IPFS-KIT"
          
          # Verify modified content via IPFS
          log "INFO" "Verifying modified content via IPFS..." "IPFS-KIT"
          local new_cat_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
            -H "Content-Type: application/json" \
            -d "{\"jsonrpc\":\"2.0\",\"method\":\"ipfs_cat\",\"params\":{\"cid\":\"$new_cid\"},\"id\":8}")
          
          if [[ "$new_cat_response" != *"Modified via VFS"* ]]; then
            log "ERROR" "Modified content not reflected in IPFS: $new_cat_response" "IPFS-KIT"
            integration_working=false
          else
            log "SUCCESS" "Modified content successfully verified via IPFS" "IPFS-KIT"
          fi
        fi
      fi
    fi
  fi
  
  # Clean up
  log "INFO" "Cleaning up test files..." "IPFS-KIT"
  curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_rm\",\"params\":{\"path\":\"$vfs_file\"},\"id\":9}" > /dev/null
    
  curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_rmdir\",\"params\":{\"path\":\"$vfs_path\"},\"id\":10}" > /dev/null
  
  # Generate report
  local report_file="$RESULTS_DIR/ipfs_kit_integration_report_$(date +%Y%m%d_%H%M%S).md"
  cat > "$report_file" << EOF
# IPFS Kit Integration Test Report

Generated: $(date "+%Y-%m-%d %H:%M:%S")

## Test Results

| Component | Status | 
|-----------|--------|
| IPFS Tools | ${ipfs_tools_working:+"✅ WORKING"} ${ipfs_tools_working:="❌ FAILURE"} |
| VFS Tools | ${vfs_tools_working:+"✅ WORKING"} ${vfs_tools_working:="❌ FAILURE"} |
| Integration | ${integration_working:+"✅ WORKING"} ${integration_working:="❌ FAILURE"} |

## Test Details

- Test file: \`$test_file\`
- Original CID: \`$cid\`
- VFS Path: \`$vfs_file\`
- Modified CID: \`${new_cid:-"N/A"}\`

EOF
  
  log "INFO" "IPFS Kit integration test report written to: $report_file" "IPFS-KIT"
  
  # Return success if all components worked
  if $ipfs_tools_working && $vfs_tools_working && $integration_working; then
    log "SUCCESS" "IPFS Kit integration test passed" "IPFS-KIT"
    return 0
  else
    log "ERROR" "IPFS Kit integration test failed" "IPFS-KIT"
    return 1
  fi
}

# Function to verify IPFS kit functionality exposed as MCP tools
verify_ipfs_kit_tool_coverage() {
  log "INFO" "Verifying IPFS kit functionality exposed as MCP tools..." "COVERAGE"
  
  # Get list of all tools
  local tools_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
  
  # Check if the response contains tools
  if [ $? -ne 0 ] || [[ ! $tools_response == *"tools"* ]]; then
    log "ERROR" "Failed to get list of tools from the server" "COVERAGE"
    return 1
  fi
  
  # Extract all tools
  local all_tools=$(echo "$tools_response" | grep -o '"[^"]*"' | grep -v '"jsonrpc"' | grep -v '"id"' | grep -v '"method"' | grep -v '"result"' | grep -v '"tools"' | tr -d '"')
  
  # Define expected IPFS functions
  local expected_ipfs_functions=(
    "ipfs_add"
    "ipfs_cat"
    "ipfs_get"
    "ipfs_ls"
    "ipfs_version"
    "ipfs_pin_add"
    "ipfs_pin_rm"
    "ipfs_pin_ls"
    "ipfs_files_cp"
    "ipfs_files_write"
    "ipfs_files_read"
    "ipfs_files_mkdir"
    "ipfs_files_stat"
    "ipfs_files_ls"
    "ipfs_files_rm"
  )
  
  # Define expected VFS functions
  local expected_vfs_functions=(
    "vfs_read"
    "vfs_write"
    "vfs_mkdir"
    "vfs_rmdir"
    "vfs_ls"
    "vfs_rm"
    "vfs_mv"
    "vfs_cp"
    "vfs_stat"
    "vfs_import"
    "vfs_export"
  )
  
  # Count found functions
  local ipfs_found=0
  local vfs_found=0
  local missing_ipfs=()
  local missing_vfs=()
  
  # Check IPFS functions
  for func in "${expected_ipfs_functions[@]}"; do
    if echo "$all_tools" | grep -q "$func"; then
      ((ipfs_found++))
      log "DEBUG" "Found expected IPFS function: $func" "COVERAGE"
    else
      missing_ipfs+=("$func")
      log "WARNING" "Missing expected IPFS function: $func" "COVERAGE"
    fi
  done
  
  # Check VFS functions
  for func in "${expected_vfs_functions[@]}"; do
    if echo "$all_tools" | grep -q "$func"; then
      ((vfs_found++))
      log "DEBUG" "Found expected VFS function: $func" "COVERAGE"
    else
      missing_vfs+=("$func")
      log "WARNING" "Missing expected VFS function: $func" "COVERAGE"
    fi
  done
  
  # Calculate coverage percentages
  local ipfs_coverage=$((ipfs_found * 100 / ${#expected_ipfs_functions[@]}))
  local vfs_coverage=$((vfs_found * 100 / ${#expected_vfs_functions[@]}))
  local total_coverage=$(((ipfs_found + vfs_found) * 100 / (${#expected_ipfs_functions[@]} + ${#expected_vfs_functions[@]})))
  
  log "INFO" "IPFS functionality coverage: $ipfs_coverage%" "COVERAGE"
  log "INFO" "VFS functionality coverage: $vfs_coverage%" "COVERAGE"
  log "INFO" "Overall IPFS Kit integration coverage: $total_coverage%" "COVERAGE"
  
  # Generate coverage report
  local report_file="$RESULTS_DIR/ipfs_kit_coverage_$(date +%Y%m%d_%H%M%S).md"
  cat > "$report_file" << EOF
# IPFS Kit Tool Coverage Report

Generated: $(date "+%Y-%m-%d %H:%M:%S")

## Coverage Summary

| Category | Available | Expected | Coverage |
|----------|-----------|----------|----------|
| IPFS Tools | $ipfs_found | ${#expected_ipfs_functions[@]} | $ipfs_coverage% |
| VFS Tools | $vfs_found | ${#expected_vfs_functions[@]} | $vfs_coverage% |
| **Total** | $((ipfs_found + vfs_found)) | $((${#expected_ipfs_functions[@]} + ${#expected_vfs_functions[@]})) | $total_coverage% |

## Details

### Missing IPFS Functions
EOF

  if [ ${#missing_ipfs[@]} -eq 0 ]; then
    echo "- *None - All expected IPFS functions are implemented*" >> "$report_file"
  else
    for func in "${missing_ipfs[@]}"; do
      echo "- \`$func\`" >> "$report_file"
    done
  fi
  
  cat >> "$report_file" << EOF

### Missing VFS Functions
EOF

  if [ ${#missing_vfs[@]} -eq 0 ]; then
    echo "- *None - All expected VFS functions are implemented*" >> "$report_file"
  else
    for func in "${missing_vfs[@]}"; do
      echo "- \`$func\`" >> "$report_file"
    done
  fi
  
  cat >> "$report_file" << EOF

## Recommendations

Based on the coverage analysis, the following actions are recommended:

EOF

  if [ "$total_coverage" -lt 80 ]; then
    cat >> "$report_file" << EOF
- **High Priority**: Implement the missing functions to improve integration.
- Consider implementing the most critical missing functions first.
EOF
  elif [ "$total_coverage" -lt 95 ]; then
    cat >> "$report_file" << EOF
- **Medium Priority**: Add the remaining functions to achieve full coverage.
- Focus on implementing the most useful missing functions.
EOF
  else
    cat >> "$report_file" << EOF
- **Low Priority**: Coverage is already excellent.
- Consider implementing the few remaining functions for completeness.
EOF
  fi
  
  log "INFO" "Tool coverage report written to: $report_file" "COVERAGE"
  
  # Return success if coverage is acceptable (>75%)
  if [ "$total_coverage" -ge 75 ]; then
    return 0
  else
    return 1
  fi
}

# Function to restart and monitor MCP server
restart_and_monitor_server() {
  log "INFO" "Restarting and monitoring MCP server..." "MONITOR"
  
  # Stop the server if running
  stop_server
  
  # Record the start time
  local start_time=$(date +%s)
  
  # Start the server
  start_server || {
    log "ERROR" "Failed to start MCP server" "MONITOR"
    return 1
  }
  
  # Get the PID of the server
  local pid=$(cat "$SERVER_PID_FILE")
  log "INFO" "MCP server started with PID: $pid" "MONITOR"
  
  # Create monitoring log file
  local monitor_log="$RESULTS_DIR/server_monitor_$(date +%Y%m%d_%H%M%S).log"
  
  # Record initial stats
  log "INFO" "Recording initial stats to $monitor_log" "MONITOR"
  echo "=== MCP Server Monitoring Log - $(date) ===" > "$monitor_log"
  echo "Server PID: $pid" >> "$monitor_log"
  echo "Server File: $SERVER_FILE" >> "$monitor_log"
  echo "Port: $PORT" >> "$monitor_log"
  echo "" >> "$monitor_log"
  
  # Run a quick check of available tools
  local tools_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
  
  if [[ "$tools_response" == *"tools"* ]]; then
    # Count total, ipfs, and vfs tools
    local total_tools=$(echo "$tools_response" | grep -o '"tools"' | wc -l)
    local ipfs_tools=$(echo "$tools_response" | grep -o '"ipfs_[^"]*"' | wc -l)
    local vfs_tools=$(echo "$tools_response" | grep -o '"vfs_[^"]*"' | wc -l)
    
    echo "Initial Tool Count:" >> "$monitor_log"
    echo "- Total tools: $total_tools" >> "$monitor_log"
    echo "- IPFS tools: $ipfs_tools" >> "$monitor_log"
    echo "- VFS tools: $vfs_tools" >> "$monitor_log"
    echo "" >> "$monitor_log"
  else
    echo "WARNING: Could not get initial tool count" >> "$monitor_log"
  fi
  
  # Monitor process for 30 seconds
  log "INFO" "Monitoring server process for 30 seconds..." "MONITOR"
  local end_time=$((start_time + 30))
  local check_interval=5
  local iteration=1
  
  while [ $(date +%s) -lt $end_time ]; do
    # Check if process is still running
    if ! ps -p "$pid" > /dev/null; then
      log "ERROR" "Server process has died during monitoring" "MONITOR"
      echo "ERROR: Server process died at $(date)" >> "$monitor_log"
      return 1
    fi
    
    # Record process stats
    echo "=== Iteration $iteration - $(date) ===" >> "$monitor_log"
    ps -p "$pid" -o pid,ppid,user,%cpu,%mem,vsz,rss,stat,start,time,command >> "$monitor_log"
    echo "" >> "$monitor_log"
    
    # Test basic server functionality
    curl -s "$HEALTH_ENDPOINT" >> "$monitor_log" 2>&1
    echo "" >> "$monitor_log"
    
    # Test a ping call
    local ping_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}')
    echo "Ping response: $ping_response" >> "$monitor_log"
    echo "" >> "$monitor_log"
    
    # Increment and wait
    ((iteration++))
    sleep $check_interval
  done
  
  # Final health check
  log "INFO" "Performing final health check..." "MONITOR"
  if curl -s "$HEALTH_ENDPOINT" | grep -q "ok"; then
    log "SUCCESS" "Server is healthy after monitoring period" "MONITOR"
    echo "FINAL STATUS: Server is healthy after monitoring period" >> "$monitor_log"
    return 0
  else
    log "ERROR" "Server is not responding healthily after monitoring period" "MONITOR"
    echo "FINAL STATUS: Server is not responding healthily" >> "$monitor_log"
    return 1
  fi
}
