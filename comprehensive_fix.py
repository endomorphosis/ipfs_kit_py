#!/usr/bin/env python3

"""
Comprehensive fix for all indentation issues in ai_ml_integration.py
"""

def fix_vector_store_method():
    file_path = 'ipfs_kit_py/ai_ml_integration.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the create_vector_store method
    method_start_idx = content.find('def create_vector_store(')
    if method_start_idx == -1:
        print("Could not find create_vector_store method")
        return False
    
    # Find where the method should end (before the next unindented def or class)
    method_end_pattern = '\n    if PYDANTIC_AVAILABLE:'
    method_end_idx = content.find(method_end_pattern, method_start_idx)
    if method_end_idx == -1:
        print("Could not find end of method")
        return False
    
    # Make sure the line before this is properly indented
    before_end = content.rfind('\n', 0, method_end_idx)
    if before_end != -1:
        # Check what's between the last line and the Pydantic class
        method_body_end = content[before_end+1:method_end_idx].strip()
        
        # If the last line in the method is a return, we have the correct structure
        if method_body_end and ('return' in method_body_end):
            # The structure is correct, we just need to add an extra newline
            print("Method ends correctly with a return statement, adding newline")
            new_content = (content[:method_end_idx] + 
                          '\n' +  # Add an extra newline between method and next section
                          content[method_end_idx:])
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        else:
            print("Method doesn't end correctly, more extensive fix needed")
            return False
    
    print("Could not find proper location to fix")
    return False

def fix_document_loader_method():
    file_path = 'ipfs_kit_py/ai_ml_integration.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the create_document_loader method
    method_start_idx = content.find('def create_document_loader(')
    if method_start_idx == -1:
        print("Could not find create_document_loader method")
        return False
    
    # Find where the method should end (before the next unindented def or class)
    method_end_pattern = '\n    if PYDANTIC_AVAILABLE:'
    method_end_idx = content.find(method_end_pattern, method_start_idx)
    if method_end_idx == -1:
        print("Could not find end of document_loader method")
        return False
    
    # Same procedure as before
    before_end = content.rfind('\n', 0, method_end_idx)
    if before_end != -1:
        method_body_end = content[before_end+1:method_end_idx].strip()
        
        if method_body_end and ('return' in method_body_end):
            print("Document loader method ends correctly with a return statement, adding newline")
            new_content = (content[:method_end_idx] + 
                          '\n' +  # Add an extra newline
                          content[method_end_idx:])
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
    
    print("Could not find proper location to fix document_loader method")
    return False

if __name__ == "__main__":
    # Fix the create_vector_store method
    vector_store_fixed = fix_vector_store_method()
    print(f"Vector store method fixed: {vector_store_fixed}")
    
    # Fix the create_document_loader method
    document_loader_fixed = fix_document_loader_method()
    print(f"Document loader method fixed: {document_loader_fixed}")
    
    if vector_store_fixed and document_loader_fixed:
        print("All fixes applied successfully!")
    else:
        print("Some fixes could not be applied.")