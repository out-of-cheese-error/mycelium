import React, { useState } from 'react';
import { Lock, Unlock, Plus, Trash2, Sliders } from 'lucide-react';
import { useStore } from '../store';

const EmotionsPanel = () => {
    const emotions = useStore(state => state.emotions);
    const updateEmotions = useStore(state => state.updateEmotions);
    const [isAdding, setIsAdding] = useState(false);
    const [newScaleName, setNewScaleName] = useState("");
    const [expanded, setExpanded] = useState(false);

    if (!emotions) return null;

    // Safety check for old format if store hasn't refreshed yet
    const scales = emotions.scales || [];
    const motive = emotions.motive || "";

    const handleUpdateScale = (index, newValue) => {
        const newScales = [...scales];
        newScales[index] = { ...newScales[index], value: parseInt(newValue) };
        updateEmotions({ ...emotions, scales: newScales });
    };

    const toggleFreeze = (index) => {
        const newScales = [...scales];
        newScales[index] = { ...newScales[index], frozen: !newScales[index].frozen };
        updateEmotions({ ...emotions, scales: newScales });
    };

    const handleDelete = (index) => {
        const newScales = scales.filter((_, i) => i !== index);
        updateEmotions({ ...emotions, scales: newScales });
    };

    const handleAddScale = () => {
        if (!newScaleName.trim()) {
            setIsAdding(false);
            return;
        }
        const newScales = [...scales, { name: newScaleName.trim(), value: 50, frozen: false }];
        updateEmotions({ ...emotions, scales: newScales });
        setNewScaleName("");
        setIsAdding(false);
    };

    const handleUpdateMotive = (val) => {
        updateEmotions({ ...emotions, motive: val });
    };

    return (
        <div className="space-y-3 pr-1 custom-scrollbar">
            {/* HEADER (Clickable to toggle) */}
            <div className={`pb-2 ${expanded ? 'border-b border-gray-800' : ''}`}>
                <div
                    onClick={() => setExpanded(!expanded)}
                    className="flex items-center justify-between cursor-pointer group"
                >
                    <div className="text-xs text-gray-500 font-bold uppercase tracking-wider mb-1 group-hover:text-gray-300 transition-colors">
                        Sliders {expanded ? '▼' : '▶'}
                    </div>
                </div>
            </div>

            {/* EXPANDABLE AREA */}
            {expanded && (
                <div className="animate-fade-in space-y-4 max-h-64 overflow-y-auto">
                    {/* MOTIVE */}
                    <div className="space-y-1">
                        <div className="text-xs text-gray-500 font-bold uppercase tracking-wider">Current Motive</div>
                        <input
                            type="text"
                            value={motive}
                            onChange={(e) => handleUpdateMotive(e.target.value)}
                            className="w-full bg-transparent text-sm text-purple-400 font-medium italic border-none focus:ring-0 focus:outline-none placeholder-gray-600"
                            placeholder="Set a motive..."
                        />
                    </div>
                    <div className="space-y-4">
                        {scales.map((scale, idx) => (
                            <div key={idx} className="space-y-1 group">
                                <div className="flex items-center justify-between text-xs">
                                    <span className="text-gray-400 font-medium flex items-center gap-2">
                                        {scale.name}
                                        {scale.frozen && <Lock size={10} className="text-blue-400" />}
                                    </span>
                                    <div className="flex items-center gap-2 opacity-80 hover:opacity-100 transition-opacity">
                                        <span className="font-mono text-gray-300">{scale.value}%</span>

                                        <button
                                            onClick={() => toggleFreeze(idx)}
                                            className={`p-1 rounded hover:bg-gray-800 ${scale.frozen ? 'text-blue-400' : 'text-gray-600'}`}
                                            title={scale.frozen ? "Unfreeze (AI cannot change)" : "Freeze (Prevent AI changes)"}
                                        >
                                            {scale.frozen ? <Lock size={12} /> : <Unlock size={12} />}
                                        </button>

                                        <button
                                            onClick={() => handleDelete(idx)}
                                            className="p-1 rounded hover:bg-gray-800 text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                            title="Delete Scale"
                                        >
                                            <Trash2 size={12} />
                                        </button>
                                    </div>
                                </div>
                                <input
                                    type="range" min="0" max="100"
                                    value={scale.value}
                                    onChange={(e) => handleUpdateScale(idx, e.target.value)}
                                    className={`w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer ${scale.frozen ? 'accent-blue-500' : 'accent-purple-500'}`}
                                />
                            </div>
                        ))}
                    </div>

                    {/* ADD NEW */}
                    {isAdding ? (
                        <div className="flex items-center gap-2 mt-2 animate-fade-in">
                            <input
                                autoFocus
                                type="text"
                                value={newScaleName}
                                onChange={(e) => setNewScaleName(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleAddScale()}
                                className="flex-1 bg-gray-800 text-xs text-white px-2 py-1 rounded border border-gray-600 outline-none"
                                placeholder="Emotion name..."
                            />
                            <button onClick={handleAddScale} className="text-green-400 hover:text-green-300 text-xs">Add</button>
                            <button onClick={() => setIsAdding(false)} className="text-gray-500 hover:text-gray-300 text-xs">Cancel</button>
                        </div>
                    ) : (
                        <button
                            onClick={() => setIsAdding(true)}
                            className="w-full mt-2 py-1 flex items-center justify-center gap-1 text-xs text-gray-500 hover:text-gray-300 border border-dashed border-gray-700 hover:border-gray-500 rounded transition-all"
                        >
                            <Plus size={12} /> Add Emotion Scale
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default EmotionsPanel;
