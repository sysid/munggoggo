import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'munggoggo'))

from behaviour import Behaviour, SqlBehav
from core import Core


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
        loglevel="info",
        logfile=None,
        daemon=True,
        redirect_stdouts=False,
    )

    worker.execute_from_commandline()
