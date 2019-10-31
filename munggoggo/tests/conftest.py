import logging
import logging
import os
from pathlib import Path

import factory
import pytest
import time
from factory.fuzzy import FuzzyText
from pytest_factoryboy import register
from twpy import utcnow

import sys, os

sys.path.insert(0, f"{os.getenv('PROJ_DIR')}/munggoggo")
# print(sys.path)

from behaviour import Behaviour
from core import Core
from messages import TraceStoreMessage
from settings import BINDING_KEY_FANOUT, BINDING_KEY_TOPIC, SQLITE_PATH
from utils import setup_logging

setup_logging(level=logging.DEBUG)

logging.getLogger("aio_pika").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)


@pytest.fixture()
async def core1(event_loop):
    identity = "core1"
    async with Core(identity=identity) as a:
        a.logger.setLevel(logging.DEBUG)
        await a.channel.exchange_delete(BINDING_KEY_TOPIC)  # remove all topic bindings
        # await a.channel.exchange_delete(BINDING_KEY_FANOUT)
        yield a


@pytest.fixture()
async def core2(event_loop):
    identity = "core2"
    async with Core(identity=identity) as a:
        await a.channel.exchange_delete(BINDING_KEY_TOPIC)  # remove all topic bindings
        # await a.channel.exchange_delete(BINDING_KEY_FANOUT)
        yield a


@pytest.fixture()
async def ctrl(event_loop):
    identity = "ctrl"
    async with Core(identity=identity) as a:
        await a.channel.exchange_delete(BINDING_KEY_TOPIC)  # remove all topic bindings
        # await a.channel.exchange_delete(BINDING_KEY_FANOUT)
        yield a


@pytest.fixture()
async def init_rmq(event_loop):
    print(f"Init RMQ.")
    identity = "init_rmq"
    async with Core(identity=identity) as ctrl:
        await ctrl.channel.exchange_delete(BINDING_KEY_TOPIC)  # remove all topic bindings
        await ctrl.channel.exchange_delete(BINDING_KEY_FANOUT)


@pytest.fixture()
async def behav(core1):
    b = Behaviour(core1)
    await core1.add_runtime_dependency(b)

    yield b


@pytest.fixture()
async def pubsub_behav(core1):
    topics = ["x.y", "x.z", "a.#"]
    b = Behaviour(core1, binding_keys=topics)
    await core1.add_runtime_dependency(b)

    yield b
    # await asyncio.sleep(0.1)


@pytest.fixture()
async def rpc_behav(core1):
    b = Behaviour(core1, configure_rpc=True)
    await core1.add_runtime_dependency(b)

    yield b


class TraceStoreMessageFactory(factory.Factory):
    class Meta:
        model = TraceStoreMessage

    body = '{"key":"value"}'
    body_size = factory.LazyAttribute(lambda obj: len(obj.body))
    headers = {"header_key": "value"}
    content_type = 'json'
    content_encoding = ""
    delivery_mode = 1
    priority = None
    correlation_id = FuzzyText('uuid', length=8)
    reply_to = ""
    expiration = None
    message_id = factory.Sequence(lambda n: 'msg%d' % n)
    timestamp = factory.LazyFunction(time.time)
    user_id = 'guest'
    app_id = 'sender'
    cluster_id = None
    consumer_tag = 'consumer_tag'
    delivery_tag = None
    exchange = 'exchange'
    redelivered = False
    routing_key = 'routing_key'


register(TraceStoreMessageFactory)

@pytest.fixture()
def json_data_values():
    return [
        {"type": "type1", "ts": utcnow(), "data": {"a": "aaa", "b": "bbb"}},
        {"type": "type1", "ts": utcnow(), "data": {"a": "xxx", "b": "yyy"}},
    ]

@pytest.fixture()
def rm_sqlite():
    path = Path(SQLITE_PATH)
    if path.exists():
        os.remove(path)

