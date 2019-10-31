import asyncio
from datetime import datetime, timedelta

import pytest

from periodic import Periodic, RunAt


@pytest.mark.asyncio
async def test_run_at():
    async def xxx():
        print(f"Hallo {datetime.now()}")

    start = datetime.now()
    print(f"\nStarting: {start}")
    ra = RunAt(xxx)
    await ra.run_at(start + timedelta(seconds=1))


@pytest.mark.asyncio
async def test_periodic():
    print("\nStarting:")
    p = Periodic(lambda: print("test"), 1)
    try:
        await p.start()
        await asyncio.sleep(3.1)
    finally:
        await p.stop()
