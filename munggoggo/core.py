from __future__ import (
    annotations,
)  # make all type hints be strings and skip evaluating them

import asyncio
import io
import json
import logging
import re
import uuid
from datetime import datetime
from types import TracebackType
from typing import TYPE_CHECKING, Optional, Type, Any

import sys
from aio_pika import IncomingMessage, Message, connect_robust, ExchangeType
from aiormq import ChannelLockedResource
from async_timeout import timeout

from handler import Registry, SystemHandler, RmqMessageTypes
from messages import RpcMessage, RpcError, TraceStoreMessage, PingControl, ServiceStatus, CoreStatus
from mode import Service, ServiceT
from mode.utils.logging import CompositeLogger
from mode.utils.times import want_seconds
from mode.utils.types.trees import NodeT
from settings import (
    RMQ_URL,
    BINDING_KEY_FANOUT,
    BINDING_KEY_TOPIC,
    TIMEOUT,
)
from trace import TraceStore
from utils import setup_logging, JSONType

sys.setrecursionlimit(1500)  # TODO remove

# avoid circular imports
if TYPE_CHECKING:
    pass


class MyService(Service):
    """Base class for agent and behaviours
        Defines async service framework.
    """
    def __init__(
        self, identity, *, beacon: NodeT = None, loop: asyncio.AbstractEventLoop = None
    ) -> None:
        super(MyService, self).__init__(beacon=beacon, loop=loop)

        self.identity = identity
        self.log = CompositeLogger(self.logger, formatter=self._format_log)

    def _format_log(self, severity: int, msg: str, *args: Any, **kwargs: Any) -> str:
        return f'[{self.identity}:^{"-" * (self.beacon.depth - 1)}{self.shortlabel}]: {msg}'


