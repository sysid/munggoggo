import asyncio
import logging
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent / 'munggoggo'))

from behaviour import Behaviour
from core import Core


class SubscribeBehav(Behaviour):
    async def setup(self):
        print(f"Starting {self.name} . . .")

    async def run(self):
        msg = await self.receive()
        if msg:
            print(f"{self.name}: Message: {msg.body.decode()}")

    async def teardown(self):
        print(f"Finished {self.name} . . .")



class Agent2(Core):
    @property
    def behaviour(self) -> Behaviour:
        return SubscribeBehav(self, binding_keys=['ping'])

    async def setup(self) -> None:
        await self.add_runtime_dependency(self.behaviour)



if __name__ == '__main__':
    from mode import Worker
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)

    worker = Worker(
        Agent2(identity='agent2'),
        loglevel="info",
        logfile=None,
        daemon=True,
        redirect_stdouts=False,
    )

    worker.execute_from_commandline()
    # Worker(Agent2(idetity='agent2'), loglevel="info").execute_from_commandline()
