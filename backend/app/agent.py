from typing import TypedDict, List, Annotated
import operator
import json
import re
import os
import uuid
import time
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.runnables import RunnableConfig
from langchain_community.tools import DuckDuckGoSearchRun
from app.memory_store import GraphMemory
from app.llm_config import llm_config
from langchain_core.tools import tool

@tool
def create_note(title: str, content: str, workspace_id: str = "default"):
    """Creates a new note with the given title and Markdown content."""
    try:
        note_id = str(uuid.uuid4())[:8]
        path = f"./memory_data/{workspace_id}/notes/{note_id}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        data = {
            "id": note_id,
            "title": title,
            "content": content,
            "updated_at": time.time()
        }
        with open(path, 'w') as f:
            json.dump(data, f)
            
        # Sync Embedding
        try:
            mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
            mem.index_note(note_id, title, content)
        except Exception as e:
            pass # Fail silently for agent tools to avoid breaking flow? Or return warning?
            
        return f"Note created successfully. ID: {note_id}"
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
def update_note(note_id: str, content: str = None, title: str = None, workspace_id: str = "default"):
    """Updates an existing note. Pass 'content' or 'title' (or both) to update."""
    try:
        path = f"./memory_data/{workspace_id}/notes/{note_id}.json"
        if not os.path.exists(path):
            return "Note not found."
            
        with open(path, 'r') as f:
            data = json.load(f)
            
        if title: data["title"] = title
        if content: data["content"] = content
        data["updated_at"] = time.time()
        
        with open(path, 'w') as f:
            json.dump(data, f)
            
        # Sync Embedding
        try:
            mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
            # We need to make sure we index the FULL content, so use data['title'] and data['content']
            mem.index_note(note_id, data["title"], data["content"])
        except Exception as e:
            pass
            
        return "Note updated successfully."
    except Exception as e:
        return f"Failed to update note: {e}"

@tool
def list_notes(workspace_id: str = "default"):
    """Lists all available notes (ID and Title) in the current workspace."""
    try:
        path = f"./memory_data/{workspace_id}/notes"
        if not os.path.exists(path):
            return "No notes found."
            
        notes = []
        for filename in os.listdir(path):
            if filename.endswith(".json"):
                with open(os.path.join(path, filename), 'r') as f:
                    data = json.load(f)
                    notes.append(f"- {data.get('title', 'Untitled')} (ID: {data.get('id')})")
        return "\n".join(notes) if notes else "No notes found."
    except Exception as e:
        return f"Failed to list notes: {e}"

