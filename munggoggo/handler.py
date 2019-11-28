"""
    async def handler(meta, body, *args, **kwargs):
"""
from __future__ import (
    annotations,
)  # make all type hints be strings and skip evaluating them

import asyncio
import functools
import importlib
import inspect
import logging
from asyncio import Task
from enum import Enum
from typing import TYPE_CHECKING, Union, Dict, Optional, Any

from aio_pika import IncomingMessage
from async_timeout import timeout
from marshmallow import Schema, fields

from messages import RpcMessageTypes, RpcMessage, Pong, RpcError, RpcObject, Ping, ListBehav, ManageBehav, \
    ListTraceStore, Shutdown, ControlMessage, SerializableObject, PongControl, PingControl, RmqMessageTypes
from mode.utils.logging import CompositeLogger, get_logger
from settings import TIMEOUT

if TYPE_CHECKING:
    from behaviour import Behaviour
    from core import Core

_log = logging.getLogger(__name__)


async def default_handler(behav: Behaviour, msg: IncomingMessage, *args, **kwargs):
    print(f"{inspect.currentframe().f_code.co_name}: dispatched message: {msg.body}")
    _log.warning(f"{inspect.currentframe().f_code.co_name}: dispatched message: {msg.body}")


class Handler(object):
    """
        Must be non-blocking, else deadlock in _step/run.
    """

    class MessageSchema(Schema):
        msg = fields.Str()

    schema = MessageSchema()

    def __init__(self):
        super().__init__()

    async def handle(self, behav: Behaviour, msg: IncomingMessage, *args, **kwargs):
        body = self.schema.loads(msg.body)
        print(f"{self}: dispatched message: {body}")

    def __str__(self):
        return "{}/{}".format(
            "/".join(base.__name__ for base in self.__class__.__bases__),
            self.__class__.__name__,
        )


class SystemHandler(object):

    log: CompositeLogger

    logger: Optional[logging.Logger] = None

    def __init_subclass__(self) -> None:
        self._init_subclass_logger()

    @classmethod
    def _init_subclass_logger(cls) -> None:
        # make sure class has a logger.
        if cls.logger is None or getattr(cls.logger, '__modex__', False):
            logger = cls.logger = get_logger(cls.__module__)
            logger.__modex__ = True

    def __init__(self, core: Core):
        super().__init__()
        self.core = core
        self.log = CompositeLogger(self.logger, formatter=self._format_log)

    def _format_log(self, severity: int, msg: str, *args: Any, **kwargs: Any) -> str:
        return f'[{self.core.identity}:^{"-" * (self.core.beacon.depth - 1)}{self.core.shortlabel}.{self.__class__.__name__}]: {msg}'

    async def handle(self, msg: IncomingMessage, *args, **kwargs):
        print(f"{self}: dispatched message: {msg.body}")

    def __str__(self):
        return "{}/{}".format(
            "/".join(base.__name__ for base in self.__class__.__bases__),
            self.__class__.__name__,
        )


class Control(SystemHandler):
    """ Handles messages which do NOT require request/response protocol """

    async def handle(self, msg: IncomingMessage, *args, **kwargs):
        # body = self.schema.loads(msg.body)
        # control_msg = ControlMessage.deserialize(msg.body)
        ctrl_obj = SerializableObject.deserialize(msg.body)

        requestor = msg.app_id
        self.log.debug(f"{self}: got command: {type(ctrl_obj).__name__}")

        if isinstance(ctrl_obj, PingControl):
            behaviour = self.core.list_behaviour()
            reply = PongControl(status=self.core.status).serialize()
            await self.core.direct_send(
                reply, RmqMessageTypes.CONTROL.name, requestor, msg.correlation_id
            )

        elif isinstance(ctrl_obj, PongControl):
            self.log.debug(f"Got pong status from : {msg.app_id}, {msg.correlation_id}")
            self.core.peers.append(event=ctrl_obj.status, category=msg.correlation_id)

        else:
            self.log.warning(f"{self}: got unknown command: {type(ctrl_obj)}")


