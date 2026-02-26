import React, { useState, useEffect } from 'react';
import { X, Save, Palette, Server, Volume2, Settings2, RefreshCw, Check, Plug, Plus, Trash2, Play, AlertCircle, Link, Layers, Brain } from 'lucide-react';
import { useStore } from '../store';
import { THEMES, applyThemeToDOM } from './ThemeProvider';
import { TAB_REGISTRY, DEFAULT_ENABLED_TABS } from '../tabRegistry';

const FONT_OPTIONS = [
    { value: 'Inter', label: 'Inter' },
    { value: 'Roboto', label: 'Roboto' },
    { value: 'Source Code Pro', label: 'Source Code Pro' },
    { value: 'JetBrains Mono', label: 'JetBrains Mono' },
    { value: 'system', label: 'System Default' },
];

const THEME_OPTIONS = [
    { value: 'dark', label: 'Dark', preview: { bg: '#0a0a0a', secondary: '#1f2937', text: '#f9fafb' } },
    { value: 'light', label: 'Light', preview: { bg: '#ffffff', secondary: '#f3f4f6', text: '#111827' } },
    { value: 'midnight', label: 'Midnight', preview: { bg: '#0f172a', secondary: '#334155', text: '#f1f5f9' } },
    { value: 'forest', label: 'Forest', preview: { bg: '#022c22', secondary: '#065f46', text: '#ecfdf5' } },
];

const ACCENT_PRESETS = [
    '#8b5cf6', // Purple
    '#3b82f6', // Blue
    '#10b981', // Green
    '#f59e0b', // Amber
    '#ef4444', // Red
    '#ec4899', // Pink
    '#06b6d4', // Cyan
    '#f97316', // Orange
];

