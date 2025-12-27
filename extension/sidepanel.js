// Mycelium Chrome Extension - Side Panel Script

const DEFAULT_API_URL = 'http://localhost:8000';

// Theme definitions (same as frontend ThemeProvider.jsx)
const THEMES = {
    dark: {
        '--bg-primary': '#0a0a0a',
        '--bg-secondary': '#111827',
        '--bg-tertiary': '#1f2937',
        '--bg-elevated': '#374151',
        '--text-primary': '#f9fafb',
        '--text-secondary': '#e5e7eb',
        '--text-muted': '#9ca3af',
        '--border-color': '#374151',
        '--border-subtle': '#1f2937',
    },
    light: {
        '--bg-primary': '#ffffff',
        '--bg-secondary': '#f9fafb',
        '--bg-tertiary': '#f3f4f6',
        '--bg-elevated': '#e5e7eb',
        '--text-primary': '#111827',
        '--text-secondary': '#374151',
        '--text-muted': '#6b7280',
        '--border-color': '#d1d5db',
        '--border-subtle': '#e5e7eb',
    },
    midnight: {
        '--bg-primary': '#0f172a',
        '--bg-secondary': '#1e293b',
        '--bg-tertiary': '#334155',
        '--bg-elevated': '#475569',
        '--text-primary': '#f1f5f9',
        '--text-secondary': '#cbd5e1',
        '--text-muted': '#94a3b8',
        '--border-color': '#475569',
        '--border-subtle': '#334155',
    },
    forest: {
        '--bg-primary': '#022c22',
        '--bg-secondary': '#064e3b',
        '--bg-tertiary': '#065f46',
        '--bg-elevated': '#047857',
        '--text-primary': '#ecfdf5',
        '--text-secondary': '#d1fae5',
        '--text-muted': '#6ee7b7',
        '--border-color': '#047857',
        '--border-subtle': '#065f46',
    }
};

// Get the API URL from storage
async function getApiUrl() {
    const result = await chrome.storage.sync.get(['apiUrl']);
    return result.apiUrl || DEFAULT_API_URL;
}

// Convert hex to HSL
function hexToHsl(hex) {
    const num = parseInt(hex.replace('#', ''), 16);
    const r = (num >> 16) / 255;
    const g = ((num >> 8) & 0x00FF) / 255;
    const b = (num & 0x0000FF) / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;

    if (max === min) {
        h = s = 0;
    } else {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }
    return { h: h * 360, s: s * 100, l: l * 100 };
}

// Convert HSL to hex
function hslToHex(h, s, l) {
    s /= 100;
    l /= 100;
    const a = s * Math.min(l, 1 - l);
    const f = n => {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        return Math.round(255 * color).toString(16).padStart(2, '0');
    };
    return `#${f(0)}${f(8)}${f(4)}`;
}

// Generate harmonious color palette from accent color
function computeColorPalette(accentHex) {
    const hsl = hexToHsl(accentHex);

    // Generate unique color for each markdown element using hue rotation
    return {
        heading: accentHex, // Base accent for headers
        bold: hslToHex((hsl.h + 15) % 360, Math.min(hsl.s + 5, 100), Math.min(hsl.l + 5, 85)),
        italic: hslToHex((hsl.h + 45) % 360, Math.min(hsl.s, 90), Math.min(hsl.l + 10, 85)),
        link: hslToHex((hsl.h + 60) % 360, Math.min(hsl.s + 10, 100), Math.min(hsl.l + 10, 85)),
        code: hslToHex((hsl.h + 180) % 360, Math.max(hsl.s - 20, 40), Math.min(hsl.l + 15, 80)),
        listMarker: hslToHex((hsl.h + 90) % 360, hsl.s, Math.min(hsl.l + 5, 80)),
        blockquote: hslToHex((hsl.h + 270) % 360, Math.max(hsl.s - 20, 40), Math.min(hsl.l + 15, 75)),
    };
}

