"""
Lightweight topic segmentation using existing embedding infrastructure.

Inspired by LightMem's SenMemBufferManager topic segmentation, but avoids
requiring a separate BERT model by reusing the embedding model already
configured in mycelium (via llm_config.get_embeddings()).

Groups consecutive buffered turns into topic segments based on cosine
similarity. When similarity between consecutive turns drops below a
threshold, a topic boundary is placed.
"""

import numpy as np
from typing import List

from app.services.extraction_buffer import BufferedTurn


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def segment_by_topic(
    turns: List[BufferedTurn],
    embedding_fn,
    similarity_threshold: float = 0.3,
) -> List[List[BufferedTurn]]:
    """
    Group consecutive turns into topic segments based on embedding similarity.

    Args:
        turns: List of buffered chat turns to segment.
        embedding_fn: A LangChain Embeddings instance (from llm_config.get_embeddings()).
        similarity_threshold: Boundary placed when consecutive similarity drops below this.

    Returns:
        List of segments, where each segment is a list of related turns.
    """
    if len(turns) <= 1:
        return [turns] if turns else []

    # Embed each turn (user + ai concatenated for full context)
    texts = [f"{t.user_message}\n{t.ai_response}" for t in turns]
    try:
        embeddings = embedding_fn.embed_documents(texts)
    except Exception as e:
        print(f"BG: Topic segmentation embedding failed: {e}. Returning single segment.")
        return [turns]

    # Find boundaries where similarity drops
    segments: List[List[BufferedTurn]] = []
    current_segment: List[BufferedTurn] = [turns[0]]

    for i in range(1, len(turns)):
        sim = _cosine_similarity(embeddings[i - 1], embeddings[i])
        if sim < similarity_threshold:
            # Topic boundary — start a new segment
            segments.append(current_segment)
            current_segment = [turns[i]]
        else:
            current_segment.append(turns[i])

    # Don't forget the last segment
    if current_segment:
        segments.append(current_segment)

    return segments
