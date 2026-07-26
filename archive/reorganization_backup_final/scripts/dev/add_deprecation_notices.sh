#!/bin/bash
# add_deprecation_notices.sh
# This script adds deprecation notices to all start_* and run_* files

# Function to add deprecation notice to python files
add_python_deprecation() {
    local file=$1
    local replacement=$2
    
    # Check if file exists
    if [ ! -f "$file" ]; then
        echo "File not found: $file"
        return
    fi
    
    # Create backup of original file if it doesn't already have one
    if [[ ! -f "${file}.bak_$(date +%Y%m%d_%H%M%S)" ]]; then
        cp "$file" "${file}.bak_$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Get the first line of the file to check if it's a shebang
    first_line=$(head -n 1 "$file")
    
    if [[ "$first_line" == "#!/usr/bin/env python"* ]]; then
        # If the file starts with a shebang, keep it and replace everything after it
        sed -i "1a\\
\"\"\"\\
DEPRECATED: This script has been replaced by $replacement\\
\\
This file is kept for reference only. Please use the new consolidated script instead.\\
See the README.md file for more information about the consolidated files.\\
\"\"\"\\
\\
# Original content follows:\\
" "$file"
    else
        # If no shebang, add deprecation notice at the beginning
        sed -i "1i\\
#!/usr/bin/env python3\\
\"\"\"\\
DEPRECATED: This script has been replaced by $replacement\\
\\
This file is kept for reference only. Please use the new consolidated script instead.\\
See the README.md file for more information about the consolidated files.\\
\"\"\"\\
\\
# Original content follows:\\
" "$file"
    fi
    
    echo "Added deprecation notice to $file"
}

# Function to add deprecation notice to shell scripts
add_shell_deprecation() {
    local file=$1
    local replacement=$2
    
    # Check if file exists
    if [ ! -f "$file" ]; then
        echo "File not found: $file"
        return
    fi
    
    # Create backup of original file if it doesn't already have one
    if [[ ! -f "${file}.bak_$(date +%Y%m%d_%H%M%S)" ]]; then
        cp "$file" "${file}.bak_$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Get the first line of the file to check if it's a shebang
    first_line=$(head -n 1 "$file")
    
    if [[ "$first_line" == "#!/bin/bash" || "$first_line" == "#!/usr/bin/env bash" ]]; then
        # If the file starts with a bash shebang, keep it and replace everything after it
        sed -i "1a\\
# DEPRECATED: This script has been replaced by $replacement\\
#\\
# This file is kept for reference only. Please use the new consolidated script instead.\\
# See the README.md file for more information about the consolidated files.\\
\\
# Original content follows:\\
" "$file"
    else
        # If no shebang, add deprecation notice at the beginning
        sed -i "1i\\
#!/bin/bash\\
# DEPRECATED: This script has been replaced by $replacement\\
#\\
# This file is kept for reference only. Please use the new consolidated script instead.\\
# See the README.md file for more information about the consolidated files.\\
\\
# Original content follows:\\
" "$file"
    fi
    
    echo "Added deprecation notice to $file"
}

# Process all run_* files (Python)
echo "Processing run_* Python files..."
for file in run_*.py; do
    # Skip the new consolidated files
    if [[ "$file" == "mcp_server_runner.py" || "$file" == "mcp_test_runner.py" ]]; then
        continue
    fi
    
    # Handle based on file type
    if [[ "$file" == *"_test"* || "$file" == *"tests"* ]]; then
        add_python_deprecation "$file" "mcp_test_runner.py"
    elif [[ "$file" == *"mcp_server"* || "$file" == *"enhanced_mcp"* ]]; then
        add_python_deprecation "$file" "mcp_server_runner.py"
    else
        # For other run files, determine by content
        if grep -q "test" "$file"; then
            add_python_deprecation "$file" "mcp_test_runner.py"
        else
            add_python_deprecation "$file" "mcp_server_runner.py"
        fi
    fi
done

# Process all start_* files (Python)
echo "Processing start_* Python files..."
for file in start_*.py; do
    # Skip the new consolidated file
    if [[ "$file" == "daemon_manager.py" ]]; then
        continue
    fi
    
    # Handle based on file type
    if [[ "$file" == *"daemon"* || "$file" == *"ipfs"* || "$file" == *"lotus"* || "$file" == *"aria2"* ]]; then
        add_python_deprecation "$file" "daemon_manager.py"
    elif [[ "$file" == *"mcp"* || "$file" == *"server"* ]]; then
        add_python_deprecation "$file" "mcp_server_runner.py"
    else
        # For other start files, determine by content
        if grep -q "daemon" "$file"; then
            add_python_deprecation "$file" "daemon_manager.py"
        else
            add_python_deprecation "$file" "mcp_server_runner.py"
        fi
    fi
done

# Process all start_* shell script files
echo "Processing start_* shell script files..."
for file in start_*.sh; do
    # Handle based on file type
    if [[ "$file" == *"daemon"* || "$file" == *"ipfs"* || "$file" == *"lotus"* || "$file" == *"aria2"* ]]; then
        add_shell_deprecation "$file" "daemon_manager.py"
    elif [[ "$file" == *"mcp"* || "$file" == *"server"* ]]; then
        add_shell_deprecation "$file" "mcp_server_runner.py"
    else
        # For other start files, determine by content
        if grep -q "daemon" "$file"; then
            add_shell_deprecation "$file" "daemon_manager.py"
        else
            add_shell_deprecation "$file" "mcp_server_runner.py"
        fi
    fi
done

# Process all run_* shell script files
echo "Processing run_* shell script files..."
for file in run_*.sh; do
    # Handle based on file type
    if [[ "$file" == *"test"* || "$file" == *"tests"* ]]; then
        add_shell_deprecation "$file" "mcp_test_runner.py"
    else
        add_shell_deprecation "$file" "mcp_server_runner.py"
    fi
done

echo "Deprecation notices added. All original files are backed up with .bak_TIMESTAMP extension."