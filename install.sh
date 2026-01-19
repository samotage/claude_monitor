#!/bin/bash
#
# Claude Monitor - Installation Script
#
# This script sets up Claude Monitor on your Mac.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════╗"
echo "║       Claude Monitor Installer        ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check for macOS
check_macos() {
    if [[ "$(uname)" != "Darwin" ]]; then
        echo -e "${RED}Error: Claude Monitor requires macOS (uses AppleScript for iTerm integration)${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} macOS detected"
}

# Check for Python 3.10+
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: Python 3 is not installed${NC}"
        echo "  Install with: brew install python@3.11"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [[ $MAJOR -lt 3 ]] || [[ $MAJOR -eq 3 && $MINOR -lt 10 ]]; then
        echo -e "${RED}Error: Python 3.10+ required (found $PYTHON_VERSION)${NC}"
        echo "  Install with: brew install python@3.11"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
}

# Check for iTerm2
check_iterm() {
    if [[ ! -d "/Applications/iTerm.app" ]]; then
        echo -e "${YELLOW}Warning: iTerm2 not found in /Applications${NC}"
        echo "  Claude Monitor requires iTerm2 for session tracking."
        echo "  Download from: https://iterm2.com/"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✓${NC} iTerm2 found"
    fi
}

# Check for Homebrew
check_homebrew() {
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}Warning: Homebrew not found${NC}"
        echo "  terminal-notifier (for notifications) requires Homebrew."
        echo "  Install from: https://brew.sh/"
        return 1
    fi
    echo -e "${GREEN}✓${NC} Homebrew found"
    return 0
}

# Install terminal-notifier
install_terminal_notifier() {
    if command -v terminal-notifier &> /dev/null; then
        echo -e "${GREEN}✓${NC} terminal-notifier already installed"
        return
    fi

    if check_homebrew; then
        echo -e "${CYAN}Installing terminal-notifier...${NC}"
        brew install terminal-notifier
        echo -e "${GREEN}✓${NC} terminal-notifier installed"
    else
        echo -e "${YELLOW}Skipping terminal-notifier (notifications will be disabled)${NC}"
    fi
}

# Check for Claude Code CLI
check_claude() {
    if ! command -v claude &> /dev/null; then
        echo -e "${YELLOW}Warning: Claude Code CLI not found${NC}"
        echo "  Install from: https://docs.anthropic.com/en/docs/claude-code"
    else
        echo -e "${GREEN}✓${NC} Claude Code CLI found"
    fi
}

# Create virtual environment and install dependencies
setup_python_env() {
    echo -e "\n${CYAN}Setting up Python environment...${NC}"

    if [[ -d "$SCRIPT_DIR/venv" ]]; then
        echo "  Virtual environment already exists"
    else
        python3 -m venv "$SCRIPT_DIR/venv"
        echo -e "${GREEN}✓${NC} Virtual environment created"
    fi

    source "$SCRIPT_DIR/venv/bin/activate"
    pip install --quiet --upgrade pip
    pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
    echo -e "${GREEN}✓${NC} Dependencies installed"
}

# Setup config file
setup_config() {
    if [[ -f "$SCRIPT_DIR/config.yaml" ]]; then
        echo -e "${YELLOW}config.yaml already exists, skipping${NC}"
    else
        cp "$SCRIPT_DIR/config.yaml.example" "$SCRIPT_DIR/config.yaml"
        echo -e "${GREEN}✓${NC} Created config.yaml from example"
    fi
}

# Setup PATH for claude-monitor script
setup_path() {
    echo -e "\n${CYAN}Setting up claude-monitor command...${NC}"

    # Create ~/bin if it doesn't exist
    mkdir -p "$HOME/bin"

    # Create symlink
    if [[ -L "$HOME/bin/claude-monitor" ]] || [[ -f "$HOME/bin/claude-monitor" ]]; then
        rm "$HOME/bin/claude-monitor"
    fi
    ln -s "$SCRIPT_DIR/bin/claude-monitor" "$HOME/bin/claude-monitor"
    echo -e "${GREEN}✓${NC} Linked claude-monitor to ~/bin/"

    # Check if ~/bin is in PATH
    if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
        echo -e "${YELLOW}Note: ~/bin is not in your PATH${NC}"
        echo ""
        echo "  Add this line to your ~/.zshrc or ~/.bashrc:"
        echo -e "  ${CYAN}export PATH=\"\$HOME/bin:\$PATH\"${NC}"
        echo ""
    fi
}

# Print success message
print_success() {
    echo ""
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Installation complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo -e "${CYAN}Quick Start:${NC}"
    echo ""
    echo "  1. Edit config.yaml to add your projects:"
    echo -e "     ${YELLOW}$SCRIPT_DIR/config.yaml${NC}"
    echo ""
    echo "  2. Start the dashboard:"
    echo -e "     ${YELLOW}cd $SCRIPT_DIR && source venv/bin/activate && python monitor.py${NC}"
    echo ""
    echo "  3. Launch Claude Code with monitoring:"
    echo -e "     ${YELLOW}cd /path/to/your/project && claude-monitor start${NC}"
    echo ""
    echo "  4. Open http://localhost:5050 in your browser"
    echo ""
    echo -e "${CYAN}Tip:${NC} You can ask Claude Code to help configure this!"
    echo "     Just paste the README.md and ask for setup assistance."
    echo ""
}

# Main installation
main() {
    echo "Checking requirements..."
    echo ""

    check_macos
    check_python
    check_iterm
    check_claude

    echo ""
    install_terminal_notifier

    setup_python_env
    setup_config
    setup_path

    print_success
}

main "$@"
