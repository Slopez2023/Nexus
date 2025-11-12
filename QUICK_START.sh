#!/bin/bash
#
# Quick Start Script - Warehouse API Integration Test
# 
# This script sets up and runs the complete test flow
# Usage: ./QUICK_START.sh [options]
#
# Examples:
#   ./QUICK_START.sh                    # Run with defaults (AAPL, Jan-Mar 2024)
#   ./QUICK_START.sh MSFT              # Test MSFT symbol
#   ./QUICK_START.sh AAPL compare      # Test AAPL with source comparison
#   ./QUICK_START.sh --help            # Show options
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Defaults
SYMBOL="AAPL"
START_DATE="2024-01-01"
END_DATE="2024-03-31"
COMPARE_SOURCES=false
SKIP_WAREHOUSE=false
SHOW_HELP=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            SHOW_HELP=true
            shift
            ;;
        --symbol|-s)
            SYMBOL="$2"
            shift 2
            ;;
        --start)
            START_DATE="$2"
            shift 2
            ;;
        --end)
            END_DATE="$2"
            shift 2
            ;;
        --compare)
            COMPARE_SOURCES=true
            shift
            ;;
        --no-warehouse)
            SKIP_WAREHOUSE=true
            shift
            ;;
        *)
            # Positional arguments (backward compatible)
            if [ -z "$SYMBOL" ] || [ "$SYMBOL" = "AAPL" ]; then
                SYMBOL="$1"
            elif [ "$1" = "compare" ]; then
                COMPARE_SOURCES=true
            elif [ "$1" = "noapi" ]; then
                SKIP_WAREHOUSE=true
            fi
            shift
            ;;
    esac
done

# Show help if requested
if [ "$SHOW_HELP" = true ]; then
    cat << EOF
${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}NEXUS Warehouse API Integration - Quick Start${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

USAGE:
  ./QUICK_START.sh [OPTIONS]

OPTIONS:
  -h, --help              Show this help message
  -s, --symbol SYMBOL     Trading symbol (default: AAPL)
      --start DATE        Start date YYYY-MM-DD (default: 2024-01-01)
      --end DATE          End date YYYY-MM-DD (default: 2024-03-31)
      --compare           Compare Warehouse API with legacy sources
      --no-warehouse      Test without Warehouse API (legacy fallback)

EXAMPLES:
  ./QUICK_START.sh
  ./QUICK_START.sh --symbol MSFT
  ./QUICK_START.sh --symbol AAPL --compare
  ./QUICK_START.sh --symbol BTC/USD --start 2023-01-01 --end 2024-03-31
  ./QUICK_START.sh --no-warehouse

EOF
    exit 0
fi

# Banner
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}NEXUS Warehouse API Integration - Quick Start${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo

# Check prerequisites
echo -e "${YELLOW}[1/5] Checking Prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION}${NC}"

# Check if in project directory
if [ ! -f "test_warehouse_strategy_flow.py" ]; then
    echo -e "${RED}✗ test_warehouse_strategy_flow.py not found${NC}"
    echo -e "${YELLOW}  Make sure you're in the project root directory${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Project directory verified${NC}"

# Check virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not activated${NC}"
    echo -e "${YELLOW}  Attempting to activate...${NC}"
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}✗ Virtual environment not found${NC}"
        echo -e "${YELLOW}  Run: python3 -m venv venv && source venv/bin/activate${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Virtual environment active${NC}"
fi

# Check dependencies
echo -e "${GREEN}✓ Dependencies check${NC}"
python3 -c "import pandas, nexus" 2>/dev/null || {
    echo -e "${YELLOW}  Installing dependencies...${NC}"
    pip install -q -r requirements.txt
}

# Check services
echo
echo -e "${YELLOW}[2/5] Checking Services...${NC}"

# Check PostgreSQL
if pg_isready -h localhost &>/dev/null; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${YELLOW}⚠ PostgreSQL not responding${NC}"
    echo -e "${YELLOW}  Start with: brew services start postgresql@15${NC}"
fi

