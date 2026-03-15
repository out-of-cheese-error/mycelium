# MyCelium Backend API Reference

**Framework:** FastAPI
**Default Base URL:** `http://localhost:8000`
**Auth:** None (open access)
**CORS:** All origins allowed

---

## System

> Prefix: `/system`

### `GET /system/health`
Health check.

**Response:** `{"status": "ok"}`

---

### `GET /system/config`
Get current LLM configuration.

**Response:** `LLMConfigModel` — includes `chat_base_url`, `chat_api_key`, `chat_model`, `tts_base_url`, `tts_voice`, `tts_enabled`, `thinking_enabled`, MCP server configs, etc.

---

### `POST /system/config`
Update LLM configuration. Also refreshes MCP server connections and syncs OpenCode config.

**Body:** `LLMConfigModel`

**Response:** Updated `LLMConfigModel`

---

### `GET /system/models`
Fetch available models from the configured LLM provider (OpenAI-compatible `/models` endpoint).

**Response:**
```json
{"models": ["model-id-1", "model-id-2"]}
```

---

### `POST /system/mcp/test`
Test an MCP server connection and list its tools. Disconnects after testing.

**Body:** `MCPServerConfig` — `{name, command, args, env}`

**Response:** Connection result with tools list.

---

### `GET /system/mcp/tools`
Get all tools from currently connected MCP servers.

**Response:** List of tool definitions.

---

### `POST /system/mcp/refresh`
Refresh connections to all configured MCP servers.

**Response:** `{"server_name": {"connected": bool, "tools": [...], "error": str?}}`

---

### `GET /system/mcp/status`
Get connection status of all MCP servers.

**Response:** `{"server_name": {"connected": bool, "tool_count": int}}`

---

## Workspaces

> Prefix: `/workspaces`

### `GET /workspaces/`
List all workspaces.

**Response:** `[{"id": str, "node_count": int, "edge_count": int}]`

---

### `POST /workspaces/`
Create a new workspace.

**Body:**
```json
{"workspace_id": "my-workspace"}
```
ID must be alphanumeric (spaces, dashes, underscores allowed).

**Response:** `{"id": str, "node_count": 0, "edge_count": 0}`

---

### `DELETE /workspaces/{workspace_id}`
Delete a workspace and all its data. Also kills any associated tmux session.

**Response:** `{"status": "deleted"}`

---

### `POST /workspaces/{workspace_id}/rename`
Rename a workspace.

**Body:** `{"new_workspace_id": str}`

**Response:** `{"status": "success", "old_id": str, "new_id": str}`

---

### `GET /workspaces/{workspace_id}/stats`
Get workspace graph statistics.

**Response:** `{"node_count": int, "edge_count": int, ...}`

---

### `GET /workspaces/available_tools`
List all available tools (built-in + MCP).

**Response:**
```json
{
  "builtin": ["tool_name_1", "tool_name_2"],
  "mcp": [{"name": str, "server": str, "original_name": str, "description": str}]
}
```

---

### `GET /workspaces/exposed_tools`
List workspaces that are exposed as tools for other workspaces.

**Response:** List of exposed workspace tool definitions.

---

### `POST /workspaces/{workspace_id}/generate_tool_description`
Generate a tool description for this workspace using LLM (based on its concepts).

**Response:** `{"description": str}`

---

## Workspace Settings

### `GET /workspaces/{workspace_id}/settings`
Get workspace settings.

**Response:** `WorkspaceSettings`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `system_prompt` | str | `"You are a helpful assistant..."` | Base system prompt |
| `allow_search` | bool | `true` | Enable web search tools |
| `enabled_tools` | str[] \| null | *(see source)* | List of enabled tool names |
| `chat_message_limit` | int | `20` | Max messages in chat context |
| `graph_k` | int | `3` | Number of graph nodes to retrieve |
| `graph_depth` | int | `1` | Graph traversal depth |
| `graph_include_descriptions` | bool | `false` | Include node descriptions in context |
| `skill_persistent_context` | bool | `false` | Always inject skill summaries |
| `skill_persistent_max_words` | int | `150` | Max words per skill in persistent context |
| `skill_surface_threshold` | float | `0.50` | Similarity threshold to surface skills |
| `skill_auto_inject_threshold` | float | `0.85` | Similarity threshold to auto-inject skill instructions |
| `skill_surface_max` | int | `5` | Max skills surfaced per turn |
| `library_k` | int | `5` | Library search result count |
| `library_min_score` | float | `0.5` | Library minimum similarity score |
| `is_tool_enabled` | bool | `false` | Expose this workspace as a tool |
| `tool_name` | str? | `null` | Tool name when exposed |
| `tool_description` | str? | `null` | Tool description when exposed |

