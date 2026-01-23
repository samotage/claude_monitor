/* API Functions - All fetch calls to the backend */

async function fetchSessionsAPI() {
    const response = await fetch('/api/sessions');
    return await response.json();
}

async function focusWindowAPI(pid) {
    const response = await fetch(`/api/focus/${pid}`, { method: 'POST' });
    return await response.json();
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
