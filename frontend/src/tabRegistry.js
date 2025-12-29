import { MessageSquare, Network, Notebook, BookOpen, Layers, Flame, Route, BrainCircuit, Compass } from 'lucide-react';

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
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'graph', label: 'Graph', icon: Network },
    { id: 'notes', label: 'Notes', icon: Notebook },
    { id: 'learn', label: 'Learn', icon: BookOpen },
    { id: 'concepts', label: 'Concepts', icon: Layers },
    { id: 'hot_topics', label: 'Hot Topics', icon: Flame },
    { id: 'connectors', label: 'Connectors', icon: Route },
    { id: 'grow', label: 'Grow', icon: BrainCircuit },
    { id: 'theWay', label: 'theWay', icon: Compass, activeColor: 'bg-purple-600' },
];

/**
 * Default enabled state for all tabs (all enabled by default).
 */
export const DEFAULT_ENABLED_TABS = TAB_REGISTRY.reduce((acc, tab) => {
    acc[tab.id] = true;
    return acc;
}, {});