@tool
def delete_note(note_id: str, workspace_id: str = "default"):
    """Deletes a note by its ID."""
    try:
        path = f"./memory_data/{workspace_id}/notes/{note_id}.json"
        if os.path.exists(path):
            os.remove(path)
            # Try to remove embedding, but we can't easily access GraphMemory here without base_dir context?
            # Ideally the agent calls the API, but here we are acting DIRECTLY.
            # We should probably replicate the sync logic or use the API endpoint logic (but we are in backend).
            # Let's instantiate GraphMemory.
            try:
                mem = GraphMemory(workspace_id=workspace_id, base_dir="./memory_data")
                mem.delete_note_embedding(note_id)
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
    Use this when the user asks you to apply a skill (e.g., "use your email writing skill to...").
    The returned instructions tell you HOW to perform the skill - follow them carefully.
    """
    try:
        mem = GraphMemory(workspace_id=workspace_id)
        return mem.search_skills(query)
    except Exception as e:
        return f"Skill lookup failed: {e}"


tools = [
    DuckDuckGoSearchRun(), create_note, read_note, update_note, list_notes, delete_note, search_notes, 
    visit_page, search_images, generate_lesson, search_reddit, browse_subreddit, read_reddit_thread, 
    get_reddit_user, search_concepts,
    add_graph_node, update_graph_node, add_graph_edge, update_graph_edge, search_graph_nodes, traverse_graph_node,
    search_books, get_books_by_subject, search_authors,
    search_gutenberg_books, ingest_gutenberg_book,
    search_wikipedia, ingest_wikipedia_page,
    check_ingestion_status, ingest_web_page,
    search_biorxiv, read_biorxiv_abstract,
    search_arxiv, read_arxiv_abstract, ingest_arxiv_paper,
    consult_workspace, list_expert_workspaces,
    lookup_skill
]


# --- Helper ---
def get_llm():
    return llm_config.get_chat_llm()

# --- State Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    context: str
    workspace_id: str

# --- Nodes ---

def retrieve_node(state: AgentState):
    """Retrieves relevant context from the graph based on the last user message."""
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

        # 2. Vector Search (Standard RAG)
        try:
            rag_context = memory_store.retrieve_context(content_text, k=k, depth=depth, include_descriptions=include_descriptions)
        except Exception as e:
            print(f"WARNING: Retrieval failed: {e}")
            rag_context = ""
            
        # Combine
        parts = []
        if explicit_context:
            parts.append("### EXPLICITLY REFERENCED CONTEXT (@Mentions):")
            parts.append("\n\n".join(explicit_context))
            parts.append("### RELEVANT MEMORY (Automatic):")
            
        parts.append(rag_context)
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
        # Graph Operations
        "add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge", 
        "search_graph_nodes", "traverse_graph_node", "search_concepts",
        # Ingestion
        "search_gutenberg_books", "ingest_gutenberg_book", "search_wikipedia", 
        "ingest_wikipedia_page", "check_ingestion_status", "get_books_by_subject", "ingest_web_page",
        # Science / Research
        "search_biorxiv", "read_biorxiv_abstract", "search_arxiv", "read_arxiv_abstract", "ingest_arxiv_paper",
        # Utility
        "generate_lesson"
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

    # Load Notes List
    notes_context = ""
    try:
        notes_dir = f"./memory_data/{workspace_id}/notes"
        if os.path.exists(notes_dir):
            note_headers = []
            for filename in os.listdir(notes_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(notes_dir, filename), 'r') as f:
                        data = json.load(f)
                        note_headers.append(f"- {data.get('title', 'Untitled')} (ID: {data.get('id')})")
            
            if note_headers:
                notes_context = f"""
    AVAILABLE NOTES:
    {chr(10).join(note_headers)}
    - You can use 'read_note(note_id)' to read the full content of any note.
    - You can use 'list_notes' to see this list again.
    - You can use 'search_notes(query)' to semantically search across all notes (RAG).
    - You can use 'create_note', 'update_note', or 'delete_note' to manage them.
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

    system_prompt = f"""{base_system_prompt}
    CURRENT WORKSPACE ID: {workspace_id}

    CONTEXT FROM LONG-TERM MEMORY:
    {context}
    
    {emotion_context}
    
    {notes_context}

    {tools_section}
    
    If the context is empty, it means you don't recall anything specific about this yet.
    Answer the user's latest message naturally.
    
    IMPORTANT: When using ANY tool, YOU MUST PASS the 'workspace_id' argument as "{workspace_id}" if the tool accepts it. Do not use the default.
    
    GUIDANCE ON CONCEPTS & GRAPH RAG:
    - If the user asks to explore a "Concept" or "Topic", use 'search_concepts' to retrieve the high-level summary and extracted entities.
    - The Concept summary is just a starting point. Your "Graph RAG" (Graph Retrieval) has already provided detailed relationships in the "CONTEXT FROM LONG-TERM MEMORY" section above.
    - MERGE information from the 'search_concepts' result and the 'CONTEXT' to provide a comprehensive answer.
    - PROACTIVELY PROMOTE your Graph capabilities: Tell the user you can "traverse the graph" or "trace relationships" for specific entities to uncover deeper connections if they wish.
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
        
    # We take the LAST 'limit' messages.
    # Note: 'messages' in state contains only Human/AI messages from history, 
    # SystemMessage is injected below.
    history_messages = messages
    if len(history_messages) > limit:
        history_messages = history_messages[-limit:]
        
    prompt_messages = [SystemMessage(content=system_prompt)] + history_messages
    
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
                        "add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge", "delete_graph_node", "delete_graph_edge",
                        "search_graph_nodes", "traverse_graph_node", "search_concepts",
                        "ingest_web_page", "ingest_gutenberg_book", "ingest_wikipedia_page", "check_ingestion_status", "generate_lesson",
                        "ingest_biorxiv_article", "search_reddit", "read_note"
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

    return {"messages": [response]}

    return {"messages": [response]}

def extract_knowledge_node(state: AgentState):
    """Analyzes the latest interaction to extract new entities and relations."""
    workspace_id = state.get("workspace_id", "default")
    memory_store = GraphMemory(workspace_id=workspace_id)

    # We look at the last Human message and the last AI message
    messages = state["messages"]
    if len(messages) < 2:
        return {}
    
    last_human = next((m for m in reversed(messages[:-1]) if isinstance(m, HumanMessage)), None)
    last_ai = messages[-1]
    
    if not last_human:
        return {}

    extraction_prompt = f"""Analyze the following interaction and extract meaningful entities and relationships to build a knowledge graph.
    
    User: {last_human.content}
    AI: {last_ai.content}
    
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
    
    try:
        llm = get_llm()
        extraction_response = llm.invoke([HumanMessage(content=extraction_prompt)])

        content = extraction_response.content
        print(f"DEBUG: Extraction raw content: {content[:100]}...") # Log start of content
        
        # Basic cleanup to find JSON if wrapped in markdown
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
            
            entities = data.get("entities", [])
            relations = data.get("relations", [])
            
            if not entities and not relations:
                print("DEBUG: LLM found no entities/relations.")
            
            # Update Memory
            for entity in entities:
                memory_store.add_entity(entity["name"], entity["type"], entity["description"])
            
            for rel in relations:
                memory_store.add_relation(rel["source"], rel["target"], rel["relation"])
                
            print(f"DEBUG: Extracted {len(entities)} entities and {len(relations)} relations for workspace {workspace_id}.")
        else:
            print("DEBUG: No JSON found in extraction response.")
            
    except Exception as e:
        print(f"DEBUG: Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        
    return {}

def update_emotions_node(state: AgentState):
    """Analyzes the interaction to update the bot's emotional state dynamically."""
    workspace_id = state.get("workspace_id", "default")
    messages = state["messages"]
    if len(messages) < 2:
        return {}
    
    last_human = next((m for m in reversed(messages[:-1]) if isinstance(m, HumanMessage)), None)
    last_ai = messages[-1]
    
    if not last_human:
        return {}

    # Load current emotions (new dynamic format)
    emotion_path = f"./memory_data/{workspace_id}/emotion.json"
    current_data = {"motive": "Help the user", "scales": []}
    
    if os.path.exists(emotion_path):
        try:
            with open(emotion_path, 'r') as f:
                data = json.load(f)
                
                # Handle new format (scales array)
                if "scales" in data:
                    current_data = data
                # Migration from old format (top-level emotion keys)
                elif "happiness" in data:
                    # Dynamically migrate any emotion keys that exist
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
    
    # If no scales exist, nothing to update
    if not scales:
        print(f"DEBUG: No emotion scales defined for {workspace_id}, skipping update.")
        return {}
    
    # Build dynamic prompt based on existing scales
    # Only include non-frozen scales in the prompt (frozen = user doesn't want AI to change them)
    updatable_scales = [s for s in scales if not s.get("frozen", False)]
    
    if not updatable_scales:
        print(f"DEBUG: All emotion scales are frozen for {workspace_id}, skipping update.")
        return {}
    
    scales_str = "\n".join([f"    - {s['name']}: {s['value']} (0-100)" for s in updatable_scales])
    delta_keys = ", ".join([f'"{s["name"].lower()}_delta": int' for s in updatable_scales])
    
    prompt = f"""Analyze the user's message and the AI's response to update the AI's emotional state and MOTIVE.
    
Current Emotional Scales (only these can be updated):
{scales_str}
    - Current Motive: "{motive}"
    
User: {last_human.content}
AI: {last_ai.content}
    
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
    
    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])

        match = re.search(r"\{.*\}", response.content, re.DOTALL)
        if match:
            output = json.loads(match.group(0))
            
            # Update scales dynamically
            for scale in scales:
                if scale.get("frozen", False):
                    continue  # Skip frozen scales
                    
                delta_key = f"{scale['name'].lower()}_delta"
                delta = output.get(delta_key, 0)
                
                if delta != 0:
                    old_val = scale["value"]
                    scale["value"] = max(0, min(100, old_val + delta))
                    print(f"DEBUG: {scale['name']}: {old_val} -> {scale['value']} (delta: {delta})")
            
            # Update Motive
            if "new_motive" in output and output["new_motive"]:
                current_data["motive"] = output["new_motive"]
            
            # Save
            current_data["scales"] = scales
            with open(emotion_path, 'w') as f:
                json.dump(current_data, f, indent=2)
            
            print(f"DEBUG: Updated emotions for {workspace_id}")
            
    except Exception as e:
        print(f"DEBUG: Emotion update failed: {e}")
        import traceback
        traceback.print_exc()
        
    return {}

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
        "add_graph_node", "update_graph_node", "add_graph_edge", "update_graph_edge", 
        "search_graph_nodes", "traverse_graph_node", "search_concepts",
        "search_gutenberg_books", "ingest_gutenberg_book", "search_wikipedia", 
        "ingest_wikipedia_page", "check_ingestion_status", "get_books_by_subject", "ingest_web_page",
        "search_biorxiv", "read_biorxiv_abstract", "search_arxiv", "read_arxiv_abstract", "ingest_arxiv_paper",
        "generate_lesson"
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
workflow.add_node("extract", extract_knowledge_node)
workflow.add_node("update_emotions", update_emotions_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")

def route_generate(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return "extract"

workflow.add_conditional_edges(
    "generate",
    route_generate,
    {
        "tools": "tools",
        "extract": "extract"
    }
)

workflow.add_edge("tools", "generate")
workflow.add_edge("extract", "update_emotions")
workflow.add_edge("update_emotions", END)

app_agent = workflow.compile()
