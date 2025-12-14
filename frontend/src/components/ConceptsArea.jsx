import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '../store';
import { Sparkles, ChevronDown, ChevronRight, Share2, Layers, RefreshCw, Settings, Sliders, MessageSquare } from 'lucide-react';
import axios from 'axios';
import ForceGraph2D from 'react-force-graph-2d';

// ... ConceptGraph component ...
const ConceptGraph = ({ nodeIds }) => {
    const graphData = useStore(state => state.graphData);
    const containerRef = useRef(null);
    const [dimensions, setDimensions] = useState({ width: 0, height: 300 });

    useEffect(() => {
        if (containerRef.current) {
            setDimensions({
                width: containerRef.current.clientWidth,
                height: 300
            });
        }
    }, []);

    // Construct Subgraph - Memoized to prevent frequent re-renders of ForceGraph
    const { nodes, links } = React.useMemo(() => {
        const relevantNodes = graphData.nodes.filter(n => nodeIds.includes(n.id)).map(n => ({ ...n }));
        const relevantLinks = graphData.links.filter(l => {
            const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
            const targetId = typeof l.target === 'object' ? l.target.id : l.target;
            return nodeIds.includes(sourceId) && nodeIds.includes(targetId);
        }).map(l => ({
            ...l,
            source: typeof l.source === 'object' ? l.source.id : l.source,
            target: typeof l.target === 'object' ? l.target.id : l.target
        }));
        return { nodes: relevantNodes, links: relevantLinks };
    }, [graphData, nodeIds]);

    // Prepare data object for ForceGraph - Memoized
    const finalGraphData = React.useMemo(() => ({ nodes, links }), [nodes, links]);

    if (nodes.length === 0) return <div className="text-gray-500 text-xs p-4">No graph data available.</div>;

    return (
        <div ref={containerRef} className="w-full bg-black/50 rounded-lg border border-gray-700 overflow-hidden my-4">
            {dimensions.width > 0 && (
                <ForceGraph2D
                    width={dimensions.width}
                    height={dimensions.height}
                    graphData={finalGraphData}
                    nodeLabel="id"
                    nodeColor={() => "#a855f7"} // Purple
                    nodeRelSize={6}
                    linkColor={() => "#4b5563"}
                    backgroundColor="rgba(0,0,0,0)"
                    cooldownTicks={100}
                />
            )}
        </div>
    );
};

