.. munggoggo documentation master file, created by
   sphinx-quickstart on Sun Aug 25 06:20:49 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Munggoggo
=========
A modern message based async agent framework
--------------------------------------------
An asyncio based agent platform written in Python and based on RabbitMQ.
Agents are isolated processes which can host multiple parallel running `behaviours` as business
logic and can be deployed as dedicated pods in a kubernetes cluster. WEB communication access to the
agent network via REST/HTTP, websocket and jsonrpc.

Documentation: https://munggoggo.readthedocs.io/en/latest/

.. code:: python

   from mode import Worker
   from behaviour import Behaviour
   from core import Core


   class Agent(Core):
       class PingBehav(Behaviour):
           async def setup(self):
               self.counter = 0

           async def run(self):
               self.counter += 1
               msg = await self.receive()
               if msg:
                   print(f"{self.name}: Message received: {msg.body.decode()}")
               await self.publish(str(self.counter), 'ping')
               await asyncio.sleep(0.9)

       async def setup(self) -> None:
           """ Register behaviour and subscribe to 'ping' topic """
           await self.add_runtime_dependency(self.PingBehav(self, binding_keys=['ping']))


   if __name__ == '__main__':
       Worker(Agent(identity='Agent'), loglevel="info").execute_from_commandline()

This gets you an agent which publishes and reads messages from the message bus on topic: ``ping``.


Features
--------

- asyncio based agent framework
- RabbitMQ messaging backend
- agents can have (multiple) behaviours
- agents and their behaviours form a graph and can be visualized
- communication model: broadcast, point-to-point, topics pub-sub, RPC
- WEB RPC
- React based frontend using WebSockets
- Python >= 3.7
- `ASGI <https://asgi.readthedocs.io>`_ framework, the future of Python web services.
- **A built in testing agent for the web ...**.
- Automatic gzipped web responses.
- Capability of running within uvicorn
- WebSocket support!
- OpenAPI schema generation, with interactive documentation!
- Single-page webapp support!

Web features powered by `Starlette <https://www.starlette.io/>`_.


Installing Munggoggo
--------------------
Install ``docker`` and ``docker-compose``.

.. code-block:: shell

   $ git clone https://github.com/sysid/munggoggo.git
   $ cd munggoggo; pipenv install
   ✨🍰✨

Only **Python 3.7+** is supported.

Start RabbitMQ as communication backend.

.. code-block:: shell

    # prerequisite: docker, docker-compose
    cd rmq
    docker-compose up

Start demo agents and WEB user interface in separate terminals:

.. code-block:: shell

   # terminal1
   python agent1.py

   # terminal2
   python agent2.py

   # terminal3
   python asgi.py

To see the frontend go to ``http://localhost:8000/static/frontend/index.html``.


The Basic Idea
--------------

The basic idea is a combination of several best practices I came accros during my work on agent based systems and consolidate them into a single framework, along with some new ideas I have.
Not everything is 1000% full quality yet so see it as a proof of concept rather than production ready software!

User Guides
-----------
A modern message based async agent framework: version (0.2.5-dev0)

.. toctree::
   :maxdepth: 2

   tour
   core
   behaviour
   asgi


Ideas
-----

- I love `Volttron <https://github.com/VOLTTRON/volttron>`_ ...
- https://github.com/ask/mode!!!
- `Uvicorn <https://www.uvicorn.org/>`_ built-in as a production web server.

.. - https://github.com/javipalanca/spade


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
