# OTL Commands for Claude Code and Cursor

Standard Operating Procedure commands that automate the OpenSpec change workflow in Claude Code and Cursor. These commands handle the full development lifecycle from starting a change through implementation to archiving.

## Command Invocation in Claude Code

All OTL commands are registered with YAML frontmatter and can be invoked in Claude Code by typing the command name as shown in each command's documentation.

**Example:**
- To invoke the PRD workshop: Type `10: prd-workshop`
- To start the queue process: Type `20: prd-orchestrate`

Commands are organized in subdirectories:
- `orch/` - Queue-based orchestration commands
- `build/` - Build automation commands  
- `prds/` - PRD management commands
- Root level - Standard Operating Procedure (SOP) commands

The directory structure is symlinked from `.cursor/commands/otl/` to `.claude/commands/otl/` for compatibility with both Claude Code and Cursor.

## Overview

These commands standardize how you work with OpenSpec change proposals in this Python project. Each command automates specific steps in the spec-driven development process, reducing manual work and ensuring consistent workflow.

## Workflows

### Manual Workflow (SOP Commands)

Use these commands in sequence for a complete change lifecycle with interactive checkpoints:

1. **SOP 10: preflight** - Verify git state is clean
2. **SOP 20: start-work-unit** - Create feature branch and OpenSpec proposal
3. **SOP 30: prebuild-snapshot** - Commit spec/docs before implementation
4. **SOP 60: review-current-diff** - Check for scope creep during development
5. **SOP 70: targeted-tests** - Run relevant tests for the change
6. **SOP 80: archive-and-commit** - Archive OpenSpec change and commit to GitHub
7. **SOP 99: rollback-the-alamo** - Emergency rollback if something goes wrong

### PRD Management Commands (Pre-Build)

Use these commands to prepare PRDs before they enter the build process:

1. **PRD 10: workshop** - Create or remediate PRDs interactively
2. **PRD 20: list** - Show pending PRDs awaiting build
3. **PRD 30: validate** - Quality gate (pass/fail) before orchestration
4. **PRD 40: sequence** - Recommend build order based on dependencies

See [PRD Command Suite README](prds/README.md) for detailed usage.

### Build Commands (Automated PRD-to-Implementation)

Use the build commands for automated PRD-to-implementation with minimal intervention:

1. **Build 50: build-unit** - Main orchestrator (prepare → proposal → build → test)
2. **Build 53: prepare** - Git preflight and branch setup sub-agent
3. **Build 56: test** - Test execution and reporting sub-agent

See [Build Command Suite README](build/README.md) for detailed usage.

**Workflow:**

```
10: prd-workshop     →  Create PRD
30: prd-validate     →  Quality gate
Build 50: build-unit  →  Full automated build with checkpoints
```

**Human intervention points:**

1. After PRD creation - validate and fix issues
2. After OpenSpec proposal creation - review/adjust/approve
3. After testing - review results, run SOP 80

### PRD Validation State

PRDs carry validation metadata in their YAML frontmatter to track their readiness for orchestration:

```yaml
---
validation:
  status: valid | invalid | unvalidated
  validated_at: "2026-01-03T10:30:00Z"
  validation_errors:  # Only present when invalid
    - "Missing Success Criteria section"
    - "TODO marker found on line 45"
---
```

**Validation States:**

- **valid** - PRD passed validation checks, ready for orchestration
- **invalid** - PRD failed validation with documented errors
- **unvalidated** - PRD has not been validated yet

**Key Points:**

- The `10: prd-workshop` command auto-validates PRDs after creation
- The `20: prd-list` command displays validation status badges for each PRD
- The `30: prd-validate` command updates the frontmatter with validation results
- Only validated PRDs can be added to the orchestration queue (validation gate)
- Validation status is checked during `20: prd-orchestrate` to skip re-validating already valid PRDs

### Queue-Based Orchestration (orch/)

For batch processing multiple PRDs, use the Ruby-based orchestration in `orch/`:

1. **Orchestration 10: queue-add** - Add validated PRD to build queue
2. **Orchestration 20: prd-orchestrate** - Main orchestrator (spawns sub-agents)
   - Automates: PREPARE → PROPOSAL → PREBUILD → BUILD → TEST → VALIDATE → FINALIZE → POST-MERGE
   - Human checkpoints: Proposal review, test completion, spec compliance, PR merge
   - Utility commands (91-93): checkpoint handling, notifications, status display

See [Orchestration README](orch/README.md) for the Ruby-backed queue system.

## Command Reference

### SOP 01: Workshop

**Purpose:** Reusable instruction block for collaborative refinement of requirements or specifications.

**When to use:** Before starting implementation, when refining requirements, or when instructions seem ambiguous.

