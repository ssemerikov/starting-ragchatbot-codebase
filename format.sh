#!/bin/bash

# Auto-format Script for RAG Chatbot
# Automatically formats code using black and isort

set -e  # Exit on error

echo "=================================="
echo "Auto-formatting Code"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd backend

echo "1. Sorting imports with isort..."
uv run isort .
echo -e "${GREEN}✓ Imports sorted${NC}"
echo ""

echo "2. Formatting code with black..."
uv run black .
echo -e "${GREEN}✓ Code formatted${NC}"
echo ""

echo "=================================="
echo -e "${GREEN}Formatting complete!${NC}"
echo ""
echo -e "${YELLOW}Tip: Run './quality_check.sh' to verify all quality checks pass${NC}"
