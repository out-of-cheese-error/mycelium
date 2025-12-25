# Mycelium Desktop

Cross-platform desktop application for Mycelium using Tauri.

## Prerequisites

- [Rust](https://rustup.rs/) (latest stable)
- [Node.js](https://nodejs.org/) (v18+)
- Python 3.10+ with pip
- PyInstaller (`pip install pyinstaller`)

## Development

```bash
# Install dependencies
npm install

# Run in development mode (uses live frontend dev server)
npm run tauri dev
```

## Building

### Step 1: Build the Python Backend

```bash
npm run build:backend
```

This creates a standalone executable in `src-tauri/binaries/`.

### Step 2: Build the Desktop App

```bash
npm run build
```

This creates platform-specific installers in `src-tauri/target/release/bundle/`.

## Output Locations

| Platform | Output |
|----------|--------|
| macOS | `target/release/bundle/dmg/*.dmg` |
| Windows | `target/release/bundle/msi/*.msi` |
| Linux | `target/release/bundle/appimage/*.AppImage` |

## Architecture

```
┌─────────────────────────────────────┐
│         Tauri Window                │
│  ┌───────────────────────────────┐  │
│  │     React Frontend (Vite)     │  │
│  │                               │  │
│  │    HTTP calls to localhost    │──┼──┐
│  └───────────────────────────────┘  │  │
└─────────────────────────────────────┘  │
                                         │
┌─────────────────────────────────────┐  │
│    Python Backend (Sidecar)         │◄─┘
│    - FastAPI on port 8000           │
│    - ChromaDB vector store          │
│    - LangChain/LangGraph agent      │
└─────────────────────────────────────┘
```

## Troubleshooting

### Backend doesn't start
Check the console output for errors. The backend logs are prefixed with `[Backend]`.

### Slow first startup
The first launch may take longer as ChromaDB initializes the embedding model.

### Port 8000 in use
If another process is using port 8000, the backend won't start. Kill the conflicting process.
