/* Global Configuration and State */

// Refresh interval comes from window.CONFIG set by inline Jinja template
const REFRESH_INTERVAL = window.CONFIG?.refreshInterval || 2000;

// Global state
let currentProjects = [];
let pollingTimeoutId = null;
let isPollingActive = true;
let lastFetchTime = 0;
let currentSessions = null;

// Priority dashboard state
let prioritiesData = null;
let prioritiesAvailable = false;
let sortMode = localStorage.getItem('sortMode') || 'priority';
let contextPanelSessionPid = null;

// Priority polling interval (separate from session polling)
const PRIORITY_POLL_INTERVAL = 60000; // 60 seconds
let priorityPollTimeoutId = null;

// Notification state
let notificationsEnabled = true;

// Headspace state
let currentHeadspace = null;

// Roadmap state
const roadmapCache = {};
const roadmapEditMode = {};
const roadmapSaveTimers = {};
const roadmapExpandedState = {};  // Track expanded roadmaps
const roadmapFormCache = {};  // Cache in-progress form values to survive re-renders

// Kanban fingerprint for change detection
let lastFingerprint = '';

// Flag to track if a render was deferred due to blocking UI state
let renderDeferred = false;

// Track previous activity states per session for transition detection
// When processing → idle/input_needed, we need fresh AI summaries
let previousActivityStates = {};

// Cache DOM element references
let inputNeededCountEl;
let workingCountEl;
let idleCountEl;
let refreshIndicator;
let indicatorTimeout = null;
let prevStats = { inputNeeded: -1, working: -1, idle: -1 };

// Initialize DOM cache on load
function initDOMCache() {
    inputNeededCountEl = document.getElementById('input-needed-count');
    workingCountEl = document.getElementById('working-count');
    idleCountEl = document.getElementById('idle-count');
    refreshIndicator = document.getElementById('refresh-indicator');
}
