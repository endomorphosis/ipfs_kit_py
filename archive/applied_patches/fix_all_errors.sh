#!/bin/bash

# Script to fix all remaining errors in ipfs_kit_py/mcp
LOG_FILE="error_fixes.log"
echo "===== Starting Error Fixes $(date) =====" > $LOG_FILE

# Set the MCP directory path
MCP_DIR="ipfs_kit_py/mcp"
echo "Target MCP directory: $MCP_DIR" | tee -a $LOG_FILE

# Create backup directory
BACKUP_DIR="code_backups_$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "Created backup directory: $BACKUP_DIR" | tee -a $LOG_FILE

# 1. Fix F401 - Unused imports
echo "Fixing F401 - Unused imports..." | tee -a $LOG_FILE
# Find files with unused imports
FILES_WITH_UNUSED_IMPORTS=$(ruff check --select=F401 $MCP_DIR --format=text | grep -o "$MCP_DIR.*\.py" | sort -u)

for file in $FILES_WITH_UNUSED_IMPORTS; do
  if [ -f "$file" ]; then
    echo "Processing $file for unused imports" | tee -a $LOG_FILE
    # Make a backup
    cp "$file" "$BACKUP_DIR/$(basename "$file").bak"
    
    # Get unused imports
    UNUSED_IMPORTS=$(ruff check --select=F401 "$file" --format=json | grep -o '"name": "[^"]*"' | sed 's/"name": "//g' | sed 's/"//g')
    
    # Remove each unused import using sed
    for import_name in $UNUSED_IMPORTS; do
      echo "  Removing unused import: $import_name" | tee -a $LOG_FILE
      
      # Check if it's a 'from X import Y' or just 'import Y'
      if grep -q "from .* import .*$import_name" "$file"; then
        # Case: from X import Y
        # Check if it's the only import in that line
        if grep -q "from .* import $import_name$" "$file"; then
          # It's the only import, remove the whole line
          sed -i "/from .* import $import_name$/d" "$file"
        else
          # It's one of multiple imports
          # Remove just this import and the comma if needed
          sed -i "s/, $import_name//g" "$file"
          sed -i "s/$import_name, //g" "$file"
          sed -i "s/from \(.*\) import $import_name/from \1 import/g" "$file"
          # Clean up lines that end up as "from X import "
          sed -i "/from .* import $/d" "$file"
        fi
      else
        # Case: import Y
        sed -i "/import $import_name$/d" "$file"
      fi
    done
  fi
done

# 2. Fix E722 - Bare except
echo "Fixing E722 - Bare except blocks..." | tee -a $LOG_FILE
FILES_WITH_BARE_EXCEPT=$(ruff check --select=E722 $MCP_DIR --format=text | grep -o "$MCP_DIR.*\.py" | sort -u)

for file in $FILES_WITH_BARE_EXCEPT; do
  if [ -f "$file" ]; then
    echo "Processing $file for bare except blocks" | tee -a $LOG_FILE
    # Make a backup if not already backed up
    if [ ! -f "$BACKUP_DIR/$(basename "$file").bak" ]; then
      cp "$file" "$BACKUP_DIR/$(basename "$file").bak"
    fi
    
    # Replace 'except:' with 'except Exception:'
    sed -i 's/except:/except Exception:/g' "$file"
  fi
done

# 3. Fix E402 - Module imports not at top of file
echo "Fixing E402 - Imports not at top of file..." | tee -a $LOG_FILE
FILES_WITH_LATE_IMPORTS=$(ruff check --select=E402 $MCP_DIR --format=text | grep -o "$MCP_DIR.*\.py" | sort -u)

for file in $FILES_WITH_LATE_IMPORTS; do
  if [ -f "$file" ]; then
    echo "Processing $file for imports not at top" | tee -a $LOG_FILE
    # This is more complex, just mark files for manual review
    echo "  Marked for manual review: import statements not at top of file" | tee -a $LOG_FILE
    echo "$file" >> "manual_review_late_imports.txt"
  fi
done

# 4. Fix F403 - Undefined locals with import star
echo "Fixing F403 - Undefined locals with import star..." | tee -a $LOG_FILE
FILES_WITH_IMPORT_STAR=$(ruff check --select=F403 $MCP_DIR --format=text | grep -o "$MCP_DIR.*\.py" | sort -u)

for file in $FILES_WITH_IMPORT_STAR; do
  if [ -f "$file" ]; then
    echo "Processing $file for import star issues" | tee -a $LOG_FILE
    # This requires careful analysis, just mark for manual review
    echo "  Marked for manual review: import * issues" | tee -a $LOG_FILE
    echo "$file" >> "manual_review_import_star.txt"
  fi
