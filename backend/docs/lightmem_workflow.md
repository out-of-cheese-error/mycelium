# LightMem-Inspired Memory Pipeline — Workflow Diagram

## Chat Session Flow

```
                          USER MESSAGE
                               │
                               ▼
                    ┌─────────────────────┐
                    │   LangGraph Agent    │
                    │  retrieve → generate │
                    │   → tool_execution   │
                    └──────────┬──────────┘
                               │
                          AI RESPONSE
                               │
                    ┌──────────▼──────────┐
                    │  Background Thread   │
                    │  (per-workspace lock) │
                    └──────────┬──────────┘
                               │
                   ┌───────────▼───────────┐
                   │  memory_extraction_mode │
                   └───┬───────────────┬───┘
                       │               │
                "immediate"       "buffered"
                  (default)      (LightMem)
                       │               │
                       ▼               ▼
        ┌──────────────────┐  ┌──────────────────────────────────────┐
        │  IMMEDIATE MODE  │  │         BUFFERED MODE (LightMem)     │
        │                  │  │                                      │
        │  ┌────────────┐  │  │  ┌─────────────────────────────────┐ │
        │  │ Pre-filter  │  │  │  │  SENSORY MEMORY (Light1)       │ │
        │  │ trivial msg?│  │  │  │                                │ │
        │  └──┬─────┬───┘  │  │  │  ┌───────────┐                 │ │
        │  skip    pass    │  │  │  │ Pre-filter │ trivial? → skip │ │
        │     │      │     │  │  │  └─────┬─────┘                 │ │
        │     │      ▼     │  │  │        │ pass                  │ │
        │     │  ┌───────┐ │  │  │        ▼                       │ │
        │     │  │Extract│ │  │  │  ┌────────────────┐            │ │
        │     │  │ (LLM) │ │  │  │  │ Add to Buffer  │            │ │
        │     │  └───┬───┘ │  │  │  │ (per-workspace) │            │ │
        │     │      │     │  │  │  └───────┬────────┘            │ │
        │     │      ▼     │  │  │          │                     │ │
        │     │  ┌───────┐ │  │  │  ┌───────▼────────┐           │ │
        │     │  │ Graph │ │  │  │  │ Threshold met? │           │ │
        │     │  │ Store │ │  │  │  │ turns≥5 OR     │           │ │
        │     │  └───────┘ │  │  │  │ tokens≥2000 OR │           │ │
        │     │            │  │  │  │ time≥10min     │           │ │
        │     │            │  │  │  └──┬──────────┬──┘           │ │
        │     │            │  │  │   no│         yes│             │ │
        │     │            │  │  │     ▼           │             │ │
        │     │            │  │  │  save to        │             │ │
        │     │            │  │  │  disk &         │             │ │
        │     │            │  │  │  wait           │             │ │
        │     │            │  │  └─────────────────┼─────────────┘ │
        │     │            │  │                    │                │
        │     │            │  │  ┌─────────────────▼──────────────┐ │
        │     │            │  │  │  SHORT-TERM MEMORY (Light2)   │ │
        │     │            │  │  │                               │ │
        │     │            │  │  │  ┌─────────────────────────┐  │ │
        │     │            │  │  │  │ Flush buffer            │  │ │
        │     │            │  │  │  │ (get all pending turns) │  │ │
        │     │            │  │  │  └───────────┬─────────────┘  │ │
        │     │            │  │  │              │                │ │
        │     │            │  │  │  ┌───────────▼─────────────┐  │ │
        │     │            │  │  │  │ Topic Segmentation      │  │ │
        │     │            │  │  │  │ (embedding similarity)  │  │ │
        │     │            │  │  │  │                         │  │ │
        │     │            │  │  │  │ Turn1 ─┐               │  │ │
        │     │            │  │  │  │ Turn2 ─┤ Segment A     │  │ │
        │     │            │  │  │  │ Turn3 ─┘  (sim > 0.3)  │  │ │
        │     │            │  │  │  │     ── boundary ──      │  │ │
        │     │            │  │  │  │ Turn4 ─┐               │  │ │
        │     │            │  │  │  │ Turn5 ─┘ Segment B     │  │ │
        │     │            │  │  │  └──┬──────────────┬──────┘  │ │
        │     │            │  │  │     │              │         │ │
        │     │            │  │  │     ▼              ▼         │ │
        │     │            │  │  │ ┌────────┐   ┌────────┐     │ │
        │     │            │  │  │ │Extract │   │Extract │     │ │
        │     │            │  │  │ │Seg A   │   │Seg B   │     │ │
        │     │            │  │  │ │(1 LLM  │   │(1 LLM  │     │ │
        │     │            │  │  │ │ call)  │   │ call)  │     │ │
        │     │            │  │  │ └───┬────┘   └───┬────┘     │ │
        │     │            │  │  │     │            │          │ │
        │     │            │  │  │     ▼            ▼          │ │
        │     │            │  │  │  ┌──────────────────────┐   │ │
        │     │            │  │  │  │   Graph Store        │   │ │
        │     │            │  │  │  │   (entities+relations)│   │ │
        │     │            │  │  │  └──────────┬───────────┘   │ │
        │     │            │  │  │             │               │ │
        │     │            │  │  │  ┌──────────▼───────────┐   │ │
        │     │            │  │  │  │ Flag workspace for   │   │ │
        │     │            │  │  │  │ consolidation        │   │ │
        │     │            │  │  │  └──────────────────────┘   │ │
        │     │            │  │  └───────────────────────────────┘ │
        └─────┼────────────┘  └────────────────────────────────────┘
              │
              ▼
    ┌──────────────────┐
    │  Emotion Update   │
    │  (always runs)    │
    └──────────────────┘
```

