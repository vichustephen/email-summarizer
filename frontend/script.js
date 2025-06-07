const API_URL = 'http://localhost:8000';
let ws = null;

// DOM Elements
const statusBadge = document.getElementById('status-badge');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const intervalInput = document.getElementById('interval-input');
const setIntervalBtn = document.getElementById('set-interval-btn');
const lastRunSpan = document.getElementById('last-run');
const nextRunSpan = document.getElementById('next-run');

// Helper Functions
function formatDateTime(dateStr) {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleString();
}

function showToast(message, type = 'success') {
    const toastContainer = document.querySelector('.toast-container');
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

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
}

// WebSocket Connection
function connectWebSocket() {
    ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'status') {
            updateStatus(data.data);
        }
    };
    
    ws.onclose = () => {
        // Try to reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = () => {
        showToast('Connection lost. Retrying...', 'warning');
    };
}

// API Calls
async function startSummarizer() {
    try {
        const response = await fetch(`${API_URL}/start`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to start summarizer');
        showToast('Summarizer started successfully');
    } catch (error) {
        showToast(error.message, 'danger');
    }
}

async function stopSummarizer() {
    try {
        const response = await fetch(`${API_URL}/stop`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to stop summarizer');
        showToast('Summarizer stopped successfully');
    } catch (error) {
        showToast(error.message, 'danger');
    }
}

async function setInterval() {
    const minutes = parseInt(intervalInput.value);
    if (isNaN(minutes) || minutes < 5 || minutes > 1440) {
        showToast('Please enter a valid interval between 5 and 1440 minutes', 'warning');
        return;
    }
    
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
    }
}

// Event Listeners
startBtn.addEventListener('click', startSummarizer);
stopBtn.addEventListener('click', stopSummarizer);
setIntervalBtn.addEventListener('click', setInterval);

// Initialize WebSocket connection
connectWebSocket(); 