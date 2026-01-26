/* API Functions - All fetch calls to the backend */

// ============================================================================
// Agent API (new terminology - replaces "sessions")
// ============================================================================

async function fetchAgentsAPI() {
    const response = await fetch('/api/agents');
    return await response.json();
}

async function fetchAgentAPI(agentId) {
    const response = await fetch(`/api/agents/${agentId}`);
    return await response.json();
}

async function focusAgentAPI(agentId) {
    const response = await fetch(`/api/agents/${agentId}/focus`, { method: 'POST' });
    return await response.json();
}

async function sendToAgentAPI(agentId, text, enter = true) {
    const response = await fetch(`/api/agents/${agentId}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, enter })
    });
    return await response.json();
}

async function fetchAgentContentAPI(agentId, lines = 100) {
    const response = await fetch(`/api/agents/${agentId}/content?lines=${lines}`);
    return await response.json();
}

// Legacy compatibility aliases
async function fetchSessionsAPI() {
    // Maps to new agent API but returns compatible format
    const data = await fetchAgentsAPI();
    // Transform agents to session-like format for backward compatibility
    return {
        sessions: (data.agents || []).map(agentToSessionFormat),
        projects: data.projects || []
    };
}

async function focusWindowAPI(pid) {
    // Legacy PID-based focus - try to find agent by terminal session
    const response = await fetch(`/api/focus/${pid}`, { method: 'POST' });
    return await response.json();
}

async function focusSessionAPI(sessionName) {
    // Legacy session name focus
    const response = await fetch(`/api/focus/session/${encodeURIComponent(sessionName)}`, { method: 'POST' });
    return await response.json();
}

/**
 * Transform agent object to legacy session format for backward compatibility.
 */
function agentToSessionFormat(agent) {
    const task = agent.current_task;
    const taskState = task?.state || 'idle';

    // Map new 5-state to legacy 3-state for backward compatibility
    const legacyStateMap = {
        'idle': 'idle',
        'commanded': 'processing',
        'processing': 'processing',
        'awaiting_input': 'input_needed',
        'complete': 'idle'
    };

    return {
        // Agent fields
        id: agent.id,
        project_name: agent.project_name,
        terminal_session_id: agent.terminal_session_id,
        session_name: agent.session_name,

        // Task state (new 5-state)
        task_state: taskState,

        // Legacy compatibility (3-state)
        activity_state: legacyStateMap[taskState] || 'idle',
        status: task ? 'active' : 'completed',

        // Task details
        current_task: task,
        priority_score: task?.priority_score,
        priority_rationale: task?.priority_rationale,

        // Legacy fields for compatibility
        uuid: agent.id,
        uuid_short: agent.id.slice(0, 8),
        pid: null,  // No longer relevant with WezTerm
        tmux_session: agent.session_name,
        session_type: 'wezterm',
        elapsed: formatElapsedTime(agent.created_at),
        started_at: agent.created_at
    };
}

/**
 * Format elapsed time from ISO timestamp.
 */
function formatElapsedTime(isoTimestamp) {
    if (!isoTimestamp) return '0m';
    try {
        const start = new Date(isoTimestamp);
        const now = new Date();
        const diffMs = now - start;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);

        if (diffHours > 0) {
            return `${diffHours}h ${diffMins % 60}m`;
        }
        return `${diffMins}m`;
    } catch (e) {
        return '0m';
    }
}

async function fetchNotificationStatusAPI() {
    const response = await fetch('/api/notifications');
    return await response.json();
}

async function toggleNotificationsAPI(enabled) {
    const response = await fetch('/api/notifications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: enabled })
    });
    return await response.json();
}

async function testNotificationAPI() {
    const response = await fetch('/api/notifications/test', { method: 'POST' });
    return await response.json();
}

async function fetchReadmeAPI() {
    const response = await fetch('/api/readme');
    return await response.json();
}

async function fetchConfigAPI() {
    const response = await fetch('/api/config');
    return await response.json();
}

async function saveConfigAPI(config) {
    const response = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });
    return await response.json();
}

async function fetchHeadspaceAPI() {
    const response = await fetch('/api/headspace');
    return await response.json();
}

async function saveHeadspaceAPI(data) {
    const response = await fetch('/api/headspace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    return await response.json();
}

async function fetchPrioritiesAPI(forceRefresh = false) {
    const url = forceRefresh ? '/api/priorities?refresh=true' : '/api/priorities';
    const response = await fetch(url);
    return response;
}

async function fetchBrainRefreshAPI(projectName, sessionId = null) {
    // Convert project name to permalink (slug)
    const permalink = projectName.toLowerCase().replace(/\s+/g, '-');
    let url = `/api/project/${permalink}/brain-refresh`;
    if (sessionId) {
        url += `?session_id=${encodeURIComponent(sessionId)}`;
    }
    const response = await fetch(url);
    return await response.json();
}

async function fetchRoadmapAPI(projectSlug) {
    const response = await fetch(`/api/project/${projectSlug}/roadmap`);
    return await response.json();
}

async function saveRoadmapAPI(projectSlug, roadmapData) {
    const response = await fetch(`/api/project/${projectSlug}/roadmap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(roadmapData)
    });
    return await response.json();
}

async function resetWorkingStateAPI() {
    const response = await fetch('/api/reset', { method: 'POST' });
    return await response.json();
}
