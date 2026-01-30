#!/bin/bash
# GitHub CLI Caching Wrapper for Bash/Shell Scripts
#
# This script provides a drop-in replacement for 'gh' command that uses caching
# to reduce GitHub API rate limit usage.
#
# Usage:
#   source gh_cache_wrapper.sh
#   gh repo list    # Uses cache
#   gh_nocache repo list   # Bypasses cache
#   gh_cache_stats  # Show cache statistics

# Configuration
export GH_CACHE_DIR="${GH_CACHE_DIR:-$HOME/.ipfs_kit/gh_cache}"
export GH_CACHE_ENABLED="${GH_CACHE_ENABLED:-1}"
export GH_CACHE_IPFS="${GH_CACHE_IPFS:-0}"
export GH_CACHE_DEBUG="${GH_CACHE_DEBUG:-0}"

# Colors for output
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Initialize cache directory
init_gh_cache() {
    mkdir -p "$GH_CACHE_DIR"
    
    if [ "$GH_CACHE_DEBUG" = "1" ]; then
        echo -e "${BLUE}📦 GitHub CLI cache initialized: $GH_CACHE_DIR${NC}" >&2
    fi
}

# Check if Python is available
check_python_cache() {
    if command -v python3 &> /dev/null; then
        # Check if gh_cache module is available
        python3 -c "from ipfs_kit_py.gh_cache import GHCache" 2>/dev/null
        return $?
    fi
    return 1
}

# Generate cache key for a command
generate_cache_key() {
    local cmd="$*"
    local user="${USER:-default}"
    echo -n "${user}:${cmd}" | sha256sum | cut -d' ' -f1
}

# Get TTL for a command (in seconds)
get_command_ttl() {
    local cmd="$*"
    
    # Immutable data - 1 year
    if [[ "$cmd" =~ (commit|release\ view) ]]; then
        echo "31536000"
        return
    fi
    
    # Repository metadata - 1 hour
    if [[ "$cmd" =~ (repo\ view|repo\ list) ]]; then
        echo "3600"
        return
    fi
    
    # User data - 1 hour
    if [[ "$cmd" =~ (api\ /user|auth\ status) ]]; then
        echo "3600"
        return
    fi
    
    # Workflow runs - 5 minutes
    if [[ "$cmd" =~ (run\ list|run\ view|run\ download) ]]; then
        echo "300"
        return
    fi
    
    # PR data - 2 minutes
    if [[ "$cmd" =~ (pr\ list|pr\ view|pr\ diff|pr\ checks) ]]; then
        echo "120"
        return
    fi
    
    # Issue data - 2 minutes
    if [[ "$cmd" =~ (issue\ list|issue\ view) ]]; then
        echo "120"
        return
    fi
    
    # Default - 1 minute
    echo "60"
}

# Check if command should be cached
should_cache_command() {
    local cmd="$*"
    
    # Don't cache write operations
    local no_cache_patterns=(
        "pr create" "pr merge" "pr close" "pr comment" "pr edit" "pr ready"
        "issue create" "issue comment" "issue close" "issue edit"
        "release create" "release upload" "release delete"
        "repo create" "repo delete" "repo fork"
        "secret set" "secret delete"
        "variable set" "variable delete"
        "workflow run"
    )
    
    for pattern in "${no_cache_patterns[@]}"; do
        if [[ "$cmd" =~ $pattern ]]; then
            return 1  # Don't cache
        fi
    done
    
    return 0  # Cache
}

# Check if cache entry is valid
is_cache_valid() {
    local cache_file="$1"
    local ttl="$2"
    
    if [ ! -f "$cache_file" ]; then
        return 1  # Cache miss
    fi
    
    local cache_age=$(( $(date +%s) - $(stat -c %Y "$cache_file" 2>/dev/null || stat -f %m "$cache_file" 2>/dev/null) ))
    
    if [ "$cache_age" -gt "$ttl" ]; then
        return 1  # Cache expired
    fi
    
    return 0  # Cache valid
}

# Cached gh command (Python-based)
gh_cached_python() {
    local cache_args=""
    
    if [ "$GH_CACHE_IPFS" = "1" ]; then
        cache_args="$cache_args --enable-ipfs"
    fi
    
    if [ "$GH_CACHE_DEBUG" = "1" ]; then
        cache_args="$cache_args --verbose"
    fi
    
    python3 -m ipfs_kit_py.gh_cache $cache_args gh "$@"
    return $?
}

