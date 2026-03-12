import os
import json
import uuid
import re
import copy
import random
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from langchain_core.messages import HumanMessage
from app.memory_store import GraphMemory, MEMORY_BASE_DIR
from app.llm_config import llm_config
from app.utils.thinking import strip_thinking


# --- Evolutionary Article Optimization Data Structures ---

@dataclass
class SectionGene:
    title: str
    content: str
    cluster_id: Optional[str]
    sources: list
    cluster_nodes: list
    cluster_summary: str = ""
    section_description: str = ""
    scores: Optional[dict] = None  # {grounding, consistency, coherence, completeness, feedback}

    def avg_score(self) -> float:
        if not self.scores:
            return 0.0
        keys = ["grounding", "consistency", "coherence", "completeness"]
        vals = [self.scores.get(k, 0) for k in keys]
        return sum(vals) / len(vals)


@dataclass
class ArticleGenome:
    id: str
    generation: int
    sections: list  # list of SectionGene (body sections only)
    fitness: Optional[dict] = None  # {grounding, consistency, coherence, completeness, overall}

    @property
    def overall_fitness(self) -> float:
        if not self.fitness:
            return 0.0
        return self.fitness.get("overall", 0.0)


VARIANT_CONFIGS = [
    (0.4, "Write in a precise, academic style. Be exact and cite specific entities."),
    (0.8, "Write in an engaging, narrative style. Make the content compelling and readable."),
    (0.6, "Write in a comprehensive, systematic style. Be thorough and cover all key entities."),
]


