#!/usr/bin/env python

import logging
import sys
from pathlib import Path

import click

from behaviour import Behaviour, SqlBehav
from core import Core

sys.path.insert(0, str(Path(__file__).parent / "munggoggo"))



class SqlAgent(Core):
    @property
    def behaviour(self) -> Behaviour:
        topics = ["x.y", "x.z", "a.#"]
        topics = None
        return SqlBehav(self, binding_keys=topics)

    async def setup(self) -> None:
        await self.add_runtime_dependency(self.behaviour)


@click.command()
@click.option("--debug", "-d", is_flag=True)
@click.pass_context
def run(ctx, debug):
    loglevel = "info"
    if debug:
        loglevel = "debug"

    from mode import Worker

    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("mode").setLevel(logging.INFO)

    worker = Worker(
        SqlAgent(identity="SqlAgent"),
        loglevel=loglevel,
        logfile=None,
        daemon=True,
        redirect_stdouts=False,
    )
    worker.execute_from_commandline()


if __name__ == "__main__":
    run()
