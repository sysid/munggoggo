import os
import asyncio
import logging
from asyncio import CancelledError, TimeoutError

import pytest
import sys
from async_timeout import timeout

from utils import AgentFormatter, AgentFilter, load_config


def get_logger(name: str, with_formatter=False) -> logging.Logger:
    _LOGGER = logging.getLogger(name)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(AgentFormatter())
    if with_formatter:
        handler.addFilter(AgentFilter('twagent_name'))
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.DEBUG)
    return _LOGGER


def test_agent_logger_with_filter():
    # given: root logger with AgentFormatter and Filter
    _LOGGER = get_logger("agenttestlogger", with_formatter=True)

    # when logging without extra dict
    _LOGGER.info("Test message.")

    # then "twagent_name" should be in output


def test_agent_formatter():
    # given: root logger with AgentFormatter
    _LOGGER = get_logger("agenttestlogger")

    # when logging with extra-dict and agent key
    _LOGGER.info("Test message.", extra=dict(agent="agent123"))

    # then 'agent123' should be in output (caveat: filter has got precedence)
    # TODO: caplog not working


def test_agent_formatter_with_defined_logger_name():
    # given logger with well defined name 'agents.log'
    _LOGGER = get_logger("agents.log")

    # when logging message
    _LOGGER.info("Test message.")

    # then logger name should be augmented: (MainProcess 51035) agents.log
    # TODO: caplog not working


def test_agent_formatter_with_adapter():
    # given: root logger with AgentFormatter and Adapter
    _LOGGER = get_logger("agenttestlogger")

    class A(object):

        def __init__(self):
            self.logger = logging.LoggerAdapter(_LOGGER, {'agent': 'agent123'})

        def process(self):
            self.logger.info('hello')

    # when logging message
    A().logger.info("Hallo Thomas")

    # then 'agent123' should be in output (caveat: filter has got precedence)
    # TODO: caplog not working


@pytest.mark.asyncio
async def test_timeout_catch_inner_exception():
    try:
        with timeout(0.5):
            try:
                await asyncio.sleep(1)
            except CancelledError as e:
                print("Cancelled Error")
    except TimeoutError as e:
        print("Timeout Error")


@pytest.mark.asyncio
async def test_timeout_catch_outer_exception():
    """ Gotcha: asyncio.Timeout NOT builtin.Timeout"""
    try:
        with timeout(0.5):
            await asyncio.sleep(1)
    except TimeoutError as e:
        print("Timeout Error")


@pytest.mark.parametrize('path', [
    f"{os.getenv('PROJ_DIR')}/munggoggo/tests/agent_config.yaml",
    f"{os.getenv('PROJ_DIR')}/munggoggo/tests/agent_config.json",
])
def test_load_config(path):
    # path = f"{os.getenv('PROJ_DIR')}/munggoggo/tests/agent_config.yaml"
    # config = load_config("agent_config.yaml")
    config = load_config(path)
    print(config)
    assert config == {'Key': 'value', 'Array': [1, 2, 'drei']}

