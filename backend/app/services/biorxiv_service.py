
import httpx
import urllib.parse
import os
from app.llm_config import llm_config

class BioRxivService:
    def __init__(self):
        self.eu_pmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        self.biorxiv_api_url = "https://api.biorxiv.org/details"
        
    def _get_headers(self):
        # Good practice to identify
        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }

    async def search_articles(self, query: str, limit: int = 5):
        """
        Searches bioRxiv papers using Europe PMC API.
        Query automatically appends 'AND SRC:PPR' to find preprints.
        """
        # Europe PMC Query
        # We assume bioRxiv DOIs start with 10.1101. 
        # But we can also just search all preprints and filter or trust the user query?
        # Let's force bioRxiv context if possible, or just preprints.
        # Adding (PUBLISHER:"Code Spring Harbor Laboratory" OR DOI:10.1101/%) helps but simpler is better.
        
        full_query = f"{query} AND SRC:PPR"
        
        params = {
            "query": full_query,
            "format": "json",
            "pageSize": limit * 2 # Request more to filter
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.eu_pmc_url, params=params, headers=self._get_headers())
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for item in data.get('resultList', {}).get('result', []):
                # Filter for bioRxiv/medRxiv (mostly 10.1101)
                doi = item.get('doi', '')
                publisher = item.get('bookOrReportDetails', {}).get('publisher', '').lower()
                
                # Loose filter: strict bioRxiv usually implies checking publisher or DOI
                if "biorxiv" in publisher or doi.startswith("10.1101/"):
                    results.append({
                        "title": item.get('title'),
                        "doi": doi,
                        "authors": item.get('authorString'),
                        "year": item.get('pubYear'),
                        "source": "bioRxiv",
                        "url": f"https://www.biorxiv.org/content/{doi}v1" # Abstract page guess
                    })
                    
            return results[:limit]

    async def get_article_details(self, doi: str):
        """
        Fetches abstract and details from bioRxiv API.
        """
        # Endpoint: https://api.biorxiv.org/details/[server]/[doi]
        # We don't know if it's bioRxiv or medRxiv easily from just DOI (both 10.1101).
        # We try bioRxiv first.
        
        # Clean DOI if it has version
        base_doi = doi.split('v')[0] # Remove version suffix if present for API check? 
        # Actually API handles versions or base DOI.
        
        url = f"{self.biorxiv_api_url}/biorxiv/{doi}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            # If 404/failure, try medrxiv?
            if resp.status_code != 200 or '"messages":"No papers found"' in resp.text:
                url = f"{self.biorxiv_api_url}/medrxiv/{doi}"
                resp = await client.get(url)
            
            if resp.status_code != 200:
                return None
                
            data = resp.json()
            collection = data.get('collection', [])
            if not collection:
                return None
                
            # Use the latest version
            paper = collection[-1]
            return {
                "title": paper.get('title'),
                "abstract": paper.get('abstract'),
                "doi": paper.get('doi'),
                "date": paper.get('date'),
                "authors": paper.get('authors'),
                "version": paper.get('version'),
                "pdf_url": f"https://www.biorxiv.org/content/{paper.get('doi')}v{paper.get('version')}.full.pdf"
            }

    async def download_pdf(self, doi: str, output_path: str):
        """
        Downloads the PDF for a given DOI.
        """
        details = await self.get_article_details(doi)
        print(f"DEBUG: BioRxiv details for {doi}: {details}")
        if not details or not details.get('pdf_url'):
            raise Exception("Could not find article details or PDF URL.")
            
        pdf_url = details['pdf_url']
        print(f"DEBUG: Downloading BioRxiv PDF from {pdf_url}")
        
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(pdf_url, headers=self._get_headers())
                print(f"DEBUG: PDF Download Status: {resp.status_code}")
                resp.raise_for_status()
                
                with open(output_path, "wb") as f:
                    f.write(resp.content)
            
            return output_path, details['title']
            
        except Exception as e:
            print(f"DEBUG: PDF download failed ({e}). Attempting HTML full-text scrape...")
            
            try:
                # Try HTML Full Text
                # User suggestion: .full-text
                urls_to_try = [
                    f"https://www.biorxiv.org/content/{doi}v1.full",
                    f"https://www.biorxiv.org/content/{doi}v1.full-text"
                ]
                
                content = ""
                html_url = ""
                
                for h_url in urls_to_try:
                    print(f"DEBUG: Scraping HTML from {h_url}")
                    async with httpx.AsyncClient(follow_redirects=True) as client:
                        resp = await client.get(h_url, headers=self._get_headers())
                        print(f"DEBUG: HTML Status: {resp.status_code}")
                        
                        if resp.status_code == 200:
                            html_url = h_url
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            
                            # Method A: Specific container
                            article_body = soup.find('div', class_='article fulltext-view')
                            if article_body:
                                 content = article_body.get_text(separator='\n\n')
                            else:
                                 # Method B: Main tag
                                 main = soup.find('main')
                                 if main:
                                     content = main.get_text(separator='\n\n')
                                 else:
                                     # Method C: All paragraph text
                                     paras = soup.find_all('p')
                                     content = "\n\n".join([p.get_text() for p in paras])
                            
                            if len(content) > 500:
                                break # Success
                
                if len(content) > 500:
                    print(f"DEBUG: Successfully scraped {len(content)} chars of HTML.")
                    txt_path = output_path.replace(".pdf", ".txt")
                    with open(txt_path, "w") as f:
                        f.write(f"Title: {details['title']}\n")
                        f.write(f"Source: Full Text HTML Scrape ({html_url})\n")
                        f.write(f"DOI: {details['doi']}\n\n")
                        f.write(content)
                    return txt_path, details['title']
            except Exception as scrape_e:
                 print(f"DEBUG: HTML scrape failed: {scrape_e}")
            except Exception as scrape_e:
                 print(f"DEBUG: HTML scrape failed: {scrape_e}")

            print("DEBUG: Falling back to abstract only.")
            # Fallback: Create a text file with Abstract
            txt_path = output_path.replace(".pdf", ".txt")
            with open(txt_path, "w") as f:
                f.write(f"Title: {details['title']}\n")
                f.write(f"Authors: {details['authors']}\n")
                f.write(f"DOI: {details['doi']}\n")
                f.write(f"Date: {details['date']}\n\n")
                f.write(f"Abstract:\n{details['abstract']}")
            
            return txt_path, details['title']

biorxiv_service = BioRxivService()
