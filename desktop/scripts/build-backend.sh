#!/bin/bash
# Build Mycelium backend as standalone executable using PyInstaller

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKEND_DIR="$PROJECT_ROOT/backend"
OUTPUT_DIR="$SCRIPT_DIR/../src-tauri/binaries"

echo "Building Mycelium backend..."
echo "Backend dir: $BACKEND_DIR"
echo "Output dir: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Navigate to backend directory
cd "$BACKEND_DIR"

# Install PyInstaller if not present
python -m pip install pyinstaller

# Determine platform suffix for Tauri sidecar naming
case "$(uname -s)" in
    Darwin*)
        if [[ "$(uname -m)" == "arm64" ]]; then
            PLATFORM_SUFFIX="aarch64-apple-darwin"
        else
            PLATFORM_SUFFIX="x86_64-apple-darwin"
        fi
        ;;
    Linux*)
        PLATFORM_SUFFIX="x86_64-unknown-linux-gnu"
        ;;
    MINGW*|CYGWIN*|MSYS*)
        PLATFORM_SUFFIX="x86_64-pc-windows-msvc.exe"
        ;;
    *)
        echo "Unknown platform"
        exit 1
        ;;
esac

echo "Platform suffix: $PLATFORM_SUFFIX"

# Build with PyInstaller
pyinstaller \
    --onefile \
    --name "mycelium-backend-$PLATFORM_SUFFIX" \
    --add-data "app:app" \
    --hidden-import chromadb \
    --hidden-import chromadb.config \
    --hidden-import sentence_transformers \
    --hidden-import langchain \
    --hidden-import langchain_core \
    --hidden-import langchain_openai \
    --hidden-import langchain_ollama \
    --hidden-import langchain_community \
    --hidden-import langgraph \
    --hidden-import langgraph.graph \
    --hidden-import langgraph.prebuilt \
    --hidden-import networkx \
    --hidden-import pydantic \
    --hidden-import uvicorn \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.loops \
    --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols \
    --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.auto \
    --hidden-import uvicorn.protocols.websockets \
    --hidden-import uvicorn.protocols.websockets.auto \
    --hidden-import uvicorn.lifespan \
    --hidden-import uvicorn.lifespan.on \
    --hidden-import fastapi \
    --hidden-import httpx \
    --hidden-import duckduckgo_search \
    --hidden-import beautifulsoup4 \
    --hidden-import bs4 \
    --hidden-import wikipedia \
    --hidden-import pypdf \
    --hidden-import arxiv \
    --collect-all chromadb \
    --collect-all sentence_transformers \
    --collect-all langchain \
    --collect-all langchain_core \
    --collect-all langgraph \
    app/main.py

# Move to output directory
mv "dist/mycelium-backend-$PLATFORM_SUFFIX"* "$OUTPUT_DIR/"

echo "✅ Backend built successfully!"
echo "Output: $OUTPUT_DIR/mycelium-backend-$PLATFORM_SUFFIX"
