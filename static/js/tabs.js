/* Tab Navigation Functions */

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
            if (btn.dataset.tab === 'health') {
                loadReadme();
            } else if (btn.dataset.tab === 'settings') {
                loadSettings();
            }
        });
    });
}
