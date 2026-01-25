/* Settings Functions */

// Auto-save debounce timer for settings
let settingsSaveTimer = null;

/**
 * Schedule auto-save for settings (debounced, longer delay for batching)
 */
function scheduleSettingsAutoSave() {
    if (settingsSaveTimer) {
        clearTimeout(settingsSaveTimer);
    }
    settingsSaveTimer = setTimeout(() => {
        saveSettingsQuietly();
    }, 500);
}

/**
 * Auto-save settings without clearing status message immediately
 */
async function saveSettingsQuietly() {
    const statusEl = document.getElementById('settings-status');

    // Filter out empty projects
    const validProjects = currentProjects.filter(p => p.name && p.path);

    const config = {
        projects: validProjects,
        scan_interval: parseInt(document.getElementById('scan-interval').value) || 2,
        idle_timeout_minutes: parseInt(document.getElementById('idle-timeout-minutes').value) || 60,
        stale_threshold_hours: parseFloat(document.getElementById('stale-threshold-hours').value) || 4,
        openrouter: {
            api_key: document.getElementById('openrouter-api-key').value || '',
            model: document.getElementById('openrouter-model').value || 'anthropic/claude-3-haiku',
            compression_interval: parseInt(document.getElementById('openrouter-compression-interval').value) || 300
        },
        headspace: {
            enabled: getToggleState('headspace-enabled-btn'),
            history_enabled: getToggleState('headspace-history-btn')
        },
        priorities: {
            enabled: getToggleState('priorities-enabled-btn'),
            polling_interval: parseInt(document.getElementById('priorities-polling-interval').value) || 60,
            model: document.getElementById('priorities-model').value || ''
        }
    };

    statusEl.className = 'settings-status';
    statusEl.textContent = 'Auto-saving...';

    try {
        const result = await saveConfigAPI(config);

        if (result.success) {
            statusEl.className = 'settings-status success';
            statusEl.textContent = 'Saved';
            currentProjects = validProjects;

            setTimeout(() => {
                if (statusEl.textContent === 'Saved') {
                    statusEl.textContent = '';
                    statusEl.className = 'settings-status';
                }
            }, 1500);
        } else {
            statusEl.className = 'settings-status error';
            statusEl.textContent = 'Error: ' + (result.error || 'unknown');
            setTimeout(() => {
                statusEl.className = 'settings-status';
            }, 3000);
        }
    } catch (error) {
        statusEl.className = 'settings-status error';
        statusEl.textContent = 'Error: ' + error.message;
        setTimeout(() => {
            statusEl.className = 'settings-status';
        }, 3000);
    }
}

async function loadReadme() {
    try {
        const data = await fetchReadmeAPI();
        document.getElementById('readme-content').innerHTML = data.html;
    } catch (error) {
        console.error('Failed to load README:', error);
        document.getElementById('readme-content').innerHTML = '<p>// failed to load documentation</p>';
    }
}

async function loadSettings() {
    try {
        const config = await fetchConfigAPI();

        // Projects (existing)
        currentProjects = config.projects || [];
        renderProjectList();

        // Dashboard settings (existing)
        document.getElementById('scan-interval').value = config.scan_interval || 2;

        // Session summarization
        document.getElementById('idle-timeout-minutes').value = config.idle_timeout_minutes || 60;

        // Brain reboot
        document.getElementById('stale-threshold-hours').value = config.stale_threshold_hours || 4;

        // OpenRouter (nested)
        const openrouter = config.openrouter || {};
        document.getElementById('openrouter-api-key').value = openrouter.api_key || '';
        document.getElementById('openrouter-model').value = openrouter.model || 'anthropic/claude-3-haiku';
        document.getElementById('openrouter-compression-interval').value = openrouter.compression_interval || 300;

        // Headspace (nested)
        const headspace = config.headspace || {};
        setToggleState('headspace-enabled-btn', headspace.enabled !== false);
        setToggleState('headspace-history-btn', headspace.history_enabled !== false);

        // Priorities (nested)
        const priorities = config.priorities || {};
        setToggleState('priorities-enabled-btn', priorities.enabled !== false);
        document.getElementById('priorities-polling-interval').value = priorities.polling_interval || 60;
        document.getElementById('priorities-model').value = priorities.model || '';

        // Terminal Logging - load from dedicated endpoint for accurate in-memory state
        await loadTerminalLoggingState();

    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

/**
 * Load terminal logging debug state from API
 */
async function loadTerminalLoggingState() {
    try {
        const response = await fetch('/api/logs/terminal/debug');
        const data = await response.json();
        if (data.success) {
            setToggleState('terminal-logging-enabled-btn', data.debug_enabled);
        }
    } catch (error) {
        console.error('Failed to load terminal logging state:', error);
        setToggleState('terminal-logging-enabled-btn', false);
    }
}

/**
 * Toggle terminal debug logging
 */
async function toggleTerminalLogging() {
    const btn = document.getElementById('terminal-logging-enabled-btn');
    const currentState = btn?.dataset.state === 'on';
    const newState = !currentState;

    // Optimistically update UI
    setToggleState('terminal-logging-enabled-btn', newState);

    try {
        const response = await fetch('/api/logs/terminal/debug', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: newState })
        });
        const data = await response.json();

        if (!data.success) {
            // Revert on failure
            setToggleState('terminal-logging-enabled-btn', currentState);
            console.error('Failed to toggle terminal logging:', data.error);
        }
    } catch (error) {
        // Revert on error
        setToggleState('terminal-logging-enabled-btn', currentState);
        console.error('Failed to toggle terminal logging:', error);
    }
}

