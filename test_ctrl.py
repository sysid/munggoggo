import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from ctrl import list_peers, cli

"""
Cannot resolve at end of every test:
asyncio.streams.IncompleteReadError: 0 bytes read on a total of 1 expected bytes
has got nothing to do with timing of closedown of SqlAgent
"""


# spin up subprocess for entire session once
@pytest.fixture(scope="session", autouse=True)
def start_historian(request):
    path = Path("./example.db")
    if path.exists():
        os.remove(path)
    logfile = Path("./test_ctrl.log")
    if logfile.exists():
        os.remove(logfile)
    with open(logfile, "a") as log:
        log.write("some text, as header of the file\n")
        log.flush()  # <-- here's something not to forget!
        with subprocess.Popen(["./historian.py", "-d"], stdout=log, stderr=log) as proc:
            time.sleep(2)
            yield
            proc.kill()


def test_list_peers():
    start = datetime.now()
    runner = CliRunner()
    # given
    # when list-peers is called
    result = runner.invoke(cli, ["list-peers"], obj=dict(start=start))

    # then only self/Ctrl must be found
    assert result.exit_code == 0
    assert "Ctrl" in result.output
    print(result.output)


def test_broadcast():
    start = datetime.now()
    runner = CliRunner()

    # given correct serialized message
    msg = r'{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}"}'

    # when broadcast is called
    result = runner.invoke(cli, ["broadcast", msg, "CUSTOM"], obj=dict(start=start))

    # then only self/Ctrl must be found
    assert result.exit_code == 0


def test_broadcast_wrong_message_format(caplog):
    caplog.set_level(logging.DEBUG)

    start = datetime.now()
    runner = CliRunner()

    # given wrong serialized message
    msg = r"wrong_message_format"

    # when broadcast is called
    result = runner.invoke(cli, ["broadcast", msg, "CUSTOM"], obj=dict(start=start))

    # then ERROR must be logged by receiving agent
    assert result.exit_code == 0
    assert "[ERROR] Wrong message format" not in caplog.text


def test_send_message(caplog):
    caplog.set_level(logging.DEBUG)

    start = datetime.now()
    runner = CliRunner()

    # given correct serialized message
    msg = r'{"c_type": "DemoData", "c_data": "{\"message\": \"Hallo\", \"date\": 1546300800.0}"}'

    # when broadcast is called
    result = runner.invoke(
        cli, ["send-message", msg, "CUSTOM", "SqlAgent"], obj=dict(start=start)
    )

    # then only self/Ctrl must be found
    assert result.exit_code == 0


def test_call_stop(caplog):
    caplog.set_level(logging.DEBUG)

    start = datetime.now()
    runner = CliRunner()

    # given

    # when RPC stop is called
    result = runner.invoke(
        cli, ["call", "stop", "SqlAgent", "SqlBehav"], obj=dict(start=start)
    )

    # then only self/Ctrl must be found
    expected = r"result='SqlAgent.SqlBehav stopped: init'"
    assert result.exit_code == 0
    assert expected in result.output
