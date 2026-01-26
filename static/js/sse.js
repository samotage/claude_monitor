/* Server-Sent Events client for real-time dashboard updates */

let eventSource = null;
let sseReconnectTimeout = null;
let sseConnected = false;

/**
 * Connect to the SSE endpoint for real-time updates.
 * Automatically reconnects on connection loss.
 */
function connectSSE() {
    // Clean up any existing connection
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    if (sseReconnectTimeout) {
        clearTimeout(sseReconnectTimeout);
        sseReconnectTimeout = null;
    }

    eventSource = new EventSource('/api/events');

    eventSource.onopen = function() {
        sseConnected = true;
        console.log('SSE connected');
    };

    eventSource.onmessage = function(event) {
        try {
            const message = JSON.parse(event.data);
            console.log('SSE event:', message.type, message.data);

            // Handle new agent-based events
            if (message.type === 'agent_created' ||
                message.type === 'agent_updated' ||
                message.type === 'agent_removed') {
                // Agent lifecycle event - refresh agent list
                if (typeof fetchSessions === 'function') {
                    fetchSessions();
                }
            } else if (message.type === 'task_state_changed') {
                // Task state transition - refresh and check for priority update
                if (typeof fetchSessions === 'function') {
                    fetchSessions();
                }
                // State change may affect priorities
                setTimeout(() => {
                    if (typeof fetchPriorities === 'function') {
                        fetchPriorities(true);
                    }
                }, 500);
            } else if (message.type === 'task_created') {
                // New task created - refresh
                if (typeof fetchSessions === 'function') {
                    fetchSessions();
                }
            } else if (message.type === 'headspace_changed') {
                // Headspace updated - refresh headspace display and priorities
                if (typeof loadHeadspace === 'function') {
                    loadHeadspace();
                }
                setTimeout(() => {
                    if (typeof fetchPriorities === 'function') {
                        fetchPriorities(true);
                    }
                }, 500);
            } else if (message.type === 'session_update') {
                // Legacy: Enter pressed in WezTerm - immediately fetch fresh session data
                // This bypasses the 2-second polling delay
                if (typeof fetchSessions === 'function') {
                    fetchSessions();
                }
            } else if (message.type === 'priorities_invalidated') {
                // Turn completed - fetch fresh priorities for Recommended Next panel
                // Small delay to allow server-side LLM call to complete
                setTimeout(() => {
                    if (typeof fetchPriorities === 'function') {
                        fetchPriorities(true);  // force refresh
                    }
                }, 500);
            } else if (message.type === 'hook_session_start' ||
                       message.type === 'hook_session_end' ||
                       message.type === 'hook_stop' ||
                       message.type === 'hook_user_prompt_submit' ||
                       message.type === 'hook_notification') {
                // Hook event received - update UI and mark as receiving
                if (typeof markHookEventReceived === 'function') {
                    markHookEventReceived();
                }
                // Refresh hook status
                if (typeof fetchHookStatus === 'function') {
                    fetchHookStatus();
                }
                // Refresh sessions on state-changing events
                if (message.type === 'hook_stop' || message.type === 'hook_user_prompt_submit') {
                    if (typeof fetchSessions === 'function') {
                        fetchSessions();
                    }
                }
            }
        } catch (e) {
            console.warn('SSE message parse error:', e);
        }
    };

    eventSource.onerror = function(error) {
        sseConnected = false;
        console.warn('SSE connection error, reconnecting in 5s...');
        eventSource.close();
        eventSource = null;

        // Reconnect after 5 seconds
        sseReconnectTimeout = setTimeout(connectSSE, 5000);
    };
}

/**
 * Disconnect from SSE and clean up resources.
 */
function disconnectSSE() {
    if (sseReconnectTimeout) {
        clearTimeout(sseReconnectTimeout);
        sseReconnectTimeout = null;
    }

    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    sseConnected = false;
}

/**
 * Check if SSE is currently connected.
 * @returns {boolean} True if connected
 */
function isSSEConnected() {
    return sseConnected;
}

// Connect on page load
document.addEventListener('DOMContentLoaded', connectSSE);

// Disconnect on page unload to clean up server resources
window.addEventListener('beforeunload', disconnectSSE);

// Reconnect when page becomes visible again (handles tab switching)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Page hidden - disconnect to save server resources
        disconnectSSE();
    } else {
        // Page visible - reconnect
        connectSSE();
    }
});
