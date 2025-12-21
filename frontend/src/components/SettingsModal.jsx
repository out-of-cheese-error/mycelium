import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '../store';
import { X, Save, Sparkles, BrainCircuit, RefreshCw, Upload, Download, Globe, Wand2, Settings2, Wrench, Sliders, Database } from 'lucide-react';

const TabButton = ({ active, onClick, icon: Icon, children }) => (
    <button
        onClick={onClick}
        className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all`}
        style={{
            backgroundColor: active ? 'var(--accent)' : 'transparent',
            color: active ? 'white' : 'var(--text-muted)',
        }}
    >
        <Icon size={16} />
        {children}
    </button>
);

const SettingsModal = ({ workspaceId, onClose }) => {
    const { fetchWorkspaceSettings, updateWorkspaceSettings, generatePersona, grow, fetchAvailableTools, exportGraph, importGraph, renameWorkspace } = useStore();
    const [systemPrompt, setSystemPrompt] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('context');
    const fileInputRef = useRef(null);

    // Tools State
    const [availableTools, setAvailableTools] = useState([]);
    const [mcpTools, setMcpTools] = useState([]);
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

    // Workspace-as-Tool State
    const [isToolEnabled, setIsToolEnabled] = useState(false);
    const [toolName, setToolName] = useState('');
    const [toolDescription, setToolDescription] = useState('');
    const [isGeneratingDesc, setIsGeneratingDesc] = useState(false);

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
        setIsContemplating(true);
        await grow(contemplateCount, contemplateTopic || null, saveToNotes, workspaceId, contextDepth);
        setIsContemplating(false);
        onClose();
    };

    const handleGenerate = async () => {
        setIsGenerating(true);
        await generatePersona(personaCues);
        setIsGenerating(false);
        onClose();
    };

    useEffect(() => {
        const load = async () => {
            const [settings, tools] = await Promise.all([
                fetchWorkspaceSettings(workspaceId),
                fetchAvailableTools()
            ]);

            setAvailableTools(tools.builtin || tools || []);
            setMcpTools(tools.mcp || []);

            // Combined list for enabled tools comparison
            const allToolNames = [...(tools.builtin || tools || []), ...(tools.mcp || []).map(t => t.name)];

            if (settings) {
                setSystemPrompt(settings.system_prompt);
                if (settings.enabled_tools) {
                    setEnabledTools(settings.enabled_tools);
                } else {
                    setEnabledTools(allToolNames);
                }
                setChatMessageLimit(settings.chat_message_limit !== undefined ? settings.chat_message_limit : 20);
                setGraphK(settings.graph_k !== undefined ? settings.graph_k : 3);
                setGraphDepth(settings.graph_depth !== undefined ? settings.graph_depth : 1);
                setGraphIncludeDesc(settings.graph_include_descriptions !== undefined ? settings.graph_include_descriptions : false);
                setIsToolEnabled(settings.is_tool_enabled || false);
                setToolName(settings.tool_name || '');
                setToolDescription(settings.tool_description || '');
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
                allow_search: true,
                chat_message_limit: parseInt(chatMessageLimit),
                graph_k: parseInt(graphK),
                graph_depth: parseInt(graphDepth),
                graph_include_descriptions: graphIncludeDesc,
                is_tool_enabled: isToolEnabled,
                tool_name: toolName.trim().toLowerCase().replace(/\s+/g, '_'),
                tool_description: toolDescription
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

    if (isLoading) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.8)' }}>
            <div
                className="rounded-xl w-full max-w-2xl overflow-hidden shadow-2xl border"
                style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}
            >
                {/* Header */}
                <div
                    className="p-4 border-b flex items-center justify-between"
                    style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                >
                    <div className="flex items-center gap-2 flex-1 mr-4">
                        <Settings2 size={20} style={{ color: 'var(--accent)' }} />
                        {isRenaming ? (
                            <input
                                className="flex-1 rounded px-2 py-1 text-sm focus:outline-none"
                                style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--accent)' }}
                                value={renameValue}
                                onChange={(e) => setRenameValue(e.target.value)}
                                autoFocus
                                onBlur={handleRename}
                                onKeyDown={(e) => e.key === 'Enter' && handleRename()}
                            />
                        ) : (
                            <h3
                                className="font-bold cursor-pointer hover:opacity-80 flex items-center gap-2 group"
                                style={{ color: 'var(--text-primary)' }}
                                onClick={() => setIsRenaming(true)}
                                title="Click to rename"
                            >
                                {workspaceId}
                                <span className="opacity-0 group-hover:opacity-50 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>(rename)</span>
                            </h3>
                        )}
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1 rounded transition-colors"
                        style={{ color: 'var(--text-muted)' }}
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Tab Navigation */}
                <div
                    className="flex gap-2 p-3 border-b overflow-x-auto"
                    style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                >
                    <TabButton active={activeTab === 'context'} onClick={() => setActiveTab('context')} icon={Sliders}>
                        Context
                    </TabButton>
                    <TabButton active={activeTab === 'tools'} onClick={() => setActiveTab('tools')} icon={Wrench}>
                        Tools
                    </TabButton>
                    <TabButton active={activeTab === 'persona'} onClick={() => setActiveTab('persona')} icon={Sparkles}>
                        Persona
                    </TabButton>
                    <TabButton active={activeTab === 'data'} onClick={() => setActiveTab('data')} icon={Database}>
                        Data
                    </TabButton>
                </div>

                {/* Tab Content */}
                <div className="p-6 max-h-[60vh] overflow-y-auto custom-scrollbar">

                    {/* CONTEXT TAB */}
                    {activeTab === 'context' && (
                        <div className="space-y-6">
                            {/* Context Settings */}
                            <div
                                className="p-4 rounded-lg border"
                                style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                            >
                                <h4 className="text-sm font-bold mb-4" style={{ color: 'var(--accent)' }}>Context Settings</h4>
                                <div className="grid grid-cols-3 gap-4">
                                    <div>
                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Chat Window</label>
                                        <input
                                            type="number" min="1" max="100"
                                            className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                            value={chatMessageLimit}
                                            onChange={e => setChatMessageLimit(e.target.value)}
                                        />
                                        <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Max past messages</p>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Graph Nodes (k)</label>
                                        <input
                                            type="number" min="1" max="20"
                                            className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                            value={graphK}
                                            onChange={e => setGraphK(e.target.value)}
                                        />
                                        <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Start nodes retrieved</p>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Traversal Depth</label>
                                        <input
                                            type="number" min="0" max="3"
                                            className="w-full p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                            value={graphDepth}
                                            onChange={e => setGraphDepth(e.target.value)}
                                        />
                                        <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Hops from start nodes</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 mt-4">
                                    <input
                                        type="checkbox" id="wsGraphDesc"
                                        checked={graphIncludeDesc}
                                        onChange={e => setGraphIncludeDesc(e.target.checked)}
                                        className="w-4 h-4 rounded"
                                        style={{ accentColor: 'var(--accent)' }}
                                    />
                                    <label htmlFor="wsGraphDesc" className="text-xs font-medium cursor-pointer" style={{ color: 'var(--text-secondary)' }}>
                                        Include Neighbor Descriptions
                                    </label>
                                </div>
                            </div>

                            {/* Expose as Expert Tool */}
                            <div
                                className="p-4 rounded-lg border"
                                style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                            >
                                <div className="flex items-center gap-2 mb-4">
                                    <Globe size={16} style={{ color: 'var(--accent)' }} />
                                    <h4 className="text-sm font-bold" style={{ color: 'var(--accent)' }}>Expose as Expert Tool</h4>
                                </div>
                                <div className="flex items-center gap-3 mb-4">
                                    <input
                                        type="checkbox"
                                        id="wsToolEnabled"
                                        checked={isToolEnabled}
                                        onChange={e => setIsToolEnabled(e.target.checked)}
                                        className="w-5 h-5 rounded"
                                        style={{ accentColor: 'var(--accent)' }}
                                    />
                                    <label htmlFor="wsToolEnabled" className="text-sm cursor-pointer" style={{ color: 'var(--text-secondary)' }}>
                                        Allow other workspaces to consult this workspace's knowledge
                                    </label>
                                </div>

                                {isToolEnabled && (
                                    <div className="space-y-4">
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Tool Name</label>
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm" style={{ color: 'var(--text-muted)' }}>ask_</span>
                                                <input
                                                    type="text"
                                                    className="flex-1 p-2 rounded border text-sm focus:outline-none focus:ring-2"
                                                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                    value={toolName}
                                                    onChange={e => setToolName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
                                                    placeholder="physics_expert"
                                                />
                                            </div>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Description</label>
                                            <textarea
                                                className="w-full h-20 rounded border p-2 text-sm focus:outline-none focus:ring-2 resize-none"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                                value={toolDescription}
                                                onChange={e => setToolDescription(e.target.value)}
                                                placeholder="Consult this expert for questions about..."
                                            />
                                            <button
                                                onClick={async () => {
                                                    setIsGeneratingDesc(true);
                                                    try {
                                                        const { generateToolDescription } = useStore.getState();
                                                        const desc = await generateToolDescription(workspaceId);
                                                        if (desc) setToolDescription(desc);
                                                    } catch (e) {
                                                        console.error("Failed to generate description:", e);
                                                    } finally {
                                                        setIsGeneratingDesc(false);
                                                    }
                                                }}
                                                disabled={isGeneratingDesc}
                                                className="mt-2 flex items-center gap-2 px-3 py-1 rounded text-xs transition-colors disabled:opacity-50"
                                                style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--accent)', border: '1px solid var(--border-color)' }}
                                            >
                                                {isGeneratingDesc ? <RefreshCw size={12} className="animate-spin" /> : <Wand2 size={12} />}
                                                {isGeneratingDesc ? 'Generating...' : 'Auto-Generate from Concepts'}
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* TOOLS TAB */}
                    {activeTab === 'tools' && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between mb-2">
                                <label className="text-sm font-bold" style={{ color: 'var(--text-muted)' }}>
                                    Enabled Tools ({enabledTools.length}/{availableTools.length + mcpTools.length})
                                </label>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setEnabledTools([...availableTools, ...mcpTools.map(t => t.name)])}
                                        className="text-xs px-2 py-1 rounded transition-colors"
                                        style={{ color: 'var(--accent)' }}
                                    >
                                        Select All
                                    </button>
                                    <button
                                        onClick={() => setEnabledTools([])}
                                        className="text-xs px-2 py-1 rounded transition-colors"
                                        style={{ color: 'var(--text-muted)' }}
                                    >
                                        Deselect All
                                    </button>
                                </div>
                            </div>

                            <div
                                className="p-4 rounded-lg border max-h-[400px] overflow-y-auto custom-scrollbar"
                                style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                            >
                                {(() => {
                                    const CATEGORIES = {
                                        "Search & Web": ["duckduckgo_search", "visit_page", "search_images", "search_books", "search_authors"],
                                        "Knowledge & Notes": ["create_note", "read_note", "update_note", "list_notes", "delete_note", "search_notes"],
                                        "Graph Operations": ["add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge", "search_graph_nodes", "traverse_graph_node", "search_concepts"],
                                        "Workspace Cross-Talk": ["consult_workspace", "list_expert_workspaces"],
                                        "Ingestion": ["search_gutenberg_books", "ingest_gutenberg_book", "search_wikipedia", "ingest_wikipedia_page", "check_ingestion_status", "get_books_by_subject", "ingest_web_page"],
                                        "Science / Research": ["search_biorxiv", "read_biorxiv_abstract", "search_arxiv", "read_arxiv_abstract", "ingest_arxiv_paper"],
                                        "Social / Reddit": ["search_reddit", "browse_subreddit", "read_reddit_thread", "get_reddit_user"],
                                        "Utility": ["generate_lesson"]
                                    };

                                    const categorizedTools = {};
                                    const usedTools = new Set();

                                    Object.entries(CATEGORIES).forEach(([cat, tools]) => {
                                        categorizedTools[cat] = tools.filter(t => availableTools.includes(t));
                                        tools.forEach(t => usedTools.add(t));
                                    });

                                    const otherTools = availableTools.filter(t => !usedTools.has(t));
                                    if (otherTools.length > 0) {
                                        categorizedTools["Other"] = otherTools;
                                    }

                                    // Add MCP categories - group by server name
                                    if (mcpTools.length > 0) {
                                        const mcpByServer = {};
                                        mcpTools.forEach(t => {
                                            const serverName = t.server || 'unknown';
                                            if (!mcpByServer[serverName]) {
                                                mcpByServer[serverName] = [];
                                            }
                                            mcpByServer[serverName].push(t.name);
                                        });

                                        Object.entries(mcpByServer).forEach(([server, tools]) => {
                                            categorizedTools[`MCP: ${server}`] = tools;
                                        });
                                    }

                                    // Helper functions for category selection
                                    const selectCategory = (tools) => {
                                        setEnabledTools(prev => [...new Set([...prev, ...tools])]);
                                    };
                                    const deselectCategory = (tools) => {
                                        setEnabledTools(prev => prev.filter(t => !tools.includes(t)));
                                    };
                                    const isCategoryFullySelected = (tools) => tools.every(t => enabledTools.includes(t));

                                    return Object.entries(categorizedTools).map(([category, tools]) => {
                                        if (tools.length === 0) return null;
                                        const allSelected = isCategoryFullySelected(tools);
                                        return (
                                            <div key={category} className="mb-4 last:mb-0">
                                                <div className="flex items-center justify-between sticky top-0 py-1" style={{ backgroundColor: 'var(--bg-primary)' }}>
                                                    <h4 className="text-xs font-bold uppercase" style={{ color: 'var(--accent)' }}>
                                                        {category}
                                                    </h4>
                                                    <div className="flex gap-2">
                                                        <button
                                                            onClick={() => selectCategory(tools)}
                                                            className="text-xs px-2 py-0.5 rounded transition-colors hover:opacity-80"
                                                            style={{ color: allSelected ? 'var(--text-muted)' : 'var(--accent)' }}
                                                        >
                                                            All
                                                        </button>
                                                        <button
                                                            onClick={() => deselectCategory(tools)}
                                                            className="text-xs px-2 py-0.5 rounded transition-colors hover:opacity-80"
                                                            style={{ color: 'var(--text-muted)' }}
                                                        >
                                                            None
                                                        </button>
                                                    </div>
                                                </div>
                                                <div className="grid grid-cols-2 gap-2">
                                                    {tools.map(tool => (
                                                        <div key={tool} className="flex items-center gap-2">
                                                            <input
                                                                type="checkbox"
                                                                id={`tool-${tool}`}
                                                                checked={enabledTools.includes(tool)}
                                                                onChange={() => toggleTool(tool)}
                                                                className="w-4 h-4 rounded"
                                                                style={{ accentColor: 'var(--accent)' }}
                                                            />
                                                            <label
                                                                htmlFor={`tool-${tool}`}
                                                                className="text-xs cursor-pointer select-none truncate"
                                                                style={{ color: 'var(--text-secondary)' }}
                                                                title={tool}
                                                            >
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
                        </div>
                    )}

                    {/* PERSONA TAB */}
                    {activeTab === 'persona' && (
                        <div className="space-y-6">
                            {/* System Prompt */}
                            <div>
                                <label className="block text-sm font-bold mb-2" style={{ color: 'var(--text-muted)' }}>
                                    System Persona / Prompt
                                </label>
                                <textarea
                                    className="w-full h-48 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 resize-none"
                                    style={{
                                        backgroundColor: 'var(--bg-primary)',
                                        borderColor: 'var(--border-color)',
                                        color: 'var(--text-primary)',
                                        border: '1px solid var(--border-color)',
                                        '--tw-ring-color': 'var(--accent)',
                                    }}
                                    value={systemPrompt}
                                    onChange={(e) => setSystemPrompt(e.target.value)}
                                    placeholder="You are a helpful assistant..."
                                />
                                <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                                    This prompt defines how the AI behaves and responds within this workspace.
                                </p>
                            </div>

                            {/* Magic Persona Generator */}
                            <div
                                className="p-4 rounded-lg border"
                                style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                            >
                                <h4 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--accent)' }}>
                                    <Sparkles size={16} />
                                    Magic Persona Generator
                                </h4>
                                <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
                                    Describe a character (e.g., "A grumpy 19th-century lighthouse keeper") and the AI will hallucinate a backstory, emotions, and memories for it.
                                </p>
                                <textarea
                                    className="w-full h-20 rounded border p-2 text-sm focus:outline-none focus:ring-2 resize-none mb-3"
                                    style={{ backgroundColor: 'var(--bg-tertiary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', '--tw-ring-color': 'var(--accent)' }}
                                    placeholder="Enter cues here..."
                                    value={personaCues}
                                    onChange={(e) => setPersonaCues(e.target.value)}
                                />
                                <button
                                    onClick={handleGenerate}
                                    disabled={isGenerating || !personaCues.trim()}
                                    className="w-full py-2 rounded text-sm font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                                    style={{ backgroundColor: 'var(--accent)', color: 'white' }}
                                >
                                    {isGenerating ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                                    {isGenerating ? "Hallucinating..." : "Generate & Seed Persona"}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* DATA TAB */}
                    {activeTab === 'data' && (
                        <div className="space-y-6">
                            <div
                                className="p-4 rounded-lg border"
                                style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                            >
                                <h4 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--accent)' }}>
                                    <Database size={16} />
                                    Memory Management
                                </h4>
                                <div className="flex gap-3">
                                    <button
                                        onClick={exportGraph}
                                        className="flex-1 py-2 rounded text-sm flex items-center justify-center gap-2 transition-colors"
                                        style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}
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
                                                    e.target.value = null;
                                                }
                                            }}
                                            className="hidden"
                                            accept=".json"
                                        />
                                        <button
                                            onClick={() => fileInputRef.current?.click()}
                                            className="w-full py-2 rounded text-sm flex items-center justify-center gap-2 transition-colors"
                                            style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}
                                        >
                                            <Upload size={14} />
                                            Import Graph
                                        </button>
                                    </div>
                                </div>
                                <p className="text-xs mt-3" style={{ color: 'var(--text-muted)' }}>
                                    Back up your knowledge graph or restore from a JSON file. Import triggers a re-index of the vector memory.
                                </p>
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
                        disabled={isLoading}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isLoading}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50"
                        style={{ backgroundColor: 'var(--accent)' }}
                    >
                        <Save size={16} />
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SettingsModal;
