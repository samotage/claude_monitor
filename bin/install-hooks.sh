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
# 4. Merges hook configuration into ~/.claude/settings.json (requires jq)
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

# Get absolute home directory path
HOME_DIR="$HOME"

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

# Step 3: Generate hooks configuration with absolute paths
HOOK_SCRIPT="$HOME_DIR/.claude/hooks/notify-monitor.sh"
SETTINGS_FILE="$HOME_DIR/.claude/settings.json"

# Check if jq is available for smart merging
if command -v jq &> /dev/null; then
    echo -n "Merging hooks into settings.json... "

    # Create the hooks JSON with absolute paths
    HOOKS_JSON=$(cat <<EOF
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": null,
        "hooks": [
          {
            "type": "command",
            "command": "$HOOK_SCRIPT session-start"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": null,
        "hooks": [
          {
            "type": "command",
            "command": "$HOOK_SCRIPT session-end"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": null,
        "hooks": [
          {
            "type": "command",
            "command": "$HOOK_SCRIPT stop"
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": null,
        "hooks": [
          {
            "type": "command",
            "command": "$HOOK_SCRIPT notification"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": null,
        "hooks": [
          {
            "type": "command",
            "command": "$HOOK_SCRIPT user-prompt-submit"
          }
        ]
      }
    ]
  }
}
EOF
)

    if [ -f "$SETTINGS_FILE" ]; then
        # Backup existing
        BACKUP_FILE="$SETTINGS_FILE.backup.$(date +%s)"
        cp "$SETTINGS_FILE" "$BACKUP_FILE"

        # Merge hooks into existing settings (deep merge)
        MERGED=$(jq -s '.[0] * .[1]' "$SETTINGS_FILE" <(echo "$HOOKS_JSON"))
        echo "$MERGED" > "$SETTINGS_FILE"
        echo -e "${GREEN}done${NC}"
        echo -e "  Backup saved to: ${YELLOW}$BACKUP_FILE${NC}"
    else
        # Create new settings file
        echo "$HOOKS_JSON" > "$SETTINGS_FILE"
        echo -e "${GREEN}done${NC}"
    fi
else
    echo -e "${YELLOW}jq not found - cannot automatically merge settings${NC}"
    echo ""
    echo "Please manually add hooks to ~/.claude/settings.json"
    echo ""
    echo "Add this to your settings.json (merge with existing content):"
    echo ""
    cat <<EOF
  "hooks": {
    "SessionStart": [{"matcher": null, "hooks": [{"type": "command", "command": "$HOOK_SCRIPT session-start"}]}],
    "SessionEnd": [{"matcher": null, "hooks": [{"type": "command", "command": "$HOOK_SCRIPT session-end"}]}],
    "Stop": [{"matcher": null, "hooks": [{"type": "command", "command": "$HOOK_SCRIPT stop"}]}],
    "Notification": [{"matcher": null, "hooks": [{"type": "command", "command": "$HOOK_SCRIPT notification"}]}],
    "UserPromptSubmit": [{"matcher": null, "hooks": [{"type": "command", "command": "$HOOK_SCRIPT user-prompt-submit"}]}]
  }
EOF
    echo ""
    echo -e "${YELLOW}Or install jq (brew install jq) and run this script again${NC}"
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

# Check settings.json exists and contains hooks
if [ -f ~/.claude/settings.json ]; then
    if grep -q '"hooks"' ~/.claude/settings.json 2>/dev/null; then
        # Check that paths are absolute (not using ~ or $HOME)
        if grep -q '~/.claude/hooks' ~/.claude/settings.json 2>/dev/null; then
            echo -e "  ${YELLOW}!${NC} settings.json uses ~ paths - may not work correctly"
            echo -e "      Run this script again with jq installed to fix"
        elif grep -q '\$HOME' ~/.claude/settings.json 2>/dev/null; then
            echo -e "  ${YELLOW}!${NC} settings.json uses \$HOME - may not work correctly"
            echo -e "      Run this script again with jq installed to fix"
        else
            echo -e "  ${GREEN}✓${NC} settings.json contains hooks with absolute paths"
        fi
    else
        echo -e "  ${YELLOW}!${NC} settings.json exists but needs hooks configuration"
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
