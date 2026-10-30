import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


def _check_url(url: str):
    parsed=urlparse(url)
    if parsed.scheme not in ("http","https") or not parsed.hostname:
        raise ValueError("Only valid HTTP(S) URLs are accepted.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")
    try:
        addresses={item[4][0] for item in socket.getaddrinfo(parsed.hostname,None)}
    except OSError as exc:
        raise ValueError("The URL host could not be resolved.") from exc
    if not addresses:
        raise ValueError("The URL host could not be resolved.")
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("Private, local, and reserved network addresses are blocked.")


async def extract_url(url: str) -> dict:
    current=url
    for _ in range(6):
        _check_url(current)
        redirect=None
        async with httpx.AsyncClient(timeout=12,follow_redirects=False,headers={"User-Agent":"Mozilla/5.0 (compatible; NukeNews/1.0)"}) as client:
            async with client.stream("GET",current) as response:
                if response.status_code in (301,302,303,307,308):
                    location=response.headers.get("location")
                    if location: redirect=urljoin(current,location)
                else:
                    response.raise_for_status()
                    content_type=response.headers.get("content-type","").lower()
                    if content_type and not any(value in content_type for value in ("text/html","application/xhtml+xml","text/plain")):
                        raise ValueError("The URL does not return a readable HTML or text page.")
                    chunks=[]; size=0
                    async for chunk in response.aiter_bytes():
                        size+=len(chunk)
                        if size>5_000_000: raise ValueError("Page is larger than the 5 MB limit.")
                        chunks.append(chunk)
                    page_url=str(response.url)
                    html=b"".join(chunks).decode(response.encoding or "utf-8",errors="replace")
        if redirect:
            current=redirect
            continue
        if response.status_code in (301,302,303,307,308):
            raise ValueError("Redirect response did not include a valid location.")
        soup=BeautifulSoup(html,"html.parser")
        title=soup.title.get_text(" ",strip=True) if soup.title else ""
        try:
            import trafilatura
            article=trafilatura.extract(html,include_comments=False,include_tables=False) or ""
        except ImportError:
            article=""
        if "text/plain" in content_type:
            article=html.strip()
        if not article:
            for tag in soup(["script","style","nav","footer","header"]): tag.decompose()
            article="\n".join(p.get_text(" ",strip=True) for p in soup.find_all("p"))
        if not article.strip():
            raise ValueError("No readable article text was found. The page may be inaccessible or paywalled.")
        return {"title":title,"text":article[:100000],"canonical_url":page_url,"publisher":urlparse(page_url).hostname,"status":"extracted"}
    raise ValueError("Too many redirects.")
