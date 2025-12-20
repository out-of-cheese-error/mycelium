import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import ReactMarkdown from 'react-markdown';
import { Send, Cpu, Share2, MessageSquare, Network, Notebook, BookOpen, Layers, Flame, Route, BrainCircuit, RefreshCw } from 'lucide-react';
import { useStore } from './store';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import NotesArea from './components/NotesArea';
import LearnArea from './components/LearnArea';
import ConceptsArea from './components/ConceptsArea';
import HotTopicsArea from './components/HotTopicsArea';
import ConnectorsArea from './components/ConnectorsArea';
import GrowArea from './components/GrowArea';
import GraphChat from './components/GraphChat';

function App() {
    const { graphData, currentWorkspace, currentThread, activeView, setActiveView } = useStore();
    const hasActiveJobs = useStore(state => state.ingestJobs && state.ingestJobs.length > 0);
    const [selectedNode, setSelectedNode] = useState(null);

    // Graph chat highlighting
    const highlightedNodes = useStore(state => state.highlightedNodes);
    const highlightedEdges = useStore(state => state.highlightedEdges);
    const setGraphChatFocusedNode = useStore(state => state.setGraphChatFocusedNode);
    const setGraphChatOpen = useStore(state => state.setGraphChatOpen);

    // Create a Set for fast lookup of highlighted nodes
    const highlightedNodeSet = useMemo(() => new Set(highlightedNodes), [highlightedNodes]);

    // Helper to check if an edge is highlighted
    const isEdgeHighlighted = useCallback((link) => {
        return highlightedEdges.some(e =>
            (e.source === link.source?.id && e.target === link.target?.id) ||
            (e.source === link.target?.id && e.target === link.source?.id) ||
            (e.source === link.source && e.target === link.target) ||
            (e.source === link.target && e.target === link.source)
        );
    }, [highlightedEdges]);

    // Node color function with highlighting
    const getNodeColor = useCallback((node) => {
        if (highlightedNodeSet.has(node.id)) {
            return '#22c55e'; // Green for highlighted nodes
        }
        return undefined; // Let auto-color handle it
    }, [highlightedNodeSet]);

    // Link color function with highlighting
    const getLinkColor = useCallback((link) => {
        if (isEdgeHighlighted(link)) {
            return '#22c55e'; // Green for highlighted edges
        }
        return '#4b5563'; // Default gray
    }, [isEdgeHighlighted]);

    // Link width function with highlighting
    const getLinkWidth = useCallback((link) => {
        return isEdgeHighlighted(link) ? 3 : 1;
    }, [isEdgeHighlighted]);

    // Handle node click - show details and set as focused for graph chat
    const handleNodeClick = useCallback((node) => {
        setSelectedNode(node);
        setGraphChatFocusedNode({
            id: node.id,
            type: node.type || 'Unknown',
            description: node.description || ''
        });
        setGraphChatOpen(true);
    }, [setGraphChatFocusedNode, setGraphChatOpen]);

    // Global Ingest Polling
    useEffect(() => {
        let interval;
        const poll = () => useStore.getState().checkIngestStatus();

        if (currentWorkspace) {
            poll(); // Initial check
            // Fast poll if active jobs, slow poll (5s) if idle
            const delay = hasActiveJobs ? 1000 : 5000;
            interval = setInterval(poll, delay);
        }
        return () => clearInterval(interval);
    }, [currentWorkspace, hasActiveJobs]);

    if (!currentWorkspace) {
        return (
            <div className="flex h-screen w-full bg-gray-950 text-white font-sans">
                <Sidebar />
                <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                    <Share2 size={48} className="mb-4 text-gray-700" />
                    <h2 className="text-xl font-semibold text-gray-300">No Workspace Selected</h2>
                    <p>Create or select a workspace from the sidebar to begin.</p>
                </div>
            </div>
        )
    }

    return (
        <div className="flex h-screen w-full bg-gray-950 text-white font-sans overflow-hidden">
            <Sidebar />

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col h-full relative">

                {/* Header / Tabs */}
                <div className="h-14 border-b border-gray-800 bg-gray-900 flex items-center justify-between px-4 sticky top-0 z-20">
                    <div className="font-bold text-gray-200 flex items-center gap-2">
                        <Cpu size={18} className="text-blue-500" />
                        <span className="text-gray-400">{currentWorkspace.id}</span>
                        <span className="text-gray-600">/</span>
                        <span>{currentThread?.title || 'New Chat'}</span>
                    </div>

                    <div className="flex bg-gray-800 rounded p-1">
                        <button
                            onClick={() => setActiveView('chat')}
                            className={`flex items-center gap-2 px-3 py-1 rounded text-sm font-medium transition-colors ${activeView === 'chat' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <MessageSquare size={14} /> Chat
                        </button>
                        <button
                            onClick={() => setActiveView('graph')}
                            className={`flex items-center gap-2 px-3 py-1 rounded text-sm font-medium transition-colors ${activeView === 'graph' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <Network size={14} /> Graph
                        </button>
                        <button
                            onClick={() => {
                                setActiveView('notes');
                                if (currentWorkspace) useStore.getState().fetchNotesList(currentWorkspace.id);
                            }}
                            className={`flex items-center gap-2 px-3 py-1 rounded text-sm font-medium transition-colors ${activeView === 'notes' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <Notebook size={14} /> Notes
                        </button>
                        <button
                            onClick={() => {
                                setActiveView('learn');
                            }}
                            className={`flex items-center gap-2 px-3 py-1 rounded text-sm font-medium transition-colors ${activeView === 'learn' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <BookOpen size={14} /> Learn
                        </button>
                        <button
                            onClick={() => {
                                setActiveView('concepts');
                            }}
                            className={`flex items-center gap-2 px-3 py-1 rounded text-sm font-medium transition-colors ${activeView === 'concepts' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <Layers size={14} /> Concepts
                        </button>
                        <button
                            onClick={() => {
                                setActiveView('hot_topics');
                            }}
                            className={`flex items-center gap-2 px-3 py-1 rounded text-sm font-medium transition-colors ${activeView === 'hot_topics' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <Flame size={14} /> Hot Topics
                        </button>
                        <button
                            onClick={() => {
                                setActiveView('connectors');
                            }}
                            className={`flex items-center gap-2 px-3 py-1 rounded text-sm font-medium transition-colors ${activeView === 'connectors' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <Route size={14} /> Connectors
                        </button>
                        <button
                            onClick={() => {
                                setActiveView('grow');
                            }}
                            className={`flex items-center gap-2 px-3 py-1 rounded text-sm font-medium transition-colors ${activeView === 'grow' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                        >
                            <BrainCircuit size={14} /> Grow
                        </button>
                    </div>
                </div >

                {/* Content Views */}
                < div className="flex-1 relative overflow-hidden" >

                    {/* GRAPH VIEW */}
                    < div className={`absolute inset-0 z-0 bg-black ${activeView === 'graph' ? 'visible' : 'invisible'}`
                    }>
                        {/* ... graph content ... */}
                        < div className="absolute top-4 left-4 z-10 bg-black/60 backdrop-blur p-2 rounded border border-gray-800 text-xs text-gray-300" >
                            <div className="flex items-center justify-between gap-4 mb-2">
                                <span className="font-bold text-blue-400">Graph Stats</span>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        useStore.getState().fetchGraph();
                                    }}
                                    className="text-gray-500 hover:text-white transition-colors"
                                    title="Refresh Graph"
                                >
                                    <RefreshCw size={12} />
                                </button>
                            </div>
                            <div>Nodes: {graphData.nodes.length}</div>
                            <div>Edges: {graphData.links.length}</div>
                        </div >
                        {
                            graphData.nodes.length > 0 ? (
                                <>
                                    <ForceGraph2D
                                        graphData={graphData}
                                        nodeLabel="id"
                                        linkLabel="relation"
                                        nodeAutoColorBy="type"
                                        nodeColor={getNodeColor}
                                        nodeRelSize={6}
                                        linkColor={getLinkColor}
                                        linkWidth={getLinkWidth}
                                        backgroundColor="#000000"
                                        showNavInfo={false}
                                        width={window.innerWidth - 256}
                                        onNodeClick={handleNodeClick}
                                        cooldownTicks={100}
                                        warmupTicks={100}
                                    />
                                    {/* Node details panel - moved to top-left to not conflict with chat */}
                                    {selectedNode && (
                                        <div className="absolute top-32 left-4 z-20 bg-gray-900/90 backdrop-blur p-4 rounded-xl border border-gray-700 w-72 shadow-2xl animate-fade-in-up">
                                            <div className="flex justify-between items-start mb-2">
                                                <div>
                                                    <h3 className="font-bold text-white text-lg leading-tight">{selectedNode.id}</h3>
                                                    <span className="text-xs font-mono text-blue-400 bg-blue-900/30 px-1.5 py-0.5 rounded">{selectedNode.type || 'Unknown'}</span>
                                                </div>
                                                <button
                                                    onClick={() => setSelectedNode(null)}
                                                    className="text-gray-500 hover:text-white transition-colors"
                                                >
                                                    ✕
                                                </button>
                                            </div>
                                            <div className="text-sm text-gray-300 max-h-32 overflow-y-auto">
                                                {selectedNode.description || <span className="italic text-gray-500">No description available.</span>}
                                            </div>
                                        </div>
                                    )}
                                    {/* Graph Chat Panel */}
                                    <GraphChat />
                                </>
                            ) : (
                                <div className="h-full flex items-center justify-center text-gray-600 text-sm">
                                    <div className="text-center">
                                        <p className="mb-2">Graph is empty.</p>
                                        <GraphChat />
                                    </div>
                                </div>
                            )
                        }
                    </div >

                    {/* NOTES VIEW */}
                    < div className={`absolute inset-0 z-10 bg-gray-900 ${activeView === 'notes' ? 'block' : 'hidden'}`}>
                        <NotesArea />
                    </div >

                    {/* LEARN VIEW */}
                    < div className={`absolute inset-0 z-10 bg-gray-900 ${activeView === 'learn' ? 'block' : 'hidden'}`}>
                        <LearnArea />
                    </div >

                    {/* CONCEPTS VIEW */}
                    < div className={`absolute inset-0 z-10 bg-gray-900 ${activeView === 'concepts' ? 'block' : 'hidden'}`}>
                        <ConceptsArea />
                    </div >

                    {/* HOT TOPICS VIEW */}
                    < div className={`absolute inset-0 z-10 bg-gray-900 ${activeView === 'hot_topics' ? 'block' : 'hidden'}`}>
                        <HotTopicsArea />
                    </div >

                    {/* CONNECTORS VIEW */}
                    < div className={`absolute inset-0 z-10 bg-gray-900 ${activeView === 'connectors' ? 'block' : 'hidden'}`}>
                        <ConnectorsArea />
                    </div >

                    {/* GROW VIEW */}
                    < div className={`absolute inset-0 z-10 bg-gray-900 ${activeView === 'grow' ? 'block' : 'hidden'}`}>
                        <GrowArea />
                    </div >

                    {/* CHAT VIEW (Overlay on top if active) */}
                    {
                        activeView === 'chat' && (
                            <ChatArea />
                        )
                    }
                </div >
            </div >
        </div >
    );
}

export default App;
