import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '../store';
import { LibraryBig, Search, Upload, Trash2, ChevronDown, ChevronRight, FileText, X, Settings, Sliders, ArrowUpToLine, Loader2 } from 'lucide-react';
import axios from 'axios';

const LibraryArea = () => {
    const currentWorkspace = useStore(state => state.currentWorkspace);
    const librarySources = useStore(state => state.librarySources);
    const librarySearchResults = useStore(state => state.librarySearchResults);
    const librarySelectedChunks = useStore(state => state.librarySelectedChunks);
    const libraryStats = useStore(state => state.libraryStats);
    const libraryLoading = useStore(state => state.libraryLoading);
    const fetchLibrarySources = useStore(state => state.fetchLibrarySources);
    const fetchLibraryStats = useStore(state => state.fetchLibraryStats);
    const searchLibrary = useStore(state => state.searchLibrary);
    const fetchLibraryChunks = useStore(state => state.fetchLibraryChunks);
    const deleteLibrarySource = useStore(state => state.deleteLibrarySource);
    const uploadToLibrary = useStore(state => state.uploadToLibrary);
    const promoteLibrarySearch = useStore(state => state.promoteLibrarySearch);
    const API_BASE = useStore(state => state.API_BASE);

    const [searchQuery, setSearchQuery] = useState('');
    const [isSearchMode, setIsSearchMode] = useState(false);
    const [selectedSource, setSelectedSource] = useState(null);
    const [expandedChunks, setExpandedChunks] = useState({});
    const [promoting, setPromoting] = useState(false);
    const [promoteResult, setPromoteResult] = useState(null);
    const [showSettings, setShowSettings] = useState(false);
    const [settings, setSettings] = useState({
        library_k: 5,
        library_min_score: 0.5,
    });
    const [settingsLoaded, setSettingsLoaded] = useState(false);
    const fileInputRef = useRef(null);

    // Load workspace settings
    useEffect(() => {
        if (currentWorkspace) {
            fetchLibrarySources();
            fetchLibraryStats();
            // Load library settings from workspace config
            axios.get(`${API_BASE}/workspaces/${currentWorkspace.id}/settings`)
                .then(res => {
                    setSettings({
                        library_k: res.data.library_k ?? 5,
                        library_min_score: res.data.library_min_score ?? 0.5,
                    });
                    setSettingsLoaded(true);
                })
                .catch(() => setSettingsLoaded(true));
        }
    }, [currentWorkspace]);

    // Save settings: fetch full config, merge library fields, then save
    const saveSettings = (newSettings) => {
        setSettings(newSettings);
        if (currentWorkspace) {
            axios.get(`${API_BASE}/workspaces/${currentWorkspace.id}/settings`)
                .then(res => {
                    const merged = { ...res.data, ...newSettings };
                    return axios.post(`${API_BASE}/workspaces/${currentWorkspace.id}/settings`, merged);
                })
                .catch(e => console.error("Failed to save library settings", e));
        }
    };

    const handleSearch = (e) => {
        e.preventDefault();
        if (!searchQuery.trim()) return;
        setIsSearchMode(true);
        setSelectedSource(null);
        searchLibrary(searchQuery, settings.library_k);
    };

    const clearSearch = () => {
        setSearchQuery('');
        setIsSearchMode(false);
        useStore.setState({ librarySearchResults: [] });
    };

    const handleSourceClick = (source) => {
        setSelectedSource(source);
        setIsSearchMode(false);
        setExpandedChunks({});
        fetchLibraryChunks(source.source_id);
    };

    const handleDelete = (sourceId, e) => {
        e.stopPropagation();
        if (confirm('Delete this source and all its chunks from the library?')) {
            deleteLibrarySource(sourceId);
            if (selectedSource?.source_id === sourceId) {
                setSelectedSource(null);
            }
        }
    };

    const handleUpload = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            const files = Array.from(e.target.files);
            e.target.value = '';
            uploadToLibrary(files);
        }
    };

    const handlePromote = async () => {
        if (!searchQuery.trim()) return;
        setPromoting(true);
        setPromoteResult(null);
        const result = await promoteLibrarySearch(searchQuery, settings.library_k, settings.library_min_score);
        setPromoteResult(result);
        setPromoting(false);
        // Auto-clear after 8 seconds
        setTimeout(() => setPromoteResult(null), 8000);
    };

    const toggleChunk = (id) => {
        setExpandedChunks(prev => ({ ...prev, [id]: !prev[id] }));
    };

    const truncateText = (text, maxLen = 200) => {
        if (text.length <= maxLen) return text;
        return text.slice(0, maxLen) + '...';
    };

    // Filter search results by min_score for display
    const filteredResults = isSearchMode
        ? librarySearchResults.filter(r => r.score >= settings.library_min_score)
        : [];
    const belowThresholdCount = isSearchMode
        ? librarySearchResults.length - filteredResults.length
        : 0;

    if (!currentWorkspace) return null;

    return (
        <div className="absolute inset-0 bg-gray-900 overflow-y-auto p-8">
            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                            <LibraryBig className="text-amber-500" />
                            Library
                        </h1>
                        <p className="text-gray-400 mt-2">
                            Document store for on-demand RAG retrieval. The AI searches this when it needs deeper knowledge.
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        {libraryStats && (
                            <div className="text-sm text-gray-400 bg-gray-800 px-3 py-1.5 rounded-lg border border-gray-700">
                                {libraryStats.source_count} sources &middot; {libraryStats.chunk_count} chunks
                            </div>
                        )}
                        <button
                            onClick={() => setShowSettings(!showSettings)}
                            className={`p-2 rounded-lg transition-colors ${showSettings ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}
                            title="Library Settings"
                        >
                            <Sliders size={20} />
                        </button>
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-medium transition-colors"
                        >
                            <Upload size={18} />
                            Upload
                        </button>
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            accept=".pdf,.txt,.md"
                            onChange={handleUpload}
                            className="hidden"
                        />
                    </div>
                </div>

                {/* Settings Panel */}
                {showSettings && (
                    <div className="mb-6 bg-gray-800/50 border border-gray-700 rounded-xl p-5 animate-fade-in-up">
                        <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                            <Settings size={14} /> Library RAG Settings
                        </h3>
                        <p className="text-xs text-gray-500 mb-4">
                            These settings control how the AI searches and promotes library content to the knowledge graph.
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Top K */}
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">
                                    Results per search (k): {settings.library_k}
                                </label>
                                <input
                                    type="range"
                                    min="1"
                                    max="20"
                                    step="1"
                                    value={settings.library_k}
                                    onChange={(e) => saveSettings({ ...settings, library_k: parseInt(e.target.value) })}
                                    className="w-full accent-amber-500"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    How many chunks to retrieve per search query.
                                </p>
                            </div>

                            {/* Min Score */}
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">
                                    Min relevance score: {settings.library_min_score.toFixed(2)}
                                </label>
                                <input
                                    type="range"
                                    min="0"
                                    max="0.95"
                                    step="0.05"
                                    value={settings.library_min_score}
                                    onChange={(e) => saveSettings({ ...settings, library_min_score: parseFloat(e.target.value) })}
                                    className="w-full accent-amber-500"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Chunks below this cosine similarity are filtered out from search results and graph promotion.
                                    Lower = more results, higher = stricter relevance.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Search Bar */}
                <form onSubmit={handleSearch} className="mb-6">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search library for relevant passages..."
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-10 py-3 text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none transition-colors"
                        />
                        {isSearchMode && (
                            <button
                                type="button"
                                onClick={clearSearch}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                            >
                                <X size={18} />
                            </button>
                        )}
                    </div>
                </form>

                <div className="flex gap-6">
                    {/* Left Panel: Sources */}
                    <div className="w-72 flex-shrink-0">
                        <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Sources</h3>
                        {librarySources.length === 0 ? (
                            <div className="text-center py-10 border-2 border-dashed border-gray-800 rounded-xl bg-gray-900/50">
                                <FileText size={32} className="mx-auto text-gray-700 mb-3" />
                                <p className="text-sm text-gray-500">No documents yet</p>
                                <p className="text-xs text-gray-600 mt-1">Upload files to populate the library</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {librarySources.map(source => (
                                    <div
                                        key={source.source_id}
                                        onClick={() => handleSourceClick(source)}
                                        className={`p-3 rounded-lg border cursor-pointer transition-all group ${
                                            selectedSource?.source_id === source.source_id
                                                ? 'bg-amber-600/20 border-amber-500/50 text-white'
                                                : 'bg-gray-800/50 border-gray-700 text-gray-300 hover:border-gray-600 hover:bg-gray-800'
                                        }`}
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{source.source_name}</p>
                                                <p className="text-xs text-gray-500 mt-1">{source.chunk_count} chunks</p>
                                            </div>
                                            <button
                                                onClick={(e) => handleDelete(source.source_id, e)}
                                                className="text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all ml-2"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Right Panel: Search Results or Source Chunks */}
                    <div className="flex-1 min-w-0">
                        {libraryLoading ? (
                            <div className="flex justify-center py-20 text-gray-500 animate-pulse">
                                Loading...
                            </div>
                        ) : isSearchMode ? (
                            /* Search Results */
                            <div>
                                <div className="flex items-center justify-between mb-3">
                                    <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                        Search Results ({filteredResults.length})
                                    </h3>
                                    <div className="flex items-center gap-3">
                                        {belowThresholdCount > 0 && (
                                            <span className="text-xs text-gray-600">
                                                {belowThresholdCount} filtered below {(settings.library_min_score * 100).toFixed(0)}%
                                            </span>
                                        )}
                                        {filteredResults.length > 0 && (
                                            <button
                                                onClick={handlePromote}
                                                disabled={promoting}
                                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                                    promoting
                                                        ? 'bg-blue-900/50 text-blue-300 cursor-not-allowed'
                                                        : 'bg-blue-600 hover:bg-blue-500 text-white'
                                                }`}
                                            >
                                                {promoting
                                                    ? <Loader2 size={14} className="animate-spin" />
                                                    : <ArrowUpToLine size={14} />
                                                }
                                                {promoting ? 'Promoting...' : 'Promote to Graph'}
                                            </button>
                                        )}
                                    </div>
                                </div>
                                {/* Promote Result Banner */}
                                {promoteResult && (
                                    <div className={`mb-3 p-3 rounded-lg border text-sm ${
                                        promoteResult.entities > 0
                                            ? 'bg-green-500/10 border-green-500/30 text-green-400'
                                            : promoteResult.error
                                                ? 'bg-red-500/10 border-red-500/30 text-red-400'
                                                : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                                    }`}>
                                        {promoteResult.message || promoteResult.error || 'Done.'}
                                    </div>
                                )}
                                {filteredResults.length === 0 ? (
                                    <div className="text-center py-16 text-gray-500">
                                        {librarySearchResults.length > 0
                                            ? `Found ${librarySearchResults.length} results but all scored below the ${(settings.library_min_score * 100).toFixed(0)}% threshold. Try lowering the min relevance score in settings.`
                                            : `No results found for "${searchQuery}"`
                                        }
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        {filteredResults.map((result, idx) => (
                                            <div
                                                key={result.id || idx}
                                                className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 hover:border-gray-600 transition-colors"
                                            >
                                                <div className="flex items-center justify-between mb-2">
                                                    <span className="text-xs text-gray-500">
                                                        {result.source_name}
                                                        {result.page_number >= 0 && ` · Page ${result.page_number}`}
                                                        {` · Chunk ${result.chunk_index}`}
                                                    </span>
                                                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                                        result.score >= 0.8 ? 'bg-green-500/20 text-green-400' :
                                                        result.score >= 0.6 ? 'bg-amber-500/20 text-amber-400' :
                                                        'bg-gray-700 text-gray-400'
                                                    }`}>
                                                        {(result.score * 100).toFixed(0)}% match
                                                    </span>
                                                </div>
                                                <div
                                                    className="cursor-pointer"
                                                    onClick={() => toggleChunk(result.id)}
                                                >
                                                    <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                                                        {expandedChunks[result.id] ? result.text : truncateText(result.text, 300)}
                                                    </p>
                                                    {result.text.length > 300 && (
                                                        <button className="text-xs text-amber-500 mt-1 hover:underline">
                                                            {expandedChunks[result.id] ? 'Show less' : 'Show more'}
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ) : selectedSource ? (
                            /* Source Chunks */
                            <div>
                                <div className="flex items-center justify-between mb-3">
                                    <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                                        {selectedSource.source_name} ({librarySelectedChunks.length} chunks)
                                    </h3>
                                    <button
                                        onClick={() => setSelectedSource(null)}
                                        className="text-xs text-gray-500 hover:text-white"
                                    >
                                        Close
                                    </button>
                                </div>
                                <div className="space-y-2">
                                    {librarySelectedChunks.map((chunk, idx) => (
                                        <div
                                            key={chunk.id || idx}
                                            className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden"
                                        >
                                            <div
                                                className="p-3 flex items-center gap-2 cursor-pointer hover:bg-white/5 transition-colors"
                                                onClick={() => toggleChunk(chunk.id)}
                                            >
                                                {expandedChunks[chunk.id]
                                                    ? <ChevronDown size={14} className="text-gray-500 flex-shrink-0" />
                                                    : <ChevronRight size={14} className="text-gray-500 flex-shrink-0" />
                                                }
                                                <span className="text-xs text-gray-500 flex-shrink-0">#{chunk.chunk_index}</span>
                                                <p className="text-sm text-gray-400 truncate">
                                                    {truncateText(chunk.text, 120)}
                                                </p>
                                            </div>
                                            {expandedChunks[chunk.id] && (
                                                <div className="px-4 pb-4 border-t border-gray-700/50">
                                                    <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap mt-3">
                                                        {chunk.text}
                                                    </p>
                                                    {chunk.page_number >= 0 && (
                                                        <p className="text-xs text-gray-600 mt-2">Page {chunk.page_number}</p>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            /* Empty State */
                            <div className="text-center py-20 border-2 border-dashed border-gray-800 rounded-2xl bg-gray-900/50">
                                <Search size={48} className="mx-auto text-gray-700 mb-4" />
                                <h3 className="text-xl font-semibold text-gray-400">Search or Browse</h3>
                                <p className="text-gray-500 mt-2 max-w-md mx-auto">
                                    Use the search bar to find relevant passages, or click a source on the left to browse its content.
                                </p>
                                <div className="mt-6 p-4 bg-gray-800/50 rounded-lg border border-gray-700 max-w-md mx-auto text-left">
                                    <p className="text-xs text-gray-500 uppercase tracking-wider font-bold mb-2">How it works</p>
                                    <ul className="text-sm text-gray-400 space-y-1">
                                        <li>Documents uploaded here are chunked and embedded</li>
                                        <li>The AI can search the library on-demand during chat</li>
                                        <li>Relevant findings can be promoted to the knowledge graph</li>
                                        <li>Adjust k and min score in settings to tune retrieval</li>
                                    </ul>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LibraryArea;
