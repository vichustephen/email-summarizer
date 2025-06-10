document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    const loadBtn = document.getElementById('load-btn');
    const summariesContainer = document.getElementById('summaries-container');

    // Set max date to yesterday and min date to 7 days ago
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    const weekAgo = new Date(yesterday);
    weekAgo.setDate(yesterday.getDate() - 6);

    startDateInput.max = yesterday.toISOString().split('T')[0];
    startDateInput.min = weekAgo.toISOString().split('T')[0];
    endDateInput.max = yesterday.toISOString().split('T')[0];
    endDateInput.min = weekAgo.toISOString().split('T')[0];

    // Set default values
    startDateInput.value = weekAgo.toISOString().split('T')[0];
    endDateInput.value = yesterday.toISOString().split('T')[0];

    // Function to create summary card HTML
    function createSummaryCardHTML(summary) {
        return `
            <div class="card shadow mb-4">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Summary for ${new Date(summary.date).toLocaleDateString()}</h4>
                </div>
                <div class="card-body">
                    <div class="row mb-4">
                        <div class="col">
                            <h5>Total Amount</h5>
                            <h3>${summary.total_amount.toFixed(2)}</h3>
                        </div>
                        <div class="col text-end">
                            <h5>Transactions</h5>
                            <h3>${summary.transaction_count}</h3>
                        </div>
                    </div>
                    <div class="summary-text">
                        <pre class="text-muted">${summary.summary_text}</pre>
                    </div>
                </div>
            </div>
        `;
    }

    // Function to load and display summaries
    async function loadSummaries() {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;

        if (!startDate || !endDate) {
            showToast('Please select both start and end dates', 'error');
            return;
        }

        if (new Date(startDate) > new Date(endDate)) {
            showToast('Start date must be before end date', 'error');
            return;
        }

        try {
            loadBtn.disabled = true;
            loadBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';

            const response = await fetch(`${API_URL}/summaries?start_date=${startDate}&end_date=${endDate}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch data');
            }

            const summaries = await response.json();

            // Display summaries
            summariesContainer.innerHTML = summaries.length > 0 
                ? summaries.map(createSummaryCardHTML).join('')
                : '<div class="alert alert-info">No summaries found for the selected date range.</div>';

        } catch (error) {
            console.error('Error:', error);
            showToast('Failed to load summaries. Please try again.', 'error');
            summariesContainer.innerHTML = '<div class="alert alert-danger">Error loading summaries. Please try again.</div>';
        } finally {
            loadBtn.disabled = false;
            loadBtn.innerHTML = '<i class="fas fa-search me-2"></i>Load Summaries';
        }
    }

    // Event listener for load button
    loadBtn.addEventListener('click', loadSummaries);

    // Load summaries on page load
    loadSummaries();
});
