#!/bin/bash
# Restart the Claude Monitor Flask server

# Kill any existing server (case-insensitive match for Python/python)
pkill -if "python.*monitor\.py" 2>/dev/null

# Wait for process to die
sleep 1

# Start server in background
cd "$(dirname "$0")"
source venv/bin/activate
python monitor.py > /tmp/claude_monitor.log 2>&1 &

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
