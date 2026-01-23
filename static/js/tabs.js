/* Tab Navigation Functions */

// Track if tabs have been initialized
let helpInitialized = false;
let loggingTabInitialized = false;

/**
 * Check if the navigation tabs overflow and need hamburger menu
 * This runs on load and resize to dynamically show/hide the hamburger
 */
function checkNavOverflow() {
    const tabNav = document.querySelector('.tab-nav');
    const tabBtnGroup = document.querySelector('.tab-btn-group');
    const hamburgerBtn = document.querySelector('.hamburger-btn');
    const navBrand = document.querySelector('.nav-brand');
    
    if (!tabNav || !tabBtnGroup || !hamburgerBtn || !navBrand) return;
    
    // Temporarily force tab buttons visible to measure their width
    // This overrides both our JS classes AND the CSS media query
    tabBtnGroup.style.display = 'flex';
    
    // Remove all overflow classes temporarily for measurement
    tabBtnGroup.classList.remove('nav-overflow-hidden', 'nav-overflow-visible');
    hamburgerBtn.classList.remove('nav-overflow-hidden', 'nav-overflow-visible');
    
    // Force a reflow to get accurate measurements
    tabBtnGroup.offsetWidth;
    
    // Calculate available width and required width
    const navWidth = tabNav.offsetWidth;
    const brandWidth = navBrand.offsetWidth;
    const tabsWidth = tabBtnGroup.scrollWidth;
    const padding = 20; // Safety margin
    
    // Check if tabs fit
    const availableWidth = navWidth - brandWidth - padding;
    const tabsFit = tabsWidth <= availableWidth;
    
    // Clear inline style - let CSS classes control display
    tabBtnGroup.style.display = '';
    
    if (!tabsFit) {
        // Tabs don't fit - show hamburger, hide tabs
        tabBtnGroup.classList.add('nav-overflow-hidden');
        tabBtnGroup.classList.remove('nav-overflow-visible');
        hamburgerBtn.classList.add('nav-overflow-visible');
        hamburgerBtn.classList.remove('nav-overflow-hidden');
    } else {
        // Tabs fit - show tabs, hide hamburger
        tabBtnGroup.classList.add('nav-overflow-visible');
        tabBtnGroup.classList.remove('nav-overflow-hidden');
        hamburgerBtn.classList.add('nav-overflow-hidden');
        hamburgerBtn.classList.remove('nav-overflow-visible');
    }
}

/**
 * Initialize responsive navigation
 * Sets up resize listener and initial check
 */
function initResponsiveNav() {
    // Check on load
    checkNavOverflow();
    
    // Check on resize with debounce
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(checkNavOverflow, 100);
    });
}

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

/* Mobile Menu Functions */

/**
 * Toggle the mobile menu open/closed
 */
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    const overlay = document.getElementById('mobile-menu-overlay');
    const hamburger = document.querySelector('.hamburger-btn');

    if (menu && overlay && hamburger) {
        const isOpen = menu.classList.contains('active');
        if (isOpen) {
            closeMobileMenu();
        } else {
            menu.classList.add('active');
            overlay.classList.add('active');
            hamburger.classList.add('active');
            // Prevent body scroll when menu is open
            document.body.style.overflow = 'hidden';
        }
    }
}

/**
 * Close the mobile menu
 */
function closeMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    const overlay = document.getElementById('mobile-menu-overlay');
    const hamburger = document.querySelector('.hamburger-btn');

    if (menu) menu.classList.remove('active');
    if (overlay) overlay.classList.remove('active');
    if (hamburger) hamburger.classList.remove('active');
    // Restore body scroll
    document.body.style.overflow = '';
}

/**
 * Switch to a tab from the mobile menu
 * @param {string} tabName - The name of the tab to switch to
 */
function switchToTabMobile(tabName) {
    // Update desktop tab buttons
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const desktopBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
    if (desktopBtn) desktopBtn.classList.add('active');

    // Update mobile menu items
    document.querySelectorAll('.mobile-menu-item').forEach(b => b.classList.remove('active'));
    const mobileBtn = document.querySelector(`.mobile-menu-item[data-tab="${tabName}"]`);
    if (mobileBtn) mobileBtn.classList.add('active');

    // Update content
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const tabContent = document.getElementById(tabName + '-tab');
    if (tabContent) tabContent.classList.add('active');

    // Load tab-specific content
    if (tabName === 'help') {
        if (!helpInitialized && typeof initHelp === 'function') {
            initHelp();
            helpInitialized = true;
        }
    } else if (tabName === 'config') {
        loadSettings();
    } else if (tabName === 'focus') {
        loadFocusTab();
    } else if (tabName === 'logging') {
        if (!loggingTabInitialized && typeof initLogging === 'function') {
            initLogging();
            loggingTabInitialized = true;
        }
    }

    // Close the mobile menu
    closeMobileMenu();
}

/**
 * Programmatically switch to a tab (used by nav brand click)
 * @param {string} tabName - The name of the tab to switch to
 */
function switchToTab(tabName) {
    // Use mobile function as it handles both desktop and mobile
    switchToTabMobile(tabName);
}

// Close mobile menu on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeMobileMenu();
    }
});
