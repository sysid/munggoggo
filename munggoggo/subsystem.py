from __future__ import annotations  # make all type hints be strings and skip evaluating them
from typing import TYPE_CHECKING, Any, Optional, ClassVar

from messages import TraceStoreMessage
from mode.utils.logging import CompositeLogger, get_logger

if TYPE_CHECKING:
    from behaviour import Behaviour
    from core import Core


import inspect
import logging

from aio_pika import Queue, IncomingMessage
from aio_pika.patterns import RPC


class SubSystem(object):

    #: Set to True if this service class is abstract-only,
    #: meaning it will only be used as a base class.
    abstract: ClassVar[bool] = True
    log: CompositeLogger

    #: Logger used by this service.
    #: If not explicitly set this will be based on get_logger(cls.__name__)
    logger: Optional[logging.Logger] = None

    def __init_subclass__(self) -> None:
        if self.abstract:
            self.abstract = False
        self._init_subclass_logger()

    @classmethod
    def _init_subclass_logger(cls) -> None:
        # make sure class has a logger.
        if cls.logger is None or getattr(cls.logger, '__modex__', False):
            logger = cls.logger = get_logger(cls.__module__)
            logger.__modex__ = True

    def __init__(self, behaviour):
        """
            #### ATTENTION: configuration only in on_start !!!!
        """
        super().__init__()
        self.behaviour: Behaviour = behaviour
        self.core: Core = behaviour.core
        self.log = CompositeLogger(self.logger, formatter=self._format_log)

    def _format_log(self, severity: int, msg: str,
                    *args: Any, **kwargs: Any) -> str:
        return f'[^{"-" * (self.behaviour.beacon.depth - 1)}{self.behaviour.shortlabel}.{self.__class__.__name__}]: {msg}'


class PubSub(SubSystem):

    def __init__(self, behaviour, binding_keys: list):
        """
            #### ATTENTION: configuration only in on_start !!!!
        """
        super().__init__(behaviour)
        self.queue_name = f"{self.behaviour.name}.pubsub_queue"
        self.pubsub_queue = None
        self.binding_keys = binding_keys

    async def on_start(self):
        """ Initializes pubsub
            only here are the container classes initialized (core, behviour)
        """
        self.log.info(f"on_start PubSub")
        await self._configure_pubsub()

        # Bindings are individual per behaviour
        bindings = await self._get_binding(self.pubsub_queue)
        self.log.info(f"Subscribing to {self.pubsub_queue}, topics: {bindings}")
        await self.pubsub_queue.consume(
            consumer_tag=self.behaviour.name, callback=self.on_message
        )

    async def _configure_pubsub(self):
        await self.core.configure_exchanges()
        self.pubsub_queue = await self.core.channel.declare_queue(
            name=self.queue_name, auto_delete=False, durable=False
        )
        self.log.info(f"Queue declared: {self.queue_name}")

        for binding_key in self.binding_keys:
            await self.pubsub_queue.bind(
                self.core.topic_exchange, routing_key=binding_key
            )
            self.log.info(f"Queue '{self.queue_name}' bound to {binding_key}.")

    @staticmethod
    async def _get_binding(queue: Queue):
        bindings = list()
        # noinspection PyProtectedMember
        for binding in queue._bindings.keys():
            bindings.append(binding[1])
        return bindings

    async def on_message(self, message: IncomingMessage):
        """
        on_message doesn't necessarily have to be defined as async.
        """
        async with message.process():
            self.log.debug(f"Received:")
            self.log.debug(f"   {message.info()}")
            self.log.debug(f"   {message.body}")
            self.core.traces.append(TraceStoreMessage.from_msg(message), category="incoming")
            await self.behaviour.enqueue(message)

    async def on_end(self):
        self.log.info(f"on_end: deleting queue {self.pubsub_queue}")

        # await self.pubsub_queue.unbind(exchange=self.core.topic_exchange)
        await self._unconfigure_pubsub()

    async def _unconfigure_pubsub(self):
        await self.pubsub_queue.purge()
        for binding_key in self.binding_keys:
            await self.pubsub_queue.unbind(
                self.core.topic_exchange, routing_key=binding_key
            )
            self.log.info(f"Queue '{self.queue_name}' unbound from {binding_key}.")

        await self.pubsub_queue.delete(if_unused=False, if_empty=False)


def list_rpc_methods(obj):
    methods = [
        getattr(obj, method_name)
        for method_name in dir(obj)
        if callable(
            inspect.getattr_static(obj, method_name)
        )  # https://bugs.python.org/issue35108
    ]
    return [
        method for method in methods if hasattr(method, "__rpc__") and method.__rpc__
    ]


def expose(func):
    """Decorator that enables RPC access to the decorated function.

    *func* will not be wrapped but only gain an ``__rpc__`` attribute.
    """
    if not hasattr(func, "__call__"):
        raise ValueError('"{}" is not callable.'.format(func))

    func.__rpc__ = True
    return func


class RPC_SubSystem(SubSystem):

    def __init__(self, behav):
        super().__init__(behav)
        self.rpc = None

    async def on_start(self):
        """ Initializes rpc
            only here are the container classes initialized (core, behviour)
        """
        self.log.info(f"on_start RPC")
        await self._configure_rpc()

    async def _configure_rpc(self):
        self.rpc = await RPC.create(self.core.channel)
        for rpc_method in list_rpc_methods(self.behaviour):
            self.log.info(f"Registering RPC: {rpc_method.__name__}")
            await self.rpc.register(rpc_method.__name__, rpc_method, auto_delete=False)

            if self.core.web:
                web = self.core.web
                web.rpc_dispatcher.add_method(rpc_method)



    @property
    def methods(self):
        return list(self.rpc.routes.keys())

    async def list_registered_rpc_methods(self):
        return [queue.name for queue in self.rpc.queues.values()]

    async def rpc_call(self, method: str, **kwargs):
        self.log.debug(f"RPC call: {method}, {kwargs}")
        if method in self.methods:
            return await self.rpc.call(method, kwargs=kwargs)
        else:
            return f"Illegal method '{method}' called. Available RPC methods are: {self.methods}"

    async def on_end(self):
        pass
