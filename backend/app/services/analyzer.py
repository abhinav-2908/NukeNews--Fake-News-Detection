import asyncio
import re
from urllib.parse import urlparse
from uuid import uuid4
from datetime import datetime, timezone

from langdetect import detect, LangDetectException

from app.core.config import settings
from app.extraction.url import extract_url
from app.ml.inference import classifier
from app.verification.search import search
from app.verification.openrouter import verify
from app.schemas.analysis import AnalysisResult, Source, Claim


def _passage(article: str, query: str, max_words: int = 25) -> str:
    """Choose one short relevant passage from a fetched article for review."""
    terms={t.lower() for t in re.findall(r"[\w'-]{4,}",query) if t.lower() not in {"this","that","with","from","were","have","what","when","where","will","would","there","their","about","after","before"}}
    sentences=re.split(r"(?<=[.!?])\s+",article)
    ranked=sorted(enumerate(sentences),key=lambda pair:sum(term in pair[1].lower() for term in terms),reverse=True)
    selected=ranked[0][1] if ranked else article
    words=selected.split()
    if len(words)<8:
        words=(article.strip().split()[:max_words])
    return " ".join(words[:max_words])


async def _hydrate_sources(raw: list[dict], query: str) -> list[dict]:
    async def hydrate(item: dict) -> dict:
        try:
            page=await extract_url(item["url"])
            passage=_passage(page.get("text",""),query)
            if passage:
                return {**item,"url":page.get("canonical_url",item["url"]),"publisher":page.get("publisher") or item.get("publisher"),"snippet":passage,"retrieval_mode":"article_page_excerpt"}
        except Exception:
            pass
        # Keep the actual search provider's snippet if a page is blocked/paywalled/unavailable.
        item["snippet"]=(item.get("snippet") or "")[:500]
        return item
    # Bound outbound fetch fan-out and work; lower-ranked results retain their search snippets.
    targets=raw[:4]
    fetched=await asyncio.gather(*(hydrate(item) for item in targets),return_exceptions=True)
    enriched=[value if isinstance(value,dict) else raw[i] for i,value in enumerate(fetched)]
    return enriched+raw[4:]


async def analyze(text: str, title: str="", input_type: str="text", extraction: dict|None=None) -> AnalysisResult:
    text=(text or "").strip()
    if len(text)<3: raise ValueError("Enter at least three characters of meaningful text.")
    try: language=detect((title+" "+text)[:4000])
    except LangDetectException: language="unknown"
    limitations=[]
    if language=="en":
        model=classifier.predict((title+"\n"+text).strip())
        if model.get("status")!="ready": limitations.append("No trained classifier is installed; classifier-only results are unavailable.")
    elif language=="hi":
        model={"status":"unsupported_language","prediction":None,"probabilities":None,"message":"The ISOT-trained classifier is validated only on English-language data."}
        limitations.append("ISOT is English-language data; classifier output is withheld for Hindi text.")
    else:
        model={"status":"unsupported_language","prediction":None,"probabilities":None,"message":"The initial classifier supports English only."}
        limitations.append(f"Language {language} is outside the validated English classifier scope.")

    query=(title or text[:240]).replace("\n"," ")[:300]
    raw=[]
    search_status="ok"
    try:
        raw=await search(query)
        if not raw: search_status="no_results"
    except Exception:
        search_status="unavailable"
        limitations.append("Evidence search is unavailable; no external sources were retrieved.")

    sources=[]; seen=set()
    for item in raw:
        url=item.get("url","")
        parsed=urlparse(url)
        if parsed.scheme not in ("http","https") or not parsed.hostname or url in seen: continue
        seen.add(url); sources.append({**item,"id":f"S{len(sources)+1}"})
    if sources:
        sources=await _hydrate_sources(sources,query)

    llm=None; llm_status="not_configured" if not (settings.openrouter_api_key and settings.openrouter_model) else "unavailable"
    llm_verification={"status":llm_status,"verdict":"INCONCLUSIVE","summary":"LLM verification has not completed."}
    try:
        llm=await verify(text,title,sources)
        if llm is None:
            llm_status="not_configured"
            llm_verification={"status":llm_status,"verdict":"INCONCLUSIVE","summary":"Configure OpenRouter to enable the LLM claim check."}
        else:
            llm_status="completed"
            llm_verification={"status":llm_status,"verdict":llm.get("verdict","INCONCLUSIVE"),"summary":str(llm.get("summary") or "")}
    except Exception as exc:
        llm_status="invalid_response" if isinstance(exc,(ValueError,KeyError,TypeError)) else "unavailable"
        llm_verification={"status":llm_status,"verdict":"INCONCLUSIVE","summary":"The LLM request failed or returned invalid structured output."}
        limitations.append("LLM verification was unavailable or returned an invalid response.")

    verdict="INCONCLUSIVE"; summary="Available evidence is insufficient for a reliable verdict."
    claims=[]
    if llm:
        summary=str(llm.get("summary") or summary)
        verdict=llm.get("verdict","INCONCLUSIVE")
        try:
            claims=[Claim(**c) for c in llm.get("claims",[])]
        except Exception:
            claims=[]; verdict="INCONCLUSIVE"; llm_status="invalid_response"
            llm_verification={"status":llm_status,"verdict":"INCONCLUSIVE","summary":"The model returned claims that did not match the expected schema."}
            limitations.append("LLM verification returned claims that did not match the required schema.")
        llm_limits=llm.get("limitations",[])
        if isinstance(llm_limits,str): llm_limits=[llm_limits]
        if isinstance(llm_limits,list): limitations.extend(item for item in llm_limits if isinstance(item,str))

    page_ids={source["id"] for source in sources if source.get("retrieval_mode")=="article_page_excerpt"}
    cited_page_ids=set()
    for claim in claims:
        if claim.assessment=="SUPPORTED": cited_page_ids.update(set(claim.supporting_source_ids)&page_ids)
        if claim.assessment=="CONTRADICTED": cited_page_ids.update(set(claim.contradicting_source_ids)&page_ids)
    if search_status!="ok" or not sources:
        verdict="INCONCLUSIVE"
        if not sources:
            limitations.append("No traceable search sources were returned; the classifier cannot establish factual truth by itself.")
    elif llm and verdict in ("REAL","FAKE") and not cited_page_ids:
        llm_verdict=verdict
        verdict="INCONCLUSIVE"
        summary=f"The LLM assessed the report as {llm_verdict}, but it cited only search-result snippets or unrelated pages. No retrieved article passage directly supports or contradicts the central claim, so the final verdict is INCONCLUSIVE."
        limitations.append("The LLM verdict is not backed by a relevant retrieved article passage; snippets alone are insufficient for a REAL or FAKE verdict.")
    # The LLM verdict is evidence assessment, not calibrated probability; the classifier stays separate.
    result=AnalysisResult(id=str(uuid4()),created_at=datetime.now(timezone.utc).isoformat(),input_type=input_type,title=title,text=text[:100000],language=language,
      classifier=model,llm_verification=llm_verification,evidence_search={"status":search_status,"provider":settings.search_provider,"source_count":len(sources),"article_pages_read":len(page_ids),"claim_cited_pages":len(cited_page_ids)},verdict=verdict,summary=summary,claims=claims,
      sources=[Source(**s) for s in sources],supporting_evidence=[],contradicting_evidence=[],limitations=list(dict.fromkeys(limitations)),extraction=extraction or {})
    return result
