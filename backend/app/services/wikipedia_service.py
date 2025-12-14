
import wikipedia
import os
import httpx

class WikipediaService:
    def search_pages(self, query: str, limit: int = 5) -> str:
        """
        Searches for Wikipedia pages.
        Returns a markdown list of results.
        """
        try:
            results = wikipedia.search(query, results=limit)
            if not results:
                return f"No Wikipedia pages found for '{query}'."
            
            output = [f"### Wikipedia Pages for '{query}':"]
            for title in results:
                try:
                    # Fetch summary or just list title
                    # Attempting to get summary can be slow, so listing titles is safer for search
                    output.append(f"- **{title}**")
                except Exception:
                    continue
                    
            return "\n".join(output)

        except Exception as e:
            return f"Error searching Wikipedia: {e}"

    def get_page_content(self, title: str) -> str:
        """
        Retrieves the full content of a Wikipedia page.
        """
        try:
            # Auto-suggest if exact match not found
            page = wikipedia.page(title, auto_suggest=True) 
            return page.content
        except wikipedia.DisambiguationError as e:
            return f"Error: The title '{title}' is ambiguous. Options: {e.options[:5]}"
        except wikipedia.PageError:
            return f"Error: Page '{title}' not found."
        except Exception as e:
            return f"Error fetching Wikipedia page: {e}"

wikipedia_service = WikipediaService()
