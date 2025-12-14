from pydantic import BaseModel
from typing import Literal
import os
import json

CONFIG_FILE = "llm_config.json"

class LLMConfigModel(BaseModel):
    # Provider Selection: "openai" (for OpenAI API), "ollama" (for Ollama), "lmstudio" (for LM Studio)
    provider: Literal["openai", "ollama", "lmstudio"] = "lmstudio"
    
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

    # TTS Settings
    tts_base_url: str = "http://localhost:3000/v1"
    tts_model: str = "tts-1"
    tts_voice: str = "en-Emma_woman"
    tts_enabled: bool = True

    # Reddit Settings
    reddit_user_agent: str = "python:graph_chat_agent:v1.0 (public access)"

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
        """Factory method to get the appropriate Embeddings model based on provider."""
        cfg = self.config
        
        if cfg.provider == "ollama":
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

llm_config = LLMConfig()
