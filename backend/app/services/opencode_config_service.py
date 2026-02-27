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
        opencode_cfg = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "ollama": {
                    "options": {
                        "baseURL": cfg.ollama_base_url,
                    }
                }
            },
            "model": f"ollama/{cfg.ollama_chat_model}",
        }
    else:
        # openai or lmstudio — both are OpenAI-compatible
        opencode_cfg = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "openai-compatible": {
                    "options": {
                        "baseURL": cfg.chat_base_url,
                        "apiKey": cfg.chat_api_key,
                    }
                }
            },
            "model": f"openai-compatible/{cfg.chat_model}",
        }

    os.makedirs(os.path.dirname(OPENCODE_CONFIG_PATH), exist_ok=True)
    with open(OPENCODE_CONFIG_PATH, "w") as f:
        json.dump(opencode_cfg, f, indent=2)
