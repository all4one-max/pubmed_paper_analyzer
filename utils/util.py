import asyncio
import logging
import re

logger = logging.getLogger(__name__)


def run_async_task(coro):
    """Wrapper to run a coroutine in a synchronous function."""
    asyncio.run(coro)


def get_paper_id(url: str) -> tuple[str, bool]:
    match = re.search(r"/(\d{8})/", url)
    if not match:
        logger.exception(f"Failed to extract paper ID from URL: {url}")
        return "", False

    return match.group(1), True


async def schedule_task(semaphore: asyncio.Semaphore, func, *args):
    async with semaphore:
        return await func(*args)
