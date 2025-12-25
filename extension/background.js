// Mycelium Chrome Extension - Background Service Worker

const DEFAULT_API_URL = 'http://localhost:8000';

// Get the API URL from storage
async function getApiUrl() {
    const result = await chrome.storage.sync.get(['apiUrl']);
    return result.apiUrl || DEFAULT_API_URL;
}

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: 'ingest-page',
        title: 'Save to Mycelium',
        contexts: ['page']
    });

    chrome.contextMenus.create({
        id: 'ingest-selection',
        title: 'Save Selection to Mycelium',
        contexts: ['selection']
    });

    // Set side panel to open when clicking extension icon
    // This is the most reliable way to open side panel
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(console.error);
});

// Capture page content when extension icon is clicked (before side panel opens)
chrome.action.onClicked.addListener(async (tab) => {
    if (tab?.id) {
        let pageContent = null;

        try {
            pageContent = await chrome.tabs.sendMessage(tab.id, { action: 'getPageContent' });
        } catch (e) {
            // Try scripting API
            try {
                const results = await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: () => {
                        const clone = document.body.cloneNode(true);
                        clone.querySelectorAll('script, style, nav, footer, header, aside, iframe, noscript').forEach(el => el.remove());
                        let text = (clone.innerText || clone.textContent || '').split('\n').map(l => l.trim()).filter(l => l).join('\n').replace(/\n{3,}/g, '\n\n');
                        return { success: true, content: text, title: document.title, url: window.location.href, length: text.length };
                    }
                });
                if (results?.[0]?.result) pageContent = results[0].result;
            } catch (err) {
                console.log('Could not get page content');
            }
        }

        if (pageContent?.success) {
            await chrome.storage.session.set({
                currentPageContent: pageContent.content,
                currentPageUrl: pageContent.url,
                currentPageTitle: pageContent.title,
                currentPageLength: pageContent.length
            });
        } else {
            await chrome.storage.session.remove(['currentPageContent', 'currentPageUrl', 'currentPageTitle', 'currentPageLength']);
        }
    }
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (info.menuItemId === 'ingest-page') {
        await ingestUrl(tab.url, tab.title);
    } else if (info.menuItemId === 'ingest-selection') {
        await ingestUrl(tab.url, tab.title);
    }
});

