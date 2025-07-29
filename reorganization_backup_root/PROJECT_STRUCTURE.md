# IPFS Kit Project Structure

This document outlines the logical organization of the IPFS Kit project from a maintainer's perspective.

## 🏗️ Root Level (Essential Files Only)

**Production-Ready Executables:**
- `standalone_cluster_server.py` - Primary production cluster server
- `start_3_node_cluster.py` - Production cluster launcher  
- `main.py` - Main application entry point

**Core Project Files:**
- `README.md` - Primary project documentation
- `CHANGELOG.md` - Version history and changes
- `LICENSE` - Project license
- `pyproject.toml` - Python project configuration
- `setup.py` - Package setup script
- `Makefile` - Build and development commands

**Cluster Documentation:**
- `CLUSTER_DEPLOYMENT_GUIDE.md` - Deployment instructions
- `CLUSTER_TEST_RESULTS.md` - Test results and validation
- `IPFS_KIT_MCP_INTEGRATION_PLAN.md` - Integration planning
- `MCP_DEVELOPMENT_STATUS.md` - **MCP server development status and roadmap**

## 📁 Organized Directories

### `/ipfs_kit_py/` - Core Python Package
The main library package containing:
- Core modules and classes
- VFS integration (`ipfs_fsspec.py`)
- Daemon management utilities
- Package configuration

### `/cluster/` - Cluster Management
Top-level cluster functionality:
- Distributed system components
- Cluster coordination logic
- Multi-node management

### `/servers/` - Development Servers
Various server implementations for development and testing:
- Enhanced server variations
- Containerized implementations
- Experimental servers
- Testing configurations

### `/tests/` - All Testing & Validation
Comprehensive testing suite:
- Unit tests
- Integration tests
- Validation scripts
- Verification utilities
- Debug test files

### `/tools/` - Development & Maintenance Tools
Utilities for project maintenance:
- Analysis scripts
- Debugging tools
- Configuration patches
- Development utilities
- Project status tools

### `/bin/` - Demonstration Scripts
Executable demonstration and example scripts:
- Cluster demonstrations
- Usage examples
- Tutorial scripts

### `/docs/` - Documentation
Organized documentation:
- `/docs/summaries/` - Project summaries and status reports
- `/docs/integration/` - Integration documentation
- `/docs/workflows/` - Workflow and process documentation
- Core API and user documentation

### `/examples/` - Code Examples
Sample code and usage examples:
- Tutorial examples
- Integration examples
- Best practice demonstrations

### `/scripts/` - Utility Scripts
Shell scripts and automation:
- Build scripts
- Deployment automation
- Development utilities

### `/config/` - Configuration
Configuration files and templates:
- Service configurations
- Tool registries
- Environment settings

### `/deployment/` - Deployment Resources
Deployment-related resources:
- Deployment scripts
- Container configurations
- Infrastructure templates

### `/logs/` - Log Files
Runtime logs and outputs:
- Application logs
- Debug outputs
- Process logs

### `/temp/` - Temporary Files
Temporary and transient files:
- Build artifacts
- Debug outputs
- Temporary data

### `/archive/` - Archived Content
Preserved historical content:
- Old implementations
- Backup files
- Deprecated features

## 🎯 Organization Principles

### **Root Level = Production Ready**
Only essential, production-ready files remain at the root level for easy access and deployment.

### **Logical Grouping**
Files are grouped by purpose rather than arbitrary naming:
- Tests with tests
- Tools with tools  
- Documentation with documentation

### **Clear Hierarchy**
The structure makes it immediately clear:
- What's ready for production
- What's for development
- What's for testing
- What's for documentation

### **Maintainer Friendly**
The organization supports common maintainer tasks:
- Finding and running tests
- Locating development tools
- Understanding project status
- Deploying to production

## 🚀 Quick Start for Maintainers

**Run Production Cluster:**
```bash
python start_3_node_cluster.py
```

**Run Tests:**
```bash
cd tests/
python -m pytest
```

**Development Server:**
```bash
cd servers/
python enhanced_mcp_server_with_full_config.py
```

**View Project Status:**
```bash
cd tools/
python verify_reorganization.py
```

This structure balances accessibility, organization, and maintainability for long-term project success.
