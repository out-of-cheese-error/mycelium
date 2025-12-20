import React, { useEffect, useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useStore } from '../store';
import { Save, Edit2, Plus, Trash2, FileText, Bold, Italic, List, ListOrdered, Heading1, Heading2, Heading3, Code, Link, Table } from 'lucide-react';

const MarkdownToolbar = ({ onInsert }) => {
    return (
        <div className="flex items-center gap-1 p-2 bg-gray-800 border-b border-gray-700 overflow-x-auto">
            <ToolbarButton onClick={() => onInsert('bold')} icon={<Bold size={16} />} title="Bold" />
            <ToolbarButton onClick={() => onInsert('italic')} icon={<Italic size={16} />} title="Italic" />
            <div className="w-px h-4 bg-gray-700 mx-1" />
            <ToolbarButton onClick={() => onInsert('h1')} icon={<Heading1 size={16} />} title="Heading 1" />
            <ToolbarButton onClick={() => onInsert('h2')} icon={<Heading2 size={16} />} title="Heading 2" />
            <ToolbarButton onClick={() => onInsert('h3')} icon={<Heading3 size={16} />} title="Heading 3" />
            <div className="w-px h-4 bg-gray-700 mx-1" />
            <ToolbarButton onClick={() => onInsert('bullet')} icon={<List size={16} />} title="Bullet List" />
            <ToolbarButton onClick={() => onInsert('number')} icon={<ListOrdered size={16} />} title="Numbered List" />
            <div className="w-px h-4 bg-gray-700 mx-1" />
            <ToolbarButton onClick={() => onInsert('code')} icon={<Code size={16} />} title="Code Block" />
            <ToolbarButton onClick={() => onInsert('link')} icon={<Link size={16} />} title="Link" />
            <ToolbarButton onClick={() => onInsert('table')} icon={<Table size={16} />} title="Table" />
        </div>
    );
};