done

# 5. Fix remaining issues that need more analysis
echo "Identifying files with other issues for manual review..." | tee -a $LOG_FILE

# F811 - Redefined but unused
FILES_WITH_REDEFINED=$(ruff check --select=F811 $MCP_DIR --format=text | grep -o "$MCP_DIR.*\.py" | sort -u)
for file in $FILES_WITH_REDEFINED; do
  if [ -f "$file" ]; then
    echo "Marked for manual review (F811 - redefined variables): $file" | tee -a $LOG_FILE
    echo "$file" >> "manual_review_redefined_vars.txt"
  fi
done

# F821 - Undefined names
FILES_WITH_UNDEFINED=$(ruff check --select=F821 $MCP_DIR --format=text | grep -o "$MCP_DIR.*\.py" | sort -u)
for file in $FILES_WITH_UNDEFINED; do
  if [ -f "$file" ]; then
    echo "Marked for manual review (F821 - undefined names): $file" | tee -a $LOG_FILE
    echo "$file" >> "manual_review_undefined_names.txt"
  fi
done

# F823 - Undefined local variables
FILES_WITH_UNDEFINED_LOCAL=$(ruff check --select=F823 $MCP_DIR --format=text | grep -o "$MCP_DIR.*\.py" | sort -u)
for file in $FILES_WITH_UNDEFINED_LOCAL; do
  if [ -f "$file" ]; then
    echo "Marked for manual review (F823 - undefined locals): $file" | tee -a $LOG_FILE
    echo "$file" >> "manual_review_undefined_locals.txt"
  fi
done

# E741 - Ambiguous variable names
FILES_WITH_AMBIGUOUS=$(ruff check --select=E741 $MCP_DIR --format=text | grep -o "$MCP_DIR.*\.py" | sort -u)
for file in $FILES_WITH_AMBIGUOUS; do
  if [ -f "$file" ]; then
    echo "Marked for manual review (E741 - ambiguous variable names): $file" | tee -a $LOG_FILE
    echo "$file" >> "manual_review_ambiguous_vars.txt"
  fi
done

# Generate a manual review summary file
echo "Generating manual review summary file..." | tee -a $LOG_FILE
echo "===== Files Needing Manual Review =====" > manual_review_summary.txt

if [ -f "manual_review_late_imports.txt" ]; then
  echo -e "\n== E402 - Imports not at top of file ==" >> manual_review_summary.txt
  cat manual_review_late_imports.txt >> manual_review_summary.txt
fi

if [ -f "manual_review_import_star.txt" ]; then
  echo -e "\n== F403 - Undefined locals with import star ==" >> manual_review_summary.txt
  cat manual_review_import_star.txt >> manual_review_summary.txt
fi

if [ -f "manual_review_redefined_vars.txt" ]; then
  echo -e "\n== F811 - Redefined but unused variables ==" >> manual_review_summary.txt
  cat manual_review_redefined_vars.txt >> manual_review_summary.txt
fi

if [ -f "manual_review_undefined_names.txt" ]; then
  echo -e "\n== F821 - Undefined names ==" >> manual_review_summary.txt
  cat manual_review_undefined_names.txt >> manual_review_summary.txt
fi

if [ -f "manual_review_undefined_locals.txt" ]; then
  echo -e "\n== F823 - Undefined local variables ==" >> manual_review_summary.txt
  cat manual_review_undefined_locals.txt >> manual_review_summary.txt
fi

if [ -f "manual_review_ambiguous_vars.txt" ]; then
  echo -e "\n== E741 - Ambiguous variable names ==" >> manual_review_summary.txt
  cat manual_review_ambiguous_vars.txt >> manual_review_summary.txt
fi

# Run the final fixes with Ruff and Black
echo "Running final passes with Ruff and Black..." | tee -a $LOG_FILE
ruff check --fix --quiet $MCP_DIR >> $LOG_FILE 2>&1
black --quiet $MCP_DIR >> $LOG_FILE 2>&1

# Get statistics on remaining issues
echo "===== Final Error Status =====" | tee -a $LOG_FILE
echo "Fix process completed at $(date)" | tee -a $LOG_FILE
ruff check $MCP_DIR --statistics >> $LOG_FILE 2>&1
ruff check $MCP_DIR --statistics | tee -a /dev/tty

echo "Fixes applied. See $LOG_FILE for details." | tee -a /dev/tty
echo "Files requiring manual review are listed in manual_review_summary.txt" | tee -a /dev/tty