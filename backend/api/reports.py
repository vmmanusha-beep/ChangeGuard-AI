from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.db import get_db, get_all_analyses, get_analysis_by_id
from models.schemas import AnalyzeResponse, ReportListItem, FindingSchema

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportListItem])
async def list_reports(db: AsyncSession = Depends(get_db)):
    """Return all past analysis reports, newest first."""
    records = await get_all_analyses(db)
    return [
        ReportListItem(
            id=r.id,
            title=r.title,
            risk_level=r.risk_level,
            risk_score=r.risk_score,
            summary=r.summary,
            affected_files=r.affected_files,
            findings_count=len(r.findings),
            engine=r.engine,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/{report_id}", response_model=AnalyzeResponse)
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Return a single analysis report by ID."""
    record = await get_analysis_by_id(db, report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found.")

    return AnalyzeResponse(
        id=record.id,
        title=record.title,
        risk_level=record.risk_level,
        risk_score=record.risk_score,
        summary=record.summary,
        affected_files=record.affected_files,
        findings=[FindingSchema(**f) for f in record.findings],
        safer_alternatives=record.safer_alternatives,
        recommended_tests=record.recommended_tests,
        engine=record.engine,
        created_at=record.created_at,
    )
