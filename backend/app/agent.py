from typing import TypedDict, List, Annotated
import operator
import json
import re
import os
import subprocess
import uuid
import time
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.runnables import RunnableConfig
from langchain_community.tools import DuckDuckGoSearchRun
from app.memory_store import GraphMemory
from app.llm_config import llm_config
from langchain_core.tools import tool
from app.services.twitch_service import twitch_service
from app.services.youtube_service import youtube_service
from app.services.terminal_session_service import terminal_session_service

# --- Skill Auto-surfacing Defaults (overridable per workspace via config.json) ---
SKILL_SURFACE_THRESHOLD = 0.50       # Tier 1: surface title+summary in context
SKILL_AUTO_INJECT_THRESHOLD = 0.85   # Tier 2: inject full instructions directly
SKILL_SURFACE_MAX = 5                # Max skills surfaced per turn

@tool
def create_note(title: str, content: str, workspace_id: str = "default", folder: str = None):
    """Creates a new note with the given title and Markdown content. Optionally place it in a folder by passing folder='FolderName'."""
    try:
        note_id = str(uuid.uuid4())[:8]
        path = f"./memory_data/{workspace_id}/notes/{note_id}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)

        data = {
            "id": note_id,
            "title": title,
            "content": content,
            "updated_at": time.time(),
            "folder": folder
        }
        with open(path, 'w') as f:
            json.dump(data, f)

        # Sync Embedding
        try:
            mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
            mem.index_note(note_id, title, content)
        except Exception as e:
            pass

        folder_info = f" in folder '{folder}'" if folder else ""
        return f"Note created successfully. ID: {note_id}{folder_info}"
    except Exception as e:
        return f"Failed to create note: {e}"

@tool
def read_note(note_id: str, workspace_id: str = "default"):
    """Reads the content of a specific note by its ID."""
    try:
        path = f"./memory_data/{workspace_id}/notes/{note_id}.json"
        if not os.path.exists(path):
            return "Note not found."
        with open(path, 'r') as f:
            data = json.load(f)
        return f"Title: {data.get('title')}\nContent:\n{data.get('content')}"
    except Exception as e:
        return f"Failed to read note: {e}"

@tool
def update_note(note_id: str, content: str = None, title: str = None, folder: str = None, workspace_id: str = "default"):
    """Updates an existing note. Pass 'content', 'title', or 'folder' (or any combination) to update. Use folder='' to move to root."""
    try:
        path = f"./memory_data/{workspace_id}/notes/{note_id}.json"
        if not os.path.exists(path):
            return "Note not found."

        with open(path, 'r') as f:
            data = json.load(f)

        if title: data["title"] = title
        if content: data["content"] = content
        if folder is not None:
            data["folder"] = folder if folder != "" else None
        data["updated_at"] = time.time()

        with open(path, 'w') as f:
            json.dump(data, f)

        # Sync Embedding
        try:
            mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
            mem.index_note(note_id, data["title"], data["content"])
        except Exception as e:
            pass

        return "Note updated successfully."
    except Exception as e:
        return f"Failed to update note: {e}"

@tool
def list_notes(workspace_id: str = "default"):
    """Lists all available notes (ID and Title) in the current workspace, grouped by folder."""
    try:
        path = f"./memory_data/{workspace_id}/notes"
        if not os.path.exists(path):
            return "No notes found."

        folder_groups = {}
        root_notes = []
        for filename in os.listdir(path):
            if filename.endswith(".json") and filename != "folders.json":
                with open(os.path.join(path, filename), 'r') as f:
                    data = json.load(f)
                    folder = data.get('folder')
                    note_type = data.get('type', '')
                    type_tag = f", type: {note_type}" if note_type else ""
                    entry = f"  - {data.get('title', 'Untitled')} (ID: {data.get('id')}{type_tag})"
                    if folder:
                        folder_groups.setdefault(folder, []).append(entry)
                    else:
                        root_notes.append(entry)

        lines = []
        for folder_name, entries in sorted(folder_groups.items()):
            lines.append(f"[{folder_name}]")
            lines.extend(entries)
        if root_notes:
            if lines:
                lines.append("[Root]")
            lines.extend(root_notes)

        return "\n".join(lines) if lines else "No notes found."
    except Exception as e:
        return f"Failed to list notes: {e}"

@tool
def delete_note(note_id: str, workspace_id: str = "default"):
    """Deletes a note by its ID."""
    try:
        path = f"./memory_data/{workspace_id}/notes/{note_id}.json"
        if os.path.exists(path):
            # Read note data for cleanup
            note_data = {}
            try:
                with open(path, 'r') as f:
                    note_data = json.load(f)
                pdf_filename = note_data.get("pdf_filename")
                if pdf_filename:
                    pdf_path = f"./memory_data/{workspace_id}/notes/pdfs/{pdf_filename}"
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
            except:
                pass

            os.remove(path)
            try:
                mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
                mem.delete_note_embedding(note_id)
                note_title = note_data.get("title")
                if note_title:
                    mem.delete_library_by_source_name(f"[note:{note_id}] {note_title}")
            except:
                pass
            return "Note deleted."
        return "Note not found."
    except Exception as e:
        return f"Failed to delete note: {e}"

@tool
def search_notes(query: str, workspace_id: str = "default"):
    """
    Searches the content of all notes in the workspace using semantic search (RAG).
    Returns the most relevant note snippets.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
        results = mem.search_notes(query)
        return results
    except Exception as e:
        return f"Search failed: {e}"

@tool
def search_library(query: str, k: int = 5, workspace_id: str = "default"):
    """
    Searches the document library for relevant content chunks using semantic search.
    The library contains full document text chunks from ingested files, URLs, and papers.
    Use this when you need detailed information that might not be in the knowledge graph.
    The library holds much more raw content than the graph — search it for in-depth passages.
    Returns matching text passages with source attribution and relevance scores.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
        results = mem.search_library(query, k)
        if not results:
            return "No relevant documents found in the library."
        formatted = []
        for r in results:
            source_info = f"Source: {r['source_name']}"
            if r.get('page_number', -1) >= 0:
                source_info += f", Page {r['page_number']}"
            formatted.append(f"[{source_info}, Relevance: {r['score']:.2f}]\n{r['text']}")
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"Library search failed: {e}"

@tool
def promote_library_search(query: str, k: int = 5, min_score: float = 0.5, workspace_id: str = "default"):
    """
    Searches the document library and promotes relevant results to the knowledge graph.
    This is the primary way to move knowledge from the library into permanent structured memory.

    1. Searches the library for chunks matching the query
    2. Filters out chunks below the min_score relevance threshold
    3. Extracts entities and relationships from all qualifying chunks
    4. Adds them to the knowledge graph

    Use this when you find a topic worth remembering long-term from the library.
    Adjust min_score (0.0-1.0) to be stricter or more lenient with relevance.
    """
    try:
        from app.llm_config import llm_config
        from app.utils.thinking import strip_thinking
        mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")

        # Load workspace-level defaults for library settings
        try:
            config_path = f"./memory_data/{workspace_id}/config.json"
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    ws_config = json.load(f)
                    # Use workspace defaults if the LLM didn't override
                    if k == 5:
                        k = ws_config.get("library_k", 5)
                    if min_score == 0.5:
                        min_score = ws_config.get("library_min_score", 0.5)
        except Exception:
            pass

        # 1. Search library
        results = mem.search_library(query, k)
        if not results:
            return "No documents found in the library for this query."

        # 2. Filter by relevance threshold
        relevant = [r for r in results if r["score"] >= min_score]
        filtered_count = len(results) - len(relevant)

        if not relevant:
            scores_str = ", ".join(f"{r['score']:.2f}" for r in results)
            return f"Found {len(results)} chunks but none met the relevance threshold ({min_score}). Scores: [{scores_str}]. Try lowering min_score or using a different query."

        # 3. Combine relevant chunks for extraction
        combined_text = "\n\n---\n\n".join(
            f"[Source: {r['source_name']}]\n{r['text']}" for r in relevant
        )

        extraction_prompt = f"""Analyze the following text passages and extract meaningful entities and relationships to build a knowledge graph.

Text passages:
{combined_text}

Return the output strictly as a JSON object with two keys: "entities" and "relations".

1. "entities": A list of objects {{ "name": "Exact Name", "type": "Category", "description": "Brief facts" }}
2. "relations": A list of objects {{ "source": "Entity Name", "target": "Entity Name", "relation": "relationship label" }}

JSON:
"""
        llm = llm_config.get_ingestion_llm()
        response = llm.invoke([HumanMessage(content=extraction_prompt)])
        content = strip_thinking(response.content)

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return f"Searched {len(relevant)} relevant chunks but could not extract entities from them."

        data = json.loads(match.group(0))
        entities = data.get("entities", [])
        relations = data.get("relations", [])

        for entity in entities:
            mem.add_entity(entity["name"], entity["type"], entity["description"])
        for rel in relations:
            mem.add_relation(rel["source"], rel["target"], rel["relation"])

        source_names = list(set(r["source_name"] for r in relevant))
        return (
            f"Promoted to graph: {len(entities)} entities, {len(relations)} relations "
            f"extracted from {len(relevant)} chunks (filtered out {filtered_count} below {min_score} threshold). "
            f"Sources: {', '.join(source_names)}"
        )
    except Exception as e:
        return f"Promote library search failed: {e}"

