import os
import json
from pydantic import BaseModel
from typing import Literal

CONFIG_FILE = "backend/llm_config.json"

class LLMConfigModel(BaseModel):
    provider: Literal["openai", "ollama", "lmstudio"] = "lmstudio"
    chat_base_url: str = "http://localhost:1234/v1"
    chat_api_key: str = "lm-studio"
    chat_model: str = "qwen/qwen3-vl-30b"
    temperature: float = 0.7
    embedding_base_url: str = "http://localhost:1234/v1"
    embedding_api_key: str = "lm-studio"
    embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embedding_model: str = "nomic-embed-text"
    tts_base_url: str = "http://localhost:3000/v1"
    tts_model: str = "tts-1"
    tts_voice: str = "en-Emma_woman"
    tts_enabled: bool = True
    reddit_user_agent: str = "python:graph_chat_agent:v1.0 (public access)"
    mcp_servers: dict[str, dict] = {} 

def load():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return LLMConfigModel(**data)
    return LLMConfigModel()

def save(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config.model_dump(), f, indent=2)
    print("Saved!")

print(f"CWD: {os.getcwd()}")
print(f"File exists? {os.path.exists(CONFIG_FILE)}")

try:
    cfg = load()
    print("Loaded config:", cfg.mcp_servers)
    
    # Simulate adding a server
    cfg.mcp_servers["test_server"] = {"command": "echo", "args": ["hello"], "env": {}, "enabled": True}
    save(cfg)
    
    # Reload
    cfg2 = load()
    print("Reloaded config:", cfg2.mcp_servers)
    
    if "test_server" in cfg2.mcp_servers:
        print("SUCCESS: Persistence working manually.")
    else:
        print("FAILURE: Persistence failed.")
        
    # Cleanup
    del cfg2.mcp_servers["test_server"]
    save(cfg2)
    
except Exception as e:
    print(f"Error: {e}")