const ConceptsArea = () => {
    const currentWorkspace = useStore(state => state.currentWorkspace);
    const API_BASE = useStore(state => state.API_BASE);
    const graphData = useStore(state => state.graphData);
    const setActiveView = useStore(state => state.setActiveView);
    const setChatInput = useStore(state => state.setChatInput);
    const [concepts, setConcepts] = useState([]);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [expanded, setExpanded] = useState({});

    // Configuration State
    const [showConfig, setShowConfig] = useState(false);
    const [config, setConfig] = useState({
        resolution: 0.9,
        max_clusters: 25,
        min_cluster_size: 5
    });

    const fetchConcepts = async () => {
        if (!currentWorkspace) return;
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/concepts/${currentWorkspace.id}`);
            if (Array.isArray(res.data)) {
                setConcepts(res.data);
            } else {
                console.warn("API returned non-array for concepts:", res.data);
                setConcepts([]);
            }
        } catch (e) {
            console.error("Failed to fetch concepts", e);
            setConcepts([]);
        } finally {
            setLoading(false);
        }
    };

    const generateConcepts = async () => {
        if (!currentWorkspace) return;
        setGenerating(true);
        setConcepts([]); // Clear existing for fresh stream
        setExpanded({}); // Collapse all on new generation

        try {
            const response = await fetch(`${API_BASE}/concepts/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workspace_id: currentWorkspace.id,
                    ...config
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Server Error ${response.status}: ${errorText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;

                // Process complete lines
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep the last incomplete chunk

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const concept = JSON.parse(line);
                        setConcepts(prev => [...prev, concept]);
                    } catch (e) {
                        console.warn("Failed to parse concept chunk:", line);
                    }
                }
            }

        } catch (e) {
            console.error("Failed to generate concepts", e);
            alert(`Failed to generate concepts: ${e.message}`);
        } finally {
            setGenerating(false);
        }
    };

    useEffect(() => {
        fetchConcepts();
    }, [currentWorkspace]);

    // Calculate node degrees for heatmapping
    const { nodeDegrees, maxDegree } = React.useMemo(() => {
        const degrees = {};
        let max = 0;

        // Initialize
        graphData.nodes.forEach(n => degrees[n.id] = 0);

        // Count connections
        graphData.links.forEach(l => {
            const source = typeof l.source === 'object' ? l.source.id : l.source;
            const target = typeof l.target === 'object' ? l.target.id : l.target;
            if (degrees[source] !== undefined) degrees[source]++;
            if (degrees[target] !== undefined) degrees[target]++;
        });

        Object.values(degrees).forEach(d => {
            if (d > max) max = d;
        });

        return { nodeDegrees: degrees, maxDegree: Math.max(max, 1) };
    }, [graphData]);

    const getNodeColor = (nodeId) => {
        const degree = nodeDegrees[nodeId] || 0;
        const normalized = Math.min(degree / 10, 1); // Cap at 10 for coloring purposes
        // HSL: Blue (220) to Purple (280) to Red (360/0)
        // Let's do a simple gradient: Dark Blue/Gray -> Purple -> Bright Purple
        // Or opacity based? 
        // User asked for "color them", let's do a heatmap intensity (Purple scale)
        const intensity = 0.2 + (normalized * 0.8); // 0.2 to 1.0 alpha
        return `rgba(168, 85, 247, ${intensity})`; // Purple with varying opacity
    };

    const toggleExpand = (id) => {
        setExpanded(prev => ({ ...prev, [id]: !prev[id] }));
    };

    if (!currentWorkspace) return null;

    return (
        <div className="absolute inset-0 bg-gray-900 overflow-y-auto p-8">
            <div className="max-w-4xl mx-auto">
                <div className="flex justify-between items-start mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                            <Layers className="text-purple-500" />
                            Knowledge Concepts
                        </h1>
                        <p className="text-gray-400 mt-2">
                            Clusters of related knowledge automatically extracted from your graph.
                        </p>
                    </div>

                    <div className="flex flex-col items-end gap-2">
                        <div className="flex gap-2">
                            <button
                                onClick={() => setShowConfig(!showConfig)}
                                className={`p-2 rounded-lg transition-colors ${showConfig ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}
                                title="Configure Algorithm"
                            >
                                <Sliders size={20} />
                            </button>
                            <button
                                onClick={generateConcepts}
                                disabled={generating}
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${generating
                                    ? 'bg-purple-900/50 text-purple-300 cursor-not-allowed'
                                    : 'bg-purple-600 hover:bg-purple-500 text-white shadow-lg hover:shadow-purple-500/20'
                                    }`}
                            >
                                {generating ? <RefreshCw className="animate-spin" size={18} /> : <Sparkles size={18} />}
                                {generating ? 'Synthesizing...' : 'Generate Analysis'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Configuration Panel */}
                {showConfig && (
                    <div className="mb-8 bg-gray-800/50 border border-gray-700 rounded-xl p-5 animate-fade-in-up">
                        <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                            <Settings size={14} /> Algorithm Configuration
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                            {/* Resolution */}
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">
                                    Resolution ({config.resolution})
                                </label>
                                <input
                                    type="range"
                                    min="0.5"
                                    max="5.0"
                                    step="0.1"
                                    value={config.resolution}
                                    onChange={(e) => setConfig({ ...config, resolution: parseFloat(e.target.value) })}
                                    className="w-full accent-purple-500"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Lower = fewer, larger clusters.<br />Higher = more specific clusters.
                                </p>
                            </div>

                            {/* Max Clusters */}
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">
                                    Max Clusters
                                </label>
                                <input
                                    type="number"
                                    min="1"
                                    max="50"
                                    value={config.max_clusters}
                                    onChange={(e) => setConfig({ ...config, max_clusters: parseInt(e.target.value) })}
                                    className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white text-sm focus:border-purple-500 outline-none"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Maximum number of concepts to generate.
                                </p>
                            </div>

                            {/* Min Size */}
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">
                                    Min Cluster Size
                                </label>
                                <input
                                    type="number"
                                    min="2"
                                    max="50"
                                    value={config.min_cluster_size}
                                    onChange={(e) => setConfig({ ...config, min_cluster_size: parseInt(e.target.value) })}
                                    className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white text-sm focus:border-purple-500 outline-none"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Ignore clusters smaller than this.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {loading ? (
                    <div className="flex justify-center py-20 text-gray-500 animate-pulse">
                        Loading concepts...
                    </div>
                ) : concepts.length === 0 ? (
                    <div className="text-center py-20 border-2 border-dashed border-gray-800 rounded-2xl bg-gray-900/50">
                        <Share2 size={48} className="mx-auto text-gray-700 mb-4" />
                        <h3 className="text-xl font-semibold text-gray-400">No Concepts Yet</h3>
                        <p className="text-gray-500 mt-2 max-w-md mx-auto">
                            Click "Generate Analysis" to have the AI analyze your graph structure and identify key topics.
                        </p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {concepts.map((concept) => (
                            <div
                                key={concept.id}
                                className="bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden transition-all hover:border-gray-600"
                            >
                                <div
                                    className="p-5 flex items-start gap-4 cursor-pointer hover:bg-white/5 transition-colors"
                                    onClick={() => toggleExpand(concept.id)}
                                >
                                    <button className="mt-1 text-gray-400 hover:text-white transition-colors">
                                        {expanded[concept.id] ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                                    </button>

                                    <div className="flex-1">
                                        <h3 className="text-xl font-bold text-gray-100">{concept.title}</h3>
                                        <p className="text-gray-400 mt-1 leading-relaxed">{concept.summary}</p>

                                        {!expanded[concept.id] && (
                                            <div className="mt-3 flex gap-2">
                                                {concept.nodes.slice(0, 5).map(node => (
                                                    <span key={node} className="text-xs bg-gray-900 text-gray-500 px-2 py-1 rounded border border-gray-700">
                                                        {node}
                                                    </span>
                                                ))}
                                                {concept.nodes.length > 5 && (
                                                    <span className="text-xs text-gray-600 px-2 py-1">+{concept.nodes.length - 5} more</span>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {expanded[concept.id] && (
                                    <div className="px-5 pb-5 pl-14">
                                        {/* Visualization */}
                                        <ConceptGraph nodeIds={concept.nodes} />

                                        <div className="bg-black/30 rounded-lg p-4 border border-gray-800/50">
                                            <button
                                                onClick={() => {
                                                    setChatInput(`I want to explore the concept "${concept.title}". Can you tell me more about its key entities and their relationships?`);
                                                    setActiveView('chat');
                                                }}
                                                className="w-full py-3 bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 hover:text-white border border-blue-500/30 rounded-lg transition-colors flex items-center justify-center gap-2 font-medium mb-4"
                                            >
                                                <MessageSquare size={18} />
                                                Start Chat
                                            </button>

                                            <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Related Entities in this Cluster</h4>
                                            <div className="flex flex-wrap gap-2 mb-4">
                                                {concept.nodes.map(node => (
                                                    <span
                                                        key={node}
                                                        className="text-sm text-white px-3 py-1.5 rounded-md border border-gray-700 transition-colors cursor-default"
                                                        style={{ backgroundColor: getNodeColor(node) }}
                                                        title={`Degree: ${nodeDegrees[node] || 0}`}
                                                    >
                                                        {node}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ConceptsArea;