function renderProjectList() {
    const container = document.getElementById('project-list');
    if (currentProjects.length === 0) {
        container.innerHTML = '<p class="settings-description" style="margin-bottom: 0;">no projects configured. add one below.</p>';
        return;
    }

    container.innerHTML = currentProjects.map((project, index) => `
        <div class="project-item">
            <input type="text" class="project-name" placeholder="project_name"
                   value="${escapeHtml(project.name)}" onchange="updateProject(${index}, 'name', this.value)" onblur="scheduleSettingsAutoSave()">
            <input type="text" class="project-path" placeholder="/path/to/project"
                   value="${escapeHtml(project.path)}" onchange="updateProject(${index}, 'path', this.value)" onblur="scheduleSettingsAutoSave()">
            <button class="btn btn-danger" onclick="removeProject(${index}); scheduleSettingsAutoSave()">rm</button>
        </div>
    `).join('');
}

function addProject() {
    currentProjects.push({ name: '', path: '' });
    renderProjectList();
}

function updateProject(index, field, value) {
    currentProjects[index][field] = value;
}

function removeProject(index) {
    currentProjects.splice(index, 1);
    renderProjectList();
}

async function saveSettings() {
    const statusEl = document.getElementById('settings-status');

    // Filter out empty projects
    const validProjects = currentProjects.filter(p => p.name && p.path);

    const config = {
        // Projects
        projects: validProjects,

        // Dashboard settings
        scan_interval: parseInt(document.getElementById('scan-interval').value) || 2,

        // Session summarization
        idle_timeout_minutes: parseInt(document.getElementById('idle-timeout-minutes').value) || 60,

        // Brain reboot
        stale_threshold_hours: parseFloat(document.getElementById('stale-threshold-hours').value) || 4,

        // OpenRouter (nested)
        openrouter: {
            api_key: document.getElementById('openrouter-api-key').value || '',
            model: document.getElementById('openrouter-model').value || 'anthropic/claude-3-haiku',
            compression_interval: parseInt(document.getElementById('openrouter-compression-interval').value) || 300
        },

        // Headspace (nested)
        headspace: {
            enabled: getToggleState('headspace-enabled-btn'),
            history_enabled: getToggleState('headspace-history-btn')
        },

        // Priorities (nested)
        priorities: {
            enabled: getToggleState('priorities-enabled-btn'),
            polling_interval: parseInt(document.getElementById('priorities-polling-interval').value) || 60,
            model: document.getElementById('priorities-model').value || ''
        }
    };

    try {
        const result = await saveConfigAPI(config);

        if (result.success) {
            statusEl.className = 'settings-status success';
            statusEl.textContent = 'config written successfully';
            currentProjects = validProjects;
            renderProjectList();
        } else {
            statusEl.className = 'settings-status error';
            statusEl.textContent = 'error: ' + (result.error || 'unknown error');
        }
    } catch (error) {
        statusEl.className = 'settings-status error';
        statusEl.textContent = 'error: ' + error.message;
    }

    setTimeout(() => {
        statusEl.className = 'settings-status';
    }, 3000);
}

/* Toggle button state management for boolean settings */
function setToggleState(btnId, isOn) {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    if (isOn) {
        btn.textContent = 'ON';
        btn.classList.remove('off');
        btn.classList.add('on');
        btn.dataset.state = 'on';
    } else {
        btn.textContent = 'OFF';
        btn.classList.remove('on');
        btn.classList.add('off');
        btn.dataset.state = 'off';
    }
}

function getToggleState(btnId) {
    const btn = document.getElementById(btnId);
    return btn?.dataset.state === 'on';
}

function toggleSettingBoolean(btnId) {
    const btn = document.getElementById(btnId);
    const currentState = btn?.dataset.state === 'on';
    setToggleState(btnId, !currentState);
    // Auto-save after toggle
    scheduleSettingsAutoSave();
}

/* Password visibility toggle */
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;

    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = 'hide';
        btn.classList.add('revealed');
    } else {
        input.type = 'password';
        btn.textContent = 'show';
        btn.classList.remove('revealed');
    }
}

/* Reset working state */
async function resetWorkingState() {
    const btn = document.getElementById('reset-state-btn');
    const statusEl = document.getElementById('reset-status');

    // Disable button during operation
    btn.disabled = true;
    btn.textContent = 'resetting...';
    statusEl.textContent = '';

    try {
        const result = await resetWorkingStateAPI();

        if (result.success) {
            statusEl.textContent = 'reset complete';
            statusEl.style.color = 'var(--color-success)';

            // Clear the fingerprint so next fetch triggers a full re-render
            if (typeof lastFingerprint !== 'undefined') {
                lastFingerprint = null;
            }

            // Refresh the dashboard immediately
            if (typeof fetchSessions === 'function') {
                fetchSessions();
            }

            // Switch to dashboard tab to show the refreshed state
            if (typeof switchToTab === 'function') {
                switchToTab('dashboard');
            }

            // Clear status after delay
            setTimeout(() => {
                statusEl.textContent = '';
                statusEl.style.color = '';
            }, 2000);
        } else {
            statusEl.textContent = 'error: ' + (result.error || 'unknown');
            statusEl.style.color = 'var(--color-error)';
        }
    } catch (error) {
        statusEl.textContent = 'error: ' + error.message;
        statusEl.style.color = 'var(--color-error)';
    } finally {
        btn.disabled = false;
        btn.textContent = 'reset working state';
    }
}
