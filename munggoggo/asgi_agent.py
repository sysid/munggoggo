"""
https://github.com/encode/uvicorn/issues/183#issuecomment-515735604

In order to run message-consumers based on aio-pika inside a set of HTTP endpoints served by uvicorn
in the same event loop, it requires to move configuration and initialization of consumers inside the app served by uvicorn.
"""
import asyncio
import logging
import os

import apistar
import uvicorn
import yaml
from aiofile import AIOFile
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from marshmallow import Schema, fields
from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, HTMLResponse, StreamingResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket
from starlette_apispec import APISpecSchemaGenerator
from starlette_jsonrpc import dispatcher

from agent import Agent
from jsonrpc_endpoint import ExampleRpcEndpoint
from messages import ManageBehav
from settings import DEFAULT_CORS_PARAMS, html2, html_sse
from utils import setup_logging

_log = logging.getLogger(__name__)


class PlatformInformationSchema(Schema):
    name = fields.Str()


class JsonRpcSchema(Schema):
    id = fields.Int()
    method = fields.Str()
    jsonrpc = fields.Str()
    params = fields.List(fields.Raw())
    # params = fields.Raw()


class WsController(WebSocketEndpoint):
    """WsController

    Implements websocket communication for AsgiAgent.
    Exposes websocket at Core as ``self.ws``
    """

    counter = 0
    encoding = "json"

    # TODO: only working for one connection: https://github.com/taoufik07/nejma
    async def on_receive(self, websocket, data):
        app = self.scope.get("app")
        core = app.agent
        _log.debug(f"ws.receive: {data}")

        msg = dict(msg=f"Message text was: {data['command']}")
        originator = data.get("originator")
        agent = originator.get("name").split(".")[0]
        behav = originator.get("name").split(".")[1]
        command = data.get("command")
        obj = ManageBehav(behav=behav, command="stop",)

        # map commands
        if command == "Stop":
            obj.command = "stop"
        else:
            obj.command = "start"

        result = await core.call(obj.to_rpc(), target=agent)
        core.log.info(f"rpc result: {result}")
        # await websocket.send_json(msg)

    async def on_connect(self, websocket):
        app = self.scope.get("app")
        app.ws = websocket  # make ws available at AsgiAgent
        core = app.agent
        await websocket.accept()
        msg = dict(msg=f"Connected with {core.identity}")
        await websocket.send_json(msg)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        app = self.scope.get("app")
        app.ws = None
        core = app.agent
        await websocket.close(code=1000)
        core.log.info(f"Webscoket connection closed by client {websocket.client}")