**Usage:** Copy and paste the entire command content into your prompt or chat when you want to workshop content with the AI assistant.

**What it does:**

- Guides a structured workshop process
- Reduces assumptions and ensures completeness
- Includes checkpoints for validation

---

### SOP 10: Preflight

**Purpose:** Ensure you're on `development`, up to date, and in a clean git state before starting any change.

**When to use:** Before starting any new work unit. Run this first to verify your repository is ready.

**Usage:** Invoke `SOP 10: preflight` in Cursor chat.

**What it does:**

- Checks current branch and working tree status
- Switches to `development` if needed
- Pulls latest changes from origin
- Verifies final state is clean and ready

**Output:** Confirms branch, status, and next steps.

---

### SOP 20: Start Work Unit

**Purpose:** Start a new change cleanly by creating a feature branch and preparing an OpenSpec proposal.

**When to use:** When beginning a new change or feature.

**Usage:** Invoke `SOP 20: start-work-unit` with:

- Change name (e.g., `settings-controller-endpoint`)
- Brief description (1-3 sentences)

**What it does:**

- Verifies git state (assumes SOP 10 already run)
- Creates feature branch from `development`
- Helps define a one-line Definition of Done
- Prepares a ready-to-paste `/openspec/proposal` message

**Output:** Feature branch created, DoD agreed, OpenSpec proposal message ready to use.

**Next steps:** Copy the proposal message into a new planning agent tab.

---

### SOP 30: Prebuild Snapshot

**Purpose:** Create a git safety checkpoint by committing only spec/docs files before starting implementation.

**When to use:** After OpenSpec proposal is approved and before writing any implementation code.

**Usage:** Invoke `SOP 30: prebuild-snapshot` in Cursor chat.

**What it does:**

- Auto-detects change name from branch
- Categorizes files as spec/docs vs app code
- Validates OpenSpec planning tasks are complete
- Commits only spec/docs files
- Pushes to remote

**Safety checks:**

- Blocks if app code files are detected
- Blocks if OpenSpec planning tasks are incomplete
- Creates backup of existing commands if needed

**Output:** Spec snapshot commit created and pushed, working tree clean.

---

### SOP 60: Review Current Diff

**Purpose:** Summarize what changed in the current diff and flag scope creep relative to the intended change.

**When to use:** During development to verify you're staying within scope.

**Usage:** Invoke `SOP 60: review-current-diff` with the change name.

**What it does:**

- Analyzes current git diff
- Compares changes against OpenSpec proposal
- Flags files that seem out of scope
- Identifies potential scope creep
- Provides structured checkpoint for review

**Output:** Diff summary, scope analysis, and recommendations.

---

### SOP 70: Targeted Tests

**Purpose:** Choose and run the most relevant tests for a given change.

**When to use:** After implementation is complete, before archiving.

**Usage:** Invoke `SOP 70: targeted-tests` with the change name.

**What it does:**

- Verifies implementation tasks are complete
- Discovers test files based on changed files
- Maps tests to OpenSpec tasks
- Runs tests in parallel groups where safe
- Diagnoses failures with suggested fixes
- Updates Testing Status Summary in `tasks.md`

**Output:** Test results, failure diagnosis (if any), and updated `tasks.md`.

---

### SOP 80: Archive and Commit

**Purpose:** Standardize the final wrap-up for a work unit by archiving the OpenSpec change and committing to GitHub.

**When to use:** When all work is complete and ready to commit.

**Usage:** Invoke `SOP 80: archive-and-commit` with the change name.

**What it does:**

- Validates all tasks in `tasks.md` are complete
- Archives OpenSpec change
- Analyzes git status for cleanup
- Proposes commit message
- Commits and pushes to remote
- Optionally creates pull request

**Safety checks:**

- Blocks if tasks are incomplete
- Backs up existing commands
- Verifies archive completion

**Output:** Change archived, committed, pushed, and PR created (if requested).

---

### SOP 99: Rollback the Alamo

**Purpose:** Safely roll back a feature branch to the last good commit when a change has gone wrong.

**When to use:** Emergency use only, when you need to abandon current work and start over.

**Usage:** Invoke `SOP 99: rollback-the-alamo` with the change name.

**What it does:**

- Inspects recent commit history
- Identifies candidate last good commit (prefers prebuild snapshot)
- Explains destructive effects
- Provides rollback commands
- Verifies rollback state

**Warning:** This operation discards uncommitted changes and cannot be undone with normal git commands.

**Output:** Branch reset to last good commit, working tree clean.

---

## PRD Management Commands

These commands manage the PRD lifecycle before building. They ensure PRDs are validated and ready for automated builds.

### PRD 10: Workshop

**Purpose:** Interactive workshop for creating new PRDs or remediating failing ones.

