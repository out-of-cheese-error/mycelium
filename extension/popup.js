// Mycelium Chrome Extension - Popup Script

document.addEventListener('DOMContentLoaded', async () => {
    const workspaceSelect = document.getElementById('workspaceSelect');
    const pageUrlDiv = document.getElementById('pageUrl');
    const ingestBtn = document.getElementById('ingestBtn');
    const openChatBtn = document.getElementById('openChatBtn');
    const openSettings = document.getElementById('openSettings');
    const statusDiv = document.getElementById('status');
    const connectionStatus = document.getElementById('connectionStatus');

    let currentUrl = '';
    let currentTitle = '';

    // Get current tab URL
    async function getCurrentTab() {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        return tab;
    }

    // Show status message
    function showStatus(message, type = 'loading') {
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

    // Update connection status
    function updateConnectionStatus(connected) {
        const dot = connectionStatus.querySelector('.status-dot');
        const text = connectionStatus.querySelector('.status-text');

        if (connected) {
            dot.className = 'status-dot connected';
            text.textContent = 'Connected to Mycelium';
        } else {
            dot.className = 'status-dot disconnected';
            text.textContent = 'Not connected';
        }
    }

    // Load workspaces
    async function loadWorkspaces() {
        try {
            const response = await chrome.runtime.sendMessage({ action: 'getWorkspaces' });

            if (response.success && response.data) {
                workspaceSelect.innerHTML = '';

                // Get saved workspace preference
                const { selectedWorkspace } = await chrome.storage.sync.get(['selectedWorkspace']);

                response.data.forEach(ws => {
                    const option = document.createElement('option');
                    option.value = ws.id;
                    option.textContent = ws.id;
                    if (ws.id === selectedWorkspace) {
                        option.selected = true;
                    }
                    workspaceSelect.appendChild(option);
                });

                // If no workspaces, show message
                if (response.data.length === 0) {
                    workspaceSelect.innerHTML = '<option value="default">default</option>';
                }

                updateConnectionStatus(true);
            } else {
                throw new Error(response.error || 'Failed to load workspaces');
            }
        } catch (error) {
            console.error('Error loading workspaces:', error);
            workspaceSelect.innerHTML = '<option value="default">default</option>';
            updateConnectionStatus(false);
        }
    }

    // Initialize
    async function init() {
        // Get current tab
        const tab = await getCurrentTab();
        currentUrl = tab.url;
        currentTitle = tab.title;

        // Display URL
        pageUrlDiv.textContent = currentUrl;
        pageUrlDiv.title = currentUrl;

        // Load workspaces
        await loadWorkspaces();
    }

    // Save workspace preference
    workspaceSelect.addEventListener('change', () => {
        chrome.storage.sync.set({ selectedWorkspace: workspaceSelect.value });
    });

    // Ingest button click
    ingestBtn.addEventListener('click', async () => {
        const workspaceId = workspaceSelect.value || 'default';

        ingestBtn.disabled = true;
        showStatus('Ingesting page...', 'loading');

        try {
            const response = await chrome.runtime.sendMessage({
                action: 'ingestUrl',
                url: currentUrl,
                title: currentTitle,
                workspaceId
            });

            if (response.success) {
                showStatus('✓ Page ingested successfully!', 'success');
                setTimeout(hideStatus, 3000);
            } else {
                throw new Error(response.error || 'Ingestion failed');
            }
        } catch (error) {
            console.error('Ingestion error:', error);
            showStatus(`✗ ${error.message}`, 'error');
        } finally {
            ingestBtn.disabled = false;
        }
    });

    // Open chat sidebar
    openChatBtn.addEventListener('click', async () => {
        try {
            await chrome.runtime.sendMessage({ action: 'openSidePanel' });
            window.close();
        } catch (error) {
            console.error('Error opening side panel:', error);
        }
    });

    // Open settings
    openSettings.addEventListener('click', () => {
        chrome.runtime.openOptionsPage();
    });

    // Init
    init();
});
