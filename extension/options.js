// Mycelium Chrome Extension - Options Script

const DEFAULT_API_URL = 'http://localhost:8000';

document.addEventListener('DOMContentLoaded', async () => {
    const apiUrlInput = document.getElementById('apiUrl');
    const testBtn = document.getElementById('testBtn');
    const saveBtn = document.getElementById('saveBtn');
    const statusDiv = document.getElementById('status');

    // Load saved settings
    const { apiUrl } = await chrome.storage.sync.get(['apiUrl']);
    apiUrlInput.value = apiUrl || DEFAULT_API_URL;

    // Show status
    function showStatus(message, type) {
        statusDiv.className = `status status-${type}`;
        statusDiv.innerHTML = type === 'loading'
            ? `<span class="spinner"></span><span>${message}</span>`
            : `<span>${message}</span>`;
        statusDiv.classList.remove('hidden');
    }

    // Hide status
    function hideStatus() {
        statusDiv.classList.add('hidden');
    }

    // Test connection
    testBtn.addEventListener('click', async () => {
        const url = apiUrlInput.value.trim();
        if (!url) {
            showStatus('Please enter a URL', 'error');
            return;
        }

        showStatus('Testing connection...', 'loading');

        try {
            const response = await chrome.runtime.sendMessage({
                action: 'testConnection',
                apiUrl: url
            });

            if (response.success) {
                showStatus('✓ Connected successfully!', 'success');
            } else {
                showStatus(`✗ Connection failed: ${response.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            showStatus(`✗ ${error.message}`, 'error');
        }
    });

    // Save settings
    saveBtn.addEventListener('click', async () => {
        const url = apiUrlInput.value.trim() || DEFAULT_API_URL;

        await chrome.storage.sync.set({ apiUrl: url });
        showStatus('✓ Settings saved!', 'success');

        setTimeout(hideStatus, 2000);
    });
});
