"""`scripts/migration_lag.py` warns when the database isn't at the checkout's head."""

from scripts.migration_lag import describe_lag, libpq_url

KNOWN = {"a1", "b2", "c3"}


def test_silent_at_head() -> None:
    assert describe_lag({"c3"}, {"c3"}, KNOWN, "ai_reviewer") is None


def test_warns_when_behind() -> None:
    warning = describe_lag({"b2"}, {"c3"}, KNOWN, "ai_reviewer")

    assert warning is not None
    assert "is behind" in warning
    assert "at b2" in warning
    assert "head is c3" in warning


def test_warns_when_database_has_another_branchs_migration() -> None:
    warning = describe_lag({"zz"}, {"c3"}, KNOWN, "ai_reviewer")

    assert warning is not None
    assert "another branch" in warning
    assert "usually harmless" in warning


def test_mixed_known_and_unknown_counts_as_another_branch() -> None:
    warning = describe_lag({"c3", "zz"}, {"c3"}, KNOWN, "ai_reviewer")

    assert warning is not None
    assert "another branch" in warning


def test_silent_at_several_heads() -> None:
    assert (
        describe_lag({"b2", "c3"}, {"b2", "c3"}, KNOWN | {"b2"}, "ai_reviewer") is None
    )


def test_warns_on_an_empty_database() -> None:
    warning = describe_lag(set(), {"c3"}, KNOWN, "ai_reviewer")

    assert warning is not None
    assert "at none" in warning


def test_libpq_url_drops_the_sqlalchemy_driver() -> None:
    url = libpq_url("postgresql+psycopg://user:pw@localhost:5432/ai_reviewer")

    assert url == "postgresql://user:pw@localhost:5432/ai_reviewer"
