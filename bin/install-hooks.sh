#!/bin/bash
#
# Claude Code Hooks Installation Script
#
# This script installs the Claude Code hooks integration for the Claude Monitor.
#
# What it does:
# 1. Creates ~/.claude/hooks directory if needed
# 2. Copies the notify-monitor.sh hook script
# 3. Makes the script executable
# 4. Creates or updates ~/.claude/settings.json with hook configuration
#
# Usage:
#   ./bin/install-hooks.sh
#
# After installation:
# 1. Start the Claude Monitor: python run.py
# 2. Start a Claude Code session in a project directory
# 3. Verify hooks are working at http://localhost:5050/hook/status
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "Installing Claude Code hooks for Claude Monitor..."
echo ""

# Step 1: Create hooks directory
echo -n "Creating ~/.claude/hooks directory... "
mkdir -p ~/.claude/hooks
echo -e "${GREEN}done${NC}"

# Step 2: Copy hook script
echo -n "Installing notify-monitor.sh... "
cp "$REPO_DIR/bin/notify-monitor.sh" ~/.claude/hooks/
chmod +x ~/.claude/hooks/notify-monitor.sh
echo -e "${GREEN}done${NC}"

# Step 3: Handle settings.json
SETTINGS_FILE=~/.claude/settings.json
TEMPLATE_FILE="$REPO_DIR/docs/claude-code-hooks-settings.json"

if [ -f "$SETTINGS_FILE" ]; then
    echo -e "${YELLOW}Found existing ~/.claude/settings.json${NC}"
    echo ""
    echo "You have two options:"
    echo "  1. Backup and replace with hook-enabled settings"
    echo "  2. Manually merge hooks from the template"
    echo ""
    read -p "Replace settings.json? (y/n): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Backup existing
        BACKUP_FILE=~/.claude/settings.json.backup.$(date +%s)
        cp "$SETTINGS_FILE" "$BACKUP_FILE"
        echo -e "Backed up to: ${YELLOW}$BACKUP_FILE${NC}"

        # Replace with template
        cp "$TEMPLATE_FILE" "$SETTINGS_FILE"
        echo -e "${GREEN}Settings replaced with hook configuration${NC}"
    else
        echo ""
        echo "Please manually merge hooks from:"
        echo -e "  ${YELLOW}$TEMPLATE_FILE${NC}"
        echo ""
        echo "Add the \"hooks\" section to your existing settings.json"
    fi
else
    echo -n "Creating ~/.claude/settings.json... "
    cp "$TEMPLATE_FILE" "$SETTINGS_FILE"
    echo -e "${GREEN}done${NC}"
fi

# Step 4: Verify installation
echo ""
echo "Verifying installation..."

VERIFY_FAILED=0

# Check hook script exists and is executable
if [ -x ~/.claude/hooks/notify-monitor.sh ]; then
    echo -e "  ${GREEN}✓${NC} Hook script installed and executable"
else
    echo -e "  ${RED}✗${NC} Hook script not found or not executable"
    VERIFY_FAILED=1
fi

# Check settings.json exists
if [ -f ~/.claude/settings.json ]; then
    # Check if it contains hooks configuration
    if grep -q '"hooks"' ~/.claude/settings.json 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} settings.json contains hooks configuration"
    else
        echo -e "  ${YELLOW}!${NC} settings.json exists but may need hooks configuration"
    fi
else
    echo -e "  ${RED}✗${NC} settings.json not found"
    VERIFY_FAILED=1
fi

echo ""

if [ $VERIFY_FAILED -eq 0 ]; then
    echo -e "${GREEN}Installation complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start the Claude Monitor:"
    echo "     python run.py"
    echo ""
    echo "  2. Start a Claude Code session in any project"
    echo ""
    echo "  3. Verify hooks are working:"
    echo "     curl http://localhost:5050/hook/status"
    echo ""
    echo "  4. View the dashboard:"
    echo "     http://localhost:5050"
else
    echo -e "${RED}Installation incomplete - please check the errors above${NC}"
    exit 1
fi
