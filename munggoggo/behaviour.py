from __future__ import annotations  # make all type hints be strings and skip evaluating them

import asyncio
import inspect
import sys
import traceback
from asyncio import CancelledError
from enum import Enum
from typing import Any, Optional, List, Type, Dict, Tuple, AsyncIterable
from typing import TYPE_CHECKING

import sqlalchemy
from asgiref.sync import sync_to_async
from databases import Database
from sqlalchemy import MetaData, Table, Column
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from twpy import utcnow

from core import MyService
from messages import SerializableObject, DemoData, WrongMessageFormatException
from mode import Service
from mode.utils.locks import Event
from mode.utils.types.trees import NodeT
from model import TsDb, metadata
from settings import DB_URL

if TYPE_CHECKING:
    pass

from aio_pika import Message, IncomingMessage

import subsystem
from handler import Registry, Handler
from subsystem import PubSub, RPC_SubSystem


class BehaviourNotFinishedException(Exception):
    """ """
    pass


class Behaviour(MyService):
    """ Behaviour is a Service which defines set of actions

        all incoming messages are queued into input queue
        outgoing messages can either by broadcast to all listening agents
        or point-to-point sent to one agent
        or sent to a message topic (PubSub pattern)
    """

    def __init__(self, core, *,
                 beacon: NodeT = None,
                 loop: asyncio.AbstractEventLoop = None,
                 binding_keys: list = None,
                 configure_rpc: bool = False) -> None:

        super().__init__(identity=core.identity, beacon=beacon, loop=loop)

        self.core = core
        self.name = f"{core.identity}.{self.__class__.__name__}"
        self.handlers = core.handlers

        self._exit_code = 0

        self.pubsub: Optional[PubSub] = None
        self.binding_keys = binding_keys

        self.rpc: Optional[RPC_SubSystem] = None
        self.configure_rpc = configure_rpc

        self.on_start_coros = list()
        self.on_end_coros = list()

        self.is_configured_asyncio = False

        # self.queue: Optional[asyncio.Queue[IncomingMessage]] = None
        self.queue = asyncio.Queue()  # TODO: unlimited queue size

        self.is_configured_asyncio = True

        self._force_kill = self._new_force_kill_event()

        # self.future_store = FutureStore(loop=self.loop)

    def _new_force_kill_event(self) -> Event:
        return Event(loop=self._loop)

    def _new_shutdown_done_event(self) -> Event:
        return Event(loop=self._loop)

    @property
    def exit_code(self) -> Any:
        """
        Returns the exit_code of the behaviour.
        It only works when the behaviour is done or killed, otherwise it raises an exception.

        Returns:
          object: the exit code of the behaviour
        """
        if self.is_killed():
            return self._exit_code
        else:
            raise BehaviourNotFinishedException

    @exit_code.setter
    def exit_code(self, value: Any):
        self._exit_code = value

    def set(self, name: str, value: Any) -> None:
        """ Stores a knowledge item in the agent knowledge base. """
        self.core.set(name, value)

    def get(self, name: str) -> Any:
        """ Recovers a knowledge item from the agent's knowledge base. """
        return self.core.get(name)

    async def on_start(self):
        """ Coroutine called before the behaviour is started.
        """
        # self.identity = self.beacon.root.data.identity

        self.on_start_coros = list()
        self.on_end_coros = list()

        if self.binding_keys is not None:
            self.pubsub = PubSub(self, binding_keys=self.binding_keys)
            self.on_start_coros.append(self.pubsub.on_start())
            self.on_end_coros.append(self.pubsub.on_end())

        if self.configure_rpc:
            self.rpc = subsystem.RPC_SubSystem(self)
            self.on_start_coros.append(self.rpc.on_start())
            self.on_end_coros.append(self.rpc.on_end())

        await asyncio.gather(*self.on_start_coros)

        await self.setup()
        self.log.debug(f"{self.name} done.")

    async def setup(self):
        pass

    async def on_stop(self) -> None:
        self.log.info(f"Stopping {self.name}.")
        # self.kill(exit_code="Gracefull Shutdown")
        await self.teardown()

    async def teardown(self):
        pass

    async def on_shutdown(self):
        self.set_shutdown()
        # for coro in self.on_end_coros:
        #     await coro
        await asyncio.gather(*self.on_end_coros)
        self.log.info(f"{self.name} shutdown: {self.state}")

    async def _on_end(self):
        await self.on_end()

        self.log.debug(f"{self.name} done.")

    async def on_end(self):
        """ Coroutine called after the behaviour is done or killed.

            will be overwritten by custom behaviour!!!
        """
        self.log.debug(f"{self.name} done.")

    def is_killed(self) -> bool:
        return self._force_kill.is_set()

    async def run(self):
        """ Body of the behaviour, runs per step of runloop
        To be implemented by user.
        """
        await asyncio.sleep(0.1)

    async def _run(self):
        """
        Function to be overload by more complex behaviours.
        In other case it just calls run() coroutine.
        """
        await self.run()

    @Service.task
    async def _step(self):
        """ Main loop of the behaviour.
        checks whether behaviour is done or killed, otherwise it calls run() coroutine.
       """
        cancelled = False
        while not self.should_stop and not self.is_killed():
            try:
                await self._run()
                await asyncio.sleep(0)  # relinquish cpu
            except CancelledError:
                self.log.info(f"Behaviour {self} cancelled")
                cancelled = True
            except Exception as e:
                self.log.error(f"Exception running behaviour {self}: {e}")
                self.log.error(traceback.format_exc())
                # self.kill(exit_code=e)

        try:
            if not cancelled:
                await self._on_end()
        except Exception as e:
            self.log.error("Exception running on_end in behaviour {self}: {e}")
            self.log.error(traceback.format_exc())
            # self.kill(exit_code=e)
        finally:
            self.log.info(f"---------- loop final ----------")

    async def enqueue(self, message: Message):
        """ Enqueues a message in the behaviour's mailbox """
        self.log.debug(f"message enqueued: {message.body}")
        await self.queue.put(message)

    def mailbox_size(self) -> int:
        return self.queue.qsize()

    async def direct_send(self, msg: str, msg_type: str, target: str = None, correlation_id: str = None):
        await self.core.direct_send(msg, msg_type, target, correlation_id)
        # self.agent.traces.append(TraceStoreMessage.from_msg(msg), category=str(self))

    async def publish(self, msg: str, routing_key: str):
        await self.core.publish(msg, routing_key)
        # self.agent.traces.append(TraceStoreMessage.from_msg(msg), category=str(self))

    async def fanout_send(self, msg: str, msg_type: str):
        await self.core.fanout_send(msg, msg_type)
        # self.agent.traces.append(TraceStoreMessage.from_msg(msg), category=str(self))

    async def receive(self, timeout: float = None) -> IncomingMessage:
        """ Receives a message for this behaviour.

       If timeout is not None it returns the message or "None"
       after timeout is done.
       """
        if timeout:
            coro = self.queue.get()
            try:
                msg = await asyncio.wait_for(coro, timeout=timeout)
                self.queue.task_done()
            except asyncio.TimeoutError:
                msg = None
        else:
            try:
                msg = self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                msg = None
        return msg

    async def receive_all(self) -> AsyncIterable[IncomingMessage]:
        while self.queue.qsize() != 0:
            yield await self.receive()

    async def get_and_dispatch(self, timeout: float = None):
        msg = await self.receive(timeout=timeout)
        if msg:
            self.log.info(f"{self.name}: Message: {msg.body.decode()}")
            return await self.dispatch(msg)

    async def dispatch(self, msg: IncomingMessage, handlers: Registry = None) -> None:
        if handlers is None:
            handlers = self.handlers

        msg_type = msg.type
        handler = handlers.get(handler=msg_type)

        if isinstance(handler, Handler):
            return await handler.handle(self, msg)
        else:
            return await handler(self, msg)

    @subsystem.expose
    async def example_rpc_method(self, x, y, flag=None, **kwargs):
        self.log.info(
            f"example_method: Signature: {inspect.signature(self.example_rpc_method)}"
        )
        self.log.info(f"exmpale_method called with: {x}, {y}, {flag}, {kwargs}")
        return x * y

    def __str__(self):
        if self.name:
            return self.name
        else:
            return "{}/{}".format(
                "/".join(base.__name__ for base in self.__class__.__bases__),
                self.__class__.__name__,
            )