---

### `POST /workspaces/{workspace_id}/settings`
Update workspace settings.

**Body:** `WorkspaceSettings` (same schema as above)

**Response:** Updated `WorkspaceSettings`

---

## Workspace Emotions

### `GET /workspaces/{workspace_id}/emotions`
Get workspace emotion state.

**Response:**
```json
{
  "motive": "Help the user",
  "scales": [{"name": "Curiosity", "value": 75, "frozen": false}]
}
```

---

### `POST /workspaces/{workspace_id}/emotions`
Update workspace emotion state.

**Body:** `EmotionState` — `{motive: str, scales: [{name: str, value: 0-100, frozen: bool}]}`

**Response:** Updated `EmotionState`

---

## Persona Generation

### `POST /workspaces/{workspace_id}/generate_persona`
Generate a complete persona (system prompt, emotions, seed memories) from natural language cues.

**Body:** `{"cues": "A curious Victorian-era scientist"}`

**Response:** `{"status": "success", "message": str}`

Side effects: Updates `config.json` (system prompt), `emotion.json`, and adds entities/relations to the graph.

---

## Document Ingestion (to Knowledge Graph)

### `POST /workspaces/{workspace_id}/upload`
Upload and process a document — chunks it, extracts entities/relations into the knowledge graph.

**Form params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `file` | File | *(required)* | The document file |
| `chunk_size` | int | `4800` | Characters per chunk |
| `chunk_overlap` | int | `400` | Overlap between chunks |
| `language` | str | `"English"` | Document language |

**Response:** Processing result with extraction counts.

---

### `GET /workspaces/{workspace_id}/ingest_status`
Get ingestion job status for a workspace.

**Response:** Job status info (progress, current chunk, etc.)

---

### `POST /workspaces/{workspace_id}/ingest/stop`
Stop an active ingestion job.

**Query params:** `job_id` (str, required)

**Response:** `{"status": "stopped"}` or `{"status": "not_running"}`

---

### `POST /workspaces/{workspace_id}/ingest-url`
Ingest a web page or PDF URL into the knowledge graph. Runs in background.

**Body:**
```json
{"url": "https://example.com/page", "title": "Optional title"}
```

**Response:** `{"status": "started", "job_id": str, "message": str, "url": str, "is_pdf": bool}`

---

## Notes

### `GET /workspaces/{workspace_id}/notes`
List all notes, sorted by `updated_at` descending.

**Response:** `[{"id": str, "title": str, "content": str, "updated_at": float, "type": str?}]`

---

### `POST /workspaces/{workspace_id}/notes`
Create a new note.

**Body:** `{"title": str, "content": str}`

**Response:** `Note`

---

### `GET /workspaces/{workspace_id}/notes/{note_id}`
Get a specific note.

**Response:** `Note`

---

### `PUT /workspaces/{workspace_id}/notes/{note_id}`
Update a note.

**Body:** `{"title": str?, "content": str?}` — both optional

**Response:** Updated `Note`

---

### `DELETE /workspaces/{workspace_id}/notes/{note_id}`
Delete a note.

**Response:** `{"status": "deleted"}`

---

## Skills

### `GET /workspaces/{workspace_id}/skills`
List all skills, sorted by `updated_at` descending.

**Response:** `[{"id": str, "title": str, "summary": str, "explanation": str, "updated_at": float}]`

---

### `POST /workspaces/{workspace_id}/skills`
Create a new skill.

**Body:** `{"title": str, "summary": str, "explanation": str}`

**Response:** `Skill`

