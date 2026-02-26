import React, { useState, useEffect, useRef } from 'react';
import { Play, Settings, Terminal, Search, Zap, AlertCircle, GitMerge, ChevronRight, Link, ArrowRight, Brain } from 'lucide-react';
import { useStore } from '../store';

const GrowArea = () => {
    const {
        grow, growLogs, isLoading, currentWorkspace,
        knowledgeGaps, knowledgeGapsLoading, fetchKnowledgeGaps,
        collapseRedundancyLoading, collapseRedundancyPreview,
        previewCollapseRedundancy, executeCollapseRedundancy, clearCollapseRedundancyPreview,
        mergeSingleGroup,
        // Assign Singletons
        assignSingletonsLoading, assignSingletonsProposals, selectedProposalIds,
        previewAssignSingletons, executeAssignSingletons,
        toggleProposalSelection, selectAllProposals, deselectAllProposals, clearAssignSingletonsPreview,
        // Consolidation
        consolidationLoading, consolidationResult, consolidationProgress,
        runConsolidation, stopConsolidation, clearConsolidationResult
    } = useStore();

    const logs = (currentWorkspace && growLogs[currentWorkspace.id]) ? growLogs[currentWorkspace.id] : [];

    // Local state for form input
    const [topic, setTopic] = useState('');
    const [iterations, setIterations] = useState(5);
    const [depth, setDepth] = useState(2);
    const [saveToNotes, setSaveToNotes] = useState(true);

    // Knowledge Gaps config
    const [gapLimit, setGapLimit] = useState(10);
    const [gapMaxDegree, setGapMaxDegree] = useState(2);

    // Collapse Redundancy config
    const [redundancyN, setRedundancyN] = useState(20);
    const [redundancyIncludeNeighbors, setRedundancyIncludeNeighbors] = useState(true);

    // Assign Singletons config
    const [singletonsN, setSingletonsN] = useState(10);
    const [expandedProposals, setExpandedProposals] = useState({}); // Track which proposal reasons are expanded

    // Consolidation config
    const [consolidationThreshold, setConsolidationThreshold] = useState(0.85);
    const [consolidationWorkers, setConsolidationWorkers] = useState(4);

    const logsContainerRef = useRef(null);

    // Auto-scroll logs
    useEffect(() => {
        if (logsContainerRef.current) {
            logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
        }
    }, [logs]);

    const handleStart = () => {
        grow(iterations, topic, saveToNotes, null, depth);
    };

    const handleFindGaps = () => {
        fetchKnowledgeGaps(gapLimit, gapMaxDegree);
    };

    const handleSelectGap = (gap) => {
        setTopic(gap.id);
    };

    const handleGrowGap = (gap) => {
        setTopic(gap.id);
        // Optionally auto-start growth
        grow(iterations, gap.id, saveToNotes, null, depth);
    };

    return (
        <div className="h-full flex flex-col bg-gray-900 text-gray-100 p-6 overflow-hidden">
            <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
                <Terminal className="text-purple-400" />
                Growth Engine
            </h1>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-full overflow-hidden">
                {/* Configuration Panel */}
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-lg overflow-y-auto">
                    <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-purple-300">
                        <Settings size={18} /> Configuration
                    </h2>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Topic (Optional)</label>
                            <input
                                type="text"
                                value={topic}
                                onChange={(e) => setTopic(e.target.value)}
                                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:border-purple-500 focus:outline-none placeholder-gray-600"
                                placeholder="e.g. AI Safety, Quantum Physics..."
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Iterations</label>
                                <input
                                    type="number"
                                    min="1" max="20"
                                    value={iterations}
                                    onChange={(e) => setIterations(parseInt(e.target.value) || 1)}
                                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Depth</label>
                                <input
                                    type="number"
                                    min="1" max="5"
                                    value={depth}
                                    onChange={(e) => setDepth(parseInt(e.target.value) || 1)}
                                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                                />
                            </div>
                        </div>

                        <div className="flex items-center gap-2 py-2">
                            <input
                                type="checkbox"
                                id="saveNotes"
                                checked={saveToNotes}
                                onChange={(e) => setSaveToNotes(e.target.checked)}
                                className="rounded bg-gray-900 border-gray-700 text-purple-500 focus:ring-purple-500"
                            />
                            <label htmlFor="saveNotes" className="text-sm text-gray-300 cursor-pointer select-none">
                                Save findings to Notes
                            </label>
                        </div>


                        <div className="flex gap-2">
                            <button
                                onClick={handleStart}
                                disabled={isLoading}
                                className={`flex-1 py-3 px-4 rounded-xl flex items-center justify-center gap-2 font-semibold transition-all ${isLoading
                                    ? 'bg-gray-700 text-gray-400 cursor-not-allowed opacity-50'
                                    : 'bg-purple-600 hover:bg-purple-500 text-white shadow-lg hover:shadow-purple-500/20'
                                    }`}
                            >
                                {isLoading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Play size={18} fill="currentColor" />}
                                {isLoading ? 'Running...' : 'Start'}
                            </button>

                            {isLoading && (
                                <button
                                    onClick={() => useStore.getState().interruptGeneration()}
                                    className="px-4 py-3 bg-red-900/50 hover:bg-red-900/80 text-red-200 rounded-xl border border-red-800 transition-colors"
                                    title="Stop Growth"
                                >
                                    <div className="w-4 h-4 rounded-sm bg-current" />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Knowledge Gaps Section */}
                    <div className="mt-6 pt-6 border-t border-gray-700">
                        <h3 className="text-md font-semibold mb-3 flex items-center gap-2 text-amber-400">
                            <AlertCircle size={16} /> Knowledge Gaps
                        </h3>
                        <p className="text-xs text-gray-500 mb-3">
                            Find topics with few connections that could benefit from expansion.
                        </p>

                        <div className="grid grid-cols-2 gap-3 mb-3">
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Limit</label>
                                <input
                                    type="number"
                                    min="1" max="20"
                                    value={gapLimit}
                                    onChange={(e) => setGapLimit(parseInt(e.target.value) || 5)}
                                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:border-amber-500 focus:outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Max Connections</label>
                                <input
                                    type="number"
                                    min="0" max="5"
                                    value={gapMaxDegree}
                                    onChange={(e) => setGapMaxDegree(parseInt(e.target.value) || 2)}
                                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:border-amber-500 focus:outline-none"
                                />
                            </div>
                        </div>

                        <button
                            onClick={handleFindGaps}
                            disabled={knowledgeGapsLoading}
                            className="w-full py-2 px-3 rounded-lg flex items-center justify-center gap-2 text-sm font-medium transition-all bg-amber-900/30 hover:bg-amber-900/50 text-amber-300 border border-amber-800/50"
                        >
                            {knowledgeGapsLoading ? (
                                <div className="w-4 h-4 border-2 border-amber-300/30 border-t-amber-300 rounded-full animate-spin" />
                            ) : (
                                <Search size={14} />
                            )}
                            {knowledgeGapsLoading ? 'Searching...' : 'Find Gaps'}
                        </button>

                        {/* Gaps List */}
                        {knowledgeGaps.length > 0 && (
                            <div className="mt-3 space-y-2 max-h-48 overflow-y-auto">
                                {knowledgeGaps.map((gap, i) => (
                                    <div
                                        key={i}
                                        className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-2 hover:border-amber-600/50 transition-colors group"
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="flex-1 min-w-0">
                                                <div className="text-sm font-medium text-gray-200 truncate" title={gap.id}>
                                                    {gap.id}
                                                </div>
                                                <div className="text-xs text-gray-500 flex items-center gap-2">
                                                    <span className="bg-gray-800 px-1.5 py-0.5 rounded text-gray-400">{gap.type}</span>
                                                    <span>• {gap.degree} connection{gap.degree !== 1 ? 's' : ''}</span>
                                                </div>
                                            </div>
                                            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <button
                                                    onClick={() => handleSelectGap(gap)}
                                                    className="p-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 transition-colors"
                                                    title="Set as topic"
                                                >
                                                    <Search size={12} />
                                                </button>
                                                <button
                                                    onClick={() => handleGrowGap(gap)}
                                                    disabled={isLoading}
                                                    className="p-1.5 rounded bg-purple-900/50 hover:bg-purple-800 text-purple-300 hover:text-purple-100 transition-colors disabled:opacity-50"
                                                    title="Grow this topic"
                                                >
                                                    <Zap size={12} />
                                                </button>
                                            </div>
                                        </div>
                                        {gap.description && (
                                            <div className="text-xs text-gray-500 mt-1 line-clamp-2" title={gap.description}>
                                                {gap.description.slice(0, 80)}{gap.description.length > 80 ? '...' : ''}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {knowledgeGaps.length === 0 && !knowledgeGapsLoading && (
                            <div className="mt-3 text-xs text-gray-600 text-center py-2">
                                Click "Find Gaps" to discover weak points in your knowledge graph.
                            </div>
                        )}
                    </div>

                    {/* Collapse Redundancy Section */}
                    <div className="mt-6 pt-6 border-t border-gray-700">
                        <h3 className="text-md font-semibold mb-3 flex items-center gap-2 text-cyan-400">
                            <GitMerge size={16} /> Collapse Redundancy
                        </h3>
                        <p className="text-xs text-gray-500 mb-3">
                            Find and merge duplicate nodes that represent the same concept.
                        </p>

                        <div className="grid grid-cols-2 gap-3 mb-3">
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Top Nodes</label>
                                <input
                                    type="number"
                                    min="5" max="50"
                                    value={redundancyN}
                                    onChange={(e) => setRedundancyN(parseInt(e.target.value) || 20)}
                                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:border-cyan-500 focus:outline-none"
                                />
                            </div>
                            <div className="flex items-end">
                                <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={redundancyIncludeNeighbors}
                                        onChange={(e) => setRedundancyIncludeNeighbors(e.target.checked)}
                                        className="rounded bg-gray-900 border-gray-700 text-cyan-500 focus:ring-cyan-500"
                                    />
                                    Include Neighbors
                                </label>
                            </div>
                        </div>

                        <div className="flex gap-2">
                            <button
                                onClick={() => previewCollapseRedundancy(redundancyN, redundancyIncludeNeighbors)}
                                disabled={collapseRedundancyLoading || isLoading}
                                className="flex-1 py-2 px-3 rounded-lg flex items-center justify-center gap-2 text-sm font-medium transition-all bg-cyan-900/30 hover:bg-cyan-900/50 text-cyan-300 border border-cyan-800/50 disabled:opacity-50"
                            >
                                {collapseRedundancyLoading ? (
                                    <div className="w-4 h-4 border-2 border-cyan-300/30 border-t-cyan-300 rounded-full animate-spin" />
                                ) : (
                                    <Search size={14} />
                                )}
                                Preview
                            </button>
                            {collapseRedundancyPreview?.groups?.length > 0 && (
                                <button
                                    onClick={() => executeCollapseRedundancy(redundancyN, redundancyIncludeNeighbors)}
                                    disabled={collapseRedundancyLoading || isLoading}
                                    className="flex-1 py-2 px-3 rounded-lg flex items-center justify-center gap-2 text-sm font-medium transition-all bg-green-900/30 hover:bg-green-900/50 text-green-300 border border-green-800/50 disabled:opacity-50"
                                >
                                    <GitMerge size={14} />
                                    Execute Merge
                                </button>
                            )}
                        </div>

                        {/* Preview Results */}
                        {collapseRedundancyPreview?.groups?.length > 0 && (
                            <div className="mt-3 space-y-2 max-h-40 overflow-y-auto">
                                {collapseRedundancyPreview.groups.map((group, i) => (
                                    <div
                                        key={i}
                                        className="bg-gray-900/50 border border-gray-700/50 rounded-lg p-2"
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-1 text-sm flex-1 min-w-0">
                                                <span className="text-cyan-300 font-medium truncate">{group.canonical}</span>
                                                <ChevronRight size={12} className="text-gray-500 flex-shrink-0" />
                                                <span className="text-gray-400 truncate">{group.duplicates.join(', ')}</span>
                                            </div>
                                            <button
                                                onClick={() => mergeSingleGroup(group.canonical, group.duplicates)}
                                                disabled={collapseRedundancyLoading}
                                                className="ml-2 px-2 py-1 text-xs rounded bg-green-900/30 hover:bg-green-900/50 text-green-300 border border-green-800/50 flex items-center gap-1 flex-shrink-0 disabled:opacity-50"
                                                title="Merge this group"
                                            >
                                                <GitMerge size={10} />
                                                Merge
                                            </button>
                                        </div>
                                        {group.reason && (
                                            <div className="text-xs text-gray-500 mt-1">{group.reason}</div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Assign Singletons Section */}
                    <div className="mt-6 pt-6 border-t border-gray-700">
                        <h3 className="text-md font-semibold mb-3 flex items-center gap-2 text-emerald-400">
                            <Link size={16} /> Assign Singletons
                        </h3>
                        <p className="text-xs text-gray-500 mb-3">
                            Find orphaned nodes and suggest relations or merges with established nodes.
                        </p>

                        <div className="mb-3">
                            <label className="block text-xs text-gray-500 mb-1">Singletons to Analyze</label>
                            <input
                                type="number"
                                min="1" max="30"
                                value={singletonsN}
                                onChange={(e) => setSingletonsN(parseInt(e.target.value) || 10)}
                                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:border-emerald-500 focus:outline-none"
                            />
                        </div>

                        <button
                            onClick={() => previewAssignSingletons(singletonsN)}
                            disabled={assignSingletonsLoading || isLoading}
                            className="w-full py-2 px-3 rounded-lg flex items-center justify-center gap-2 text-sm font-medium transition-all bg-emerald-900/30 hover:bg-emerald-900/50 text-emerald-300 border border-emerald-800/50 disabled:opacity-50"
                        >
                            {assignSingletonsLoading ? (
                                <div className="w-4 h-4 border-2 border-emerald-300/30 border-t-emerald-300 rounded-full animate-spin" />
                            ) : (
                                <Search size={14} />
                            )}
                            {assignSingletonsLoading ? 'Analyzing...' : 'Analyze'}
                        </button>

                        {/* Proposals List */}
                        {assignSingletonsProposals?.proposals?.length > 0 && (
                            <div className="mt-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs text-gray-400">
                                        {selectedProposalIds.length} / {assignSingletonsProposals.proposals.filter(p => p.action !== 'skip').length} selected
                                    </span>
                                    <div className="flex gap-1">
                                        <button
                                            onClick={selectAllProposals}
                                            className="text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-400"
                                        >
                                            All
                                        </button>
                                        <button
                                            onClick={deselectAllProposals}
                                            className="text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-400"
                                        >
                                            None
                                        </button>
                                    </div>
                                </div>
                                <div className="space-y-2 max-h-48 overflow-y-auto">
                                    {assignSingletonsProposals.proposals.map((proposal) => (
                                        <div
                                            key={proposal.id}
                                            className={`bg-gray-900/50 border rounded-lg p-2 transition-colors ${proposal.action === 'skip'
                                                ? 'border-gray-700/30 opacity-50'
                                                : selectedProposalIds.includes(proposal.id)
                                                    ? 'border-emerald-600/50 bg-emerald-900/10'
                                                    : 'border-gray-700/50 hover:border-emerald-600/30'
                                                }`}
                                        >
                                            <div className="flex items-start gap-2">
                                                {proposal.action !== 'skip' && (
                                                    <input
                                                        type="checkbox"
                                                        checked={selectedProposalIds.includes(proposal.id)}
                                                        onChange={() => toggleProposalSelection(proposal.id)}
                                                        className="mt-1 rounded bg-gray-900 border-gray-700 text-emerald-500 focus:ring-emerald-500"
                                                    />
                                                )}
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-1 text-sm flex-wrap">
                                                        <span className="text-gray-200 font-medium truncate">{proposal.singleton_id}</span>
                                                        <ArrowRight size={12} className="text-gray-500 flex-shrink-0" />
                                                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${proposal.action === 'merge' ? 'bg-cyan-900/50 text-cyan-300' :
                                                            proposal.action === 'relate' ? 'bg-green-900/50 text-green-300' :
                                                                'bg-gray-800 text-gray-400'
                                                            }`}>
                                                            {proposal.action}
                                                        </span>
                                                        {proposal.target_id && (
                                                            <span className="text-gray-400 truncate">{proposal.target_id}</span>
                                                        )}
                                                        {proposal.relation && (
                                                            <span className="text-gray-500 text-xs">({proposal.relation})</span>
                                                        )}
                                                    </div>
                                                    {proposal.reason && (
                                                        <div
                                                            className={`text-xs text-gray-500 mt-1 cursor-pointer hover:text-gray-400 ${expandedProposals[proposal.id] ? '' : 'line-clamp-1'}`}
                                                            onClick={() => setExpandedProposals(prev => ({ ...prev, [proposal.id]: !prev[proposal.id] }))}
                                                            title={expandedProposals[proposal.id] ? 'Click to collapse' : 'Click to expand'}
                                                        >
                                                            {proposal.reason}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                {selectedProposalIds.length > 0 && (
                                    <button
                                        onClick={executeAssignSingletons}
                                        disabled={assignSingletonsLoading}
                                        className="w-full mt-3 py-2 px-3 rounded-lg flex items-center justify-center gap-2 text-sm font-medium transition-all bg-green-900/30 hover:bg-green-900/50 text-green-300 border border-green-800/50 disabled:opacity-50"
                                    >
                                        <Link size={14} />
                                        Execute Selected ({selectedProposalIds.length})
                                    </button>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Consolidate Graph Section */}
                    <div className="mt-6 pt-6 border-t border-gray-700">
                        <h3 className="text-md font-semibold mb-3 flex items-center gap-2 text-rose-400">
                            <Brain size={16} /> Consolidate Graph
                        </h3>
                        <p className="text-xs text-gray-500 mb-3">
                            Find semantically similar nodes via embeddings and merge, update, or remove redundant ones.
                        </p>

                        <div className="grid grid-cols-2 gap-3 mb-3">
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Similarity Threshold</label>
                                <input
                                    type="number"
                                    min="0.5" max="0.99" step="0.05"
                                    value={consolidationThreshold}
                                    onChange={(e) => setConsolidationThreshold(parseFloat(e.target.value) || 0.85)}
                                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:border-rose-500 focus:outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Max Workers</label>
                                <input
                                    type="number"
                                    min="1" max="8"
                                    value={consolidationWorkers}
                                    onChange={(e) => setConsolidationWorkers(parseInt(e.target.value) || 4)}
                                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-sm focus:border-rose-500 focus:outline-none"
                                />
                            </div>
                        </div>

                        {!consolidationLoading ? (
                            <button
                                onClick={() => runConsolidation(consolidationThreshold, consolidationWorkers)}
                                disabled={isLoading}
                                className="w-full py-2 px-3 rounded-lg flex items-center justify-center gap-2 text-sm font-medium transition-all bg-rose-900/30 hover:bg-rose-900/50 text-rose-300 border border-rose-800/50 disabled:opacity-50"
                            >
                                <Brain size={14} />
                                Run
                            </button>
                        ) : (
                            <div className="space-y-2">
                                <div className="flex items-center gap-2 text-xs text-gray-400">
                                    <div className="w-3 h-3 border-2 border-rose-300/30 border-t-rose-300 rounded-full animate-spin" />
                                    <span className="capitalize">
                                        {consolidationProgress?.phase === 'similarity' ? 'Finding similar nodes' :
                                         consolidationProgress?.phase === 'llm' ? 'LLM decisions' :
                                         consolidationProgress?.phase === 'applying' ? 'Applying changes' :
                                         consolidationProgress?.phase === 'fetching' ? 'Fetching embeddings' :
                                         'Starting...'}
                                    </span>
                                    {consolidationProgress?.total > 0 && (
                                        <span className="text-gray-500">
                                            {consolidationProgress.current}/{consolidationProgress.total}
                                        </span>
                                    )}
                                </div>
                                <div className="relative w-full h-2 bg-gray-800 rounded-full overflow-hidden">
                                    <div
                                        className="absolute inset-y-0 left-0 bg-rose-500 rounded-full transition-all duration-500"
                                        style={{ width: `${consolidationProgress?.progress || 0}%` }}
                                    />
                                </div>
                                <button
                                    onClick={stopConsolidation}
                                    className="w-full py-1.5 px-3 rounded-lg text-xs font-medium bg-red-900/30 hover:bg-red-900/50 text-red-300 border border-red-800/50 transition-colors"
                                >
                                    Stop
                                </button>
                            </div>
                        )}

                        {/* Results */}
                        {consolidationResult && (
                            <div className="mt-3 bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
                                <div className="grid grid-cols-2 gap-2 text-xs">
                                    <div className="text-gray-400">Nodes Analyzed: <span className="text-gray-200">{consolidationResult.nodes_analyzed || 0}</span></div>
                                    <div className="text-gray-400">Merges: <span className="text-cyan-300">{consolidationResult.merges || 0}</span></div>
                                    <div className="text-gray-400">Updates: <span className="text-green-300">{consolidationResult.updates || 0}</span></div>
                                    <div className="text-gray-400">Deletes: <span className="text-red-300">{consolidationResult.deletes || 0}</span></div>
                                </div>
                                <button
                                    onClick={clearConsolidationResult}
                                    className="mt-2 text-xs text-gray-600 hover:text-gray-400"
                                >
                                    Clear
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* Logs / Output Panel */}
                <div className="md:col-span-2 bg-black/40 rounded-xl border border-gray-700 p-4 flex flex-col min-h-0">
                    <div className="flex items-center justify-between mb-2">
                        <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider">Process Log</h2>
                        <span className="text-xs text-gray-600">{logs.length} events</span>
                    </div>

                    <div ref={logsContainerRef} className="flex-1 overflow-y-auto space-y-2 font-mono text-sm p-2">
                        {logs.length === 0 && (
                            <div className="text-gray-600 italic text-center mt-10">No growth logs yet. Start a process to see results here.</div>
                        )}
                        {logs.map((log, i) => (
                            <div key={i} className={`p-2 rounded border-l-2 ${log.type === 'error' ? 'border-red-500 bg-red-900/10 text-red-300' :
                                log.type === 'success' ? 'border-green-500 bg-green-900/10 text-green-300' :
                                    'border-blue-500 bg-blue-900/10 text-gray-300'
                                }`}>
                                <span className="opacity-50 mr-2">[{i + 1}]</span>
                                {log.text}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default GrowArea;
