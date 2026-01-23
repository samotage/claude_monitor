---
name: 'SOP 70: targeted-tests'
description: 'Choose and run most relevant tests for a given change'
---

# SOP 70: targeted-tests

**Command name:** `SOP 70: targeted-tests`

**Prompt:**

You help me choose and run the most relevant tests for a given change in a Ruby on Rails monorepo.

You have access to Cursor's workspace and integrated terminal. Whenever these instructions mention running shell commands or reading/writing files, **you must perform those actions yourself** using Cursor's tools.

- Do **not** ask me to run shell commands or manually open/edit files, except to confirm that a plan or result looks correct.
- After each critical action (collecting context, reading OpenSpec, computing changed files, planning tests, running tests, updating tasks), **checkpoint with me and wait for confirmation** before proceeding.
- **Always update the Testing Status Summary section in `tasks.md` after test runs are complete**, before finishing the command.

---

## Step 0: Get Change Name Input

**IMPORTANT: DO NOT PROCEED without this input.**

1. **Check if change name is provided:**

   🔍 **CONDITIONAL CHECK - YOU MUST EVALUATE THIS EXACTLY**

   **Condition to check:** Is `{{change_name}}` empty, not provided, or appears as a placeholder (like "{{change_name}}")?

   **IF `{{change_name}}` is empty/placeholder:**

   🛑 **MANDATORY STOP - YOU MUST NOT PROCEED WITHOUT INPUT**

   **YOU MUST:**
   - Display the following message to the user:

     ```
     Please provide the change name to run targeted tests.

     Example: `inquiry-02-email` or `settings-controller`

     What is the change name?
     ```

   - **WAIT for user response in plain text**
   - **YOU MUST NOT proceed until the user provides a valid change name**
   - **YOU MUST end your message/turn after asking for the change name**

   **ELSE IF `{{change_name}}` is provided:**

   - **YOU MUST output:** `✓ Step 0 complete - Change name received: {{change_name}}`
   - Store the value as `{{change_name}}`
   - **YOU MUST proceed to Step 0.5**

---

## Step 0.5: Verify implementation tasks are complete

**Before proceeding with testing, you must verify that all preceding implementation tasks are complete.**

Now that you have the change name, automatically perform this verification:

1. **Read the OpenSpec `tasks.md` file** (if it exists) for this change:

   - Locate `openspec/changes/{{change_name}}/tasks.md`
   - Read the entire file to understand all task phases

2. **Identify all implementation-related tasks** (tasks that should be completed before testing):

   - Look for sections labeled "Implementation", "Phase 2: Implementation", or similar
   - Include validation tasks that are prerequisites to testing
   - Exclude testing tasks themselves (those will be verified after tests run)

3. **Check task completion status**:

   - Identify all implementation/validation tasks that are NOT marked as complete (`- [ ]` instead of `- [x]`)
   - Create a list of incomplete tasks with their descriptions

4. **Investigate incomplete tasks**:

   - First, run `git diff --name-only` to get changed files (needed for investigation)
   - For each incomplete task, check if the work described has actually been completed:
     - Review changed files from git diff to see if the task work is present
     - Read relevant source files mentioned in task descriptions to verify implementation
     - Check if the described functionality exists in the codebase
     - Compare task requirements with actual code changes
   - Determine if each task can be safely marked as complete based on code verification
   - **If tasks can be verified as complete, automatically update `tasks.md` to mark them complete** (update checkboxes from `- [ ]` to `- [x]`)
   - Track which tasks were auto-completed for the checkpoint report

5. **Determine if blockers exist**:

   - After investigation, categorize tasks:
     - Tasks that were auto-completed (verified in code)
     - Tasks that remain incomplete but can be verified (auto-completed)
     - Tasks that remain incomplete and **cannot** be verified through code inspection (blockers)

