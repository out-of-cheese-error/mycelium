import React, { useState, useEffect } from 'react';
import { X, Save, Server, RefreshCw } from 'lucide-react';
import { useStore } from '../store';

const GlobalSettingsModal = ({ onClose }) => {
    const { fetchSystemConfig, updateSystemConfig, fetchModels } = useStore();
    const [availableModels, setAvailableModels] = useState([]);
    const [isFetchingModels, setIsFetchingModels] = useState(false);

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
        temperature: 0.7
    });
    // TTS Settings
    const [ttsBaseUrl, setTtsBaseUrl] = useState('');
    const [ttsModel, setTtsModel] = useState('');
    const [ttsVoice, setTtsVoice] = useState('');
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
                    tts_enabled: data.tts_enabled !== undefined ? data.tts_enabled : true,

                    reddit_user_agent: data.reddit_user_agent || ''
                });
            }
            setIsLoading(false);
        };
        load();
    }, []);

    const handleFetchModels = async () => {
        setIsFetchingModels(true);
        const models = await fetchModels();
        setAvailableModels(models);
        setIsFetchingModels(false);
    };

    const handleSave = async () => {
        try {
            await updateSystemConfig({
                ...config,
                temperature: parseFloat(config.temperature), // Ensure temperature is parsed as float
            });
            onClose();
        } catch (e) {
            alert("Failed to save settings");
        }
    };

    if (isLoading) return null;

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
            <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md overflow-hidden shadow-2xl">
                <div className="p-4 border-b border-gray-800 flex items-center justify-between">
                    <h2 className="text-lg font-bold text-gray-200 flex items-center gap-2">
                        <Server size={20} className="text-purple-500" />
                        LLM Configuration
                    </h2>
                    <button onClick={onClose} className="text-gray-500 hover:text-white">
                        <X size={20} />
                    </button>
                </div>

                <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto custom-scrollbar">

                    {/* PROVIDER SELECTION */}
                    <div className="space-y-4">
                        <h3 className="text-sm font-bold text-gray-400 border-b border-gray-700 pb-1">Provider</h3>
                        <div>
                            <label className="block text-xs font-bold text-gray-500 uppercase mb-1">LLM Provider</label>
                            <select
                                className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                value={config.provider || 'lmstudio'}
                                onChange={e => setConfig({ ...config, provider: e.target.value })}
                            >
                                <option value="ollama">Ollama (Local)</option>
                                <option value="lmstudio">LM Studio (Local)</option>
                                <option value="openai">OpenAI (Cloud)</option>
                            </select>
                        </div>
                    </div>

                    {/* OLLAMA SETTINGS - Only shown when provider is ollama */}
                    {config.provider === 'ollama' && (
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold text-gray-400 border-b border-gray-700 pb-1">Ollama Settings</h3>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Ollama Base URL</label>
                                <input
                                    className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                    value={config.ollama_base_url || ''}
                                    onChange={e => setConfig({ ...config, ollama_base_url: e.target.value })}
                                    placeholder="http://localhost:11434"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Chat Model</label>
                                <input
                                    className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                    value={config.ollama_chat_model || ''}
                                    onChange={e => setConfig({ ...config, ollama_chat_model: e.target.value })}
                                    placeholder="llama3.2"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Embedding Model</label>
                                <input
                                    className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                    value={config.ollama_embedding_model || ''}
                                    onChange={e => setConfig({ ...config, ollama_embedding_model: e.target.value })}
                                    placeholder="nomic-embed-text"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Temperature ({config.temperature})</label>
                                <input
                                    type="range"
                                    min="0" max="1" step="0.1"
                                    className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
                                    value={config.temperature || 0.7}
                                    onChange={e => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                                />
                            </div>
                        </div>
                    )}

                    {/* CHAT SETTINGS - Only shown when provider is NOT ollama */}
                    {config.provider !== 'ollama' && (
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold text-gray-400 border-b border-gray-700 pb-1">Chat Settings</h3>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Base URL</label>
                                <input
                                    className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                    value={config.chat_base_url || ''}
                                    onChange={e => setConfig({ ...config, chat_base_url: e.target.value })}
                                    placeholder={config.provider === 'openai' ? "https://api.openai.com/v1" : "http://localhost:1234/v1"}
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">API Key</label>
                                <input
                                    type="password"
                                    className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                    value={config.chat_api_key || ''}
                                    onChange={e => setConfig({ ...config, chat_api_key: e.target.value })}
                                    placeholder={config.provider === 'openai' ? "sk-..." : "lm-studio"}
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Model Name</label>
                                <div className="flex gap-2">
                                    <div className="relative flex-1">
                                        <input
                                            className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                            value={config.chat_model || ''}
                                            onChange={e => setConfig({ ...config, chat_model: e.target.value })}
                                            list="model-options"
                                            placeholder="Select or type model..."
                                        />
                                        <datalist id="model-options">
                                            {availableModels.map(m => (
                                                <option key={m} value={m} />
                                            ))}
                                        </datalist>
                                    </div>
                                    <button
                                        onClick={handleFetchModels}
                                        disabled={isFetchingModels}
                                        className="p-2 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded border border-gray-700 transition-colors"
                                        title="Fetch Models"
                                    >
                                        <RefreshCw size={16} className={isFetchingModels ? "animate-spin" : ""} />
                                    </button>
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Temperature ({config.temperature})</label>
                                <input
                                    type="range"
                                    min="0" max="1" step="0.1"
                                    className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
                                    value={config.temperature || 0.7}
                                    onChange={e => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                                />
                            </div>
                        </div>
                    )}

                    {/* EMBEDDING SETTINGS - Only shown when provider is NOT ollama */}
                    {config.provider !== 'ollama' && (
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold text-gray-400 border-b border-gray-700 pb-1">Embedding Settings</h3>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Base URL</label>
                                <input
                                    className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                    value={config.embedding_base_url || ''}
                                    onChange={e => setConfig({ ...config, embedding_base_url: e.target.value })}
                                    placeholder="http://localhost:1234/v1"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">API Key</label>
                                <input
                                    type="password"
                                    className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                    value={config.embedding_api_key || ''}
                                    onChange={e => setConfig({ ...config, embedding_api_key: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Model Name</label>
                                <input
                                    className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none"
                                    value={config.embedding_model || ''}
                                    onChange={e => setConfig({ ...config, embedding_model: e.target.value })}
                                />
                            </div>
                        </div>
                    )}

                    {/* TTS AND OTHER SETTINGS */}
                    <div className="space-y-4">
                        {/* TTS Settings */}
                        <div className="space-y-3 pt-4 border-t border-gray-800">
                            <h4 className="text-sm font-semibold text-purple-400 uppercase tracking-wider flex items-center justify-between">
                                TTS Settings
                                <div className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        id="ttsEnabled"
                                        checked={config.tts_enabled !== false}
                                        onChange={e => setConfig({ ...config, tts_enabled: e.target.checked })}
                                        className="w-4 h-4 rounded bg-gray-700 border-gray-600 text-purple-500 focus:ring-purple-500"
                                    />
                                    <label htmlFor="ttsEnabled" className="text-xs text-gray-400 cursor-pointer select-none">Enable</label>
                                </div>
                            </h4>
                            <div className={`grid grid-cols-1 gap-3 transition-opacity ${config.tts_enabled === false ? 'opacity-50 pointer-events-none' : ''}`}>
                                <div>
                                    <label className="block text-xs font-medium text-gray-400 mb-1">Base URL</label>
                                    <input
                                        type="text"
                                        className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-200"
                                        value={config.tts_base_url || ''}
                                        onChange={e => setConfig({ ...config, tts_base_url: e.target.value })}
                                        placeholder="http://akdel.mehmet-alps.nord:3000/v1"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">Model Name</label>
                                        <input
                                            type="text"
                                            className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-200"
                                            value={config.tts_model || ''}
                                            onChange={e => setConfig({ ...config, tts_model: e.target.value })}
                                            placeholder="tts-1"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">Voice</label>
                                        <input
                                            type="text"
                                            className="w-full bg-black border border-gray-700 rounded p-2 text-sm text-gray-200"
                                            value={config.tts_voice || ''}
                                            onChange={e => setConfig({ ...config, tts_voice: e.target.value })}
                                            placeholder="alloy"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>



                    </div>
                </div>

                <div className="p-4 border-t border-gray-800 flex justify-end">
                    <button
                        onClick={handleSave}
                        className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
                    >
                        <Save size={16} />
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
    );
};

export default GlobalSettingsModal;