class ArticleService:
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.memory = GraphMemory(workspace_id=workspace_id)
        self.llm = llm_config.get_chat_llm()

    async def _llm_invoke(self, prompt: str, timeout: float = 60.0) -> str:
        """Invoke LLM with timeout and strip thinking tags."""
        response = await asyncio.wait_for(
            self.llm.ainvoke([HumanMessage(content=prompt)]),
            timeout=timeout
        )
        return strip_thinking(response.content)

    async def _summarize_cluster(self, cluster_nodes: list, cluster_index: int) -> dict:
        """Generate a summary for a cluster of graph nodes."""
        context_nodes = cluster_nodes[:50]
        context = self.memory.get_subgraph_context(context_nodes)

        if len(cluster_nodes) > 50:
            context += f"\n... (+{len(cluster_nodes) - 50} more entities)"

        prompt = f"""Analyze the following knowledge graph subgraph and create a concise summary.

Subgraph Data:
{context}

Task:
1. Provide a short 'Title' (max 6 words) that captures the main theme.
2. Provide a 'Summary' (3-5 sentences) explaining the key information, entities, and relationships.
3. List the most important entities (up to 10).

Output strictly as JSON:
{{
    "title": "...",
    "summary": "...",
    "key_entities": ["entity1", "entity2", ...]
}}
"""
        try:
            content = await self._llm_invoke(prompt, timeout=30.0)
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {
                    "cluster_id": f"cluster_{cluster_index}",
                    "title": data.get("title", "Untitled"),
                    "summary": data.get("summary", ""),
                    "key_entities": data.get("key_entities", []),
                    "nodes": cluster_nodes
                }
        except Exception as e:
            print(f"Error summarizing cluster {cluster_index}: {e}")

        return {
            "cluster_id": f"cluster_{cluster_index}",
            "title": f"Cluster {cluster_index}",
            "summary": "",
            "key_entities": [],
            "nodes": cluster_nodes
        }

    async def _generate_outline(self, topic: str, cluster_summaries: list) -> dict:
        """Generate a hierarchical outline mapped to clusters."""
        summaries_text = ""
        for cs in cluster_summaries:
            summaries_text += f"\n--- {cs['cluster_id']}: {cs['title']} ---\n{cs['summary']}\n"

        prompt = f"""You are creating the outline for a long-form article about: "{topic}"

You have the following knowledge clusters available:

{summaries_text}

Task:
1. Create a hierarchical article outline with an Introduction, main body sections, and Conclusion.
2. Each main body section MUST map to exactly ONE knowledge cluster. Use the cluster that best fits that section's theme.
3. Order sections for logical flow and coherent argumentation.
4. Only use information from the provided clusters — do not invent topics not covered by the clusters.

Output strictly as JSON:
{{
    "title": "Article Title",
    "sections": [
        {{"title": "Introduction", "cluster_id": null, "description": "Brief description of what this section covers"}},
        {{"title": "Section Title", "cluster_id": "cluster_0", "description": "Brief description"}},
        {{"title": "Another Section", "cluster_id": "cluster_1", "description": "Brief description"}},
        {{"title": "Conclusion", "cluster_id": null, "description": "Brief description"}}
    ]
}}
"""
        content = await self._llm_invoke(prompt, timeout=45.0)
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("Failed to parse outline from LLM response")

    def _build_cluster_roster(self, cluster_summary: dict) -> str:
        """Build a compact one-line-per-node overview of the cluster."""
        lines = []
        for node_id in cluster_summary["nodes"]:
            if self.memory.graph.has_node(node_id):
                data = self.memory.graph.nodes[node_id]
                node_type = data.get("type", "Unknown")
                desc = data.get("description", "")
                if len(desc) > 120:
                    desc = desc[:120] + "..."
                degree = self.memory.graph.degree[node_id]
                lines.append(f"- {node_id} ({node_type}, {degree} connections): {desc}")
        return "\n".join(lines)

    def _build_unexplored_roster(self, cluster_summary: dict, explored: set) -> str:
        """Build roster of nodes not yet explored."""
        lines = []
        for node_id in cluster_summary["nodes"]:
            if node_id in explored:
                continue
            if self.memory.graph.has_node(node_id):
                data = self.memory.graph.nodes[node_id]
                desc = data.get("description", "")
                if len(desc) > 120:
                    desc = desc[:120] + "..."
                degree = self.memory.graph.degree[node_id]
                lines.append(f"- {node_id} ({data.get('type', 'Unknown')}, {degree} connections): {desc}")
        return "\n".join(lines) if lines else "(All entities explored)"

    def _parse_exploration_actions(self, response: str) -> tuple:
        """Parse LLM exploration response. Returns (node_ids_to_explore, is_done)."""
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if not match:
            return [], True
        try:
            data = json.loads(match.group(0))
            action = data.get("action", "DONE")
            if action == "DONE":
                return [], True
            nodes = data.get("explore", [])
            valid = [n for n in nodes if self.memory.graph.has_node(n)]
            return valid[:15], False
        except json.JSONDecodeError:
            return [], True

    async def _explore_cluster_graph(self, section_title: str, section_desc: str,
                                      cluster_summary: dict, topic: str,
                                      article_outline: list = None,
                                      max_rounds: int = 3) -> str:
        """LLM-driven iterative graph exploration to gather section-relevant context."""
        roster = self._build_cluster_roster(cluster_summary)
        explored_context = []
        explored_node_ids = set()

        # Build outline context so the LLM knows the full article structure
        outline_context = ""
        if article_outline:
            outline_lines = [f"  - {s['title']}: {s.get('description', '')}" for s in article_outline]
            outline_context = f"\nFull Article Outline (this section is part of a larger article):\n" + "\n".join(outline_lines)

        for round_num in range(max_rounds):
            if round_num == 0:
                exploration_prompt = f"""You are researching a knowledge graph to gather context for writing an article section.

Article Main Subject: "{topic}"
Section Title: "{section_title}"
Section Purpose: {section_desc}
{outline_context}

Cluster Summary: {cluster_summary['summary']}

Available Entities in this knowledge cluster:
{roster}

Your task: Select the most relevant entities to explore in detail for writing this section.

IMPORTANT: This section is part of a larger article about "{topic}". Prioritize entities that:
1. Directly relate to the main subject "{topic}" AND this section's focus
2. Provide specific facts that connect this section's theme back to the main subject
3. Bridge between this section's cluster and the overarching article narrative

Avoid selecting entities that are only tangentially related or would lead the section away from the main subject.

Respond with JSON:
{{"action": "EXPLORE", "explore": ["entity_id_1", "entity_id_2", ...], "reasoning": "brief explanation"}}

Or if the cluster summary alone is sufficient:
{{"action": "DONE", "reasoning": "why no exploration needed"}}

Select 5-15 entities that are most relevant."""
            else:
                already_explored = "\n".join(explored_context)
                unexplored = self._build_unexplored_roster(cluster_summary, explored_node_ids)
                is_final = (round_num == max_rounds - 1)

                exploration_prompt = f"""You are continuing to research a knowledge graph for an article section.

Article Main Subject: "{topic}"
Section Title: "{section_title}"
Section Purpose: {section_desc}
{outline_context}

Context gathered so far:
{already_explored}

Available entities NOT yet explored:
{unexplored}

{"This is the final exploration round. Select any remaining important entities, or respond DONE." if is_final else "Select more entities to explore, or respond DONE if you have enough context."}

Remember: prioritize entities that connect this section back to the main subject "{topic}" and support the overall article narrative.

Respond with JSON:
{{"action": "EXPLORE", "explore": ["entity_id_1", ...], "reasoning": "brief explanation"}}
or
{{"action": "DONE", "reasoning": "why exploration is complete"}}"""

            response = await self._llm_invoke(exploration_prompt, timeout=30.0)
            nodes_to_explore, is_done = self._parse_exploration_actions(response)

            if is_done or not nodes_to_explore:
                break

            # Gather detailed info for selected nodes
            round_lines = [f"--- Exploration Round {round_num + 1} ---"]
            for node_id in nodes_to_explore:
                if node_id in explored_node_ids:
                    continue
                explored_node_ids.add(node_id)
                neighbor_data = self.memory.get_node_neighbors(node_id)
                if not neighbor_data:
                    continue

                round_lines.append(f"\n=== {neighbor_data['id']} ({neighbor_data['type']}) ===")
                round_lines.append(f"Description: {neighbor_data['description']}")
                if neighbor_data["neighbors"]:
                    round_lines.append("Connections:")
                    for nb in neighbor_data["neighbors"]:
                        nb_desc = ""
                        if self.memory.graph.has_node(nb["id"]):
                            nb_data = self.memory.graph.nodes[nb["id"]]
                            nb_desc = nb_data.get("description", "")
                            nb_type = nb_data.get("type", "Unknown")
                            if len(nb_desc) > 100:
                                nb_desc = nb_desc[:100] + "..."
                            round_lines.append(
                                f"  - [{nb['relation']}] -> {nb['id']} ({nb_type}): {nb_desc}"
                            )
                        else:
                            round_lines.append(f"  - [{nb['relation']}] -> {nb['id']}")

            explored_context.append("\n".join(round_lines))

        if not explored_context:
            return self.memory.get_subgraph_context(cluster_summary["nodes"][:60])

        return "\n\n".join(explored_context)

    async def _generate_section(self, section_title: str, section_desc: str,
                                 cluster_summary: dict, topic: str,
                                 article_outline: list = None) -> str:
        """Generate content for a single article section grounded in its cluster."""
        # LLM-driven graph exploration to gather targeted context
        context = await self._explore_cluster_graph(
            section_title, section_desc, cluster_summary, topic,
            article_outline=article_outline
        )

        # Build outline context for the writing prompt
        outline_info = ""
        if article_outline:
            outline_lines = [f"  - {s['title']}" for s in article_outline]
            outline_info = f"\nArticle Structure:\n" + "\n".join(outline_lines)

        prompt = f"""You are writing a section of a long-form article about: "{topic}"

Section Title: {section_title}
Section Purpose: {section_desc}
{outline_info}

Knowledge Context (gathered by exploring the knowledge graph):
{context}

Cluster Summary: {cluster_summary['summary']}

Instructions:
- Write a detailed, well-structured section (3-6 paragraphs).
- Ground ALL claims in the provided knowledge context. Do not fabricate information.
- Reference specific entities and relationships from the context.
- Connect the content of this section back to the main subject "{topic}". This section should read as part of a coherent article, not a standalone essay.
- Use clear, informative prose suitable for an educated reader.
- Do NOT include the section title in your output — just the body text.
- Use markdown formatting where appropriate (bold, italic, lists).
"""
        return await self._llm_invoke(prompt, timeout=60.0)

    async def _generate_intro_conclusion(self, topic: str, article_title: str,
                                          body_text: str, section_type: str) -> str:
        """Generate introduction or conclusion from the assembled body."""
        if section_type == "introduction":
            prompt = f"""Write an engaging introduction for a long-form article.

Article Title: {article_title}
Topic: {topic}

The article covers the following content:
{body_text[:3000]}

Instructions:
- Introduce the topic and its significance (2-3 paragraphs).
- Preview the main themes covered in the article.
- Hook the reader's attention.
- Do NOT include a heading — just the body text.
"""
        else:
            prompt = f"""Write a conclusion for a long-form article.

Article Title: {article_title}
Topic: {topic}

The article covered the following content:
{body_text[:3000]}

Instructions:
- Summarize the key insights (2-3 paragraphs).
- Highlight the most important takeaways.
- End with a forward-looking statement or open question.
- Do NOT include a heading — just the body text.
"""
        return await self._llm_invoke(prompt, timeout=45.0)

    async def _research_topic(self, topic: str, sources: list = None):
        """Research mode: generate search keywords and find sources to ingest."""
        if sources is None:
            sources = ["wikipedia"]

        prompt = f"""Generate 5-8 specific search keywords/phrases for researching the topic: "{topic}"

These keywords should cover different aspects and subtopics.
Output as a JSON array of strings:
["keyword1", "keyword2", ...]
"""
        content = await self._llm_invoke(prompt, timeout=20.0)
        match = re.search(r"\[.*\]", content, re.DOTALL)
        keywords = json.loads(match.group(0)) if match else [topic]

        results = {"keywords": keywords, "ingested": []}

        for keyword in keywords[:6]:
            for source in sources:
                try:
                    if source == "wikipedia":
                        from app.services.wikipedia_service import wikipedia_service
                        from app.document_processor import process_file
                        # Search for relevant pages
                        search_result = wikipedia_service.search_pages(keyword, limit=2)
                        # Parse titles from search result (format: "1. Title - snippet")
                        for line in search_result.split("\n"):
                            line = line.strip()
                            if line and line[0].isdigit() and ". " in line:
                                title = line.split(". ", 1)[1].split(" - ")[0].strip()
                                if title and title not in [r.split(":")[-1] for r in results["ingested"]]:
                                    content = wikipedia_service.get_page_content(title)
                                    if not content.startswith("Error"):
                                        # Save to temp and process
                                        temp_dir = os.path.join(os.getcwd(), "temp", self.workspace_id)
                                        os.makedirs(temp_dir, exist_ok=True)
                                        safe_title = "".join(x for x in title if x.isalnum() or x in " -_").strip()
                                        file_path = os.path.join(temp_dir, f"wiki_{safe_title}.txt")
                                        with open(file_path, "w", encoding="utf-8") as f:
                                            f.write(content)
                                        import uuid as _uuid
                                        job_id = str(_uuid.uuid4())
                                        await process_file(file_path, self.workspace_id, chunk_size=4000, job_id=job_id)
                                        results["ingested"].append(f"wikipedia:{title}")
                except Exception as e:
                    print(f"Research ingestion error for '{keyword}' from {source}: {e}")

        return results

    async def generate_article_stream(self, topic: str, mode: str = "existing",
                                       research_sources: list = None,
                                       resolution: float = 1.0,
                                       min_cluster_size: int = 3,
                                       max_clusters: int = 8):
        """
        Main ConvergeWriter pipeline. Yields progress updates as dicts.

        Stages:
        1. (Optional) Research & ingest new sources
        2. Get topic-relevant clusters from the knowledge graph
        3. Summarize each cluster
        4. Generate outline mapped to clusters
        5. Generate each section grounded in its cluster
        6. Generate intro/conclusion
        7. Save article
        """
        article_id = str(uuid.uuid4())[:8]

        # Stage 1: Research (optional)
        if mode == "research":
            yield {"stage": "research", "status": "starting", "message": "Researching topic and ingesting sources..."}
            try:
                research_result = await self._research_topic(topic, research_sources)
                yield {
                    "stage": "research", "status": "complete",
                    "message": f"Ingested {len(research_result['ingested'])} sources",
                    "details": research_result
                }
            except Exception as e:
                yield {"stage": "research", "status": "error", "message": f"Research failed: {e}"}

        # Stage 2: Get topic-relevant clusters
        yield {"stage": "clustering", "status": "starting", "message": "Finding relevant knowledge clusters..."}
        clusters = self.memory.get_topic_clusters(
            topic, resolution=resolution,
            min_cluster_size=min_cluster_size,
            max_clusters=max_clusters
        )

        if not clusters:
            yield {"stage": "clustering", "status": "error",
                   "message": "No relevant clusters found. The knowledge graph may not have enough data on this topic."}
            return

        yield {
            "stage": "clustering", "status": "complete",
            "message": f"Found {len(clusters)} relevant clusters",
            "cluster_count": len(clusters)
        }

        # Stage 3: Summarize clusters
        yield {"stage": "summarizing", "status": "starting", "message": "Summarizing knowledge clusters..."}
        cluster_summaries = []
        for i, cluster in enumerate(clusters):
            summary = await self._summarize_cluster(cluster["nodes"], i)
            summary["relevance_score"] = cluster["score"]
            cluster_summaries.append(summary)
            yield {
                "stage": "summarizing", "status": "progress",
                "message": f"Summarized cluster {i + 1}/{len(clusters)}: {summary['title']}",
                "cluster": summary
            }

        yield {"stage": "summarizing", "status": "complete", "message": "All clusters summarized"}

        # Stage 4: Generate outline
        yield {"stage": "outline", "status": "starting", "message": "Generating article outline..."}
        try:
            outline = await self._generate_outline(topic, cluster_summaries)
        except Exception as e:
            yield {"stage": "outline", "status": "error", "message": f"Outline generation failed: {e}"}
            return

        yield {
            "stage": "outline", "status": "complete",
            "message": f"Outline created with {len(outline.get('sections', []))} sections",
            "outline": outline
        }

        # Stage 5: Generate sections
        yield {"stage": "writing", "status": "starting", "message": "Writing article sections..."}
        sections = []
        cluster_map = {cs["cluster_id"]: cs for cs in cluster_summaries}

        # Separate body sections from intro/conclusion
        body_sections = [s for s in outline.get("sections", []) if s.get("cluster_id")]
        intro_section = next((s for s in outline.get("sections", [])
                              if "introduction" in s.get("title", "").lower()), None)
        conclusion_section = next((s for s in outline.get("sections", [])
                                   if "conclusion" in s.get("title", "").lower()), None)

        # Generate body sections first
        body_text_parts = []
        for i, section in enumerate(body_sections):
            cluster_id = section.get("cluster_id")
            cluster_summary = cluster_map.get(cluster_id)
            if not cluster_summary:
                continue

            yield {
                "stage": "writing", "status": "progress",
                "message": f"Writing section {i + 1}/{len(body_sections)}: {section['title']}"
            }

            content = await self._generate_section(
                section["title"], section.get("description", ""),
                cluster_summary, topic, article_outline=body_sections
            )
            sections.append({
                "title": section["title"],
                "content": content,
                "cluster_id": cluster_id,
                "sources": cluster_summary.get("key_entities", []),
                "cluster_nodes": cluster_summary.get("nodes", []),
                "cluster_summary_text": cluster_summary.get("summary", ""),
                "section_description": section.get("description", "")
            })
            body_text_parts.append(f"## {section['title']}\n{content}")

        body_text = "\n\n".join(body_text_parts)

        # Stage 6: Generate intro and conclusion
        yield {"stage": "writing", "status": "progress", "message": "Writing introduction..."}
        article_title = outline.get("title", topic)
        intro_content = await self._generate_intro_conclusion(topic, article_title, body_text, "introduction")
        intro = {
            "title": intro_section.get("title", "Introduction") if intro_section else "Introduction",
            "content": intro_content,
            "cluster_id": None,
            "sources": []
        }

        yield {"stage": "writing", "status": "progress", "message": "Writing conclusion..."}
        conclusion_content = await self._generate_intro_conclusion(topic, article_title, body_text, "conclusion")
        conclusion = {
            "title": conclusion_section.get("title", "Conclusion") if conclusion_section else "Conclusion",
            "content": conclusion_content,
            "cluster_id": None,
            "sources": []
        }

        # Assemble final article as markdown
        all_sections = [intro] + sections + [conclusion]
        all_cited = []
        for s in all_sections:
            all_cited.extend(s.get("sources", []))

        # Build markdown content
        markdown_parts = [f"# {article_title}\n"]
        for s in all_sections:
            markdown_parts.append(f"## {s['title']}\n\n{s['content']}")
            if s.get("sources"):
                entities = ", ".join(s["sources"])
                markdown_parts.append(f"\n*Sources: {entities}*")
        markdown_content = "\n\n".join(markdown_parts)

        # Save as a note so it appears in the Notes tab
        yield {"stage": "saving", "status": "starting", "message": "Saving article as note..."}
        note_id = article_id
        note_path = os.path.join(MEMORY_BASE_DIR, self.workspace_id, "notes", f"{note_id}.json")
        os.makedirs(os.path.dirname(note_path), exist_ok=True)

        # Build sections_meta for evolution support
        sections_meta = [{
            "title": s["title"],
            "cluster_id": s.get("cluster_id"),
            "sources": s.get("sources", []),
            "cluster_nodes": s.get("cluster_nodes", []),
            "cluster_summary": s.get("cluster_summary_text", ""),
            "section_description": s.get("section_description", "")
        } for s in sections]  # body sections only (not intro/conclusion)

        import time
        note_data = {
            "id": note_id,
            "title": article_title,
            "content": markdown_content,
            "updated_at": time.time(),
            "type": "article",
            "topic": topic,
            "mode": mode,
            "cited_entities": list(set(all_cited)),
            "sections_meta": sections_meta
        }
        with open(note_path, 'w') as f:
            json.dump(note_data, f, indent=2)

        # Index in vector store for searchability
        try:
            self.memory.index_note(note_id, article_title, markdown_content)
        except Exception as e:
            print(f"Error indexing article note: {e}")

        yield {
            "stage": "complete", "status": "complete",
            "message": f"Article '{article_title}' saved as note! Find it in the Notes tab.",
            "note_id": note_id,
            "title": article_title
        }

    async def generate_article(self, topic: str, mode: str = "existing",
                                research_sources: list = None, **kwargs) -> dict:
        """Non-streaming wrapper — returns the final result with note_id."""
        result = None
        async for update in self.generate_article_stream(topic, mode, research_sources, **kwargs):
            if update.get("stage") == "complete":
                result = update
        return result

    # =====================================================================
    # Evolutionary Article Optimization (AlphaEvolve-inspired)
    # =====================================================================

    def _make_llm(self, temperature: float):
        """Create an LLM instance with a specific temperature."""
        cfg = llm_config.get_config()
        if cfg.provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=cfg.ollama_chat_model,
                base_url=cfg.ollama_base_url,
                temperature=temperature
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                base_url=cfg.chat_base_url,
                api_key=cfg.chat_api_key,
                model=cfg.chat_model,
                temperature=temperature
            )

    async def _llm_invoke_sem(self, semaphore: asyncio.Semaphore,
                               llm, prompt: str, timeout: float = 60.0) -> str:
        """LLM invoke with semaphore for concurrency control."""
        async with semaphore:
            response = await asyncio.wait_for(
                llm.ainvoke([HumanMessage(content=prompt)]),
                timeout=timeout
            )
            return strip_thinking(response.content)

    def _parse_note_into_genes(self, note_data: dict) -> tuple:
        """Parse an article note into SectionGene objects.
        Returns (topic, title, body_genes: list[SectionGene])."""
        topic = note_data.get("topic", "")
        title = note_data.get("title", "")
        sections_meta = note_data.get("sections_meta", [])
        content = note_data.get("content", "")

        # Split markdown by ## headers
        parts = re.split(r'\n## ', content)
        # First part is the # title, skip it
        section_texts = {}
        for part in parts[1:]:
            lines = part.split("\n", 1)
            sec_title = lines[0].strip()
            sec_content = lines[1].strip() if len(lines) > 1 else ""
            # Remove trailing *Sources: ...* line
            sec_content = re.sub(r'\n\n\*Sources:.*?\*\s*$', '', sec_content).strip()
            section_texts[sec_title] = sec_content

        # Build SectionGene list from sections_meta (body sections only)
        genes = []
        for meta in sections_meta:
            sec_title = meta["title"]
            sec_content = section_texts.get(sec_title, "")
            if not sec_content:
                # Try fuzzy match
                for k, v in section_texts.items():
                    if sec_title.lower() in k.lower() or k.lower() in sec_title.lower():
                        sec_content = v
                        break
            genes.append(SectionGene(
                title=sec_title,
                content=sec_content,
                cluster_id=meta.get("cluster_id"),
                sources=meta.get("sources", []),
                cluster_nodes=meta.get("cluster_nodes", []),
                cluster_summary=meta.get("cluster_summary", ""),
                section_description=meta.get("section_description", "")
            ))

        return topic, title, genes

    async def _generate_variant_sections(self, semaphore: asyncio.Semaphore,
                                          seed_genes: list, topic: str,
                                          temperature: float, persona: str,
                                          variant_id: str) -> ArticleGenome:
        """Generate a full variant by rewriting all sections with a different style."""
        llm = self._make_llm(temperature)
        sections = []
        for gene in seed_genes:
            context = self.memory.get_subgraph_context(gene.cluster_nodes[:60])
            cluster_info = f"\nCluster Summary: {gene.cluster_summary}\n" if gene.cluster_summary else ""
            desc_info = f"\nSection Purpose: {gene.section_description}\n" if gene.section_description else ""
            prompt = f"""You are writing a section of a long-form article about: "{topic}"

Section Title: {gene.title}{desc_info}

Knowledge Context (from knowledge graph):
{context}
{cluster_info}
Style instruction: {persona}

Instructions:
- Write a detailed, well-structured section (3-6 paragraphs).
- Ground ALL claims in the provided knowledge context. Do not fabricate information.
- Reference specific entities and relationships from the context.
- Do NOT include the section title in your output — just the body text.
- Use markdown formatting where appropriate.
"""
            content = await self._llm_invoke_sem(semaphore, llm, prompt, timeout=600.0)
            sections.append(SectionGene(
                title=gene.title,
                content=content,
                cluster_id=gene.cluster_id,
                sources=gene.sources,
                cluster_nodes=gene.cluster_nodes,
                cluster_summary=gene.cluster_summary,
                section_description=gene.section_description
            ))
        return ArticleGenome(id=variant_id, generation=0, sections=sections)

    def _get_surrounding_context(self, sections: list, index: int, max_chars: int = 500) -> str:
        """Get truncated text of neighboring sections for consistency checking."""
        parts = []
        if index > 0:
            prev = sections[index - 1]
            parts.append(f"[Previous section: {prev.title}]\n{prev.content[:max_chars]}...")
        if index < len(sections) - 1:
            nxt = sections[index + 1]
            parts.append(f"[Next section: {nxt.title}]\n{nxt.content[:max_chars]}...")
        return "\n\n".join(parts) if parts else "(No surrounding sections)"

    async def _score_section(self, semaphore: asyncio.Semaphore,
                              section: SectionGene, full_article_text: str,
                              evaluator_persona: str = None) -> dict:
        """Score a single section using LLM-as-judge with full article context."""
        context = self.memory.get_subgraph_context(section.cluster_nodes[:40])
        sources_list = ", ".join(section.sources[:10]) if section.sources else "N/A"

        persona_instruction = ""
        if evaluator_persona:
            persona_instruction = f"\nYour evaluator perspective: {evaluator_persona}. Let this perspective influence how you weigh quality — for example, prioritize rigor if scientific, narrative flow if literary, clarity if pedagogical, etc.\n"

        prompt = f"""You are an expert article evaluator.{persona_instruction} Score one specific section of an article.

=== FULL ARTICLE (for consistency/flow context) ===
{full_article_text}

=== SECTION BEING EVALUATED ===
Section Title: {section.title}
Section Content:
{section.content}

=== KNOWLEDGE CONTEXT (ground truth from knowledge graph) ===
{context}

=== KEY ENTITIES THAT SHOULD BE COVERED ===
{sources_list}

Score this specific section as an integer 0-10 on each dimension:
- grounding: Does the section accurately reflect the knowledge context? Are claims supported?
- completeness: Are key entities from the knowledge context mentioned and discussed?
- coherence: Does the section read well? Is the prose clear and well-structured?
- consistency: Does this section fit well within the full article? No contradictions, no unnecessary repetition, smooth transitions with the introduction, surrounding sections, and conclusion?
{f'- subjective: Based on your evaluator perspective ("{evaluator_persona}"), how well does this section satisfy your particular sensibilities? Score based on your persona preferences.' if evaluator_persona else ''}

Output strictly as JSON:
{{"grounding": N, "completeness": N, "coherence": N, "consistency": N, {'"subjective": N, ' if evaluator_persona else ''}"feedback": "1-2 sentences of specific actionable critique"}}
"""
        try:
            content = await self._llm_invoke_sem(semaphore, self.llm, prompt, timeout=600.0)
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            print(f"Error scoring section '{section.title}': {e}")
        defaults = {"grounding": 5, "completeness": 5, "coherence": 5, "consistency": 5,
                "feedback": "Scoring failed, using default scores."}
        if evaluator_persona:
            defaults["subjective"] = 5
        return defaults

    async def _score_article(self, semaphore: asyncio.Semaphore,
                              genome: ArticleGenome,
                              intro_text: str = "", conclusion_text: str = "",
                              evaluator_persona: str = None) -> dict:
        """Score all sections of an article in a single LLM call."""
        # Build full article text
        full_parts = []
        if intro_text:
            full_parts.append(f"## Introduction\n{intro_text}")
        for s in genome.sections:
            full_parts.append(f"## {s.title}\n{s.content}")
        if conclusion_text:
            full_parts.append(f"## Conclusion\n{conclusion_text}")
        full_article_text = "\n\n".join(full_parts)

        n = len(genome.sections)
        if n == 0:
            result = {"grounding": 0, "consistency": 0, "coherence": 0, "completeness": 0, "overall": 0}
            if evaluator_persona:
                result["subjective"] = 0
            return result

        # Build per-section knowledge context
        section_contexts = []
        for i, s in enumerate(genome.sections):
            context = self.memory.get_subgraph_context(s.cluster_nodes[:40])
            sources_list = ", ".join(s.sources[:10]) if s.sources else "N/A"
            section_contexts.append(
                f"### Section {i+1}: \"{s.title}\"\n"
                f"Knowledge context: {context}\n"
                f"Key entities: {sources_list}"
            )

        persona_instruction = ""
        if evaluator_persona:
            persona_instruction = f"\nYour evaluator perspective: {evaluator_persona}. Let this perspective influence how you weigh quality.\n"

        subjective_dim = ""
        subjective_json = ""
        if evaluator_persona:
            subjective_dim = f'\n- subjective: Based on your evaluator perspective ("{evaluator_persona}"), how well does this section satisfy your particular sensibilities?'
            subjective_json = ', "subjective": N'

        prompt = f"""You are an expert article evaluator.{persona_instruction} Score ALL sections of the following article in a single response.

=== FULL ARTICLE ===
{full_article_text}

=== PER-SECTION KNOWLEDGE CONTEXT (ground truth) ===
{chr(10).join(section_contexts)}

Score each section as an integer 0-10 on each dimension:
- grounding: Does the section accurately reflect the knowledge context? Are claims supported?
- completeness: Are key entities from the knowledge context mentioned and discussed?
- coherence: Does the section read well? Is the prose clear and well-structured?
- consistency: Does this section fit well within the full article? No contradictions, smooth transitions?{subjective_dim}

Output strictly as a JSON array with one object per section, in order:
[{{"section": "Section Title", "grounding": N, "completeness": N, "coherence": N, "consistency": N{subjective_json}, "feedback": "1-2 sentences of specific actionable critique"}}, ...]
"""
        try:
            content = await self._llm_invoke_sem(semaphore, self.llm, prompt, timeout=600.0)
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                scores_list = json.loads(match.group(0))
                # Match scores to sections by position (fallback to title matching)
                section_scores = []
                for i, section in enumerate(genome.sections):
                    if i < len(scores_list):
                        section_scores.append(scores_list[i])
                    else:
                        defaults = {"grounding": 5, "completeness": 5, "coherence": 5,
                                    "consistency": 5, "feedback": "Score missing, using defaults."}
                        if evaluator_persona:
                            defaults["subjective"] = 5
                        section_scores.append(defaults)
            else:
                raise ValueError("No JSON array found in LLM response")
        except Exception as e:
            print(f"Error scoring article '{genome.id}': {e}")
            section_scores = []
            for s in genome.sections:
                defaults = {"grounding": 5, "completeness": 5, "coherence": 5,
                            "consistency": 5, "feedback": "Scoring failed, using default scores."}
                if evaluator_persona:
                    defaults["subjective"] = 5
                section_scores.append(defaults)

        # Attach scores to sections
        for section, scores in zip(genome.sections, section_scores):
            section.scores = scores

        # Compute overall fitness (weighted average across sections)
        avg = lambda key: sum(s.get(key, 0) for s in section_scores) / n
        g, con, coh, comp = avg("grounding"), avg("consistency"), avg("coherence"), avg("completeness")

        if evaluator_persona:
            subj = avg("subjective")
            overall = 0.25 * g + 0.20 * con + 0.20 * coh + 0.15 * comp + 0.20 * subj
        else:
            subj = None
            overall = 0.30 * g + 0.25 * con + 0.25 * coh + 0.20 * comp

        result = {
            "grounding": round(g, 2),
            "consistency": round(con, 2),
            "coherence": round(coh, 2),
            "completeness": round(comp, 2),
            "overall": round(overall, 2)
        }
        if evaluator_persona:
            result["subjective"] = round(subj, 2)
        return result

    def _select_parents(self, population: list) -> tuple:
        """Elitist tournament selection. Returns (elite, [(p1,p2), ...])."""
        elite = max(population, key=lambda g: g.overall_fitness)
        parents = []
        for _ in range(len(population) - 1):
            a, b = random.sample(population, 2)
            p1 = a if a.overall_fitness >= b.overall_fitness else b
            a, b = random.sample(population, 2)
            p2 = a if a.overall_fitness >= b.overall_fitness else b
            parents.append((p1, p2))
        return elite, parents

    def _crossover(self, parent1: ArticleGenome, parent2: ArticleGenome,
                   child_id: str, generation: int) -> ArticleGenome:
        """Per-section crossover: pick the better-scoring section from each parent."""
        child_sections = []
        for i in range(len(parent1.sections)):
            s1 = parent1.sections[i]
            s2 = parent2.sections[i]
            if s1.avg_score() >= s2.avg_score():
                child_sections.append(copy.deepcopy(s1))
            else:
                child_sections.append(copy.deepcopy(s2))
        return ArticleGenome(id=child_id, generation=generation, sections=child_sections)

    async def _mutate_section(self, semaphore: asyncio.Semaphore,
                               section: SectionGene, surrounding: str,
                               topic: str, article_outline: list = None) -> str:
        """Rewrite a section using evaluator feedback."""
        # Build cluster_summary dict from SectionGene fields for graph exploration
        cluster_summary = {
            "nodes": section.cluster_nodes,
            "summary": section.cluster_summary,
            "key_entities": section.sources,
            "cluster_id": section.cluster_id,
        }

        # Use LLM-driven graph exploration for targeted context
        context = await self._explore_cluster_graph(
            section.title, section.section_description,
            cluster_summary, topic, article_outline=article_outline
        )

        feedback = section.scores.get("feedback", "No specific feedback.") if section.scores else ""
        sources_list = ", ".join(section.sources[:10]) if section.sources else "N/A"

        cluster_info = f"\nCluster Summary: {section.cluster_summary}\n" if section.cluster_summary else ""
        desc_info = f"\nSection Purpose: {section.section_description}\n" if section.section_description else ""

        prompt = f"""You are rewriting a section of an article about "{topic}" to improve it.

Current Section Title: {section.title}{desc_info}
Current Section Text:
{section.content}

Evaluator Feedback: {feedback}

Knowledge Context (gathered by exploring the knowledge graph):
{context}
{cluster_info}
Key Entities to Cover: {sources_list}

Surrounding Sections (maintain consistency with these):
{surrounding}

Instructions:
- Address the evaluator's feedback specifically.
- Improve grounding by referencing more entities and relationships from the knowledge context.
- Connect the content back to the main subject "{topic}" — this section should read as part of a coherent article.
- Maintain consistency with the surrounding sections.
- Keep the same general structure and length (3-6 paragraphs).
- Output ONLY the rewritten section text, no titles or meta-commentary.
"""
        return await self._llm_invoke_sem(semaphore, self.llm, prompt, timeout=600.0)

    async def _apply_mutations(self, semaphore: asyncio.Semaphore,
                                genome: ArticleGenome, topic: str) -> ArticleGenome:
        """Mutate low-scoring sections in a genome. Returns the mutated genome."""
        mutation_tasks = []
        mutation_indices = []

        # Build outline once for all mutations
        article_outline = [
            {"title": s.title, "description": s.section_description}
            for s in genome.sections
        ]

        for i, section in enumerate(genome.sections):
            score = section.avg_score()
            prob = max(0.1, 1.0 - (score / 10.0))
            if random.random() < prob:
                surrounding = self._get_surrounding_context(genome.sections, i)
                mutation_tasks.append(
                    self._mutate_section(semaphore, section, surrounding, topic,
                                         article_outline=article_outline)
                )
                mutation_indices.append(i)

        if mutation_tasks:
            results = await asyncio.gather(*mutation_tasks)
            for idx, new_content in zip(mutation_indices, results):
                genome.sections[idx].content = new_content
                genome.sections[idx].scores = None  # needs re-evaluation

        return genome

    async def _save_changelog_note(self, original_note_id: str, article_title: str,
                                      topic: str, seed_fitness: dict,
                                      winner: 'ArticleGenome',
                                      seed_section_texts: dict,
                                      seed_section_scores: dict,
                                      seed_intro: str, evolved_intro: str,
                                      seed_conclusion: str, evolved_conclusion: str) -> str:
        """Generate and save a changelog note comparing seed vs evolved article."""
        # Build per-section diff summary (body sections)
        section_diffs = []
        for section in winner.sections:
            old_text = seed_section_texts.get(section.title, "")
            new_text = section.content
            old_len = len(old_text.split())
            new_len = len(new_text.split())
            changed = old_text.strip() != new_text.strip()
            old_scores = seed_section_scores.get(section.title, {})
            new_scores = dict(section.scores) if section.scores else {}
            section_diffs.append({
                "title": section.title,
                "changed": changed,
                "old_words": old_len,
                "new_words": new_len,
                "old_scores": old_scores,
                "new_scores": new_scores,
                "feedback": new_scores.get("feedback", "")
            })

        # Track intro/conclusion changes
        intro_changed = seed_intro.strip() != evolved_intro.strip()
        conclusion_changed = seed_conclusion.strip() != evolved_conclusion.strip()
        body_changes = sum(1 for d in section_diffs if d["changed"])
        total_changes = body_changes + (1 if intro_changed else 0) + (1 if conclusion_changed else 0)

        # Build summary for LLM prompt
        diff_summary_parts = []
        if intro_changed:
            diff_summary_parts.append(
                f"- **Introduction** [REGENERATED]: {len(seed_intro.split())} → {len(evolved_intro.split())} words")
        else:
            diff_summary_parts.append(f"- **Introduction** [UNCHANGED]: {len(seed_intro.split())} words")

        for d in section_diffs:
            status = "MODIFIED" if d["changed"] else "UNCHANGED"
            scores_before = ""
            scores_after = ""
            if d["old_scores"]:
                scores_before = (f" Seed scores: g={d['old_scores'].get('grounding','?')}, "
                                 f"co={d['old_scores'].get('coherence','?')}, "
                                 f"cn={d['old_scores'].get('consistency','?')}, "
                                 f"cm={d['old_scores'].get('completeness','?')}")
                if "subjective" in d["old_scores"]:
                    scores_before += f", subj={d['old_scores'].get('subjective','?')}"
                scores_before += "."
            if d["new_scores"]:
                scores_after = (f" Final scores: g={d['new_scores'].get('grounding','?')}, "
                                f"co={d['new_scores'].get('coherence','?')}, "
                                f"cn={d['new_scores'].get('consistency','?')}, "
                                f"cm={d['new_scores'].get('completeness','?')}")
                if "subjective" in d["new_scores"]:
                    scores_after += f", subj={d['new_scores'].get('subjective','?')}"
                scores_after += "."
            diff_summary_parts.append(
                f"- **{d['title']}** [{status}]: {d['old_words']} → {d['new_words']} words.{scores_before}{scores_after}")

        if conclusion_changed:
            diff_summary_parts.append(
                f"- **Conclusion** [REGENERATED]: {len(seed_conclusion.split())} → {len(evolved_conclusion.split())} words")
        else:
            diff_summary_parts.append(f"- **Conclusion** [UNCHANGED]: {len(seed_conclusion.split())} words")

        seed_overall = seed_fitness.get("overall", 0) if seed_fitness else 0
        winner_overall = winner.overall_fitness

        prompt = f"""Summarize the evolution of an article titled "{article_title}" (topic: "{topic}").

Seed article fitness: {seed_overall:.1f}/10
Evolved article fitness: {winner_overall:.1f}/10

Seed fitness breakdown: {json.dumps(seed_fitness)}
Evolved fitness breakdown: {json.dumps(winner.fitness)}

Per-section changes (including intro/conclusion):
{chr(10).join(diff_summary_parts)}

Total sections changed: {total_changes} out of {len(section_diffs) + 2}

IMPORTANT: Only describe changes that ACTUALLY happened. If a section is marked UNCHANGED, do not speculate about hidden changes. Introduction and Conclusion are always regenerated at the end of evolution to match the evolved body.

Write a concise 2-4 paragraph summary covering:
1. Overall fitness change (seed → evolved)
2. Which sections were actually modified and what the score deltas show
3. If no body sections changed, note that the seed body was already strong and improvements came from regenerated intro/conclusion
4. Evaluator feedback on the final sections

Be factual. Do not invent explanations for score changes you cannot see in the data."""

        summary_text = await self._llm_invoke(prompt, timeout=60.0)

        # Build the changelog markdown
        changelog_md = f"# Evolution Changelog: {article_title}\n\n"
        changelog_md += f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
        changelog_md += f"## Fitness Overview\n\n"
        changelog_md += f"| Metric | Seed | Evolved | Delta |\n"
        changelog_md += f"|--------|------|---------|-------|\n"
        fitness_keys = ["grounding", "consistency", "coherence", "completeness"]
        if (seed_fitness and "subjective" in seed_fitness) or (winner.fitness and "subjective" in winner.fitness):
            fitness_keys.append("subjective")
        fitness_keys.append("overall")
        for key in fitness_keys:
            s_val = seed_fitness.get(key, 0) if seed_fitness else 0
            e_val = winner.fitness.get(key, 0) if winner.fitness else 0
            delta = e_val - s_val
            sign = "+" if delta > 0 else ""
            changelog_md += f"| {key.capitalize()} | {s_val:.1f} | {e_val:.1f} | {sign}{delta:.1f} |\n"

        changelog_md += f"\n## Section Changes\n\n"

        # Intro
        intro_label = "Regenerated" if intro_changed else "Unchanged"
        changelog_md += f"### Introduction ({intro_label})\n"
        changelog_md += f"- Words: {len(seed_intro.split())} → {len(evolved_intro.split())}\n\n"

        # Body sections
        for d in section_diffs:
            status = "Modified" if d["changed"] else "Unchanged"
            marker = "~" if d["changed"] else "="
            changelog_md += f"### [{marker}] {d['title']} ({status})\n"
            changelog_md += f"- Words: {d['old_words']} → {d['new_words']}\n"
            if d["changed"]:
                # Show score deltas only for actually modified sections
                section_dims = ["grounding", "coherence", "consistency", "completeness"]
                if (d["old_scores"] and "subjective" in d["old_scores"]) or (d["new_scores"] and "subjective" in d["new_scores"]):
                    section_dims.append("subjective")
                if d["old_scores"] and d["new_scores"]:
                    for dim in section_dims:
                        old_v = d["old_scores"].get(dim, "?")
                        new_v = d["new_scores"].get(dim, "?")
                        if old_v != "?" and new_v != "?":
                            delta = new_v - old_v
                            sign = "+" if delta > 0 else ""
                            changelog_md += f"  - {dim}: {old_v} → {new_v} ({sign}{delta})\n"
                elif d["new_scores"]:
                    for dim in section_dims:
                        changelog_md += f"  - {dim}: {d['new_scores'].get(dim, '?')}\n"
            else:
                changelog_md += f"- *Body unchanged — score deltas omitted (LLM-as-judge variance)*\n"
            if d["feedback"]:
                changelog_md += f"- Evaluator: *{d['feedback']}*\n"
            changelog_md += "\n"

        # Conclusion
        conclusion_label = "Regenerated" if conclusion_changed else "Unchanged"
        changelog_md += f"### Conclusion ({conclusion_label})\n"
        changelog_md += f"- Words: {len(seed_conclusion.split())} → {len(evolved_conclusion.split())}\n\n"

        changelog_md += f"## Summary\n\n{summary_text}\n"

        # Save as note
        cl_note_id = str(uuid.uuid4())
        cl_note_path = os.path.join(MEMORY_BASE_DIR, self.workspace_id, "notes", f"{cl_note_id}.json")
        os.makedirs(os.path.dirname(cl_note_path), exist_ok=True)

        cl_note_data = {
            "id": cl_note_id,
            "title": f"Changelog: {article_title}",
            "content": changelog_md,
            "updated_at": time.time(),
            "type": "changelog",
            "source_note_id": original_note_id
        }
        with open(cl_note_path, 'w') as f:
            json.dump(cl_note_data, f, indent=2)

        try:
            self.memory.index_note(cl_note_id, cl_note_data["title"], changelog_md)
        except Exception as e:
            print(f"Error indexing changelog note: {e}")

        return cl_note_id

    async def evolve_article_stream(self, note_id: str,
                                     max_generations: int = 3,
                                     convergence_threshold: float = 8.5,
                                     stagnation_limit: int = 2,
                                     evaluator_persona: str = None):
        """
        Evolutionary optimization of an existing article note.

        Reads the article, generates diverse variants, evaluates with LLM-as-judge,
        then evolves through selection, crossover, and mutation.
        """
        semaphore = asyncio.Semaphore(4)

        # Load the existing article note
        note_path = os.path.join(MEMORY_BASE_DIR, self.workspace_id, "notes", f"{note_id}.json")
        if not os.path.exists(note_path):
            yield {"stage": "error", "status": "error", "message": f"Note {note_id} not found."}
            return

        with open(note_path, 'r') as f:
            note_data = json.load(f)

        if note_data.get("type") != "article" or not note_data.get("sections_meta"):
            yield {"stage": "error", "status": "error",
                   "message": "This note is not an evolvable article (missing sections_meta)."}
            return

        topic, article_title, seed_genes = self._parse_note_into_genes(note_data)

        if not seed_genes:
            yield {"stage": "error", "status": "error",
                   "message": "Could not parse any body sections from this article."}
            return

        # Capture seed content for changelog comparison
        seed_content_snapshot = note_data.get("content", "")
        seed_section_texts = {g.title: g.content for g in seed_genes}
        # Also capture intro/conclusion from the original markdown
        seed_intro = ""
        seed_conclusion = ""
        parts = re.split(r'\n## ', seed_content_snapshot)
        for part in parts[1:]:
            lines = part.split("\n", 1)
            sec_title = lines[0].strip()
            sec_body = lines[1].strip() if len(lines) > 1 else ""
            sec_body = re.sub(r'\n\n\*Sources:.*?\*\s*$', '', sec_body).strip()
            if sec_title.lower() == "introduction":
                seed_intro = sec_body
            elif sec_title.lower() == "conclusion":
                seed_conclusion = sec_body

        yield {"stage": "evolution", "status": "starting",
               "message": f"Starting evolution of '{article_title}' ({len(seed_genes)} sections, {max_generations} max generations)"}

        # --- Generation 0: Create initial population ---
        yield {"stage": "evolution", "generation": 0, "status": "generating",
               "message": "Creating 4 article variants (1 seed + 3 diverse rewrites)..."}

        # Seed is variant 0
        seed_genome = ArticleGenome(
            id="gen0_seed", generation=0,
            sections=[copy.deepcopy(g) for g in seed_genes]
        )

        # Generate 3 diverse variants concurrently
        variant_tasks = []
        for i, (temp, persona) in enumerate(VARIANT_CONFIGS):
            variant_tasks.append(
                self._generate_variant_sections(
                    semaphore, seed_genes, topic, temp, persona, f"gen0_var{i+1}"
                )
            )
        variants = await asyncio.gather(*variant_tasks)
        population = [seed_genome] + list(variants)

        yield {"stage": "evolution", "generation": 0, "status": "generated",
               "message": f"4 variants created. Evaluating..."}

        # Evaluate all gen 0 (pass seed intro/conclusion as article framing context)
        eval_tasks = [self._score_article(semaphore, g, seed_intro, seed_conclusion, evaluator_persona) for g in population]
        fitness_results = await asyncio.gather(*eval_tasks)
        for genome, fitness in zip(population, fitness_results):
            genome.fitness = fitness

        best = max(population, key=lambda g: g.overall_fitness)
        seed_fitness = seed_genome.fitness  # capture seed fitness for changelog
        seed_section_scores = {s.title: dict(s.scores) for s in seed_genome.sections if s.scores}
        yield {
            "stage": "evolution", "generation": 0, "status": "evaluated",
            "message": f"Gen 0 best: {best.overall_fitness:.1f}/10 ({best.id})",
            "scores": [{"id": g.id, **g.fitness} for g in population],
            "best": best.overall_fitness
        }

        # --- Evolution loop ---
        stagnation_count = 0
        best_fitness = best.overall_fitness

        for gen in range(1, max_generations + 1):
            yield {"stage": "evolution", "generation": gen, "status": "evolving",
                   "message": f"Generation {gen}: selection, crossover, mutation..."}

            # Selection
            elite, parent_pairs = self._select_parents(population)

            # Crossover + mutation
            children = []
            for i, (p1, p2) in enumerate(parent_pairs):
                child = self._crossover(p1, p2, f"gen{gen}_var{i+1}", gen)
                child = await self._apply_mutations(semaphore, child, topic)
                children.append(child)

            # New population: elite (keeps fitness) + children (need evaluation)
            population = [copy.deepcopy(elite)] + children
            population[0].id = f"gen{gen}_elite"
            population[0].generation = gen

            # Evaluate children (with seed intro/conclusion as framing context)
            child_eval_tasks = [self._score_article(semaphore, c, seed_intro, seed_conclusion, evaluator_persona) for c in children]
            child_fitness = await asyncio.gather(*child_eval_tasks)
            for child, fitness in zip(children, child_fitness):
                child.fitness = fitness

            new_best = max(population, key=lambda g: g.overall_fitness)
            improved = new_best.overall_fitness > best_fitness

            yield {
                "stage": "evolution", "generation": gen, "status": "evaluated",
                "message": f"Gen {gen} best: {new_best.overall_fitness:.1f}/10 ({new_best.id})"
                           + (" [improved]" if improved else " [no improvement]"),
                "scores": [{"id": g.id, **g.fitness} for g in population],
                "best": new_best.overall_fitness,
                "improved": improved
            }

            # Convergence check
            if new_best.overall_fitness >= convergence_threshold:
                yield {"stage": "evolution", "status": "converged",
                       "message": f"Converged at generation {gen} with score {new_best.overall_fitness:.1f}/10"}
                best_fitness = new_best.overall_fitness
                best = new_best
                break

            # Stagnation check
            if improved:
                stagnation_count = 0
                best_fitness = new_best.overall_fitness
                best = new_best
            else:
                stagnation_count += 1
                if stagnation_count >= stagnation_limit:
                    yield {"stage": "evolution", "status": "stagnated",
                           "message": f"Stopped at generation {gen} (no improvement for {stagnation_limit} generations). Best: {best_fitness:.1f}/10"}
                    break

        # --- Finalize: regenerate intro/conclusion for the winner ---
        winner = max(population, key=lambda g: g.overall_fitness)
        yield {"stage": "finalizing", "status": "starting",
               "message": "Regenerating introduction and conclusion for the winning variant..."}

        body_text_parts = [f"## {s.title}\n{s.content}" for s in winner.sections]
        body_text = "\n\n".join(body_text_parts)

        intro_content = await self._generate_intro_conclusion(topic, article_title, body_text, "introduction")
        conclusion_content = await self._generate_intro_conclusion(topic, article_title, body_text, "conclusion")

        # Build final markdown
        markdown_parts = [f"# {article_title}\n"]
        markdown_parts.append(f"## Introduction\n\n{intro_content}")
        for s in winner.sections:
            markdown_parts.append(f"## {s.title}\n\n{s.content}")
            if s.sources:
                markdown_parts.append(f"\n*Sources: {', '.join(s.sources)}*")
        markdown_parts.append(f"## Conclusion\n\n{conclusion_content}")
        markdown_content = "\n\n".join(markdown_parts)

        # Update the existing note
        all_cited = []
        for s in winner.sections:
            all_cited.extend(s.sources)

        note_data["content"] = markdown_content
        note_data["updated_at"] = time.time()
        note_data["evolved"] = True
        note_data["evolution_fitness"] = winner.fitness

        with open(note_path, 'w') as f:
            json.dump(note_data, f, indent=2)

        try:
            self.memory.index_note(note_id, article_title, markdown_content)
        except Exception as e:
            print(f"Error re-indexing evolved article: {e}")

        # --- Generate changelog note (seed vs best) ---
        yield {"stage": "changelog", "status": "generating",
               "message": "Generating evolution changelog..."}

        changelog_note_id = None
        try:
            changelog_note_id = await self._save_changelog_note(
                note_id, article_title, topic,
                seed_fitness, winner, seed_section_texts,
                seed_section_scores,
                seed_intro, intro_content,
                seed_conclusion, conclusion_content
            )
        except Exception as e:
            print(f"Error generating changelog: {e}")

        yield {
            "stage": "complete", "status": "complete",
            "message": f"Article evolved! Final fitness: {winner.overall_fitness:.1f}/10",
            "note_id": note_id,
            "title": article_title,
            "fitness": winner.fitness,
            "changelog_note_id": changelog_note_id
        }
