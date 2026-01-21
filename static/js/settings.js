/* Settings Functions */

async function loadReadme() {
    try {
        const data = await fetchReadmeAPI();
        document.getElementById('readme-content').innerHTML = data.html;
    } catch (error) {
        console.error('Failed to load README:', error);
        document.getElementById('readme-content').innerHTML = '<p>// failed to load documentation</p>';
    }
}

async function loadSettings() {
    try {
        const config = await fetchConfigAPI();
        currentProjects = config.projects || [];
        renderProjectList();
        document.getElementById('scan-interval').value = config.scan_interval || 2;
        document.getElementById('focus-delay').value = config.iterm_focus_delay || 0.1;
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

function renderProjectList() {
    const container = document.getElementById('project-list');
    if (currentProjects.length === 0) {
        container.innerHTML = '<p class="settings-description" style="margin-bottom: 0;">no projects configured. add one below.</p>';
        return;
    }

    container.innerHTML = currentProjects.map((project, index) => `
        <div class="project-item">
            <input type="text" class="project-name" placeholder="project_name"
                   value="${escapeHtml(project.name)}" onchange="updateProject(${index}, 'name', this.value)">
            <input type="text" class="project-path" placeholder="/path/to/project"
                   value="${escapeHtml(project.path)}" onchange="updateProject(${index}, 'path', this.value)">
            <button class="btn btn-danger" onclick="removeProject(${index})">rm</button>
        </div>
    `).join('');
}

function addProject() {
    currentProjects.push({ name: '', path: '' });
    renderProjectList();
}

function updateProject(index, field, value) {
    currentProjects[index][field] = value;
}

function removeProject(index) {
    currentProjects.splice(index, 1);
    renderProjectList();
}

async function saveSettings() {
    const statusEl = document.getElementById('settings-status');

    // Filter out empty projects
    const validProjects = currentProjects.filter(p => p.name && p.path);

    const config = {
        projects: validProjects,
        scan_interval: parseInt(document.getElementById('scan-interval').value) || 2,
        iterm_focus_delay: parseFloat(document.getElementById('focus-delay').value) || 0.1
    };

    try {
        const result = await saveConfigAPI(config);

        if (result.success) {
            statusEl.className = 'settings-status success';
            statusEl.textContent = 'config written successfully';
            currentProjects = validProjects;
            renderProjectList();
        } else {
            statusEl.className = 'settings-status error';
            statusEl.textContent = 'error: ' + (result.error || 'unknown error');
        }
    } catch (error) {
        statusEl.className = 'settings-status error';
        statusEl.textContent = 'error: ' + error.message;
    }

    setTimeout(() => {
        statusEl.className = 'settings-status';
    }, 3000);
}
