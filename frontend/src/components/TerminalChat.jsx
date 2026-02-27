import React, { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, X, MessageSquare, Minimize2, Maximize2, Trash2, ChevronRight } from 'lucide-react';
import { useStore } from '../store';

// Compact thinking block for terminal chat panel
const TerminalThinkingBlock = ({ thinking, isThinking }) => {
    const [expanded, setExpanded] = useState(false);
    if (!thinking && !isThinking) return null;
    return (
        <div className="mb-1.5">
            <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-gray-300 transition-colors"
            >
                {isThinking && <div className="w-1 h-1 bg-green-500 rounded-full animate-pulse" />}
                <ChevronRight size={10} className={`transition-transform ${expanded ? 'rotate-90' : ''}`} />
                {isThinking ? 'Thinking...' : 'Thought process'}
            </button>
            {expanded && thinking && (
                <div className="mt-1 pl-2 border-l border-green-500/30 text-[10px] text-gray-500 italic max-h-40 overflow-y-auto">
                    {thinking}
                </div>
            )}
        </div>
    );
};

const TerminalChat = () => {
    const {
        terminalChatMessages,
        terminalChatLoading,
        terminalChatOpen,
        setTerminalChatOpen,
        sendTerminalChatMessage,
        clearTerminalChat,
    } = useStore();

    const [input, setInput] = useState('');
    const [isMinimized, setIsMinimized] = useState(false);
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [terminalChatMessages]);

    // Focus input when panel opens
    useEffect(() => {
        if (terminalChatOpen && !isMinimized && inputRef.current) {
            inputRef.current.focus();
        }
    }, [terminalChatOpen, isMinimized]);

    const handleSend = () => {
        if (input.trim()) {
            sendTerminalChatMessage(input);
            setInput('');
        }
    };

    if (!terminalChatOpen) {
        return (
            <button
                onClick={() => setTerminalChatOpen(true)}
                className="absolute bottom-4 right-4 z-30 bg-gray-600 hover:bg-gray-500 text-white p-4 rounded-full shadow-xl transition-all hover:scale-105"
                title="Open Terminal Chat"
            >
                <MessageSquare size={24} />
            </button>
        );
    }

    if (isMinimized) {
        return (
            <div className="absolute bottom-4 right-4 z-30 bg-gray-900/95 backdrop-blur border border-gray-700 rounded-xl shadow-2xl p-3 flex items-center gap-3">
                <MessageSquare size={18} className="text-green-400" />
                <span className="text-sm text-gray-300 font-medium">Terminal Chat</span>
                <button
                    onClick={() => setIsMinimized(false)}
                    className="text-gray-400 hover:text-white transition-colors"
                    title="Expand"
                >
                    <Maximize2 size={16} />
                </button>
                <button
                    onClick={() => setTerminalChatOpen(false)}
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
                    <MessageSquare size={18} className="text-green-400" />
                    <span className="font-semibold text-gray-200">Terminal Chat</span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={clearTerminalChat}
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
                        onClick={() => setTerminalChatOpen(false)}
                        className="text-gray-400 hover:text-red-400 transition-colors p-1"
                        title="Close"
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            {/* Messages Area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
                {terminalChatMessages.length === 0 ? (
                    <div className="text-center text-gray-500 text-sm mt-8 px-4">
                        <MessageSquare size={32} className="mx-auto mb-3 text-gray-600" />
                        <p className="mb-2">Ask me to run commands in the terminal.</p>
                        <p className="text-xs text-gray-600">
                            Describe what you want to do in plain language.
                            Commands run in a hidden tmux window so your terminal stays clean.
                        </p>
                    </div>
                ) : (
                    terminalChatMessages.map((m, i) => (
                        <div
                            key={i}
                            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[85%] px-3 py-2 rounded-xl text-sm ${m.role === 'user'
                                    ? 'bg-gray-600/80 text-white rounded-br-none'
                                    : m.role === 'system'
                                        ? 'bg-red-900/50 text-red-200 border border-red-800/50'
                                        : 'bg-gray-800 text-gray-200 rounded-bl-none border border-gray-700'
                                    }`}
                            >
                                {m.role === 'assistant' ? (
                                    <>
                                        <TerminalThinkingBlock thinking={m.thinking} isThinking={m.isThinking} />
                                        <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                                p: ({ node, ...props }) => (
                                                    <p className="mb-1.5 last:mb-0" {...props} />
                                                ),
                                                code: ({ node, className, children, ...props }) =>
                                                    className ? (
                                                        <code
                                                            className="text-xs font-mono"
                                                            {...props}
                                                        >{children}</code>
                                                    ) : (
                                                        <code
                                                            className="bg-black/30 px-1 py-0.5 rounded text-xs font-mono"
                                                            {...props}
                                                        >{children}</code>
                                                    ),
                                                pre: ({ node, ...props }) => (
                                                    <pre
                                                        className="bg-black/30 p-2 rounded my-1 overflow-x-auto text-xs"
                                                        {...props}
                                                    />
                                                ),
                                            }}
                                        >
                                            {m.content || (terminalChatLoading && i === terminalChatMessages.length - 1 ? '...' : '')}
                                        </ReactMarkdown>
                                    </>
                                ) : (
                                    m.content
                                )}
                            </div>
                        </div>
                    ))
                )}
                {terminalChatLoading && terminalChatMessages.length > 0 &&
                    terminalChatMessages[terminalChatMessages.length - 1]?.content === '' && (
                        <div className="flex justify-start">
                            <div className="bg-gray-800 px-3 py-2 rounded-xl rounded-bl-none border border-gray-700 text-xs text-gray-400 flex items-center gap-2">
                                <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-bounce" />
                                Running...
                            </div>
                        </div>
                    )}
            </div>

            {/* Input Area */}
            <div className="p-3 bg-gray-800/50 border-t border-gray-700 flex gap-2">
                <input
                    ref={inputRef}
                    className="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-green-500 transition-colors"
                    placeholder="Describe what to run..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSend();
                        }
                    }}
                    disabled={terminalChatLoading}
                />
                <button
                    onClick={handleSend}
                    disabled={terminalChatLoading || !input.trim()}
                    className="bg-gray-600 hover:bg-gray-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white p-2 rounded-lg transition-colors"
                >
                    <Send size={18} />
                </button>
            </div>
        </div>
    );
};

export default TerminalChat;
