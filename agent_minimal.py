#!/usr/bin/env python
""" for documentation in index.rst """

import asyncio
import logging
import sys
from pathlib import Path

from mode import Worker

from behaviour import Behaviour
from core import Core

sys.path.insert(0, str(Path(__file__).parent / "munggoggo"))

logging.getLogger("aio_pika").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.INFO)



class Agent(Core):
    class PingBehav(Behaviour):
        async def setup(self):
            self.counter = 0

        async def run(self):
            self.counter += 1
            msg = await self.receive()
            if msg:
                print(f"{self.name}: Message received: {msg.body.decode()}")
            await self.publish(str(self.counter), "ping")
            await asyncio.sleep(0.9)

    async def setup(self) -> None:
        """ Register behaviour and subscribe to 'ping' topic """
        await self.add_runtime_dependency(self.PingBehav(self, binding_keys=["ping"]))


if __name__ == "__main__":
    Worker(Agent(identity="Agent"), loglevel="info").execute_from_commandline()
