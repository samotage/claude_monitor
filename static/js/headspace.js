/* Headspace Functions */

// Auto-save debounce timers
let headspaceSaveTimer = null;
let focusTabSaveTimer = null;

/**
 * Schedule auto-save for headspace panel (debounced)
 */
function scheduleHeadspaceAutoSave() {
    if (headspaceSaveTimer) {
        clearTimeout(headspaceSaveTimer);
    }
    headspaceSaveTimer = setTimeout(() => {
        saveHeadspaceQuietly();
    }, 300);
}

/**
 * Schedule auto-save for focus tab (debounced)
 */
function scheduleFocusTabAutoSave() {
    if (focusTabSaveTimer) {
        clearTimeout(focusTabSaveTimer);
    }
    focusTabSaveTimer = setTimeout(() => {
        saveFocusTabQuietly();
    }, 300);
}

async function loadHeadspace() {
    const panel = document.getElementById('headspace-panel');
    if (!panel) return;

    try {
        const data = await fetchHeadspaceAPI();

        if (data.success) {
            currentHeadspace = data.data;
            renderHeadspace();
        }
    } catch (error) {
        console.error('Failed to load headspace:', error);
    }
}

function renderHeadspace() {
    const panel = document.getElementById('headspace-panel');
    const focusEl = document.getElementById('headspace-focus');
    const constraintsEl = document.getElementById('headspace-constraints');
    const constraintsTextEl = document.getElementById('headspace-constraints-text');
    const timestampEl = document.getElementById('headspace-timestamp');
    const emptyEl = document.getElementById('headspace-empty');
    const viewEl = panel.querySelector('.headspace-view');
    const editBtn = panel.querySelector('.headspace-edit-btn');

    // Show the panel
    panel.style.display = 'block';

    if (currentHeadspace && currentHeadspace.current_focus) {
        // Has headspace - show view mode
        viewEl.style.display = 'block';
        emptyEl.style.display = 'none';
        editBtn.textContent = 'Edit';

        focusEl.textContent = currentHeadspace.current_focus;

        if (currentHeadspace.constraints) {
            constraintsEl.style.display = 'block';
            constraintsTextEl.textContent = currentHeadspace.constraints;
        } else {
            constraintsEl.style.display = 'none';
        }

        timestampEl.textContent = formatHeadspaceTimestamp(currentHeadspace.updated_at);
    } else {
        // No headspace - show empty state
        viewEl.style.display = 'none';
        emptyEl.style.display = 'block';
        editBtn.textContent = 'Set';
    }
}

function enterHeadspaceEditMode() {
    const panel = document.getElementById('headspace-panel');
    const focusInput = document.getElementById('headspace-focus-input');
    const constraintsInput = document.getElementById('headspace-constraints-input');

    // Populate inputs with current values
    if (currentHeadspace) {
        focusInput.value = currentHeadspace.current_focus || '';
        constraintsInput.value = currentHeadspace.constraints || '';
    } else {
        focusInput.value = '';
        constraintsInput.value = '';
    }

    panel.classList.add('editing');
    focusInput.focus();
}

function exitHeadspaceEditMode() {
    const panel = document.getElementById('headspace-panel');
    panel.classList.remove('editing');
}

async function saveHeadspace() {
    const focusInput = document.getElementById('headspace-focus-input');
    const constraintsInput = document.getElementById('headspace-constraints-input');

    const currentFocus = focusInput.value.trim();
    const constraints = constraintsInput.value.trim() || null;

    if (!currentFocus) {
        focusInput.focus();
        return;
    }

    try {
        const data = await saveHeadspaceAPI({
            current_focus: currentFocus,
            constraints: constraints
        });

        if (data.success) {
            currentHeadspace = data.data;
            exitHeadspaceEditMode();
            renderHeadspace();
        } else {
            console.error('Failed to save headspace:', data.error);
        }
    } catch (error) {
        console.error('Failed to save headspace:', error);
    }
}

/**
 * Auto-save headspace without exiting edit mode (quiet save)
 */
async function saveHeadspaceQuietly() {
    const focusInput = document.getElementById('headspace-focus-input');
    const constraintsInput = document.getElementById('headspace-constraints-input');
    const panel = document.getElementById('headspace-panel');

    if (!focusInput) return;

    const currentFocus = focusInput.value.trim();
    const constraints = constraintsInput.value.trim() || null;

    // Don't save if focus is empty
    if (!currentFocus) return;

    // Show saving indicator
    panel.classList.add('saving');

    try {
        const data = await saveHeadspaceAPI({
            current_focus: currentFocus,
            constraints: constraints
        });

        if (data.success) {
            currentHeadspace = data.data;
            renderHeadspace();
            panel.classList.remove('saving');
            panel.classList.add('saved');
            setTimeout(() => panel.classList.remove('saved'), 1500);
        } else {
            panel.classList.remove('saving');
            panel.classList.add('save-error');
            setTimeout(() => panel.classList.remove('save-error'), 2000);
        }
    } catch (error) {
        console.error('Failed to auto-save headspace:', error);
        panel.classList.remove('saving');
        panel.classList.add('save-error');
        setTimeout(() => panel.classList.remove('save-error'), 2000);
    }
}

