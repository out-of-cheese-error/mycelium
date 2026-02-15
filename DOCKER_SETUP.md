# Docker Setup Guide

This guide explains how to configure persistent storage and settings for MyCelium when running with Docker.

## Quick Start

1. **Copy the environment template**:
   ```bash
   cp .env.example .env
   ```

2. **Ensure config file exists**:
   ```bash
   cd backend
   cp llm_config.example.json llm_config.json
   cd ..
   ```

3. **Run with Docker**:
   ```bash
   docker-compose up --build
   ```

That's it! Your configuration and data will persist across restarts.

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

---

## How It Works

### Configuration Persistence

The `llm_config.json` file stores:
- LLM provider settings (OpenAI, Ollama, LM Studio)
- API keys and URLs
- Model selections
- UI preferences

**Important**: The `CONFIG_PATH` should be a **directory** that contains `llm_config.json`, not the file itself.

When you update settings through the UI or edit the file directly, changes persist to the host machine.

### Data Persistence

The `MEMORY_DATA_PATH` contains:
- **NetworkX graphs** (`graph.json` per workspace)
- **ChromaDB vector store** (embeddings for semantic search)
- **Notes and skills data**

All data is stored per-workspace and survives container restarts/rebuilds.

### Automatic Initialization

The Docker container includes an initialization script that:
1. Creates the config file from `llm_config.example.json` if it doesn't exist
2. Ensures all directories are created
3. Sets up the environment before starting the backend

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

---

## Connecting to Ollama/LM Studio on Host

When using Docker, `localhost` inside the container refers to the container itself, not your host machine.

To connect to services running on your host (like Ollama or LM Studio), use:

**Linux/Mac**: `host.docker.internal`
**Windows**: `host.docker.internal`

Example `llm_config.json`:
```json
{
  "provider": "ollama",
  "ollama_base_url": "http://host.docker.internal:11434",
  "ollama_chat_model": "llama3.2",
  "ollama_embedding_model": "nomic-embed-text"
}
```
