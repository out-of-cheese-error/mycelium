import React, { useEffect, useState, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useStore } from '../store';
import {
    Save, Plus, Trash2, Compass, Check, Loader2, X, Edit2
} from 'lucide-react';

// Toast notification component
const Toast = ({ message, type, onClose }) => {
    useEffect(() => {
        const timer = setTimeout(onClose, 3000);
        return () => clearTimeout(timer);
    }, [onClose]);

    const bgColor = type === 'success' ? 'bg-green-600' : type === 'error' ? 'bg-red-600' : 'bg-blue-600';

    return (
        <div className={`fixed bottom-4 right-4 ${bgColor} text-white px-4 py-3 rounded-lg shadow-lg 
                        flex items-center gap-2 animate-slide-up z-50`}>
            {type === 'success' && <Check size={18} />}
            {type === 'error' && <X size={18} />}
            <span>{message}</span>
        </div>
    );
};

// Save status indicator
const SaveStatus = ({ status }) => {
    const config = {
        saved: { icon: <Check size={14} />, text: 'Saved', color: 'text-green-400' },
        saving: { icon: <Loader2 size={14} className="animate-spin" />, text: 'Saving...', color: 'text-yellow-400' },
        unsaved: { icon: <Edit2 size={14} />, text: 'Unsaved', color: 'text-orange-400' },
    };

    const { icon, text, color } = config[status] || config.saved;

    return (
        <div className={`flex items-center gap-1.5 text-xs ${color} transition-all duration-300`}>
            {icon}
            <span>{text}</span>
        </div>
    );
};