// Handle messages from popup and sidepanel
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'ingestUrl') {
        ingestUrl(request.url, request.title, request.workspaceId)
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true;
    }

    if (request.action === 'getWorkspaces') {
        getWorkspaces()
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true;
    }

    if (request.action === 'getThreads') {
        getThreads(request.workspaceId)
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true;
    }

    if (request.action === 'createWorkspace') {
        createWorkspace(request.workspaceId)
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true;
    }

    if (request.action === 'createThread') {
        createThread(request.workspaceId, request.title)
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true;
    }

    if (request.action === 'testConnection') {
        testConnection(request.apiUrl)
            .then(result => sendResponse(result))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true;
    }

    if (request.action === 'openSidePanel') {
        (async () => {
            try {
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if (tab?.id) {
                    // Capture page content before opening popup
                    let pageContent = null;

                    // Try content script first
                    try {
                        pageContent = await chrome.tabs.sendMessage(tab.id, { action: 'getPageContent' });
                    } catch (e) {
                        console.log('Content script not available, using scripting API');
                    }

                    // Fallback: use scripting API to inject and run
                    if (!pageContent?.success) {
                        try {
                            const results = await chrome.scripting.executeScript({
                                target: { tabId: tab.id },
                                func: () => {
                                    const clone = document.body.cloneNode(true);
                                    const remove = clone.querySelectorAll('script, style, nav, footer, header, aside, iframe, noscript');
                                    remove.forEach(el => el.remove());
                                    let text = clone.innerText || clone.textContent || '';
                                    text = text.split('\n').map(l => l.trim()).filter(l => l).join('\n');
                                    text = text.replace(/\n{3,}/g, '\n\n');
                                    return {
                                        success: true,
                                        content: text,
                                        title: document.title,
                                        url: window.location.href,
                                        length: text.length
                                    };
                                }
                            });
                            if (results?.[0]?.result) {
                                pageContent = results[0].result;
                            }
                        } catch (scriptError) {
                            console.log('Scripting API failed:', scriptError.message);
                        }
                    }

                    // Store the content if we got it
                    if (pageContent?.success) {
                        await chrome.storage.session.set({
                            currentPageContent: pageContent.content,
                            currentPageUrl: pageContent.url,
                            currentPageTitle: pageContent.title,
                            currentPageLength: pageContent.length
                        });
                    } else {
                        // Clear any stale data
                        await chrome.storage.session.remove(['currentPageContent', 'currentPageUrl', 'currentPageTitle', 'currentPageLength']);
                    }

                    // Try side panel with windowId (more reliable)
                    try {
                        await chrome.sidePanel.setOptions({
                            path: 'sidepanel.html',
                            enabled: true
                        });

                        // Get current window
                        const window = await chrome.windows.getCurrent();
                        await chrome.sidePanel.open({ windowId: window.id });
                        sendResponse({ success: true });
                        return;
                    } catch (sidePanelError) {
                        console.log('Side panel with windowId failed:', sidePanelError.message);

                        // Try with tabId as fallback
                        try {
                            await chrome.sidePanel.setOptions({
                                tabId: tab.id,
                                path: 'sidepanel.html',
                                enabled: true
                            });
                            await chrome.sidePanel.open({ tabId: tab.id });
                            sendResponse({ success: true });
                            return;
                        } catch (tabError) {
                            console.log('Side panel with tabId failed:', tabError.message);
                            throw tabError;
                        }
                    }
                } else {
                    throw new Error('No active tab found');
                }
            } catch (error) {
                console.error('Side panel error, using fallback popup:', error);
                // Fallback: open in popup window
                try {
                    await chrome.windows.create({
                        url: chrome.runtime.getURL('sidepanel.html'),
                        type: 'popup',
                        width: 420,
                        height: 700
                    });
                    sendResponse({ success: true, fallback: true });
                } catch (e) {
                    sendResponse({ success: false, error: error.message });
                }
            }
        })();
        return true;
    }

    if (request.action === 'getPageContent') {
        (async () => {
            try {
                // Always get fresh content from active tab
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if (!tab?.id) {
                    sendResponse({ success: false, error: 'No active tab' });
                    return;
                }

                let pageContent = null;

                // Try content script first
                try {
                    pageContent = await chrome.tabs.sendMessage(tab.id, { action: 'getPageContent' });
                } catch (e) {
                    // Content script not available, use scripting API
                    try {
                        const results = await chrome.scripting.executeScript({
                            target: { tabId: tab.id },
                            func: () => {
                                const clone = document.body.cloneNode(true);
                                clone.querySelectorAll('script, style, nav, footer, header, aside, iframe, noscript').forEach(el => el.remove());
                                let text = (clone.innerText || clone.textContent || '').split('\n').map(l => l.trim()).filter(l => l).join('\n').replace(/\n{3,}/g, '\n\n');
                                return { success: true, content: text, title: document.title, url: window.location.href, length: text.length };
                            }
                        });
                        if (results?.[0]?.result) {
                            pageContent = results[0].result;
                        }
                    } catch (scriptError) {
                        sendResponse({ success: false, error: 'Could not get page content' });
                        return;
                    }
                }

                sendResponse(pageContent || { success: false, error: 'No content' });
            } catch (error) {
                sendResponse({ success: false, error: error.message });
            }
        })();
        return true;
    }
});

// API Functions
async function ingestUrl(url, title, workspaceId = 'default') {
    const apiUrl = await getApiUrl();

    const response = await fetch(`${apiUrl}/workspaces/${workspaceId}/ingest-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, title })
    });

    if (!response.ok) {
        throw new Error(`Failed to ingest: ${response.statusText}`);
    }

    const data = await response.json();
    return { success: true, data };
}

async function getWorkspaces() {
    const apiUrl = await getApiUrl();

    const response = await fetch(`${apiUrl}/workspaces`);
    if (!response.ok) {
        throw new Error(`Failed to get workspaces: ${response.statusText}`);
    }

    const data = await response.json();
    return { success: true, data };
}

async function createWorkspace(workspaceId) {
    const apiUrl = await getApiUrl();

    const response = await fetch(`${apiUrl}/workspaces/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId })
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Failed to create workspace: ${response.statusText}`);
    }

    const data = await response.json();
    return { success: true, data };
}

async function getThreads(workspaceId) {
    const apiUrl = await getApiUrl();

    const response = await fetch(`${apiUrl}/threads/${workspaceId}`);
    if (!response.ok) {
        throw new Error(`Failed to get threads: ${response.statusText}`);
    }

    const data = await response.json();
    return { success: true, data };
}

async function createThread(workspaceId, title = 'New Chat') {
    const apiUrl = await getApiUrl();

    const response = await fetch(`${apiUrl}/threads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId, title })
    });

    if (!response.ok) {
        throw new Error(`Failed to create thread: ${response.statusText}`);
    }

    const data = await response.json();
    return { success: true, data };
}

async function testConnection(apiUrl) {
    try {
        const response = await fetch(`${apiUrl}/workspaces`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000)
        });
        return { success: response.ok };
    } catch (error) {
        return { success: false, error: error.message };
    }
}
