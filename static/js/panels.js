/* Side Panel Functions - Context Panel and Reboot Panel */

// =============================================================================
// Context Panel Functions
// =============================================================================

async function openContextPanel(projectName, sessionPid) {
    const panel = document.getElementById('context-panel');
    const overlay = document.getElementById('context-panel-overlay');
    const content = document.getElementById('context-panel-content');
    const title = document.getElementById('context-panel-project-name');

    contextPanelSessionPid = sessionPid;
    title.textContent = projectName;
    content.innerHTML = '<div class="reboot-loading">Loading context...</div>';

    panel.classList.add('active');
    overlay.classList.add('active');

    try {
        const rebootData = await fetchRebootBriefingAPI(projectName);
        const priorityInfo = getSessionPriority(sessionPid);

        let html = '';

        // Priority section
        if (priorityInfo) {
            const level = priorityInfo.priority_score >= 70 ? 'High' :
                          priorityInfo.priority_score >= 40 ? 'Medium' : 'Low';
            html += `
                <div class="context-section">
                    <div class="context-section-header">
                        <span class="context-section-icon">\u2605</span>
                        <span>WHY RECOMMENDED</span>
                    </div>
                    <div class="context-section-content">
                        <div class="context-priority-display">
                            <span class="context-priority-score">${priorityInfo.priority_score}</span>
                            <span class="context-priority-level">${level} Priority</span>
                        </div>
                        <p class="context-rationale">${escapeHtml(priorityInfo.rationale || 'No rationale available')}</p>
                    </div>
                </div>
            `;
        }

        // Roadmap section
        if (rebootData.success && rebootData.briefing) {
            const briefing = rebootData.briefing;

            if (briefing.roadmap) {
                html += `
                    <div class="context-section">
                        <div class="context-section-header">
                            <span class="context-section-icon">\uD83D\uDDFA</span>
                            <span>ROADMAP</span>
                        </div>
                        <div class="context-section-content">
                `;

                if (briefing.roadmap.next_up) {
                    html += `
                        <div class="context-roadmap-item">
                            <div class="context-roadmap-title">Next: ${escapeHtml(briefing.roadmap.next_up.title || 'Untitled')}</div>
                            ${briefing.roadmap.next_up.why ? `<div class="context-roadmap-why">${escapeHtml(briefing.roadmap.next_up.why)}</div>` : ''}
                        </div>
                    `;
                }

                if (briefing.roadmap.upcoming && briefing.roadmap.upcoming.length > 0) {
                    html += '<div style="color: var(--text-muted); font-size: 0.75rem; margin-top: 8px;">Then:</div>';
                    briefing.roadmap.upcoming.slice(0, 2).forEach(item => {
                        html += `<div class="context-roadmap-item"><div class="context-roadmap-title">${escapeHtml(item.title || item)}</div></div>`;
                    });
                }

                html += '</div></div>';
            }

            // Current state
            if (briefing.current_state && briefing.current_state.summary) {
                html += `
                    <div class="context-section">
                        <div class="context-section-header">
                            <span class="context-section-icon">\uD83D\uDCCA</span>
                            <span>CURRENT STATE</span>
                        </div>
                        <div class="context-section-content">
                            <p class="context-state-summary">${escapeHtml(briefing.current_state.summary)}</p>
                        </div>
                    </div>
                `;
            }

            // Recent sessions
            if (briefing.recent_sessions && briefing.recent_sessions.length > 0) {
                html += `
                    <div class="context-section">
                        <div class="context-section-header">
                            <span class="context-section-icon">\uD83D\uDCDD</span>
                            <span>RECENT SESSIONS</span>
                        </div>
                        <div class="context-section-content">
                            <ul class="context-session-list">
                `;

                briefing.recent_sessions.slice(0, 5).forEach(session => {
                    const summary = session.summary || session.task || 'No summary';
                    const time = session.ended_at ? formatRelativeTime(session.ended_at) : '';
                    html += `
                        <li class="context-session-item">
                            ${time ? `<span class="context-session-time">${time}</span> ` : ''}
                            ${escapeHtml(summary)}
                        </li>
                    `;
                });

                html += '</ul></div></div>';
            }
        } else {
            html += `
                <div class="context-section">
                    <div class="context-empty-state">
                        No project data available.
                        <a href="#" onclick="event.stopPropagation(); openRebootPanel('${escapeHtml(projectName)}'); closeContextPanel();">View Headspace</a>
                    </div>
                </div>
            `;
        }

        content.innerHTML = html || '<div class="context-empty-state">No context available</div>';
    } catch (error) {
        console.error('Failed to load context:', error);
        content.innerHTML = '<div class="context-empty-state">Failed to load context</div>';
    }
}

function closeContextPanel() {
    const panel = document.getElementById('context-panel');
    const overlay = document.getElementById('context-panel-overlay');
    panel.classList.remove('active');
    overlay.classList.remove('active');
    contextPanelSessionPid = null;
}

function focusContextSession() {
    if (contextPanelSessionPid) {
        focusWindow(contextPanelSessionPid);
    }
}

