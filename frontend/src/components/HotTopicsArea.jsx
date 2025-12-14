import React, { useState, useEffect } from 'react';
import { useStore } from '../store';
import { Flame, RefreshCw, Settings, TrendingUp } from 'lucide-react';
import axios from 'axios';

const HotTopicsArea = () => {
    const { currentWorkspace, API_BASE, setActiveView, setChatInput } = useStore();
    const [hotTopics, setHotTopics] = useState([]);
    const [loading, setLoading] = useState(false);

    // Configuration
    const [showConfig, setShowConfig] = useState(false);
    const [limit, setLimit] = useState(10);
    const [expandedTopics, setExpandedTopics] = useState({});

    const toggleExpand = (id) => {
        setExpandedTopics(prev => ({
            ...prev,
            [id]: !prev[id]
        }));
    };

    const fetchHotTopics = async () => {
        if (!currentWorkspace) return;
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/hot_topics/${currentWorkspace.id}`, {
                params: { limit }
            });
            if (Array.isArray(res.data)) {
                setHotTopics(res.data);
            } else {
                setHotTopics([]);
            }
        } catch (e) {
            console.error("Failed to fetch hot topics", e);
            setHotTopics([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHotTopics();
    }, [currentWorkspace, limit]);

    if (!currentWorkspace) return null;

    return (
        <div className="absolute inset-0 bg-gray-900 overflow-y-auto p-8">
            <div className="max-w-4xl mx-auto">
                <div className="flex justify-between items-start mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                            <Flame className="text-orange-500" />
                            Hot Topics
                        </h1>
                        <p className="text-gray-400 mt-2">
                            Top entities ranked by their connectivity (degree centrality).
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
                            onClick={fetchHotTopics}
                            className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-medium transition-all shadow-lg hover:shadow-orange-500/20"
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
                                    className="flex-1 accent-orange-500"
                                />
                                <span className="text-white font-mono w-8 text-right">{limit}</span>
                            </div>
                        </div>
                    </div>
                )}

                {loading ? (
                    <div className="flex justify-center py-20 text-gray-500 animate-pulse">
                        Loading hot topics...
                    </div>
                ) : hotTopics.length === 0 ? (
                    <div className="text-center py-20 text-gray-500">
                        No hot topics found. Try adding more data to your graph.
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {hotTopics.map((topic, index) => (
                            <div
                                key={topic.id}
                                className={`bg-gray-800/50 border border-gray-700 p-4 rounded-xl hover:border-orange-500/50 transition-all cursor-pointer ${expandedTopics[topic.id] ? 'bg-gray-800' : ''}`}
                                onClick={() => toggleExpand(topic.id)}
                            >
                                <div className="flex justify-between items-start">
                                    <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-full bg-orange-900/50 text-orange-400 flex items-center justify-center font-bold text-sm border border-orange-500/30">
                                            #{index + 1}
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-white text-lg">{topic.id}</h3>
                                            <span className="text-xs text-gray-400 bg-gray-900 px-2 py-0.5 rounded border border-gray-700">
                                                {topic.type || 'Unknown'}
                                            </span>
                                        </div>
                                    </div>

                                    <div className="flex flex-col items-end">
                                        <div className="flex items-center gap-1 text-orange-400 font-mono font-bold">
                                            <TrendingUp size={14} />
                                            {(topic.centrality || 0).toFixed(4)}
                                        </div>
                                        <div className="text-xs text-gray-500">
                                            Degree: {topic.degree || 0}
                                        </div>
                                    </div>
                                </div>

                                {topic.description && (
                                    <p className={`mt-3 text-sm text-gray-400 transition-all ${expandedTopics[topic.id] ? '' : 'line-clamp-2'}`}>
                                        {topic.description}
                                    </p>
                                )}

                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setChatInput(`Tell me more about "${topic.id}" and why it is a hot topic.`);
                                        setActiveView('chat');
                                    }}
                                    className="mt-4 w-full py-2 bg-gray-700/50 hover:bg-orange-600/20 hover:text-orange-300 text-gray-400 rounded-lg text-sm transition-colors"
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

export default HotTopicsArea;
