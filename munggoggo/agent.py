from __future__ import (
    annotations,
)  # make all type hints be strings and skip evaluating them

from behaviour import Behaviour
from core import Core


class Agent(Core):
    """Demo Agent

    Use this agent as an example with simple behaviour.
    Agent identity must be unique within agent network.
    Run it with the Worker class::

        from mode import Worker

        worker = Worker(
            Agent(identity='agent'),
            loglevel="info",
            logfile=None,
            daemon=True,
        )

        worker.execute_from_commandline()

    Stop the agent wih CTRL-C
    """

    async def setup(self) -> None:
        """ setup is run during agent initialization
            Put in your all setup and behaviours you need.
        """
        await self.add_runtime_dependency(self.behaviour)

    @property
    def behaviour(self) -> Behaviour:
        return Behaviour(
            self,
            binding_keys=self.config.get("binding_keys"),
            configure_rpc=self.config.get("configure_rpc")
        )

    def create_graph(self) -> None:
        print('APP STARTING')
        import pydot
        import io
        o = io.StringIO()
        beacon = self.beacon.root or self.beacon
        beacon.as_graph().to_dot(o)
        graph, = pydot.graph_from_dot_data(o.getvalue())
        print('WRITING GRAPH TO image.png')
        with open('image.png', 'wb') as fh:
            fh.write(graph.create_png())


if __name__ == '__main__':
    from mode import Worker

    config = {
        "binding_keys": ['x.y'],
        "configure_rpc": True
    }

    worker = Worker(
        Agent(identity='agent', config=config),
        loglevel="info",
        logfile=None,
        daemon=True,
        redirect_stdouts=False,
    )

    worker.execute_from_commandline()

    # Worker(Agent(identity='agent'), loglevel="info").execute_from_commandline()

