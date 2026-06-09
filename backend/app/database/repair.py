from sqlalchemy import inspect, text
from app.database.postgres import engine
from app.utils.logging import get_logger

logger = get_logger("database.repair")


EXPECTED_MARKET_SIGNALS_COLUMNS = {
    "id",
    "source",
    "source_type",
    "source_id",
    "query_id",
    "query_domain",
    "title",
    "content",
    "url",
    "author",
    "score",
    "comments_count",
    "credibility_score",
    "query_relevance_score",
    "created_at",
    "collected_at",
    "extra_metadata",
}

EXPECTED_COLUMN_ALTERATIONS = {
    "source_type": "ALTER TABLE market_signals ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) NOT NULL DEFAULT 'unknown'",
    "query_id": "ALTER TABLE market_signals ADD COLUMN IF NOT EXISTS query_id UUID NULL",
    "query_domain": "ALTER TABLE market_signals ADD COLUMN IF NOT EXISTS query_domain VARCHAR(50) NOT NULL DEFAULT 'general'",
    "credibility_score": "ALTER TABLE market_signals ADD COLUMN IF NOT EXISTS credibility_score DOUBLE PRECISION NOT NULL DEFAULT 0.5",
    "query_relevance_score": "ALTER TABLE market_signals ADD COLUMN IF NOT EXISTS query_relevance_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "extra_metadata": "ALTER TABLE market_signals ADD COLUMN IF NOT EXISTS extra_metadata JSONB NOT NULL DEFAULT '{}'::jsonb",
}

EXPECTED_STARTUP_OPPORTUNITY_COLUMNS = {
    "id",
    "market_gap_id",
    "query_id",
    "query_domain",
    "startup_name",
    "problem",
    "solution",
    "market_score",
    "opportunity_score",
    "confidence_score",
    "evidence_score",
    "demand_score",
    "pain_score",
    "growth_score",
    "competition_score",
    "whitespace_score",
    "feasibility_score",
    "query_relevance_score",
    "competition_level",
    "emergence_date",
    "last_signal_at",
    "signal_growth_30d",
    "trend_acceleration",
    "market_momentum",
    "evidence",
    "explanation",
    "target_customers",
    "revenue_model",
    "mvp_features",
    "go_to_market",
    "created_at",
}

EXPECTED_STARTUP_OPPORTUNITY_ALTERATIONS = {
    "confidence_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "opportunity_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS opportunity_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "evidence_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS evidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "demand_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS demand_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "pain_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS pain_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "growth_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS growth_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "competition_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS competition_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "whitespace_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS whitespace_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "feasibility_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS feasibility_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "competition_level": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS competition_level VARCHAR(20) NOT NULL DEFAULT 'Unknown'",
    "emergence_date": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS emergence_date TIMESTAMPTZ NULL",
    "last_signal_at": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS last_signal_at TIMESTAMPTZ NULL",
    "signal_growth_30d": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS signal_growth_30d INTEGER NOT NULL DEFAULT 0",
    "trend_acceleration": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS trend_acceleration DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "market_momentum": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS market_momentum DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "query_id": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS query_id UUID NULL",
    "query_domain": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS query_domain VARCHAR(50) NOT NULL DEFAULT 'general'",
    "query_relevance_score": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS query_relevance_score DOUBLE PRECISION NOT NULL DEFAULT 0.0",
    "evidence": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '{}'::jsonb",
    "explanation": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS explanation JSONB NOT NULL DEFAULT '{}'::jsonb",
    "target_customers": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS target_customers TEXT NOT NULL DEFAULT ''",
    "revenue_model": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS revenue_model TEXT NOT NULL DEFAULT ''",
    "mvp_features": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS mvp_features JSONB NOT NULL DEFAULT '{}'::jsonb",
    "go_to_market": "ALTER TABLE startup_opportunities ADD COLUMN IF NOT EXISTS go_to_market TEXT NOT NULL DEFAULT ''",
}

EXPECTED_COLLECTED_DOCUMENT_COLUMNS = {
    "id",
    "source",
    "source_type",
    "query_id",
    "query_domain",
    "title",
    "content",
    "url",
    "created_at",
    "metadata_json",
    "ingested_at",
}

EXPECTED_COLLECTED_DOCUMENT_ALTERATIONS = {
    "query_id": "ALTER TABLE collected_documents ADD COLUMN IF NOT EXISTS query_id UUID NULL",
    "query_domain": "ALTER TABLE collected_documents ADD COLUMN IF NOT EXISTS query_domain VARCHAR(50) NOT NULL DEFAULT 'general'",
}

EXPECTED_GENERATED_REPORT_COLUMNS = {
    "id",
    "query_id",
    "query_domain",
    "query",
    "report_payload",
    "created_at",
}

EXPECTED_GENERATED_REPORT_ALTERATIONS = {
    "query_id": "ALTER TABLE generated_reports ADD COLUMN IF NOT EXISTS query_id UUID NULL",
    "query_domain": "ALTER TABLE generated_reports ADD COLUMN IF NOT EXISTS query_domain VARCHAR(50) NOT NULL DEFAULT 'general'",
}


