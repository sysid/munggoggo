import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import sys

from dataclasses_json import dataclass_json

from messages import SerializableObject

sys.path.insert(0, str(Path(__file__).parent / 'munggoggo'))

from behaviour import Behaviour, SqlBehav
from core import Core


class MySqlBehav(SqlBehav):
    async def setup(self):
        print(f"Starting {self.name} . . .")
        self.counter = 0

    async def teardown(self):
        # print(f"Finished {self.name} with exit_code {self.exit_code}. . .")
        print(f"Finished {self.name} . . .")


class SqlAgent(Core):

    @property
    def behaviour(self) -> Behaviour:
        topics = ["x.y", "x.z", "a.#"]
        topics = None
        return SqlBehav(self, binding_keys=topics)

    async def setup(self) -> None:
        await self.add_runtime_dependency(self.behaviour)


if __name__ == '__main__':
    from mode import Worker

    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("mode").setLevel(logging.INFO)

    worker = Worker(
        SqlAgent(identity='SqlAgent'),
        loglevel="debug",
        logfile=None,
        daemon=True,
        redirect_stdouts=False,
    )

    worker.execute_from_commandline()
