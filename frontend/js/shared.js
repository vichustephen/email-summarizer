const API_URL = 'http://localhost:8000';

// Toast notification system
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

// Date formatting
function formatDateTime(dateStr) {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleString();
}

function formatDate(dateStr) {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString();
}

// API calls
async function fetchWithError(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        showToast(error.message, 'danger');
        throw error;
    }
}

// WebSocket connection
function setupWebSocket(onMessage) {
    let ws = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    
    function connect() {
        ws = new WebSocket('ws://localhost:8000/ws');
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            onMessage(data);
        };
        
        ws.onopen = () => {
            console.log('WebSocket connected');
            reconnectAttempts = 0;
        };
        
        ws.onclose = () => {
            console.log('WebSocket closed');
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                setTimeout(connect, 5000 * reconnectAttempts); // Exponential backoff
            } else {
                showToast('Connection lost. Please refresh the page.', 'error');
            }
        };
        
        ws.onerror = () => {
            console.error('WebSocket error');
        };
    }
    
    connect();
    return ws;
}

// Date validation for summarizer
function validateDateRange(startDate, endDate) {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const today = new Date();
    const maxDate = new Date(today);
    maxDate.setDate(today.getDate()); // Today is the max date
    const minDate = new Date(maxDate);
    minDate.setDate(maxDate.getDate() - 7); // 7 days before max date
    
    if (start > maxDate || end > maxDate) {
        showToast('Cannot select future dates or today', 'warning');
        return false;
    }
    
    if (start < minDate) {
        showToast('Cannot select dates more than 7 days in the past', 'warning');
        return false;
    }
    
    if (start > end) {
        showToast('Start date must be before end date', 'warning');
        return false;
    }
    
    return true;
}

// Button loading utility
function toggleButtonLoading(button, isLoading = true, loadingText = 'Loading...') {
    if (isLoading) {
        button.disabled = true;
        // Save current HTML if not already saved
        if (!button.dataset.originalHtml) {
            button.dataset.originalHtml = button.innerHTML;
        }
        button.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${loadingText}`;
    } else {
        button.disabled = false;
        if (button.dataset.originalHtml) {
            button.innerHTML = button.dataset.originalHtml;
            delete button.dataset.originalHtml;
        }
    }
}