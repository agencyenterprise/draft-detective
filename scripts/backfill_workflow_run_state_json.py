"""Backfill WorkflowRun.state_json from existing LangGraph checkpoints.

One-shot, idempotent. Skips rows that already have state_json so it can run
alongside the dual-write rollout: any row written by the live runner satisfies
the skip, any row whose checkpoint can't be hydrated is logged and counted.

Run with:
    uv run python scripts/backfill_workflow_run_state_json.py

Optional flags:
    --dry-run           Report what would change without writing.
    --batch-size N      Rows per page (default 100).
    --limit N           Stop after N rows (useful for spot-checks).
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Allow running as a plain script: `python scripts/backfill_..._json.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlmodel import col  # noqa: E402

from lib.config.database import get_async_db_session  # noqa: E402
from lib.models.workflow_run import WorkflowRun  # noqa: E402
from lib.services.workflow_runs import (  # noqa: E402
    get_workflow_run_state_by_thread_id,
    persist_workflow_run_state,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("backfill_state_json")


class Stats:
    filled = 0
    already_set = 0
    no_checkpoint = 0
    errored = 0
    scanned = 0

    def log(self) -> None:
        logger.info(
            "scanned=%d filled=%d already_set=%d no_checkpoint=%d errored=%d",
            self.scanned,
            self.filled,
            self.already_set,
            self.no_checkpoint,
            self.errored,
        )


async def _fetch_batch(
    after_id, batch_size: int, only_missing: bool
) -> list[WorkflowRun]:
    async with get_async_db_session() as session:
        stmt = select(WorkflowRun).order_by(col(WorkflowRun.id)).limit(batch_size)
        if only_missing:
            stmt = stmt.where(col(WorkflowRun.state_json).is_(None))
        if after_id is not None:
            stmt = stmt.where(col(WorkflowRun.id) > after_id)
        return list((await session.execute(stmt)).scalars().all())


async def backfill(
    *,
    dry_run: bool,
    batch_size: int,
    limit: Optional[int],
) -> Stats:
    """Walk all WorkflowRuns missing state_json and hydrate from the checkpointer.

    Iteration uses a keyset cursor on `id` so concurrent inserts from the live
    runner don't cause us to skip or revisit rows.
    """
    stats = Stats()
    after_id = None

    while True:
        if limit is not None and stats.scanned >= limit:
            break

        page_size = batch_size
        if limit is not None:
            page_size = min(page_size, limit - stats.scanned)

        runs = await _fetch_batch(after_id, page_size, only_missing=True)
        if not runs:
            break
        after_id = runs[-1].id
        stats.scanned += len(runs)

        for run in runs:
            if run.state_json is not None:
                # Race with live writer. Treat as success.
                stats.already_set += 1
                continue

            try:
                state = await get_workflow_run_state_by_thread_id(
                    run.langgraph_thread_id, run.type
                )
            except Exception as e:
                logger.error(
                    "load failed for run=%s thread=%s: %s",
                    run.id,
                    run.langgraph_thread_id,
                    e,
                )
                stats.errored += 1
                continue

            if state is None:
                # No checkpoint, or unrecognized state schema. Leaving the
                # column NULL is correct — those rows have no state to surface.
                stats.no_checkpoint += 1
                continue

            if dry_run:
                logger.info(
                    "[dry-run] would fill run=%s type=%s (state size=%d keys)",
                    run.id,
                    run.type,
                    len(state.model_dump(mode="json")),
                )
                stats.filled += 1
                continue

            try:
                await persist_workflow_run_state(str(run.id), state)
            except Exception as e:
                # One bad row (e.g. a payload Postgres rejects) must not abort
                # the whole backfill. Log, count, keep walking.
                logger.error("persist failed for run=%s: %s", run.id, e)
                stats.errored += 1
                continue
            logger.info("filled run=%s type=%s", run.id, run.type)
            stats.filled += 1

        # Periodic progress in case the run is long.
        if stats.scanned % (batch_size * 10) == 0:
            stats.log()

    return stats


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--limit", type=int, default=None)
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    if args.dry_run:
        logger.info("DRY RUN — no rows will be modified")
    stats = await backfill(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        limit=args.limit,
    )
    stats.log()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