class Core(MyService):
    """Docstring for Core.

    Every queue is automatically bound to the default exchange with a routing key which is the same as the queue name.
    All async tasks must only be started in on_start method because only there the eventloop is configured.

    """

    def __init__(
        self,
        *,
        identity=None,
        config=None,
        clock=None,
        channel_number: int = None,
        beacon: NodeT = None,
        loop: asyncio.AbstractEventLoop = None,
    ) -> None:
        identity = identity or str(uuid.uuid4())
        super().__init__(identity=identity, beacon=beacon, loop=loop)

        self.config = {}
        if config is not None:
            if not isinstance(config, dict):
                self.log.error(
                    f"Configuration must be valid dictionay, got {config}. Resetting to {{}}."
                )
            else:
                self.log.info(f"Configuration: {config}.")
                self.config = config

        self.connection = None
        self.channel = None
        self.channel_number = channel_number
        self.direct_queue = None
        self.topic_exchange = None
        self.fanout_exchange = None
        self.behaviours = self._children
        self.traces = TraceStore(size=1000)
        self.peers = TraceStore(size=100)

        self.futures = dict()  # store for RPC futures

        self.handlers: Registry = Registry()

        self.clock = clock

        self.web = None  # set by class AsgiAgent
        self.ws = None

    async def __aenter__(self) -> Core:
        await super(Core, self).__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] = None,
        exc_val: BaseException = None,
        exc_tb: TracebackType = None,
    ) -> Optional[bool]:
        await super(Core, self).__aexit__()
        return None

    async def on_first_start(self):
        ...

    async def on_start(self):
        self.log.info("Starting agent.")
        try:
            self.connection = await connect_robust(url=RMQ_URL)
        except ConnectionError as e:
            self.log.exception(f"Check RabbitMQ: {e}")  # TODO: implement RMW precheck

        # needs to be managed when several cores running in one process (else always 1)
        if self.channel_number:
            self.channel = await self.connection.channel(
                channel_number=self.channel_number
            )
        else:
            self.channel = await self.connection.channel()

        await self.channel.set_qos(prefetch_count=1)

        await self.configure_exchanges()

        try:
            await self._configure_agent_queues()
        except ChannelLockedResource as e:
            self.log.error(f"Potential identity conflict: {self.identity}.")
            raise

        self.log.info(f"Start consuming: {self.direct_queue}, {self.fanout_queue}")
        await self.direct_queue.consume(
            consumer_tag=self.identity, callback=self.on_message
        )
        await self.fanout_queue.consume(callback=self.on_message)

        await self._update_peers()
        # TODO: refactor for better understanding and configuration
        if self.config.get("UPDATE_PEER_INTERVAL") is not None:
            interval = self.config.get("UPDATE_PEER_INTERVAL")
            self.log.debug(f"Starting peer update with interval: {interval}")
            # noinspection PyAsyncCall
            self.add_future(self.periodic_update_peers(interval))  # service awaits future

        await self.setup()

    async def setup(self):
        """ to be overwritten by agent """
        pass

    async def configure_exchanges(self):
        self.topic_exchange = await self.channel.declare_exchange(
            name=BINDING_KEY_TOPIC, type=ExchangeType.TOPIC
        )
        self.fanout_exchange = await self.channel.declare_exchange(
            name=BINDING_KEY_FANOUT, type=ExchangeType.FANOUT
        )
        self.log.info(
            f"Exchanges created: {self.topic_exchange}, {self.fanout_exchange}"
        )

    async def _configure_agent_queues(self):
        queue_name = self.identity
        self.direct_queue = await self.channel.declare_queue(
            name=queue_name, auto_delete=False, durable=False, exclusive=True
        )

        self.fanout_queue = await self.channel.declare_queue(
            name="", auto_delete=False, durable=False, exclusive=True
        )
        self.log.info(f"Queues declared: {self.direct_queue}, {self.fanout_queue}")

        await self.fanout_queue.bind(
            self.fanout_exchange, routing_key=BINDING_KEY_FANOUT
        )
        self.log.info(
            f"Binding: {self.fanout_queue} to {self.fanout_exchange}: BindingKey: {BINDING_KEY_FANOUT}"
        )

    async def on_started(self):
        ...

    async def dummy(self):
        return True

    async def stop(self) -> None:
        """Stop the service."""
        if not self._stopped.is_set():
            # self._log_mundane('Stopping...')
            self.log.info(f"Stopping agent and behaviours: {self.list_behaviour()}...")
            self._stopped.set()
            await self._stop_children()  # tw: order reversed with regards to service.stop()
            await self.on_stop()
            self.log.debug("Shutting down...")
            if self.wait_for_shutdown:
                self.log.debug("Waiting for shutdown")
                await asyncio.wait_for(self._shutdown.wait(), self.shutdown_timeout)
                self.log.debug("Shutting down now")
            await self._stop_futures()
            await self._stop_exit_stacks()
            await self.on_shutdown()
            self.log.debug("-Stopped!")

    async def on_stop(self):
        """ Stops an agent and kills all its behaviours. """
        await self.teardown()
        await self.connection.close()
        await self.channel.close()
        self.log.info(f"Agent stopped: {self.state}")

    async def teardown(self):
        """" To be overwritten by agent class """
        pass

    async def on_shutdown(self):
        self.set_shutdown()
        self.log.info(f"Agent shutdown: {self.state}")

    # async def _async_connect(self):  # pragma: no cover
    #     try:
    #         self.connection = await connect_robust(url=RMQ_URL)
    #         aenter = type(self.connection).__aenter__(self.connection)
    #         self.channel = await aenter
    #         self.log.info(f"Agent {self.identity} connected and authenticated.")
    #     except Exception:
    #         raise

    # async def _async_disconnect(self):
    #     if self.is_alive:
    #         aexit = self.connection.__aexit__(*sys.exc_info())
    #         await aexit
    #         self.log.info("Client disconnected.")

    def has_behaviour(self, behaviour):
        return behaviour in self.behaviours

    def list_behaviour(self):
        return [str(behav) for behav in self.behaviours]

    def get_behaviour(self, name: str) -> Optional[ServiceT]:
        behav = [behav for behav in self.behaviours if str(behav).endswith(name)]
        if len(behav) > 1:
            self.log.warning(
                f"{len(behav)} behaviours found for {name}. Name not unique!"
            )
        elif len(behav) == 0:
            return None
        return behav[0]

    async def call(self, msg: str, target: str = None) -> str:
        if target is None:
            target = self.identity  # loopback send

        result = None
        correlation_id = str(uuid.uuid4())
        future = self.loop.create_future()

        # create awaitable future, so that in background future can be resolved while here awaiting future.result
        self.futures[correlation_id] = future

        await self.direct_send(msg, RmqMessageTypes.RPC.name, target, correlation_id)

        try:
            async with timeout(timeout=TIMEOUT):
                result = await future
        except asyncio.TimeoutError as e:
            rpc_message = RpcMessage.from_json(msg)
            err_msg = f"{self}: TimeoutError after {TIMEOUT}s while waiting for RPC request: {rpc_message.c_type}: {correlation_id}"
            future = self.futures.pop(correlation_id)
            # future.set_exception(e)
            future.cancel()
            self.log.error(err_msg)

            result = RpcError(error=err_msg)

        return result

    async def direct_send(
        self,
        msg: str,
        msg_type: str,
        target: str = None,
        correlation_id: str = None,
        headers: dict = None,
    ) -> None:
        if target is None:
            target = self.identity  # loopback send
        await self.channel.default_exchange.publish(
            message=self._create_message(msg, msg_type, correlation_id, headers),
            routing_key=target,
            timeout=None,
        )
        self.log.debug(
            f"Sent message: {msg}, routing_key: {self.identity}, type: {msg_type}"
        )

    async def fanout_send(
        self, msg: str, msg_type: str, correlation_id: str = None, headers: dict = None
    ) -> None:
        await self.fanout_exchange.publish(
            message=self._create_message(msg, msg_type, correlation_id, headers),
            routing_key=BINDING_KEY_FANOUT,
            timeout=None,
        )
        self.log.debug(f"Sent fanout message: {msg}, routing_key: {BINDING_KEY_FANOUT}")

    async def publish(self, msg: str, routing_key: str, headers: dict = None) -> None:
        """ Publishes message to topic """
        await self.topic_exchange.publish(
            message=self._create_message(
                msg, msg_type="pubsub", correlation_id=None, headers=headers
            ),
            routing_key=routing_key,
            timeout=None,
        )
        self.log.debug(f"Sent: {msg}, routing_key: {routing_key}")

    def _create_message(
        self, msg: str, msg_type: str, correlation_id: str = None, headers: dict = None
    ) -> Message:
        return Message(
            content_type="application/json",
            body=msg.encode(),
            timestamp=datetime.now(),
            type=msg_type,
            app_id=self.identity,
            user_id="guest",
            headers=headers,
            correlation_id=correlation_id,
        )

    async def on_message(self, message: IncomingMessage):

        # If context processor will catch an exception, the message will be returned to the queue.
        async with message.process():
            self.log.debug(f"Received (info/body:")
            self.log.debug(f"   {message.info()}")
            self.log.debug(f"   {message.body.decode()}")
            self.traces.append(TraceStoreMessage.from_msg(message), category="incoming")

            if message.type in (RmqMessageTypes.CONTROL.name, RmqMessageTypes.RPC.name):
                handler = self.handlers.get(handler=message.type)
                if issubclass(handler, SystemHandler):
                    handler_instance = handler(core=self)
                    return await handler_instance.handle(message)
                else:
                    return await handler(self, message)

            for behaviour in self.behaviours:
                await behaviour.enqueue(message)
                self.log.debug(f"Message enqueued to: {behaviour} --> {message.body}")
                self.traces.append(
                    TraceStoreMessage.from_msg(message), category=str(behaviour)
                )

    async def _update_peers(self) -> None:
        """ Triggers update of peer list
            PongControl handler update self.peers
        """
        msg = PingControl().serialize()
        correlation_id = str(uuid.uuid4())
        await self.fanout_send(
            msg=msg,
            msg_type=RmqMessageTypes.CONTROL.name,
            correlation_id=correlation_id,
        )

    async def periodic_update_peers(self, interval):
        _interval = want_seconds(interval)
        async for _ in self.itertimer(_interval):
            await self._update_peers()
            msg = self._create_peer_msg()
            await self._publish_ws(msg)

    def _create_peer_msg(self) -> JSONType:
        latest = self.peers.latest()
        corr_id = latest[2]
        peers = sorted([status for (ts, status, cor_id) in self.peers.filter(category=corr_id)],
                       key=lambda status: status.name)
        peers = CoreStatus.schema().dump(peers, many=True)
        msg = {
            'from': self.identity,
            'peers': peers
        }
        return msg

    async def _publish_ws(self, msg: JSONType):
        if self.web and self.web.ws:
            self.log.debug(f"Publishing ws message: {msg}")
            try:
                await self.web.ws.send_json(msg)
            except RuntimeError as e:
                self.log.exception(e)

    # TODO: https://github.com/aio-libs/aiohttp-sse/blob/66407db5752d19abd4d312f0b22fa8106feb6ca2/aiohttp_sse/__init__.py
    async def publish_sse(self, interval: int, id: str = None, event: str = None, retry: int = None):
        self.DEFAULT_SEPARATOR = '\r\n'
        self.LINE_SEP_EXPR = re.compile(r'\r\n|\r|\n')
        self._sep = self.DEFAULT_SEPARATOR
        async for _ in self.itertimer(want_seconds(interval)):
            data = json.dumps(self._create_peer_msg())
            buffer = io.StringIO()
            if id is not None:
                buffer.write(self.LINE_SEP_EXPR.sub('', 'id: {}'.format(id)))
                buffer.write(self._sep)

            if event is not None:
                buffer.write(self.LINE_SEP_EXPR.sub('', 'event: {}'.format(event)))
                buffer.write(self._sep)

            for chunk in self.LINE_SEP_EXPR.split(data):
                buffer.write('data: {}'.format(chunk))
                buffer.write(self._sep)

            if retry is not None:
                if not isinstance(retry, int):
                    raise TypeError('retry argument must be int')
                buffer.write('retry: {}'.format(retry))
                buffer.write(self._sep)

            buffer.write(self._sep)
            self.log.warning(buffer.getvalue().encode('utf-8'))
            yield buffer.getvalue().encode('utf-8')

    def __repr__(self):
        return "{}".format(self.__class__.__name__)

    @property
    def status(self):
        behav_stati = list()
        for behav in self.behaviours:
            behav_status = ServiceStatus(name=str(behav), state=behav.state)
            behav_stati.append(behav_status)
        return CoreStatus(
            name=self.identity, state=self.state, behaviours=behav_stati
        )


if __name__ == "__main__":
    logging.getLogger("aio_pika").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)

    setup_logging(logging.DEBUG)
    from mode import Worker

    config = dict(UPDATE_PEER_INTERVAL=1.0)
    app = Core(identity='core', config=config)

    Worker(app, loglevel="info").execute_from_commandline()
