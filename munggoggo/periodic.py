import asyncio
import datetime
from contextlib import suppress


class RunAt:
    def __init__(self, coro):
        self.coro = coro

    @staticmethod
    async def wait_for(dt: datetime):
        # sleep until the specified datetime
        while True:
            now = datetime.datetime.now()
            remaining = (dt - now).total_seconds()
            if remaining < 86400:
                break
            # asyncio.sleep doesn't like long sleeps, so don't sleep more
            # than a day at a time
            await asyncio.sleep(86400)
        await asyncio.sleep(remaining)

    async def run_at(self, dt):
        await self.wait_for(dt)
        return await self.coro()


class Periodic:
    def __init__(self, func, time):
        self.func = func
        self.time = time
        self.is_started = False
        self._task = None

    async def start(self):
        if not self.is_started:
            self.is_started = True
            # Start task to call func periodically:
            self._task = asyncio.create_task(self._run())

    async def stop(self):
        if self.is_started:
            self.is_started = False
            # Stop task and await it stopped:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self):
        while True:
            await asyncio.sleep(self.time)
            self.func()


async def main():
    p = Periodic(lambda: print("test"), 1)
    try:
        print("Start")
        await p.start()
        await asyncio.sleep(3.1)

        print("Stop")
        await p.stop()
        await asyncio.sleep(3.1)

        print("Start")
        await p.start()
        await asyncio.sleep(3.1)
    finally:
        await p.stop()  # we should stop task finally


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
