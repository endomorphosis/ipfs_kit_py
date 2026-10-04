#!/usr/bin/env bash

# Run comprehensive tests for the IPFS Kit Python project
# Usage: ./run_tests.sh [category] [--verbose] [--parallel] [--html-report] [--junit-xml]

set -e

# Default values
CATEGORY="all"
VERBOSE=""
PARALLEL=""
HTML_REPORT=""
JUNIT_XML=""
REPORT_DIR="test_reports/$(date +%Y%m%d_%H%M%S)"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    core|mcp|storage|fsspec|api|tools|integrations|all)
      CATEGORY="$1"
      shift
      ;;
    --verbose|-v)
      VERBOSE="--verbose"
      shift
      ;;
    --parallel|-p)
      PARALLEL="--parallel"
      shift
      ;;
    --html-report)
      HTML_REPORT="--html-report"
      shift
      ;;
    --junit-xml)
      JUNIT_XML="--junit-xml"
      shift
      ;;
    --report-dir)
      REPORT_DIR="$2"
      shift
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: ./run_tests.sh [category] [--verbose] [--parallel] [--html-report] [--junit-xml] [--report-dir path]"
      echo "Categories: all, core, mcp, storage, fsspec, api, tools, integrations"
      exit 1
      ;;
  esac
done

echo "Running IPFS Kit Python tests - $(date)"
echo "Category: $CATEGORY"
echo "Report directory: $REPORT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python -m venv .venv
  source .venv/bin/activate
  pip install -e ".[dev,full]"
else
  source .venv/bin/activate
fi

# Make sure pytest and other dependencies are installed
pip install -q pytest pytest-cov pytest-html pytest-xdist

# Run the tests
python run_comprehensive_tests.py --category $CATEGORY $VERBOSE $PARALLEL $HTML_REPORT $JUNIT_XML --report-dir $REPORT_DIR

# Get the exit code
EXIT_CODE=$?

# Show summary
if [ $EXIT_CODE -eq 0 ]; then
  echo "All tests passed successfully!"
else
  echo "Some tests failed. Check the reports in $REPORT_DIR"
fi

echo "Testing completed - $(date)"
exit $EXIT_CODE
