import { create } from 'zustand';
import axios from 'axios';

// Get backend URL from localStorage, environment variable, or default
const getApiBase = () => {
    const stored = localStorage.getItem('mycelium_api_url');
    if (stored) return stored;
    return import.meta.env.VITE_API_BASE || 'http://localhost:8000';
};

let API_base = getApiBase();

/**
 * Parse thinking content from raw LLM output.
 * Handles both explicit (<think>...</think>) and implicit (no <think>, just </think>) thinking.
 * Returns { thinking, content, isThinking }
 */
function parseThinking(raw) {
    // Check for </think> which marks the end of thinking
    const closeIdx = raw.indexOf('</think>');
    if (closeIdx !== -1) {
        // Found end of thinking - split into thinking and response
        const openIdx = raw.indexOf('<think>');
        const thinkStart = (openIdx !== -1 && openIdx < closeIdx) ? openIdx + 7 : 0;
        const thinking = raw.slice(thinkStart, closeIdx).trim();
        const content = raw.slice(closeIdx + 8).trim(); // 8 = "</think>".length
        return { thinking, content, isThinking: false };
    }

    // No </think> yet - check if we're mid-thinking
    const openIdx = raw.indexOf('<think>');
    if (openIdx !== -1) {
        // Explicit <think> found but no </think> yet - still streaming thinking
        const content = raw.slice(0, openIdx);
        const thinking = raw.slice(openIdx + 7); // 7 = "<think>".length
        return { thinking, content, isThinking: true };
    }

    // No think tags at all - regular content
    return { thinking: '', content: raw, isThinking: false };
}

