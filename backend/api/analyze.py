import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.db import get_db, save_analysis
from models.schemas import AnalyzeRequest, AnalyzeResponse, FindingSchema
from core.diff_parser import parse_diff
from core.ai_engine import analyze as mock_analyze
from core.watsonx_engine import analyze_with_watsonx, WatsonxUnavailable
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("", response_model=AnalyzeResponse)
async def analyze_diff(payload: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """Parse the submitted git diff and return a risk analysis report."""
    files = parse_diff(payload.diff)
    if not files:
        raise HTTPException(
            status_code=422,
            detail="Could not parse any files from the provided diff.",
        )

    settings = get_settings()
    result = None
    engine_used = "mock"

    # ── Try watsonx.ai first (unless explicitly disabled) ────────────────────
    if not settings.use_mock_ai:
        try:
            result = analyze_with_watsonx(files)
            engine_used = "watsonx"
        except WatsonxUnavailable as exc:
            logger.warning("watsonx.ai unavailable — falling back to mock engine: %s", exc)

    # ── Fall back to local heuristic engine ───────────────────────────────────
    if result is None:
        result = mock_analyze(files)
        engine_used = "mock"

    logger.info(
        "Analysis complete: engine=%s risk=%s score=%d findings=%d",
        engine_used,
        result.risk_level,
        result.risk_score,
        len(result.findings),
    )

    record = await save_analysis(db, payload.title, result, engine_used=engine_used)

    return AnalyzeResponse(
        id=record.id,
        title=record.title,
        risk_level=result.risk_level,
        risk_score=result.risk_score,
        summary=result.summary,
        affected_files=result.affected_files,
        safer_alternatives=result.safer_alternatives,
        recommended_tests=result.recommended_tests,
        findings=[
            FindingSchema(
                file=f.file,
                line_hint=f.line_hint,
                category=f.category,
                description=f.description,
                suggestion=f.suggestion,
                severity=f.severity,
            )
            for f in result.findings
        ],
        created_at=record.created_at,
        engine=engine_used,
    )
