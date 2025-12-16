
import React, { useRef, useState, useEffect } from 'react';
import { useStore } from '../store';
import { Box, Plus, Upload, MessageSquare, Trash2, X, Settings } from 'lucide-react';
import SettingsModal from './SettingsModal';
import GlobalSettingsModal from './GlobalSettingsModal';
import EmotionsPanel from './EmotionsPanel';

import logo from '../logo.png';

const Sidebar = () => {
    const {
        workspaces,
        fetchWorkspaces,
        createWorkspace,
        currentWorkspace,
        selectWorkspace,
        deleteWorkspace,
        uploadFiles,
        isLoading,
        threads,
        currentThread,
        createThread,
        selectThread,
        deleteThread,
        emotions,
        updateEmotions,
        ingestJobs,
        stopIngest,
        fetchAvailableTools
    } = useStore();

    const [availableTools, setAvailableTools] = useState({ builtin: [], mcp: [] });

    const [isCreating, setIsCreating] = useState(false);
    const [newWsName, setNewWsName] = useState('');
    const [editingWs, setEditingWs] = useState(null);
    const [showGlobalSettings, setShowGlobalSettings] = useState(false);
    const [ingestSettings, setIngestSettings] = useState({ chunkSize: 4800, chunkOverlap: 400 });
    const [showIngestSettings, setShowIngestSettings] = useState(false);
    const fileInputRef = useRef(null);

    useEffect(() => {
        fetchWorkspaces();
        fetchAvailableTools().then(tools => {
            if (tools && (tools.builtin || tools.mcp)) {
                setAvailableTools(tools);
            } else if (Array.isArray(tools)) {
                // Fallback for old API if needed, though we updated it
                setAvailableTools({ builtin: tools, mcp: [] });
            }
        });
    }, []);

    const handleCreate = () => {
        if (newWsName.trim()) {
            createWorkspace(newWsName.trim());
            setNewWsName('');
            setIsCreating(false);
        }
    };

    const handleUpload = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            uploadFiles(e.target.files, ingestSettings);
        }
    };

    return (
        <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0 h-full">
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <img src={logo} alt="MyCelium Logo" className="w-8 h-8 rounded-lg object-contain bg-white p-0.5" />
                    <span className="font-bold text-gray-200">MyCelium</span>
                </div>
                <button
                    onClick={() => setShowGlobalSettings(true)}
                    className="p-1 text-gray-500 hover:text-white transition-colors"
                    title="Global LLM Settings"
                >
                    <Settings size={16} />
                </button>
            </div>

            {/* WORKSPACES */}
            <div className="flex-1 overflow-y-auto px-2 py-4 space-y-6">
                <div>
                    <div className="flex items-center justify-between px-2 mb-2">
                        <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Workspaces</h3>
                        <button onClick={() => setIsCreating(true)} className="p-1 hover:bg-gray-800 rounded text-gray-400 hover:text-white transition-colors">
                            <Plus size={14} />
                        </button>
                    </div>

                    {isCreating && (
                        <div className="px-2 mb-2">
                            <input
                                className="w-full bg-black border border-blue-500 rounded px-2 py-1 text-sm text-white focus:outline-none"
                                placeholder="Name..."
                                autoFocus
                                value={newWsName}
                                onChange={e => setNewWsName(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && handleCreate()}
                                onBlur={() => !newWsName && setIsCreating(false)}
                            />
                        </div>
                    )}

                    <div className="space-y-1">
                        {workspaces.map(ws => (
                            <div
                                key={ws.id}
                                onClick={() => selectWorkspace(ws)}
                                className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${currentWorkspace?.id === ws.id ? 'bg-blue-600/20 text-blue-400' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}
                            >
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <Box size={16} className="flex-shrink-0" />
                                    <span className="truncate">{ws.id}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <span className="text-xs text-gray-600 group-hover:text-gray-500 transition-colors">
                                        {ws.node_count} nodes
                                    </span>
                                    {currentWorkspace?.id !== ws.id && ( // Prevent deleting active workspace accidentally or requiring complex logic
                                        <button
                                            onClick={(e) => { e.stopPropagation(); deleteWorkspace(ws.id); }}
                                            className="p-1 text-gray-700 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                        >
                                            <X size={12} />
                                        </button>
                                    )}
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setEditingWs(ws.id); }}
                                        className="p-1 text-gray-600 hover:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                        title="Workspace Settings"
                                    >
                                        <Settings size={12} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* DOCUMENT INGESTION */}
                {currentWorkspace && (
                    <div>
                        <div className="flex items-center justify-between px-2 mb-2">
                            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Knowledge Base</h3>
                            <button
                                onClick={() => setShowIngestSettings(!showIngestSettings)}
                                className={`p-1 rounded transition-colors ${showIngestSettings ? 'text-blue-400 bg-blue-600/10' : 'text-gray-500 hover:text-gray-300'}`}
                                title="Ingestion Settings"
                            >
                                <Settings size={12} />
                            </button>
                        </div>

                        {showIngestSettings && (
                            <div className="px-2 mb-2 space-y-2 bg-gray-800/50 p-2 rounded text-xs border border-gray-700">
                                <div>
                                    <label className="text-gray-500 block mb-0.5">Chunk Size (chars)</label>
                                    <input
                                        type="number"
                                        value={ingestSettings.chunkSize}
                                        onChange={e => setIngestSettings({ ...ingestSettings, chunkSize: parseInt(e.target.value) || 0 })}
                                        className="w-full bg-black border border-gray-700 rounded px-1.5 py-0.5 text-gray-300 focus:border-blue-500 focus:outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="text-gray-500 block mb-0.5">Overlap (chars)</label>
                                    <input
                                        type="number"
                                        value={ingestSettings.chunkOverlap}
                                        onChange={e => setIngestSettings({ ...ingestSettings, chunkOverlap: parseInt(e.target.value) || 0 })}
                                        className="w-full bg-black border border-gray-700 rounded px-1.5 py-0.5 text-gray-300 focus:border-blue-500 focus:outline-none"
                                    />
                                </div>
                            </div>
                        )}

                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={isLoading}
                            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-gray-700 text-gray-400 text-sm hover:border-gray-500 hover:text-gray-300 transition-colors"
                        >
                            <Upload size={16} />
                            <span>Ingest Document</span>
                            <input type="file" ref={fileInputRef} className="hidden" onChange={handleUpload} accept=".txt,.pdf,.md" multiple />

                        </button>
                    </div>
                )}

                {/* Ingestion Progress List */}
                {currentWorkspace && ingestJobs && ingestJobs.map((job) => (
                    <div key={job.job_id} className="px-2 mb-2">
                        <div className="bg-gray-800 rounded p-2 text-xs border border-gray-700">
                            <div className="flex justify-between text-gray-400 mb-1 items-center">
                                <span className="truncate max-w-[120px]" title={job.filename}>{job.filename || 'Processing...'}</span>
                                <div className="flex items-center gap-2">
                                    <span>
                                        {job.current} / {job.total}
                                    </span>
                                    {/* Show status text if not processing */}
                                    {job.status !== 'processing' && (
                                        <span className={`text-[10px] uppercase font-bold ${job.status === 'completed' ? 'text-green-500' :
                                            job.status === 'cancelled' ? 'text-yellow-500' : 'text-red-500'
                                            }`}>
                                            {job.status}
                                        </span>
                                    )}
                                    {/* Stop button only if processing */}
                                    {job.status === 'processing' && (
                                        <button
                                            onClick={(e) => { e.stopPropagation(); stopIngest(job.job_id); }}
                                            className="text-gray-500 hover:text-red-400 transition-colors"
                                            title="Stop Ingestion"
                                        >
                                            <X size={12} />
                                        </button>
                                    )}
                                </div>
                            </div>
                            <div className="w-full bg-gray-700 h-1.5 rounded-full overflow-hidden">
                                <div
                                    className={`h-full transition-all duration-300 ease-out ${job.status === 'completed' ? 'bg-green-500' :
                                        job.status === 'error' ? 'bg-red-500' :
                                            job.status === 'cancelled' ? 'bg-yellow-500' :
                                                'bg-blue-500'
                                        }`}
                                    style={{
                                        width: `${Math.min(100, (job.current / Math.max(1, job.total)) * 100)}%`
                                    }}
                                ></div>
                            </div>
                        </div>
                    </div>
                ))}

                {/* THREADS */}
                {currentWorkspace && (
                    <div>
                        <div className="flex items-center justify-between px-2 mb-2">
                            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Chats</h3>
                            <button onClick={() => createThread(currentWorkspace.id)} className="p-1 hover:bg-gray-800 rounded text-gray-400 hover:text-white transition-colors">
                                <Plus size={14} />
                            </button>
                        </div>

                        <div className="space-y-1">
                            {threads.map(t => (
                                <div
                                    key={t.id}
                                    onClick={() => selectThread(t)}
                                    className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${currentThread?.id === t.id ? 'bg-gray-800 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}
                                >
                                    <div className="flex items-center gap-2 overflow-hidden">
                                        <MessageSquare size={16} className="flex-shrink-0" />
                                        <span className="truncate">{t.title || 'Untitled'}</span>
                                    </div>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); deleteThread(t.id); }}
                                        className="p-1 text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <Trash2 size={12} />
                                    </button>
                                </div>
                            ))}
                            {threads.length === 0 && (
                                <div className="px-3 py-2 text-xs text-gray-600 italic">No chats yet.</div>
                            )}
                        </div>
                    </div>
                )}

                {/* TOOLS LIST */}
                {currentWorkspace && (
                    <div className="px-2 mt-4 mb-4">
                        <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider px-2 mb-2">Tools</h3>
                        <div className="space-y-3 px-3">
                            {/* Built-in Tools */}
                            <div className="space-y-1">
                                <h4 className="text-[10px] uppercase text-gray-600 font-semibold">Built-in</h4>
                                <div className="flex flex-wrap gap-1">
                                    {availableTools.builtin.map(t => (
                                        <span key={t} className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded border border-gray-700" title={t}>
                                            {t}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {/* MCP Tools */}
                            {availableTools.mcp.length > 0 && (
                                <div className="space-y-1">
                                    <h4 className="text-[10px] uppercase text-purple-400 font-semibold">MCP Tools</h4>
                                    <div className="flex flex-wrap gap-1">
                                        {availableTools.mcp.map(t => (
                                            <span key={t} className="text-[10px] bg-purple-900/20 text-purple-300 px-1.5 py-0.5 rounded border border-purple-800" title={t}>
                                                {t}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {availableTools.mcp.length === 0 && (
                                <div className="text-[10px] text-gray-600 italic">No MCP tools loaded.</div>
                            )}
                        </div>
                    </div>
                )}

            </div>

            {/* STATUS & EMOTIONS */}
            {currentWorkspace && (
                <div className="p-4 border-t border-gray-800 bg-black/20 space-y-3">
                    {emotions && <EmotionsPanel />}
                    <div className="text-xs text-gray-500 font-mono pt-2 border-t border-gray-800">
                        WS: {currentWorkspace.id}
                    </div>
                </div>
            )}

            {editingWs && (
                <SettingsModal
                    workspaceId={editingWs}
                    onClose={() => setEditingWs(null)}
                />
            )}

            {showGlobalSettings && (
                <GlobalSettingsModal
                    onClose={() => setShowGlobalSettings(false)}
                />
            )}
        </div>
    );
};

export default Sidebar;
