import React, { useState, useEffect, useRef } from 'react';
import { Play, Settings, Terminal, Search, Zap, AlertCircle } from 'lucide-react';
import { useStore } from '../store';

const GrowArea = () => {
    const { grow, growLogs, isLoading, currentWorkspace, knowledgeGaps, knowledgeGapsLoading, fetchKnowledgeGaps } = useStore();

    const logs = (currentWorkspace && growLogs[currentWorkspace.id]) ? growLogs[currentWorkspace.id] : [];

    // Local state for form input
    const [topic, setTopic] = useState('');
    const [iterations, setIterations] = useState(5);
    const [depth, setDepth] = useState(2);
    const [saveToNotes, setSaveToNotes] = useState(true);

    // Knowledge Gaps config
    const [gapLimit, setGapLimit] = useState(10);
    const [gapMaxDegree, setGapMaxDegree] = useState(2);

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
