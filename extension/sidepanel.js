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

// Apply theme to the extension
function applyTheme(settings) {
    const { theme = 'dark', accent_color = '#8b5cf6' } = settings;

    // Get theme colors
    const themeColors = THEMES[theme] || THEMES.dark;

    // Generate accent variations
    const accentHover = adjustColor(accent_color, -20);
    const accentMuted = accent_color + '40';

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

    // Load saved max context setting
    const { maxContextK } = await chrome.storage.sync.get(['maxContextK']);
    if (maxContextK !== undefined) {
        maxContextInput.value = maxContextK;
        maxContextLabel.textContent = maxContextK + 'k';
    }

    function getMaxInlineChars() {
        return (parseInt(maxContextInput.value) || 5) * 1000;
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

                // Select first thread if exists
                if (response.data.length > 0) {
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

    // Simple markdown renderer
    function renderMarkdown(text) {
        if (!text) return '';

        // Escape HTML
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks (must be first to protect content)
        const codeBlocks = [];
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            codeBlocks.push(`<pre class="code-block"><code>${code.trim()}</code></pre>`);
            return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
        });

        // Inline code (protect from other transformations)
        const inlineCode = [];
        html = html.replace(/`([^`]+)`/g, (match, code) => {
            inlineCode.push(`<code class="inline-code">${code}</code>`);
            return `__INLINE_CODE_${inlineCode.length - 1}__`;
        });

        // Headers (h1-h4)
        html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

        // Blockquotes
        html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

        // Horizontal rules
        html = html.replace(/^---$/gm, '<hr>');

        // Unordered lists - convert items and wrap in ul
        html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>[\s\S]*?<\/li>)\n?(<li>)/g, '$1$2'); // Remove newlines between li
        html = html.replace(/(<li>.*<\/li>)(\n(?!<li>)|$)/g, '</ul>$1'); // Mark end of list
        html = html.replace(/<\/ul>(<li>)/g, '<ul>$1'); // Add ul at start
        html = html.replace(/<\/ul>$/g, ''); // Clean up stray end tag

        // Simpler approach: wrap consecutive li elements
        html = html.replace(/(<li>.*?<\/li>\s*)+/g, (match) => {
            return '<ul>' + match.replace(/\n/g, '') + '</ul>';
        });

        // Ordered lists
        html = html.replace(/^\d+\. (.+)$/gm, '<oli>$1</oli>');
        html = html.replace(/(<oli>.*?<\/oli>\s*)+/g, (match) => {
            return '<ol>' + match.replace(/<\/?oli>/g, (m) => m.replace('oli', 'li')).replace(/\n/g, '') + '</ol>';
        });

        // Bold (do before italic)
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Links
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

        // Restore inline code
        inlineCode.forEach((code, i) => {
            html = html.replace(`__INLINE_CODE_${i}__`, code);
        });

        // Restore code blocks
        codeBlocks.forEach((block, i) => {
            html = html.replace(`__CODE_BLOCK_${i}__`, block);
        });

        // Paragraphs: split by double newlines
        html = html.split(/\n\n+/).map(p => {
            p = p.trim();
            // Don't wrap block elements in <p>
            if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<ol') ||
                p.startsWith('<pre') || p.startsWith('<blockquote') || p.startsWith('<hr')) {
                return p;
            }
            return p ? `<p>${p.replace(/\n/g, '<br>')}</p>` : '';
        }).join('');

        return html;
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
    function updatePageInfo(info) {
        if (!info) {
            pageInfo.textContent = '';
            return;
        }
        const chars = info.length;
        if (chars > getMaxInlineChars()) {
            pageInfo.textContent = `${(chars / 1000).toFixed(1)}k chars (will ingest)`;
            pageInfo.className = 'page-info';
        } else {
            pageInfo.textContent = `${(chars / 1000).toFixed(1)}k chars`;
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
                            const maxAttempts = 60; // Max 2 minutes

                            while (attempts < maxAttempts) {
                                try {
                                    const statusResp = await fetch(
                                        `${apiUrl}/workspaces/${currentWorkspace}/ingest_status?job_id=${jobId}`
                                    );
                                    const status = await statusResp.json();

                                    if (status.status === 'completed' || status.status === 'done' || !status.status) {
                                        break;
                                    } else if (status.status === 'error' || status.status === 'failed') {
                                        throw new Error('Ingestion failed');
                                    }

                                    // Update progress
                                    if (status.progress !== undefined) {
                                        pageInfo.textContent = `Ingesting... ${Math.round(status.progress * 100)}%`;
                                    } else {
                                        pageInfo.textContent = `Ingesting... (${attempts + 1}s)`;
                                    }
                                } catch (pollError) {
                                    // If status endpoint returns 404 or error, assume done
                                    if (pollError.message.includes('404')) break;
                                    console.log('Poll check:', pollError.message);
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
        if (currentThread) {
            await loadMessages();
        } else {
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
            ingestBtn.title = 'Could not get page content';
            return;
        }

        ingestBtn.disabled = true;
        ingestBtn.title = 'Ingesting...';

        try {
            await chrome.runtime.sendMessage({
                action: 'ingestUrl',
                url: page.url,
                title: page.title,
                workspaceId: currentWorkspace
            });
            ingestBtn.title = 'Page ingested ✓';
            setTimeout(() => {
                ingestBtn.title = 'Ingest current page';
                ingestBtn.disabled = false;
            }, 3000);
        } catch (e) {
            ingestBtn.title = 'Ingest failed';
            ingestBtn.disabled = false;
        }
    });

    // Initialize
    await loadWorkspaces();
    updateInputState();
});