**When to use:** When creating a new feature PRD or fixing validation failures.

**Usage:**

```bash
# Create new PRD
10: prd-workshop

# Remediate existing PRD
10: prd-workshop docs/prds/campaigns/my-prd.md
```

**Features:**

- BMAD techniques: Five Whys, gap detection, assumption reversal
- Conflict checking against existing work
- Scope assessment (targets 20-30 tasks)
- Requirement focus enforcement (WHAT not HOW)
- **Auto-validation after PRD creation** - Automatically validates and updates frontmatter

---

### PRD 20: List

**Purpose:** Show pending PRDs awaiting build with summaries and validation status.

**When to use:** To see what PRDs are ready for the build queue.

**Usage:** `20: prd-list`

**Output:** Grouped by subsystem with 18-token summaries and validation status badges:
- `[✓ Valid - Jan 2]` - Ready for orchestration
- `[✗ Invalid - 3 errors]` - Needs remediation
- `[⊗ Unvalidated]` - Needs validation

---

### PRD 30: Validate

**Purpose:** Quality gate that validates PRDs before build and updates their frontmatter.

**When to use:** Before running a build command on a PRD.

**Usage:** `30: prd-validate docs/prds/campaigns/my-prd.md`

**Checks:**

- Format compliance (required sections)
- Gap detection (no TODOs, placeholders)
- Requirement focus (WHAT not HOW)
- Conflict detection (existing work)
- Scope assessment (20-30 tasks target)
- Ambiguity check (measurable requirements)

**Output:** PASS, FAIL, or BLOCKED with remediation guidance.

**Important:** Automatically updates PRD frontmatter with validation status, timestamp, and errors (if any).

---

### PRD 40: Sequence

**Purpose:** Recommend build order for pending PRDs.

**When to use:** Before batch-adding PRDs to the queue.

**Usage:** `40: prd-sequence`

**Factors:** Dependencies, foundation features, complexity, size, business priority.

**Output:** Dependency graph and recommended build order with rationale.

---

## Build Commands

The build commands provide automated PRD-to-implementation workflows. See [Build README](build/README.md) for full documentation.

### Build 50: build-unit (Main Orchestrator)

**Purpose:** Automated PRD-to-implementation workflow with minimal intervention.

**When to use:** When you have a validated PRD and want to automate the full build process.

**Usage:** Invoke `Build 50: build-unit` with the PRD file path.

**Input:** PRD path - e.g., `docs/prds/inquiry-system/inquiry-02-email-prd.md`

**What it does:**

1. Invokes Build 53 (prepare sub-agent) to set up git state
2. Creates OpenSpec proposal from PRD content
3. Validates with `openspec validate --strict`
4. **Human checkpoint:** Review and approve proposal
5. Commits approved proposal (prebuild snapshot)
6. Compacts context (`/compact`)
7. Implements all tasks from tasks.md
8. Hands off to Build 56 (test sub-agent)

**Human checkpoints:**

- After OpenSpec creation - review, adjust if needed, approve
- After testing - review results via Build 56 notification

---

### Build 53: prepare (Setup Sub-Agent)

**Purpose:** Automated git preflight and branch setup.

**When to use:** Called automatically by Build 50. Can also be used standalone.

**Input:** PRD file path

**What it does:**

1. Validates PRD file exists
2. Derives change name from filename
3. Extracts Definition of Done from PRD
4. Checks git state with warning checkpoints for dirty tree or wrong branch
5. Creates feature branch `feature/{change_name}`

**Warning checkpoints:**

- Dirty working tree - prompts to proceed or clean up
- Not on development branch - prompts to proceed or switch
- Branch already exists - prompts to use, recreate, or abort

---

### Build 56: test (Test Sub-Agent)

**Purpose:** Automated testing and result notification.

**When to use:** Called automatically by Build 50 after implementation. Can also be used standalone.

**Input:** Change name (e.g., `inquiry-02-email`)

**What it does:**

1. Verifies implementation tasks complete (auto-marks if code evidence exists)
2. Discovers test files based on git diff
3. Runs tests in parallel groups
4. Updates Testing Status Summary in tasks.md
5. Displays results with actionable guidance

**On success:** Displays completion notification, reminds to run SOP 80

**On failure:** Displays failure details with diagnosis and suggested fixes

---

## Best Practices

### Full PRD Workflow (Recommended)

The complete workflow from idea to implementation:

**Phase 1: PRD Creation & Validation**

```
1. 10: prd-workshop        →  Create new PRD
2. 30: prd-validate        →  Quality gate
3. If FAIL: 10: prd-workshop {path}  →  Remediate
4. Repeat until PASS
```

**Phase 2: Automated Build**

