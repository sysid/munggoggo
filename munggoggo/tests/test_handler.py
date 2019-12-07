import asyncio
import logging
import uuid
from datetime import datetime

import pytest
import pytz

from behaviour import Behaviour, EmptyBehav
from core import Core
from handler import Control, RmqMessageTypes
from messages import (
    ControlMessage,
    DemoObj,
    ListBehav,
    ListTraceStore,
    ManageBehav,
    Ping,
    PingControl,
    Pong,
    RpcError,
    Shutdown,
)
from settings import TIMEOUT


@pytest.mark.asyncio
class TestDispatcher:
    async def test_receive_dispatch_default_handler(self, behav, caplog):
        caplog.set_level(logging.DEBUG)
        # Given

        # when message of unknown type xxx is sent
        msg = "Hallo World"
        await behav.direct_send(msg=msg, msg_type="xxxx")
        await asyncio.sleep(0)  # relinquish cpu

        # then message must be handled by 'default' handler
        msg = await behav.receive(timeout=3)
        await behav.dispatch(msg)

        for record in caplog.records:
            assert record.levelname != "ERROR"
        assert "default_handler" in caplog.text


@pytest.mark.asyncio
class TestControl:
    async def test_handle_ping(self, core1, caplog):
        caplog.set_level(logging.DEBUG)

        # Given control ping message
        # msg = ControlMessage(command="ping", args=None, kwargs=None).serialize()
        msg = PingControl().serialize()

        # when control ping message is sent
        correlation_id = str(uuid.uuid4())
        await core1.direct_send(
            msg=msg,
            msg_type=RmqMessageTypes.CONTROL.name,
            target=core1.identity,
            correlation_id=correlation_id,
        )
        await asyncio.sleep(0.1)

        # then message must be handled by 'control' handler
        for record in caplog.records:
            assert record.levelname != "ERROR"
        assert "SystemHandler/Control: got command: PongControl" in caplog.text

    async def test_handle_ping_with_behav_fanout(self, core1):
        b = Behaviour(core1)
        b2 = Behaviour(core1)
        await core1.add_runtime_dependency(b)
        await core1.add_runtime_dependency(b2)

        assert b.started
        assert b2.started

        # Given control ping message and core with default behaviour
        msg = PingControl().serialize()

        # when control ping message is broadcast
        correlation_id = str(uuid.uuid4())
        await core1.fanout_send(
            msg=msg,
            msg_type=RmqMessageTypes.CONTROL.name,
            correlation_id=correlation_id,
        )
        await asyncio.sleep(0.2)

        # then response from itself with list of 2 behaviours
        dt, latest, correlation_id = core1.peers.latest()
        assert latest.name == "core1"
        assert len(latest.behaviours) == 2

    async def test_ping_pong_presence_fanout(self, ctrl, core1):
        # Given control ping message
        msg = PingControl().serialize()

        # when control ping message is broadcast
        correlation_id = str(uuid.uuid4())
        await ctrl.fanout_send(
            msg=msg,
            msg_type=RmqMessageTypes.CONTROL.name,
            correlation_id=correlation_id,
        )
        await asyncio.sleep(0.2)

        # then peers store should have pong answers from all peers (ctrl, core) and itself from startup
        assert len(ctrl.peers.all()) == 3
        identities = [status.name for (ts, status, cor_id) in ctrl.peers.all()]
        assert "ctrl" in identities
        assert "core1" in identities


@pytest.mark.asyncio
class TestRpcHandler:
    async def test_receive_dispatch_rpc_handler_ping(self, core1):
        obj = Ping(ping="ping")
        result = await core1.call(obj.to_rpc())
        assert isinstance(result, Pong)

    @pytest.mark.skipif(TIMEOUT is None, reason="would block without TIMEOUT")
    async def test_receive_dispatch_rpc_handler_ping_timeout(self, core1, mocker):
        mocker.patch("core.TIMEOUT", 0.1)

        obj = Ping(ping="ping")
        result = await core1.call(obj.to_rpc(), target="non-existing")
        assert isinstance(result, RpcError)
        assert "TimeoutError" in result.error

    @pytest.mark.skipif(TIMEOUT is None, reason="would block without TIMEOUT")
    async def test_unknown_rpc_request(self, core1, mocker):
        mocker.patch("core.TIMEOUT", 0.1)
        date = datetime(2019, 1, 1, tzinfo=pytz.UTC)
        obj = DemoObj(message="Hallo", date=date)
        result = await core1.call(obj.to_rpc(), target="non-existing")
        assert isinstance(result, RpcError)
        assert "TimeoutError" in result.error

    async def test_list_behav(self, core1):
        obj = ListBehav()
        result = await core1.call(obj.to_rpc())
        assert isinstance(result, ListBehav)
        assert len(result.behavs) == 0

    async def test_stop_start_behav_self(self, behav, mocker):
        mocker.patch("core.TIMEOUT", None)

        # given behaviour
        core = behav.core

        # when stop RPC command
        obj = ManageBehav(behav="Behaviour", command="stop",)
        result = await core.call(obj.to_rpc())

        # then result is stopped behav
        assert isinstance(result, ManageBehav)
        assert "init" in result.result
        assert not behav.started

        # when start commmand
        obj = ManageBehav(behav="Behaviour", command="start",)
        result = await core.call(obj.to_rpc())

        # then result is started behav
        assert isinstance(result, ManageBehav)
        assert behav.started

    async def test_stop_start_behav_via_ctrl_agent(self, behav, ctrl, mocker):
        mocker.patch("core.TIMEOUT", None)

        # given behaviour
        core = behav.core

        # when stop RPC command
        obj = ManageBehav(behav="Behaviour", command="stop",)
        result = await ctrl.call(obj.to_rpc(), target="core1")

        # then result is stopped behav
        assert isinstance(result, ManageBehav)
        assert "init" in result.result
        assert not behav.started

        # when start commmand
        obj = ManageBehav(behav="Behaviour", command="start",)
        result = await ctrl.call(obj.to_rpc(), target="core1")

        # then result is started behav
        assert isinstance(result, ManageBehav)
        assert behav.started

    async def test_list_trace_store(self, core1, mocker):
        mocker.patch("core.TIMEOUT", None)

        # given RPC class
        obj = ListTraceStore()

        # when called
        result = await core1.call(obj.to_rpc())

        # then TraceStore has got 3 incoming messages: ListTraceStore, ping, pong
        assert isinstance(result, ListTraceStore)
        assert len(result.traces) == 6
        assert result.traces[0][2] == "outgoing"
        assert result.traces[1][2] == "incoming"

    async def test_list_trace_store_filtered(self, core1, mocker):
        mocker.patch("core.TIMEOUT", None)

        # given RPC command
        obj = ListTraceStore(app_id=core1.identity, limit=1, category="incoming")

        # when called
        result = await core1.call(obj.to_rpc())

        # then
        assert len(result.traces) == 1

        # given RPC command
        obj = ListTraceStore(app_id="not-existing", limit=1, category="incoming")

        # when called
        result = await core1.call(obj.to_rpc())

        # then
        assert len(result.traces) == 0

    async def test_shutdown(self, core1, event_loop, mocker):
        mocker.patch("core.TIMEOUT", None)
        identity = "twagent"

        async with Core(identity=identity) as a:
            # when shutdown command is sent
            obj = Shutdown()
            result = await core1.call(obj.to_rpc())

            # then shutdown response is received
            assert isinstance(result, Shutdown)
            assert "initiated" in result.result
            await asyncio.sleep(2)
