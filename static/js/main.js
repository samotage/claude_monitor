/* Main Initialization */

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize DOM cache
    initDOMCache();

    // Initialize tab navigation
    initTabNavigation();

    // Initialize responsive navigation (overflow detection)
    initResponsiveNav();

    // Initialize panel event listeners
    initPanelEventListeners();

    // Load headspace
    loadHeadspace();

    // Initialize priorities
    initializePriorities();

    // Load notification status
    setTimeout(loadNotificationStatus, 100);

    // Initial hook status fetch
    if (typeof fetchHookStatus === 'function') {
        fetchHookStatus();
        // Refresh hook status periodically
        setInterval(fetchHookStatus, 10000);  // Every 10 seconds
    }

    // Initial session fetch and start polling
    fetchSessions();
    startPolling();
});