// =============================================================================
// Brain Reboot Panel Functions
// =============================================================================

async function openRebootPanel(projectName) {
    const panel = document.getElementById('reboot-panel');
    const overlay = document.getElementById('reboot-panel-overlay');
    const content = document.getElementById('reboot-panel-content');
    const title = document.getElementById('reboot-panel-project-name');

    title.textContent = projectName;
    content.innerHTML = '<div class="reboot-loading">Loading briefing...</div>';

    panel.classList.add('active');
    overlay.classList.add('active');

    try {
        const data = await fetchRebootBriefingAPI(projectName);

        if (!data.success) {
            content.innerHTML = '<div class="reboot-empty-state">Failed to load briefing: ' + escapeHtml(data.error) + '</div>';
            return;
        }

        const briefing = data.briefing;
        let html = '';

        // Roadmap Section
        html += '<div class="reboot-section">';
        html += '<div class="reboot-section-header"><span class="reboot-section-icon">&#128205;</span> Where You\'re Going</div>';
        html += '<div class="reboot-section-content">';
        if (briefing.roadmap.focus) {
            html += '<p><span class="label">Focus:</span> <span class="value">' + escapeHtml(briefing.roadmap.focus) + '</span></p>';
            if (briefing.roadmap.why) {
                html += '<p><span class="label">Why:</span> ' + escapeHtml(briefing.roadmap.why) + '</p>';
            }
            if (briefing.roadmap.next_steps && briefing.roadmap.next_steps.length > 0) {
                html += '<p><span class="label">Next:</span> ' + escapeHtml(briefing.roadmap.next_steps[0]) + '</p>';
            }
        } else {
            html += '<div class="reboot-empty-state">No roadmap defined yet.<br><a href="#" onclick="event.preventDefault(); closeRebootPanel(); toggleRoadmap(\'' + projectName.toLowerCase().replace(/\s+/g, '-') + '\');">Define a roadmap</a></div>';
        }
        html += '</div></div>';

        // State Section
        html += '<div class="reboot-section">';
        html += '<div class="reboot-section-header"><span class="reboot-section-icon">&#128204;</span> Where You Are</div>';
        html += '<div class="reboot-section-content">';
        if (briefing.state.last_action || briefing.state.status) {
            if (briefing.state.last_session_time) {
                const hours = calculateStalenessHours(briefing.state.last_session_time);
                html += '<p><span class="label">Last session:</span> ' + formatStaleness(hours) + ' ago</p>';
            }
            if (briefing.state.status) {
                html += '<p><span class="label">Status:</span> ' + escapeHtml(briefing.state.status) + '</p>';
            }
            if (briefing.state.last_action) {
                html += '<p><span class="label">Last action:</span> ' + escapeHtml(briefing.state.last_action) + '</p>';
            }
        } else {
            html += '<div class="reboot-empty-state">No session activity recorded yet</div>';
        }
        html += '</div></div>';

        // Recent Sessions Section
        html += '<div class="reboot-section">';
        html += '<div class="reboot-section-header"><span class="reboot-section-icon">&#128336;</span> Recent Sessions</div>';
        html += '<div class="reboot-section-content">';
        if (briefing.recent && briefing.recent.length > 0) {
            html += '<ul>';
            briefing.recent.forEach(session => {
                let itemHtml = '<li>';
                itemHtml += '<span class="label">' + escapeHtml(session.date) + ':</span> ';
                itemHtml += escapeHtml(session.summary);
                if (session.files_count > 0) {
                    itemHtml += ' <span class="label">(' + session.files_count + ' files)</span>';
                }
                itemHtml += '</li>';
                html += itemHtml;
            });
            html += '</ul>';
        } else {
            html += '<div class="reboot-empty-state">No recent sessions</div>';
        }
        html += '</div></div>';

        // History Section
        html += '<div class="reboot-section">';
        html += '<div class="reboot-section-header"><span class="reboot-section-icon">&#128218;</span> Project History</div>';
        html += '<div class="reboot-section-content">';
        if (briefing.history.narrative) {
            html += '<p>' + escapeHtml(briefing.history.narrative) + '</p>';
        } else {
            html += '<div class="reboot-empty-state">No compressed history yet</div>';
        }
        html += '</div></div>';

        content.innerHTML = html;

    } catch (error) {
        content.innerHTML = '<div class="reboot-empty-state">Failed to load briefing: ' + escapeHtml(error.message) + '</div>';
    }
}

function closeRebootPanel() {
    const panel = document.getElementById('reboot-panel');
    const overlay = document.getElementById('reboot-panel-overlay');
    panel.classList.remove('active');
    overlay.classList.remove('active');
}

function initPanelEventListeners() {
    // Click outside to close reboot panel
    const rebootOverlay = document.getElementById('reboot-panel-overlay');
    if (rebootOverlay) {
        rebootOverlay.addEventListener('click', closeRebootPanel);
    }

    // Escape key to close panels
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeRebootPanel();
            closeContextPanel();
        }
    });
}
