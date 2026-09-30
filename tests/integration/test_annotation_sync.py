"""Integration tests for the full annotation sync that runs on every container start."""

import asyncio

import pytest
from sqlalchemy import func, select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.annotation import AnnotationItem, AnnotationItemStatus, AnnotationSet
from lib.services.annotations.catalog import ANNOTATION_SETS
from lib.services.annotations.eval_items import items_from_inventory
from lib.services.annotations.sync import sync_annotation_sets


async def _active_items_by_slug() -> dict[str, int]:
    stmt = (
        select(col(AnnotationSet.slug), func.count())
        .join(AnnotationItem, col(AnnotationItem.set_id) == col(AnnotationSet.id))
        .where(
            col(AnnotationSet.is_active),
            col(AnnotationItem.status) == AnnotationItemStatus.ACTIVE,
        )
        .group_by(col(AnnotationSet.slug))
    )
    async with get_async_db_session() as session:
        return dict((await session.execute(stmt)).tuples().all())


@pytest.mark.asyncio
async def test_concurrent_syncs_take_turns_and_agree():
    """Replicas starting together each run the sync; the advisory lock makes
    them take turns, so neither trips the unique constraints and the second
    finds everything the first wrote."""
    # deactivate_missing=False: other test workers' fixture sets are not in the
    # catalog, and deactivating them mid-test would fail those tests.
    first, second = await asyncio.gather(
        sync_annotation_sets(deactivate_missing=False),
        sync_annotation_sets(deactivate_missing=False),
    )

    assert [r.slug for r in first] == [r.slug for r in second]
    assert min(sum(r.created for r in first), sum(r.created for r in second)) == 0

    expected = {spec.slug: len(items_from_inventory(spec)) for spec in ANNOTATION_SETS}
    active = await _active_items_by_slug()
    assert {slug: active.get(slug, 0) for slug in expected} == expected