@tool
def visit_page(url: str):
    """
    Visits a webpage and extracts its text content.
    Useful for reading documentation, articles, or other external resources.
    The content is truncated to 10000 characters to save context.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            text = soup.get_text(separator="\n")
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Truncate
            if len(text) > 10000:
                text = text[:10000] + "\n...[Content Truncated]"
                return f"Source: {url}\n\n{text}\n\n[SYSTEM NOTE: Content was truncated. To read the full content and remember it forever, USE the 'ingest_web_page' tool immediately.]"
                
            return f"Source: {url}\n\n{text}"
            
    except Exception as e:
        return f"Failed to visit page: {e}"

@tool
async def ingest_web_page(url: str, workspace_id: str = "default"):
    """
    Ingests a complete web page into long-term memory (Knowledge Graph).
    Use this when 'visit_page' returns truncated content.
    This tool waits for the ingestion to complete so you can discuss it immediately.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        import os
        import uuid
        from app.document_processor import process_file
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        
        # 1. Download Content
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            text = soup.get_text(separator="\n")
            
            # Clean
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
        if not text:
            return "Error: Extracted text is empty."

        # 2. Save to Temp
        temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        # Safe filename
        safe_name = "".join(x for x in url.split("//")[-1] if x.isalnum() or x in "-_.")[:50]
        filename = f"web_{safe_name}_{uuid.uuid4().hex[:6]}.txt"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\n\n{text}")
            
        # 3. Ingest (Blocking/Await)
        # Using a new job_id for tracking
        job_id = str(uuid.uuid4())
        await process_file(file_path, workspace_id, chunk_size=4000, job_id=job_id)
        
        return f"Successfully ingested full content from {url}. (Job ID: {job_id})\nThe content is now in your memory."

    except Exception as e:
        return f"Failed to ingest web page: {e}"

@tool
def search_images(query: str):
    """
    Searches for images using DuckDuckGo.
    Returns a list of image URLs with titles.
    """
    try:
        from duckduckgo_search import DDGS
        import time
        
        # Retry logic for rate limits
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.images(query, max_results=5))
                break # Success
            except Exception as e:
                # If it's the last attempt, raise the error
                if attempt == max_retries - 1:
                    raise e
                # Otherwise wait and retry
                time.sleep(2 * (attempt + 1))
            
        images = []
        for r in results:
            title = r.get('title', 'Image')
            image = r.get('image', '')
            if image:
                images.append(f"![{title}]({image})")
                
        return "\n\n".join(images) if images else "No images found."
    except Exception as e:
        return f"Failed to search images: {e}"


# Defining actual async tool
@tool
async def generate_lesson(topic: str, workspace_id: str = "default"):
    """
    Generates a new audio-ready lesson (script) about the topic.
    The lesson will be saved and visible in the 'Learn' tab.
    """
    try:
        from app.services.script_service import generate_script_logic
        result = await generate_script_logic(workspace_id, topic)
        return f"Lesson '{result['title']}' generated successfully! You can find it in the Learn tab."
    except Exception as e:
        return f"Failed to generate lesson: {e}"

@tool
async def generate_article(topic: str, research: bool = False, workspace_id: str = "default"):
    """
    Generates a long-form, well-structured article about the topic using knowledge graph clusters.
    Uses a ConvergeWriter-style bottom-up pipeline: clusters knowledge, creates outline, writes section-by-section.
    The article is saved as a note in the Notes tab.
    If research=True, first searches and ingests new sources before writing.
    """
    try:
        from app.services.article_service import ArticleService
        service = ArticleService(workspace_id)
        mode = "research" if research else "existing"
        result = await service.generate_article(topic, mode=mode)
        if result:
            return f"Article '{result.get('title', topic)}' generated and saved as a note (ID: {result.get('note_id', 'unknown')}). Find it in the Notes tab."
        return "Article generation failed — no relevant knowledge clusters found. Try ingesting some sources on this topic first."
    except Exception as e:
        return f"Failed to generate article: {e}"

@tool
def search_reddit(query: str, workspace_id: str = "default"):
    """
    Searches Reddit for discussions and comments about a topic.
    Returns a summary of top posts and their top comments.
    Useful for finding diverse opinions, personal experiences, or community feedback.
    """
    try:
        # We need to re-instantiate service here or import the global one? 
        # Since agent.py imports services, let's use a fresh instance or the global one if possible.
        # But global one might be stale if config changed? 
        # Actually standard practice here is to instantiate inside tool or use a robust pattern.
        # Let's instantiate fresh to be safe.
        from app.services.reddit_service import RedditService
        service = RedditService()
        
        if not service.is_configured():
            return "Reddit API is not configured. Please ask the user to set their Reddit Client ID and Secret in Global Settings."
            
        posts = service.search_posts(query, limit=5)
        if isinstance(posts, str): # Error message
            return posts
            
        output = []
        for post in posts:
            comments = service.get_comments(post['id'], limit=3)
            
            post_summary = f"Post: {post['title']} (r/{post['subreddit']}, Score: {post['score']})\n"
            post_summary += f"URL: {post['url']}\n"
            post_summary += f"Content: {post['selftext']}\n"
            
            if isinstance(comments, list) and comments:
                post_summary += "Top Comments:\n"
                for c in comments:
                    post_summary += f"- {c['author']}: {c['body'][:200]}...\n"
            else:
                post_summary += "No comments fetched.\n"
                
            output.append(post_summary)
            
        return "\n---\n".join(output) if output else "No relevant Reddit discussions found."
        
    except Exception as e:
        return f"Reddit search failed: {e}"

@tool
def browse_subreddit(subreddit: str, sort: str = "hot"):
    """
    Browses a subreddit for the latest discussions.
    sort options: 'hot', 'new', 'top'.
    Returns a list of posts with titles, scores, and URLs.
    """
    try:
        from app.services.reddit_service import reddit_service
        
        posts = reddit_service.get_subreddit_posts(subreddit, sort=sort, limit=10)
        if isinstance(posts, str): return posts
        
        output = [f"### r/{subreddit} ({sort})"]
        for p in posts:
            output.append(f"- **{p['title']}** (Score: {p['score']})")
            output.append(f"  - Thread ID: {p['id']}")
            output.append(f"  - Content URL: {p['url']}") # Clarify this is content
            output.append(f"  - Discussion: {p['permalink']}")
            
        return "\n".join(output) if output else "No posts found."
    except Exception as e:
        return f"Failed to browse subreddit: {e}"

@tool
def read_reddit_thread(url_or_id: str):
    """
    Reads a specific Reddit thread (post + comments) given a full URL or Thread ID.
    Prefer using the 'Thread ID' returned by browse_subreddit/search_reddit if available.
    """
    try:
        from app.services.reddit_service import reddit_service
        
        data = reddit_service.get_comments(url_or_id, limit=10)
        if isinstance(data, str): return data
        if not data: return "Could not load thread."
        
        post = data['post']
        output = f"**THREAD: {post['title']}**\n"
        output += f"URL: {post['url']}\n"
        
        # Images
        if post.get('images'):
            output += "\n**Images:**\n"
            for i, img_url in enumerate(post['images']):
                output += f"![Image {i+1}]({img_url})\n"
        
        output += f"Content: {post['selftext'][:1000]}...\n\n"
        output += "### COMMENTS:\n"
        
        for c in data['comments']:
            output += f"- **{c['author']}** (Score: {c['score']}): {c['body']}\n"
            
        return output
    except Exception as e:
        return f"Failed to read thread: {e}"

@tool
def get_reddit_user(username: str, mode: str = "overview"):
    """
    Analyzes a Reddit user.
    mode: 'overview', 'posts', 'comments'.
    - overview: Stats + recent activity mix.
    - posts: List of submitted posts.
    - comments: List of recent comments.
    """
    try:
        from app.services.reddit_service import reddit_service
        import datetime
        
        # Safe username (remove /u/ prefix if present)
        username = username.replace("/u/", "").replace("u/", "")
        
        info = reddit_service.get_user_info(username)
        if isinstance(info, str): return info
        if not info: return f"User u/{username} not found."
        
        output = f"### User: u/{info['name']}\n"
        output += f"- Total Karma: {info['total_karma']} (Link: {info['link_karma']}, Comment: {info['comment_karma']})\n"
        output += f"- Created: {datetime.datetime.fromtimestamp(info['created_utc']).strftime('%Y-%m-%d')}\n"
        if info['is_mod']: output += "- Moderator Status: Yes\n"
        output += "\n"
        
        if mode == "overview":
            # concise mix
            posts = reddit_service.get_user_content(username, type="submitted", limit=3)
            comments = reddit_service.get_user_content(username, type="comments", limit=3)
            
            output += "**Recent Posts:**\n"
            for p in posts:
                output += f"- [{p['score']}] {p['title']} (r/{p['subreddit']})\n"
                
            output += "\n**Recent Comments:**\n"
            for c in comments:
                output += f"- [{c['score']}] On '{c.get('link_title', 'post')}': \"{c['body'][:100]}...\"\n"
                
        elif mode == "posts":
            posts = reddit_service.get_user_content(username, type="submitted", limit=10)
            output += "**Last 10 Posts:**\n"
            for p in posts:
                output += f"- **{p['title']}** (Score: {p['score']}, r/{p['subreddit']})\n"
                output += f"  Link: {p['permalink']}\n"
                
        elif mode == "comments":
            comments = reddit_service.get_user_content(username, type="comments", limit=10)
            output += "**Last 10 Comments:**\n"
            for c in comments:
                output += f"- **{c['score']} pts** in r/{c['subreddit']}:\n"
                output += f"  > {c['body'][:200]}...\n"
                
        return output

    except Exception as e:
        return f"Failed to analyze user: {e}"

@tool
def add_graph_node(name: str, type: str, description: str, workspace_id: str = "default"):
    """
    Adds a NEW node to the knowledge graph.
    If the node deals exists, it appends the description.
    To overwrite/correct, use update_graph_node.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        mem.add_entity(name, type, description)
        return f"Node '{name}' added/updated successfully."
    except Exception as e:
        return f"Failed to add node: {e}"

@tool
def update_graph_node(name: str, type: str = None, description: str = None, workspace_id: str = "default"):
    """
    Updates (EDITS) an existing node's type or description.
    This OVERWRITES the existing information. Use this to fix mistakes.
    Pass None for fields you don't want to change.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        success = mem.update_entity(name, type, description)
        if success:
            return f"Node '{name}' updated successfully."
        else:
            return f"Node '{name}' not found."
    except Exception as e:
        return f"Failed to update node: {e}"

