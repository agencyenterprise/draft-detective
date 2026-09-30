"""Annotation for users: the sets, the next item to judge, and saving answers."""

import uuid
from datetime import datetime, timezone
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
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
    AnnotationOutcome,
    AnnotationPassage,
    AnnotationQuestion,
    AnnotationSetSummary,
    AnnotationSubmission,
    AnnotationTask,
    AnnotationTaskSet,
)


def validate_answers(
    answers: dict[str, str], questions: Sequence[AnnotationQuestion]
) -> None:
    """Raise ValueError unless ``answers`` answers every question with one of its options."""
    for question in questions:
        allowed = {option.value for option in question.options}
        if answers.get(question.key) not in allowed:
            raise ValueError(f"'{question.key}' must be one of {sorted(allowed)}")
    extra = set(answers) - {q.key for q in questions}
    if extra:
        raise ValueError(f"unknown questions: {sorted(extra)}")


# Annotations per item before the set moves on: three gives a majority.
TARGET_ANNOTATIONS = 3


def questions_of(annotation_set: AnnotationSet) -> list[AnnotationQuestion]:
    return [AnnotationQuestion.model_validate(q) for q in annotation_set.questions]


def _active_items(set_id: uuid.UUID | None = None):
    stmt = select(AnnotationItem).where(
        col(AnnotationItem.status) == AnnotationItemStatus.ACTIVE
    )
    return stmt if set_id is None else stmt.where(col(AnnotationItem.set_id) == set_id)


async def _progress(
    session: AsyncSession, user_id: uuid.UUID
) -> dict[uuid.UUID, tuple[int, int]]:
    """(active items, items the user answered) per set."""
    items_stmt = (
        select(col(AnnotationItem.set_id), func.count())
        .where(col(AnnotationItem.status) == AnnotationItemStatus.ACTIVE)
        .group_by(col(AnnotationItem.set_id))
    )
    answered_stmt = (
        select(col(AnnotationItem.set_id), func.count())
        .join(Annotation, col(Annotation.item_id) == col(AnnotationItem.id))
        .where(
            col(AnnotationItem.status) == AnnotationItemStatus.ACTIVE,
            col(Annotation.user_id) == user_id,
        )
        .group_by(col(AnnotationItem.set_id))
    )
    totals = dict((await session.execute(items_stmt)).tuples().all())
    answered = dict((await session.execute(answered_stmt)).tuples().all())
    return {
        set_id: (count, answered.get(set_id, 0)) for set_id, count in totals.items()
    }


async def list_sets(user: User) -> list[AnnotationSetSummary]:
    stmt = (
        select(AnnotationSet)
        .where(col(AnnotationSet.is_active))
        .order_by(col(AnnotationSet.title))
    )
    async with get_async_db_session() as session:
        sets = (await session.execute(stmt)).scalars().all()
        progress = await _progress(session, user.id)
    return [
        AnnotationSetSummary(
            slug=s.slug,
            title=s.title,
            summary=s.summary,
            workflow_type=s.workflow_type,
            item_count=progress.get(s.id, (0, 0))[0],
            answered_by_me=progress.get(s.id, (0, 0))[1],
        )
        for s in sets
    ]


async def load_set(session: AsyncSession, slug: str) -> AnnotationSet:
    """The active set with this slug, or a 404."""
    stmt = select(AnnotationSet).where(
        col(AnnotationSet.slug) == slug, col(AnnotationSet.is_active)
    )
    annotation_set = (await session.execute(stmt)).scalar_one_or_none()
    if annotation_set is None:
        raise HTTPException(status_code=404, detail="Annotation set not found")
    return annotation_set


async def _pick_item(
    session: AsyncSession,
    set_id: uuid.UUID,
    user_id: uuid.UUID,
    skip: Sequence[uuid.UUID],
) -> AnnotationItem | None:
    """An item the user has not answered. Items short of TARGET_ANNOTATIONS come
    first, the most-answered of them first, so each item reaches a majority
    before annotators spread thin across the set; the rest follow at random."""
    counts = (
        select(col(Annotation.item_id), func.count().label("n"))
        .group_by(col(Annotation.item_id))
        .subquery()
    )
    answered = func.coalesce(counts.c.n, 0)
    reached_target = answered >= TARGET_ANNOTATIONS
    mine = select(col(Annotation.item_id)).where(col(Annotation.user_id) == user_id)
    stmt = (
        _active_items(set_id)
        .outerjoin(counts, counts.c.item_id == col(AnnotationItem.id))
        .where(col(AnnotationItem.id).not_in(mine))
        .order_by(
            case((reached_target, 1), else_=0),
            case((reached_target, 0), else_=answered).desc(),
            func.random(),
        )
        .limit(1)
    )
    if skip:
        stmt = stmt.where(col(AnnotationItem.id).not_in(skip))
    return (await session.execute(stmt)).scalar_one_or_none()


async def next_task(
    slug: str, user: User, skip: Sequence[uuid.UUID] = ()
) -> AnnotationTask:
    async with get_async_db_session() as session:
        annotation_set = await load_set(session, slug)
        item = await _pick_item(session, annotation_set.id, user.id, skip)
        progress = await _progress(session, user.id)
    total, answered = progress.get(annotation_set.id, (0, 0))
    return AnnotationTask(
        set=AnnotationTaskSet(
            slug=annotation_set.slug,
            title=annotation_set.title,
            guidance=annotation_set.guidance,
            questions=questions_of(annotation_set),
        ),
        item_id=item.id if item else None,
        passage=AnnotationPassage.model_validate(item.payload) if item else None,
        item_count=total,
        answered_by_me=answered,
    )


async def _item_with_set(
    session: AsyncSession, item_id: uuid.UUID
) -> tuple[AnnotationItem, AnnotationSet]:
    stmt = (
        select(AnnotationItem, AnnotationSet)
        .join(AnnotationSet, col(AnnotationSet.id) == col(AnnotationItem.set_id))
        .where(col(AnnotationItem.id) == item_id)
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Annotation item not found")
    return row._tuple()


async def _save(
    session: AsyncSession,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    submission: AnnotationSubmission,
) -> None:
    """Upsert, so a double click or a second tab cannot trip the unique constraint.
    A resubmission keeps the time it took to answer the first time."""
    now = datetime.now(timezone.utc)
    comment = (submission.comment or "").strip() or None
    stmt = (
        insert(Annotation)
        .values(
            item_id=item_id,
            user_id=user_id,
            answers=submission.answers,
            comment=comment,
            time_spent_ms=submission.time_spent_ms,
        )
        .on_conflict_do_update(
            constraint="uq_annotations_item_user",
            set_={"answers": submission.answers, "comment": comment, "updated_at": now},
        )
    )
    await session.execute(stmt)


async def submit_annotation(
    item_id: uuid.UUID, user: User, submission: AnnotationSubmission
) -> AnnotationOutcome:
    """Save the user's answers, replacing earlier ones."""
    async with get_async_db_session() as session:
        item, annotation_set = await _item_with_set(session, item_id)
        try:
            validate_answers(submission.answers, questions_of(annotation_set))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        await _save(session, item.id, user.id, submission)
        await session.commit()
        progress = await _progress(session, user.id)
    _, answered = progress.get(annotation_set.id, (0, 0))
    return AnnotationOutcome(item_id=item.id, answered_by_me=answered)
