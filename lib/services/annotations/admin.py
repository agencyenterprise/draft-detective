"""Annotation results for admins: agreement with the eval datasets, per set and per item.

Volumes are small (a few hundred items, a handful of annotations each), so the
rows are loaded once and aggregated in Python rather than in SQL.
"""

import uuid
from collections import defaultdict
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.annotation import (
    Annotation,
    AnnotationItem,
    AnnotationItemStatus,
    AnnotationSet,
)
from lib.models.user import User
from lib.services.annotations.models import (
    AnnotatedItem,
    AnnotationPassage,
    AnnotationQuestion,
    AnnotationRecord,
    AnnotationSetStats,
)
from lib.services.annotations.service import load_set, questions_of


def agrees_with_reference(
    answers: dict[str, str],
    reference: dict[str, str],
    questions: Sequence[AnnotationQuestion],
) -> Optional[bool]:
    """True when every referenced question is answered the same way, False when
    any is answered differently, None when the user abstained on any of them."""
    abstain = {q.key: q.abstain_value for q in questions}
    for key, expected in reference.items():
        answer = answers.get(key)
        if answer is None or answer == abstain.get(key):
            return None
        if answer != expected:
            return False
    return True


def _record(
    annotation: Annotation,
    user: User,
    item: AnnotationItem,
    questions: Sequence[AnnotationQuestion],
) -> AnnotationRecord:
    return AnnotationRecord(
        user_name=user.name,
        user_email=user.email,
        answers=annotation.answers,
        agrees=agrees_with_reference(
            annotation.answers, item.reference_answers, questions
        ),
        comment=annotation.comment,
        time_spent_ms=annotation.time_spent_ms,
        created_at=annotation.created_at,
    )


def _tally(records: Sequence[AnnotationRecord]) -> tuple[int, int, int]:
    agreements = sum(1 for r in records if r.agrees is True)
    disagreements = sum(1 for r in records if r.agrees is False)
    return agreements, disagreements, len(records) - agreements - disagreements


async def _records_by_item(
    session: AsyncSession, set_id: uuid.UUID, questions: Sequence[AnnotationQuestion]
) -> dict[uuid.UUID, list[AnnotationRecord]]:
    stmt = (
        select(Annotation, User, AnnotationItem)
        .join(User, col(User.id) == col(Annotation.user_id))
        .join(AnnotationItem, col(AnnotationItem.id) == col(Annotation.item_id))
        .where(col(AnnotationItem.set_id) == set_id)
        .order_by(col(Annotation.created_at))
    )
    records: dict[uuid.UUID, list[AnnotationRecord]] = defaultdict(list)
    for annotation, user, item in (await session.execute(stmt)).tuples():
        records[item.id].append(_record(annotation, user, item, questions))
    return records


async def _set_stats(
    session: AsyncSession, annotation_set: AnnotationSet
) -> AnnotationSetStats:
    questions = questions_of(annotation_set)
    records = await _records_by_item(session, annotation_set.id, questions)
    items_stmt = select(col(AnnotationItem.id)).where(
        col(AnnotationItem.set_id) == annotation_set.id,
        col(AnnotationItem.status) == AnnotationItemStatus.ACTIVE,
    )
    active_ids = set((await session.execute(items_stmt)).scalars())
    flat = [r for rs in records.values() for r in rs]
    agreements, disagreements, abstentions = _tally(flat)
    return AnnotationSetStats(
        slug=annotation_set.slug,
        title=annotation_set.title,
        item_count=len(active_ids),
        annotated_items=len(active_ids & set(records)),
        annotation_count=len(flat),
        annotator_count=len({r.user_email for r in flat}),
        agreements=agreements,
        disagreements=disagreements,
        abstentions=abstentions,
    )


async def list_set_stats() -> list[AnnotationSetStats]:
    stmt = (
        select(AnnotationSet)
        .where(col(AnnotationSet.is_active))
        .order_by(col(AnnotationSet.title))
    )
    async with get_async_db_session() as session:
        return [
            await _set_stats(session, s)
            for s in (await session.execute(stmt)).scalars().all()
        ]


def _annotated_item(
    item: AnnotationItem, records: list[AnnotationRecord]
) -> AnnotatedItem:
    agreements, disagreements, abstentions = _tally(records)
    return AnnotatedItem(
        item_id=item.id,
        source_key=item.source_key,
        kind=item.kind,
        passage=AnnotationPassage.model_validate(item.payload),
        reference_answers=item.reference_answers,
        reference_explanation=item.reference_explanation,
        annotations=records,
        agreements=agreements,
        disagreements=disagreements,
        abstentions=abstentions,
    )


async def list_annotated_items(
    slug: str, only_disagreements: bool = False
) -> list[AnnotatedItem]:
    """Every item with at least one annotation, the most contested first.
    Retired items are included: their labels still describe the passage they showed."""
    async with get_async_db_session() as session:
        annotation_set = await load_set(session, slug)
        records = await _records_by_item(
            session, annotation_set.id, questions_of(annotation_set)
        )
        stmt = select(AnnotationItem).where(col(AnnotationItem.id).in_(list(records)))
        items = [
            _annotated_item(item, records[item.id])
            for item in (await session.execute(stmt)).scalars()
        ]
    if only_disagreements:
        items = [item for item in items if item.disagreements > 0]
    return sorted(
        items, key=lambda i: (-i.disagreements, -len(i.annotations), i.source_key)
    )
