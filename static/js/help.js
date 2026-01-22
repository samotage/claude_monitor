/* Help Documentation System */

// State
let helpIndex = [];
let currentPage = null;
let searchTimeout = null;

// Initialize help system
async function initHelp() {
    await loadHelpIndex();
    
    // Load default page (index) or from URL hash
    const hash = window.location.hash.slice(1);
    const initialPage = hash.startsWith('help-') ? hash.slice(5) : 'index';
    await loadHelpPage(initialPage);
    
    // Set up search input
    const searchInput = document.getElementById('help-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounceSearch);
        searchInput.addEventListener('keydown', handleSearchKeydown);
    }
}

// Load help index (list of all pages)
async function loadHelpIndex() {
    try {
        const response = await fetch('/api/help');
        const data = await response.json();
        
        if (data.success) {
            helpIndex = data.pages;
            renderHelpNav();
        }
    } catch (error) {
        console.error('Failed to load help index:', error);
    }
}

// Render navigation sidebar
function renderHelpNav() {
    const nav = document.getElementById('help-nav');
    if (!nav) return;
    
    let html = '<ul class="help-nav-list">';
    for (const page of helpIndex) {
        const activeClass = currentPage === page.slug ? 'active' : '';
        html += `<li class="help-nav-item ${activeClass}">
            <a href="#help-${page.slug}" onclick="loadHelpPage('${page.slug}'); return false;">
                ${escapeHtml(page.title)}
            </a>
        </li>`;
    }
    html += '</ul>';
    nav.innerHTML = html;
}

// Load a specific help page
async function loadHelpPage(slug) {
    const content = document.getElementById('help-content');
    if (!content) return;
    
    content.innerHTML = '<div class="help-loading">Loading...</div>';
    
    try {
        const response = await fetch(`/api/help/${encodeURIComponent(slug)}`);
        const data = await response.json();
        
        if (data.success) {
            currentPage = slug;
            renderHelpContent(data.page);
            updateNavHighlight();
            
            // Update URL hash
            window.location.hash = `help-${slug}`;
            
            // Scroll to top of content
            content.scrollTop = 0;
        } else {
            content.innerHTML = `<div class="help-error">Page not found: ${escapeHtml(slug)}</div>`;
        }
    } catch (error) {
        console.error('Failed to load help page:', error);
        content.innerHTML = '<div class="help-error">Failed to load help page</div>';
    }
}

// Render help page content
function renderHelpContent(page) {
    const content = document.getElementById('help-content');
    if (!content) return;
    
    // The HTML comes pre-rendered from the server
    content.innerHTML = `
        <div class="help-page">
            <div class="help-page-content">
                ${page.html}
            </div>
        </div>
    `;
    
    // Initialize Mermaid diagrams if present
    if (typeof mermaid !== 'undefined') {
        initializeMermaidDiagrams();
    }
}

// Update navigation highlight
function updateNavHighlight() {
    const navItems = document.querySelectorAll('.help-nav-item');
    navItems.forEach(item => {
        const link = item.querySelector('a');
        if (link && link.getAttribute('href') === `#help-${currentPage}`) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// Search functionality
function debounceSearch(event) {
    const query = event.target.value;
    
    // Clear previous timeout
    if (searchTimeout) {
        clearTimeout(searchTimeout);
    }
    
    // Debounce search
    searchTimeout = setTimeout(() => {
        if (query.trim()) {
            searchHelp(query);
        } else {
            clearSearchResults();
        }
    }, 300);
}

// Handle search input keydown
function handleSearchKeydown(event) {
    if (event.key === 'Escape') {
        event.target.value = '';
        clearSearchResults();
    } else if (event.key === 'Enter') {
        // Navigate to first result
        const firstResult = document.querySelector('.help-search-result');
        if (firstResult) {
            const slug = firstResult.dataset.slug;
            if (slug) {
                loadHelpPage(slug);
                clearSearchResults();
                event.target.value = '';
            }
        }
    }
}

// Perform search
async function searchHelp(query) {
    try {
        const response = await fetch(`/api/help/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.success) {
            renderSearchResults(data.results, query);
        }
    } catch (error) {
        console.error('Search failed:', error);
    }
}

// Render search results
function renderSearchResults(results, query) {
    const container = document.getElementById('help-search-results');
    if (!container) return;
    
    if (results.length === 0) {
        container.innerHTML = '<div class="help-search-empty">No results found</div>';
        container.classList.add('active');
        return;
    }
    
    let html = '';
    for (const result of results.slice(0, 10)) { // Limit to 10 results
        html += `
            <div class="help-search-result" data-slug="${result.slug}" onclick="loadHelpPage('${result.slug}'); clearSearchResults(); document.getElementById('help-search').value = '';">
                <div class="help-search-result-title">${escapeHtml(result.title)}</div>
                <div class="help-search-result-snippet">${escapeHtml(result.snippet)}</div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    container.classList.add('active');
}

// Clear search results
function clearSearchResults() {
    const container = document.getElementById('help-search-results');
    if (container) {
        container.innerHTML = '';
        container.classList.remove('active');
    }
}

// Initialize Mermaid diagrams in help content
function initializeMermaidDiagrams() {
    const codeBlocks = document.querySelectorAll('#help-content pre code');
    
    codeBlocks.forEach((block, index) => {
        const text = block.textContent.trim();
        
        // Check if this is a mermaid diagram
        if (text.startsWith('graph ') || 
            text.startsWith('flowchart ') || 
            text.startsWith('sequenceDiagram') ||
            text.startsWith('classDiagram') ||
            text.startsWith('erDiagram') ||
            text.startsWith('gantt') ||
            text.startsWith('pie') ||
            text.startsWith('gitGraph')) {
            
            // Create a container for the diagram
            const container = document.createElement('div');
            container.className = 'mermaid';
            container.id = `mermaid-${index}`;
            container.textContent = text;
            
            // Replace the code block with the mermaid container
            const pre = block.parentElement;
            pre.parentElement.replaceChild(container, pre);
        }
    });
    
    // Re-run mermaid to render new diagrams
    if (typeof mermaid !== 'undefined') {
        mermaid.init(undefined, '.mermaid');
    }
}

// Escape HTML helper
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close search results when clicking outside
document.addEventListener('click', (event) => {
    const searchContainer = document.getElementById('help-search-container');
    if (searchContainer && !searchContainer.contains(event.target)) {
        clearSearchResults();
    }
});

// Handle hash changes for navigation
window.addEventListener('hashchange', () => {
    const hash = window.location.hash.slice(1);
    if (hash.startsWith('help-')) {
        const slug = hash.slice(5);
        if (slug !== currentPage) {
            loadHelpPage(slug);
        }
    }
});
