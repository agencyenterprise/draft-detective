"""Tasks the job queue runs.

Nothing in the workflow path defers a job yet. `ping` exists so the queue can be
checked end to end: defer it, and a worker in any API process runs it once.
"""

import logging

from lib.config.task_queue import task_queue

logger = logging.getLogger(__name__)


@task_queue.task(name="ping")
async def ping(message: str) -> str:
    """Log the message and return it, so a test can see which job ran."""
    logger.info("task queue ping: %s", message)
    return message