const ToolbarButton = ({ onClick, icon, title }) => (
    <button
        onClick={onClick}
        className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
        title={title}
    >
        {icon}
    </button>
);

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

    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState("");
    const [editTitle, setEditTitle] = useState("");
    const textareaRef = useRef(null);

    // Initial Fetch
    useEffect(() => {
        if (currentWorkspace) {
            fetchNotesList(currentWorkspace.id);
        }
    }, [currentWorkspace]);

    // Update local state when active note changes
    useEffect(() => {
        if (activeNote) {
            setEditContent(activeNote.content || "");
            setEditTitle(activeNote.title || "Untitled");
        } else {
            setEditContent("");
            setEditTitle("");
            setIsEditing(false);
        }
    }, [activeNote]);

    const handleSave = () => {
        if (currentWorkspace && activeNote) {
            updateNote(activeNote.id, editTitle, editContent);
            setIsEditing(false);
        }
    };

    const handleCreate = () => {
        createNote("New Note", "");
        setIsEditing(true);
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
        let newCursorPos = end;

        switch (type) {
            case 'bold':
                newText = `${before}**${selection || 'bold text'}**${after}`;
                newCursorPos = selection ? end + 4 : start + 2 + 9; // +2 for **, +9 for 'bold text'
                break;
            case 'italic':
                newText = `${before}*${selection || 'italic text'}*${after}`;
                newCursorPos = selection ? end + 2 : start + 1 + 11;
                break;
            case 'h1':
                newText = `${before}# ${selection || 'Heading 1'}\n${after}`;
                break;
            case 'h2':
                newText = `${before}## ${selection || 'Heading 2'}\n${after}`;
                break;
            case 'h3':
                newText = `${before}### ${selection || 'Heading 3'}\n${after}`;
                break;
            case 'bullet':
                newText = `${before}- ${selection || 'List item'}\n${after}`;
                break;
            case 'number':
                newText = `${before}1. ${selection || 'List item'}\n${after}`;
                break;
            case 'code':
                newText = `${before}\`\`\`\n${selection || 'code'}\n\`\`\`\n${after}`;
                break;
            case 'link':
                newText = `${before}[${selection || 'link text'}](url)${after}`;
                break;
            case 'table':
                const tableTemplate = `
| Header 1 | Header 2 |
| -------- | -------- |
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
`;
                newText = `${before}${tableTemplate}${after}`;
                break;
        }

        setEditContent(newText);

        // Restore focus and cursor (approximate)
        setTimeout(() => {
            textarea.focus();
            // In a real app we'd calculate exact cursor position but this is simple enough
        }, 0);
    };

    if (!currentWorkspace) return <div className="p-8 text-gray-500">Select a workspace.</div>;

    return (
        <div className="flex h-full bg-gray-900 text-gray-300">
            {/* MAIN EDITOR AREA (Left) */}
            <div className="flex-1 flex flex-col border-r border-gray-800">
                {activeNote ? (
                    <>
                        <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-gray-900/50 backdrop-blur">
                            {isEditing ? (
                                <input
                                    className="bg-transparent text-xl font-bold text-white focus:outline-none w-full mr-4"
                                    value={editTitle}
                                    onChange={(e) => setEditTitle(e.target.value)}
                                    placeholder="Note Title"
                                />
                            ) : (
                                <h2 className="text-xl font-bold text-white truncate">{activeNote.title}</h2>
                            )}

                            <button
                                onClick={() => isEditing ? handleSave() : setIsEditing(true)}
                                className="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors flex items-center gap-2 shrink-0"
                            >
                                {isEditing ? <><Save size={16} /> Save</> : <><Edit2 size={16} /> Edit</>}
                            </button>
                        </div>

                        {isEditing && <MarkdownToolbar onInsert={insertText} />}

                        <div className="flex-1 overflow-auto p-6">
                            {isEditing ? (
                                <textarea
                                    ref={textareaRef}
                                    className="w-full h-full bg-gray-800 text-white p-4 rounded-xl border border-gray-700 
                                               focus:outline-none focus:border-blue-500 font-mono text-sm leading-relaxed resize-none"
                                    value={editContent}
                                    onChange={(e) => setEditContent(e.target.value)}
                                    placeholder="Start writing..."
                                />
                            ) : (
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
                                            li: ({ node, ...props }) => <li className="text-gray-300" {...props} />,
                                            blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-blue-500 pl-4 italic text-gray-400 my-4" {...props} />,
                                            code: ({ node, inline, ...props }) =>
                                                inline
                                                    ? <code className="bg-gray-800 text-blue-300 px-1 py-0.5 rounded text-sm font-mono" {...props} />
                                                    : <code className="block bg-gray-800 p-4 rounded-lg text-sm font-mono my-4 overflow-x-auto" {...props} />,
                                            a: ({ node, ...props }) => <a className="text-blue-400 hover:underline" {...props} />,
                                            img: ({ node, ...props }) => <img className="rounded-xl max-w-full my-4 shadow-lg border border-gray-700 mx-auto" {...props} />,
                                            table: ({ node, ...props }) => <div className="overflow-x-auto my-4 rounded-lg border border-gray-700"><table className="min-w-full divide-y divide-gray-700" {...props} /></div>,
                                            thead: ({ node, ...props }) => <thead className="bg-gray-800" {...props} />,
                                            tbody: ({ node, ...props }) => <tbody className="divide-y divide-gray-700 bg-gray-900" {...props} />,
                                            tr: ({ node, ...props }) => <tr className="hover:bg-gray-800/50 transition-colors" {...props} />,
                                            th: ({ node, ...props }) => <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider" {...props} />,
                                            td: ({ node, ...props }) => <td className="px-4 py-3 text-sm text-gray-300 whitespace-nowrap" {...props} />,
                                        }}
                                    >
                                        {activeNote.content || "*Empty note*"}
                                    </ReactMarkdown>
                                </div>
                            )}
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                        <FileText size={48} className="mb-4 text-gray-700" />
                        <p>Select a note to view or create a new one.</p>
                    </div>
                )}
            </div>

            {/* SIDEBAR (Right) */}
            <div className="w-64 bg-gray-900 border-l border-gray-800 flex flex-col">
                <div className="p-4 border-b border-gray-800 flex justify-between items-center">
                    <span className="font-semibold text-gray-400 text-sm">NOTES</span>
                    <button
                        onClick={handleCreate}
                        className="p-1 hover:bg-gray-800 rounded text-blue-400 transition-colors"
                        title="Create Note"
                    >
                        <Plus size={20} />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto">
                    {notesList.length === 0 ? (
                        <div className="p-4 text-center text-xs text-gray-600">No notes yet.</div>
                    ) : (
                        notesList.map(note => (
                            <div
                                key={note.id}
                                onClick={() => selectNote(note)}
                                className={`p-3 border-b border-gray-800 cursor-pointer transition-colors group relative
                                            ${activeNote?.id === note.id ? 'bg-gray-800 border-l-2 border-l-blue-500' : 'hover:bg-gray-800/50'}`}
                            >
                                <div className="font-medium text-gray-300 text-sm truncate pr-6">{note.title || "Untitled"}</div>
                                <div className="text-xs text-gray-500 mt-1">
                                    {new Date((note.updated_at || 0) * 1000).toLocaleDateString()}
                                </div>

                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        deleteNote(note.id);
                                    }}
                                    className="absolute right-2 top-3 p-1 text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};

export default NotesArea;