// Apply theme to the extension
function applyTheme(settings) {
    const { theme = 'dark', accent_color = '#8b5cf6', colorful_markdown = false } = settings;

    // Get theme colors
    const themeColors = THEMES[theme] || THEMES.dark;

    // Generate accent variations
    const accentHover = adjustColor(accent_color, -20);
    const accentMuted = accent_color + '40';

    // Generate markdown colors
    let mdColors;
    if (colorful_markdown) {
        const palette = computeColorPalette(accent_color);
        mdColors = {
            '--md-heading': palette.heading,
            '--md-bold': palette.bold,
            '--md-italic': palette.italic,
            '--md-link': palette.link,
            '--md-code-bg': palette.code + '30',
            '--md-code-text': palette.code,
            '--md-list-marker': palette.listMarker,
            '--md-blockquote': palette.blockquote,
        };
    } else {
        // Neutral/muted colors when disabled
        mdColors = {
            '--md-heading': themeColors['--text-primary'],
            '--md-bold': 'inherit',
            '--md-italic': 'inherit',
            '--md-link': accent_color,
            '--md-code-bg': 'rgba(0,0,0,0.2)',
            '--md-code-text': themeColors['--text-secondary'],
            '--md-list-marker': themeColors['--text-muted'],
            '--md-blockquote': themeColors['--text-muted'],
        };
    }

    // Create or update theme style element
    let styleEl = document.getElementById('mycelium-theme');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'mycelium-theme';
        document.head.appendChild(styleEl);
    }

    // Build CSS string with all theme variables
    styleEl.textContent = `
        :root {
            --bg-primary: ${themeColors['--bg-primary']} !important;
            --bg-secondary: ${themeColors['--bg-secondary']} !important;
            --bg-tertiary: ${themeColors['--bg-tertiary']} !important;
            --bg-elevated: ${themeColors['--bg-elevated']} !important;
            --text-primary: ${themeColors['--text-primary']} !important;
            --text-secondary: ${themeColors['--text-secondary']} !important;
            --text-muted: ${themeColors['--text-muted']} !important;
            --border-color: ${themeColors['--border-color']} !important;
            --border-subtle: ${themeColors['--border-subtle']} !important;
            --accent: ${accent_color} !important;
            --accent-hover: ${accentHover} !important;
            --accent-muted: ${accentMuted} !important;
            --md-heading: ${mdColors['--md-heading']} !important;
            --md-bold: ${mdColors['--md-bold']} !important;
            --md-italic: ${mdColors['--md-italic']} !important;
            --md-link: ${mdColors['--md-link']} !important;
            --md-code-bg: ${mdColors['--md-code-bg']} !important;
            --md-code-text: ${mdColors['--md-code-text']} !important;
            --md-list-marker: ${mdColors['--md-list-marker']} !important;
            --md-blockquote: ${mdColors['--md-blockquote']} !important;
        }
    `;
}

// Helper to darken/lighten a hex color
function adjustColor(hex, amount) {
    const num = parseInt(hex.replace('#', ''), 16);
    const r = Math.min(255, Math.max(0, (num >> 16) + amount));
    const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amount));
    const b = Math.min(255, Math.max(0, (num & 0x0000FF) + amount));
    return `#${(1 << 24 | r << 16 | g << 8 | b).toString(16).slice(1)}`;
}

