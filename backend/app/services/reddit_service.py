
import httpx
from app.llm_config import llm_config
import urllib.parse
import traceback

class RedditService:
    def __init__(self):
        self.base_url = "https://www.reddit.com"

    def _get_headers(self):
        cfg = llm_config.get_config()
        # Default user agent if not set
        ua = cfg.reddit_user_agent if cfg.reddit_user_agent else "python:graph_chat_agent:v1.0 (public access)"
        return {"User-Agent": ua}

    def is_configured(self):
        return True # No auth needed for public access

    def search_posts(self, query: str, limit: int = 5):
        """Searches for posts matching the query using public JSON API."""
        try:
            headers = self._get_headers()
            # Reddit search endpoint: /search.json?q=QUERY&limit=LIMIT&sort=relevance
            encoded_query = urllib.parse.quote(query)
            url = f"{self.base_url}/search.json?q={encoded_query}&limit={limit}&sort=relevance"
            
            print(f"DEBUG: Reddit Search URL: {url}")
            
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                
                if resp.status_code == 429:
                    return "Error: Reddit rate limit exceeded. Please wait a moment."
                
                resp.raise_for_status()
                data = resp.json()
                
                posts = []
                children = data.get("data", {}).get("children", [])
                
                for child in children:
                    kind = child.get("kind")
                    item = child.get("data", {})
                    
                    if kind == "t3": # Link/Text Post
                        posts.append({
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "score": item.get("score"),
                            "num_comments": item.get("num_comments"),
                            "selftext": item.get("selftext", "")[:500] + "...",
                            "id": item.get("id"),
                            "subreddit": item.get("subreddit"),
                            "permalink": item.get("permalink")
                        })
                
                return posts

        except Exception as e:
            traceback.print_exc()
            return f"Reddit search failed: {e}"

    def get_subreddit_posts(self, subreddit: str, sort: str = "new", limit: int = 10):
        """Fetches posts from a subreddit (sort: new, hot, top)."""
        try:
            # /r/SUBREDDIT/new.json
            sort = sort.lower() if sort.lower() in ["new", "hot", "top"] else "new"
            url = f"{self.base_url}/r/{subreddit}/{sort}.json?limit={limit}"
            headers = self._get_headers()
            
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 429:
                    return "Error: Rate limit exceeded."
                if resp.status_code == 404:
                    return f"Error: Subreddit r/{subreddit} not found."
                    
                resp.raise_for_status()
                data = resp.json()
                
                posts = []
                children = data.get("data", {}).get("children", [])
                
                for child in children:
                    item = child.get("data", {})
                    posts.append({
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "score": item.get("score"),
                        "num_comments": item.get("num_comments"),
                        "selftext": item.get("selftext", "")[:500] + "...",
                        "id": item.get("id"),
                        "subreddit": item.get("subreddit"),
                        "permalink": f"https://www.reddit.com{item.get('permalink')}"
                    })
                return posts

        except Exception as e:
            return f"Failed to fetch r/{subreddit}: {e}"

    def _extract_images(self, post_data):
        """Extracts image URLs from post data (direct URL or Gallery)."""
        images = []
        try:
            # 1. Direct Image URL
            url = post_data.get("url", "")
            if url.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                images.append(url)
            
            # 2. Gallery
            if "gallery_data" in post_data and "media_metadata" in post_data:
                gallery_items = post_data.get("gallery_data", {}).get("items", [])
                media_meta = post_data.get("media_metadata", {})
                
                for item in gallery_items:
                    media_id = item.get("media_id")
                    if media_id in media_meta:
                        meta = media_meta[media_id]
                        # usually 's' is the source image object, 'u' is the url
                        if "s" in meta:
                            # Prefer 'u' (url) or 'gif' (url)
                            img_url = meta["s"].get("u") or meta["s"].get("gif")
                            if img_url:
                                # Reddit URLs often have &amp; that breaks markdown
                                images.append(img_url.replace("&amp;", "&"))
                                
        except Exception as e:
            print(f"Image extraction error: {e}")
            
        return images

    def get_comments(self, submission_id_or_url: str, limit: int = 10):
        """Fetches comments for a submission ID or full URL."""
        try:
            submission_id = submission_id_or_url
            
            # Extract ID from URL if valid
            # e.g. https://www.reddit.com/r/Python/comments/12345/title/
            if "reddit.com" in submission_id_or_url and "/comments/" in submission_id_or_url:
                try:
                    parts = submission_id_or_url.split("/comments/")
                    if len(parts) > 1:
                        submission_id = parts[1].split("/")[0]
                except:
                    pass

            url = f"{self.base_url}/comments/{submission_id}.json?limit={limit}"
            headers = self._get_headers()
            
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                
                if isinstance(data, list) and len(data) > 0:
                    # Post Info from [0]
                    post_data = data[0].get("data", {}).get("children", [])[0].get("data", {})
                    
                    # Extract Images
                    images = self._extract_images(post_data)
                    
                    post_info = {
                        "title": post_data.get("title"),
                        "selftext": post_data.get("selftext", ""),
                        "url": post_data.get("url"),
                        "images": images
                    }
                    
                    # Comments from [1]
                    comments = []
                    if len(data) > 1:
                        comments_data = data[1].get("data", {}).get("children", [])
                        for child in comments_data:
                            if child.get("kind") == "t1": 
                                comm = child.get("data", {})
                                comments.append({
                                    "author": comm.get("author", "[deleted]"),
                                    "body": comm.get("body", ""),
                                    "score": comm.get("score", 0)
                                })
                    
                    return {"post": post_info, "comments": comments}
                    
                return None

        except Exception as e:
            return f"Failed to fetch comments: {e}"

    def get_user_info(self, username: str):
        """Fetches public user profile information."""
        try:
            # /user/USERNAME/about.json
            url = f"{self.base_url}/user/{username}/about.json"
            headers = self._get_headers()
            
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 404:
                    return None # User not found
                resp.raise_for_status()
                data = resp.json()
                
                user_data = data.get("data", {})
                return {
                    "name": user_data.get("name"),
                    "id": user_data.get("id"),
                    "created_utc": user_data.get("created_utc"),
                    "link_karma": user_data.get("link_karma"),
                    "comment_karma": user_data.get("comment_karma"),
                    "total_karma": user_data.get("total_karma"),
                    "is_mod": user_data.get("is_mod"),
                    "is_gold": user_data.get("is_gold")
                }
        except Exception as e:
            return f"Failed to fetch user info: {e}"

    def get_user_content(self, username: str, type: str = "submitted", limit: int = 10):
        """Fetches user content (submitted or comments)."""
        try:
            # /user/USERNAME/submitted.json or /user/USERNAME/comments.json
            if type not in ["submitted", "comments", "overview"]:
                type = "submitted"
                
            url = f"{self.base_url}/user/{username}/{type}.json?limit={limit}"
            headers = self._get_headers()
            
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 404:
                    return []
                resp.raise_for_status()
                data = resp.json()
                
                items = []
                children = data.get("data", {}).get("children", [])
                
                for child in children:
                    kind = child.get("kind")
                    item = child.get("data", {})
                    
                    if kind == "t3": # Post
                        items.append({
                            "type": "post",
                            "title": item.get("title"),
                            "subreddit": item.get("subreddit"),
                            "score": item.get("score"),
                            "url": item.get("url"),
                            "permalink": f"https://www.reddit.com{item.get('permalink')}",
                            "created_utc": item.get("created_utc")
                        })
                    elif kind == "t1": # Comment
                        items.append({
                            "type": "comment",
                            "body": item.get("body"),
                            "subreddit": item.get("subreddit"),
                            "score": item.get("score"),
                            "link_title": item.get("link_title"),
                            "link_permalink": f"https://www.reddit.com{item.get('permalink')}", # This usually points to comment
                            "created_utc": item.get("created_utc")
                        })
                        
                return items
        except Exception as e:
            return f"Failed to fetch user content: {e}"

# Global instance
reddit_service = RedditService()
