/* Logging Panel Functions */

// Track initialization and state
let loggingInitialized = false;
let loggingPollingInterval = null;
let lastLogTimestamp = null;
let expandedEntries = new Set();
let allLogs = [];

/**
 * Initialize the logging panel
 */
function initLogging() {
    if (loggingInitialized) return;
    loggingInitialized = true;

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

    // Load initial logs
    loadOpenRouterLogs();

    // Start polling for new logs
    startLogPolling();
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

        allLogs = data.logs || [];
        renderLogs(allLogs);

        // Update last timestamp for polling
        if (allLogs.length > 0) {
            lastLogTimestamp = allLogs[0].timestamp;
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
 * Render a single log entry
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
                    <div class="log-entry-section-content">${escapeHtml(requestContent)}</div>
                </div>
                <div class="log-entry-section">
                    <div class="log-entry-section-label">Response</div>
                    <div class="log-entry-section-content">${escapeHtml(responseContent)}</div>
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
        renderLogs(allLogs);
        hideNoResults();
        return;
    }

    // Filter logs client-side
    const filtered = allLogs.filter(entry => {
        const searchableFields = [
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

        const combined = searchableFields.join(' ').toLowerCase();
        return combined.includes(query);
    });

    renderLogs(filtered);

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
 * Poll for new logs since last timestamp
 */
async function pollForNewLogs() {
    if (!lastLogTimestamp) {
        // No logs yet, do a full load
        await loadOpenRouterLogs();
        return;
    }

    try {
        const response = await fetch(`/api/logs/openrouter?since=${encodeURIComponent(lastLogTimestamp)}`);
        if (!response.ok) return;

        const data = await response.json();
        if (!data.success) return;

        const newLogs = data.logs || [];
        if (newLogs.length === 0) return;

        // Update last timestamp
        lastLogTimestamp = newLogs[0].timestamp;

        // Prepend new logs to allLogs
        allLogs = [...newLogs, ...allLogs];

        // Re-render with current search filter
        const searchInput = document.getElementById('logging-search');
        const query = searchInput ? searchInput.value.trim() : '';

        if (query) {
            searchLogs(query);
        } else {
            renderLogs(allLogs);
        }

    } catch (error) {
        console.error('Failed to poll for new logs:', error);
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

    // Reset timestamp to get full log list
    lastLogTimestamp = null;
    await loadOpenRouterLogs();

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

        // Format date and time
        const dateStr = date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });

        const time = date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        const datetime = `${dateStr} ${time}`;
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
 * Escape HTML to prevent XSS
 */
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
