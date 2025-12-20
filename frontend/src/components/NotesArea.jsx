import React, { useEffect, useState, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useStore } from '../store';
import {
    Save, Edit2, Plus, Trash2, FileText, Bold, Italic, List, ListOrdered,
    Heading1, Heading2, Heading3, Code, Link, Table, Quote, Strikethrough,
    Minus, CheckSquare, Maximize2, Minimize2, Eye, EyeOff, X, Check, Loader2,
    Undo2, Redo2
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

// Enhanced toolbar with more options and keyboard shortcut hints
const MarkdownToolbar = ({ onInsert, onUndo, onRedo, canUndo, canRedo, disabled }) => {
    const toolbarGroups = [
        [
            { type: 'undo', icon: <Undo2 size={16} />, title: 'Undo', shortcut: '⌘Z', action: onUndo, disabled: !canUndo },
            { type: 'redo', icon: <Redo2 size={16} />, title: 'Redo', shortcut: '⌘⇧Z', action: onRedo, disabled: !canRedo },
        ],
        [
            { type: 'bold', icon: <Bold size={16} />, title: 'Bold', shortcut: '⌘B' },
            { type: 'italic', icon: <Italic size={16} />, title: 'Italic', shortcut: '⌘I' },
            { type: 'strikethrough', icon: <Strikethrough size={16} />, title: 'Strikethrough', shortcut: '⌘⇧X' },
        ],
        [
            { type: 'h1', icon: <Heading1 size={16} />, title: 'Heading 1' },
            { type: 'h2', icon: <Heading2 size={16} />, title: 'Heading 2' },
            { type: 'h3', icon: <Heading3 size={16} />, title: 'Heading 3' },
        ],
        [
            { type: 'bullet', icon: <List size={16} />, title: 'Bullet List' },
            { type: 'number', icon: <ListOrdered size={16} />, title: 'Numbered List' },
            { type: 'checklist', icon: <CheckSquare size={16} />, title: 'Checklist' },
        ],
        [
            { type: 'quote', icon: <Quote size={16} />, title: 'Quote' },
            { type: 'code', icon: <Code size={16} />, title: 'Code Block', shortcut: '⌘⇧K' },
            { type: 'hr', icon: <Minus size={16} />, title: 'Horizontal Rule' },
        ],
        [
            { type: 'link', icon: <Link size={16} />, title: 'Link', shortcut: '⌘K' },
            { type: 'table', icon: <Table size={16} />, title: 'Table' },
        ],
    ];

    return (
        <div className="flex items-center gap-0.5 p-2 bg-gray-800/80 border-b border-gray-700 overflow-x-auto backdrop-blur-sm">
            {toolbarGroups.map((group, groupIndex) => (
                <React.Fragment key={groupIndex}>
                    {groupIndex > 0 && <div className="w-px h-5 bg-gray-700 mx-1.5" />}
                    {group.map((item) => (
                        <button
                            key={item.type}
                            onClick={() => item.action ? item.action() : onInsert(item.type)}
                            disabled={disabled || item.disabled}
                            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-all 
                                     duration-150 disabled:opacity-30 disabled:cursor-not-allowed group relative"
                            title={item.shortcut ? `${item.title} (${item.shortcut})` : item.title}
                        >
                            {item.icon}
                            {/* Tooltip on hover */}
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 
                                          text-xs text-white rounded opacity-0 group-hover:opacity-100 transition-opacity
                                          pointer-events-none whitespace-nowrap z-10 shadow-lg">
                                {item.title}
                                {item.shortcut && <span className="ml-2 text-gray-400">{item.shortcut}</span>}
                            </div>
                        </button>
                    ))}
                </React.Fragment>
            ))}
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

// Word/character count component
const WordCount = ({ content }) => {
    const words = content.trim() ? content.trim().split(/\s+/).length : 0;
    const chars = content.length;

    return (
        <div className="flex items-center gap-3 text-xs text-gray-500">
            <span>{words} words</span>
            <span>{chars} chars</span>
        </div>
    );
};

const NotesArea = () => {
    const {
        currentWorkspace,
        notesList,
        activeNote,
        fetchNotesList,
        createNote,
        updateNote,
        deleteNote,
        selectNote
    } = useStore();

    const [editContent, setEditContent] = useState("");
    const [editTitle, setEditTitle] = useState("");
    const [saveStatus, setSaveStatus] = useState('saved');
    const [showPreview, setShowPreview] = useState(true);
    const [focusMode, setFocusMode] = useState(false);
    const [toast, setToast] = useState(null);
    const textareaRef = useRef(null);
    const saveTimeoutRef = useRef(null);
    const lastSavedContent = useRef({ title: '', content: '' });

    // Undo/Redo history
    const [history, setHistory] = useState([]);
    const [historyIndex, setHistoryIndex] = useState(-1);
    const isUndoRedoAction = useRef(false);
    const historyTimeoutRef = useRef(null);

    // Initial Fetch
    useEffect(() => {
        if (currentWorkspace) {
            fetchNotesList(currentWorkspace.id);
        }
    }, [currentWorkspace]);

    // Update local state when active note changes
    useEffect(() => {
        if (activeNote) {
            const initialContent = activeNote.content || "";
            setEditContent(initialContent);
            setEditTitle(activeNote.title || "Untitled");
            lastSavedContent.current = {
                title: activeNote.title || "Untitled",
                content: initialContent
            };
            setSaveStatus('saved');
            // Reset history for new note
            setHistory([initialContent]);
            setHistoryIndex(0);
        } else {
            setEditContent("");
            setEditTitle("");
            setSaveStatus('saved');
            setHistory([]);
            setHistoryIndex(-1);
        }
    }, [activeNote]);

    // Add to history when content changes (debounced)
    useEffect(() => {
        if (isUndoRedoAction.current) {
            isUndoRedoAction.current = false;
            return;
        }

        if (historyTimeoutRef.current) {
            clearTimeout(historyTimeoutRef.current);
        }

        historyTimeoutRef.current = setTimeout(() => {
            if (editContent !== history[historyIndex]) {
                // Truncate any redo history and add new state
                const newHistory = [...history.slice(0, historyIndex + 1), editContent];
                // Keep max 100 history entries
                if (newHistory.length > 100) newHistory.shift();
                setHistory(newHistory);
                setHistoryIndex(newHistory.length - 1);
            }
        }, 500);

        return () => {
            if (historyTimeoutRef.current) {
                clearTimeout(historyTimeoutRef.current);
            }
        };
    }, [editContent]);

    // Warn about unsaved changes before leaving
    useEffect(() => {
        const handleBeforeUnload = (e) => {
            if (saveStatus === 'unsaved') {
                e.preventDefault();
                e.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [saveStatus]);

    // Escape key to exit focus mode
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape' && focusMode) {
                setFocusMode(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [focusMode]);

    // Autosave with debounce
    const triggerAutosave = useCallback(() => {
        if (!activeNote) return;

        const hasChanges =
            editTitle !== lastSavedContent.current.title ||
            editContent !== lastSavedContent.current.content;

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
                await updateNote(activeNote.id, editTitle, editContent);
                lastSavedContent.current = { title: editTitle, content: editContent };
                setSaveStatus('saved');
            } catch (error) {
                setSaveStatus('unsaved');
                setToast({ message: 'Failed to save note', type: 'error' });
            }
        }, 1500);
    }, [activeNote, editTitle, editContent, updateNote]);

    // Trigger autosave when content changes
    useEffect(() => {
        if (activeNote) {
            triggerAutosave();
        }
        return () => {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
        };
    }, [editTitle, editContent, triggerAutosave]);

    // Manual save
    const handleSave = async () => {
        if (!currentWorkspace || !activeNote) return;

        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }

        setSaveStatus('saving');
        try {
            await updateNote(activeNote.id, editTitle, editContent);
            lastSavedContent.current = { title: editTitle, content: editContent };
            setSaveStatus('saved');
            setToast({ message: 'Note saved', type: 'success' });
        } catch (error) {
            setSaveStatus('unsaved');
            setToast({ message: 'Failed to save note', type: 'error' });
        }
    };

    const handleCreate = async () => {
        await createNote("New Note", "");
        setToast({ message: 'Note created', type: 'success' });
    };

    const handleDelete = async (noteId) => {
        await deleteNote(noteId);
        setToast({ message: 'Note deleted', type: 'success' });
    };

    // Undo/Redo handlers
    const handleUndo = useCallback(() => {
        if (historyIndex > 0) {
            isUndoRedoAction.current = true;
            const newIndex = historyIndex - 1;
            setHistoryIndex(newIndex);
            setEditContent(history[newIndex]);
        }
    }, [history, historyIndex]);

    const handleRedo = useCallback(() => {
        if (historyIndex < history.length - 1) {
            isUndoRedoAction.current = true;
            const newIndex = historyIndex + 1;
            setHistoryIndex(newIndex);
            setEditContent(history[newIndex]);
        }
    }, [history, historyIndex]);

    const canUndo = historyIndex > 0;
    const canRedo = historyIndex < history.length - 1;

    // Keyboard shortcuts handler
    const handleKeyDown = (e) => {
        const isMod = e.metaKey || e.ctrlKey;

        if (isMod && e.key === 's') {
            e.preventDefault();
            handleSave();
        } else if (isMod && e.key === 'z') {
            e.preventDefault();
            if (e.shiftKey) {
                handleRedo();
            } else {
                handleUndo();
            }
        } else if (isMod && e.key === 'b') {
            e.preventDefault();
            insertText('bold');
        } else if (isMod && e.key === 'i') {
            e.preventDefault();
            insertText('italic');
        } else if (isMod && e.key === 'k') {
            e.preventDefault();
            if (e.shiftKey) {
                insertText('code');
            } else {
                insertText('link');
            }
        } else if (isMod && e.shiftKey && e.key === 'x') {
            e.preventDefault();
            insertText('strikethrough');
        }
    };

    const insertText = (type) => {
        const textarea = textareaRef.current;
        if (!textarea) return;

        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const text = editContent;
        const before = text.substring(0, start);
        const selection = text.substring(start, end);
        const after = text.substring(end);

        let newText = text;
        let newCursorStart = start;
        let newCursorEnd = end;

        const insertions = {
            bold: { prefix: '**', suffix: '**', placeholder: 'bold text' },
            italic: { prefix: '*', suffix: '*', placeholder: 'italic text' },
            strikethrough: { prefix: '~~', suffix: '~~', placeholder: 'strikethrough' },
            h1: { prefix: '# ', suffix: '\n', placeholder: 'Heading 1', lineStart: true },
            h2: { prefix: '## ', suffix: '\n', placeholder: 'Heading 2', lineStart: true },
            h3: { prefix: '### ', suffix: '\n', placeholder: 'Heading 3', lineStart: true },
            bullet: { prefix: '- ', suffix: '\n', placeholder: 'List item', lineStart: true },
            number: { prefix: '1. ', suffix: '\n', placeholder: 'List item', lineStart: true },
            checklist: { prefix: '- [ ] ', suffix: '\n', placeholder: 'Task item', lineStart: true },
            quote: { prefix: '> ', suffix: '\n', placeholder: 'Quote', lineStart: true },
            code: { prefix: '```\n', suffix: '\n```\n', placeholder: 'code' },
            link: { prefix: '[', suffix: '](url)', placeholder: 'link text' },
            hr: { prefix: '\n---\n', suffix: '', placeholder: '' },
            table: {
                prefix: '\n| Header 1 | Header 2 |\n| -------- | -------- |\n| Cell 1   | Cell 2   |\n| Cell 3   | Cell 4   |\n',
                suffix: '',
                placeholder: ''
            },
        };

        const insert = insertions[type];
        if (!insert) return;

        const content = selection || insert.placeholder;
        newText = `${before}${insert.prefix}${content}${insert.suffix}${after}`;

        // Calculate new cursor position
        newCursorStart = start + insert.prefix.length;
        newCursorEnd = newCursorStart + content.length;

        setEditContent(newText);

        // Restore focus and selection
        setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(newCursorStart, newCursorEnd);
        }, 0);
    };

    if (!currentWorkspace) {
        return (
            <div className="flex items-center justify-center h-full bg-gray-900 text-gray-500">
                <div className="text-center">
                    <FileText size={48} className="mx-auto mb-4 text-gray-700" />
                    <p>Select a workspace to view notes.</p>
                </div>
            </div>
        );
    }

    const editorContainerClass = focusMode
        ? "fixed inset-0 z-40 bg-gray-900 flex flex-col"
        : "flex h-full bg-gray-900 text-gray-300";

    return (
        <>
            <div className={editorContainerClass}>
                {/* MAIN EDITOR AREA */}
                <div className={`flex-1 flex flex-col ${focusMode ? '' : 'border-r border-gray-800'}`}>
                    {activeNote ? (
                        <>
                            {/* Header */}
                            <div className="p-3 border-b border-gray-800 flex justify-between items-center bg-gray-900/80 backdrop-blur-sm">
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                    <input
                                        className="bg-transparent text-xl font-bold text-white focus:outline-none 
                                                 focus:bg-gray-800/50 px-2 py-1 rounded-lg transition-colors flex-1 min-w-0"
                                        value={editTitle}
                                        onChange={(e) => setEditTitle(e.target.value)}
                                        placeholder="Note Title"
                                    />
                                    <SaveStatus status={saveStatus} />
                                </div>

                                <div className="flex items-center gap-2 ml-4">
                                    <button
                                        onClick={() => setShowPreview(!showPreview)}
                                        className={`p-2 rounded-lg transition-colors ${showPreview ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800'}`}
                                        title={showPreview ? 'Hide Preview' : 'Show Preview'}
                                    >
                                        {showPreview ? <Eye size={16} /> : <EyeOff size={16} />}
                                    </button>
                                    <button
                                        onClick={() => setFocusMode(!focusMode)}
                                        className="p-2 text-gray-400 hover:bg-gray-800 rounded-lg transition-colors"
                                        title={focusMode ? 'Exit Focus Mode (Esc)' : 'Focus Mode'}
                                    >
                                        {focusMode ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                                    </button>
                                    <button
                                        onClick={handleSave}
                                        disabled={saveStatus === 'saved'}
                                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 
                                                 disabled:text-gray-500 text-white rounded-lg transition-colors 
                                                 flex items-center gap-2"
                                    >
                                        <Save size={14} />
                                        <span className="text-sm">Save</span>
                                    </button>
                                </div>
                            </div>

                            {/* Toolbar */}
                            <MarkdownToolbar onInsert={insertText} disabled={false} />

                            {/* Editor + Preview Split */}
                            <div className="flex-1 flex overflow-hidden">
                                {/* Editor Pane */}
                                <div className={`flex flex-col ${showPreview ? 'w-1/2 border-r border-gray-700' : 'w-full'}`}>
                                    <textarea
                                        ref={textareaRef}
                                        className="flex-1 w-full bg-gray-900 text-white p-4 
                                                 focus:outline-none font-mono text-sm leading-relaxed resize-none"
                                        value={editContent}
                                        onChange={(e) => setEditContent(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        placeholder="Start writing in Markdown..."
                                        spellCheck="false"
                                    />
                                    {/* Footer with word count */}
                                    <div className="px-4 py-2 border-t border-gray-800 bg-gray-900/50">
                                        <WordCount content={editContent} />
                                    </div>
                                </div>

                                {/* Preview Pane */}
                                {showPreview && (
                                    <div className="w-1/2 flex flex-col bg-gray-850">
                                        <div className="px-4 py-2 text-xs text-gray-500 border-b border-gray-800 bg-gray-800/50">
                                            PREVIEW
                                        </div>
                                        <div className="flex-1 overflow-auto p-6">
                                            <div className="prose prose-invert max-w-none">
                                                <ReactMarkdown
                                                    remarkPlugins={[remarkGfm]}
                                                    components={{
                                                        h1: ({ node, ...props }) => <h1 className="text-3xl font-bold text-blue-400 mb-4 mt-6" {...props} />,
                                                        h2: ({ node, ...props }) => <h2 className="text-2xl font-semibold text-blue-300 mb-3 mt-5" {...props} />,
                                                        h3: ({ node, ...props }) => <h3 className="text-xl font-medium text-blue-200 mb-2 mt-4" {...props} />,
                                                        p: ({ node, ...props }) => <p className="mb-4 leading-relaxed text-gray-300" {...props} />,
                                                        ul: ({ node, ...props }) => <ul className="list-disc pl-6 mb-4 space-y-2" {...props} />,
                                                        ol: ({ node, ...props }) => <ol className="list-decimal pl-6 mb-4 space-y-2" {...props} />,
                                                        li: ({ node, children, ...props }) => {
                                                            // Handle checklist items
                                                            const childText = String(children);
                                                            if (childText.startsWith('[ ] ')) {
                                                                return <li className="text-gray-300 list-none flex items-center gap-2" {...props}>
                                                                    <input type="checkbox" disabled className="rounded" />
                                                                    {childText.slice(4)}
                                                                </li>;
                                                            }
                                                            if (childText.startsWith('[x] ') || childText.startsWith('[X] ')) {
                                                                return <li className="text-gray-300 list-none flex items-center gap-2" {...props}>
                                                                    <input type="checkbox" disabled checked className="rounded" />
                                                                    <span className="line-through text-gray-500">{childText.slice(4)}</span>
                                                                </li>;
                                                            }
                                                            return <li className="text-gray-300" {...props}>{children}</li>;
                                                        },
                                                        blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-blue-500 pl-4 italic text-gray-400 my-4" {...props} />,
                                                        code: ({ node, inline, ...props }) =>
                                                            inline
                                                                ? <code className="bg-gray-800 text-blue-300 px-1.5 py-0.5 rounded text-sm font-mono" {...props} />
                                                                : <code className="block bg-gray-800 p-4 rounded-lg text-sm font-mono my-4 overflow-x-auto" {...props} />,
                                                        a: ({ node, ...props }) => <a className="text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />,
                                                        img: ({ node, ...props }) => <img className="rounded-xl max-w-full my-4 shadow-lg border border-gray-700 mx-auto" {...props} />,
                                                        hr: ({ node, ...props }) => <hr className="border-gray-700 my-6" {...props} />,
                                                        del: ({ node, ...props }) => <del className="text-gray-500" {...props} />,
                                                        table: ({ node, ...props }) => <div className="overflow-x-auto my-4 rounded-lg border border-gray-700"><table className="min-w-full divide-y divide-gray-700" {...props} /></div>,
                                                        thead: ({ node, ...props }) => <thead className="bg-gray-800" {...props} />,
                                                        tbody: ({ node, ...props }) => <tbody className="divide-y divide-gray-700 bg-gray-900" {...props} />,
                                                        tr: ({ node, ...props }) => <tr className="hover:bg-gray-800/50 transition-colors" {...props} />,
                                                        th: ({ node, ...props }) => <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider" {...props} />,
                                                        td: ({ node, ...props }) => <td className="px-4 py-3 text-sm text-gray-300" {...props} />,
                                                    }}
                                                >
                                                    {editContent || "*Start typing to see preview...*"}
                                                </ReactMarkdown>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                            <FileText size={48} className="mb-4 text-gray-700" />
                            <p className="mb-2">Select a note to start editing</p>
                            <p className="text-sm text-gray-600">or create a new one from the sidebar</p>
                        </div>
                    )}
                </div>

                {/* SIDEBAR (Right) - Hidden in focus mode */}
                {!focusMode && (
                    <div className="w-64 bg-gray-900 border-l border-gray-800 flex flex-col">
                        <div className="p-4 border-b border-gray-800 flex justify-between items-center">
                            <span className="font-semibold text-gray-400 text-sm">NOTES</span>
                            <button
                                onClick={handleCreate}
                                className="p-1.5 hover:bg-gray-800 rounded-lg text-blue-400 transition-colors"
                                title="Create Note"
                            >
                                <Plus size={18} />
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto">
                            {notesList.length === 0 ? (
                                <div className="p-4 text-center text-xs text-gray-600">
                                    <FileText size={24} className="mx-auto mb-2 text-gray-700" />
                                    <p>No notes yet.</p>
                                    <p className="mt-1">Click + to create one.</p>
                                </div>
                            ) : (
                                notesList.map(note => (
                                    <div
                                        key={note.id}
                                        onClick={() => selectNote(note)}
                                        className={`p-3 border-b border-gray-800 cursor-pointer transition-all duration-150 group relative
                                                  ${activeNote?.id === note.id
                                                ? 'bg-gray-800 border-l-2 border-l-blue-500'
                                                : 'hover:bg-gray-800/50 border-l-2 border-l-transparent'}`}
                                    >
                                        <div className="font-medium text-gray-300 text-sm truncate pr-6">
                                            {note.title || "Untitled"}
                                        </div>
                                        <div className="text-xs text-gray-500 mt-1">
                                            {new Date((note.updated_at || 0) * 1000).toLocaleDateString()}
                                        </div>

                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDelete(note.id);
                                            }}
                                            className="absolute right-2 top-3 p-1 text-gray-600 hover:text-red-400 
                                                     opacity-0 group-hover:opacity-100 transition-all duration-150"
                                            title="Delete note"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                )}
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

export default NotesArea;
