---
title: Troubleshooting
keywords: troubleshooting, problems, issues, fix, error, not working, debug, help
order: 5
---

# Troubleshooting

Common issues and how to resolve them.

## Sessions Not Showing

### Symptoms
- Dashboard shows no sessions
- Project column is empty despite running Claude

### Solutions

1. **Use the wrapper script**
   ```bash
   # Wrong - sessions won't be tracked
   claude
   
   # Correct - creates state file for tracking
   claude-monitor start
   ```

2. **Check project is in config.yaml**
   - Go to the config.yaml tab
   - Verify your project is listed with the correct path

3. **Verify state file exists**
   ```bash
   ls -la /path/to/your/project/.claude-monitor-*.json
   ```
   If no file exists, the wrapper script isn't being used.

4. **Check project path matches exactly**
   - The path in config.yaml must match where you're running `claude-monitor start`
   - Paths are case-sensitive

## Click-to-Focus Not Working

### Symptoms
- Clicking session cards does nothing
- iTerm window doesn't come to foreground

### Solutions

1. **Grant automation permissions**
   - Open **System Preferences → Privacy & Security → Automation**
   - Find your terminal application (Terminal.app or the app running the monitor)
   - Ensure it has permission to control iTerm

2. **Test AppleScript manually**
   ```bash
   osascript -e 'tell application "iTerm" to get name of windows'
   ```
   If this fails, permissions are the issue.

3. **Increase focus delay**
   In config.yaml:
   ```yaml
   iterm_focus_delay: 0.3  # Try higher values
   ```

## Notifications Not Appearing

### Symptoms
- No macOS notifications when input is needed
- "Test Notification" button does nothing

### Solutions

1. **Check terminal-notifier is installed**
   ```bash
   which terminal-notifier
   ```
   If not found:
   ```bash
   brew install terminal-notifier
   ```

2. **Verify notifications are enabled**
   - Go to config.yaml tab
   - Check the notifications section shows "enabled"

3. **Check macOS notification settings**
   - Open **System Preferences → Notifications**
   - Find "terminal-notifier"
   - Ensure notifications are allowed

4. **Check Do Not Disturb**
   - Notifications are suppressed when DND is active

## Port 5050 Already in Use

### Symptoms
- `Address already in use` error on startup
- Dashboard won't start

### Solutions

1. **Find and kill the existing process**
   ```bash
   lsof -i :5050
   kill <PID>
   ```

2. **Use the restart script**
   ```bash
   ./restart_server.sh
   ```

## tmux Not Working

### Symptoms
- "tmux is not available on this system" error
- Sessions not running in tmux mode
- Send API returns errors

### Solutions

1. **Install tmux**
   ```bash
   brew install tmux
   ```

2. **Verify installation**
   ```bash
   which tmux
   tmux -V
   ```
   Should show the tmux path and version.

3. **Enable tmux for your project**
   Add `tmux: true` to the project in config.yaml:
   ```yaml
   projects:
     - name: "my-app"
       path: "/Users/you/dev/my-app"
       tmux: true
   ```

4. **Or force tmux via command line**
   ```bash
   claude-monitor start --tmux
   ```

5. **Check if session is running in tmux**
   ```bash
   tmux list-sessions
   ```
   You should see `claude-<project-name>` listed.

### Send API Returns "Not a tmux session"

The session is running in iTerm mode (default). Either:
- Enable tmux in config.yaml for the project
- Or restart the session with `--tmux` flag

### tmux Session Already Exists

If you see "tmux session 'claude-my-app' already exists":
- The wrapper will attach to the existing session
- To kill it and start fresh: `tmux kill-session -t claude-my-app`

## AI Features Not Working

### Symptoms
- No priority recommendations
- History compression not running
- "OpenRouter API key not configured" message

### Solutions

1. **Add your API key to config.yaml**
   ```yaml
   openrouter:
     api_key: "sk-or-v1-your-key-here"
   ```

2. **Verify the key is valid**
   - Go to https://openrouter.ai/keys
   - Check your key is active and has credits

3. **Check for rate limiting**
   - If you see "rate_limited" errors, wait a few minutes
   - Consider upgrading your OpenRouter plan

4. **Restart the server**
   ```bash
   ./restart_server.sh
   ```

## Dashboard Shows "Initializing..."

### Symptoms
- Dashboard stuck on "initializing..."
- No content loads

### Solutions

1. **Check browser console for errors**
   - Open Developer Tools (Cmd+Option+I)
   - Look for JavaScript errors in Console

2. **Verify server is running**
   ```bash
   curl http://localhost:5050/api/sessions
   ```

3. **Check server logs**
   Look at the terminal where `python monitor.py` is running for errors.

## Stale Data / Not Updating

### Symptoms
- Session states seem outdated
- Dashboard not reflecting current iTerm state

### Solutions

1. **Check scan interval**
   - Default is 5 seconds
   - If set too high, updates will be slow

2. **Force refresh**
   - Refresh the browser page (Cmd+R)

3. **Check iTerm windows**
   - Minimized or hidden windows may not update properly

## Virtual Environment Issues

### Symptoms
- `ModuleNotFoundError` errors
- Commands not found

### Solutions

1. **Activate the virtual environment**
   ```bash
   source venv/bin/activate
   ```

2. **Reinstall dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Recreate virtual environment**
   ```bash
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Data File Issues

### Symptoms
- "Project not found" errors
- Missing roadmap or session data

### Solutions

1. **Check data directory exists**
   ```bash
   ls -la data/projects/
   ```

2. **Verify YAML syntax**
   If you've manually edited YAML files, check for syntax errors:
   ```bash
   python -c "import yaml; yaml.safe_load(open('data/projects/your-project.yaml'))"
   ```

3. **Reset project data**
   Delete the project's YAML file to reset:
   ```bash
   rm data/projects/your-project.yaml
   ```
   It will be recreated on next dashboard load.

## Getting More Help

If none of these solutions work:

1. **Check the server logs** - Run `python monitor.py` in a terminal and watch for errors
2. **Check browser console** - Look for JavaScript errors
3. **Review your config** - Ensure config.yaml is valid YAML
4. **Check file permissions** - Ensure the monitor can read/write to data directories