```
1. Build 50: build-unit {prd_path}  →  Full automated workflow
2. Review OpenSpec proposal when prompted
3. Approve to continue with implementation
4. Review test results
5. Run SOP 80: archive-and-commit
```

**Benefits:**

- Quality gate catches issues early (cheaper to fix)
- Automated git setup and branching
- Minimal intervention during builds
- Clear checkpoints for human review

### Using SOP Commands (Manual Workflow)

For more control or when working without a complete PRD:

#### Starting a New Change

1. Always run **SOP 10: preflight** first
2. Use **SOP 20: start-work-unit** to create the feature branch
3. Get OpenSpec proposal approved before proceeding
4. Run **SOP 30: prebuild-snapshot** to commit the plan
5. Then start implementation

#### During Development

- Use **SOP 60: review-current-diff** periodically to check scope
- Keep `tasks.md` updated as you complete work
- Run tests locally before using **SOP 70: targeted-tests**

#### Completing a Change

1. Ensure all tasks in `tasks.md` are marked complete
2. Run **SOP 70: targeted-tests** to verify everything works
3. Use **SOP 80: archive-and-commit** to wrap up
4. Create PR and merge when ready

### Emergency Situations

If something goes wrong and you need to start over:

- Use **SOP 99: rollback-the-alamo** to reset to last good commit
- Re-run **SOP 20: start-work-unit** with a tighter scope if needed

## Integration with OpenSpec

These commands are designed to work with OpenSpec change proposals. They expect:

- OpenSpec changes in `openspec/changes/<change-name>/`
- `proposal.md` for change description
- `tasks.md` for task tracking
- `spec.md` for detailed specifications (optional)

Commands automatically detect and use OpenSpec files when available.

## Requirements

- Python project with pytest
- Ruby (for orchestration scripts)
- OpenSpec installed and configured
- Git repository with `development` branch
- Claude Code or Cursor IDE with integrated terminal access

## PRD Location Convention

PRDs must be organized in subsystem folders:

```
docs/prds/
├── walking-skeleton-prd.md      # Root-level: IGNORED
├── beta_signups/
│   ├── feature-prd.md           # Pending (to build)
│   └── done/
│       └── completed-prd.md     # Completed
├── campaigns/
│   └── ...
```

- **Pending**: `docs/prds/{subsystem}/{name}.md`
- **Completed**: `docs/prds/{subsystem}/done/{name}.md`
- **Root-level**: Ignored by orchestration

**PRD File Format with Validation:**

Each PRD should include YAML frontmatter with validation metadata:

```markdown
---
validation:
  status: valid
  validated_at: "2026-01-03T10:30:00Z"
---

# PRD: Feature Name

## Executive Summary
...
```

The validation frontmatter is automatically managed by the `30: prd-validate` command and `10: prd-workshop` command.

## Troubleshooting

**Command not found:** Ensure the command file exists in `.cursor/commands/otl/` and you're invoking it correctly in Cursor chat.

**Git state issues:** Run **SOP 10: preflight** to reset to a clean state.

**OpenSpec not detected:** Verify the change name matches the OpenSpec directory name in `openspec/changes/`.

**Tasks incomplete:** Review `openspec/changes/<change-name>/tasks.md` and mark completed tasks before archiving.

**PRD validation fails:** Use `10: prd-workshop {path}` to remediate issues interactively.

**PRD not listed:** Ensure PRD is in a subsystem folder (not root level) and not in a `done/` subdirectory.

## Directory Structure

```
.cursor/commands/otl/
├── README.md                    # This file
├── build/                       # Build automation commands
│   ├── README.md
│   ├── 50-build-unit.md        # Main orchestrator
│   ├── 53-prepare.md           # Setup sub-agent
│   └── 56-test.md              # Test sub-agent
├── orch/                        # Queue-based orchestration
│   ├── README.md
│   ├── 10-queue-add.md
│   ├── 20-start-queue-process.md
│   ├── 30-proposal.md
│   ├── 35-build.md
│   ├── 40-test.md
│   ├── 45-validate-build.md
│   ├── 50-finalize.md
│   ├── 60-post-merge.md
│   ├── 91-checkpoint.md
│   ├── 92-notify.md
│   └── 93-queue-status.md
├── prds/                        # PRD management commands
│   ├── README.md
│   ├── 10-workshop.md
│   ├── 20-list.md
│   ├── 30-validate.md
│   └── 40-sequence.md
├── sop-01-workshop.md           # Manual workflow SOPs
├── sop-10-preflight.md
├── sop-20-start-work-unit.md
├── sop-30-prebuild-snapshot.md
├── sop-60-review-current-diff.md
├── sop-70-targeted-tests.md
├── sop-80-archive-and-commit.md
└── sop-99-rollback-the-alamo.md
```
