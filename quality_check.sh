#!/bin/bash

# Quality Check Script for RAG Chatbot
# Runs code formatting checks and linting tools

set -e  # Exit on error

echo "=================================="
echo "Running Code Quality Checks"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2 passed${NC}"
    else
        echo -e "${RED}✗ $2 failed${NC}"
    fi
}

# Track overall status
FAILED=0

# Change to backend directory
cd backend

echo "1. Checking code formatting with black..."
if uv run black --check . 2>&1; then
    print_status 0 "Black formatting check"
else
    print_status 1 "Black formatting check"
    FAILED=1
    echo -e "${YELLOW}  Run 'uv run black backend/' to fix formatting${NC}"
fi
echo ""

echo "2. Checking import sorting with isort..."
if uv run isort --check-only . 2>&1; then
    print_status 0 "Import sorting check"
else
    print_status 1 "Import sorting check"
    FAILED=1
    echo -e "${YELLOW}  Run 'uv run isort backend/' to fix imports${NC}"
fi
echo ""

echo "3. Running flake8 linting..."
if uv run flake8 --max-line-length=88 --extend-ignore=E203,W503 . 2>&1; then
    print_status 0 "Flake8 linting"
else
    print_status 1 "Flake8 linting"
    FAILED=1
fi
echo ""

echo "4. Running mypy type checking..."
if uv run mypy . 2>&1; then
    print_status 0 "Type checking"
else
    print_status 1 "Type checking"
    FAILED=1
fi
echo ""

# Summary
echo "=================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All quality checks passed!${NC}"
    exit 0
else
    echo -e "${RED}Some quality checks failed.${NC}"
    echo "Please fix the issues above before committing."
    exit 1
fi
