/* Headspace Functions */

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
