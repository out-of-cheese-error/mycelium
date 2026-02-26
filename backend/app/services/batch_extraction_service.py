"""
Batch extraction service — orchestrates the LightMem-inspired pipeline.

Flow: pre-filter → buffer → (on trigger) segment by topic → extract per
segment → add to graph.
"""

import json
import os
import re
import traceback
from typing import List

from langchain_core.messages import HumanMessage

from app.memory_store import GraphMemory, MEMORY_BASE_DIR
from app.llm_config import llm_config
from app.services.message_filter import should_extract
from app.services.extraction_buffer import (
    BufferedTurn, BufferConfig, get_buffer,
)
from app.services.topic_segmenter import segment_by_topic


def _build_segment_extraction_prompt(segment: List[BufferedTurn]) -> str:
    """
    Build an extraction prompt for a topic segment (multiple turns).

    This is richer than the single-turn prompt: the LLM sees a coherent
    block of conversation on the same topic and can extract cross-turn
    entities and relationships.
    """
    conversation_lines = []
    for i, turn in enumerate(segment, 1):
        conversation_lines.append(f"  Turn {i}:")
        conversation_lines.append(f"    User: {turn.user_message}")
        conversation_lines.append(f"    AI: {turn.ai_response}")
    conversation_text = "\n".join(conversation_lines)

    return f"""Analyze the following conversation segment and extract meaningful entities and relationships to build a knowledge graph.

{conversation_text}

Return the output strictly as a JSON object with two keys: "entities" and "relations".

1. "entities": A list of objects {{ "name": "Exact Name", "type": "Category", "description": "Brief facts" }}
2. "relations": A list of objects {{ "source": "Entity Name", "target": "Entity Name", "relation": "relationship label" }}

Rules:
- Extract factual, long-term useful information (names, preferences, tech stacks, projects, locations, dates).
- CONNECT entities with relations whenever possible — especially across different turns in the segment.
- Consolidate information about the same entity from multiple turns into a single entity entry.
- Ignore greetings or trivial chit-chat.

Example JSON:
{{
  "entities": [
    {{ "name": "User", "type": "Person", "description": "The user of the system" }},
    {{ "name": "MyCelium", "type": "Project", "description": "A knowledge graph chatbot project using Python and FastAPI" }},
    {{ "name": "Python", "type": "Technology", "description": "Programming language" }}
  ],
  "relations": [
    {{ "source": "User", "target": "MyCelium", "relation": "working_on" }},
    {{ "source": "MyCelium", "target": "Python", "relation": "uses" }}
  ]
}}

JSON:
"""


def _extract_and_store(workspace_id: str, segment: List[BufferedTurn]):
    """Run LLM extraction on a single topic segment and store results."""
    from app.utils.thinking import strip_thinking

    prompt = _build_segment_extraction_prompt(segment)
    llm = llm_config.get_ingestion_llm()
    response = llm.invoke([HumanMessage(content=prompt)])

    content = strip_thinking(response.content)
    print(f"BG [buffered]: Extraction raw content: {content[:100]}...")

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        print("BG [buffered]: No JSON found in extraction response.")
        return

    data = json.loads(match.group(0))
    entities = data.get("entities", [])
    relations = data.get("relations", [])

    memory_store = GraphMemory(workspace_id=workspace_id)

    for entity in entities:
        memory_store.add_entity(entity["name"], entity["type"], entity["description"])

    for rel in relations:
        memory_store.add_relation(rel["source"], rel["target"], rel["relation"])

    print(
        f"BG [buffered]: Extracted {len(entities)} entities and "
        f"{len(relations)} relations from {len(segment)}-turn segment "
        f"for {workspace_id}."
    )


def run_buffered_extraction(workspace_id: str, user_message: str, ai_response: str):
    """
    Main entry point for buffered extraction mode.
    Called from the background thread in agent.py instead of immediate extraction.
    """
    # 1. Pre-filter trivial messages
    if not should_extract(user_message, ai_response):
        print(f"BG [buffered]: Skipping trivial message for {workspace_id}")
        return

    # 2. Load config from llm_config
    cfg = llm_config.get_config()
    buf_config = BufferConfig(
        turn_threshold=getattr(cfg, "buffer_turn_threshold", 5),
        token_threshold=getattr(cfg, "buffer_token_threshold", 2000),
        time_threshold_seconds=getattr(cfg, "buffer_time_threshold_seconds", 600),
    )

    # 3. Add to buffer
    buffer = get_buffer(workspace_id, buf_config)
    should_trigger = buffer.add_turn(user_message, ai_response)

    # Persist buffer to disk after every addition (crash safety)
    ws_dir = os.path.join(MEMORY_BASE_DIR, workspace_id)
    buffer.save_to_disk(ws_dir)

    if not should_trigger:
        print(
            f"BG [buffered]: Buffered turn for {workspace_id} "
            f"({len(buffer.turns)} turns in buffer)"
        )
        return

    # 4. Flush buffer and segment by topic
    turns = buffer.flush()
    # Clear the persisted buffer file
    buf_file = os.path.join(ws_dir, "extraction_buffer.json")
    if os.path.exists(buf_file):
        try:
            os.remove(buf_file)
        except Exception:
            pass

    print(
        f"BG [buffered]: Triggered extraction for {workspace_id} "
        f"({len(turns)} turns)"
    )

    similarity_threshold = getattr(cfg, "topic_similarity_threshold", 0.3)
    try:
        embedding_fn = llm_config.get_embeddings()
        segments = segment_by_topic(turns, embedding_fn, similarity_threshold)
    except Exception as e:
        print(f"BG [buffered]: Topic segmentation failed, using single segment: {e}")
        segments = [turns]

    print(f"BG [buffered]: Segmented into {len(segments)} topic group(s)")

    # 5. Extract from each segment
    for i, segment in enumerate(segments):
        try:
            _extract_and_store(workspace_id, segment)
        except Exception as e:
            print(f"BG [buffered]: Extraction failed for segment {i}: {e}")
            traceback.print_exc()


def force_extract_turns(workspace_id: str, turns: List[BufferedTurn]):
    """
    Force-extract a list of turns (e.g., on server shutdown).
    Skips buffering and immediately processes.
    """
    if not turns:
        return

    print(f"BG [buffered]: Force-extracting {len(turns)} turns for {workspace_id}")

    try:
        embedding_fn = llm_config.get_embeddings()
        cfg = llm_config.get_config()
        similarity_threshold = getattr(cfg, "topic_similarity_threshold", 0.3)
        segments = segment_by_topic(turns, embedding_fn, similarity_threshold)
    except Exception:
        segments = [turns]

    for segment in segments:
        try:
            _extract_and_store(workspace_id, segment)
        except Exception as e:
            print(f"BG [buffered]: Force extraction failed: {e}")
            traceback.print_exc()
