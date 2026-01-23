/* Kanban Rendering Functions */

function renderKanban(sessions, projects) {
    const kanban = document.getElementById('kanban');

    // Store sessions and projects globally
    currentSessions = sessions;
    currentProjects = projects;

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

        // Check if this is the recommended next session
        const isRecommendedNext = prioritiesAvailable && prioritiesData?.priorities?.[0]?.session_id === String(session.pid);
        const recommendedClass = isRecommendedNext ? 'recommended-next-card' : '';

        // Get priority info
        const priorityInfo = getSessionPriority(session.pid);
        let priorityHtml = '';
        if (priorityInfo && prioritiesAvailable) {
            const badgeClass = getPriorityBadgeClass(priorityInfo.priority_score);
            const rationale = priorityInfo.rationale ? escapeHtml(priorityInfo.rationale) : '';
            // Use last_message for detailed tooltip, fall back to rationale
            const lastMessage = session.last_message ? escapeHtml(session.last_message) : '';
            const tooltipContent = lastMessage || rationale;
            priorityHtml = `
                <div class="card-priority">
                    <span class="priority-score ${badgeClass}">${priorityInfo.priority_score}</span>
                    ${rationale ? `<span class="priority-rationale" data-tooltip="${tooltipContent}" onclick="event.stopPropagation(); showTooltipPopup(this)">// ${rationale}</span>` : ''}
                </div>
            `;
        }

        return `
            <div class="card ${statusClass} ${inputNeededClass} ${staleClass} ${recommendedClass}" onclick="openContextPanel('${escapeHtml(projectName)}', ${session.pid || 0}, '${escapeHtml(session.uuid)}')" title="Click for details">
                <div class="card-line-numbers">${lineNums}</div>
                <div class="card-content">
                    <div class="card-header">
                        <span class="status ${session.status}">${session.status}</span>
                        <span class="uuid">${session.uuid_short}</span>
                        <span class="elapsed">${session.elapsed}</span>
                        ${session.pid ? `<span class="pid-info">${session.pid}</span>` : ''}
                        <button class="reboot-btn" onclick="event.stopPropagation(); openRebootPanel('${escapeHtml(projectName)}', '${escapeHtml(session.uuid)}')">Headspace</button>
                    </div>
                    <div class="activity-state ${session.activity_state}" onclick="event.stopPropagation(); focusWindow(${session.pid || 0})" title="Click to focus ${session.session_type === 'tmux' ? 'tmux session' : 'iTerm window'}">
                        <span class="activity-icon">${activityInfo.icon}</span>
                        <span class="activity-label">${activityInfo.label}</span>
                        ${session.session_type === 'tmux' ? `<span class="tmux-badge ${session.tmux_attached ? 'attached' : 'detached'}" title="tmux: ${escapeHtml(session.tmux_session || '')}${session.tmux_attached ? ' (attached)' : ' (detached)'}">tmux</span>` : ''}
                    </div>
                    ${isStale ? `<div class="stale-indicator"><span class="stale-icon">&#128347;</span> Stale - ${formatStaleness(stalenessHours)}</div>` : ''}
                    ${priorityInfo && priorityInfo.activity_summary ?
                        `<div class="activity-summary">${escapeHtml(priorityInfo.activity_summary)}</div>` :
                        `<div class="task-summary">${escapeHtml(session.task_summary)}</div>`}
                    ${priorityHtml}
                </div>
            </div>
        `;
    }

    let html = '';

    // Always group by project - projects are always Kanban columns
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

    // Build priority order map for sorting within projects
    const priorityOrder = {};
    if (sortMode === 'priority' && prioritiesAvailable && prioritiesData && prioritiesData.priorities) {
        prioritiesData.priorities.forEach((p, idx) => {
            priorityOrder[String(p.session_id)] = idx;
        });
    }

    for (const [projectName, projectSessions] of Object.entries(byProject)) {
        if (projectSessions.length === 0) {
            continue;
        }

        // Sort sessions within this project based on sortMode
        let sortedProjectSessions;
        if (sortMode === 'priority' && prioritiesAvailable && Object.keys(priorityOrder).length > 0) {
            // Sort by Headspace-driven priority within this project
            sortedProjectSessions = [...projectSessions].sort((a, b) => {
                const aIdx = priorityOrder[String(a.pid)] ?? 999;
                const bIdx = priorityOrder[String(b.pid)] ?? 999;
                return aIdx - bIdx;
            });
        } else {
            // Default sort: by activity state (input_needed first, then processing, then idle)
            const stateOrder = { 'input_needed': 0, 'processing': 1, 'idle': 2 };
            sortedProjectSessions = [...projectSessions].sort((a, b) => {
                const aState = stateOrder[a.activity_state] ?? 3;
                const bState = stateOrder[b.activity_state] ?? 3;
                return aState - bState;
            });
        }

        const count = sortedProjectSessions.length;

        // Roadmap panel slug
        const projectSlug = projectName.toLowerCase().replace(/\s+/g, '-');

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

        sortedProjectSessions.forEach(session => {
            html += renderSessionCard(session, projectName);
        });

        html += '</div></div>';
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

/**
 * Show tooltip popup with content from a rationale element.
 * Works on both desktop (click) and mobile (tap).
 * @param {HTMLElement} element - The element with data-tooltip attribute
 */
function showTooltipPopup(element) {
    const tooltip = element.getAttribute('data-tooltip');
    if (!tooltip) return;

    const overlay = document.getElementById('tooltip-popup-overlay');
    const popup = document.getElementById('tooltip-popup');
    const content = document.getElementById('tooltip-popup-content');

    if (!overlay || !popup || !content) return;

    // Decode HTML entities and set content
    const decoded = tooltip.replace(/&amp;/g, '&')
                          .replace(/&lt;/g, '<')
                          .replace(/&gt;/g, '>')
                          .replace(/&quot;/g, '"')
                          .replace(/&#039;/g, "'")
                          .replace(/&#x27;/g, "'");
    content.textContent = decoded;

    // Position popup near the element on desktop, bottom of screen on mobile
    const isMobile = window.innerWidth <= 768;
    if (!isMobile) {
        const rect = element.getBoundingClientRect();
        const popupHeight = 200; // Estimate
        const spaceBelow = window.innerHeight - rect.bottom;
        const spaceAbove = rect.top;

        // Position horizontally centered on element, clamped to viewport
        let left = rect.left + (rect.width / 2) - 200; // 200 is half of max-width
        left = Math.max(20, Math.min(left, window.innerWidth - 420));

        // Position vertically: below if space, otherwise above
        let top;
        if (spaceBelow > popupHeight + 20) {
            top = rect.bottom + 10;
        } else if (spaceAbove > popupHeight + 20) {
            top = rect.top - popupHeight - 10;
        } else {
            top = Math.max(20, (window.innerHeight - popupHeight) / 2);
        }

        popup.style.left = `${left}px`;
        popup.style.top = `${top}px`;
        popup.style.right = 'auto';
        popup.style.bottom = 'auto';
    }

    // Show overlay and popup
    overlay.classList.add('active');
    popup.classList.add('active');
}

/**
 * Hide the tooltip popup.
 */
function hideTooltipPopup() {
    const overlay = document.getElementById('tooltip-popup-overlay');
    const popup = document.getElementById('tooltip-popup');

    if (overlay) overlay.classList.remove('active');
    if (popup) popup.classList.remove('active');
}

// Close tooltip on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        hideTooltipPopup();
    }
});
