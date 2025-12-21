import React, { createContext, useContext, useEffect } from 'react';
import { useStore } from '../store';

const ThemeContext = createContext(null);

// Theme definitions
const THEMES = {
    dark: {
        '--bg-primary': '#0a0a0a',
        '--bg-secondary': '#111827',
        '--bg-tertiary': '#1f2937',
        '--bg-elevated': '#374151',
        '--text-primary': '#f9fafb',
        '--text-secondary': '#e5e7eb',
        '--text-muted': '#9ca3af',
        '--border-color': '#374151',
        '--border-subtle': '#1f2937',
    },
    light: {
        '--bg-primary': '#ffffff',
        '--bg-secondary': '#f9fafb',
        '--bg-tertiary': '#f3f4f6',
        '--bg-elevated': '#e5e7eb',
        '--text-primary': '#111827',
        '--text-secondary': '#374151',
        '--text-muted': '#6b7280',
        '--border-color': '#d1d5db',
        '--border-subtle': '#e5e7eb',
    },
    midnight: {
        '--bg-primary': '#0f172a',
        '--bg-secondary': '#1e293b',
        '--bg-tertiary': '#334155',
        '--bg-elevated': '#475569',
        '--text-primary': '#f1f5f9',
        '--text-secondary': '#cbd5e1',
        '--text-muted': '#94a3b8',
        '--border-color': '#475569',
        '--border-subtle': '#334155',
    },
    forest: {
        '--bg-primary': '#022c22',
        '--bg-secondary': '#064e3b',
        '--bg-tertiary': '#065f46',
        '--bg-elevated': '#047857',
        '--text-primary': '#ecfdf5',
        '--text-secondary': '#d1fae5',
        '--text-muted': '#6ee7b7',
        '--border-color': '#047857',
        '--border-subtle': '#065f46',
    }
};

// Font size scales
const FONT_SIZES = {
    sm: {
        '--font-size-xs': '0.65rem',
        '--font-size-sm': '0.75rem',
        '--font-size-base': '0.8rem',
        '--font-size-lg': '0.95rem',
        '--font-size-xl': '1.1rem',
    },
    md: {
        '--font-size-xs': '0.75rem',
        '--font-size-sm': '0.875rem',
        '--font-size-base': '1rem',
        '--font-size-lg': '1.125rem',
        '--font-size-xl': '1.25rem',
    },
    lg: {
        '--font-size-xs': '0.85rem',
        '--font-size-sm': '1rem',
        '--font-size-base': '1.125rem',
        '--font-size-lg': '1.25rem',
        '--font-size-xl': '1.5rem',
    }
};

export const applyThemeToDOM = (settings) => {
    const { theme = 'dark', accent_color = '#8b5cf6', font_family = 'Inter', font_size = 'md' } = settings;

    const root = document.documentElement;

    // Apply theme colors
    const themeColors = THEMES[theme] || THEMES.dark;
    Object.entries(themeColors).forEach(([key, value]) => {
        root.style.setProperty(key, value);
    });

    // Apply accent color
    root.style.setProperty('--accent', accent_color);
    root.style.setProperty('--accent-hover', adjustColor(accent_color, -20));
    root.style.setProperty('--accent-muted', accent_color + '40');

    // Apply font family
    const fontStack = font_family === 'system'
        ? '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        : `"${font_family}", sans-serif`;
    root.style.setProperty('--font-family', fontStack);

    // Apply font sizes
    const fontSizes = FONT_SIZES[font_size] || FONT_SIZES.md;
    Object.entries(fontSizes).forEach(([key, value]) => {
        root.style.setProperty(key, value);
    });
};

// Helper to darken/lighten a hex color
function adjustColor(hex, amount) {
    const num = parseInt(hex.replace('#', ''), 16);
    const r = Math.min(255, Math.max(0, (num >> 16) + amount));
    const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amount));
    const b = Math.min(255, Math.max(0, (num & 0x0000FF) + amount));
    return `#${(1 << 24 | r << 16 | g << 8 | b).toString(16).slice(1)}`;
}

export const ThemeProvider = ({ children }) => {
    const uiSettings = useStore(state => state.uiSettings);
    const themeLoaded = useStore(state => state.themeLoaded);

    useEffect(() => {
        // Only apply theme changes AFTER initial load is complete
        // App.jsx handles the initial theme application from fetchSystemConfig
        if (themeLoaded && uiSettings) {
            applyThemeToDOM(uiSettings);
        }
    }, [uiSettings, themeLoaded]);

    return (
        <ThemeContext.Provider value={uiSettings}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = () => useContext(ThemeContext);

export { THEMES, FONT_SIZES };
export default ThemeProvider;
