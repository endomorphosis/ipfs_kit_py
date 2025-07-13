#!/bin/bash
# Unified setup script for all IPFS Kit filesystem backends

set -e

echo "🚀 IPFS Kit Filesystem Backends Setup"
echo "======================================"

# Check if we're in the right directory
if [ ! -f "ipfs_kit_py/ipfs_kit.py" ]; then
    echo "❌ Error: Please run this script from the IPFS Kit project root directory"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
fi

# Parse command line arguments
BACKEND="all"
VERBOSE=""
TEST=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend=*)
            BACKEND="${1#*=}"
            shift
            ;;
        --backend)
            BACKEND="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --test)
            TEST="--test"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backend=BACKEND  Backend to setup (all, ipfs, lotus, storacha, synapse)"
            echo "  --verbose          Enable verbose output"
            echo "  --test            Run integration tests after setup"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Backends:"
            echo "  all      - Setup all backends (default)"
            echo "  ipfs     - Setup IPFS only"
            echo "  lotus    - Setup Lotus only"
            echo "  storacha - Setup Storacha only"
            echo "  synapse  - Setup Synapse SDK only"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🔧 Backend: $BACKEND"
if [ -n "$VERBOSE" ]; then
    echo "📝 Verbose mode enabled"
fi
if [ -n "$TEST" ]; then
    echo "🧪 Integration tests will run after setup"
fi
echo ""

# Run the Python setup script
echo "🐍 Running Python setup script..."
python scripts/setup/setup_all_backends.py --backend="$BACKEND" $VERBOSE $TEST

SETUP_EXIT_CODE=$?

if [ $SETUP_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Filesystem backends setup completed successfully!"
    echo ""
    echo "🎯 Next steps:"
    echo "1. Configure environment variables for the backends you plan to use:"
    echo "   - Synapse: SYNAPSE_PRIVATE_KEY, SYNAPSE_NETWORK, GLIF_TOKEN"
    echo "   - Storacha: STORACHA_SPACE, STORACHA_KEY"
    echo "   - S3: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    echo ""
    echo "2. Test the integration:"
    echo "   python scripts/setup/setup_all_backends.py --test"
    echo ""
    echo "3. Start using the backends in your code:"
    echo "   from ipfs_kit_py.ipfs_kit import ipfs_kit"
    echo "   kit = ipfs_kit(metadata={'role': 'leecher'})"
    echo ""
else
    echo ""
    echo "❌ Filesystem backends setup failed (exit code: $SETUP_EXIT_CODE)"
    echo "Please check the error messages above and try again."
    echo ""
    echo "For help, try:"
    echo "  $0 --help"
    echo "  python scripts/setup/setup_all_backends.py --verbose"
fi

exit $SETUP_EXIT_CODE
