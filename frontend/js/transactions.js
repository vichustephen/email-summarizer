// DOM Elements
const startDateInput = document.getElementById('start-date');
const endDateInput = document.getElementById('end-date');
const loadBtn = document.getElementById('load-btn');
const transactionsContainer = document.getElementById('transactions-container');

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

async function loadTransactions() {
    const startDate = startDateInput.value;
    const endDate = endDateInput.value;
    
    if (!validateDateRange(startDate, endDate)) {
        return;
    }
    
    try {
        const transactions = await fetchWithError(
            `${API_URL}/transactions?start_date=${startDate}&end_date=${endDate}`
        );
        
        displayTransactions(transactions);
    } catch (error) {
        console.error('Failed to load transactions:', error);
    }
}

function displayTransactions(transactions) {
    if (!transactions || transactions.length === 0) {
        transactionsContainer.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-4">
                    No transactions found for the selected date range.
                </td>
            </tr>
        `;
        return;
    }
    
    const html = transactions.map(transaction => `
        <tr class="transaction-row">
            <td>${formatDate(transaction.date)}</td>
            <td>${transaction.vendor}</td>
            <td>${transaction.amount.toFixed(2)}</td>
            <td>
                <span class="badge bg-${transaction.type === 'credit' ? 'success' : 'danger'}">
                    ${transaction.type}
                </span>
            </td>
            <td>
                <span class="badge bg-secondary">
                    ${transaction.category}
                </span>
            </td>
            <td>
                <small class="text-muted">${transaction.ref || '-'}</small>
            </td>
        </tr>
    `).join('');
    
    transactionsContainer.innerHTML = html;
}

// Event Listeners
loadBtn.addEventListener('click', loadTransactions);

// Load transactions on page load
loadTransactions(); 