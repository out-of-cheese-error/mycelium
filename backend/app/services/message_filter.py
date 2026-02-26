"""
Heuristic pre-filter for knowledge extraction.

Inspired by LightMem's sensory memory stage: filters out trivial/noisy messages
before they reach the LLM extraction pipeline, saving API calls without losing
meaningful information.
"""

import re

# Patterns that indicate trivial messages not worth extracting
TRIVIAL_PATTERNS = [
    r"^(hi|hello|hey|yo|sup|greetings|howdy|hiya)\b",
    r"^(ok|okay|sure|yes|no|yep|nope|yeah|nah|yea|nay|uh huh|mhm)\b",
    r"^(thanks|thank you|thx|ty|cheers|appreciated)\b",
    r"^(bye|goodbye|see ya|later|cya|ttyl|gn|good night)\b",
    r"^(lol|lmao|haha|heh|hmm|wow|cool|nice|great|awesome|neat)\b",
    r"^(got it|understood|makes sense|i see|ah|oh|right)\b",
    r"^[\W\s]*$",  # Only punctuation, whitespace, or empty
    r"^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\s]+$",  # Emoji-only
]

_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in TRIVIAL_PATTERNS]

# Common stopwords to filter when counting substantive words
STOPWORDS = {
    "i", "me", "my", "we", "you", "your", "it", "its", "the", "a", "an",
    "is", "am", "are", "was", "were", "be", "been", "do", "does", "did",
    "have", "has", "had", "will", "would", "could", "should", "can", "may",
    "to", "of", "in", "for", "on", "at", "by", "with", "from", "as",
    "and", "or", "but", "not", "so", "if", "then", "that", "this", "what",
    "just", "very", "really", "too", "also", "well", "still", "even",
}


def should_extract(user_message: str, ai_response: str) -> bool:
    """
    Returns True if the exchange likely contains extractable knowledge.
    Returns False for trivial messages that should be skipped.

    Only examines the user message — the AI response is assumed to follow
    the user's topic and doesn't independently generate extractable facts.
    """
    if not user_message:
        return False

    msg = user_message.strip()
    msg_lower = msg.lower()

    # Short messages matching trivial patterns → skip
    if len(msg) < 20:
        for pattern in _compiled_patterns:
            if pattern.match(msg_lower):
                return False

    # Count substantive words (non-stopword, length > 2)
    words = msg_lower.split()
    substantive = [w for w in words if w not in STOPWORDS and len(w) > 2]
    if len(substantive) < 2:
        return False

    return True
