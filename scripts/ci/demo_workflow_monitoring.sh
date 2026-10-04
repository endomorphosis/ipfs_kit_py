#!/bin/bash

# Demo Script: Workflow Trigger and Installation Monitoring
# This script demonstrates how to use both monitoring tools together

set -e

echo "======================================================================"
echo "Workflow Trigger and Installation Monitoring Demo"
echo "======================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"
echo ""

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo -e "${YELLOW}⚠️ GitHub CLI (gh) not installed${NC}"
    echo "   Install from: https://cli.github.com/"
    echo "   Workflow monitoring will be skipped"
    SKIP_WORKFLOW=1
else
    echo -e "${GREEN}✅ GitHub CLI (gh) is available${NC}"
    gh --version
    echo ""
    
    # Check if authenticated
    if gh auth status &> /dev/null; then
        echo -e "${GREEN}✅ GitHub CLI is authenticated${NC}"
        gh auth status 2>&1 | head -2
    else
        echo -e "${YELLOW}⚠️ GitHub CLI not authenticated${NC}"
        echo "   Run: gh auth login"
        echo "   Workflow monitoring will be skipped"
        SKIP_WORKFLOW=1
    fi
fi
echo ""

# Check Python
echo -e "${BLUE}🐍 Checking Python...${NC}"
python3 --version
echo ""

# ======================================================================
# Part 1: Workflow Monitoring Demo
# ======================================================================
if [ -z "$SKIP_WORKFLOW" ]; then
    echo "======================================================================"
    echo "Part 1: GitHub Workflow Monitoring"
    echo "======================================================================"
    echo ""
    
    echo -e "${BLUE}📋 Listing available workflows...${NC}"
    python3 scripts/ci/trigger_and_monitor_workflow.py --list-workflows | head -10
    echo ""
    
    echo -e "${BLUE}📋 Listing recent runs for daemon-config-tests.yml...${NC}"
    python3 scripts/ci/trigger_and_monitor_workflow.py \
        --list \
        --workflow daemon-config-tests.yml | head -10
    echo ""
    
    echo -e "${YELLOW}ℹ️ To trigger a workflow:${NC}"
    echo "   python3 scripts/ci/trigger_and_monitor_workflow.py \\"
    echo "     --workflow daemon-config-tests.yml \\"
    echo "     --trigger --monitor"
    echo ""
    
    echo -e "${YELLOW}ℹ️ To monitor an existing run:${NC}"
    echo "   python3 scripts/ci/trigger_and_monitor_workflow.py \\"
    echo "     --run-id <RUN_ID> --monitor"
    echo ""
else
    echo "======================================================================"
    echo "Part 1: GitHub Workflow Monitoring (SKIPPED)"
    echo "======================================================================"
    echo ""
    echo -e "${YELLOW}⚠️ GitHub CLI not available or not authenticated${NC}"
    echo "   Install and authenticate to use workflow monitoring"
    echo ""
fi

# ======================================================================
# Part 2: Installation Monitoring Demo
# ======================================================================
echo "======================================================================"
echo "Part 2: Installation Monitoring"
echo "======================================================================"
echo ""

echo -e "${BLUE}🔍 Checking current installation status...${NC}"
echo ""
python3 scripts/ci/monitor_first_install.py --verify
echo ""

echo -e "${BLUE}⚙️ Checking configuration files...${NC}"
echo ""
python3 scripts/ci/monitor_first_install.py --config-only
echo ""

echo -e "${YELLOW}ℹ️ To monitor a fresh installation:${NC}"
echo "   python3 scripts/ci/monitor_first_install.py \\"
echo "     --command \"pip install 'ipfs_kit_py @ git+https://github.com/endomorphosis/ipfs_kit_py@main'\""
echo ""

echo -e "${YELLOW}ℹ️ To monitor local development installation:${NC}"
echo "   python3 scripts/ci/monitor_first_install.py \\"
echo "     --command \"pip install -e .\""
echo ""

# ======================================================================
# Part 3: Generated Artifacts
# ======================================================================
echo "======================================================================"
echo "Part 3: Generated Monitoring Artifacts"
echo "======================================================================"
echo ""

echo -e "${BLUE}📄 Installation monitoring artifacts:${NC}"
if [ -d /tmp/install_monitor ]; then
    ls -lh /tmp/install_monitor/
else
    echo "   No artifacts yet"
fi
echo ""

echo -e "${BLUE}📄 Workflow monitoring artifacts:${NC}"
if [ -d /tmp/workflow_monitor ]; then
    ls -lh /tmp/workflow_monitor/
else
    echo "   No artifacts yet (workflow monitoring not run)"
fi
echo ""

# ======================================================================
# Summary
# ======================================================================
echo "======================================================================"
echo "Demo Complete!"
echo "======================================================================"
echo ""
echo -e "${GREEN}✅ Workflow monitoring script: scripts/ci/trigger_and_monitor_workflow.py${NC}"
echo -e "${GREEN}✅ Installation monitoring script: scripts/ci/monitor_first_install.py${NC}"
echo ""
echo "Documentation:"
echo "  - scripts/ci/WORKFLOW_MONITORING.md"
echo "  - scripts/ci/README.md"
echo "  - ARM64_MONITORING_GUIDE.md"
echo ""
echo "Next steps:"
echo "  1. Run workflow monitoring to trigger and track GitHub Actions"
echo "  2. Use installation monitoring during package setup"
echo "  3. Review generated reports in /tmp/install_monitor/"
echo "  4. Integrate into CI/CD workflows"
echo ""
