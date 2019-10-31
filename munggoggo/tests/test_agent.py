import asyncio
import logging

import pytest

from agent import Agent
from handler import Control
from mode import Worker


@pytest.mark.asyncio
class TestConfiguration:
    async def test_config_set(self, caplog):
        caplog.set_level(logging.DEBUG)
        config = {
            "binding_keys": ['x.y'],
            "configure_rpc": True
        }

        identity = "core1"
        async with Agent(identity=identity, config=config) as a:
            a.logger.setLevel(logging.DEBUG)

            for record in caplog.records:
                assert record.levelname != 'ERROR'
            assert 'Registering RPC: example_rpc_method' in caplog.text
            assert "pubsub_queue, topics: ['x.y']" in caplog.text

    async def test_config_not_set(self, caplog):
        caplog.set_level(logging.DEBUG)
        config = {}

        identity = "core1"
        async with Agent(identity=identity, config=config) as a:
            a.logger.setLevel(logging.DEBUG)

            for record in caplog.records:
                assert record.levelname != 'ERROR'
            assert 'Registering RPC: example_rpc_method' not in caplog.text
            assert "pubsub_queue, topics: ['x.y']" not in caplog.text


@pytest.mark.skip("must be fixed")
@pytest.mark.asyncio
class TestAgentControl:
    async def test_agent_fixture(self, agent):
        assert await agent.dummy()

    async def test_control_handler_ping(self, agent):
        # agent_name.set(agent.identity)

        # Given control ping message
        msg = Control().schema.dumps(dict(command="ping"))

        # when control ping message is sent
        await agent.direct_send(msg=msg, msg_type='control', target='twagent')
        await asyncio.sleep(1)

    async def test_control_handler_stop(self, event_loop):
        # agent_name.set(agent.identity)
        identity = "twagent"
        async with Agent(identity=identity) as a:
            await a.start()

            # Given control ping message
            msg = Control().schema.dumps(dict(command="stop"))

            # when control stop message is sent
            await a.direct_send(msg=msg, msg_type='control', target=identity)
            await asyncio.sleep(1)

            control = a.get_behaviour('Control')
            # for task in control.tasks:
            #     await task
            for task in a.tasks:
                await task
            _ = None

    async def test_list_behaviour(self, agent):
        # it should start running
        assert agent.is_alive()

        control = agent.get_behaviour('Control')
        result = await control.rpc.rpc_call("list_behaviour")
        assert len(result) == 1
        assert result[0] == 'twagent.Control'
