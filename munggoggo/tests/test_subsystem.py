import asyncio
import logging

import pytest
from aiormq import DeliveryError

import subsystem
from behaviour import EmptyBehav


@pytest.mark.asyncio
class TestPubSub:
    async def test_subscribe_wildcard_topic(self, pubsub_behav):
        # given

        # when messages are published to wildcard topic
        await pubsub_behav.publish("xxxxx", "a.x")
        await asyncio.sleep(0.1)  # relinquish cpu

        # then trace store has got the messages
        msg = pubsub_behav.core.traces.store[0][1]
        assert "xxxxx" in msg.body

    async def test_subscribe_two_topics(self, pubsub_behav):

        # Given two topics

        # when messages are published to both of them
        await pubsub_behav.publish("xxxxx", "x.y")
        await asyncio.sleep(0)  # relinquish cpu
        await pubsub_behav.publish("yyyyy", "x.z")
        await asyncio.sleep(0)  # relinquish cpu

        # then trace store has got both messages + ping/pong
        assert len(pubsub_behav.core.traces.store) == 4

    async def test_receive(self, pubsub_behav):
        # Given

        # when messages are published
        await pubsub_behav.publish("xxxxx", "x.y")
        await asyncio.sleep(0.1)  # relinquish cpu

        # then message must be in mailbox queue
        assert pubsub_behav.mailbox_size() == 1
        msg = await pubsub_behav.receive(timeout=3)
        assert "xxxxx" in msg.body.decode()


@pytest.mark.asyncio
class TestRPC:
    async def test_rpc_call(self, rpc_behav):

        result = await rpc_behav.rpc.rpc_call("example_rpc_method", x=30, y=2, flag=True)
        assert result == 60

    async def test_agent_rpc_non_existing_method(self, rpc_behav):

        # with pytest.raises(DeliveryError):
        #     response = await rpc_behav.rpc.rpc_call("not-existing", x=30, y=2)
        response = await rpc_behav.rpc.rpc_call("not-existing", x=30, y=2)
        assert isinstance(response, str)
        assert 'Illegal' in response


def test_list_rpc_methods():
    class A:
        @subsystem.expose
        def method(self):
            return True

        @property
        def exit_code(self):
            if False:
                return False
            else:
                raise ValueError

    a = A()
    assert subsystem.list_rpc_methods(a)[0].__name__ == "method"

    A.method.__rpc__ = False
    assert len(subsystem.list_rpc_methods(a)) == 0
