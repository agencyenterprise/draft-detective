"""Integration tests for annotation sync, item assignment, submission and admin stats."""

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.annotation import (
    AnnotationItem,
    AnnotationItemKind,
    AnnotationItemStatus,
    AnnotationSet,
)
from lib.models.user import User, UserRole
from lib.services.annotations import admin, service
from lib.services.annotations.catalog import ACTIVE_VOICE, SHOULD_FLAG
from lib.services.annotations.eval_items import AnnotationItemDraft
from lib.services.annotations.models import (
    MAX_TIME_SPENT_MS,
    AnnotationPassage,
    AnnotationSubmission,
)
from lib.services.annotations.sync import sync_items


def _draft(anchor: str, answer: str) -> AnnotationItemDraft:
    return AnnotationItemDraft(
        source_key=f"key-{anchor}",
        kind=(
            AnnotationItemKind.EXPECTED_ISSUE
            if answer == "yes"
            else AnnotationItemKind.DECOY
        ),
        passage=AnnotationPassage(document=f"{anchor}.", anchor=anchor, line=1),
        reference_answers={SHOULD_FLAG: answer},
        reference_explanation="because",
    )


async def _make_user() -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"annotator-{uuid.uuid4()}@example.com",
        name="Annotator",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    return user


async def _delete(model, row_id: uuid.UUID) -> None:
    async with get_async_db_session() as session:
        row = (
            await session.execute(select(model).where(col(model.id) == row_id))
        ).scalar_one_or_none()
        if row is not None:
            await session.delete(row)
            await session.commit()


@pytest_asyncio.fixture
async def users():
    made = [await _make_user() for _ in range(4)]
    yield made
    for user in made:
        await _delete(User, user.id)


@pytest_asyncio.fixture
async def annotation_set():
    slug = f"test-{uuid.uuid4().hex[:8]}"
    async with get_async_db_session() as session:
        row = AnnotationSet(
            slug=slug,
            title="Test set",
            workflow_type="active_voice",
            summary="s",
            guidance="g",
            questions=[q.model_dump() for q in ACTIVE_VOICE.questions],
        )
        session.add(row)
        await session.flush()
        await sync_items(
            session, row.id, slug, [_draft("alpha", "yes"), _draft("beta", "no")]
        )
        await session.commit()
    yield row
    await _delete(AnnotationSet, row.id)


async def _submit(
    item_id: uuid.UUID, user: User, answer: str, comment: str | None = None
):
    return await service.submit_annotation(
        item_id,
        user,
        AnnotationSubmission(answers={SHOULD_FLAG: answer}, comment=comment),
    )


async def _next(annotation_set: AnnotationSet, user: User, skip=()):
    return await service.next_task(annotation_set.slug, user, skip)


@pytest.mark.asyncio
async def test_next_task_hides_reference_and_skips_answered_items(
    annotation_set, users
):
    first = await _next(annotation_set, users[0])
    assert first.item_id is not None and first.passage is not None
    assert "reference" not in first.model_dump_json()

    outcome = await _submit(first.item_id, users[0], "yes")
    assert outcome.answered_by_me == 1

    second = await _next(annotation_set, users[0])
    assert second.item_id not in (None, first.item_id)
    assert (
        await _next(annotation_set, users[0], skip=[second.item_id])
    ).item_id is None


@pytest.mark.asyncio
async def test_next_task_finishes_items_before_starting_new_ones(annotation_set, users):
    task = await _next(annotation_set, users[0])
    assert task.item_id is not None
    await _submit(task.item_id, users[0], "no")

    assert (await _next(annotation_set, users[1])).item_id == task.item_id


@pytest.mark.asyncio
async def test_next_task_moves_on_once_an_item_reaches_the_target(
    annotation_set, users
):
    first = await _next(annotation_set, users[0])
    assert first.item_id is not None
    for user in users[: service.TARGET_ANNOTATIONS]:
        await _submit(first.item_id, user, "yes")

    other = await _next(annotation_set, users[service.TARGET_ANNOTATIONS])
    assert other.item_id not in (None, first.item_id)


@pytest.mark.asyncio
async def test_resubmitting_replaces_answers_and_comment(annotation_set, users):
    task = await _next(annotation_set, users[0])
    assert task.item_id is not None
    await _submit(task.item_id, users[0], "unsure")
    outcome = await _submit(task.item_id, users[0], "no", comment="  reads fine  ")
    assert "reference" not in outcome.model_dump_json()

    [item] = await admin.list_annotated_items(annotation_set.slug)
    assert len(item.annotations) == 1
    assert item.annotations[0].answers == {SHOULD_FLAG: "no"}
    assert item.annotations[0].comment == "reads fine"
    assert item.annotations[0].agrees is (item.reference_answers[SHOULD_FLAG] == "no")


@pytest.mark.asyncio
async def test_submit_rejects_answers_outside_the_options(annotation_set, users):
    task = await _next(annotation_set, users[0])
    assert task.item_id is not None
    with pytest.raises(HTTPException) as error:
        await _submit(task.item_id, users[0], "maybe")
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_admin_stats_count_agreement(annotation_set, users):
    async with get_async_db_session() as session:
        items = {
            i.source_key: i.id
            for i in (
                await session.execute(
                    select(AnnotationItem).where(
                        col(AnnotationItem.set_id) == annotation_set.id
                    )
                )
            ).scalars()
        }
    await _submit(items["key-alpha"], users[0], "yes")
    await _submit(items["key-alpha"], users[1], "no")
    await _submit(items["key-beta"], users[0], "unsure")

    stats = next(
        s for s in await admin.list_set_stats() if s.slug == annotation_set.slug
    )
    contested = await admin.list_annotated_items(
        annotation_set.slug, only_disagreements=True
    )

    assert (stats.agreements, stats.disagreements, stats.abstentions) == (1, 1, 1)
    assert (stats.annotated_items, stats.annotator_count) == (2, 2)
    assert [i.source_key for i in contested] == ["key-alpha"]


@pytest.mark.asyncio
async def test_sync_retires_items_that_left_the_dataset(annotation_set):
    async with get_async_db_session() as session:
        report = await sync_items(
            session, annotation_set.id, annotation_set.slug, [_draft("alpha", "yes")]
        )
        await session.commit()
        rows = (
            await session.execute(
                select(AnnotationItem).where(
                    col(AnnotationItem.set_id) == annotation_set.id
                )
            )
        ).scalars()
        statuses = {row.source_key: row.status for row in rows}

    assert (report.created, report.updated, report.retired) == (0, 1, 1)
    assert statuses == {
        "key-alpha": AnnotationItemStatus.ACTIVE,
        "key-beta": AnnotationItemStatus.RETIRED,
    }


@pytest.mark.asyncio
async def test_submit_stores_an_oversized_time_spent(annotation_set, users):
    task = await _next(annotation_set, users[0])
    assert task.item_id is not None
    await service.submit_annotation(
        task.item_id,
        users[0],
        AnnotationSubmission(answers={SHOULD_FLAG: "yes"}, time_spent_ms=10**12),
    )

    [item] = await admin.list_annotated_items(annotation_set.slug)
    assert item.annotations[0].time_spent_ms == MAX_TIME_SPENT_MS
