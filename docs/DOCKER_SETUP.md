# Docker Setup Guide

This guide explains how to configure persistent storage and settings for MyCelium when running with Docker.

## Architecture

MyCelium runs as multiple Docker services:

| Service | Port | Description |
|---------|------|-------------|
| **frontend** | `3000` | Nginx serving the React app + reverse proxy to backend |
| **backend** | `8000` | FastAPI server (knowledge graph, RAG, chat) |
| **tts** | `8100` | Optional GPU-accelerated TTS (VibeVoice 0.5B) |

The frontend proxies all `/api/` requests to the backend, so you only need to access `http://localhost:3000`.

## Quick Start

1. **Run with Docker**:
   ```bash
   docker-compose up --build
   ```

2. **Open**: [http://localhost:3000](http://localhost:3000)

3. **Configure your LLM** in the Settings page (gear icon).

That's it — sensible defaults are built in. Your configuration and data will persist across restarts.

### With TTS (requires NVIDIA GPU)

To also start the text-to-speech service:
```bash
docker-compose --profile tts up --build
```

---

## Configuration Options

### Environment Variables (.env file)

Create a `.env` file in the project root to customize storage locations:

#### `MEMORY_DATA_PATH`
Where your knowledge graphs, embeddings, and notes are stored.
- **Default**: `./backend/memory_data`
- **Example**: `MEMORY_DATA_PATH=/home/user/mycelium-data`
- **Example (Windows)**: `MEMORY_DATA_PATH=D:/mycelium-data`

#### `LOGS_PATH`
Where application logs are stored.
- **Default**: `./backend/logs`
- **Example**: `LOGS_PATH=/var/log/mycelium`

#### `CONFIG_PATH`
Directory containing `llm_config.json` (the LLM configuration file).
- **Default**: `./backend`
- **Example**: `CONFIG_PATH=/home/user/.config/mycelium`

#### `TTS_CACHE_PATH`
Where HuggingFace model weights are cached for the TTS service.
- **Default**: Docker named volume `tts_cache`
- **Example**: `TTS_CACHE_PATH=/mnt/models/tts-cache`

#### `TTS_VOICES_PATH`
Where downloaded voice presets are stored for the TTS service.
- **Default**: Docker named volume `tts_voices`
- **Example**: `TTS_VOICES_PATH=/mnt/models/tts-voices`

---

## How It Works

### Frontend & Reverse Proxy

The frontend container runs Nginx which:
- Serves the React SPA on port 80 (mapped to host port 3000)
- Reverse-proxies `/api/*` requests to the backend (stripping the `/api` prefix)
- Supports WebSocket connections (used for voice calls)
- Supports SSE streaming (used for chat responses)
- Allows file uploads up to 50 MB (for document ingestion)

### Configuration Persistence

The `llm_config.json` file stores:
- LLM provider settings (OpenAI, Ollama, LM Studio)
- API keys and URLs
- Model selections
- TTS settings
- UI preferences

**Important**: The `CONFIG_PATH` should be a **directory** that contains `llm_config.json`, not the file itself.

When you update settings through the UI or edit the file directly, changes persist to the host machine.

### Data Persistence

The `MEMORY_DATA_PATH` contains:
- **NetworkX graphs** (`graph.json` per workspace)
- **ChromaDB vector store** (embeddings for semantic search)
- **Notes and skills data**

All data is stored per-workspace and survives container restarts/rebuilds.

### TTS Service

The TTS service is **optional** and only starts when using the `tts` profile. It:
- Uses the NVIDIA CUDA runtime (requires an NVIDIA GPU with Docker GPU support)
- Downloads the VibeVoice model on first start (~may take several minutes)
- Caches model weights and voice presets in persistent volumes
- Exposes an OpenAI-compatible `/v1/audio/speech` endpoint on port 8100

To enable TTS in the app, set `tts_enabled: true` in `llm_config.json`. The default TTS URL (`http://tts:8100/v1`) works automatically via Docker networking.

---

## Example Configurations

### Default (No .env file)
Everything stored in the project directory:
```
./backend/memory_data/   # Knowledge graphs and embeddings
./backend/logs/          # Application logs
./backend/llm_config.json # LLM settings
```

### Custom Data Directory
Store data on a separate drive:
```bash
# .env
MEMORY_DATA_PATH=/mnt/external-drive/mycelium-data
LOGS_PATH=/mnt/external-drive/mycelium-logs
CONFIG_PATH=/home/user/.config/mycelium
```

### Windows Example
Store data on D: drive:
```bash
# .env
MEMORY_DATA_PATH=D:/MyCelium/data
LOGS_PATH=D:/MyCelium/logs
CONFIG_PATH=D:/MyCelium/config
```

---

## Troubleshooting

### Config changes not persisting
1. Make sure the `CONFIG_PATH` directory exists on your host
2. Ensure `llm_config.json` exists in that directory
3. Check file permissions (container needs read/write access)

### Memory data not persisting
1. Verify `MEMORY_DATA_PATH` is accessible
2. Check that the directory has write permissions
3. Look for errors in the container logs: `docker-compose logs backend`

### TTS not working
1. Verify you have an NVIDIA GPU and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed
2. Make sure you started with `--profile tts`: `docker-compose --profile tts up`
3. Check TTS logs: `docker-compose logs tts`
4. First startup downloads ~1 GB of model weights — allow time for this to complete

### Starting fresh
To reset all data while keeping your config:
```bash
# Stop containers
docker-compose down

# Remove memory data (keeps config)
rm -rf ./backend/memory_data/*

# Restart
docker-compose up
```

To also reset TTS caches:
```bash
docker-compose down -v   # removes named volumes (tts_cache, tts_voices)
```

---

## Connecting to Ollama/LM Studio on Host

When using Docker, `localhost` inside the container refers to the container itself, not your host machine.

To connect to services running on your host (like Ollama or LM Studio), use `host.docker.internal`:

Example `llm_config.json`:
```json
{
  "provider": "ollama",
  "ollama_base_url": "http://host.docker.internal:11434",
  "ollama_chat_model": "llama3.2",
  "ollama_embedding_model": "nomic-embed-text",
  "tts_base_url": "http://tts:8100/v1",
  "tts_enabled": false
}
```

For LM Studio:
```json
{
  "provider": "lm_studio",
  "chat_base_url": "http://host.docker.internal:1234/v1",
  "chat_api_key": "lm-studio",
  "chat_model": "your-model-name",
  "embedding_base_url": "http://host.docker.internal:1234/v1",
  "embedding_api_key": "lm-studio",
  "embedding_model": "text-embedding-nomic-embed-text-v1.5"
}
```