6. **Handle blockers**:

   - **If there are blockers** (incomplete tasks that cannot be verified as complete):
     - Present findings and stop:
       > **⚠️ BLOCKER: Implementation Task Status**
       >
       > **Remaining incomplete tasks that cannot be verified:**
       >
       > - `- [ ] 2.5 Manual browser testing` - **Investigation**: No evidence this has been performed. **Recommendation**: Requires manual verification before proceeding.
       >
       > [List any tasks that cannot be marked complete after investigation]
       >
       > **Testing cannot proceed until these tasks are completed.**
       >
       > [Wait for user to complete remaining tasks]
     - **WAIT for user confirmation** before proceeding
   - **If there are NO blockers** (all tasks complete or auto-completed):
     - If any tasks were auto-completed, briefly note: `✓ Auto-completed [N] implementation task(s) based on code verification`
     - **Auto-proceed directly to Steps 1.1-1.3** without stopping for confirmation

**Important:** Only stop and wait for confirmation if there are incomplete implementation tasks that cannot be verified as complete through code inspection. If all tasks are complete or can be auto-completed, proceed automatically to testing.

---

## Step 1: Automate initial setup

**After Step 0 and Step 0.5 complete (change name collected and implementation verified):**

The change name is already stored as `{{change_name}}` from Step 0.

**After Step 0.5 completes (no blockers, or blockers resolved and user approved):**

Automatically perform Steps 1.1, 1.2, and 1.3 without waiting for confirmation.

**Important:** Step 0.5 will only stop if there are blockers (incomplete tasks that cannot be auto-completed). If all tasks are complete or can be auto-completed, it will auto-proceed to Steps 1.1-1.3.

---

## Step 1.1: Infer context and description

1. Try to infer `{{change_desc}}` from the OpenSpec change with the same `{{change_name}}`:

   - Check if `openspec/changes/{{change_name}}/proposal.md` or `openspec/changes/{{change_name}}/spec.md` exists.
   - If found, read it and extract a brief description.
   - If not found, use a placeholder like `"Change description not found in OpenSpec"`.

