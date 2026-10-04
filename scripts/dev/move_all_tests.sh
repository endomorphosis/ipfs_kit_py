#!/bin/bash

# Function to determine the best target directory for a test file
determine_target_dir() {
    local file=$1
    local filename=$(basename "$file")
    
    # MCP-related tests
    if [[ "$filename" == *"mcp"* ]]; then
        if [[ "$filename" == *"controller"* ]]; then
            echo "test/mcp/controller/"
        elif [[ "$filename" == *"model"* ]]; then
            echo "test/mcp/model/"
        elif [[ "$filename" == *"server"* ]]; then
            echo "test/mcp/server/"
        else
            echo "test/mcp/"
        fi
        return
    fi
    
    # WebRTC tests
    if [[ "$filename" == *"webrtc"* ]]; then
        echo "test/integration/webrtc/"
        return
    fi
    
    # API tests
    if [[ "$filename" == *"api"* ]]; then
        echo "test/unit/api/"
        return
    fi
    
    # IPFS tests
    if [[ "$filename" == *"ipfs"* ]]; then
        echo "test/integration/ipfs/"
        return
    fi
    
    # libp2p tests
    if [[ "$filename" == *"libp2p"* ]]; then
        echo "test/integration/libp2p/"
        return
    fi
    
    # Storage tests
    if [[ "$filename" == *"storage"* || "$filename" == *"s3"* || "$filename" == *"storacha"* ]]; then
        echo "test/unit/storage/"
        return
    fi
    
    # CLI tests
    if [[ "$filename" == *"cli"* ]]; then
        echo "test/functional/cli/"
        return
    fi
    
    # Filecoin tests
    if [[ "$filename" == *"filecoin"* || "$filename" == *"lotus"* ]]; then
        echo "test/integration/lotus/"
        return
    fi
    
    # Discovery tests
    if [[ "$filename" == *"discovery"* ]]; then
        echo "test/integration/libp2p/"
        return
    fi

    # WAL tests
    if [[ "$filename" == *"wal"* ]]; then
        echo "test/unit/wal/"
        return
    fi
    
    # AI/ML tests
    if [[ "$filename" == *"ai_ml"* || "$filename" == *"huggingface"* ]]; then
        echo "test/unit/ai_ml/"
        return
    fi
    
    # Default to unit/core for anything else
    echo "test/unit/core/"
}

# Move all test files into the appropriate directories
find_test_files() {
    find . -path "./test" -prune -o -name "test_*.py" -not -path "*venv*" -not -path "*/node_modules*" -not -path "*/lib/python*" -not -path "*/docs/*" -print
}

move_test_files() {
    for file in $(find_test_files); do
        target_dir=$(determine_target_dir "$file")
        mkdir -p "$target_dir"
        echo "Moving $file to $target_dir"
        cp "$file" "$target_dir"
    done
}

# Create required directories if they don't exist
mkdir -p test/unit/api test/unit/core test/unit/storage test/unit/ai_ml test/unit/wal
mkdir -p test/integration/ipfs test/integration/libp2p test/integration/lotus test/integration/s3 test/integration/storacha test/integration/webrtc
mkdir -p test/functional/cli test/functional/filesystem test/functional/streaming
mkdir -p test/mcp/controller test/mcp/model test/mcp/server
mkdir -p test/performance

# Move the tests
move_test_files

# Handle test_discovery directory separately
if [ -d "test_discovery" ]; then
    echo "Moving tests from test_discovery directory"
    for file in $(find test_discovery -name "test_*.py"); do
        cp "$file" "test/integration/libp2p/"
    done
fi

echo "All test files have been copied to the test directory structure."
