/**
 * API Configuration for Mycelium
 * Works in both web and Tauri desktop environments
 */

// Check if running in Tauri
const isTauri = () => {
    return typeof window !== 'undefined' && window.__TAURI_INTERNALS__ !== undefined;
};

// Get the API base URL
export const getApiBase = () => {
    // Environment variable takes precedence (for Docker/custom deployments)
    if (import.meta.env.VITE_API_BASE) {
        return import.meta.env.VITE_API_BASE;
    }

    // In Tauri, the backend runs on localhost:8000
    // In development web, also use localhost:8000
    return 'http://localhost:8000';
};

export const API_BASE = getApiBase();

export default {
    API_BASE,
    isTauri,
    getApiBase,
};
