#!/bin/bash
# Restart the Claude Headspace Flask server
#
# Uses the new src/ architecture via run.py

# Kill any existing server (match both monitor.py and run.py)
pkill -if "python.*(monitor|run)\.py" 2>/dev/null

# Wait for process to die
sleep 1

# Start server in background
cd "$(dirname "$0")"
source venv/bin/activate

# Use new architecture entry point (run.py)
# Falls back to legacy if run.py doesn't exist
if [[ -f "run.py" ]]; then
    python run.py > /tmp/claude_monitor.log 2>&1 &
else
    # Legacy fallback
    python monitor.py > /tmp/claude_monitor.log 2>&1 &
fi

# Wait for startup
sleep 2

# Verify it's running
if lsof -i :5050 > /dev/null 2>&1; then
    echo "Server started on port 5050"
    lsof -i :5050 | head -3
else
    echo "Server failed to start. Check /tmp/claude_monitor.log"
    tail -20 /tmp/claude_monitor.log
fi
