/* Main Initialization */

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize DOM cache
    initDOMCache();

    // Initialize tab navigation
    initTabNavigation();

    // Initialize panel event listeners
    initPanelEventListeners();

    // Load headspace
    loadHeadspace();

    // Initialize priorities
    initializePriorities();

    // Load notification status
    setTimeout(loadNotificationStatus, 100);

    // Initial session fetch and start polling
    fetchSessions();
    startPolling();
});
