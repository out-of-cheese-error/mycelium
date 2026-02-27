import { MessageSquare, Network, Notebook, BookOpen, Layers, Flame, Route, BrainCircuit, Compass, Phone, TerminalSquare } from 'lucide-react';

/**
 * Central registry of all available tabs.
 * This pattern makes it easy to add new extensions in the future.
 * Each tab has:
 *   - id: unique identifier (used in enabled_tabs settings)
 *   - label: display name
 *   - icon: lucide-react icon component
 *   - activeColor: optional custom active color (defaults to blue-600)
 *   - onActivate: optional callback when tab becomes active
 */
export const TAB_REGISTRY = [
    { id: 'chat', label: 'Chat', icon: MessageSquare, description: 'Main conversation interface for chatting with the AI assistant.' },
    { id: 'graph', label: 'Graph', icon: Network, description: 'Interactive visualization of your knowledge graph showing entities and their relationships.' },
    { id: 'notes', label: 'Notes', icon: Notebook, description: 'Create and manage personal notes with markdown support.' },
    { id: 'learn', label: 'Learn', icon: BookOpen, description: 'Educational content and learning resources generated from your knowledge base.' },
    { id: 'concepts', label: 'Concepts', icon: Layers, description: 'Browse and explore key concepts extracted from your ingested documents.' },
    { id: 'hot_topics', label: 'Hot Topics', icon: Flame, description: 'Discover trending topics and frequently referenced subjects in your knowledge graph.' },
    { id: 'connectors', label: 'Connectors', icon: Route, description: 'Find connections and pathways between different concepts in your knowledge base.' },
    { id: 'grow', label: 'Grow', icon: BrainCircuit, description: 'Expand your knowledge graph by ingesting new documents, URLs, and content.' },
    { id: 'theWay', label: 'theWay', icon: Compass, activeColor: 'bg-purple-600', description: 'Custom skills and workflows to enhance your AI assistant\'s capabilities.' },
    { id: 'call', label: 'Call', icon: Phone, activeColor: 'bg-green-600', description: 'Live voice conversation with your AI assistant.' },
    { id: 'terminal', label: 'Terminal', icon: TerminalSquare, activeColor: 'bg-gray-600', description: 'Terminal access to the backend container with OpenCode TUI.' },
];

/**
 * Default enabled state for all tabs (all enabled by default).
 */
export const DEFAULT_ENABLED_TABS = TAB_REGISTRY.reduce((acc, tab) => {
    acc[tab.id] = true;
    return acc;
}, {});
