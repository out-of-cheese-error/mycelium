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
    const { theme = 'dark', accent_color = '#8b5cf6', font_family = 'Inter', font_size = 'md', colorful_markdown = false } = settings;

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

    // Apply markdown colors (colorful or neutral)
    if (colorful_markdown) {
        const palette = computeColorPalette(accent_color);
        root.style.setProperty('--md-heading', palette.heading);
        root.style.setProperty('--md-bold', palette.bold);
        root.style.setProperty('--md-italic', palette.italic);
        root.style.setProperty('--md-link', palette.link);
        root.style.setProperty('--md-code-bg', palette.code + '30'); // With transparency
        root.style.setProperty('--md-code-text', palette.code);
        root.style.setProperty('--md-list-marker', palette.listMarker);
        root.style.setProperty('--md-blockquote', palette.blockquote);
    } else {
        // Neutral/muted colors when disabled
        root.style.setProperty('--md-heading', 'var(--text-primary)');
        root.style.setProperty('--md-bold', 'inherit');
        root.style.setProperty('--md-italic', 'inherit');
        root.style.setProperty('--md-link', 'var(--accent)');
        root.style.setProperty('--md-code-bg', 'rgba(0,0,0,0.2)');
        root.style.setProperty('--md-code-text', 'var(--text-secondary)');
        root.style.setProperty('--md-list-marker', 'var(--text-muted)');
        root.style.setProperty('--md-blockquote', 'var(--text-muted)');
    }

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

// Convert hex to HSL
function hexToHsl(hex) {
    const num = parseInt(hex.replace('#', ''), 16);
    const r = (num >> 16) / 255;
    const g = ((num >> 8) & 0x00FF) / 255;
    const b = (num & 0x0000FF) / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;

    if (max === min) {
        h = s = 0;
    } else {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }
    return { h: h * 360, s: s * 100, l: l * 100 };
}

// Convert HSL to hex
function hslToHex(h, s, l) {
    s /= 100;
    l /= 100;
    const a = s * Math.min(l, 1 - l);
    const f = n => {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        return Math.round(255 * color).toString(16).padStart(2, '0');
    };
    return `#${f(0)}${f(8)}${f(4)}`;
}

// Generate harmonious color palette from accent color
function computeColorPalette(accentHex) {
    const hsl = hexToHsl(accentHex);

    // Generate unique color for each markdown element using hue rotation
    const colors = {
        heading: accentHex, // Base accent for headers
        bold: hslToHex((hsl.h + 15) % 360, Math.min(hsl.s + 5, 100), Math.min(hsl.l + 5, 85)), // Slight shift for bold
        italic: hslToHex((hsl.h + 45) % 360, Math.min(hsl.s, 90), Math.min(hsl.l + 10, 85)), // Analogous for italic
        link: hslToHex((hsl.h + 60) % 360, Math.min(hsl.s + 10, 100), Math.min(hsl.l + 10, 85)), // Analogous for links
        code: hslToHex((hsl.h + 180) % 360, Math.max(hsl.s - 20, 40), Math.min(hsl.l + 15, 80)), // Complementary for code
        listMarker: hslToHex((hsl.h + 90) % 360, hsl.s, Math.min(hsl.l + 5, 80)), // Triadic for lists
        blockquote: hslToHex((hsl.h + 270) % 360, Math.max(hsl.s - 20, 40), Math.min(hsl.l + 15, 75)), // Split-complementary for blockquotes
    };

    return colors;
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
