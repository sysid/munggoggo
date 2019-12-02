import importlib
import json
from json import JSONDecodeError

import sys

import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TypeVar, List, Optional, Tuple, Type, Dict

import pytz
from aio_pika import Message, IncomingMessage
from dataclasses_json import dataclass_json

_log = logging.getLogger(__name__)

""" Message Definition and Serialization:

    Self describing data serialization format based on json and python dataclasses.

    Two stage serialization:
    1. serialize payload by using dataclasses and marshmallow (dataclass with dataclass_json decorator)
    2. wrap result into RPC dataclass with two fields: {c_type: str, c_data: json_payload}

    This allows during deserialization to
    1. extract the class_type of payload from the SerializedObject (obj.c_type)
    2. deserizalize the json_payload with the class_type into the usable python object

    Caveat when serializing dataclasses:
    As specified in the datetime docs, if your datetime object is naive, it will assume your system local timezone
    when calling .timestamp(). JSON nunbers corresponding to a datetime field in your dataclass are decoded into
    a datetime-aware object, with tzinfo set to your system local timezone.
    Thus, if you encode a datetime-naive object, you will decode into a datetime-aware object.
    This is important, because encoding and decoding won't strictly be inverses.

    When using tz-aware objects everything should be fine

    Rabbit MQ Message attributes and their semantic:
        body: payload
        headers: message headers
        headers_raw: message raw headers
        content_type: application/json
        content_encoding: string
        delivery_mode: delivery mode
        priority: priority (not used)
        correlation_id: correlation id
        reply_to: reply to
        routing_key: routing_key (e.g. topic)
        expiration: expiration in seconds (or datetime or timedelta)
        message_id: message id
        timestamp: timestamp
        type: type  -> (RmqMessageTypes: not rmq relevant, for application to communicate semantics)
        user_id: user id -> (rmq user, e.g. guest)
        app_id: app id -> (sender identity)
"""

# dataclass with dataclass_json decorator
SerializableDataclass = TypeVar("SerializableDataclass")


def convert_to_utc(obj):
    # convert from local timezone to UTC
    for field in obj.__class__.__dataclass_fields__.values():
        if field.type is datetime:
            dt = getattr(obj, field.name)
            setattr(obj, field.name, dt.astimezone(pytz.UTC))
    return obj


class RmqMessageTypes(Enum):
    """ Defines the RMQ messages which are handled by system

        User can define arbitrary message types by using the
        msg_type parameter of fanout_send/direct_send methods.
    """

    CONTROL = 0
    RPC = 1
    PUBSUB = 2


class RpcMessageTypes(Enum):
    RPC_REQUEST = 1
    RPC_RESPONSE = 2


@dataclass_json
@dataclass
class RpcMessage:
    c_type: str
    c_data: str
    request_type: str = RpcMessageTypes.RPC_REQUEST  # 'request', 'response'

    def is_request(self):
        return self.request_type is RpcMessageTypes.RPC_REQUEST

    def is_response(self):
        return self.request_type is RpcMessageTypes.RPC_RESPONSE


@dataclass_json
@dataclass()
class RpcObject:
    def to_rpc(self, rt: RpcMessageTypes = None) -> str:
        rpc_message = RpcMessage(c_type=self.__class__.__name__, c_data=self.to_json())
        if rt is not None:
            rpc_message.request_type = rt
        return rpc_message.to_json()

    @staticmethod
    def from_rpc(msg: str) -> Tuple[RpcMessageTypes, SerializableDataclass]:
        rpc_msg = RpcMessage.from_json(msg)

        module = importlib.import_module("messages")
        class_ = getattr(module, rpc_msg.c_type)
        rpc_obj = class_.from_json(rpc_msg.c_data)
        rpc_obj = convert_to_utc(rpc_obj)
        return RpcMessageTypes(rpc_msg.request_type), rpc_obj


def to_rpc(obj: SerializableDataclass) -> str:
    """ Creates self describing serialized json RPC object """
    return RpcMessage(c_type=obj.__class__.__name__, c_data=obj.to_json()).to_json()


def from_rpc(msg: str) -> SerializableDataclass:
    rpc_msg = RpcMessage.from_json(msg)

    module = importlib.import_module("messages")
    class_ = getattr(module, rpc_msg.c_type)
    rpc_obj = class_.from_json(rpc_msg.c_data)
    return rpc_obj


@dataclass_json
@dataclass()
class Ping(RpcObject):
    ping: str = "ping"


@dataclass_json
@dataclass()
class Pong(RpcObject):
    pong: str = "pong"


@dataclass_json
@dataclass()
class RpcError(RpcObject):
    error: str = ""


@dataclass_json
@dataclass()
class DemoObj(RpcObject):
    message: str = ""
    date: datetime = None


