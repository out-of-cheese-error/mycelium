import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '../store';
import { Play, Loader, BookOpen, Mic, PlayCircle, Square, Trash2 } from 'lucide-react';
import axios from 'axios';
import { confirm } from './ConfirmModal';

const API_base = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const LearnArea = () => {
    const { scripts, fetchScripts, generateScript, deleteScript, currentWorkspace } = useStore();
    const [topic, setTopic] = useState("");
    const [isGenerating, setIsGenerating] = useState(false);

    // Audio State
    const [activeScriptId, setActiveScriptId] = useState(null); // ID of script currently playing
    const [currentlyPlayingPartIndex, setCurrentlyPlayingPartIndex] = useState(null); // Index of part currently playing
    const audioRef = useRef(null); // Keep track of the HTMLAudioElement
    const isPlayingRef = useRef(false); // Flag to stop playing loop

    useEffect(() => {
        if (currentWorkspace) {
            fetchScripts();
        }
        return () => stopPlayback(); // Cleanup on unmount
    }, [currentWorkspace]);

    const handleGenerate = async () => {
        if (!topic.trim()) return;
        setIsGenerating(true);
        try {
            await generateScript(topic);
            setTopic("");
        } catch (e) {
            alert("Failed to generate script.");
        } finally {
            setIsGenerating(false);
        }
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();
        if (await confirm("Are you sure you want to delete this lesson?")) {
            try {
                if (activeScriptId === id) stopPlayback();
                await deleteScript(id);
            } catch (error) {
                alert("Failed to delete lesson");
            }
        }
    };

    const stopPlayback = () => {
        isPlayingRef.current = false;
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current = null;
        }
        setActiveScriptId(null);
        setCurrentlyPlayingPartIndex(null);
    };

    const playAudioStream = async (text) => {
        try {
            // Use GET /audio/stream for direct streaming
            // Note: GET has length limits, but script parts are short (2-3 sentences)
            const url = API_base + "/audio/stream?input=" + encodeURIComponent(text);
            const audio = new Audio(url);
            audioRef.current = audio;

            await new Promise((resolve, reject) => {
                audio.onended = () => {
                    resolve();
                };
                audio.onerror = (e) => reject(e);

                // If stopped before playing
                if (!isPlayingRef.current) {
                    resolve();
                    return;
                }

                audio.play().catch(reject);
            });
        } catch (e) {
            console.error("Audio playback error", e);
            throw e;
        }
    };

    const handlePlayScript = async (script) => {
        // If already playing this script, stop it
        if (activeScriptId === script.id) {
            stopPlayback();
            return;
        }

        stopPlayback(); // Stop any other playback
        setActiveScriptId(script.id);
        isPlayingRef.current = true;

        for (let i = 0; i < script.parts.length; i++) {
            if (!isPlayingRef.current) break;

            setCurrentlyPlayingPartIndex(i);
            try {
                await playAudioStream(script.parts[i].text);
            } catch (e) {
                console.error("Playback error", e);
                break;
            }
        }
        stopPlayback();
    };

    const handlePlaySingle = async (scriptId, partIndex, text) => {
        stopPlayback();
        setActiveScriptId(scriptId);
        setCurrentlyPlayingPartIndex(partIndex);
        isPlayingRef.current = true;
        try {
            await playAudioStream(text);
        } catch (e) {
            console.error("Single playback error", e);
        }
        stopPlayback();
    };

    return (
        <div className="flex flex-col h-full bg-black text-gray-200 p-6 overflow-y-auto custom-scrollbar">
            {/* Header / Input */}
            <div className="mb-8">
                <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-purple-400">
                    <BookOpen /> Learn & Listen
                </h2>
                <div className="flex gap-4 items-center bg-gray-900 border border-gray-800 p-4 rounded-xl shadow-lg">
                    <div className="flex-1">
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">
                            What do you want to learn about?
                        </label>
                        <input
                            className="w-full bg-black border border-gray-700 rounded p-3 text-white focus:border-purple-500 focus:outline-none"
                            placeholder="e.g. Architecture of the project, History of AI..."
                            value={topic}
                            onChange={e => setTopic(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleGenerate()}
                        />
                    </div>
                    <button
                        onClick={handleGenerate}
                        disabled={isGenerating || !topic.trim()}
                        className="px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 h-12 mt-5"
                    >
                        {isGenerating ? <Loader className="animate-spin" /> : <Mic />}
                        Generate Lesson
                    </button>
                </div>
            </div>

            {/* Content Cards */}
            <div className="grid grid-cols-1 gap-6 pb-20">
                {scripts.length === 0 && !isGenerating && (
                    <div className="text-center text-gray-500 mt-10">
                        <p>No lessons generated yet. Enter a topic above!</p>
                    </div>
                )}

                {scripts.map((script) => (
                    <div key={script.id} className="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-xl relative group">
                        <div className="flex justify-between items-start mb-4 border-b border-gray-800 pb-2">
                            <div>
                                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                                    {script.title}
                                    <button
                                        onClick={() => handlePlayScript(script)}
                                        className="text-gray-400 hover:text-purple-400 transition-colors"
                                        title={activeScriptId === script.id ? "Stop All" : "Play All"}
                                    >
                                        {activeScriptId === script.id ? <Square size={20} fill="currentColor" /> : <PlayCircle size={20} />}
                                    </button>
                                </h3>
                                <p className="text-xs text-gray-500">{new Date(script.created_at).toLocaleString()}</p>
                            </div>
                            <button
                                onClick={(e) => handleDelete(script.id, e)}
                                className="p-2 text-gray-600 hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                                title="Delete Lesson"
                            >
                                <Trash2 size={18} />
                            </button>
                        </div>

                        <div className="space-y-4">
                            {script.parts.map((part, idx) => {
                                const isPlayingThis = activeScriptId === script.id && currentlyPlayingPartIndex === idx;
                                return (
                                    <div key={idx} className={`bg-black/40 border ${isPlayingThis ? 'border-purple-500 bg-purple-900/10' : 'border-gray-800'} rounded-lg p-4 hover:border-purple-900 transition-colors`}>
                                        <div className="flex justify-between items-center mb-2">
                                            <h4 className={`font-bold ${isPlayingThis ? 'text-purple-300' : 'text-gray-300'}`}>{part.title}</h4>
                                            <button
                                                onClick={() => isPlayingThis ? stopPlayback() : handlePlaySingle(script.id, idx, part.text)}
                                                className={`p-2 rounded-full transition-all shadow-lg ${isPlayingThis ? 'bg-purple-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-purple-600 hover:text-white'}`}
                                                title={isPlayingThis ? "Stop" : "Listen"}
                                            >
                                                {isPlayingThis ? <Square size={12} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                                            </button>
                                        </div>
                                        <p className="text-gray-400 text-sm leading-relaxed font-mono">
                                            {part.text}
                                        </p>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default LearnArea;