class EmptyBehav(Behaviour):
    async def on_start(self):
        print(f"Starting {self.name} . . .")

    async def run(self):
        # >1 triggers log messages: syncio:poll 999.294 ms took 1000.570 ms: timeout
        await asyncio.sleep(0)

    async def on_end(self):
        print(f"Finished {self.name} with exit_code {self.exit_code}. . .")


class SqlBehav(Behaviour):
    """ Subscribes to topic and stores known message_types to database """

    def __init__(self, core, *,
                 beacon: NodeT = None,
                 loop: asyncio.AbstractEventLoop = None,
                 binding_keys: list = None,
                 configure_rpc: bool = False) -> None:

        super(SqlBehav, self).__init__(core, beacon=beacon, loop=loop, binding_keys=binding_keys,
                                       configure_rpc=configure_rpc)
        self.db: Optional[Database] = None
        self.engine: Optional[Engine] = None
        self.metadata: Optional[MetaData] = None
        self.msg_types: Dict[str, Type[SerializableObject]] = {DemoData.__name__: DemoData}

        # allow already serialized json to be inserted in JSON column as text
        # as class variable overwrites tests while loading (startup-time vs. runtime)
        self.json_data = Table(
            "json_data",
            metadata,
            Column("id", sqlalchemy.Integer, primary_key=True),
            Column("ts", sqlalchemy.TIMESTAMP(timezone=True)),
            Column("type", sqlalchemy.String(length=100)),
            Column("data", sqlalchemy.Text),
            extend_existing=True  # allow redefinition to JSON column to send json string
        )

    def add_msg_type(self, msg_type: Type[SerializableObject]):
        self.msg_types[msg_type.__name__] = msg_type

    async def setup(self):
        await self.init_db()
        self.db = Database(DB_URL)
        await self.db.connect()

    @sync_to_async
    def init_db(self) -> None:
        self.log.info(f"Initializating db: {DB_URL}")
        TsDb.create_new_db(DB_URL)
        db = TsDb(url=DB_URL, meta=metadata)
        db.init_db()

    async def run(self):
        try:
            msg = await self.receive()
            if msg:
                print(f"{self.name}: Message received: {msg.body.decode()}")
                msg_type_key = SerializableObject.extract_type(msg.body.decode())
                msg_type = self.msg_types.get(msg_type_key)

                if msg_type:
                    obj = SerializableObject.deserialize(msg.body.decode(), msg_type=msg_type)
                    await self.save_to_db(obj)
                else:
                    self.log.error(f"Unknown message type {msg_type_key} read from topics {self.binding_keys}.")
                    self.log.error(f"Not saving to DB")
        except WrongMessageFormatException as e:
            # self.log.exception(f"{e}", exc_info=sys.exc_info())
            self.log.exception(f"{e}")

    async def save_to_db(self, obj):
        if isinstance(obj, SerializableObject):
            data = {"type": obj.__class__.__name__, "ts": utcnow(), "data": obj.to_json()}
            query = self.json_data.insert()
            try:
                await self.db.execute(query=query, values=data)
            except SQLAlchemyError as e:
                self.log.exception(e)
                raise
        else:
            self.log.warning(f"Only type 'SerializableObject' can be stored to db, got: {type(obj)}.")

    async def on_end(self):
        await self.db.disconnect()


class SystemBehaviour(Enum):
    EMPTY = EmptyBehav
