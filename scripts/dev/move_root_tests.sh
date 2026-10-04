#!/bin/bash

# Function to determine the best target directory for a test file
determine_target_dir() {
    local filename=$1
    
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

# Loop through all test files in the root directory and move them to appropriate test directories
for file in $(find . -maxdepth 1 -name "test_*.py"); do
    filename=$(basename "$file")
    target_dir=$(determine_target_dir "$filename")
    echo "Moving $file to $target_dir$filename"
    mv "$file" "$target_dir$filename"
done

echo "All root test files have been moved to the test directory structure."