---

### `GET /workspaces/{workspace_id}/skills/{skill_id}`
Get a specific skill.

**Response:** `Skill`

---

### `PUT /workspaces/{workspace_id}/skills/{skill_id}`
Update a skill.

**Body:** `{"title": str?, "summary": str?, "explanation": str?}` — all optional

**Response:** Updated `Skill`

---

### `DELETE /workspaces/{workspace_id}/skills/{skill_id}`
Delete a skill.

**Response:** `{"status": "deleted"}`

---

## Scripts (Learning)

### `POST /workspaces/{workspace_id}/scripts/generate`
Generate a learning script based on a topic using the workspace's knowledge graph.

**Body:** `{"topic": str}`

**Response:** Generated script object.

---

### `GET /workspaces/{workspace_id}/scripts`
List all scripts, sorted by `created_at` descending.

**Response:** List of script objects.

---

### `DELETE /workspaces/{workspace_id}/scripts/{script_id}`
Delete a script.

**Response:** `{"status": "deleted", "id": str}`

---

## Graph Import/Export

### `GET /workspaces/{workspace_id}/graph/export`
Export the workspace graph as a JSON file download.

**Response:** `application/json` file download (`graph_export_{workspace_id}_{timestamp}.json`)

---

### `POST /workspaces/{workspace_id}/graph/import`
Import a graph from a JSON file. Backs up the existing graph before overwriting. Re-indexes in background.

**Form params:** `file` (File, required) — NetworkX node-link JSON

**Response:** `{"status": "success", "message": str, "node_count": int}`

---

## Graph Operations

### `POST /workspaces/{workspace_id}/contemplate`
Run contemplation — LLM generates new insights and connections from existing graph knowledge.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `n` | int | `3` | Number of contemplation rounds |
| `topic` | str? | `null` | Optional focus topic |
| `save_to_notes` | bool | `false` | Save contemplation results to notes |
| `depth` | int | `1` | Traversal depth |
| `job_id` | str? | `null` | Job ID for cancellation support |

**Response:** Contemplation results (new entities/relations discovered).

---

### `POST /workspaces/{workspace_id}/contemplate/stop`
Stop a running contemplation job.

**Query params:** `job_id` (str, required)

**Response:** `{"status": "stopped"}` or `{"status": "not_found"}`

---

### `GET /workspaces/{workspace_id}/knowledge_gaps`
Get nodes with low connectivity that could benefit from expansion.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `10` | Max results |
| `max_degree` | int | `2` | Maximum degree to be considered a "gap" |

**Response:** List of low-connectivity nodes.

---

### `POST /workspaces/{workspace_id}/collapse_redundancy`
Find semantically duplicate nodes. Optionally merge them.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `n` | int | `20` | Number of top nodes (by degree) to analyze |
| `include_neighbors` | bool | `true` | Include 1st-degree neighbors in analysis |
| `preview` | bool | `true` | If true, only return proposed groups without modifying graph |
| `job_id` | str? | `null` | Job ID for cancellation |

**Response:** List of duplicate groups with proposed merges.

---

### `POST /workspaces/{workspace_id}/collapse_redundancy/stop`
Stop a running redundancy collapse job.

**Query params:** `job_id` (str, required)

**Response:** `{"status": "stopped"}` or `{"status": "not_found"}`

---

### `POST /workspaces/{workspace_id}/merge_group`
Merge a group of duplicate nodes into a canonical node.

**Body:**
```json
{"canonical": "Main Node Name", "duplicates": ["Duplicate 1", "Duplicate 2"]}
```

**Response:** `{"status": "success", "message": str, "nodes_removed": int, ...}`

---

### `POST /workspaces/{workspace_id}/consolidate`
Trigger background graph consolidation (LightMem-inspired). Poll `/consolidate/progress` for status.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `similarity_threshold` | float | `0.85` | Embedding similarity threshold for merging |
| `max_workers` | int | `4` | Parallel workers |
| `job_id` | str? | `null` | Custom job ID |

**Response:** `{"status": "started", "job_id": str}` or `{"status": "already_running", "job_id": str}`

---

