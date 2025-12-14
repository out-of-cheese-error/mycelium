import React, { useState, useEffect, useRef } from 'react';
import { Play, Settings, Terminal } from 'lucide-react';
import { useStore } from '../store';

const GrowArea = () => {
    const { grow, growLogs, isLoading, currentWorkspace } = useStore();

    const logs = (currentWorkspace && growLogs[currentWorkspace.id]) ? growLogs[currentWorkspace.id] : [];

    // Local state for form input
    const [topic, setTopic] = useState('');
    const [iterations, setIterations] = useState(5);
    const [depth, setDepth] = useState(2);
    const [saveToNotes, setSaveToNotes] = useState(true);

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

    return (
        <div className="h-full flex flex-col bg-gray-900 text-gray-100 p-6 overflow-hidden">
            <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
                <Terminal className="text-purple-400" />
                Growth Engine
            </h1>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-full">
                {/* Configuration Panel */}
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-lg h-fit">
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
                                    onClick={() => useStore.getState().interruptGeneration()} // Reusing generic interrupt since we don't have specific stopGrow yet or renamed it
                                    className="px-4 py-3 bg-red-900/50 hover:bg-red-900/80 text-red-200 rounded-xl border border-red-800 transition-colors"
                                    title="Stop Growth"
                                >
                                    <div className="w-4 h-4 rounded-sm bg-current" />
                                </button>
                            )}
                        </div>
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
