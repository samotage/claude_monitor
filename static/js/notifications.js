/* macOS Notification Functions */

async function loadNotificationStatus() {
    try {
        const data = await fetchNotificationStatusAPI();
        notificationsEnabled = data.enabled;
        updateNotificationButton();
    } catch (error) {
        console.error('Failed to load notification status:', error);
    }
}

function updateNotificationButton() {
    const btn = document.getElementById('notification-toggle-btn');
    if (!btn) return;
    if (notificationsEnabled) {
        btn.textContent = 'ON';
        btn.style.background = 'var(--green)';
        btn.style.color = 'var(--bg-void)';
    } else {
        btn.textContent = 'OFF';
        btn.style.background = 'transparent';
        btn.style.color = 'var(--text-muted)';
        btn.style.border = '1px solid var(--border)';
    }
}

async function toggleNotifications() {
    try {
        const data = await toggleNotificationsAPI(!notificationsEnabled);
        notificationsEnabled = data.enabled;
        updateNotificationButton();
    } catch (error) {
        console.error('Failed to toggle notifications:', error);
    }
}

async function testMacNotification() {
    try {
        const data = await testNotificationAPI();
        if (!data.success) {
            alert('Failed to send notification');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
