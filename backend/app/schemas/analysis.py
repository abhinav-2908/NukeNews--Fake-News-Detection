from typing import Literal, Any
from pydantic import BaseModel, Field

Verdict = Literal["REAL", "FAKE", "INCONCLUSIVE"]
class TextRequest(BaseModel):
    title: str = Field(default="", max_length=2000)
    text: str = Field(min_length=3, max_length=100000)
    input_type: Literal["text", "pdf", "image"] = "text"
    extraction: dict[str, Any] = {}
class Source(BaseModel):
    id: str
    title: str
    url: str
    publisher: str | None = None
    snippet: str = ""
    published_at: str | None = None
    retrieval_mode: str = "search_result"
class Claim(BaseModel):
    claim: str
    assessment: Literal["SUPPORTED", "CONTRADICTED", "MIXED", "UNVERIFIED"]
    reasoning: str = ""
    supporting_source_ids: list[str] = []
    contradicting_source_ids: list[str] = []
class AnalysisResult(BaseModel):
    id: str | None = None
    created_at: str | None = None
    input_type: str
    title: str = ""
    text: str = ""
    language: str = "unknown"
    classifier: dict[str, Any] = {}
    llm_verification: dict[str, Any] = {}
    evidence_search: dict[str, Any] = {}
    verdict: Verdict = "INCONCLUSIVE"
    summary: str = ""
    claims: list[Claim] = []
    sources: list[Source] = []
    supporting_evidence: list[Source] = []
    contradicting_evidence: list[Source] = []
    limitations: list[str] = []
    extraction: dict[str, Any] = {}
