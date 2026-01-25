/* Priority Dashboard Functions */

function schedulePriorityPoll() {
    if (priorityPollTimeoutId) {
        clearTimeout(priorityPollTimeoutId);
    }
    priorityPollTimeoutId = setTimeout(async () => {
        if (!document.hidden) {
            await fetchPriorities();
            schedulePriorityPoll();
        }
    }, PRIORITY_POLL_INTERVAL);
}

async function fetchPriorities(forceRefresh = false) {
    try {
        const response = await fetchPrioritiesAPI(forceRefresh);

        if (!response.ok) {
            if (response.status === 404) {
                prioritiesAvailable = false;
                hidePriorityUI();
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (data.success === false) {
            prioritiesAvailable = false;
            hidePriorityUI();
            console.log('Priorities unavailable:', data.error);
            return;
        }

        prioritiesData = data;
        prioritiesAvailable = true;

        showPriorityUI();
        updateRecommendedNextPanel();

        // Re-render kanban if in priority mode to update badges
        // But skip if user has blocking UI state (e.g., editing roadmap)
        if (sortMode === 'priority' && currentSessions && !hasBlockingUIState()) {
            renderKanban(currentSessions, currentProjects);
        }
    } catch (error) {
        console.error('Failed to fetch priorities:', error);
        prioritiesAvailable = false;
    }
}

function showPriorityUI() {
    document.getElementById('recommended-next-panel').style.display = 'block';
    document.getElementById('sort-toggle-container').style.display = 'flex';
}

function hidePriorityUI() {
    document.getElementById('recommended-next-panel').style.display = 'none';
    document.getElementById('sort-toggle-container').style.display = 'none';
}

function updateRecommendedNextPanel() {
    const panel = document.getElementById('recommended-next-panel');
    const content = panel.querySelector('.recommended-next-content');
    const emptyState = document.getElementById('recommended-next-empty');
    const scoreEl = document.getElementById('recommended-next-score');
    const uuidEl = document.getElementById('recommended-next-uuid');
    const nameEl = document.getElementById('recommended-next-name');
    const stateEl = document.getElementById('recommended-next-state');
    const rationaleEl = document.getElementById('recommended-next-rationale');

    if (!prioritiesData || !prioritiesData.priorities || prioritiesData.priorities.length === 0) {
        content.style.display = 'none';
        emptyState.style.display = 'block';
        scoreEl.style.display = 'none';
        return;
    }

    const topSession = prioritiesData.priorities[0];

    content.style.display = 'flex';
    emptyState.style.display = 'none';
    scoreEl.style.display = 'inline';

    scoreEl.textContent = topSession.priority_score;
    uuidEl.textContent = topSession.uuid_short || '';
    nameEl.textContent = topSession.project_name;

    // Find the matching session from currentSessions for FRESH data
    const sessionPid = topSession.session_id;
    const matchingSession = currentSessions?.find(s => String(s.pid) === String(sessionPid));

    // Use FRESH activity_state from currentSessions, not stale prioritiesData
    const freshActivityState = matchingSession?.activity_state || topSession.activity_state;
    stateEl.textContent = formatActivityState(freshActivityState);
    stateEl.className = 'recommended-next-state ' + freshActivityState;

    const lastMessage = matchingSession?.last_message || '';

    // Add tooltip with last message if available
    if (lastMessage) {
        stateEl.setAttribute('data-tooltip', escapeHtml(lastMessage));
        stateEl.classList.add('has-tooltip');
        stateEl.onclick = function(e) {
            e.stopPropagation();
            showTooltipPopup(this);
        };
    } else {
        stateEl.removeAttribute('data-tooltip');
        stateEl.classList.remove('has-tooltip');
        stateEl.onclick = null;
    }

    // Apply HYBRID SUMMARY logic - same as session cards
    // This ensures Recommended Next shows fresh/deterministic content, not stale AI
    const turnCommand = matchingSession?.turn_command || '';
    let summaryText;

    if (freshActivityState === 'processing') {
        // Deterministic: show user's command
        summaryText = turnCommand
            ? `Processing: ${turnCommand.length > 50 ? turnCommand.substring(0, 47) + '...' : turnCommand}`
            : 'Processing...';
    } else if (freshActivityState === 'input_needed') {
        summaryText = topSession.activity_summary || 'Waiting for input';
    } else {
        // Idle: prefer AI summary, then turn_command context, then rationale
        if (topSession.activity_summary) {
            summaryText = topSession.activity_summary;
        } else if (turnCommand) {
            summaryText = `Completed: ${turnCommand.length > 50 ? turnCommand.substring(0, 47) + '...' : turnCommand}`;
        } else {
            summaryText = topSession.rationale || 'Ready for task';
        }
    }

    rationaleEl.textContent = summaryText;
}

function focusRecommendedSession() {
    if (!prioritiesData || !prioritiesData.priorities || prioritiesData.priorities.length === 0) {
        return;
    }
    const topSession = prioritiesData.priorities[0];
    // Look up session name from currentSessions for WezTerm focus support
    const matchingSession = currentSessions?.find(s =>
        s.uuid_short === topSession.uuid_short || String(s.pid) === String(topSession.session_id)
    );
    const sessionName = matchingSession?.tmux_session || '';
    focusWindow(parseInt(topSession.session_id) || 0, sessionName);
}

function setSortMode(mode) {
    sortMode = mode;
    localStorage.setItem('sortMode', mode);
    updateSortToggleState();

    if (currentSessions) {
        renderKanban(currentSessions, currentProjects);
    }
}

function updateSortToggleState() {
    const projectBtn = document.getElementById('sort-by-project');
    const priorityBtn = document.getElementById('sort-by-priority');

    if (sortMode === 'project') {
        projectBtn.classList.add('active');
        priorityBtn.classList.remove('active');
    } else {
        projectBtn.classList.remove('active');
        priorityBtn.classList.add('active');
    }
}

function getSessionPriority(sessionPid) {
    if (!prioritiesData || !prioritiesData.priorities) return null;
    return prioritiesData.priorities.find(p =>
        String(p.session_id) === String(sessionPid)
    );
}

function getPriorityBadgeClass(score) {
    if (score >= 70) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
}

async function initializePriorities() {
    await fetchPriorities();
    schedulePriorityPoll();
    updateSortToggleState();
}
