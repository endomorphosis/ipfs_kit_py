#!/bin/bash

# Set to 1 for dry run, 0 for actual move
DRY_RUN=0

# Create log file
LOGFILE="md_file_moves.log"
echo "File organization started at $(date)" > $LOGFILE
echo "DRY RUN MODE: $DRY_RUN" >> $LOGFILE

# Function to move or echo move based on dry run setting
move_file() {
  local file=$1
  local dest=$2
  if [ $DRY_RUN -eq 1 ]; then
    echo "WOULD MOVE: $file -> $dest" | tee -a $LOGFILE
  else
    echo "Moving $file to $dest" | tee -a $LOGFILE
    mv "$file" "$dest"
  fi
}

# Files to keep in root
HIGH_LEVEL=(
  "./README.md"
  "./CONTRIBUTING.md"
  "./CHANGELOG.md"
  "./RELEASE_NOTES.md"
  "./LICENSE.md"
  "./README-PyPI.md"
  "./RELEASE_GUIDE.md"
  "./RELEASE_CHECKLIST.md"
  "./PYPI_RELEASE_CHECKLIST.md"
)

# Track processed files to avoid duplicate moves
declare -A PROCESSED_FILES

# Function to check if file is in array
contains() {
  local value="$1"
  shift
  for item; do
    [[ "$item" == "$value" ]] && return 0
  done
  return 1
}

# Function to check if file should be skipped
should_skip() {
  local file=$1
  
  # Skip if already processed
  [[ -n "${PROCESSED_FILES[$file]}" ]] && return 0
  
  # Skip if in HIGH_LEVEL
  contains "$file" "${HIGH_LEVEL[@]}" && return 0
  
  # Skip README files
  [[ $(basename "$file") == "README.md" ]] && return 0
  
  # Skip files in important directories like ipfs_kit_py/ subdirectories
  [[ "$file" == "./ipfs_kit_py/"* ]] && return 0
  
  return 1
}

# Mark file as processed
mark_processed() {
  local file=$1
  PROCESSED_FILES["$file"]=1
}

# Process files based on type
process_file_category() {
  local category=$1
  local dest_dir=$2
  shift 2
  local patterns=("$@")
  
  echo "Processing $category files..." | tee -a $LOGFILE
  for pattern in "${patterns[@]}"; do
    for file in $(find . -name "$pattern" -not -path "*/\.*" -not -path "*/venv*" -not -path "*/node_modules*" -not -path "*/docs/*" -not -path "*/test_*env/*" -not -path "*/build_venv/*" -not -path "*/libp2p_test_env/*"); do
      if ! should_skip "$file"; then
        move_file "$file" "$dest_dir"
        mark_processed "$file"
      fi
    done
  done
}

# Define file categories and patterns
declare -A CATEGORIES
CATEGORIES["implementation"]="docs/implementation/ *IMPLEMENTATION*.md *IMPLEMENTATION_*.md *_IMPLEMENTATION_*.md IPFS_CLUSTER_STATUS*.md"
CATEGORIES["integration"]="docs/implementation/ *INTEGRATION*.md *INTEGRATION_*.md *_INTEGRATION_*.md"
CATEGORIES["fixes"]="docs/fixes/ *FIX*.md fix_*.md *_FIX_*.md"
CATEGORIES["reports"]="docs/reports/ *REPORT*.md *_report.md *VERIFICATION*.md"
CATEGORIES["testing"]="docs/testing/ *TEST*.md *_test_*.md test_*.md test/*_TEST_*.md"
CATEGORIES["features"]="docs/features/ LOTUS_*.md FILECOIN_*.md WEBRTC_*.md"

# Process each category in priority order
for category in "fixes" "reports" "implementation" "integration" "testing" "features"; do
  IFS=' ' read -r dest_dir patterns <<< "${CATEGORIES[$category]}"
  process_file_category "$category" "$dest_dir" $patterns
done

# Move any remaining markdown files
echo "Processing remaining markdown files..." | tee -a $LOGFILE
for file in $(find . -name "*.md" -not -path "*/\.*" -not -path "*/venv*" -not -path "*/node_modules*" -not -path "*/docs/*" -not -path "*/test_*env/*" -not -path "*/build_venv/*" -not -path "*/libp2p_test_env/*"); do
  if ! should_skip "$file"; then
    move_file "$file" "docs/"
    mark_processed "$file"
  fi
done

echo "File organization plan completed at $(date)" | tee -a $LOGFILE
echo ""
echo "Total files processed: ${#PROCESSED_FILES[@]}"
echo ""
echo "To actually move the files, edit this script and set DRY_RUN=0, then run it again."