@dataclass_json
@dataclass()
class ListBehav(RpcObject):
    behavs: List[str] = field(default_factory=list)


@dataclass_json
@dataclass()
class ManageBehav(RpcObject):
    behav: str = None
    command: str = None
    result: str = ""


@dataclass_json
@dataclass()
class ListTraceStore(RpcObject):
    limit: Optional[int] = None
    app_id: Optional[str] = None
    category: Optional[str] = None
    traces: List[str] = field(default_factory=list)


@dataclass_json
@dataclass()
class Shutdown(RpcObject):
    result: str = ""


# @api.schema("ExampleMethodParameter")
# class ExampleMethodParameterSchema(Schema):
#     x = fields.Float()
#     y = fields.Float()


@dataclass_json
@dataclass()
class TraceStoreMessage:
    body: str
    body_size: int
    headers: dict  # rmq: headers_raw
    content_type: str
    content_encoding: str
    delivery_mode: int
    priority: int
    correlation_id: str
    reply_to: str
    expiration: datetime
    message_id: str
    timestamp: time
    user_id: str
    app_id: str
    cluster_id: str
    consumer_tag: str
    delivery_tag: int
    exchange: str
    redelivered: bool
    routing_key: str

    @staticmethod
    def from_msg(msg: IncomingMessage):
        self = TraceStoreMessage(
            body=msg.body.decode(),
            body_size=msg.body_size,
            headers=msg.headers_raw,
            content_type=msg.content_type,
            content_encoding=msg.content_encoding,
            delivery_mode=msg.delivery_mode,
            priority=msg.priority,
            correlation_id=msg.correlation_id,
            reply_to=msg.reply_to,
            expiration=msg.expiration,
            message_id=msg.message_id,
            timestamp=time.mktime(msg.timestamp),
            user_id=msg.user_id,
            app_id=msg.app_id,
            cluster_id=msg.cluster_id,
            consumer_tag=msg.consumer_tag,
            delivery_tag=msg.delivery_tag,
            exchange=msg.exchange,
            redelivered=msg.redelivered,
            routing_key=msg.routing_key,
        )
        return self


class WrongMessageFormatException(Exception):
    pass


@dataclass_json
@dataclass
class SerializedObject:
    c_type: str
    c_data: str


@dataclass_json
@dataclass()
class SerializableObject:
    def serialize(self, to_dict=False) -> str:
        """ Serializes dataclass including type into SerializedObject """
        obj = SerializedObject(
            c_type=self.__class__.__name__,
            c_data=self.to_json(),  # method from dataclass_json
        )

        return obj.to_json()

    @staticmethod
    def deserialize(
        msg: str, msg_type: Type["SerializableObject"] = None
    ) -> SerializableDataclass:
        """ Deserializes SerializedObject into correct type """

        obj = None
        serialized_obj = SerializableObject.extract_serialized_obj(msg)

        # load msg_type from module messages.py for deserialization
        if serialized_obj is not None:
            if not msg_type:
                module = importlib.import_module("messages")
                try:
                    msg_type = getattr(module, serialized_obj.c_type)
                except AttributeError as e:
                    _log.error(
                        f"Object type unknown: {serialized_obj.c_type}.",
                        exc_info=sys.exc_info(),
                    )
                    # raise WrongMessageFormatException(e).with_traceback(sys.exc_info()[2])
                    return obj

            obj = msg_type.from_json(serialized_obj.c_data)

            obj = convert_to_utc(obj)
        return obj

    @staticmethod
    def extract_serialized_obj(msg):
        try:
            serialized_obj = SerializedObject.from_json(msg)
            return serialized_obj
        except (KeyError, JSONDecodeError) as e:
            _log.error(
                f"Wrong message format: {msg}. Expected {{c_type: str, c_data: str}}.",
                exc_info=sys.exc_info(),
            )
            # raise WrongMessageFormatException(e).with_traceback(sys.exc_info()[2])
            # return SerializedObject(c_type="NoneTypeOrWrongMessageFormat", c_data="")

    @classmethod
    def extract_type(cls, msg: str) -> str:
        serialized_obj = cls.extract_serialized_obj(msg)
        return "NoneType" if serialized_obj is None else serialized_obj.c_type


@dataclass_json
@dataclass
class DemoData(SerializableObject):
    message: str
    date: datetime = None


@dataclass_json
@dataclass
class ControlMessage(SerializableObject):
    command: str
    args: List[str]
    kwargs: Dict


@dataclass_json
@dataclass
class PingControl(SerializableObject):
    pass


@dataclass_json
@dataclass
class ServiceStatus:
    name: str
    state: str


@dataclass_json
@dataclass
class CoreStatus:
    name: str
    state: str
    behaviours: List[ServiceStatus]


@dataclass_json
@dataclass
class PongControl(SerializableObject):
    status: CoreStatus