// Load theme from backend
async function loadTheme() {
    try {
        const apiUrl = await getApiUrl();
        const response = await fetch(`${apiUrl}/system/config`);
        if (response.ok) {
            const settings = await response.json();
            applyTheme(settings);
        }
    } catch (e) {
        // Silently use defaults if backend unavailable
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Load theme first
    await loadTheme();

    const workspaceSelect = document.getElementById('workspaceSelect');
    const threadSelect = document.getElementById('threadSelect');
    const messagesContainer = document.getElementById('messagesContainer');
    const emptyState = document.getElementById('emptyState');
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const newThreadBtn = document.getElementById('newThreadBtn');
    const includePageToggle = document.getElementById('includePageToggle');
    const pageInfo = document.getElementById('pageInfo');
    const ingestBtn = document.getElementById('ingestBtn');
    const newWorkspaceBtn = document.getElementById('newWorkspaceBtn');

    let currentWorkspace = 'default';
    let currentThread = null;
    let isStreaming = false;
    let currentPageContent = null;
    let currentPageUrl = null;
    let currentPageTitle = null;
    let pageIngested = false;
    const maxContextInput = document.getElementById('maxContextInput');
    const maxContextLabel = document.getElementById('maxContextLabel');

    // Load saved max context setting (in k tokens)
    const { maxContextK } = await chrome.storage.sync.get(['maxContextK']);
    if (maxContextK !== undefined) {
        maxContextInput.value = maxContextK;
        maxContextLabel.textContent = maxContextK + 'k';
    }

    // Get max inline chars from token limit (tokens * 4 = approx chars)
    function getMaxInlineChars() {
        return (parseInt(maxContextInput.value) || 5) * 1000 * 4;
    }

    // Update label and save when slider changes
    maxContextInput.addEventListener('input', () => {
        maxContextLabel.textContent = maxContextInput.value + 'k';
    });
    maxContextInput.addEventListener('change', () => {
        chrome.storage.sync.set({ maxContextK: parseInt(maxContextInput.value) || 5 });
    });

    // Load workspaces
    async function loadWorkspaces() {
        try {
            const response = await chrome.runtime.sendMessage({ action: 'getWorkspaces' });

            if (response.success && response.data) {
                workspaceSelect.innerHTML = '';

                // Get saved preference
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

                if (response.data.length === 0) {
                    workspaceSelect.innerHTML = '<option value="default">default</option>';
                }

                currentWorkspace = workspaceSelect.value || 'default';
                await loadThreads();
            }
        } catch (error) {
            console.error('Error loading workspaces:', error);
            workspaceSelect.innerHTML = '<option value="default">default</option>';
        }
    }

    // Load threads for current workspace
    async function loadThreads() {
        try {
            const response = await chrome.runtime.sendMessage({
                action: 'getThreads',
                workspaceId: currentWorkspace
            });

            if (response.success && response.data) {
                threadSelect.innerHTML = '<option value="">New conversation</option>';

                response.data.forEach(thread => {
                    const option = document.createElement('option');
                    option.value = thread.id;
                    option.textContent = thread.title || 'Untitled';
                    threadSelect.appendChild(option);
                });

                // Restore previously selected thread for this workspace
                const storageKey = `selectedThread_${currentWorkspace}`;
                const stored = await chrome.storage.sync.get([storageKey]);
                const savedThreadId = stored[storageKey];

                // Check if saved thread still exists in the list
                const savedThreadExists = savedThreadId && response.data.some(t => t.id === savedThreadId);

                if (savedThreadExists) {
                    threadSelect.value = savedThreadId;
                    currentThread = savedThreadId;
                    await loadMessages();
                } else if (response.data.length > 0) {
                    // Fallback to first thread if saved one doesn't exist
                    threadSelect.value = response.data[0].id;
                    currentThread = response.data[0].id;
                    await loadMessages();
                } else {
                    currentThread = null;
                    clearMessages();
                }

                updateInputState();
            }
        } catch (error) {
            console.error('Error loading threads:', error);
            threadSelect.innerHTML = '<option value="">New conversation</option>';
        }
    }

    // Load messages for current thread
    async function loadMessages() {
        if (!currentThread) {
            clearMessages();
            return;
        }

        try {
            const apiUrl = await getApiUrl();
            const response = await fetch(
                `${apiUrl}/threads/${currentWorkspace}/${currentThread}/history`
            );

            if (response.ok) {
                const messages = await response.json();
                displayMessages(messages);
            }
        } catch (error) {
            console.error('Error loading messages:', error);
        }
    }

    // Display messages
    function displayMessages(messages) {
        messagesContainer.innerHTML = '';

        if (messages.length === 0) {
            messagesContainer.appendChild(emptyState.cloneNode(true));
            return;
        }

        messages.forEach(msg => {
            const type = msg.type || (msg.role === 'user' ? 'human' : 'ai');
            if (type === 'human' || type === 'user') {
                addMessage(msg.content, 'user');
            } else if (type === 'ai' || type === 'assistant') {
                addMessage(msg.content, 'ai');
            }
        });

        scrollToBottom();
    }

    // Clear messages
    function clearMessages() {
        messagesContainer.innerHTML = '';
        const emptyClone = document.createElement('div');
        emptyClone.className = 'empty-state';
        emptyClone.innerHTML = `
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <p>Start a conversation</p>
      <span class="text-muted text-sm">Ask anything about your knowledge graph</span>
    `;
        messagesContainer.appendChild(emptyClone);
    }

    // Add a message to the container
    function addMessage(content, type, streaming = false) {
        // Remove empty state if present
        const emptyState = messagesContainer.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        const msgDiv = document.createElement('div');
        msgDiv.className = `message message-${type}`;
        if (streaming) msgDiv.classList.add('streaming');

        if (type === 'ai') {
            // Extract token usage from content (pattern: *(Tokens: ...)* )
            const tokenRegex = /\*\((Tokens: .*?)\)\*/g;
            let mainContent = content;
            let tokenString = null;

            const matches = [...content.matchAll(tokenRegex)];
            if (matches.length > 0) {
                tokenString = matches[matches.length - 1][1]; // Use last match
                mainContent = content.replace(tokenRegex, '').trim();
            }

            // Create content wrapper
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.innerHTML = renderMarkdown(mainContent);
            msgDiv.appendChild(contentDiv);

            // Add token footer if present
            if (tokenString) {
                const tokenDiv = document.createElement('div');
                tokenDiv.className = 'message-tokens';
                tokenDiv.textContent = tokenString;
                msgDiv.appendChild(tokenDiv);
            }
        } else {
            // User messages: hide the context note for cleaner display
            const displayContent = content.replace(/\n\n\[Context.*$/s, '').trim();
            msgDiv.textContent = displayContent;
        }

        messagesContainer.appendChild(msgDiv);
        scrollToBottom();

        return msgDiv;
    }

    // Update streaming message
    function updateStreamingMessage(element, content) {
        // Extract token usage from content
        const tokenRegex = /\*\((Tokens: .*?)\)\*/g;
        let mainContent = content;
        let tokenString = null;

        const matches = [...content.matchAll(tokenRegex)];
        if (matches.length > 0) {
            tokenString = matches[matches.length - 1][1];
            mainContent = content.replace(tokenRegex, '').trim();
        }

        // Update or create content div
        let contentDiv = element.querySelector('.message-content');
        if (!contentDiv) {
            contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            element.appendChild(contentDiv);
        }
        contentDiv.innerHTML = renderMarkdown(mainContent);

        // Update or create token div
        let tokenDiv = element.querySelector('.message-tokens');
        if (tokenString) {
            if (!tokenDiv) {
                tokenDiv = document.createElement('div');
                tokenDiv.className = 'message-tokens';
                element.appendChild(tokenDiv);
            }
            tokenDiv.textContent = tokenString;
        } else if (tokenDiv) {
            tokenDiv.remove();
        }

        scrollToBottom();
    }

    // Use marked library for proper markdown rendering
    function renderMarkdown(text) {
        if (!text) return '';

        // Configure marked for our needs
        marked.setOptions({
            breaks: true,  // Convert \n to <br>
            gfm: true,     // GitHub Flavored Markdown
            headerIds: false,
            mangle: false
        });

        return marked.parse(text);
    }

    // Scroll to bottom
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Update input state
    function updateInputState() {
        const enabled = !isStreaming;
        messageInput.disabled = !enabled;
        sendBtn.disabled = !enabled || !messageInput.value.trim();
    }

    // Get page content from background (handles both popup and sidepanel)
    async function getPageContent() {
        try {
            const response = await chrome.runtime.sendMessage({ action: 'getPageContent' });
            if (response?.success) {
                return response;
            }
        } catch (error) {
            console.log('Could not get page content:', error.message);
        }
        return null;
    }

    // Update page info display
    // Approximate tokens from characters (~4 chars per token)
    function charsToTokens(chars) {
        return Math.round(chars / 4);
    }

    function updatePageInfo(info) {
        if (!info) {
            pageInfo.textContent = '';
            return;
        }
        const chars = info.length;
        const tokens = charsToTokens(chars);
        const tokenDisplay = tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}k` : tokens;
        if (chars > getMaxInlineChars()) {
            pageInfo.textContent = `~${tokenDisplay} tokens (will ingest)`;
            pageInfo.className = 'page-info';
        } else {
            pageInfo.textContent = `~${tokenDisplay} tokens`;
            pageInfo.className = 'page-info';
        }
    }

    // Refresh page content (used for tab changes and toggle)
    async function refreshPageContent() {
        if (!includePageToggle.checked) return;

        pageInfo.textContent = 'Loading...';
        const page = await getPageContent();
        if (page) {
            currentPageContent = page.content;
            currentPageUrl = page.url;
            currentPageTitle = page.title;
            pageIngested = false; // Reset for new page
            updatePageInfo(page.content);
        } else {
            pageInfo.textContent = 'Could not load page';
            currentPageContent = null;
        }
    }

    // Listen for tab changes to refresh page content
    chrome.tabs.onActivated.addListener(async () => {
        await refreshPageContent();
    });

    // Handle page toggle change
    includePageToggle.addEventListener('change', async () => {
        if (includePageToggle.checked) {
            await refreshPageContent();
        } else {
            pageInfo.textContent = '';
            currentPageContent = null;
            pageIngested = false;
        }
    });

    // Send message
    async function sendMessage() {
        let content = messageInput.value.trim();
        if (!content || isStreaming) return;

        // Capture fresh page content for dynamic pages
        if (includePageToggle.checked) {
            pageInfo.textContent = 'Capturing page...';
            const page = await getPageContent();
            if (page) {
                // Check if page content changed (different URL or significantly different length)
                const isNewPage = page.url !== currentPageUrl;
                const significantChange = currentPageContent &&
                    Math.abs(page.content.length - currentPageContent.length) > 500;

                if (isNewPage || significantChange) {
                    pageIngested = false; // Reset if content changed significantly
                }

                currentPageContent = page.content;
                currentPageUrl = page.url;
                currentPageTitle = page.title;
                updatePageInfo(page.content);
            } else {
                pageInfo.textContent = 'Could not capture page';
            }
        }

        // Handle page context
        let pageContextNote = '';
        if (includePageToggle.checked && currentPageContent) {
            if (currentPageContent.length > getMaxInlineChars()) {
                // Large page: ingest only on first message
                if (!pageIngested) {
                    pageInfo.textContent = 'Ingesting page...';
                    pageInfo.className = 'page-info ingesting';
                    try {
                        const ingestResult = await chrome.runtime.sendMessage({
                            action: 'ingestUrl',
                            url: currentPageUrl,
                            title: currentPageTitle,
                            workspaceId: currentWorkspace
                        });

                        // Poll for completion
                        if (ingestResult?.success && ingestResult?.data?.job_id) {
                            const jobId = ingestResult.data.job_id;
                            const apiUrl = await getApiUrl();
                            let attempts = 0;
                            const maxAttempts = 120; // Max 4 minutes

                            while (attempts < maxAttempts) {
                                try {
                                    const statusResp = await fetch(
                                        `${apiUrl}/workspaces/${currentWorkspace}/ingest_status?job_id=${jobId}`
                                    );
                                    const data = await statusResp.json();

                                    // Find our job in the jobs array
                                    const job = data.jobs?.find(j => j.job_id === jobId);

                                    if (!job || job.status === 'completed' || job.status === 'done') {
                                        break;
                                    } else if (job.status === 'error' || job.status === 'failed') {
                                        throw new Error('Ingestion failed');
                                    } else if (job.status === 'cancelled') {
                                        pageInfo.textContent = 'Ingestion cancelled';
                                        return;
                                    }

                                    // Update progress with current/total
                                    if (job.total > 0) {
                                        pageInfo.textContent = `Ingesting... ${job.current}/${job.total} chunks`;
                                    } else {
                                        pageInfo.textContent = `Ingesting... (${attempts + 1}s)`;
                                    }
                                } catch (pollError) {
                                    // If status endpoint returns 404 or error, assume done
                                    if (pollError.message?.includes('404')) break;
                                }

                                await new Promise(r => setTimeout(r, 2000));
                                attempts++;
                            }
                        }

                        pageIngested = true;
                        pageInfo.textContent = 'Ingested ✓';
                        pageInfo.className = 'page-info ingested';
                    } catch (e) {
                        console.error('Ingest failed:', e);
                        pageInfo.textContent = 'Ingest failed';
                    }
                }
                // Always add context note (either first time or follow-up)
                pageContextNote = `\n\n[Context: I'm looking at "${currentPageTitle}" (${currentPageUrl}) - this page is in your knowledge graph.]`;
            } else {
                // Include inline
                pageContextNote = `\n\n[Context from current page "${currentPageTitle}" (${currentPageUrl}):]\n\n${currentPageContent}`;
            }
            content += pageContextNote;
        }

        // Create thread if needed
        if (!currentThread) {
            try {
                const response = await chrome.runtime.sendMessage({
                    action: 'createThread',
                    workspaceId: currentWorkspace,
                    title: content.substring(0, 50)
                });

                if (response.success && response.data) {
                    currentThread = response.data.id;

                    // Add to dropdown
                    const option = document.createElement('option');
                    option.value = response.data.id;
                    option.textContent = response.data.title;
                    threadSelect.insertBefore(option, threadSelect.firstChild.nextSibling);
                    threadSelect.value = response.data.id;

                    // Save to storage
                    const storageKey = `selectedThread_${currentWorkspace}`;
                    chrome.storage.sync.set({ [storageKey]: currentThread });
                } else {
                    console.error('Failed to create thread:', response.error);
                    return;
                }
            } catch (error) {
                console.error('Error creating thread:', error);
                return;
            }
        }

        // Add user message to UI
        addMessage(content, 'user');
        messageInput.value = '';
        updateInputState();

        // Start streaming response
        isStreaming = true;
        updateInputState();

        const aiMessage = addMessage('', 'ai', true);
        let fullContent = '';

        try {
            const apiUrl = await getApiUrl();
            const response = await fetch(
                `${apiUrl}/threads/${currentWorkspace}/${currentThread}/chat`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: content })
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                // Backend returns plain text, not SSE JSON
                const chunk = decoder.decode(value, { stream: true });
                if (chunk) {
                    fullContent += chunk;
                    updateStreamingMessage(aiMessage, fullContent);
                }
            }

            // Finalize message
            aiMessage.classList.remove('streaming');
            if (!fullContent) {
                aiMessage.innerHTML = renderMarkdown('*No response received*');
            }

        } catch (error) {
            console.error('Chat error:', error);
            aiMessage.classList.remove('streaming');
            aiMessage.innerHTML = `<span style="color: var(--error)">Error: ${error.message}</span>`;
        } finally {
            isStreaming = false;
            updateInputState();
            messageInput.focus(); // Return focus to input field
        }
    }

    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        updateInputState();
    });

    // Send on Enter (Shift+Enter for newline)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send button click
    sendBtn.addEventListener('click', sendMessage);

    // New workspace button
    newWorkspaceBtn.addEventListener('click', async () => {
        const name = prompt('Enter workspace name:');
        if (!name || !name.trim()) return;

        try {
            newWorkspaceBtn.disabled = true;
            const response = await chrome.runtime.sendMessage({
                action: 'createWorkspace',
                workspaceId: name.trim()
            });

            if (response.success) {
                // Reload workspaces and select the new one
                await loadWorkspaces();
                workspaceSelect.value = name.trim();
                currentWorkspace = name.trim();
                chrome.storage.sync.set({ selectedWorkspace: currentWorkspace });
                await loadThreads();
            } else {
                alert('Failed to create workspace: ' + (response.error || 'Unknown error'));
            }
        } catch (e) {
            alert('Error: ' + e.message);
        } finally {
            newWorkspaceBtn.disabled = false;
        }
    });

    // Workspace change
    workspaceSelect.addEventListener('change', async () => {
        currentWorkspace = workspaceSelect.value;
        chrome.storage.sync.set({ selectedWorkspace: currentWorkspace });
        await loadThreads();
    });

    // Thread change
    threadSelect.addEventListener('change', async () => {
        currentThread = threadSelect.value || null;
        // Save selected thread for this workspace
        const storageKey = `selectedThread_${currentWorkspace}`;
        if (currentThread) {
            chrome.storage.sync.set({ [storageKey]: currentThread });
            await loadMessages();
        } else {
            chrome.storage.sync.remove(storageKey);
            clearMessages();
        }
        updateInputState();
    });

    // New thread button
    newThreadBtn.addEventListener('click', () => {
        threadSelect.value = '';
        currentThread = null;
        clearMessages();
        updateInputState();
        messageInput.focus();
    });

    // Ingest button - quick ingest current page
    ingestBtn.addEventListener('click', async () => {
        const page = await getPageContent();
        if (!page) {
            pageInfo.textContent = 'Could not get page content';
            return;
        }

        ingestBtn.disabled = true;
        pageInfo.textContent = 'Starting ingestion...';
        pageInfo.className = 'page-info ingesting';

        try {
            const result = await chrome.runtime.sendMessage({
                action: 'ingestUrl',
                url: page.url,
                title: page.title,
                workspaceId: currentWorkspace
            });

            // Poll for completion if we got a job ID
            if (result?.success && result?.data?.job_id) {
                const jobId = result.data.job_id;
                const apiUrl = await getApiUrl();
                let attempts = 0;
                const maxAttempts = 120;

                while (attempts < maxAttempts) {
                    try {
                        const statusResp = await fetch(
                            `${apiUrl}/workspaces/${currentWorkspace}/ingest_status`
                        );
                        const data = await statusResp.json();
                        const job = data.jobs?.find(j => j.job_id === jobId);

                        if (!job || job.status === 'completed' || job.status === 'done') {
                            break;
                        } else if (job.status === 'error' || job.status === 'failed') {
                            throw new Error('Ingestion failed');
                        }

                        // Update progress
                        if (job.total > 0) {
                            pageInfo.textContent = `Ingesting... ${job.current}/${job.total} chunks`;
                        } else {
                            pageInfo.textContent = `Ingesting... (${attempts + 1}s)`;
                        }
                    } catch (pollError) {
                        if (pollError.message?.includes('404')) break;
                    }

                    await new Promise(r => setTimeout(r, 2000));
                    attempts++;
                }
            }

            pageInfo.textContent = 'Ingested ✓';
            pageInfo.className = 'page-info ingested';
            setTimeout(() => {
                pageInfo.textContent = '';
                ingestBtn.disabled = false;
            }, 3000);
        } catch (e) {
            pageInfo.textContent = 'Ingest failed: ' + e.message;
            pageInfo.className = 'page-info error';
            ingestBtn.disabled = false;
        }
    });

    // Initialize
    await loadWorkspaces();
    updateInputState();
});