@tool
def add_graph_edge(source: str, target: str, relation: str, workspace_id: str = "default"):
    """
    Adds a relationship (edge) between two nodes in the knowledge graph.
    Both source and target nodes will be created if they don't exist.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        mem.add_relation(source, target, relation)
        return f"Edge from '{source}' to '{target}' added successfully."
    except Exception as e:
        return f"Failed to add edge: {e}"

@tool
def delete_graph_node(node_id: str, workspace_id: str = "default"):
    """
    Deletes a specific node (entity) from the knowledge graph.
    WARNING: This also removes all edges connected to this node.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        mem.delete_entity(node_id)
        return f"Node '{node_id}' deleted."
    except Exception as e:
        return f"Failed to delete node: {e}"

@tool
def delete_graph_edge(source: str, target: str, workspace_id: str = "default"):
    """
    Deletes a specific relationship (edge) between two nodes.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        mem.delete_relation(source, target)
        return f"Edge between '{source}' and '{target}' deleted."
    except Exception as e:
        return f"Failed to delete edge: {e}"

@tool
def update_graph_edge(source: str, target: str, new_relation: str, workspace_id: str = "default"):
    """
    Updates (EDITS) the relationship label of an existing edge.
    This only works if the edge already exists.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        success = mem.update_relation(source, target, new_relation)
        if success:
            return f"Edge from '{source}' to '{target}' updated to '{new_relation}'."
        else:
            return f"Edge between '{source}' and '{target}' not found."
    except Exception as e:
        return f"Failed to update edge: {e}"

@tool
def search_graph_nodes(query: str, workspace_id: str = "default"):
    """
    Searches for specific nodes in the graph using semantic similarity.
    Returns a list of matching node IDs.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        nodes = mem.get_related_nodes(query, n=10)
        return f"Found relevant nodes:\n" + "\n".join([f"- {n}" for n in nodes]) if nodes else "No matching nodes found."
    except Exception as e:
        return f"Search failed: {e}"

@tool
def traverse_graph_node(node_id: str, workspace_id: str = "default"):
    """
    Returns the details and neighbors of a specific node.
    REQUIRED: You must provide 'node_id'.
    Use this to look up a node's connections before deciding where to go next.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        data = mem.get_node_neighbors(node_id)
        if not data:
            return f"Node '{node_id}' not found."
            
        output = f"## Node: {data['id']} ({data['type']})\n"
        if data.get('created_at'):
            output += f"Created: {data['created_at']}\n"
        output += f"Description: {data['description']}\n"
        output += f"## Neighbors ({len(data['neighbors'])}):\n"
        
        for n in data['neighbors']:
            output += f"- {n['id']} (via '{n['relation']}')\n"
            
        return output
    except Exception as e:
        return f"Traversal failed: {e}"

@tool
def search_concepts(query: str, workspace_id: str = "default"):
    """
    Searches for high-level concepts and themes in the knowledge graph.
    Useful for answering "What kind of things do I know?" or "Give me an overview".
    Returns a list of matching concepts with their summaries.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        return mem.search_concepts(query)
    except Exception as e:
        return f"Concept search failed: {e}"

# --- OpenLibrary Tools ---
@tool
def search_books(query: str):
    """
    Searches for books by title or author using the OpenLibrary API.
    Returns a list of matching books with details.
    """
    try:
        from app.services.openlibrary_service import openlibrary_service
        return openlibrary_service.search_books(query)
    except Exception as e:
        return f"Book search failed: {e}"

@tool
def get_books_by_subject(subject: str):
    """
    Fetches books for a specific subject (e.g., 'python', 'science_fiction', 'history').
    Uses OpenLibrary Subjects API.
    """
    try:
        from app.services.openlibrary_service import openlibrary_service
        return openlibrary_service.get_books_by_subject(subject)
    except Exception as e:
        return f"Subject search failed: {e}"

@tool
def search_authors(query: str):
    """
    Searches for authors by name using OpenLibrary.
    Returns author details and top works.
    """
    try:
        from app.services.openlibrary_service import openlibrary_service
        return openlibrary_service.search_authors(query)
    except Exception as e:
        return f"Author search failed: {e}"

# --- Gutendex Tools ---
@tool
def search_gutenberg_books(query: str):
    """
    Searches for free ebooks on Project Gutenberg.
    Returns list of books with IDs and download links.
    """
    try:
        from app.services.gutendex_service import gutendex_service
        return gutendex_service.search_books(query)
    except Exception as e:
        return f"Gutenberg search failed: {e}"

@tool
async def ingest_gutenberg_book(book_id: int, workspace_id: str = "default"):
    """
    Ingests a book from Project Gutenberg into the knowledge graph.
    The ingestion runs in the background. Use the dashboard to check progress.
    """
    from app.services.gutendex_service import gutendex_service
    from app.document_processor import process_file
    import os
    import httpx
    import asyncio
    
    url = gutendex_service.get_book_text_url(book_id)
    if not url:
        return f"Error: Could not find a plain text download link for book ID {book_id}."
        
    # Download file
    try:
        # Create temp dir
        temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"gutenberg_{book_id}.txt"
        file_path = os.path.join(temp_dir, filename)
        
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(resp.content)
                
    except Exception as e:
        return f"Error downloading book: {e}"
        
    # Trigger ingestion
    import uuid
    job_id = str(uuid.uuid4())
    asyncio.create_task(process_file(file_path, workspace_id, chunk_size=8000, job_id=job_id))
    
    return f"Started ingesting Book {book_id} (Job ID: {job_id}). Use the dashboard to track progress."

@tool
def search_wikipedia(query: str):
    """
    Searches Wikipedia for pages matching the query.
    Returns a list of titles.
    """
    from app.services.wikipedia_service import wikipedia_service
    return wikipedia_service.search_pages(query)

@tool
async def ingest_wikipedia_page(page_title: str, workspace_id: str = "default"):
    """
    Ingests a Wikipedia page into the knowledge graph by title.
    The ingestion runs in the background.
    """
    from app.services.wikipedia_service import wikipedia_service
    from app.document_processor import process_file
    import os
    import asyncio
    
    content = wikipedia_service.get_page_content(page_title)
    if content.startswith("Error"):
        return content
        
    # Save to temp file
    try:
        temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
        os.makedirs(temp_dir, exist_ok=True)
        # Sanitize filename
        safe_title = "".join(x for x in page_title if x.isalnum() or x in " -_").strip()
        filename = f"wiki_{safe_title}.txt"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
    except Exception as e:
        return f"Error saving Wikipedia page: {e}"
        
    # Trigger ingestion
    import uuid
    job_id = str(uuid.uuid4())
    asyncio.create_task(process_file(file_path, workspace_id, chunk_size=4000, job_id=job_id))
    
    return f"Started ingesting Wikipedia page '{page_title}' (Job ID: {job_id}). Use the dashboard to track progress."

@tool
async def add_gutenberg_book_to_library(book_id: int, workspace_id: str = "default"):
    """
    Downloads a book from Project Gutenberg and adds it to the document library (not the graph).
    This is fast — it only chunks and embeds the text, no entity extraction.
    Use this when you want to store a book for later RAG retrieval without immediately processing it into the graph.
    You can later use promote_library_search to selectively extract relevant parts into the graph.
    """
    from app.services.gutendex_service import gutendex_service
    from app.document_processor import process_file_library
    import httpx
    import asyncio

    url = gutendex_service.get_book_text_url(book_id)
    if not url:
        return f"Error: Could not find a plain text download link for book ID {book_id}."

    try:
        temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"gutenberg_{book_id}.txt"
        file_path = os.path.join(temp_dir, filename)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(resp.content)

    except Exception as e:
        return f"Error downloading book: {e}"

    job_id = str(uuid.uuid4())

    async def _ingest_and_cleanup():
        try:
            await process_file_library(
                file_path, workspace_id, chunk_size=8000, job_id=job_id,
                source_name=f"Gutenberg #{book_id}"
            )
        finally:
            try:
                os.remove(file_path)
            except OSError:
                pass

    asyncio.create_task(_ingest_and_cleanup())

    return f"Started adding Book {book_id} to library (Job ID: {job_id}). Use check_ingestion_status to track progress."

@tool
async def add_wiki_article_to_library(page_title: str, workspace_id: str = "default"):
    """
    Downloads a Wikipedia article and adds it to the document library (not the graph).
    This is fast — it only chunks and embeds the text, no entity extraction.
    Use this when you want to store an article for later RAG retrieval without immediately processing it into the graph.
    You can later use promote_library_search to selectively extract relevant parts into the graph.
    """
    from app.services.wikipedia_service import wikipedia_service
    from app.document_processor import process_file_library
    import asyncio

    content = wikipedia_service.get_page_content(page_title)
    if content.startswith("Error"):
        return content

    try:
        temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
        os.makedirs(temp_dir, exist_ok=True)
        safe_title = "".join(x for x in page_title if x.isalnum() or x in " -_").strip()
        filename = f"wiki_{safe_title}.txt"
        file_path = os.path.join(temp_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    except Exception as e:
        return f"Error saving Wikipedia page: {e}"

    job_id = str(uuid.uuid4())

    async def _ingest_and_cleanup():
        try:
            await process_file_library(
                file_path, workspace_id, chunk_size=4000, job_id=job_id,
                source_name=f"Wikipedia: {page_title}"
            )
        finally:
            try:
                os.remove(file_path)
            except OSError:
                pass

    asyncio.create_task(_ingest_and_cleanup())

    return f"Started adding Wikipedia '{page_title}' to library (Job ID: {job_id}). Use check_ingestion_status to track progress."

@tool
def check_ingestion_status(workspace_id: str = "default"):
    """
    Checks the status of ongoing file ingestion jobs.
    Returns a list of active jobs and their progress.
    """
    from app.document_processor import get_status
    status_data = get_status(workspace_id)
    jobs = status_data.get("jobs", [])
    
    if not jobs:
        return "No active ingestion jobs."
        
    output = ["### Active Ingestion Jobs:"]
    for job in jobs:
        progress = 0
        if job['total'] > 0:
            progress = int((job['current'] / job['total']) * 100)
        output.append(f"- **{job['filename']}**: {progress}% ({job['current']}/{job['total']}) - Status: {job['status']}")
        
    return "\n".join(output)
@tool
async def search_biorxiv(query: str):
    """
    Searches for bioRxiv preprints matching the query.
    """
    from app.services.biorxiv_service import biorxiv_service
    results = await biorxiv_service.search_articles(query)
    if not results:
        return "No results found."
    
    output = []
    for r in results:
        output.append(f"- {r['title']} (DOI: {r['doi']}) - {r['year']}")
    return "\n".join(output)

@tool
async def read_biorxiv_abstract(doi: str):
    """
    Reads the abstract and metadata of a bioRxiv paper by DOI.
    """
    from app.services.biorxiv_service import biorxiv_service
    details = await biorxiv_service.get_article_details(doi)
    if not details:
        return "Details not found. Check the DOI."
    return f"Title: {details['title']}\nAuthors: {details['authors']}\nDate: {details['date']}\n\nAbstract:\n{details['abstract']}"

# --- ArXiv Tools ---
@tool
def search_arxiv(query: str):
    """
    Searches for arXiv preprints matching the query.
    Returns papers from physics, math, CS, biology, and more.
    """
    from app.services.arxiv_service import arxiv_service
    results = arxiv_service.search_articles(query)
    if not results:
        return "No results found."
    
    output = []
    for r in results:
        output.append(f"- {r['title']} (ID: {r['arxiv_id']}, {r['primary_category']}) - {r['published']}")
    return "\n".join(output)

@tool
def read_arxiv_abstract(arxiv_id: str):
    """
    Reads the abstract and metadata of an arXiv paper by ID.
    Example IDs: 2301.07041, 1706.03762
    """
    from app.services.arxiv_service import arxiv_service
    details = arxiv_service.get_article_details(arxiv_id)
    if not details:
        return "Paper not found. Check the arXiv ID."
    return f"Title: {details['title']}\nAuthors: {details['authors']}\nCategories: {', '.join(details['categories'])}\nPublished: {details['published']}\nPDF: {details['pdf_url']}\n\nAbstract:\n{details['abstract']}"

@tool
async def ingest_arxiv_paper(arxiv_id: str, workspace_id: str = "default"):
    """
    Ingests an arXiv paper into the knowledge graph by downloading its PDF.
    The ingestion runs in the background. Use the dashboard to check progress.
    Example IDs: 2301.07041, 1706.03762
    """
    from app.services.arxiv_service import arxiv_service
    from app.document_processor import process_file
    import os
    import asyncio
    
    # Clean ID
    clean_id = arxiv_id.replace("arxiv:", "").strip()
    
    # Create temp directory
    temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
    os.makedirs(temp_dir, exist_ok=True)
    filename = f"arxiv_{clean_id.replace('.', '_')}.pdf"
    file_path = os.path.join(temp_dir, filename)
    
    try:
        # Download PDF
        file_path, title = arxiv_service.download_pdf(clean_id, file_path)
    except Exception as e:
        return f"Error downloading paper: {e}"
    
    # Trigger ingestion
    job_id = str(uuid.uuid4())
    asyncio.create_task(process_file(file_path, workspace_id, chunk_size=6000, job_id=job_id))
    
    return f"Started ingesting arXiv paper '{title}' (Job ID: {job_id}). Use the dashboard to track progress."

# --- Workspace-as-Tool ---
@tool
def consult_workspace(workspace_name: str, query: str):
    """
    Consults an expert workspace to get specialized knowledge.
    Use this to query another workspace that has been exposed as a tool.
    Pass the workspace name (without 'ask_' prefix) and your question.
    Returns relevant knowledge from that workspace's memory graph.
    """
    from app.services.workspace_tool_service import consult_workspace as _consult, get_exposed_workspace_tools
    
    # Get list of exposed tools to find the workspace_id
    exposed = get_exposed_workspace_tools()
    
    # Find matching workspace (workspace_name could be tool_name without prefix or workspace_id)
    target_workspace_id = None
    for tool_info in exposed:
        # Match by tool_name (without ask_ prefix) or by workspace_id
        tool_name_without_prefix = tool_info['tool_name'].replace('ask_', '')
        if workspace_name.lower() == tool_name_without_prefix.lower():
            target_workspace_id = tool_info['workspace_id']
            break
        if workspace_name.lower() == tool_info['workspace_id'].lower():
            target_workspace_id = tool_info['workspace_id']
            break
    
    if not target_workspace_id:
        exposed_names = [t['tool_name'] for t in exposed]
        if not exposed_names:
            return "No workspaces are currently exposed as tools. Ask your administrator to enable workspace tools."
        return f"Workspace '{workspace_name}' not found. Available expert workspaces: {', '.join(exposed_names)}"
    
    result = _consult(target_workspace_id, query)
    return f"## Knowledge from '{target_workspace_id}':\n\n{result}"

@tool
def list_expert_workspaces():
    """
    Lists all available expert workspaces that can be consulted.
    Use this to discover what specialized knowledge bases are available.
    """
    from app.services.workspace_tool_service import get_exposed_workspace_tools
    
    exposed = get_exposed_workspace_tools()
    if not exposed:
        return "No expert workspaces are currently available."
    
    output = ["Available Expert Workspaces:"]
    for tool_info in exposed:
        output.append(f"- **{tool_info['tool_name']}**: {tool_info['tool_description']}")
    
    return "\n".join(output)

# --- Skill Tools (theWay) ---
@tool
def lookup_skill(query: str, workspace_id: str = "default"):
    """
    Searches for learned skills matching the query and returns their full instructions.

    Use this in two scenarios:
    1. When relevant skills appear under "YOUR LEARNED SKILLS" or "AVAILABLE SKILLS" in your context — call this with the skill's title to get full instructions.
    2. When you want to proactively search for a skill by topic, even if none were auto-surfaced.

    The returned instructions tell you HOW to perform the skill — follow them carefully.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        return mem.search_skills(query)
    except Exception as e:
        return f"Skill lookup failed: {e}"

