from pydantic import BaseModel
from typing import Literal, List, Dict, Optional
import os
import json

CONFIG_FILE = "llm_config.json"

class MCPServerConfig(BaseModel):
    """Configuration for an MCP (Model Context Protocol) server."""
    name: str  # Display name for the server
    command: str  # Command to run (e.g., "npx", "python", "node")
    args: List[str] = []  # Arguments (e.g., ["-y", "@modelcontextprotocol/server-brave-search"])
    env: Dict[str, str] = {}  # Environment variables (e.g., {"BRAVE_API_KEY": "xxx"})

class LLMConfigModel(BaseModel):
    # Provider Selection for Chat LLM: "openai" (for OpenAI API), "ollama" (for Ollama), "lmstudio" (for LM Studio)
    provider: Literal["openai", "ollama", "lmstudio"] = "lmstudio"
    # Provider Selection for Embeddings (independent from LLM provider)
    embedding_provider: Literal["openai", "ollama", "lmstudio"] = "lmstudio"
    
    # Chat Settings (used for openai/lmstudio providers)
    chat_base_url: str = "http://localhost:1234/v1"
    chat_api_key: str = "lm-studio"
    chat_model: str = "qwen/qwen3-vl-30b"
    temperature: float = 0.7
    
    # Embedding Settings (used for openai/lmstudio providers)
    embedding_base_url: str = "http://localhost:1234/v1"
    embedding_api_key: str = "lm-studio"
    embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    
    # Ollama Settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embedding_model: str = "nomic-embed-text"

    # Ingestion LLM Settings (optional, separate LLM for graph building/entity extraction)
    ingestion_llm_enabled: bool = False  # If False, uses the Chat LLM for ingestion
    ingestion_provider: Literal["openai", "ollama", "lmstudio"] = "lmstudio"
    ingestion_base_url: str = "http://localhost:1234/v1"
    ingestion_api_key: str = "lm-studio"
    ingestion_model: str = ""
    ingestion_ollama_model: str = "llama3.2"  # Used when ingestion_provider is "ollama"

    # TTS Settings
    tts_base_url: str = "http://localhost:3000/v1"
    tts_model: str = "tts-1"
    tts_voice: str = "en-Emma_woman"
    tts_enabled: bool = True

    # Reddit Settings
    reddit_user_agent: str = "python:graph_chat_agent:v1.0 (public access)"

    # UI Appearance Settings
    theme: str = "dark"  # dark, light, midnight, forest
    accent_color: str = "#8b5cf6"  # purple accent
    font_family: str = "Inter"  # Inter, Roboto, Source Code Pro, system
    font_size: str = "md"  # sm, md, lg

    # MCP (Model Context Protocol) Servers
    mcp_servers: List[MCPServerConfig] = [
        MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/app"],
            env={}
        ),
        MCPServerConfig(
            name="shell",
            command="npx",
            args=["-y", "@mako10k/mcp-shell-server"],
            env={}
        )
    ]

    # Data Storage Settings
    data_directory: str = "./memory_data"  # Base directory for workspaces, notes, and configs

class LLMConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMConfig, cls).__new__(cls)
            cls._instance.config = LLMConfigModel()
            cls._instance.load()
        return cls._instance

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.config = LLMConfigModel(**data)
            except:
                pass

    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config.model_dump(), f, indent=2)

    def get_config(self) -> LLMConfigModel:
        return self.config

    def update_config(self, new_config: LLMConfigModel):
        self.config = new_config
        self.save()
    
    def get_data_directory(self) -> str:
        """Get the configured data directory, with special handling for bundled builds.
        
        Priority:
        1. Environment variable MYCELIUM_DATA_DIR (if set)
        2. Config file data_directory (if absolute path)
        3. For PyInstaller bundles: ~/Library/Application Support/Mycelium (macOS)
        4. For development: ./memory_data (relative to working dir)
        """
        import sys
        
        # 1. Environment variable takes highest priority
        env_dir = os.environ.get("MYCELIUM_DATA_DIR")
        if env_dir:
            return env_dir
        
        # 2. If config specifies an absolute path, use it
        if os.path.isabs(self.config.data_directory):
            return self.config.data_directory
        
        # 3. For PyInstaller bundles, use platform-specific user data directory
        if getattr(sys, 'frozen', False):
            # Running as compiled bundle
            if sys.platform == 'darwin':
                # macOS: ~/Library/Application Support/Mycelium
                data_dir = os.path.expanduser("~/Library/Application Support/Mycelium")
            elif sys.platform == 'win32':
                # Windows: %APPDATA%\Mycelium
                data_dir = os.path.join(os.environ.get('APPDATA', ''), 'Mycelium')
            else:
                # Linux: ~/.local/share/mycelium
                data_dir = os.path.expanduser("~/.local/share/mycelium")
            
            # Create the directory if it doesn't exist
            os.makedirs(data_dir, exist_ok=True)
            return data_dir
        
        # 4. Development mode: use config value (relative or absolute)
        return self.config.data_directory
    
    def get_chat_llm(self):
        """Factory method to get the appropriate Chat LLM based on provider."""
        cfg = self.config
        
        if cfg.provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=cfg.ollama_chat_model,
                base_url=cfg.ollama_base_url,
                temperature=cfg.temperature
            )
        else:
            # Works for both "openai" and "lmstudio" (OpenAI-compatible APIs)
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                base_url=cfg.chat_base_url,
                api_key=cfg.chat_api_key,
                model=cfg.chat_model,
                temperature=cfg.temperature
            )
    
    def get_embeddings(self):
        """Factory method to get the appropriate Embeddings model based on embedding_provider."""
        cfg = self.config
        
        if cfg.embedding_provider == "ollama":
            from langchain_ollama import OllamaEmbeddings
            return OllamaEmbeddings(
                model=cfg.ollama_embedding_model,
                base_url=cfg.ollama_base_url
            )
        else:
            # Works for both "openai" and "lmstudio" (OpenAI-compatible APIs)
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(
                base_url=cfg.embedding_base_url,
                api_key=cfg.embedding_api_key,
                model=cfg.embedding_model,
                check_embedding_ctx_length=False
            )
    
    def get_ingestion_llm(self):
        """Factory method to get the LLM for ingestion/graph building.
        
        If ingestion_llm_enabled is False, falls back to the chat LLM.
        """
        cfg = self.config
        
        if not cfg.ingestion_llm_enabled:
            return self.get_chat_llm()
        
        if cfg.ingestion_provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=cfg.ingestion_ollama_model,
                base_url=cfg.ollama_base_url,
                temperature=0.3  # Lower temperature for more consistent extraction
            )
        else:
            # Works for both "openai" and "lmstudio" (OpenAI-compatible APIs)
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                base_url=cfg.ingestion_base_url,
                api_key=cfg.ingestion_api_key,
                model=cfg.ingestion_model,
                temperature=0.3  # Lower temperature for more consistent extraction
            )

llm_config = LLMConfig()