2. Prepare the context line (but don't ask for confirmation yet):
   - Context: `{{change_name}}` – `{{change_desc}}`

---

## Step 1.2: Locate OpenSpec `tasks.md`

Locate and read the OpenSpec `tasks.md` file for this change **using Cursor's file tools**:

1. Check if `openspec/changes/{{change_name}}/tasks.md` exists in the workspace.
2. If it exists:

   - Open and read the file.
   - Identify all test-related tasks (look for sections like `Testing`, `7. Testing`, or checklist items that clearly relate to tests).
   - Note the task numbers/labels and their descriptions.

3. If it doesn't exist:

   - Note: `No OpenSpec tasks.md found for this change`.
   - Continue with test proposal (the change may not use OpenSpec).

Prepare a summary (but don't ask for confirmation yet):

- Found tasks.md: [y/n based on findings]
- Test-related tasks: [short list or `none`]

---

## Step 1.3: Compute changed files via git

Determine the changed files using git **yourself**:

1. From the repository root, use Cursor's terminal to run:

   - `git diff --name-only`

2. Capture the full command output.

3. Prepare the output in a fenced code block format (but don't ask for confirmation yet).

4. Prepare a clean bullet list of changed files.

Do **not** ask me to run `git diff`; you are responsible for running it and pasting the results here.

---

## Step 1.4: Automated test file discovery

**Automatically discover test files** based on Rails conventions and changed files:

1. For each changed file, apply the following discovery rules:

   **Model files** (`app/models/*.rb`):

   - Direct: `spec/models/{model_name}_spec.rb`
   - Related: Search for feature specs that might test this model (e.g., `spec/features/*{model_name}*_spec.rb`)

   **Controller files** (`app/controllers/*_controller.rb`):

   - Direct: `spec/requests/{controller_name}_spec.rb` (without `_controller` suffix)
   - Alternative: `spec/features/{controller_name}_spec.rb`
   - Related: `spec/controllers/{controller_name}_controller_spec.rb` (if using controller specs)

   **View files** (`app/views/**/*.{haml,erb}`):

   - Direct: `spec/features/{view_path}_spec.rb` (e.g., `app/views/accounts/edit.html.haml` → `spec/features/account_edit_spec.rb`)
   - Related: Feature specs that match the controller/action

   **Test files** (`spec/**/*_spec.rb`):

   - Direct: Run the changed test file itself

   **Routes** (`config/routes.rb`):

   - Run broader integration/feature tests

   **Migrations** (`db/migrate/*.rb`):

   - Model specs for affected models
   - Feature specs that use affected models

   **Shared/common files** (`app/concerns/*.rb`, `app/services/*.rb`, `app/helpers/*.rb`):

   - Search for specs that include/use these files
   - Run broader test suite if impact is unclear

2. For each discovered test file, check if it exists using file system tools.

3. Prioritize discovered test files:

   - **Priority 1**: Direct test files (changed test files or exact matches)
   - **Priority 2**: Model/controller/view specs (direct Rails convention matches)
   - **Priority 3**: Related feature specs (broader coverage)
   - **Priority 4**: Integration tests (if no specific tests found)

4. Limit to **5-7 most relevant test files** (prioritize by specificity and relevance).

5. Prepare a list of discovered test files with their priority and mapping to changed files (but don't ask for confirmation yet).

---

## Step 1.5: Display context and discovered information (informational only)

After completing Steps 1.1, 1.2, 1.3, and 1.4 automatically, present all results together for informational purposes, then auto-proceed:

> **Context and Test Discovery Summary:**
>
> **1. Context:**
> Context: `{{change_name}}` – `{{change_desc}}`
>
> **2. OpenSpec summary for `{{change_name}}`:**
>
> - Found tasks.md: [y/n based on findings]
> - Test-related tasks: [short list or `none`]
> - Use for task mapping: [yes/no based on whether tasks.md exists and has test tasks]
>
> **3. Changed files from `git diff --name-only`:**
>
> ```
> # Output of: git diff --name-only
> [paste the actual output here]
> ```
>
> Detected changed files:
>
> - [list each file]
>
> **4. Automatically discovered test files:**
>
> - [Priority 1] `spec/path/to/direct_test_spec.rb` (matches: `app/path/to/file.rb`)
> - [Priority 2] `spec/path/to/model_spec.rb` (matches: `app/models/model.rb`)
> - [Priority 3] `spec/features/feature_spec.rb` (related to: `app/controllers/controller.rb`)
>
> → Proceeding automatically to create test plan and run tests...

**Auto-proceed to Step 2** without waiting for confirmation.

---

## Step 2: Map tests to OpenSpec tasks and create test plan

1. Review the test-related tasks identified in Step 1.2 (if available).

2. For each discovered test file from Step 1.4, identify which OpenSpec task(s) it covers (if tasks.md exists).

3. Create a mapping between test files and OpenSpec tasks.

4. Group test files by type for parallel execution:

   - **Group 1**: Model specs (can run in parallel)
   - **Group 2**: Request specs (can run in parallel)
   - **Group 3**: Feature specs (can run in parallel, but may be slower)
   - **Sequential**: If tests have dependencies or shared state, run sequentially

5. Present the test plan with mapping (informational), then auto-proceed:

> **Test Plan:**
>
> **Group 1 (Model specs - parallel):**
>
> 1. `bundle exec rspec spec/models/invite_spec.rb` → Covers tasks 13.9
>
> **Group 2 (Request specs - parallel):** 2. `bundle exec rspec spec/requests/invites_spec.rb` → Covers tasks 13.4, 13.8, 13.10
>
> **Group 3 (Feature specs - parallel):** 3. `bundle exec rspec spec/features/account_edit_spec.rb` → Covers tasks 13.1, 13.2, 13.3, 13.5, 13.6, 13.7, 13.11
>
> **Total: 3 test files, organized into 3 parallel groups**
>
> → Starting test execution...

**Auto-proceed directly to Step 3 (running tests)** without asking for confirmation.

---

## Step 3: Execute tests (parallel where safe)

1. **For parallel groups**: Run all test files in the group simultaneously using background processes.

   - Use `&` to run commands in background
   - Capture output to temporary files: `bundle exec rspec spec/path/to/test_spec.rb > /tmp/test_output_1.txt 2>&1 &`
   - Wait for all background processes to complete using `wait`
   - Read and combine all output files

2. **For sequential tests**: Run one at a time, waiting for completion before proceeding.

3. **Execution strategy**:

   - Run model specs first (fastest, most isolated)
   - Then request specs (moderate speed)
   - Finally feature specs (slowest, may have dependencies)
   - Within each group, run in parallel

4. For each test execution:

   - Run the command using Cursor's terminal
   - Capture the full output (stdout and stderr)
   - Parse the output to extract:
     - Total examples/tests
     - Passing count
     - Failing count
     - Pending count
     - Failure details (test name, file, line number, error message)

5. **After all tests complete**, collect all outputs and prepare a comprehensive summary (but don't ask for confirmation yet).

6. Present results:

> **Test Execution Results:**
>
> **Group 1 (Model specs):**
>
> ```
> # Output of: bundle exec rspec spec/models/invite_spec.rb
> [paste full output]
> ```
>
> ✅ **Result**: 27 examples, 27 passing, 0 failures
>
> **Group 2 (Request specs):**
>
> ```
> # Output of: bundle exec rspec spec/requests/invites_spec.rb
> [paste full output]
> ```
>
> ✅ **Result**: 19 examples, 19 passing, 0 failures
>
> **Group 3 (Feature specs):**
>
> ```
> # Output of: bundle exec rspec spec/features/account_edit_spec.rb
> [paste full output]
> ```
>
> ⚠️ **Result**: 49 examples, 48 passing, 0 failures, 1 pending
>
> **Overall Summary:**
>
> - Total: 95 examples
> - Passing: 94 (98.9%)
> - Pending: 1 (1.1%)
> - Failing: 0 (0%)

**Do not checkpoint after each individual test** - wait until all tests in a group complete, then proceed to Step 4.

---

## Step 4: Diagnose failures and suggest fixes

**After all tests complete**, analyze the results:

1. **Overall status**: Determine if all tests passed, or if there are failures/pending tests.

2. **For each failure**:

   - Extract test name, file, and line number
   - Analyze error message to identify likely cause
   - Apply common failure pattern detection:

     **Pattern: Missing migration**

     - Error: `ActiveRecord::StatementInvalid` or `PG::UndefinedColumn`
     - Suggestion: Run `rails db:migrate RAILS_ENV=test`

     **Pattern: Missing factory**

     - Error: `FactoryBot::UnknownFactory` or `Factory not registered`
     - Suggestion: Create or update factory file

     **Pattern: Route error**

     - Error: `ActionController::RoutingError` or `No route matches`
     - Suggestion: Check `config/routes.rb` and verify route exists

     **Pattern: Missing helper/method**

     - Error: `NoMethodError` or `undefined method`
     - Suggestion: Check if method exists, verify includes/extends

     **Pattern: Database constraint**

     - Error: `ActiveRecord::RecordInvalid` or `PG::ForeignKeyViolation`
     - Suggestion: Check model validations and associations

     **Pattern: View/partial missing**

     - Error: `ActionView::MissingTemplate` or `Missing partial`
     - Suggestion: Verify view file exists at expected path

3. **Present comprehensive diagnosis**:

   - **If there are test failures:**
     - Present diagnosis and wait for confirmation:
       > **CHECKPOINT 3 of 4: Test results and diagnosis**
       >
       > **Overall Status:**
       >
       > - ❌ Failures: [count and details]
       > - ⚠️ Warnings/pending: [count and details]
       >
       > **Failure Details:**
       >
       > 1. **Test**: `spec/features/account_edit_spec.rb:123` - "User can close dialog with ESC key"
       >    - **Error**: `Capybara::ElementNotFound: Unable to find button "Close"`
       >    - **Likely cause**: Dialog button selector changed or dialog not rendering
       >    - **Suggested fix**: Check `app/views/accounts/_invite_dialog.html.haml` for button ID/class
       >    - **Re-run command**: `bundle exec rspec spec/features/account_edit_spec.rb:123`
       >
       > **Next Steps:**
       >
       > - [List actionable fixes with file paths and commands]
       >
       > **Does this diagnosis look correct? [y,n]**
       >
       > - If **n**, specify what needs adjustment.
       > - If **y**, proceed to update tasks.md.
     - Wait for user response before proceeding to Step 5.
   - **If all tests pass** (no failures, only passing/pending):
     - Present summary (informational only):
       > **Test Results Summary:**
       >
       > **Overall Status:**
       >
       > - ✅ All tests passing: [yes/no]
       > - ⚠️ Warnings/pending: [count and details if any]
       >
       > → All tests passed. Proceeding to update tasks.md...
     - **Auto-proceed to Step 5** without asking for confirmation.

---

## Step 5: Update Testing Status Summary in `tasks.md`

**This step must be completed before finishing the command, regardless of test pass/fail status.**

1. Check if `openspec/changes/{{change_name}}/tasks.md` exists.

2. If it exists:

   - Read the current `tasks.md` file using Cursor's file editing tools.
   - Locate the "Testing Status Summary" section (usually at the end of the Testing section).
   - If the section doesn't exist, create it after the Testing section.

3. **Automatically parse test results** and update the section:

   - Extract from test outputs:
     - Test file names
     - Example counts (total, passing, failing, pending)
     - Failure details (if any)
   - Format with proper status indicators:
     - ✅ for all passing
     - ⚠️ for warnings/pending
     - ❌ for failures
   - Include overall summary statistics
   - Note any new tests written or existing tests updated

4. **Format example**:

   ```markdown
   **Testing Status Summary:**

   **Overall Test Results:**

   - Total examples: 95
   - Passing: 94 (98.9%)
   - Pending: 1 (1.1%)
   - Failing: 0 (0%)

   **Test File Breakdown:**

   1. ✅ **Model specs: `spec/models/invite_spec.rb`** (27 examples, all passing)

      - All existing tests passing
      - Added 5 new tests for `personal_message` field validation
      - Status: ✅ **100% passing**

   2. ✅ **Request specs: `spec/requests/invites_spec.rb`** (19 examples, all passing)

      - Preview endpoint tests (7 tests) - all passing
      - Create action tests (10 tests) - all passing
      - Authorization tests (2 tests) - all passing
      - Status: ✅ **100% passing**

   3. ✅ **Feature specs: `spec/features/account_edit_spec.rb`** (49 examples, 48 passing, 1 pending)
      - 24 existing tests: All passing
      - 25 new dialog tests: 24 passing, 1 pending
      - **Pending test**: Backdrop click to close dialog (JS test environment issue)
      - Status: ✅ **98.0% passing** - All critical functionality tested and passing
   ```

5. Write the updated `tasks.md` file back using Cursor's file editing tools.

6. Display confirmation:

   > ✓ Updated `openspec/changes/{{change_name}}/tasks.md`
   > ✓ Updated Testing Status Summary with current test results

7. If `tasks.md` doesn't exist, note this and continue to Step 6 (if applicable).

**Important:** This summary should always reflect the actual current state of testing, whether tests passed or failed.

---

## Step 6: Update OpenSpec `tasks.md` task checkboxes (if all tests pass)

**Only proceed with this step if ALL relevant tests have passed and `tasks.md` exists.**

1. Review which test tasks correspond to the passing tests (from the Step 2 mapping).

2. Show me which tasks you propose to mark complete:

> **CHECKPOINT 4 of 4: Update OpenSpec task checkboxes**
>
> **OpenSpec Tasks to Update:**
> The following tasks will be marked complete in `openspec/changes/{{change_name}}/tasks.md`:
>
> - [x] 13.1 Write feature specs for dialog opening/closing
> - [x] 13.2 Write feature specs for email validation (all edge cases)
> - [x] 13.3 Write feature specs for personal message customization
> - [x] 13.4 Write feature specs for preview functionality
> - [x] 13.5 Write feature specs for invitation creation via dialog
> - [x] 13.6 Write feature specs for duplicate email handling
> - [x] 13.7 Write feature specs for unsaved changes warning
> - [x] 13.8 Write controller specs for preview endpoint
> - [x] 13.9 Write model specs for personal_message field
> - [x] 13.10 Test Turbo Stream responses work correctly
> - [x] 13.11 Test accessibility (keyboard navigation, ARIA labels, screen readers)
>
> **Is this the correct set of tasks to mark complete? [y,n]**

3. Wait for my response. Do **not** proceed until I answer.

4. If I answer **y**:

   - Using Cursor's file editing tools, read the current `tasks.md` file.
   - Update the relevant task checkboxes from `- [ ]` to `- [x]`.
   - Write the updated file back.
   - Optionally show a small diff or snippet of the updated section.
   - Display confirmation:

     > ✓ Updated `openspec/changes/{{change_name}}/tasks.md`
     > ✓ Marked the following tasks as complete: [list task numbers]

5. If I answer **n** or `tasks.md` doesn't exist, clearly state that you are skipping the update and why.

**Important:** Only mark tasks complete if **all** corresponding tests passed. If any tests failed, do not update `tasks.md` task checkboxes (but still update the Testing Status Summary).

---

## Return / Response format

**Before tests are run:**

- **Step 0 (Input collection)** - Only if change name not provided:
  - MANDATORY STOP to collect change name
  - Wait for user response before proceeding
- **Step 0.5 (Prerequisite check)** - Only if blockers are found:
  - Implementation task completion status
  - Investigation results for incomplete tasks
  - Auto-completed tasks (if any)
  - Blockers that must be resolved
  - **STOPS and waits for user confirmation** only if blockers exist
  - If no blockers, auto-proceeds silently (may note auto-completed tasks)
- **Context and Test Discovery Summary (informational only)** - Auto-proceeds:
  - A short **Context** line using the inputs
  - A summary of OpenSpec test-related tasks (or a note that none were found)
  - Changed files from `git diff --name-only`
  - **Automatically discovered test files** with priority and mapping
  - States "→ Proceeding automatically to create test plan and run tests..."
- **Test Plan (informational only)** - Auto-proceeds:
  - **Automatically discovered test files** organized into parallel groups
  - **Mapping to OpenSpec tasks** (if `tasks.md` exists)
  - States "→ Starting test execution..."
  - **Runs tests immediately** without confirmation

**While running tests:**

- For each parallel group:
  - List the test files being run in parallel
  - After group completion, show all outputs together
  - Summary for the group (pass/fail counts)
- No per-command checkpoints (batch reporting instead)

**After tests are complete:**

- **If test failures exist:**
  - Comprehensive diagnosis checkpoint (CHECKPOINT 3 of 4) with:
    - **Overall Pass/Fail summary** (all groups combined)
    - **Per-failure details** with file/line, error analysis, and suggested fixes
    - **Common failure pattern detection** with actionable suggestions
    - A **Next steps** section with concrete guidance
    - **Asks for confirmation** before proceeding
- **If all tests pass:**
  - Test results summary (informational only)
  - States "→ All tests passed. Proceeding to update tasks.md..."
  - **Auto-proceeds** to Step 5 without confirmation

**After tests are complete (regardless of pass/fail):**

- Automatic update of "Testing Status Summary" section in `tasks.md` (if it exists)
- Include test file names, pass/fail counts, and overall status
- Parsed and formatted automatically from test outputs

**If all tests pass and `tasks.md` exists:**

- Final checkpoint (CHECKPOINT 4 of 4) showing which OpenSpec tasks correspond to passing tests
- Ask for confirmation before updating task checkboxes in `tasks.md`
- After confirmation, update task checkboxes using Cursor's file tools and display what changed

**Summary of checkpoint flow:**
- **Before tests:** 0-1 checkpoints (only if Step 0 finds blockers)
- **After tests (failures):** 1 checkpoint (diagnosis confirmation)
- **After tests (all pass):** 0 checkpoints (auto-proceed) + 1 final checkpoint (task checkbox update)

Always keep responses focused and practical, optimised for a tight Rails TDD feedback loop, and always run commands + file edits yourself, checkpointing only when user intervention is required.

---

**SOP 70 complete.**
