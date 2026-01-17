/**
 * Greyhound Racing Value Finder - Client-side JavaScript
 *
 * Handles dynamic interactions, auto-refresh, and UI enhancements.
 */

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Greyhound Racing Value Finder loaded');

    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Add countdown timers if needed
    updateCountdowns();
    setInterval(updateCountdowns, 60000); // Update every minute
});

/**
 * Update countdown timers on the page
 */
function updateCountdowns() {
    const countdownElements = document.querySelectorAll('[data-countdown]');

    countdownElements.forEach(function(element) {
        const targetTime = new Date(element.dataset.countdown);
        const now = new Date();
        const diff = targetTime - now;

        if (diff > 0) {
            const minutes = Math.floor(diff / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            element.textContent = `${minutes}m ${seconds}s`;
        } else {
            element.textContent = 'Started';
            element.classList.add('text-danger');
        }
    });
}

/**
 * Refresh data via AJAX (future enhancement)
 */
function refreshData() {
    console.log('Refreshing data...');
    // TODO: Implement AJAX refresh instead of full page reload
    // This would allow updating odds without full page refresh
}

/**
 * Highlight best odds in table (future enhancement)
 */
function highlightBestOdds() {
    const oddsTable = document.querySelector('.odds-table');
    if (!oddsTable) return;

    // Find highest odds in each row and highlight
    const rows = oddsTable.querySelectorAll('tbody tr');
    rows.forEach(function(row) {
        const oddsCells = row.querySelectorAll('.odds-cell');
        let maxOdds = 0;
        let maxCell = null;

        oddsCells.forEach(function(cell) {
            const oddsText = cell.querySelector('strong')?.textContent;
            if (oddsText) {
                const odds = parseFloat(oddsText);
                if (odds > maxOdds) {
                    maxOdds = odds;
                    maxCell = cell;
                }
            }
        });

        if (maxCell) {
            maxCell.classList.add('table-success');
        }
    });
}

/**
 * Show loading indicator
 */
function showLoading() {
    const loader = document.createElement('div');
    loader.className = 'loading';
    loader.id = 'page-loader';
    document.body.appendChild(loader);
}

/**
 * Hide loading indicator
 */
function hideLoading() {
    const loader = document.getElementById('page-loader');
    if (loader) {
        loader.remove();
    }
}