## Sleep-Time Consolidation (Light3) — Offline Process

```
  ┌──────────────────────────────────────────────────────────┐
  │  TRIGGERS                                                │
  │  • Periodic timer (every 6h by default)                  │
  │  • Manual: POST /workspaces/{id}/consolidate             │
  │  • Checks for "consolidation_needed" flag file           │
  └──────────────────────┬───────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Step 1: Get ALL node embeddings from ChromaDB           │
  │                                                          │
  │  [Node A] [Node B] [Node C] [Node D] ... [Node N]       │
  │   emb_a    emb_b    emb_c    emb_d        emb_n         │
  └──────────────────────┬───────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Step 2: Build update queues (time-aware similarity)     │
  │                                                          │
  │  For each node, find top-K similar nodes where:          │
  │  • cosine_similarity ≥ 0.85                              │
  │  • candidate.created_at > target.created_at              │
  │    (only newer nodes can update older ones)              │
  │                                                          │
  │  Node A (old) ← queue: [Node D (new, sim=0.92),         │
  │                          Node F (new, sim=0.87)]         │
  │  Node B (old) ← queue: [Node E (new, sim=0.91)]         │
  │  Node C       ← queue: []  (no similar candidates)      │
  └──────────────────────┬───────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Step 3: LLM decisions (parallel via ThreadPoolExecutor) │
  │                                                          │
  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
  │  │  Worker 1   │ │  Worker 2   │ │  Worker 3   │        │
  │  │             │ │             │ │             │        │
  │  │  Node A +   │ │  Node B +   │ │  Node G +   │        │
  │  │  candidates │ │  candidates │ │  candidates │        │
  │  │      │      │ │      │      │ │      │      │        │
  │  │      ▼      │ │      ▼      │ │      ▼      │        │
  │  │  LLM call   │ │  LLM call   │ │  LLM call   │        │
  │  │      │      │ │      │      │ │      │      │        │
  │  │      ▼      │ │      ▼      │ │      ▼      │        │
  │  │  "merge"    │ │  "update"   │ │  "ignore"   │        │
  │  └─────────────┘ └─────────────┘ └─────────────┘        │
  └──────────────────────┬───────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Step 4: Execute decisions                               │
  │                                                          │
  │  "merge"  → merge_nodes(target, [candidates])            │
  │             transfers edges, merges descriptions          │
  │             removes duplicate nodes                      │
  │                                                          │
  │  "update" → update_entity(target, new_description)       │
  │             enriches node with candidate info            │
  │                                                          │
  │  "delete" → delete_entity(target)                        │
  │             target is fully redundant                    │
  │                                                          │
  │  "ignore" → no action                                    │
  └──────────────────────────────────────────────────────────┘
```

## Comparison: Immediate vs Buffered

```
  IMMEDIATE (default)              BUFFERED (LightMem)
  ─────────────────────            ─────────────────────
  5 messages = 5 LLM calls         5 messages = 1-2 LLM calls
  Each turn isolated               Turns grouped by topic
  No filtering (relies on LLM)     Pre-filter skips noise
  No consolidation trigger         Flags for sleep-time update
  ─────────────────────            ─────────────────────
  Latency: per-turn LLM call       Latency: none until threshold
  Quality: fragmented entities     Quality: coherent extraction
  Cost: ~5x higher                 Cost: ~1x baseline
```
