/* Logging Panel Functions */

// Track initialization and state
let loggingInitialized = false;
let loggingPollingInterval = null;
let lastLogTimestamp = null;
let expandedEntries = new Set();
let allLogs = [];

// Tab state - 'openrouter' or 'terminal'
let activeLoggingTab = 'openrouter';

// Backend filter state for terminal logs - 'all', 'tmux', or 'wezterm'
let activeBackendFilter = 'all';

// Separate log storage for each tab
let openrouterLogs = [];
let terminalLogs = [];
let lastOpenrouterTimestamp = null;
let lastTerminalTimestamp = null;

/**
 * Initialize the logging panel
 */
function initLogging() {
    if (loggingInitialized) return;
    loggingInitialized = true;

    // Set up tab switching
    setupLoggingTabs();

    // Set up search input handler
    const searchInput = document.getElementById('logging-search');
    if (searchInput) {
        let debounceTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimeout);
            debounceTimeout = setTimeout(() => {
                searchLogs(this.value);
            }, 100);
        });
    }

    // Load initial logs for active tab
    loadLogsForActiveTab();

    // Start polling for new logs
    startLogPolling();
}

/**
 * Set up tab switching event handlers
 */
function setupLoggingTabs() {
    const tabButtons = document.querySelectorAll('.logging-subtab');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.getAttribute('data-subtab');
            switchLoggingTab(tabName);
        });
    });
}

/**
 * Switch between logging tabs (openrouter, terminal)
 */