### `GET /workspaces/{workspace_id}/consolidate/progress`
Poll consolidation job progress.

**Query params:** `job_id` (str, required)

**Response:** Progress data or `{"status": "not_found"}`

---

### `POST /workspaces/{workspace_id}/consolidate/stop`
Stop a running consolidation job.

**Query params:** `job_id` (str, required)

**Response:** `{"status": "stopped"}` or `{"status": "not_found"}`

---

### `POST /workspaces/{workspace_id}/flush_buffer`
Force-flush the extraction buffer and run entity extraction immediately on buffered turns.

**Response:** `{"status": "flushed", "turns_flushed": int, "message": str}` or `{"status": "empty", ...}`

---

### `POST /workspaces/{workspace_id}/assign_singletons`
Analyze singleton (isolated) nodes and propose relationships or merges.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `n` | int | `10` | Number of singletons to analyze |
| `preview` | bool | `true` | Only return proposals without modifying graph |
| `job_id` | str? | `null` | Job ID for cancellation |

**Response:** List of proposals.

---

### `POST /workspaces/{workspace_id}/assign_singletons/stop`
Stop a running singleton assignment job.

**Query params:** `job_id` (str, required)

**Response:** `{"status": "stopped"}` or `{"status": "not_found"}`

---

### `POST /workspaces/{workspace_id}/execute_singleton_proposals`
Execute selected singleton proposals.

**Body:**
```json
{"proposal_ids": ["id1", "id2"], "proposals": [/* full proposals list */]}
```

**Response:** Execution result with counts.

---

## Chat

### `POST /chat`
Stateless chat endpoint. Uses graph memory for context but does not persist conversation history.

**Body:**
```json
{"message": "Hello", "workspace_id": "default"}
```

**Response:** `{"response": str}`

---

## Threads (Multi-turn Chat)

> Prefix: `/threads`

### `GET /threads/{workspace_id}`
List all threads in a workspace.

**Response:** `[{"id": str, "workspace_id": str, "title": str, "created_at": str}]`

---

### `POST /threads/`
Create a new empty thread.

**Body:** `{"workspace_id": str, "title": "New Chat"}`

**Response:** `Thread`

---

### `POST /threads/with_messages`
Create a thread with pre-populated messages (e.g., carrying over from graph chat).

**Body:**
```json
{
  "workspace_id": str,
  "title": "Graph Chat",
  "messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

**Response:** `Thread`

---

### `DELETE /threads/{workspace_id}/{thread_id}`
Delete a specific thread.

**Response:** `{"status": "deleted"}`

---

### `DELETE /threads/{workspace_id}`
Delete all threads in a workspace.

**Response:** `{"status": "deleted", "count": int}`

---

### `GET /threads/{workspace_id}/{thread_id}/history`
Get full message history for a thread.

**Response:** `[{"role": str, "content": str, "thinking": str?}]`

---

### `POST /threads/{workspace_id}/{thread_id}/chat` (Streaming)
Send a message in a thread. Streams the response as `text/plain`.

**Body:** `{"message": str}`

**Response:** Streaming `text/plain` — LLM tokens streamed in real-time. Includes tool usage indicators (`> Usage: tool_name`) and token usage stats. Auto-generates thread title on first message.

Side effects: Saves messages to thread, triggers background entity extraction and emotion update.

---

## Graph Chat

> Prefix: `/graph`

### `GET /graph/{workspace_id}`
Get full graph data for visualization.

**Response:** `{"nodes": [...], "links": [...]}`

---

### `POST /graph/{workspace_id}/chat` (Streaming)
Chat with knowledge graph context. Streams response as `text/plain`.

**Body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message` | str | *(required)* | User's question |
| `focused_node_id` | str? | `null` | Focus retrieval around a specific node |
| `k` | int? | workspace default or `3` | Number of nodes to retrieve |
| `depth` | int? | workspace default or `1` | Traversal depth |

**Response:** Streaming text. Final line contains metadata:
```
###GRAPH_CONTEXT###{"retrieved_nodes": [...], "retrieved_edges": [...]}
```

---

### `GET /graph/{workspace_id}/node/{node_id}`
Get context for a specific node and its neighbors.

