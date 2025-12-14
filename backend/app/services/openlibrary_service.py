import httpx
import urllib.parse

class OpenLibraryService:
    BASE_URL = "https://openlibrary.org"

    def search_books(self, query: str, limit: int = 5) -> str:
        """
        Searches for books by title or author.
        Returns a markdown list of results.
        """
        try:
            params = {
                "q": query,
                "limit": limit
            }
            # The API allows fields selection, but standard response is fine.
            # fields=key,title,author_name,first_publish_year,editions,isbn
            
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.BASE_URL}/search.json", params=params)
                resp.raise_for_status()
                data = resp.json()

            docs = data.get("docs", [])
            if not docs:
                return f"No books found for '{query}'."

            output = [f"### Books found for '{query}':"]
            for doc in docs:
                title = doc.get("title", "Unknown Title")
                authors = ", ".join(doc.get("author_name", ["Unknown Author"]))
                year = doc.get("first_publish_year", "Unknown Year")
                key = doc.get("key", "") # e.g. /works/OL123W
                
                # Construct a direct link if possible, though key is usually internal
                link = f"{self.BASE_URL}{key}" if key else ""
                
                output.append(f"- **{title}** by {authors} ({year})")
                if link:
                    output.append(f"  - Link: {link}")
                    
            return "\n".join(output)

        except Exception as e:
            return f"Error searching books: {e}"

    def get_books_by_subject(self, subject: str, limit: int = 5) -> str:
        """
        Fetches books for a specific subject (e.g., 'python', 'history', 'romance').
        """
        try:
            # Subject API: /subjects/{subject}.json
            # Subject must be lowercase usually?
            safe_subject = subject.lower().strip().replace(" ", "_")
            
            params = {"limit": limit}
            
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.BASE_URL}/subjects/{safe_subject}.json", params=params)
                
                if resp.status_code == 404:
                     return f"Subject '{subject}' not found."
                
                resp.raise_for_status()
                data = resp.json()

            works = data.get("works", [])
            if not works:
                return f"No books found for subject '{subject}'."

            output = [f"### Books in subject '{data.get('name', subject)}':"]
            for work in works:
                title = work.get("title", "Unknown Title")
                # Authors in subject API are list of dicts: [{'name': '...', 'key': '...'}]
                authors = ", ".join([a.get("name", "Unknown") for a in work.get("authors", [])])
                year = work.get("first_publish_year", "Unknown Year")
                key = work.get("key", "")
                
                link = f"{self.BASE_URL}{key}" if key else ""
                
                output.append(f"- **{title}** by {authors} ({year})")
                if link:
                    output.append(f"  - Link: {link}")

            return "\n".join(output)

        except Exception as e:
            return f"Error fetching subject: {e}"

    def search_authors(self, query: str, limit: int = 5) -> str:
        """
        Searches for authors.
        """
        try:
            params = {
                "q": query,
                "limit": limit
            }
            
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.BASE_URL}/search/authors.json", params=params)
                resp.raise_for_status()
                data = resp.json()

            docs = data.get("docs", [])
            if not docs:
                return f"No authors found for '{query}'."

            output = [f"### Authors found for '{query}':"]
            for doc in docs:
                name = doc.get("name", "Unknown")
                top_work = doc.get("top_work", "")
                birth_date = doc.get("birth_date", "")
                death_date = doc.get("death_date", "")
                key = doc.get("key", "")
                
                date_str = ""
                if birth_date:
                    date_str = f"({birth_date} - {death_date if death_date else ''})"
                
                link = f"{self.BASE_URL}{key}" if key else ""
                
                output.append(f"- **{name}** {date_str}")
                if top_work:
                    output.append(f"  - Top Work: {top_work}")
                if link:
                    output.append(f"  - Link: {link}")
                    
            return "\n".join(output)

        except Exception as e:
            return f"Error searching authors: {e}"

# Global instance
openlibrary_service = OpenLibraryService()
