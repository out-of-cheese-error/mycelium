import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useStore } from '../store';
import { LibraryBig, Search, Upload, Trash2, ChevronDown, ChevronRight, FileText, X, Settings, Sliders, ArrowUpToLine, Loader2, Globe, ExternalLink, CheckSquare, Square, ArrowLeft } from 'lucide-react';
import axios from 'axios';
import ForceGraph2D from 'react-force-graph-2d';

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

    // Crawler store
    const crawlerState = useStore(state => state.crawlerState);
    const crawlerResults = useStore(state => state.crawlerResults);
    const crawlerSeedInfo = useStore(state => state.crawlerSeedInfo);
    const crawlerGraph = useStore(state => state.crawlerGraph);
    const crawlerError = useStore(state => state.crawlerError);
    const crawlerIngestJobs = useStore(state => state.crawlerIngestJobs);
    const discoverCrawlLinks = useStore(state => state.discoverCrawlLinks);
    const ingestCrawlSelections = useStore(state => state.ingestCrawlSelections);
    const resetCrawler = useStore(state => state.resetCrawler);

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

    // Crawler local state
    const [crawlerOpen, setCrawlerOpen] = useState(false);
    const [seedUrl, setSeedUrl] = useState('');
    const [crawlerTopic, setCrawlerTopic] = useState('');
    const [includeWebSearch, setIncludeWebSearch] = useState(false);
    const [crawlDepth, setCrawlDepth] = useState(1);
    const [depthMinScore, setDepthMinScore] = useState(0.7);
    const [maxLinks, setMaxLinks] = useState(200);
    const [selectedUrls, setSelectedUrls] = useState(new Set());
    const graphContainerRef = useRef(null);
    const [graphDimensions, setGraphDimensions] = useState({ width: 0 });

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

    // Auto-select high-scoring links when results come in
    useEffect(() => {
        if (crawlerState === 'results' && crawlerResults.length > 0) {
            const highScore = new Set(
                crawlerResults.filter(l => l.score >= 0.7).map(l => l.url)
            );
            setSelectedUrls(highScore);
        }
    }, [crawlerState, crawlerResults]);

    // Measure graph container width when results arrive
    useEffect(() => {
        if (graphContainerRef.current && crawlerState === 'results') {
            setGraphDimensions({ width: graphContainerRef.current.clientWidth });
        }
    }, [crawlerState, crawlerGraph]);

    // Memoize graph data to prevent ForceGraph2D re-renders
    const crawlGraphData = useMemo(() => {
        if (!crawlerGraph) return { nodes: [], links: [] };
        return {
            nodes: crawlerGraph.nodes.map(n => ({ ...n })),
            links: (crawlerGraph.links || []).map(l => ({
                ...l,
                source: typeof l.source === 'object' ? l.source.id : l.source,
                target: typeof l.target === 'object' ? l.target.id : l.target,
            })),
        };
    }, [crawlerGraph]);

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

    // Crawler handlers
    const handleCrawlDiscover = (e) => {
        e.preventDefault();
        if (!seedUrl.trim() || !crawlerTopic.trim()) return;
        discoverCrawlLinks(seedUrl, crawlerTopic, includeWebSearch, crawlDepth, depthMinScore, maxLinks);
    };

    const toggleUrlSelection = (url) => {
        setSelectedUrls(prev => {
            const next = new Set(prev);
            if (next.has(url)) next.delete(url);
            else next.add(url);
            return next;
        });
    };

    const selectAllUrls = () => {
        setSelectedUrls(new Set(crawlerResults.map(l => l.url)));
    };

    const deselectAllUrls = () => {
        setSelectedUrls(new Set());
    };

    const handleCrawlIngest = () => {
        const toIngest = crawlerResults
            .filter(l => selectedUrls.has(l.url))
            .map(l => ({ url: l.url, source_name: l.title || l.url }));
        if (toIngest.length === 0) return;
        ingestCrawlSelections(toIngest);
    };

    const handleCloseCrawler = () => {
        setCrawlerOpen(false);
        resetCrawler();
        setSeedUrl('');
        setCrawlerTopic('');
        setIncludeWebSearch(false);
        setCrawlDepth(1);
        setDepthMinScore(0.7);
        setMaxLinks(200);
        setSelectedUrls(new Set());
    };

    // Filter search results by min_score for display
    const filteredResults = isSearchMode
        ? librarySearchResults.filter(r => r.score >= settings.library_min_score)
        : [];
    const belowThresholdCount = isSearchMode
        ? librarySearchResults.length - filteredResults.length
        : 0;

    if (!currentWorkspace) return null;

    // --- Crawler Panel ---
    const renderCrawlerPanel = () => {
        if (crawlerState === 'crawling') {
            return (
                <div className="text-center py-20">
                    <Loader2 size={40} className="mx-auto text-blue-400 animate-spin mb-4" />
                    <h3 className="text-lg font-semibold text-gray-300">Analyzing page and evaluating links...</h3>
                    <p className="text-sm text-gray-500 mt-2">
                        Fetching {seedUrl} and scoring links for relevance to your topic
                    </p>
                    {crawlDepth > 1 && (
                        <p className="text-xs text-gray-600 mt-1">Crawling up to {crawlDepth} levels deep — this may take a while</p>
                    )}
                    {includeWebSearch && (
                        <p className="text-xs text-gray-600 mt-1">Also searching the web for related pages</p>
                    )}
                </div>
            );
        }

        if (crawlerState === 'results') {
            const allSelected = selectedUrls.size === crawlerResults.length;
            return (
                <div>
                    {/* Results header */}
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <h3 className="text-sm font-bold text-gray-300">
                                Found {crawlerResults.length} relevant links
                            </h3>
                            {crawlerSeedInfo?.seed_title && (
                                <p className="text-xs text-gray-500 mt-0.5">from: {crawlerSeedInfo.seed_title}</p>
                            )}
                        </div>
                        <div className="flex items-center gap-3">
                            <button
                                onClick={allSelected ? deselectAllUrls : selectAllUrls}
                                className="text-xs text-gray-400 hover:text-white transition-colors"
                            >
                                {allSelected ? 'Deselect All' : 'Select All'}
                            </button>
                            <button
                                onClick={() => { resetCrawler(); setSelectedUrls(new Set()); }}
                                className="flex items-center gap-1 text-xs text-gray-500 hover:text-white transition-colors"
                            >
                                <ArrowLeft size={12} /> Back
                            </button>
                        </div>
                    </div>

                    {/* Crawl Graph Visualization */}
                    {crawlGraphData.nodes.length > 0 && (
                        <div ref={graphContainerRef} className="w-full bg-black/30 rounded-xl border border-gray-700 overflow-hidden mb-4" style={{ height: 350 }}>
                            {graphDimensions.width > 0 && (
                                <ForceGraph2D
                                    width={graphDimensions.width}
                                    height={350}
                                    graphData={crawlGraphData}
                                    nodeLabel={node => `${node.title || node.id}\nScore: ${((node.score || 0) * 100).toFixed(0)}%`}
                                    nodeColor={node =>
                                        node.type === 'seed' ? '#3b82f6' :
                                        node.score >= 0.6 ? '#22c55e' : '#ef4444'
                                    }
                                    nodeRelSize={5}
                                    nodeVal={node => node.type === 'seed' ? 3 : 1}
                                    linkColor={() => '#374151'}
                                    linkDirectionalArrowLength={3}
                                    linkDirectionalArrowRelPos={1}
                                    backgroundColor="rgba(0,0,0,0)"
                                    cooldownTicks={100}
                                    onNodeClick={(node) => {
                                        if (node.type !== 'seed') toggleUrlSelection(node.id);
                                    }}
                                />
                            )}
                        </div>
                    )}

                    {/* Links list */}
                    <div className="space-y-2 max-h-[calc(100vh-380px)] overflow-y-auto pr-1">
                        {crawlerResults.map((link, idx) => (
                            <div
                                key={link.url}
                                onClick={() => toggleUrlSelection(link.url)}
                                className={`p-3 rounded-xl border cursor-pointer transition-all ${
                                    selectedUrls.has(link.url)
                                        ? 'bg-blue-600/10 border-blue-500/40'
                                        : 'bg-gray-800/50 border-gray-700 hover:border-gray-600'
                                }`}
                            >
                                <div className="flex items-start gap-3">
                                    {/* Checkbox */}
                                    <div className="mt-0.5 flex-shrink-0">
                                        {selectedUrls.has(link.url)
                                            ? <CheckSquare size={18} className="text-blue-400" />
                                            : <Square size={18} className="text-gray-600" />
                                        }
                                    </div>

                                    {/* Content */}
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <p className="text-sm font-medium text-gray-200 truncate">{link.title}</p>
                                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${
                                                link.score >= 0.8 ? 'bg-green-500/20 text-green-400' :
                                                link.score >= 0.6 ? 'bg-amber-500/20 text-amber-400' :
                                                'bg-gray-700 text-gray-400'
                                            }`}>
                                                {(link.score * 100).toFixed(0)}%
                                            </span>
                                            {link.source === 'web_search' && (
                                                <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 flex-shrink-0">
                                                    Web Search
                                                </span>
                                            )}
                                            {link.source && link.source.startsWith('depth_') && (
                                                <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 flex-shrink-0">
                                                    {link.source.replace('_', ' ')}
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-xs text-gray-500 truncate">{link.url}</p>
                                        {link.reasoning && (
                                            <p className="text-xs text-gray-400 mt-1 italic">{link.reasoning}</p>
                                        )}
                                    </div>

                                    {/* External link */}
                                    <a
                                        href={link.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="text-gray-600 hover:text-gray-400 flex-shrink-0 mt-0.5"
                                    >
                                        <ExternalLink size={14} />
                                    </a>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Footer actions */}
                    <div className="mt-4 flex items-center justify-between pt-4 border-t border-gray-700/50">
                        <span className="text-sm text-gray-500">
                            {selectedUrls.size} of {crawlerResults.length} selected
                        </span>
                        <button
                            onClick={handleCrawlIngest}
                            disabled={selectedUrls.size === 0}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                                selectedUrls.size === 0
                                    ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                                    : 'bg-blue-600 hover:bg-blue-500 text-white'
                            }`}
                        >
                            <Upload size={16} />
                            Add Selected ({selectedUrls.size}) to Library
                        </button>
                    </div>
                </div>
            );
        }

        if (crawlerState === 'ingesting') {
            const allDone = crawlerIngestJobs.every(j => j.status === 'completed' || j.status === 'error');
            return (
                <div>
                    <h3 className="text-sm font-bold text-gray-300 mb-4">Ingesting pages to library...</h3>
                    <div className="space-y-2">
                        {crawlerIngestJobs.map((job, idx) => (
                            <div key={job.job_id || idx} className="flex items-center gap-3 p-3 bg-gray-800/50 border border-gray-700 rounded-lg">
                                {job.status === 'completed' ? (
                                    <CheckSquare size={16} className="text-green-400 flex-shrink-0" />
                                ) : job.status === 'error' ? (
                                    <X size={16} className="text-red-400 flex-shrink-0" />
                                ) : (
                                    <Loader2 size={16} className="text-blue-400 animate-spin flex-shrink-0" />
                                )}
                                <span className="text-sm text-gray-300 truncate">{job.url}</span>
                                <span className={`text-xs ml-auto flex-shrink-0 ${
                                    job.status === 'completed' ? 'text-green-400' :
                                    job.status === 'error' ? 'text-red-400' :
                                    'text-gray-500'
                                }`}>
                                    {job.status}
                                </span>
                            </div>
                        ))}
                    </div>
                    {allDone && (
                        <div className="mt-4 flex justify-end">
                            <button
                                onClick={handleCloseCrawler}
                                className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium transition-colors"
                            >
                                Done
                            </button>
                        </div>
                    )}
                </div>
            );
        }

        // idle state — input form
        return (
            <div className="max-w-xl mx-auto py-8">
                <div className="text-center mb-8">
                    <Globe size={40} className="mx-auto text-blue-400 mb-3" />
                    <h3 className="text-xl font-semibold text-gray-300">Intelligent Web Crawler</h3>
                    <p className="text-sm text-gray-500 mt-2">
                        Enter a starting URL and a topic. The AI will analyze links on the page and score them for relevance.
                    </p>
                </div>

                {crawlerError && (
                    <div className="mb-4 p-3 rounded-lg border bg-red-500/10 border-red-500/30 text-red-400 text-sm">
                        {crawlerError}
                    </div>
                )}

                <form onSubmit={handleCrawlDiscover} className="space-y-4">
                    <div>
                        <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider font-bold">Seed URL</label>
                        <input
                            type="url"
                            value={seedUrl}
                            onChange={(e) => setSeedUrl(e.target.value)}
                            placeholder="https://en.wikipedia.org/wiki/..."
                            required
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none transition-colors"
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider font-bold">Topic / Direction</label>
                        <input
                            type="text"
                            value={crawlerTopic}
                            onChange={(e) => setCrawlerTopic(e.target.value)}
                            placeholder="e.g., protein folding mechanisms, CRISPR applications..."
                            required
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none transition-colors"
                        />
                    </div>
                    <label className="flex items-center gap-3 p-3 bg-gray-800/50 border border-gray-700 rounded-lg cursor-pointer hover:border-gray-600 transition-colors">
                        <input
                            type="checkbox"
                            checked={includeWebSearch}
                            onChange={(e) => setIncludeWebSearch(e.target.checked)}
                            className="accent-blue-500 w-4 h-4"
                        />
                        <div>
                            <span className="text-sm text-gray-300">Also search the web</span>
                            <p className="text-xs text-gray-500">Use DuckDuckGo to find additional pages beyond the seed URL's links</p>
                        </div>
                    </label>
                    <div className="p-3 bg-gray-800/50 border border-gray-700 rounded-lg space-y-3">
                        <div>
                            <label className="block text-xs text-gray-400 mb-1">
                                Crawl depth: {crawlDepth} {crawlDepth === 1 ? '(seed page only)' : `(follow links ${crawlDepth - 1} level${crawlDepth > 2 ? 's' : ''} deep)`}
                            </label>
                            <input
                                type="range"
                                min="1"
                                max="3"
                                step="1"
                                value={crawlDepth}
                                onChange={(e) => setCrawlDepth(parseInt(e.target.value))}
                                className="w-full accent-blue-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">
                                Higher depth discovers more links but takes longer. Each level follows top-scoring pages from the previous level.
                            </p>
                        </div>
                        {crawlDepth > 1 && (
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">
                                    Min score to follow: {(depthMinScore * 100).toFixed(0)}%
                                </label>
                                <input
                                    type="range"
                                    min="0.3"
                                    max="0.9"
                                    step="0.1"
                                    value={depthMinScore}
                                    onChange={(e) => setDepthMinScore(parseFloat(e.target.value))}
                                    className="w-full accent-blue-500"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Only pages scoring above this threshold will be crawled for deeper links.
                                </p>
                            </div>
                        )}
                        <div>
                            <label className="block text-xs text-gray-400 mb-1">
                                Max links per page: {maxLinks}
                            </label>
                            <input
                                type="range"
                                min="50"
                                max="500"
                                step="50"
                                value={maxLinks}
                                onChange={(e) => setMaxLinks(parseInt(e.target.value))}
                                className="w-full accent-blue-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">
                                How many links to extract from each page. Higher values find more links but produce larger LLM prompts.
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3 pt-2">
                        <button
                            type="submit"
                            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors"
                        >
                            <Search size={18} />
                            Discover Links
                        </button>
                        <button
                            type="button"
                            onClick={handleCloseCrawler}
                            className="px-4 py-2.5 text-gray-400 hover:text-white transition-colors"
                        >
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        );
    };

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
                            onClick={() => { setCrawlerOpen(true); resetCrawler(); }}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                                crawlerOpen
                                    ? 'bg-blue-700 text-white'
                                    : 'bg-blue-600 hover:bg-blue-500 text-white'
                            }`}
                        >
                            <Globe size={18} />
                            Crawl Web
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

                {/* Crawler Panel (replaces normal content when open) */}
                {crawlerOpen ? (
                    <div className="bg-gray-800/30 border border-gray-700 rounded-2xl p-6">
                        {renderCrawlerPanel()}
                    </div>
                ) : (
                    <>
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
                    </>
                )}
            </div>
        </div>
    );
};

export default LibraryArea;