**Query params:** `depth` (int, default `1`)

**Response:**
```json
{
  "node": {"id": str, "type": str, "description": str},
  "neighbors": [{"id": str, "type": str, "description": str}],
  "edges": [{"source": str, "target": str, "relation": str}]
}
```

---

### `GET /debug/graph_check/{workspace_id}`
Debug endpoint to check graph consistency.

**Query params:** `node_id` (str?, optional)

**Response:** Debug info including node counts, mismatches, and similar node search results.

---

## Concepts

> Prefix: `/concepts`

### `GET /concepts/{workspace_id}`
Get existing concepts for a workspace.

**Response:** List of concept objects.

---

### `POST /concepts/generate` (Streaming)
Generate concepts via graph clustering. Streams as NDJSON.

**Body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace_id` | str | *(required)* | Target workspace |
| `resolution` | float | `1.0` | Clustering resolution |
| `max_clusters` | int | `5` | Maximum number of clusters |
| `min_cluster_size` | int | `5` | Minimum nodes per cluster |

**Response:** `application/x-ndjson` stream of concept objects.

---

## Hot Topics

> Prefix: `/hot_topics`

### `GET /hot_topics/{workspace_id}`
Get top nodes by degree centrality.

**Query params:** `limit` (int, 1-100, default `10`)

**Response:** List of top nodes with degree scores.

---

## Connectors

> Prefix: `/connectors`

### `GET /connectors/{workspace_id}`
Get top nodes by betweenness centrality (bridge/connector nodes).

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `10` (1-100) | Max results |
| `sample_size` | int? | `null` (1-5000) | Approximate with k nodes for speed |
| `normalize` | bool | `true` | Normalize by degree for per-connection bridging score |

**Response:** List of connector nodes with centrality scores.

---

## Articles

> Prefix: `/articles`

### `POST /articles/generate` (Streaming)
Generate a long-form article using the ConvergeWriter pipeline. Streams as NDJSON.

**Body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace_id` | str | *(required)* | Source workspace |
| `topic` | str | *(required)* | Article topic |
| `mode` | str | `"existing"` | `"existing"` (graph only) or `"research"` (with web research) |
| `research_sources` | str[]? | `null` | Sources for research mode: `"wikipedia"`, `"arxiv"`, `"web"` |
| `resolution` | float | `1.0` | Clustering resolution |
| `min_cluster_size` | int | `3` | Min nodes per cluster |
| `max_clusters` | int | `8` | Max clusters |

**Response:** `application/x-ndjson` stream of progress updates and final article.

---

### `POST /articles/evolve` (Streaming)
Evolve an existing article note using genetic algorithm optimization. Streams as NDJSON.

