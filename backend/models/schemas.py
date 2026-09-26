from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime


# ── Request ───────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    diff: str = Field(..., min_length=10, description="Raw unified git diff text")
    title: str = Field(default="Untitled Analysis", max_length=200)


# ── Response pieces ───────────────────────────────────────────────────────────

class FindingSchema(BaseModel):
    file: str
    line_hint: str
    category: str
    description: str
    suggestion: str
    severity: str  # "high" | "medium" | "low"


class AnalyzeResponse(BaseModel):
    id: int
    title: str
    risk_level: str
    risk_score: int
    summary: str
    affected_files: list[str]
    findings: list[FindingSchema]
    safer_alternatives: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    engine: str = "mock"   # "mock" | "watsonx"
    created_at: datetime


# ── History list item ─────────────────────────────────────────────────────────

class ReportListItem(BaseModel):
    id: int
    title: str
    risk_level: str
    risk_score: int
    summary: str
    affected_files: list[str]
    findings_count: int
    engine: str = "mock"
    created_at: datetime
