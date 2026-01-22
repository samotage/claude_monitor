/* Utility Functions */

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatRelativeTime(dateString) {
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    } catch (e) {
        return '';
    }
}

function formatHeadspaceTimestamp(isoTimestamp) {
    if (!isoTimestamp) return '';
    try {
        const date = new Date(isoTimestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffMins < 1) return 'Updated just now';
        if (diffMins < 60) return 'Updated ' + diffMins + ' minute' + (diffMins !== 1 ? 's' : '') + ' ago';
        if (diffHours < 24) return 'Updated ' + diffHours + ' hour' + (diffHours !== 1 ? 's' : '') + ' ago';
        if (diffDays < 7) return 'Updated ' + diffDays + ' day' + (diffDays !== 1 ? 's' : '') + ' ago';
        return 'Updated on ' + date.toLocaleDateString();
    } catch (e) {
        return '';
    }
}

function calculateStalenessHours(lastActivity) {
    if (!lastActivity) return null;
    try {
        const lastTime = new Date(lastActivity);
        const now = new Date();
        const diffMs = now - lastTime;
        return Math.round(diffMs / (1000 * 60 * 60) * 10) / 10;
    } catch (e) {
        return null;
    }
}

function isProjectStale(lastActivity, thresholdHours = 4) {
    const hours = calculateStalenessHours(lastActivity);
    return hours !== null && hours >= thresholdHours;
}

function formatStaleness(hours) {
    if (hours === null) return '';
    if (hours < 1) return 'less than 1 hour';
    if (hours < 24) return Math.round(hours) + ' hour' + (Math.round(hours) !== 1 ? 's' : '');
    const days = Math.round(hours / 24);
    return days + ' day' + (days !== 1 ? 's' : '');
}

function formatActivityState(state) {
    const states = {
        'processing': 'processing',
        'input_needed': 'input needed',
        'idle': 'idle',
        'completed': 'completed'
    };
    return states[state] || state;
}

function getActivityInfo(state) {
    const states = {
        'processing': {
            icon: '\u2699',
            label: "Claude's turn - working..."
        },
        'input_needed': {
            icon: '\uD83D\uDD14',
            label: 'INPUT NEEDED!'
        },
        'idle': {
            icon: '\uD83D\uDCA4',
            label: 'Idle - ready for task'
        },
        'completed': {
            icon: '\u2713',
            label: 'Session ended'
        },
        'unknown': {
            icon: '?',
            label: 'Unknown state'
        }
    };
    return states[state] || states['unknown'];
}

function getSessionFingerprint(sessions) {
    return sessions.map(s => `${s.uuid}:${s.activity_state}:${s.status}:${s.elapsed}`).join('|');
}

/**
 * Check if any blocking UI state is active that should prevent full kanban re-render.
 * Returns true if roadmap editing, side panels open, etc.
 */
function hasBlockingUIState() {
    // Check if any roadmap is in edit mode
    for (const slug in roadmapEditMode) {
        if (roadmapEditMode[slug]) return true;
    }

    // Check if Headspace panel is open
    const rebootPanel = document.getElementById('reboot-panel');
    if (rebootPanel && rebootPanel.classList.contains('active')) return true;

    // Check if Context panel is open
    const contextPanel = document.getElementById('context-panel');
    if (contextPanel && contextPanel.classList.contains('active')) return true;

    return false;
}

/**
 * Get current UI state to preserve during targeted updates.
 */
function captureUIState() {
    const state = {
        expandedRoadmaps: [],
        editingRoadmaps: []
    };

    // Capture expanded roadmaps
    document.querySelectorAll('.roadmap-panel.expanded').forEach(panel => {
        const slug = panel.id.replace('roadmap-', '');
        state.expandedRoadmaps.push(slug);
    });

    // Capture editing roadmaps
    for (const slug in roadmapEditMode) {
        if (roadmapEditMode[slug]) {
            state.editingRoadmaps.push(slug);
        }
    }

    return state;
}

/**
 * Restore UI state after kanban re-render.
 */
function restoreUIState(state) {
    // Restore expanded roadmaps
    state.expandedRoadmaps.forEach(slug => {
        const panel = document.getElementById(`roadmap-${slug}`);
        if (panel) {
            panel.classList.add('expanded');
            // Re-render the roadmap content from cache
            if (roadmapCache[slug]) {
                renderRoadmapDisplay(slug, roadmapCache[slug]);
            }
        }
    });
}
