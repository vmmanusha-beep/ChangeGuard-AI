import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    risk_level = Column(String(10), nullable=False)
    risk_score = Column(Integer, nullable=False)
    summary = Column(Text, nullable=False)
    affected_files_json = Column(Text, nullable=False, default="[]")
    findings_json = Column(Text, nullable=False, default="[]")
    safer_alternatives_json = Column(Text, nullable=False, default="[]")
    recommended_tests_json = Column(Text, nullable=False, default="[]")
    engine = Column(String(20), nullable=False, default="mock")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def affected_files(self) -> list[str]:
        return json.loads(self.affected_files_json)

    @property
    def findings(self) -> list[dict]:
        return json.loads(self.findings_json)

    @property
    def safer_alternatives(self) -> list[str]:
        return json.loads(self.safer_alternatives_json)

    @property
    def recommended_tests(self) -> list[str]:
        return json.loads(self.recommended_tests_json)


# Columns added after the initial schema.
# Each tuple: (column_name, SQLite_type_and_constraints)
_MIGRATIONS: list[tuple[str, str]] = [
    ("safer_alternatives_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("recommended_tests_json",  "TEXT NOT NULL DEFAULT '[]'"),
    ("engine",                  "VARCHAR(20) NOT NULL DEFAULT 'mock'"),
]


def _apply_migrations(sync_conn):
    """
    Receive the synchronous SQLAlchemy Connection passed by run_sync and use
    SQLAlchemy's own text() API to inspect and alter the table.
    Called after create_all so the table is guaranteed to exist.
    """
    from sqlalchemy import text as sa_text

    existing = {
        row[1]
        for row in sync_conn.execute(sa_text("PRAGMA table_info(analyses)"))
    }
    for col_name, col_ddl in _MIGRATIONS:
        if col_name not in existing:
            sync_conn.execute(
                sa_text(f"ALTER TABLE analyses ADD COLUMN {col_name} {col_ddl}")
            )


async def init_db():
    async with engine.begin() as conn:
        # 1. Create the table if it doesn't exist yet (no-op if it does).
        await conn.run_sync(Base.metadata.create_all)
        # 2. Add any missing columns introduced after the initial schema (preserves data).
        await conn.run_sync(_apply_migrations)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def save_analysis(session: AsyncSession, title: str, result, engine_used: str = "mock") -> AnalysisRecord:
    record = AnalysisRecord(
        title=title,
        risk_level=result.risk_level,
        risk_score=result.risk_score,
        summary=result.summary,
        affected_files_json=json.dumps(result.affected_files),
        findings_json=json.dumps(
            [
                {
                    "file": f.file,
                    "line_hint": f.line_hint,
                    "category": f.category,
                    "description": f.description,
                    "suggestion": f.suggestion,
                    "severity": f.severity,
                }
                for f in result.findings
            ]
        ),
        safer_alternatives_json=json.dumps(getattr(result, "safer_alternatives", [])),
        recommended_tests_json=json.dumps(getattr(result, "recommended_tests", [])),
        engine=engine_used,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_all_analyses(session: AsyncSession) -> list[AnalysisRecord]:
    result = await session.execute(
        select(AnalysisRecord).order_by(AnalysisRecord.created_at.desc())
    )
    return list(result.scalars().all())


async def get_analysis_by_id(session: AsyncSession, analysis_id: int) -> AnalysisRecord | None:
    result = await session.execute(
        select(AnalysisRecord).where(AnalysisRecord.id == analysis_id)
    )
    return result.scalar_one_or_none()
