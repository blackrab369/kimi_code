import requests
import re
import urllib.parse
import json

import os

def search_web(query, max_results=5):
    """
    Search web using Serper Device (if key present) or valid scraper fallback.
    """
    try:
        # 1. Try Serper API (High Quality JSON)
        api_key = os.environ.get("SERPER_API_KEY")
        if api_key:
            url = "https://google.serper.dev/search"
            payload = json.dumps({"q": query, "num": max_results})
            headers = {
                'X-API-KEY': api_key,
                'Content-Type': 'application/json'
            }
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            if response.ok:
                data = response.json()
                organic = data.get("organic", [])
                results = []
                for item in organic:
                    results.append({
                        "title": item.get("title"),
                        "href": item.get("link"),
                        "body": item.get("snippet", "")
                    })
                return results

        # 2. Fallback to Scraper (DuckDuckGo Lite)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # DDG Lite is easier to parse
        url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text
        
        results = []
        
        # Simple Regex Parsing for DDG Lite
        # Structure: <tr><td><a href="...">Title</a>... snippet ...
        # This is brittle but works without BS4
        
        # Find all result links
        # <a rel="nofollow" href="LINK" class="result-link">TITLE</a>
        # DDG Lite: <a href="http..." class="result-link">
        
        links = re.findall(r'<a href="(http[^"]+)" class="result-link">([^<]+)</a>', html)
        snippets = re.findall(r'<tr>\s*<td valign="top">.*?</td>\s*<td>(.*?)</td>', html, re.DOTALL)
        
        for i, (link, title) in enumerate(links[:max_results]):
            snippet = "No snippet"
            # Matching snippets to links is hard with regex on raw html, 
            # let's just return Title + Link which is often enough for "Research"
            # Or try to get snippet if possible.
            
            results.append({
                "title": title,
                "href": link,
                "body": f"Source: {title} ({link})" 
            })
            
        return results

    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]
