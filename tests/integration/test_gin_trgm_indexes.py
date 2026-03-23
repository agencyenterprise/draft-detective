"""
Verifies that GIN trigram indexes exist on all tables that declare them,
and that the query planner uses them for ILIKE pattern matching.

Index existence is checked via pg_indexes (always reliable).
Index usage is verified by disabling seq scans so the planner must use the
indexes if they exist — on a small test dataset the planner would otherwise
prefer a seq scan, masking any misconfiguration.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lib.config.database import get_async_db_session


EXPECTED_INDEXES = [
    ("feedback", "ix_feedback_feedback_text_trgm"),
    ("issues", "ix_issues_title_trgm"),
    ("issues", "ix_issues_description_trgm"),
    ("issues", "ix_issues_long_description_trgm"),
    ("projects", "ix_projects_title_trgm"),
    ("users", "ix_users_name_trgm"),
    ("users", "ix_users_email_trgm"),
]

# Columns searched per table (used to build the EXPLAIN query)
SEARCH_COLUMNS = [
    ("issues", "title"),
    ("issues", "description"),
    ("issues", "long_description"),
    ("feedback", "feedback_text"),
    ("projects", "title"),
    ("users", "name"),
    ("users", "email"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("table,index_name", EXPECTED_INDEXES)
async def test_gin_trgm_index_exists(table: str, index_name: str):
    """Each expected GIN trigram index is present in pg_indexes."""
    async with get_async_db_session() as session:
        result = await session.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE tablename = :table AND indexname = :index"
            ),
            {"table": table, "index": index_name},
        )
        row = result.scalar_one_or_none()

    assert row is not None, (
        f"GIN trigram index '{index_name}' not found on table '{table}'. "
        "Run 'uv run alembic upgrade head' to apply migrations."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("table,column", SEARCH_COLUMNS)
async def test_gin_trgm_index_used_for_ilike(table: str, column: str):
    """With seq scans disabled, the planner uses a GIN index for ILIKE '%term%'."""
    query = f"SELECT 1 FROM {table} WHERE {column} ILIKE '%test%'"  # noqa: S608

    async with get_async_db_session() as session:
        await session.execute(text("SET LOCAL enable_seqscan = off"))
        result = await session.execute(text(f"EXPLAIN {query}"))
        plan_lines = [row[0] for row in result.fetchall()]

    plan = "\n".join(plan_lines)
    assert "Index" in plan or "Bitmap" in plan, (
        f"Expected an index scan on {table}.{column} with seq scans disabled, "
        f"but got:\n{plan}"
    )
