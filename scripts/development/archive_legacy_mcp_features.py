#!/usr/bin/env python3
"""
Archive Legacy MCP Features

This script archives the comprehensive MCP dashboard features that were lost
during refactoring and provides a bridge to restore them.
"""

import shutil
from pathlib import Path
from datetime import datetime

def archive_legacy_features():
    """Archive legacy MCP dashboard features."""
    project_root = Path(__file__).parent
    archive_dir = project_root / "archived_mcp_features" / datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Files to archive
    legacy_files = [
        "deprecated_dashboards/comprehensive_mcp_dashboard.py",
        "deprecated_dashboards/integrated_mcp_server_with_dashboard.py",
        "deprecated_dashboards/enhanced_dashboard.py",
        "deprecated_dashboards/dashboard_templates_extra.py",
        "examples/unified_observability_mcp_server.py",
        "mcp/unified_mcp_server_with_full_observability.py"
    ]
    
    print(f"📁 Creating archive directory: {archive_dir}")
    
    for file_path in legacy_files:
        source = project_root / file_path
        if source.exists():
            dest = archive_dir / source.name
            shutil.copy2(source, dest)
            print(f"✅ Archived: {file_path} -> {dest}")
        else:
            print(f"⚠️  Missing: {file_path}")
    
    # Create archive manifest
    manifest_content = f"""# MCP Dashboard Features Archive
Archive Date: {datetime.now().isoformat()}

## Archived Files:
{chr(10).join([f"- {f}" for f in legacy_files])}

## Key Features Archived:
- Service monitoring and control
- Backend health monitoring  
- Peer management interface
- Real-time log streaming
- Advanced analytics dashboard
- Configuration file management
- WebSocket real-time updates
- Complete MCP tool integration

## Restoration Instructions:
Use enhance_unified_mcp_dashboard.py to restore these features
to the current UnifiedMCPDashboard implementation.
"""
    
    (archive_dir / "README.md").write_text(manifest_content)
    print(f"📋 Archive manifest created: {archive_dir / 'README.md'}")
    
    return archive_dir

if __name__ == "__main__":
    archive_dir = archive_legacy_features()
    print(f"\n✅ Legacy MCP features archived to: {archive_dir}")
