import React, { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, Volume2, Loader, Square } from 'lucide-react';
import { useStore } from '../store';

const ChatArea = () => {
    const { messages, isLoading, sendMessage, currentWorkspace, currentThread, getAudioStreamUrl, chatInput, setChatInput, graphData, notesList, fetchNotesList, interruptGeneration } = useStore();
    // Removed local input state to persist drafts in store
    const scrollRef = useRef(null);

    // Suggestion State
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const [mentionQuery, setMentionQuery] = useState('');
    const inputRef = useRef(null);

    // Fetch notes on mount/workspace change
    useEffect(() => {
        if (currentWorkspace) {
            fetchNotesList(currentWorkspace.id);
        }
    }, [currentWorkspace]);

    // Removed sync effect (useEffect dependent on chatInput) since we use store directly now

    // Audio State
    const [playingId, setPlayingId] = useState(null); // Index of message playing
    const [audioLoadingId, setAudioLoadingId] = useState(null);
    const audioRef = useRef(new Audio());

    // Track if we switched threads to force scroll
    const lastThreadIdRef = useRef(null);

    useEffect(() => {
        const div = scrollRef.current;
        if (div) {
            // Check if thread changed
            const isNewThread = currentThread?.id !== lastThreadIdRef.current;

            if (isNewThread && messages.length > 0) {
                // Force scroll to bottom on new thread load
                div.scrollTop = div.scrollHeight;
                lastThreadIdRef.current = currentThread.id;
            } else {
                // Smart auto-scroll for same thread: Only scroll if we were already near the bottom
                const distanceToBottom = div.scrollHeight - div.scrollTop - div.clientHeight;
                if (distanceToBottom < 150) {
                    div.scrollTop = div.scrollHeight;
                }
            }
        }
    }, [messages, currentThread]);

    useEffect(() => {
        // Cleanup audio on unmount
        const audio = audioRef.current;
        return () => {
            audio.pause();
            audio.src = "";
        };
    }, []);

    const handleInputChange = (e) => {
        const val = e.target.value;
        const cursorValues = val.slice(0, e.target.selectionStart);
        const lastWord = cursorValues.split(/[\s\n]/).pop();

        setChatInput(val);

        if (lastWord.startsWith('@')) {
            const query = lastWord.slice(1).toLowerCase();
            setMentionQuery(query);

            const matchedNotes = notesList.filter(n => n.title.toLowerCase().includes(query)).slice(0, 5);
            // Search nodes (limit 5)
            const matchedNodes = graphData?.nodes
                ? graphData.nodes.filter(n => n.id.toLowerCase().includes(query)).slice(0, 5)
                : [];

            const combined = [
                ...matchedNotes.map(n => ({ type: 'Note', label: n.title, id: n.title })), // Use title as ID for notes
                ...matchedNodes.map(n => ({ type: 'Node', label: n.id, id: n.id }))
            ];

            setSuggestions(combined);
            setShowSuggestions(true);
        } else {
            setShowSuggestions(false);
        }
    };

    const insertMention = (item) => {
        const cursor = document.querySelector('input').selectionStart; // Simple assumption
        // Actually better to use ref if possible, but state is king.
        // We find the last @ before cursor.
        // Re-calculate last word index
        // Simplified: replace the *last occurrence* of @query with @[Label]
        // This is risky if user types "@foo @foo".

        // Robust way:
        const beforeCursor = chatInput.slice(0, inputRef.current.selectionStart);
        const afterCursor = chatInput.slice(inputRef.current.selectionStart);

        const lastAt = beforeCursor.lastIndexOf('@');
        const prefix = beforeCursor.slice(0, lastAt);
        const suffix = afterCursor; // Should be empty?

        // Actually we just want to replace the word being typed.
        const newVal = prefix + `@[${item.label}:${item.type}] ` + suffix;
        setChatInput(newVal);
        setShowSuggestions(false);
        inputRef.current.focus();
    };

    const handleSend = () => {
        if (chatInput.trim()) {
            sendMessage(chatInput);
            setChatInput('');
            setShowSuggestions(false);
        }
    };

    // ... (Audio functions remain same)

    const playAudio = React.useCallback((index, text) => {
        const audio = audioRef.current;
        if (playingId === index) {
            audio.pause();
            setPlayingId(null);
            setAudioLoadingId(null);
            return;
        }
        audio.pause();
        audio.currentTime = 0;
        setPlayingId(null);
        setAudioLoadingId(index);
        const url = getAudioStreamUrl(text);
        audio.src = url;
        audio.load();
        const onPlay = () => { setAudioLoadingId(null); setPlayingId(index); };
        const onEnd = () => { setPlayingId(null); setAudioLoadingId(null); audio.removeEventListener('playing', onPlay); audio.removeEventListener('ended', onEnd); audio.removeEventListener('error', onError); };
        const onError = (e) => { console.error("Audio playback error", e); setAudioLoadingId(null); setPlayingId(null); alert("Failed to play audio stream."); audio.removeEventListener('playing', onPlay); audio.removeEventListener('ended', onEnd); audio.removeEventListener('error', onError); };
        audio.addEventListener('playing', onPlay);
        audio.addEventListener('ended', onEnd);
        audio.addEventListener('error', onError);
        audio.play().catch(e => { console.error("Play request interrupted", e); setAudioLoadingId(null); });
    }, [playingId, getAudioStreamUrl]);

    return (
        <div className="absolute inset-0 z-10 bg-gray-900 flex flex-col">
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                    <div className="text-center text-gray-600 text-sm mt-10">Start the conversation...</div>
                )}
                {messages.map((m, i) => (
                    <ChatMessage
                        key={i}
                        role={m.role}
                        content={m.content}
                        index={i}
                        isPlaying={playingId === i}
                        isLoadingAudio={audioLoadingId === i}
                        onPlayAudio={playAudio}
                    />
                ))}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-gray-800 px-4 py-2 rounded-2xl rounded-bl-none border border-gray-700 text-xs text-gray-400 flex items-center gap-2">
                            <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
                            Thinking & Updating Memory...
                        </div>
                    </div>
                )}
            </div>

            <div className="p-4 bg-gray-900 border-t border-gray-800 flex gap-2 relative">
                {showSuggestions && suggestions.length > 0 && (
                    <div className="absolute bottom-full left-4 mb-2 w-64 bg-gray-800 border border-gray-700 rounded-xl shadow-xl overflow-hidden z-50">
                        <div className="text-xs text-gray-500 px-3 py-2 bg-gray-900 font-bold uppercase tracking-wider">Suggestions</div>
                        <ul className="max-h-48 overflow-y-auto">
                            {suggestions.map((item, idx) => (
                                <li
                                    key={idx}
                                    onClick={() => insertMention(item)}
                                    className="px-3 py-2 text-sm text-gray-200 hover:bg-blue-600/20 hover:text-blue-200 cursor-pointer flex items-center justify-between group"
                                >
                                    <span>{item.label}</span>
                                    <span className="text-[10px] bg-gray-700 px-1.5 py-0.5 rounded text-gray-400 group-hover:text-blue-300">{item.type}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                <input
                    ref={inputRef}
                    className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors shadow-inner"
                    placeholder={`Message ${currentWorkspace?.id || '...'}`}
                    value={chatInput}
                    onChange={handleInputChange}
                    onKeyDown={e => {
                        if (e.key === 'Enter') handleSend();
                        if (e.key === 'Escape') setShowSuggestions(false);
                    }}
                    autoFocus
                />
                {isLoading ? (
                    <button
                        onClick={interruptGeneration}
                        className="bg-red-600 hover:bg-red-500 text-white p-3 rounded-xl transition-colors shadow-lg animate-pulse"
                        title="Interrupt generation"
                    >
                        <Square size={20} fill="currentColor" />
                    </button>
                ) : (
                    <button onClick={handleSend} className="bg-blue-600 hover:bg-blue-500 text-white p-3 rounded-xl transition-colors shadow-lg">
                        <Send size={20} />
                    </button>
                )}
            </div>
        </div>
    );
};

// Memoized Message Component to prevent re-renders breaking selection
// We pass primitives (role, content) instead of the full object to avoid reference equality issues with mutable store state
const ChatMessage = React.memo(({ role, content, index, isPlaying, isLoadingAudio, onPlayAudio }) => {
    return (
        <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`relative max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed select-text ${role === 'user' ? 'bg-blue-600/90 text-white rounded-br-none' : 'bg-gray-800 text-gray-200 rounded-bl-none border border-gray-700'}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
                    p: ({ node, ...props }) => <p className="mb-2 last:mb-0 select-text" {...props} />,
                    a: ({ node, ...props }) => <a className="underline decoration-white/30 hover:decoration-white transition-all font-semibold" {...props} />,
                    ul: ({ node, ...props }) => <ul className="list-disc pl-4 mb-2 space-y-1" {...props} />,
                    ol: ({ node, ...props }) => <ol className="list-decimal pl-4 mb-2 space-y-1" {...props} />,
                    code: ({ node, inline, ...props }) => inline ? <code className="bg-black/20 px-1 py-0.5 rounded text-xs font-mono select-text" {...props} /> : <code className="text-xs font-mono bg-transparent select-text" {...props} />,
                    pre: ({ node, ...props }) => <pre className="bg-black/30 p-2 rounded-lg my-2 overflow-x-auto select-text" {...props} />,
                    img: ({ node, ...props }) => <img className="rounded-lg max-w-full max-h-80 object-contain my-2 bg-black/50" {...props} />,
                }}>
                    {content}
                </ReactMarkdown>
                {role === 'assistant' && (
                    <button onClick={() => onPlayAudio(index, content)} className="absolute -bottom-6 left-0 text-gray-500 hover:text-purple-400 transition-colors p-1" title="Read Aloud">
                        {isLoadingAudio ? <Loader size={14} className="animate-spin" /> : isPlaying ? <Square size={14} fill="currentColor" /> : <Volume2 size={14} />}
                    </button>
                )}
            </div>
        </div>
    );
});

export default ChatArea;
