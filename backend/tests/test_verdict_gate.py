import asyncio
import app.services.analyzer as analyzer

async def fake_search(_query):
    return [{"title":"A reported claim","url":"https://news.example/article","snippet":"Short search result snippet.","publisher":"Example News","retrieval_mode":"search_result_snippet"}]

async def keep_sources(items, _query):
    return items

async def llm_real(*_args):
    return {"verdict":"REAL","summary":"The LLM considers the claim supported.","claims":[{"claim":"The central claim","assessment":"SUPPORTED","reasoning":"Source S1 supports it.","supporting_source_ids":["S1"],"contradicting_source_ids":[]}],"limitations":"Some details are unverified."}

def setup(monkeypatch, retrieval_mode):
    monkeypatch.setattr(analyzer, "search", fake_search)
    async def hydrate(items, query):
        items[0]["retrieval_mode"]=retrieval_mode
        return items
    monkeypatch.setattr(analyzer, "_hydrate_sources", hydrate)
    monkeypatch.setattr(analyzer, "verify", llm_real)
    monkeypatch.setattr(analyzer.classifier, "predict", lambda _text:{"status":"ready","prediction":"REAL","probabilities":{"REAL":0.8,"FAKE":0.2}})

def test_search_snippet_alone_does_not_set_real(monkeypatch):
    setup(monkeypatch,"search_result_snippet")
    result=asyncio.run(analyzer.analyze("This is an English factual news claim for testing."))
    assert result.llm_verification["verdict"]=="REAL"
    assert result.verdict=="INCONCLUSIVE"
    assert result.evidence_search["claim_cited_pages"]==0
    assert any("snippets alone are insufficient" in x for x in result.limitations)
    assert "Some details are unverified." in result.limitations

def test_relevant_retrieved_passage_can_support_verdict(monkeypatch):
    setup(monkeypatch,"article_page_excerpt")
    result=asyncio.run(analyzer.analyze("This is an English factual news claim for testing."))
    assert result.verdict=="REAL"
    assert result.evidence_search["claim_cited_pages"]==1
