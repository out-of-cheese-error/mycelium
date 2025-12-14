import httpx

class GutendexService:
    BASE_URL = "https://gutendex.com/books/"

    def search_books(self, query: str, limit: int = 5) -> str:
        """
        Searches for books on Project Gutenberg via Gutendex.
        Returns a markdown list of results.
        """
        try:
            params = {
                "search": query
            }
            
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            if not results:
                return f"No books found for '{query}'."
            
            # Limit results
            results = results[:limit]

            output = [f"### Project Gutenberg Books for '{query}':"]
            for book in results:
                title = book.get("title", "Unknown Title")
                authors = ", ".join([a.get("name", "Unknown") for a in book.get("authors", [])])
                book_id = book.get("id")
                
                # Check for formats
                formats = book.get("formats", {})
                text_link = (
                    formats.get("text/plain; charset=utf-8") or 
                    formats.get("text/plain; charset=us-ascii") or 
                    formats.get("text/plain")
                )
                
                output.append(f"- **{title}** by {authors} (ID: {book_id})")
                if text_link:
                    output.append(f"  - Read/Download: {text_link}")
                else:
                    output.append(f"  - No text format available.")
                    
            return "\n".join(output)

        except Exception as e:
            return f"Error searching Gutendex: {e}"

    def get_book_text_url(self, book_id: int) -> str:
        """
        Returns the text/plain download URL for a specific book ID.
        Returns None if not found.
        """
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(f"{self.BASE_URL}{book_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                book = resp.json()
                
            formats = book.get("formats", {})
            return (
                formats.get("text/plain; charset=utf-8") or 
                formats.get("text/plain; charset=us-ascii") or 
                formats.get("text/plain")
            )
            
        except Exception as e:
            print(f"DEBUG ERROR in get_book_text_url: {e}")
            return None

gutendex_service = GutendexService()