const SkillsArea = () => {
    const {
        currentWorkspace,
        skillsList,
        activeSkill,
        fetchSkillsList,
        createSkill,
        updateSkill,
        deleteSkill,
        selectSkill
    } = useStore();

    const [editTitle, setEditTitle] = useState("");
    const [editSummary, setEditSummary] = useState("");
    const [editExplanation, setEditExplanation] = useState("");
    const [saveStatus, setSaveStatus] = useState('saved');
    const [toast, setToast] = useState(null);
    const saveTimeoutRef = useRef(null);
    const lastSavedContent = useRef({ title: '', summary: '', explanation: '' });

    // Initial Fetch
    useEffect(() => {
        if (currentWorkspace) {
            fetchSkillsList(currentWorkspace.id);
        }
    }, [currentWorkspace]);

    // Update local state when active skill changes
    useEffect(() => {
        if (activeSkill) {
            setEditTitle(activeSkill.title || "");
            setEditSummary(activeSkill.summary || "");
            setEditExplanation(activeSkill.explanation || "");
            lastSavedContent.current = {
                title: activeSkill.title || "",
                summary: activeSkill.summary || "",
                explanation: activeSkill.explanation || ""
            };
            setSaveStatus('saved');
        } else {
            setEditTitle("");
            setEditSummary("");
            setEditExplanation("");
            setSaveStatus('saved');
        }
    }, [activeSkill]);

    // Autosave with debounce
    const triggerAutosave = useCallback(() => {
        if (!activeSkill) return;

        const hasChanges =
            editTitle !== lastSavedContent.current.title ||
            editSummary !== lastSavedContent.current.summary ||
            editExplanation !== lastSavedContent.current.explanation;

        if (!hasChanges) {
            setSaveStatus('saved');
            return;
        }

        setSaveStatus('unsaved');

        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }

        saveTimeoutRef.current = setTimeout(async () => {
            setSaveStatus('saving');
            try {
                await updateSkill(activeSkill.id, editTitle, editSummary, editExplanation);
                lastSavedContent.current = { title: editTitle, summary: editSummary, explanation: editExplanation };
                setSaveStatus('saved');
            } catch (error) {
                setSaveStatus('unsaved');
                setToast({ message: 'Failed to save skill', type: 'error' });
            }
        }, 1500);
    }, [activeSkill, editTitle, editSummary, editExplanation, updateSkill]);

    // Trigger autosave when content changes
    useEffect(() => {
        if (activeSkill) {
            triggerAutosave();
        }
        return () => {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
        };
    }, [editTitle, editSummary, editExplanation, triggerAutosave]);

    // Manual save
    const handleSave = async () => {
        if (!currentWorkspace || !activeSkill) return;

        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }

        setSaveStatus('saving');
        try {
            await updateSkill(activeSkill.id, editTitle, editSummary, editExplanation);
            lastSavedContent.current = { title: editTitle, summary: editSummary, explanation: editExplanation };
            setSaveStatus('saved');
            setToast({ message: 'Skill saved', type: 'success' });
        } catch (error) {
            setSaveStatus('unsaved');
            setToast({ message: 'Failed to save skill', type: 'error' });
        }
    };

    const handleCreate = async () => {
        await createSkill("New Skill", "Brief description of what this skill does", "Detailed instructions for how to apply this skill...");
        setToast({ message: 'Skill created', type: 'success' });
    };

    const handleDelete = async (skillId) => {
        await deleteSkill(skillId);
        setToast({ message: 'Skill deleted', type: 'success' });
    };

    // Keyboard shortcuts
    const handleKeyDown = (e) => {
        const isMod = e.metaKey || e.ctrlKey;
        if (isMod && e.key === 's') {
            e.preventDefault();
            handleSave();
        }
    };

    if (!currentWorkspace) {
        return (
            <div className="flex items-center justify-center h-full bg-gray-900 text-gray-500">
                <div className="text-center">
                    <Compass size={48} className="mx-auto mb-4 text-gray-700" />
                    <p>Select a workspace to view skills.</p>
                </div>
            </div>
        );
    }

    return (
        <>
            <div className="flex h-full bg-gray-900 text-gray-300">
                {/* MAIN EDITOR AREA */}
                <div className="flex-1 flex flex-col border-r border-gray-800">
                    {activeSkill ? (
                        <>
                            {/* Header */}
                            <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-gray-900/80 backdrop-blur-sm">
                                <div className="flex items-center gap-3 flex-1">
                                    <Compass size={20} className="text-purple-400" />
                                    <span className="text-sm text-gray-500">Skill Editor</span>
                                    <SaveStatus status={saveStatus} />
                                </div>
                                <button
                                    onClick={handleSave}
                                    disabled={saveStatus === 'saved'}
                                    className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 
                                             disabled:text-gray-500 text-white rounded-lg transition-colors 
                                             flex items-center gap-2"
                                >
                                    <Save size={14} />
                                    <span className="text-sm">Save</span>
                                </button>
                            </div>

                            {/* Editor Content */}
                            <div className="flex-1 overflow-auto p-6 space-y-6" onKeyDown={handleKeyDown}>
                                {/* Title */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-2">
                                        Skill Title
                                    </label>
                                    <input
                                        className="w-full bg-gray-800 text-white px-4 py-3 rounded-lg border border-gray-700 
                                                 focus:outline-none focus:border-purple-500 text-lg font-semibold"
                                        value={editTitle}
                                        onChange={(e) => setEditTitle(e.target.value)}
                                        placeholder="e.g., Email Writing, Data Analysis, Code Review"
                                    />
                                </div>

                                {/* Summary */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-2">
                                        Summary / Description
                                        <span className="text-gray-500 font-normal ml-2">
                                            (Used for search - keep it concise)
                                        </span>
                                    </label>
                                    <textarea
                                        className="w-full bg-gray-800 text-white px-4 py-3 rounded-lg border border-gray-700 
                                                 focus:outline-none focus:border-purple-500 resize-none h-24"
                                        value={editSummary}
                                        onChange={(e) => setEditSummary(e.target.value)}
                                        placeholder="Brief description of what this skill is for..."
                                    />
                                </div>

                                {/* Explanation */}
                                <div className="flex-1">
                                    <label className="block text-sm font-medium text-gray-400 mb-2">
                                        Skill Instructions
                                        <span className="text-gray-500 font-normal ml-2">
                                            (Detailed instructions the AI will follow when using this skill)
                                        </span>
                                    </label>
                                    <textarea
                                        className="w-full bg-gray-800 text-white px-4 py-3 rounded-lg border border-gray-700 
                                                 focus:outline-none focus:border-purple-500 resize-none font-mono text-sm"
                                        style={{ minHeight: '300px' }}
                                        value={editExplanation}
                                        onChange={(e) => setEditExplanation(e.target.value)}
                                        placeholder={`Detailed step-by-step instructions for this skill...

Example for "Email Writing":
1. Start with an appropriate greeting based on the relationship
2. Keep paragraphs short (2-3 sentences max)
3. Use a clear subject line that summarizes the purpose
4. End with a call to action if needed
5. Sign off professionally

The AI will follow these instructions when you ask it to "use your email writing skill".`}
                                    />
                                </div>

                                {/* Usage Hint */}
                                <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
                                    <h4 className="text-sm font-medium text-purple-400 mb-2">💡 How to use this skill</h4>
                                    <p className="text-sm text-gray-400">
                                        Once saved, ask the AI: <code className="bg-gray-700 px-2 py-0.5 rounded text-purple-300">
                                            "Use your {editTitle || 'skill name'} skill to..."
                                        </code>
                                    </p>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                            <Compass size={48} className="mb-4 text-gray-700" />
                            <p className="mb-2">Select a skill to edit</p>
                            <p className="text-sm text-gray-600">or create a new one from the sidebar</p>
                        </div>
                    )}
                </div>

                {/* SIDEBAR (Right) */}
                <div className="w-72 bg-gray-900 border-l border-gray-800 flex flex-col">
                    <div className="p-4 border-b border-gray-800 flex justify-between items-center">
                        <div className="flex items-center gap-2">
                            <Compass size={16} className="text-purple-400" />
                            <span className="font-semibold text-gray-400 text-sm">THE WAY</span>
                        </div>
                        <button
                            onClick={handleCreate}
                            className="p-1.5 hover:bg-gray-800 rounded-lg text-purple-400 transition-colors"
                            title="Create Skill"
                        >
                            <Plus size={18} />
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto">
                        {skillsList.length === 0 ? (
                            <div className="p-4 text-center text-xs text-gray-600">
                                <Compass size={24} className="mx-auto mb-2 text-gray-700" />
                                <p>No skills yet.</p>
                                <p className="mt-1">Click + to teach me a skill.</p>
                            </div>
                        ) : (
                            skillsList.map(skill => (
                                <div
                                    key={skill.id}
                                    onClick={() => selectSkill(skill)}
                                    className={`p-3 border-b border-gray-800 cursor-pointer transition-all duration-150 group relative
                                              ${activeSkill?.id === skill.id
                                            ? 'bg-gray-800 border-l-2 border-l-purple-500'
                                            : 'hover:bg-gray-800/50 border-l-2 border-l-transparent'}`}
                                >
                                    <div className="font-medium text-gray-300 text-sm truncate pr-6">
                                        {skill.title || "Untitled Skill"}
                                    </div>
                                    <div className="text-xs text-gray-500 mt-1 truncate">
                                        {skill.summary || "No description"}
                                    </div>

                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDelete(skill.id);
                                        }}
                                        className="absolute right-2 top-3 p-1 text-gray-600 hover:text-red-400 
                                                 opacity-0 group-hover:opacity-100 transition-all duration-150"
                                        title="Delete skill"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            ))
                        )}
                    </div>

                    {/* Info Footer */}
                    <div className="p-3 border-t border-gray-800 bg-gray-850">
                        <p className="text-xs text-gray-500 text-center">
                            Skills are instructions the AI can look up and follow.
                        </p>
                    </div>
                </div>
            </div>

            {/* Toast Notifications */}
            {toast && (
                <Toast
                    message={toast.message}
                    type={toast.type}
                    onClose={() => setToast(null)}
                />
            )}

            {/* Global styles for animations */}
            <style>{`
                @keyframes slide-up {
                    from {
                        opacity: 0;
                        transform: translateY(1rem);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                .animate-slide-up {
                    animation: slide-up 0.2s ease-out;
                }
            `}</style>
        </>
    );
};

export default SkillsArea;