**Body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace_id` | str | *(required)* | Workspace |
| `note_id` | str | *(required)* | Note containing the article to evolve |
| `max_generations` | int | `3` | GA max generations |
| `convergence_threshold` | float | `8.5` | Score threshold to stop |
| `stagnation_limit` | int | `2` | Stop after N generations without improvement |
| `evaluator_persona` | str? | `null` | Custom evaluator persona prompt |

**Response:** `application/x-ndjson` stream of generation scores and final evolved article.

---

## Library (RAG Document Store)

> Prefix: `/library`

### `POST /library/{workspace_id}/search`
Semantic search over library chunks.

**Body:** `{"query": str, "k": 10}`

**Response:** `{"results": [{"text": str, "source_name": str, "score": float, ...}]}`

---

### `GET /library/{workspace_id}/sources`
List all library sources with chunk counts.

**Response:** `{"sources": [{"source_id": str, "source_name": str, "chunk_count": int, ...}]}`

---

### `GET /library/{workspace_id}/source/{source_id}/chunks`
Get all chunks for a specific source, ordered by chunk index.

**Response:** `{"chunks": [...]}`

---

### `DELETE /library/{workspace_id}/source/{source_id}`
Delete a source and all its chunks.

**Response:** `{"status": "deleted", "source_id": str}`

---

### `GET /library/{workspace_id}/stats`
Get library statistics.

**Response:** Stats object (source count, chunk count, etc.)

---

### `POST /library/{workspace_id}/upload`
Upload a file to the library (chunk + embed, no entity extraction).

**Form params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `file` | File | *(required)* | Document file |
| `chunk_size` | int | `4800` | Characters per chunk |
| `chunk_overlap` | int | `400` | Overlap between chunks |

**Response:** Processing result.

---

### `POST /library/{workspace_id}/ingest-url`
Fetch a URL and ingest into the library. Runs in background.

**Body:**
```json
{"url": str, "chunk_size": 4800, "chunk_overlap": 400, "source_name": str?}
```

**Response:** `{"job_id": str, "status": "started", "source_name": str}`

---

### `POST /library/{workspace_id}/promote`
Search library and extract entities from relevant chunks into the knowledge graph.

**Body:**
```json
{"query": str, "k": 5, "min_score": 0.5}
```

**Response:**
```json
{
  "entities": int,
  "relations": int,
  "chunks_used": int,
  "filtered": int,
  "sources": [str],
  "message": str
}
```

---

## Audio / Text-to-Speech

> Prefix: `/audio`

### `GET /audio/test`
Test TTS service connectivity.

**Response:** `{"status": "connected" | "error", ...}` — includes available voices when connected.

---

### `POST /audio/speech` (Streaming)
Generate speech from text. Streams WAV audio (24kHz, 16-bit, mono PCM).

**Body:** `{"input": "Text to speak"}`

**Response:** `audio/wav` stream.

---

### `GET /audio/stream` (Streaming)
Same as `POST /audio/speech` but as GET.

**Query params:** `input` (str, required)

**Response:** `audio/wav` stream.

---

### `GET /audio/extract-text`
Fetch a URL and extract the article text (cleaned for TTS).

**Query params:** `url` (str, required)

**Response:** `{"title": str, "text": str}`

---

## Voice Call (WebSocket)

> Prefix: `/call`

### `WS /call/ws`
Live voice call endpoint. Full duplex: browser mic audio in, TTS audio out.

**Flow:** Browser mic -> WebSocket binary -> ASR transcription -> LLM (streaming) -> TTS -> WebSocket binary -> speaker

**Control messages (JSON, client -> server):**

| Type | Fields | Description |
|------|--------|-------------|
| `start_call` | `workspace_id`, `thread_id` | Initialize call session |
| `vad_speech_end` | — | Voice activity detection: user stopped speaking, process buffered audio |
| `interrupt` | — | Cancel current LLM/TTS response |
| `end_call` | — | End the call |

**Audio data:** Binary frames (PCM16) for microphone input.

**Server -> client messages:**

| Type | Fields | Description |
|------|--------|-------------|
| `call_started` | — | Call session initialized |
| `call_ended` | — | Call session ended |
| `state` | `state`: `"listening"` \| `"thinking"` \| `"speaking"` | Current call state |
| `transcript` | `text`, `final` | User speech transcription |
| `response_text` | `text`, `done` | LLM response text chunks |
| `error` | `message` | Error message |

Binary frames from server = TTS PCM audio.

---

## Terminal

> Prefix: `/terminal`

### `WS /terminal/{workspace_id}/ws`
Interactive terminal via WebSocket. Attaches to a persistent tmux session for the workspace.

**Binary frames (client -> server):** Terminal input bytes.

**JSON control messages (client -> server):**

| Type | Fields | Description |
|------|--------|-------------|
| `resize` | `cols`, `rows` | Resize the terminal |

**Binary frames (server -> client):** Terminal output bytes.

---

### `POST /terminal/{workspace_id}/chat` (Streaming)
Natural language terminal assistant. LLM translates requests to shell commands and executes them.

**Body:**
```json
{
  "message": "Install numpy and check the version",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

**Response:** Streaming `text/plain` — explanations, executed commands (`` > `command` ``), and their output.

---

## Error Handling

All endpoints return standard HTTP error codes:

| Code | Meaning |
|------|---------|
| `400` | Bad request / invalid parameters |
| `404` | Resource not found |
| `500` | Internal server error |

Error response format: `{"detail": "error message"}`
