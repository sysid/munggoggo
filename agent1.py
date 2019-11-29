#!/usr/bin/env python

import asyncio
import logging
import sys
from pathlib import Path

from behaviour import Behaviour
from core import Core

sys.path.insert(0, str(Path(__file__).parent / "munggoggo"))



class PingBehav(Behaviour):
    async def setup(self):
        print(f"Starting {self.name} . . .")
        self.counter = 0

    async def run(self):
        self.counter += 1
        msg = await self.receive()
        if msg:
            print(
                f"{self.name}: Message: {msg.body.decode()} from: {msg.app_id}, qsize: {self.queue.qsize()}"
            )  # TODO: log.warning ?!!
        print(f"{self.name}: Counter: {self.counter}")
        await self.publish(str(self.counter), "ping")
        await asyncio.sleep(
            0.9
        )  # >1 triggers log messages: syncio:poll 999.294 ms took 1000.570 ms: timeout

    async def teardown(self):
        # print(f"Finished {self.name} with exit_code {self.exit_code}. . .")
        print(f"Finished {self.name} . . .")


class Agent1(Core):
    @property
    def behaviour(self) -> Behaviour:
        return PingBehav(self, binding_keys=["ping"])

    async def setup(self) -> None:
        await self.add_runtime_dependency(self.behaviour)


if __name__ == "__main__":
    from mode import Worker

    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)

    worker = Worker(
        Agent1(identity="agent1"),
        loglevel="info",
        logfile=None,
        daemon=True,
        redirect_stdouts=False,
    )

    worker.execute_from_commandline()
