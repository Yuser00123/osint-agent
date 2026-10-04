import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

# Curated OSINT Google Dork Templates categorized by investigative goal
DORK_CATALOG = {
    "sensitive_files": [
        'site:{target} filetype:env | filetype:yml | filetype:yaml | filetype:json | filetype:conf',
        'site:{target} filetype:sql | filetype:db | filetype:sqlite | filetype:bak',
        'site:{target} filetype:log | filetype:txt "password" | "token" | "secret"',
        'site:{target} filetype:pem | filetype:key | filetype:crt | filetype:ovpn',
    ],
    "exposed_directories": [
        'site:{target} intitle:"index of /" "parent directory"',
        'site:{target} intitle:"index of /" "admin" | "backup" | "uploads" | "config"',
        'site:{target} intitle:"Index of" ".git"',
        'site:{target} intitle:"Index of" ".svn"',
    ],
    "admin_portals": [
        'site:{target} inurl:admin | inurl:login | inurl:dashboard | inurl:cpanel | inurl:portal',
        'site:{target} intitle:"admin login" | intitle:"dashboard login"',
        'site:{target} inurl:wp-admin | inurl:wp-login.php',
    ],
    "cloud_buckets_storage": [
        'site:s3.amazonaws.com "{target}"',
        'site:blob.core.windows.net "{target}"',
        'site:storage.googleapis.com "{target}"',
        'site:drive.google.com "{target}"',
    ],
    "subdomain_recon": [
        'site:*.{target} -www.{target}',
        'site:*.*.{target}',
        'site:{target} inurl:api | inurl:dev | inurl:staging | inurl:test | inurl:vpn',
    ],
    "confidential_documents": [
        'site:{target} filetype:pdf | filetype:doc | filetype:docx "confidential" | "not for public distribution"',
        'site:{target} filetype:xls | filetype:xlsx "internal" | "salary" | "budget" | "ssn"',
        'site:{target} "strictly private" | "do not distribute"',
    ],
    "debug_errors": [
        'site:{target} "fatal error" | "uncaught exception" | "stack trace" | "mysql error"',
        'site:{target} "Warning:" | "Notice:" filetype:php',
        'site:{target} inurl:debug | inurl:trace | inurl:status',
    ]
}

class GoogleDorksEngine:
    """
    Automated Google Dorks Generator, Validator, and Search Executor.
    Designed for defensive attack-surface discovery and asset reconnaissance.
    """

    def generate_dorks(self, target: str, category: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Generates formatted dorks for a target domain or keyword.
        """
        clean_target = target.strip().replace("https://", "").replace("http://", "").rstrip("/")
        results = []

        categories = [category] if category and category in DORK_CATALOG else DORK_CATALOG.keys()

        for cat in categories:
            templates = DORK_CATALOG.get(cat, [])
            for tmpl in templates:
                query = tmpl.replace("{target}", clean_target)
                google_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
                duckduckgo_url = f"https://duckduckgo.com/?q={urllib.parse.quote_plus(query)}"
                results.append({
                    "category": cat,
                    "query": query,
                    "google_search_url": google_url,
                    "duckduckgo_url": duckduckgo_url
                })
        return results

    async def execute_dork_search(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Executes a dork query using privacy search engines (DuckDuckGo Lite/HTML)
        to prevent bot-detection/captchas while extracting live results.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        encoded_query = urllib.parse.quote_plus(query)
        # Using DuckDuckGo html search endpoint which is fast, lightweight, and doesn't require API keys
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        try:
            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20.0) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    return {
                        "query": query,
                        "status": "error",
                        "error": f"Search engine returned status {resp.status_code}",
                        "results": []
                    }

                soup = BeautifulSoup(resp.text, "html.parser")
                items = []

                for result in soup.find_all("div", class_="result"):
                    title_elem = result.find("a", class_="result__a")
                    snippet_elem = result.find("a", class_="result__snippet")
                    url_elem = result.find("a", class_="result__url")

                    if title_elem and title_elem.get("href"):
                        href = title_elem.get("href")
                        # DuckDuckGo redirect link parsing
                        if "uddg=" in href:
                            actual_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                        else:
                            actual_url = href

                        title = title_elem.get_text(strip=True)
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                        items.append({
                            "title": title,
                            "url": actual_url,
                            "snippet": snippet
                        })
                        if len(items) >= max_results:
                            break

                return {
                    "query": query,
                    "status": "success",
                    "count": len(items),
                    "results": items
                }

        except Exception as e:
            return {
                "query": query,
                "status": "error",
                "error": str(e),
                "results": []
            }

google_dorks_engine = GoogleDorksEngine()