// =============================================================================
// Focus Tab Functions
// =============================================================================

async function loadFocusTab() {
    const focusInput = document.getElementById('focus-current-input');
    const constraintsInput = document.getElementById('focus-constraints-input');
    const historyList = document.getElementById('focus-history-list');

    // Load current headspace into inputs
    try {
        const data = await fetchHeadspaceAPI();
        if (data.success && data.data) {
            focusInput.value = data.data.current_focus || '';
            constraintsInput.value = data.data.constraints || '';
        }
    } catch (error) {
        console.error('Failed to load headspace for focus tab:', error);
    }

    // Load history
    try {
        const response = await fetch('/api/headspace/history');
        const data = await response.json();

        if (data.success && data.data && data.data.length > 0) {
            let html = '';
            data.data.slice(0, 10).forEach(item => {
                const time = formatHeadspaceTimestamp(item.updated_at);
                html += `
                    <div class="focus-history-item">
                        <div class="focus-history-content">"${escapeHtml(item.current_focus)}"</div>
                        <div class="focus-history-time">${time}</div>
                    </div>
                `;
            });
            historyList.innerHTML = html;
        } else {
            historyList.innerHTML = '<p class="focus-empty">No focus history yet.</p>';
        }
    } catch (error) {
        console.error('Failed to load focus history:', error);
        historyList.innerHTML = '<p class="focus-empty">Failed to load history.</p>';
    }
}

async function saveFocusFromTab() {
    const focusInput = document.getElementById('focus-current-input');
    const constraintsInput = document.getElementById('focus-constraints-input');
    const statusEl = document.getElementById('focus-save-status');

    const currentFocus = focusInput.value.trim();
    const constraints = constraintsInput.value.trim() || null;

    if (!currentFocus) {
        statusEl.textContent = 'Focus is required';
        statusEl.className = 'focus-status error';
        focusInput.focus();
        return;
    }

    statusEl.textContent = 'Saving...';
    statusEl.className = 'focus-status';

    try {
        const data = await saveHeadspaceAPI({
            current_focus: currentFocus,
            constraints: constraints
        });

        if (data.success) {
            currentHeadspace = data.data;
            statusEl.textContent = 'Saved!';
            statusEl.className = 'focus-status success';

            // Also update the dashboard headspace panel
            renderHeadspace();

            // Reload history
            loadFocusTab();

            setTimeout(() => {
                statusEl.textContent = '';
                statusEl.className = 'focus-status';
            }, 2000);
        } else {
            statusEl.textContent = 'Failed to save';
            statusEl.className = 'focus-status error';
        }
    } catch (error) {
        console.error('Failed to save focus:', error);
        statusEl.textContent = 'Error saving';
        statusEl.className = 'focus-status error';
    }
}

/**
 * Auto-save focus tab without reloading history (quiet save)
 */
async function saveFocusTabQuietly() {
    const focusInput = document.getElementById('focus-current-input');
    const constraintsInput = document.getElementById('focus-constraints-input');
    const statusEl = document.getElementById('focus-save-status');

    if (!focusInput) return;

    const currentFocus = focusInput.value.trim();
    const constraints = constraintsInput.value.trim() || null;

    // Don't save if focus is empty
    if (!currentFocus) return;

    statusEl.textContent = 'Auto-saving...';
    statusEl.className = 'focus-status';

    try {
        const data = await saveHeadspaceAPI({
            current_focus: currentFocus,
            constraints: constraints
        });

        if (data.success) {
            currentHeadspace = data.data;
            statusEl.textContent = 'Saved';
            statusEl.className = 'focus-status success';

            // Update the dashboard headspace panel
            renderHeadspace();

            setTimeout(() => {
                statusEl.textContent = '';
                statusEl.className = 'focus-status';
            }, 1500);
        } else {
            statusEl.textContent = 'Save failed';
            statusEl.className = 'focus-status error';
            setTimeout(() => {
                statusEl.textContent = '';
                statusEl.className = 'focus-status';
            }, 2000);
        }
    } catch (error) {
        console.error('Failed to auto-save focus:', error);
        statusEl.textContent = 'Error';
        statusEl.className = 'focus-status error';
        setTimeout(() => {
            statusEl.textContent = '';
            statusEl.className = 'focus-status';
        }, 2000);
    }
}