const TabButton = ({ active, onClick, icon: Icon, children }) => (
    <button
        onClick={onClick}
        className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${active
            ? 'bg-accent text-white'
            : 'text-theme-muted hover:text-theme-primary hover:bg-theme-tertiary'
            }`}
        style={active ? { backgroundColor: 'var(--accent)' } : {}}
    >
        <Icon size={16} />
        {children}
    </button>
);

const AppSettingsModal = ({ onClose }) => {
    const { fetchSystemConfig, updateSystemConfig, fetchModels, setUiSettings, setApiBase, API_BASE } = useStore();
    const [availableModels, setAvailableModels] = useState([]);
    const [isFetchingModels, setIsFetchingModels] = useState(false);
    const [activeTab, setActiveTab] = useState('connection');
    const [isSaving, setIsSaving] = useState(false);

    // Connection state
    const [backendUrl, setBackendUrl] = useState(API_BASE);
    const [connectionStatus, setConnectionStatus] = useState(null); // null, 'loading', 'success', 'error'
    const [connectionError, setConnectionError] = useState('');

    // TTS state
    const [availableVoices, setAvailableVoices] = useState([]);
    const [ttsTestStatus, setTtsTestStatus] = useState(null); // null, 'loading', 'success', 'error'
    const [ttsTestDetail, setTtsTestDetail] = useState('');

    const [config, setConfig] = useState({
        provider: 'lmstudio',
        embedding_provider: 'lmstudio',
        chat_base_url: '',
        chat_api_key: '',
        chat_model: '',
        embedding_base_url: '',
        embedding_api_key: '',
        embedding_model: '',
        ollama_base_url: 'http://localhost:11434',
        ollama_chat_model: '',
        ollama_embedding_model: '',
        temperature: 0.7,
        // Ingestion LLM Settings
        ingestion_llm_enabled: false,
        ingestion_provider: 'lmstudio',
        ingestion_base_url: '',
        ingestion_api_key: '',
        ingestion_model: '',
        ingestion_ollama_model: '',
        // TTS Settings
        tts_base_url: '',
        tts_model: '',
        tts_voice: '',
        tts_enabled: false,
        // ASR Settings
        asr_enabled: false,
        asr_language: 'en',
        // UI Settings
        theme: 'dark',
        accent_color: '#8b5cf6',
        font_family: 'Inter',
        font_size: 'md',
        colorful_markdown: false,
        // Tab Visibility
        enabled_tabs: DEFAULT_ENABLED_TABS,
        // Memory Extraction
        memory_extraction_mode: 'immediate',
        buffer_turn_threshold: 5,
        buffer_token_threshold: 2000,
        buffer_time_threshold_seconds: 600,
        topic_similarity_threshold: 0.3,
        // MCP Servers
        mcp_servers: [],
    });

    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            const data = await fetchSystemConfig();
            if (data) {
                setConfig({
                    provider: data.provider || 'lmstudio',
                    embedding_provider: data.embedding_provider || data.provider || 'lmstudio',
                    chat_base_url: data.chat_base_url || '',
                    chat_api_key: data.chat_api_key || '',
                    chat_model: data.chat_model || '',
                    temperature: data.temperature !== undefined ? data.temperature : 0.7,
                    embedding_base_url: data.embedding_base_url || '',
                    embedding_api_key: data.embedding_api_key || '',
                    embedding_model: data.embedding_model || '',
                    ollama_base_url: data.ollama_base_url || 'http://localhost:11434',
                    ollama_chat_model: data.ollama_chat_model || '',
                    ollama_embedding_model: data.ollama_embedding_model || '',
                    // Ingestion LLM Settings
                    ingestion_llm_enabled: data.ingestion_llm_enabled || false,
                    ingestion_provider: data.ingestion_provider || 'lmstudio',
                    ingestion_base_url: data.ingestion_base_url || '',
                    ingestion_api_key: data.ingestion_api_key || '',
                    ingestion_model: data.ingestion_model || '',
                    ingestion_ollama_model: data.ingestion_ollama_model || '',
                    // TTS Settings
                    tts_base_url: data.tts_base_url || '',
                    tts_model: data.tts_model || '',
                    tts_voice: data.tts_voice || '',
                    tts_enabled: data.tts_enabled || false,
                    // ASR Settings
                    asr_enabled: data.asr_enabled || false,
                    asr_language: data.asr_language || 'en',
                    reddit_user_agent: data.reddit_user_agent || '',
                    // UI Settings
                    theme: data.theme || 'dark',
                    accent_color: data.accent_color || '#8b5cf6',
                    font_family: data.font_family || 'Inter',
                    font_size: data.font_size || 'md',
                    colorful_markdown: data.colorful_markdown || false,
                    enabled_tabs: data.enabled_tabs || DEFAULT_ENABLED_TABS,
                    // Memory Extraction
                    memory_extraction_mode: data.memory_extraction_mode || 'immediate',
                    buffer_turn_threshold: data.buffer_turn_threshold !== undefined ? data.buffer_turn_threshold : 5,
                    buffer_token_threshold: data.buffer_token_threshold !== undefined ? data.buffer_token_threshold : 2000,
                    buffer_time_threshold_seconds: data.buffer_time_threshold_seconds !== undefined ? data.buffer_time_threshold_seconds : 600,
                    topic_similarity_threshold: data.topic_similarity_threshold !== undefined ? data.topic_similarity_threshold : 0.3,
                    mcp_servers: data.mcp_servers || [],
                });
            }
            setIsLoading(false);
        };
        load();
    }, []);

    // Live preview of appearance changes
    useEffect(() => {
        applyThemeToDOM({
            theme: config.theme,
            accent_color: config.accent_color,
            font_family: config.font_family,
            font_size: config.font_size,
            colorful_markdown: config.colorful_markdown,
        });
    }, [config.theme, config.accent_color, config.font_family, config.font_size, config.colorful_markdown]);

    const handleFetchModels = async () => {
        setIsFetchingModels(true);
        const models = await fetchModels();
        setAvailableModels(models);
        setIsFetchingModels(false);
    };

    // Test backend connection
    const testConnection = async () => {
        const url = backendUrl.trim();
        if (!url) {
            setConnectionStatus('error');
            setConnectionError('Please enter a URL');
            return;
        }

        setConnectionStatus('loading');
        setConnectionError('');

        try {
            const response = await fetch(`${url}/system/health`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
            });

            if (response.ok) {
                setConnectionStatus('success');
            } else {
                setConnectionStatus('error');
                setConnectionError(`Server returned ${response.status}`);
            }
        } catch (e) {
            setConnectionStatus('error');
            setConnectionError(e.message || 'Connection failed');
        }
    };

    // MCP Server management
    const [newMcpServer, setNewMcpServer] = useState({ name: '', command: '', args: '', env: '' });
    const [testingServer, setTestingServer] = useState(null);
    const [testResult, setTestResult] = useState(null);

    const handleAddMcpServer = () => {
        if (!newMcpServer.name.trim() || !newMcpServer.command.trim()) {
            alert('Name and Command are required');
            return;
        }
        const serverConfig = {
            name: newMcpServer.name.trim(),
            command: newMcpServer.command.trim(),
            args: newMcpServer.args.split(' ').filter(s => s.trim()),
            env: newMcpServer.env ? Object.fromEntries(
                newMcpServer.env.split(',').map(pair => {
                    const [k, v] = pair.split('=').map(s => s.trim());
                    return [k, v];
                }).filter(([k, v]) => k && v)
            ) : {}
        };
        setConfig(c => ({ ...c, mcp_servers: [...c.mcp_servers, serverConfig] }));
        setNewMcpServer({ name: '', command: '', args: '', env: '' });
    };

    const handleRemoveMcpServer = (name) => {
        setConfig(c => ({ ...c, mcp_servers: c.mcp_servers.filter(s => s.name !== name) }));
    };

    const handleTestMcpServer = async (server) => {
        setTestingServer(server.name);
        setTestResult(null);
        try {
            const res = await fetch(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}/system/mcp/test`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(server)
            });
            const data = await res.json();
            setTestResult({ server: server.name, ...data });
        } catch (e) {
            setTestResult({ server: server.name, connected: false, error: e.message });
        } finally {
            setTestingServer(null);
        }
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            // Save backend URL first
            if (backendUrl.trim() !== API_BASE) {
                setApiBase(backendUrl.trim());
            }

            await updateSystemConfig({
                ...config,
                temperature: parseFloat(config.temperature),
                buffer_turn_threshold: parseInt(config.buffer_turn_threshold),
                buffer_token_threshold: parseInt(config.buffer_token_threshold),
                buffer_time_threshold_seconds: parseInt(config.buffer_time_threshold_seconds),
                topic_similarity_threshold: parseFloat(config.topic_similarity_threshold),
            });
            // Update UI settings in store for persistence
            setUiSettings({
                theme: config.theme,
                accent_color: config.accent_color,
                font_family: config.font_family,
                font_size: config.font_size,
                colorful_markdown: config.colorful_markdown,
                enabled_tabs: config.enabled_tabs,
            });
            onClose();
        } catch (e) {
            alert("Failed to save settings");
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.8)' }}>
            <div
                className="rounded-xl w-full max-w-2xl overflow-hidden shadow-2xl border"
                style={{
                    backgroundColor: 'var(--bg-secondary)',
                    borderColor: 'var(--border-color)'
                }}
            >
                {/* Header */}
                <div
                    className="p-4 border-b flex items-center justify-between"
                    style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                >
                    <h2 className="text-lg font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                        <Settings2 size={20} style={{ color: 'var(--accent)' }} />
                        Settings
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-1 rounded hover:bg-theme-tertiary transition-colors"
                        style={{ color: 'var(--text-muted)' }}
                    >
                        <X size={20} />
                    </button>
                </div>

                <div
                    className="flex gap-2 p-3 border-b overflow-x-auto"
                    style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                >
                    <TabButton active={activeTab === 'connection'} onClick={() => setActiveTab('connection')} icon={Link}>
                        Connection
                    </TabButton>
                    <TabButton active={activeTab === 'llm'} onClick={() => setActiveTab('llm')} icon={Server}>
                        LLM
                    </TabButton>
                    <TabButton active={activeTab === 'tts'} onClick={() => setActiveTab('tts')} icon={Volume2}>
                        TTS
                    </TabButton>
                    <TabButton active={activeTab === 'appearance'} onClick={() => setActiveTab('appearance')} icon={Palette}>
                        Appearance
                    </TabButton>
                    <TabButton active={activeTab === 'mcp'} onClick={() => setActiveTab('mcp')} icon={Plug}>
                        MCP
                    </TabButton>
                    <TabButton active={activeTab === 'tabs'} onClick={() => setActiveTab('tabs')} icon={Layers}>
                        Tabs
                    </TabButton>
                </div>

                {/* Tab Content */}
                <div className="p-6 max-h-[60vh] overflow-y-auto custom-scrollbar">

                    {/* CONNECTION TAB */}
                    {activeTab === 'connection' && (
                        <div className="space-y-6">
                            <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <h4 className="text-sm font-bold" style={{ color: 'var(--accent)' }}>Backend Connection</h4>
                                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                    Configure the URL where your Mycelium backend is running.
                                </p>

                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>API URL</label>
                                    <div className="flex gap-2">
                                        <input
                                            className="flex-1 p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                            value={backendUrl}
                                            onChange={e => setBackendUrl(e.target.value)}
                                            placeholder="http://localhost:8000"
                                        />
                                        <button
                                            onClick={testConnection}
                                            disabled={connectionStatus === 'loading'}
                                            className="px-4 py-2 rounded border text-sm font-medium transition-colors disabled:opacity-50"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-secondary)' }}
                                        >
                                            {connectionStatus === 'loading' ? (
                                                <RefreshCw size={16} className="animate-spin" />
                                            ) : (
                                                'Test'
                                            )}
                                        </button>
                                    </div>
                                </div>

                                {/* Connection Status */}
                                {connectionStatus && connectionStatus !== 'loading' && (
                                    <div className={`p-3 rounded flex items-start gap-2 ${connectionStatus === 'success' ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                                        {connectionStatus === 'success' ? (
                                            <Check size={16} className="text-green-500 mt-0.5" />
                                        ) : (
                                            <AlertCircle size={16} className="text-red-500 mt-0.5" />
                                        )}
                                        <div className="flex-1">
                                            <div className="text-sm font-medium" style={{ color: connectionStatus === 'success' ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)' }}>
                                                {connectionStatus === 'success' ? 'Connected successfully!' : 'Connection failed'}
                                            </div>
                                            {connectionError && (
                                                <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{connectionError}</div>
                                            )}
                                        </div>
                                    </div>
                                )}

                                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                    Changes will be applied after saving. The page may need to be refreshed for all features to use the new URL.
                                </p>
                            </div>
                        </div>
                    )}

                    {activeTab === 'appearance' && (
                        <div className="space-y-6">
                            {/* Theme Selection */}
                            <div>
                                <label className="block text-sm font-bold mb-3" style={{ color: 'var(--text-muted)' }}>
                                    Theme
                                </label>
                                <div className="grid grid-cols-4 gap-3">
                                    {THEME_OPTIONS.map(theme => (
                                        <button
                                            key={theme.value}
                                            onClick={() => setConfig({ ...config, theme: theme.value })}
                                            className={`relative p-3 rounded-lg border-2 transition-all ${config.theme === theme.value
                                                ? 'ring-2 ring-offset-2'
                                                : 'hover:scale-105'
                                                }`}
                                            style={{
                                                backgroundColor: theme.preview.bg,
                                                borderColor: config.theme === theme.value ? 'var(--accent)' : theme.preview.secondary,
                                                '--tw-ring-color': 'var(--accent)',
                                                '--tw-ring-offset-color': 'var(--bg-secondary)',
                                            }}
                                        >
                                            <div
                                                className="h-8 rounded mb-2"
                                                style={{ backgroundColor: theme.preview.secondary }}
                                            />
                                            <span
                                                className="text-xs font-medium"
                                                style={{ color: theme.preview.text }}
                                            >
                                                {theme.label}
                                            </span>
                                            {config.theme === theme.value && (
                                                <div
                                                    className="absolute top-1 right-1 w-5 h-5 rounded-full flex items-center justify-center"
                                                    style={{ backgroundColor: 'var(--accent)' }}
                                                >
                                                    <Check size={12} className="text-white" />
                                                </div>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Accent Color */}
                            <div>
                                <label className="block text-sm font-bold mb-3" style={{ color: 'var(--text-muted)' }}>
                                    Accent Color
                                </label>
                                <div className="flex items-center gap-3">
                                    <div className="flex gap-2">
                                        {ACCENT_PRESETS.map(color => (
                                            <button
                                                key={color}
                                                onClick={() => setConfig({ ...config, accent_color: color })}
                                                className={`w-8 h-8 rounded-full transition-all ${config.accent_color === color
                                                    ? 'ring-2 ring-offset-2 scale-110'
                                                    : 'hover:scale-110'
                                                    }`}
                                                style={{
                                                    backgroundColor: color,
                                                    '--tw-ring-color': color,
                                                    '--tw-ring-offset-color': 'var(--bg-secondary)',
                                                }}
                                            />
                                        ))}
                                    </div>
                                    <div className="flex items-center gap-2 ml-4">
                                        <input
                                            type="color"
                                            value={config.accent_color}
                                            onChange={e => setConfig({ ...config, accent_color: e.target.value })}
                                            className="w-8 h-8 rounded cursor-pointer border-0"
                                        />
                                        <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                                            {config.accent_color}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Font Family */}
                            <div>
                                <label className="block text-sm font-bold mb-3" style={{ color: 'var(--text-muted)' }}>
                                    Font Family
                                </label>
                                <select
                                    value={config.font_family}
                                    onChange={e => setConfig({ ...config, font_family: e.target.value })}
                                    className="w-full p-3 rounded-lg border text-sm focus:outline-none focus:ring-2"
                                    style={{
                                        backgroundColor: 'var(--bg-primary)',
                                        borderColor: 'var(--border-color)',
                                        color: 'var(--text-primary)',
                                        '--tw-ring-color': 'var(--accent)',
                                    }}
                                >
                                    {FONT_OPTIONS.map(font => (
                                        <option key={font.value} value={font.value} style={{ fontFamily: font.value }}>
                                            {font.label}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Font Size */}
                            <div>
                                <label className="block text-sm font-bold mb-3" style={{ color: 'var(--text-muted)' }}>
                                    Font Size
                                </label>
                                <div className="flex gap-3">
                                    {[
                                        { value: 'sm', label: 'Small' },
                                        { value: 'md', label: 'Medium' },
                                        { value: 'lg', label: 'Large' },
                                    ].map(size => (
                                        <button
                                            key={size.value}
                                            onClick={() => setConfig({ ...config, font_size: size.value })}
                                            className={`flex-1 py-2 px-4 rounded-lg border text-sm font-medium transition-all`}
                                            style={{
                                                backgroundColor: config.font_size === size.value ? 'var(--accent)' : 'var(--bg-primary)',
                                                borderColor: config.font_size === size.value ? 'var(--accent)' : 'var(--border-color)',
                                                color: config.font_size === size.value ? 'white' : 'var(--text-secondary)',
                                            }}
                                        >
                                            {size.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Colorful Markdown Toggle */}
                            <div className="flex items-center justify-between p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <div>
                                    <h4 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Colorful Markdown</h4>
                                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Color different markdown elements using accent color palette</p>
                                </div>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={config.colorful_markdown}
                                        onChange={e => setConfig({ ...config, colorful_markdown: e.target.checked })}
                                        className="sr-only peer"
                                    />
                                    <div
                                        className="w-11 h-6 rounded-full peer after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"
                                        style={{
                                            backgroundColor: config.colorful_markdown ? 'var(--accent)' : 'var(--bg-tertiary)',
                                        }}
                                    />
                                </label>
                            </div>


                        </div>
                    )}

                    {/* LLM TAB */}
                    {activeTab === 'llm' && (
                        <div className="space-y-6">
                            {/* Chat LLM Provider Selection */}
                            <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <h4 className="text-sm font-bold" style={{ color: 'var(--accent)' }}>Chat / LLM</h4>
                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Provider</label>
                                    <select
                                        className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                        style={{
                                            backgroundColor: 'var(--bg-tertiary)',
                                            borderColor: 'var(--border-color)',
                                            color: 'var(--text-primary)',
                                            '--tw-ring-color': 'var(--accent)',
                                        }}
                                        value={config.provider || 'lmstudio'}
                                        onChange={e => setConfig({ ...config, provider: e.target.value })}
                                    >
                                        <option value="ollama">Ollama (Local)</option>
                                        <option value="lmstudio">LM Studio (Local)</option>
                                        <option value="openai">OpenAI (Cloud)</option>
                                    </select>
                                </div>

                                {/* Ollama LLM Settings */}
                                {config.provider === 'ollama' && (
                                    <>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Base URL</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.ollama_base_url || ''}
                                                onChange={e => setConfig({ ...config, ollama_base_url: e.target.value })}
                                                placeholder="http://localhost:11434"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Chat Model</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.ollama_chat_model || ''}
                                                onChange={e => setConfig({ ...config, ollama_chat_model: e.target.value })}
                                                placeholder="llama3.2"
                                            />
                                        </div>
                                    </>
                                )}

                                {/* OpenAI/LM Studio LLM Settings */}
                                {config.provider !== 'ollama' && (
                                    <>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Base URL</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.chat_base_url || ''}
                                                onChange={e => setConfig({ ...config, chat_base_url: e.target.value })}
                                                placeholder={config.provider === 'openai' ? "https://api.openai.com/v1" : "http://localhost:1234/v1"}
                                            />
                                        </div>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>API Key</label>
                                                <input
                                                    type="password"
                                                    className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                    value={config.chat_api_key || ''}
                                                    onChange={e => setConfig({ ...config, chat_api_key: e.target.value })}
                                                    placeholder={config.provider === 'openai' ? "sk-..." : "lm-studio"}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Model</label>
                                                <div className="flex gap-2">
                                                    <input
                                                        className="flex-1 p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                        style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                        value={config.chat_model || ''}
                                                        onChange={e => setConfig({ ...config, chat_model: e.target.value })}
                                                        list="model-options"
                                                        placeholder="Model name..."
                                                    />
                                                    <datalist id="model-options">
                                                        {availableModels.map(m => <option key={m} value={m} />)}
                                                    </datalist>
                                                    <button
                                                        onClick={handleFetchModels}
                                                        disabled={isFetchingModels}
                                                        className="p-2 rounded border transition-colors"
                                                        style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}
                                                        title="Fetch Models"
                                                    >
                                                        <RefreshCw size={16} className={isFetchingModels ? "animate-spin" : ""} />
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </>
                                )}
                            </div>

                            {/* Embedding Provider Selection */}
                            <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <h4 className="text-sm font-bold" style={{ color: 'var(--accent)' }}>Embeddings</h4>
                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Provider</label>
                                    <select
                                        className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                        style={{
                                            backgroundColor: 'var(--bg-tertiary)',
                                            borderColor: 'var(--border-color)',
                                            color: 'var(--text-primary)',
                                            '--tw-ring-color': 'var(--accent)',
                                        }}
                                        value={config.embedding_provider || 'lmstudio'}
                                        onChange={e => setConfig({ ...config, embedding_provider: e.target.value })}
                                    >
                                        <option value="ollama">Ollama (Local)</option>
                                        <option value="lmstudio">LM Studio (Local)</option>
                                        <option value="openai">OpenAI (Cloud)</option>
                                    </select>
                                </div>

                                {/* Ollama Embedding Settings */}
                                {config.embedding_provider === 'ollama' && (
                                    <>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Base URL</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.ollama_base_url || ''}
                                                onChange={e => setConfig({ ...config, ollama_base_url: e.target.value })}
                                                placeholder="http://localhost:11434"
                                            />
                                            <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Shared with LLM if using Ollama for both</p>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Embedding Model</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.ollama_embedding_model || ''}
                                                onChange={e => setConfig({ ...config, ollama_embedding_model: e.target.value })}
                                                placeholder="nomic-embed-text"
                                            />
                                        </div>
                                    </>
                                )}

                                {/* OpenAI/LM Studio Embedding Settings */}
                                {config.embedding_provider !== 'ollama' && (
                                    <>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Base URL</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.embedding_base_url || ''}
                                                onChange={e => setConfig({ ...config, embedding_base_url: e.target.value })}
                                                placeholder="http://localhost:1234/v1"
                                            />
                                        </div>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>API Key</label>
                                                <input
                                                    type="password"
                                                    className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                    value={config.embedding_api_key || ''}
                                                    onChange={e => setConfig({ ...config, embedding_api_key: e.target.value })}
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Model</label>
                                                <input
                                                    className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                    value={config.embedding_model || ''}
                                                    onChange={e => setConfig({ ...config, embedding_model: e.target.value })}
                                                />
                                            </div>
                                        </div>
                                    </>
                                )}
                            </div>

                            {/* Ingestion LLM (Optional) */}
                            <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h4 className="text-sm font-bold" style={{ color: 'var(--accent)' }}>Ingestion LLM</h4>
                                        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Use a separate model for graph building (optional)</p>
                                    </div>
                                    <label className="relative inline-flex items-center cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={config.ingestion_llm_enabled}
                                            onChange={e => setConfig({ ...config, ingestion_llm_enabled: e.target.checked })}
                                            className="sr-only peer"
                                        />
                                        <div
                                            className="w-11 h-6 rounded-full peer after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"
                                            style={{
                                                backgroundColor: config.ingestion_llm_enabled ? 'var(--accent)' : 'var(--bg-tertiary)',
                                            }}
                                        />
                                    </label>
                                </div>

                                {config.ingestion_llm_enabled && (
                                    <>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Provider</label>
                                            <select
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{
                                                    backgroundColor: 'var(--bg-tertiary)',
                                                    borderColor: 'var(--border-color)',
                                                    color: 'var(--text-primary)',
                                                    '--tw-ring-color': 'var(--accent)',
                                                }}
                                                value={config.ingestion_provider || 'lmstudio'}
                                                onChange={e => setConfig({ ...config, ingestion_provider: e.target.value })}
                                            >
                                                <option value="ollama">Ollama (Local)</option>
                                                <option value="lmstudio">LM Studio (Local)</option>
                                                <option value="openai">OpenAI (Cloud)</option>
                                            </select>
                                        </div>

                                        {/* Ollama Ingestion Settings */}
                                        {config.ingestion_provider === 'ollama' && (
                                            <div>
                                                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Ingestion Model</label>
                                                <input
                                                    className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                    value={config.ingestion_ollama_model || ''}
                                                    onChange={e => setConfig({ ...config, ingestion_ollama_model: e.target.value })}
                                                    placeholder="llama3.2"
                                                />
                                                <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Uses shared Ollama Base URL</p>
                                            </div>
                                        )}

                                        {/* OpenAI/LM Studio Ingestion Settings */}
                                        {config.ingestion_provider !== 'ollama' && (
                                            <>
                                                <div>
                                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Base URL</label>
                                                    <input
                                                        className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                        style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                        value={config.ingestion_base_url || ''}
                                                        onChange={e => setConfig({ ...config, ingestion_base_url: e.target.value })}
                                                        placeholder={config.ingestion_provider === 'openai' ? "https://api.openai.com/v1" : "http://localhost:1234/v1"}
                                                    />
                                                </div>
                                                <div className="grid grid-cols-2 gap-4">
                                                    <div>
                                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>API Key</label>
                                                        <input
                                                            type="password"
                                                            className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                            value={config.ingestion_api_key || ''}
                                                            onChange={e => setConfig({ ...config, ingestion_api_key: e.target.value })}
                                                            placeholder={config.ingestion_provider === 'openai' ? "sk-..." : "lm-studio"}
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Model</label>
                                                        <div className="flex gap-2">
                                                            <input
                                                                className="flex-1 p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                                value={config.ingestion_model || ''}
                                                                onChange={e => setConfig({ ...config, ingestion_model: e.target.value })}
                                                                list="ingestion-model-options"
                                                                placeholder="Model name..."
                                                            />
                                                            <datalist id="ingestion-model-options">
                                                                {availableModels.map(m => <option key={m} value={m} />)}
                                                            </datalist>
                                                            <button
                                                                onClick={handleFetchModels}
                                                                disabled={isFetchingModels}
                                                                className="p-2 rounded border transition-colors"
                                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}
                                                                title="Fetch Models"
                                                            >
                                                                <RefreshCw size={16} className={isFetchingModels ? "animate-spin" : ""} />
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </>
                                        )}
                                    </>
                                )}
                            </div>

                            {/* Temperature */}
                            <div>
                                <label className="block text-sm font-bold mb-2" style={{ color: 'var(--text-muted)' }}>
                                    Temperature: {config.temperature}
                                </label>
                                <input
                                    type="range"
                                    min="0" max="1" step="0.1"
                                    className="w-full h-2 rounded-lg appearance-none cursor-pointer"
                                    style={{
                                        backgroundColor: 'var(--bg-tertiary)',
                                        accentColor: 'var(--accent)',
                                    }}
                                    value={config.temperature || 0.7}
                                    onChange={e => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                                />
                            </div>

                            {/* Thinking Model Support */}
                            <div className="flex items-center justify-between p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <div>
                                    <h4 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Thinking Display</h4>
                                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Show reasoning from models that use &lt;think&gt; tags (QwQ, Qwen3, DeepSeek R1)</p>
                                </div>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={config.thinking_enabled ?? true}
                                        onChange={e => setConfig({ ...config, thinking_enabled: e.target.checked })}
                                        className="sr-only peer"
                                    />
                                    <div className="w-11 h-6 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:rounded-full after:h-5 after:w-5 after:transition-all"
                                        style={{
                                            backgroundColor: config.thinking_enabled ?? true ? 'var(--accent)' : 'var(--bg-tertiary)',
                                        }}>
                                        <div className={`absolute top-[2px] ${config.thinking_enabled ?? true ? 'left-[22px]' : 'left-[2px]'} w-5 h-5 rounded-full transition-all`}
                                            style={{ backgroundColor: 'var(--text-primary)' }} />
                                    </div>
                                </label>
                            </div>
                            {/* Memory Extraction */}
                            <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <h4 className="text-sm font-bold flex items-center gap-2" style={{ color: 'var(--accent)' }}>
                                    <Brain size={14} />
                                    Memory Extraction
                                </h4>
                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Extraction Mode</label>
                                    <select
                                        className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                        style={{
                                            backgroundColor: 'var(--bg-tertiary)',
                                            borderColor: 'var(--border-color)',
                                            color: 'var(--text-primary)',
                                            '--tw-ring-color': 'var(--accent)',
                                        }}
                                        value={config.memory_extraction_mode}
                                        onChange={e => setConfig({ ...config, memory_extraction_mode: e.target.value })}
                                    >
                                        <option value="immediate">Immediate (per-turn)</option>
                                        <option value="buffered">Buffered (LightMem)</option>
                                    </select>
                                    <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>
                                        Buffered mode batches turns by topic before extraction, reducing API calls.
                                    </p>
                                </div>

                                <div className={`space-y-3 transition-opacity ${config.memory_extraction_mode !== 'buffered' ? 'opacity-40 pointer-events-none' : ''}`}>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Turn Threshold</label>
                                            <input
                                                type="number"
                                                min="2" max="20" step="1"
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.buffer_turn_threshold}
                                                onChange={e => setConfig({ ...config, buffer_turn_threshold: e.target.value })}
                                            />
                                            <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>Turns before flush</p>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Token Threshold</label>
                                            <input
                                                type="number"
                                                min="500" max="10000" step="100"
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.buffer_token_threshold}
                                                onChange={e => setConfig({ ...config, buffer_token_threshold: e.target.value })}
                                            />
                                            <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>Est. tokens before flush</p>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Time Threshold (sec)</label>
                                            <input
                                                type="number"
                                                min="60" max="3600" step="60"
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.buffer_time_threshold_seconds}
                                                onChange={e => setConfig({ ...config, buffer_time_threshold_seconds: e.target.value })}
                                            />
                                            <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>Max idle time before flush</p>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
                                                Topic Similarity ({config.topic_similarity_threshold})
                                            </label>
                                            <input
                                                type="range"
                                                min="0.1" max="0.8" step="0.05"
                                                className="w-full h-2 rounded-lg appearance-none cursor-pointer mt-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', accentColor: 'var(--accent)' }}
                                                value={config.topic_similarity_threshold}
                                                onChange={e => setConfig({ ...config, topic_similarity_threshold: parseFloat(e.target.value) })}
                                            />
                                            <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>Lower = more segments</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* TTS TAB */}
                    {activeTab === 'tts' && (
                        <div className="space-y-6">
                            <div className="flex items-center justify-between p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <div>
                                    <h4 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Enable Text-to-Speech</h4>
                                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Play AI responses aloud</p>
                                </div>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={config.tts_enabled}
                                        onChange={e => setConfig({ ...config, tts_enabled: e.target.checked })}
                                        className="sr-only peer"
                                    />
                                    <div
                                        className="w-11 h-6 rounded-full peer after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"
                                        style={{
                                            backgroundColor: config.tts_enabled ? 'var(--accent)' : 'var(--bg-tertiary)',
                                        }}
                                    />
                                </label>
                            </div>

                            {config.tts_enabled && (
                                <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                    <div>
                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Base URL</label>
                                        <input
                                            className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                            value={config.tts_base_url || ''}
                                            onChange={e => setConfig({ ...config, tts_base_url: e.target.value })}
                                            placeholder="http://tts:8100/v1"
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Model</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.tts_model || ''}
                                                onChange={e => setConfig({ ...config, tts_model: e.target.value })}
                                                placeholder="VibeVoice-Realtime-0.5B"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Voice</label>
                                            {availableVoices.length > 0 ? (
                                                <select
                                                    className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                    value={config.tts_voice || ''}
                                                    onChange={e => setConfig({ ...config, tts_voice: e.target.value })}
                                                >
                                                    {!config.tts_voice && <option value="">Select a voice...</option>}
                                                    {availableVoices.map(v => (
                                                        <option key={v} value={v}>{v}</option>
                                                    ))}
                                                </select>
                                            ) : (
                                                <input
                                                    className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                    value={config.tts_voice || ''}
                                                    onChange={e => setConfig({ ...config, tts_voice: e.target.value })}
                                                    placeholder="en-Emma_woman"
                                                />
                                            )}
                                        </div>
                                    </div>
                                    <button
                                        className="w-full mt-3 px-4 py-2 rounded text-sm font-medium transition-colors flex items-center justify-center gap-2"
                                        style={{
                                            backgroundColor: ttsTestStatus === 'success' ? 'var(--bg-tertiary)' : 'var(--bg-tertiary)',
                                            color: ttsTestStatus === 'success' ? '#10b981' : ttsTestStatus === 'error' ? '#ef4444' : 'var(--text-secondary)',
                                            border: `1px solid ${ttsTestStatus === 'success' ? '#10b981' : ttsTestStatus === 'error' ? '#ef4444' : 'var(--border-color)'}`
                                        }}
                                        disabled={ttsTestStatus === 'loading'}
                                        onClick={async () => {
                                            setTtsTestStatus('loading');
                                            setTtsTestDetail('');
                                            try {
                                                const res = await fetch(`${API_BASE}/audio/test`);
                                                if (!res.ok) {
                                                    setTtsTestStatus('error');
                                                    setTtsTestDetail(`Backend returned ${res.status}`);
                                                    return;
                                                }
                                                const data = await res.json();
                                                if (data.status === 'connected') {
                                                    setTtsTestStatus('success');
                                                    setTtsTestDetail(data.model || 'Connected');
                                                    if (data.voices && data.voices.length > 0) {
                                                        setAvailableVoices(data.voices);
                                                        if (!config.tts_voice && data.default) {
                                                            setConfig(prev => ({ ...prev, tts_voice: data.default }));
                                                        }
                                                    }
                                                } else {
                                                    setTtsTestStatus('error');
                                                    setTtsTestDetail(data.detail || 'Unknown error');
                                                }
                                            } catch (e) {
                                                setTtsTestStatus('error');
                                                setTtsTestDetail(e.message || 'Network error');
                                            }
                                        }}
                                    >
                                        {ttsTestStatus === 'loading' && <RefreshCw size={14} className="animate-spin" />}
                                        {ttsTestStatus === 'success' && <Check size={14} />}
                                        {ttsTestStatus === 'error' && <AlertCircle size={14} />}
                                        {ttsTestStatus === 'loading' ? 'Testing...' :
                                         ttsTestStatus === 'success' ? ttsTestDetail :
                                         ttsTestStatus === 'error' ? ttsTestDetail :
                                         'Test Connection'}
                                    </button>
                                </div>
                            )}

                            {/* ASR (Speech Recognition) */}
                            <div className="flex items-center justify-between p-4 rounded-lg border mt-4" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <div>
                                    <h4 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Enable Speech Recognition (ASR)</h4>
                                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Required for the Call tab (uses faster-whisper in the TTS container)</p>
                                </div>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={config.asr_enabled}
                                        onChange={e => setConfig({ ...config, asr_enabled: e.target.checked })}
                                        className="sr-only peer"
                                    />
                                    <div
                                        className="w-11 h-6 rounded-full peer after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"
                                        style={{
                                            backgroundColor: config.asr_enabled ? 'var(--accent)' : 'var(--bg-tertiary)',
                                        }}
                                    />
                                </label>
                            </div>

                            {config.asr_enabled && (
                                <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                    <div>
                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Language</label>
                                        <select
                                            className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                            value={config.asr_language || 'en'}
                                            onChange={e => setConfig({ ...config, asr_language: e.target.value })}
                                        >
                                            <option value="auto">Auto-detect</option>
                                            <option value="en">English</option>
                                            <option value="es">Spanish</option>
                                            <option value="fr">French</option>
                                            <option value="de">German</option>
                                            <option value="it">Italian</option>
                                            <option value="pt">Portuguese</option>
                                            <option value="nl">Dutch</option>
                                            <option value="pl">Polish</option>
                                            <option value="ja">Japanese</option>
                                            <option value="ko">Korean</option>
                                            <option value="zh">Chinese</option>
                                        </select>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* MCP TAB */}
                    {activeTab === 'mcp' && (
                        <div className="space-y-6">
                            <div className="p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <h4 className="text-sm font-bold mb-2" style={{ color: 'var(--accent)' }}>MCP Servers</h4>
                                <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
                                    Configure Model Context Protocol servers to add external tools. These tools will be available across all workspaces.
                                </p>

                                {/* Existing Servers */}
                                {config.mcp_servers.length > 0 && (
                                    <div className="space-y-2 mb-4">
                                        {config.mcp_servers.map((server, idx) => (
                                            <div key={idx} className="flex items-center gap-2 p-3 rounded border" style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)' }}>
                                                <div className="flex-1">
                                                    <div className="flex items-center gap-2">
                                                        <Plug size={14} style={{ color: 'var(--accent)' }} />
                                                        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{server.name}</span>
                                                    </div>
                                                    <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                                                        {server.command} {server.args.join(' ')}
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => handleTestMcpServer(server)}
                                                    disabled={testingServer === server.name}
                                                    className="p-2 rounded transition-colors disabled:opacity-50"
                                                    style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}
                                                    title="Test Connection"
                                                >
                                                    {testingServer === server.name ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
                                                </button>
                                                <button
                                                    onClick={() => handleRemoveMcpServer(server.name)}
                                                    className="p-2 rounded transition-colors hover:bg-red-500/20"
                                                    style={{ color: 'var(--text-muted)' }}
                                                    title="Remove"
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Test Result */}
                                {testResult && (
                                    <div className={`p-3 rounded mb-4 flex items-start gap-2 ${testResult.connected ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                                        {testResult.connected ? (
                                            <Check size={16} className="text-green-500 mt-0.5" />
                                        ) : (
                                            <AlertCircle size={16} className="text-red-500 mt-0.5" />
                                        )}
                                        <div className="flex-1">
                                            <div className="text-sm font-medium" style={{ color: testResult.connected ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)' }}>
                                                {testResult.connected ? `Connected! Found ${testResult.tools?.length || 0} tools` : 'Connection failed'}
                                            </div>
                                            {testResult.error && (
                                                <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{testResult.error}</div>
                                            )}
                                            {testResult.connected && testResult.tools?.length > 0 && (
                                                <div className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                                                    Tools: {testResult.tools.map(t => t.name).join(', ')}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* Add New Server */}
                                <div className="p-3 rounded border" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-subtle)' }}>
                                    <h5 className="text-xs font-bold mb-3" style={{ color: 'var(--text-muted)' }}>Add New Server</h5>
                                    <div className="grid grid-cols-2 gap-3 mb-3">
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Name *</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={newMcpServer.name}
                                                onChange={e => setNewMcpServer({ ...newMcpServer, name: e.target.value })}
                                                placeholder="brave-search"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Command *</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={newMcpServer.command}
                                                onChange={e => setNewMcpServer({ ...newMcpServer, command: e.target.value })}
                                                placeholder="npx"
                                            />
                                        </div>
                                    </div>
                                    <div className="mb-3">
                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Arguments (space-separated)</label>
                                        <input
                                            className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                            value={newMcpServer.args}
                                            onChange={e => setNewMcpServer({ ...newMcpServer, args: e.target.value })}
                                            placeholder="-y @modelcontextprotocol/server-brave-search"
                                        />
                                    </div>
                                    <div className="mb-3">
                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Environment Variables (comma-separated KEY=VALUE)</label>
                                        <input
                                            className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                            value={newMcpServer.env}
                                            onChange={e => setNewMcpServer({ ...newMcpServer, env: e.target.value })}
                                            placeholder="BRAVE_API_KEY=xxx, OTHER_VAR=yyy"
                                        />
                                    </div>
                                    <button
                                        onClick={handleAddMcpServer}
                                        className="flex items-center gap-2 px-3 py-2 rounded text-sm font-medium transition-colors"
                                        style={{ backgroundColor: 'var(--accent)', color: 'white' }}
                                    >
                                        <Plus size={14} />
                                        Add Server
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* TABS TAB */}
                    {activeTab === 'tabs' && (
                        <div className="space-y-6">
                            <div className="p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                <h4 className="text-sm font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Tab Visibility</h4>
                                <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
                                    Choose which tabs to show in the header. Toggle tabs on or off based on your workflow.
                                </p>
                                <div className="space-y-3">
                                    {TAB_REGISTRY.map(tab => {
                                        const Icon = tab.icon;
                                        const isEnabled = config.enabled_tabs?.[tab.id] !== false;
                                        return (
                                            <div
                                                key={tab.id}
                                                className="flex items-start gap-3 p-3 rounded-lg border transition-all"
                                                style={{
                                                    backgroundColor: isEnabled ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'var(--bg-tertiary)',
                                                    borderColor: isEnabled ? 'var(--accent)' : 'var(--border-subtle)',
                                                }}
                                            >
                                                <label className="relative inline-flex items-center cursor-pointer mt-1">
                                                    <input
                                                        type="checkbox"
                                                        checked={isEnabled}
                                                        onChange={e => setConfig({
                                                            ...config,
                                                            enabled_tabs: {
                                                                ...config.enabled_tabs,
                                                                [tab.id]: e.target.checked
                                                            }
                                                        })}
                                                        className="sr-only peer"
                                                    />
                                                    <div
                                                        className="w-9 h-5 rounded-full peer after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"
                                                        style={{
                                                            backgroundColor: isEnabled ? 'var(--accent)' : 'var(--bg-primary)',
                                                        }}
                                                    />
                                                </label>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <Icon size={16} style={{ color: isEnabled ? 'var(--accent)' : 'var(--text-muted)' }} />
                                                        <span className="text-sm font-medium" style={{ color: isEnabled ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                                                            {tab.label}
                                                        </span>
                                                    </div>
                                                    <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                                                        {tab.description}
                                                    </p>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div
                    className="p-4 border-t flex justify-end gap-3"
                    style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                >
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium rounded-lg transition-colors"
                        style={{ color: 'var(--text-muted)' }}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50"
                        style={{ backgroundColor: 'var(--accent)' }}
                    >
                        <Save size={16} />
                        {isSaving ? 'Saving...' : 'Save Changes'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AppSettingsModal;
