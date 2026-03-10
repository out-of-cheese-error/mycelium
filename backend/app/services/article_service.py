import os
import json
import uuid
import re
import asyncio
from datetime import datetime
from langchain_core.messages import HumanMessage
from app.memory_store import GraphMemory, MEMORY_BASE_DIR
from app.llm_config import llm_config
from app.utils.thinking import strip_thinking


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

    async def _generate_section(self, section_title: str, section_desc: str,
                                 cluster_summary: dict, topic: str) -> str:
        """Generate content for a single article section grounded in its cluster."""
        # Get full context from the cluster's nodes
        context_nodes = cluster_summary["nodes"][:60]
        context = self.memory.get_subgraph_context(context_nodes)

        prompt = f"""You are writing a section of a long-form article about: "{topic}"

Section Title: {section_title}
Section Purpose: {section_desc}

Knowledge Context (from knowledge graph):
{context}

Cluster Summary: {cluster_summary['summary']}

Instructions:
- Write a detailed, well-structured section (3-6 paragraphs).
- Ground ALL claims in the provided knowledge context. Do not fabricate information.
- Reference specific entities and relationships from the context.
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
                cluster_summary, topic
            )
            sections.append({
                "title": section["title"],
                "content": content,
                "cluster_id": cluster_id,
                "sources": cluster_summary.get("key_entities", [])
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

        import time
        note_data = {
            "id": note_id,
            "title": article_title,
            "content": markdown_content,
            "updated_at": time.time(),
            "type": "article",
            "topic": topic,
            "mode": mode,
            "cited_entities": list(set(all_cited))
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