class AsgiAgent(Starlette):
    """AsgiAgent

    Wraps agent into Starlette ASGI application.
    Implements jsonrpc interface::

         curl -X POST -H "content-type: application/json" -d '{"method":"example_rpc_method","params":[1,2],"jsonrpc":"2.0","id":1}' http://localhost:8000/jsonrpc

    Provides OPENAPI (Swagger) documention of exposed endpoints via https://apispec.readthedocs.io/en/latest/::

        http://0.0.0.0:8000/openapi

    Serves static files from ./static::

        http://0.0.0.0:8000/static/schema.yaml

    Exposes websocket at::

        http://0.0.0.0:8000/ws.

    """

    def __init__(self, agent, *args, **kwargs):
        super(AsgiAgent, self).__init__(*args, **kwargs)
        self.debug = kwargs.get("debug", False)

        self.ws = None
        self.agent = agent
        self.agent.web = self
        self.add_event_handler("startup", self.agent.start)
        self.add_event_handler("shutdown", self.agent.stop)

        # Gotcha: not working with SSE streaming
        # self.add_middleware(GZipMiddleware, minimum_size=1000)

        self.cors = True  # TODO: make it configurable
        self.cors_params = DEFAULT_CORS_PARAMS
        if self.cors:
            self.add_middleware(CORSMiddleware, **self.cors_params)

        self.add_middleware(ServerErrorMiddleware, debug=self.debug)

        self.allowed_hosts = ["*"]
        self.add_middleware(TrustedHostMiddleware, allowed_hosts=self.allowed_hosts)

        self.hsts_enabled = kwargs.get("hsts_enbled", False)
        if self.hsts_enabled:
            self.add_middleware(HTTPSRedirectMiddleware)

        self.add_route("/", self.homepage, methods=["GET"], include_in_schema=True)
        self.add_route(
            path=f"/jsonrpc", route=ExampleRpcEndpoint, include_in_schema=True
        )
        self.add_route(path=f"/openapi", route=self.openapi, include_in_schema=False)
        self.add_route(path=f"/sse_html", route=self.sse_html, include_in_schema=True)
        self.add_route(path=f"/sse", route=self.sse, include_in_schema=False)
        self.add_route(path=f"/ws_html", route=self.ws_html, include_in_schema=False)
        self.add_websocket_route(path="/ws", route=WsController, name="ws")

        self.rpc_dispatcher = dispatcher

        ################################################################################
        # OpenAPI
        ################################################################################
        self.schema_generator = None
        self.schema_models = dict()
        self.add_schema("PlatformInformation", PlatformInformationSchema)
        # self.add_schema('JsonRpc', JsonRpcSchema)  # TODO: fix openapi spec with model definition

        ################################################################################
        # static files
        ################################################################################
        self.static_dir = "static/"
        self.static_route = f"/{self.static_dir}"

        # Make the static/templates directory if they don't exist.
        for _dir in (self.static_dir,):
            if _dir is not None:
                os.makedirs(_dir, exist_ok=True)

        if self.static_dir is not None:
            _log.info(f"Configuring route {self.static_route}")
            self.mount(
                self.static_route,
                app=StaticFiles(directory=self.static_dir, packages=None),
                name="static",
            )

    async def homepage(self, request):
        """home
        ---
        description: Home
        responses:
            200:
                content:
                    application/json:
                        schema: PlatformInformationSchema
        """
        return JSONResponse(PlatformInformationSchema().dump({"name": "ASGI Agent"}))

    def ws_html(self, request):
        return HTMLResponse(html2)

    def sse_html(self, request):
        return HTMLResponse(html_sse)

    async def sse(self, request):
        async def slow_numbers(minimum, maximum):
            yield ("<html><body><ul>")
            for number in range(minimum, maximum + 1):
                yield "<li>%d</li>" % number
                await asyncio.sleep(0.5)
            yield ("</ul></body></html>")

        # generator = slow_numbers(1, 5)
        generator = self.agent.publish_sse(interval=1)

        headers = {
            "Content-Type": "text/event-stream",
            "Content-Encoding": "identity",  # TODO: remove
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(generator, headers=headers, media_type="text/html")

    async def openapi(self, request):
        # noinspection PyTypeChecker
        self.schema_generator = APISpecSchemaGenerator(
            APISpec(
                title="Example API",
                version="1.0",
                openapi_version="3.0.0",
                info={"description": "ASGI Agent"},
                plugins=[MarshmallowPlugin()],
            )
        )  # type: ignore

        # add opneapi models based on Marshammallow
        for name, schema in self.schema_models.items():
            self.schema_generator.spec.components.schema(name, schema=schema)

        # create spec file for display via apistar
        schema = yaml.dump(
            self.schema_generator.get_schema(routes=self.routes),
            default_flow_style=False,
        )

        # TODO: fix (Deactivated due to: ValueError: call stack is not deep enough)
        # async with AIOFile('static/schema.yaml', 'w+') as afp:
        #     await afp.write(schema)  # BUG: ValueError: call stack is not deep enough

        return HTMLResponse(
            apistar.docs(
                schema,
                schema_url="/static/schema.yaml",
                theme="swaggerui",
                static_url="/static/",
            )
        )

    def add_schema(
        self, name: str, schema: Schema, check_existing: bool = True
    ) -> None:
        """Adds a mashmallow schema to the API specification.

        :param name: ClassName
        :param schema: SchemaName of Class
        :param check_existing: make sure it is only added once
        """
        if check_existing:
            assert name not in self.schema_models

        self.schema_models[name] = schema

    def schema(self, name, **options):
        """Decorator for creating new routes around function and class definitions.

           Caveat: agent instance must exist in order to use it

        Usage::

            @asgi_agent.schema("Pet")
            class PetSchema(Schema):
                name = fields.Str()
        """

        def decorator(f):
            self.add_schema(name=name, schema=f, **options)
            return f

        return decorator

    async def ws(self, ws):
        await ws.accept()
        await ws.send_text(f"Connected via ws with {self.agent.identity}")
        await ws.close()


if __name__ == "__main__":
    logging.getLogger("aio_pika").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("core").setLevel(logging.INFO)
    logging.getLogger("mode").setLevel(logging.INFO)
    logging.getLogger("handler").setLevel(logging.INFO)

    setup_logging(logging.DEBUG)

    config = dict(UPDATE_PEER_INTERVAL=1.0)
    agent = Agent(identity="AsgiAgent", config=config)
    app = AsgiAgent(agent=agent, debug=True)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
