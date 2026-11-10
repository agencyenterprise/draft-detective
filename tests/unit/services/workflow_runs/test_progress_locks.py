"""The per-(run, name) locks behind get_or_create_progress."""

import uuid

from lib.services.workflow_runs.progress import _get_progress_lock, _progress_locks


def test_same_key_shares_a_lock_while_it_is_in_use() -> None:
    run_id = uuid.uuid4()
    lock = _get_progress_lock(run_id, "node")
    for _ in range(300):
        _get_progress_lock(uuid.uuid4(), "other node")
    assert _get_progress_lock(run_id, "node") is lock


def test_unused_locks_are_dropped() -> None:
    run_id = uuid.uuid4()
    _get_progress_lock(run_id, "node")
    assert (run_id, "node") not in _progress_locks
