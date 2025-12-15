import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '../store';
import { X, Save, Sparkles, BrainCircuit, RefreshCw, Upload, Download } from 'lucide-react';

const SettingsModal = ({ workspaceId, onClose }) => {
    const { fetchWorkspaceSettings, updateWorkspaceSettings, generatePersona, grow, fetchAvailableTools, exportGraph, importGraph, renameWorkspace } = useStore();
    const [systemPrompt, setSystemPrompt] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const fileInputRef = useRef(null);

    // Tools State
    const [availableTools, setAvailableTools] = useState([]);
    const [enabledTools, setEnabledTools] = useState([]);

    // Generator State
    const [personaCues, setPersonaCues] = useState("");
    const [isGenerating, setIsGenerating] = useState(false);

    // Contemplation State
    const [contemplateCount, setContemplateCount] = useState(3);
    const [contextDepth, setContextDepth] = useState(1);
    const [contemplateTopic, setContemplateTopic] = useState("");
    const [saveToNotes, setSaveToNotes] = useState(false);
    const [isContemplating, setIsContemplating] = useState(false);

    // Context Settings (Workspace)
    const [chatMessageLimit, setChatMessageLimit] = useState(20);
    const [graphK, setGraphK] = useState(3);
    const [graphDepth, setGraphDepth] = useState(1);
    const [graphIncludeDesc, setGraphIncludeDesc] = useState(false);

    // Rename State
    const [isRenaming, setIsRenaming] = useState(false);
    const [renameValue, setRenameValue] = useState(workspaceId);

    const handleRename = async () => {
        if (!renameValue.trim() || renameValue === workspaceId) {
            setIsRenaming(false);
            return;
        }
        const success = await renameWorkspace(workspaceId, renameValue.trim());
        if (success) {
            onClose();
        }
    };

    const handleGrow = async () => {
        console.log("SettingsModal: handleGrow using workspaceId:", workspaceId);
        setIsContemplating(true);
        await grow(contemplateCount, contemplateTopic || null, saveToNotes, workspaceId, contextDepth);
        setIsContemplating(false);
        onClose(); // Optional: close on success
    };

    const handleGenerate = async () => {
        setIsGenerating(true);
        await generatePersona(personaCues);
        setIsGenerating(false);
        onClose(); // Close modal on success (store alerts user)
    };

    useEffect(() => {
        const load = async () => {
            // Parallel fetch
            const [settings, tools] = await Promise.all([
                fetchWorkspaceSettings(workspaceId),
                fetchAvailableTools()
            ]);

            setAvailableTools(tools || []);

            if (settings) {
                setSystemPrompt(settings.system_prompt);

                // If enabled_tools is null/undefined in settings, it means All Enabled.
                if (settings.enabled_tools) {
                    setEnabledTools(settings.enabled_tools);
                } else {
                    // Default: All tools enabled
                    setEnabledTools(tools || []);
                }

                // Load Context Settings
                setChatMessageLimit(settings.chat_message_limit !== undefined ? settings.chat_message_limit : 20);
                setGraphK(settings.graph_k !== undefined ? settings.graph_k : 3);
                setGraphDepth(settings.graph_depth !== undefined ? settings.graph_depth : 1);
                setGraphIncludeDesc(settings.graph_include_descriptions !== undefined ? settings.graph_include_descriptions : false);
            }
            setIsLoading(false);
        };
        load();
    }, [workspaceId]);

    const handleSave = async () => {
        setIsLoading(true);
        try {
            await updateWorkspaceSettings(workspaceId, {
                system_prompt: systemPrompt,
                enabled_tools: enabledTools,
                allow_search: true, // Deprecated/Legacy

                // Context Settings
                chat_message_limit: parseInt(chatMessageLimit),
                graph_k: parseInt(graphK),
                graph_depth: parseInt(graphDepth),
                graph_include_descriptions: graphIncludeDesc
            });
            onClose();
        } catch (e) {
            alert("Failed to save settings");
        } finally {
            setIsLoading(false);
        }
    };

    const toggleTool = (toolName) => {
        if (enabledTools.includes(toolName)) {
            setEnabledTools(enabledTools.filter(t => t !== toolName));
        } else {
            setEnabledTools([...enabledTools, toolName]);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg overflow-hidden shadow-2xl">
                <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gray-950">
                    <div className="flex items-center gap-2 flex-1 mr-4">
                        {isRenaming ? (
                            <div className="flex items-center gap-2 w-full">
                                <input
                                    className="flex-1 bg-black border border-blue-500 rounded px-2 py-1 text-sm text-white focus:outline-none"
                                    value={renameValue}
                                    onChange={(e) => setRenameValue(e.target.value)}
                                    autoFocus
                                    onBlur={handleRename}
                                    onKeyDown={(e) => e.key === 'Enter' && handleRename()}
                                />
                            </div>
                        ) : (
                            <h3
                                className="font-bold text-gray-200 cursor-pointer hover:text-blue-400 flex items-center gap-2 group"
                                onClick={() => setIsRenaming(true)}
                                title="Click to rename"
                            >
                                {workspaceId}
                                <span className="opacity-0 group-hover:opacity-50 text-xs font-normal text-gray-500">(rename)</span>
                            </h3>
                        )}
                    </div>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto custom-scrollbar">
                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-2">System Persona / Prompt</label>
                        <textarea
                            className="w-full h-48 bg-black border border-gray-700 rounded-lg p-3 text-sm text-gray-300 focus:border-blue-500 focus:outline-none resize-none"
                            value={systemPrompt}
                            onChange={(e) => setSystemPrompt(e.target.value)}
                            placeholder="You are a helpful assistant..."
                            disabled={isLoading}
                        />
                        <p className="text-xs text-gray-600 mt-2">
                            This prompt defines how the AI behaves and responds within this workspace.
                        </p>
                    </div>

                    {/* CONTEXT SETTINGS */}
                    <div className="pt-4 border-t border-gray-800">
                        <label className="block text-sm font-bold text-blue-400 mb-2">Context Settings</label>
                        <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Chat Window</label>
                                    <input
                                        type="number" min="1" max="100"
                                        className="w-full bg-black border border-gray-600 rounded px-2 py-1 text-sm text-gray-300 focus:border-blue-500 focus:outline-none"
                                        value={chatMessageLimit}
                                        onChange={e => setChatMessageLimit(e.target.value)}
                                    />
                                    <p className="text-[10px] text-gray-500 mt-1">Max past messages.</p>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Graph Nodes (k)</label>
                                    <input
                                        type="number" min="1" max="20"
                                        className="w-full bg-black border border-gray-600 rounded px-2 py-1 text-sm text-gray-300 focus:border-blue-500 focus:outline-none"
                                        value={graphK}
                                        onChange={e => setGraphK(e.target.value)}
                                    />
                                    <p className="text-[10px] text-gray-500 mt-1">Start nodes retrieved.</p>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Traversal Depth</label>
                                    <input
                                        type="number" min="0" max="3"
                                        className="w-full bg-black border border-gray-600 rounded px-2 py-1 text-sm text-gray-300 focus:border-blue-500 focus:outline-none"
                                        value={graphDepth}
                                        onChange={e => setGraphDepth(e.target.value)}
                                    />
                                    <p className="text-[10px] text-gray-500 mt-1">Hops from start nodes.</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox" id="wsGraphDesc"
                                    checked={graphIncludeDesc}
                                    onChange={e => setGraphIncludeDesc(e.target.checked)}
                                    className="w-4 h-4 rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
                                />
                                <label htmlFor="wsGraphDesc" className="text-xs font-bold text-gray-400 uppercase cursor-pointer">Include Neighbor Descriptions</label>
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-2">
                            Enabled Tools ({enabledTools.length}/{availableTools.length})
                        </label>
                        <div className="p-3 bg-black border border-gray-700 rounded-lg max-h-[400px] overflow-y-auto custom-scrollbar">
                            {(() => {
                                const CATEGORIES = {
                                    "Search & Web": ["duckduckgo_search", "visit_page", "search_images", "search_books", "search_authors"],
                                    "Knowledge & Notes": ["create_note", "read_note", "update_note", "list_notes", "delete_note", "search_notes"],
                                    "Graph Operations": ["add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge", "search_graph_nodes", "traverse_graph_node", "search_concepts"],
                                    "Ingestion": ["search_gutenberg_books", "ingest_gutenberg_book", "search_wikipedia", "ingest_wikipedia_page", "check_ingestion_status", "get_books_by_subject", "ingest_web_page"],
                                    "Science / bioRxiv": ["search_biorxiv", "read_biorxiv_abstract"],
                                    "Social / Reddit": ["search_reddit", "browse_subreddit", "read_reddit_thread", "get_reddit_user"],
                                    "Utility": ["generate_lesson"]
                                };

                                const categorizedTools = {};
                                const usedTools = new Set();

                                // Sort tools into categories
                                Object.entries(CATEGORIES).forEach(([cat, tools]) => {
                                    categorizedTools[cat] = tools.filter(t => availableTools.includes(t));
                                    tools.forEach(t => usedTools.add(t));
                                });

                                // Find "Other" tools (Dynamic / MCP)
                                const otherTools = availableTools.filter(t => !usedTools.has(t));
                                if (otherTools.length > 0) {
                                    categorizedTools["Custom / MCP"] = otherTools;
                                }

                                return Object.entries(categorizedTools).map(([category, tools]) => {
                                    if (tools.length === 0) return null;
                                    return (
                                        <div key={category} className="mb-4 last:mb-0">
                                            <h4 className="text-xs font-bold text-gray-500 uppercase mb-2 sticky top-0 bg-black py-1">{category}</h4>
                                            <div className="grid grid-cols-2 gap-2">
                                                {tools.map(tool => (
                                                    <div key={tool} className="flex items-center gap-2">
                                                        <input
                                                            type="checkbox"
                                                            id={`tool-${tool}`}
                                                            checked={enabledTools.includes(tool)}
                                                            onChange={() => toggleTool(tool)}
                                                            className="w-4 h-4 text-purple-600 bg-gray-700 border-gray-600 rounded focus:ring-purple-600 focus:ring-1"
                                                        />
                                                        <label htmlFor={`tool-${tool}`} className="text-xs text-gray-300 cursor-pointer select-none truncate" title={tool}>
                                                            {tool}
                                                        </label>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                });
                            })()}
                        </div>
                        <div className="flex gap-2 mt-2">
                            <button onClick={() => setEnabledTools(availableTools)} className="text-xs text-blue-400 hover:text-blue-300">Select All</button>
                            <button onClick={() => setEnabledTools([])} className="text-xs text-gray-500 hover:text-gray-400">Deselect All</button>
                        </div>
                    </div>

                    <div className="pt-4 border-t border-gray-800">
                        <label className="block text-sm font-bold text-purple-400 mb-2">Growth Engine</label>
                        <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
                            <label className="block text-xs text-gray-500 mb-1">Topic (Optional)</label>
                            <input
                                type="text"
                                value={contemplateTopic}
                                onChange={(e) => setContemplateTopic(e.target.value)}
                                className="w-full bg-black border border-gray-600 rounded px-2 py-1 text-sm mb-3 focus:border-purple-500 focus:outline-none"
                                placeholder="Specific subject..."
                            />
                            <div className="flex gap-4 mb-4">
                                <div className="flex-1">
                                    <label className="block text-xs text-gray-500 mb-1">Iterations</label>
                                    <input
                                        type="number"
                                        min="1" max="10"
                                        value={contemplateCount}
                                        onChange={(e) => setContemplateCount(Number(e.target.value))}
                                        className="w-full bg-black border border-gray-600 rounded px-2 py-1 text-sm focus:border-purple-500 focus:outline-none"
                                    />
                                </div>
                                <div className="flex-1">
                                    <label className="block text-xs text-gray-500 mb-1">Depth</label>
                                    <input
                                        type="number"
                                        min="1" max="5"
                                        value={contextDepth}
                                        onChange={(e) => setContextDepth(Number(e.target.value))}
                                        className="w-full bg-black border border-gray-600 rounded px-2 py-1 text-sm focus:border-purple-500 focus:outline-none"
                                    />
                                </div>
                            </div>
                            <button
                                onClick={handleGrow}
                                disabled={isContemplating}
                                className="w-full py-2 bg-purple-900/50 hover:bg-purple-900 border border-purple-700 rounded text-sm text-purple-100 flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                            >
                                {isContemplating ? <RefreshCw size={14} className="animate-spin" /> : <BrainCircuit size={14} />}
                                {isContemplating ? 'Growing...' : 'Start Growth Cycle'}
                            </button>
                        </div>
                    </div>
                    <div className="pt-4 border-t border-gray-800">
                        <label className="block text-sm font-bold text-green-400 mb-2">Memory Management</label>
                        <div className="flex gap-3">
                            <button
                                onClick={exportGraph}
                                className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded text-sm text-gray-200 flex items-center justify-center gap-2 transition-colors"
                            >
                                <Download size={14} />
                                Export Graph
                            </button>
                            <div className="flex-1">
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={(e) => {
                                        if (e.target.files?.[0]) {
                                            if (confirm("Overwrite current memory with this file? This cannot be undone (a backup will be created).")) {
                                                importGraph(e.target.files[0]);
                                            }
                                            e.target.value = null; // Reset
                                        }
                                    }}
                                    className="hidden"
                                    accept=".json"
                                />
                                <button
                                    onClick={() => fileInputRef.current?.click()}
                                    className="w-full py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 rounded text-sm text-gray-200 flex items-center justify-center gap-2 transition-colors"
                                >
                                    <Upload size={14} />
                                    Import Graph
                                </button>
                            </div>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                            Back up your knowledge graph or restore from a JSON file. Import triggers a re-index of the vector memory.
                        </p>
                    </div>

                    <div className="pt-4 border-t border-gray-800">
                        <label className="block text-sm font-bold text-purple-400 mb-2 flex items-center gap-2">
                            <Sparkles size={16} /> Magic Persona Generator
                        </label>
                        <div className="bg-purple-900/10 border border-purple-500/30 rounded-lg p-4">
                            <p className="text-xs text-gray-400 mb-3">
                                Describe a character (e.g., "A grumpy 19th-century lighthouse keeper") and the AI will hallucinate a backstory, emotions, and memories for it.
                            </p>
                            <textarea
                                className="w-full h-20 bg-black/50 border border-gray-700 rounded p-2 text-sm text-gray-300 focus:border-purple-500 focus:outline-none resize-none mb-3"
                                placeholder="Enter cues here..."
                                value={personaCues}
                                onChange={(e) => setPersonaCues(e.target.value)}
                            />
                            <button
                                onClick={handleGenerate}
                                disabled={isGenerating || !personaCues.trim()}
                                className="w-full py-2 bg-purple-600 hover:bg-purple-500 text-white rounded text-sm font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {isGenerating ? "Hallucinating..." : "Generate & Seed Persona"}
                            </button>
                        </div>
                    </div>


                </div>

                <div className="p-4 border-t border-gray-800 bg-gray-950 flex justify-end gap-2">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
                        disabled={isLoading}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isLoading}
                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        <Save size={16} />
                        Save Persona
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SettingsModal;
