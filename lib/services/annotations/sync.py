"""Write the annotation catalog and its eval-built items to the database.

Idempotent: sets are upserted by slug and items by source key. An item whose
passage left the dataset is retired, never deleted, so its annotations stay.
A set dropped from the catalog is deactivated the same way.

Run after changing a dataset or the catalog::

    uv run python -m lib.services.annotations.sync
"""

import asyncio
import uuid
from typing import Sequence

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.annotation import AnnotationItem, AnnotationItemStatus, AnnotationSet
from lib.services.annotations.catalog import ANNOTATION_SETS, AnnotationSetSpec
from lib.services.annotations.eval_items import (
    AnnotationItemDraft,
    items_from_inventory,
)


class SetSyncReport(BaseModel):
    slug: str
    created: int
    updated: int
    retired: int


async def _upsert_set(session: AsyncSession, spec: AnnotationSetSpec) -> AnnotationSet:
    stmt = select(AnnotationSet).where(col(AnnotationSet.slug) == spec.slug)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = AnnotationSet(slug=spec.slug)
        session.add(row)
    row.title = spec.title
    row.workflow_type = spec.workflow_type
    row.summary = spec.summary
    row.guidance = spec.guidance
    row.questions = [q.model_dump() for q in spec.questions]
    row.is_active = True
    await session.flush()
    return row


def _apply_draft(item: AnnotationItem, draft: AnnotationItemDraft) -> None:
    item.kind = draft.kind
    item.status = AnnotationItemStatus.ACTIVE
    item.payload = draft.passage.model_dump()
    item.reference_answers = draft.reference_answers
    item.reference_explanation = draft.reference_explanation


async def sync_items(
    session: AsyncSession,
    set_id: uuid.UUID,
    slug: str,
    drafts: Sequence[AnnotationItemDraft],
) -> SetSyncReport:
    """Make the set's active items exactly ``drafts``."""
    stmt = select(AnnotationItem).where(col(AnnotationItem.set_id) == set_id)
    existing = {
        item.source_key: item for item in (await session.execute(stmt)).scalars()
    }
    wanted = {draft.source_key for draft in drafts}
    created = 0
    for draft in drafts:
        item = existing.get(draft.source_key)
        if item is None:
            item = AnnotationItem(set_id=set_id, source_key=draft.source_key)
            session.add(item)
            created += 1
        _apply_draft(item, draft)
    retired = 0
    for key, item in existing.items():
        if key not in wanted and item.status == AnnotationItemStatus.ACTIVE:
            item.status = AnnotationItemStatus.RETIRED
            retired += 1
    await session.flush()
    return SetSyncReport(
        slug=slug, created=created, updated=len(drafts) - created, retired=retired
    )


async def _deactivate_others(session: AsyncSession, slugs: set[str]) -> None:
    stmt = select(AnnotationSet).where(col(AnnotationSet.slug).not_in(slugs))
    for row in (await session.execute(stmt)).scalars():
        row.is_active = False


async def sync_annotation_sets(
    specs: Sequence[AnnotationSetSpec] = ANNOTATION_SETS,
) -> list[SetSyncReport]:
    """Write every set and its items in one transaction."""
    reports = []
    async with get_async_db_session() as session:
        for spec in specs:
            row = await _upsert_set(session, spec)
            drafts = items_from_inventory(spec)
            reports.append(await sync_items(session, row.id, spec.slug, drafts))
        await _deactivate_others(session, {spec.slug for spec in specs})
        await session.commit()
    return reports


async def main() -> None:
    for report in await sync_annotation_sets():
        print(
            f"{report.slug}: {report.created} created, {report.updated} updated, {report.retired} retired"
        )


if __name__ == "__main__":
    asyncio.run(main())
