import asyncio
import logging
from pathlib import Path

import sys

import uvicorn
from marshmallow import Schema, fields

import inspect

from starlette.responses import PlainTextResponse

sys.path.insert(0, str(Path(__file__).parent / 'munggoggo'))

import subsystem
from asgi_agent import AsgiAgent
from behaviour import Behaviour
from core import Core

logging.getLogger("aio_pika").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)


class PingBehav(Behaviour):
    async def setup(self):
        print(f"Starting {self.name} . . .")
        self.counter = 0

    @subsystem.expose
    async def say_hello(self, name: str) -> str:
        """rpc method 'say_hello'
        curl -X POST -H "content-type: application/json" -d '{"method":"say_hello","params":["YourName"],"jsonrpc":"2.0","id":1}' http://localhost:8000/jsonrpc
        """
        self.log.info(
            f"'say_hello': Signature: {inspect.signature(self.example_rpc_method)}"
        )
        self.log.info(f"'say_hello' called with: {name}")
        return f"Hello {name}."

    async def run(self):
        self.counter += 1
        async for msg in self.receive_all():
            print(f"{self.name}: Message: {msg.body.decode()} from: {msg.app_id} qsize: {self.queue.qsize()}")
        await self.publish(str(self.counter), 'ping')
        await asyncio.sleep(
            0.9
        )

    async def teardown(self):
        print(f"Finished {self.name} . . .")


class Agent(Core):

    @property
    def behaviour(self) -> Behaviour:
        return PingBehav(self, binding_keys=['ping'], configure_rpc=True)

    async def setup(self) -> None:
        await self.add_runtime_dependency(self.behaviour)


app = AsgiAgent(
    agent=Agent(identity="starlette", config=dict(UPDATE_PEER_INTERVAL=1.0)),
    debug=True
)


@app.route('/hello')
async def hello(request):
    """hello
    ---
    description: Hello
    responses:
        200:
            content:
                text/plain:
                    schema: HelloSchema
    """
    agent = request.app.agent
    behav = agent.get_behaviour('PingBehav')
    return PlainTextResponse(f'Hello, world, received already {behav.counter} pings from other agent.')


@app.schema('HelloSchema')
class HelloSchema(Schema):
    answer = fields.Str()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
