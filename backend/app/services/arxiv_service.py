"""
ArXiv Service - Provides search and retrieval of arXiv papers.
Uses the official arxiv Python library.
"""

import arxiv
from typing import List, Dict, Optional


class ArxivService:
    def __init__(self):
        self.client = arxiv.Client()
    
    def search_articles(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Searches arXiv for papers matching the query.
        Returns list of papers with title, authors, id, date, and URL.
        """
        try:
            search = arxiv.Search(
                query=query,
                max_results=limit,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results = []
            for paper in self.client.results(search):
                results.append({
                    "title": paper.title,
                    "arxiv_id": paper.get_short_id(),
                    "authors": ", ".join([a.name for a in paper.authors[:5]]),  # Limit authors
                    "published": paper.published.strftime("%Y-%m-%d"),
                    "primary_category": paper.primary_category,
                    "url": paper.entry_id,
                    "pdf_url": paper.pdf_url
                })
            
            return results
            
        except Exception as e:
            print(f"ArXiv search error: {e}")
            return []
    
    def get_article_details(self, arxiv_id: str) -> Optional[Dict]:
        """
        Fetches the full abstract and metadata for a specific arXiv paper.
        Accepts ID in format: 2301.07041 or arxiv:2301.07041
        """
        try:
            # Clean ID
            clean_id = arxiv_id.replace("arxiv:", "").strip()
            
            search = arxiv.Search(id_list=[clean_id])
            paper = next(self.client.results(search), None)
            
            if not paper:
                return None
            
            return {
                "title": paper.title,
                "arxiv_id": paper.get_short_id(),
                "abstract": paper.summary,
                "authors": ", ".join([a.name for a in paper.authors]),
                "published": paper.published.strftime("%Y-%m-%d"),
                "updated": paper.updated.strftime("%Y-%m-%d") if paper.updated else None,
                "primary_category": paper.primary_category,
                "categories": paper.categories,
                "url": paper.entry_id,
                "pdf_url": paper.pdf_url,
                "doi": paper.doi
            }
            
        except Exception as e:
            print(f"ArXiv fetch error for {arxiv_id}: {e}")
            return None
    
    def download_pdf(self, arxiv_id: str, output_path: str) -> tuple:
        """
        Downloads the PDF for an arXiv paper.
        Returns (file_path, title) on success.
        """
        import httpx
        
        details = self.get_article_details(arxiv_id)
        if not details or not details.get('pdf_url'):
            raise Exception(f"Could not find paper or PDF URL for {arxiv_id}")
        
        pdf_url = details['pdf_url']
        print(f"DEBUG: Downloading arXiv PDF from {pdf_url}")
        
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                resp = client.get(pdf_url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; MyceliumBot/1.0)"
                })
                resp.raise_for_status()
                
                with open(output_path, "wb") as f:
                    f.write(resp.content)
            
            return output_path, details['title']
            
        except Exception as e:
            print(f"DEBUG: PDF download failed: {e}")
            raise Exception(f"Failed to download PDF: {e}")


# Singleton instance
arxiv_service = ArxivService()
