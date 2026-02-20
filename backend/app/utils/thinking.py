import re

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"
THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def strip_thinking(text: str) -> str:
    """Remove all thinking content from text.
    Handles both explicit (<think>...</think>) and implicit (no <think>, just </think>) thinking."""
    # First handle explicit <think>...</think> blocks
    result = THINK_PATTERN.sub("", text)
    # Then handle implicit thinking: content before </think> without preceding <think>
    if "</think>" in result:
        parts = result.split("</think>", 1)
        result = parts[1] if len(parts) > 1 else ""
    return result.strip()


def extract_thinking(text: str) -> tuple:
    """Extract thinking and clean content from a complete response.
    Handles both explicit (<think>...</think>) and implicit (no <think>, just </think>) thinking.
    Returns (thinking_content, clean_content)."""
    thinking_parts = THINK_PATTERN.findall(text)
    clean = THINK_PATTERN.sub("", text)
    # Handle implicit thinking (no <think>, just </think>)
    if "</think>" in clean:
        parts = clean.split("</think>", 1)
        implicit_thinking = parts[0].strip()
        if implicit_thinking:
            thinking_parts.append(implicit_thinking)
        clean = parts[1] if len(parts) > 1 else ""
    thinking = "\n".join(thinking_parts).strip()
    clean = clean.strip()
    return thinking, clean
