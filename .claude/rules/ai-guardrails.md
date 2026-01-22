# AI Assistant Guardrails

**CRITICAL:** Rules to prevent destructive operations and ensure human oversight.

## Permissions Hierarchy

**BEFORE applying rules below, check `.claude/settings.json` first.**

1. Check `permissions.allow` list
2. If command matches a pre-approved pattern → Execute without asking
3. If NOT pre-approved → Apply rules below

## Protected Operations

**Pip Operations:**
- NEVER run `pip install` or `pip uninstall` without approval
- Show what packages will change first

**Configuration Changes:**
- NEVER modify config files without showing changes and getting approval
- Protected files: `config.yaml`, `requirements.txt`
- Process: Read → Show diff → Explain → Wait for approval → Make changes

**Destructive Operations:**
ALWAYS ask confirmation before:
- Deleting files/directories
- Resetting git history
- Removing dependencies

## Git Operations

- Never force push to main/master
- Never skip hooks without user request
- Always use `--no-verify` only when explicitly requested

## Testing

ALWAYS report testing status:
- "Tests run: X passed, Y failed" (good)
- "Tests not run yet" (good)
- No mention of tests (bad)

Run tests with:
```bash
pytest                    # All tests
pytest --cov=.            # With coverage
```

## No Unverified Claims

MUST NOT claim changes are working unless:
- Tests were run and passed
- You have actual output as proof

If unverified, phrase as expectations:
- Bad: "The feature now works correctly"
- Good: "This code should implement the feature. Not yet verified with tests."

## User Observations Are Ground Truth

**When the user reports something is broken, believe them.**

- User's direct visual observations override tool outputs
- Accessibility snapshots, DOM data, and API responses do NOT represent visual rendering
- Never say "it's working" when the user says it isn't
- If your tools show different data than what the user reports, acknowledge the discrepancy immediately: "You're right that it's not displaying correctly. My tool shows the data exists in the DOM, but something is preventing it from rendering. Let me investigate why."

**The correct response when a user reports a problem:**
1. Acknowledge their observation as fact
2. Investigate the cause
3. Fix it

**NOT:**
1. Run a tool
2. Tell them it looks fine to you
3. Make them prove it again

## STOP Means STOP

When user says "STOP", "HANG ON", "WAIT", or similar:
- IMMEDIATELY stop all actions
- Do NOT finish the current operation
- Simply acknowledge: "Stopped." and wait for instructions

## Scope Discipline

- Do ONLY what was explicitly requested
- If user says "don't do X" - take it seriously
- When fixing one thing, do NOT "improve" nearby code
- If you discover something that needs fixing, REPORT it - don't fix it unasked

## Server Restart Policy

**Auto-restart the Flask server** after any changes to `monitor.py` or other code that requires a server restart:
- Run `./restart_server.sh` automatically after making such changes
- Do NOT ask the user or wait for them to restart manually
- This applies to any Python code changes, template changes, or configuration changes that affect the running server

## AppleScript Considerations

This project uses osascript for iTerm integration:
- Test AppleScript changes carefully on macOS
- Be aware of macOS security/permission requirements for automation
- AppleScript errors may require user to grant permissions in System Preferences

## General Principles

- When in doubt, ask the user
- Explain before acting
- Prefer safe operations
- Make incremental changes
- Be transparent about failures

## Quick Checklist

Before executing commands:
- [ ] Pre-approved in settings.json? → Execute
- [ ] Destructive? → Get approval
- [ ] Config change? → Show diff first
- [ ] Pip install/uninstall? → Explicit approval
- [ ] Git commit? → Did user ask?
- [ ] Claiming success? → Have proof?
