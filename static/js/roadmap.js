/* Roadmap Functions */

function scheduleRoadmapAutoSave(projectSlug) {
    if (roadmapSaveTimers[projectSlug]) {
        clearTimeout(roadmapSaveTimers[projectSlug]);
    }
    roadmapSaveTimers[projectSlug] = setTimeout(() => {
        saveRoadmapQuietly(projectSlug);
    }, 300);
}

async function saveRoadmapQuietly(projectSlug) {
    const statusEl = document.getElementById(`roadmap-status-${projectSlug}`);

    const titleEl = document.getElementById(`roadmap-edit-title-${projectSlug}`);
    if (!titleEl) return;

    const title = titleEl.value.trim();
    const why = document.getElementById(`roadmap-edit-why-${projectSlug}`)?.value.trim() || '';
    const dod = document.getElementById(`roadmap-edit-dod-${projectSlug}`)?.value.trim() || '';
    const upcomingText = document.getElementById(`roadmap-edit-upcoming-${projectSlug}`)?.value || '';
    const laterText = document.getElementById(`roadmap-edit-later-${projectSlug}`)?.value || '';
    const notNowText = document.getElementById(`roadmap-edit-notnow-${projectSlug}`)?.value || '';

    const parseList = (text) => text.split('\n').map(s => s.trim()).filter(s => s.length > 0);

    const roadmapData = {
        next_up: { title, why, definition_of_done: dod },
        upcoming: parseList(upcomingText),
        later: parseList(laterText),
        not_now: parseList(notNowText)
    };

    if (statusEl) {
        statusEl.className = 'roadmap-status saving';
        statusEl.textContent = 'Auto-saving...';
        statusEl.style.display = 'block';
    }

    try {
        const data = await saveRoadmapAPI(projectSlug, roadmapData);

        if (data.success) {
            roadmapCache[projectSlug] = data.data;

            if (statusEl) {
                statusEl.className = 'roadmap-status success';
                statusEl.textContent = 'Saved';
                setTimeout(() => {
                    if (statusEl.textContent === 'Saved') {
                        statusEl.style.display = 'none';
                    }
                }, 1500);
            }
        } else {
            if (statusEl) {
                statusEl.className = 'roadmap-status error';
                statusEl.textContent = `Error: ${data.error}`;
            }
        }
    } catch (error) {
        console.error('Auto-save failed:', error);
        if (statusEl) {
            statusEl.className = 'roadmap-status error';
            statusEl.textContent = 'Auto-save failed';
        }
    }
}

async function toggleRoadmap(projectSlug) {
    const panel = document.getElementById(`roadmap-${projectSlug}`);
    const isExpanded = panel.classList.contains('expanded');

    if (isExpanded) {
        panel.classList.remove('expanded');
    } else {
        panel.classList.add('expanded');
        if (!roadmapCache[projectSlug]) {
            await loadRoadmap(projectSlug);
        }
    }
}

async function loadRoadmap(projectSlug) {
    const loadingEl = document.getElementById(`roadmap-loading-${projectSlug}`);
    const displayEl = document.getElementById(`roadmap-display-${projectSlug}`);

    loadingEl.classList.add('active');

    try {
        const data = await fetchRoadmapAPI(projectSlug);

        if (data.success) {
            roadmapCache[projectSlug] = data.data;
            renderRoadmapDisplay(projectSlug, data.data);
        } else {
            displayEl.innerHTML = `<div class="roadmap-empty">Error: ${escapeHtml(data.error)}</div>`;
        }
    } catch (error) {
        displayEl.innerHTML = `<div class="roadmap-empty">Failed to load roadmap</div>`;
        console.error('Failed to load roadmap:', error);
    } finally {
        loadingEl.classList.remove('active');
    }
}

