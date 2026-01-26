#!/bin/bash
#
# Claude Code Hook Notifier
#
# This script is called by Claude Code hooks to send lifecycle events
# to the Claude Monitor application.
#
# Usage:
#   notify-monitor.sh <event-type>
#
# Event types:
#   session-start      - Claude Code session started
#   session-end        - Claude Code session ended
#   stop               - Claude finished a turn (primary completion signal)
#   notification       - Various notifications from Claude Code
#   user-prompt-submit - User submitted a prompt
#
# Environment variables (set by Claude Code):
#   CLAUDE_SESSION_ID        - Unique session identifier
#   CLAUDE_WORKING_DIRECTORY - Current working directory
#
# Configuration:
#   CLAUDE_MONITOR_URL - Monitor URL (default: http://localhost:5050)
#
# Installation:
#   1. Copy this script to ~/.claude/hooks/notify-monitor.sh
#   2. Make it executable: chmod +x ~/.claude/hooks/notify-monitor.sh
#   3. Configure hooks in ~/.claude/settings.json
#

set -e

# Configuration
MONITOR_URL="${CLAUDE_MONITOR_URL:-http://localhost:5050}"
TIMEOUT_CONNECT=1
TIMEOUT_MAX=2

# Event type from first argument
EVENT_TYPE="${1:-unknown}"

# Session details from Claude Code environment
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
WORKING_DIR="${CLAUDE_WORKING_DIRECTORY:-$(pwd)}"
TIMESTAMP=$(date +%s)

# Build JSON payload
# Using printf for proper JSON escaping of paths
PAYLOAD=$(printf '{"session_id":"%s","event":"%s","cwd":"%s","timestamp":%s}' \
    "$SESSION_ID" \
    "$EVENT_TYPE" \
    "$WORKING_DIR" \
    "$TIMESTAMP")

# Send to monitor (fail silently if unavailable)
# The monitor may not be running, and we must never block Claude Code
curl -s \
    --connect-timeout "$TIMEOUT_CONNECT" \
    --max-time "$TIMEOUT_MAX" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "${MONITOR_URL}/hook/${EVENT_TYPE}" \
    2>/dev/null || true

# Always exit successfully so we don't block Claude Code
exit 0
