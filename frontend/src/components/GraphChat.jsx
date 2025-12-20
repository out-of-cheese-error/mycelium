import React, { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, X, MessageSquare, Minimize2, Maximize2, Trash2, ExternalLink, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { useStore } from '../store';

const GraphChat = () => {
    const {
        graphChatMessages,
        graphChatFocusedNode,
        graphChatLoading,
        graphChatOpen,
        graphChatSettings,
        setGraphChatOpen,
        sendGraphChatMessage,
        setGraphChatFocusedNode,
        setGraphChatSettings,
        clearGraphChat,
        clearGraphHighlights,
        carryToMainChat,
        highlightedNodes
    } = useStore();

    const [input, setInput] = useState('');
    const [isMinimized, setIsMinimized] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [graphChatMessages]);

    // Focus input when panel opens
    useEffect(() => {
        if (graphChatOpen && !isMinimized && inputRef.current) {
            inputRef.current.focus();
        }
    }, [graphChatOpen, isMinimized]);

    const handleSend = () => {
        if (input.trim()) {
            sendGraphChatMessage(input);
            setInput('');
        }
    };

    const handleClearFocus = () => {
        setGraphChatFocusedNode(null);
        clearGraphHighlights();
    };

    const handleClearChat = () => {
        clearGraphChat();
    };

    const handleCarryToMain = () => {
        carryToMainChat();
    };

    if (!graphChatOpen) {
        // Show floating button to open chat
        return (
            <button
                onClick={() => setGraphChatOpen(true)}
                className="absolute bottom-4 right-4 z-30 bg-blue-600 hover:bg-blue-500 text-white p-4 rounded-full shadow-xl transition-all hover:scale-105"
                title="Open Graph Chat"
            >
                <MessageSquare size={24} />
            </button>
        );
    }

    if (isMinimized) {
        return (
            <div className="absolute bottom-4 right-4 z-30 bg-gray-900/95 backdrop-blur border border-gray-700 rounded-xl shadow-2xl p-3 flex items-center gap-3">
                <MessageSquare size={18} className="text-blue-400" />
                <span className="text-sm text-gray-300 font-medium">Graph Chat</span>
                {highlightedNodes.length > 0 && (
                    <span className="text-[10px] bg-green-600/30 text-green-300 px-1.5 py-0.5 rounded">
                        {highlightedNodes.length} nodes
                    </span>
                )}
                <button
                    onClick={() => setIsMinimized(false)}
                    className="text-gray-400 hover:text-white transition-colors"
                    title="Expand"
                >
                    <Maximize2 size={16} />
                </button>
                <button
                    onClick={() => setGraphChatOpen(false)}
                    className="text-gray-400 hover:text-red-400 transition-colors"
                    title="Close"
                >
                    <X size={16} />
                </button>
            </div>
        );
    }

    return (
        <div className="absolute bottom-4 right-4 z-30 w-96 h-[500px] max-h-[70vh] bg-gray-900/95 backdrop-blur border border-gray-700 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-fade-in-up">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-gray-800/80 border-b border-gray-700">
                <div className="flex items-center gap-2">
                    <MessageSquare size={18} className="text-blue-400" />
                    <span className="font-semibold text-gray-200">Graph Chat</span>
                    {highlightedNodes.length > 0 && (
                        <span className="text-[10px] bg-green-600/30 text-green-300 px-1.5 py-0.5 rounded">
                            {highlightedNodes.length} retrieved
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {graphChatMessages.length > 0 && (
                        <button
                            onClick={handleCarryToMain}
                            className="text-gray-400 hover:text-green-400 transition-colors p-1"
                            title="Continue in Main Chat"
                        >
                            <ExternalLink size={14} />
                        </button>
                    )}
                    <button
                        onClick={() => setShowSettings(!showSettings)}
                        className={`transition-colors p-1 ${showSettings ? 'text-blue-400' : 'text-gray-400 hover:text-white'}`}
                        title="Settings"
                    >
                        <Settings size={14} />
                    </button>
                    <button
                        onClick={handleClearChat}
                        className="text-gray-400 hover:text-orange-400 transition-colors p-1"
                        title="Clear Chat"
                    >
                        <Trash2 size={14} />
                    </button>
                    <button
                        onClick={() => setIsMinimized(true)}
                        className="text-gray-400 hover:text-white transition-colors p-1"
                        title="Minimize"
                    >
                        <Minimize2 size={14} />
                    </button>
                    <button
                        onClick={() => setGraphChatOpen(false)}
                        className="text-gray-400 hover:text-red-400 transition-colors p-1"
                        title="Close"
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            {/* Settings Panel */}
            {showSettings && (
                <div className="px-4 py-3 bg-gray-800/60 border-b border-gray-700 space-y-3">
                    <div className="text-xs text-gray-400 font-medium mb-2">Search Parameters</div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-[10px] text-gray-500 block mb-1">Max Nodes (k)</label>
                            <input
                                type="number"
                                min="1"
                                max="20"
                                value={graphChatSettings.k}
                                onChange={(e) => setGraphChatSettings({ k: parseInt(e.target.value) || 5 })}
                                className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500"
                            />
                        </div>
                        <div>
                            <label className="text-[10px] text-gray-500 block mb-1">Depth</label>
                            <input
                                type="number"
                                min="1"
                                max="5"
                                value={graphChatSettings.depth}
                                onChange={(e) => setGraphChatSettings({ depth: parseInt(e.target.value) || 2 })}
                                className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500"
                            />
                        </div>
                    </div>
                    <div className="text-[10px] text-gray-600">
                        k = starting nodes, depth = traversal hops
                    </div>
                </div>
            )}

            {/* Focused Node Banner */}
            {graphChatFocusedNode && (
                <div className="px-4 py-2 bg-blue-900/30 border-b border-blue-800/50 flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                        <div className="text-xs text-blue-300 font-medium">Focused Node:</div>
                        <div className="text-sm text-white font-semibold truncate">
                            {graphChatFocusedNode.id}
                        </div>
                        <div className="text-[10px] text-blue-400/70">
                            {graphChatFocusedNode.type || 'Unknown type'}
                        </div>
                    </div>
                    <button
                        onClick={handleClearFocus}
                        className="text-blue-400 hover:text-blue-200 transition-colors ml-2"
                        title="Clear Focus"
                    >
                        <X size={14} />
                    </button>
                </div>
            )}

            {/* Messages Area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
                {graphChatMessages.length === 0 ? (
                    <div className="text-center text-gray-500 text-sm mt-8 px-4">
                        <MessageSquare size={32} className="mx-auto mb-3 text-gray-600" />
                        <p className="mb-2">Ask questions about your knowledge graph.</p>
                        <p className="text-xs text-gray-600">
                            Click a node to focus on it, then ask questions.
                            Retrieved nodes will be highlighted in green.
                        </p>
                    </div>
                ) : (
                    graphChatMessages.map((m, i) => (
                        <div
                            key={i}
                            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[85%] px-3 py-2 rounded-xl text-sm ${m.role === 'user'
                                    ? 'bg-blue-600/80 text-white rounded-br-none'
                                    : m.role === 'system'
                                        ? 'bg-red-900/50 text-red-200 border border-red-800/50'
                                        : 'bg-gray-800 text-gray-200 rounded-bl-none border border-gray-700'
                                    }`}
                            >
                                {m.role === 'assistant' ? (
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                            p: ({ node, ...props }) => (
                                                <p className="mb-1.5 last:mb-0" {...props} />
                                            ),
                                            code: ({ node, inline, ...props }) =>
                                                inline ? (
                                                    <code
                                                        className="bg-black/30 px-1 py-0.5 rounded text-xs font-mono"
                                                        {...props}
                                                    />
                                                ) : (
                                                    <code
                                                        className="text-xs font-mono"
                                                        {...props}
                                                    />
                                                ),
                                            pre: ({ node, ...props }) => (
                                                <pre
                                                    className="bg-black/30 p-2 rounded my-1 overflow-x-auto text-xs"
                                                    {...props}
                                                />
                                            ),
                                        }}
                                    >
                                        {m.content || (graphChatLoading && i === graphChatMessages.length - 1 ? '...' : '')}
                                    </ReactMarkdown>
                                ) : (
                                    m.content
                                )}
                            </div>
                        </div>
                    ))
                )}
                {graphChatLoading && graphChatMessages.length > 0 &&
                    graphChatMessages[graphChatMessages.length - 1]?.content === '' && (
                        <div className="flex justify-start">
                            <div className="bg-gray-800 px-3 py-2 rounded-xl rounded-bl-none border border-gray-700 text-xs text-gray-400 flex items-center gap-2">
                                <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" />
                                Thinking...
                            </div>
                        </div>
                    )}
            </div>

            {/* Input Area */}
            <div className="p-3 bg-gray-800/50 border-t border-gray-700 flex gap-2">
                <input
                    ref={inputRef}
                    className="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    placeholder={
                        graphChatFocusedNode
                            ? `Ask about ${graphChatFocusedNode.id}...`
                            : 'Ask about the graph...'
                    }
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSend();
                        }
                    }}
                    disabled={graphChatLoading}
                />
                <button
                    onClick={handleSend}
                    disabled={graphChatLoading || !input.trim()}
                    className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white p-2 rounded-lg transition-colors"
                >
                    <Send size={18} />
                </button>
            </div>
        </div>
    );
};

export default GraphChat;