function renderRoadmapDisplay(projectSlug, roadmap) {
    const displayEl = document.getElementById(`roadmap-display-${projectSlug}`);
    const isEmpty = isRoadmapEmpty(roadmap);

    if (isEmpty) {
        displayEl.innerHTML = `
            <div class="roadmap-empty">
                No roadmap defined yet.<br>
                Click Edit to set project direction.
            </div>
        `;
        return;
    }

    let html = '';

    // Next Up section
    if (roadmap.next_up && (roadmap.next_up.title || roadmap.next_up.why || roadmap.next_up.definition_of_done)) {
        html += `
            <div class="roadmap-section">
                <div class="roadmap-section-title">Next Up</div>
                <div class="roadmap-next-up">
                    ${roadmap.next_up.title ? `<div class="roadmap-next-up-title">${escapeHtml(roadmap.next_up.title)}</div>` : ''}
                    ${roadmap.next_up.why ? `<div class="roadmap-next-up-why">${escapeHtml(roadmap.next_up.why)}</div>` : ''}
                    ${roadmap.next_up.definition_of_done ? `<div class="roadmap-next-up-dod">${escapeHtml(roadmap.next_up.definition_of_done)}</div>` : ''}
                </div>
            </div>
        `;
    }

    // List sections
    const listSections = [
        { key: 'upcoming', title: 'Upcoming' },
        { key: 'later', title: 'Later' },
        { key: 'not_now', title: 'Not Now' }
    ];

    for (const section of listSections) {
        const items = roadmap[section.key] || [];
        if (items.length > 0) {
            html += `
                <div class="roadmap-section">
                    <div class="roadmap-section-title">${section.title}</div>
                    <ul class="roadmap-list">
                        ${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
    }

    displayEl.innerHTML = html || '<div class="roadmap-empty">No roadmap content</div>';
}

function isRoadmapEmpty(roadmap) {
    const nextUp = roadmap.next_up || {};
    const hasNextUp = nextUp.title || nextUp.why || nextUp.definition_of_done;
    const hasUpcoming = (roadmap.upcoming || []).length > 0;
    const hasLater = (roadmap.later || []).length > 0;
    const hasNotNow = (roadmap.not_now || []).length > 0;

    return !hasNextUp && !hasUpcoming && !hasLater && !hasNotNow;
}

function editRoadmap(projectSlug) {
    const panel = document.getElementById(`roadmap-${projectSlug}`);
    const displayEl = document.getElementById(`roadmap-display-${projectSlug}`);
    const editEl = document.getElementById(`roadmap-edit-${projectSlug}`);

    if (!panel.classList.contains('expanded')) {
        panel.classList.add('expanded');
    }

    const roadmap = roadmapCache[projectSlug] || {
        next_up: { title: '', why: '', definition_of_done: '' },
        upcoming: [],
        later: [],
        not_now: []
    };

    roadmapEditMode[projectSlug] = true;
    displayEl.style.display = 'none';
    editEl.style.display = 'block';

    editEl.innerHTML = `
        <div class="roadmap-section">
            <div class="roadmap-section-title">Next Up</div>
            <div class="roadmap-field">
                <label>Title</label>
                <input type="text" id="roadmap-edit-title-${projectSlug}"
                       value="${escapeHtml(roadmap.next_up?.title || '')}"
                       placeholder="What's the immediate focus?"
                       onblur="scheduleRoadmapAutoSave('${projectSlug}')">
            </div>
            <div class="roadmap-field">
                <label>Why</label>
                <input type="text" id="roadmap-edit-why-${projectSlug}"
                       value="${escapeHtml(roadmap.next_up?.why || '')}"
                       placeholder="Why is this important?"
                       onblur="scheduleRoadmapAutoSave('${projectSlug}')">
            </div>
            <div class="roadmap-field">
                <label>Definition of Done</label>
                <input type="text" id="roadmap-edit-dod-${projectSlug}"
                       value="${escapeHtml(roadmap.next_up?.definition_of_done || '')}"
                       placeholder="When is this complete?"
                       onblur="scheduleRoadmapAutoSave('${projectSlug}')">
            </div>
        </div>

        <div class="roadmap-section">
            <div class="roadmap-section-title">Upcoming (one per line)</div>
            <div class="roadmap-field">
                <textarea id="roadmap-edit-upcoming-${projectSlug}"
                          placeholder="Near-term items..."
                          onblur="scheduleRoadmapAutoSave('${projectSlug}')">${escapeHtml((roadmap.upcoming || []).join('\n'))}</textarea>
            </div>
        </div>

        <div class="roadmap-section">
            <div class="roadmap-section-title">Later (one per line)</div>
            <div class="roadmap-field">
                <textarea id="roadmap-edit-later-${projectSlug}"
                          placeholder="Backlog items..."
                          onblur="scheduleRoadmapAutoSave('${projectSlug}')">${escapeHtml((roadmap.later || []).join('\n'))}</textarea>
            </div>
        </div>

        <div class="roadmap-section">
            <div class="roadmap-section-title">Not Now (one per line)</div>
            <div class="roadmap-field">
                <textarea id="roadmap-edit-notnow-${projectSlug}"
                          placeholder="Explicitly deferred..."
                          onblur="scheduleRoadmapAutoSave('${projectSlug}')">${escapeHtml((roadmap.not_now || []).join('\n'))}</textarea>
            </div>
        </div>

        <div class="roadmap-edit-actions">
            <button class="roadmap-btn" onclick="cancelRoadmapEdit('${projectSlug}')">Done</button>
        </div>
    `;
}

function cancelRoadmapEdit(projectSlug) {
    const displayEl = document.getElementById(`roadmap-display-${projectSlug}`);
    const editEl = document.getElementById(`roadmap-edit-${projectSlug}`);
    const statusEl = document.getElementById(`roadmap-status-${projectSlug}`);

    roadmapEditMode[projectSlug] = false;
    editEl.style.display = 'none';
    displayEl.style.display = 'block';
    statusEl.className = 'roadmap-status';
    statusEl.textContent = '';

    // Re-render display with updated cache data (fixes bug where auto-saved data wasn't displayed)
    if (roadmapCache[projectSlug]) {
        renderRoadmapDisplay(projectSlug, roadmapCache[projectSlug]);
    }

    // Clear any cached form values for this roadmap
    delete roadmapFormCache[projectSlug];

    // Trigger deferred render if blocking state has ended
    triggerDeferredRenderIfReady();
}

async function saveRoadmap(projectSlug) {
    const statusEl = document.getElementById(`roadmap-status-${projectSlug}`);

    const title = document.getElementById(`roadmap-edit-title-${projectSlug}`).value.trim();
    const why = document.getElementById(`roadmap-edit-why-${projectSlug}`).value.trim();
    const dod = document.getElementById(`roadmap-edit-dod-${projectSlug}`).value.trim();
    const upcomingText = document.getElementById(`roadmap-edit-upcoming-${projectSlug}`).value;
    const laterText = document.getElementById(`roadmap-edit-later-${projectSlug}`).value;
    const notNowText = document.getElementById(`roadmap-edit-notnow-${projectSlug}`).value;

    const parseList = (text) => text.split('\n').map(s => s.trim()).filter(s => s.length > 0);

    const roadmapData = {
        next_up: { title, why, definition_of_done: dod },
        upcoming: parseList(upcomingText),
        later: parseList(laterText),
        not_now: parseList(notNowText)
    };

    statusEl.className = 'roadmap-status';
    statusEl.textContent = 'Saving...';
    statusEl.style.display = 'block';

    try {
        const data = await saveRoadmapAPI(projectSlug, roadmapData);

        if (data.success) {
            roadmapCache[projectSlug] = data.data;
            statusEl.className = 'roadmap-status success';
            statusEl.textContent = 'Roadmap saved';

            setTimeout(() => {
                cancelRoadmapEdit(projectSlug);
                renderRoadmapDisplay(projectSlug, data.data);
            }, 1000);
        } else {
            statusEl.className = 'roadmap-status error';
            statusEl.textContent = `Error: ${data.error}`;
        }
    } catch (error) {
        statusEl.className = 'roadmap-status error';
        statusEl.textContent = 'Failed to save roadmap';
        console.error('Failed to save roadmap:', error);
    }
}
