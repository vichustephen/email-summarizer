// DOM Elements
const statusBadge = document.getElementById('status-badge');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const intervalInput = document.getElementById('interval-input');
const setIntervalBtn = document.getElementById('set-interval-btn');
const lastRunSpan = document.getElementById('last-run');
const nextRunSpan = document.getElementById('next-run');
const startDateInput = document.getElementById('start-date');
const endDateInput = document.getElementById('end-date');
const processBtn = document.getElementById('process-btn');
const notifyCheckbox = document.getElementById('notify-checkbox');

// Processing status elements
const processingMessage = document.getElementById('processing-message');
const emailCount = document.getElementById('email-count');
const processingProgress = document.getElementById('processing-progress');

// Set max date to yesterday and min date to 7 days ago
const today = new Date();
const yesterday = new Date(today);
yesterday.setDate(today.getDate());
const weekAgo = new Date(yesterday);
weekAgo.setDate(yesterday.getDate() - 6);

startDateInput.max = yesterday.toISOString().split('T')[0];
startDateInput.min = weekAgo.toISOString().split('T')[0];
endDateInput.max = yesterday.toISOString().split('T')[0];
endDateInput.min = weekAgo.toISOString().split('T')[0];

// Set default values
startDateInput.value = weekAgo.toISOString().split('T')[0];
endDateInput.value = yesterday.toISOString().split('T')[0];

// WebSocket status updates
function updateStatus(status) {
    const isRunning = status.is_running;
    
    // Update badge
    statusBadge.className = `badge rounded-pill text-bg-${isRunning ? 'success' : 'secondary'} status-badge`;
    statusBadge.textContent = isRunning ? 'Running' : 'Stopped';
    
    // Update buttons
    startBtn.disabled = isRunning;
    stopBtn.disabled = !isRunning;
    
    // Update timestamps
    lastRunSpan.textContent = formatDateTime(status.last_run);
    nextRunSpan.textContent = formatDateTime(status.next_run);
    
    // Update processing status
    if (status.current_batch) {
        const batch = status.current_batch;
        processingMessage.textContent = batch.processing_message;
        emailCount.textContent = `${batch.processed}/${batch.total_emails}`;
        
        // Calculate progress percentage
        const progress = batch.total_emails > 0 
            ? Math.round((batch.processed / batch.total_emails) * 100) 
            : 0;
       
        if (batch.processed === batch.total_emails && batch.current_email !== null && batch.current_email !== '') {
            showToast('Processing complete! Check your email or history tab.');
        }
        processingProgress.style.width = `${progress}%`;
        processingProgress.setAttribute('aria-valuenow', progress);
    }
}

// API Calls
async function startSummarizer() {
    toggleButtonLoading(startBtn, true, 'Starting...');
    try {
        const response = await fetch(`${API_URL}/start`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to start summarizer');
        showToast('Summarizer started successfully');
    } catch (error) {
        showToast(error.message, 'danger');
    } finally {
        toggleButtonLoading(startBtn, false);
    }
}

async function stopSummarizer() {
    toggleButtonLoading(stopBtn, true, 'Stopping...');
    try {
        const response = await fetch(`${API_URL}/stop`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to stop summarizer');
        showToast('Summarizer stopped successfully');
    } catch (error) {
        showToast(error.message, 'danger');
    } finally {
        toggleButtonLoading(stopBtn, false);
    }
}

async function setInterval() {
    const minutes = parseInt(intervalInput.value);
    if (isNaN(minutes) || minutes < 5 || minutes > 1440) {
        showToast('Please enter a valid interval between 5 and 1440 minutes', 'warning');
        return;
    }
    toggleButtonLoading(setIntervalBtn, true, 'Saving...');
    
    try {
        const response = await fetch(`${API_URL}/configure`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ interval_minutes: minutes }),
        });
        
        if (!response.ok) throw new Error('Failed to configure interval');
        showToast(`Interval set to ${minutes} minutes`);
    } catch (error) {
        showToast(error.message, 'danger');
    } finally {
        toggleButtonLoading(setIntervalBtn, false);
    }
}

// Fetch and set notification preference on load
async function fetchNotificationPreference() {
    try {
        const response = await fetch(`${API_URL}/notification-preference`);
        if (response.ok) {
            const data = await response.json();
            notifyCheckbox.checked = !!data.notify_user;
        }
    } catch (e) { /* ignore */ }
}

// Update notification preference when toggled
notifyCheckbox.addEventListener('change', async function() {
    try {
        await fetch(`${API_URL}/notification-preference`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notify_user: notifyCheckbox.checked })
        });
    } catch (e) { /* ignore */ }
});

async function processDateRange() {
    const startDate = startDateInput.value;
    const endDate = endDateInput.value;
    if (!validateDateRange(startDate, endDate)) {
        return;
    }
    toggleButtonLoading(processBtn, true, 'Processing...');
    try {
        const response = await fetch(`${API_URL}/summarize-range`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                start_date: startDate,
                end_date: endDate
            }),
        });
        if (!response.ok) throw new Error('Failed to process date range');
        showToast('Processing date range. Check history for results.');
    } catch (error) {
        showToast(error.message, 'danger');
    } finally {
        toggleButtonLoading(processBtn, false);
    }
}

// Event Listeners
startBtn.addEventListener('click', startSummarizer);
stopBtn.addEventListener('click', stopSummarizer);
setIntervalBtn.addEventListener('click', setInterval);
processBtn.addEventListener('click', processDateRange);

// Initialize WebSocket connection
setupWebSocket((data) => {
    if (data.type === 'status') {
        updateStatus(data.data);
    }
});

fetchNotificationPreference(); 