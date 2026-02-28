import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AudioLines, Play, Square, Loader, Link, Trash2 } from 'lucide-react';
import { useStore } from '../store';

function cleanTextForDisplay(text) {
    // Strip references, citations, and wiki-style annotations
    text = text.replace(/\[(?:Image|File|Category|Citation needed)[^\]]*\]/gi, '');  // [Image:...], [Citation needed], etc.
    text = text.replace(/\[\d+\]/g, '');                             // [1], [32], etc.
    text = text.replace(/\[[\w\s,]+\]/g, '');                        // [a], [note 1], [edit], etc.
    text = text.replace(/\{\{[^}]*\}\}/g, '');                       // {{template}} wiki markup

    // Strip markdown formatting
    text = text.replace(/```[\s\S]*?```/g, '');                      // code blocks
    text = text.replace(/^#{1,6}\s+/gm, '');                         // headers
    text = text.replace(/\*{1,3}(.*?)\*{1,3}/g, '$1');               // bold/italic
    text = text.replace(/_{1,3}(.*?)_{1,3}/g, '$1');                 // underscored bold/italic
    text = text.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1');            // images
    text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');             // links
    text = text.replace(/`([^`]+)`/g, '$1');                         // inline code
    text = text.replace(/^[-*_]{3,}\s*$/gm, '');                     // horizontal rules
    text = text.replace(/^>\s?/gm, '');                              // blockquotes
    text = text.replace(/^\s*[-*+]\s+/gm, '');                       // unordered list markers
    text = text.replace(/^\s*\d+\.\s+/gm, '');                       // ordered list markers
    text = text.replace(/<[^>]+>/g, '');                             // HTML tags
    text = text.replace(/[ \t]+/g, ' ');                             // collapse whitespace
    text = text.replace(/\n{3,}/g, '\n\n');                          // collapse blank lines
    return text.trim();
}

// Split a long paragraph into sentence-sized chunks for streaming TTS.
// Each chunk stays under maxLen characters to avoid URL length limits with GET /audio/stream.
function splitIntoChunks(text, maxLen = 800) {
    if (text.length <= maxLen) return [text];

    const sentences = text.match(/[^.!?]+[.!?]+[\s]*/g) || [text];
    const chunks = [];
    let current = '';

    for (const sentence of sentences) {
        if (current.length + sentence.length > maxLen && current.length > 0) {
            chunks.push(current.trim());
            current = '';
        }
        current += sentence;
    }
    if (current.trim()) chunks.push(current.trim());
    return chunks;
}

const TTSReaderArea = () => {
    const API_BASE = useStore(state => state.API_BASE);

    // Text content
    const [text, setText] = useState('');
    const [paragraphs, setParagraphs] = useState([]);

    // URL loading
    const [url, setUrl] = useState('');
    const [isLoadingUrl, setIsLoadingUrl] = useState(false);
    const [urlError, setUrlError] = useState('');
    const [articleTitle, setArticleTitle] = useState('');

    // Playback
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentParagraphIndex, setCurrentParagraphIndex] = useState(null);
    const audioRef = useRef(null);
    const isPlayingRef = useRef(false);
    const paragraphListRef = useRef(null);

    // Parse paragraphs when text changes
    useEffect(() => {
        const cleaned = cleanTextForDisplay(text);
        const paras = cleaned
            .split(/\n\s*\n/)
            .map(p => p.replace(/\n/g, ' ').trim())
            .filter(p => p.length > 0);
        setParagraphs(paras);
    }, [text]);

    // Auto-scroll to currently playing paragraph
    useEffect(() => {
        if (currentParagraphIndex !== null && paragraphListRef.current) {
            const items = paragraphListRef.current.children;
            if (items[currentParagraphIndex]) {
                items[currentParagraphIndex].scrollIntoView({
                    behavior: 'smooth',
                    block: 'nearest'
                });
            }
        }
    }, [currentParagraphIndex]);

    // Cleanup on unmount
    useEffect(() => {
        return () => stopPlayback();
    }, []);

    const stopPlayback = useCallback(() => {
        isPlayingRef.current = false;
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.src = '';
            audioRef.current = null;
        }
        setIsPlaying(false);
        setCurrentParagraphIndex(null);
    }, []);

    // Stream a single text chunk via GET /audio/stream (returns WAV, plays as it downloads)
    const playAudioStream = useCallback(async (text) => {
        const url = API_BASE + "/audio/stream?input=" + encodeURIComponent(text);
        const audio = new Audio(url);
        audioRef.current = audio;

        await new Promise((resolve, reject) => {
            audio.onended = resolve;
            audio.onerror = (e) => reject(e);
            if (!isPlayingRef.current) {
                resolve();
                return;
            }
            audio.play().catch(reject);
        });
    }, [API_BASE]);

    const playFromParagraph = useCallback(async (startIndex) => {
        stopPlayback();
        isPlayingRef.current = true;
        setIsPlaying(true);

        for (let i = startIndex; i < paragraphs.length; i++) {
            if (!isPlayingRef.current) break;

            setCurrentParagraphIndex(i);

            // Split long paragraphs into sentence chunks for streaming
            const chunks = splitIntoChunks(paragraphs[i]);

            for (const chunk of chunks) {
                if (!isPlayingRef.current) break;

                try {
                    await playAudioStream(chunk);
                } catch (e) {
                    if (isPlayingRef.current) {
                        console.error('TTS playback error for paragraph', i, e);
                    }
                    // Stop on error
                    isPlayingRef.current = false;
                    break;
                }
            }
        }

        // Only reset if we weren't manually stopped
        if (isPlayingRef.current) {
            isPlayingRef.current = false;
            setIsPlaying(false);
            setCurrentParagraphIndex(null);
        }
    }, [paragraphs, stopPlayback, playAudioStream]);

    const handleLoadUrl = async () => {
        if (!url.trim()) return;
        setIsLoadingUrl(true);
        setUrlError('');
        try {
            const resp = await fetch(`${API_BASE}/audio/extract-text?url=${encodeURIComponent(url.trim())}`);
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `HTTP ${resp.status}`);
            }
            const data = await resp.json();
            setText(data.text);
            setArticleTitle(data.title || '');
        } catch (e) {
            setUrlError(e.message || 'Failed to load URL');
        } finally {
            setIsLoadingUrl(false);
        }
    };

    const handleClear = () => {
        stopPlayback();
        setText('');
        setArticleTitle('');
        setUrl('');
        setUrlError('');
    };

    return (
        <div className="flex flex-col h-full bg-[var(--bg-primary)] text-[var(--text-primary)] p-6 overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
                <AudioLines className="text-orange-400" size={24} />
                <h1 className="text-xl font-bold">TTS Reader</h1>
                {articleTitle && (
                    <span className="text-sm text-[var(--text-muted)] truncate ml-2">— {articleTitle}</span>
                )}
            </div>

            {/* URL Input Row */}
            <div className="flex gap-2 mb-4">
                <input
                    type="url"
                    value={url}
                    onChange={e => setUrl(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleLoadUrl()}
                    placeholder="Paste a URL to extract article text..."
                    className="flex-1 px-3 py-2 rounded bg-[var(--bg-secondary)] border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-orange-500"
                />
                <button
                    onClick={handleLoadUrl}
                    disabled={isLoadingUrl || !url.trim()}
                    className="flex items-center gap-2 px-4 py-2 rounded bg-[var(--bg-tertiary)] border border-[var(--border-color)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-orange-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isLoadingUrl ? <Loader size={14} className="animate-spin" /> : <Link size={14} />}
                    Load
                </button>
            </div>
            {urlError && <div className="text-red-400 text-sm mb-2">{urlError}</div>}

            {/* Main Content: Two Panels */}
            <div className="flex-1 flex gap-4 min-h-0 overflow-hidden">
                {/* Left: Textarea */}
                <div className="w-1/2 flex flex-col min-h-0">
                    <textarea
                        value={text}
                        onChange={e => setText(e.target.value)}
                        placeholder="Paste text here, or load from a URL above..."
                        className="flex-1 p-3 rounded bg-[var(--bg-secondary)] border border-[var(--border-color)] text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] resize-none font-mono focus:outline-none focus:border-orange-500 custom-scrollbar"
                    />
                    <div className="flex items-center gap-3 mt-2 text-xs text-[var(--text-muted)]">
                        <span>{paragraphs.length} paragraph{paragraphs.length !== 1 ? 's' : ''}</span>
                        {text && (
                            <button
                                onClick={handleClear}
                                className="flex items-center gap-1 text-red-400 hover:text-red-300 transition-colors"
                            >
                                <Trash2 size={12} /> Clear
                            </button>
                        )}
                    </div>
                </div>

                {/* Right: Paragraph List */}
                <div className="w-1/2 flex flex-col min-h-0">
                    <div ref={paragraphListRef} className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                        {paragraphs.map((para, i) => (
                            <div
                                key={i}
                                className={`flex items-start gap-2 p-3 rounded text-sm transition-colors cursor-pointer ${
                                    currentParagraphIndex === i
                                        ? 'bg-orange-900/30 border border-orange-500/50'
                                        : 'bg-[var(--bg-secondary)] border border-transparent hover:border-[var(--border-color)]'
                                }`}
                                onClick={() => playFromParagraph(i)}
                            >
                                <button
                                    className="mt-0.5 shrink-0 text-[var(--text-muted)] hover:text-orange-400 transition-colors"
                                    title={`Play from paragraph ${i + 1}`}
                                >
                                    {currentParagraphIndex === i && isPlaying
                                        ? <AudioLines size={14} className="text-orange-400 animate-pulse" />
                                        : <Play size={14} />}
                                </button>
                                <span className="text-xs text-[var(--text-muted)] shrink-0 w-5 mt-0.5">{i + 1}.</span>
                                <p className="text-[var(--text-secondary)] leading-relaxed line-clamp-3">{para}</p>
                            </div>
                        ))}
                        {paragraphs.length === 0 && (
                            <div className="flex flex-col items-center justify-center text-[var(--text-muted)] text-sm mt-16 gap-2">
                                <AudioLines size={32} className="opacity-30" />
                                <p>Paste text or load a URL to see paragraphs here.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Bottom Controls */}
            <div className="flex items-center gap-3 mt-4 pt-3 border-t border-[var(--border-color)]">
                {!isPlaying ? (
                    <button
                        onClick={() => playFromParagraph(0)}
                        disabled={paragraphs.length === 0}
                        className="flex items-center gap-2 px-5 py-2 rounded bg-orange-600 hover:bg-orange-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Play size={16} /> Read All
                    </button>
                ) : (
                    <button
                        onClick={stopPlayback}
                        className="flex items-center gap-2 px-5 py-2 rounded bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-colors"
                    >
                        <Square size={16} /> Stop
                    </button>
                )}
                {isPlaying && currentParagraphIndex !== null && (
                    <span className="text-sm text-[var(--text-muted)]">
                        Playing {currentParagraphIndex + 1} of {paragraphs.length}
                    </span>
                )}
            </div>
        </div>
    );
};

export default TTSReaderArea;