async def ensure_market_signals_schema() -> dict:
    async with engine.begin() as conn:
        def _get_columns(sync_conn):
            inspector = inspect(sync_conn)
            return {col["name"] for col in inspector.get_columns("market_signals")}

        columns = await conn.run_sync(_get_columns)
        missing = sorted(EXPECTED_MARKET_SIGNALS_COLUMNS - columns)
        extra = sorted(columns - EXPECTED_MARKET_SIGNALS_COLUMNS)

        for column, ddl in EXPECTED_COLUMN_ALTERATIONS.items():
            if column in missing:
                logger.warning("Adding missing market_signals.%s column", column)
                await conn.execute(text(ddl))
                if column == "source_type":
                    await conn.execute(
                        text(
                            "UPDATE market_signals "
                            "SET source_type = 'unknown' "
                            "WHERE source_type IS NULL OR source_type = ''"
                        )
                    )
                missing.remove(column)

        return {
            "table": "market_signals",
            "missing_after_repair": missing,
            "extra_columns": extra,
        }


async def verify_market_signals_schema() -> dict:
    async with engine.begin() as conn:
        def _get_columns(sync_conn):
            inspector = inspect(sync_conn)
            return {col["name"] for col in inspector.get_columns("market_signals")}

        columns = await conn.run_sync(_get_columns)
        return {
            "expected": sorted(EXPECTED_MARKET_SIGNALS_COLUMNS),
            "actual": sorted(columns),
            "missing": sorted(EXPECTED_MARKET_SIGNALS_COLUMNS - columns),
            "extra": sorted(columns - EXPECTED_MARKET_SIGNALS_COLUMNS),
        }


async def ensure_startup_opportunities_schema() -> dict:
    async with engine.begin() as conn:
        def _get_columns(sync_conn):
            inspector = inspect(sync_conn)
            return {col["name"] for col in inspector.get_columns("startup_opportunities")}

        columns = await conn.run_sync(_get_columns)
        missing = sorted(EXPECTED_STARTUP_OPPORTUNITY_COLUMNS - columns)
        extra = sorted(columns - EXPECTED_STARTUP_OPPORTUNITY_COLUMNS)

        for column, ddl in EXPECTED_STARTUP_OPPORTUNITY_ALTERATIONS.items():
            if column in missing:
                logger.warning("Adding missing startup_opportunities.%s column", column)
                await conn.execute(text(ddl))
                missing.remove(column)

        return {
            "table": "startup_opportunities",
            "missing_after_repair": missing,
            "extra_columns": extra,
        }


async def ensure_collected_documents_schema() -> dict:
    async with engine.begin() as conn:
        def _get_columns(sync_conn):
            inspector = inspect(sync_conn)
            return {col["name"] for col in inspector.get_columns("collected_documents")}

        columns = await conn.run_sync(_get_columns)
        missing = sorted(EXPECTED_COLLECTED_DOCUMENT_COLUMNS - columns)
        extra = sorted(columns - EXPECTED_COLLECTED_DOCUMENT_COLUMNS)

        for column, ddl in EXPECTED_COLLECTED_DOCUMENT_ALTERATIONS.items():
            if column in missing:
                logger.warning("Adding missing collected_documents.%s column", column)
                await conn.execute(text(ddl))
                missing.remove(column)

        return {
            "table": "collected_documents",
            "missing_after_repair": missing,
            "extra_columns": extra,
        }


async def ensure_generated_reports_schema() -> dict:
    async with engine.begin() as conn:
        def _get_columns(sync_conn):
            inspector = inspect(sync_conn)
            return {col["name"] for col in inspector.get_columns("generated_reports")}

        columns = await conn.run_sync(_get_columns)
        missing = sorted(EXPECTED_GENERATED_REPORT_COLUMNS - columns)
        extra = sorted(columns - EXPECTED_GENERATED_REPORT_COLUMNS)

        for column, ddl in EXPECTED_GENERATED_REPORT_ALTERATIONS.items():
            if column in missing:
                logger.warning("Adding missing generated_reports.%s column", column)
                await conn.execute(text(ddl))
                missing.remove(column)

        return {
            "table": "generated_reports",
            "missing_after_repair": missing,
            "extra_columns": extra,
        }


async def verify_startup_opportunities_schema() -> dict:
    async with engine.begin() as conn:
        def _get_columns(sync_conn):
            inspector = inspect(sync_conn)
            return {col["name"] for col in inspector.get_columns("startup_opportunities")}

        columns = await conn.run_sync(_get_columns)
        return {
            "expected": sorted(EXPECTED_STARTUP_OPPORTUNITY_COLUMNS),
            "actual": sorted(columns),
            "missing": sorted(EXPECTED_STARTUP_OPPORTUNITY_COLUMNS - columns),
            "extra": sorted(columns - EXPECTED_STARTUP_OPPORTUNITY_COLUMNS),
        }
