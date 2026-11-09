#!/usr/bin/env python3
import re

filepath = 'ipfs_kit_py/mcp/extensions/auth.py'

with open(filepath, 'r') as file:
    content = file.read()

# Fix missing commas in auth_config dictionary
pattern = re.compile(r'"auth_enabled": True\s+"jwt_secret"', re.DOTALL)
fixed_content = re.sub(pattern, '"auth_enabled": True,\n            "jwt_secret"', content)

pattern = re.compile(r'"jwt_secret": jwt_secret\s+"default_admin_password"', re.DOTALL)
fixed_content = re.sub(pattern, '"jwt_secret": jwt_secret,\n            "default_admin_password"', fixed_content)

pattern = re.compile(r'"default_admin_password": default_admin_password\s+"allow_anonymous_access"', re.DOTALL)
fixed_content = re.sub(pattern, '"default_admin_password": default_admin_password,\n            "allow_anonymous_access"', fixed_content)

# Fix missing commas in anon_allowed_paths list
pattern = re.compile(r'"/api/v0/health"\s+"/api/v0/metrics/status"', re.DOTALL)
fixed_content = re.sub(pattern, '"/api/v0/health",\n                "/api/v0/metrics/status"', fixed_content)

pattern = re.compile(r'"/api/v0/metrics/status"\s+"/api/v0/ipfs/version"', re.DOTALL)
fixed_content = re.sub(pattern, '"/api/v0/metrics/status",\n                "/api/v0/ipfs/version"', fixed_content)

with open(filepath, 'w') as file:
    file.write(fixed_content)

print(f"Fixed missing commas in {filepath}")