class RpcHandler(SystemHandler):
    """ Handles messages which do require request/response protocol """

    async def handle(self, msg: IncomingMessage, *args, **kwargs):
        self.log.info(f"{self}: received message: {msg.body}")
        reply = None
        request_type, rpc_obj = RpcObject.from_rpc(msg.body)

        if request_type is RpcMessageTypes.RPC_REQUEST:

            if isinstance(rpc_obj, Ping):
                reply = Pong(pong="pong").to_rpc(rt=RpcMessageTypes.RPC_RESPONSE)

            elif isinstance(rpc_obj, ListBehav):
                rpc_obj.behavs = self.core.list_behaviour()
                reply = rpc_obj.to_rpc(rt=RpcMessageTypes.RPC_RESPONSE)

            elif isinstance(rpc_obj, ManageBehav):
                reply = await self.handle_manage_behav(reply, rpc_obj)

            elif isinstance(rpc_obj, ListTraceStore):
                rpc_obj.traces = self.core.traces.filter(limit=rpc_obj.limit, app_id=rpc_obj.app_id, category=rpc_obj.category)
                reply = rpc_obj.to_rpc(rt=RpcMessageTypes.RPC_RESPONSE)

            elif isinstance(rpc_obj, Shutdown):
                reply = await self.handle_shutdown(reply, rpc_obj)

            else:
                # path cannot be reached: timeout of rpc.call
                reply = RpcError(error=f"Unknown RPC request: {type(rpc_obj)}").to_rpc()

        elif request_type is RpcMessageTypes.RPC_RESPONSE:
            future = self.core.futures.pop(msg.correlation_id)
            future.set_result(rpc_obj)
            return

        else:
            reply = RpcError(error="Unknown RPC request").to_rpc(rt=RpcMessageTypes.RPC_RESPONSE)

        try:
            with timeout(TIMEOUT):
                await self.core.direct_send(
                    msg=reply,
                    msg_type=RmqMessageTypes.RPC.name,
                    target=msg.app_id,
                    correlation_id=msg.correlation_id,
                )
        except TimeoutError as e:
            self.log.error(f"TimeoutError while sending to {msg.app_id}.")

    async def handle_shutdown(self, reply, rpc_obj):
        rpc_obj.result = f"Shutdown of {self.core.identity} initiated."
        reply = rpc_obj.to_rpc(rt=RpcMessageTypes.RPC_RESPONSE)
        # ensure, that response still gets sent back
        self.core.loop.call_later(delay=0.2, callback=functools.partial(self.core.loop.create_task, self.core.stop()))
        return reply

    async def handle_manage_behav(self, reply, rpc_obj):
        behav = self.core.get_behaviour(rpc_obj.behav)
        if behav:
            if rpc_obj.command == 'start':
                if not behav.started:
                    await behav.start()
                    rpc_obj.result = f"{behav} started."
                else:
                    rpc_obj.result = f"{behav} already running."
            elif rpc_obj.command == 'stop':
                if behav.started:
                    await behav.stop()
                    behav.service_reset()
                rpc_obj.result = f"{behav} stopped: {behav.state}"
            else:
                rpc_obj.result = f"Unknown command {rpc_obj.command}."
        else:
            rpc_obj.result = f"No behaviour {rpc_obj.behav}"
        reply = rpc_obj.to_rpc(rt=RpcMessageTypes.RPC_RESPONSE)
        return reply

    def __str__(self):
        return "{}/{}".format(
            "/".join(base.__name__ for base in self.__class__.__bases__),
            self.__class__.__name__,
        )


class Registry(object):
    def __init__(self):
        self.handlers = {
            "default": default_handler,
            # "msg": Handler,
            RmqMessageTypes.CONTROL.name: Control,
            RmqMessageTypes.RPC.name: RpcHandler,
        }

    def get(self, handler):
        return self.handlers.get(handler, self.handlers.get("default"))

    def add(self, handler):
        self.handlers[str(handler)] = handler
        return handler
