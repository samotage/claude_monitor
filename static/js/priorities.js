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
        softTransitionPending = data.metadata?.soft_transition_pending || false;

        showPriorityUI();
        updateRecommendedNextPanel();
        updateSoftTransitionIndicator();

        // Re-render kanban if in priority mode to update badges
        if (sortMode === 'priority' && currentSessions) {
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
    stateEl.textContent = formatActivityState(topSession.activity_state);
    stateEl.className = 'recommended-next-state ' + topSession.activity_state;
    // Show activity summary if available, otherwise fall back to rationale
    rationaleEl.textContent = topSession.activity_summary || topSession.rationale || 'Top priority session';
}

function focusRecommendedSession() {
    if (!prioritiesData || !prioritiesData.priorities || prioritiesData.priorities.length === 0) {
        return;
    }
    const topSession = prioritiesData.priorities[0];
    if (topSession.session_id) {
        focusWindow(parseInt(topSession.session_id));
    }
}

function updateSoftTransitionIndicator() {
    const indicator = document.getElementById('soft-transition-indicator');
    if (softTransitionPending) {
        indicator.classList.add('visible');
    } else {
        indicator.classList.remove('visible');
    }
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
