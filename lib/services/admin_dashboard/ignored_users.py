"""Users whose activity the dashboard leaves out unless an admin says otherwise."""

from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.user import User
from lib.services.admin_dashboard.models import DashboardIgnoredUser

# The accounts the e2e eval suites run as: the current `DEFAULT_USER_EMAIL` in
# `evals_inspectai/common/api_client.py` (where a change has to be mirrored)
# and the one it had before the product was renamed, which older environments
# still carry. Their runs are machine work: one eval pass starts more
# assessments than every human user does in a week, so counting them makes the
# dashboard describe the test rig rather than adoption.
#
# These are emails to look for, not users that must exist. An environment the
# evals have never touched — production, typically — has neither, and the
# lookup below returns nothing for it: no error, no dangling id, nobody
# ignored.
DEFAULT_IGNORED_USER_EMAILS: tuple[str, ...] = (
    "eval@draft-detective.local",
    "eval@ai-reviewer.local",
)


async def get_default_ignored_users() -> list[DashboardIgnoredUser]:
    """The default ignore list, resolved to the users that actually exist.

    Only emails with a matching row come back. An environment the evals have
    never run against has none, and the dashboard there ignores nobody: the
    list is what is found, not what is configured.
    """
    stmt = (
        select(col(User.id), col(User.name), col(User.email))
        .where(col(User.email).in_(DEFAULT_IGNORED_USER_EMAILS))
        .order_by(col(User.email))
    )
    async with get_async_db_session() as session:
        rows = (await session.execute(stmt)).all()
    return [
        DashboardIgnoredUser(user_id=row[0], name=row[1], email=row[2])
        for row in rows
    ]
