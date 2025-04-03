#!/usr/bin/env python3

"""
Script to fix the indentation in ai_ml_integration.py
"""

def fix_indentation():
    file_path = 'ipfs_kit_py/ai_ml_integration.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Fix the indentation around line 6033
    # Capture the correct indentation level for the class
    create_vector_store_end = None
    pydantic_class_start = None
    
    for i in range(6030, 6050):
        if i < len(lines) and 'if PYDANTIC_AVAILABLE:' in lines[i] and lines[i].lstrip().startswith('if'):
            pydantic_class_start = i
            break
    
    if pydantic_class_start:
        # Fix is needed - adjust indentation
        with open(file_path, 'w', encoding='utf-8') as f:
            for i, line in enumerate(lines):
                # Add method ending if needed
                if i == pydantic_class_start - 1:
                    f.write(line)
                    # Close the create_vector_store method
                    f.write('    # End of create_vector_store method\n\n')
                elif i == pydantic_class_start:
                    # Write the Pydantic class at the correct indentation
                    f.write(line)
                else:
                    f.write(line)
        print("Successfully fixed indentation in", file_path)
    else:
        print("Could not find the Pydantic class start")

if __name__ == "__main__":
    fix_indentation()