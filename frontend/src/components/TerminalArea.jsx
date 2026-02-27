import React, { useRef, useEffect } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { useStore } from '../store';

const TerminalArea = () => {
    const termRef = useRef(null);
    const xtermRef = useRef(null);
    const fitAddonRef = useRef(null);
    const wsRef = useRef(null);
    const initRef = useRef(false);

    const API_BASE = useStore((s) => s.API_BASE);

    useEffect(() => {
        // Guard against double-init in StrictMode / HMR
        if (!termRef.current || initRef.current) return;
        initRef.current = true;

        const term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
            theme: {
                background: '#0a0a0a',
                foreground: '#e4e4e7',
                cursor: '#8b5cf6',
                selectionBackground: 'rgba(139,92,246,0.25)',
                black: '#18181b',
                red: '#ef4444',
                green: '#22c55e',
                yellow: '#eab308',
                blue: '#3b82f6',
                magenta: '#a855f7',
                cyan: '#06b6d4',
                white: '#e4e4e7',
            },
            scrollback: 10000,
            convertEol: true,
        });

        const fitAddon = new FitAddon();
        const webLinksAddon = new WebLinksAddon();

        term.loadAddon(fitAddon);
        term.loadAddon(webLinksAddon);
        term.open(termRef.current);

        xtermRef.current = term;
        fitAddonRef.current = fitAddon;

        // Initial fit after DOM settles
        requestAnimationFrame(() => fitAddon.fit());

        // --- WebSocket connection ---
        const wsUrl = `${API_BASE.replace(/^http/, 'ws')}/terminal/ws`;
        const socket = new WebSocket(wsUrl);
        wsRef.current = socket;
        socket.binaryType = 'arraybuffer';

        socket.onopen = () => {
            const { cols, rows } = term;
            socket.send(JSON.stringify({ type: 'resize', cols, rows }));
        };

        socket.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                term.write(new Uint8Array(event.data));
            } else {
                term.write(event.data);
            }
        };

        socket.onerror = () => {
            term.write('\r\n\x1b[31mWebSocket connection error\x1b[0m\r\n');
        };

        socket.onclose = () => {
            term.write('\r\n\x1b[33mSession ended. Refresh to reconnect.\x1b[0m\r\n');
        };

        // Terminal input -> WebSocket (binary)
        term.onData((data) => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send(new TextEncoder().encode(data));
            }
        });

        // Notify backend of resize
        term.onResize(({ cols, rows }) => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: 'resize', cols, rows }));
            }
        });

        // Re-fit when container size changes
        const observer = new ResizeObserver(() => {
            try {
                fitAddon.fit();
            } catch {
                // ignore if terminal is disposed
            }
        });
        observer.observe(termRef.current);

        return () => {
            observer.disconnect();
            socket.close();
            term.dispose();
            initRef.current = false;
        };
    }, [API_BASE]);

    return (
        <div className="h-full w-full bg-[#0a0a0a] p-1">
            <div ref={termRef} className="h-full w-full" />
        </div>
    );
};

export default TerminalArea;