# Check Warehouse API
echo -n "Checking Warehouse API... "
if timeout 2 curl -s http://localhost:8000/health &>/dev/null; then
    echo -e "${GREEN}✓ Available${NC}"
    WAREHOUSE_AVAILABLE=true
else
    echo -e "${YELLOW}⚠ Not available${NC}"
    echo -e "${YELLOW}  Start the Warehouse API server or use --no-warehouse${NC}"
    WAREHOUSE_AVAILABLE=false
fi

# Check .env
echo -n "Checking configuration... "
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env found${NC}"
else
    echo -e "${YELLOW}⚠ .env not found${NC}"
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}  Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${GREEN}✓ .env created${NC}"
    fi
fi

# Print configuration
echo
echo -e "${YELLOW}[3/5] Configuration${NC}"
echo "  Symbol:          ${SYMBOL}"
echo "  Period:          ${START_DATE} to ${END_DATE}"
if [ "$COMPARE_SOURCES" = true ]; then
    echo "  Comparison:      Enabled"
else
    echo "  Comparison:      Disabled"
fi
if [ "$SKIP_WAREHOUSE" = true ]; then
    echo "  Warehouse API:   Disabled (legacy sources only)"
elif [ "$WAREHOUSE_AVAILABLE" = true ]; then
    echo "  Warehouse API:   Enabled (available)"
else
    echo "  Warehouse API:   Enabled (not responding - will fallback)"
fi

# Ask for confirmation
echo
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Ready to run test flow. Continue? [Y/n]${NC}"
read -r -p "> " -t 10 response
response=${response:-Y}

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Aborted${NC}"
    exit 0
fi

# Run the test
echo
echo -e "${YELLOW}[4/5] Running Test Flow...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo

# Build command
CMD="python3 test_warehouse_strategy_flow.py"
CMD="$CMD --symbol $SYMBOL"
CMD="$CMD --start $START_DATE"
CMD="$CMD --end $END_DATE"

if [ "$COMPARE_SOURCES" = true ]; then
    CMD="$CMD --compare"
fi

if [ "$SKIP_WAREHOUSE" = true ]; then
    CMD="$CMD --no-warehouse"
fi

# Execute
if eval "$CMD"; then
    EXIT_CODE=0
    echo
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ TEST FLOW COMPLETED SUCCESSFULLY${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
else
    EXIT_CODE=$?
    echo
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}✗ TEST FLOW FAILED (exit code: $EXIT_CODE)${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
fi

# Show next steps
echo
echo -e "${YELLOW}[5/5] Next Steps${NC}"

if [ $EXIT_CODE -eq 0 ]; then
    echo
    echo -e "${GREEN}Success! Here are recommended next steps:${NC}"
    echo
    echo "1. Review the output above for data and signal metrics"
    echo
    echo "2. Run integration tests:"
    echo "   ${BLUE}pytest tests/integration/test_warehouse_api_integration.py -v${NC}"
    echo
    echo "3. Check logs for details:"
    echo "   ${BLUE}tail -f nexus.log${NC}"
    echo
    echo "4. Try different symbols or date ranges:"
    echo "   ${BLUE}./QUICK_START.sh --symbol MSFT${NC}"
    echo "   ${BLUE}./QUICK_START.sh --symbol BTC/USD --compare${NC}"
    echo
    echo "5. View detailed documentation:"
    echo "   ${BLUE}cat TEST_FLOW_GUIDE.md${NC}"
    echo
else
    echo
    echo -e "${RED}Troubleshooting:${NC}"
    echo
    echo "1. Check service status:"
    echo "   ${BLUE}psql -d nexus_trading -c \"SELECT 1\"${NC}"
    echo "   ${BLUE}curl http://localhost:8000/api/v1/health${NC}"
    echo
    echo "2. Review logs:"
    echo "   ${BLUE}tail -50 nexus.log${NC}"
    echo
    echo "3. See troubleshooting guide:"
    echo "   ${BLUE}cat FLOW_CHECKLIST.md${NC}"
    echo
fi

exit $EXIT_CODE
