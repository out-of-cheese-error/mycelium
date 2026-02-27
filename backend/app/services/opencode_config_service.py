"""
Generates an opencode.json configuration from mycelium's llm_config.json.
This keeps OpenCode TUI in sync with the LLM provider configured in mycelium.
"""

import json
import os


OPENCODE_CONFIG_PATH = os.environ.get("OPENCODE_CONFIG", "/app/.opencode/opencode.json")


def sync_opencode_config():
    """Read mycelium LLM config and write a matching opencode.json."""
    from app.llm_config import llm_config

    cfg = llm_config.get_config()

    if cfg.provider == "ollama":
        model_name = cfg.ollama_chat_model
        opencode_cfg = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "ollama": {
                    "options": {
                        "baseURL": cfg.ollama_base_url,
                    },
                    "models": {
                        model_name: {}
                    }
                }
            },
            "model": f"ollama/{model_name}",
        }
    elif cfg.provider == "lmstudio":
        model_name = cfg.chat_model
        opencode_cfg = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "lmstudio": {
                    "options": {
                        "baseURL": cfg.chat_base_url,
                    },
                    "models": {
                        model_name: {}
                    }
                }
            },
            "model": f"lmstudio/{model_name}",
        }
    else:
        # openai or other OpenAI-compatible APIs
        model_name = cfg.chat_model
        opencode_cfg = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "openai": {
                    "options": {
                        "baseURL": cfg.chat_base_url,
                        "apiKey": cfg.chat_api_key,
                    },
                    "models": {
                        model_name: {}
                    }
                }
            },
            "model": f"openai/{model_name}",
        }

    os.makedirs(os.path.dirname(OPENCODE_CONFIG_PATH), exist_ok=True)
    with open(OPENCODE_CONFIG_PATH, "w") as f:
        json.dump(opencode_cfg, f, indent=2)
