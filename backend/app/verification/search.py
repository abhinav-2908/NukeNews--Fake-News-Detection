import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

BING_HEADERS={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36"}

async def _brave(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=8,follow_redirects=False) as client:
        r=await client.get("https://api.search.brave.com/res/v1/web/search",params={"q":query,"count":6},headers={"X-Subscription-Token":settings.brave_search_api_key,"Accept":"application/json"})
        r.raise_for_status()
    return [{"title":x.get("title",""),"url":x.get("url",""),"snippet":x.get("description",""),"publisher":x.get("meta_url",{}).get("hostname"),"published_at":None,"retrieval_mode":"search_result_snippet"} for x in r.json().get("web",{}).get("results",[])[:6]]

async def _bing_news(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=12,follow_redirects=True,headers=BING_HEADERS) as client:
        r=await client.get("https://www.bing.com/news/search",params={"q":query[:400]})
        r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    results=[]; seen=set()
    for card in soup.select("div.news-card"):
        title_node=card.select_one("a.title")
        title=(title_node.get_text(" ",strip=True) if title_node else card.get("data-title",""))
        url=card.get("data-url") or (title_node.get("href") if title_node else "")
        parsed=urlparse(url)
        if parsed.scheme not in ("http","https") or not parsed.hostname or url in seen: continue
        seen.add(url)
        snippet_node=card.select_one(".snippet")
        source_node=card.select_one(".source")
        date_node=card.select_one("[aria-label]")
        results.append({"title":title,"url":url,"snippet":snippet_node.get_text(" ",strip=True) if snippet_node else "","publisher":card.get("data-author") or (source_node.get_text(" ",strip=True) if source_node else None),"published_at":date_node.get("aria-label") if date_node else None,"retrieval_mode":"search_result_snippet"})
        if len(results)>=6: break
    return results

async def _google_news_rss(query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=12,follow_redirects=True,headers={"User-Agent":"Mozilla/5.0 NukeNews research client"}) as client:
        r=await client.get("https://news.google.com/rss/search",params={"q":query[:400],"hl":"en-US","gl":"US","ceid":"US:en"})
        r.raise_for_status()
    root=ET.fromstring(r.content); results=[]
    for item in root.findall("./channel/item")[:6]:
        source=item.find("source")
        results.append({"title":item.findtext("title",default=""),"url":item.findtext("link",default=""),"snippet":"","publisher":source.text if source is not None else None,"published_at":item.findtext("pubDate"),"retrieval_mode":"news_rss_title"})
    return results

async def search(query: str) -> list[dict]:
    """Free-first news search, with Brave available as an opt-in API provider."""
    if settings.search_provider=="brave" and settings.brave_search_api_key:
        return await _brave(query)
    if settings.search_provider=="google_news":
        return await _google_news_rss(query)
    # Bing News currently returns publisher URLs, titles and short result snippets without a key.
    # Fall back to Google News RSS when the HTML result changes or is unavailable.
    try:
        results=await _bing_news(query)
        if results: return results
    except Exception:
        pass
    return await _google_news_rss(query)
