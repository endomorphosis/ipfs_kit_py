#!/usr/bin/env python3
"""
Clean up any remaining secrets from the IPFS Kit codebase.

This script helps identify and remove any remaining hardcoded secrets.
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any

def find_potential_secrets(directory: str) -> List[Dict[str, Any]]:
    """Find potential secrets in the codebase."""
    
    secrets = []
    
    # Patterns for different types of secrets
    patterns = [
        # Hugging Face tokens
        (r'hf_[A-Za-z0-9]{34}', 'Hugging Face Token'),
        # AWS/S3 Access Keys
        (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
        (r'CWINWZ[A-Za-z0-9]{14}', 'CoreWeave Access Key'),
        # Generic API keys
        (r'[A-Za-z0-9]{40}', 'Potential API Key (40 chars)'),
        # JWT tokens
        (r'ey[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*', 'JWT Token'),
        # Private keys
        (r'-----BEGIN [A-Z ]+ KEY-----', 'Private Key'),
        # Generic long secrets
        (r'[A-Za-z0-9+/]{32,}={0,2}', 'Base64 encoded secret'),
    ]
    
    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        if any(skip in root for skip in ['.git', '__pycache__', '.venv', 'node_modules']):
            continue
            
        for file in files:
            if file.endswith(('.py', '.json', '.yaml', '.yml', '.toml', '.ini', '.env')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern, secret_type in patterns:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            # Skip if it's in comments explaining security
                            line_start = content.rfind('\n', 0, match.start()) + 1
                            line_end = content.find('\n', match.end())
                            if line_end == -1:
                                line_end = len(content)
                            line = content[line_start:line_end]
                            
                            # Skip if it's clearly a placeholder or example
                            if any(word in line.lower() for word in ['example', 'placeholder', 'your_', 'test_', 'mock_']):
                                continue
                            
                            # Skip if it's in a comment about security
                            if any(word in line.lower() for word in ['security', 'deprecated', 'removed', 'secure']):
                                continue
                            
                            secrets.append({
                                'file': file_path,
                                'type': secret_type,
                                'pattern': pattern,
                                'match': match.group(),
                                'line': line.strip(),
                                'position': match.start()
                            })
                            
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    
    return secrets

def create_security_report(secrets: List[Dict[str, Any]]) -> str:
    """Create a security report."""
    
    if not secrets:
        return "✅ No hardcoded secrets found in the codebase!"
    
    report = "🔐 Security Report: Potential Secrets Found\n"
    report += "=" * 50 + "\n\n"
    
    for secret in secrets:
        report += f"🚨 {secret['type']} found:\n"
        report += f"   File: {secret['file']}\n"
        report += f"   Line: {secret['line']}\n"
        report += f"   Match: {secret['match'][:20]}...\n"
        report += "-" * 30 + "\n"
    
    report += f"\nTotal secrets found: {len(secrets)}\n"
    report += "\n🔧 Recommended Actions:\n"
    report += "1. Remove all hardcoded secrets from the codebase\n"
    report += "2. Use environment variables or secure config files\n"
    report += "3. Run: python setup_credentials.py\n"
    report += "4. Review and update .gitignore\n"
    report += "5. Consider using git filter-branch to remove from history\n"
    
    return report

def main():
    """Main function."""
    
    print("🔍 Scanning for potential secrets in the codebase...")
    
    # Scan the current directory
    secrets = find_potential_secrets('.')
    
    # Create and display report
    report = create_security_report(secrets)
    print(report)
    
    # Save report to file
    report_file = Path('security_report.txt')
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Security report saved to: {report_file}")
    
    # Check if credentials are properly configured
    print("\n🔐 Checking secure credential configuration...")
    
    config_dir = Path("/tmp/ipfs_kit_config")
    if config_dir.exists():
        print(f"✓ Config directory exists: {config_dir}")
        
        credentials_file = config_dir / "credentials.json"
        if credentials_file.exists():
            print(f"✓ Credentials file exists: {credentials_file}")
            
            # Check permissions
            stat = os.stat(credentials_file)
            permissions = oct(stat.st_mode)[-3:]
            if permissions == '600':
                print("✓ Credentials file has secure permissions (600)")
            else:
                print(f"⚠️  Credentials file permissions: {permissions} (should be 600)")
                print("   Fix with: chmod 600 /tmp/ipfs_kit_config/credentials.json")
        else:
            print("⚠️  No credentials file found")
            print("   Run: python setup_credentials.py")
    else:
        print("⚠️  Config directory not found")
        print("   Run: python setup_credentials.py")
    
    # Check environment variables
    print("\n🌍 Checking environment variables...")
    env_vars = [
        'IPFS_KIT_HUGGINGFACE_TOKEN',
        'IPFS_KIT_S3_ACCESS_KEY',
        'IPFS_KIT_S3_SECRET_KEY',
        'IPFS_KIT_STORACHA_TOKEN'
    ]
    
    for var in env_vars:
        if os.getenv(var):
            print(f"✓ {var} is set")
        else:
            print(f"⚪ {var} is not set")
    
    print("\n✅ Security scan complete!")
    
    if secrets:
        print("\n⚠️  WARNING: Potential secrets found!")
        print("   Please review the security report and remove any hardcoded secrets.")
        return 1
    else:
        print("\n🎉 No hardcoded secrets found!")
        return 0

if __name__ == "__main__":
    exit(main())
