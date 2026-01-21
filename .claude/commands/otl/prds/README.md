# PRD Workflow Commands

This directory contains commands for managing the PRD (Product Requirements Document) workflow.

## Commands Overview

- **10: prd-workshop** - Interactive workshop for creating or remediating PRDs
- **20: prd-list** - List all PRDs with validation status
- **30: prd-validate** - Validate a PRD before adding to orchestration queue
- **40: prd-sequence** - Create a sequence of related PRDs

## Git History Integration

### What It Does

The PRD workflow now incorporates git commit history analysis to help the AI understand:
- What has already been implemented in the codebase
- Recent development activity in related subsystems
- Patterns established by previous OpenSpec changes
- Files that are likely to be affected by new requirements

### When It's Used

#### During PRD Creation (10: prd-workshop)

**Phase 3: Existing Implementation Check**

Before defining detailed requirements, the workshop analyzes git history to:
1. Find related files in the codebase
2. Identify recent commits (last 12 months)
3. Map OpenSpec changes previously applied
4. Detect implementation patterns

This helps the AI:
- Detect potential conflicts early
- Suggest requirements that integrate well with existing code
- Recommend approaches consistent with project patterns
- Avoid duplicating existing functionality

**AI Context Only Mode:**

The git history information is used by the AI to inform its suggestions, but is NOT shown as raw data dumps to the user. Instead, the AI synthesizes findings into human-friendly summaries:

```
I've analyzed the project history for the inquiry subsystem.

**Existing Implementation:**
- 12 files found related to inquiries
- Active development: Last commit 2 weeks ago
- Follows pattern: model → service → controller → policy → views

**OpenSpec History:**
- inquiry-04-admin-crud - Archived Nov 20 - Added admin CRUD
- inquiry-03-email - Archived Nov 5 - Added email notifications

**Recommendations:**
- Consider integrating with existing InquiryProcessor service
- Follow established admin pattern (see admin/inquiries_controller.rb)
```

### Configuration

Default settings:
- **Timeframe:** 12 months back
- **Subsystem detection:** Automatic from PRD path (docs/prds/{subsystem}/)
- **Presentation:** AI context only (no raw dumps to user)

### Benefits

1. **Better Requirements** - AI suggests requirements aware of existing code
2. **Fewer Conflicts** - Early detection of overlapping work
3. **Consistent Patterns** - New features follow established conventions
4. **Accurate Scoping** - Understanding of affected files improves estimates

### Troubleshooting

**Git history analysis fails:**
- Ensure you're in a git repository
- Check that `git` command is available in PATH
- Verify OpenSpec directory structure exists

If analysis fails, the workflow continues without git context - PRDs can still be created, but without historical insights.

**Subsystem not detected:**
- Ensure PRD is saved in proper structure: `docs/prds/{subsystem}/{name}-prd.md`
- Root-level PRDs won't have subsystem context
- You can manually specify: `--subsystem inquiry-system`

### Performance

Git analysis adds approximately 2-5 seconds to PRD workflow.
- File listing: ~1s
- Commit history: ~1-2s
- OpenSpec mapping: ~1s

For very large repositories (>10K commits), consider reducing timeframe:
```bash
ruby orch/git_history_analyzer.rb --subsystem campaigns --months-back 6
```
