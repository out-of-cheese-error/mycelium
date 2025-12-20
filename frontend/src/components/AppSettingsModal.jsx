import React, { useState, useEffect } from 'react';
import { X, Save, Palette, Server, Volume2, Settings2, RefreshCw, Check } from 'lucide-react';
import { useStore } from '../store';
import { THEMES, applyThemeToDOM } from './ThemeProvider';

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
    const { fetchSystemConfig, updateSystemConfig, fetchModels, setUiSettings } = useStore();
    const [availableModels, setAvailableModels] = useState([]);
    const [isFetchingModels, setIsFetchingModels] = useState(false);
    const [activeTab, setActiveTab] = useState('llm');
    const [isSaving, setIsSaving] = useState(false);

    const [config, setConfig] = useState({
        provider: 'lmstudio',
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
        tts_base_url: '',
        tts_model: '',
        tts_voice: '',
        tts_enabled: false,
        // UI Settings
        theme: 'dark',
        accent_color: '#8b5cf6',
        font_family: 'Inter',
        font_size: 'md',
    });

    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            const data = await fetchSystemConfig();
            if (data) {
                setConfig({
                    provider: data.provider || 'lmstudio',
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
                    tts_base_url: data.tts_base_url || '',
                    tts_model: data.tts_model || '',
                    tts_voice: data.tts_voice || '',
                    tts_enabled: data.tts_enabled || false,
                    reddit_user_agent: data.reddit_user_agent || '',
                    // UI Settings
                    theme: data.theme || 'dark',
                    accent_color: data.accent_color || '#8b5cf6',
                    font_family: data.font_family || 'Inter',
                    font_size: data.font_size || 'md',
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
        });
    }, [config.theme, config.accent_color, config.font_family, config.font_size]);

    const handleFetchModels = async () => {
        setIsFetchingModels(true);
        const models = await fetchModels();
        setAvailableModels(models);
        setIsFetchingModels(false);
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await updateSystemConfig({
                ...config,
                temperature: parseFloat(config.temperature),
            });
            // Update UI settings in store for persistence
            setUiSettings({
                theme: config.theme,
                accent_color: config.accent_color,
                font_family: config.font_family,
                font_size: config.font_size,
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
                    className="flex gap-2 p-3 border-b"
                    style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                >
                    <TabButton active={activeTab === 'llm'} onClick={() => setActiveTab('llm')} icon={Server}>
                        LLM
                    </TabButton>
                    <TabButton active={activeTab === 'tts'} onClick={() => setActiveTab('tts')} icon={Volume2}>
                        TTS
                    </TabButton>
                    <TabButton active={activeTab === 'appearance'} onClick={() => setActiveTab('appearance')} icon={Palette}>
                        Appearance
                    </TabButton>
                </div>

                {/* Tab Content */}
                <div className="p-6 max-h-[60vh] overflow-y-auto custom-scrollbar">

                    {/* APPEARANCE TAB */}
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
                        </div>
                    )}

                    {/* LLM TAB */}
                    {activeTab === 'llm' && (
                        <div className="space-y-6">
                            {/* Provider Selection */}
                            <div>
                                <label className="block text-sm font-bold mb-2" style={{ color: 'var(--text-muted)' }}>
                                    LLM Provider
                                </label>
                                <select
                                    className="w-full p-3 rounded-lg border text-sm focus:outline-none focus:ring-2"
                                    style={{
                                        backgroundColor: 'var(--bg-primary)',
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

                            {/* Ollama Settings */}
                            {config.provider === 'ollama' && (
                                <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                    <h4 className="text-sm font-bold" style={{ color: 'var(--accent)' }}>Ollama Settings</h4>
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
                                    <div className="grid grid-cols-2 gap-4">
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
                                    </div>
                                </div>
                            )}

                            {/* OpenAI/LM Studio Settings */}
                            {config.provider !== 'ollama' && (
                                <>
                                    <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                        <h4 className="text-sm font-bold" style={{ color: 'var(--accent)' }}>Chat Settings</h4>
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
                                    </div>

                                    <div className="space-y-4 p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
                                        <h4 className="text-sm font-bold" style={{ color: 'var(--accent)' }}>Embedding Settings</h4>
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
                                    </div>
                                </>
                            )}

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
                                            placeholder="http://localhost:3000/v1"
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
                                                placeholder="tts-1"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Voice</label>
                                            <input
                                                className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={config.tts_voice || ''}
                                                onChange={e => setConfig({ ...config, tts_voice: e.target.value })}
                                                placeholder="alloy"
                                            />
                                        </div>
                                    </div>
                                </div>
                            )}
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