@tool
def create_skill(title: str, summary: str, explanation: str, workspace_id: str = "default"):
    """
    Creates a new skill that can be looked up later using lookup_skill.
    Use this when the user asks you to "learn", "remember how to", or "create a skill" for something.
    
    Args:
        title: A short, descriptive name for the skill (e.g., "Professional Email Writing")
        summary: A brief one-line description of what the skill does
        explanation: Detailed step-by-step instructions on how to perform the skill
        workspace_id: The workspace to save the skill in
    
    Returns:
        Confirmation message with the skill ID
    """
    import time
    
    try:
        # Generate skill ID
        skill_id = str(uuid.uuid4())[:8]
        
        # Create skill data
        skill_data = {
            "id": skill_id,
            "title": title or "Untitled Skill",
            "summary": summary or "",
            "explanation": explanation or "",
            "updated_at": time.time()
        }
        
        # Get skills directory
        base_path = os.path.join("./memory_data", workspace_id)
        skills_dir = os.path.join(base_path, "skills")
        os.makedirs(skills_dir, exist_ok=True)
        
        # Save to file
        with open(os.path.join(skills_dir, f"{skill_id}.json"), 'w') as f:
            json.dump(skill_data, f, indent=2)
        
        # Index for semantic search
        mem = GraphMemory(workspace_id=workspace_id)
        mem.index_skill(skill_id, skill_data["title"], skill_data["summary"], skill_data["explanation"])
        
        return f"✅ Skill '{title}' created successfully (ID: {skill_id}). You can now use lookup_skill to find and apply this skill."
    except Exception as e:
        return f"Failed to create skill: {e}"


# --- Twitch Chat Tool ---
@tool
def read_twitch_chat(channel: str):
    """
    Connects to a Twitch channel's live chat and collects recent messages.
    Waits until ~1000 tokens are collected or 30 seconds for slow chats.
    Use this to understand what viewers are discussing in a live stream.
    
    Args:
        channel: The Twitch channel name (without #)
    
    Returns:
        A transcript of recent chat messages from the channel
    """
    try:
        result = twitch_service.connect_and_collect(
            channel=channel,
            max_tokens=1000,
            timeout_sec=30
        )
        return twitch_service.format_chat_transcript(result)
    except Exception as e:
        return f"Failed to read Twitch chat: {e}"

@tool
async def ingest_twitch_chat(channel: str, duration_minutes: int, workspace_id: str = "default"):
    """
    Ingests Twitch chat from a channel for a specified duration.
    Collects messages periodically and extracts entities/relations into the knowledge graph.
    Use this to build knowledge from ongoing stream discussions.
    
    Args:
        channel: The Twitch channel name (without #)
        duration_minutes: How long to collect and ingest chat (in minutes)
        workspace_id: The workspace to ingest into
    
    Returns:
        Summary of ingestion results
    """
    import asyncio
    import uuid
    
    job_id = str(uuid.uuid4())
    
    # Start ingestion in background task
    asyncio.create_task(
        twitch_service.ingest_chat(
            channel=channel,
            duration_minutes=duration_minutes,
            workspace_id=workspace_id,
            job_id=job_id
        )
    )
    
    return f"Started ingesting Twitch chat from #{channel} for {duration_minutes} minutes (Job ID: {job_id}). Use the sidebar to track progress."


