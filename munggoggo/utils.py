import asyncio
import logging
import os
from functools import wraps

from typing import NewType, Dict, List, Union, Any

import yaml

LogFmtStr = NewType('LogFmtStr', str)

JSONType = Union[
    Dict[str, Any],
    List[Any],
]

import logging


_log = logging.getLogger(__name__)
# log_fmt = r'%(asctime)-15s %(levelname)s %(name)s %(funcName)s:%(lineno)d %(message)s'
# logging.basicConfig(format=log_fmt, level=logging.DEBUG)


class AgentFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        if fmt is None:
            fmt = r'%(asctime)-15s %(levelname)s %(agent)s %(composite_name)s %(funcName)s:%(lineno)d: %(message)s'
            # fmt = r'%(asctime)-15s %(levelname)s %(name)s %(funcName)s:%(lineno)d %(message)s'
        super(AgentFormatter, self).__init__(fmt=fmt, datefmt=datefmt)

    # create augmented name for logger-name
    # noinspection PyMethodMayBeStatic
    def composite_name(self, record: logging.LogRecord) -> str:
        if record.name == 'agents.log':
            cname = '(%(processName)s %(process)d) %(name)s'
        else:
            cname = '() %(name)s'
        return cname % record.__dict__

    def format(self, record: logging.LogRecord) -> str:
        if 'agent' not in record.__dict__:
            record.__dict__['agent'] = ""
        if 'composite_name' not in record.__dict__:
            record.__dict__['composite_name'] = self.composite_name(record)
        return super(AgentFormatter, self).format(record)


class AgentFilter(logging.Filter):
    """add field 'agent' to LogRecord """

    def __init__(self, agent: str = ""):
        super(AgentFilter, self).__init__()
        self.agent = agent

    def filter(self, record):
        record.agent = self.agent
        return True


def setup_logging(level=logging.DEBUG, agent_name: str = None, agent_log_filter=None, init=True):
    root = logging.getLogger()
    if init:
        handlers = list(root.handlers)  # copy
        for handler in handlers:
            root.removeHandler(handler)
    if not root.handlers:
        handler = logging.StreamHandler()
        # handler.setFormatter(AgentFormatter())
        formatter = logging.Formatter('%(asctime)-15s %(levelname)-5s %(name)s %(message)s')
        handler.setFormatter(formatter)

        if agent_name:
            handler.addFilter(AgentFilter(agent=agent_name))
        elif agent_log_filter:
            handler.addFilter(agent_log_filter)

        root.addHandler(handler)
    root.setLevel(level)


def shield(func):
    """ shield decorator """

    async def awaiter(future):
        return await future

    @wraps(func)
    def wrap(*args, **kwargs):
        return wraps(func)(awaiter)(asyncio.shield(func(*args, **kwargs)))

    return wrap


def load_config(config_path):
    """Load a JSON-encoded configuration file."""
    if config_path is None:
        return {}

    if not os.path.exists(config_path):
        _log.error(f"Config file {config_path} does not exist, returning empty configuration.")
        return {}

    try:
        with open(config_path) as f:
            return yaml.safe_load(f.read())
    except yaml.YAMLError as e:
        _log.error(f"Error in config file: {e}")
        raise


