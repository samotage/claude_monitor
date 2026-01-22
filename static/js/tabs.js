/* Tab Navigation Functions */

// Track if tabs have been initialized
let helpInitialized = false;
let loggingTabInitialized = false;

function initTabNavigation() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Update buttons
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update content
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(btn.dataset.tab + '-tab').classList.add('active');

            // Load tab-specific content
            if (btn.dataset.tab === 'help') {
                // Initialize help system on first visit
                if (!helpInitialized && typeof initHelp === 'function') {
                    initHelp();
                    helpInitialized = true;
                }
            } else if (btn.dataset.tab === 'config') {
                loadSettings();
            } else if (btn.dataset.tab === 'focus') {
                loadFocusTab();
            } else if (btn.dataset.tab === 'logging') {
                // Initialize logging panel on first visit
                if (!loggingTabInitialized && typeof initLogging === 'function') {
                    initLogging();
                    loggingTabInitialized = true;
                }
            }
        });
    });
}