function switchLoggingTab(tabName) {
    if (tabName === activeLoggingTab) return;

    activeLoggingTab = tabName;

    // Update tab button states
    const tabButtons = document.querySelectorAll('.logging-subtab');
    tabButtons.forEach(btn => {
        if (btn.getAttribute('data-subtab') === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Clear search input
    const searchInput = document.getElementById('logging-search');
    if (searchInput) {
        searchInput.value = '';
    }

    // Clear expanded entries (they don't carry across tabs)
    expandedEntries.clear();

    // Reset backend filter when switching tabs
    activeBackendFilter = 'all';
    updateBackendFilterButtons();

    // Show/hide terminal-specific controls
    updateTerminalControls();

    // Update empty state message
    updateEmptyStateMessage();

    // Load logs for the new tab
    loadLogsForActiveTab();
}

/**
 * Show/hide terminal-specific controls based on active tab
 */
function updateTerminalControls() {
    const backendFilter = document.getElementById('terminal-backend-filter');
    const clearLogsBtn = document.getElementById('terminal-clear-logs-btn');

    const showControls = activeLoggingTab === 'terminal';

    if (backendFilter) {
        backendFilter.style.display = showControls ? 'flex' : 'none';
    }
    if (clearLogsBtn) {
        clearLogsBtn.style.display = showControls ? 'flex' : 'none';
    }
}

/**
 * Update backend filter button states
 */
function updateBackendFilterButtons() {
    const filterButtons = document.querySelectorAll('.logging-filter-btn');
    filterButtons.forEach(btn => {
        if (btn.getAttribute('data-backend') === activeBackendFilter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

/**
 * Set the backend filter and reload logs
 */
function setBackendFilter(backend) {
    if (backend === activeBackendFilter) return;

    activeBackendFilter = backend;
    updateBackendFilterButtons();

    // Reload terminal logs with new filter
    loadTerminalLogs();
}

/**
 * Show the custom confirmation modal
 * @param {string} message - The message to display
 * @param {function} onConfirm - Callback when user confirms
 */
function showConfirmModal(message, onConfirm) {
    const overlay = document.getElementById('confirm-modal-overlay');
    const modal = document.getElementById('confirm-modal');
    const messageEl = document.getElementById('confirm-modal-message');
    const cancelBtn = document.getElementById('confirm-modal-cancel');
    const confirmBtn = document.getElementById('confirm-modal-confirm');

    if (!overlay || !modal || !messageEl || !cancelBtn || !confirmBtn) {
        // Fallback to native confirm if modal elements missing
        if (confirm(message)) {
            onConfirm();
        }
        return;
    }

    messageEl.textContent = message;

    // Show modal
    overlay.classList.add('active');
    modal.classList.add('active');

    // Clean up old listeners by cloning buttons
    const newCancelBtn = cancelBtn.cloneNode(true);
    const newConfirmBtn = confirmBtn.cloneNode(true);
    cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

    function closeModal() {
        overlay.classList.remove('active');
        modal.classList.remove('active');
    }

    // Cancel button
    newCancelBtn.addEventListener('click', closeModal);

    // Confirm button
    newConfirmBtn.addEventListener('click', () => {
        closeModal();
        onConfirm();
    });

    // Close on overlay click
    overlay.addEventListener('click', closeModal, { once: true });

    // Close on Escape key
    function handleEscape(e) {
        if (e.key === 'Escape') {
            closeModal();
            document.removeEventListener('keydown', handleEscape);
        }
    }
    document.addEventListener('keydown', handleEscape);
}

/**
 * Clear all terminal logs with confirmation
 */
function clearTerminalLogs() {
    showConfirmModal(
        'Are you sure you want to delete all terminal logs? This action cannot be undone.',
        async () => {
            try {
                const response = await fetch('/api/logs/terminal', {
                    method: 'DELETE'
                });

                const data = await response.json();

                if (data.success) {
                    // Reload to show empty state
                    terminalLogs = [];
                    allLogs = [];
                    renderTerminalLogs([]);
                } else {
                    console.error('Failed to clear logs:', data.error);
                    showErrorModal('Failed to clear logs: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Failed to clear logs:', error);
                showErrorModal('Failed to clear logs: ' + error.message);
            }
        }
    );
}

/**
 * Show an error message in a modal (replaces alert)
 */
function showErrorModal(message) {
    const overlay = document.getElementById('confirm-modal-overlay');
    const modal = document.getElementById('confirm-modal');
    const messageEl = document.getElementById('confirm-modal-message');
    const cancelBtn = document.getElementById('confirm-modal-cancel');
    const confirmBtn = document.getElementById('confirm-modal-confirm');
    const titleEl = modal.querySelector('.confirm-modal-title');

    if (!overlay || !modal) {
        alert(message);
        return;
    }

    // Update title and message for error
    if (titleEl) titleEl.textContent = 'Error';
    messageEl.textContent = message;

    // Hide cancel, change confirm to "OK"
    cancelBtn.style.display = 'none';
    confirmBtn.textContent = 'OK';
    confirmBtn.className = 'confirm-modal-btn confirm-modal-cancel'; // Use cancel style (not destructive)

    // Show modal
    overlay.classList.add('active');
    modal.classList.add('active');

    function closeModal() {
        overlay.classList.remove('active');
        modal.classList.remove('active');
        // Restore defaults
        if (titleEl) titleEl.textContent = 'Confirm Action';
        cancelBtn.style.display = '';
        confirmBtn.textContent = 'Delete';
        confirmBtn.className = 'confirm-modal-btn confirm-modal-confirm';
    }

    // Clone to remove old listeners
    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

    newConfirmBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', closeModal, { once: true });
}

/**
 * Update the empty state message based on active tab
 */
function updateEmptyStateMessage() {
    const emptyState = document.getElementById('logging-empty');
    if (!emptyState) return;

    if (activeLoggingTab === 'terminal') {
        emptyState.textContent = 'No terminal logs yet. Logs will appear here when terminal session operations occur.';
    } else {
        emptyState.textContent = 'No API logs yet. Logs will appear here when OpenRouter API calls are made.';
    }
}

/**
 * Load logs for the currently active tab
 */
function loadLogsForActiveTab() {
    if (activeLoggingTab === 'terminal') {
        loadTerminalLogs();
    } else {
        loadOpenRouterLogs();
    }
}

/**
 * Load OpenRouter logs from the API
 */
async function loadOpenRouterLogs() {
    const entriesContainer = document.getElementById('logging-entries');
    const emptyState = document.getElementById('logging-empty');
    const errorState = document.getElementById('logging-error');

    if (!entriesContainer) return;

    try {
        const response = await fetch('/api/logs/openrouter');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Unknown error');
        }

        openrouterLogs = data.logs || [];
        allLogs = openrouterLogs;
        renderLogs(allLogs);

        // Update last timestamp for polling
        if (openrouterLogs.length > 0) {
            lastOpenrouterTimestamp = openrouterLogs[0].timestamp;
            lastLogTimestamp = lastOpenrouterTimestamp;
        }

        // Hide error state
        if (errorState) {
            errorState.style.display = 'none';
        }

    } catch (error) {
        console.error('Failed to load logs:', error);
        if (errorState) {
            errorState.style.display = 'flex';
        }
        if (emptyState) {
            emptyState.style.display = 'none';
        }
    }
}

/**
 * Load terminal logs from the API
 */
async function loadTerminalLogs() {
    const entriesContainer = document.getElementById('logging-entries');
    const emptyState = document.getElementById('logging-empty');
    const errorState = document.getElementById('logging-error');

    if (!entriesContainer) return;

    try {
        // Build URL with optional backend filter
        let url = '/api/logs/terminal';
        if (activeBackendFilter !== 'all') {
            url += `?backend=${encodeURIComponent(activeBackendFilter)}`;
        }

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Unknown error');
        }

        terminalLogs = data.logs || [];
        allLogs = terminalLogs;
        renderTerminalLogs(allLogs);

        // Update last timestamp for polling
        if (terminalLogs.length > 0) {
            lastTerminalTimestamp = terminalLogs[0].timestamp;
            lastLogTimestamp = lastTerminalTimestamp;
        }

        // Hide error state
        if (errorState) {
            errorState.style.display = 'none';
        }

    } catch (error) {
        console.error('Failed to load terminal logs:', error);
        if (errorState) {
            errorState.style.display = 'flex';
        }
        if (emptyState) {
            emptyState.style.display = 'none';
        }
    }
}

/**
 * Render logs to the container
 */
function renderLogs(logs) {
    const entriesContainer = document.getElementById('logging-entries');
    const emptyState = document.getElementById('logging-empty');

    if (!entriesContainer) return;

    // Check for empty state
    if (logs.length === 0) {
        // Show empty state, hide entries
        if (emptyState) {
            emptyState.style.display = 'flex';
        }
        // Remove any existing log entries (but keep empty/error states)
        const existingEntries = entriesContainer.querySelectorAll('.log-entry');
        existingEntries.forEach(el => el.remove());
        return;
    }

    // Hide empty state
    if (emptyState) {
        emptyState.style.display = 'none';
    }

    // Render log entries
    const html = logs.map(entry => renderLogEntry(entry)).join('');

    // Remove existing entries and add new ones
    const existingEntries = entriesContainer.querySelectorAll('.log-entry');
    existingEntries.forEach(el => el.remove());

    // Insert entries after the empty/error states
    const noResultsEl = entriesContainer.querySelector('.logging-no-results');
    if (noResultsEl) {
        noResultsEl.insertAdjacentHTML('afterend', html);
    } else {
        entriesContainer.insertAdjacentHTML('beforeend', html);
    }

    // Restore expanded state
    expandedEntries.forEach(id => {
        const entry = document.querySelector(`.log-entry[data-id="${id}"]`);
        if (entry) {
            entry.classList.add('expanded');
        }
    });
}

/**
 * Render terminal logs to the container
 */
function renderTerminalLogs(logs) {
    const entriesContainer = document.getElementById('logging-entries');
    const emptyState = document.getElementById('logging-empty');

    if (!entriesContainer) return;

    // Check for empty state
    if (logs.length === 0) {
        // Show empty state, hide entries
        if (emptyState) {
            emptyState.style.display = 'flex';
        }
        // Remove any existing log entries (but keep empty/error states)
        const existingEntries = entriesContainer.querySelectorAll('.log-entry');
        existingEntries.forEach(el => el.remove());
        return;
    }

    // Hide empty state
    if (emptyState) {
        emptyState.style.display = 'none';
    }

    // Render log entries
    const html = logs.map(entry => renderTerminalLogEntry(entry)).join('');

    // Remove existing entries and add new ones
    const existingEntries = entriesContainer.querySelectorAll('.log-entry');
    existingEntries.forEach(el => el.remove());

    // Insert entries after the empty/error states
    const noResultsEl = entriesContainer.querySelector('.logging-no-results');
    if (noResultsEl) {
        noResultsEl.insertAdjacentHTML('afterend', html);
    } else {
        entriesContainer.insertAdjacentHTML('beforeend', html);
    }

    // Restore expanded state
    expandedEntries.forEach(id => {
        const entry = document.querySelector(`.log-entry[data-id="${id}"]`);
        if (entry) {
            entry.classList.add('expanded');
        }
    });
}

/**
 * Render a single terminal log entry
 */
function renderTerminalLogEntry(entry) {
    const isExpanded = expandedEntries.has(entry.id);
    const { datetime, ago } = formatTimestampWithAgo(entry.timestamp);
    const statusIcon = entry.success ? '✓' : '✗';
    const statusClass = entry.success ? 'success' : 'error';

    // Direction indicator
    const directionIcon = entry.direction === 'out' ? '→' : '←';
    const directionText = entry.direction === 'out' ? 'OUT' : 'IN';
    const directionClass = entry.direction === 'out' ? 'direction-out' : 'direction-in';

    // Session name (use tmux_session_name or session_id)
    const sessionName = entry.tmux_session_name || entry.session_id || 'unknown';

    // Backend indicator
    const backend = entry.backend || 'tmux';
    const backendClass = backend === 'wezterm' ? 'backend-wezterm' : 'backend-tmux';

    // Payload display - preserve newlines for human readability
    const hasPayload = entry.payload !== null && entry.payload !== undefined;
    const payloadContent = hasPayload ? entry.payload : '(payload logging disabled)';

    // Truncation notice
    const truncationNotice = entry.truncated
        ? `<div class="log-entry-truncation-notice">Truncated from ${formatBytes(entry.original_size)}</div>`
        : '';

    // Correlation ID section
    const correlationSection = entry.correlation_id
        ? `<div class="log-entry-meta-item">
               <span class="log-entry-meta-label">Correlation ID</span>
               <span class="log-entry-meta-value">${escapeHtml(entry.correlation_id)}</span>
           </div>`
        : '';

    // Backend section in expanded view
    const backendSection = `<div class="log-entry-meta-item">
           <span class="log-entry-meta-label">Backend</span>
           <span class="log-entry-meta-value">${escapeHtml(backend)}</span>
       </div>`;

    return `
        <div class="log-entry terminal-entry ${isExpanded ? 'expanded' : ''}" data-id="${entry.id}" onclick="toggleLogEntry('${entry.id}')">
            <div class="log-entry-header">
                <span class="log-entry-timestamp">
                    <span class="log-entry-timestamp-datetime">${datetime}</span>
                    <span class="log-entry-timestamp-ago">${ago}</span>
                </span>
                <span class="log-entry-backend ${backendClass}">${escapeHtml(backend)}</span>
                <span class="log-entry-context">
                    <span class="log-entry-context-event">${escapeHtml(entry.event_type)}</span>
                    <span class="log-entry-context-session">${escapeHtml(sessionName)}</span>
                </span>
                <span class="log-entry-direction ${directionClass}">
                    <span class="direction-icon">${directionIcon}</span>
                    <span class="direction-text">${directionText}</span>
                </span>
                <span class="log-entry-status">
                    <span class="log-entry-status-icon ${statusClass}">${statusIcon}</span>
                </span>
                <span class="log-entry-expand-icon">▼</span>
            </div>
            <div class="log-entry-body">
                ${backendSection}
                ${correlationSection}
                <div class="log-entry-section">
                    <div class="log-entry-section-label">Payload</div>
                    <div class="log-entry-section-content payload-content ${hasPayload ? '' : 'disabled'}">${escapeHtml(payloadContent)}</div>
                    ${truncationNotice}
                </div>
            </div>
        </div>
    `;
}

/**
 * Format bytes to human readable string
 */
function formatBytes(bytes) {
    if (bytes === null || bytes === undefined) return '--';
    if (bytes < 1024) return bytes + ' bytes';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Render a single log entry (OpenRouter)
 */
function renderLogEntry(entry) {
    const isExpanded = expandedEntries.has(entry.id);
    const { datetime, ago } = formatTimestampWithAgo(entry.timestamp);
    const statusIcon = entry.success ? '✓' : '✗';
    const statusText = entry.success ? 'Success' : 'Failed';
    const statusClass = entry.success ? 'success' : 'error';
    const cost = formatCost(entry.cost);
    const totalTokens = (entry.input_tokens || 0) + (entry.output_tokens || 0);

    // Format request messages for display
    const requestContent = entry.request_messages
        ? JSON.stringify(entry.request_messages, null, 2)
        : '(no request data)';

    // Format response content
    const responseContent = entry.response_content || '(no response)';

    // Error section (only if failed)
    const errorSection = !entry.success && entry.error
        ? `<div class="log-entry-section">
               <div class="log-entry-section-label">Error</div>
               <div class="log-entry-section-content error-content">${escapeHtml(entry.error)}</div>
           </div>`
        : '';

    return `
        <div class="log-entry ${isExpanded ? 'expanded' : ''}" data-id="${entry.id}" onclick="toggleLogEntry('${entry.id}')">
            <div class="log-entry-header">
                <span class="log-entry-timestamp">
                    <span class="log-entry-timestamp-datetime">${datetime}</span>
                    <span class="log-entry-timestamp-ago">${ago}</span>
                </span>
                <span class="log-entry-model">${escapeHtml(entry.model || 'unknown')}</span>
                <span class="log-entry-status">
                    <span class="log-entry-status-icon ${statusClass}">${statusIcon}</span>
                    <span class="log-entry-status-text ${statusClass}">${statusText}</span>
                </span>
                <span class="log-entry-cost">${cost}</span>
                <span class="log-entry-tokens">${totalTokens} tok</span>
                <span class="log-entry-expand-icon">▼</span>
            </div>
            <div class="log-entry-body">
                <div class="log-entry-section">
                    <div class="log-entry-section-label">Request</div>
                    <div class="log-entry-section-content json-content">${formatJsonForHtml(requestContent)}</div>
                </div>
                <div class="log-entry-section">
                    <div class="log-entry-section-label">Response</div>
                    <div class="log-entry-section-content json-content">${formatJsonForHtml(responseContent)}</div>
                </div>
                ${errorSection}
                <div class="log-entry-token-breakdown">
                    <div class="log-entry-token-item">
                        <span class="log-entry-token-label">Input</span>
                        <span class="log-entry-token-value">${entry.input_tokens || 0}</span>
                    </div>
                    <div class="log-entry-token-item">
                        <span class="log-entry-token-label">Output</span>
                        <span class="log-entry-token-value">${entry.output_tokens || 0}</span>
                    </div>
                    <div class="log-entry-token-item">
                        <span class="log-entry-token-label">Total</span>
                        <span class="log-entry-token-value">${totalTokens}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Toggle log entry expanded/collapsed state
 */
function toggleLogEntry(entryId) {
    const entry = document.querySelector(`.log-entry[data-id="${entryId}"]`);
    if (!entry) return;

    if (expandedEntries.has(entryId)) {
        expandedEntries.delete(entryId);
        entry.classList.remove('expanded');
    } else {
        expandedEntries.add(entryId);
        entry.classList.add('expanded');
    }
}

/**
 * Search/filter logs by query
 */
function searchLogs(query) {
    const entriesContainer = document.getElementById('logging-entries');
    if (!entriesContainer) return;

    query = query.trim().toLowerCase();

    if (!query) {
        // No query, show all logs
        if (activeLoggingTab === 'terminal') {
            renderTerminalLogs(allLogs);
        } else {
            renderLogs(allLogs);
        }
        hideNoResults();
        return;
    }

    // Filter logs client-side based on active tab
    const filtered = allLogs.filter(entry => {
        let searchableFields;

        if (activeLoggingTab === 'terminal') {
            // terminal log fields
            searchableFields = [
                entry.session_id || '',
                entry.tmux_session_name || '',
                entry.event_type || '',
                entry.payload || '',
                entry.correlation_id || '',
                entry.direction || '',
                entry.backend || '',
            ];
        } else {
            // OpenRouter log fields
            searchableFields = [
                entry.model || '',
                entry.response_content || '',
                entry.error || '',
                entry.caller || '',
            ];

            // Also search in request messages
            if (entry.request_messages) {
                entry.request_messages.forEach(msg => {
                    searchableFields.push(msg.content || '');
                });
            }
        }

        const combined = searchableFields.join(' ').toLowerCase();
        return combined.includes(query);
    });

    if (activeLoggingTab === 'terminal') {
        renderTerminalLogs(filtered);
    } else {
        renderLogs(filtered);
    }

    // Show "no results" if nothing matches
    if (filtered.length === 0 && allLogs.length > 0) {
        showNoResults(query);
    } else {
        hideNoResults();
    }
}

/**
 * Show "no results" message
 */
function showNoResults(query) {
    const entriesContainer = document.getElementById('logging-entries');
    let noResultsEl = entriesContainer.querySelector('.logging-no-results');

    if (!noResultsEl) {
        noResultsEl = document.createElement('div');
        noResultsEl.className = 'logging-no-results';
        entriesContainer.appendChild(noResultsEl);
    }

    noResultsEl.innerHTML = `No logs matching "${escapeHtml(query)}"`;
    noResultsEl.classList.add('visible');

    // Hide empty state
    const emptyState = document.getElementById('logging-empty');
    if (emptyState) {
        emptyState.style.display = 'none';
    }
}

/**
 * Hide "no results" message
 */
function hideNoResults() {
    const noResultsEl = document.querySelector('.logging-no-results');
    if (noResultsEl) {
        noResultsEl.classList.remove('visible');
    }
}

/**
 * Start polling for new log entries
 */
function startLogPolling() {
    // Clear any existing interval
    if (loggingPollingInterval) {
        clearInterval(loggingPollingInterval);
    }

    // Poll every 5 seconds
    const pollInterval = 5000;
    loggingPollingInterval = setInterval(pollForNewLogs, pollInterval);
}

/**
 * Poll for new logs since last timestamp (handles both tabs)
 */
async function pollForNewLogs() {
    // Poll for the active tab
    if (activeLoggingTab === 'terminal') {
        await pollForNewTerminalLogs();
    } else {
        await pollForNewOpenRouterLogs();
    }
}

/**
 * Poll for new OpenRouter logs
 */
async function pollForNewOpenRouterLogs() {
    if (!lastOpenrouterTimestamp) {
        await loadOpenRouterLogs();
        return;
    }

    try {
        const response = await fetch(`/api/logs/openrouter?since=${encodeURIComponent(lastOpenrouterTimestamp)}`);
        if (!response.ok) return;

        const data = await response.json();
        if (!data.success) return;

        const newLogs = data.logs || [];
        if (newLogs.length === 0) return;

        // Update last timestamp
        lastOpenrouterTimestamp = newLogs[0].timestamp;
        lastLogTimestamp = lastOpenrouterTimestamp;

        // Prepend new logs
        openrouterLogs = [...newLogs, ...openrouterLogs];
        allLogs = openrouterLogs;

        // Re-render with current search filter
        const searchInput = document.getElementById('logging-search');
        const query = searchInput ? searchInput.value.trim() : '';

        if (query) {
            searchLogs(query);
        } else {
            renderLogs(allLogs);
        }

    } catch (error) {
        console.error('Failed to poll for new OpenRouter logs:', error);
    }
}

/**
 * Poll for new terminal logs
 */
async function pollForNewTerminalLogs() {
    if (!lastTerminalTimestamp) {
        await loadTerminalLogs();
        return;
    }

    try {
        // Build URL with since timestamp and optional backend filter
        let url = `/api/logs/terminal?since=${encodeURIComponent(lastTerminalTimestamp)}`;
        if (activeBackendFilter !== 'all') {
            url += `&backend=${encodeURIComponent(activeBackendFilter)}`;
        }

        const response = await fetch(url);
        if (!response.ok) return;

        const data = await response.json();
        if (!data.success) return;

        const newLogs = data.logs || [];
        if (newLogs.length === 0) return;

        // Update last timestamp
        lastTerminalTimestamp = newLogs[0].timestamp;
        lastLogTimestamp = lastTerminalTimestamp;

        // Prepend new logs
        terminalLogs = [...newLogs, ...terminalLogs];
        allLogs = terminalLogs;

        // Re-render with current search filter
        const searchInput = document.getElementById('logging-search');
        const query = searchInput ? searchInput.value.trim() : '';

        if (query) {
            searchLogs(query);
        } else {
            renderTerminalLogs(allLogs);
        }

    } catch (error) {
        console.error('Failed to poll for new terminal logs:', error);
    }
}

/**
 * Stop polling for logs
 */
function stopLogPolling() {
    if (loggingPollingInterval) {
        clearInterval(loggingPollingInterval);
        loggingPollingInterval = null;
    }
}

/**
 * Open logging panel in a new tab (pop-out)
 */
function openLoggingPopout() {
    window.open('/logging', '_blank', 'width=900,height=700');
}

/**
 * Manually refresh logs (with visual feedback)
 */
async function refreshLogs() {
    const btn = document.querySelector('.logging-action-btn[onclick="refreshLogs()"]');
    if (btn) {
        btn.classList.add('refreshing');
    }

    // Reset timestamp to get full log list for active tab
    if (activeLoggingTab === 'terminal') {
        lastTerminalTimestamp = null;
        lastLogTimestamp = null;
        await loadTerminalLogs();
    } else {
        lastOpenrouterTimestamp = null;
        lastLogTimestamp = null;
        await loadOpenRouterLogs();
    }

    // Remove animation class after it completes
    setTimeout(() => {
        if (btn) {
            btn.classList.remove('refreshing');
        }
    }, 500);
}

/**
 * Format timestamp with date/time and "time ago"
 */
function formatTimestampWithAgo(isoTimestamp) {
    if (!isoTimestamp) return { datetime: '--', ago: '' };

    try {
        const date = new Date(isoTimestamp);

        // Format as DD.MM.YY HH:MM:SS
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = String(date.getFullYear()).slice(-2);
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');

        const datetime = `${day}.${month}.${year} ${hours}:${minutes}:${seconds}`;
        const ago = formatTimeAgo(date);

        return { datetime, ago };
    } catch (e) {
        return { datetime: isoTimestamp.slice(0, 19).replace('T', ' '), ago: '' };
    }
}

/**
 * Format a date as "time ago" in words
 */
function formatTimeAgo(date) {
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 0) return 'just now';
    if (seconds < 60) return seconds === 1 ? '1 second ago' : `${seconds} seconds ago`;

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes === 1 ? '1 minute ago' : `${minutes} minutes ago`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours === 1 ? '1 hour ago' : `${hours} hours ago`;

    const days = Math.floor(hours / 24);
    if (days < 7) return days === 1 ? '1 day ago' : `${days} days ago`;

    const weeks = Math.floor(days / 7);
    if (weeks < 4) return weeks === 1 ? '1 week ago' : `${weeks} weeks ago`;

    const months = Math.floor(days / 30);
    if (months < 12) return months === 1 ? '1 month ago' : `${months} months ago`;

    const years = Math.floor(days / 365);
    return years === 1 ? '1 year ago' : `${years} years ago`;
}

/**
 * Format timestamp for display (legacy, kept for compatibility)
 */
function formatTimestamp(isoTimestamp) {
    if (!isoTimestamp) return '--';

    try {
        const date = new Date(isoTimestamp);
        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();

        const time = date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        if (isToday) {
            return time;
        }

        const dateStr = date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric'
        });

        return `${dateStr} ${time}`;
    } catch (e) {
        return isoTimestamp.slice(0, 19).replace('T', ' ');
    }
}

/**
 * Format cost as currency
 */
function formatCost(cost) {
    if (cost === null || cost === undefined) return '--';
    if (cost === 0) return '$0.00';

    // Format small costs with more precision
    if (cost < 0.01) {
        return '$' + cost.toFixed(4);
    }

    return '$' + cost.toFixed(2);
}

/**
 * Format JSON string for HTML display, converting escaped sequences to actual characters
 * This processes the JSON string to make embedded JSON readable in content fields
 */
function formatJsonForHtml(jsonString) {
    if (!jsonString) return '';
    
    // Process BEFORE escaping HTML so we can match the JSON structure properly
    // Find content fields with escaped JSON and convert \\n to actual newlines
    let processed = jsonString.replace(/"content"\s*:\s*"((?:[^"\\]|\\.)*)"/g, function(match, content) {
        // Check if content contains JSON-like patterns (has { and escaped sequences)
        if (content.includes('{') && (content.includes('\\"') || /\\[ntr]/.test(content))) {
            // Convert escaped sequences to actual characters
            let processedContent = content
                .replace(/\\n/g, '\n')        // \n -> actual newline
                .replace(/\\t/g, '\t')        // \t -> actual tab
                .replace(/\\r/g, '\r')        // \r -> carriage return
                .replace(/\\"/g, '"');        // \" -> quote
            
            // Re-escape for JSON string format, but preserve newlines/tabs
            processedContent = processedContent
                .replace(/\\/g, '\\\\')       // Escape backslashes
                .replace(/"/g, '\\"');         // Escape quotes
            
            return '"content": "' + processedContent + '"';
        }
        return match;
    });
    
    // Now escape HTML to prevent XSS
    // The newlines/tabs will be preserved and displayed by pre-wrap CSS
    return escapeHtml(processed);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
