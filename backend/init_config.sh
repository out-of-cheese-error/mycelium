#!/bin/bash
# Initialize config file if it doesn't exist

CONFIG_FILE="${LLM_CONFIG_FILE:-llm_config.json}"
CONFIG_DIR=$(dirname "$CONFIG_FILE")

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# If config file doesn't exist, copy from example
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config file not found at $CONFIG_FILE"

    # Check if example file exists in the app directory
    if [ -f "/app/llm_config.example.json" ]; then
        echo "Copying example config to $CONFIG_FILE"
        cp /app/llm_config.example.json "$CONFIG_FILE"
    else
        echo "Warning: llm_config.example.json not found, creating minimal config"
        cat > "$CONFIG_FILE" << EOF
{
  "provider": "ollama",
  "embedding_provider": "ollama",
  "ollama_base_url": "http://host.docker.internal:11434",
  "ollama_chat_model": "llama3.2",
  "ollama_embedding_model": "nomic-embed-text",
  "temperature": 0.7,
  "tts_enabled": false
}
EOF
    fi
    echo "Config file created at $CONFIG_FILE"
else
    echo "Config file already exists at $CONFIG_FILE"
fi

# Ensure memory directory exists
MEMORY_DIR="${MEMORY_BASE_DIR:-./memory_data}"
mkdir -p "$MEMORY_DIR"
echo "Memory directory ready at $MEMORY_DIR"

# Execute the main command (passed as arguments to this script)
exec "$@"