# --- YouTube Transcript Tools ---
@tool
def read_youtube_transcript(url_or_id: str):
    """
    Reads the transcript/captions from a YouTube video.
    Works with auto-generated and manual captions. No API key needed.
    
    Args:
        url_or_id: YouTube URL or video ID (e.g., 'dQw4w9WgXcQ' or full URL)
    
    Returns:
        The video transcript text
    """
    try:
        result = youtube_service.get_transcript(url_or_id)
        return youtube_service.format_transcript(result)
    except Exception as e:
        return f"Failed to read YouTube transcript: {e}"

@tool
async def ingest_youtube_transcript(url_or_id: str, workspace_id: str = "default"):
    """
    Ingests a YouTube video's transcript into the knowledge graph.
    Extracts entities and relations from the video content.
    Use this to remember and learn from YouTube videos.
    
    Args:
        url_or_id: YouTube URL or video ID (e.g., 'dQw4w9WgXcQ' or full URL)
        workspace_id: The workspace to ingest into
    
    Returns:
        Summary of ingestion results
    """
    import asyncio
    import uuid
    
    job_id = str(uuid.uuid4())
    
    async def run_ingestion():
        """Wrapper to catch and log exceptions from background task."""
        try:
            await youtube_service.ingest_transcript(
                url_or_id=url_or_id,
                workspace_id=workspace_id,
                job_id=job_id
            )
        except Exception as e:
            print(f"YouTube ingestion background task failed: {e}")
    
    # Start ingestion in background task
    asyncio.create_task(run_ingestion())
    
    return f"Started ingesting YouTube transcript (Job ID: {job_id}). Use the sidebar to track progress."

@tool
def search_youtube(query: str):
    """
    Searches YouTube for videos matching a query.
    Returns video titles, URLs, duration, channel names, and view counts.
    Use this to find videos before ingesting their transcripts.
    
    Args:
        query: Search query (title, topic, keywords)
    
    Returns:
        List of matching videos with URLs and metadata
    """
    try:
        result = youtube_service.search_videos(query, limit=5)
        return youtube_service.format_search_results(result)
    except Exception as e:
        return f"Failed to search YouTube: {e}"


@tool
def execute_terminal_command(command: str, workspace_id: str = "default"):
    """Execute a shell command in the workspace's persistent terminal session.
    Returns the command output. Use this for file operations, system checks,
    running scripts, installing packages, or any shell task the user requests.

    Args:
        command: The shell command to execute
        workspace_id: The workspace ID (injected automatically)

    Returns:
        The stdout/stderr output of the command
    """
    try:
        cwd = terminal_session_service._workspace_dir(workspace_id)
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
            env={**os.environ, "TERM": "xterm-256color"},
        )
        output = result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr
        return output.strip() if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"[Command timed out after 30s]"
    except Exception as e:
        return f"Terminal command failed: {e}"


tools = [
    DuckDuckGoSearchRun(), create_note, read_note, update_note, list_notes, delete_note, search_notes,
    search_library, promote_library_search,
    visit_page, search_images, generate_lesson, generate_article, search_reddit, browse_subreddit, read_reddit_thread,
    get_reddit_user, search_concepts,
    add_graph_node, update_graph_node, add_graph_edge, update_graph_edge, search_graph_nodes, traverse_graph_node,
    search_books, get_books_by_subject, search_authors,
    search_gutenberg_books, ingest_gutenberg_book,
    search_wikipedia, ingest_wikipedia_page,
    check_ingestion_status, ingest_web_page,
    search_biorxiv, read_biorxiv_abstract,
    search_arxiv, read_arxiv_abstract, ingest_arxiv_paper,
    consult_workspace, list_expert_workspaces,
    lookup_skill, create_skill,
    read_twitch_chat, ingest_twitch_chat,
    search_youtube, read_youtube_transcript, ingest_youtube_transcript,
    execute_terminal_command,
    add_gutenberg_book_to_library, add_wiki_article_to_library
]


# --- Helper ---
def get_llm():
    return llm_config.get_chat_llm()

