/* Kanban Rendering Functions */

function renderKanban(sessions, projects) {
    const kanban = document.getElementById('kanban');

    // Store sessions globally for context panel
    currentSessions = sessions;

    // Helper to render a single session card
    function renderSessionCard(session, projectName) {
        const statusClass = session.status === 'active' ? 'active-session' : 'completed-session';
        const inputNeededClass = session.activity_state === 'input_needed' ? 'input-needed-card' : '';
        const lineNums = ['01', '02', '03', '04', '05'].join('<br>');

        const activityInfo = getActivityInfo(session.activity_state);

        // Calculate staleness from session data
        const lastActivity = session.started_at;
        const stalenessHours = calculateStalenessHours(lastActivity);
        const isStale = session.status !== 'active' && isProjectStale(lastActivity);
        const staleClass = isStale ? 'stale' : '';

        // Get priority badge
        const priorityInfo = getSessionPriority(session.pid);
        let priorityBadgeHtml = '';
        if (priorityInfo && prioritiesAvailable) {
            const badgeClass = getPriorityBadgeClass(priorityInfo.priority_score);
            priorityBadgeHtml = `<span class="priority-badge ${badgeClass}">${priorityInfo.priority_score}</span>`;
        }

        return `
            <div class="card ${statusClass} ${inputNeededClass} ${staleClass}" onclick="openContextPanel('${escapeHtml(projectName)}', ${session.pid || 0})" title="Click for details">
                ${priorityBadgeHtml}
                <div class="card-line-numbers">${lineNums}</div>
                <div class="card-content">
                    <div class="card-header">
                        <span class="uuid">${session.uuid_short}</span>
                        <span class="status ${session.status}">${session.status}</span>
                        <button class="reboot-btn" onclick="event.stopPropagation(); openRebootPanel('${escapeHtml(projectName)}')">Headspace</button>
                    </div>
                    <div class="activity-state ${session.activity_state}">
                        <span class="activity-icon">${activityInfo.icon}</span>
                        <span class="activity-label">${activityInfo.label}</span>
                    </div>
                    ${isStale ? `<div class="stale-indicator"><span class="stale-icon">&#128347;</span> Stale - ${formatStaleness(stalenessHours)}</div>` : ''}
                    <div class="task-summary">${escapeHtml(session.task_summary)}</div>
                    <div class="card-footer">
                        <span class="elapsed">${session.elapsed}</span>
                        ${session.pid ? `<span class="pid-info">${session.pid}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    let html = '';

    // Sort by priority mode: single column with all sessions sorted by priority
    if (sortMode === 'priority' && prioritiesAvailable && prioritiesData && prioritiesData.priorities) {
        // Create a map of session PIDs to their priority order
        const priorityOrder = {};
        prioritiesData.priorities.forEach((p, idx) => {
            priorityOrder[String(p.session_id)] = idx;
        });

        // Sort sessions by priority (sessions not in priorities list go to end)
        const sortedSessions = [...sessions].sort((a, b) => {
            const aIdx = priorityOrder[String(a.pid)] ?? 999;
            const bIdx = priorityOrder[String(b.pid)] ?? 999;
            return aIdx - bIdx;
        });

        html += `
            <div class="column" style="flex: 2; min-width: 400px;">
                <div class="column-header">
                    <div class="column-title">
                        <div class="window-dots">
                            <span class="window-dot red"></span>
                            <span class="window-dot yellow"></span>
                            <span class="window-dot green"></span>
                        </div>
                        <span class="column-name">All Sessions (By Priority)</span>
                    </div>
                    <span class="column-count">${sortedSessions.length} active</span>
                </div>
                <div class="column-body">
        `;

        sortedSessions.forEach(session => {
            html += renderSessionCard(session, session.project_name);
        });

        html += '</div></div>';
    } else {
        // Default: group by project
        const byProject = {};
        projects.forEach(p => {
            byProject[p.name] = [];
        });

        sessions.forEach(session => {
            const projectName = session.project_name;
            if (!byProject[projectName]) {
                byProject[projectName] = [];
            }
            byProject[projectName].push(session);
        });

        for (const [projectName, projectSessions] of Object.entries(byProject)) {
            if (projectSessions.length === 0) {
                continue;
            }

            const count = projectSessions.length;

            html += `
                <div class="column">
                    <div class="column-header">
                        <div class="column-title">
                            <div class="window-dots">
                                <span class="window-dot red"></span>
                                <span class="window-dot yellow"></span>
                                <span class="window-dot green"></span>
                            </div>
                            <span class="column-name">${escapeHtml(projectName)}</span>
                        </div>
                        <span class="column-count">${count} active</span>
                    </div>
                    <div class="column-body">
            `;

            projectSessions.forEach(session => {
                html += renderSessionCard(session, projectName);
            });

            // Add roadmap panel for this project
            const projectSlug = projectName.toLowerCase().replace(/\s+/g, '-');
            html += `
                <div class="roadmap-panel" id="roadmap-${projectSlug}" data-project="${escapeHtml(projectName)}">
                    <div class="roadmap-header" onclick="toggleRoadmap('${projectSlug}')">
                        <div class="roadmap-toggle">
                            <span class="roadmap-toggle-icon">\u25B6</span>
                            <span>Roadmap</span>
                        </div>
                        <div class="roadmap-actions">
                            <button class="roadmap-btn" onclick="event.stopPropagation(); editRoadmap('${projectSlug}')">Edit</button>
                        </div>
                    </div>
                    <div class="roadmap-content" id="roadmap-content-${projectSlug}">
                        <div class="roadmap-loading" id="roadmap-loading-${projectSlug}">Loading...</div>
                        <div id="roadmap-display-${projectSlug}"></div>
                        <div id="roadmap-edit-${projectSlug}" style="display: none;"></div>
                        <div class="roadmap-status" id="roadmap-status-${projectSlug}"></div>
                    </div>
                </div>
            `;

            html += '</div></div>';
        }
    }

    kanban.innerHTML = html || '<div class="no-sessions">no active sessions</div>';
}

async function focusWindow(pid) {
    if (!pid) {
        console.warn('No PID available for this session');
        return;
    }
    try {
        const data = await focusWindowAPI(pid);
        if (!data.success) {
            console.warn('Could not focus window');
        }
    } catch (error) {
        console.error('Failed to focus window:', error);
    }
}
