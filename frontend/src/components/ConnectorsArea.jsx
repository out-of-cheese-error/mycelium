import React, { useState, useEffect } from 'react';
import { useStore } from '../store';
import { Route, RefreshCw, Settings, Activity } from 'lucide-react';
import axios from 'axios';

const ConnectorsArea = () => {
    const { currentWorkspace, API_BASE, setActiveView, setChatInput } = useStore();
    const [connectors, setConnectors] = useState([]);
    const [loading, setLoading] = useState(false);

    // Configuration
    const [showConfig, setShowConfig] = useState(false);
    const [limit, setLimit] = useState(10);
    const [sampleSize, setSampleSize] = useState(50); // Default sample size
    const [expandedTopics, setExpandedTopics] = useState({});

    const toggleExpand = (id) => {
        setExpandedTopics(prev => ({
            ...prev,
            [id]: !prev[id]
        }));
    };

    const fetchConnectors = async () => {
        if (!currentWorkspace) return;
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/connectors/${currentWorkspace.id}`, {
                params: { limit, sample_size: sampleSize }
            });
            if (Array.isArray(res.data)) {
                setConnectors(res.data);
            } else {
                setConnectors([]);
            }
        } catch (e) {
            console.error("Failed to fetch connectors", e);
            setConnectors([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchConnectors();
    }, [currentWorkspace, limit, sampleSize]);

    if (!currentWorkspace) return null;

    return (
        <div className="absolute inset-0 bg-gray-900 overflow-y-auto p-8">
            <div className="max-w-4xl mx-auto">
                <div className="flex justify-between items-start mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                            <Route className="text-indigo-500" />
                            Connectors
                        </h1>
                        <p className="text-gray-400 mt-2">
                            Key bridges and brokers in your knowledge network (betweenness centrality).
                        </p>
                    </div>

                    <div className="flex gap-2">
                        <button
                            onClick={() => setShowConfig(!showConfig)}
                            className={`p-2 rounded-lg transition-colors ${showConfig ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}
                            title="Configure"
                        >
                            <Settings size={20} />
                        </button>
                        <button
                            onClick={fetchConnectors}
                            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-all shadow-lg hover:shadow-indigo-500/20"
                        >
                            <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                            Refresh
                        </button>
                    </div>
                </div>

                {/* Configuration Panel */}
                {showConfig && (
                    <div className="mb-8 bg-gray-800/50 border border-gray-700 rounded-xl p-5 animate-fade-in-up">
                        <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                            <Settings size={14} /> Configuration
                        </h3>
                        <div>
                            <label className="block text-xs text-gray-400 mb-1">
                                Number of Top Nodes ({limit})
                            </label>
                            <div className="flex items-center gap-4">
                                <input
                                    type="range"
                                    min="3"
                                    max="50"
                                    step="1"
                                    value={limit}
                                    onChange={(e) => setLimit(parseInt(e.target.value))}
                                    className="flex-1 accent-indigo-500"
                                />
                                <span className="text-white font-mono w-8 text-right">{limit}</span>
                            </div>
                        </div>

                        <div className="mt-4">
                            <label className="block text-xs text-gray-400 mb-1">
                                Analysis Sample Size (k={sampleSize})
                            </label>
                            <div className="flex items-center gap-4">
                                <input
                                    type="range"
                                    min="10"
                                    max="500"
                                    step="10"
                                    value={sampleSize}
                                    onChange={(e) => setSampleSize(parseInt(e.target.value))}
                                    className="flex-1 accent-indigo-500"
                                />
                                <span className="text-white font-mono w-8 text-right">{sampleSize}</span>
                            </div>
                            <p className="text-xs text-gray-500 mt-1">
                                Lower values are faster but less accurate. Use max for full accuracy on small graphs.
                            </p>
                        </div>
                    </div>
                )}

                {loading ? (
                    <div className="flex justify-center py-20 text-gray-500 animate-pulse">
                        Loading connectors...
                    </div>
                ) : connectors.length === 0 ? (
                    <div className="text-center py-20 text-gray-500">
                        No connectors found. Try adding more data to your graph.
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {connectors.map((node, index) => (
                            <div
                                key={node.id}
                                className={`bg-gray-800/50 border border-gray-700 p-4 rounded-xl hover:border-indigo-500/50 transition-all cursor-pointer ${expandedTopics[node.id] ? 'bg-gray-800' : ''}`}
                                onClick={() => toggleExpand(node.id)}
                            >
                                <div className="flex justify-between items-start">
                                    <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-full bg-indigo-900/50 text-indigo-400 flex items-center justify-center font-bold text-sm border border-indigo-500/30">
                                            #{index + 1}
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-white text-lg">{node.id}</h3>
                                            <span className="text-xs text-gray-400 bg-gray-900 px-2 py-0.5 rounded border border-gray-700">
                                                {node.type || 'Unknown'}
                                            </span>
                                        </div>
                                    </div>

                                    <div className="flex flex-col items-end">
                                        <div className="flex items-center gap-1 text-indigo-400 font-mono font-bold">
                                            <Activity size={14} />
                                            {(node.centrality || 0).toFixed(4)}
                                        </div>
                                        <div className="text-xs text-gray-500">
                                            Degree: {node.degree || 0}
                                        </div>
                                    </div>
                                </div>

                                {node.description && (
                                    <p className={`mt-3 text-sm text-gray-400 transition-all ${expandedTopics[node.id] ? '' : 'line-clamp-2'}`}>
                                        {node.description}
                                    </p>
                                )}

                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setChatInput(`Tell me more about "${node.id}" and its role as a connector in the graph.`);
                                        setActiveView('chat');
                                    }}
                                    className="mt-4 w-full py-2 bg-gray-700/50 hover:bg-indigo-600/20 hover:text-indigo-300 text-gray-400 rounded-lg text-sm transition-colors"
                                >
                                    Ask about this
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ConnectorsArea;