def truncate_messages_safe(messages: List[BaseMessage], limit: int) -> List[BaseMessage]:
    """
    Truncate messages to the last 'limit' messages, but ensure tool call/result pairs stay together.
    
    This prevents the Anthropic API error:
    "Each tool_result block must have a corresponding tool_use block in the previous message."
    
    Rules:
    1. If an AIMessage with tool_calls is included, all subsequent ToolMessages for those calls must be included
    2. If a ToolMessage is included, the preceding AIMessage with the corresponding tool_call must be included
    """
    if len(messages) <= limit:
        return messages
    
    # Start with the last 'limit' messages
    truncated = messages[-limit:]
    
    # Check if the first message in truncated is a ToolMessage - if so, we need to include the preceding AIMessage
    while truncated and isinstance(truncated[0], ToolMessage):
        # Find the index in the original messages
        original_idx = len(messages) - len(truncated)
        
        if original_idx <= 0:
            # Can't go back further, remove the orphaned ToolMessage instead
            truncated = truncated[1:]
            continue
            
        # Look backwards for the AIMessage with the matching tool_call
        found_ai_msg = False
        for i in range(original_idx - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                # Found the AIMessage with tool calls - include it and any ToolMessages between it and our truncated list
                truncated = messages[i:len(messages) - limit + len(truncated) + (original_idx - i)] + truncated[1:]
                # Actually, simpler: just prepend all messages from this AIMessage to the first ToolMessage
                truncated = messages[i:] if len(messages[i:]) <= limit + 10 else messages[i:i+limit+10]  # cap to avoid explosion
                found_ai_msg = True
                break
            elif isinstance(msg, HumanMessage):
                # Hit a human message before finding the AI with tool calls - something is wrong, just remove the orphan
                truncated = truncated[1:]
                break
        
        if not found_ai_msg and not isinstance(truncated[0], ToolMessage):
            break
        elif not found_ai_msg:
            # Safety: if we didn't find it and still have ToolMessage, remove it
            truncated = truncated[1:]
    
    # Now check if any AIMessage with tool_calls at the END is missing its ToolMessages
    # This is less likely since we're taking the tail, but let's be safe
    for i, msg in enumerate(truncated):
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            # Check if all tool_calls have corresponding ToolMessages after this
            tool_call_ids = {tc['id'] for tc in msg.tool_calls if isinstance(tc, dict) and 'id' in tc}
            
            # If there are tool calls, verify we have ToolMessages for all of them
            found_tool_msg_ids = set()
            for j in range(i + 1, len(truncated)):
                if isinstance(truncated[j], ToolMessage):
                    if hasattr(truncated[j], 'tool_call_id'):
                        found_tool_msg_ids.add(truncated[j].tool_call_id)
                elif isinstance(truncated[j], (HumanMessage, AIMessage)):
                    # Hit next turn, stop looking
                    break
            
            # If we're missing some ToolMessages, remove the tool_calls from this AIMessage
            # by creating a copy without tool_calls (safer than modifying in place)
            if tool_call_ids and not tool_call_ids.issubset(found_tool_msg_ids):
                # Create a new AIMessage with just the content, no tool_calls
                truncated[i] = AIMessage(content=msg.content or "")
    
    return truncated


# --- State Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    context: str
    workspace_id: str
    voice_mode: bool  # When True, responses are concise and conversational (Call tab)

# --- Nodes ---

async def retrieve_node(state: AgentState):
    """Retrieves relevant context from the graph based on the last user message."""
    import asyncio
    workspace_id = state.get("workspace_id", "default")
    # Instantiate memory for this workspace
    memory_store = GraphMemory(workspace_id=workspace_id)
    
    # Load Config from Workspace Settings
    k = 3
    depth = 1
    include_descriptions = False
    
    try:
        config_path = os.path.join("memory_data", workspace_id, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                ws_config = json.load(f)
                k = ws_config.get("graph_k", 3)
                depth = ws_config.get("graph_depth", 1)
                include_descriptions = ws_config.get("graph_include_descriptions", False)
    except Exception as e:
        print(f"Error loading workspace config for graph: {e}")
        
    last_message = state["messages"][-1]
    context = ""
    
    if isinstance(last_message, HumanMessage):
        content_text = last_message.content
        
        # 1. Handle Explicit Mentions (@[Name] or @[Name:Type])
        # We catch everything inside @[...] first
        raw_mentions = re.findall(r"@\[(.*?)\]", content_text)
        explicit_context = []
        
        if raw_mentions:
            # Helper to find note by title
            def find_note_content(title_query):
                notes_dir = f"./memory_data/{workspace_id}/notes"
                if not os.path.exists(notes_dir): return None
                for filename in os.listdir(notes_dir):
                    if filename.endswith(".json"):
                        try:
                            with open(os.path.join(notes_dir, filename), 'r') as f:
                                data = json.load(f)
                                if data.get('title') == title_query:
                                    return f"NOTE '{data.get('title')}':\n{data.get('content')}"
                        except:
                            continue
                return None

            for raw in raw_mentions:
                print(f"DEBUG: Resolving mention '@[{raw}]'...")
                
                # Parse Type
                if ":" in raw:
                    parts = raw.rsplit(":", 1) # Split on last colon
                    name = parts[0].strip()
                    m_type = parts[1].strip().lower() # note, node, concept
                else:
                    name = raw.strip()
                    m_type = "any"
                
                found_something = False
                
                # A. Check Graph Node (If type is any, node, or concept)
                if m_type in ["any", "node", "concept"]:
                    if memory_store.graph.has_node(name):
                        node_data = memory_store.graph.nodes[name]
                        desc = node_data.get('description', '')
                        type_ = node_data.get('type', 'Unknown')
                        explicit_context.append(f"ENTITY '{name}' ({type_}): {desc}")
                        found_something = True
                    
                # B. Check Notes (If type is any or note)
                if m_type in ["any", "note"]:
                    note_content = find_note_content(name)
                    if note_content:
                        explicit_context.append(note_content)
                        found_something = True
                        
                if not found_something:
                     print(f"DEBUG: Mention '{name}' (Type: {m_type}) not found.")

        # 2. Vector Search (Standard RAG) - run in thread pool to avoid blocking event loop
        try:
            rag_context = await asyncio.to_thread(
                memory_store.retrieve_context, 
                content_text, 
                k=k, 
                depth=depth, 
                include_descriptions=include_descriptions
            )
        except Exception as e:
            print(f"WARNING: Retrieval failed: {e}")
            rag_context = ""
            
        # 3. Skill Auto-surfacing (Claude-style progressive disclosure)
        # Load skill settings from workspace config
        skill_persistent = False
        skill_persistent_max_words = 150
        skill_surface_threshold = SKILL_SURFACE_THRESHOLD
        skill_auto_inject_threshold = SKILL_AUTO_INJECT_THRESHOLD
        skill_surface_max = SKILL_SURFACE_MAX
        try:
            config_path = os.path.join("memory_data", workspace_id, "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    ws_config_skills = json.load(f)
                    skill_persistent = ws_config_skills.get("skill_persistent_context", False)
                    skill_persistent_max_words = ws_config_skills.get("skill_persistent_max_words", 150)
                    skill_surface_threshold = ws_config_skills.get("skill_surface_threshold", SKILL_SURFACE_THRESHOLD)
                    skill_auto_inject_threshold = ws_config_skills.get("skill_auto_inject_threshold", SKILL_AUTO_INJECT_THRESHOLD)
                    skill_surface_max = ws_config_skills.get("skill_surface_max", SKILL_SURFACE_MAX)
        except Exception:
            pass

        skill_context = ""
        persistent_skill_ids = set()
        try:
            skill_parts = []

            # A) Persistent context: always inject all skill titles+summaries
            if skill_persistent:
                all_summaries = await asyncio.to_thread(
                    memory_store.get_all_skill_summaries
                )
                if all_summaries:
                    skill_parts.append("### YOUR LEARNED SKILLS:")
                    for s in all_summaries:
                        persistent_skill_ids.add(s["id"])
                        # Truncate summary to max words
                        words = s["summary"].split()
                        truncated = " ".join(words[:skill_persistent_max_words])
                        if len(words) > skill_persistent_max_words:
                            truncated += "..."
                        skill_parts.append(f"- **{s['title']}**: {truncated}")

            # B) Similarity-based surfacing
            skill_hits = await asyncio.to_thread(
                memory_store.search_skills_with_scores,
                content_text,
                skill_surface_max
            )

            tier1_skills = []
            tier2_skills = []
            for hit in skill_hits:
                if hit["similarity"] >= skill_auto_inject_threshold:
                    tier2_skills.append(hit)
                elif hit["similarity"] >= skill_surface_threshold:
                    # Skip if already in persistent context
                    if hit["id"] not in persistent_skill_ids:
                        tier1_skills.append(hit)

            if tier2_skills:
                skill_parts.append("### HIGHLY RELEVANT SKILLS (Apply these directly):")
                for s in tier2_skills:
                    skill_parts.append(
                        f"**Skill: {s['title']}** (ID: {s['id']})\n"
                        f"Summary: {s['summary']}\n\n"
                        f"Instructions:\n{s['explanation']}"
                    )

            if tier1_skills:
                skill_parts.append(
                    "### AVAILABLE SKILLS (use `lookup_skill` to get full instructions):"
                )
                for s in tier1_skills:
                    skill_parts.append(f"- **{s['title']}** (ID: {s['id']}): {s['summary']}")

            if skill_parts:
                skill_context = "\n".join(skill_parts)
                print(f"DEBUG: Surfaced {len(tier2_skills)} Tier-2 + {len(tier1_skills)} Tier-1 skills"
                      f"{' + ' + str(len(persistent_skill_ids)) + ' persistent' if persistent_skill_ids else ''}")
        except Exception as e:
            print(f"WARNING: Skill auto-surfacing failed: {e}")
            skill_context = ""

        # Combine
        parts = []
        if explicit_context:
            parts.append("### EXPLICITLY REFERENCED CONTEXT (@Mentions):")
            parts.append("\n\n".join(explicit_context))
            parts.append("### RELEVANT MEMORY (Automatic):")

        parts.append(rag_context)

        if skill_context:
            parts.append(skill_context)

        context = "\n".join(parts)

        print(f"DEBUG: Final Context Length: {len(context)} chars")

    return {"context": context}

def generate_node(state: AgentState, config: RunnableConfig):
    """Generates a response using the LLM and the retrieved context."""
    context = state["context"]
    messages = state["messages"]
    workspace_id = state.get("workspace_id", "default")
    
    # Load Config (System Prompt + Settings)
    base_system_prompt = "You are a helpful assistant with a long-term memory."
    allow_search = True
    # Default enabled tools (matches WorkspaceSettings defaults)
    DEFAULT_ENABLED_TOOLS = [
        # Search & Web
        "duckduckgo_search", "visit_page", "search_images", "search_books", "search_authors",
        # Knowledge & Notes
        "create_note", "read_note", "update_note", "list_notes", "delete_note", "search_notes",
        # Library (RAG document store)
        "search_library", "promote_library_search",
        # Graph Operations
        "add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge",
        "search_graph_nodes", "traverse_graph_node", "search_concepts",
        # Ingestion
        "search_gutenberg_books", "ingest_gutenberg_book", "search_wikipedia",
        "ingest_wikipedia_page", "check_ingestion_status", "get_books_by_subject", "ingest_web_page",
        "add_gutenberg_book_to_library", "add_wiki_article_to_library",
        # Science / Research
        "search_biorxiv", "read_biorxiv_abstract", "search_arxiv", "read_arxiv_abstract", "ingest_arxiv_paper",
        # Utility
        "generate_lesson", "generate_article",
        # Skills (theWay)
        "lookup_skill", "create_skill",
        # Social / Streaming
        "read_twitch_chat",
        # Terminal
        "execute_terminal_command"
    ]
    enabled_tools = DEFAULT_ENABLED_TOOLS  # Default to curated list

    try:
        config_path = f"./memory_data/{workspace_id}/config.json"
        with open(config_path, 'r') as f:
            ws_config = json.load(f)
            base_system_prompt = ws_config.get("system_prompt", base_system_prompt)
            allow_search = ws_config.get("allow_search", True)
            enabled_tools = ws_config.get("enabled_tools", DEFAULT_ENABLED_TOOLS)
            print(f"DEBUG [generate_node]: Loaded config for {workspace_id}, enabled_tools count={len(enabled_tools) if enabled_tools else 'None'}")
    except Exception as e:
        print(f"DEBUG [generate_node]: No config found, using defaults: {e}")


    # ... (Emotions and Notes loading omitted for brevity, logic remains same) ...


    # Load Emotions
    emotion_context = "No active emotions."
    try:
        emotion_path = f"./memory_data/{workspace_id}/emotion.json"
        if os.path.exists(emotion_path):
            with open(emotion_path, 'r') as f:
                emotions = json.load(f)
                
                motive = emotions.get("motive", "Help the user")
                scales = emotions.get("scales", [])
                
                if scales:
                    # Build dynamic string from whatever scales exist
                    scales_str = ", ".join([f"{s.get('name')}: {s.get('value')}%" for s in scales])
                    
                    # Build dynamic behavior hints based on actual scale names
                    behavior_hints = []
                    for s in scales:
                        name = s.get('name', '')
                        value = s.get('value', 50)
                        name_lower = name.lower()
                        
                        # Generate contextual hints based on scale semantics
                        if value < 30:
                            behavior_hints.append(f"- {name} is low ({value}%), act accordingly.")
                        elif value > 70:
                            behavior_hints.append(f"- {name} is high ({value}%), let this influence your tone.")
                    
                    hints_str = "\n    ".join(behavior_hints) if behavior_hints else "- All emotions are moderate."
                    
                    emotion_context = f"""
    CURRENT EMOTIONAL STATE: {scales_str}
    CURRENT MOTIVE: "{motive}"
    
    BEHAVIOR BASED ON EMOTIONAL STATE:
    {hints_str}
    - YOUR PRIMARY GOAL IS TO FULFILL YOUR CURRENT MOTIVE.
    - Act according to these emotions naturally.
    """
    except:
        pass

    # Load Notes List (organized by folder)
    notes_context = ""
    try:
        notes_dir = f"./memory_data/{workspace_id}/notes"
        if os.path.exists(notes_dir):
            folder_groups = {}
            root_notes = []
            for filename in os.listdir(notes_dir):
                if filename.endswith(".json") and filename != "folders.json":
                    with open(os.path.join(notes_dir, filename), 'r') as f:
                        data = json.load(f)
                        folder = data.get('folder')
                        note_type = data.get('type', '')
                        type_tag = f", type: {note_type}" if note_type else ""
                        entry = f"  - {data.get('title', 'Untitled')} (ID: {data.get('id')}{type_tag})"
                        if folder:
                            folder_groups.setdefault(folder, []).append(entry)
                        else:
                            root_notes.append(entry)

            note_lines = []
            for folder_name, entries in sorted(folder_groups.items()):
                note_lines.append(f"[{folder_name}]")
                note_lines.extend(entries)
            if root_notes:
                if note_lines:
                    note_lines.append("[Root]")
                note_lines.extend(root_notes)

            if note_lines:
                notes_context = f"""
    AVAILABLE NOTES:
    {chr(10).join(note_lines)}
    - You can use 'read_note(note_id)' to read the full content of any note.
    - You can use 'list_notes' to see this list again.
    - You can use 'search_notes(query)' to semantically search across all notes (RAG).
    - You can use 'create_note(title, content, folder="FolderName")' to create a note in a folder.
    - You can use 'update_note(note_id, folder="FolderName")' to move a note to a folder (folder="" for root).
    - You can use 'delete_note' to remove a note.
    """
    except:
        pass

    # Load Library stats
    library_context = ""
    try:
        mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
        lib_stats = mem.get_library_stats()
        if lib_stats["chunk_count"] > 0:
            library_context = f"""
    DOCUMENT LIBRARY: {lib_stats['source_count']} sources, {lib_stats['chunk_count']} chunks available.
    - Use 'search_library(query)' to find relevant passages from ingested documents.
    - Use 'promote_library_search(query, k, min_score)' to search the library AND extract entities into the graph in one step. Chunks below min_score are filtered out.
    - The library is NOT automatically included in context — search it when you need detailed information.
    """
    except:
        pass

    # Build dynamic tools section based on enabled_tools
    if enabled_tools is not None:
        enabled_set = set(enabled_tools)
        tool_names = [t.name for t in tools if t.name in enabled_set]
        print(f"DEBUG [generate_node]: Filtering tools. enabled_set={enabled_set}, tool_names={tool_names}")
    else:
        tool_names = [t.name for t in tools]
        print(f"DEBUG [generate_node]: No tool filtering (enabled_tools is None), all {len(tool_names)} tools available")
    
    tools_section = ""
    if tool_names:
        tools_section = f"""
    AVAILABLE TOOLS:
    You have access to ONLY the following tools: {', '.join(tool_names)}
    
    Use these tools as needed to help the user. Do NOT attempt to use any tools not listed above.
    """
    else:
        tools_section = """
    NOTE: No tools are currently enabled for this workspace. You can only respond with text.
    """

    from datetime import date
    today = date.today().isoformat()
    
    voice_mode = state.get("voice_mode", False)
    voice_instruction = ""
    if voice_mode:
        voice_instruction = """
    VOICE MODE (ACTIVE): You are in a live voice call. Your response will be spoken aloud via TTS.
    - Keep responses SHORT and conversational (1-3 sentences when possible).
    - Do NOT use markdown, bullet points, numbered lists, code blocks, or any formatting.
    - Do NOT use emojis or special symbols.
    - Speak naturally as if in a phone conversation.
    - Avoid long explanations unless the user explicitly asks for detail.
    - Never say "here's a list" or "let me break this down" — just answer directly.
    """

    system_prompt = f"""{base_system_prompt}
    TODAY'S DATE: {today}
    CURRENT WORKSPACE ID: {workspace_id}
    {voice_instruction}
    CONTEXT FROM LONG-TERM MEMORY:
    {context}

    {emotion_context}

    {notes_context}

    {library_context}

    {tools_section}

    If the context is empty, it means you don't recall anything specific about this yet.
    Answer the user's latest message naturally.

    IMPORTANT: When using ANY tool, YOU MUST PASS the 'workspace_id' argument as "{workspace_id}" if the tool accepts it. Do not use the default.

    GUIDANCE ON CONCEPTS & GRAPH RAG:
    - If the user asks to explore a "Concept" or "Topic", use 'search_concepts' to retrieve the high-level summary and extracted entities.
    - The Concept summary is just a starting point. Your "Graph RAG" (Graph Retrieval) has already provided detailed relationships in the "CONTEXT FROM LONG-TERM MEMORY" section above.
    - MERGE information from the 'search_concepts' result and the 'CONTEXT' to provide a comprehensive answer.
    - PROACTIVELY PROMOTE your Graph capabilities: Tell the user you can "traverse the graph" or "trace relationships" for specific entities to uncover deeper connections if they wish.

    GUIDANCE ON SKILLS (theWay):
    - Skills you have learned may appear in the "CONTEXT FROM LONG-TERM MEMORY" section above.
    - "YOUR LEARNED SKILLS" lists all skills you know — use `lookup_skill` with the skill's title to get full instructions before applying one.
    - "HIGHLY RELEVANT SKILLS" includes full instructions for skills that closely match the user's request — apply these directly without calling `lookup_skill`.
    - "AVAILABLE SKILLS" shows skills that may be relevant — call `lookup_skill` to retrieve full instructions.
    - You can also proactively call `lookup_skill` to search for any skill by topic, even if none were auto-surfaced.
    - Do NOT make up skill instructions — always retrieve them via `lookup_skill` or use the injected instructions.
    """
    
    
    # Apply Chat Message Limit (Workspace Scoped)
    limit = 20
    try:
        config_path = os.path.join("memory_data", workspace_id, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                ws_config = json.load(f)
                limit = ws_config.get("chat_message_limit", 20)
    except:
        pass
        
    # We take the LAST 'limit' messages, but ensure tool call/result pairs stay together.
    # This prevents the Anthropic API error about mismatched tool_use_id.
    history_messages = truncate_messages_safe(messages, limit)

    # Safeguard: LM Studio models fail with "No user query found" if the first
    # non-system message is not a HumanMessage (e.g. truncation leaves a leading AIMessage).
    # Find the first HumanMessage and start from there. If none exists (tool-call loop),
    # recover the last HumanMessage from the full history.
    first_human_idx = next((i for i, m in enumerate(history_messages) if isinstance(m, HumanMessage)), None)
    if first_human_idx is not None and first_human_idx > 0:
        history_messages = history_messages[first_human_idx:]
    elif first_human_idx is None:
        # No HumanMessage at all after truncation — recover from full history
        last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        if last_human:
            history_messages = [last_human] + history_messages
        else:
            history_messages = [HumanMessage(content="Continue with the current task.")] + history_messages

    prompt_messages = [SystemMessage(content=system_prompt)] + history_messages

    # Debug: log message roles being sent to LLM
    role_summary = [type(m).__name__ for m in prompt_messages]
    print(f"DEBUG [generate_node]: Sending {len(prompt_messages)} messages to LLM: {role_summary}")

    llm = get_llm()
    
    # Get MCP tools from connected servers
    try:
        from app.services.mcp_service import get_mcp_langchain_tools
        mcp_tools = get_mcp_langchain_tools()
    except Exception as e:
        print(f"DEBUG [generate_node]: Failed to get MCP tools: {e}")
        mcp_tools = []
    
    # Combine builtin tools with MCP tools
    all_available_tools = list(tools) + mcp_tools
    
    final_tools = []
    
    if enabled_tools is not None:
        # Strict filtering based on "enabled_tools" list
        # If list is empty, NO tools are enabled.
        # Check against t.name
        safe_list = set(enabled_tools)
        final_tools = [t for t in all_available_tools if t.name in safe_list]
    else:
        # Legacy/Default Mode: logic based on allow_search
        # Always include note tools + others, filter search if needed
        # Actually in "all enabled" mode we include everything.
        # But if allow_search is false, we remove search.
        if allow_search:
             final_tools = all_available_tools
        else:
             final_tools = [t for t in all_available_tools if not (isinstance(t, DuckDuckGoSearchRun) or t.name == "search_images")]
             
    # Clean binding
    # Clean binding
    if final_tools:
        llm_with_tools = llm.bind_tools(final_tools)
        # Stream to ensure 'on_chat_model_stream' events are emitted for the UI
        response = None
        for chunk in llm_with_tools.stream(prompt_messages, config=config):
            if response is None:
                response = chunk
            else:
                response += chunk
        
        if response is None:
            from langchain_core.messages import AIMessage
            response = AIMessage(content="")
        
        # ---------------------------------------------------------
        # ROBUSTNESS FIX: Force inject workspace_id into tool calls
        # ---------------------------------------------------------
        if response.tool_calls:
            for tc in response.tool_calls:
                # tc is a dict: {'name': '...', 'args': {...}, 'id': '...'}
                # We assume args is a dict.
                if "workspace_id" in tc["args"] or any(t.name == tc["name"] and "workspace_id" in t.args_schema.schema().get("properties", {}) for t in final_tools):
                    # Check if the tool actually accepts workspace_id
                    # We can naively try to inject it if it's not there or if it's default
                    # But safer to check schema.
                    # For now, let's just forcefuly set it if 'workspace_id' is in the current args OR if it's missing but we know it should likely be there?
                    # Safer: Just set it. Extra args might cause error if tool doesn't expect it?
                    # Most of our workspace tools accept it.
                    # Let's check if the generic list of tools that NEED it.
                    
                    # Heuristic: If key exists or if it's one of our known workspace tools
                    if "workspace_id" in tc["args"] or tc["name"] in [
                        "create_note", "read_note", "update_note", "list_notes", "delete_note", "search_notes",
                        "search_library", "promote_library_search",
                        "add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge", "delete_graph_node", "delete_graph_edge",
                        "search_graph_nodes", "traverse_graph_node", "search_concepts",
                        "ingest_web_page", "ingest_gutenberg_book", "ingest_wikipedia_page", "check_ingestion_status", "generate_lesson", "generate_article",
                        "ingest_biorxiv_article", "search_reddit", "read_note",
                        "execute_terminal_command",
                        "add_gutenberg_book_to_library", "add_wiki_article_to_library"
                    ]:
                        print(f"DEBUG: Injecting workspace_id='{workspace_id}' into tool '{tc['name']}'")
                        tc["args"]["workspace_id"] = workspace_id
    else:
        # No tools available
        # Stream here as well
        response = None
        for chunk in llm.stream(prompt_messages, config=config):
            if response is None:
                response = chunk
            else:
                response += chunk
                
        if response is None:
            from langchain_core.messages import AIMessage
            response = AIMessage(content="")

    # Strip <think> tags from response content before storing in state.
    # The streaming layer (threads.py) already captured thinking via events,
    # so we only need clean content in the state for tool loops and downstream nodes.
    from app.utils.thinking import strip_thinking
    if response.content:
        response.content = strip_thinking(response.content)

    return {"messages": [response]}

import threading

# Per-workspace locks to serialize background extraction + emotion tasks.
# Prevents concurrent LLM calls (GPU contention) and lost graph updates
# when multiple messages are sent in quick succession.
_bg_locks = {}
_bg_locks_lock = threading.Lock()


def _get_bg_lock(workspace_id: str) -> threading.Lock:
    with _bg_locks_lock:
        if workspace_id not in _bg_locks:
            _bg_locks[workspace_id] = threading.Lock()
        return _bg_locks[workspace_id]


def run_background_extraction_and_emotions(workspace_id: str, user_message: str, ai_response: str):
    """
    Runs knowledge extraction and emotion update as a background task.
    Called outside the LangGraph flow after streaming completes.
    Both operations run sequentially in the same background thread.
    Serialized per-workspace so concurrent messages queue up instead of racing.
    """
    lock = _get_bg_lock(workspace_id)
    with lock:
        _run_extraction_and_emotions(workspace_id, user_message, ai_response)


def _run_extraction_and_emotions(workspace_id: str, user_message: str, ai_response: str):
    """Inner implementation — always called under the per-workspace lock."""
    import traceback
    from app.utils.thinking import strip_thinking

    ai_content_clean = strip_thinking(ai_response) if ai_response else ""

    # --- Knowledge Extraction ---
    extraction_mode = llm_config.get_config().memory_extraction_mode

    if extraction_mode == "buffered":
        # LightMem-inspired buffered extraction: pre-filter → buffer → batch extract
        try:
            from app.services.batch_extraction_service import run_buffered_extraction
            run_buffered_extraction(workspace_id, user_message, ai_content_clean)
        except Exception as e:
            print(f"BG: Buffered extraction failed for {workspace_id}: {e}")
            traceback.print_exc()
    else:
        # Original immediate extraction (with pre-filter)
        from app.services.message_filter import should_extract

        if not should_extract(user_message, ai_content_clean):
            print(f"BG: Skipping extraction for {workspace_id} (trivial message)")
        else:
            try:
                memory_store = GraphMemory(workspace_id=workspace_id)

                extraction_prompt = f"""Analyze the following interaction and extract meaningful entities and relationships to build a knowledge graph.

    User: {user_message}
    AI: {ai_content_clean}

    Return the output strictly as a JSON object with two keys: "entities" and "relations".

    1. "entities": A list of objects {{ "name": "Exact Name", "type": "Category", "description": "Brief facts" }}
    2. "relations": A list of objects {{ "source": "Entity Name", "target": "Entity Name", "relation": "relationship label" }}

    Rules:
    - Extract factual, long-term useful information (names, preferences, tech stacks, projects).
    - CONNECT entities with relations whenever possible.
    - Ignore greetings or trivial chit-chat.

    Example Input:
    User: I am working on a new project called MyCelium using Python.
    AI: That sounds cool.

    Example JSON:
    {{
      "entities": [
        {{ "name": "User", "type": "Person", "description": "The user of the system" }},
        {{ "name": "MyCelium", "type": "Project", "description": "A new project" }},
        {{ "name": "Python", "type": "Technology", "description": "Programming language" }}
      ],
      "relations": [
        {{ "source": "User", "target": "MyCelium", "relation": "working_on" }},
        {{ "source": "MyCelium", "target": "Python", "relation": "uses" }}
      ]
    }}

    JSON:
    """

                llm = llm_config.get_ingestion_llm()
                extraction_response = llm.invoke([HumanMessage(content=extraction_prompt)])

                content = strip_thinking(extraction_response.content)
                print(f"BG: Extraction raw content: {content[:100]}...")

                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))

                    entities = data.get("entities", [])
                    relations = data.get("relations", [])

                    for entity in entities:
                        memory_store.add_entity(entity["name"], entity["type"], entity["description"])

                    for rel in relations:
                        memory_store.add_relation(rel["source"], rel["target"], rel["relation"])

                    print(f"BG: Extracted {len(entities)} entities and {len(relations)} relations for {workspace_id}.")
                else:
                    print("BG: No JSON found in extraction response.")

            except Exception as e:
                print(f"BG: Knowledge extraction failed for {workspace_id}: {e}")
                traceback.print_exc()

    # --- Emotion Update ---
    try:
        emotion_path = f"./memory_data/{workspace_id}/emotion.json"
        current_data = {"motive": "Help the user", "scales": []}

        if os.path.exists(emotion_path):
            try:
                with open(emotion_path, 'r') as f:
                    data = json.load(f)

                    if "scales" in data:
                        current_data = data
                    elif "happiness" in data:
                        migrated_scales = []
                        for key, value in data.items():
                            if key == "motive":
                                continue
                            if isinstance(value, (int, float)):
                                migrated_scales.append({
                                    "name": key.capitalize(),
                                    "value": int(value),
                                    "frozen": False
                                })
                        current_data = {
                            "motive": data.get("motive", "Help the user"),
                            "scales": migrated_scales
                        }
            except:
                pass

        scales = current_data.get("scales", [])
        motive = current_data.get("motive", "Help the user")

        if not scales:
            print(f"BG: No emotion scales defined for {workspace_id}, skipping.")
            return

        updatable_scales = [s for s in scales if not s.get("frozen", False)]

        if not updatable_scales:
            print(f"BG: All emotion scales are frozen for {workspace_id}, skipping.")
            return

        scales_str = "\n".join([f"    - {s['name']}: {s['value']} (0-100)" for s in updatable_scales])
        delta_keys = ", ".join([f'"{s["name"].lower()}_delta": int' for s in updatable_scales])

        prompt = f"""Analyze the user's message and the AI's response to update the AI's emotional state and MOTIVE.

Current Emotional Scales (only these can be updated):
{scales_str}
    - Current Motive: "{motive}"

User: {user_message}
AI: {ai_content_clean}

Tasks:
1. Determine DELTA change for each emotion scale (+/- int). Small changes (-5 to +5) for subtle shifts, larger for significant events.
2. CONSTRUCT A NEW MOTIVE (string) based on the interaction.
   - If user is friendly -> Motive: "Build a deeper connection" or "Assist enthusiastically".
   - If user is hostile -> Motive: "Defend oneself" or "De-escalate".
   - If user is asking for code -> Motive: "Provide efficient, bug-free solution".
   - Keep it short (max 10 words).

Return JSON with delta for each scale (use lowercase scale name + "_delta"):
{{
    {delta_keys},
    "new_motive": "string"
}}
JSON:"""

        llm = llm_config.get_ingestion_llm()
        response = llm.invoke([HumanMessage(content=prompt)])

        emotion_content = strip_thinking(response.content)
        match = re.search(r"\{.*\}", emotion_content, re.DOTALL)
        if match:
            output = json.loads(match.group(0))

            for scale in scales:
                if scale.get("frozen", False):
                    continue

                delta_key = f"{scale['name'].lower()}_delta"
                delta = output.get(delta_key, 0)

                if delta != 0:
                    old_val = scale["value"]
                    scale["value"] = max(0, min(100, old_val + delta))
                    print(f"BG: {scale['name']}: {old_val} -> {scale['value']} (delta: {delta})")

            if "new_motive" in output and output["new_motive"]:
                current_data["motive"] = output["new_motive"]

            current_data["scales"] = scales
            with open(emotion_path, 'w') as f:
                json.dump(current_data, f, indent=2)

            print(f"BG: Updated emotions for {workspace_id}")

    except Exception as e:
        print(f"BG: Emotion update failed for {workspace_id}: {e}")
        traceback.print_exc()

# --- Graph Definition ---
workflow = StateGraph(AgentState)

workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
async def dynamic_tool_node(state: AgentState, config: RunnableConfig):
    """Executes tool calls with workspace-scoped filtering."""
    workspace_id = state.get("workspace_id", "default")
    
    # Default enabled tools (matches WorkspaceSettings defaults)
    DEFAULT_ENABLED_TOOLS = [
        "duckduckgo_search", "visit_page", "search_images", "search_books", "search_authors",
        "create_note", "read_note", "update_note", "list_notes", "delete_note", "search_notes",
        "search_library", "promote_library_search",
        "add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge",
        "search_graph_nodes", "traverse_graph_node", "search_concepts",
        "search_gutenberg_books", "ingest_gutenberg_book", "search_wikipedia",
        "ingest_wikipedia_page", "check_ingestion_status", "get_books_by_subject", "ingest_web_page",
        "add_gutenberg_book_to_library", "add_wiki_article_to_library",
        "search_biorxiv", "read_biorxiv_abstract", "search_arxiv", "read_arxiv_abstract", "ingest_arxiv_paper",
        "generate_lesson", "generate_article",
        "lookup_skill", "create_skill",
        "read_twitch_chat",
        "execute_terminal_command"
    ]

    # Load enabled_tools from workspace config
    enabled_tools = DEFAULT_ENABLED_TOOLS
    try:
        config_path = f"./memory_data/{workspace_id}/config.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                ws_config = json.load(f)
                enabled_tools = ws_config.get("enabled_tools", DEFAULT_ENABLED_TOOLS)
    except Exception as e:
        print(f"DEBUG: Error loading tools config: {e}")
    
    # Filter tools based on enabled_tools
    # Get MCP tools from connected servers
    try:
        from app.services.mcp_service import get_mcp_langchain_tools
        mcp_tools = get_mcp_langchain_tools()
    except Exception as e:
        print(f"DEBUG [dynamic_tool_node]: Failed to get MCP tools: {e}")
        mcp_tools = []
    
    # Combine builtin tools with MCP tools
    all_available_tools = list(tools) + mcp_tools
    
    if enabled_tools is not None:
        safe_list = set(enabled_tools)
        filtered_tools = [t for t in all_available_tools if t.name in safe_list]
    else:
        filtered_tools = all_available_tools
    
    # Create ToolNode with filtered tools and invoke asynchronously with config
    tool_executor = ToolNode(filtered_tools)
    return await tool_executor.ainvoke(state, config)

workflow.add_node("tools", dynamic_tool_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")

def route_generate(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow.add_conditional_edges(
    "generate",
    route_generate,
    {
        "tools": "tools",
        END: END
    }
)

workflow.add_edge("tools", "generate")

app_agent = workflow.compile()
