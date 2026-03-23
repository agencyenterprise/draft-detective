"""Integration tests for the get_all_users service function."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.user import User, UserRole
from lib.services.users import get_all_users


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(*, name: str, email: str, role: UserRole = UserRole.USER) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        name=name,
        role=role,
        show_experimental_features=False,
    )


async def _insert(user: User) -> User:
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    return user


async def _delete(user_id: uuid.UUID) -> None:
    async with get_async_db_session() as session:
        stmt = select(User).where(col(User.id) == user_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def tag():
    """Unique tag used as a discriminator across all users created in a test."""
    return str(uuid.uuid4()).replace("-", "")[:12]


@pytest_asyncio.fixture
async def three_users(tag):
    """Alice (ADMIN), Bob (USER), Carol (RAND) — names and emails all contain *tag*."""
    alice = await _insert(_make_user(name=f"Alice {tag}", email=f"alice-{tag}@example.com", role=UserRole.ADMIN))
    bob = await _insert(_make_user(name=f"Bob {tag}", email=f"bob-{tag}@example.com", role=UserRole.USER))
    carol = await _insert(_make_user(name=f"Carol {tag}", email=f"carol-{tag}@example.com", role=UserRole.RAND))

    yield alice, bob, carol

    for u in (alice, bob, carol):
        await _delete(u.id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_users_ordered_by_name(three_users, tag):
    alice, bob, carol = three_users

    results = await get_all_users(search=tag, limit=10)
    names = [u.name for u in results]

    assert names == sorted(names)


@pytest.mark.asyncio
async def test_search_by_name(three_users, tag):
    alice, bob, carol = three_users

    results = await get_all_users(search=f"Alice {tag}", limit=10)
    ids = {u.id for u in results}

    assert alice.id in ids
    assert bob.id not in ids
    assert carol.id not in ids


@pytest.mark.asyncio
async def test_search_by_email(three_users, tag):
    alice, bob, carol = three_users

    results = await get_all_users(search=f"bob-{tag}", limit=10)
    ids = {u.id for u in results}

    assert bob.id in ids
    assert alice.id not in ids
    assert carol.id not in ids


@pytest.mark.asyncio
async def test_search_multi_token_all_match(three_users, tag):
    """All tokens must match — 'Alice <tag>' matches only Alice."""
    alice, bob, carol = three_users

    results = await get_all_users(search=f"Alice {tag}", limit=10)
    ids = {u.id for u in results}

    assert alice.id in ids
    assert bob.id not in ids


@pytest.mark.asyncio
async def test_search_multi_token_partial_no_match(three_users, tag):
    """If one token doesn't match, the user is excluded."""
    alice, bob, carol = three_users

    results = await get_all_users(search=f"Alice nomatch-{tag}", limit=10)
    ids = {u.id for u in results}

    assert alice.id not in ids
    assert bob.id not in ids
    assert carol.id not in ids


@pytest.mark.asyncio
async def test_filter_by_role_admin(three_users, tag):
    alice, bob, carol = three_users

    results = await get_all_users(search=tag, role=UserRole.ADMIN, limit=10)
    ids = {u.id for u in results}

    assert alice.id in ids
    assert bob.id not in ids
    assert carol.id not in ids


@pytest.mark.asyncio
async def test_filter_by_role_rand(three_users, tag):
    alice, bob, carol = three_users

    results = await get_all_users(search=tag, role=UserRole.RAND, limit=10)
    ids = {u.id for u in results}

    assert carol.id in ids
    assert alice.id not in ids
    assert bob.id not in ids


@pytest.mark.asyncio
async def test_filter_by_role_combined_with_search(three_users, tag):
    """search + role must both apply."""
    alice, bob, carol = three_users

    # Search matches alice and bob, but role=ADMIN narrows to alice only
    results = await get_all_users(search=tag, role=UserRole.ADMIN, limit=10)
    ids = {u.id for u in results}

    assert alice.id in ids
    assert bob.id not in ids


@pytest.mark.asyncio
async def test_limit(three_users, tag):
    results = await get_all_users(search=tag, limit=2)

    assert len(results) <= 2


@pytest.mark.asyncio
async def test_offset_paginates(three_users, tag):
    """Fetching with offset skips earlier results."""
    first_page = await get_all_users(search=tag, limit=2, offset=0)
    second_page = await get_all_users(search=tag, limit=2, offset=2)

    first_ids = {u.id for u in first_page}
    second_ids = {u.id for u in second_page}

    # Pages must not overlap
    assert first_ids.isdisjoint(second_ids)


@pytest.mark.asyncio
async def test_offset_beyond_results_returns_empty(three_users, tag):
    results = await get_all_users(search=tag, limit=10, offset=1000)

    ids = {u.id for u in results}
    assert three_users[0].id not in ids
    assert three_users[1].id not in ids
    assert three_users[2].id not in ids


@pytest.mark.asyncio
async def test_no_filters_includes_created_users(three_users, tag):
    """Calling with no filters still returns the created users (among others)."""
    alice, bob, carol = three_users

    # Fetch a large page and check all three are present somewhere
    results = await get_all_users(limit=100)
    ids = {u.id for u in results}

    assert alice.id in ids
    assert bob.id in ids
    assert carol.id in ids
