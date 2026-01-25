/* Session Polling Functions */

// Page Visibility API - pause polling when tab is hidden
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopPolling();
    } else {
        startPolling();
        fetchSessions(); // Immediate refresh when tab becomes visible
    }
});

function startPolling() {
    if (!pollingTimeoutId && !document.hidden) {
        isPollingActive = true;
        scheduleNextPoll();
    }
}

function stopPolling() {
    if (pollingTimeoutId) {
        clearTimeout(pollingTimeoutId);
        pollingTimeoutId = null;
        isPollingActive = false;
    }
}

function scheduleNextPoll() {
    pollingTimeoutId = setTimeout(() => {
        if (!document.hidden && isPollingActive) {
            fetchSessions().finally(scheduleNextPoll);
        }
    }, REFRESH_INTERVAL);
}

async function fetchSessions() {
    try {
        const data = await fetchSessionsAPI();

        // Check if anything actually changed before re-rendering
        const fingerprint = getSessionFingerprint(data.sessions);
        const hasChanges = fingerprint !== lastFingerprint;

        if (hasChanges) {
            // Check for blocking UI state (editing roadmap, panels open)
            if (hasBlockingUIState()) {
                // Skip full re-render to preserve UI state
                // Just update the global session data for when panels close
                currentSessions = data.sessions;
                currentProjects = data.projects;
                // Mark that a render was deferred - will trigger when blocking state ends
                renderDeferred = true;
            } else {
                // Capture UI state before re-render
                const uiState = captureUIState();

                // Full re-render
                renderKanban(data.sessions, data.projects);

                // Restore UI state (expanded roadmaps)
                restoreUIState(uiState);
            }
            lastFingerprint = fingerprint;
        }

        updateStats(data.sessions);
        updateRefreshIndicator();

        // Update Recommended Next panel with fresh session data
        // This ensures activity_state and hybrid summary stay in sync
        if (typeof updateRecommendedNextPanel === 'function') {
            updateRecommendedNextPanel();
        }

        // Check for state transitions that require fresh AI summaries
        // When processing → idle/input_needed, a turn completed - get new AI summary
        const shouldRefreshPriorities = detectStateTransitions(data.sessions);
        if (shouldRefreshPriorities && typeof fetchPriorities === 'function') {
            console.log('State transition detected - refreshing priorities for fresh AI summary');
            fetchPriorities(true);  // force refresh
        }
    } catch (error) {
        console.error('Failed to fetch sessions:', error);
    }
}

/**
 * Get a stable session identifier that matches backend tracking.
 * Priority: tmux_session > uuid > pid (fallback)
 * This ensures frontend and backend use the same keys for state tracking.
 */
function getStableSessionId(session) {
    return session.tmux_session || session.uuid || String(session.pid);
}

/**
 * Detect state transitions that require a priority refresh.
 * Returns true if any session transitioned from processing → idle/input_needed
 * (indicating a turn completed and we need fresh AI summary).
 */
function detectStateTransitions(sessions) {
    let needsRefresh = false;

    for (const session of sessions) {
        // Use stable session identifier that matches backend tracking
        const sessionId = getStableSessionId(session);
        const currentState = session.activity_state;
        const previousState = previousActivityStates[sessionId];

        // Turn completed: processing → idle or input_needed
        if (previousState === 'processing' && (currentState === 'idle' || currentState === 'input_needed')) {
            console.log(`Turn completed for session ${sessionId}: ${previousState} → ${currentState}`);
            needsRefresh = true;
        }

        // Update tracking
        previousActivityStates[sessionId] = currentState;
    }

    // Clean up sessions that no longer exist
    const currentSessionIds = new Set(sessions.map(s => getStableSessionId(s)));
    for (const sessionId of Object.keys(previousActivityStates)) {
        if (!currentSessionIds.has(sessionId)) {
            delete previousActivityStates[sessionId];
        }
    }

    return needsRefresh;
}

function updateStats(sessions) {
    const inputNeeded = sessions.filter(s => s.activity_state === 'input_needed').length;
    const working = sessions.filter(s => s.activity_state === 'processing').length;
    const idle = sessions.filter(s => s.activity_state === 'idle').length;

    // Only update DOM if values changed
    if (prevStats.inputNeeded !== inputNeeded) {
        inputNeededCountEl.textContent = inputNeeded;
        prevStats.inputNeeded = inputNeeded;
    }
    if (prevStats.working !== working) {
        workingCountEl.textContent = working;
        prevStats.working = working;
    }
    if (prevStats.idle !== idle) {
        idleCountEl.textContent = idle;
        prevStats.idle = idle;
    }

    // Update document title with input needed count for tab visibility
    if (inputNeeded > 0) {
        document.title = `(${inputNeeded}) INPUT NEEDED - Claude Headspace`;
    } else {
        document.title = 'Claude Headspace';
    }
}

function updateRefreshIndicator() {
    const now = new Date().toLocaleTimeString('en-US', { hour12: false });
    refreshIndicator.textContent = `last_sync: ${now}`;
    refreshIndicator.classList.add('active');

    // Clear previous timeout to avoid stacking
    if (indicatorTimeout) clearTimeout(indicatorTimeout);
    indicatorTimeout = setTimeout(() => refreshIndicator.classList.remove('active'), 500);
}