export const useStore = create((set, get) => ({
    workspaces: [],
    currentWorkspace: null,
    threads: [],
    currentThread: null,
    emotions: null, // { happiness, trust, anger }
    messages: [], // Chat messages for current session
    graphData: { nodes: [], links: [] },
    isLoading: false,
    workspaceLoading: false, // Track workspace switching loading state
    isUploading: false, // Separate flag for file uploads (doesn't block chat)
    initialLoading: true, // Track initial app loading state
    themeLoaded: false, // Track when theme has been applied
    API_BASE: API_base,

    // Set the backend API URL
    setApiBase: (url) => {
        const cleanUrl = url.replace(/\/$/, ''); // Remove trailing slash
        localStorage.setItem('mycelium_api_url', cleanUrl);
        API_base = cleanUrl;
        set({ API_BASE: cleanUrl });
    },

    // Get current API base (for components that need it)
    getApiBase: () => API_base,

    // View State
    activeView: 'chat',
    chatInput: '',

    // UI Settings (theme, font, etc.)
    uiSettings: {
        theme: 'dark',
        accent_color: '#8b5cf6',
        font_family: 'Inter',
        font_size: 'md',
        colorful_markdown: false,
        enabled_tabs: {
            chat: true,
            graph: true,
            notes: true,
            learn: true,
            concepts: true,
            hot_topics: true,
            connectors: true,
            grow: true,
            theWay: true,
            call: false
        },
    },
    setUiSettings: (settings) => set({ uiSettings: settings }),

    setActiveView: (view) => set({ activeView: view }),
    setChatInput: (input) => set({ chatInput: input }),

    fetchWorkspaces: async (retryCount = 0) => {
        const maxRetries = 5;
        const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 5000); // Exponential backoff, max 5s

        try {
            const res = await axios.get(`${API_base}/workspaces/`);
            set({ workspaces: res.data, initialLoading: false });

            // Auto-select: Prefer persisted ID, else first available
            const persistedWsId = localStorage.getItem('lastWorkspaceId');
            const found = persistedWsId ? res.data.find(w => w.id === persistedWsId) : null;

            if (found) {
                get().selectWorkspace(found);
            } else if (!get().currentWorkspace && res.data.length > 0) {
                get().selectWorkspace(res.data[0]);
            }
        } catch (e) {
            console.error("Fetch workspaces failed", e);
            // Retry with exponential backoff if backend not ready
            if (retryCount < maxRetries) {
                console.log(`Retrying in ${retryDelay}ms... (attempt ${retryCount + 1}/${maxRetries})`);
                setTimeout(() => {
                    get().fetchWorkspaces(retryCount + 1);
                }, retryDelay);
            } else {
                // Give up after max retries
                set({ initialLoading: false });
                console.error("Failed to connect to backend after multiple retries");
            }
        }
    },

    createWorkspace: async (id) => {
        try {
            const res = await axios.post(`${API_base}/workspaces/`, { workspace_id: id });
            set(state => ({ workspaces: [...state.workspaces, res.data] }));
            get().selectWorkspace(res.data);
        } catch (e) {
            console.error("Create workspace failed", e);
            alert("Failed to create workspace: " + (e.response?.data?.detail || e.message));
        }
    },

    deleteWorkspace: async (id) => {
        if (!confirm(`Delete workspace ${id}? This cannot be undone.`)) return;
        try {
            await axios.delete(`${API_base}/workspaces/${id}`);
            set(state => ({ workspaces: state.workspaces.filter(w => w.id !== id) }));
            if (get().currentWorkspace?.id === id) {
                set({ currentWorkspace: null, currentThread: null, messages: [], graphData: { nodes: [], links: [] } });
            }
        } catch (e) {
            console.error("Delete failed", e);
        }
    },

    renameWorkspace: async (oldId, newId) => {
        try {
            const res = await axios.post(`${API_base}/workspaces/${oldId}/rename`, { new_workspace_id: newId });

            set(state => ({
                workspaces: state.workspaces.map(w =>
                    w.id === oldId ? { ...w, id: newId } : w
                ),
                currentWorkspace: state.currentWorkspace?.id === oldId
                    ? { ...state.currentWorkspace, id: newId }
                    : state.currentWorkspace
            }));

            // Update persistence if active was renamed
            if (localStorage.getItem('lastWorkspaceId') === oldId) {
                localStorage.setItem('lastWorkspaceId', newId);
            }

            return true;
        } catch (e) {
            console.error("Rename failed", e);
            alert("Failed to rename workspace: " + (e.response?.data?.detail || e.message));
            return false;
        }
    },

    selectWorkspace: async (workspace) => {
        localStorage.setItem('lastWorkspaceId', workspace.id); // Persist
        set({ currentWorkspace: workspace, messages: [], graphData: { nodes: [], links: [] }, currentThread: null, emotions: null, workspaceLoading: true });
        try {
            await get().fetchGraph();
            await get().fetchThreads(workspace.id);
            await get().fetchEmotions();
        } finally {
            set({ workspaceLoading: false });
        }
    },

    fetchThreads: async (workspaceId) => {
        try {
            const res = await axios.get(`${API_base}/threads/${workspaceId}`);
            set({ threads: res.data });

            // Auto-select: Prefer persisted ID, else first, else new
            const persistedThreadId = localStorage.getItem('lastThreadId');
            const found = persistedThreadId ? res.data.find(t => t.id === persistedThreadId) : null;

            if (found) {
                get().selectThread(found);
            } else if (res.data.length > 0) {
                // If we didn't find the persisted one, pick the first
                get().selectThread(res.data[0]);
            } else {
                get().createThread(workspaceId, "General");
            }
        } catch (e) {
            console.error("Fetch threads failed", e);
        }
    },

    updateThreadTitle: async (workspaceId, threadId, title) => {
        // ... (existing implementation if any, or placeholder)
    },

    generateAudio: async (text) => {
        try {
            const response = await axios.post(`${API_base}/audio/speech`, { input: text }, {
                responseType: 'blob'
            });
            return response.data;
        } catch (error) {
            console.error('TTS Error:', error);
            return null;
        }
    },

    getAudioStreamUrl: (text) => {
        return `${API_base}/audio/stream?input=${encodeURIComponent(text)}`;
    },

    // --- Call (Voice Conversation) State ---
    callActive: false,
    callState: 'idle', // idle | connecting | listening | thinking | speaking
    callTranscript: '',
    callResponseText: '',
    callMessages: [],
    callError: null,
    _callWs: null,

    startCall: () => {
        const ws = get().currentWorkspace;
        const thread = get().currentThread;
        if (!ws || !thread) {
            set({ callError: 'Select a workspace and thread first' });
            return;
        }

        const wsUrl = `${API_base.replace(/^http/, 'ws')}/call/ws`;
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            socket.send(JSON.stringify({
                type: 'start_call',
                workspace_id: ws.id,
                thread_id: thread.id,
            }));
            set({ callActive: true, callState: 'connecting', _callWs: socket, callError: null, callMessages: [] });
        };

        socket.onmessage = (event) => {
            if (event.data instanceof Blob) {
                // Binary TTS audio — handled by CallArea component via onCallAudio listener
                const listeners = get()._callAudioListeners || [];
                listeners.forEach(fn => fn(event.data));
                return;
            }

            const msg = JSON.parse(event.data);
            switch (msg.type) {
                case 'call_started':
                    set({ callState: 'listening' });
                    break;
                case 'state':
                    set({ callState: msg.state });
                    break;
                case 'transcript':
                    if (msg.final) {
                        set(state => ({
                            callTranscript: '',
                            callMessages: [...state.callMessages, { role: 'user', content: msg.text }],
                        }));
                    } else {
                        set({ callTranscript: msg.text });
                    }
                    break;
                case 'response_text':
                    if (msg.done) {
                        set(state => ({
                            callMessages: [...state.callMessages, { role: 'assistant', content: state.callResponseText }],
                            callResponseText: '',
                        }));
                    } else {
                        set(state => ({ callResponseText: state.callResponseText + msg.text }));
                    }
                    break;
                case 'error':
                    set({ callError: msg.message });
                    break;
                case 'call_ended':
                    set({ callActive: false, callState: 'idle', _callWs: null });
                    break;
            }
        };

        socket.onerror = () => {
            set({ callError: 'WebSocket connection error', callActive: false, callState: 'idle', _callWs: null });
        };

        socket.onclose = () => {
            set({ callActive: false, callState: 'idle', _callWs: null });
        };
    },

    endCall: () => {
        const socket = get()._callWs;
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'end_call' }));
        }
        set({ callActive: false, callState: 'idle', _callWs: null, callResponseText: '' });
    },

    interruptCall: () => {
        const socket = get()._callWs;
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'interrupt' }));
        }
    },

    sendCallAudio: (pcmBuffer) => {
        const socket = get()._callWs;
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(pcmBuffer);
        }
    },

    sendVadSpeechEnd: () => {
        const socket = get()._callWs;
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'vad_speech_end' }));
        }
    },

    // Audio listener registry (CallArea registers to receive binary TTS blobs)
    _callAudioListeners: [],
    addCallAudioListener: (fn) => {
        set(state => ({ _callAudioListeners: [...state._callAudioListeners, fn] }));
    },
    removeCallAudioListener: (fn) => {
        set(state => ({ _callAudioListeners: state._callAudioListeners.filter(l => l !== fn) }));
    },

    createThread: async (workspaceId, title = "New Chat") => {
        try {
            const res = await axios.post(`${API_base}/threads/`, { workspace_id: workspaceId, title });
            set(state => ({ threads: [res.data, ...state.threads] }));
            get().selectThread(res.data);
        } catch (e) {
            console.error("Create thread failed", e);
        }
    },

    refreshThreadList: async () => {
        const ws = get().currentWorkspace;
        const current = get().currentThread;
        if (!ws) return;
        try {
            const res = await axios.get(`${API_base}/threads/${ws.id}`);
            set({ threads: res.data });
            if (current) {
                const fresh = res.data.find(t => t.id === current.id);
                if (fresh && fresh.title !== current.title) {
                    set(state => ({
                        currentThread: { ...state.currentThread, title: fresh.title }
                    }));
                }
            }
        } catch (e) {
            console.error("Refresh threads failed", e);
        }
    },

    deleteThread: async (threadId) => {
        if (!confirm("Delete this chat thread?")) return;
        const ws = get().currentWorkspace;
        if (!ws) return;

        try {
            await axios.delete(`${API_base}/threads/${ws.id}/${threadId}`);
            set(state => ({
                threads: state.threads.filter(t => t.id !== threadId),
                currentThread: state.currentThread?.id === threadId ? null : state.currentThread,
                messages: state.currentThread?.id === threadId ? [] : state.messages
            }));
            // If we deleted the active one, select another or create new
            const remaining = get().threads;
            if (remaining.length > 0) {
                get().selectThread(remaining[0]);
            } else {
                get().createThread(ws.id, "General");
            }
        } catch (e) {
            console.error("Delete thread failed", e);
        }
    },

    deleteAllThreads: async () => {
        if (!confirm("Delete all chat threads in this workspace? This cannot be undone.")) return;
        const ws = get().currentWorkspace;
        if (!ws) return;

        try {
            await axios.delete(`${API_base}/threads/${ws.id}`);
            set({
                threads: [],
                currentThread: null,
                messages: []
            });
            // Create a fresh "General" thread
            get().createThread(ws.id, "General");
        } catch (e) {
            console.error("Delete all threads failed", e);
        }
    },

    selectThread: async (thread) => {
        const ws = get().currentWorkspace;
        if (thread) localStorage.setItem('lastThreadId', thread.id); // Persist

        set({ currentThread: thread, messages: [] });
        if (!thread || !ws) return;

        try {
            const res = await axios.get(`${API_base}/threads/${ws.id}/${thread.id}/history`);
            set({ messages: res.data });
        } catch (e) {
            console.error("Load history failed", e);
        }
    },

    fetchGraph: async () => {
        const ws = get().currentWorkspace;
        if (!ws) return;
        try {
            const res = await axios.get(`${API_base}/graph/${ws.id}`);
            const data = res.data || {};
            const nodes = Array.isArray(data.nodes) ? data.nodes : [];
            // NetworkX v2.x returns 'links', newer versions or config might return 'edges'
            const links = Array.isArray(data.links) ? data.links : (Array.isArray(data.edges) ? data.edges : []);

            set({
                graphData: { nodes, links }
            });

            // Update workspace stats in the sidebar list
            const newNodeCount = nodes.length;
            const newEdgeCount = links.length;

            set(state => ({
                workspaces: state.workspaces.map(w =>
                    w.id === ws.id
                        ? { ...w, node_count: newNodeCount, edge_count: newEdgeCount }
                        : w
                )
            }));
        } catch (e) {
            console.error("Fetch graph failed", e);
        }
    },

    messageQueue: [],

    setMessageQueue: (queue) => set({ messageQueue: queue }),

    sendMessage: async (content) => {
        // Enqueue the message
        set(state => ({ messageQueue: [...state.messageQueue, content] }));

        // Try to process
        get().processChatQueue();
    },

    abortController: null,

    interruptGeneration: () => {
        const { abortController } = get();
        if (abortController) {
            abortController.abort();
        }
        set({
            messageQueue: [],
            isLoading: false,
            abortController: null,
            // Optional: Add a system message saying it was stopped?
            messages: [...get().messages, { role: 'system', content: 'Generation interrupted by user.' }]
        });
    },

    processChatQueue: async () => {
        const { isLoading, messageQueue, currentWorkspace, currentThread } = get();

        // If busy or empty, stop
        if (isLoading || messageQueue.length === 0) return;

        // Dequeue first message
        const content = messageQueue[0];
        set({ messageQueue: messageQueue.slice(1) });

        if (!currentWorkspace) {
            alert("No workspace selected.");
            return;
        }
        if (!currentThread) {
            alert("No chat thread selected.");
            return;
        }

        // Add User Message
        set(state => ({
            messages: [...state.messages, { role: 'user', content }],
            isLoading: true
        }));

        // Add Placeholder Assistant Message
        set(state => ({
            messages: [...state.messages, { role: 'assistant', content: '' }]
        }));

        let rawContent = "";  // Accumulated raw content from stream
        const controller = new AbortController();
        set({ abortController: controller });

        try {
            const response = await fetch(`${API_base}/threads/${currentWorkspace.id}/${currentThread.id}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: content }),
                signal: controller.signal
            });

            if (!response.body) {
                throw new Error("No response body");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                rawContent += chunk;

                // Parse thinking from accumulated raw content
                const parsed = parseThinking(rawContent);

                // Update UI incrementally
                set(state => {
                    const msgs = [...state.messages];
                    const lastMsg = msgs[msgs.length - 1];
                    if (lastMsg.role === 'assistant') {
                        lastMsg.content = parsed.content;
                        lastMsg.thinking = parsed.thinking || null;
                        lastMsg.isThinking = parsed.isThinking;
                    }
                    return { messages: msgs };
                });
            }

            // Final parse for post-stream checks
            const finalParsed = parseThinking(rawContent);

            // Post-stream updates
            get().fetchGraph();
            get().fetchEmotions();
            get().fetchNotesList();
            get().refreshThreadList();

            // Check if we generated a lesson
            if (finalParsed.content.includes("Learn tab") || finalParsed.content.includes("Lesson")) {
                get().fetchScripts();
            }

            // If deeper integration needed: Refetch active note if it exists
            const activeNote = get().activeNote;
            if (activeNote) {
                get().selectNote(activeNote.id);
            }

            setTimeout(() => get().fetchGraph(), 2000);

        } catch (e) {
            if (e.name === 'AbortError') {
                console.log("Chat generation aborted");
                return; // Exit cleanly, interruptGeneration handles state cleanup
            }
            console.error("Chat error", e);
            set(state => ({
                messages: [...state.messages, { role: 'system', content: `Error: ${e.message}` }]
            }));
        } finally {
            // Only process next if NOT aborted (if aborted, isLoading is already false via interruptGeneration)
            // But we need to be careful. interruptGeneration sets isLoading=false.
            // If we finish normally, we set isLoading=false here.

            // If we are still loading (meaning NOT aborted externally), we finish up.
            if (get().isLoading) {
                set({ isLoading: false, abortController: null });
                get().processChatQueue();
            }
        }
    },

    ingestJobs: [], // List of { job_id, status, current, total, filename }

    uploadFiles: async (files, settings = { chunkSize: 4800, chunkOverlap: 400 }) => {
        const ws = get().currentWorkspace;
        if (!ws || !files || files.length === 0) return;

        set({ isUploading: true });
        let pollInterval;

        try {
            // Initial poll to catch any existing jobs (optional, but good for cleanliness)
            await get().checkIngestStatus();

            // Start Polling
            pollInterval = setInterval(async () => {
                await get().checkIngestStatus();
            }, 1000);

            let successCount = 0;
            let failCount = 0;

            // Process uploads concurrently
            const uploadPromises = Array.from(files).map(async (file) => {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('chunk_size', settings.chunkSize);
                formData.append('chunk_overlap', settings.chunkOverlap);

                try {
                    await axios.post(`${API_base}/workspaces/${ws.id}/upload`, formData, {
                        headers: { 'Content-Type': 'multipart/form-data' }
                    });
                    successCount++;
                } catch (e) {
                    console.error(`Upload failed for ${file.name}`, e);
                    failCount++;
                }
            });

            await Promise.all(uploadPromises);

            if (failCount === 0) {
                alert(`Successfully uploaded ${successCount} file(s)!`);
            } else {
                alert(`Finished with ${successCount} success(es) and ${failCount} failure(s).`);
            }

            get().fetchGraph();
        } catch (e) {
            console.error("Batch upload failed", e);
            alert("Batch upload process encountered an error.");
        } finally {
            // Keep polling for a bit to ensure status updates clear out or complete
            setTimeout(() => {
                clearInterval(pollInterval);
                set({ isUploading: false });
                get().checkIngestStatus(); // Final status check
            }, 2000);
        }
    },

    uploadFile: async (file, settings) => {
        return get().uploadFiles([file], settings);
    },

    fetchWorkspaceSettings: async (id) => {
        try {
            const res = await axios.get(`${API_base}/workspaces/${id}/settings`);
            return res.data;
        } catch (e) {
            console.error("Fetch settings failed", e);
            return null;
        }
    },

    updateWorkspaceSettings: async (id, settings) => {
        try {
            const res = await axios.post(`${API_base}/workspaces/${id}/settings`, settings);
            return res.data;
        } catch (e) {
            console.error("Update settings failed", e);
            throw e;
        }
    },

    fetchAvailableTools: async () => {
        try {
            const res = await axios.get(`${API_base}/workspaces/available_tools`);
            return res.data;
        } catch (e) {
            console.error("Fetch available tools failed", e);
            return [];
        }
    },

    generateToolDescription: async (workspaceId) => {
        try {
            const res = await axios.post(`${API_base}/workspaces/${workspaceId}/generate_tool_description`);
            return res.data.description;
        } catch (e) {
            console.error("Generate tool description failed", e);
            return null;
        }
    },

    notesList: [],
    activeNote: null, // { id, title, content, updated_at }

    fetchNotesList: async (workspaceId) => {
        try {
            const res = await axios.get(`${API_base}/workspaces/${workspaceId}/notes`);
            set({ notesList: res.data });
        } catch (e) {
            console.error("Fetch notes list failed", e);
            set({ notesList: [] });
        }
    },

    selectNote: async (note) => {
        const ws = get().currentWorkspace;
        if (!ws || !note) return;

        // Optimistically set active note (content might be missing if just from list)
        set({ activeNote: note });

        try {
            const res = await axios.get(`${API_base}/workspaces/${ws.id}/notes/${note.id}`);
            set({ activeNote: res.data });
        } catch (e) {
            console.error("Fetch note content failed", e);
        }
    },

    createNote: async (title = "Untitled Note", content = "") => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        try {
            const res = await axios.post(`${API_base}/workspaces/${ws.id}/notes`, { title, content });
            const newNote = res.data;
            set(state => ({
                notesList: [newNote, ...state.notesList],
                activeNote: newNote
            }));
        } catch (e) {
            console.error("Create note failed", e);
        }
    },

    updateNote: async (noteId, title, content) => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        // Optimistic update
        set(state => ({
            activeNote: state.activeNote?.id === noteId ? { ...state.activeNote, title, content } : state.activeNote,
            notesList: state.notesList.map(n => n.id === noteId ? { ...n, title, updated_at: Date.now() / 1000 } : n)
        }));

        try {
            await axios.put(`${API_base}/workspaces/${ws.id}/notes/${noteId}`, { title, content });
        } catch (e) {
            console.error("Update note failed", e);
            // Revert or re-fetch?
            get().selectNote({ id: noteId }); // Re-fetch to sync
        }
    },

    deleteNote: async (noteId) => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        if (!confirm("Delete this note?")) return;

        try {
            await axios.delete(`${API_base}/workspaces/${ws.id}/notes/${noteId}`);
            set(state => ({
                notesList: state.notesList.filter(n => n.id !== noteId),
                activeNote: state.activeNote?.id === noteId ? null : state.activeNote
            }));
        } catch (e) {
            console.error("Delete note failed", e);
        }
    },

    // --- Skills (theWay) ---
    skillsList: [],
    activeSkill: null, // { id, title, summary, explanation, updated_at }

    fetchSkillsList: async (workspaceId) => {
        const ws = workspaceId || get().currentWorkspace?.id;
        if (!ws) return;
        try {
            const res = await axios.get(`${API_base}/workspaces/${ws}/skills`);
            set({ skillsList: res.data });
        } catch (e) {
            console.error("Fetch skills list failed", e);
            set({ skillsList: [] });
        }
    },

    selectSkill: async (skill) => {
        const ws = get().currentWorkspace;
        if (!ws || !skill) return;

        // Optimistically set active skill
        set({ activeSkill: skill });

        try {
            const res = await axios.get(`${API_base}/workspaces/${ws.id}/skills/${skill.id}`);
            set({ activeSkill: res.data });
        } catch (e) {
            console.error("Fetch skill content failed", e);
        }
    },

    createSkill: async (title = "New Skill", summary = "", explanation = "") => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        try {
            const res = await axios.post(`${API_base}/workspaces/${ws.id}/skills`, { title, summary, explanation });
            const newSkill = res.data;
            set(state => ({
                skillsList: [newSkill, ...state.skillsList],
                activeSkill: newSkill
            }));
        } catch (e) {
            console.error("Create skill failed", e);
        }
    },

    updateSkill: async (skillId, title, summary, explanation) => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        // Optimistic update
        set(state => ({
            activeSkill: state.activeSkill?.id === skillId
                ? { ...state.activeSkill, title, summary, explanation }
                : state.activeSkill,
            skillsList: state.skillsList.map(s =>
                s.id === skillId ? { ...s, title, summary, updated_at: Date.now() / 1000 } : s
            )
        }));

        try {
            await axios.put(`${API_base}/workspaces/${ws.id}/skills/${skillId}`, { title, summary, explanation });
        } catch (e) {
            console.error("Update skill failed", e);
            // Re-fetch to sync
            get().selectSkill({ id: skillId });
        }
    },

    deleteSkill: async (skillId) => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        if (!confirm("Delete this skill?")) return;

        try {
            await axios.delete(`${API_base}/workspaces/${ws.id}/skills/${skillId}`);
            set(state => ({
                skillsList: state.skillsList.filter(s => s.id !== skillId),
                activeSkill: state.activeSkill?.id === skillId ? null : state.activeSkill
            }));
        } catch (e) {
            console.error("Delete skill failed", e);
        }
    },

    fetchEmotions: async () => {
        const ws = get().currentWorkspace;
        if (!ws) return;
        try {
            const res = await axios.get(`${API_base}/workspaces/${ws.id}/emotions`);
            set({ emotions: res.data });
        } catch (e) {
            console.error("Fetch emotions failed", e);
        }
    },

    updateEmotions: async (emotions) => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        // Optimistic update
        set({ emotions });

        try {
            await axios.post(`${API_base}/workspaces/${ws.id}/emotions`, emotions);
        } catch (e) {
            console.error("Update emotions failed", e);
        }
    },

    generatePersona: async (cues) => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        try {
            const res = await axios.post(`${API_base}/workspaces/${ws.id}/generate_persona`, { cues });
            alert(res.data.message);
            // Refresh config, emotions, and graph
            get().fetchWorkspaceSettings(ws.id);
            get().fetchEmotions();
            get().fetchGraph();
        } catch (e) {
            console.error("Persona generation failed", e);
            alert("Failed to generate persona.");
        }
    },


    fetchSystemConfig: async () => {
        try {
            const res = await axios.get(`${API_base}/system/config`);
            const data = res.data;
            // Update UI settings in store when config is loaded
            if (data) {
                set({
                    uiSettings: {
                        theme: data.theme || 'dark',
                        accent_color: data.accent_color || '#8b5cf6',
                        font_family: data.font_family || 'Inter',
                        font_size: data.font_size || 'md',
                        colorful_markdown: data.colorful_markdown || false,
                        enabled_tabs: data.enabled_tabs || {
                            chat: true,
                            graph: true,
                            notes: true,
                            learn: true,
                            concepts: true,
                            hot_topics: true,
                            connectors: true,
                            grow: true,
                            theWay: true
                        },
                    }
                });
            }
            return data;
        } catch (e) {
            console.error("Fetch system config failed", e);
            return null;
        }
    },

    updateSystemConfig: async (config) => {
        try {
            const res = await axios.post(`${API_base}/system/config`, config);
            return res.data;
        } catch (e) {
            console.error("Update system config failed", e);
            throw e;
        }
    },

    // Knowledge Gaps state and actions
    knowledgeGaps: [],
    knowledgeGapsLoading: false,

    fetchKnowledgeGaps: async (limit = 10, maxDegree = 2) => {
        const ws = get().currentWorkspace;
        if (!ws) return [];

        set({ knowledgeGapsLoading: true });
        try {
            const res = await axios.get(`${API_base}/workspaces/${ws.id}/knowledge_gaps`, {
                params: { limit, max_degree: maxDegree }
            });
            set({ knowledgeGaps: res.data });
            return res.data;
        } catch (e) {
            console.error("Fetch knowledge gaps failed", e);
            set({ knowledgeGaps: [] });
            return [];
        } finally {
            set({ knowledgeGapsLoading: false });
        }
    },

    // Assign Singletons state and actions
    assignSingletonsLoading: false,
    assignSingletonsProposals: null, // { proposals: [...], logs: [...] }
    selectedProposalIds: [], // IDs of proposals user wants to execute

    previewAssignSingletons: async (n = 10) => {
        const ws = get().currentWorkspace;
        if (!ws) return null;

        const appendLog = (logObj) => {
            set(state => ({
                growLogs: {
                    ...state.growLogs,
                    [ws.id]: [...(state.growLogs[ws.id] || []), logObj]
                }
            }));
        };

        set({ assignSingletonsLoading: true, assignSingletonsProposals: null, selectedProposalIds: [] });
        appendLog({ type: 'info', text: `Analyzing ${n} singleton nodes...` });

        try {
            const params = new URLSearchParams({
                n: n,
                preview: true
            });

            const res = await axios.post(`${API_base}/workspaces/${ws.id}/assign_singletons?${params.toString()}`);

            // Append backend logs
            if (res.data.logs && Array.isArray(res.data.logs)) {
                res.data.logs.forEach(log => appendLog(log));
            }

            if (res.data.proposals && res.data.proposals.length > 0) {
                set({ assignSingletonsProposals: res.data });
                appendLog({ type: 'success', text: `Generated ${res.data.proposals.length} proposal(s).` });
            } else {
                appendLog({ type: 'info', text: 'No proposals generated.' });
            }

            return res.data;
        } catch (e) {
            console.error("Preview assign singletons failed", e);
            const errMsg = e.response?.data?.detail || e.message || "Unknown error";
            appendLog({ type: 'error', text: `Error: ${errMsg}` });
            return null;
        } finally {
            set({ assignSingletonsLoading: false });
        }
    },

    executeAssignSingletons: async () => {
        const ws = get().currentWorkspace;
        const proposals = get().assignSingletonsProposals?.proposals;
        const selectedIds = get().selectedProposalIds;
        if (!ws || !proposals || selectedIds.length === 0) return null;

        const appendLog = (logObj) => {
            set(state => ({
                growLogs: {
                    ...state.growLogs,
                    [ws.id]: [...(state.growLogs[ws.id] || []), logObj]
                }
            }));
        };

        set({ assignSingletonsLoading: true });
        appendLog({ type: 'info', text: `Executing ${selectedIds.length} selected proposal(s)...` });

        try {
            const res = await axios.post(`${API_base}/workspaces/${ws.id}/execute_singleton_proposals`, {
                proposal_ids: selectedIds,
                proposals: proposals
            });

            // Append backend logs
            if (res.data.logs && Array.isArray(res.data.logs)) {
                res.data.logs.forEach(log => appendLog(log));
            }

            appendLog({ type: 'success', text: res.data.message || 'Proposals executed.' });

            // Clear proposals and refresh graph
            set({ assignSingletonsProposals: null, selectedProposalIds: [] });
            get().fetchGraph();

            return res.data;
        } catch (e) {
            console.error("Execute assign singletons failed", e);
            const errMsg = e.response?.data?.detail || e.message || "Unknown error";
            appendLog({ type: 'error', text: `Error: ${errMsg}` });
            return null;
        } finally {
            set({ assignSingletonsLoading: false });
        }
    },

    toggleProposalSelection: (proposalId) => {
        set(state => {
            const current = state.selectedProposalIds;
            if (current.includes(proposalId)) {
                return { selectedProposalIds: current.filter(id => id !== proposalId) };
            } else {
                return { selectedProposalIds: [...current, proposalId] };
            }
        });
    },

    selectAllProposals: () => {
        const proposals = get().assignSingletonsProposals?.proposals || [];
        const allIds = proposals.filter(p => p.action !== 'skip').map(p => p.id);
        set({ selectedProposalIds: allIds });
    },

    deselectAllProposals: () => {
        set({ selectedProposalIds: [] });
    },

    clearAssignSingletonsPreview: () => set({ assignSingletonsProposals: null, selectedProposalIds: [] }),

    // Collapse Redundancy state and actions
    collapseRedundancyLoading: false,
    collapseRedundancyPreview: null, // { groups: [...] }

    previewCollapseRedundancy: async (n = 20, includeNeighbors = true) => {
        const ws = get().currentWorkspace;
        if (!ws) return null;

        const appendLog = (logObj) => {
            set(state => ({
                growLogs: {
                    ...state.growLogs,
                    [ws.id]: [...(state.growLogs[ws.id] || []), logObj]
                }
            }));
        };

        set({ collapseRedundancyLoading: true, collapseRedundancyPreview: null });
        appendLog({ type: 'info', text: `Analyzing top ${n} nodes for redundancy...` });

        try {
            const params = new URLSearchParams({
                n: n,
                include_neighbors: includeNeighbors,
                preview: true
            });

            const res = await axios.post(`${API_base}/workspaces/${ws.id}/collapse_redundancy?${params.toString()}`);

            // Append backend logs
            if (res.data.logs && Array.isArray(res.data.logs)) {
                res.data.logs.forEach(log => appendLog(log));
            }

            if (res.data.groups && res.data.groups.length > 0) {
                set({ collapseRedundancyPreview: res.data });
                appendLog({ type: 'success', text: `Found ${res.data.groups.length} group(s) of potential duplicates.` });
            } else {
                appendLog({ type: 'info', text: 'No duplicate nodes found.' });
            }

            return res.data;
        } catch (e) {
            console.error("Preview collapse redundancy failed", e);
            const errMsg = e.response?.data?.detail || e.message || "Unknown error";
            appendLog({ type: 'error', text: `Error: ${errMsg}` });
            return null;
        } finally {
            set({ collapseRedundancyLoading: false });
        }
    },

    executeCollapseRedundancy: async (n = 20, includeNeighbors = true) => {
        const ws = get().currentWorkspace;
        if (!ws) return null;

        const appendLog = (logObj) => {
            set(state => ({
                growLogs: {
                    ...state.growLogs,
                    [ws.id]: [...(state.growLogs[ws.id] || []), logObj]
                }
            }));
        };

        set({ collapseRedundancyLoading: true });
        appendLog({ type: 'info', text: `Executing merge...` });

        try {
            const params = new URLSearchParams({
                n: n,
                include_neighbors: includeNeighbors,
                preview: false
            });

            const res = await axios.post(`${API_base}/workspaces/${ws.id}/collapse_redundancy?${params.toString()}`);

            // Append backend logs
            if (res.data.logs && Array.isArray(res.data.logs)) {
                res.data.logs.forEach(log => appendLog(log));
            }

            appendLog({ type: 'success', text: res.data.message || 'Merge complete.' });

            // Clear preview and refresh graph
            set({ collapseRedundancyPreview: null });
            get().fetchGraph();

            return res.data;
        } catch (e) {
            console.error("Execute collapse redundancy failed", e);
            const errMsg = e.response?.data?.detail || e.message || "Unknown error";
            appendLog({ type: 'error', text: `Error: ${errMsg}` });
            return null;
        } finally {
            set({ collapseRedundancyLoading: false });
        }
    },

    clearCollapseRedundancyPreview: () => set({ collapseRedundancyPreview: null }),

    mergeSingleGroup: async (canonical, duplicates) => {
        const ws = get().currentWorkspace;
        if (!ws) return null;

        const appendLog = (logObj) => {
            set(state => ({
                growLogs: {
                    ...state.growLogs,
                    [ws.id]: [...(state.growLogs[ws.id] || []), logObj]
                }
            }));
        };

        appendLog({ type: 'info', text: `Merging ${duplicates.join(', ')} into '${canonical}'...` });

        try {
            const res = await axios.post(`${API_base}/workspaces/${ws.id}/merge_group`, {
                canonical,
                duplicates
            });

            appendLog({ type: 'success', text: res.data.message });

            // Remove this group from preview
            set(state => {
                if (!state.collapseRedundancyPreview?.groups) return state;
                const updatedGroups = state.collapseRedundancyPreview.groups.filter(
                    g => g.canonical !== canonical
                );
                return {
                    collapseRedundancyPreview: updatedGroups.length > 0
                        ? { ...state.collapseRedundancyPreview, groups: updatedGroups }
                        : null
                };
            });

            // Refresh graph
            get().fetchGraph();

            return res.data;
        } catch (e) {
            console.error("Merge single group failed", e);
            const errMsg = e.response?.data?.detail || e.message || "Unknown error";
            appendLog({ type: 'error', text: `Error: ${errMsg}` });
            return null;
        }
    },

    growLogs: {}, // { [workspaceId]: [] }


    grow: async (n, topic = null, save_to_notes = false, workspaceId = null, depth = 1) => {
        const ws = get().currentWorkspace;
        const targetId = workspaceId || ws?.id;

        if (!targetId) return;

        // Helper to update specific workspace logs
        const appendLog = (logObj) => {
            set(state => ({
                growLogs: {
                    ...state.growLogs,
                    [targetId]: [...(state.growLogs[targetId] || []), logObj]
                }
            }));
        };

        const appendLogs = (logsArray) => {
            set(state => ({
                growLogs: {
                    ...state.growLogs,
                    [targetId]: [...(state.growLogs[targetId] || []), ...logsArray]
                }
            }));
        };

        set({ isLoading: true });
        appendLog({ type: 'info', text: `Starting growth on "${topic || 'General'}" (n=${n}, depth=${depth})...` });

        try {
            // Generate Job ID
            const jobId = crypto.randomUUID();
            set({ contemplationJobId: jobId }); // Use existing ID field or rename if desired. Let's keep existing for now to minimize breakage unless asked.
            // Actually, let's rename it to growJobId if we want to be thorough. But for now I'll stick to contemplationJobId in state to avoid breaking other parts I haven't seen.

            const params = new URLSearchParams({
                n: n,
                save_to_notes: save_to_notes,
                depth: depth,
                job_id: jobId
            });
            if (topic) params.append('topic', topic);

            const url = `${API_base}/workspaces/${targetId}/contemplate?${params.toString()}`;
            const res = await axios.post(url);

            // Append backend logs if available
            if (res.data.logs && Array.isArray(res.data.logs)) {
                appendLogs(res.data.logs);
            }
            appendLog({ type: 'success', text: res.data.message });

            get().fetchGraph();
            if (save_to_notes) get().fetchNotesList(targetId);
        } catch (error) {
            console.error(error);
            if (error.response && error.response.data && error.response.data.logs) {
                appendLogs(error.response.data.logs);
                appendLog({ type: 'error', text: 'Growth failed/cancelled.' });
            } else {
                const errMsg = error.response?.data?.detail || error.message || "Unknown error";
                appendLog({ type: 'error', text: `Error: ${errMsg}` });
            }
        } finally {
            set({ isLoading: false, contemplationJobId: null });
        }
    },

    fetchModels: async () => {
        try {
            const res = await axios.get(`${API_base}/system/models`);
            if (res.data.models) {
                return res.data.models;
            }
            return [];
        } catch (e) {
            console.error("Fetch models failed", e);
            return [];
        }
    },

    scripts: [],
    fetchScripts: async () => {
        const ws = get().currentWorkspace;
        if (!ws) return;
        try {
            const res = await axios.get(`${API_base}/workspaces/${ws.id}/scripts`);
            set({ scripts: res.data });
        } catch (e) {
            console.error("Fetch scripts failed", e);
            set({ scripts: [] });
        }
    },

    generateScript: async (topic) => {
        const ws = get().currentWorkspace;
        if (!ws) return;
        try {
            const res = await axios.post(`${API_base}/workspaces/${ws.id}/scripts/generate`, { topic });
            // Prepend new script
            set(state => ({ scripts: [res.data, ...state.scripts] }));
            return res.data;
        } catch (e) {
            console.error("Generate script failed", e);
            throw e;
        }
    },

    deleteScript: async (scriptId) => {
        const ws = get().currentWorkspace;
        if (!ws) return;
        try {
            await axios.delete(`${API_base}/workspaces/${ws.id}/scripts/${scriptId}`);
            set(state => ({ scripts: state.scripts.filter(s => s.id !== scriptId) }));
        } catch (e) {
            console.error("Delete script failed", e);
            throw e;
        }
    },

    exportGraph: async () => {
        const ws = get().currentWorkspace;
        if (!ws) return;
        try {
            const response = await axios.get(`${API_base}/workspaces/${ws.id}/graph/export`, {
                responseType: 'blob',
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `graph_export_${ws.id}.json`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (e) {
            console.error("Export failed", e);
            alert("Failed to export graph.");
        }
    },

    importGraph: async (file) => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            set({ isLoading: true });
            const res = await axios.post(`${API_base}/workspaces/${ws.id}/graph/import`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            alert(`Success: ${res.data.message}`);
            // Force refresh of graph data
            await get().fetchGraph();
        } catch (e) {
            console.error("Import failed", e);
            alert("Failed to import graph: " + (e.response?.data?.detail || e.message));
            // Ensure local sync for updates (though backend reindex handles main logic)
        } finally {
            set({ isLoading: false });
        }
    },

    checkIngestStatus: async () => {
        const ws = get().currentWorkspace;
        if (!ws) return;
        try {
            const res = await axios.get(`${API_base}/workspaces/${ws.id}/ingest_status`);
            const data = res.data;
            // Expected data: { jobs: [ ... ] }
            if (data && data.jobs) {
                set({ ingestJobs: data.jobs });
            } else {
                set({ ingestJobs: [] });
            }
        } catch (e) {
            // prevent log spam
        }
    },

    stopIngest: async (jobId) => {
        const ws = get().currentWorkspace;
        if (!ws || !jobId) return;
        try {
            await axios.post(`${API_base}/workspaces/${ws.id}/ingest/stop?job_id=${jobId}`);
            // Optimistically update status to 'stopping...'
            const currentJobs = get().ingestJobs.map(job =>
                job.job_id === jobId ? { ...job, status: 'stopping...' } : job
            );
            set({ ingestJobs: currentJobs });
        } catch (e) {
            console.error("Stop ingest failed", e);
        }
    },

    // --- Graph Chat State ---
    graphChatMessages: [],
    graphChatFocusedNode: null,  // { id, type, description } of selected node
    highlightedNodes: [],  // Array of node IDs to highlight
    highlightedEdges: [],  // Array of { source, target } edges to highlight
    graphChatLoading: false,
    graphChatOpen: false,
    graphChatSettings: {
        k: 3,      // Number of nodes to retrieve
        depth: 1   // Traversal depth
    },

    setGraphChatOpen: (open) => set({ graphChatOpen: open }),

    setGraphChatFocusedNode: (node) => {
        set({ graphChatFocusedNode: node });
    },

    setGraphChatSettings: (settings) => {
        set(state => ({
            graphChatSettings: { ...state.graphChatSettings, ...settings }
        }));
    },

    clearGraphHighlights: () => {
        set({ highlightedNodes: [], highlightedEdges: [] });
    },

    clearGraphChat: () => {
        set({
            graphChatMessages: [],
            graphChatFocusedNode: null,
            highlightedNodes: [],
            highlightedEdges: []
        });
    },

    // Transfer graph chat messages to main chat and switch to chat view
    carryToMainChat: async () => {
        const graphMessages = get().graphChatMessages;
        const currentThread = get().currentThread;
        const ws = get().currentWorkspace;

        if (!ws || !currentThread || graphMessages.length === 0) return;

        // Format graph chat history as context for main chat
        const contextSummary = graphMessages
            .map(m => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`)
            .join('\n\n');

        const continuationMessage = `Continue this graph exploration conversation:\n\n---\n${contextSummary}\n---\n\nPlease continue helping me explore this topic.`;

        // Clear graph chat
        set({
            graphChatMessages: [],
            graphChatFocusedNode: null,
            highlightedNodes: [],
            highlightedEdges: [],
            graphChatOpen: false,
            activeView: 'chat'
        });

        // Send to main chat
        get().sendMessage(continuationMessage);
    },

    // Create a NEW thread with the exact graph chat messages as proper bubbles
    carryToNewChat: async () => {
        const graphMessages = get().graphChatMessages;
        const ws = get().currentWorkspace;
        const focusedNode = get().graphChatFocusedNode;

        if (!ws || graphMessages.length === 0) return;

        try {
            // Generate a title based on focused node or first message
            const title = focusedNode
                ? `Graph: ${focusedNode.id}`
                : `Graph Chat ${new Date().toLocaleDateString()}`;

            // Create a new thread with the exact messages
            const res = await axios.post(`${API_base}/threads/with_messages`, {
                workspace_id: ws.id,
                title: title,
                messages: graphMessages.map(m => ({
                    role: m.role,
                    content: m.content
                }))
            });

            const newThread = res.data;

            // Add to threads list and select it
            set(state => ({
                threads: [newThread, ...state.threads],
                currentThread: newThread,
                messages: graphMessages, // Set messages directly
                graphChatMessages: [],
                graphChatFocusedNode: null,
                highlightedNodes: [],
                highlightedEdges: [],
                graphChatOpen: false,
                activeView: 'chat'
            }));

        } catch (e) {
            console.error("Failed to create new chat from graph chat", e);
        }
    },

    sendGraphChatMessage: async (message) => {
        const ws = get().currentWorkspace;
        if (!ws) return;

        const focusedNode = get().graphChatFocusedNode;
        const settings = get().graphChatSettings;

        // Add user message
        set(state => ({
            graphChatMessages: [...state.graphChatMessages, { role: 'user', content: message }],
            graphChatLoading: true
        }));

        // Add placeholder for AI response
        set(state => ({
            graphChatMessages: [...state.graphChatMessages, { role: 'assistant', content: '' }]
        }));

        let rawContent = "";

        try {
            const response = await fetch(`${API_base}/graph/${ws.id}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    focused_node_id: focusedNode?.id || null,
                    k: settings.k,
                    depth: settings.depth
                })
            });

            if (!response.body) {
                throw new Error("No response body");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                rawContent += chunk;

                // Parse thinking from accumulated raw content (strip metadata marker for display)
                const withoutMeta = rawContent.split('###GRAPH_CONTEXT###')[0];
                const parsed = parseThinking(withoutMeta);

                set(state => {
                    const msgs = [...state.graphChatMessages];
                    const lastMsg = msgs[msgs.length - 1];
                    if (lastMsg.role === 'assistant') {
                        lastMsg.content = parsed.content;
                        lastMsg.thinking = parsed.thinking || null;
                        lastMsg.isThinking = parsed.isThinking;
                    }
                    return { graphChatMessages: msgs };
                });
            }

            // Parse metadata from the end of the raw content
            if (rawContent.includes('###GRAPH_CONTEXT###')) {
                const parts = rawContent.split('###GRAPH_CONTEXT###');
                const metadataStr = parts[1];
                const parsed = parseThinking(parts[0]);

                try {
                    const metadata = JSON.parse(metadataStr);
                    set({
                        highlightedNodes: metadata.retrieved_nodes || [],
                        highlightedEdges: metadata.retrieved_edges || []
                    });
                } catch (e) {
                    console.error("Failed to parse graph context metadata", e);
                }

                // Update final message content without metadata
                set(state => {
                    const msgs = [...state.graphChatMessages];
                    const lastMsg = msgs[msgs.length - 1];
                    if (lastMsg.role === 'assistant') {
                        lastMsg.content = parsed.content;
                    }
                    return { graphChatMessages: msgs };
                });
            }

        } catch (e) {
            console.error("Graph chat error", e);
            set(state => ({
                graphChatMessages: [...state.graphChatMessages, { role: 'system', content: `Error: ${e.message}` }]
            }));
        } finally {
            set({ graphChatLoading: false });
        }
    }
}));