# Cached gh command (shell-based fallback)
gh_cached_shell() {
    local cmd="gh $*"
    
    # Check if should cache
    if ! should_cache_command "$cmd"; then
        if [ "$GH_CACHE_DEBUG" = "1" ]; then
            echo -e "${YELLOW}⚠️  Bypassing cache: $cmd${NC}" >&2
        fi
        command gh "$@"
        return $?
    fi
    
    # Generate cache key
    local cache_key=$(generate_cache_key "$cmd")
    local cache_file="$GH_CACHE_DIR/${cache_key}.txt"
    local ttl=$(get_command_ttl "$cmd")
    
    # Check cache
    if is_cache_valid "$cache_file" "$ttl"; then
        if [ "$GH_CACHE_DEBUG" = "1" ]; then
            echo -e "${GREEN}✅ Cache HIT: $cmd${NC}" >&2
        fi
        cat "$cache_file"
        return 0
    fi
    
    # Cache miss - execute command
    if [ "$GH_CACHE_DEBUG" = "1" ]; then
        echo -e "${RED}❌ Cache MISS: $cmd${NC}" >&2
    fi
    
    # Execute and cache result
    local output=$(command gh "$@" 2>&1)
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "$output" > "$cache_file"
    fi
    
    echo "$output"
    return $exit_code
}

# Main gh wrapper function
gh() {
    # Initialize cache on first use
    if [ ! -d "$GH_CACHE_DIR" ]; then
        init_gh_cache
    fi
    
    # Check if caching is disabled
    if [ "$GH_CACHE_ENABLED" != "1" ]; then
        command gh "$@"
        return $?
    fi
    
    # Try Python-based caching first
    if check_python_cache; then
        gh_cached_python "$@"
        return $?
    fi
    
    # Fallback to shell-based caching
    if [ "$GH_CACHE_DEBUG" = "1" ]; then
        echo -e "${YELLOW}⚠️  Using shell-based cache (Python cache not available)${NC}" >&2
    fi
    gh_cached_shell "$@"
    return $?
}

# Bypass cache for single command
gh_nocache() {
    command gh "$@"
}

# Clear cache
gh_cache_clear() {
    if [ -z "$1" ]; then
        # Clear all
        rm -rf "$GH_CACHE_DIR"/*.txt
        echo -e "${GREEN}🗑️  Cleared all cache entries${NC}"
    else
        # Clear matching entries
        local pattern="$1"
        local count=0
        for file in "$GH_CACHE_DIR"/*.txt; do
            if [ -f "$file" ]; then
                # This is a simple implementation - doesn't check command content
                rm -f "$file"
                ((count++))
            fi
        done
        echo -e "${GREEN}🗑️  Cleared $count cache entries${NC}"
    fi
}

# Show cache statistics
gh_cache_stats() {
    if [ ! -d "$GH_CACHE_DIR" ]; then
        echo "Cache directory not initialized"
        return
    fi
    
    local total_files=$(ls -1 "$GH_CACHE_DIR"/*.txt 2>/dev/null | wc -l)
    local total_size=$(du -sh "$GH_CACHE_DIR" 2>/dev/null | cut -f1)
    
    echo -e "\n${BLUE}📊 GitHub CLI Cache Statistics:${NC}"
    echo "   Cache Dir: $GH_CACHE_DIR"
    echo "   Cache Entries: $total_files"
    echo "   Cache Size: $total_size"
    echo "   Python Cache: $(check_python_cache && echo 'Available' || echo 'Not Available')"
    echo "   IPFS Enabled: $([ "$GH_CACHE_IPFS" = "1" ] && echo 'Yes' || echo 'No')"
    echo ""
}

# Export functions
export -f gh
export -f gh_nocache
export -f gh_cache_clear
export -f gh_cache_stats

# Auto-initialize
init_gh_cache

if [ "$GH_CACHE_DEBUG" = "1" ]; then
    echo -e "${GREEN}✅ GitHub CLI caching enabled${NC}" >&2
    echo -e "${BLUE}   Use 'gh' for cached commands${NC}" >&2
    echo -e "${BLUE}   Use 'gh_nocache' to bypass cache${NC}" >&2
    echo -e "${BLUE}   Use 'gh_cache_stats' for statistics${NC}" >&2
fi
